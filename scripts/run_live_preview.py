"""
03:15 PM Live Preview Screener & Adversarial Debate Runner.
Executes the full 5-tier quantitative pipeline before the 3:30 PM market close:
1. Liquidity Guard (ADTV >= 50L, T2T BE/BZ exclusion)
2. Vectorized VCP & Trend screening
3. Anti-Trap Shield & Shariah compliance filters
4. TradingView 26-Indicator Consensus Rating
5. LangGraph Bull / Bear / Judge Adversarial Debate with MemorySaver
6. Deterministic Risk Sizing & Telegram Trade Card Dispatch
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import json
import logging
import datetime
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
import yfinance as yf

from src.config.settings import settings, get_market_cap_tier
from src.notification.telegram_bot import is_system_halted, send_telegram_alert
from src.notification.trade_card import format_telegram_trade_card
from src.screening.liquidity_guard import check_liquidity_and_executability
from src.screening.shariah_filter import check_shariah_compliance
from src.screening.vcp_screener import evaluate_minervini_vcp_batch
from src.screening.anti_trap_shield import evaluate_anti_trap_shield
from src.screening.ml_predictor import evaluate_ml_probability
from src.screening.mean_reversion_screener import evaluate_mean_reversion, evaluate_mean_reversion_batch
from src.ingestion.screener_scraper import scrape_screener_fundamentals
from src.ingestion.macro_feeds import fetch_macro_weather_data
from src.ingestion.tradingview import get_tradingview_technical_ratings
from src.agents.debate_graph import build_debate_graph
from src.db.session import get_read_connection
from src.db.queue_writer import db_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_live_preview")

from src.utils.holidays import is_nse_holiday


def is_variant_candidate(symbol: str, scan_date: str) -> bool:
    """
    Stateless deterministic hashing: ~20% (1 in 5) of symbol+date pairs
    route to the experimental variant for Shadow Mode A/B evaluation.
    """
    import hashlib
    hash_int = int(hashlib.md5(f"{symbol}_{scan_date}".encode()).hexdigest(), 16)
    return (hash_int % 5) == 0


def get_active_universe(conn, as_of_date: Optional[datetime.date] = None):
    """
    Fetches the active trading universe from bhavcopy_daily.
    Enforces 5-day active trading date window, positive volume filter,
    and excludes delisted stocks (with NULL safety).
    """
    ref_date = as_of_date or datetime.date.today()
    return conn.execute("""
        SELECT b.symbol, MAX(b.series) as series, MAX(b.circuit_band_pct) as cb
        FROM bhavcopy_daily b
        WHERE b.symbol IS NOT NULL
          AND b.trade_date >= (CURRENT_DATE - INTERVAL '5 days')
          AND b.total_traded_qty > 0
          AND b.symbol NOT IN (
              SELECT symbol FROM delisted_stocks
              WHERE symbol IS NOT NULL AND delisted_date IS NOT NULL AND delisted_date <= CURRENT_DATE
          )
        GROUP BY b.symbol
    """).fetchall()

def run_live_preview_pipeline():
    logger.info("=" * 70)
    logger.info("STARTING 03:15 PM LIVE PREVIEW SCREENER & MULTI-AGENT DEBATE")
    logger.info("=" * 70)

    # 1. Kill-switch check
    if is_system_halted():
        logger.warning("System is currently HALTED by kill-switch. Aborting 03:15 PM run.")
        return

    # 2. Market Day Check
    today_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).date()
    if today_ist.weekday() >= 5:
        logger.info(f"Today is weekend ({today_ist.strftime('%A')}). Skipping run.")
        return

    if is_nse_holiday(today_ist):
        logger.info(f"Today ({today_ist}) is an NSE Trading Holiday. Skipping run.")
        return

    # 3. Macro Radar Ingestion (Read from DB pre-market snapshot first)
    macro_data = None
    try:
        with get_read_connection() as conn:
            row = conn.execute("""
                SELECT us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                       usdinr_price, usdinr_pct_change, polymarket_risk_score,
                       market_regime, macro_weather_score, target_cash_exposure_pct, source
                FROM macro_weather 
                WHERE scan_date = ? OR scan_date = CURRENT_DATE
                ORDER BY scan_date DESC LIMIT 1
            """, (today_ist,)).fetchone()
            if row:
                macro_data = {
                    "us_vix": row[0], "sp500_pct_change": row[1],
                    "crude_oil_price": row[2], "crude_oil_pct_change": row[3],
                    "usdinr_price": row[4], "usdinr_pct_change": row[5],
                    "polymarket_risk_score": row[6], "market_regime": row[7],
                    "macro_weather_score": row[8], "target_cash_exposure_pct": row[9],
                    "source": row[10],
                }
                logger.info(f"Macro Radar (from DB): Regime={macro_data['market_regime']}, Weather Score={macro_data['macro_weather_score']}")
    except Exception as e:
        logger.warning(f"Could not read macro_weather from DB: {e}")

    if macro_data is None:
        logger.warning("macro_weather DB row absent today — falling back to live fetch.")
        macro_data = fetch_macro_weather_data()
        logger.info(f"Macro Radar (live fetch): Regime={macro_data.get('market_regime')}")

    # 4. Fetch Universe from DuckDB
    with get_read_connection() as conn:
        symbols_data = get_active_universe(conn, as_of_date=today_ist)
        
    symbols = [row[0] for row in symbols_data]
    series_map = {row[0]: row[1] or "EQ" for row in symbols_data}
    circuit_band_map = {}
    for row in symbols_data:
        sym = row[0]
        ser = row[1] or "EQ"
        if ser in ["BE", "BZ", "SM"]:
            band = float(row[2]) if row[2] is not None else 5.0
            band = min(band, 5.0)
        else:
            band = float(row[2]) if row[2] is not None else 20.0
        circuit_band_map[sym] = band

    if not symbols:
        logger.warning("No historical symbols found in bhavcopy_daily. Please run EOD ingestion first.")
        return

    # 5. Pass 1: Vectorized Liquidity Filter in DuckDB (~0.4s)
    logger.info("Evaluating liquidity guard across active universe...")
    liquid_symbols = []
    liquid_metrics_map = {}
    market_cap_tier_map = {}

    with get_read_connection() as conn:
        # Pre-fetch cached market cap from fundamentals_cache if available
        cached_mcap_map = {}
        try:
            fc_rows = conn.execute("SELECT symbol, fundamentals_json FROM fundamentals_cache").fetchall()
            for s, fj in fc_rows:
                try:
                    fj_data = json.loads(fj) if isinstance(fj, str) else fj
                    if "market_cap_crores" in fj_data and fj_data["market_cap_crores"]:
                        cached_mcap_map[s] = float(fj_data["market_cap_crores"])
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not load fundamentals_cache for market cap: {e}")

        # Batch query 30-day median turnover and latest price in DuckDB for all active symbols in 1 query (~0.3s)
        adtv_rows = conn.execute("""
            WITH ranked AS (
                SELECT symbol, total_traded_val, close_price,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date DESC) as rn
                FROM bhavcopy_daily
                WHERE total_traded_qty > 0 AND series != 'BE' AND series != 'BZ'
            )
            SELECT symbol, 
                   MEDIAN(total_traded_val) as adtv_30d_median,
                   COUNT(*) as data_days,
                   MAX(CASE WHEN rn=1 THEN close_price END) as last_close
            FROM ranked
            WHERE rn <= 30
            GROUP BY symbol
        """).fetchall()
        adtv_map = {r[0]: {"adtv": float(r[1] or 0), "days": int(r[2] or 0), "close": float(r[3] or 0)} for r in adtv_rows}

        for symbol in symbols:
            actual_series = series_map.get(symbol, "EQ")
            if actual_series in ["BE", "BZ", "T2T"]:
                continue
            circuit_band = circuit_band_map.get(symbol, 20.0)
            if circuit_band < 5.0:
                continue

            sym_adtv_info = adtv_map.get(symbol, {"adtv": 0.0, "days": 0, "close": 0.0})
            if sym_adtv_info["close"] < 10.0 or sym_adtv_info["days"] < 10:
                continue

            if symbol in cached_mcap_map and cached_mcap_map[symbol] > 0:
                tier = get_market_cap_tier(cached_mcap_map[symbol])
            else:
                t_val = sym_adtv_info["adtv"]
                if t_val >= 500_000_000.0:
                    tier = "LARGE"
                elif t_val >= 150_000_000.0:
                    tier = "MID"
                elif t_val >= 25_000_000.0:
                    tier = "SMALL"
                else:
                    tier = "SMALL"

            market_cap_tier_map[symbol] = tier
            adtv_floor = 2500000.0  # ₹25 Lakhs floor
            if sym_adtv_info["adtv"] >= adtv_floor:
                liquid_symbols.append(symbol)
                liquid_metrics_map[symbol] = {
                    "symbol": symbol,
                    "series": actual_series,
                    "adtv_20d_rupees": sym_adtv_info["adtv"],
                    "data_days": sym_adtv_info["days"],
                    "circuit_band_pct": circuit_band,
                    "market_cap_tier": tier
                }

        logger.info(f"Liquidity Filter complete: {len(liquid_symbols)} liquid symbols out of {len(symbols)} active universe.")

        # 6. Pass 2: Technical Screener on DuckDB History
        vcp_results_list = evaluate_minervini_vcp_batch(
            liquid_symbols, conn, batch_size=500
        )
        vcp_results_map = {res["symbol"]: res for res in vcp_results_list}
        mr_results_map = evaluate_mean_reversion_batch(liquid_symbols, conn)

        raw_candidates = []
        for symbol in liquid_symbols:
            vcp_candidate = vcp_results_map.get(symbol)
            mr_signal = mr_results_map.get(symbol, False)

            has_vcp = vcp_candidate is not None
            if not (has_vcp or mr_signal):
                continue

            cur_price = vcp_candidate["current_price"] if vcp_candidate else adtv_map.get(symbol, {}).get("close", 100.0)
            trig_price = vcp_candidate["trigger_price"] if vcp_candidate else cur_price * 1.015
            pat_type = vcp_candidate["pattern_type"] if vcp_candidate else "MEAN_REVERSION"
            cand_tier = market_cap_tier_map.get(symbol, "SMALL")

            raw_candidates.append({
                "symbol": symbol,
                "candidate": {
                    "pattern_type": pat_type,
                    "current_price": cur_price,
                    "trigger_price": trig_price,
                    "regime_bypass_size_reduction": vcp_candidate.get("regime_bypass_size_reduction", 1.0) if vcp_candidate else 1.0
                },
                "circuit_band": circuit_band_map.get(symbol, 20.0),
                "market_cap_tier": cand_tier,
                "ml_prob": 0.0,
                "mr_signal": mr_signal,
                "has_vcp": has_vcp,
                "l_metrics": liquid_metrics_map.get(symbol, {})
            })

        logger.info(f"Pass 2 preliminary technical screen found {len(raw_candidates)} candidates.")

        # Sort candidates to prioritize high-conviction setups before ML scoring
        raw_candidates.sort(key=lambda x: (
            x["has_vcp"],
            x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
            x["candidate"]["current_price"] / max(x["candidate"]["trigger_price"], 1e-6),
            x["l_metrics"].get("adtv_20d_rupees", 0.0)
        ), reverse=True)

        # Defer ML probability: evaluate only the top 15 candidates before Shariah screening
        candidate_pool = raw_candidates[:15]
        for item in candidate_pool:
            item["ml_prob"] = evaluate_ml_probability(item["symbol"], conn)

    # 7. Pass 3: Targeted Live 3:15 PM Ticks via Yahoo Finance ONLY for candidates (~1-2s)
    if candidate_pool:
        logger.info(f"Fetching live 3:15 PM ticks for {len(candidate_pool)} technical candidates...")
        cand_tickers_ns = [f"{c['symbol']}.NS" for c in candidate_pool]
        try:
            live_raw = yf.download(cand_tickers_ns, period="1d", progress=False)
            if live_raw is not None and not live_raw.empty:
                for item in candidate_pool:
                    sym = item["symbol"]
                    ns_sym = f"{sym}.NS"
                    try:
                        if len(cand_tickers_ns) == 1:
                            c_val = live_raw['Close'].iloc[-1]
                        elif ns_sym in live_raw['Close']:
                            c_val = live_raw['Close'][ns_sym].iloc[-1]
                        else:
                            c_val = None
                        if c_val is not None and pd.notna(c_val) and float(c_val) > 0:
                            item["candidate"]["current_price"] = float(c_val)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not fetch live ticks for candidates: {e}")

    # 8. Pass 4: Sort and Shariah Screen (Top-N with Cache First)
    candidate_pool.sort(key=lambda x: (
        x["has_vcp"],
        x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
        x["ml_prob"]
    ), reverse=True)

    shariah_compliant_pool = []
    # Evaluate candidates (up to top 15 in pool) until 3 compliant candidates found
    for item in candidate_pool:
        sym = item["symbol"]
        try:
            funds = scrape_screener_fundamentals(sym)
            sec = funds.get("sector_name", "")
            is_sh, sh_reason = check_shariah_compliance(funds, sector_name=sec)
            if is_sh:
                item["fundamentals"] = funds
                item["sector_name"] = sec
                shariah_compliant_pool.append(item)
                if len(shariah_compliant_pool) >= 3:
                    break
            else:
                logger.info(f"[{sym}] Pre-debate exclusion by Shariah filter: {sh_reason}")
        except Exception as e:
            logger.warning(f"Failed Shariah check for {sym}: {e}")
            continue

    top_candidates = shariah_compliant_pool[:3]
    logger.info(f"Pass 1 complete. Found {len(shariah_compliant_pool)} compliant technical candidates. Proceeding with Top {len(top_candidates)}.")
    for item in top_candidates:
        logger.info(f"Top Candidate: {item['symbol']} | Tier: {item.get('market_cap_tier')} | Pattern: {item['candidate']['pattern_type']} | Trigger: ₹{item['candidate']['trigger_price']:.2f}")

    # 9. Pass 5: Shariah, Anti-Trap, TradingView, and LangGraph Multi-Agent Debate
    debate_app = build_debate_graph()
    approved_candidates = []

    for item in top_candidates:
        symbol = item["symbol"]
        try:
            candidate = item["candidate"]
            ml_prob = item["ml_prob"]
            has_vcp = item["has_vcp"]
            mr_signal = item["mr_signal"]
            l_metrics = item["l_metrics"]
            tier = item.get("market_cap_tier", "SMALL")

            fundamentals = item.get("fundamentals") or scrape_screener_fundamentals(symbol)
            mcap_cr = fundamentals.get("market_cap_crores")
            if mcap_cr is not None and float(mcap_cr) > 0:
                tier = get_market_cap_tier(float(mcap_cr))
                item["market_cap_tier"] = tier

            sector_name = item.get("sector_name") or fundamentals.get("sector_name", "")
            logger.info(f"[{symbol}] Debating Candidate | Tier: {tier} (Market Cap: ₹{fundamentals.get('market_cap_crores', 0):,.0f} Cr)")

            passed_trap, trap_reason, trap_metrics = evaluate_anti_trap_shield(
                symbol, candidate, fundamentals, live_price=candidate["current_price"]
            )
            if not passed_trap:
                logger.info(f"[{symbol}] Excluded by strict Anti-Trap Shield (ML Override disabled): {trap_reason}")
                continue

            # Fetch TradingView Ratings ($0 Free Tier)
            tv_ratings = get_tradingview_technical_ratings(symbol)

            # Calculate True 14-Day ATR
            with get_read_connection() as conn:
                atr_df = conn.execute("""
                    SELECT high_price, low_price, prev_close 
                    FROM bhavcopy_daily 
                    WHERE symbol = ? 
                    ORDER BY trade_date DESC LIMIT 15
                """, (symbol,)).df()
            
            if len(atr_df) >= 14:
                atr_df['tr1'] = atr_df['high_price'] - atr_df['low_price']
                atr_df['tr2'] = (atr_df['high_price'] - atr_df['prev_close']).abs()
                atr_df['tr3'] = (atr_df['low_price'] - atr_df['prev_close']).abs()
                real_atr = float(atr_df[['tr1', 'tr2', 'tr3']].max(axis=1).head(14).mean())
            else:
                real_atr = max(candidate["current_price"] * 0.025, 1.0)

            # Prepare State for LangGraph
            cand_macro = dict(macro_data) if macro_data else {}
            bypass_factor = candidate.get("regime_bypass_size_reduction", 1.0)
            if bypass_factor < 1.0:
                cand_macro["target_cash_exposure_pct"] = max(cand_macro.get("target_cash_exposure_pct", 0.0), 50.0)

            # Sanitize fundamentals dictionary values to native python types
            clean_fundamentals = {}
            for k, v in {**fundamentals, "atr_14": float(real_atr)}.items():
                if hasattr(v, 'item'):
                    clean_fundamentals[k] = v.item()
                else:
                    clean_fundamentals[k] = v

            state_input = {
                "symbol": str(symbol),
                "scan_date": today_ist.isoformat(),
                "current_price": float(candidate["current_price"]),
                "trigger_price": float(candidate["trigger_price"]),
                "market_cap_tier": str(tier),
                "adtv_20d": float(l_metrics.get("adtv_20d_rupees", 5000000.0)),
                "circuit_band": float(item.get("circuit_band", 20.0)),
                "fundamentals": clean_fundamentals,
                "macro_weather": cand_macro,
                "historical_memory": [],
                "tv_technical_rating": tv_ratings,
                "messages": [],
                "macro_context": f"Regime: {macro_data.get('market_regime')}",
                "current_verdict": None,
                "vcp_signal": bool(has_vcp),
                "ml_probability": float(ml_prob),
                "mr_signal": bool(mr_signal),
                "shield_passed": bool(passed_trap),
                "macro_regime_score": float(macro_data.get("macro_weather_score", 0.8)),
                "bull_thesis": None,
                "bear_risks": None,
                "judge_synthesis": None,
                "conviction_score": -1.0,  # Sentinel: -1.0 indicates unscored / graph failed
                "clarification_count": 0,
                "risk_verdict": None,
                "suggested_shares": 0,
                "stop_loss_price": 0.0,
                "target_1_price": 0.0,
                "target_2_price": 0.0,
                "risk_reward_ratio": 0.0,
                "portfolio_allocation_pct": 0.0,
                "rejection_reason": None,
                "telegram_card_markdown": None,
                "manual_review_payload": None
            }

            # Execute LangGraph Debate Graph with Checkpoint Thread
            try:
                config = {"configurable": {"thread_id": f"debate_{symbol}_{today_ist.isoformat()}"}}
                final_state = debate_app.invoke(state_input, config=config)
            except Exception as e:
                logger.error(f"LangGraph debate execution failed for {symbol}: {e}")
                final_state = dict(state_input)
                final_state["rejection_reason"] = f"Debate graph execution failed: {e}"

            # Determine status for Second Opinion Consensus Gate
            initial_status = final_state.get("risk_verdict") or "REJECT"
            if initial_status in ["APPROVE", "APPROVE_WITH_WARNING", "REDUCE_SIZE"]:
                initial_status = "PENDING_REVIEW"
                
            # Shadow Mode A/B Routing (P6-6)
            ab_group = "control"
            ml_cutoff = settings.ML_CUTOFF_CONTROL
            if settings.SHADOW_MODE and is_variant_candidate(symbol, today_ist.isoformat()):
                ab_group = "variant"
                ml_cutoff = settings.ML_CUTOFF_VARIANT
                logger.info(f"[{symbol}] Routed to SHADOW variant (ab_group='variant', ml_cutoff={ml_cutoff})")

            cand_id = f"{symbol}_{today_ist.isoformat()}"
            db_write("""
                INSERT OR REPLACE INTO screener_candidates (
                    id, scan_date, symbol, sector, pattern_type, trigger_price, adtv_20d, market_cap_tier, circuit_band, is_t2t, 
                    ml_probability, mr_signal, shield_passed, status, rejection_reason, ab_group
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, ?, ?, ?, ?, ?, ?);
            """, (
                cand_id, today_ist.isoformat(), str(symbol), str(sector_name), str(candidate["pattern_type"]), float(candidate["trigger_price"]), 
                float(l_metrics.get("adtv_20d_rupees", 0)), str(tier), float(item.get("circuit_band", 20.0)), float(ml_prob), bool(mr_signal), bool(passed_trap), str(initial_status),
                str(final_state.get("rejection_reason") or ""),
                str(ab_group)
            ), sync=True)

            if initial_status == "PENDING_REVIEW":
                logger.info(f"[{symbol}] Running Second Opinion Consensus Gate synchronously (ab_group={ab_group}, ml_cutoff={ml_cutoff})...")
                
                # Joint consensus gate: Judge Conviction >= 7.0 AND XGBoost ML Probability >= ml_cutoff
                conv_val = final_state.get("conviction_score")
                try:
                    conviction = float(conv_val) if conv_val is not None else -1.0
                except (ValueError, TypeError):
                    conviction = -1.0
                graph_completed = conviction >= 0.0
                if not graph_completed:
                    logger.error(f"[{symbol}] Debate graph failed to produce a valid judge verdict (conviction={conviction}). Failing closed.")
                gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob >= ml_cutoff)
                
                if gate_approved:
                    logger.info(f"[{symbol}] Second Opinion APPROVED (Conviction: {conviction:.1f}/10, ML Prob: {ml_prob:.2f}).")
                    
                    # Breakout confirmation: price must reach or exceed trigger price
                    if candidate["current_price"] < candidate["trigger_price"]:
                        logger.info(f"[{symbol}] Current price ₹{candidate['current_price']:.2f} < Trigger price ₹{candidate['trigger_price']:.2f}. Breakout not confirmed yet. Skipping order execution.")
                        db_write("UPDATE screener_candidates SET status = 'AWAITING_TRIGGER' WHERE id = ?", (cand_id,))
                        continue

                    # Size trade strictly via Deterministic Risk Arbiter
                    try:
                        suggested_qty = int(final_state.get("suggested_shares", 0))
                    except (ValueError, TypeError):
                        suggested_qty = 0
                    if suggested_qty <= 0:
                        logger.warning(f"[{symbol}] Risk Arbiter suggested 0 shares. Skipping paper order execution.")
                        db_write("UPDATE screener_candidates SET status = 'SIZING_REJECTED' WHERE id = ?", (cand_id,))
                    else:
                        # Execute Paper Trade with Risk Arbiter calculated quantity
                        from src.execution.order_manager import execute_paper_trade
                        trade_id = execute_paper_trade(
                            symbol=symbol, 
                            price=candidate["trigger_price"], 
                            atr=real_atr, 
                            quantity=suggested_qty,
                            sector=sector_name,
                            initial_stop=final_state.get("stop_loss_price"),
                            target_1=final_state.get("target_1_price"),
                            target_2=final_state.get("target_2_price"),
                            candidate_id=cand_id
                        )
                        
                        if trade_id:
                            logger.info(f"[{symbol}] Trade executed with ID {trade_id}. Updating candidate status to APPROVED.")
                            db_write("UPDATE screener_candidates SET status = 'APPROVED' WHERE id = ?", (cand_id,))
                            approved_candidates.append(symbol)
                            
                            # Dispatch Telegram
                            try:
                                from src.notification.telegram_bot import send_telegram_trade_card
                                send_telegram_trade_card(final_state)
                            except Exception as tg_err:
                                logger.warning(f"Telegram dispatch failed: {tg_err}")
                        else:
                            logger.warning(f"[{symbol}] Order placement rejected by execution engine (circuit band / slippage clamp).")
                            db_write("UPDATE screener_candidates SET status = 'EXECUTION_REJECTED' WHERE id = ?", (cand_id,))
                else:
                    logger.info(f"[{symbol}] VETOED by Second Opinion Consensus Gate (Conviction: {conviction:.1f}/10, ML Prob: {ml_prob:.2f}).")
                    db_write("UPDATE screener_candidates SET status = 'VETOED' WHERE id = ?", (cand_id,))

            db_write("""
                INSERT OR REPLACE INTO debate_transcripts (
                    id, symbol, debate_date, macro_regime_score, bull_thesis, bear_risks,
                    judge_synthesis, tv_technical_rating, conviction_score, risk_manager_verdict,
                    suggested_shares, stop_loss, target_1, target_2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"deb_{symbol}_{today_ist.isoformat()}",
                str(symbol),
                today_ist.isoformat(),
                float(macro_data.get("macro_weather_score", 0.8)),
                str(final_state.get("bull_thesis") or ""),
                str(final_state.get("bear_risks") or ""),
                str(final_state.get("judge_synthesis") or ""),
                str(tv_ratings.get("recommendation", "NEUTRAL")),
                float(final_state.get("conviction_score", 0.0) if final_state.get("conviction_score") is not None else -1.0),
                str(final_state.get("risk_verdict") or "REJECT"),
                int(final_state.get("suggested_shares", 0)),
                float(final_state.get("stop_loss_price", 0.0)),
                float(final_state.get("target_1_price", 0.0)),
                float(final_state.get("target_2_price", 0.0))
            ), sync=True)
        except Exception as cand_err:
            logger.error(f"Error processing candidate {symbol}: {cand_err}", exc_info=True)
            continue

    logger.info(f"03:15 PM Live Preview completed successfully. Approved candidates: {approved_candidates}")

    # Dispatch guaranteed 3:15 PM Sentinel Scan Summary to Telegram
    try:
        from src.portfolio.state import get_portfolio_state
        port_state = get_portfolio_state()
        core_equity = port_state.get("core_equity", 1000000.0)
    except Exception:
        core_equity = 1000000.0

    regime_val = macro_data.get("market_regime") if macro_data else 0
    regime_desc = "🟢 Bullish (Regime 1 / Uptrend)" if regime_val != 0 else "🔴 Defensive (Regime 0 / Market Correction)"
    
    summary_msg = (
        f"📊 <b>AlphaSentinel 3:15 PM Scan Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Date:</b> {today_ist.strftime('%d-%b-%Y')}\n"
        f"• <b>Market Regime:</b> {regime_desc}\n"
        f"• <b>Liquid Universe:</b> {len(liquid_symbols)} stocks\n"
        f"• <b>Setups Identified:</b> {len(candidate_pool)}\n"
        f"• <b>Top Setups Debated:</b> {len(top_candidates)}\n"
        f"• <b>Trades Approved:</b> {len(approved_candidates)} ({', '.join(approved_candidates) if approved_candidates else 'None'})\n"
        f"• <b>Portfolio Capital:</b> ₹{core_equity:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if approved_candidates:
        summary_msg += f"✅ <b>Active Orders:</b> Placed in paper portfolio. See Trade Cards."
    else:
        summary_msg += f"🛡️ <b>Capital Preserved:</b> All gates held firm. No forced trades."

    try:
        from src.notification.telegram_bot import send_telegram_alert
        send_telegram_alert(summary_msg)
        logger.info("Dispatched 3:15 PM summary alert to Telegram.")
    except Exception as tg_err:
        logger.warning(f"Failed to dispatch daily summary alert to Telegram: {tg_err}")


if __name__ == "__main__":
    run_live_preview_pipeline()

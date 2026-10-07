"""
Deterministic Python Risk Arbiter & Position Sizer.
Pure mathematical risk allocation without LLM hallucination risk.
Uses ATR-based volatility sizing and Macro Target Cash Exposure caps.
"""

import math
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Load strategy config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "strategy.yaml"

def get_risk_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f)
            return cfg.get("risk", {}) if cfg else {}
    except Exception:
        return {}

RISK_CONFIG = get_risk_config()


from src.db.session import get_read_connection

def calculate_deterministic_risk_and_position(
    symbol: str,
    trigger_price: float,
    current_price: Optional[float] = None,
    atr_14: float = 0.0,
    base_low_10d: Optional[float] = None,
    regime_risk_pct: Optional[float] = None,
    circuit_band: float = 20.0,
    macro_weather: Optional[Dict[str, Any]] = None,
    portfolio_capital_rupees: float = 10_00_000.0, # Standard ₹10 Lakhs paper portfolio
    adtv_20d: float = 0.0,
    sector: str = "",
    market_cap_tier: str = "LARGE",
    open_positions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Calculates exact mathematical position sizing, structural stop-loss, and profit targets.
    Enforces risk parity allocation (1.0% risk / 16.0% max pos), portfolio heat ceiling (5.0%),
    Macro Agent's cash exposure limits, ADTV constraints, and Sector caps.
    """
    if trigger_price <= 0:
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "stop_distance_pct": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": 0.0,
            "rejection_reason": "Trigger price <= 0",
            "reason": "Trigger price <= 0",
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    if current_price is None or current_price <= 0:
        current_price = trigger_price
    if macro_weather is None:
        macro_weather = {}

    # P2-4: Dynamically bind portfolio capital to live core equity
    live_core_equity = None
    default_caps = (10_00_000.0, float(getattr(settings, "ALGO_ALLOCATED_CAPITAL", 10_00_000.0)))
    if portfolio_capital_rupees in default_caps and portfolio_capital_rupees > 0:
        try:
            import src.portfolio.state as portfolio_state
            pstate = portfolio_state.get_portfolio_state()
            if pstate and "core_equity" in pstate and pstate["core_equity"] > 0:
                live_core_equity = pstate["core_equity"]
                portfolio_capital_rupees = live_core_equity
        except Exception as e:
            logger.warning(f"Could not load live core equity for arbiter: {e}")

    core_equity = live_core_equity if (live_core_equity is not None and portfolio_capital_rupees > 0) else portfolio_capital_rupees

    # Load open positions for count, sector, and heat monitoring
    if open_positions is not None:
        open_pos_list = list(open_positions)
    else:
        open_pos_list = []
        try:
            with get_read_connection() as conn:
                rows = conn.execute("""
                    SELECT symbol, entry_price, quantity, current_ltp, trailing_stop_loss, risk_rupees, sector
                    FROM positions 
                    WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')
                """).fetchall()
                for r in rows:
                    open_pos_list.append({
                        "symbol": r[0],
                        "entry_price": float(r[1] or 0.0),
                        "quantity": int(r[2] or 0),
                        "current_ltp": float(r[3] or r[1] or 0.0),
                        "stop_loss": float(r[4] or 0.0),
                        "risk_rupees": float(r[5] or 0.0),
                        "sector": str(r[6] or "")
                    })
        except Exception as e:
            logger.warning(f"Could not load open positions from DB: {e}")

    # Helper function to compute rupee risk of a position
    def _get_pos_risk_rupees(pos: Dict[str, Any], equity: float) -> float:
        if "risk_rupees" in pos and pos["risk_rupees"] is not None and float(pos["risk_rupees"]) > 0:
            return float(pos["risk_rupees"])
        if "risk_pct" in pos and pos["risk_pct"] is not None and float(pos["risk_pct"]) > 0:
            return float(pos["risk_pct"]) * equity / 100.0
        if "heat_pct" in pos and pos["heat_pct"] is not None and float(pos["heat_pct"]) > 0:
            return float(pos["heat_pct"]) * equity / 100.0
        qty = float(pos.get("quantity", 0) or pos.get("suggested_shares", 0) or 0)
        entry = float(pos.get("entry_price", 0.0) or pos.get("current_ltp", 0.0) or pos.get("trigger_price", 0.0) or 0.0)
        sl = float(pos.get("trailing_stop_loss", 0.0) or pos.get("stop_loss", 0.0) or pos.get("stop_loss_price", 0.0) or 0.0)
        if qty > 0 and entry > sl and sl > 0:
            return qty * (entry - sl)
        return 0.0

    existing_open_risk_rupees = sum(_get_pos_risk_rupees(p, core_equity) for p in open_pos_list)
    current_heat_pct = (existing_open_risk_rupees / core_equity) * 100.0 if core_equity > 0 else 0.0

    # 0. Portfolio & Sector Open Position Limits
    risk_cfg = get_risk_config()
    max_total_open = risk_cfg.get("max_open_positions", 6)
    max_sector_open = risk_cfg.get("max_positions_per_sector", risk_cfg.get("sector_exposure", {}).get("max_open_positions", 2))
    max_sector_pct = risk_cfg.get("sector_exposure", {}).get("max_portfolio_pct", 25.0) / 100.0

    if len(open_pos_list) >= max_total_open:
        rej_msg = f"Portfolio max open positions limit reached: {len(open_pos_list)} open positions (max {max_total_open})."
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "stop_distance_pct": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": round(current_heat_pct, 2),
            "rejection_reason": rej_msg,
            "reason": rej_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    if sector:
        if open_positions is not None:
            sector_open_count = sum(1 for p in open_pos_list if p.get("sector") == sector)
            sector_capital = sum(
                float(p.get("entry_price", p.get("current_ltp", 0.0)) or 0.0) * float(p.get("quantity", 0) or 0)
                for p in open_pos_list if p.get("sector") == sector
            )
        else:
            try:
                with get_read_connection() as conn:
                    sector_open_count = conn.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM positions WHERE sector = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED')) +
                            (SELECT COUNT(*) FROM screener_candidates WHERE sector = ? AND scan_date = CURRENT_DATE AND status IN ('APPROVED', 'PENDING_REVIEW'))
                    """, (sector, sector)).fetchone()[0]
                    sector_capital = conn.execute("""
                        SELECT COALESCE(SUM(entry_price * quantity), 0.0) 
                        FROM positions 
                        WHERE sector = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED')
                    """, (sector,)).fetchone()[0]
            except Exception:
                sector_open_count = sum(1 for p in open_pos_list if p.get("sector") == sector)
                sector_capital = sum(
                    float(p.get("entry_price", p.get("current_ltp", 0.0)) or 0.0) * float(p.get("quantity", 0) or 0)
                    for p in open_pos_list if p.get("sector") == sector
                )

        if sector_open_count >= max_sector_open:
            rej_msg = f"Sector cap reached: {max_sector_open} open/pending positions in {sector}."
            return {
                "symbol": symbol,
                "verdict": "REJECT",
                "suggested_shares": 0,
                "shares_to_buy": 0,
                "trigger_price": trigger_price,
                "stop_loss_price": 0.0,
                "stop_distance_pct": 0.0,
                "target_1_price": 0.0,
                "target_2_price": 0.0,
                "risk_reward_ratio": 0.0,
                "risk_rupees": 0.0,
                "risk_per_trade_pct": 0.0,
                "total_capital_deployed": 0.0,
                "position_value_rupees": 0.0,
                "portfolio_allocation_pct": 0.0,
                "portfolio_heat_pct_after": round(current_heat_pct, 2),
                "rejection_reason": rej_msg,
                "reason": rej_msg,
                "is_paper_trade": settings.PAPER_TRADING_MODE
            }

        if (sector_capital + (portfolio_capital_rupees * 0.10)) > (portfolio_capital_rupees * max_sector_pct):
            rej_msg = f"Sector capital cap reached: ₹{sector_capital:.2f} deployed in {sector} (max {max_sector_pct:.0%})."
            return {
                "symbol": symbol,
                "verdict": "REJECT",
                "suggested_shares": 0,
                "shares_to_buy": 0,
                "trigger_price": trigger_price,
                "stop_loss_price": 0.0,
                "stop_distance_pct": 0.0,
                "target_1_price": 0.0,
                "target_2_price": 0.0,
                "risk_reward_ratio": 0.0,
                "risk_rupees": 0.0,
                "risk_per_trade_pct": 0.0,
                "total_capital_deployed": 0.0,
                "position_value_rupees": 0.0,
                "portfolio_allocation_pct": 0.0,
                "portfolio_heat_pct_after": round(current_heat_pct, 2),
                "rejection_reason": rej_msg,
                "reason": rej_msg,
                "is_paper_trade": settings.PAPER_TRADING_MODE
            }

    # 0.5 Realized Compounding Base & Equity Insolvency Guard
    realized_pnl = 0.0
    open_pos_val = 0.0
    if open_positions is not None:
        open_pos_val = sum(
            float(p.get("current_ltp", p.get("entry_price", 0.0)) or 0.0) * float(p.get("quantity", 0) or 0)
            for p in open_pos_list
        )
    else:
        try:
            with get_read_connection() as conn:
                res = conn.execute("SELECT COALESCE(SUM(realized_pnl), 0) FROM positions WHERE status IN ('TARGET_REACHED', 'STOPPED_OUT', 'CLOSED', 'TARGET_1_TRIMMED')").fetchone()
                realized_pnl = res[0] if res and res[0] else 0.0
                open_pos_val = conn.execute("SELECT COALESCE(SUM(current_ltp * quantity), 0.0) FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')").fetchone()[0]
        except Exception:
            pass

    core_equity = live_core_equity if live_core_equity is not None else (portfolio_capital_rupees + realized_pnl)
    if core_equity <= 0.0:
        rej_msg = f"Portfolio equity exhausted: core equity is ₹{core_equity:.2f}."
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "stop_distance_pct": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": 0.0,
            "rejection_reason": rej_msg,
            "reason": rej_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    available_cash = core_equity - open_pos_val
    if available_cash < (core_equity * 0.05):
        rej_msg = f"Portfolio cash floor reached: Available cash ₹{available_cash:.2f} is under 5% reserve."
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "stop_distance_pct": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": round(current_heat_pct, 2),
            "rejection_reason": rej_msg,
            "reason": rej_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    portfolio_capital_rupees = core_equity

    # 1. Stop-Loss Calculation
    if atr_14 is None or math.isnan(atr_14) or atr_14 <= 0:
        atr_14 = trigger_price * 0.03

    atr_mult = float(risk_cfg.get("stop_loss", {}).get("atr_multiplier", 2.5))
    max_pct_stop = float(risk_cfg.get("stop_loss", {}).get("max_pct_stop", risk_cfg.get("max_pct_stop", 8.0)))

    # Structural stop formula:
    # Stop = max(Base_Low_10d - 0.25 * ATR_14, Trigger - 2.5 * ATR_14) when base_low_10d is provided,
    # else Trigger - 2.5 * ATR_14 (with clean backward-compatible fallback).
    atr_stop = round(trigger_price - (atr_mult * atr_14), 2)
    if base_low_10d is not None and not math.isnan(base_low_10d) and base_low_10d > 0:
        structural_stop = round(base_low_10d - (0.25 * atr_14), 2)
        stop_loss = round(max(structural_stop, atr_stop), 2)
    else:
        stop_loss = atr_stop

    risk_per_share = round(trigger_price - stop_loss, 2)
    if risk_per_share <= 0:
        risk_per_share = round(trigger_price * 0.05, 2) # 5% minimum buffer
        stop_loss = round(trigger_price - risk_per_share, 2)

    stop_distance_pct = round((risk_per_share / trigger_price) * 100.0, 2)

    # 2. Profit Targets
    t1_rr = float(risk_cfg.get("profit_targets", {}).get("target_1_rr", 2.0))
    t2_rr = float(risk_cfg.get("profit_targets", {}).get("target_2_rr", 3.5))
    target_1 = round(trigger_price + (t1_rr * risk_per_share), 2)
    target_2 = round(trigger_price + (t2_rr * risk_per_share), 2)
    risk_reward_ratio = round((target_1 - trigger_price) / risk_per_share, 2)

    # Reject candidate ONLY if stop distance > 8.0% (max_pct_stop)
    if (trigger_price - stop_loss) / trigger_price > (max_pct_stop / 100.0):
        rejection_msg = f"Stock is too volatile. Required stop loss ({stop_loss}) exceeds max allowed stop of {max_pct_stop:.1f}% ({stop_distance_pct:.2f}%)."
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": stop_loss,
            "stop_distance_pct": stop_distance_pct,
            "target_1_price": target_1,
            "target_2_price": target_2,
            "risk_reward_ratio": risk_reward_ratio,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": round(current_heat_pct, 2),
            "rejection_reason": rejection_msg,
            "reason": rejection_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    # 3. Maximum Capital Allocation per Trade
    if regime_risk_pct is not None:
        risk_per_trade_pct = float(regime_risk_pct)
    else:
        risk_per_trade_pct = float(risk_cfg.get("risk_per_trade_pct", 1.0))

    if risk_per_trade_pct <= 0.0:
        rejection_msg = "Risk per trade is 0.0% (Market regime RISK_OFF). Zero new entries permitted."
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": stop_loss,
            "stop_distance_pct": stop_distance_pct,
            "target_1_price": target_1,
            "target_2_price": target_2,
            "risk_reward_ratio": risk_reward_ratio,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": round(current_heat_pct, 2),
            "rejection_reason": rejection_msg,
            "reason": rejection_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    max_trade_risk_rupees = core_equity * (risk_per_trade_pct / 100.0)
    raw_shares = math.floor(max_trade_risk_rupees / risk_per_share)

    # Max position value: allow up to 16.0% (max_position_size_pct)
    max_pos_pct = float(risk_cfg.get("max_position_size_pct", 16.0)) / 100.0
    max_position_value = core_equity * max_pos_pct
    max_shares_by_value = math.floor(max_position_value / trigger_price)

    # Cap total position size based on market cap tier ADTV participation
    mcap = market_cap_tier.upper() if market_cap_tier else "LARGE"
    adtv_caps = risk_cfg.get("adtv_participation_caps", {})
    cap_pct = adtv_caps.get(mcap, adtv_caps.get("DEFAULT", risk_cfg.get("max_adtv_participation_pct", 1.5)))
    adtv_pct = cap_pct / 100.0
        
    if adtv_20d > 0:
        max_shares_by_adtv = math.floor((adtv_20d * adtv_pct) / trigger_price)
    else:
        # If adtv_20d is omitted or 0, attempt lookup from bhavcopy_daily
        try:
            with get_read_connection() as conn:
                res = conn.execute("""
                    SELECT MEDIAN(total_traded_val) 
                    FROM (SELECT total_traded_val FROM bhavcopy_daily WHERE symbol = ? ORDER BY trade_date DESC LIMIT 20)
                """, (symbol,)).fetchone()
                if res and res[0] and res[0] > 0:
                    adtv_20d = float(res[0])
                    max_shares_by_adtv = math.floor((adtv_20d * adtv_pct) / trigger_price)
                else:
                    max_shares_by_adtv = max_shares_by_value
        except Exception:
            max_shares_by_adtv = max_shares_by_value
    
    shares = min(raw_shares, max_shares_by_value, max_shares_by_adtv)

    # 4. Apply Macro Weather Cash Exposure Factor
    target_cash_exposure = macro_weather.get("target_cash_exposure_pct", 0.0)
    exposure_multiplier = max(0.0, min(1.0, (100.0 - target_cash_exposure) / 100.0))
    adjusted_shares = math.floor(shares * exposure_multiplier)

    # 4.1 CPPI Drawdown Control (P6-2)
    try:
        from src.risk.cppi import calculate_cppi_exposure
        from src.portfolio.state import get_portfolio_state
        p_state = get_portfolio_state()
        cppi_mult = calculate_cppi_exposure(
            core_equity=p_state.get("core_equity", core_equity),
            lifetime_hwm=p_state.get("lifetime_hwm", core_equity)
        )
        if cppi_mult < 0.9999:
            logger.info(f"[{symbol}] CPPI Drawdown scalar applied: {cppi_mult:.4f}")
            adjusted_shares = math.floor(adjusted_shares * cppi_mult)
    except Exception as e:
        logger.warning(f"[{symbol}] CPPI evaluation failed: {e}. Keeping current sizing.")

    # 4.2 Portfolio Volatility Targeting (P6-3)
    if adjusted_shares > 0:
        try:
            from src.risk.vol_target import calculate_volatility_scalar
            candidate_val = adjusted_shares * trigger_price
            open_pos_map = {
                p.get("symbol", f"pos_{i}"): float(p.get("current_ltp", p.get("entry_price", 0.0)) or 0.0) * float(p.get("quantity", 0) or 0)
                for i, p in enumerate(open_pos_list)
            }
            vol_scalar = calculate_volatility_scalar(
                open_positions=open_pos_map,
                candidate_symbol=symbol,
                candidate_value=candidate_val,
                core_equity=core_equity,
                fallback_scalar=0.75,
            )
            if vol_scalar < 0.9999:
                logger.info(f"[{symbol}] Volatility target scalar applied: {vol_scalar:.4f}")
                adjusted_shares = math.floor(adjusted_shares * vol_scalar)
        except Exception as e:
            logger.warning(f"[{symbol}] Volatility targeting evaluation failed: {e}. Keeping current sizing.")

    # 4.3 Portfolio Heat Ceiling Constraint (Requirement R1)
    # Aggregate open stop risk across open positions + candidate risk <= max_portfolio_heat_pct (5.0%)
    max_portfolio_heat_pct = float(risk_cfg.get("max_portfolio_heat_pct", 5.0))
    max_heat_rupees = core_equity * (max_portfolio_heat_pct / 100.0)
    available_risk_budget_rupees = max_heat_rupees - existing_open_risk_rupees

    if available_risk_budget_rupees <= 0.0:
        rej_msg = (
            f"Portfolio heat ceiling reached: Existing open risk ({current_heat_pct:.2f}%) "
            f"meets or exceeds max allowed {max_portfolio_heat_pct:.1f}%. Zero additional risk permitted."
        )
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "shares_to_buy": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": stop_loss,
            "stop_distance_pct": stop_distance_pct,
            "target_1_price": target_1,
            "target_2_price": target_2,
            "risk_reward_ratio": risk_reward_ratio,
            "risk_rupees": 0.0,
            "risk_per_trade_pct": 0.0,
            "total_capital_deployed": 0.0,
            "position_value_rupees": 0.0,
            "portfolio_allocation_pct": 0.0,
            "portfolio_heat_pct_after": round(current_heat_pct, 2),
            "rejection_reason": rej_msg,
            "reason": rej_msg,
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }

    desired_candidate_risk_rupees = adjusted_shares * risk_per_share
    if desired_candidate_risk_rupees > available_risk_budget_rupees:
        max_shares_by_heat = math.floor(available_risk_budget_rupees / risk_per_share)
        if max_shares_by_heat <= 0:
            rej_msg = (
                f"Portfolio heat ceiling reached: Remaining risk budget ₹{available_risk_budget_rupees:.2f} "
                f"insufficient to allocate 1 share of {symbol} (risk/share ₹{risk_per_share:.2f})."
            )
            return {
                "symbol": symbol,
                "verdict": "REJECT",
                "suggested_shares": 0,
                "shares_to_buy": 0,
                "trigger_price": trigger_price,
                "stop_loss_price": stop_loss,
                "stop_distance_pct": stop_distance_pct,
                "target_1_price": target_1,
                "target_2_price": target_2,
                "risk_reward_ratio": risk_reward_ratio,
                "risk_rupees": 0.0,
                "risk_per_trade_pct": 0.0,
                "total_capital_deployed": 0.0,
                "position_value_rupees": 0.0,
                "portfolio_allocation_pct": 0.0,
                "portfolio_heat_pct_after": round(current_heat_pct, 2),
                "rejection_reason": rej_msg,
                "reason": rej_msg,
                "is_paper_trade": settings.PAPER_TRADING_MODE
            }
        logger.info(
            f"[{symbol}] Heat ceiling regulation: scaling shares from {adjusted_shares} to {max_shares_by_heat} "
            f"to enforce max portfolio heat <= {max_portfolio_heat_pct:.1f}%."
        )
        adjusted_shares = max_shares_by_heat

    # 5. Circuit Band Warning Check & Final Verdict
    if adjusted_shares <= 0:
        verdict = "REJECT"
        adjusted_shares = 0
        reason = "Calculated position size is 0 due to extreme risk, tight macro cash caps, heat ceiling, or ADTV limits."
    elif circuit_band is None or math.isnan(circuit_band):
        verdict = "REJECT"
        adjusted_shares = 0
        reason = "Missing or NaN circuit band data. Fails closed to protect against unknown liquidity/circuit lock risk."
    elif circuit_band <= 2.0:
        verdict = "REJECT"
        adjusted_shares = 0
        reason = "2% Circuit Band poses extreme gap-and-lock liquidity risk. Hard Rejection."
    elif circuit_band <= 5.0:
        adjusted_shares = math.floor(adjusted_shares * 0.5)
        if adjusted_shares <= 0:
            verdict = "REJECT"
            adjusted_shares = 0
            reason = "5% Circuit Band reduction reduced position size to 0 shares. Trade rejected."
        else:
            verdict = "REDUCE_SIZE"
            reason = "5% Circuit Band poses severe gap-and-lock liquidity risk. Halved position size."
    elif circuit_band <= 10.0:
        verdict = "APPROVE_WITH_WARNING"
        reason = "Passed quantitative gates. WARNING: 10% Circuit Band poses moderate lock limit risk."
    else:
        verdict = "APPROVE"
        reason = f"Passed all quantitative gates. Risk budget ₹{max_trade_risk_rupees:.0f} strictly respected."

    total_capital_deployed = adjusted_shares * trigger_price
    allocation_pct = round((total_capital_deployed / core_equity) * 100.0, 2)
    candidate_risk_rupees = round(adjusted_shares * risk_per_share, 2)
    heat_after_rupees = existing_open_risk_rupees + candidate_risk_rupees
    portfolio_heat_pct_after = round((heat_after_rupees / core_equity) * 100.0, 2)

    result = {
        "symbol": symbol,
        "verdict": verdict,
        "suggested_shares": adjusted_shares,
        "shares_to_buy": adjusted_shares,
        "trigger_price": trigger_price,
        "stop_loss_price": stop_loss,
        "stop_distance_pct": stop_distance_pct,
        "target_1_price": target_1,
        "target_2_price": target_2,
        "risk_reward_ratio": risk_reward_ratio,
        "risk_rupees": candidate_risk_rupees,
        "risk_per_trade_pct": risk_per_trade_pct,
        "total_capital_deployed": total_capital_deployed,
        "position_value_rupees": total_capital_deployed,
        "portfolio_allocation_pct": allocation_pct,
        "portfolio_heat_pct_after": portfolio_heat_pct_after,
        "rejection_reason": reason,
        "reason": reason,
        "is_paper_trade": settings.PAPER_TRADING_MODE
    }

    if settings.PAPER_TRADING_MODE:
        logger.info(
            f"[PAPER TRADE] {symbol} | Verdict: {verdict} | "
            f"Qty: {adjusted_shares} @ ₹{trigger_price} | "
            f"SL: ₹{stop_loss} | T1: ₹{target_1} | T2: ₹{target_2} | "
            f"Capital: ₹{total_capital_deployed:.0f} | Heat: {portfolio_heat_pct_after:.2f}%"
        )

    return result


def evaluate_eod_risk_offload(
    symbol: str,
    current_shares: int,
    current_price: float,
    circuit_band: float,
    macro_weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    3:00 PM EOD Risk Offloader.
    Evaluates if an open position needs to be scaled down before market close
    due to overnight gap risks (e.g., macro weather turning bearish or
    tight circuit bands increasing gap-and-lock probability).
    """
    offload_reason = ""
    suggested_shares = current_shares
    
    # Check 1: Macro Weather Risk Off
    target_cash_exposure = macro_weather.get("target_cash_exposure_pct", 0.0)
    if target_cash_exposure > 0.0:
        # We need to know how much cash we currently have to determine if we must offload
        # A proper fix requires calculating total portfolio equity. 
        # For now, if macro targets a very high cash position (e.g. >= 50%), we defensively reduce shares
        if target_cash_exposure >= 50.0:
            multiplier = max(0.0, min(1.0, (100.0 - target_cash_exposure) / 100.0))
            new_shares = math.floor(current_shares * multiplier)
            if new_shares < suggested_shares:
                suggested_shares = new_shares
                offload_reason = f"Macro risk high (target cash {target_cash_exposure}%)."
            
    # Check 2: Thin Circuit Bands (Overnight Gap-and-Lock risk)
    if circuit_band is not None and circuit_band <= 5.0:
        new_shares = math.floor(suggested_shares * 0.5)
        if new_shares < suggested_shares:
            suggested_shares = new_shares
            offload_reason += f" Thin circuit band ({circuit_band}%) poses gap risk."
            
    if suggested_shares < current_shares:
        verdict = "REDUCE_POSITION"
    else:
        verdict = "HOLD"
        
    return {
        "symbol": symbol,
        "verdict": verdict,
        "current_shares": current_shares,
        "suggested_shares": suggested_shares,
        "shares_to_sell": current_shares - suggested_shares,
        "offload_reason": offload_reason.strip()
    }

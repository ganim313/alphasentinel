"""
06:00 PM EOD Reconciliation Pass.
Ingests official NSE Bhavcopy, calculates Delivery %, reconciles open/partially closed positions,
executes 50% partial exits at Target 1 (3R) with Breakeven ratchets, Target 2 (6R) runner exits,
and records Shariah purification logs on realized profitable trades.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.notification.telegram_bot import is_system_halted
from src.db.session import get_read_connection
from src.db.queue_writer import db_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_eod_reconciliation")


def log_shariah_purification(trade_id: str, symbol: str, profit: float, conn=None) -> None:
    """
    Logs mandatory Shariah purification amount for realized profitable trades.
    Extracts impure income ratio from fundamentals_cache (defaulting to 5% safe ceiling).
    """
    if profit <= 0.0:
        return
        
    impure_ratio = 0.05
    try:
        if conn is not None:
            row = conn.execute("SELECT fundamentals_json FROM fundamentals_cache WHERE symbol = ?", (symbol,)).fetchone()
            if row:
                fdata = json.loads(row[0])
                impure_ratio = float(fdata.get("interest_income_ratio", 0.05))
        else:
            with get_read_connection() as r_conn:
                row = r_conn.execute("SELECT fundamentals_json FROM fundamentals_cache WHERE symbol = ?", (symbol,)).fetchone()
                if row:
                    fdata = json.loads(row[0])
                    impure_ratio = float(fdata.get("interest_income_ratio", 0.05))
    except Exception as e:
        logger.debug(f"Could not load custom impure ratio for {symbol}: {e}. Defaulting to 5.0%.")

    purification_amt = round(profit * impure_ratio, 2)
    pur_id = f"pur_{trade_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        db_write("""
            INSERT OR REPLACE INTO purification_log (
                id, trade_id, symbol, exit_date, net_profit, impure_income_ratio, purification_amount, is_donated
            ) VALUES (?, ?, ?, CURRENT_DATE, ?, ?, ?, FALSE);
        """, (pur_id, trade_id, symbol, profit, impure_ratio, purification_amt), sync=True)
        logger.info(f"🕌 Logged Shariah purification for {symbol}: Gross Profit ₹{profit:.2f}, Impure Ratio {impure_ratio:.2%}, Mandatory Donation ₹{purification_amt:.2f}")
    except Exception as err:
        logger.warning(f"Failed to record purification log for {symbol}: {err}")


def run_eod_reconciliation_pipeline():
    if is_system_halted():
        logger.warning("System is currently HALTED. Running EOD reconciliation in DEFENSIVE EXIT/RECONCILIATION mode.")

    logger.info("Executing 06:00 PM EOD Reconciliation Pipeline...")

    # 0. Download & Ingest Official NSE Bhavcopy (Backfill missed days)
    from src.ingestion.bhavcopy import ingest_bhavcopy_dataframe, fetch_bhavcopy_with_retry_and_fallback
    
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    
    try:
        # Determine the last ingested date to prevent survivorship bias gaps
        with get_read_connection() as conn:
            last_date_row = conn.execute("SELECT MAX(trade_date) FROM bhavcopy_daily").fetchone()
            last_date = last_date_row[0] if last_date_row and last_date_row[0] else (today - timedelta(days=1))
        
        # Generate list of dates to fetch (from last_date + 1 up to today)
        dates_to_fetch = []
        curr_date = last_date + timedelta(days=1)
        while curr_date <= today:
            if curr_date.weekday() < 5: # Monday to Friday
                dates_to_fetch.append(curr_date)
            curr_date += timedelta(days=1)
            
        for d in dates_to_fetch:
            try:
                df_bhav = fetch_bhavcopy_with_retry_and_fallback(d)
                if df_bhav is not None and not df_bhav.empty:
                    ingest_bhavcopy_dataframe(df_bhav, d)
                else:
                    logger.warning(f"Could not retrieve data for {d} via Bhavcopy or yfinance fallback.")
            except Exception as e:
                logger.warning(f"Error processing Bhavcopy for {d}: {e}")
                
    except Exception as e:
        logger.error(f"Critical failure during Bhavcopy ingestion loop: {e}")
        from src.notification.telegram_bot import set_system_halt_state, send_telegram_safe_halt_alarm
        set_system_halt_state(True, f"Bhavcopy Ingestion Failure: {e}")
        send_telegram_safe_halt_alarm(f"Bhavcopy Ingestion Failure: {e}")

    # 1. Update Open & Partially Closed Paper Positions based on latest Close price in DuckDB
    with get_read_connection() as conn:
        positions_to_reconcile = conn.execute("""
            SELECT p.id, p.symbol, p.entry_price, p.trailing_stop_loss, p.target_1, p.target_2,
                   b.close_price, b.low_price, b.high_price, b.lower_circuit, b.upper_circuit,
                   p.quantity, b.open_price, p.status, COALESCE(p.realized_pnl, 0.0),
                   p.entry_date, b.trade_date
            FROM positions p
            JOIN bhavcopy_daily b ON p.symbol = b.symbol
            WHERE p.status IN ('OPEN', 'TARGET_1_TRIMMED') 
              AND b.trade_date = (SELECT MAX(trade_date) FROM bhavcopy_daily) 
              AND b.trade_date >= p.entry_date;
        """).fetchall()

    logger.info(f"Reconciling {len(positions_to_reconcile)} active positions...")
    
    for row in positions_to_reconcile:
        pos_id = row[0]
        symbol = row[1]
        entry_p = row[2]
        stop_loss = row[3]
        target_1 = row[4]

        if len(row) >= 17:
            target_2 = row[5]
            ltp = row[6]
            low_p = row[7]
            high_p = row[8]
            lower_c = row[9]
            upper_c = row[10]
            quantity = row[11]
            open_p = row[12]
            pos_status = row[13]
            prior_realized_pnl = row[14]
            entry_date = row[15]
            trade_date = row[16]
        elif len(row) >= 15:
            target_2 = row[5]
            ltp = row[6]
            low_p = row[7]
            high_p = row[8]
            lower_c = row[9]
            upper_c = row[10]
            quantity = row[11]
            open_p = row[12]
            pos_status = row[13]
            prior_realized_pnl = row[14]
            entry_date = None
            trade_date = None
        elif len(row) >= 12:
            target_2 = None
            ltp = row[5]
            low_p = row[6]
            high_p = row[7]
            lower_c = row[8]
            upper_c = row[9]
            quantity = row[10]
            open_p = row[11]
            pos_status = 'OPEN'
            prior_realized_pnl = 0.0
            entry_date = None
            trade_date = None
        else: # 11 elements from test fixtures
            target_2 = None
            ltp = row[5]
            low_p = row[6]
            high_p = row[7]
            lower_c = row[8]
            upper_c = row[9]
            quantity = row[10]
            open_p = None
            pos_status = 'OPEN'
            prior_realized_pnl = 0.0
            entry_date = None
            trade_date = None

        if any(v is None for v in (ltp, low_p, high_p, stop_loss, target_1, entry_p)):
            logger.warning(f"Missing core price data for {symbol}, skipping reconciliation.")
            continue
            
        # Circuit Lock Shield (Microstructure Trap Fix)
        if lower_c is not None and (ltp <= lower_c or low_p <= lower_c):
            # If we touched lower circuit and closed there, it's highly likely a gap-and-lock or intraday lock.
            if ltp <= lower_c:
                logger.warning(f"🔒 CIRCUIT LOCK: {symbol} is locked at lower circuit (LTP: {ltp}). No exits possible. Marking for EOD closure / AMO exit.")
                db_write("UPDATE positions SET status = 'MARKED_FOR_CLOSURE', current_ltp = ?, unrealized_pnl = ? WHERE id = ?", 
                         (ltp, round((ltp - entry_p) * (quantity if quantity is not None else 1), 2), pos_id))
                continue # Bypass all stop-loss and target simulated fills because order book is frozen
        elif upper_c is not None and (ltp >= upper_c or high_p >= upper_c):
            if ltp >= upper_c:
                logger.info(f"🔒 CIRCUIT LOCK: {symbol} is locked at UPPER circuit (LTP: {ltp}). Order book frozen. Holding position.")

        # Case A: Stop Loss Hit (Pessimistic Fill Enforced for Data Integrity)
        # Skip stop loss check on entry day (entry at 3:15 PM was not subjected to morning low)
        is_same_day_entry = (entry_date is not None and trade_date is not None and str(entry_date) == str(trade_date))
        if not is_same_day_entry and low_p <= stop_loss:
            actual_exit = min(open_p, stop_loss) if open_p else stop_loss
            exit_pnl = round((actual_exit - entry_p) * (quantity if quantity is not None else 1), 2)
            total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
            
            db_write("""
                UPDATE positions 
                SET status = 'STOPPED_OUT', exit_price = ?, exit_date = CURRENT_DATE, realized_pnl = ?, current_ltp = ?
                WHERE id = ?;
            """, (actual_exit, total_realized_pnl, ltp, pos_id))
            
            # P3-4: Update agent_memory on stop loss
            ret_pct = round((actual_exit - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
            db_write("""
                UPDATE agent_memory 
                SET outcome_label = 'LOSS', triple_barrier_label = -1, outcome_3d_pct = ?
                WHERE symbol = ? AND outcome_label IS NULL;
            """, (ret_pct, symbol))
            
            logger.warning(f"Position {symbol} HIT STOP LOSS. Low: ₹{low_p}, Executed at: ₹{actual_exit} (SL: ₹{stop_loss}) | PnL: ₹{exit_pnl:.2f}")
            try:
                from src.notification.telegram_bot import send_telegram_alert
                import html
                send_telegram_alert(
                    f"🛑 <b>STOP LOSS HIT: {html.escape(symbol)}</b>\n"
                    f"Exit Price: ₹{actual_exit:.2f} (SL: ₹{stop_loss:.2f})\n"
                    f"Realized PnL: ₹{total_realized_pnl:,.2f}"
                )
            except Exception:
                pass

            if exit_pnl > 0:
                log_shariah_purification(pos_id, symbol, exit_pnl)
            continue

        # Case B: Target 2 Hit on a Partially Closed Runner Position
        if pos_status == 'TARGET_1_TRIMMED' and target_2 is not None and high_p >= target_2:
            actual_exit = max(open_p, target_2) if open_p else target_2
            exit_pnl = round((actual_exit - entry_p) * (quantity if quantity is not None else 1), 2)
            total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
            
            db_write("""
                UPDATE positions 
                SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE, realized_pnl = ?, current_ltp = ?
                WHERE id = ?;
            """, (actual_exit, total_realized_pnl, ltp, pos_id))
            
            # P3-4: Update agent_memory on target 2 hit
            ret_pct = round((actual_exit - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
            db_write("""
                UPDATE agent_memory 
                SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
                WHERE symbol = ? AND outcome_label IS NULL;
            """, (ret_pct, symbol))
            
            logger.info(f"🏆 Position {symbol} HIT TARGET 2 (runner exit) at ₹{high_p}, Executed at: ₹{actual_exit} | Remaining PnL: ₹{exit_pnl:.2f}")
            try:
                from src.notification.telegram_bot import send_telegram_alert
                import html
                send_telegram_alert(
                    f"🏆 <b>TARGET 2 RUNNER HIT: {html.escape(symbol)}</b>\n"
                    f"Exit Price: ₹{actual_exit:.2f} (T2: ₹{target_2:.2f})\n"
                    f"Total Position Realized PnL: ₹{total_realized_pnl:,.2f}"
                )
            except Exception:
                pass

            if exit_pnl > 0:
                log_shariah_purification(pos_id, symbol, exit_pnl)
            continue

        # Case C: Target 1 Hit (Only if position is OPEN and has NOT already been trimmed)
        if pos_status == 'OPEN' and high_p >= target_1:
            actual_exit = max(open_p, target_1) if open_p else target_1
            
            # If Target 2 is configured and quantity > 1, execute 50% partial trim and ratchet SL to Breakeven
            if target_2 is not None and quantity is not None and quantity > 1:
                half_qty = quantity // 2
                rem_qty = quantity - half_qty
                partial_pnl = round((actual_exit - entry_p) * half_qty, 2)
                total_realized_pnl = round(prior_realized_pnl + partial_pnl, 2)
                
                # Ratchet stop-loss to Breakeven (+0.5% friction buffer)
                breakeven_sl = round(entry_p * 1.005, 2)
                new_sl = max(stop_loss, breakeven_sl)
                new_unrealized_pnl = round((ltp - entry_p) * rem_qty, 2)
                
                db_write("""
                    UPDATE positions 
                    SET status = 'TARGET_1_TRIMMED', quantity = ?, trailing_stop_loss = ?,
                        realized_pnl = ?, unrealized_pnl = ?, current_ltp = ?
                    WHERE id = ?;
                """, (rem_qty, new_sl, total_realized_pnl, new_unrealized_pnl, ltp, pos_id))
                
                logger.info(
                    f"🎯 Position {symbol} HIT TARGET 1 at ₹{high_p}! "
                    f"Trimmed 50% ({half_qty} shares @ ₹{actual_exit:.2f}, PnL: ₹{partial_pnl:.2f}). "
                    f"Trailing SL on remaining {rem_qty} shares ratcheted to Breakeven: ₹{new_sl:.2f}."
                )
                try:
                    from src.notification.telegram_bot import send_telegram_alert
                    import html
                    send_telegram_alert(
                        f"🎯 <b>TARGET 1 TRIM: {html.escape(symbol)}</b>\n"
                        f"Trimmed 50% ({half_qty} shares @ ₹{actual_exit:.2f})\n"
                        f"Realized PnL: ₹{partial_pnl:,.2f}\n"
                        f"Trailing SL ratcheted to ₹{new_sl:.2f} on {rem_qty} runner shares."
                    )
                except Exception:
                    pass

                if partial_pnl > 0:
                    log_shariah_purification(pos_id, symbol, partial_pnl)
            else:
                # Single target full liquidation
                exit_pnl = round((actual_exit - entry_p) * (quantity if quantity is not None else 1), 2)
                total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
                db_write("""
                    UPDATE positions 
                    SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE, realized_pnl = ?, current_ltp = ?
                    WHERE id = ?;
                """, (actual_exit, total_realized_pnl, ltp, pos_id))
                
                # P3-4: Update agent_memory on target 1 hit (full exit)
                ret_pct = round((actual_exit - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
                db_write("""
                    UPDATE agent_memory 
                    SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
                    WHERE symbol = ? AND outcome_label IS NULL;
                """, (ret_pct, symbol))
                
                logger.info(f"🎯 Position {symbol} HIT TARGET 1 at ₹{high_p}, Executed at: ₹{actual_exit} (Target: ₹{target_1})")
                try:
                    from src.notification.telegram_bot import send_telegram_alert
                    import html
                    send_telegram_alert(
                        f"🎯 <b>TARGET 1 REACHED: {html.escape(symbol)}</b>\n"
                        f"Closed full position ({quantity} shares @ ₹{actual_exit:.2f})\n"
                        f"Realized PnL: ₹{total_realized_pnl:,.2f}"
                    )
                except Exception:
                    pass

                if exit_pnl > 0:
                    log_shariah_purification(pos_id, symbol, exit_pnl)
            continue

        # Case D: Active Position Maintenance & Mark-to-Market
        unrealized_pnl = round((ltp - entry_p) * (quantity if quantity is not None else 1), 2)
        risk_pct = ((ltp - entry_p) / entry_p) * 100
        
        if risk_pct <= -5.0 or (lower_c is not None and ltp <= lower_c):
            logger.warning(f"CRITICAL OFFLOAD: Position {symbol} exhibits excessive risk ({risk_pct:.2f}%) or is near lower circuit. Marking for EOD closure.")
            db_write("""
                UPDATE positions SET status = 'MARKED_FOR_CLOSURE', current_ltp = ?, unrealized_pnl = ? WHERE id = ?;
            """, (ltp, unrealized_pnl, pos_id))
        else:
            db_write("""
                UPDATE positions SET current_ltp = ?, unrealized_pnl = ? WHERE id = ?;
            """, (ltp, unrealized_pnl, pos_id))

    logger.info("EOD Reconciliation completed successfully.")
    
    # -------------------------------------------------------------
    # EOD RISK OFFLOADER CHECK
    # -------------------------------------------------------------
    try:
        from src.risk.arbiter import evaluate_eod_risk_offload
        macro_data = None
        try:
            with get_read_connection() as conn:
                row = conn.execute("""
                    SELECT us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                           usdinr_price, usdinr_pct_change, polymarket_risk_score,
                           market_regime, macro_weather_score, target_cash_exposure_pct, source
                    FROM macro_weather 
                    WHERE scan_date = CURRENT_DATE
                    ORDER BY scan_date DESC LIMIT 1
                """).fetchone()
                if row:
                    macro_data = {
                        "us_vix": row[0], "sp500_pct_change": row[1],
                        "crude_oil_price": row[2], "crude_oil_pct_change": row[3],
                        "usdinr_price": row[4], "usdinr_pct_change": row[5],
                        "polymarket_risk_score": row[6], "market_regime": row[7],
                        "macro_weather_score": row[8], "target_cash_exposure_pct": row[9],
                        "source": row[10],
                    }
        except Exception:
            pass

        with get_read_connection() as conn:
            open_positions = conn.execute("""
                SELECT p.id, p.symbol, p.quantity, p.current_ltp, b.circuit_band_pct
                FROM positions p
                LEFT JOIN (
                    SELECT symbol, circuit_band_pct FROM bhavcopy_daily
                    WHERE trade_date = (SELECT MAX(trade_date) FROM bhavcopy_daily)
                ) b ON p.symbol = b.symbol
                WHERE p.status IN ('OPEN', 'TARGET_1_TRIMMED')
            """).fetchall()

        macro_weather_dict = macro_data or {}
        for pos_id, sym, qty, ltp, cb in open_positions:
            offload_res = evaluate_eod_risk_offload(
                symbol=sym,
                current_shares=qty or 0,
                current_price=ltp or 0.0,
                circuit_band=cb or 20.0,
                macro_weather=macro_weather_dict
            )
            if offload_res.get("verdict") == "REDUCE_POSITION":
                logger.warning(f"⚠️ EOD RISK OFFLOAD: Position {sym} flagged for position reduction: {offload_res}")
                from src.notification.telegram_bot import send_telegram_alert
                send_telegram_alert(
                    f"⚠️ <b>EOD RISK OFFLOAD FLAGGED: {sym}</b>\n"
                    f"Suggested shares: {offload_res['suggested_shares']} (sell {offload_res['shares_to_sell']})\n"
                    f"Reason: Macro/circuit risk."
                )
    except Exception as offload_err:
        logger.warning(f"EOD risk offload evaluation encountered non-critical error: {offload_err}")

    # -------------------------------------------------------------
    # DAILY EQUITY CURVE SNAPSHOT
    # -------------------------------------------------------------
    try:
        from src.portfolio.state import get_portfolio_state
        pstate = get_portfolio_state()
        core_eq = pstate["core_equity"]
        unrealized = pstate["unrealized_pnl_total"]
        total_eq = core_eq
        realized = pstate["realized_pnl_total"]
        
        db_write("""
            INSERT OR REPLACE INTO equity_curve (
                trade_date, total_equity, core_equity, unrealized_pnl
            ) VALUES (CURRENT_DATE, ?, ?, ?);
        """, (total_eq, core_eq - unrealized, unrealized))
        logger.info(f"📊 Daily equity_curve recorded: Total ₹{total_eq:,.2f} | Unrealized ₹{unrealized:,.2f}")
    except Exception as eq_err:
        logger.warning(f"Failed to record daily equity_curve row: {eq_err}")

    # -------------------------------------------------------------
    # DRAWDOWN CIRCUIT BREAKER CHECK
    # -------------------------------------------------------------
    from scripts.run_drawdown_check import check_drawdown
    check_drawdown()


if __name__ == "__main__":
    try:
        run_eod_reconciliation_pipeline()
    except Exception as e:
        import traceback
        logger.error(f"Cron execution failed: {e}")
        from src.notification.telegram_bot import send_telegram_error_alert
        send_telegram_error_alert("run_eod_reconciliation", str(e) + "\n" + traceback.format_exc())

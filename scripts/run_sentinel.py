"""
15-Minute Intraday Trailing Stop-Loss Sentinel.
Monitors open positions, raises trailing stops on new highs, and triggers stop-out alerts.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import logging
from src.notification.telegram_bot import is_system_halted
from src.db.session import get_read_connection
from src.db.queue_writer import db_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_sentinel")


def run_sentinel_check():
    if is_system_halted():
        logger.warning("System is currently HALTED. Sentinel running in DEFENSIVE EXIT-ONLY mode for open positions.")

    logger.info("Running 15-minute Trailing Stop-Loss Sentinel check...")

    with get_read_connection() as conn:
        open_positions = conn.execute("""
            SELECT id, symbol, entry_price, trailing_stop_loss, atr, quantity, status,
                   COALESCE(peak_high, entry_price) as peak_high,
                   COALESCE(realized_pnl, 0.0) as realized_pnl,
                   target_1, target_2
            FROM positions
            WHERE status IN ('OPEN', 'TARGET_1_TRIMMED', 'MARKED_FOR_CLOSURE');
        """).fetchall()

    if not open_positions:
        logger.info("No open positions to monitor.")
        return

    symbols = [p[1] for p in open_positions]
    
    # Fetch real live data
    import yfinance as yf
    try:
        yf_symbols = [f"{sym}.NS" for sym in symbols]
        live_data = None
        for attempt in range(3):
            try:
                live_data = yf.download(yf_symbols, period="1d", interval="15m", progress=False)
                if live_data is not None and not live_data.empty:
                    break
            except Exception as e:
                logger.warning(f"Live data download attempt {attempt+1}/3 failed: {e}")
                import time
                time.sleep(2 ** attempt)

        if live_data is None or live_data.empty:
            logger.error("Sentinel failed to fetch live data after 3 retries.")
            from src.notification.telegram_bot import set_system_halt_state, send_telegram_safe_halt_alarm
            set_system_halt_state(True, "Live Data Provider Persistent Failure (yfinance)")
            send_telegram_safe_halt_alarm("Live Data Provider Persistent Failure (yfinance)")
            return
    except Exception as e:
        logger.error(f"Sentinel unexpected failure fetching live data: {e}")
        return

    update_sl_params = []
    update_ltp_params = []
    
    for row in open_positions:
        pos_id = row[0]
        symbol = row[1]
        entry_p = row[2]
        current_sl = row[3]
        atr = row[4]
        quantity = row[5]
        pos_status = row[6]
        peak_high = float(row[7]) if row[7] is not None else entry_p
        prior_realized_pnl = float(row[8]) if row[8] is not None else 0.0
        target_1 = float(row[9]) if len(row) > 9 and row[9] is not None else None
        target_2 = float(row[10]) if len(row) > 10 and row[10] is not None else None

        try:
            import math
            if len(symbols) == 1:
                c_series = live_data['Close'].dropna()
                h_series = live_data['High'].dropna()
                l_series = live_data['Low'].dropna()
                if c_series.empty or h_series.empty or l_series.empty:
                    continue
                ltp = float(c_series.iloc[-1])
                high_price = float(h_series.iloc[-1])
                low_price = float(l_series.iloc[-1])
            else:
                c_series = live_data['Close'][f"{symbol}.NS"].dropna()
                h_series = live_data['High'][f"{symbol}.NS"].dropna()
                l_series = live_data['Low'][f"{symbol}.NS"].dropna()
                if c_series.empty or h_series.empty or l_series.empty:
                    continue
                ltp = float(c_series.iloc[-1])
                high_price = float(h_series.iloc[-1])
                low_price = float(l_series.iloc[-1])

            if math.isnan(ltp) or math.isnan(high_price) or math.isnan(low_price):
                continue
        except (KeyError, IndexError, TypeError, ValueError):
            logger.warning(f"Failed to extract live price for {symbol}")
            continue

        # 0. Liquidate MARKED_FOR_CLOSURE positions immediately once no longer locked at lower circuit
        if pos_status == 'MARKED_FOR_CLOSURE':
            from src.execution.order_manager import check_lower_circuit_trap
            lc_status = check_lower_circuit_trap(symbol, current_price=ltp)
            if lc_status["is_trapped"]:
                logger.warning(f"🔒 [{symbol}] Still trapped at Lower Circuit (₹{ltp:.2f}). Holding MARKED_FOR_CLOSURE.")
                continue
            exit_p = ltp
            exit_pnl = round((exit_p - entry_p) * (quantity if quantity is not None else 1), 2)
            total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
            db_write("""
                UPDATE positions
                SET status = 'CLOSED', exit_price = ?, exit_date = CURRENT_DATE,
                    realized_pnl = ?, current_ltp = ?, unrealized_pnl = 0.0
                WHERE id = ? AND status = 'MARKED_FOR_CLOSURE';
            """, (exit_p, total_realized_pnl, ltp, pos_id))
            logger.info(f"✅ [{symbol}] Liquidated MARKED_FOR_CLOSURE position at ₹{exit_p:.2f} | Realized PnL: ₹{total_realized_pnl:.2f}")
            continue

        # 1. STOP-OUT execution branch:
        if current_sl is not None and low_price <= current_sl:
            from src.execution.order_manager import check_lower_circuit_trap
            lc_status = check_lower_circuit_trap(symbol, current_price=ltp)
            if lc_status["is_trapped"]:
                logger.warning(f"🔒 [{symbol}] LOWER CIRCUIT TRAP at ₹{ltp:.2f} (LC: ₹{lc_status['lower_circuit']:.2f}). Market exit impossible. Marking MARKED_FOR_CLOSURE.")
                db_write("""
                    UPDATE positions
                    SET status = 'MARKED_FOR_CLOSURE', current_ltp = ?, unrealized_pnl = ?
                    WHERE id = ? AND status = ?
                """, (ltp, round((ltp - entry_p) * (quantity or 1), 2), pos_id, pos_status))
                
                from src.notification.telegram_bot import send_telegram_alert
                send_telegram_alert(
                    f"🔒 <b>LOWER CIRCUIT TRAP: {symbol}</b>\n"
                    f"Stop-loss breached (SL: ₹{current_sl:.2f}) but stock is locked at Lower Circuit (₹{lc_status['lower_circuit']:.2f}).\n"
                    f"Status set to <code>MARKED_FOR_CLOSURE</code>. Manual AMO exit required."
                )
                continue

            exit_p = min(ltp, current_sl) # Simulate stop market fill
            exit_pnl = round((exit_p - entry_p) * (quantity if quantity is not None else 1), 2)
            total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
            
            # RETURNING id guarantees row check passes and avoids silent alert drops
            res = db_write("""
                UPDATE positions 
                SET status = 'STOPPED_OUT', exit_price = ?, exit_date = CURRENT_DATE, 
                    realized_pnl = ?, current_ltp = ?, unrealized_pnl = 0.0 
                WHERE id = ? AND status = ?
                RETURNING id;
            """, (exit_p, total_realized_pnl, ltp, pos_id, pos_status))
            
            if res and len(res) > 0:
                logger.warning(f"🚨 INTRADAY STOP LOSS HIT: {symbol} at ₹{ltp:.2f} (SL: ₹{current_sl:.2f})")
                from src.notification.telegram_bot import send_telegram_alert
                import html
                escaped_sym = html.escape(str(symbol))
                send_telegram_alert(
                    f"🚨 <b>INTRADAY STOP LOSS TRIGGERED</b>\n\n"
                    f"<b>Symbol:</b> {escaped_sym}\n"
                    f"<b>Exit Price:</b> ₹{exit_p:.2f}\n"
                    f"<b>Stop Out PnL:</b> ₹{exit_pnl:,.2f}\n"
                    f"<b>Total Realized PnL:</b> ₹{total_realized_pnl:,.2f}"
                )
            continue

        # 2. INTRADAY TARGET 2 execution branch (for TARGET_1_TRIMMED runner positions):
        if pos_status == 'TARGET_1_TRIMMED' and target_2 is not None and high_price >= target_2:
            exit_p = max(ltp, target_2)
            exit_pnl = round((exit_p - entry_p) * (quantity if quantity is not None else 1), 2)
            total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
            db_write("""
                UPDATE positions
                SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE,
                    realized_pnl = ?, current_ltp = ?, unrealized_pnl = 0.0
                WHERE id = ? AND status = 'TARGET_1_TRIMMED';
            """, (exit_p, total_realized_pnl, ltp, pos_id))
            ret_pct = round((exit_p - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
            db_write("""
                UPDATE agent_memory
                SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
                WHERE symbol = ? AND outcome_label IS NULL;
            """, (ret_pct, symbol))
            logger.info(f"🏆 INTRADAY TARGET 2 HIT: {symbol} at ₹{high_price:.2f} (T2: ₹{target_2:.2f}) | Realized PnL: ₹{total_realized_pnl:.2f}")
            try:
                from scripts.run_eod_reconciliation import log_shariah_purification
                if exit_pnl > 0:
                    log_shariah_purification(pos_id, symbol, exit_pnl)
            except Exception:
                pass
            try:
                from src.notification.telegram_bot import send_telegram_alert
                import html
                send_telegram_alert(
                    f"🏆 <b>INTRADAY TARGET 2 RUNNER HIT: {html.escape(str(symbol))}</b>\n"
                    f"Exit Price: ₹{exit_p:.2f} (T2: ₹{target_2:.2f})\n"
                    f"Total Realized PnL: ₹{total_realized_pnl:,.2f}"
                )
            except Exception:
                pass
            continue

        # 3. INTRADAY TARGET 1 execution branch (50% partial profit booking + breakeven SL ratchet, or full T1+T2 exit if both hit on same bar):
        if pos_status == 'OPEN' and target_1 is not None and high_price >= target_1:
            exit_p = max(ltp, target_1)
            if target_2 is not None and quantity is not None and quantity > 1 and high_price >= target_2:
                half_qty = quantity // 2
                rem_qty = quantity - half_qty
                t1_exit = max(ltp, target_1)
                t2_exit = max(ltp, target_2)
                exit_pnl = round((t1_exit - entry_p) * half_qty + (t2_exit - entry_p) * rem_qty, 2)
                total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
                db_write("""
                    UPDATE positions
                    SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE,
                        realized_pnl = ?, current_ltp = ?, unrealized_pnl = 0.0
                    WHERE id = ? AND status = 'OPEN';
                """, (t2_exit, total_realized_pnl, ltp, pos_id))
                ret_pct = round((t2_exit - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
                db_write("""
                    UPDATE agent_memory
                    SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
                    WHERE symbol = ? AND outcome_label IS NULL;
                """, (ret_pct, symbol))
                logger.info(
                    f"🏆 INTRADAY TARGET 1 & TARGET 2 HIT ON SAME BAR: {symbol} at ₹{high_price:.2f}! "
                    f"Closed full position ({half_qty} @ ₹{t1_exit:.2f} + {rem_qty} @ ₹{t2_exit:.2f}) | Realized PnL: ₹{total_realized_pnl:.2f}"
                )
                try:
                    from scripts.run_eod_reconciliation import log_shariah_purification
                    if exit_pnl > 0:
                        log_shariah_purification(pos_id, symbol, exit_pnl)
                except Exception:
                    pass
                try:
                    from src.notification.telegram_bot import send_telegram_alert
                    import html
                    send_telegram_alert(
                        f"🏆 <b>INTRADAY TARGET 1 & 2 REACHED: {html.escape(str(symbol))}</b>\n"
                        f"Exit Price: ₹{t2_exit:.2f} (T1: ₹{target_1:.2f}, T2: ₹{target_2:.2f})\n"
                        f"Total Realized PnL: ₹{total_realized_pnl:,.2f}"
                    )
                except Exception:
                    pass
            elif target_2 is not None and quantity is not None and quantity > 1:
                half_qty = quantity // 2
                rem_qty = quantity - half_qty
                partial_pnl = round((exit_p - entry_p) * half_qty, 2)
                total_realized_pnl = round(prior_realized_pnl + partial_pnl, 2)
                breakeven_sl = round(entry_p * 1.005, 2)
                new_peak = max(peak_high, high_price)
                eff_atr = atr if (atr is not None and atr > 0) else (entry_p * 0.025)
                trail_from_peak = round(new_peak - (eff_atr * 1.8), 2)
                new_sl = max(current_sl or 0.0, breakeven_sl, trail_from_peak)
                new_unrealized = round((ltp - entry_p) * rem_qty, 2)
                db_write("""
                    UPDATE positions
                    SET status = 'TARGET_1_TRIMMED', quantity = ?, trailing_stop_loss = ?,
                        peak_high = ?, realized_pnl = ?, unrealized_pnl = ?, current_ltp = ?
                    WHERE id = ? AND status = 'OPEN';
                """, (rem_qty, new_sl, new_peak, total_realized_pnl, new_unrealized, ltp, pos_id))
                logger.info(
                    f"🎯 INTRADAY TARGET 1 HIT: {symbol} at ₹{high_price:.2f}! "
                    f"Trimmed 50% ({half_qty} shares @ ₹{exit_p:.2f}, PnL: ₹{partial_pnl:.2f}). "
                    f"Runner SL ratcheted to ₹{new_sl:.2f} on {rem_qty} shares."
                )
                try:
                    from scripts.run_eod_reconciliation import log_shariah_purification
                    if partial_pnl > 0:
                        log_shariah_purification(pos_id, symbol, partial_pnl)
                except Exception:
                    pass
                try:
                    from src.notification.telegram_bot import send_telegram_alert
                    import html
                    send_telegram_alert(
                        f"🎯 <b>INTRADAY TARGET 1 TRIM: {html.escape(str(symbol))}</b>\n"
                        f"Trimmed 50% ({half_qty} shares @ ₹{exit_p:.2f})\n"
                        f"Realized PnL: ₹{partial_pnl:,.2f}\n"
                        f"Trailing SL ratcheted to ₹{new_sl:.2f} on {rem_qty} runner shares."
                    )
                except Exception:
                    pass
            else:
                exit_pnl = round((exit_p - entry_p) * (quantity if quantity is not None else 1), 2)
                total_realized_pnl = round(prior_realized_pnl + exit_pnl, 2)
                db_write("""
                    UPDATE positions
                    SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE,
                        realized_pnl = ?, current_ltp = ?, unrealized_pnl = 0.0
                    WHERE id = ? AND status = 'OPEN';
                """, (exit_p, total_realized_pnl, ltp, pos_id))
                ret_pct = round((exit_p - entry_p) / entry_p * 100.0, 2) if entry_p else 0.0
                db_write("""
                    UPDATE agent_memory
                    SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
                    WHERE symbol = ? AND outcome_label IS NULL;
                """, (ret_pct, symbol))
                logger.info(f"🎯 INTRADAY TARGET 1 FULL EXIT: {symbol} at ₹{exit_p:.2f} | Realized PnL: ₹{total_realized_pnl:.2f}")
                try:
                    from scripts.run_eod_reconciliation import log_shariah_purification
                    if exit_pnl > 0:
                        log_shariah_purification(pos_id, symbol, exit_pnl)
                except Exception:
                    pass
            continue

        # 4. Dynamic Trailing Stop logic: 1.8x ATR from highest price recorded
        if atr is None or atr <= 0:
            atr = entry_p * 0.025
            
        new_peak = max(peak_high, high_price)
        if pos_status == 'TARGET_1_TRIMMED':
            # Runner trail: cannot drop below breakeven (+0.5% buffer)
            breakeven_sl = round(entry_p * 1.005, 2)
            trail_from_peak = round(new_peak - (atr * 1.8), 2)
            new_sl = max(current_sl or 0.0, breakeven_sl, trail_from_peak)
        else:
            trail_from_peak = round(new_peak - (atr * 1.8), 2)
            new_sl = max(current_sl or 0.0, trail_from_peak)
        
        unrealized_pnl_val = round((ltp - entry_p) * (quantity if quantity else 1), 2)
        if (current_sl is None or new_sl > current_sl) or new_peak > peak_high:
            if current_sl is None or new_sl > current_sl:
                logger.info(f"Trailing Stop Raised for {symbol}: ₹{current_sl if current_sl else 'None'} -> ₹{new_sl:.2f} (Peak: ₹{new_peak:.2f})")
            update_sl_params.append((new_sl, new_peak, ltp, unrealized_pnl_val, pos_id, pos_status))
        else:
            update_ltp_params.append((ltp, unrealized_pnl_val, pos_id, pos_status))
            
    if update_sl_params:
        from src.db.queue_writer import db_write_many
        db_write_many("UPDATE positions SET trailing_stop_loss = ?, peak_high = ?, current_ltp = ?, unrealized_pnl = ? WHERE id = ? AND status = ?;", update_sl_params)
    
    if update_ltp_params:
        from src.db.queue_writer import db_write_many
        db_write_many("UPDATE positions SET current_ltp = ?, unrealized_pnl = ? WHERE id = ? AND status = ?;", update_ltp_params)


if __name__ == "__main__":
    try:
        run_sentinel_check()
    except Exception as e:
        import traceback
        logger.error(f"Cron execution failed: {e}")
        from src.notification.telegram_bot import send_telegram_error_alert
        send_telegram_error_alert("run_sentinel", str(e) + "\n" + traceback.format_exc())

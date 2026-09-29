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
        logger.warning("System is currently HALTED. Sentinel is in idle standby.")
        return

    logger.info("Running 15-minute Trailing Stop-Loss Sentinel check...")

    with get_read_connection() as conn:
        open_positions = conn.execute("""
            SELECT id, symbol, entry_price, trailing_stop_loss, atr, quantity, status,
                   COALESCE(peak_high, entry_price) as peak_high,
                   COALESCE(realized_pnl, 0.0) as realized_pnl
            FROM positions
            WHERE status IN ('OPEN', 'TARGET_1_TRIMMED');
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

        # STOP-OUT execution branch:
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

        # Dynamic Trailing Stop logic: 1.8x ATR from highest price recorded
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

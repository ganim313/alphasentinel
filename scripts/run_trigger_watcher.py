"""
AWAITING_TRIGGER Intraday Polling Daemon.
Polls approved candidates whose status is 'AWAITING_TRIGGER' during market hours.
Fires order placement when live price >= trigger_price.
"""
import sys
import os
import time
import math
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.session import get_read_connection
from src.db.queue_writer import db_write
from src.notification.telegram_bot import is_system_halted, send_telegram_alert
from src.utils.holidays import is_nse_holiday
from src.execution.order_manager import PaperBroker
from src.risk.arbiter import calculate_deterministic_risk_and_position
from src.config.settings import settings
from src.portfolio.paper_capital import get_paper_capital
import yfinance as yf

logger = logging.getLogger("run_trigger_watcher")
IST = ZoneInfo("Asia/Kolkata")


def check_and_execute_triggers() -> int:
    """Checks all active AWAITING_TRIGGER candidates and places orders for triggered ones."""
    if is_system_halted():
        logger.info("System halted. Trigger watcher idle.")
        return 0

    macro_data = {}
    with get_read_connection() as conn:
        rows = conn.execute("""
            SELECT id, symbol, trigger_price, pattern_type, sector, market_cap_tier, circuit_band, adtv_20d, created_at
            FROM screener_candidates
            WHERE status = 'AWAITING_TRIGGER'
              AND scan_date >= (CURRENT_DATE - INTERVAL '5 days')
            ORDER BY scan_date ASC
        """).fetchall()
        try:
            mw_row = conn.execute("""
                SELECT us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                       usdinr_price, usdinr_pct_change, polymarket_risk_score,
                       market_regime, macro_weather_score, target_cash_exposure_pct, source
                FROM macro_weather
                ORDER BY scan_date DESC LIMIT 1
            """).fetchone()
            if mw_row and len(mw_row) >= 11:
                macro_data = {
                    "us_vix": mw_row[0], "sp500_pct_change": mw_row[1],
                    "crude_oil_price": mw_row[2], "crude_oil_pct_change": mw_row[3],
                    "usdinr_price": mw_row[4], "usdinr_pct_change": mw_row[5],
                    "polymarket_risk_score": mw_row[6], "market_regime": mw_row[7],
                    "macro_weather_score": mw_row[8], "target_cash_exposure_pct": mw_row[9],
                    "source": mw_row[10],
                }
        except Exception as mw_err:
            logger.debug(f"Could not load macro_weather in trigger watcher: {mw_err}")

    if not rows:
        return 0

    symbols = [r[1] for r in rows]
    logger.info(f"Checking triggers for {len(symbols)} candidate(s): {symbols}")
    
    # Batch download quotes
    tickers = [f"{s}.NS" for s in symbols]
    executed_count = 0
    try:
        data = yf.download(tickers, period="1d", interval="5m", progress=False)
        if data is None or data.empty:
            return 0
    except Exception as e:
        logger.warning(f"Error fetching live prices in trigger watcher: {e}")
        return 0

    import pandas as pd
    for row in rows:
        cand_id, sym, trigger_p, pattern, sector, mcap_tier, cb = row[:7]
        cand_adtv = float(row[7]) if len(row) > 7 and row[7] is not None and float(row[7]) > 0 else 5000000.0
        cand_created_at = row[8] if len(row) > 8 else None
        try:
            col = f"{sym}.NS"
            if len(symbols) == 1:
                close_series = data["Close"].dropna()
                high_series = data["High"].dropna()
            else:
                close_series = data["Close"][col].dropna() if col in data["Close"] else None
                high_series = data["High"][col].dropna() if col in data["High"] else None

            if close_series is None or close_series.empty or high_series is None or high_series.empty:
                continue

            if isinstance(high_series.index, pd.DatetimeIndex) and cand_created_at is not None:
                try:
                    cand_ts = pd.Timestamp(cand_created_at)
                    idx_tz = high_series.index.tz
                    if idx_tz is not None:
                        cand_ts = cand_ts.tz_localize(IST).tz_convert(idx_tz) if cand_ts.tzinfo is None else cand_ts.tz_convert(idx_tz)
                    elif cand_ts.tzinfo is not None:
                        cand_ts = cand_ts.tz_convert(IST).tz_localize(None)
                    cutoff_ts = cand_ts - pd.Timedelta(minutes=5)
                    high_series = high_series[high_series.index >= cutoff_ts]
                    if high_series.empty:
                        continue
                except Exception:
                    pass

            current_p = float(close_series.iloc[-1])
            high_p = float(high_series.max())

            if high_p >= trigger_p:
                logger.info(f"🎯 [{sym}] TRIGGER HIT! High ₹{high_p:.2f} >= Trigger ₹{trigger_p:.2f}")
                
                # Fetch recent ATR and sort chronologically (ascending by trade_date)
                with get_read_connection() as conn:
                    bhav_df = conn.execute("""
                        SELECT trade_date, high_price, low_price, close_price
                        FROM bhavcopy_daily WHERE symbol = ?
                        ORDER BY trade_date DESC LIMIT 20
                    """, (sym,)).df()
                
                from src.utils.technical_indicators import atr as calc_atr
                if not bhav_df.empty and len(bhav_df) >= 5:
                    if "trade_date" in bhav_df.columns:
                        bhav_df = bhav_df.sort_values("trade_date", ascending=True).reset_index(drop=True)
                    else:
                        bhav_df = bhav_df.iloc[::-1].reset_index(drop=True)
                    atr_val = float(calc_atr(bhav_df['high_price'], bhav_df['low_price'], bhav_df['close_price']).iloc[-1])
                else:
                    atr_val = current_p * 0.025

                current_capital = get_paper_capital()
                risk_calc = calculate_deterministic_risk_and_position(
                    symbol=sym,
                    trigger_price=trigger_p,
                    current_price=current_p,
                    atr_14=atr_val,
                    circuit_band=cb if cb is not None else 20.0,
                    macro_weather=macro_data,
                    adtv_20d=cand_adtv,
                    sector=sector or "",
                    market_cap_tier=mcap_tier or "SMALL",
                    portfolio_capital_rupees=current_capital
                )
                try:
                    qty = int(risk_calc.get("suggested_shares", 0) or 0)
                except (ValueError, TypeError):
                    qty = 0

                if qty <= 0:
                    rej_reason = risk_calc.get("rejection_reason", "Risk arbiter allocated 0 shares")
                    logger.warning(f"[{sym}] Risk arbiter allocated 0 shares. Rejecting candidate: {rej_reason}")
                    db_write("UPDATE screener_candidates SET status = 'EXECUTION_REJECTED' WHERE id = ?", (cand_id,))
                    continue

                stop_loss_p = risk_calc.get("stop_loss_price") or round(current_p - 1.8 * atr_val, 2)
                target_1_p = risk_calc.get("target_1_price") or round(current_p + 3.0 * atr_val, 2)
                target_2_p = risk_calc.get("target_2_price") or round(current_p + 6.0 * atr_val, 2)

                broker = PaperBroker()
                order_id = broker.place_order(
                    symbol=sym,
                    price=current_p,
                    quantity=qty,
                    atr=atr_val,
                    sector=sector,
                    initial_stop=float(stop_loss_p),
                    target_1=float(target_1_p),
                    target_2=float(target_2_p),
                    candidate_id=cand_id,
                )

                if order_id:
                    db_write("UPDATE screener_candidates SET status = 'APPROVED' WHERE id = ?", (cand_id,))
                    send_telegram_alert(
                        f"🎯 <b>TRIGGER CONFIRMED: {sym}</b>\n"
                        f"Price ₹{current_p:.2f} breached Trigger ₹{trigger_p:.2f}.\n"
                        f"Paper order placed: <code>{order_id}</code>"
                    )
                    executed_count += 1
                else:
                    logger.warning(f"[{sym}] Order placement rejected by execution engine.")
                    db_write("UPDATE screener_candidates SET status = 'EXECUTION_REJECTED' WHERE id = ?", (cand_id,))

        except Exception as e:
            logger.error(f"Error evaluating trigger for {sym}: {e}", exc_info=True)

    return executed_count


def run_trigger_watcher(poll_interval: int = 300, max_iterations: Optional[int] = None):
    """Main watcher loop running during market hours."""
    iterations = 0
    logger.info("Starting AWAITING_TRIGGER Intraday Watcher...")
    while True:
        try:
            now = datetime.now(IST)
            if now.weekday() < 5 and not is_nse_holiday(now.date()):
                market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
                if market_open <= now <= market_close:
                    check_and_execute_triggers()
        except Exception as e:
            logger.error(f"Error in trigger watcher loop: {e}")

        iterations += 1
        if max_iterations and iterations >= max_iterations:
            break
        time.sleep(poll_interval)


if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("run_trigger_watcher"):
        run_trigger_watcher(poll_interval=300)

"""
Monthly Drawdown Circuit Breaker check.
Calculates realized and unrealized P&L for the month and halts the system if drawdown exceeds 6%.
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import src.notification.telegram_bot as telegram_bot
from src.notification.telegram_bot import set_system_halt_state, send_telegram_safe_halt_alarm, send_telegram_alert
from src.config.settings import settings
import src.portfolio.state as portfolio_state
from src.portfolio.state import get_portfolio_state
from src.db.queue_writer import db_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_drawdown_check")

def check_drawdown():
    logger.info("Executing Dual-Mode Drawdown Circuit Breaker Check...")
    monthly_warn_pct = getattr(settings, "MONTHLY_DRAWDOWN_SOFT_WARN_PCT", 4.0)
    lifetime_kill_pct = getattr(settings, "MAX_DRAWDOWN_KILL_PCT", 6.0)

    try:
        pstate = portfolio_state.get_portfolio_state()
        core_equity = pstate["core_equity"]
        lifetime_dd_pct = pstate["lifetime_hwm_dd_pct"]
        monthly_dd_pct = pstate["monthly_dd_pct"]
        hwm = pstate["lifetime_hwm"]
        monthly_peak = pstate["monthly_peak_equity"]

        logger.info(
            f"Core Equity: ₹{core_equity:,.2f} | HWM: ₹{hwm:,.2f} | "
            f"Lifetime DD: {lifetime_dd_pct:.2f}% (Limit: {lifetime_kill_pct}%) | "
            f"Monthly DD: {monthly_dd_pct:.2f}% (Warn: {monthly_warn_pct}%)"
        )

        # Persist updated metrics to circuit_breaker_state
        db_write("""
            UPDATE circuit_breaker_state 
            SET monthly_drawdown_pct = ?, high_water_mark = ?, monthly_peak_equity = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = 1;
        """, (monthly_dd_pct, hwm, monthly_peak), sync=True)

        # 1. Monthly Soft Warning (Alert only, no halt)
        if monthly_dd_pct >= monthly_warn_pct:
            warn_msg = (
                f"⚠️ <b>MONTHLY DRAWDOWN WARNING</b>\n"
                f"Monthly Drawdown has reached <b>{monthly_dd_pct:.2f}%</b> (Warn Threshold: {monthly_warn_pct}%).\n"
                f"Current Equity: ₹{core_equity:,.2f} (Monthly Peak: ₹{monthly_peak:,.2f}).\n"
                f"Trading operations continue."
            )
            logger.warning(warn_msg)
            telegram_bot.send_telegram_alert(warn_msg)

        # 2. Lifetime Hard Kill Switch
        if lifetime_dd_pct >= lifetime_kill_pct:
            reason = f"Max Lifetime Drawdown Exceeded: {lifetime_dd_pct:.2f}% >= {lifetime_kill_pct}%"
            logger.critical(f"EMERGENCY SAFE HALT: {reason}")
            telegram_bot.set_system_halt_state(True, reason)
            telegram_bot.send_telegram_safe_halt_alarm(reason)

    except Exception as e:
        logger.error(f"Failed to check drawdown: {e}")
        raise

if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("run_drawdown_check"):
        check_drawdown()

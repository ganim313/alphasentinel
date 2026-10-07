"""
Master Autonomous Scheduler Daemon.
Orchestrates daily and periodic quantitative trading pipelines:
- 06:00 AM IST (Mon-Fri): Fyers Instrument Master Sync
- 08:30 AM IST (Mon-Fri): Pre-market Macro Radar & Corporate Actions
- 08:45 AM IST (Mon-Fri): Morning 2FA Token Refresh (scripts/fyers_auth.py)
- 08:50 AM IST (Mon-Fri): Morning Telegram Digest (send_morning_digest)
- 09:15-15:30 IST (Mon-Fri): Market Hours (FYERS server-side GTT OCO execution)
- 19:00 IST (Mon-Fri): Bhavcopy Ingestion (bhavcopy.py)
- 19:15 IST (Mon-Fri): EOD Screening (vcp_screener.py & regime_engine.py)
- 19:30 IST (Mon-Fri): Nightly Holdings Guardian (fyers_guardian.py)
- Sunday 01:00 AM IST: Database Maintenance & Vacuum
- 1st of Month 08:00 AM IST: Shariah Purification Report
"""

import sys
import os
import time
import datetime
import signal
import subprocess
import threading
import logging
from pathlib import Path
import portalocker
import schedule

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Indian Standard Time (UTC+5:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Scheduler] %(message)s"
)
logger = logging.getLogger("master_scheduler")

stop_requested = False
_scheduler_lock_fh = None


def signal_handler(signum, frame):
    global stop_requested
    logger.info(f"Shutdown signal ({signum}) received. Stopping Master Scheduler gracefully...")
    stop_requested = True


def is_weekday_ist() -> bool:
    """Returns True if today is Monday to Friday in IST."""
    return datetime.datetime.now(IST).weekday() < 5


def is_market_hours_ist() -> bool:
    """Returns True if current time is within Indian Market trading hours (09:15 - 15:30 IST) on an active trading day."""
    from src.utils.holidays import is_nse_holiday
    now_ist = datetime.datetime.now(IST)
    if now_ist.weekday() >= 5:
        return False
    if is_nse_holiday(now_ist.date()):
        return False
    market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now_ist <= market_close


def _is_holiday_today() -> bool:
    """Returns True if today is an NSE holiday (including weekends)."""
    from src.utils.holidays import is_nse_holiday
    return is_nse_holiday(datetime.datetime.now(IST).date())


def run_script(script_name: str, timeout_seconds: int = 600) -> bool:
    """Runs a target script as an isolated subprocess with timeout and logging."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        script_path = PROJECT_ROOT / script_name
    if not script_path.exists():
        script_path = PROJECT_ROOT / "src" / script_name
    if not script_path.exists():
        logger.error(f"Target script does not exist: {script_path}")
        return False

    logger.info(f"==> [START] Executing task: {script_name}")
    start_time = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(PROJECT_ROOT)
        )
        elapsed = time.time() - start_time
        if proc.returncode == 0:
            logger.info(f"==> [SUCCESS] Task {script_name} completed in {elapsed:.2f}s.")
            out_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
            err_lines = [ln.strip() for ln in (proc.stderr or "").splitlines() if ln.strip()]
            if out_lines:
                tail_out = "\n  ".join(out_lines[-5:])
                logger.info(f"  [{script_name} stdout tail]:\n  {tail_out}")
            if err_lines:
                tail_err = "\n  ".join(err_lines[-5:])
                logger.info(f"  [{script_name} stderr tail]:\n  {tail_err}")
            return True
        else:
            logger.error(
                f"==> [FAILED] Task {script_name} failed (code {proc.returncode}) in {elapsed:.2f}s.\n"
                f"--- STDERR ---\n{proc.stderr.strip()}\n"
                f"--- STDOUT ---\n{proc.stdout[-500:].strip() if proc.stdout else ''}"
            )
            return False
    except subprocess.TimeoutExpired as e:
        stdout_tail = (e.stdout[-1000:].decode(errors="replace") if isinstance(e.stdout, bytes) else str(e.stdout or "")[-1000:]).strip()
        stderr_tail = (e.stderr[-1000:].decode(errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")[-1000:]).strip()
        logger.error(
            f"==> [TIMEOUT] Task {script_name} timed out after {timeout_seconds}s.\n"
            f"--- STDERR (Tail) ---\n{stderr_tail}\n"
            f"--- STDOUT (Tail) ---\n{stdout_tail}"
        )
        return False
    except Exception as e:
        logger.error(f"==> [ERROR] Exception executing {script_name}: {e}")
        return False


def job_premarket():
    if not is_weekday_ist():
        logger.info("Skipping Pre-Market task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping pre-market analysis.")
        return
    logger.info("Triggering 08:30 AM Pre-Market Pipeline & Corporate Actions...")
    run_script("run_premarket.py")
    run_script("run_corporate_actions.py")


def job_sentinel():
    import warnings
    warnings.warn("job_sentinel is DEPRECATED. T+2 Demat Qabd compliance replaces 15-min polling.", DeprecationWarning)
    logger.warning("job_sentinel is DEPRECATED and removed from schedule.")


def job_trigger_watcher():
    import warnings
    warnings.warn("job_trigger_watcher is DEPRECATED. FYERS GTT OCO replaces intraday trigger watcher.", DeprecationWarning)
    logger.warning("job_trigger_watcher is DEPRECATED and removed from schedule.")


def job_live_preview():
    import warnings
    warnings.warn("job_live_preview (15:15 rush) is DEPRECATED. EOD screening and 08:50 digest replace 15:15 rush.", DeprecationWarning)
    logger.warning("job_live_preview is DEPRECATED and removed from schedule.")


def job_fyers_auth():
    if not is_weekday_ist():
        logger.info("Skipping Fyers Auth task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping Fyers 2FA refresh.")
        return
    logger.info("Triggering 08:45 AM Morning 2FA Token Refresh (scripts/fyers_auth.py)...")
    ok = run_script("fyers_auth.py", timeout_seconds=120)
    if not ok:
        try:
            from scripts.fyers_auth import refresh_fyers_token
            refresh_fyers_token()
            logger.info("Fyers token refreshed via in-process fallback.")
        except Exception as e:
            logger.error(f"Fyers auth refresh fallback failed: {e}")


def job_morning_digest():
    if not is_weekday_ist():
        logger.info("Skipping Morning Digest task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping morning digest.")
        return
    logger.info("Triggering 08:50 AM Morning Telegram Digest (send_morning_digest)...")
    try:
        from scripts.run_live_preview import send_morning_digest
        send_morning_digest()
    except Exception as e:
        logger.error(f"Morning digest execution failed: {e}")


def job_bhavcopy_ingestion():
    if not is_weekday_ist():
        logger.info("Skipping Bhavcopy Ingestion task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping Bhavcopy Ingestion.")
        return
    logger.info("Triggering 19:00 IST Bhavcopy Ingestion (bhavcopy.py)...")
    ok = run_script("ingestion/bhavcopy.py", timeout_seconds=600)
    if not ok:
        try:
            from src.ingestion.bhavcopy import fetch_bhavcopy_with_retry_and_fallback, ingest_bhavcopy_dataframe
            today = datetime.datetime.now(IST).date()
            df = fetch_bhavcopy_with_retry_and_fallback(today)
            if df is not None and not df.empty:
                count = ingest_bhavcopy_dataframe(df, today)
                logger.info(f"Bhavcopy Ingestion successful: {count} records inserted for {today}.")
            else:
                logger.info(f"Bhavcopy for {today} not available or already ingested.")
        except Exception as e:
            logger.error(f"Bhavcopy ingestion failed: {e}")


def job_eod_screening():
    if not is_weekday_ist():
        logger.info("Skipping EOD Screening task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping EOD Screening.")
        return
    logger.info("Triggering 19:15 IST EOD Screening (vcp_screener.py & regime_engine.py)...")
    try:
        from src.db.session import get_read_connection
        from src.screening.regime_engine import compute_market_regime
        from src.screening.vcp_screener import evaluate_minervini_vcp_batch
        with get_read_connection() as conn:
            regime_state = compute_market_regime(conn)
            logger.info(f"Market Regime: {regime_state.regime} (Score: {regime_state.score}/3, Allow Entries: {regime_state.allow_new_entries})")
            if regime_state.allow_new_entries:
                active_syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM bhavcopy_daily WHERE trade_date >= (CURRENT_DATE - INTERVAL 5 DAY)").fetchall()]
                setups = evaluate_minervini_vcp_batch(active_syms, conn)
                logger.info(f"EOD Screening complete: {len(setups)} VCP setups identified.")
            else:
                logger.info("EOD Screening skipped due to RISK_OFF regime.")
    except Exception as e:
        logger.error(f"EOD screening execution failed: {e}")


def job_holdings_guardian():
    if not is_weekday_ist():
        logger.info("Skipping Holdings Guardian task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping Holdings Guardian.")
        return
    logger.info("Triggering 19:30 IST Nightly Holdings Guardian (fyers_guardian.py)...")
    try:
        from src.db.session import get_write_connection
        from src.ingestion.fyers_client import FyersClient
        from src.portfolio.fyers_guardian import reconcile_and_evaluate_holdings
        with get_write_connection() as conn:
            fyers_client = FyersClient()
            audit_result = reconcile_and_evaluate_holdings(conn, fyers_client)
            logger.info(f"Nightly Holdings Guardian audit complete: {audit_result}")
    except Exception as e:
        logger.error(f"Holdings Guardian execution failed: {e}")


def job_eod_reconciliation():
    if not is_weekday_ist():
        logger.info("Skipping EOD Reconciliation task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping EOD reconciliation.")
        return
    logger.info("Triggering 06:30 PM EOD Trade Reconciliation...")
    run_script("run_eod_reconciliation.py", timeout_seconds=600)


def job_drawdown_check():
    if not is_weekday_ist():
        logger.info("Skipping Drawdown Check task (weekend).")
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping drawdown sentinel.")
        return
    logger.info("Triggering 07:00 PM Portfolio Drawdown & Circuit Breaker Check...")
    run_script("run_drawdown_check.py", timeout_seconds=300)


def job_symbol_sync():
    if not is_weekday_ist():
        return
    if _is_holiday_today():
        logger.info("Today is an official NSE trading holiday. Skipping symbol sync.")
        return
    logger.info("06:00 AM: Fyers symbol master sync...")
    try:
        from src.ingestion.symbol_sync import sync_instrument_master
        ok = sync_instrument_master()
        if not ok:
            from src.notification.telegram_bot import send_telegram_alert
            send_telegram_alert("⚠️ <b>SYMBOL SYNC WARNING</b>\nFyers instrument_master not updated.")
    except Exception as e:
        logger.error(f"Symbol sync failed: {e}")
        from src.notification.telegram_bot import send_telegram_alert
        send_telegram_alert(f"⚠️ <b>SYMBOL SYNC EXCEPTION:</b> {e}")


def job_db_maintenance():
    logger.info("Triggering Sunday 01:00 AM DuckDB Checkpoint, Maintenance & Vacuum...")
    run_script("run_db_maintenance.py", timeout_seconds=600)


def job_monthly_purification():
    now_ist = datetime.datetime.now(IST)
    if now_ist.day == 1:
        logger.info("Triggering 1st of Month Shariah Purification Report Generation...")
        run_script("generate_purification_report.py", timeout_seconds=300)


def job_weekly_evaluator():
    logger.info("Triggering Sunday 08:00 PM Weekly Portfolio Evaluator...")
    from src.utils.job_alert import job_alert_context
    with job_alert_context("job_weekly_evaluator"):
        from scripts.run_evaluator import run_evaluator
        run_evaluator()


def job_weekly_feedback_loop():
    logger.info("Triggering Sunday 08:30 PM Weekly Dynamic Feedback Learning Loop...")
    from src.utils.job_alert import job_alert_context
    with job_alert_context("job_weekly_feedback_loop"):
        from scripts.run_feedback_loop import evaluate_agent_learning_loop
        evaluate_agent_learning_loop()


def job_nightly_backup():
    logger.info("Triggering 02:00 AM Nightly DuckDB Cloud Backup...")
    from src.utils.job_alert import job_alert_context
    with job_alert_context("job_nightly_backup"):
        from scripts.run_nightly_backup import run_backup
        run_backup()


def job_monthly_hmm_refit():
    now_ist = datetime.datetime.now(IST)
    if now_ist.day == 1:
        logger.info("Triggering 1st of Month Gaussian HMM Regime Model Refit...")
        from src.utils.job_alert import job_alert_context
        with job_alert_context("job_monthly_hmm_refit"):
            from scripts.fit_hmm_regime import fit_and_save_hmm
            fit_and_save_hmm()


def job_monthly_retrain():
    now_ist = datetime.datetime.now(IST)
    if now_ist.day == 1:
        logger.info("Triggering 1st of Month Global XGBoost Model Retraining (run_monthly_retrain.py)...")
        run_script("run_monthly_retrain.py", timeout_seconds=1800)


def setup_schedule(include_symbol_sync: bool = True):
    tz = "Asia/Kolkata"

    # 0. 06:00 AM IST (Mon-Fri): Fyers Instrument Master Sync
    if include_symbol_sync:
        schedule.every().day.at("06:00", tz).do(job_symbol_sync)

    # 1. 08:30 AM IST (Mon-Fri): Pre-Market & Corporate Actions
    schedule.every().day.at("08:30", tz).do(job_premarket)

    # 2. 08:45 AM IST (Mon-Fri): Morning 2FA Token Refresh (scripts/fyers_auth.py)
    schedule.every().day.at("08:45", tz).do(job_fyers_auth)

    # 3. 08:50 AM IST (Mon-Fri): Morning Telegram Digest (send_morning_digest)
    schedule.every().day.at("08:50", tz).do(job_morning_digest)

    # 4. 19:00 IST (Mon-Fri): Bhavcopy Ingestion (bhavcopy.py)
    schedule.every().day.at("19:00", tz).do(job_bhavcopy_ingestion)

    # 5. 19:15 IST (Mon-Fri): EOD Screening (vcp_screener.py & regime_engine.py)
    schedule.every().day.at("19:15", tz).do(job_eod_screening)

    # 6. 19:30 IST (Mon-Fri): Nightly Holdings Guardian (fyers_guardian.py)
    schedule.every().day.at("19:30", tz).do(job_holdings_guardian)

    # 7. Sunday 01:00 AM IST: DB Maintenance & Vacuum
    schedule.every().sunday.at("01:00", tz).do(job_db_maintenance)

    # 8. Daily 08:00 AM IST check for 1st of Month: Purification Report
    schedule.every().day.at("08:00", tz).do(job_monthly_purification)

    # 9. Sunday 08:00 PM IST: Weekly Performance Evaluator
    schedule.every().sunday.at("20:00", tz).do(job_weekly_evaluator).tag("weekly_evaluator")

    # 10. Sunday 08:30 PM IST: Weekly Dynamic Feedback Learning Loop
    schedule.every().sunday.at("20:30", tz).do(job_weekly_feedback_loop).tag("weekly_feedback_loop")

    # 11. Daily 02:00 AM IST: Nightly DuckDB Cloud Backup
    schedule.every().day.at("02:00", tz).do(job_nightly_backup).tag("nightly_backup")

    # 12. Daily 00:30 AM IST check for 1st of Month: HMM Regime Refit
    schedule.every().day.at("00:30", tz).do(job_monthly_hmm_refit).tag("monthly_hmm_refit")

    # 13. Daily 01:30 AM IST check for 1st of Month: Global XGBoost Model Retraining
    schedule.every().day.at("01:30", tz).do(job_monthly_retrain).tag("monthly_retrain")


def main():
    global _scheduler_lock_fh
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # P1-1: Single-instance process lock to prevent concurrent orchestrators
    lock_file = PROJECT_ROOT / "logs" / ".scheduler.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    _scheduler_lock_fh = open(lock_file, "a+")
    try:
        portalocker.lock(_scheduler_lock_fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
        _scheduler_lock_fh.seek(0)
        _scheduler_lock_fh.truncate()
        _scheduler_lock_fh.write(f"{os.getpid()}\n")
        _scheduler_lock_fh.flush()
        logger.info(f"Scheduler instance lock acquired (PID={os.getpid()}).")
    except portalocker.LockException:
        logger.critical(
            "FATAL: Another instance of run_scheduler.py is already running. "
            "Exiting immediately to prevent double-firing and write collisions."
        )
        if _scheduler_lock_fh:
            try:
                _scheduler_lock_fh.close()
            except Exception:
                pass
            _scheduler_lock_fh = None
        sys.exit(1)

    # P1-2: Idempotent schema bootstrap & migrations at startup
    logger.info("Running idempotent database bootstrap & schema migrations...")
    from src.db.session import init_db
    try:
        init_db()
        logger.info("Database bootstrap & schema migrations complete.")
    except Exception as e:
        logger.critical(f"FATAL: Database bootstrap failed: {e}")
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("  AlphaSentinel Autonomous Master Scheduler Daemon Initialized")
    logger.info("  Timezone: IST (Asia/Kolkata, UTC+5:30)")
    logger.info("=" * 65)

    setup_schedule(include_symbol_sync=True)

    logger.info(f"Active scheduled jobs count: {len(schedule.jobs)}")
    for j in schedule.jobs:
        logger.info(f"  - {j}")

    logger.info("Master Scheduler running. Press Ctrl+C to terminate.")

    while not stop_requested:
        schedule.run_pending()
        time.sleep(1)

    if _scheduler_lock_fh:
        try:
            portalocker.unlock(_scheduler_lock_fh)
            _scheduler_lock_fh.close()
        except Exception:
            pass
        _scheduler_lock_fh = None

    logger.info("Master Scheduler has shut down cleanly.")


if __name__ == "__main__":
    main()

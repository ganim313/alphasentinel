"""
Job-Failure Alert Decorator and Context Manager.
Ensures that any unhandled exception in background cron scripts dispatches
a Telegram error alert containing job name, exception type, and full traceback.
"""

import logging
import traceback
import functools
from contextlib import contextmanager
from typing import Callable

logger = logging.getLogger(__name__)


def _send_alert(job_name: str, exc: Exception) -> None:
    """Dispatches a formatted error alert to Telegram. Fails silently if telegram errors."""
    try:
        from src.notification.telegram_bot import send_telegram_error_alert
        error_msg = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        send_telegram_error_alert(job_name, error_msg)
    except Exception as tg_err:
        logger.error(f"[job_alert] Failed to dispatch Telegram alert for {job_name}: {tg_err}")


def alert_on_failure(job_name: str) -> Callable:
    """Decorator: intercepts unhandled exceptions, dispatches Telegram alert, and re-raises."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.error(f"[{job_name}] Job execution failed: {exc}", exc_info=True)
                _send_alert(job_name, exc)
                raise
        return wrapper
    return decorator


@contextmanager
def job_alert_context(job_name: str):
    """Context manager for __main__ execution blocks."""
    try:
        yield
    except Exception as exc:
        logger.error(f"[{job_name}] Execution block failed: {exc}", exc_info=True)
        _send_alert(job_name, exc)
        raise

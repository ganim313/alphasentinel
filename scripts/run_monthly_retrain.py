#!/usr/bin/env python3
"""
Monthly Auto-Retraining Script.
Checks if the champion XGBoost model needs retraining based on:
1. Model age > 30 days
2. >= 20 new labeled trades in agent_memory since last training

Run via cron: 0 2 1 * * python scripts/run_monthly_retrain.py

Exit codes:
  0 - Retraining succeeded or was skipped (conditions not met)
  1 - Retraining attempted but failed
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import datetime
import json
import pickle

from src.db.session import get_read_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("run_monthly_retrain")

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "xgboost_global.pkl"
META_PATH = MODEL_DIR / "xgboost_global_meta.json"

# Retraining thresholds
MODEL_MAX_AGE_DAYS = 30          # Retrain if model is older than this
MIN_NEW_LABELED_TRADES = 20      # Minimum new labeled trades required to trigger retraining


def _try_send_notification(message: str) -> None:
    """Sends a Telegram notification. Silently logs on failure — never raises."""
    try:
        from src.notification.telegram_bot import send_telegram_alert
        result = send_telegram_alert(message)
        if result:
            logger.info("Telegram notification dispatched successfully.")
        else:
            logger.warning("Telegram notification returned False (possibly no token configured).")
    except Exception as e:
        logger.warning(f"Could not send Telegram notification: {e}")


def check_model_age() -> tuple[bool, float]:
    """
    Returns (needs_retrain: bool, age_days: float).
    Model is considered stale if it is older than MODEL_MAX_AGE_DAYS or does not exist.
    """
    if not MODEL_PATH.exists():
        logger.info(f"No model file found at {MODEL_PATH}. Retraining required.")
        return True, float("inf")

    mtime = datetime.datetime.fromtimestamp(MODEL_PATH.stat().st_mtime)
    age_days = (datetime.datetime.now() - mtime).total_seconds() / 86400
    needs_retrain = age_days > MODEL_MAX_AGE_DAYS

    logger.info(
        f"Model age: {age_days:.1f} days "
        f"(threshold: {MODEL_MAX_AGE_DAYS} days) → {'STALE' if needs_retrain else 'FRESH'}"
    )
    return needs_retrain, age_days


def count_new_labeled_trades(last_trained_at: datetime.datetime | None) -> int:
    """
    Counts rows in agent_memory where outcome_label IS NOT NULL and,
    if last_trained_at is known, where the record was created after that timestamp.

    Returns the count of qualifying labeled trades.
    """
    try:
        with get_read_connection() as conn:
            if last_trained_at is not None:
                # Use created_at or trade_date column if available; fall back to unfiltered count
                try:
                    row = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM agent_memory
                        WHERE outcome_label IS NOT NULL
                          AND created_at > ?
                        """,
                        [last_trained_at.isoformat()],
                    ).fetchone()
                except Exception:
                    # created_at column may not exist in all schema versions
                    logger.warning("Could not filter by created_at; counting all labeled trades.")
                    row = conn.execute(
                        "SELECT COUNT(*) FROM agent_memory WHERE outcome_label IS NOT NULL"
                    ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM agent_memory WHERE outcome_label IS NOT NULL"
                ).fetchone()

            count = int(row[0]) if row and row[0] is not None else 0
            logger.info(f"New labeled trades found: {count} (minimum required: {MIN_NEW_LABELED_TRADES})")
            return count
    except Exception as e:
        logger.error(f"Failed to query agent_memory for labeled trades: {e}")
        return 0


def read_last_trained_at() -> datetime.datetime | None:
    """
    Reads the 'trained_at' timestamp from the model metadata JSON.
    Returns None if the file doesn't exist or cannot be parsed.
    """
    if not META_PATH.exists():
        return None
    try:
        with open(META_PATH, "r") as f:
            meta = json.load(f)
        trained_at_str = meta.get("trained_at")
        if trained_at_str:
            return datetime.datetime.fromisoformat(trained_at_str)
    except Exception as e:
        logger.warning(f"Could not read model metadata from {META_PATH}: {e}")
    return None


def main() -> int:
    """
    Orchestrates the monthly retraining check.

    Returns:
        0 on success or intentional skip.
        1 on retraining failure.
    """
    logger.info("=" * 60)
    logger.info("AlphaSentinel Monthly Auto-Retraining Check")
    logger.info(f"Timestamp: {datetime.datetime.now().isoformat()}")
    logger.info("=" * 60)

    # --- Step 1: Model age check ---
    model_is_stale, age_days = check_model_age()
    if not model_is_stale:
        msg = (
            f"ℹ️ <b>Monthly Retrain: SKIPPED</b>\n"
            f"Model is only <b>{age_days:.1f} days</b> old (threshold: {MODEL_MAX_AGE_DAYS}d). "
            f"No retraining needed."
        )
        logger.info("Model is fresh. Retraining skipped.")
        _try_send_notification(msg)
        return 0

    # --- Step 2: Count new labeled trades ---
    last_trained_at = read_last_trained_at()
    if last_trained_at:
        logger.info(f"Last trained at: {last_trained_at.isoformat()}")
    else:
        logger.info("No previous training metadata found; counting all labeled trades.")

    new_trade_count = count_new_labeled_trades(last_trained_at)

    if new_trade_count < MIN_NEW_LABELED_TRADES:
        msg = (
            f"ℹ️ <b>Monthly Retrain: SKIPPED</b>\n"
            f"Only <b>{new_trade_count}</b> new labeled trades available "
            f"(minimum: {MIN_NEW_LABELED_TRADES}). "
            f"Model age: {age_days:.1f}d. Waiting for more outcomes."
        )
        logger.info(
            f"Insufficient labeled trades ({new_trade_count} < {MIN_NEW_LABELED_TRADES}). "
            "Retraining skipped."
        )
        _try_send_notification(msg)
        return 0

    # --- Step 3: Trigger retraining ---
    logger.info(
        f"Conditions met: model age={age_days:.1f}d, new trades={new_trade_count}. "
        "Triggering retraining..."
    )

    try:
        from scripts.run_model_training import train_global_model
        final_model, meta_data = train_global_model()

        msg = (
            f"✅ <b>Monthly Retrain: SUCCESS</b>\n"
            f"Model age was <b>{age_days:.1f}d</b>, "
            f"<b>{new_trade_count}</b> new labeled trades.\n"
            f"AUC (mean): <code>{meta_data.get('auc_mean', 'N/A')}</code> | "
            f"Conservative AUC: <code>{meta_data.get('auc_conservative', 'N/A')}</code>\n"
            f"Rows trained: <code>{meta_data.get('row_count', 'N/A')}</code>\n"
            f"Features: <code>{len(meta_data.get('features', []))}</code>"
        )
        logger.info("Retraining completed successfully.")
        logger.info(f"  AUC mean:         {meta_data.get('auc_mean')}")
        logger.info(f"  AUC conservative: {meta_data.get('auc_conservative')}")
        logger.info(f"  Row count:        {meta_data.get('row_count')}")
        logger.info(f"  Features:         {meta_data.get('features')}")
        _try_send_notification(msg)
        return 0

    except Exception as e:
        error_str = str(e)
        logger.error(f"Retraining FAILED: {error_str}", exc_info=True)
        msg = (
            f"🚨 <b>Monthly Retrain: FAILED</b>\n"
            f"Model age: <b>{age_days:.1f}d</b>, labeled trades: <b>{new_trade_count}</b>.\n"
            f"<b>Error:</b> <code>{error_str[:300]}</code>"
        )
        _try_send_notification(msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())

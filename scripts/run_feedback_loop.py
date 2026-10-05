"""
Weekend Dynamic Prompt Injection & Feedback Learning Loop.
Analyzes closed trade outcomes in DuckDB and injects empirical warnings
into agent prompts if win rates on specific patterns fall below 40%.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
from src.db.session import get_read_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_feedback_loop")


def evaluate_agent_learning_loop():
    logger.info("Executing Weekend Agent Feedback & Learning Loop...")

    with get_read_connection() as conn:
        stats = conn.execute("""
            SELECT 
                COUNT(*) AS total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
                AVG(realized_pnl) AS avg_pnl
            FROM positions
            WHERE status IN ('CLOSED', 'STOPPED_OUT', 'TARGET_REACHED');
        """).fetchone()

    total = stats[0] if stats else 0
    wins = stats[1] if (stats and stats[1]) else 0
    win_rate = (wins / total * 100) if total > 0 else 0.0

    logger.info(f"Historical Performance Summary: Total Trades={total} | Win Rate={win_rate:.1f}%")

    if total >= 5 and win_rate < 40.0:
        verdict = "WARNING"
        feedback_msg = (
            f"WARNING: Your historical win rate is currently {win_rate:.1f}% (<40%). "
            "Enforce stricter volume dry-up criteria and demand higher risk-reward (>2.5R) before approving setups."
        )
        logger.warning(f"Injecting Empirical Feedback Warning: {feedback_msg}")
    else:
        verdict = "HEALTHY"
        feedback_msg = f"System performance healthy. Win rate is {win_rate:.1f}% across {total} trades."
        logger.info("Win rate is within healthy parameters (>=40%). No prompt warnings injected.")

    # Persist weekly feedback to agent_memory
    try:
        from src.db.queue_writer import db_write
        import datetime
        from zoneinfo import ZoneInfo
        today = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        db_write(
            "INSERT OR REPLACE INTO agent_memory "
            "(symbol, memory_date, pattern_type, previous_verdict, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ["MARKET_WIDE", today, "STRATEGY_FEEDBACK", verdict, feedback_msg],
            sync=True
        )
        logger.info("Persisted weekly STRATEGY_FEEDBACK to agent_memory.")
    except Exception as e:
        logger.error(f"Failed to persist feedback to agent_memory: {e}")

    return verdict, feedback_msg


if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("run_feedback_loop"):
        evaluate_agent_learning_loop()

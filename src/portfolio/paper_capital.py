"""
Paper Trading Capital Manager.
Allows injecting, resetting, and tracking a configurable dummy capital amount
for paper trading — exactly simulating what happens when real money is deployed.

This module is the single source of truth for paper capital configuration.
It persists the paper capital setting in DuckDB so dashboard, arbiter, and
portfolio state all read the same value — no .env file edits needed.
"""

import logging
import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

PAPER_CAPITAL_CONFIG_TABLE = "paper_capital_config"


def _ensure_table(conn) -> None:
    """Create paper_capital_config table if it doesn't exist."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {PAPER_CAPITAL_CONFIG_TABLE} (
            id          INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            capital     DOUBLE  NOT NULL DEFAULT 1000000.0,
            label       VARCHAR DEFAULT 'Default Paper Account',
            set_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            reset_count INTEGER DEFAULT 0
        );
    """)
    # Seed with default ₹10 Lakhs if empty
    conn.execute(f"""
        INSERT OR IGNORE INTO {PAPER_CAPITAL_CONFIG_TABLE}
            (id, capital, label, reset_count)
        VALUES (1, 1000000.0, 'Default Paper Account', 0);
    """)


def get_paper_capital(conn=None) -> float:
    """
    Returns the currently configured paper capital (₹).
    Falls back to settings.ALGO_ALLOCATED_CAPITAL if the table is unavailable.
    """
    from src.config.settings import settings

    def _read(c) -> float:
        try:
            _ensure_table(c)
            row = c.execute(
                f"SELECT capital FROM {PAPER_CAPITAL_CONFIG_TABLE} WHERE id = 1"
            ).fetchone()
            return float(row[0]) if row and row[0] and float(row[0]) > 0 else float(settings.ALGO_ALLOCATED_CAPITAL)
        except Exception as e:
            logger.warning(f"Could not read paper capital config: {e}. Using settings default.")
            return float(settings.ALGO_ALLOCATED_CAPITAL)

    if conn is not None:
        return _read(conn)
    from src.db.session import get_read_connection
    with get_read_connection() as c:
        return _read(c)


def set_paper_capital(new_capital: float, label: str = "") -> Tuple[bool, str]:
    """
    Sets a new paper capital amount and writes it to DuckDB.
    Does NOT wipe existing positions — use reset_paper_portfolio() for a full reset.

    Args:
        new_capital: New capital in ₹ (must be between ₹10,000 and ₹1,00,00,000)
        label: Optional human-readable label (e.g. "Testing ₹2L scenario")

    Returns:
        (success: bool, message: str)
    """
    if new_capital < 10_000:
        return False, "Capital too low. Minimum allowed is ₹10,000."
    if new_capital > 1_00_00_000:
        return False, "Capital too high. Maximum allowed is ₹1 Crore."

    from src.db.queue_writer import db_write
    from src.db.session import get_read_connection

    try:
        with get_read_connection() as c:
            _ensure_table(c)

        label = label.strip() or f"Custom ₹{new_capital:,.0f} Account"
        db_write(
            f"""
            UPDATE {PAPER_CAPITAL_CONFIG_TABLE}
            SET capital = ?, label = ?, set_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (new_capital, label),
            sync=True,
        )

        # Also sync circuit_breaker_state HWM to the new capital baseline
        db_write(
            """
            UPDATE circuit_breaker_state
            SET high_water_mark = ?,
                monthly_peak_equity = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (new_capital, new_capital),
            sync=True,
        )

        logger.info(f"Paper capital set to ₹{new_capital:,.0f} ({label})")
        return True, f"✅ Paper capital set to ₹{new_capital:,.0f}. Label: '{label}'"
    except Exception as e:
        logger.error(f"Failed to set paper capital: {e}")
        return False, f"❌ Error setting paper capital: {e}"


def reset_paper_portfolio(new_capital: Optional[float] = None, label: str = "") -> Tuple[bool, str]:
    """
    Full paper portfolio reset:
    1. Closes all open positions (marks them MANUALLY_CLOSED with realized_pnl = 0)
    2. Clears screener_candidates queue
    3. Sets new capital (or keeps existing if None)
    4. Resets circuit_breaker_state HWM
    5. Increments reset_count for audit trail

    This simulates exactly what would happen if you started fresh with real money.

    Args:
        new_capital: New starting capital in ₹. If None, uses current configured capital.
        label: Label for this paper session

    Returns:
        (success: bool, message: str)
    """
    from src.db.queue_writer import db_write
    from src.db.session import get_read_connection

    try:
        with get_read_connection() as c:
            _ensure_table(c)
            current_capital = get_paper_capital(c)
            reset_count_row = c.execute(
                f"SELECT reset_count FROM {PAPER_CAPITAL_CONFIG_TABLE} WHERE id = 1"
            ).fetchone()
            current_reset_count = int(reset_count_row[0]) if reset_count_row else 0

        capital_to_use = float(new_capital) if new_capital and new_capital > 0 else current_capital

        if capital_to_use < 10_000 or capital_to_use > 1_00_00_000:
            return False, "Capital out of range (₹10,000 – ₹1 Crore)."

        today = datetime.date.today().isoformat()
        label = label.strip() or f"Paper Reset #{current_reset_count + 1} — ₹{capital_to_use:,.0f}"

        # 1. Close all open positions at entry price (zero P&L — fresh slate)
        db_write(
            """
            UPDATE positions
            SET status = 'MANUALLY_CLOSED',
                exit_date = ?,
                exit_price = entry_price,
                realized_pnl = 0.0
            WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')
            """,
            (today,),
            sync=True,
        )

        # 2. Clear pending screener queue
        db_write(
            """
            UPDATE screener_candidates
            SET status = 'REJECTED', rejection_reason = 'Paper portfolio reset'
            WHERE status IN ('PENDING', 'PENDING_REVIEW', 'APPROVED')
            """,
            sync=True,
        )

        # 3. Update paper capital config
        db_write(
            f"""
            UPDATE {PAPER_CAPITAL_CONFIG_TABLE}
            SET capital = ?, label = ?, set_at = CURRENT_TIMESTAMP,
                reset_count = reset_count + 1
            WHERE id = 1
            """,
            (capital_to_use, label),
            sync=True,
        )

        # 4. Reset circuit breaker HWM + monthly peak to new capital
        db_write(
            """
            UPDATE circuit_breaker_state
            SET high_water_mark = ?,
                monthly_peak_equity = ?,
                monthly_drawdown_pct = 0.0,
                is_halted = FALSE,
                halt_reason = 'RESET',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (capital_to_use, capital_to_use),
            sync=True,
        )

        msg = (
            f"✅ Paper portfolio reset complete.\n"
            f"   Starting capital: ₹{capital_to_use:,.0f}\n"
            f"   Session label: '{label}'\n"
            f"   Reset #{current_reset_count + 1}"
        )
        logger.info(msg)
        return True, msg

    except Exception as e:
        logger.error(f"Paper portfolio reset failed: {e}")
        return False, f"❌ Reset failed: {e}"


def get_paper_capital_info(conn=None) -> dict:
    """
    Returns full paper capital config info for dashboard display.
    """
    from src.config.settings import settings

    def _read(c) -> dict:
        try:
            _ensure_table(c)
            row = c.execute(
                f"SELECT capital, label, set_at, reset_count FROM {PAPER_CAPITAL_CONFIG_TABLE} WHERE id = 1"
            ).fetchone()
            if row:
                return {
                    "capital": float(row[0]),
                    "label": row[1] or "Paper Account",
                    "set_at": str(row[2]) if row[2] else "Unknown",
                    "reset_count": int(row[3]) if row[3] else 0,
                }
        except Exception as e:
            logger.warning(f"Could not read paper capital info: {e}")
        return {
            "capital": float(settings.ALGO_ALLOCATED_CAPITAL),
            "label": "Default (from .env)",
            "set_at": "N/A",
            "reset_count": 0,
        }

    if conn is not None:
        return _read(conn)
    from src.db.session import get_read_connection
    with get_read_connection() as c:
        return _read(c)

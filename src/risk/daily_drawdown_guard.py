"""
Daily Drawdown Kill-Switch Guard.

Checks whether today's portfolio has drawn down beyond a configured percentage
from the day-open (morning) core equity.  If breached, all new entries should
be blocked for the remainder of the trading session.

Design principles
-----------------
* Fail-open: any DB or data error returns (False, "") so a data outage never
  silently halts trading.  Only a confirmed drawdown breach returns True.
* Single responsibility: this module ONLY computes the intraday drawdown
  ratio.  Caller (second_opinion_gate) decides what to do with the result.
* Read-only: uses get_read_connection() exclusively – no writes.
"""

import logging
from datetime import datetime
from typing import Tuple
from zoneinfo import ZoneInfo

from src.db.session import get_read_connection

logger = logging.getLogger(__name__)


def is_daily_drawdown_breached(threshold_pct: float = 3.0) -> Tuple[bool, str]:
    """
    Check whether today's portfolio has drawn down more than ``threshold_pct``
    from the day-open core equity.

    Parameters
    ----------
    threshold_pct : float
        Maximum tolerated intraday drawdown expressed as a percentage
        (e.g. ``3.0`` means 3 %).  Read from ``src/config/strategy.yaml``
        by the caller; the default here acts as a hard-coded safety net.

    Returns
    -------
    (is_breached, reason) : tuple[bool, str]
        * ``is_breached`` – ``True`` only when the drawdown is confirmed to
          exceed the threshold.  ``False`` in all other cases (including data
          unavailability).
        * ``reason`` – human-readable explanation; empty string when not breached.

    Notes
    -----
    * The "day-open equity" is the ``core_equity`` snapshot stored in the
      ``equity_curve`` table for today's date.  If that row is absent (first
      run of the day, or table empty) the starting equity falls back to the
      live ``get_portfolio_state()`` snapshot, which effectively means no
      drawdown can be detected yet – safe fail-open behaviour.
    * Current equity = starting equity + sum of today's unrealized PnL changes
      derived from the ``positions`` table.
    * Fails open (returns ``False``) on *any* exception so that a DB outage or
      missing table never blocks trading.
    """
    try:
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        with get_read_connection() as conn:
            # ----------------------------------------------------------------
            # 1. Today's unrealized PnL + today's intraday realized PnL
            # ----------------------------------------------------------------
            unrealized_res = conn.execute(
                """
                SELECT COALESCE(SUM(unrealized_pnl), 0.0)
                FROM positions
                WHERE status IN ('OPEN', 'TARGET_1_TRIMMED', 'MARKED_FOR_CLOSURE')
                  AND unrealized_pnl IS NOT NULL
                """
            ).fetchone()
            todays_unrealized_pnl = float(unrealized_res[0]) if unrealized_res and unrealized_res[0] is not None else 0.0

            realized_today_res = conn.execute(
                """
                SELECT COALESCE(SUM(realized_pnl), 0.0)
                FROM positions
                WHERE status IN ('CLOSED', 'STOPPED_OUT', 'TARGET_REACHED')
                  AND exit_date = ?
                  AND realized_pnl IS NOT NULL
                """,
                (today,),
            ).fetchone()
            todays_realized_pnl = float(realized_today_res[0]) if realized_today_res and realized_today_res[0] is not None else 0.0

            from src.portfolio.state import get_portfolio_state
            pstate = get_portfolio_state(conn=conn)
            live_core_equity = float(pstate.get("core_equity", 0.0))

            # ----------------------------------------------------------------
            # 2. Day-open (starting) equity from equity_curve snapshot (today or most recent prior EOD)
            # ----------------------------------------------------------------
            starting_equity: float | None = None
            realized_base_at_open: float | None = None
            try:
                row = conn.execute(
                    "SELECT core_equity, trade_date, COALESCE(unrealized_pnl, 0.0) FROM equity_curve WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 1",
                    (today,),
                ).fetchone()
                if row and row[0] is not None:
                    starting_equity = float(row[0])
                    snap_unrealized = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0
                    # Strip the prior snapshot's unrealized PnL so carryover open positions are not double-counted
                    realized_base_at_open = starting_equity - snap_unrealized
            except Exception as ec_err:
                logger.debug(f"[DailyDrawdownGuard] equity_curve query failed: {ec_err}")

            if starting_equity is None:
                # Reconstruct day-open baseline before today's unrealized and realized PnL (avoids double-counting)
                starting_equity = live_core_equity - todays_unrealized_pnl - todays_realized_pnl
                realized_base_at_open = starting_equity
                logger.debug(
                    f"[DailyDrawdownGuard] No equity_curve row up to {today}; "
                    f"reconstructed day-open baseline={starting_equity:.2f}."
                )

            if starting_equity <= 0:
                logger.warning(
                    "[DailyDrawdownGuard] Starting equity is zero or negative – failing open."
                )
                return False, ""

            # ----------------------------------------------------------------
            # 3. Current equity estimate (day-open realized base + today's intraday realized & unrealized PnL)
            # ----------------------------------------------------------------
            base_eq = realized_base_at_open if realized_base_at_open is not None else starting_equity
            current_equity = base_eq + todays_unrealized_pnl + todays_realized_pnl

            # ----------------------------------------------------------------
            # 4. Drawdown ratio
            # ----------------------------------------------------------------
            drawdown_pct = ((starting_equity - current_equity) / starting_equity) * 100.0

            logger.debug(
                f"[DailyDrawdownGuard] starting={starting_equity:.2f}, "
                f"current={current_equity:.2f}, drawdown={drawdown_pct:.4f}%, "
                f"threshold={threshold_pct:.2f}%"
            )

            if drawdown_pct > threshold_pct:
                reason = (
                    f"Daily drawdown {drawdown_pct:.2f}% exceeds halt threshold {threshold_pct:.2f}%. "
                    f"Starting equity: ₹{starting_equity:,.2f} → "
                    f"Current equity: ₹{current_equity:,.2f}. "
                    "All new entries blocked for today's session."
                )
                logger.critical(f"[DailyDrawdownGuard] KILL-SWITCH TRIGGERED — {reason}")
                return True, reason

            return False, ""

    except Exception as e:
        # Fail open: never block trading due to a monitoring error
        logger.error(
            f"[DailyDrawdownGuard] Unexpected error during drawdown check – "
            f"failing open to avoid false halt. Error: {e}"
        )
        return False, ""

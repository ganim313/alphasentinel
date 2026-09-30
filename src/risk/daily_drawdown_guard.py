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
from datetime import date
from typing import Tuple

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
        today = date.today()
        with get_read_connection() as conn:
            # ----------------------------------------------------------------
            # 1. Day-open (starting) equity from equity_curve snapshot
            # ----------------------------------------------------------------
            starting_equity: float | None = None
            try:
                row = conn.execute(
                    "SELECT core_equity FROM equity_curve WHERE trade_date = ?",
                    (today,),
                ).fetchone()
                if row and row[0] is not None:
                    starting_equity = float(row[0])
            except Exception as ec_err:
                logger.debug(f"[DailyDrawdownGuard] equity_curve query failed: {ec_err}")

            if starting_equity is None:
                # Fallback: use live portfolio state as starting equity.
                # This means we cannot detect a drawdown yet (conservative / fail-open).
                from src.portfolio.state import get_portfolio_state
                pstate = get_portfolio_state(conn=conn)
                starting_equity = float(pstate.get("core_equity", 0.0))
                logger.debug(
                    f"[DailyDrawdownGuard] No equity_curve row for {today}; "
                    f"using live core_equity={starting_equity:.2f} as starting baseline."
                )

            if starting_equity <= 0:
                logger.warning(
                    "[DailyDrawdownGuard] Starting equity is zero or negative – failing open."
                )
                return False, ""

            # ----------------------------------------------------------------
            # 2. Today's unrealized PnL delta from open positions
            #    (positions opened or active today contribute their current
            #     unrealized_pnl; we sum across all open positions)
            # ----------------------------------------------------------------
            unrealized_res = conn.execute(
                """
                SELECT COALESCE(SUM(unrealized_pnl), 0.0)
                FROM positions
                WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')
                  AND unrealized_pnl IS NOT NULL
                """
            ).fetchone()
            todays_unrealized_pnl = float(unrealized_res[0]) if unrealized_res and unrealized_res[0] is not None else 0.0

            # ----------------------------------------------------------------
            # 3. Current equity estimate
            # ----------------------------------------------------------------
            current_equity = starting_equity + todays_unrealized_pnl

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

"""
Shared Portfolio State Module.
Single authoritative source for core equity, drawdown metrics, and Sharpe ratio.
All other modules (arbiter, drawdown_check, order_manager, dashboard) must import from here.
"""

import math
import logging
import datetime
from typing import Dict, Any, Optional
from src.config.settings import settings
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)

def _load_initial_capital() -> float:
    """
    Loads the authoritative paper capital from DuckDB (paper_capital_config table).
    Falls back to settings.ALGO_ALLOCATED_CAPITAL if the table is unavailable on first boot.
    This ensures any capital configured via the dashboard is used everywhere.
    """
    try:
        from src.portfolio.paper_capital import get_paper_capital
        return get_paper_capital()
    except Exception:
        return float(settings.ALGO_ALLOCATED_CAPITAL)

INITIAL_CAPITAL: float = _load_initial_capital()


def get_portfolio_state(conn=None) -> Dict[str, Any]:
    """
    Computes the canonical portfolio state snapshot.

    Returns dict containing:
        core_equity          (float) - INITIAL_CAPITAL + realized_pnl + unrealized_pnl
        realized_pnl_total   (float) - sum of realized PnL across all closed/trimmed positions
        unrealized_pnl_total (float) - sum of unrealized PnL of open positions
        open_positions_value (float) - sum of (current_ltp * quantity) for open positions
        available_cash       (float) - core_equity - open_positions_value
        lifetime_hwm         (float) - all-time high-water mark
        lifetime_hwm_dd_pct  (float) - (lifetime_hwm - core_equity) / lifetime_hwm * 100
        monthly_peak_equity  (float) - highest core_equity recorded this calendar month
        monthly_dd_pct       (float) - (monthly_peak - core_equity) / monthly_peak * 100
        annualized_sharpe    (float) - daily equity curve Sharpe * sqrt(252) (0.0 if < 10 days)
        as_of                (str)   - ISO timestamp of computation
    """
    def _compute(db_conn) -> Dict[str, Any]:
        # 1. Total Realized PnL
        realized_res = db_conn.execute("""
            SELECT COALESCE(SUM(realized_pnl), 0.0)
            FROM positions
            WHERE status IN ('TARGET_REACHED', 'STOPPED_OUT', 'CLOSED', 'MANUALLY_CLOSED', 'TARGET_1_TRIMMED')
              AND realized_pnl IS NOT NULL
        """).fetchone()
        realized_pnl_total = float(realized_res[0]) if realized_res and realized_res[0] is not None else 0.0

        # 2. Total Unrealized PnL
        unrealized_res = db_conn.execute("""
            SELECT COALESCE(SUM(unrealized_pnl), 0.0)
            FROM positions
            WHERE status IN ('OPEN', 'TARGET_1_TRIMMED', 'MARKED_FOR_CLOSURE')
              AND unrealized_pnl IS NOT NULL
        """).fetchone()
        unrealized_pnl_total = float(unrealized_res[0]) if unrealized_res and unrealized_res[0] is not None else 0.0

        # 3. Market value of open positions
        open_positions_value = 0.0
        try:
            cols = [
                row[1].lower()
                for row in db_conn.execute("PRAGMA table_info('positions');").fetchall()
            ]
            has_ltp = "current_ltp" in cols
            has_entry = "entry_price" in cols
            has_qty = "quantity" in cols

            if not has_qty:
                open_positions_value = 0.0
            else:
                if has_ltp and has_entry:
                    price_expr = "COALESCE(current_ltp, entry_price, 0.0)"
                elif has_ltp:
                    price_expr = "COALESCE(current_ltp, 0.0)"
                elif has_entry:
                    price_expr = "COALESCE(entry_price, 0.0)"
                else:
                    price_expr = "0.0"

                open_val_res = db_conn.execute(f"""
                    SELECT COALESCE(SUM({price_expr} * quantity), 0.0)
                    FROM positions
                    WHERE status IN ('OPEN', 'TARGET_1_TRIMMED', 'MARKED_FOR_CLOSURE')
                """).fetchone()
                open_positions_value = float(open_val_res[0]) if open_val_res and open_val_res[0] is not None else 0.0
        except Exception as e:
            logger.debug(f"Could not compute open positions value: {e}")
            open_positions_value = 0.0

        # 4. Core live equity & available cash — refresh capital dynamically
        # so any capital change via dashboard takes effect without a restart
        try:
            from src.portfolio.paper_capital import get_paper_capital
            initial_capital = get_paper_capital(db_conn)
        except Exception:
            initial_capital = float(getattr(settings, "ALGO_ALLOCATED_CAPITAL", INITIAL_CAPITAL))
        core_equity = initial_capital + realized_pnl_total + unrealized_pnl_total
        available_cash = core_equity - open_positions_value

        # 5. Lifetime High-Water Mark (with equity_curve fallback for corrupted/missing HWM state)
        stored_hwm = initial_capital
        try:
            hwm_res = db_conn.execute("""
                SELECT high_water_mark FROM circuit_breaker_state WHERE id = 1
            """).fetchone()
            if hwm_res and hwm_res[0] is not None and float(hwm_res[0]) > 0:
                stored_hwm = float(hwm_res[0])
            else:
                # Secondary recovery fallback: check historical maximum from equity_curve
                eq_res = db_conn.execute("SELECT MAX(core_equity) FROM equity_curve;").fetchone()
                if eq_res and eq_res[0] is not None and float(eq_res[0]) > 0:
                    stored_hwm = max(initial_capital, float(eq_res[0]))
        except Exception as e:
            logger.debug(f"Circuit breaker high_water_mark query: {e}")
            try:
                eq_res = db_conn.execute("SELECT MAX(core_equity) FROM equity_curve;").fetchone()
                if eq_res and eq_res[0] is not None and float(eq_res[0]) > 0:
                    stored_hwm = max(initial_capital, float(eq_res[0]))
            except Exception:
                stored_hwm = initial_capital

        lifetime_hwm = max(stored_hwm, core_equity)
        lifetime_hwm_dd_pct = (
            ((lifetime_hwm - core_equity) / lifetime_hwm) * 100.0
            if lifetime_hwm > 0 and core_equity < lifetime_hwm else 0.0
        )

        # 6. Monthly Peak Equity & Monthly Drawdown (Resets on new calendar month)
        stored_mpeak = initial_capital
        try:
            mpeak_res = db_conn.execute("""
                SELECT monthly_peak_equity, updated_at FROM circuit_breaker_state WHERE id = 1
            """).fetchone()
            if mpeak_res and mpeak_res[0] is not None and float(mpeak_res[0]) > 0:
                mpeak_val = float(mpeak_res[0])
                updated_at = mpeak_res[1]
                now = datetime.datetime.now()
                is_same_month = True
                if updated_at is not None:
                    if hasattr(updated_at, "year") and hasattr(updated_at, "month"):
                        if updated_at.year != now.year or updated_at.month != now.month:
                            is_same_month = False
                    elif isinstance(updated_at, str):
                        if not updated_at.startswith(now.strftime("%Y-%m")):
                            is_same_month = False
                
                if is_same_month:
                    stored_mpeak = mpeak_val
                else:
                    # New calendar month: reset monthly peak equity to start at core_equity
                    stored_mpeak = core_equity
        except Exception as e:
            logger.debug(f"Circuit breaker monthly_peak_equity query: {e}")
            stored_mpeak = initial_capital

        monthly_peak = max(stored_mpeak, core_equity)
        monthly_dd_pct = (
            ((monthly_peak - core_equity) / monthly_peak) * 100.0
            if monthly_peak > 0 and core_equity < monthly_peak else 0.0
        )

        # 7. Annualized Sharpe Ratio from closed trade equity series
        annualized_sharpe = 0.0
        try:
            daily_rows = db_conn.execute("""
                SELECT exit_date, SUM(realized_pnl) AS daily_pnl
                FROM positions
                WHERE status IN ('TARGET_REACHED', 'STOPPED_OUT', 'CLOSED', 'MANUALLY_CLOSED')
                  AND exit_date IS NOT NULL AND realized_pnl IS NOT NULL
                GROUP BY exit_date
                ORDER BY exit_date ASC
            """).fetchall()

            if len(daily_rows) >= 10:
                equity_curve = []
                cumulative = initial_capital
                for _, daily_pnl in daily_rows:
                    cumulative += float(daily_pnl)
                    equity_curve.append(cumulative)

                returns = [
                    (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
                    for i in range(1, len(equity_curve))
                    if equity_curve[i - 1] > 0
                ]
                if len(returns) >= 2:
                    mean_r = sum(returns) / len(returns)
                    variance = max(0.0, sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
                    std_r = math.sqrt(variance) if variance > 0 else 0.0
                    annualized_sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0.0
        except Exception as e:
            logger.warning(f"Could not compute annualized Sharpe: {e}")

        return {
            "core_equity": round(core_equity, 2),
            "realized_pnl_total": round(realized_pnl_total, 2),
            "unrealized_pnl_total": round(unrealized_pnl_total, 2),
            "open_positions_value": round(open_positions_value, 2),
            "available_cash": round(available_cash, 2),
            "lifetime_hwm": round(lifetime_hwm, 2),
            "lifetime_hwm_dd_pct": round(lifetime_hwm_dd_pct, 4),
            "monthly_peak_equity": round(monthly_peak, 2),
            "monthly_dd_pct": round(monthly_dd_pct, 4),
            "annualized_sharpe": round(annualized_sharpe, 4),
            "as_of": datetime.datetime.now().isoformat(),
        }

    if conn is not None:
        return _compute(conn)
    with get_read_connection() as c:
        return _compute(c)

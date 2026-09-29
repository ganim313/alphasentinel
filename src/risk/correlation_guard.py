"""
Portfolio Correlation Guard.
Rejects a new candidate if its 60-day daily return series shows high average
pairwise Pearson correlation with all currently open positions.
Prevents hidden concentration risk in momentum clusters.

Fails OPEN (allows trade) on infrastructure/data errors — this is a soft risk guard.
"""
import logging
import math
from typing import Tuple, Dict, Optional
import numpy as np
import pandas as pd
from src.db.session import get_read_connection
from src.config.settings import settings

logger = logging.getLogger(__name__)
_LOOKBACK = 60  # trading days


def evaluate_correlation_guard(
    candidate_symbol: str,
    threshold: Optional[float] = None,
) -> Tuple[bool, str, Dict]:
    """
    Returns (passed: bool, reason: str, metrics: dict).
    passed=True  -> Safe to proceed.
    passed=False -> Reject due to high correlation with open portfolio.
    """
    if threshold is None:
        threshold = getattr(settings, "CORRELATION_GUARD_THRESHOLD", 0.65)

    try:
        with get_read_connection() as conn:
            open_syms = [
                r[0] for r in conn.execute("""
                    SELECT DISTINCT symbol FROM positions
                    WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')
                """).fetchall() if r[0] != candidate_symbol
            ]

        if not open_syms:
            return True, "CORR_GUARD_SKIPPED: no open positions to correlate against.", {}

        all_syms = [candidate_symbol] + open_syms
        placeholders = ",".join(["?"] * len(all_syms))

        with get_read_connection() as conn:
            df = conn.execute(f"""
                SELECT symbol, trade_date, close_price
                FROM bhavcopy_daily
                WHERE symbol IN ({placeholders})
                  AND trade_date >= (CURRENT_DATE - INTERVAL '90 days')
                ORDER BY trade_date ASC
            """, all_syms).df()

        if df.empty:
            return True, "CORR_GUARD_SKIPPED: no price history found in bhavcopy_daily.", {}

        pivot = df.pivot(index="trade_date", columns="symbol", values="close_price")
        pivot = pivot.ffill(limit=3).dropna()
        returns = pivot.pct_change().dropna().tail(_LOOKBACK)

        if candidate_symbol not in returns.columns or len(returns) < 15:
            return True, "CORR_GUARD_SKIPPED: insufficient overlapping history.", {}

        corr_matrix = returns.corr(method="pearson")
        candidate_corrs = {
            sym: float(corr_matrix.loc[candidate_symbol, sym])
            for sym in open_syms
            if sym in corr_matrix.columns
            and not math.isnan(corr_matrix.loc[candidate_symbol, sym])
        }

        if not candidate_corrs:
            return True, "CORR_GUARD_SKIPPED: correlation matrix empty for open positions.", {}

        avg_corr = float(np.mean(list(candidate_corrs.values())))
        max_sym = max(candidate_corrs, key=lambda k: abs(candidate_corrs[k]))
        metrics = {
            "avg_pairwise_corr": round(avg_corr, 4),
            "max_corr_symbol": max_sym,
            "max_corr_value": round(candidate_corrs[max_sym], 4),
            "threshold": threshold,
            "lookback_days": len(returns),
        }

        if avg_corr > threshold:
            reason = (
                f"CORR_GUARD_REJECTED: {candidate_symbol} avg {len(returns)}d Pearson={avg_corr:.3f} > {threshold}. "
                f"Most correlated with open position {max_sym} ({candidate_corrs[max_sym]:.3f})."
            )
            return False, reason, metrics

        return True, f"CORR_GUARD_PASSED: avg_corr={avg_corr:.3f} <= {threshold}", metrics

    except Exception as exc:
        logger.error(f"correlation_guard error for {candidate_symbol}: {exc}", exc_info=True)
        return True, f"CORR_GUARD_ERROR (failing open): {exc}", {}

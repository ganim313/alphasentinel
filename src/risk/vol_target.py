"""
Portfolio Volatility Targeting Module.
Computes a scalar L_t in (0, 1] that scales down suggested_shares
when the proposed portfolio's annualized volatility exceeds VOL_TARGET_ANNUAL.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from src.config.settings import settings
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)


def _fetch_covariance_matrix(symbols: List[str], lookback_days: int = 60) -> Optional[np.ndarray]:
    """
    Fetches daily returns from bhavcopy_daily for each symbol and computes
    the annualized covariance matrix (x252). Symbols must be in sorted order
    to ensure deterministic alignment with the weights vector.

    Returns None if fewer than 15 overlapping trading days exist.
    """
    if not symbols:
        return None

    symbols_sorted = sorted(symbols)
    placeholders = ", ".join(["?"] * len(symbols_sorted))
    query = f"""
        SELECT symbol, trade_date, close_price
        FROM bhavcopy_daily
        WHERE symbol IN ({placeholders})
          AND trade_date >= (CURRENT_DATE - INTERVAL '{lookback_days + 15} days')
          AND total_traded_qty > 0
        ORDER BY trade_date ASC
    """
    try:
        with get_read_connection() as conn:
            df = conn.execute(query, symbols_sorted).df()
    except Exception as e:
        logger.warning(f"VolTarget: DB query failed: {e}")
        return None

    if df.empty:
        return None

    pivot = df.pivot(index="trade_date", columns="symbol", values="close_price")
    # Ensure all symbols are present
    missing = [s for s in symbols_sorted if s not in pivot.columns]
    if missing:
        logger.debug(f"VolTarget: Missing symbols in bhavcopy: {missing}")
        return None

    returns = pivot[symbols_sorted].pct_change().dropna()

    if len(returns) < 15:
        logger.debug(
            f"VolTarget: Only {len(returns)} overlapping trading days -- "
            "insufficient for covariance matrix. Returning None."
        )
        return None

    cov_daily = returns.cov().values  # shape: (n, n)
    cov_annualized = cov_daily * 252.0
    return cov_annualized


def calculate_volatility_scalar(
    open_positions: Dict[str, float],   # {symbol: current_value}
    candidate_symbol: str,
    candidate_value: float,
    core_equity: float,
    cov_matrix: Optional[np.ndarray] = None,
    fallback_scalar: float = 1.0,
) -> float:
    """
    Computes L_t in (0, 1] to scale down suggested_shares for the candidate.

    Args:
        open_positions:   {symbol: position_value} for open positions
        candidate_symbol: Symbol being evaluated
        candidate_value:  Proposed position value = suggested_shares * entry_price
        core_equity:      Current portfolio equity from portfolio_state
        cov_matrix:       Optional precomputed covariance matrix (used in unit tests)
        fallback_scalar:  Scalar returned when covariance data is insufficient (default 1.0)

    Returns:
        fallback_scalar (default 1.0) if portfolio is under vol target or insufficient data.
        < 1.0 if portfolio would exceed sigma_target.
    """
    if core_equity <= 0 or candidate_value <= 0:
        return 1.0

    # Build proposed portfolio: existing + candidate
    proposed = dict(open_positions)
    proposed[candidate_symbol] = proposed.get(candidate_symbol, 0.0) + candidate_value

    symbols = sorted(proposed.keys())
    if len(symbols) < 2:
        return 1.0   # Cannot compute meaningful portfolio variance with < 2 assets

    if cov_matrix is None:
        cov_matrix = _fetch_covariance_matrix(symbols, settings.VOL_TARGET_LOOKBACK_DAYS)

    if cov_matrix is None or cov_matrix.shape != (len(symbols), len(symbols)):
        return float(fallback_scalar)   # Insufficient data or shape mismatch

    # Weights aligned with sorted symbol order
    weights = np.array([proposed[s] / core_equity for s in symbols], dtype=float)

    port_var = float(weights.T @ cov_matrix @ weights)
    if port_var <= 0:
        return 1.0

    port_vol = float(np.sqrt(port_var))
    target = float(settings.VOL_TARGET_ANNUAL)
    scalar = min(1.0, target / port_vol)

    logger.debug(
        f"VolTarget [{candidate_symbol}]: port_vol={port_vol:.4f}, "
        f"target={target:.2f}, scalar={scalar:.4f}"
    )
    return float(scalar)

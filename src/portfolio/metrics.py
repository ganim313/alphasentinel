"""
Portfolio Performance Metrics including Deflated Sharpe Ratio (DSR) & PBO.
Used by run_evaluator.py for weekly reporting.
Based on Bailey & Lopez de Prado (2014): 'The Deflated Sharpe Ratio'.
"""
import math
import logging
import numpy as np
import scipy.stats as stats

logger = logging.getLogger(__name__)


def compute_dsr(
    observed_sharpe: float,
    n_trials: int,
    daily_returns: np.ndarray,
    periods_per_year: int = 252,
) -> float:
    """
    Compute the Deflated Sharpe Ratio (DSR).

    DSR answers: Given N strategy configurations tested, what is the probability
    that the observed Sharpe ratio is statistically > 0 (not an artifact of selection bias / multiple testing)?

    Formula:
        E[max(SR_N)] ~= sqrt(2 * ln(N))  (for N > 1, else 0.0)
        Var(SR) = 1 - (gamma_3 * SR) + ((gamma_4 - 1)/4 * SR^2)
        z = ((SR - E[max(SR_N)]) * sqrt(T)) / sqrt(Var(SR))
        DSR = Phi(z)

    Args:
        observed_sharpe: Annualized Sharpe ratio from equity curve.
        n_trials: Number of distinct strategy parameter configurations in strategy_version.
        daily_returns: 1-D array of daily portfolio returns.
        periods_per_year: 252 for daily equity trading.

    Returns:
        DSR in [0, 1]. Values > 0.95 indicate the Sharpe is statistically significant after deflating for N.
    """
    if n_trials < 1:
        n_trials = 1

    if daily_returns is None or len(daily_returns) < 10:
        logger.debug("DSR: Insufficient return history (< 10 obs). Returning DSR=0.0.")
        return 0.0

    returns = np.asarray(daily_returns, dtype=float)
    returns = returns[~np.isnan(returns)]
    if len(returns) < 10:
        return 0.0

    T_years = len(returns) / periods_per_year
    if T_years <= 0:
        return 0.0

    skew = float(stats.skew(returns))
    # Pearson kurtosis (normal distribution = 3, not 0): fisher=False
    kurt = float(stats.kurtosis(returns, fisher=False))

    expected_max_sr = math.sqrt(2.0 * math.log(n_trials)) if n_trials > 1 else 0.0

    # Variance of Sharpe estimator (denominator)
    var_sr = 1.0 - (skew * observed_sharpe) + (((kurt - 1.0) / 4.0) * (observed_sharpe ** 2))
    var_sr = max(var_sr, 0.001)  # Safety floor against degenerate variance

    z_stat = ((observed_sharpe - expected_max_sr) * math.sqrt(T_years)) / math.sqrt(var_sr)
    dsr = float(stats.norm.cdf(z_stat))

    logger.debug(
        f"DSR: SR={observed_sharpe:.3f}, N={n_trials}, T={T_years:.2f}yr, "
        f"E[maxSR]={expected_max_sr:.3f}, DSR={dsr:.4f}, PBO={1.0-dsr:.4f}"
    )
    return dsr

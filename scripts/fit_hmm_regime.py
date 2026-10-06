"""
Monthly HMM Regime Model Fitter (P6-1).
Fits a 3-state Gaussian HMM on canonical benchmark log-returns and saves to models/hmm_regime.pkl.
States are sorted by mean return:
  State 0: Crisis (lowest mean return)
  State 1: Choppy (median return)
  State 2: Calm / Bull (highest mean return)
"""
import os
import sys
import logging
from pathlib import Path
import numpy as np
import joblib
from hmmlearn.hmm import GaussianHMM

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.benchmark_provider import get_benchmark_ohlc

logger = logging.getLogger("fit_hmm_regime")
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "hmm_regime.pkl"


def fit_and_save_hmm(model_path: str = str(MODEL_PATH), lookback_days: int = 1825) -> GaussianHMM:
    """
    Fits 3-state Gaussian HMM on benchmark log returns.
    Ensures state ordering: 0=Crisis (negative mean return / high vol), 1=Choppy, 2=Calm.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df = get_benchmark_ohlc(lookback_days=lookback_days)
    if df is None or len(df) < 50:
        raise ValueError(f"Insufficient benchmark data for HMM fitting (< 50 rows, got {len(df) if df is not None else 0})")

    close = df["Close"].dropna()
    returns = np.log(close / close.shift(1)).dropna().values.reshape(-1, 1)
    if len(returns) < 50:
        raise ValueError("Insufficient return history for HMM fitting (< 50 valid returns)")

    raw_model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=1000, random_state=42)
    raw_model.fit(returns)

    # Sort states by fitted mean return (lowest to highest: 0=Crisis, 1=Choppy, 2=Calm)
    order = np.argsort(raw_model.means_.flatten())

    raw_model.startprob_ = raw_model.startprob_[order]
    raw_model.transmat_ = raw_model.transmat_[order, :][:, order]
    raw_model.means_ = raw_model.means_[order]
    raw_model.covars_ = raw_model.covars_[order].reshape(3, -1)

    # Anchor State 0 (Crisis/Bear) to a strictly negative mean return and highest tail variance
    # if EM converged all 3 states onto positive drift sub-clusters during a prolonged bull window.
    flat_rets = returns.flatten()
    neg_rets = flat_rets[flat_rets < 0.0]
    emp_neg_tail = float(np.percentile(neg_rets, 25)) if len(neg_rets) > 0 else -max(float(np.std(flat_rets)), 0.005)
    if float(raw_model.means_[0, 0]) >= 0.0:
        raw_model.means_[0, 0] = min(emp_neg_tail, float(raw_model.means_[1, 0]) - 1e-4, -0.0025)
    cov_flat = raw_model.covars_.flatten().copy()
    max_cov = float(np.max(cov_flat))
    if float(cov_flat[0]) < max_cov:
        cov_flat[0] = max_cov * 1.25
        raw_model.covars_ = cov_flat.reshape(3, -1)

    joblib.dump(raw_model, model_path)
    logger.info(
        f"HMM Regime Model successfully saved to {model_path}. "
        f"State Means: {raw_model.means_.flatten().tolist()}"
    )
    return raw_model


if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("fit_hmm_regime"):
        fit_and_save_hmm()

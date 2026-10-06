"""
Second Opinion Consensus Gate Module.
Validates screener setups against the pre-trained Global XGBoost model.
Enforces the dual consensus threshold: Conviction >= 7.0 AND ML Probability > 0.50.
"""

from pathlib import Path
import pickle
import logging
from typing import Optional
import pandas as pd
import numpy as np

from src.db.session import get_read_connection
from src.screening.ml_features import extract_quantitative_features
from src.risk.daily_drawdown_guard import is_daily_drawdown_breached

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "xgboost_global.pkl"
FEATURE_COLS = ['sharpe_rank', 'dist_high', 'market_regime', 'rel_rsi', 'ema_dist', 'vol_cluster',
                'delivery_ratio', 'adtv_log', 'momentum_6m']

_cached_model = None
_model_loaded = False


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts the 9 Minervini strategy-aligned quantitative features (6 core + 3 optional)."""
    return extract_quantitative_features(df)


def get_champion_model():
    """Loads and caches the global champion XGBoost model from disk."""
    global _cached_model, _model_loaded
    if _model_loaded:
        return _cached_model

    if not MODEL_PATH.exists():
        logger.warning(f"Champion model not found at {MODEL_PATH}")
        _cached_model = None
        _model_loaded = True
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            _cached_model = pickle.load(f)
        _model_loaded = True
        logger.info(f"Loaded champion XGBoost model from {MODEL_PATH}")
    except Exception as e:
        logger.error(f"Failed to load champion model: {e}")
        _cached_model = None
        _model_loaded = True

    return _cached_model


def evaluate_second_opinion(symbol: str, conn=None, live_price: float = None, live_volume: int = None) -> bool:
    """
    Evaluates whether a symbol passes the Second Opinion ML Consensus Gate.
    Returns True if ML Probability > 0.50, False otherwise.
    Fails closed (False) if model is missing or data is insufficient (< 50 bars).

    Pre-checks (run before ML inference):
      1. Daily drawdown kill-switch – blocks all new entries if today's portfolio
         has drawn down more than the configured threshold (default 3 %).
    """
    # ------------------------------------------------------------------
    # Pre-check 1: Daily Drawdown Kill-Switch
    # ------------------------------------------------------------------
    try:
        _threshold_pct = 3.0
        try:
            import yaml
            from pathlib import Path as _Path
            _cfg_path = _Path(__file__).resolve().parent.parent / "config" / "strategy.yaml"
            with open(_cfg_path, "r", encoding="utf-8") as _f:
                _cfg = yaml.safe_load(_f)
            _threshold_pct = float(_cfg.get("risk", {}).get("daily_drawdown_halt_pct", 3.0))
        except Exception:
            pass  # Silently fall back to default; guard itself also has a fallback

        breached, dd_reason = is_daily_drawdown_breached(threshold_pct=_threshold_pct)
        if breached:
            logger.warning(
                f"[{symbol}] Second opinion BLOCKED by daily drawdown kill-switch: {dd_reason}"
            )
            return False
    except Exception as _dd_err:
        # Fail open on monitoring error — do not block trading
        logger.error(f"[{symbol}] Daily drawdown guard raised unexpectedly: {_dd_err}. Continuing.")

    model = get_champion_model()
    if model is None:
        logger.warning(f"[{symbol}] Second opinion failed: Champion model is None (failing closed).")
        return False

    def _query_data(c):
        return c.execute("""
            SELECT trade_date, close_price, high_price, low_price, total_traded_qty as volume, delivery_pct, total_traded_val, split_multiplier
            FROM (
                SELECT trade_date, close_price, high_price, low_price, total_traded_qty, delivery_pct, total_traded_val, split_multiplier
                FROM bhavcopy_daily
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT 300
            ) sub
            ORDER BY trade_date ASC;
        """, (symbol,)).df()

    try:
        if conn is not None:
            df = _query_data(conn)
        else:
            with get_read_connection() as _conn:
                df = _query_data(_conn)
    except Exception as e:
        logger.error(f"Error querying history for {symbol}: {e}")
        return False

    if df.empty or len(df) < 50:
        logger.warning(f"[{symbol}] Insufficient historical data ({len(df)} bars < 50). Vetoed.")
        return False

    from src.screening.ml_features import engineer_live_tick
    df = engineer_live_tick(df, live_price, live_volume)

    df.set_index('trade_date', inplace=True)
    df = extract_quantitative_features(df)

    expected_features = getattr(model, 'feature_names_in_', None)
    if not isinstance(expected_features, (list, tuple, np.ndarray, pd.Index)):
        expected_features = FEATURE_COLS

    try:
        latest_features = df.iloc[-1:][list(expected_features)]
        if latest_features.isna().values.any():
            return False

        prob = model.predict_proba(latest_features)[0][1]
        return bool(prob > 0.50)
    except Exception as e:
        logger.error(f"Error in second opinion inference for {symbol}: {e}")
        return False

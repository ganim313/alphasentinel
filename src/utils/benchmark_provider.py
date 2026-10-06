"""
Canonical Market Benchmark Provider.
Provides authoritative benchmark data for regime filters, relative RSI, and ML features.
Eliminates train-serve benchmark skew and silent fail-open screening bugs.
"""

import logging
import datetime
from typing import Optional
import pandas as pd
import numpy as np
import yfinance as yf
from src.config.strategy import QUANT_ALPHA_CONFIG

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL: str = QUANT_ALPHA_CONFIG.get("benchmark_symbol", "^NSEI")
REGIME_DMA_PERIOD: int = int(QUANT_ALPHA_CONFIG.get("regime_dma_period", 50))

_cache: dict = {"ohlc": None, "fetched_at": None}
_CACHE_TTL_SECONDS = 3600  # 60 minutes


def clear_benchmark_cache() -> None:
    """Clears the in-memory benchmark cache (useful for testing and manual flushes)."""
    global _cache
    _cache = {"ohlc": None, "fetched_at": None}


def get_benchmark_ohlc(lookback_days: int = 400) -> pd.DataFrame:
    """
    Fetches daily OHLC series for the canonical benchmark symbol.
    Caches results in memory for 60 minutes.
    Raises RuntimeError loudly if yfinance returns insufficient data.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    fetched_at = _cache["fetched_at"]
    if fetched_at is not None:
        fetched_at = fetched_at.astimezone(ist)
    if (
        _cache["ohlc"] is not None
        and fetched_at is not None
        and (now - fetched_at).total_seconds() < _CACHE_TTL_SECONDS
        and len(_cache["ohlc"]) >= min(lookback_days, REGIME_DMA_PERIOD)
    ):
        return _cache["ohlc"]

    logger.info(f"Fetching benchmark OHLC for {BENCHMARK_SYMBOL} (lookback={lookback_days}d)...")
    ticker = yf.Ticker(BENCHMARK_SYMBOL)
    df = ticker.history(period=f"{lookback_days}d")

    if df is None or df.empty or len(df) < REGIME_DMA_PERIOD:
        row_count = len(df) if df is not None else 0
        raise RuntimeError(
            f"Benchmark {BENCHMARK_SYMBOL} returned {row_count} rows "
            f"(required >= {REGIME_DMA_PERIOD}). Cannot evaluate market regime."
        )

    _cache["ohlc"] = df
    _cache["fetched_at"] = now
    return df


from pathlib import Path
_HMM_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "hmm_regime.pkl"


def get_hmm_market_regime(
    as_of_date: Optional[object] = None,
    model_path: Optional[str] = None
) -> int:
    """
    Returns market regime via 3-state Gaussian HMM:
        0 = Crisis (lowest mean returns / high volatility)
        1 = Choppy (near-zero returns / sideways market)
        2 = Calm / Bull (positive steady returns)

    Fails closed on errors: returns 0 (Crisis).
    Falls back to SMA50 if model file is not found (returns 1 for Risk-On, 0 for Risk-Off).
    """
    path = Path(model_path) if model_path else _HMM_MODEL_PATH
    df = get_benchmark_ohlc()
    close = df["Close"].dropna()
    if as_of_date is not None:
        as_of_ts = pd.to_datetime(as_of_date)
        if close.index.tz is not None and as_of_ts.tzinfo is None:
            as_of_ts = as_of_ts.tz_localize(close.index.tz)
        elif close.index.tz is None and as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)
        close = close[close.index <= as_of_ts]

    if len(close) < 50:
        logger.warning(f"HMM Regime: Insufficient close history ({len(close)} < 50). Falling back to SMA50.")
        sma = close.rolling(min(len(close), REGIME_DMA_PERIOD)).mean()
        return 1 if float(close.iloc[-1]) >= float(sma.iloc[-1]) else 0

    if not path.exists():
        logger.debug(f"HMM model not found at {path}. Falling back to SMA50.")
        sma = close.rolling(REGIME_DMA_PERIOD).mean()
        return 1 if float(close.iloc[-1]) >= float(sma.iloc[-1]) else 0

    try:
        import joblib
        model = joblib.load(str(path))
        returns = np.log(close / close.shift(1)).dropna().values.reshape(-1, 1)
        if len(returns) < 10:
            return 0
        hidden_states = model.predict(returns)
        regime = int(hidden_states[-1])
        logger.debug(f"HMM Regime decoded: state={regime} (0=Crisis, 1=Choppy, 2=Calm)")
        return regime
    except Exception as e:
        logger.error(f"HMM predict failed: {e}. Failing closed to 0 (Crisis).")
        return 0


def get_market_regime(as_of_date: Optional[object] = None, use_hmm: bool = True) -> int:
    """
    Calculates binary market regime (1 = Risk-On, 0 = Risk-Off / Crisis).
    When use_hmm is True (default), combines the 3-state Gaussian HMM regime
    (non-Crisis state > 0) with the SMA50 structural filter (Close >= SMA50).
    When use_hmm is False, evaluates strictly 1 (Close >= SMA50) or 0 (Close < SMA50).
    Supports pd.Timestamp, datetime.datetime, datetime.date, or string date formats.
    """
    df = get_benchmark_ohlc()
    close = df["Close"].dropna()
    if as_of_date is not None:
        as_of_ts = pd.to_datetime(as_of_date)
        if close.index.tz is not None and as_of_ts.tzinfo is None:
            as_of_ts = as_of_ts.tz_localize(close.index.tz)
        elif close.index.tz is None and as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)
        close = close[close.index <= as_of_ts]

    if len(close) < REGIME_DMA_PERIOD:
        raise RuntimeError(f"Insufficient benchmark close history ({len(close)} < {REGIME_DMA_PERIOD})")

    sma = close.rolling(REGIME_DMA_PERIOD).mean()
    sma_regime = 1 if float(close.iloc[-1]) >= float(sma.iloc[-1]) else 0

    if use_hmm:
        hmm_state = get_hmm_market_regime(as_of_date=as_of_date)
        return 1 if (sma_regime == 1 and hmm_state > 0) else 0

    return sma_regime


def get_benchmark_returns(lookback_days: int = 400) -> pd.Series:
    """Returns daily percentage return series of the benchmark."""
    df = get_benchmark_ohlc(lookback_days)
    return df["Close"].pct_change().dropna()


def get_benchmark_rsi(period: int = 14) -> float:
    """Calculates Wilder's RSI on benchmark close prices."""
    from src.utils.technical_indicators import wilders_rsi
    df = get_benchmark_ohlc()
    rsi_series = wilders_rsi(df["Close"], period=period)
    return float(rsi_series.iloc[-1])


"""
Canonical technical indicator implementations for AlphaSentinel.
ALL screeners, ML feature engines, and training scripts MUST import from here.
"""
from typing import Union
import numpy as np
import pandas as pd


def wilders_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's Relative Strength Index (1978 original specification).
    
    Uses exponential smoothing with alpha = 1 / period (adjust=False) and seeds
    the initial average gain/loss with the simple moving average of the first 'period' bars.
    
    Formula:
        delta = close.diff()
        gain = max(delta, 0), loss = max(-delta, 0)
        AvgGain_t = (AvgGain_{t-1} * (period - 1) + Gain_t) / period
        AvgLoss_t = (AvgLoss_{t-1} * (period - 1) + Loss_t) / period
        RS = AvgGain / AvgLoss
        RSI = 100 - (100 / (1 + RS))
    """
    if close is None or len(close) == 0:
        return pd.Series(dtype=float)

    close_series = close.astype(float)
    if len(close_series) < period + 1:
        return pd.Series([50.0] * len(close_series), index=close_series.index, dtype=float)

    delta = close_series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Pre-allocate Series for average gain and loss
    avg_gain = pd.Series(np.nan, index=close_series.index, dtype=float)
    avg_loss = pd.Series(np.nan, index=close_series.index, dtype=float)

    # Wilder's exact seed: first valid smoothed value is the 14-period SMA
    first_valid = period
    avg_gain.iloc[first_valid] = gain.iloc[1:first_valid + 1].mean()
    avg_loss.iloc[first_valid] = loss.iloc[1:first_valid + 1].mean()

    # Recursive Wilder smoothing from first_valid + 1 onwards
    for i in range(first_valid + 1, len(close_series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Boundary conditions:
    # When avg_loss == 0 and avg_gain > 0 (pure gain series), RSI is 100.0
    rsi = rsi.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), 100.0)
    # When avg_gain == 0 and avg_loss > 0 (pure loss series), RSI is 0.0
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss > 0.0)), 0.0)
    # When both are 0.0 (completely flat), RSI is 50.0
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)

    # Fill warmup bars with 50.0 neutral default
    rsi.iloc[:first_valid] = 50.0
    return rsi.fillna(50.0)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's Average True Range (ATR).
    
    True Range = max(high - low, abs(high - close_{prev}), abs(low - close_{prev}))
    ATR = Wilder's smoothing of True Range over 'period'.
    """
    if close is None or len(close) == 0:
        return pd.Series(dtype=float)
    if len(close) < 2:
        return pd.Series([0.0] * len(close), index=close.index, dtype=float)

    high_s = high.astype(float)
    low_s = low.astype(float)
    close_s = close.astype(float)
    prev_close = close_s.shift(1)

    tr1 = high_s - low_s
    tr2 = (high_s - prev_close).abs()
    tr3 = (low_s - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr.iloc[0] = tr1.iloc[0]

    atr_series = pd.Series(np.nan, index=close.index, dtype=float)
    if len(tr) <= period:
        return tr.rolling(period, min_periods=1).mean().bfill().fillna(0.0)

    first_valid = period
    atr_series.iloc[first_valid] = tr.iloc[1:first_valid + 1].mean()
    for i in range(first_valid + 1, len(tr)):
        atr_series.iloc[i] = (atr_series.iloc[i - 1] * (period - 1) + tr.iloc[i]) / period

    return atr_series.bfill().fillna(0.0)

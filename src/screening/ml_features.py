import pandas as pd
import numpy as np
from src.utils.technical_indicators import wilders_rsi

_benchmark_cache = None

def _get_benchmark_data():
    global _benchmark_cache
    if _benchmark_cache is not None:
        return _benchmark_cache
    try:
        import yfinance as yf
        bench = yf.Ticker("^NSEI").history(period="1y")
        if not bench.empty:
            bench['rsi'] = calculate_rsi(bench['Close'])
            bench['regime'] = np.where(bench['Close'] >= bench['Close'].rolling(50).mean(), 1, 0)
            _benchmark_cache = bench
            return bench
    except Exception:
        pass
    return None

def engineer_live_tick(df, live_price, live_volume, true_high=None, true_low=None):
    if live_price is None:
        return df

    today_ts = pd.Timestamp('today').normalize()
    hp = true_high if true_high is not None else live_price
    lp = true_low if true_low is not None else live_price
    
    current_volume = live_volume or 0
    vol_col = 'total_traded_qty' if 'total_traded_qty' in df.columns else 'volume'
    
    if not df.empty and pd.to_datetime(df['trade_date'].iloc[-1]).normalize() == today_ts:
        # Update last row instead of ignoring new ticks
        df.iloc[-1, df.columns.get_loc('close_price')] = live_price
        df.iloc[-1, df.columns.get_loc('high_price')] = max(df.iloc[-1]['high_price'], hp)
        df.iloc[-1, df.columns.get_loc('low_price')] = min(df.iloc[-1]['low_price'], lp)
        if vol_col in df.columns:
            df.iloc[-1, df.columns.get_loc(vol_col)] = current_volume
        return df
        
    new_row_dict = {
        'trade_date': [today_ts], 
        'close_price': [live_price],
        'high_price': [hp],
        'low_price': [lp]
    }
    if vol_col in df.columns or vol_col == 'total_traded_qty':
        new_row_dict[vol_col] = [current_volume]
        
    new_row = pd.DataFrame(new_row_dict)
    return pd.concat([df, new_row], ignore_index=True)

def calculate_rsi(series, window=14):
    return wilders_rsi(series, period=window)

def extract_quantitative_features(df):
    df = df.copy()
    
    # Prices in bhavcopy_daily are split-adjusted at database ingestion
    adj_close = df['close_price']
    adj_high = df['high_price']

    
    # 1. dist_high: distance to 252-day high (min_periods=20 to support short histories)
    df['dist_high'] = adj_close / adj_high.rolling(252, min_periods=20).max() - 1
    
    # 2. ema_dist: distance to 20-day EMA
    df['ema_20'] = adj_close.ewm(span=20, adjust=False, min_periods=10).mean()
    df['ema_dist'] = adj_close / df['ema_20'] - 1
    
    # 3. vol_cluster: 20-day standard deviation of returns
    df['returns'] = adj_close.pct_change()
    df['vol_cluster'] = df['returns'].rolling(20, min_periods=10).std()
    
    # Fetch real benchmark regime and RSI
    bench = _get_benchmark_data()
    
    if bench is not None and not bench.empty:
        # Align bench dates to df safely without mutating tz-naive index
        df_dt = pd.DatetimeIndex(pd.to_datetime(df['trade_date'] if 'trade_date' in df.columns else df.index))
        if df_dt.tz is not None:
            df_dates = df_dt.tz_localize(None).normalize()
        else:
            df_dates = df_dt.normalize()

        bench_copy = bench.copy()
        if hasattr(bench_copy.index, 'tz') and bench_copy.index.tz is not None:
            bench_dates = bench_copy.index.tz_localize(None).normalize()
        else:
            bench_dates = bench_copy.index.normalize()
        
        bench_copy = bench_copy[~bench_copy.index.duplicated(keep='last')]
        bench_copy.index = bench_dates
        
        # Merge regime and rsi
        bench_aligned = bench_copy.reindex(df_dates).ffill()
        df['market_regime'] = bench_aligned['regime'].fillna(1).values
        bench_rsi = bench_aligned['rsi'].fillna(50).values
    else:
        df['market_regime'] = 1
        bench_rsi = 50.0
        
    df['rsi'] = calculate_rsi(adj_close)
    df['rel_rsi'] = df['rsi'] - bench_rsi
    
    # 6. sharpe_rank: standard return/volatility proxy
    mean_ret = df['returns'].rolling(60, min_periods=40).mean()
    std_ret = df['returns'].rolling(60, min_periods=40).std()
    df['sharpe_raw'] = mean_ret / (std_ret + 1e-6)
    
    # Use standard normal CDF approximation or clipping to keep it informative (not compressed to 0.5)
    # Annualized Sharpe ratio usually ranges from -2 to 3. 
    # Let's scale raw sharpe (daily) to annualized: raw * sqrt(252)
    ann_sharpe = df['sharpe_raw'] * np.sqrt(252)
    df['sharpe_rank'] = 1 / (1 + np.exp(-ann_sharpe))
    
    # Ensure expected features exactly match
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df

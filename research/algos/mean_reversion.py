import pandas as pd
import numpy as np

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def run_mean_reversion(close_df, high_df, low_df, volume_df):
    """
    Mean Reversion Logic (Buy the Dip).
    Buy rule: RSI(14) < 30 (Oversold)
    Sell rule: RSI(14) > 70 (Overbought) or Price > 20 SMA
    """
    signals = pd.DataFrame(index=close_df.index, columns=close_df.columns)
    signals.fillna(0, inplace=True)
    
    for col in close_df.columns:
        if col == '^INDIAVIX':
            continue
            
        close = close_df[col]
        rsi = calculate_rsi(close, 14)
        sma20 = close.rolling(20).mean()
        
        buy_cond = rsi < 30
        sell_cond = (rsi > 70) | (close > sma20)
        
        in_position = False
        sig = []
        
        # Need to iterate because state depends on previous state
        for i in range(len(close)):
            if not in_position:
                # Need to check if not NaN
                if pd.notna(buy_cond.iloc[i]) and buy_cond.iloc[i]:
                    in_position = True
            else:
                if pd.notna(sell_cond.iloc[i]) and sell_cond.iloc[i]:
                    in_position = False
                    
            sig.append(1 if in_position else 0)
            
        signals[col] = sig
        
    return signals

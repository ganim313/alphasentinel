import pandas as pd
import numpy as np

def run_momentum(close_df, high_df, low_df, volume_df):
    """
    Momentum/Trend Following logic (Proxy for VCP).
    Buy rule:
    - 20 SMA > 50 SMA > 200 SMA
    - Close > 20-day High (Breakout)
    Sell rule:
    - Close < 50 SMA (Trailing stop)
    """
    signals = pd.DataFrame(index=close_df.index, columns=close_df.columns)
    signals.fillna(0, inplace=True)
    
    for col in close_df.columns:
        if col == '^INDIAVIX':
            continue
            
        close = close_df[col]
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        
        high20 = close.rolling(20).max().shift(1)
        
        # Conditions
        trend_up = (sma20 > sma50) & (sma50 > sma200)
        breakout = close > high20
        
        sell_cond = close < sma50
        
        in_position = False
        sig = []
        for i in range(len(close)):
            if not in_position:
                if trend_up.iloc[i] and breakout.iloc[i]:
                    in_position = True
            else:
                if sell_cond.iloc[i]:
                    in_position = False
                    
            sig.append(1 if in_position else 0)
            
        signals[col] = sig
        
    return signals

import pandas as pd
import numpy as np
from src.db.session import get_read_connection
from src.utils.technical_indicators import wilders_rsi

def evaluate_mean_reversion(symbol: str, conn=None, live_price: float = None) -> bool:
    """
    Evaluates a stock for mean reversion (Buy the Dip in Uptrend).
    Returns True if RSI < 30 (Oversold), False otherwise.
    """
    if conn is None:
        with get_read_connection() as c:
            return evaluate_mean_reversion(symbol, conn=c, live_price=live_price)

    df = conn.execute("""
        SELECT trade_date, close_price
        FROM bhavcopy_daily
        WHERE symbol = ?
        ORDER BY trade_date ASC;
    """, (symbol,)).df()
        
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
    
    # ---------------------------------------------------------
    # CRITICAL FIX: The 3:15 PM Time-Travel Bug (Batched + IST)
    # ---------------------------------------------------------
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    ist = ZoneInfo('Asia/Kolkata')
    today = datetime.now(ist).date()
    
    if not df.empty and df['trade_date'].iloc[-1] != today and live_price is not None:
        # Append today's live tick
        new_row = pd.DataFrame({
            'trade_date': [today], 
            'close_price': [live_price]
        })
        df = pd.concat([df, new_row], ignore_index=True)

    if len(df) < 20:
        return False
        
    rsi_series = wilders_rsi(df['close_price'], period=14)
    latest_rsi = rsi_series.iloc[-1]
    
    # Return True if oversold
    return pd.notna(latest_rsi) and latest_rsi < 30

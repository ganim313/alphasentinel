import yfinance as yf
import pandas as pd
from pathlib import Path

# Nifty 50 representative basket + India VIX (note: State Bank of India is SBIN.NS)
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "^INDIAVIX"
]

DATA_DIR = Path(__file__).parent / "data"

def fetch_data(start_date="2019-01-01", end_date="2024-01-01"):
    DATA_DIR.mkdir(exist_ok=True)
    
    print("Fetching historical EOD data from Yahoo Finance...")
    data = yf.download(TICKERS, start=start_date, end=end_date)
    
    for metric in ['Close', 'High', 'Low', 'Volume']:
        if metric in data:
            file_path = DATA_DIR / f"{metric.lower()}.csv"
            data[metric].to_csv(file_path)
            print(f"Saved {metric} data to {file_path}")
            
    print("Data loading complete.")

def load_data():
    """Helper to load data into a dictionary of DataFrames."""
    if not (DATA_DIR / "close.csv").exists():
        fetch_data()
        
    dfs = {}
    for metric in ['close', 'high', 'low', 'volume']:
        file_path = DATA_DIR / f"{metric}.csv"
        if file_path.exists():
            dfs[metric] = pd.read_csv(file_path, index_col=0, parse_dates=True)
            
    return dfs

if __name__ == "__main__":
    fetch_data()

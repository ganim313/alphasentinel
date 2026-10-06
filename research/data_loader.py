import sys
from pathlib import Path
import yfinance as yf
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Shariah-compliant Nifty 50 representative basket + India VIX
# (Strictly excludes conventional banks HDFCBANK, ICICIBANK, SBIN and tobacco ITC)
SHARIAH_COMPLIANT_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HINDUNILVR.NS", "BHARTIARTL.NS",
    "LT.NS", "SUNPHARMA.NS", "TITAN.NS", "MARUTI.NS", "ASIANPAINT.NS", "^INDIAVIX"
]
TICKERS = SHARIAH_COMPLIANT_TICKERS

DATA_DIR = Path(__file__).parent / "data"


def load_duckdb_shariah_data(max_symbols: int = 50) -> dict:
    """
    Loads point-in-time split-adjusted OHLCV DataFrames from DuckDB bhavcopy_daily
    strictly restricted to Shariah-compliant equities (excluding PROHIBITED_SYMBOLS
    such as HDFCBANK, ICICIBANK, SBIN, ITC).
    """
    from src.db.session import get_read_connection
    from src.screening.shariah_filter import PROHIBITED_SYMBOLS

    with get_read_connection() as conn:
        df = conn.execute("""
            SELECT b.symbol, b.trade_date, b.close_price, b.high_price, b.low_price, b.total_traded_qty
            FROM bhavcopy_daily b
            INNER JOIN fundamentals_cache f ON b.symbol = f.symbol
            WHERE b.series = 'EQ' AND COALESCE(b.is_asm, FALSE) = FALSE AND COALESCE(b.is_gsm, FALSE) = FALSE
            ORDER BY b.trade_date ASC
        """).df()

    if df is None or df.empty:
        return {}

    df["symbol_clean"] = df["symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False)
    df = df[~df["symbol_clean"].isin(PROHIBITED_SYMBOLS)]
    if df.empty:
        return {}

    top_syms = (
        df.groupby("symbol_clean")["total_traded_qty"]
        .mean()
        .sort_values(ascending=False)
        .head(max_symbols)
        .index.tolist()
    )
    df = df[df["symbol_clean"].isin(top_syms)].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    return {
        "close": df.pivot(index="trade_date", columns="symbol_clean", values="close_price").ffill(limit=5),
        "high": df.pivot(index="trade_date", columns="symbol_clean", values="high_price").ffill(limit=5),
        "low": df.pivot(index="trade_date", columns="symbol_clean", values="low_price").ffill(limit=5),
        "volume": df.pivot(index="trade_date", columns="symbol_clean", values="total_traded_qty").fillna(0),
    }


def fetch_data(start_date="2019-01-01", end_date="2024-01-01"):
    DATA_DIR.mkdir(exist_ok=True)
    
    print("Fetching historical EOD data from Yahoo Finance (Shariah-compliant basket)...")
    data = yf.download(SHARIAH_COMPLIANT_TICKERS, start=start_date, end=end_date)
    
    for metric in ['Close', 'High', 'Low', 'Volume']:
        if metric in data:
            file_path = DATA_DIR / f"{metric.lower()}.csv"
            data[metric].to_csv(file_path)
            print(f"Saved {metric} data to {file_path}")
            
    print("Data loading complete.")


def load_data(use_duckdb: bool = True, shariah_only: bool = True):
    """
    Loads OHLCV data into a dictionary of DataFrames ('close', 'high', 'low', 'volume').
    By default attempts DuckDB Shariah-compliant universe first, falling back to CSVs
    with prohibited Haram symbols stripped.
    """
    from src.screening.shariah_filter import PROHIBITED_SYMBOLS

    if use_duckdb:
        try:
            duck_dfs = load_duckdb_shariah_data()
            if duck_dfs and "close" in duck_dfs and not duck_dfs["close"].empty:
                return duck_dfs
        except Exception:
            pass

    if not (DATA_DIR / "close.csv").exists():
        fetch_data()
        
    dfs = {}
    for metric in ['close', 'high', 'low', 'volume']:
        file_path = DATA_DIR / f"{metric}.csv"
        if file_path.exists():
            df_m = pd.read_csv(file_path, index_col=0, parse_dates=True)
            if shariah_only:
                keep_cols = [
                    c for c in df_m.columns
                    if c == "^INDIAVIX" or c.upper().replace(".NS", "") not in PROHIBITED_SYMBOLS
                ]
                df_m = df_m[keep_cols]
            dfs[metric] = df_m
            
    return dfs


if __name__ == "__main__":
    fetch_data()


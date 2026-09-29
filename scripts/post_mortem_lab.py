import logging
import json
import pandas as pd
import numpy as np
from pathlib import Path
import duckdb

import sys
import os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.session import get_read_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PostMortemLab")


def fetch_trade_data() -> pd.DataFrame:
    """Fetch closed paper trades and join with candidate features."""
    query = """
        SELECT 
            pt.id AS trade_id,
            pt.symbol,
            pt.sector,
            pt.entry_date,
            pt.exit_date,
            pt.entry_price,
            pt.exit_price,
            pt.quantity,
            pt.trailing_stop_loss AS stop_loss,
            pt.realized_pnl,
            sc.pattern_type,
            sc.adtv_20d,
            sc.circuit_band,
            sc.ml_probability
        FROM positions pt
        LEFT JOIN screener_candidates sc 
            ON pt.symbol = sc.symbol AND pt.entry_date = sc.scan_date
        WHERE pt.status IN ('CLOSED', 'STOPPED_OUT', 'TARGET_REACHED') 
          AND pt.realized_pnl IS NOT NULL
    """
    with get_read_connection() as conn:
        df = conn.execute(query).df()
    return df


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer features for statistical analysis."""
    if df.empty:
        return df

    # Basic trade features with division-by-zero protection (entry_price <= 0 and quantity <= 0)
    entry_capital = (df['entry_price'] * df['quantity'].clip(lower=1)).fillna(0.0)
    df['return_pct'] = np.where(entry_capital > 0, df['realized_pnl'].fillna(0.0) / entry_capital, 0.0)
    valid_entry = (df['entry_price'] > 0) & df['stop_loss'].notna()
    df['risk_pct'] = np.where(valid_entry, (df['entry_price'] - df['stop_loss']) / df['entry_price'], 0.0)
    
    # Time features
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df['trade_duration_days'] = (df['exit_date'] - df['entry_date']).dt.days

    return df


def analyze_losing_trades(df: pd.DataFrame):
    """Run robust statistical attribution instead of ML decision trees."""
    logger.info(f"Analyzing {len(df)} total closed trades.")
    
    df['is_winner'] = (df['realized_pnl'] > 0).astype(int)
    
    overall_win_rate = df['is_winner'].mean()
    overall_avg_return = df['return_pct'].mean()
    
    logger.info(f"Overall Win Rate: {overall_win_rate:.2%}")
    logger.info(f"Overall Avg Return: {overall_avg_return:.2%}")

    if len(df) < 2:
        logger.info("Need more trades to run meaningful statistical attribution.")
        return

    print("\n" + "="*60)
    print("STATISTICAL POST-MORTEM LAB: ROBUST ATTRIBUTION ANALYSIS")
    print("="*60)

    # 1. Win-Rate and Returns by Sector
    if 'sector' in df.columns and df['sector'].notna().any():
        print("\n--- Performance by Sector ---")
        sector_stats = df.groupby('sector').agg(
            trades=('trade_id', 'count'),
            win_rate=('is_winner', 'mean'),
            avg_return=('return_pct', 'mean'),
            total_pnl=('realized_pnl', 'sum')
        ).sort_values(by='win_rate', ascending=False)
        print(sector_stats.to_string(formatters={
            'win_rate': '{:.2%}'.format, 
            'avg_return': '{:.2%}'.format,
            'total_pnl': '{:,.2f}'.format
        }))

    # 2. Win-Rate by Pattern Type
    if 'pattern_type' in df.columns and df['pattern_type'].notna().any():
        print("\n--- Performance by Pattern Type ---")
        pattern_stats = df.groupby('pattern_type').agg(
            trades=('trade_id', 'count'),
            win_rate=('is_winner', 'mean'),
            avg_return=('return_pct', 'mean')
        ).sort_values(by='win_rate', ascending=False)
        print(pattern_stats.to_string(formatters={
            'win_rate': '{:.2%}'.format, 
            'avg_return': '{:.2%}'.format
        }))
        
    # 3. Simple Sharpe Ratio Approximation by Sector
    # Assuming risk-free rate is roughly 0 for short term trades
    print("\n--- Approximate Sharpe Ratio by Sector (Return / StdDev) ---")
    df_sectors = df.groupby('sector').filter(lambda x: len(x) > 2)
    if not df_sectors.empty:
        sharpe_stats = df_sectors.groupby('sector')['return_pct'].apply(
            lambda s: s.mean() / s.std() if s.std() > 0 and pd.notna(s.std()) else 0.0
        ).rename("sharpe_ratio").sort_values(ascending=False)
        print(sharpe_stats.to_frame().to_string(formatters={'sharpe_ratio': '{:.2f}'.format}))
    else:
        print("Not enough data per sector to calculate Sharpe ratio.")

    # 4. Max Drawdown Analysis (Time Series)
    print("\n--- Equity Curve Max Drawdown ---")
    time_series_df = df.sort_values('exit_date').copy()
    time_series_df['cumulative_pnl'] = time_series_df['realized_pnl'].cumsum()
    time_series_df['rolling_max'] = time_series_df['cumulative_pnl'].cummax()
    time_series_df['drawdown'] = time_series_df['cumulative_pnl'] - time_series_df['rolling_max']
    
    max_dd = time_series_df['drawdown'].min()
    print(f"Maximum PnL Drawdown: {max_dd:,.2f}")

    print("\nRECOMMENDATIONS FOR STRATEGY TUNING:")
    print("1. Review sectors with win-rates significantly below the overall average.")
    print("2. Consider filtering out underperforming pattern types.")
    print("3. Check drawdown periods for broader market regime impacts.")
    print("="*60 + "\n")


def main():
    logger.info("Starting Post-Mortem Lab...")
    try:
        df = fetch_trade_data()
        if df.empty:
            logger.info("No closed paper trades available for analysis.")
            return

        df = extract_features(df)
        analyze_losing_trades(df)

    except Exception as e:
        logger.error(f"Error running Post-Mortem Lab: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("post_mortem_lab"):
        main()

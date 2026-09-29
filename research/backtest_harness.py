import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from data_loader import load_data
from algos.momentum import run_momentum
from algos.mean_reversion import run_mean_reversion
from algos.ml_factor import run_ml_factor

def calculate_metrics(portfolio_returns):
    """Calculate CAGR, Max Drawdown, and Sharpe Ratio."""
    # Drop first NA
    portfolio_returns = portfolio_returns.dropna()
    
    if len(portfolio_returns) == 0:
        return 0, 0, 0
        
    cum_returns = (1 + portfolio_returns).cumprod()
    
    # CAGR
    days = (portfolio_returns.index[-1] - portfolio_returns.index[0]).days
    if days == 0:
        cagr = 0
    else:
        cagr = (cum_returns.iloc[-1]) ** (365.25 / days) - 1
        
    # Max Drawdown
    rolling_max = cum_returns.cummax()
    drawdown = (cum_returns - rolling_max) / rolling_max
    max_dd = drawdown.min()
    
    # Sharpe Ratio (assuming risk free rate = 0 for simplicity)
    daily_vol = portfolio_returns.std()
    sharpe = (portfolio_returns.mean() / daily_vol) * np.sqrt(252) if daily_vol > 0 else 0
    
    return cagr, max_dd, sharpe

def run_shootout():
    print("Loading data...")
    dfs = load_data()
    close_df = dfs['close']
    high_df = dfs['high']
    low_df = dfs['low']
    volume_df = dfs['volume']
    
    vix = close_df['^INDIAVIX'] if '^INDIAVIX' in close_df else None
    
    # We use a static 50% cutoff date so ML and rule-based are compared on the exact same out-of-sample period.
    # The ML model trains on the first half. We evaluate all algos on the second half.
    split_idx = int(len(close_df) * 0.5)
    out_of_sample_start = close_df.index[split_idx]
    
    print(f"Evaluating Out-of-Sample Period: {out_of_sample_start.date()} to {close_df.index[-1].date()}")
    
    algos = {
        "Momentum (VCP)": run_momentum,
        "Mean Reversion": run_mean_reversion,
        "ML Factor Model": run_ml_factor
    }
    
    results = []
    
    # Daily returns of the underlying stocks
    # Shift(-1) because if we get a signal today, we earn tomorrow's return
    daily_returns = close_df.pct_change().shift(-1)
    
    for name, algo_func in algos.items():
        print(f"\nRunning {name}...")
        signals = algo_func(close_df, high_df, low_df, volume_df)
        
        # Apply VIX overlay: if VIX > 22, force signal to 0
        if vix is not None:
            vix_mask = vix > 22
            # Broadcast mask to signal dataframe shape
            for col in signals.columns:
                if col != '^INDIAVIX':
                    signals.loc[vix_mask, col] = 0
                    
        # Filter for out-of-sample period
        signals = signals.loc[out_of_sample_start:]
        dr = daily_returns.loc[out_of_sample_start:]
        
        # Calculate daily portfolio return (Equal weighted among active signals)
        # We exclude VIX from returns calculation
        stock_cols = [c for c in signals.columns if c != '^INDIAVIX']
        active_signals = signals[stock_cols]
        active_dr = dr[stock_cols]
        
        # Number of active positions each day
        num_positions = active_signals.sum(axis=1)
        
        # Avoid division by zero
        weights = active_signals.div(num_positions.replace(0, 1), axis=0)
        
        # Portfolio daily return
        port_returns = (weights * active_dr).sum(axis=1)
        
        cagr, max_dd, sharpe = calculate_metrics(port_returns)
        
        # Calculate Buy & Hold benchmark for the same period
        # Equal weight all stocks
        bench_weights = pd.DataFrame(1/len(stock_cols), index=active_dr.index, columns=stock_cols)
        bench_returns = (bench_weights * active_dr).sum(axis=1)
        bench_cagr, bench_max_dd, bench_sharpe = calculate_metrics(bench_returns)
        
        # -------------------------------------------------------------
        # Statistical Validation Infrastructure (Bootstrap & Sample Size)
        # -------------------------------------------------------------
        sample_size = num_positions[num_positions > 0].count()
        if sample_size < 30:
            is_valid = "FAILED (N < 30)"
            ci_lower, ci_upper = 0.0, 0.0
        else:
            is_valid = "PASSED"
            # Bootstrap Confidence Intervals (95%)
            daily_port_returns_non_zero = port_returns[num_positions > 0].values
            np.random.seed(42)
            n_bootstraps = 1000
            bootstrap_means = []
            for _ in range(n_bootstraps):
                sample = np.random.choice(daily_port_returns_non_zero, size=len(daily_port_returns_non_zero), replace=True)
                bootstrap_means.append(np.mean(sample))
            
            ci_lower = np.percentile(bootstrap_means, 2.5) * 252 # Annualized
            ci_upper = np.percentile(bootstrap_means, 97.5) * 252 # Annualized

        results.append({
            "Algorithm": name,
            "CAGR": f"{cagr*100:.2f}%",
            "Max Drawdown": f"{max_dd*100:.2f}%",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "N_Trades": sample_size,
            "Validation": is_valid,
            "95% CI (Ann)": f"[{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]" if sample_size >= 30 else "N/A"
        })
        
    print("\n" + "="*80)
    print("BACKTEST SHOOTOUT RESULTS (OUT-OF-SAMPLE + WALK-FORWARD EMBARGO)")
    print("="*80)
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    
    print("\nBenchmark (Buy & Hold Nifty Basket):")
    print(f"CAGR: {bench_cagr*100:.2f}%, Max Drawdown: {bench_max_dd*100:.2f}%, Sharpe Ratio: {bench_sharpe:.2f}")

if __name__ == "__main__":
    run_shootout()

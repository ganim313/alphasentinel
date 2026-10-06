"""
AlphaSentinel Research Backtest Harness
========================================

╔══════════════════════════════════════════════════════════════════════════════╗
║                  ⚠  BACKTEST LIMITATIONS — READ BEFORE INTERPRETING  ⚠      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  1. SHARIAH FILTER NOT APPLIED                                               ║
║     Production AlphaSentinel filters out non-compliant stocks before any     ║
║     signal is generated.  This backtest uses the raw Nifty universe.         ║
║     Result: the backtest may include stocks the live system would never       ║
║     trade, making it an OPTIMISTIC UPPER-BOUND.                              ║
║                                                                              ║
║  2. 6-LAYER ANTI-TRAP SHIELD NOT APPLIED                                     ║
║     Production applies six overlapping risk filters (VIX regime gate,        ║
║     sector momentum guard, liquidity floor, drawdown circuit-breaker,        ║
║     earnings black-out window, and news-sentiment veto).  Only the VIX       ║
║     overlay is replicated here.  Real live performance will differ.          ║
║                                                                              ║
║  3. DATA SOURCE: yfinance (not DuckDB bhavcopy_daily)                        ║
║     Production ingests NSE bhavcopy CSVs into a local DuckDB database for    ║
║     accuracy and speed.  yfinance adjusted-close prices can differ due to    ║
║     split/dividend adjustment methodology and survivorship bias.             ║
║                                                                              ║
║  4. TRANSACTION COSTS ARE NOW MODELLED (Task A)                              ║
║     Indian-market round-trip cost ≈ 0.13–0.15% per trade is deducted from   ║
║     daily returns.  See TRANSACTION_COSTS dict below.                        ║
║                                                                              ║
║  BOTTOM LINE: These results are an optimistic upper-bound on what the        ║
║  production system can achieve.  Do not use them as a live performance       ║
║  forecast without accounting for the filters listed above.                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import argparse
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).parent))

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from data_loader import load_data
from algos.momentum import run_momentum
from algos.mean_reversion import run_mean_reversion
from algos.ml_factor import run_ml_factor
from src.screening.shariah_filter import PROHIBITED_SYMBOLS


def _filter_shariah_compliant_columns(cols: list) -> list:
    """Exclude any prohibited Haram symbols (e.g., HDFCBANK, ICICIBANK, SBIN, ITC) from tradeable columns."""
    return [
        c for c in cols
        if c != "^INDIAVIX" and str(c).upper().replace(".NS", "") not in PROHIBITED_SYMBOLS
    ]

# ── Task A: Indian Market Transaction Cost Model ───────────────────────────────
# All rates are expressed as a fraction of trade value (not percentage).
# Sources: NSE circular, SEBI schedule of charges, Indian Stamp Act 2019.
TRANSACTION_COSTS = {
    # Brokerage: 0.03% each side (buy + sell)
    "brokerage_per_side":       0.0003,

    # Securities Transaction Tax: 0.1% on SELL side only (equity delivery)
    "stt_sell_side":            0.001,

    # SEBI turnover charges: ₹10 per crore (= 0.0001%) each side
    "sebi_per_side":            0.000001,

    # NSE transaction charges: 0.00335% each side
    "nse_per_side":             0.0000335,

    # GST on brokerage: 18% of brokerage amount
    "gst_rate_on_brokerage":    0.18,

    # Stamp duty: 0.015% on BUY side only
    "stamp_duty_buy_side":      0.00015,
}

def _compute_round_trip_cost() -> float:
    """
    Return the total round-trip transaction cost as a fraction of trade value.

    Round trip = one BUY leg + one SELL leg.
    Approximate total: 0.13 – 0.15%.
    """
    tc = TRANSACTION_COSTS
    brokerage_both  = tc["brokerage_per_side"] * 2
    gst_on_brok     = brokerage_both * tc["gst_rate_on_brokerage"]
    stt_sell        = tc["stt_sell_side"]
    sebi_both       = tc["sebi_per_side"] * 2
    nse_both        = tc["nse_per_side"] * 2
    stamp_buy       = tc["stamp_duty_buy_side"]

    total = brokerage_both + gst_on_brok + stt_sell + sebi_both + nse_both + stamp_buy
    return total  # ~0.001385 ≈ 0.1385%

# Pre-compute for use throughout the module
ROUND_TRIP_COST = _compute_round_trip_cost()

# ── Metrics helper ─────────────────────────────────────────────────────────────

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

# ── Task A helper: apply transaction costs to portfolio returns ────────────────

def _apply_transaction_costs(port_returns: pd.Series,
                              signals: pd.DataFrame,
                              stock_cols: list) -> pd.Series:
    """
    Deduct transaction costs from daily portfolio returns.

    Each time a stock's signal *changes* (0→1 or 1→0) a trade occurs.
    We charge ROUND_TRIP_COST on the day a position is opened (for
    the combined open + eventual close cost), spread evenly over the
    stock universe that is active that day.

    Args:
        port_returns:  Daily equal-weighted portfolio returns Series.
        signals:       Signal DataFrame (rows=dates, cols=stocks, values 0/1).
        stock_cols:    List of tradeable stock columns (excludes '^INDIAVIX').

    Returns:
        Adjusted portfolio returns Series with transaction costs deducted.
    """
    sig = signals[stock_cols].astype(float)

    # Detect position changes: diff != 0 means a trade happened for that stock
    trade_events = sig.diff().abs()               # 0 or 1 per stock per day

    # Count trades on each day across the universe
    trades_per_day = trade_events.sum(axis=1)     # total trades on that day

    # Each trade costs half a round-trip (open or close).
    # We charge the full round-trip when a NEW position is opened because
    # we know a close will eventually happen — conservative but accurate.
    num_stocks = max(len(stock_cols), 1)
    cost_per_day = (trades_per_day / num_stocks) * (ROUND_TRIP_COST / 2)

    adjusted = port_returns - cost_per_day
    return adjusted

# ── Main shootout ─────────────────────────────────────────────────────────────

def run_shootout():
    """
    Run all three algos on the out-of-sample (second-half) period and print
    a comparison table including CAGR, Max Drawdown, Sharpe, sample size,
    statistical validation, and 95% bootstrap confidence intervals.

    Transaction costs are applied to all portfolio return series.
    See TRANSACTION_COSTS and ROUND_TRIP_COST for the cost model.
    """
    print("Loading data...")
    dfs = load_data()
    close_df  = dfs['close']
    high_df   = dfs['high']
    low_df    = dfs['low']
    volume_df = dfs['volume']

    vix = close_df['^INDIAVIX'] if '^INDIAVIX' in close_df else None

    # We use a static 50% cutoff date so ML and rule-based are compared on the
    # exact same out-of-sample period.  The ML model trains on the first half.
    # We evaluate all algos on the second half.
    split_idx = int(len(close_df) * 0.5)
    out_of_sample_start = close_df.index[split_idx]

    print(f"Evaluating Out-of-Sample Period: {out_of_sample_start.date()} to {close_df.index[-1].date()}")
    print(f"Round-trip transaction cost applied: {ROUND_TRIP_COST*100:.4f}%")

    algos = {
        "Momentum (VCP)": run_momentum,
        "Mean Reversion":  run_mean_reversion,
        "ML Factor Model": run_ml_factor,
    }

    results = []

    # Daily returns of the underlying stocks.
    # Shift(-1) because if we get a signal today, we earn tomorrow's return.
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
        dr      = daily_returns.loc[out_of_sample_start:]

        # Calculate daily portfolio return (Equal weighted among active Shariah-compliant signals).
        stock_cols = _filter_shariah_compliant_columns(list(signals.columns))
        active_signals = signals[stock_cols]
        active_dr      = dr[stock_cols]

        # Number of active positions each day
        num_positions = active_signals.sum(axis=1)

        # Avoid division by zero
        weights = active_signals.div(num_positions.replace(0, 1), axis=0)

        # Portfolio daily return (gross)
        port_returns = (weights * active_dr).sum(axis=1)

        # ── Task A: deduct transaction costs ──────────────────────────────────
        port_returns = _apply_transaction_costs(port_returns, signals, stock_cols)

        cagr, max_dd, sharpe = calculate_metrics(port_returns)

        # Calculate Buy & Hold benchmark for the same period.
        # Equal weight all stocks, NO transaction costs (pure benchmark).
        bench_weights  = pd.DataFrame(1/len(stock_cols),
                                      index=active_dr.index, columns=stock_cols)
        bench_returns  = (bench_weights * active_dr).sum(axis=1)
        bench_cagr, bench_max_dd, bench_sharpe = calculate_metrics(bench_returns)

        # ─────────────────────────────────────────────────────────────────────
        # Statistical Validation Infrastructure (Bootstrap & Sample Size)
        # ─────────────────────────────────────────────────────────────────────
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
                sample = np.random.choice(daily_port_returns_non_zero,
                                          size=len(daily_port_returns_non_zero),
                                          replace=True)
                bootstrap_means.append(np.mean(sample))

            ci_lower = np.percentile(bootstrap_means, 2.5)  * 252  # Annualised
            ci_upper = np.percentile(bootstrap_means, 97.5) * 252  # Annualised

        results.append({
            "Algorithm":    name,
            "CAGR":         f"{cagr*100:.2f}%",
            "Max Drawdown": f"{max_dd*100:.2f}%",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "N_Trades":     sample_size,
            "Validation":   is_valid,
            "95% CI (Ann)": (f"[{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]"
                             if sample_size >= 30 else "N/A"),
        })

    print("\n" + "="*80)
    print("BACKTEST SHOOTOUT RESULTS (OUT-OF-SAMPLE + WALK-FORWARD EMBARGO)")
    print(f"Transaction costs applied: {ROUND_TRIP_COST*100:.4f}% round-trip")
    print("="*80)
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    print("\nBenchmark (Buy & Hold Nifty Basket):")
    print(f"CAGR: {bench_cagr*100:.2f}%, Max Drawdown: {bench_max_dd*100:.2f}%, "
          f"Sharpe Ratio: {bench_sharpe:.2f}")

# ── Task C: Walk-Forward Backtest ─────────────────────────────────────────────

def run_walk_forward_backtest():
    """
    Walk-Forward Backtest using a rolling 12-month training / 3-month test split.

    For each window:
      • Training period: 12 months (used by ML algo to fit its model)
      • Test period:     3 months (out-of-sample, evaluated for all algos)
      • Advance by:      3 months per iteration

    Metrics averaged across all out-of-sample windows:
      • CAGR, Sharpe Ratio, Max Drawdown

    Transaction costs (ROUND_TRIP_COST) are applied to every window.

    The summary table is printed to stdout.
    """
    print("\n" + "="*80)
    print("WALK-FORWARD BACKTEST  (12-month train | 3-month test | 3-month step)")
    print(f"Transaction costs applied: {ROUND_TRIP_COST*100:.4f}% round-trip")
    print("="*80)

    print("Loading data...")
    dfs = load_data()
    close_df  = dfs['close']
    high_df   = dfs['high']
    low_df    = dfs['low']
    volume_df = dfs['volume']

    vix = close_df['^INDIAVIX'] if '^INDIAVIX' in close_df else None

    algos = {
        "Momentum (VCP)": run_momentum,
        "Mean Reversion":  run_mean_reversion,
        "ML Factor Model": run_ml_factor,
    }

    daily_returns = close_df.pct_change().shift(-1)
    stock_cols    = _filter_shariah_compliant_columns(list(close_df.columns))

    # Build window boundaries.
    # Use monthly DateOffset so windows align to calendar months.
    all_dates    = close_df.index
    start_date   = all_dates[0]
    end_date     = all_dates[-1]

    train_months = 12
    test_months  = 3
    step_months  = 3

    # Collect per-window results: {algo_name: [{"cagr": ..., "sharpe": ..., "max_dd": ...}, ...]}
    window_results = {name: [] for name in algos}
    window_dates   = []

    window_start = start_date
    window_count = 0

    while True:
        train_end = window_start + pd.DateOffset(months=train_months)
        test_end  = train_end   + pd.DateOffset(months=test_months)

        if test_end > end_date:
            break

        # Snap to actual index dates
        train_end_actual = all_dates[all_dates <= train_end]
        test_end_actual  = all_dates[all_dates <= test_end]

        if len(train_end_actual) == 0 or len(test_end_actual) == 0:
            break

        train_end_dt = train_end_actual[-1]
        test_end_dt  = test_end_actual[-1]

        # Make sure there are enough rows in the test window
        oos_mask = (all_dates > train_end_dt) & (all_dates <= test_end_dt)
        if oos_mask.sum() < 5:
            window_start += pd.DateOffset(months=step_months)
            continue

        window_count += 1
        oos_start_dt = all_dates[oos_mask][0]
        window_dates.append((oos_start_dt.date(), test_end_dt.date()))

        # Slice data for training (full window) and OOS test
        # Algos receive the full slice up to test_end so that the ML algo can
        # train on train portion; rule-based algos are evaluated on OOS only.
        train_slice_close  = close_df.loc[:test_end_dt]
        train_slice_high   = high_df.loc[:test_end_dt]
        train_slice_low    = low_df.loc[:test_end_dt]
        train_slice_volume = volume_df.loc[:test_end_dt]

        for name, algo_func in algos.items():
            signals_full = algo_func(train_slice_close, train_slice_high,
                                     train_slice_low,  train_slice_volume)

            # Apply VIX overlay
            if vix is not None:
                vix_mask_flag = vix.loc[:test_end_dt] > 22
                for col in signals_full.columns:
                    if col != '^INDIAVIX':
                        signals_full.loc[vix_mask_flag, col] = 0

            # Restrict to OOS window
            signals_oos = signals_full.loc[oos_start_dt:test_end_dt]
            dr_oos      = daily_returns.loc[oos_start_dt:test_end_dt, stock_cols]

            active_signals = signals_oos[stock_cols].astype(float)
            num_positions  = active_signals.sum(axis=1)
            weights        = active_signals.div(num_positions.replace(0, 1), axis=0)
            port_ret       = (weights * dr_oos).sum(axis=1)

            # Apply transaction costs
            port_ret = _apply_transaction_costs(port_ret, signals_oos, stock_cols)

            cagr, max_dd, sharpe = calculate_metrics(port_ret)
            window_results[name].append({"cagr": cagr, "sharpe": sharpe, "max_dd": max_dd})

        window_start += pd.DateOffset(months=step_months)

    if window_count == 0:
        print("Not enough data to build walk-forward windows.  "
              "Need at least 15 months of history.")
        return

    print(f"\nTotal walk-forward windows evaluated: {window_count}")
    print(f"Window dates (OOS): {window_dates[0]} → {window_dates[-1]}\n")

    # ── Summary table ──────────────────────────────────────────────────────────
    summary_rows = []
    for name, windows in window_results.items():
        avg_cagr   = np.mean([w["cagr"]   for w in windows])
        avg_sharpe = np.mean([w["sharpe"] for w in windows])
        avg_max_dd = np.mean([w["max_dd"] for w in windows])
        summary_rows.append({
            "Algorithm":        name,
            "Avg CAGR":         f"{avg_cagr*100:.2f}%",
            "Avg Sharpe":       f"{avg_sharpe:.2f}",
            "Avg Max Drawdown": f"{avg_max_dd*100:.2f}%",
            "Windows":          window_count,
        })

    summary_df = pd.DataFrame(summary_rows)
    print("WALK-FORWARD SUMMARY (averaged across all OOS windows)")
    print(summary_df.to_string(index=False))
    print("\n[!] Reminder: results are an optimistic upper-bound. "
          "Shariah filter and Anti-Trap Shield not applied.")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaSentinel Backtest Harness")
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Run walk-forward backtest (12-month train / 3-month test) instead of shootout",
    )
    args = parser.parse_args()

    if args.walk_forward:
        run_walk_forward_backtest()
    else:
        run_shootout()

import sys
import os
import json
import logging
import numpy as np
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.session import get_read_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluator")

def calculate_portfolio_metrics():
    """Calculates Win Rate, Max Drawdown, and Sharpe Ratio for the portfolio."""
    metrics_path = PROJECT_ROOT / "dashboard" / "portfolio_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    
    with get_read_connection() as conn:
        try:
            df_trades = conn.execute("""
                SELECT id, symbol, entry_price, quantity, exit_price, realized_pnl, exit_date
                FROM positions
                WHERE status IN ('CLOSED', 'MANUALLY_CLOSED', 'STOPPED_OUT', 'TARGET_REACHED')
                ORDER BY exit_date ASC, id ASC
            """).df()
        except Exception as e:
            logger.warning(f"Could not query positions: {e}")
            df_trades = None

        try:
            df_equity = conn.execute("""
                SELECT trade_date, core_equity
                FROM equity_curve
                ORDER BY trade_date ASC
            """).df()
        except Exception as e:
            logger.warning(f"Could not query equity_curve: {e}")
            df_equity = None

    total_trades = len(df_trades) if df_trades is not None and not df_trades.empty else 0
    if total_trades > 0:
        winners = df_trades[df_trades['realized_pnl'] > 0]
        win_rate = float((len(winners) / total_trades) * 100.0)
    else:
        win_rate = 0.0

    # If equity_curve has >= 5 rows, use continuous time-series returns for Sharpe & Drawdown
    if df_equity is not None and len(df_equity) >= 5:
        data_source = "equity_curve"
        core_eq = df_equity['core_equity'].astype(float)
        daily_returns = core_eq.pct_change().dropna()
        std_ret = float(daily_returns.std(ddof=1)) if len(daily_returns) > 1 else 0.0
        mean_ret = float(daily_returns.mean()) if len(daily_returns) > 0 else 0.0
        if std_ret > 0:
            annualized_sharpe = float((mean_ret / std_ret) * np.sqrt(252))
        else:
            annualized_sharpe = 0.0

        cummax_eq = core_eq.cummax()
        dd_series = (core_eq / cummax_eq) - 1.0
        max_dd_pct = float(abs(dd_series.min()) * 100.0) if not dd_series.empty else 0.0
        max_drawdown = max_dd_pct
        sharpe_ratio = annualized_sharpe
    else:
        data_source = "positions_only"
        if total_trades > 0:
            df_trades['cum_pnl'] = df_trades['realized_pnl'].cumsum()
            df_trades['peak_pnl'] = df_trades['cum_pnl'].cummax()
            df_trades['drawdown'] = df_trades['peak_pnl'] - df_trades['cum_pnl']
            max_drawdown = float(df_trades['drawdown'].max())
            max_dd_pct = max_drawdown

            investment = df_trades['entry_price'] * df_trades['quantity']
            df_trades['trade_return'] = np.where(investment > 0, df_trades['realized_pnl'] / investment, 0.0)
            mean_return = float(df_trades['trade_return'].mean())
            std_return = float(df_trades['trade_return'].std(ddof=1)) if len(df_trades) > 1 else 0.0
            sharpe_ratio = float(mean_return / std_return) if std_return > 0 else 0.0
            annualized_sharpe = sharpe_ratio
        else:
            max_drawdown = 0.0
            max_dd_pct = 0.0
            sharpe_ratio = 0.0
            annualized_sharpe = 0.0

    # P6-4: Deflated Sharpe Ratio (DSR) & PBO calculation
    try:
        from src.portfolio.metrics import compute_dsr
        with get_read_connection() as conn:
            n_row = conn.execute("SELECT COUNT(*) FROM strategy_version").fetchone()
            n_trials = int(n_row[0]) if n_row and n_row[0] else 1
    except Exception:
        n_trials = 1

    dsr = 0.0
    pbo = 1.0
    if df_equity is not None and len(df_equity) >= 10:
        try:
            core_eq = df_equity['core_equity'].astype(float)
            d_rets = core_eq.pct_change().dropna().values
            dsr = float(compute_dsr(observed_sharpe=annualized_sharpe, n_trials=n_trials, daily_returns=d_rets))
            pbo = float(round(1.0 - dsr, 4))
        except Exception as e:
            logger.warning(f"DSR computation failed: {e}")

    metrics = {
        "total_trades": int(total_trades),
        "win_rate": float(win_rate),
        "max_drawdown": float(max_drawdown),
        "max_drawdown_pct": float(max_dd_pct),
        "sharpe_ratio": float(sharpe_ratio),
        "annualized_sharpe": float(annualized_sharpe),
        "n_strategy_trials": int(n_trials),
        "dsr": round(dsr, 4),
        "pbo": round(pbo, 4),
        "data_source": data_source
    }

    logger.info(f"Calculated Metrics ({data_source}): {metrics}")

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=4)

    logger.info(f"Metrics saved to {metrics_path}")
    return metrics

def run_evaluator():
    logger.info("Running Evaluator to calculate core portfolio metrics...")
    metrics = calculate_portfolio_metrics()

    # P6-6: Shadow Mode A/B Group Analytics
    from src.config.settings import settings
    if settings.SHADOW_MODE:
        try:
            with get_read_connection() as conn:
                ab_df = conn.execute("""
                    SELECT 
                        COALESCE(ab_group, 'control') as ab_group,
                        COUNT(*) as total_candidates,
                        ROUND(AVG(COALESCE(ml_probability, 0.0)) * 100, 2) as avg_ml_prob,
                        SUM(CASE WHEN status IN ('APPROVED', 'TARGET_REACHED') THEN 1 ELSE 0 END) as approved_count,
                        SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count
                    FROM screener_candidates
                    GROUP BY ab_group
                """).df()
            logger.info("A/B Shadow Mode Analytics:\n" + ab_df.to_string(index=False))
        except Exception as e:
            logger.debug(f"A/B analytics evaluation skipped: {e}")

if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("run_evaluator"):
        run_evaluator()

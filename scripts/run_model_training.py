import sys
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import logging
import math
import datetime
import json
import subprocess
from sklearn.metrics import roc_auc_score

from src.db.session import get_read_connection
from src.utils.technical_indicators import wilders_rsi, atr
from src.utils.benchmark_provider import get_benchmark_ohlc, BENCHMARK_SYMBOL
from src.utils.cv import PurgedKFoldEmbargo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_model_training")

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "xgboost_global.pkl"
META_PATH = MODEL_DIR / "xgboost_global_meta.json"

FEATURE_COLS = ['sharpe_rank', 'dist_high', 'market_regime', 'rel_rsi', 'ema_dist', 'vol_cluster']


def register_strategy_trial(strategy_name: str, config_dict: dict) -> int:
    """
    Hash the training configuration and insert into strategy_version if new.
    Returns N = total distinct configurations tried for this strategy.
    """
    import hashlib
    from src.db.queue_writer import db_write

    config_str = json.dumps(config_dict, sort_keys=True)
    param_hash = hashlib.sha256(config_str.encode()).hexdigest()

    try:
        with get_read_connection() as conn:
            max_id_row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM strategy_version").fetchone()
            next_id = int(max_id_row[0]) if max_id_row and max_id_row[0] is not None else 1

        db_write(
            """
            INSERT INTO strategy_version (id, strategy_name, parameters_hash, parameters_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (parameters_hash) DO NOTHING
            """,
            [next_id, strategy_name, param_hash, config_str],
            sync=True,
        )
    except Exception as e:
        logger.warning(f"Could not persist strategy_version: {e}")

    try:
        with get_read_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM strategy_version WHERE strategy_name = ?",
                [strategy_name],
            ).fetchone()
        return int(row[0]) if row and row[0] else 1
    except Exception:
        return 1



def triple_barrier_label(
    high_series: pd.Series,
    low_series: pd.Series,
    close_series: pd.Series,
    entry_price: float,
    atr_val: float,
    upper_mult: float = 2.0,
    lower_mult: float = 1.8,
    max_days: int = 5,
) -> int:
    """
    Path-dependent Triple Barrier Labeling per Marcos López de Prado.
    
    Barriers:
    - Upper: entry_price + upper_mult * atr_val (Win, +1)
    - Lower: entry_price - lower_mult * atr_val (Loss, -1)
    - Time: max_days trading bars
    
    Returns:
    -  1 (Win): Upper barrier touched first
    - -1 (Loss): Lower barrier touched first (stop-loss priority)
    -  0 (Timeout): Neither barrier touched; resolved by terminal close direction
    """
    if atr_val <= 0.0 or np.isnan(atr_val):
        atr_val = entry_price * 0.02  # 2% safe fallback

    upper_barrier = entry_price + (upper_mult * atr_val)
    lower_barrier = entry_price - (lower_mult * atr_val)

    window_len = min(max_days, len(high_series))
    for i in range(window_len):
        h = float(high_series.iloc[i])
        l = float(low_series.iloc[i])
        
        # Stop loss priority: check lower barrier first on each bar
        if l <= lower_barrier:
            return -1
        if h >= upper_barrier:
            return 1

    # Time barrier: if neither touched, evaluate terminal close direction
    if window_len > 0:
        terminal_close = float(close_series.iloc[window_len - 1])
        if terminal_close > entry_price:
            return 1
        elif terminal_close < entry_price:
            return -1
    return 0


def extract_features_and_labels(df: pd.DataFrame, bench_features: pd.DataFrame) -> pd.DataFrame:
    """
    Computes canonical 6 quantitative features and triple-barrier binary targets
    for a single symbol DataFrame sorted by trade_date.
    """
    df = df.copy()
    close = df['close_price']
    high = df['high_price']
    low = df['low_price']

    # 1. dist_high: distance to 252-day high
    df['dist_high'] = close / high.rolling(252, min_periods=10).max() - 1.0

    # 2. ema_dist: distance to 20-day EMA
    df['ema_20'] = close.ewm(span=20, adjust=False).mean()
    df['ema_dist'] = close / df['ema_20'] - 1.0

    # 3. vol_cluster: 20-day standard deviation of returns
    df['returns'] = close.pct_change()
    df['vol_cluster'] = df['returns'].rolling(20, min_periods=10).std()

    # Technical indicators
    df['rsi'] = wilders_rsi(close, period=14)
    df['atr'] = atr(high, low, close, period=14)

    # Raw Sharpe proxy
    mean_ret = df['returns'].rolling(60, min_periods=10).mean()
    std_ret = df['returns'].rolling(60, min_periods=10).std()
    df['sharpe_raw'] = mean_ret / (std_ret + 1e-6)
    ann_sharpe = df['sharpe_raw'] * np.sqrt(252)
    df['sharpe_rank'] = 1.0 / (1.0 + np.exp(-ann_sharpe))

    # Join canonical benchmark features by trade_date
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.DatetimeIndex(df['trade_date'])
    df = df.join(bench_features, how='left')

    df['market_regime'] = df['market_regime'].ffill().bfill().fillna(1).astype(int)
    bench_rsi = df['benchmark_rsi'].ffill().bfill().fillna(50.0)
    df['rel_rsi'] = df['rsi'] - bench_rsi

    # P3-3: Triple-Barrier Path-Dependent Labeling
    max_days = 5
    labels = []
    n = len(df)
    for t in range(n):
        if t + 1 >= n:
            labels.append(np.nan)
            continue
        fut_h = high.iloc[t + 1 : t + 1 + max_days]
        fut_l = low.iloc[t + 1 : t + 1 + max_days]
        fut_c = close.iloc[t + 1 : t + 1 + max_days]
        entry_p = float(close.iloc[t])
        atr_val = float(df['atr'].iloc[t])
        
        tb = triple_barrier_label(fut_h, fut_l, fut_c, entry_p, atr_val, upper_mult=2.0, lower_mult=1.8, max_days=max_days)
        # Binary target mapping: +1 -> 1, -1 -> 0, 0 -> 0
        labels.append(1 if tb == 1 else 0)

    df['target'] = labels
    return df


def train_global_model(raw_df: pd.DataFrame = None, benchmark_df: pd.DataFrame = None):
    """
    Executes the Phase 3 XGBoost retraining pipeline:
    1. Ingests raw data and canonical benchmark data (no synthetic skew).
    2. Computes canonical features with wilders_rsi and triple-barrier labels.
    3. Runs Purged K-Fold Cross-Validation with Embargo (5 folds, 5-day embargo).
    4. Enforces strict conservative validation gate: conservative_auc = mean_auc - std_auc > 0.51.
    5. Serializes weights and provenance metadata only if gate passes.
    """
    logger.info("Starting global XGBoost model training (Phase 3 ML Overhaul)...")
    MODEL_DIR.mkdir(exist_ok=True)

    # 1. Acquire raw symbol data
    if raw_df is None:
        with get_read_connection() as conn:
            logger.info("Fetching raw historical data from DuckDB...")
            raw_df = conn.execute("""
                SELECT symbol, trade_date, close_price, high_price, low_price, total_traded_qty as volume
                FROM bhavcopy_daily
                WHERE series = 'EQ'
                ORDER BY symbol, trade_date ASC;
            """).df()

    if raw_df is None or raw_df.empty:
        raise ValueError("No data returned from DB for model training.")

    raw_df['trade_date'] = pd.to_datetime(raw_df['trade_date'])

    # 2. Acquire canonical benchmark data (eliminating synthetic equal-weight skew)
    if benchmark_df is None:
        logger.info(f"Fetching canonical benchmark data for {BENCHMARK_SYMBOL}...")
        benchmark_df = get_benchmark_ohlc(lookback_days=1000)

    bench_df = benchmark_df.copy()
    if hasattr(bench_df.index, 'tz') and bench_df.index.tz is not None:
        bench_df.index = bench_df.index.tz_localize(None).normalize()
    else:
        bench_df.index = pd.DatetimeIndex(bench_df.index).normalize()
    bench_df = bench_df[~bench_df.index.duplicated(keep='last')]

    bench_sma50 = bench_df['Close'].rolling(50, min_periods=10).mean()
    bench_df['market_regime'] = (bench_df['Close'] >= bench_sma50).astype(int)
    bench_df['benchmark_rsi'] = wilders_rsi(bench_df['Close'], period=14)
    bench_features = bench_df[['market_regime', 'benchmark_rsi']]

    # 3. Extract features and labels per symbol
    all_features = []
    logger.info("Extracting symbol-level features and triple-barrier labels...")
    grouped = raw_df.groupby('symbol')
    for symbol, group in grouped:
        if len(group) < 20:
            continue
        group_df = group.copy().sort_values('trade_date')
        feat_df = extract_features_and_labels(group_df, bench_features)
        all_features.append(feat_df)

    if not all_features:
        raise ValueError("Insufficient historical data across symbols to train model.")

    full_df = pd.concat(all_features, ignore_index=True)
    full_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    clean_df = full_df.dropna(subset=FEATURE_COLS + ['target']).copy()
    clean_df['target'] = clean_df['target'].astype(int)

    # Check minimum target variance
    if clean_df.empty or len(clean_df['target'].unique()) < 2:
        logger.error("Insufficient data for training: not enough samples or only one class present.")
        raise ValueError("Insufficient data for training: only one class present in target.")

    clean_df['trade_date'] = pd.to_datetime(clean_df['trade_date'])
    unique_dates = np.sort(clean_df['trade_date'].unique())
    logger.info(f"Compiled training dataset: {len(clean_df)} rows across {len(unique_dates)} unique dates.")

    if len(unique_dates) < 5:
        raise ValueError(f"Need at least 5 unique trading dates for cross-validation, got {len(unique_dates)}.")

    # 4. P3-2: Purged K-Fold Cross-Validation with Embargo
    n_splits = 5
    embargo_days = 5
    
    # Register strategy parameter configuration for DSR/PBO tracking
    training_config = {
        "features": FEATURE_COLS,
        "n_splits": n_splits,
        "embargo_days": embargo_days,
        "auc_gate": 0.51,
        "label": "triple_barrier",
        "xgb_params": {
            "n_estimators": 100,
            "max_depth": 4,
            "learning_rate": 0.03,
            "subsample": 0.8,
            "colsample_bytree": 0.8
        }
    }
    n_trials = register_strategy_trial("xgboost_global", training_config)
    logger.info(f"Strategy trial N={n_trials} registered for DSR/PBO tracking.")

    cv = PurgedKFoldEmbargo(n_splits=n_splits, embargo_days=embargo_days)
    fold_aucs = []

    logger.info(f"Executing Purged K-Fold Cross-Validation ({n_splits} folds, {embargo_days}-day embargo)...")
    for fold_idx, (train_idx, test_idx) in enumerate(cv.split(unique_dates)):
        train_dates = unique_dates[train_idx]
        test_dates = unique_dates[test_idx]

        train_fold = clean_df[clean_df['trade_date'].isin(train_dates)]
        test_fold = clean_df[clean_df['trade_date'].isin(test_dates)]

        if len(train_fold['target'].unique()) < 2 or len(test_fold['target'].unique()) < 2:
            logger.warning(f"Fold {fold_idx}: Skipped due to single class in split.")
            continue

        X_tr = train_fold[FEATURE_COLS]
        y_tr = train_fold['target']
        X_te = test_fold[FEATURE_COLS]
        y_te = test_fold['target']

        fold_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            n_jobs=-1,
            random_state=42,
            eval_metric="logloss"
        )
        fold_model.fit(X_tr, y_tr)
        preds = fold_model.predict_proba(X_te)[:, 1]

        try:
            auc = roc_auc_score(y_te, preds)
            fold_aucs.append(auc)
            logger.info(f"Fold {fold_idx}: ROC-AUC = {auc:.4f} (Train: {len(train_fold)}, Test: {len(test_fold)})")
        except Exception as e:
            logger.warning(f"Fold {fold_idx}: Error evaluating ROC-AUC: {e}")

    if not fold_aucs:
        raise ValueError("Cross-validation failed: no valid fold AUCs could be computed.")

    mean_auc = float(np.mean(fold_aucs))
    std_auc = float(np.std(fold_aucs, ddof=1)) if len(fold_aucs) > 1 else 0.0
    conservative_auc = mean_auc - std_auc

    logger.info(
        f"Cross-Validation Summary: Mean AUC = {mean_auc:.4f}, Std = {std_auc:.4f}, "
        f"Conservative AUC = {conservative_auc:.4f}"
    )

    # 5. Strict Validation Gate: Conservative AUC must strictly exceed 0.51
    if conservative_auc <= 0.51:
        logger.error(
            f"Model FAILED purged-CV gate: mean={mean_auc:.4f} std={std_auc:.4f} "
            f"conservative={conservative_auc:.4f} <= 0.51. Serialization aborted."
        )
        raise ValueError(
            f"Model validation gate failed (conservative AUC {conservative_auc:.4f} <= 0.51). Aborting model serialization."
        )

    # 6. Fit Final Model and Serialize
    logger.info("Validation gate passed! Training final production model on full dataset...")
    final_model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42,
        eval_metric="logloss"
    )
    final_model.fit(clean_df[FEATURE_COLS], clean_df['target'])

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(final_model, f)

    # Git commit hash provenance
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        git_commit = "unknown"

    meta_data = {
        "trained_at": datetime.datetime.now().isoformat(),
        "row_count": len(clean_df),
        "auc_mean": round(mean_auc, 4),
        "auc_std": round(std_auc, 4),
        "auc_conservative": round(conservative_auc, 4),
        "n_folds": n_splits,
        "embargo_days": embargo_days,
        "validation_gate": "conservative_auc > 0.51",
        "features": FEATURE_COLS,
        "n_strategy_trials": n_trials,
        "git_commit": git_commit,
        "benchmark_symbol": BENCHMARK_SYMBOL
    }
    with open(META_PATH, "w") as f:
        json.dump(meta_data, f, indent=2)

    logger.info(f"Enhanced Phase 3 model successfully serialized to {MODEL_PATH}")
    return final_model, meta_data


if __name__ == "__main__":
    from src.utils.job_alert import job_alert_context
    with job_alert_context("run_model_training"):
        train_global_model()

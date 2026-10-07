"""
Phase 2 LightGBM LambdaRank Cross-Sectional Ranking Model.

Trains a learning-to-rank (LTR) model on cross-sectional VCP candidate setups
grouped by trade_date, optimizing NDCG@1 and NDCG@3 against forward 5-day return deciles (0 to 9).
Provides rank_top_setups(candidates, top_n=3) for evening inference with graceful fallback.
"""

import os
import sys
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
import pandas as pd

# Project root path resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("train_lambdarank")

# LightGBM dependency detection with fallback support
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except (ImportError, Exception) as e:
    lgb = None
    HAS_LIGHTGBM = False
    logger.warning(f"LightGBM not available in runtime ({e}). Fallback ranking enabled.")

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "lgbm_lambdarank.pkl"

FEATURE_COLS = [
    "residual_momentum_score",
    "residual_momentum_rank",
    "rs_score",
    "beta",
    "delivery_pct",
    "pct_above_52w_low",
    "pct_from_52w_high",
    "volume_dryup"
]

LAMBDARANK_PARAMS = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "eval_at": [1, 3],
    "ndcg_eval_at": [1, 3],
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 5,
    "min_data_in_group": 2,
    "label_gain": [0, 1, 3, 7, 15, 31, 63, 127, 255, 511],
    "verbosity": -1,
    "random_state": 42
}


class FallbackLambdaRankModel:
    """
    Deterministic linear factor ranker used when LightGBM C library is unavailable
    or before initial multi-year LambdaRank training.
    """
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "residual_momentum_score": 0.40,
            "residual_momentum_rank": 0.30,
            "rs_score": 0.15,
            "delivery_pct": 0.10,
            "volume_dryup": 0.05
        }
        self.feature_names = FEATURE_COLS

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Computes composite linear score from feature matrix."""
        if X.ndim == 1:
            X = X.reshape(1, -1)
            
        scores = np.zeros(X.shape[0], dtype=float)
        for i, col in enumerate(self.feature_names):
            if col in self.weights and i < X.shape[1]:
                val = np.nan_to_num(X[:, i], nan=0.0)
                scores += self.weights[col] * val
        return scores


def compute_forward_decile_labels(returns: pd.Series) -> pd.Series:
    """
    Translates continuous forward 5-day returns into integer decile labels (0 to 9)
    for NDCG ranking relevance.
    """
    if len(returns) == 0:
        return pd.Series(dtype=int)
    if returns.nunique() < 2:
        return pd.Series(0, index=returns.index, dtype=int)
        
    try:
        deciles = pd.qcut(returns, q=10, labels=False, duplicates="drop")
        min_v, max_v = deciles.min(), deciles.max()
        if max_v > min_v:
            scaled = np.floor((deciles - min_v) / (max_v - min_v) * 9.0).astype(int)
            return pd.Series(scaled, index=returns.index)
        return pd.Series(0, index=returns.index, dtype=int)
    except Exception:
        pct_ranks = returns.rank(pct=True, method="first")
        deciles = np.clip(np.floor(pct_ranks * 10).astype(int), 0, 9)
        return pd.Series(deciles, index=returns.index)


def prepare_query_groups(df: pd.DataFrame, group_col: str = "trade_date") -> Tuple[pd.DataFrame, List[int]]:
    """
    Sorts dataset by query group and returns sorted dataframe along with query group sizes.
    """
    sorted_df = df.sort_values(group_col).reset_index(drop=True)
    group_sizes = sorted_df.groupby(group_col, sort=False).size().tolist()
    return sorted_df, group_sizes


def train_lambdarank_model(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    params: Optional[Dict[str, Any]] = None,
    num_boost_round: int = 100,
    model_save_path: Optional[Union[str, Path]] = None
) -> Tuple[Any, Dict[str, Any]]:
    """
    Trains LightGBM LambdaRank cross-sectional ranking model grouped by trade_date.
    Saves trained artifact to model_save_path.
    """
    cfg_params = dict(LAMBDARANK_PARAMS)
    if params:
        cfg_params.update(params)

    sorted_train, train_groups = prepare_query_groups(train_df, "trade_date")
    X_train = sorted_train[FEATURE_COLS].to_numpy()
    y_train = sorted_train["target_decile"].to_numpy().astype(int)

    metrics = {
        "num_train_queries": len(train_groups),
        "total_train_samples": len(sorted_train),
        "has_lightgbm": HAS_LIGHTGBM
    }

    if not HAS_LIGHTGBM or lgb is None:
        logger.info("Training FallbackLambdaRankModel (LightGBM not installed).")
        model = FallbackLambdaRankModel()
        metrics["model_type"] = "FallbackLambdaRankModel"
        if model_save_path:
            save_path = Path(model_save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                pickle.dump(model, f)
        return model, metrics

    # LightGBM dataset setup
    train_data = lgb.Dataset(X_train, label=y_train, group=train_groups, feature_name=FEATURE_COLS)
    
    valid_sets = [train_data]
    valid_names = ["train"]
    if val_df is not None and not val_df.empty:
        sorted_val, val_groups = prepare_query_groups(val_df, "trade_date")
        X_val = sorted_val[FEATURE_COLS].to_numpy()
        y_val = sorted_val["target_decile"].to_numpy().astype(int)
        val_data = lgb.Dataset(X_val, label=y_val, group=val_groups, reference=train_data, feature_name=FEATURE_COLS)
        valid_sets.append(val_data)
        valid_names.append("valid")
        metrics["num_val_queries"] = len(val_groups)
        metrics["total_val_samples"] = len(sorted_val)

    evals_result = {}
    booster = lgb.train(
        cfg_params,
        train_data,
        num_boost_round=num_boost_round,
        valid_sets=valid_sets,
        valid_names=valid_names,
        callbacks=[lgb.record_evaluation(evals_result)]
    )

    metrics["evals_result"] = evals_result
    metrics["model_type"] = "LightGBM_Booster"

    save_target = Path(model_save_path) if model_save_path else MODEL_PATH
    save_target.parent.mkdir(parents=True, exist_ok=True)
    with open(save_target, "wb") as f:
        pickle.dump(booster, f)
    logger.info(f"Saved LambdaRank model to {save_target}")

    return booster, metrics


def load_lambdarank_model(model_path: Optional[Union[str, Path]] = None) -> Any:
    """
    Loads saved LambdaRank model from disk with fallback to FallbackLambdaRankModel.
    """
    target_path = Path(model_path) if model_path else MODEL_PATH
    if target_path.exists():
        try:
            with open(target_path, "rb") as f:
                model = pickle.load(f)
                return model
        except Exception as e:
            logger.warning(f"Failed loading model from {target_path}: {e}")

    return FallbackLambdaRankModel()


def rank_top_setups(
    candidates: Union[List[Dict[str, Any]], pd.DataFrame],
    top_n: int = 3,
    model: Optional[Any] = None,
    feature_cols: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Ranking inference function to evaluate surviving candidate setups and output the Top N setups.
    
    Args:
        candidates: List of candidate dictionaries or DataFrame (e.g. from VCP screener).
        top_n: Number of top setups to return (default: 3).
        model: Pre-loaded model or None (will auto-load).
        feature_cols: Optional feature names list.
        
    Returns:
        List of candidate dictionaries ordered from highest to lowest predicted ranking score.
    """
    if candidates is None:
        return []

    # Normalize to list of dicts
    if isinstance(candidates, pd.DataFrame):
        candidate_list = candidates.to_dict(orient="records")
    elif isinstance(candidates, list):
        candidate_list = [dict(c) for c in candidates]
    else:
        return []

    if not candidate_list:
        return []

    if len(candidate_list) <= top_n and model is None and not MODEL_PATH.exists():
        # Short-circuit if candidates count is small and no model exists
        for i, c in enumerate(candidate_list):
            c["rank_position"] = i + 1
            c["ranking_method"] = "RESIDUAL_MOMENTUM_PERCENTILE"
            c["rank_score"] = float(c.get("residual_momentum_rank", 0.0))
        return sorted(candidate_list, key=lambda x: x.get("rank_score", 0.0), reverse=True)

    cols = feature_cols or FEATURE_COLS
    
    # Extract feature matrix
    X_rows = []
    for c in candidate_list:
        row = []
        for col in cols:
            val = c.get(col)
            if val is None:
                if col == "beta":
                    val = 1.0
                elif col == "residual_momentum_rank":
                    val = 50.0
                elif col in ["volume_dryup", "volatility_contraction"]:
                    val = 1.0 if c.get(col) else 0.0
                else:
                    val = 0.0
            row.append(float(val))
        X_rows.append(row)
    X = np.array(X_rows, dtype=float)

    # Resolve ranking model
    active_model = model if model is not None else load_lambdarank_model()
    
    try:
        raw_scores = active_model.predict(X)
        if isinstance(raw_scores, list):
            raw_scores = np.array(raw_scores)
        ranking_method = "LAMBDARANK" if (HAS_LIGHTGBM and not isinstance(active_model, FallbackLambdaRankModel)) else "RESIDUAL_MOMENTUM_PERCENTILE"
    except Exception as e:
        logger.warning(f"Inference prediction failed ({e}). Falling back to residual momentum.")
        raw_scores = np.array([float(c.get("residual_momentum_rank", 0.0)) for c in candidate_list])
        ranking_method = "RESIDUAL_MOMENTUM_PERCENTILE"

    # Sort descending
    top_indices = np.argsort(raw_scores)[::-1]
    
    ranked_results = []
    for rank_idx, idx in enumerate(top_indices[:top_n]):
        item = dict(candidate_list[idx])
        item["rank_position"] = rank_idx + 1
        item["rank_score"] = round(float(raw_scores[idx]), 4)
        item["ranking_method"] = ranking_method
        ranked_results.append(item)

    return ranked_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"[*] LambdaRank Module Loaded. LightGBM Available: {HAS_LIGHTGBM}")
    print(f"[*] Default Features: {FEATURE_COLS}")
    print(f"[*] LambdaRank Parameters: {LAMBDARANK_PARAMS}")

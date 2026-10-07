"""
Unit Tests for Phase 2 LightGBM LambdaRank Cross-Sectional Ranking Model.

Verifies:
1. LambdaRank query-grouping by trade_date.
2. Translation of forward 5-day returns to integer deciles (0 to 9).
3. Objective structure ("lambdarank", "ndcg", eval_at=[1, 3]).
4. Model training and evaluation.
5. rank_top_setups(candidates, top_n=3) outputting top 3 setups each evening.
6. Graceful fallback when LightGBM is absent or uninstalled.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from scripts.train_lambdarank import (
    prepare_query_groups,
    compute_forward_decile_labels,
    train_lambdarank_model,
    rank_top_setups,
    FallbackLambdaRankModel,
    LAMBDARANK_PARAMS,
    FEATURE_COLS,
    HAS_LIGHTGBM
)


def test_test4_lambdarank_query_grouping_and_top3_ranking_logic():
    """
    Test 4: LambdaRank query-grouping and Top 3 setup ranking logic.
    """
    # 1. Query Grouping
    trade_dates = ["2026-10-01"] * 4 + ["2026-10-02"] * 6 + ["2026-10-03"] * 5
    symbols = [f"SYM_{i:02d}" for i in range(len(trade_dates))]
    df = pd.DataFrame({
        "trade_date": trade_dates,
        "symbol": symbols,
        "residual_momentum_score": np.random.normal(0, 1, len(trade_dates)),
        "residual_momentum_rank": np.random.uniform(20, 100, len(trade_dates)),
        "rs_score": np.random.normal(5, 10, len(trade_dates)),
        "beta": np.random.uniform(0.5, 1.5, len(trade_dates)),
        "delivery_pct": np.random.uniform(20, 70, len(trade_dates)),
        "pct_above_52w_low": np.random.uniform(20, 100, len(trade_dates)),
        "pct_from_52w_high": np.random.uniform(0, 15, len(trade_dates)),
        "volume_dryup": [1.0] * len(trade_dates),
        "target_decile": np.random.randint(0, 10, len(trade_dates))
    })

    sorted_df, group_sizes = prepare_query_groups(df, "trade_date")
    assert group_sizes == [4, 6, 5], f"Expected group sizes [4, 6, 5], got {group_sizes}"
    assert len(sorted_df) == 15

    # 2. Top 3 Setup Ranking Logic
    candidates = [
        {"symbol": "SYM_ALPHA", "residual_momentum_rank": 95.0, "residual_momentum_score": 3.2, "rs_score": 25.0, "beta": 0.9, "delivery_pct": 65.0, "volume_dryup": True},
        {"symbol": "SYM_BETA", "residual_momentum_rank": 88.0, "residual_momentum_score": 2.1, "rs_score": 18.0, "beta": 1.1, "delivery_pct": 55.0, "volume_dryup": True},
        {"symbol": "SYM_GAMMA", "residual_momentum_rank": 72.0, "residual_momentum_score": 1.0, "rs_score": 12.0, "beta": 1.3, "delivery_pct": 40.0, "volume_dryup": False},
        {"symbol": "SYM_DELTA", "residual_momentum_rank": 92.0, "residual_momentum_score": 2.8, "rs_score": 22.0, "beta": 0.8, "delivery_pct": 60.0, "volume_dryup": True},
        {"symbol": "SYM_EPSILON", "residual_momentum_rank": 75.0, "residual_momentum_score": 1.2, "rs_score": 14.0, "beta": 1.0, "delivery_pct": 45.0, "volume_dryup": True},
    ]

    top_3 = rank_top_setups(candidates, top_n=3)
    assert len(top_3) == 3
    assert top_3[0]["rank_position"] == 1
    assert top_3[1]["rank_position"] == 2
    assert top_3[2]["rank_position"] == 3

    # Scores must be descending
    assert top_3[0]["rank_score"] >= top_3[1]["rank_score"] >= top_3[2]["rank_score"]

    top_symbols = [c["symbol"] for c in top_3]
    # SYM_ALPHA and SYM_DELTA have the strongest profiles and should be in top 3
    assert "SYM_ALPHA" in top_symbols
    assert "SYM_DELTA" in top_symbols


def test_forward_5day_decile_target_derivation():
    """
    Verifies forward returns are properly converted to 0..9 integer decile targets.
    """
    rets = pd.Series([
        -0.08, -0.05, -0.02, -0.01, 0.0,
        0.01, 0.03, 0.05, 0.08, 0.12,
        0.15, 0.20, 0.25, 0.30, 0.35
    ])
    deciles = compute_forward_decile_labels(rets)
    assert deciles.min() == 0
    assert deciles.max() == 9
    assert len(deciles) == len(rets)


def test_lambdarank_model_training_and_ndcg_parameters():
    """
    Verifies model training pipeline and objective configuration.
    """
    assert LAMBDARANK_PARAMS["objective"] == "lambdarank"
    assert LAMBDARANK_PARAMS["metric"] == "ndcg"
    assert 1 in LAMBDARANK_PARAMS["eval_at"]
    assert 3 in LAMBDARANK_PARAMS["eval_at"]

    # Generate synthetic training set with 3 trading sessions
    records = []
    np.random.seed(42)
    for d_idx, d in enumerate(["2026-09-01", "2026-09-02", "2026-09-03"]):
        for i in range(8):
            records.append({
                "trade_date": d,
                "symbol": f"S_{d_idx}_{i}",
                "residual_momentum_score": float(np.random.normal(0, 1)),
                "residual_momentum_rank": float(np.random.uniform(20, 100)),
                "rs_score": float(np.random.normal(0, 10)),
                "beta": float(np.random.uniform(0.6, 1.4)),
                "delivery_pct": float(np.random.uniform(20, 60)),
                "pct_above_52w_low": float(np.random.uniform(20, 80)),
                "pct_from_52w_high": float(np.random.uniform(0, 15)),
                "volume_dryup": 1.0,
                "target_decile": int(i % 10)
            })

    train_df = pd.DataFrame(records)
    model, metrics = train_lambdarank_model(train_df, num_boost_round=10)

    assert model is not None
    assert metrics["num_train_queries"] == 3
    assert metrics["total_train_samples"] == 24


def test_rank_top_setups_fallback_when_lightgbm_missing():
    """
    Verifies that when LightGBM is missing or raises an exception, rank_top_setups
    cleanly falls back to RESIDUAL_MOMENTUM_PERCENTILE without throwing errors.
    """
    candidates = [
        {"symbol": "SYM_X", "residual_momentum_rank": 78.0},
        {"symbol": "SYM_Y", "residual_momentum_rank": 94.0},
        {"symbol": "SYM_Z", "residual_momentum_rank": 82.0},
        {"symbol": "SYM_W", "residual_momentum_rank": 65.0},
    ]

    with patch("scripts.train_lambdarank.HAS_LIGHTGBM", False):
        top_setups = rank_top_setups(candidates, top_n=3, model=FallbackLambdaRankModel())

    assert len(top_setups) == 3
    assert top_setups[0]["symbol"] == "SYM_Y"  # Highest residual momentum rank (94.0)
    assert top_setups[0]["ranking_method"] in ["RESIDUAL_MOMENTUM_PERCENTILE", "LAMBDARANK"]


def test_rank_top_setups_accepts_pandas_dataframe():
    """
    Verifies rank_top_setups accepts candidates formatted as pandas DataFrame.
    """
    df = pd.DataFrame([
        {"symbol": "CAND_1", "residual_momentum_rank": 72.0, "residual_momentum_score": 1.1},
        {"symbol": "CAND_2", "residual_momentum_rank": 96.0, "residual_momentum_score": 3.4},
        {"symbol": "CAND_3", "residual_momentum_rank": 85.0, "residual_momentum_score": 2.2},
    ])

    results = rank_top_setups(df, top_n=2)
    assert len(results) == 2
    assert results[0]["symbol"] == "CAND_2"

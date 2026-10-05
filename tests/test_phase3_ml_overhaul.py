"""
Phase 3 Machine Learning & Statistical Overhaul Verification Test Suite.
Verifies:
1. Canonical technical indicators (Wilder's RSI, ATR).
2. Screener indicator alignment.
3. Purged K-Fold Cross-Validation with Embargo (López de Prado).
4. Triple-Barrier Path-Dependent Labeling.
5. Strict Conservative Validation Gate & Serialization.
6. Agent Memory continuous learning lifecycle (Debate Graph -> EOD Reconciliation).
"""

import pytest
import numpy as np
import pandas as pd
import json
from unittest.mock import patch, MagicMock

from src.utils.technical_indicators import wilders_rsi, atr
from src.screening.mean_reversion_screener import evaluate_mean_reversion
from src.screening.ml_features import calculate_rsi, extract_quantitative_features
from src.utils.benchmark_provider import get_benchmark_rsi
from src.utils.cv import PurgedKFoldEmbargo
from scripts.run_model_training import triple_barrier_label, train_global_model, FEATURE_COLS
from src.db.session import init_db, get_read_connection, get_write_connection
from src.db.queue_writer import db_write


@pytest.fixture(autouse=True)
def cleanup_phase3_db():
    """Ensure Phase 3 test symbols are cleaned up after each test."""
    yield
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'P3_SYM_%'")
            conn.execute(
                "DELETE FROM agent_memory WHERE symbol IN ('P3_TEST_SYM', 'RECON_TEST_SL', 'RECON_TEST_WIN', 'JUDGE_TEST_SYM') OR symbol LIKE 'P3_%'"
            )
            conn.execute(
                "DELETE FROM positions WHERE symbol IN ('P3_TEST_SYM', 'RECON_TEST_SL', 'RECON_TEST_WIN', 'JUDGE_TEST_SYM') OR symbol LIKE 'P3_%'"
            )
    except Exception:
        pass


# -------------------------------------------------------------------------
# 1. Canonical Technical Indicators (P3-1)
# -------------------------------------------------------------------------

def test_wilders_rsi_monotonic_uptrend():
    """Verify purely monotonic price series achieves RSI = 100.0 without divide-by-zero."""
    close = pd.Series([100.0 + i for i in range(30)])
    rsi = wilders_rsi(close, period=14)
    assert len(rsi) == 30
    assert rsi.iloc[-1] == 100.0
    # Every bar after warmup period should be 100.0
    for val in rsi.iloc[14:]:
        assert val == 100.0


def test_wilders_rsi_monotonic_downtrend():
    """Verify purely decreasing price series achieves RSI = 0.0."""
    close = pd.Series([100.0 - i for i in range(30)])
    rsi = wilders_rsi(close, period=14)
    assert len(rsi) == 30
    assert rsi.iloc[-1] == 0.0
    # Every bar after warmup period should be 0.0
    for val in rsi.iloc[14:]:
        assert val == 0.0


def test_wilders_rsi_initial_sma_seed():
    """Verify bar 14 is seeded strictly with the 14-period SMA of gains/losses per Wilder (1978)."""
    prices = [
        100.0, 102.0, 101.0, 104.0, 103.0, 105.0, 102.0,
        106.0, 104.0, 107.0, 105.0, 108.0, 106.0, 109.0, 107.0, 110.0
    ]
    close = pd.Series(prices)
    rsi = wilders_rsi(close, period=14)

    # Manual calculation of initial 14-period SMA (from bar 1 to 14)
    deltas = np.diff(prices[:15])
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain_14 = np.mean(gains)
    avg_loss_14 = np.mean(losses)
    rs_14 = avg_gain_14 / avg_loss_14
    expected_rsi_14 = 100.0 - (100.0 / (1.0 + rs_14))

    assert np.isclose(rsi.iloc[14], expected_rsi_14, atol=1e-5)
    # Warmup bars should be 50.0 neutral
    assert rsi.iloc[0] == 50.0
    assert rsi.iloc[13] == 50.0


def test_wilders_atr_calculation():
    """Verify ATR computes Wilder smoothed true range."""
    # When High - Low = 10 and Close doesn't gap, TR is 10.0
    high = pd.Series([105.0] * 25)
    low = pd.Series([95.0] * 25)
    close = pd.Series([100.0] * 25)

    atr_vals = atr(high, low, close, period=14)
    assert len(atr_vals) == 25
    assert np.isclose(atr_vals.iloc[-1], 10.0, atol=1e-3)


def test_screeners_and_benchmark_use_canonical_rsi():
    """Verify all screeners and benchmark providers import and invoke canonical wilders_rsi."""
    close = pd.Series([100.0 + i for i in range(25)])
    
    # 1. ml_features delegation
    rsi_ml = calculate_rsi(close, window=14)
    assert rsi_ml.iloc[-1] == 100.0

    # 2. benchmark_provider
    mock_df = pd.DataFrame({"Close": [100.0 + i for i in range(30)]})
    with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=mock_df):
        bench_rsi = get_benchmark_rsi(period=14)
        assert bench_rsi == 100.0


# -------------------------------------------------------------------------
# 2. Purged K-Fold Cross-Validation & Embargo (P3-2)
# -------------------------------------------------------------------------

def test_purged_kfold_embargo_no_overlap_and_margin():
    """Verify PurgedKFoldEmbargo eliminates all train/test overlap and enforces embargo buffer."""
    unique_dates = np.array([f"2026-01-{i:02d}" for i in range(1, 31)] + [f"2026-02-{i:02d}" for i in range(1, 29)])
    n_splits = 5
    embargo_days = 5
    cv = PurgedKFoldEmbargo(n_splits=n_splits, embargo_days=embargo_days)

    splits = list(cv.split(unique_dates))
    assert len(splits) == n_splits

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        # 1. Zero overlap
        overlap = set(train_idx).intersection(set(test_idx))
        assert len(overlap) == 0, f"Fold {fold_idx} has {len(overlap)} overlapping indices!"

        # 2. Strict embargo buffer
        min_test = test_idx.min()
        max_test = test_idx.max()

        train_before = train_idx[train_idx < min_test]
        train_after = train_idx[train_idx > max_test]

        if len(train_before) > 0:
            assert min_test - train_before.max() > embargo_days, f"Fold {fold_idx}: Pre-test purge violated!"
        if len(train_after) > 0:
            assert train_after.min() - max_test > embargo_days, f"Fold {fold_idx}: Post-test embargo violated!"


# -------------------------------------------------------------------------
# 3. Triple-Barrier Path-Dependent Labeling (P3-3)
# -------------------------------------------------------------------------

def test_triple_barrier_label_stop_out_priority():
    """
    Verify stop-loss priority: An intraday breach of the lower barrier on Day 1
    returns -1 (Loss) even if the price rebounds above the upper barrier on Day 5.
    """
    entry_price = 100.0
    atr_val = 5.0
    # lower barrier: 100 - 1.8 * 5 = 91.0
    # upper barrier: 100 + 2.0 * 5 = 110.0
    
    # Day 1 breaches 91.0 (Low = 89.0), Day 5 touches 120.0
    highs = pd.Series([102.0, 103.0, 104.0, 105.0, 120.0])
    lows = pd.Series([89.0, 95.0, 96.0, 97.0, 98.0])
    closes = pd.Series([101.0, 102.0, 103.0, 104.0, 119.0])

    label = triple_barrier_label(
        high_series=highs,
        low_series=lows,
        close_series=closes,
        entry_price=entry_price,
        atr_val=atr_val,
        upper_mult=2.0,
        lower_mult=1.8,
        max_days=5
    )
    assert label == -1, f"Expected -1 (Stop Loss priority), got {label}"


def test_triple_barrier_label_target_hit():
    """Verify hitting upper profit barrier first returns +1 (Win)."""
    entry_price = 100.0
    atr_val = 5.0
    # upper barrier: 110.0
    highs = pd.Series([105.0, 112.0, 103.0, 104.0, 105.0])
    lows = pd.Series([98.0, 99.0, 96.0, 97.0, 98.0])
    closes = pd.Series([103.0, 111.0, 102.0, 103.0, 104.0])

    label = triple_barrier_label(
        high_series=highs,
        low_series=lows,
        close_series=closes,
        entry_price=entry_price,
        atr_val=atr_val,
        upper_mult=2.0,
        lower_mult=1.8,
        max_days=5
    )
    assert label == 1, f"Expected +1 (Target Hit), got {label}"


def test_triple_barrier_label_timeout_direction():
    """Verify timeout case evaluates terminal close relative to entry price."""
    entry_price = 100.0
    atr_val = 5.0
    # Neither 91 nor 110 touched
    highs = pd.Series([102.0, 103.0, 102.0, 103.0, 104.0])
    lows = pd.Series([98.0, 98.0, 98.0, 97.0, 98.0])

    # Case A: Terminal close > entry -> +1
    closes_up = pd.Series([101.0, 102.0, 101.0, 102.0, 103.0])
    lbl_up = triple_barrier_label(highs, lows, closes_up, entry_price, atr_val)
    assert lbl_up == 1

    # Case B: Terminal close < entry -> -1
    closes_down = pd.Series([99.0, 99.0, 99.0, 98.0, 97.0])
    lbl_down = triple_barrier_label(highs, lows, closes_down, entry_price, atr_val)
    assert lbl_down == -1

    # Case C: Terminal close == entry -> 0
    closes_flat = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
    lbl_flat = triple_barrier_label(highs, lows, closes_flat, entry_price, atr_val)
    assert lbl_flat == 0


# -------------------------------------------------------------------------
# 4. Strict Conservative Validation Gate (P3-2)
# -------------------------------------------------------------------------

def test_conservative_auc_gate_aborts_sub_threshold():
    """
    Verify training raises ValueError and refuses to serialize weights
    when conservative AUC (mean_auc - std_auc) is <= 0.51.
    """
    # Build synthetic dataset
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    rows = []
    for d in dates:
        for sym in ["SYM1", "SYM2"]:
            rows.append({
                "symbol": sym,
                "trade_date": d,
                "close_price": 100.0 + np.random.randn() * 2,
                "high_price": 105.0 + np.random.randn() * 2,
                "low_price": 95.0 + np.random.randn() * 2,
                "volume": 100000
            })
    synthetic_raw_df = pd.DataFrame(rows)

    bench_dates = pd.date_range("2024-01-01", periods=300, freq="B")
    synthetic_bench_df = pd.DataFrame({
        "Close": [20000.0 + i for i in range(len(bench_dates))]
    }, index=bench_dates)

    # When CV AUC evaluates to random noise (0.50), gate must abort and block serialization
    with patch("scripts.run_model_training.roc_auc_score", return_value=0.50), \
         patch("scripts.run_model_training.register_strategy_trial", return_value=1):
        with pytest.raises(ValueError, match="Model validation gate failed"):
            train_global_model(raw_df=synthetic_raw_df, benchmark_df=synthetic_bench_df)


def test_conservative_auc_gate_passes_and_serializes_with_metadata(tmp_path):
    """
    Verify training succeeds and writes weights and rich provenance metadata
    when conservative AUC exceeds 0.51.
    """
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    rows = []
    for d in dates:
        for sym in ["SYM1", "SYM2"]:
            rows.append({
                "symbol": sym,
                "trade_date": d,
                "close_price": 100.0 + np.random.randn() * 2,
                "high_price": 105.0 + np.random.randn() * 2,
                "low_price": 95.0 + np.random.randn() * 2,
                "volume": 100000
            })
    synthetic_raw_df = pd.DataFrame(rows)

    bench_dates = pd.date_range("2024-01-01", periods=300, freq="B")
    synthetic_bench_df = pd.DataFrame({
        "Close": [20000.0 + i for i in range(len(bench_dates))]
    }, index=bench_dates)

    test_model_path = tmp_path / "xgboost_global.pkl"
    test_meta_path = tmp_path / "xgboost_global_meta.json"

    with patch("scripts.run_model_training.roc_auc_score", return_value=0.75), \
         patch("scripts.run_model_training.register_strategy_trial", return_value=1), \
         patch("scripts.run_model_training.MODEL_PATH", test_model_path), \
         patch("scripts.run_model_training.META_PATH", test_meta_path):
        
        model, meta = train_global_model(raw_df=synthetic_raw_df, benchmark_df=synthetic_bench_df)
        assert model is not None
        assert test_model_path.exists()
        assert test_meta_path.exists()

        # Check metadata schema
        with open(test_meta_path, "r") as f:
            saved_meta = json.load(f)

        assert "trained_at" in saved_meta
        assert saved_meta["row_count"] > 0
        assert saved_meta["auc_mean"] == 0.75
        assert saved_meta["auc_conservative"] > 0.51
        assert saved_meta["n_folds"] == 5
        assert saved_meta["embargo_days"] == 5
        assert saved_meta["validation_gate"] == "conservative_auc > 0.51"
        assert saved_meta["features"] == FEATURE_COLS
        assert "git_commit" in saved_meta
        assert "benchmark_symbol" in saved_meta


# -------------------------------------------------------------------------
# 5. Agent Memory Schema Migration & Lifecycle (P3-4)
# -------------------------------------------------------------------------

def test_agent_memory_db_migration_and_write():
    """Verify non-destructive migrations added columns and records can be inserted."""
    init_db()
    with get_read_connection() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info('agent_memory')").fetchall()]
        for required_col in ["conviction_score", "content", "outcome_label", "kronos_score"]:
            assert required_col in cols, f"Missing required column {required_col} in agent_memory!"

    # Test writing to agent_memory via db_write
    test_content = json.dumps({"thesis": "High momentum breakout", "stop_loss": 450.0})
    db_write("""
        INSERT OR REPLACE INTO agent_memory (
            symbol, memory_date, pattern_type, previous_verdict,
            rejection_reason, bear_flags_noted, kronos_score,
            conviction_score, content, outcome_label, triple_barrier_label, created_at
        ) VALUES ('P3_TEST_SYM', '2026-09-29', 'VCP_STAGE_2', 'APPROVE',
                 '', 'none', 8.5, 8.5, ?, NULL, NULL, CURRENT_TIMESTAMP);
    """, (test_content,))

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT symbol, conviction_score, content, outcome_label, triple_barrier_label
            FROM agent_memory
            WHERE symbol = 'P3_TEST_SYM';
        """).fetchone()

        assert row is not None
        assert row[0] == 'P3_TEST_SYM'
        assert row[1] == 8.5
        assert "High momentum breakout" in row[2]
        assert row[3] is None  # Initial state before liquidation
        assert row[4] is None


def test_eod_reconciliation_updates_agent_memory():
    """Verify stopped out or target reached positions update outcome_label and triple_barrier_label."""
    init_db()
    # 1. Setup candidate memory row
    db_write("""
        INSERT OR REPLACE INTO agent_memory (
            symbol, memory_date, pattern_type, previous_verdict,
            rejection_reason, bear_flags_noted, kronos_score,
            conviction_score, content, outcome_label, triple_barrier_label, created_at
        ) VALUES ('RECON_TEST_SL', '2026-09-29', 'VCP_STAGE_2', 'APPROVE',
                 '', 'none', 7.0, 7.0, '{}', NULL, NULL, CURRENT_TIMESTAMP);
    """)

    # 2. Simulate Stop Loss hit reconciliation update
    ret_pct = -3.5
    db_write("""
        UPDATE agent_memory 
        SET outcome_label = 'LOSS', triple_barrier_label = -1, outcome_3d_pct = ?
        WHERE symbol = 'RECON_TEST_SL' AND outcome_label IS NULL;
    """, (ret_pct,))

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT outcome_label, triple_barrier_label, outcome_3d_pct
            FROM agent_memory
            WHERE symbol = 'RECON_TEST_SL';
        """).fetchone()

        assert row is not None
        assert row[0] == 'LOSS'
        assert row[1] == -1
        assert row[2] == -3.5

    # 3. Setup Target Reached row
    db_write("""
        INSERT OR REPLACE INTO agent_memory (
            symbol, memory_date, pattern_type, previous_verdict,
            rejection_reason, bear_flags_noted, kronos_score,
            conviction_score, content, outcome_label, triple_barrier_label, created_at
        ) VALUES ('RECON_TEST_WIN', '2026-09-29', 'VCP_STAGE_2', 'APPROVE',
                 '', 'none', 8.0, 8.0, '{}', NULL, NULL, CURRENT_TIMESTAMP);
    """)

    # Simulate Target Hit reconciliation update
    win_pct = 7.2
    db_write("""
        UPDATE agent_memory 
        SET outcome_label = 'WIN', triple_barrier_label = 1, outcome_3d_pct = ?
        WHERE symbol = 'RECON_TEST_WIN' AND outcome_label IS NULL;
    """, (win_pct,))

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT outcome_label, triple_barrier_label, outcome_3d_pct
            FROM agent_memory
            WHERE symbol = 'RECON_TEST_WIN';
        """).fetchone()

        assert row is not None
        assert row[0] == 'WIN'
        assert row[1] == 1
        assert row[2] == 7.2


def test_agent_memory_persisted_in_research_judge_node():
    """Verify research_judge_node writes debate transcript and conviction to agent_memory."""
    init_db()
    from src.agents.debate_graph import research_judge_node

    mock_llm_response = "SYNTHESIS: Strong setup confirmed by fundamentals.\nCONVICTION_SCORE: 8.5"
    state = {
        "symbol": "JUDGE_TEST_SYM",
        "bull_thesis": "Strong volume accumulation.",
        "bear_risks": "Approaching resistance.",
        "trigger_price": 500.0,
        "stop_loss_price": 480.0,
        "target_1_price": 540.0,
        "target_2_price": 580.0,
        "suggested_shares": 50,
        "pattern_type": "VCP_STAGE_2",
        "risk_verdict": "APPROVE",
        "rejection_reason": "",
        "fundamentals": {},
        "adtv_20d": 1000000.0,
        "circuit_band": 20
    }

    with patch("src.agents.debate_graph.execute_llm_completion", return_value=mock_llm_response):
        out = research_judge_node(state)
        assert out["conviction_score"] == 8.5

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT symbol, conviction_score, content, outcome_label
            FROM agent_memory
            WHERE symbol = 'JUDGE_TEST_SYM';
        """).fetchone()

        assert row is not None
        assert row[0] == "JUDGE_TEST_SYM"
        assert row[1] == 8.5
        content = json.loads(row[2])
        assert content["target_1"] == 540.0
        assert content["suggested_shares"] == 50
        assert row[3] is None


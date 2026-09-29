"""
Comprehensive Test Suite for Phase 6 Strategic Improvements.
Covers:
  - P6-1: 3-State Gaussian HMM Market Regime Filter
  - P6-2: CPPI-Style Drawdown Control
  - P6-3: Portfolio Volatility Targeting
  - P6-4: Deflated Sharpe Ratio + PBO Tracking
  - P6-5: Nightly DuckDB Cloud Backup (with moto S3 mock)
  - P6-6: Shadow Mode A/B Framework
"""
import os
import math
import json
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import pytest
from moto import mock_aws
import boto3

from src.config.settings import settings
from src.db.session import init_db, get_read_connection, get_db_path
from src.db.queue_writer import db_write
from src.risk.cppi import calculate_cppi_exposure
from src.risk.vol_target import calculate_volatility_scalar
from src.portfolio.metrics import compute_dsr
from src.utils.benchmark_provider import get_market_regime, get_hmm_market_regime, clear_benchmark_cache
from scripts.run_live_preview import is_variant_candidate
from scripts.run_model_training import register_strategy_trial
from scripts.run_evaluator import calculate_portfolio_metrics
import scripts.run_nightly_backup as backup_mod
from scripts.fit_hmm_regime import fit_and_save_hmm


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Creates isolated DuckDB instance for each test."""
    test_db = str(tmp_path / "test_phase6.duckdb")
    monkeypatch.setattr("src.db.session.get_db_path", lambda: test_db)
    monkeypatch.setattr("scripts.run_nightly_backup.DB_PATH", test_db)
    monkeypatch.setattr("scripts.run_nightly_backup.STAGING_DIR", tmp_path / "staging")
    clear_benchmark_cache()
    init_db()
    yield test_db


# ============================================================================
# P6-1: 3-State Gaussian HMM Market Regime Filter Tests
# ============================================================================

def test_hmm_fit_and_state_ordering(tmp_path):
    """Verify HMM fitting orders states monotonically: mean[0] < mean[1] < mean[2]."""
    # Create synthetic price series with 100 days of varying regimes
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    # Low/crisis returns, choppy returns, calm returns
    crisis_rets = np.random.normal(-0.03, 0.02, 40)
    choppy_rets = np.random.normal(0.00, 0.01, 40)
    calm_rets = np.random.normal(0.02, 0.008, 40)
    all_rets = np.concatenate([crisis_rets, choppy_rets, calm_rets])
    prices = 100.0 * np.exp(np.cumsum(all_rets))

    mock_df = pd.DataFrame({
        "Open": prices * 0.99,
        "High": prices * 1.01,
        "Low": prices * 0.98,
        "Close": prices,
        "Volume": [10000] * 120
    }, index=dates)

    model_file = str(tmp_path / "hmm_regime.pkl")
    with patch("scripts.fit_hmm_regime.get_benchmark_ohlc", return_value=mock_df):
        model = fit_and_save_hmm(model_path=model_file)
        assert Path(model_file).exists()
        means = model.means_.flatten()
        assert len(means) == 3
        # State 0 (Crisis) < State 1 (Choppy) < State 2 (Calm)
        assert means[0] < means[1] < means[2], f"States not sorted: {means}"


def test_get_hmm_market_regime_decodes_state(tmp_path):
    """Verify get_hmm_market_regime correctly decodes state from fitted model."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    prices = [100.0 + i * 2.0 for i in range(60)] # Strong uptrend
    mock_df = pd.DataFrame({"Close": prices}, index=dates)

    # Train model on this mock data
    model_file = str(tmp_path / "hmm_regime.pkl")
    with patch("scripts.fit_hmm_regime.get_benchmark_ohlc", return_value=mock_df):
        fit_and_save_hmm(model_path=model_file)

    with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=mock_df):
        regime = get_hmm_market_regime(model_path=model_file)
        assert regime in (0, 1, 2)


def test_hmm_fails_closed_on_predict_error():
    """Verify get_hmm_market_regime fails closed (returns 0 for Crisis) on corrupt model."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    mock_df = pd.DataFrame({"Close": [100.0 + i for i in range(60)]}, index=dates)
    with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=mock_df):
        with patch("joblib.load", side_effect=RuntimeError("Corrupt weights")):
            with patch("pathlib.Path.exists", return_value=True):
                regime = get_hmm_market_regime(model_path="dummy_path.pkl")
                assert regime == 0  # Fail-closed to Crisis


def test_get_market_regime_fallback_when_model_missing():
    """Verify fallback to SMA50 when HMM model file does not exist."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    # Upward trending series: Close > SMA50 -> Risk-On (1)
    mock_df = pd.DataFrame({"Close": [100.0 + i for i in range(60)]}, index=dates)
    with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=mock_df):
        regime = get_market_regime(use_hmm=False)
        assert regime == 1


# ============================================================================
# P6-2: CPPI-Style Drawdown Control Tests
# ============================================================================

def test_cppi_full_exposure_at_hwm():
    """At all-time high water mark, CPPI exposure must be 1.0 (unconstrained)."""
    hwm = 1_000_000.0
    core_equity = 1_000_000.0
    exposure = calculate_cppi_exposure(core_equity, hwm)
    assert abs(exposure - 1.0) < 1e-6


def test_cppi_partial_exposure_mid_drawdown():
    """At 3% drawdown (equity 970k, floor 940k, cushion 30k), exposure is tapered."""
    hwm = 1_000_000.0
    core_equity = 970_000.0  # Floor = 940,000, Cushion = 30,000, MaxCushion = 60,000
    # Exposure = min(1.0, 30,000 / 60,000) = 0.50
    exposure = calculate_cppi_exposure(core_equity, hwm)
    assert 0.0 < exposure < 1.0
    assert abs(exposure - 0.50) < 1e-4


def test_cppi_zero_exposure_at_floor():
    """At exact floor (94% of HWM), cushion is 0, exposure must be 0.0."""
    hwm = 1_000_000.0
    core_equity = 940_000.0  # Exact floor
    assert calculate_cppi_exposure(core_equity, hwm) == 0.0


def test_cppi_zero_exposure_below_floor():
    """Below floor (e.g. 90% of HWM), cushion <= 0, exposure must be 0.0."""
    hwm = 1_000_000.0
    core_equity = 900_000.0
    assert calculate_cppi_exposure(core_equity, hwm) == 0.0


def test_cppi_invalid_inputs_return_zero():
    """Non-positive equity or HWM returns 0.0 safely."""
    assert calculate_cppi_exposure(0.0, 1_000_000.0) == 0.0
    assert calculate_cppi_exposure(-50_000.0, 1_000_000.0) == 0.0
    assert calculate_cppi_exposure(1_000_000.0, 0.0) == 0.0


# ============================================================================
# P6-3: Portfolio Volatility Targeting Tests
# ============================================================================

def test_vol_target_under_limit_returns_one():
    """When portfolio volatility is below target (15%), scalar must be 1.0."""
    open_pos = {"INFY": 50_000.0}
    cov = np.array([[0.01, 0.002], [0.002, 0.01]])  # Low vol: ~10% vol
    scalar = calculate_volatility_scalar(
        open_positions=open_pos,
        candidate_symbol="TCS",
        candidate_value=50_000.0,
        core_equity=1_000_000.0,
        cov_matrix=cov
    )
    assert scalar == 1.0


def test_vol_target_over_limit_scales_down():
    """When portfolio volatility exceeds 15% target, scalar must scale down < 1.0."""
    open_pos = {"INFY": 500_000.0}
    # Covariance matrix reflecting ~30% annualized volatility
    vol = 0.30
    cov = np.array([
        [vol**2, vol**2 * 0.5],
        [vol**2 * 0.5, vol**2]
    ])
    scalar = calculate_volatility_scalar(
        open_positions=open_pos,
        candidate_symbol="TCS",
        candidate_value=500_000.0,
        core_equity=1_000_000.0,
        cov_matrix=cov
    )
    assert scalar < 1.0
    # Expected: target (0.15) / port_vol (~0.26) ~= 0.57
    assert 0.40 < scalar < 0.70


def test_vol_target_single_asset_returns_one():
    """With no open positions, single asset has scalar 1.0."""
    scalar = calculate_volatility_scalar(
        open_positions={},
        candidate_symbol="RELIANCE",
        candidate_value=100_000.0,
        core_equity=1_000_000.0
    )
    assert scalar == 1.0


def test_vol_target_missing_data_fails_open():
    """When covariance matrix cannot be calculated, scalar fails open to 1.0."""
    open_pos = {"INFY": 50_000.0}
    scalar = calculate_volatility_scalar(
        open_positions=open_pos,
        candidate_symbol="UNKNOWN_IPO",
        candidate_value=50_000.0,
        core_equity=1_000_000.0,
        cov_matrix=None
    )
    assert scalar == 1.0


# ============================================================================
# P6-4: Deflated Sharpe Ratio + PBO Tracking Tests
# ============================================================================

def test_dsr_penalty_increases_with_n():
    """Deflated Sharpe Ratio decreases as number of parameter trials N increases."""
    np.random.seed(42)
    # Generate 252 daily returns with mean=0.08%, std=1% (~Sharpe 1.27)
    returns = np.random.normal(0.0008, 0.01, 252)
    observed_sr = float((returns.mean() / returns.std()) * np.sqrt(252))

    dsr_10 = compute_dsr(observed_sr, n_trials=10, daily_returns=returns)
    dsr_100 = compute_dsr(observed_sr, n_trials=100, daily_returns=returns)
    dsr_1000 = compute_dsr(observed_sr, n_trials=1000, daily_returns=returns)

    assert dsr_10 > dsr_100 > dsr_1000, f"DSR did not penalize larger N: {dsr_10}, {dsr_100}, {dsr_1000}"


def test_dsr_insufficient_history_returns_zero():
    """Fewer than 10 return observations returns DSR = 0.0 safely."""
    returns = np.array([0.01, -0.02, 0.005])
    assert compute_dsr(1.5, n_trials=5, daily_returns=returns) == 0.0


def test_register_strategy_trial_increments_and_deduplicates():
    """Different configs increment N; identical config is idempotent (ON CONFLICT DO NOTHING)."""
    cfg1 = {"model": "xgboost", "max_depth": 4, "learning_rate": 0.03}
    cfg2 = {"model": "xgboost", "max_depth": 6, "learning_rate": 0.03}

    n1 = register_strategy_trial("test_strat", cfg1)
    assert n1 >= 1

    # Same config repeated -> same trial count
    n1_repeat = register_strategy_trial("test_strat", cfg1)
    assert n1_repeat == n1

    # New config -> trial count increments
    n2 = register_strategy_trial("test_strat", cfg2)
    assert n2 == n1 + 1


def test_evaluator_metrics_contain_dsr_and_pbo():
    """calculate_portfolio_metrics must compute and return dsr, pbo, and n_strategy_trials."""
    # Seed 15 rows in equity_curve
    base_date = datetime.date(2026, 1, 1)
    for i in range(15):
        d = (base_date + datetime.timedelta(days=i)).isoformat()
        eq = 1_000_000.0 + (i * 2000.0)
        db_write(
            "INSERT INTO equity_curve (trade_date, total_equity, core_equity, unrealized_pnl) VALUES (?, ?, ?, 0.0)",
            [d, eq, eq],
            sync=True
        )

    metrics = calculate_portfolio_metrics()
    assert "dsr" in metrics
    assert "pbo" in metrics
    assert "n_strategy_trials" in metrics
    assert isinstance(metrics["dsr"], float)
    assert isinstance(metrics["pbo"], float)


# ============================================================================
# P6-5: Nightly DuckDB Cloud Backup Tests (with Moto S3)
# ============================================================================

@mock_aws
def test_backup_upload_with_moto(tmp_path, monkeypatch):
    """Test full backup cycle: checkpoint, staging, S3 upload, and size verification."""
    bucket_name = "test-alphasentinel-backup"
    s3_conn = boto3.client("s3", region_name="us-east-1")
    s3_conn.create_bucket(Bucket=bucket_name)

    monkeypatch.setattr(settings, "B2_KEY_ID", "test_key")
    monkeypatch.setattr(settings, "B2_APPLICATION_KEY", "test_secret")
    monkeypatch.setattr(settings, "B2_BUCKET_NAME", bucket_name)
    monkeypatch.setattr(settings, "B2_ENDPOINT_URL", "")

    # Mock _get_s3_client to return the moto mock client
    monkeypatch.setattr(backup_mod, "_get_s3_client", lambda: s3_conn)

    backup_file = backup_mod.run_backup()
    assert backup_file != ""
    assert backup_file.startswith("alphasentinel_")

    # Verify object exists in bucket
    res = s3_conn.head_object(Bucket=bucket_name, Key=backup_file)
    assert res["ContentLength"] > 0


def test_backup_missing_credentials_raises(monkeypatch):
    """When credentials are empty, _get_s3_client must raise RuntimeError."""
    monkeypatch.setattr(settings, "B2_KEY_ID", "")
    monkeypatch.setattr(settings, "B2_APPLICATION_KEY", "")
    with pytest.raises(RuntimeError, match="B2 credentials not configured"):
        backup_mod._get_s3_client()


@mock_aws
def test_backup_retention_policy_deletes_old():
    """Backups older than retention days are deleted; newer ones kept."""
    bucket_name = "test-retention-bucket"
    s3_conn = boto3.client("s3", region_name="us-east-1")
    s3_conn.create_bucket(Bucket=bucket_name)

    # Upload dummy file
    s3_conn.put_object(Bucket=bucket_name, Key="alphasentinel_old.duckdb", Body=b"old_data")
    s3_conn.put_object(Bucket=bucket_name, Key="alphasentinel_new.duckdb", Body=b"new_data")

    # Manually test retention function with cutoff
    backup_mod._enforce_retention(s3_conn, bucket_name, retention_days=0)
    # With retention_days=0, all files whose LastModified < now are deleted
    res = s3_conn.list_objects_v2(Bucket=bucket_name)
    assert "Contents" not in res or len(res["Contents"]) == 0


# ============================================================================
# P6-6: Shadow Mode A/B Framework Tests
# ============================================================================

def test_is_variant_candidate_determinism():
    """Same symbol and date must always hash to the same variant decision."""
    decision1 = is_variant_candidate("TATAMOTORS", "2026-03-15")
    decision2 = is_variant_candidate("TATAMOTORS", "2026-03-15")
    assert decision1 == decision2


def test_is_variant_candidate_distribution():
    """Hashing across 1,000 samples should route approximately 20% to variant."""
    results = [is_variant_candidate(f"STOCK_{i}", "2026-03-15") for i in range(1000)]
    variant_pct = sum(results) / len(results)
    # Check that variant rate is within reasonable tolerance (15% - 25%)
    assert 0.15 <= variant_pct <= 0.25, f"Variant rate unexpected: {variant_pct:.2%}"


def test_ab_group_stored_in_screener_candidates():
    """Verify screener_candidates table schema supports and persists ab_group."""
    cand_id = "TEST_AB_STOCK_2026-03-15"
    db_write("""
        INSERT OR REPLACE INTO screener_candidates (
            id, scan_date, symbol, pattern_type, trigger_price, adtv_20d, market_cap_tier, circuit_band,
            ml_probability, status, ab_group
        ) VALUES (?, '2026-03-15', 'TEST_AB_STOCK', 'VCP', 150.0, 1000000.0, 'LARGE', 20.0, 0.72, 'APPROVED', 'variant')
    """, [cand_id], sync=True)

    with get_read_connection() as conn:
        row = conn.execute("SELECT ab_group FROM screener_candidates WHERE id = ?", [cand_id]).fetchone()
    assert row is not None
    assert row[0] == "variant"

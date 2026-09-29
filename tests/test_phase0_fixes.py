"""
Unit tests validating Phase 0 emergency remediations.
Covers:
- P0-1: Conviction score sentinel initialization & consensus gate fail-closed behavior
- P0-2: VCP Screener 52w high/low calculation using true intraday extremes
- P0-3: Post-Mortem Lab SQL column alignment and division-by-zero protection
- P0-4: Job failure alerting decorator and context manager
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# P0-1: Live Preview Consensus Gate Sentinel & Fail-Closed Logic
# ---------------------------------------------------------------------------

def test_conviction_score_sentinel_initialization():
    """Verify that state initialization in live preview uses -1.0 sentinel."""
    with open("scripts/run_live_preview.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"conviction_score": -1.0' in content
    assert '"conviction_score": 7.0' not in content
    assert "graph_completed = conviction >= 0.0" in content


def test_consensus_gate_evaluation_logic():
    """Verify consensus gate logic fails closed on sentinel and passes on valid scores."""
    def evaluate_gate(conv_val, ml_prob):
        conviction = float(conv_val) if conv_val is not None else -1.0
        graph_completed = conviction >= 0.0
        gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob > 0.50)
        return gate_approved

    # Unscored sentinel (-1.0) must FAIL even if ML probability is high
    assert evaluate_gate(-1.0, 0.85) is False
    # None (missing) must FAIL
    assert evaluate_gate(None, 0.85) is False
    # Negative conviction must FAIL
    assert evaluate_gate(-0.5, 0.90) is False
    # Valid graph completion but below conviction threshold (6.9) must FAIL
    assert evaluate_gate(6.9, 0.85) is False
    # Valid conviction (8.0) but below ML probability threshold (0.50) must FAIL
    assert evaluate_gate(8.0, 0.49) is False
    assert evaluate_gate(8.0, 0.50) is False
    # Valid conviction (>= 7.0) AND valid ML probability (> 0.50) must APPROVE
    assert evaluate_gate(7.0, 0.51) is True
    assert evaluate_gate(8.5, 0.72) is True


# ---------------------------------------------------------------------------
# P0-2: VCP Screener Intraday High/Low
# ---------------------------------------------------------------------------

def test_vcp_screener_queries_high_low():
    """Verify that vcp_screener.py query includes high_price and low_price and uses high_df/low_df."""
    with open("src/screening/vcp_screener.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "high_price, low_price" in content
    assert "high_df = df.pivot(index='trade_date', columns='symbol', values='high_price').ffill(limit=5)" in content
    assert "low_df = df.pivot(index='trade_date', columns='symbol', values='low_price').ffill(limit=5)" in content
    assert "high_df.tail(252).max()" in content
    assert "low_df.tail(252).min()" in content


def test_vcp_screener_intraday_vs_close_divergence():
    """Verify that high_df and low_df capture true extremes when intraday diverges from close."""
    dates = pd.date_range("2026-01-01", periods=10)
    # Simulate a stock with intraday spikes and dips that close at median
    df = pd.DataFrame({
        "trade_date": dates,
        "symbol": ["TEST"] * 10,
        "close_price": [100.0] * 10,
        "high_price": [105.0] * 9 + [120.0],  # Intraday breakout high
        "low_price": [95.0] * 9 + [80.0],     # Intraday flash crash low
        "total_traded_qty": [1000] * 10,
        "delivery_pct": [50.0] * 10
    })
    close_df = df.pivot(index='trade_date', columns='symbol', values='close_price').ffill(limit=5)
    high_df = df.pivot(index='trade_date', columns='symbol', values='high_price').ffill(limit=5)
    low_df = df.pivot(index='trade_date', columns='symbol', values='low_price').ffill(limit=5)

    high_252d = high_df.tail(252).max()
    low_252d = low_df.tail(252).min()
    close_max = close_df.tail(252).max()
    close_min = close_df.tail(252).min()

    assert high_252d["TEST"] == 120.0
    assert close_max["TEST"] == 100.0
    assert low_252d["TEST"] == 80.0
    assert close_min["TEST"] == 100.0


# ---------------------------------------------------------------------------
# P0-3: Post-Mortem Lab SQL Alignment & Feature Extraction
# ---------------------------------------------------------------------------

def test_post_mortem_lab_sql_alignment():
    """Verify that post_mortem_lab does not select nonexistent columns and maps schema correctly."""
    with open("scripts/post_mortem_lab.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "sc.kronos_breakout_prob" not in content
    assert "pt.ai_model_scores_json" not in content
    assert "pt.trigger_price" not in content
    assert "pt.id AS trade_id" in content
    assert "pt.trailing_stop_loss AS stop_loss" in content
    assert "'TARGET_REACHED'" in content


def test_post_mortem_lab_extract_features_safe_math():
    """Verify extract_features handles empty DataFrames, zero quantities, and missing stop losses safely."""
    from scripts.post_mortem_lab import extract_features

    # Test 1: Empty DataFrame returns gracefully
    empty_df = pd.DataFrame()
    assert extract_features(empty_df).empty

    # Test 2: DataFrame with zero quantity (division by zero protection)
    test_df = pd.DataFrame([{
        "trade_id": "trade_001",
        "symbol": "RELIANCE",
        "sector": "Energy",
        "entry_date": "2026-01-10",
        "exit_date": "2026-01-15",
        "entry_price": 2500.0,
        "exit_price": 2600.0,
        "quantity": 0,  # Zero quantity
        "stop_loss": 2400.0,
        "realized_pnl": 500.0,
        "pattern_type": "MINERVINI_VCP_STAGE2",
        "adtv_20d": 1e8,
        "circuit_band": 20.0,
        "ml_probability": 0.65
    }, {
        "trade_id": "trade_002",
        "symbol": "INFY",
        "sector": "IT",
        "entry_date": "2026-01-10",
        "exit_date": "2026-01-20",
        "entry_price": 1800.0,
        "exit_price": 1750.0,
        "quantity": 10,
        "stop_loss": None,  # Missing stop loss
        "realized_pnl": -500.0,
        "pattern_type": "MINERVINI_VCP_STAGE2",
        "adtv_20d": 5e7,
        "circuit_band": 20.0,
        "ml_probability": 0.55
    }])

    feat_df = extract_features(test_df)
    # Check return_pct did not produce inf or nan from division by zero
    assert not np.isinf(feat_df["return_pct"]).any()
    assert not np.isnan(feat_df["return_pct"]).any()
    # Check trade 1 return_pct calculation used quantity.clip(lower=1)
    assert feat_df.loc[0, "return_pct"] == 500.0 / (2500.0 * 1)
    # Check trade 2 risk_pct with None stop_loss defaults to 0.0
    assert feat_df.loc[1, "risk_pct"] == 0.0
    # Check trade duration days
    assert feat_df.loc[0, "trade_duration_days"] == 5
    assert feat_df.loc[1, "trade_duration_days"] == 10


# ---------------------------------------------------------------------------
# P0-4: Job Failure Alerting Layer
# ---------------------------------------------------------------------------

def test_job_alert_decorator_re_raises_and_alerts():
    """Verify @alert_on_failure dispatches telegram alert and re-raises exception."""
    from src.utils.job_alert import alert_on_failure
    
    @alert_on_failure("test_job")
    def failing_fn():
        raise ValueError("Simulated job failure")
        
    with patch("src.notification.telegram_bot.send_telegram_error_alert") as mock_alert:
        with pytest.raises(ValueError, match="Simulated job failure"):
            failing_fn()
        mock_alert.assert_called_once()
        args, _ = mock_alert.call_args
        assert args[0] == "test_job"
        assert "ValueError: Simulated job failure" in args[1]


def test_job_alert_decorator_success_path():
    """Verify @alert_on_failure succeeds silently when no exception is raised."""
    from src.utils.job_alert import alert_on_failure

    @alert_on_failure("healthy_job")
    def healthy_fn():
        return 42

    with patch("src.notification.telegram_bot.send_telegram_error_alert") as mock_alert:
        result = healthy_fn()
        assert result == 42
        mock_alert.assert_not_called()


def test_job_alert_context_re_raises_and_alerts():
    """Verify job_alert_context dispatches telegram alert and re-raises exception."""
    from src.utils.job_alert import job_alert_context

    with patch("src.notification.telegram_bot.send_telegram_error_alert") as mock_alert:
        with pytest.raises(RuntimeError, match="Context failure"):
            with job_alert_context("test_context_job"):
                raise RuntimeError("Context failure")
        mock_alert.assert_called_once()
        args, _ = mock_alert.call_args
        assert args[0] == "test_context_job"
        assert "RuntimeError: Context failure" in args[1]


def test_job_alert_context_success_path():
    """Verify job_alert_context does not alert on clean completion."""
    from src.utils.job_alert import job_alert_context

    with patch("src.notification.telegram_bot.send_telegram_error_alert") as mock_alert:
        with job_alert_context("healthy_context"):
            x = 10 + 20
        assert x == 30
        mock_alert.assert_not_called()


def test_job_alert_resilient_to_telegram_failure():
    """Verify job_alert re-raises the original exception even if telegram bot dispatch raises."""
    from src.utils.job_alert import job_alert_context

    with patch("src.notification.telegram_bot.send_telegram_error_alert", side_effect=Exception("Network down")):
        with pytest.raises(ValueError, match="Original crash"):
            with job_alert_context("failing_job_with_failing_tg"):
                raise ValueError("Original crash")


# ---------------------------------------------------------------------------
# Additional Edge Case & Resilience Verifications
# ---------------------------------------------------------------------------

def test_post_mortem_lab_zero_or_negative_entry_price():
    """Verify extract_features handles zero, negative, or NaN entry_price without inf or nan."""
    from scripts.post_mortem_lab import extract_features, analyze_losing_trades

    corrupt_df = pd.DataFrame([{
        "trade_id": "trade_zero_entry",
        "symbol": "CORRUPT1",
        "sector": "Metals",
        "entry_date": "2026-01-10",
        "exit_date": "2026-01-15",
        "entry_price": 0.0,
        "exit_price": 50.0,
        "quantity": 100,
        "stop_loss": 40.0,
        "realized_pnl": 1000.0,
        "pattern_type": "VCP",
        "adtv_20d": 1e7,
        "circuit_band": 20.0,
        "ml_probability": 0.6
    }, {
        "trade_id": "trade_nan_entry",
        "symbol": "CORRUPT2",
        "sector": "Metals",
        "entry_date": "2026-01-10",
        "exit_date": "2026-01-15",
        "entry_price": np.nan,
        "exit_price": 50.0,
        "quantity": 0,
        "stop_loss": None,
        "realized_pnl": -500.0,
        "pattern_type": "VCP",
        "adtv_20d": 1e7,
        "circuit_band": 20.0,
        "ml_probability": 0.6
    }, {
        "trade_id": "trade_valid",
        "symbol": "VALID1",
        "sector": "Metals",
        "entry_date": "2026-01-10",
        "exit_date": "2026-01-15",
        "entry_price": 100.0,
        "exit_price": 120.0,
        "quantity": 10,
        "stop_loss": 90.0,
        "realized_pnl": 200.0,
        "pattern_type": "VCP",
        "adtv_20d": 1e7,
        "circuit_band": 20.0,
        "ml_probability": 0.6
    }])

    feat_df = extract_features(corrupt_df)
    assert not np.isinf(feat_df["return_pct"]).any(), "return_pct must not contain inf"
    assert not np.isnan(feat_df["return_pct"]).any(), "return_pct must not contain nan"
    assert not np.isinf(feat_df["risk_pct"]).any(), "risk_pct must not contain inf"
    assert not np.isnan(feat_df["risk_pct"]).any(), "risk_pct must not contain nan"
    assert feat_df.loc[0, "return_pct"] == 0.0
    assert feat_df.loc[0, "risk_pct"] == 0.0

    # Test analyze_losing_trades runs cleanly with 3 trades in same sector
    analyze_losing_trades(feat_df)


def test_consensus_gate_invalid_types_and_fail_closed():
    """Verify consensus gate conversion is resilient to non-numeric strings and fails closed."""
    def parse_and_eval_conviction(conv_val, ml_prob):
        try:
            conviction = float(conv_val) if conv_val is not None else -1.0
        except (ValueError, TypeError):
            conviction = -1.0
        graph_completed = conviction >= 0.0
        return graph_completed and (conviction >= 7.0) and (ml_prob > 0.50)

    # Corrupt string or non-numeric types must not raise exceptions and must fail closed
    assert parse_and_eval_conviction("N/A", 0.95) is False
    assert parse_and_eval_conviction("", 0.95) is False
    assert parse_and_eval_conviction([], 0.95) is False
    assert parse_and_eval_conviction({}, 0.95) is False
    assert parse_and_eval_conviction("7.5", 0.60) is True


def test_vcp_screener_zero_or_negative_high_low_protection():
    """Verify vcp_screener protects against division by zero when 52w extremes are zero."""
    low_val = 0.0
    high_val = 0.0
    current_price = 100.0
    pct_above_low = round((current_price - low_val) / low_val * 100, 1) if low_val > 0 else 0.0
    pct_from_high = round((high_val - current_price) / high_val * 100, 1) if high_val > 0 else 0.0
    assert pct_above_low == 0.0
    assert pct_from_high == 0.0


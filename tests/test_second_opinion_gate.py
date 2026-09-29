"""
Unit tests for Second Opinion Consensus Gate.
Verifies model path, 11-feature alignment, fail-closed handling, and thresholding.
"""
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from src.db.session import init_db
from src.db.queue_writer import db_write
import src.screening.second_opinion_gate as gate


def test_model_path_and_feature_cols():
    """Verify MODEL_PATH points to xgboost_global.pkl and FEATURE_COLS matches exactly."""
    expected_path = Path(gate.__file__).parent.parent.parent / "models" / "xgboost_global.pkl"
    assert gate.MODEL_PATH == expected_path
    
    expected_cols = ['sharpe_rank', 'dist_high', 'market_regime', 'rel_rsi', 'ema_dist', 'vol_cluster']
    assert gate.FEATURE_COLS == expected_cols


def test_extract_features_columns_and_shapes():
    """Verify extract_features produces all 11 quantitative features."""
    dates = pd.date_range('2026-01-01', periods=60)
    df = pd.DataFrame({
        'trade_date': dates,
        'close_price': np.linspace(100, 160, 60),
        'high_price': np.linspace(102, 162, 60),
        'low_price': np.linspace(98, 158, 60),
        'volume': np.random.randint(1000, 5000, 60)
    })
    
    feat_df = gate.extract_features(df)
    for col in gate.FEATURE_COLS:
        assert col in feat_df.columns
    
    # 60 days is enough to have non-NaN values for all 11 features on the latest bar
    latest = feat_df[gate.FEATURE_COLS].iloc[[-1]]
    assert not latest.isna().any().any()


def test_fail_closed_when_model_missing():
    """When consensus model is None or fails to load, gate MUST veto (return False)."""
    with patch.object(gate, "get_champion_model", return_value=None):
        result = gate.evaluate_second_opinion("ANY_STOCK")
        assert result is False, "Gate should fail-closed (return False) when model is missing"


def test_fail_closed_insufficient_data():
    """When symbol has fewer than 50 bars, gate MUST veto (return False)."""
    init_db()
    mock_model = MagicMock()
    
    with patch.object(gate, "get_champion_model", return_value=mock_model):
        # MSCI360 has only 1 row in the test DB
        result = gate.evaluate_second_opinion("MSCI360")
        assert result is False, "Gate should veto when historical data is insufficient (< 50 bars)"
        mock_model.predict_proba.assert_not_called()


def test_gate_approval_and_veto_thresholds():
    """Verify prob > 0.50 approves (True) and prob <= 0.50 vetoes (False)."""
    init_db()
    symbol = "TEST_GATE_STOCK"
    
    # Insert 60 days of synthetic price data
    base_date = date(2026, 1, 1)
    for i in range(60):
        price = 100.0 + (i * 0.5)
        trade_date = base_date + timedelta(days=i)
        db_write("""
            INSERT OR REPLACE INTO bhavcopy_daily (
                symbol, trade_date, series, open_price, high_price, low_price, 
                close_price, prev_close, total_traded_qty, total_traded_val, 
                delivery_qty, delivery_pct, split_multiplier
            ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
        """, (symbol, trade_date, price, price+1, price-1, price, price-0.5), sync=True)

    # 1. Test prob = 0.65 -> Approved (True)
    mock_model_pass = MagicMock()
    mock_model_pass.predict_proba.return_value = np.array([[0.35, 0.65]])
    with patch.object(gate, "get_champion_model", return_value=mock_model_pass):
        assert gate.evaluate_second_opinion(symbol) is True

    # 2. Test prob = 0.50 -> Vetoed (False) (threshold requires > 0.50)
    mock_model_boundary = MagicMock()
    mock_model_boundary.predict_proba.return_value = np.array([[0.50, 0.50]])
    with patch.object(gate, "get_champion_model", return_value=mock_model_boundary):
        assert gate.evaluate_second_opinion(symbol) is False

    # 3. Test prob = 0.42 -> Vetoed (False)
    mock_model_veto = MagicMock()
    mock_model_veto.predict_proba.return_value = np.array([[0.58, 0.42]])
    with patch.object(gate, "get_champion_model", return_value=mock_model_veto):
        assert gate.evaluate_second_opinion(symbol) is False


def test_live_model_evaluation_on_test_symbol():
    """Test actual xgboost_global.pkl model inference if present."""
    if not gate.MODEL_PATH.exists():
        pytest.skip("xgboost_global.pkl not present on disk")
        
    init_db()
    # Reset cached model to force load from disk
    gate._model_loaded = False
    gate._cached_model = None
    
    # Evaluate TEST_TRAP_STOCK (which has 60 rows)
    res = gate.evaluate_second_opinion("TEST_TRAP_STOCK")
    assert isinstance(res, bool)

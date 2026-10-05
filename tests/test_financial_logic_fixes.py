import inspect
import pytest
import pandas as pd
import numpy as np
from unittest import mock
from src.risk.arbiter import calculate_deterministic_risk_and_position
from scripts.run_evaluator import calculate_portfolio_metrics
from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline


def test_arbiter_default_capital():
    """Verify that default portfolio_capital_rupees is 10 Lakhs (10_00_000.0)."""
    sig = inspect.signature(calculate_deterministic_risk_and_position)
    param = sig.parameters["portfolio_capital_rupees"]
    assert param.default == 10_00_000.0

    # Verify that a ₹1,000 stock with ₹10L portfolio allows normal sizing up to ₹1.2L (12%)
    # Risk: trigger=1000, SL=950 (risk_per_share=50). Max trade risk=1.5% of 10L = ₹15,000.
    # Raw shares = 15000 / 50 = 300 shares -> 300 * 1000 = ₹300,000 > 120,000 max position (12%).
    # Max shares by value = 120,000 / 1000 = 120 shares (₹1.2 Lakhs).
    res = calculate_deterministic_risk_and_position(
        symbol="TEST_CO",
        trigger_price=1000.0,
        current_price=1000.0,
        atr_14=25.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        adtv_20d=50_000_000.0
    )
    assert res["verdict"] == "APPROVE"
    # Capital deployed should be clean ₹1.2 Lakhs (12% of 10L) rather than being capped at ₹12,000 (12% of 1L)
    assert res["total_capital_deployed"] > 50_000.0
    assert res["portfolio_allocation_pct"] <= 12.0


def test_eod_reconciliation_pnl_with_quantity():
    """Verify that EOD reconciliation calculates realized and unrealized PnL scaled by quantity."""
    with mock.patch("scripts.run_eod_reconciliation.get_read_connection") as mock_get_conn, \
         mock.patch("scripts.run_eod_reconciliation.db_write") as mock_db_write, \
         mock.patch("scripts.run_eod_reconciliation.is_system_halted", return_value=False), \
         mock.patch("src.notification.telegram_bot.send_telegram_alert"), \
         mock.patch("scripts.run_drawdown_check.check_drawdown"), \
         mock.patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", return_value=None), \
         mock.patch("src.ingestion.bhavcopy.ingest_bhavcopy_dataframe"):

        mock_conn = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        # 3 positions: 
        # 1. Hit SL: entry 100, SL 90, low 88, qty 50 -> realized = (90 - 100) * 50 = -500.0
        # 2. Hit Target: entry 100, target 120, high 125, qty 40 -> realized = (120 - 100) * 40 = 800.0
        # 3. Open MTM: entry 100, ltp 105, low 98, high 108, qty 100 -> unrealized = (105 - 100) * 100 = 500.0
        open_pos_data = [
            ("POS_SL", "SYM_SL", 100.0, 90.0, 120.0, 92.0, 88.0, 101.0, 80.0, 120.0, 50),
            ("POS_T1", "SYM_T1", 100.0, 90.0, 120.0, 122.0, 99.0, 125.0, 80.0, 130.0, 40),
            ("POS_MTM", "SYM_MTM", 100.0, 90.0, 120.0, 105.0, 98.0, 108.0, 80.0, 120.0, 100),
        ]

        import datetime
        from zoneinfo import ZoneInfo
        today = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date()

        def execute_side_effect(query, params=None):
            m = mock.MagicMock()
            if "SELECT MAX(trade_date)" in query and "JOIN" not in query:
                m.fetchone.return_value = [today]
            elif "SELECT p.id, p.symbol, p.entry_price" in query:
                m.fetchall.return_value = open_pos_data
            else:
                m.fetchall.return_value = []
                m.fetchone.return_value = None
            return m

        mock_conn.execute.side_effect = execute_side_effect

        run_eod_reconciliation_pipeline()

        writes = mock_db_write.call_args_list

        # Verify POS_SL write: realized_pnl = -500.0
        sl_write = [w for w in writes if "STOPPED_OUT" in w[0][0]][0]
        assert sl_write[0][1][1] == -500.0 # realized_pnl param

        # Verify POS_T1 write: realized_pnl = 800.0
        t1_write = [w for w in writes if "TARGET_REACHED" in w[0][0]][0]
        assert t1_write[0][1][1] == 800.0 # realized_pnl param

        # Verify POS_MTM write: unrealized_pnl = 500.0
        mtm_write = [w for w in writes if "UPDATE positions SET current_ltp = ?, unrealized_pnl = ?" in w[0][0]][0]
        assert mtm_write[0][1][1] == 500.0 # unrealized_pnl param


def test_evaluator_trade_return_and_status_filter():
    """Verify that run_evaluator queries all exit statuses and calculates trade_return correctly."""
    with mock.patch("scripts.run_evaluator.get_read_connection") as mock_get_conn, \
         mock.patch("builtins.open", mock.mock_open()), \
         mock.patch("json.dump") as mock_json_dump:

        mock_conn = mock.MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        captured_queries = []

        # Create sample trades for each exit status
        # Trade 1: STOPPED_OUT, entry 100, qty 50, realized_pnl = -500.0 (return = -500 / 5000 = -10%)
        # Trade 2: TARGET_REACHED, entry 200, qty 25, realized_pnl = +1000.0 (return = +1000 / 5000 = +20%)
        # Trade 3: CLOSED, entry 150, qty 20, realized_pnl = +300.0 (return = +300 / 3000 = +10%)
        # Trade 4: MANUALLY_CLOSED, entry 80, qty 100, realized_pnl = -400.0 (return = -400 / 8000 = -5%)
        sample_df = pd.DataFrame([
            {"id": "1", "symbol": "A", "entry_price": 100.0, "quantity": 50, "exit_price": 90.0, "realized_pnl": -500.0, "exit_date": "2026-09-01"},
            {"id": "2", "symbol": "B", "entry_price": 200.0, "quantity": 25, "exit_price": 240.0, "realized_pnl": 1000.0, "exit_date": "2026-09-02"},
            {"id": "3", "symbol": "C", "entry_price": 150.0, "quantity": 20, "exit_price": 165.0, "realized_pnl": 300.0, "exit_date": "2026-09-02"},
            {"id": "4", "symbol": "D", "entry_price": 80.0, "quantity": 100, "exit_price": 76.0, "realized_pnl": -400.0, "exit_date": "2026-09-03"},
        ])

        def execute_side_effect(query):
            captured_queries.append(query)
            m = mock.MagicMock()
            m.df.return_value = sample_df.copy()
            return m

        mock_conn.execute.side_effect = execute_side_effect

        calculate_portfolio_metrics()

        # Check that query includes all 4 statuses
        query_text = captured_queries[0]
        for status in ['CLOSED', 'MANUALLY_CLOSED', 'STOPPED_OUT', 'TARGET_REACHED']:
            assert status in query_text

        # Check the dumped metrics
        saved_metrics = mock_json_dump.call_args[0][0]
        # 2 winners out of 4 = 50.0% win rate
        assert saved_metrics["win_rate"] == 50.0
        # Returns: -0.10, +0.20, +0.10, -0.05
        # Mean return = 0.0375
        expected_returns = np.array([-0.10, 0.20, 0.10, -0.05])
        expected_mean = expected_returns.mean()
        expected_std = expected_returns.std(ddof=1)
        expected_sharpe = expected_mean / expected_std
        assert abs(saved_metrics["sharpe_ratio"] - expected_sharpe) < 1e-4

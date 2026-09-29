"""
Phase 5 Operational Reliability Verification Test Suite.
Verifies all 5 components (P5-1 to P5-5) across:
1. P5-1: Scheduler NSE Holiday Guard & Market Hours Check
2. P5-2: DhanBroker LIVE_TRADING_ENABLED Safety Gate & Routing to Paper
3. P5-3: Weekly Performance Evaluator (Time-series Sharpe & Drawdown from equity_curve)
4. P5-4: Agent Feedback Loop Persistence & Dynamic Prompt Injection
5. P5-5: Real Scheduler PID & Heartbeat Status in Dashboard
"""

import os
import sys
import json
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import schedule

from src.db.session import init_db, get_read_connection, get_write_connection
from src.config.settings import settings
from src.execution.order_manager import DhanBroker, PaperBroker
from scripts.run_scheduler import (
    is_market_hours_ist,
    _is_holiday_today,
    job_premarket,
    job_live_preview,
    job_eod_reconciliation,
    job_drawdown_check,
    job_symbol_sync,
    setup_schedule,
    IST
)
from scripts.run_evaluator import calculate_portfolio_metrics
from scripts.run_feedback_loop import evaluate_agent_learning_loop
from src.agents.debate_graph import get_latest_strategy_feedback
from dashboard.app import get_scheduler_status, PROJECT_ROOT


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist and clean up test fixtures."""
    init_db()
    yield
    # Cleanup after test
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM agent_memory WHERE symbol = 'MARKET_WIDE'")
        conn.execute("DELETE FROM equity_curve WHERE trade_date >= '2026-01-01'")


# -------------------------------------------------------------------------
# P5-1: NSE Holiday Guard Tests
# -------------------------------------------------------------------------

def test_is_market_hours_ist_blocks_nse_holidays():
    """Asserts is_market_hours_ist() returns False on official NSE holidays."""
    # Wednesday 11:00 AM IST
    fixed_time = datetime.datetime(2026, 1, 26, 11, 0, 0, tzinfo=IST)
    with patch("datetime.datetime") as mock_dt, \
         patch("src.utils.holidays.is_nse_holiday", return_value=True):
        mock_dt.now.return_value = fixed_time
        assert is_market_hours_ist() is False


def test_is_market_hours_ist_allows_regular_trading_hours():
    """Asserts is_market_hours_ist() returns True on active trading days during market hours."""
    # Wednesday 11:00 AM IST (weekday = 2)
    fixed_time = datetime.datetime(2026, 9, 30, 11, 0, 0, tzinfo=IST)
    with patch("datetime.datetime") as mock_dt, \
         patch("src.utils.holidays.is_nse_holiday", return_value=False):
        mock_dt.now.return_value = fixed_time
        assert is_market_hours_ist() is True


def test_is_market_hours_ist_blocks_weekends():
    """Asserts is_market_hours_ist() returns False on Saturdays and Sundays."""
    # Saturday 11:00 AM IST (weekday = 5)
    sat_time = datetime.datetime(2026, 10, 3, 11, 0, 0, tzinfo=IST)
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = sat_time
        assert is_market_hours_ist() is False


def test_scheduler_weekday_jobs_skip_on_holidays():
    """Asserts scheduler weekday jobs log and exit immediately on official NSE holidays."""
    with patch("scripts.run_scheduler.is_weekday_ist", return_value=True), \
         patch("scripts.run_scheduler._is_holiday_today", return_value=True), \
         patch("scripts.run_scheduler.run_script") as mock_run_script, \
         patch("src.ingestion.symbol_sync.sync_instrument_master") as mock_sync:
        
        job_premarket()
        job_live_preview()
        job_eod_reconciliation()
        job_drawdown_check()
        job_symbol_sync()

        mock_run_script.assert_not_called()
        mock_sync.assert_not_called()


# -------------------------------------------------------------------------
# P5-2: DhanBroker Live Trading Safety Gate Tests
# -------------------------------------------------------------------------

def test_dhan_broker_live_trading_disabled_by_default():
    """Asserts LIVE_TRADING_ENABLED defaults to False."""
    assert getattr(settings, "LIVE_TRADING_ENABLED", None) is False


def test_dhan_broker_routes_to_paper_when_disabled():
    """Asserts DhanBroker routes strictly to PaperBroker when live trading is disabled."""
    with patch.object(settings, "LIVE_TRADING_ENABLED", False), \
         patch.object(PaperBroker, "place_order", return_value="SIMULATED_ORDER_OK") as mock_paper:
        
        order_id = DhanBroker.place_order(
            symbol="TEST_DHAN_DIS",
            price=250.0,
            atr=5.0,
            quantity=50,
            sector="IT"
        )
        assert order_id == "SIMULATED_ORDER_OK"
        mock_paper.assert_called_once()
        kwargs = mock_paper.call_args.kwargs
        assert kwargs.get("execution_type") == "DHAN_SIMULATED"


def test_dhan_broker_emits_safety_banner_when_disabled(caplog):
    """Asserts a clear safety banner is logged when DhanBroker runs with live trading disabled."""
    with patch.object(settings, "LIVE_TRADING_ENABLED", False), \
         patch.object(PaperBroker, "place_order", return_value="SIMULATED_ORDER_OK"):
        
        with caplog.at_level("WARNING"):
            DhanBroker.place_order(symbol="TEST_DHAN_LOG", price=100.0, atr=2.0)
            assert "DHAN BROKER SAFETY GUARD: LIVE TRADING DISABLED" in caplog.text


# -------------------------------------------------------------------------
# P5-3: Weekly Performance Evaluator Tests
# -------------------------------------------------------------------------

def test_run_evaluator_generates_portfolio_metrics(tmp_path):
    """Asserts calculate_portfolio_metrics() calculates metrics and writes portfolio_metrics.json."""
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
        # Insert 3 winning trades and 1 losing trade
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status, realized_pnl, exit_price, exit_date
            ) VALUES 
            ('p_eval_1', 'TEST_EVAL1', '2026-09-01', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-05'),
            ('p_eval_2', 'TEST_EVAL2', '2026-09-02', 200.0, 10, 220.0, 4.0, 190.0, 220.0, 240.0, 100.0, 2.0, 'TARGET_REACHED', 200.0, 220.0, '2026-09-06'),
            ('p_eval_3', 'TEST_EVAL3', '2026-09-03', 150.0, 10, 135.0, 3.0, 140.0, 165.0, 180.0, 100.0, 1.5, 'STOPPED_OUT', -150.0, 135.0, '2026-09-07');
        """)

    metrics = calculate_portfolio_metrics()
    assert metrics is not None
    assert metrics["total_trades"] >= 3
    assert metrics["win_rate"] == pytest.approx(66.67, abs=1.0)
    assert "data_source" in metrics


def test_run_evaluator_uses_equity_curve_when_available():
    """Asserts evaluator uses continuous equity_curve time-series when >=5 rows exist."""
    with get_write_connection() as conn:
        conn.execute("DELETE FROM equity_curve WHERE trade_date >= '2026-09-01'")
        for i in range(1, 11):
            date_str = f"2026-09-{i:02d}"
            eq_val = 1000000.0 + (i * 2000.0)
            conn.execute(
                "INSERT INTO equity_curve (trade_date, total_equity, core_equity, unrealized_pnl) "
                "VALUES (?, ?, ?, ?)",
                [date_str, eq_val, eq_val, 0.0]
            )

    metrics = calculate_portfolio_metrics()
    assert metrics["data_source"] == "equity_curve"
    assert isinstance(metrics["annualized_sharpe"], float)
    assert isinstance(metrics["max_drawdown_pct"], float)
    assert metrics["annualized_sharpe"] > 0.0  # Steady upward equity curve should yield positive Sharpe


def test_calculate_portfolio_metrics_fallback_positions_only():
    """Asserts evaluator falls back to positions-only calculation when <5 equity_curve rows exist."""
    with get_write_connection() as conn:
        conn.execute("DELETE FROM equity_curve WHERE trade_date >= '2026-01-01'")
    
    metrics = calculate_portfolio_metrics()
    assert metrics["data_source"] == "positions_only"


def test_weekly_evaluator_scheduled_in_run_scheduler():
    """Asserts job_weekly_evaluator is registered in setup_schedule() for Sunday 20:00 IST."""
    schedule.clear()
    setup_schedule(include_symbol_sync=False)
    
    matching_jobs = [j for j in schedule.jobs if "weekly_evaluator" in j.tags]
    assert len(matching_jobs) == 1
    job = matching_jobs[0]
    assert job.unit == "weeks" or "sunday" in str(job).lower()


# -------------------------------------------------------------------------
# P5-4: Agent Learning Feedback Loop Tests
# -------------------------------------------------------------------------

def test_feedback_loop_persists_warning_to_agent_memory():
    """Asserts win rate <40% (total >=5) persists STRATEGY_FEEDBACK with verdict WARNING."""
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_WARN_%'")
        conn.execute("DELETE FROM agent_memory WHERE symbol = 'MARKET_WIDE'")
        # Insert 1 win and 5 losses (16.7% win rate)
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status, realized_pnl, exit_price, exit_date
            ) VALUES 
            ('pw_1', 'TEST_WARN_1', '2026-09-01', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-05'),
            ('pw_2', 'TEST_WARN_2', '2026-09-02', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-06'),
            ('pw_3', 'TEST_WARN_3', '2026-09-03', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-07'),
            ('pw_4', 'TEST_WARN_4', '2026-09-04', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-08'),
            ('pw_5', 'TEST_WARN_5', '2026-09-05', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-09'),
            ('pw_6', 'TEST_WARN_6', '2026-09-06', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-10');
        """)

    verdict, msg = evaluate_agent_learning_loop()
    assert verdict == "WARNING"
    assert "WARNING" in msg

    # Verify DuckDB persistence
    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT pattern_type, previous_verdict, content 
            FROM agent_memory 
            WHERE symbol = 'MARKET_WIDE' 
            ORDER BY memory_date DESC LIMIT 1;
        """).fetchone()
        assert row is not None
        assert row[0] == "STRATEGY_FEEDBACK"
        assert row[1] == "WARNING"
        assert "stricter volume dry-up" in row[2]


def test_feedback_loop_persists_healthy_to_agent_memory():
    """Asserts win rate >=40% persists STRATEGY_FEEDBACK with verdict HEALTHY."""
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_HLTH_%'")
        conn.execute("DELETE FROM agent_memory WHERE symbol = 'MARKET_WIDE'")
        # Insert 5 wins and 1 loss (83.3% win rate)
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status, realized_pnl, exit_price, exit_date
            ) VALUES 
            ('ph_1', 'TEST_HLTH_1', '2026-09-01', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-05'),
            ('ph_2', 'TEST_HLTH_2', '2026-09-02', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-06'),
            ('ph_3', 'TEST_HLTH_3', '2026-09-03', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-07'),
            ('ph_4', 'TEST_HLTH_4', '2026-09-04', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-08'),
            ('ph_5', 'TEST_HLTH_5', '2026-09-05', 100.0, 10, 110.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'TARGET_REACHED', 100.0, 110.0, '2026-09-09'),
            ('ph_6', 'TEST_HLTH_6', '2026-09-06', 100.0, 10, 90.0, 2.0, 95.0, 110.0, 120.0, 50.0, 1.0, 'STOPPED_OUT', -100.0, 90.0, '2026-09-10');
        """)

    verdict, msg = evaluate_agent_learning_loop()
    assert verdict == "HEALTHY"

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT pattern_type, previous_verdict 
            FROM agent_memory 
            WHERE symbol = 'MARKET_WIDE' 
            ORDER BY memory_date DESC LIMIT 1;
        """).fetchone()
        assert row is not None
        assert row[0] == "STRATEGY_FEEDBACK"
        assert row[1] == "HEALTHY"


def test_debate_graph_injects_feedback_warning():
    """Asserts get_latest_strategy_feedback() retrieves feedback from agent_memory."""
    feedback_text = "WARNING: Historical win rate is below 40%. Enforce strict 2.5R filter."
    today = datetime.date.today().isoformat()
    
    with get_write_connection() as conn:
        conn.execute("DELETE FROM agent_memory WHERE symbol = 'MARKET_WIDE'")
        conn.execute("""
            INSERT INTO agent_memory (symbol, memory_date, pattern_type, previous_verdict, content)
            VALUES ('MARKET_WIDE', ?, 'STRATEGY_FEEDBACK', 'WARNING', ?);
        """, (today, feedback_text))

    retrieved = get_latest_strategy_feedback()
    assert feedback_text in retrieved


def test_weekly_feedback_loop_scheduled_in_run_scheduler():
    """Asserts job_weekly_feedback_loop is registered in setup_schedule() for Sunday 20:30 IST."""
    schedule.clear()
    setup_schedule(include_symbol_sync=False)

    matching_jobs = [j for j in schedule.jobs if "weekly_feedback_loop" in j.tags]
    assert len(matching_jobs) == 1
    job = matching_jobs[0]
    assert job.unit == "weeks" or "sunday" in str(job).lower()


# -------------------------------------------------------------------------
# P5-5: Dashboard Heartbeat & Scheduler PID Tests
# -------------------------------------------------------------------------

def test_dashboard_status_detects_running_scheduler(tmp_path):
    """Asserts get_scheduler_status() returns ACTIVE when scheduler lock file holds an active PID."""
    lock_file = tmp_path / "logs" / ".scheduler.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    current_pid = os.getpid()
    lock_file.write_text(f"{current_pid}\n")

    with patch("dashboard.app.PROJECT_ROOT", tmp_path), \
         patch("dashboard.app.is_system_halted", return_value=False):
        
        status = get_scheduler_status()
        assert status.badge_type == "success"
        assert "ACTIVE" in status.status_text
        assert str(current_pid) in status.status_text
        assert status.pid == current_pid
        assert status.running is True


def test_dashboard_status_detects_stopped_scheduler(tmp_path):
    """Asserts get_scheduler_status() returns IDLE (SCHEDULER STOPPED) when lock file does not exist."""
    with patch("dashboard.app.PROJECT_ROOT", tmp_path), \
         patch("dashboard.app.is_system_halted", return_value=False):
        
        status = get_scheduler_status()
        assert status.badge_type == "warning"
        assert "IDLE" in status.status_text
        assert status.running is False
        assert status.pid is None


def test_dashboard_status_prioritizes_system_halt(tmp_path):
    """Asserts get_scheduler_status() returns HALTED when system kill switch is active."""
    with patch("dashboard.app.PROJECT_ROOT", tmp_path), \
         patch("dashboard.app.is_system_halted", return_value=True):
        
        status = get_scheduler_status()
        assert status.badge_type == "error"
        assert "HALTED" in status.status_text
        assert status.running is False

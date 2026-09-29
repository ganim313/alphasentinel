"""
Unit and integration tests validating Phase 1 Foundation Infrastructure.
Covers:
- P1-1: Scheduler single-instance lock and systemd unit
- P1-2: Idempotent DB migrations (macro_weather, equity_curve, monthly_peak_equity)
- P1-3: DB maintenance exclusive locking and alert context
- P1-4: Canonical portfolio state engine (all 11 fields, edge cases, fallbacks)
- P1-5: Market benchmark provider (caching, regime, returns) and screener fail-closed integration
"""

import os
import sys
import math
import datetime
import pytest
import portalocker
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_scheduler_single_instance_lock(tmp_path):
    """Verify that acquiring .scheduler.lock blocks a second process."""
    lock_file = tmp_path / ".scheduler.lock"
    fh1 = open(lock_file, "a+")
    portalocker.lock(fh1, portalocker.LOCK_EX | portalocker.LOCK_NB)

    fh2 = open(lock_file, "a+")
    with pytest.raises(portalocker.LockException):
        portalocker.lock(fh2, portalocker.LOCK_EX | portalocker.LOCK_NB)

    portalocker.unlock(fh1)
    fh1.close()
    fh2.close()


def test_scheduler_main_exit_on_lock_collision():
    """Verify scripts/run_scheduler.py exits with code 1 if lock cannot be acquired and cleans up fh."""
    from scripts import run_scheduler
    with patch("portalocker.lock", side_effect=portalocker.LockException("Locked")):
        with pytest.raises(SystemExit) as exc_info:
            run_scheduler.main()
        assert exc_info.value.code == 1
    assert run_scheduler._scheduler_lock_fh is None


def test_systemd_service_file_exists():
    """Verify deployment/alphasentinel-scheduler.service exists with correct settings."""
    service_path = PROJECT_ROOT / "deployment" / "alphasentinel-scheduler.service"
    assert service_path.exists(), "Service file does not exist"
    content = service_path.read_text(encoding="utf-8")
    assert "Description=AlphaSentinel Master Scheduler Daemon" in content
    assert "ExecStart=" in content
    assert "scripts/run_scheduler.py" in content
    assert "Restart=always" in content


def test_init_db_idempotency():
    """Verify init_db() runs cleanly multiple times and creates all required tables/columns."""
    from src.db.session import init_db, get_read_connection
    init_db()
    init_db()  # Run second time to verify idempotency

    with get_read_connection() as conn:
        tables = [r[0] for r in conn.execute("SHOW TABLES;").fetchall()]
        assert "macro_weather" in tables, "macro_weather table missing"
        assert "equity_curve" in tables, "equity_curve table missing"

        cb_cols = [r[1] for r in conn.execute("PRAGMA table_info('circuit_breaker_state');").fetchall()]
        assert "monthly_peak_equity" in cb_cols, "monthly_peak_equity column missing in circuit_breaker_state"
        assert "high_water_mark" in cb_cols, "high_water_mark column missing in circuit_breaker_state"


def test_db_maintenance_portalocker_locking():
    """Verify perform_maintenance acquires exclusive lock with correct flags and timeout."""
    from scripts.run_db_maintenance import perform_maintenance
    from src.db.session import get_db_path

    import warnings
    # Clean run executes smoothly without portalocker timeout warnings
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        perform_maintenance()
        for w in recorded_warnings:
            assert "timeout has no effect in blocking mode" not in str(w.message)

    # Contention test: verify portalocker.Lock is called with timeout=300 and fail_when_locked=False
    with patch("portalocker.Lock") as mock_lock:
        mock_instance = MagicMock()
        mock_instance.__enter__.side_effect = portalocker.LockException("Exclusive lock held")
        mock_lock.return_value = mock_instance

        with pytest.raises(portalocker.LockException):
            perform_maintenance()

        # Check call arguments
        assert mock_lock.call_count == 1
        call_kwargs = mock_lock.call_args[1] if mock_lock.call_args else {}
        timeout = call_kwargs.get("timeout")
        flags = call_kwargs.get("flags")
        fail_when_locked = call_kwargs.get("fail_when_locked")
        assert timeout == 300, f"Expected timeout=300, got {timeout}"
        assert fail_when_locked is False, f"Expected fail_when_locked=False, got {fail_when_locked}"
        if flags is not None:
            assert flags & portalocker.LOCK_EX


def test_portfolio_state_calculation():
    """Verify get_portfolio_state returns all 11 canonical fields with numeric consistency."""
    from src.db.session import init_db
    from src.portfolio.state import get_portfolio_state
    init_db()
    state = get_portfolio_state()

    required_keys = [
        "core_equity", "realized_pnl_total", "unrealized_pnl_total",
        "open_positions_value", "available_cash", "lifetime_hwm",
        "lifetime_hwm_dd_pct", "monthly_peak_equity", "monthly_dd_pct",
        "annualized_sharpe", "as_of"
    ]
    for key in required_keys:
        assert key in state, f"Missing key {key} in portfolio state"

    assert state["core_equity"] == round(1000000.0 + state["realized_pnl_total"] + state["unrealized_pnl_total"], 2)
    assert state["available_cash"] == round(state["core_equity"] - state["open_positions_value"], 2)
    assert state["lifetime_hwm"] >= state["core_equity"]
    assert state["lifetime_hwm_dd_pct"] >= 0.0
    assert state["monthly_peak_equity"] >= state["core_equity"]
    assert state["monthly_dd_pct"] >= 0.0


def test_portfolio_state_with_custom_connection():
    """Verify get_portfolio_state works correctly when passed an explicit connection."""
    from src.portfolio.state import get_portfolio_state
    from src.db.session import get_read_connection
    with get_read_connection() as conn:
        state = get_portfolio_state(conn=conn)
        assert isinstance(state, dict)
        assert "core_equity" in state


def test_portfolio_state_sharpe_calculation_branch():
    """Verify Sharpe ratio computation with simulated exit history >= 10 days."""
    import duckdb
    from src.portfolio.state import get_portfolio_state
    
    # Create in-memory db with schema
    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            current_ltp DOUBLE,
            entry_price DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        CREATE TABLE circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            high_water_mark DOUBLE,
            monthly_peak_equity DOUBLE
        );
        INSERT INTO circuit_breaker_state VALUES (1, 1000000.0, 1000000.0);
    """)

    # Insert 12 daily closed trades with positive returns
    for i in range(12):
        mem_conn.execute(f"""
            INSERT INTO positions VALUES (
                'pos_{i}', 'INFY', 1500.0, 1450.0, 10, 'CLOSED', 500.0, 0.0, DATE '2026-01-{i+1:02d}'
            );
        """)

    state = get_portfolio_state(conn=mem_conn)
    assert state["annualized_sharpe"] > 0.0
    assert state["realized_pnl_total"] == 6000.0
    assert state["core_equity"] == 1006000.0


def test_portfolio_state_missing_circuit_breaker_table():
    """Verify get_portfolio_state does not crash if circuit_breaker_state table does not exist."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            current_ltp DOUBLE,
            entry_price DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
    """)
    # Table circuit_breaker_state does NOT exist
    state = get_portfolio_state(conn=mem_conn)
    assert state["core_equity"] == 1000000.0
    assert state["lifetime_hwm"] == 1000000.0
    assert state["monthly_peak_equity"] == 1000000.0
    assert state["lifetime_hwm_dd_pct"] == 0.0
    assert state["monthly_dd_pct"] == 0.0


def test_portfolio_state_monthly_drawdown_fallback():
    """Verify that when account has losses and no prior peak is recorded, drawdown measures against initial capital."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            current_ltp DOUBLE,
            entry_price DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        INSERT INTO positions VALUES ('pos_loss', 'TCS', 3000.0, 3100.0, 10, 'CLOSED', -50000.0, 0.0, DATE '2026-01-05');
    """)
    state = get_portfolio_state(conn=mem_conn)
    assert state["core_equity"] == 950000.0
    assert state["monthly_peak_equity"] == 1000000.0
    assert state["monthly_dd_pct"] == 5.0
    assert state["lifetime_hwm"] == 1000000.0
    assert state["lifetime_hwm_dd_pct"] == 5.0


def test_benchmark_provider_caching_and_regime():
    """Verify BenchmarkProvider caches data and correctly calculates regime."""
    from src.utils.benchmark_provider import get_benchmark_ohlc, get_market_regime, get_benchmark_returns, clear_benchmark_cache

    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    mock_df = pd.DataFrame({
        "Open": [100.0] * 100,
        "High": [105.0] * 100,
        "Low": [95.0] * 100,
        "Close": [100.0 + i for i in range(100)],
        "Volume": [1000] * 100
    }, index=dates)

    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        # Reset cache
        clear_benchmark_cache()

        # 1. Fetch OHLC
        ohlc = get_benchmark_ohlc(lookback_days=100)
        assert len(ohlc) == 100
        assert mock_instance.history.call_count == 1

        # 2. Verify cache hit (Ticker.history not called again)
        ohlc_cached = get_benchmark_ohlc(lookback_days=100)
        assert len(ohlc_cached) == 100
        assert mock_instance.history.call_count == 1  # Still 1!

        # 3. Verify Risk-On regime (upward trending -> Close > SMA50)
        regime = get_market_regime()
        assert regime == 1

        # 4. Verify returns series
        rets = get_benchmark_returns()
        assert len(rets) == 99
        assert rets.iloc[-1] > 0

        # 5. Verify Risk-Off regime (downward trending series)
        downward_df = pd.DataFrame({
            "Open": [200.0] * 100,
            "High": [205.0] * 100,
            "Low": [195.0] * 100,
            "Close": [200.0 - i for i in range(100)],
            "Volume": [1000] * 100
        }, index=dates)
        import src.utils.benchmark_provider as bp
        bp._cache = {"ohlc": downward_df, "fetched_at": bp.datetime.datetime.now()}
        assert get_market_regime() == 0


def test_benchmark_provider_as_of_date_formats():
    """Verify get_market_regime supports str, date, timestamp, and tz-aware inputs."""
    from src.utils.benchmark_provider import get_market_regime
    import src.utils.benchmark_provider as bp

    dates = pd.date_range("2026-01-01", periods=100, freq="D", tz="Asia/Kolkata")
    mock_df = pd.DataFrame({
        "Open": [100.0] * 100,
        "High": [105.0] * 100,
        "Low": [95.0] * 100,
        "Close": [100.0 + i for i in range(100)],
        "Volume": [1000] * 100
    }, index=dates)

    bp._cache = {"ohlc": mock_df, "fetched_at": bp.datetime.datetime.now()}

    # String date
    regime_str = get_market_regime(as_of_date="2026-03-01")
    assert regime_str in (0, 1)

    # datetime.date
    regime_date = get_market_regime(as_of_date=datetime.date(2026, 3, 1))
    assert regime_date in (0, 1)

    # pd.Timestamp naive
    regime_ts = get_market_regime(as_of_date=pd.Timestamp("2026-03-01"))
    assert regime_ts in (0, 1)


def test_benchmark_provider_insufficient_data():
    """Verify RuntimeError is raised on empty or short benchmark dataframe."""
    from src.utils.benchmark_provider import get_benchmark_ohlc, clear_benchmark_cache

    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        clear_benchmark_cache()
        with pytest.raises(RuntimeError) as exc_info:
            get_benchmark_ohlc(lookback_days=100)
        assert "Cannot evaluate market regime" in str(exc_info.value)


def test_vcp_screener_fails_closed_on_benchmark_error():
    """Verify vcp_screener fails closed (returns empty list) when benchmark errors."""
    from src.screening.vcp_screener import evaluate_minervini_vcp_batch
    import duckdb

    # Create dummy in-memory connection
    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE bhavcopy_daily (
            symbol VARCHAR, trade_date DATE, close_price DOUBLE,
            high_price DOUBLE, low_price DOUBLE, total_traded_qty BIGINT,
            delivery_pct DOUBLE, series VARCHAR, is_asm BOOLEAN, is_gsm BOOLEAN
        );
        CREATE TABLE positions (
            status VARCHAR, realized_pnl DOUBLE, unrealized_pnl DOUBLE, entry_price DOUBLE
        );
    """)

    with patch("src.utils.benchmark_provider.get_market_regime", side_effect=RuntimeError("Network blackout")):
        results = evaluate_minervini_vcp_batch(["TESTSYM"], mem_conn, live_prices={"TESTSYM": 100.0})
        assert results == []


def test_vcp_screener_fails_closed_when_regime_is_risk_off():
    """Verify vcp_screener halts longs (returns empty list) when market regime is Risk-Off (0)."""
    from src.screening.vcp_screener import evaluate_minervini_vcp_batch
    import duckdb

    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE bhavcopy_daily (
            symbol VARCHAR, trade_date DATE, close_price DOUBLE,
            high_price DOUBLE, low_price DOUBLE, total_traded_qty BIGINT,
            delivery_pct DOUBLE, series VARCHAR, is_asm BOOLEAN, is_gsm BOOLEAN
        );
        CREATE TABLE positions (
            status VARCHAR, realized_pnl DOUBLE, unrealized_pnl DOUBLE, entry_price DOUBLE
        );
    """)

    with patch("src.utils.benchmark_provider.get_market_regime", return_value=0):
        results = evaluate_minervini_vcp_batch(["TESTSYM"], mem_conn, live_prices={"TESTSYM": 100.0})
        assert results == []


def test_portfolio_state_without_entry_price_column():
    """Verify get_portfolio_state dynamically falls back to current_ltp * quantity when entry_price is absent."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    # Schema intentionally omits entry_price column
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            current_ltp DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        CREATE TABLE circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            high_water_mark DOUBLE,
            monthly_peak_equity DOUBLE
        );
        INSERT INTO circuit_breaker_state VALUES (1, 1000000.0, 1000000.0);
        INSERT INTO positions VALUES ('pos_open', 'INFY', 1500.0, 10, 'OPEN', 0.0, 500.0, NULL);
    """)

    state = get_portfolio_state(conn=mem_conn)
    # open_positions_value = 1500.0 * 10 = 15000.0
    assert state["open_positions_value"] == 15000.0
    assert state["core_equity"] == 1000500.0
    assert state["available_cash"] == 1000500.0 - 15000.0


def test_portfolio_state_with_null_ltp_fallback_to_entry_price():
    """Verify get_portfolio_state falls back to entry_price when current_ltp is NULL for an open position."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            current_ltp DOUBLE,
            entry_price DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        CREATE TABLE circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            high_water_mark DOUBLE,
            monthly_peak_equity DOUBLE
        );
        INSERT INTO circuit_breaker_state VALUES (1, 1000000.0, 1000000.0);
        INSERT INTO positions VALUES ('pos_open', 'INFY', NULL, 1200.0, 10, 'OPEN', 0.0, 0.0, NULL);
    """)

    state = get_portfolio_state(conn=mem_conn)
    # open_positions_value = 1200.0 * 10 = 12000.0
    assert state["open_positions_value"] == 12000.0
    assert state["core_equity"] == 1000000.0
    assert state["available_cash"] == 1000000.0 - 12000.0


def test_portfolio_state_without_current_ltp_column():
    """Verify get_portfolio_state dynamically uses entry_price when current_ltp column is absent."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    # Schema intentionally omits current_ltp column
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            entry_price DOUBLE,
            quantity INTEGER,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        CREATE TABLE circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            high_water_mark DOUBLE,
            monthly_peak_equity DOUBLE
        );
        INSERT INTO circuit_breaker_state VALUES (1, 1000000.0, 1000000.0);
        INSERT INTO positions VALUES ('pos_open', 'INFY', 850.0, 20, 'OPEN', 0.0, 0.0, NULL);
    """)

    state = get_portfolio_state(conn=mem_conn)
    # open_positions_value = 850.0 * 20 = 17000.0
    assert state["open_positions_value"] == 17000.0
    assert state["core_equity"] == 1000000.0
    assert state["available_cash"] == 1000000.0 - 17000.0


def test_portfolio_state_missing_quantity_column_graceful_fallback():
    """Verify get_portfolio_state gracefully defaults open_positions_value to 0.0 when quantity column is missing."""
    import duckdb
    from src.portfolio.state import get_portfolio_state

    mem_conn = duckdb.connect(":memory:")
    # Schema intentionally omits quantity column
    mem_conn.execute("""
        CREATE TABLE positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            entry_price DOUBLE,
            status VARCHAR,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            exit_date DATE
        );
        CREATE TABLE circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            high_water_mark DOUBLE,
            monthly_peak_equity DOUBLE
        );
        INSERT INTO circuit_breaker_state VALUES (1, 1000000.0, 1000000.0);
        INSERT INTO positions VALUES ('pos_open', 'INFY', 850.0, 'OPEN', 0.0, 0.0, NULL);
    """)

    state = get_portfolio_state(conn=mem_conn)
    assert state["open_positions_value"] == 0.0
    assert state["core_equity"] == 1000000.0
    assert state["available_cash"] == 1000000.0



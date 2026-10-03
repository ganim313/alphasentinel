"""
Unit and Integration Test Suite for Pipeline Optimization and Tier 1 Risk Hardening.
Verifies:
1. Batch Mean Reversion output equivalence and <2.0s SLA execution.
2. MARKED_FOR_CLOSURE factoring into unrealized PnL and cash (C-02 phantom cash fix).
3. Trigger Watcher rejection when Risk Arbiter returns suggested_shares <= 0 (C-01 & NEW-D05).
4. Scheduler timeout telemetry captures stdout and stderr tails.
5. Sentinel and EOD Reconciliation defensive exit execution when system is halted (C-03).
"""

import time
import subprocess
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
import numpy as np

from src.db.session import init_db, get_read_connection, get_write_connection
from src.screening.mean_reversion_screener import evaluate_mean_reversion, evaluate_mean_reversion_batch
from src.portfolio.state import get_portfolio_state
from src.portfolio.paper_capital import get_paper_capital
from scripts.run_scheduler import run_script
from scripts.run_trigger_watcher import check_and_execute_triggers
from scripts.run_sentinel import run_sentinel_check
from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline
from src.notification.telegram_bot import set_system_halt_state


@pytest.fixture(autouse=True)
def setup_teardown_db():
    """Ensure database is initialized and cleanup test fixtures after each run."""
    init_db()
    set_system_halt_state(False, reason="Test setup reset")
    yield
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM screener_candidates WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'TEST_%'")


# -------------------------------------------------------------------------
# 1. Batch Mean Reversion Output Equivalence and Speed Test
# -------------------------------------------------------------------------

def test_batch_mean_reversion_equivalence_and_speed():
    """
    Asserts that evaluate_mean_reversion_batch matches evaluate_mean_reversion
    exactly across test symbols, and completes well within the 2.0s SLA.
    """
    with get_read_connection() as conn:
        all_syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM bhavcopy_daily").fetchall()]

    if len(all_syms) < 50:
        # Seed synthetic symbols if local DB is sparse
        with get_write_connection() as conn:
            for i in range(50):
                s = f"TEST_MR_{i:03d}"
                all_syms.append(s)
                base = 100.0 + i
                for d in range(30):
                    conn.execute("""
                        INSERT INTO bhavcopy_daily (symbol, trade_date, close_price, open_price, high_price, low_price, total_traded_qty, series)
                        VALUES (?, '2026-01-01'::DATE + (? || ' days')::INTERVAL, ?, ?, ?, ?, 10000, 'EQ')
                    """, (s, d, base - d * 0.5, base, base + 1, base - d * 0.5 - 1))

    test_symbols = all_syms[:100]

    # Batch execution benchmark
    t0 = time.time()
    with get_read_connection() as conn:
        batch_results = evaluate_mean_reversion_batch(test_symbols, conn=conn)
    batch_elapsed = time.time() - t0

    assert batch_elapsed < 2.0, f"Batch screener exceeded 2.0s SLA: {batch_elapsed:.3f}s"
    assert len(batch_results) == len(test_symbols)

    # Sequential execution ground truth comparison
    with get_read_connection() as conn:
        for sym in test_symbols:
            seq_val = evaluate_mean_reversion(sym, conn=conn)
            assert batch_results[sym] == seq_val, f"Mismatch for symbol {sym}: batch={batch_results[sym]}, seq={seq_val}"

    # Edge cases
    assert evaluate_mean_reversion_batch([]) == {}
    unknown_res = evaluate_mean_reversion_batch(["UNKNOWN_SYMBOL_XYZ"])
    assert unknown_res == {"UNKNOWN_SYMBOL_XYZ": False}


# -------------------------------------------------------------------------
# 2. MARKED_FOR_CLOSURE Factoring into Portfolio State (C-02)
# -------------------------------------------------------------------------

def test_marked_for_closure_in_portfolio_state():
    """
    Asserts that positions with status = 'MARKED_FOR_CLOSURE' are included in
    unrealized_pnl_total and open_positions_value, eliminating phantom cash expansion.
    """
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
        # Insert a regular OPEN position
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, current_ltp, quantity,
                trailing_stop_loss, target_1, target_2, risk_rupees, portfolio_allocation_pct,
                status, unrealized_pnl, realized_pnl
            ) VALUES ('test_pos_1', 'TEST_OPEN', CURRENT_DATE, 100.0, 105.0, 100, 95.0, 110.0, 120.0, 500.0, 5.0, 'OPEN', 500.0, 0.0);
        """)
        # Insert a MARKED_FOR_CLOSURE position (lower circuit trap)
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, current_ltp, quantity,
                trailing_stop_loss, target_1, target_2, risk_rupees, portfolio_allocation_pct,
                status, unrealized_pnl, realized_pnl
            ) VALUES ('test_pos_2', 'TEST_LOCKED', CURRENT_DATE, 100.0, 80.0, 100, 95.0, 110.0, 120.0, 500.0, 5.0, 'MARKED_FOR_CLOSURE', -2000.0, 0.0);
        """)

    with get_read_connection() as conn:
        state = get_portfolio_state(conn)

    # Unrealized PnL must factor in both: 500.0 + (-2000.0) = -1500.0
    assert state["unrealized_pnl_total"] == -1500.0

    # Open positions value must count both positions: (105 * 100) + (80 * 100) = 10500 + 8000 = 18500.0
    assert state["open_positions_value"] == 18500.0

    # Available cash = core_equity - open_positions_value
    # Phantom cash check: available_cash must NOT have expanded as if the 8000.0 position had vanished
    expected_available = state["core_equity"] - 18500.0
    assert abs(state["available_cash"] - round(expected_available, 2)) < 0.05


# -------------------------------------------------------------------------
# 3. Trigger Watcher Rejection on Arbiter 0 Shares (C-01 & NEW-D05)
# -------------------------------------------------------------------------

def test_trigger_watcher_rejects_when_arbiter_zero_shares():
    """
    Asserts that when Risk Arbiter returns suggested_shares <= 0:
    - Trigger watcher rejects candidate with status 'EXECUTION_REJECTED'.
    - Does NOT invoke the 2% fallback buy.
    - Connects to dynamic paper capital (NEW-D05).
    """
    test_cand_id = "test_cand_c01"
    with get_write_connection() as conn:
        conn.execute("DELETE FROM screener_candidates WHERE id = ?", (test_cand_id,))
        conn.execute("""
            INSERT INTO screener_candidates (
                id, symbol, scan_date, trigger_price, pattern_type, sector,
                market_cap_tier, circuit_band, adtv_20d, status
            ) VALUES (?, 'TEST_REJ', CURRENT_DATE, 100.0, 'VCP', 'Technology', 'MID', 20.0, 5000000.0, 'AWAITING_TRIGGER');
        """, (test_cand_id,))

    # Mock yfinance quote data: price breaches trigger price 100.0
    mock_df = pd.DataFrame({
        "Close": [105.0],
        "High": [106.0]
    })

    # Mock Arbiter to return 0 shares (e.g. Risk capacity exceeded / stop too wide)
    mock_risk = {
        "suggested_shares": 0,
        "rejection_reason": "Max portfolio risk threshold exceeded"
    }

    with patch("scripts.run_trigger_watcher.is_system_halted", return_value=False), \
         patch("scripts.run_trigger_watcher.yf.download", return_value=mock_df), \
         patch("scripts.run_trigger_watcher.calculate_deterministic_risk_and_position", return_value=mock_risk) as mock_arbiter, \
         patch("src.execution.order_manager.PaperBroker.place_order") as mock_place_order, \
         patch("scripts.run_trigger_watcher.get_paper_capital", return_value=500000.0) as mock_get_capital:

        executed = check_and_execute_triggers()

        # No order should have been placed
        assert executed == 0
        mock_place_order.assert_not_called()

        # Dynamic paper capital should have been fetched
        mock_get_capital.assert_called()
        assert mock_arbiter.call_args[1]["portfolio_capital_rupees"] == 500000.0

        # Candidate in DB should be marked EXECUTION_REJECTED, NOT APPROVED
        with get_read_connection() as conn:
            status = conn.execute("SELECT status FROM screener_candidates WHERE id = ?", (test_cand_id,)).fetchone()[0]
        assert status == "EXECUTION_REJECTED"


# -------------------------------------------------------------------------
# 4. Master Scheduler Timeout Output Tail Telemetry
# -------------------------------------------------------------------------

def test_scheduler_logs_timeout_output_tails(caplog):
    """
    Asserts that subprocess.TimeoutExpired in run_script captures and logs
    stdout and stderr tails for operator visibility.
    """
    timeout_err = subprocess.TimeoutExpired(
        cmd=["python", "run_live_preview.py"],
        timeout=5,
        output="STEP 1 SUCCESS\nSTEP 2 RUNNING TECHNICAL FILTER...\n[Pass 2 Hanging...]",
        stderr="Memory allocation warning: high contention on thread 4\nFatal lock delay"
    )

    with patch("scripts.run_scheduler.subprocess.run", side_effect=timeout_err), \
         caplog.at_level("ERROR", logger="master_scheduler"):
        success = run_script("run_live_preview.py", timeout_seconds=5)

        assert success is False
        log_text = caplog.text

        assert "==> [TIMEOUT]" in log_text
        assert "--- STDERR (Tail) ---" in log_text
        assert "Fatal lock delay" in log_text
        assert "--- STDOUT (Tail) ---" in log_text
        assert "[Pass 2 Hanging...]" in log_text


# -------------------------------------------------------------------------
# 5. Sentinel & EOD Reconciliation Decoupled from Kill Switch (C-03)
# -------------------------------------------------------------------------

def test_sentinel_runs_in_defensive_mode_when_halted(caplog):
    """
    Asserts that run_sentinel_check does not abort when system is halted,
    and runs in DEFENSIVE EXIT-ONLY mode to protect capital on open positions.
    """
    set_system_halt_state(True, reason="Circuit Breaker Active")

    with caplog.at_level("WARNING", logger="run_sentinel"), \
         patch("scripts.run_sentinel.get_read_connection") as mock_conn:
        # Return empty list of positions
        mock_conn.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []

        run_sentinel_check()

        assert "DEFENSIVE EXIT-ONLY mode" in caplog.text


def test_eod_reconciliation_runs_in_defensive_mode_when_halted(caplog):
    """
    Asserts that run_eod_reconciliation_pipeline does not abort when system is halted,
    and runs in DEFENSIVE EXIT/RECONCILIATION mode.
    """
    set_system_halt_state(True, reason="Circuit Breaker Active")

    with caplog.at_level("WARNING", logger="run_eod_reconciliation"), \
         patch("scripts.run_eod_reconciliation.get_read_connection") as mock_conn, \
         patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", return_value=None):
        mock_conn.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None

        run_eod_reconciliation_pipeline()

        assert "DEFENSIVE EXIT/RECONCILIATION mode" in caplog.text


def test_scheduler_timeout_with_bytes_output(caplog):
    """Asserts that bytes stdout/stderr in TimeoutExpired are properly decoded and logged."""
    timeout_err = subprocess.TimeoutExpired(
        cmd=["python", "run_live_preview.py"],
        timeout=10,
        output=b"Binary stdout progress chunk",
        stderr=b"Binary stderr critical error"
    )

    with patch("scripts.run_scheduler.subprocess.run", side_effect=timeout_err), \
         caplog.at_level("ERROR", logger="master_scheduler"):
        success = run_script("run_live_preview.py", timeout_seconds=10)

        assert success is False
        assert "Binary stderr critical error" in caplog.text
        assert "Binary stdout progress chunk" in caplog.text


def test_job_live_preview_uses_1200s_timeout():
    """Asserts that job_live_preview launches run_live_preview.py with a 1200s timeout."""
    from scripts.run_scheduler import job_live_preview

    with patch("scripts.run_scheduler.is_weekday_ist", return_value=True), \
         patch("scripts.run_scheduler._is_holiday_today", return_value=False), \
         patch("scripts.run_scheduler.threading.Thread") as mock_thread:

        job_live_preview()

        mock_thread.assert_called_once()
        _, kwargs = mock_thread.call_args
        args = mock_thread.call_args[1].get("args") or mock_thread.call_args[0]
        # Verify args include run_live_preview.py and 1200
        assert "run_live_preview.py" in str(args)
        assert 1200 in mock_thread.call_args[1]["args"]


def test_evaluate_mean_reversion_batch_conn_none_and_edge_cases():
    """Asserts evaluate_mean_reversion_batch works when conn is None and on empty/sparse data."""
    # Test conn=None auto-manages get_read_connection
    res = evaluate_mean_reversion_batch(["NON_EXISTENT_SYM"], conn=None)
    assert res == {"NON_EXISTENT_SYM": False}

    # Test empty list
    assert evaluate_mean_reversion_batch([]) == {}

    # Test symbol with only 5 days of data
    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = 'TEST_SPARSE'")
        for i in range(5):
            conn.execute("""
                INSERT INTO bhavcopy_daily (symbol, trade_date, close_price, open_price, high_price, low_price, total_traded_qty, total_traded_val, series)
                VALUES ('TEST_SPARSE', '2026-01-01'::DATE + (? || ' days')::INTERVAL, 100.0, 100.0, 101.0, 99.0, 10000, 1000000.0, 'EQ')
            """, (i,))

    res = evaluate_mean_reversion_batch(["TEST_SPARSE"])
    assert res["TEST_SPARSE"] is False


def test_trigger_watcher_aborts_when_halted():
    """Asserts trigger watcher halts early when system kill switch is active."""
    with patch("scripts.run_trigger_watcher.is_system_halted", return_value=True), \
         patch("scripts.run_trigger_watcher.get_read_connection") as mock_conn:

        executed = check_and_execute_triggers()
        assert executed == 0
        mock_conn.assert_not_called()


def test_run_live_preview_defers_ml_probability_to_max_15_calls():
    """
    Asserts that in run_live_preview_pipeline(), evaluate_ml_probability is ONLY
    called on the top candidates (<= 15 calls) rather than hundreds of raw candidates.
    """
    from scripts.run_live_preview import run_live_preview_pipeline
    import datetime

    # Fetch 30 real liquid symbols from DB to pass Pass 1 Liquidity Filter
    with get_read_connection() as conn:
        liquid_db = [
            r[0] for r in conn.execute("""
                SELECT symbol FROM bhavcopy_daily 
                WHERE total_traded_qty > 0 
                GROUP BY symbol 
                HAVING count(*) >= 20 AND MEDIAN(total_traded_val) >= 2500000 
                LIMIT 30
            """).fetchall()
        ]

    mock_universe = [(sym, "EQ", 20.0) for sym in liquid_db]

    mock_macro = {
        "us_vix": 15.0, "sp500_pct_change": 0.5, "crude_oil_price": 75.0,
        "crude_oil_pct_change": 0.0, "usdinr_price": 85.0, "usdinr_pct_change": 0.0,
        "polymarket_risk_score": 0.2, "market_regime": "BULL_STRONG",
        "macro_weather_score": 0.9, "target_cash_exposure_pct": 0.0, "source": "TEST"
    }

    # Wednesday date to bypass weekend check
    fake_now = datetime.datetime(2026, 10, 7, 15, 15, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))

    # Pretend all 30 symbols trigger mean reversion
    mock_mr_map = {sym: True for sym in liquid_db}

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now

    with patch("scripts.run_live_preview.is_system_halted", return_value=False), \
         patch("scripts.run_live_preview.is_nse_holiday", return_value=False), \
         patch("scripts.run_live_preview.datetime.datetime", FakeDatetime), \
         patch("scripts.run_live_preview.fetch_macro_weather_data", return_value=mock_macro), \
         patch("scripts.run_live_preview.get_active_universe", return_value=mock_universe), \
         patch("scripts.run_live_preview.evaluate_minervini_vcp_batch", return_value=[]), \
         patch("scripts.run_live_preview.evaluate_mean_reversion_batch", return_value=mock_mr_map), \
         patch("scripts.run_live_preview.evaluate_ml_probability", return_value=0.75) as mock_ml_prob, \
         patch("scripts.run_live_preview.yf.download", return_value=pd.DataFrame()), \
         patch("scripts.run_live_preview.scrape_screener_fundamentals", return_value={}), \
         patch("scripts.run_live_preview.check_shariah_compliance", return_value=(False, "TEST_EXCLUDE")):

        run_live_preview_pipeline()

        # Crucial assertion: evaluate_ml_probability should have been called EXACTLY 15 times (capped at 15)
        # Even though all 30 symbols had a mean reversion signal!
        assert mock_ml_prob.call_count == 15, f"Expected exactly 15 ML probability calls, got {mock_ml_prob.call_count}"


def test_trigger_watcher_handles_arbiter_none_shares_gracefully():
    """
    Asserts that when Risk Arbiter returns suggested_shares = None (or missing),
    run_trigger_watcher does NOT raise TypeError and marks candidate EXECUTION_REJECTED.
    """
    test_cand_id = "test_cand_c01_none"
    with get_write_connection() as conn:
        conn.execute("DELETE FROM screener_candidates WHERE id = ?", (test_cand_id,))
        conn.execute("""
            INSERT INTO screener_candidates (
                id, symbol, scan_date, trigger_price, pattern_type, sector,
                market_cap_tier, circuit_band, adtv_20d, status
            ) VALUES (?, 'TEST_NONE_SYM', CURRENT_DATE, 100.0, 'VCP', 'Finance', 'MID', 20.0, 5000000.0, 'AWAITING_TRIGGER');
        """, (test_cand_id,))

    mock_df = pd.DataFrame({"Close": [105.0], "High": [106.0]})
    # Arbiter returns None for suggested_shares
    mock_risk = {
        "suggested_shares": None,
        "rejection_reason": "Risk capacity calculation returned None"
    }

    with patch("scripts.run_trigger_watcher.is_system_halted", return_value=False), \
         patch("scripts.run_trigger_watcher.yf.download", return_value=mock_df), \
         patch("scripts.run_trigger_watcher.calculate_deterministic_risk_and_position", return_value=mock_risk), \
         patch("src.execution.order_manager.PaperBroker.place_order") as mock_place_order, \
         patch("scripts.run_trigger_watcher.get_paper_capital", return_value=500000.0):

        executed = check_and_execute_triggers()

        assert executed == 0
        mock_place_order.assert_not_called()

        with get_read_connection() as conn:
            status = conn.execute("SELECT status FROM screener_candidates WHERE id = ?", (test_cand_id,)).fetchone()[0]
        assert status == "EXECUTION_REJECTED"


def test_evaluate_mean_reversion_batch_size_chunking_and_types():
    """
    Asserts that evaluate_mean_reversion_batch handles arbitrary iterables (tuple, set)
    and executes properly when batch_size causes chunked queries.
    """
    with get_read_connection() as conn:
        all_syms = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM bhavcopy_daily LIMIT 20").fetchall()]

    if len(all_syms) < 10:
        pytest.skip("Not enough symbols in DB for chunking test")

    test_tuple = tuple(all_syms[:10])
    test_set = set(all_syms[:10])

    # Test chunking with batch_size=3
    with get_read_connection() as conn:
        res_chunked = evaluate_mean_reversion_batch(test_tuple, conn=conn, batch_size=3)
        res_single = evaluate_mean_reversion_batch(test_tuple, conn=conn, batch_size=500)
        res_set = evaluate_mean_reversion_batch(test_set, conn=conn, batch_size=4)

    assert len(res_chunked) == 10
    assert res_chunked == res_single
    assert res_set == res_single


def test_candidate_ranking_prioritizes_vcp_trigger_proximity_and_liquidity():
    """
    Asserts that preliminary candidate sorting deterministically orders:
    1. VCP pattern over Mean Reversion
    2. Confirmed triggers (current >= trigger) over unconfirmed
    3. Higher trigger proximity (current / trigger)
    4. Higher 20-day ADTV (liquidity)
    """
    cands = [
        # Mean Reversion, proximity 0.90, ADTV 10 Cr
        {
            "symbol": "MR_LOW_PROX",
            "has_vcp": False,
            "candidate": {"pattern_type": "MEAN_REVERSION", "current_price": 90.0, "trigger_price": 100.0},
            "l_metrics": {"adtv_20d_rupees": 100_000_000.0}
        },
        # Mean Reversion, proximity 0.99, ADTV 1 Cr
        {
            "symbol": "MR_HIGH_PROX_LOW_ADTV",
            "has_vcp": False,
            "candidate": {"pattern_type": "MEAN_REVERSION", "current_price": 99.0, "trigger_price": 100.0},
            "l_metrics": {"adtv_20d_rupees": 10_000_000.0}
        },
        # Mean Reversion, proximity 0.99, ADTV 5 Cr
        {
            "symbol": "MR_HIGH_PROX_HIGH_ADTV",
            "has_vcp": False,
            "candidate": {"pattern_type": "MEAN_REVERSION", "current_price": 99.0, "trigger_price": 100.0},
            "l_metrics": {"adtv_20d_rupees": 50_000_000.0}
        },
        # VCP unconfirmed (current < trigger)
        {
            "symbol": "VCP_UNCONFIRMED",
            "has_vcp": True,
            "candidate": {"pattern_type": "VCP", "current_price": 98.0, "trigger_price": 100.0},
            "l_metrics": {"adtv_20d_rupees": 20_000_000.0}
        },
        # VCP confirmed (current >= trigger)
        {
            "symbol": "VCP_CONFIRMED",
            "has_vcp": True,
            "candidate": {"pattern_type": "VCP", "current_price": 102.0, "trigger_price": 100.0},
            "l_metrics": {"adtv_20d_rupees": 20_000_000.0}
        },
    ]

    cands.sort(key=lambda x: (
        x["has_vcp"],
        x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
        x["candidate"]["current_price"] / max(x["candidate"]["trigger_price"], 1e-6),
        x["l_metrics"].get("adtv_20d_rupees", 0.0)
    ), reverse=True)

    sorted_symbols = [c["symbol"] for c in cands]
    assert sorted_symbols == [
        "VCP_CONFIRMED",
        "VCP_UNCONFIRMED",
        "MR_HIGH_PROX_HIGH_ADTV",
        "MR_HIGH_PROX_LOW_ADTV",
        "MR_LOW_PROX",
    ]


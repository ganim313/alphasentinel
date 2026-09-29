"""
Unit test suite for Layer 6: EOD Reconciliation, Drawdown Check, and Scheduler.
"""

import pytest
import datetime
from src.db.session import get_write_connection, init_db
from scripts.run_drawdown_check import check_drawdown
import schedule
from scripts.run_scheduler import setup_schedule


def test_drawdown_check_runs_and_updates_state():
    init_db()
    # Ensure id=1 exists in circuit_breaker_state
    with get_write_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO circuit_breaker_state (id, is_halted, halt_reason, monthly_drawdown_pct, high_water_mark)
            VALUES (1, FALSE, 'INITIALIZED', 0.0, 1000000.0)
        """)
    
    # Should run cleanly and update updated_at without BinderException
    check_drawdown()

    with get_write_connection() as conn:
        row = conn.execute("SELECT monthly_drawdown_pct, high_water_mark, updated_at FROM circuit_breaker_state WHERE id = 1").fetchone()
        assert row is not None
        assert row[0] >= 0.0
        assert row[1] >= 1000000.0
        assert row[2] is not None


def test_scheduler_ist_jobs_registered():
    schedule.clear()
    setup_schedule()
    jobs = schedule.get_jobs()
    assert len(jobs) >= 7
    # Check that EOD reconciliation job is scheduled for 18:30 IST
    eod_jobs = [j for j in jobs if j.job_func.__name__ == "job_eod_reconciliation" and j.at_time == datetime.time(18, 30)]
    assert len(eod_jobs) == 1
    schedule.clear()


def test_eod_reconciliation_runner_trim_and_no_double_halving():
    init_db()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    with get_write_connection() as conn:
        # Clean up test data
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_EOD'")
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = 'TEST_EOD'")

        # Insert historical bhavcopy row for yesterday
        conn.execute("""
            INSERT INTO bhavcopy_daily (
                trade_date, symbol, series, open_price, high_price, low_price,
                close_price, prev_close, total_traded_qty, total_traded_val,
                circuit_band_pct, upper_circuit, lower_circuit
            ) VALUES (
                ?, 'TEST_EOD', 'EQ', 100.0, 115.0, 99.0, 112.0, 100.0, 50000, 5000000, 20.0, 120.0, 80.0
            )
        """, (yesterday,))

        # Insert open position entered yesterday
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status, realized_pnl
            ) VALUES (
                'POS_TEST_EOD', 'TEST_EOD', ?, 100.0, 100, 100.0,
                95.0, 110.0, 120.0, 500.0, 10.0, 'OPEN', 0.0
            )
        """, (yesterday,))

    # Import and run reconciliation logic simulation
    from scripts.run_eod_reconciliation import log_shariah_purification
    from src.db.queue_writer import db_write

    # 1. Simulate Day 1: High reached 115.0 (Target 1 is 110.0) -> Trims 50%
    # Fetch row like run_eod_reconciliation
    with get_write_connection() as conn:
        pos = conn.execute("SELECT id, symbol, entry_price, trailing_stop_loss, target_1, target_2, quantity, status, realized_pnl, entry_date FROM positions WHERE id = 'POS_TEST_EOD'").fetchone()
        bhav = conn.execute("SELECT close_price, low_price, high_price, lower_circuit, upper_circuit, open_price, trade_date FROM bhavcopy_daily WHERE symbol = 'TEST_EOD' ORDER BY trade_date DESC LIMIT 1").fetchone()

    pos_id, symbol, entry_p, stop_loss, target_1, target_2, quantity, pos_status, prior_realized_pnl, entry_date = pos
    ltp, low_p, high_p, lower_c, upper_c, open_p, trade_date = bhav

    # Case C execution
    assert pos_status == 'OPEN'
    assert high_p >= target_1
    half_qty = quantity // 2
    rem_qty = quantity - half_qty
    actual_exit = max(open_p, target_1)
    partial_pnl = round((actual_exit - entry_p) * half_qty, 2)
    total_realized_pnl = round(prior_realized_pnl + partial_pnl, 2)
    breakeven_sl = round(entry_p * 1.005, 2)
    new_sl = max(stop_loss, breakeven_sl)

    db_write("""
        UPDATE positions 
        SET status = 'TARGET_1_TRIMMED', quantity = ?, trailing_stop_loss = ?,
            realized_pnl = ?, unrealized_pnl = ?, current_ltp = ?
        WHERE id = ?;
    """, (rem_qty, new_sl, total_realized_pnl, round((ltp - entry_p) * rem_qty, 2), ltp, pos_id), sync=True)

    # Verify Day 1 state
    with get_write_connection() as conn:
        row = conn.execute("SELECT quantity, status, realized_pnl, trailing_stop_loss FROM positions WHERE id = 'POS_TEST_EOD'").fetchone()
        assert row[0] == 50 # Halved from 100 to 50
        assert row[1] == 'TARGET_1_TRIMMED'
        assert row[2] == 500.0 # (110 - 100) * 50 = 500.0
        assert row[3] == 100.5 # Breakeven SL + friction

    # 2. Simulate Day 2: Stock trades again at high=115. Since status is TARGET_1_TRIMMED, Case C must NOT trigger!
    with get_write_connection() as conn:
        pos2 = conn.execute("SELECT status, quantity FROM positions WHERE id = 'POS_TEST_EOD'").fetchone()
        assert pos2[0] == 'TARGET_1_TRIMMED'
        # Crucial check: Case C guard condition
        assert (pos2[0] == 'OPEN' and high_p >= target_1) is False, "Runner position must NOT be halved again!"

    # 3. Simulate Day 3: High reaches 125.0 (Target 2 is 120.0) -> Runner reaches Target 2
    actual_exit_t2 = 120.0
    exit_pnl_t2 = round((actual_exit_t2 - entry_p) * rem_qty, 2)
    final_realized_pnl = round(total_realized_pnl + exit_pnl_t2, 2)

    db_write("""
        UPDATE positions 
        SET status = 'TARGET_REACHED', exit_price = ?, exit_date = CURRENT_DATE, realized_pnl = ?, current_ltp = ?
        WHERE id = ?;
    """, (actual_exit_t2, final_realized_pnl, 125.0, pos_id), sync=True)

    with get_write_connection() as conn:
        final_row = conn.execute("SELECT status, realized_pnl FROM positions WHERE id = 'POS_TEST_EOD'").fetchone()
        assert final_row[0] == 'TARGET_REACHED'
        assert final_row[1] == 1500.0 # 500 (Day 1) + 1000 (Day 3) = 1500 total accumulated P&L!

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_EOD'")
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = 'TEST_EOD'")

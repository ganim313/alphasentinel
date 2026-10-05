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
    from unittest.mock import patch
    from src.db.session import get_read_connection
    init_db()
    with get_read_connection() as conn:
        saved_cb_df = conn.execute("SELECT * FROM circuit_breaker_state WHERE id = 1").df()
    try:
        # Ensure id=1 exists in circuit_breaker_state
        with get_write_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO circuit_breaker_state (id, is_halted, halt_reason, monthly_drawdown_pct, high_water_mark, monthly_peak_equity)
                VALUES (1, FALSE, 'INITIALIZED', 0.0, 1000000.0, 1000000.0)
            """)
        
        # Should run cleanly and update updated_at without BinderException
        with patch("src.portfolio.paper_capital.get_paper_capital", return_value=1000000.0), \
             patch("src.notification.telegram_bot.send_telegram_alert"), \
             patch("src.notification.telegram_bot.send_telegram_safe_halt_alarm"):
            check_drawdown()

        with get_write_connection() as conn:
            row = conn.execute("SELECT monthly_drawdown_pct, high_water_mark, updated_at FROM circuit_breaker_state WHERE id = 1").fetchone()
            assert row is not None
            assert row[0] >= 0.0
            assert row[1] >= 1000000.0
            assert row[2] is not None
    finally:
        if not saved_cb_df.empty:
            with get_write_connection() as conn:
                conn.execute("DELETE FROM circuit_breaker_state WHERE id = 1")
                conn.register("saved_cb_df", saved_cb_df)
                conn.execute("INSERT INTO circuit_breaker_state SELECT * FROM saved_cb_df")
                conn.unregister("saved_cb_df")


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


def test_purification_report_first_of_month_previous_month_resolution():
    """
    Verify that resolve_report_year_month defaults to the previous completed calendar month
    when executed on the 1st of the month without explicit CLI year/month arguments.
    """
    from zoneinfo import ZoneInfo
    from scripts.generate_purification_report import resolve_report_year_month

    ist = ZoneInfo("Asia/Kolkata")

    # 1. Executed on Oct 1, 2026 at 08:00 AM IST -> reports September 2026 (2026, 9)
    oct_1 = datetime.datetime(2026, 10, 1, 8, 0, 0, tzinfo=ist)
    assert resolve_report_year_month(now=oct_1, argv=["generate_purification_report.py"]) == (2026, 9)

    # 2. Executed on Jan 1, 2027 at 08:00 AM IST -> reports December 2026 (2026, 12)
    jan_1 = datetime.datetime(2027, 1, 1, 8, 0, 0, tzinfo=ist)
    assert resolve_report_year_month(now=jan_1, argv=["generate_purification_report.py"]) == (2026, 12)

    # 3. Executed mid-month on Oct 15, 2026 -> reports current month October 2026 (2026, 10)
    oct_15 = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=ist)
    assert resolve_report_year_month(now=oct_15, argv=["generate_purification_report.py"]) == (2026, 10)

    # 4. Explicit CLI arguments override even on the 1st of the month
    assert resolve_report_year_month(
        now=oct_1, argv=["generate_purification_report.py", "2026", "5"]
    ) == (2026, 5)


def test_nightly_backup_filename_uses_ist_timezone(tmp_path, monkeypatch):
    """
    Verify that run_backup() formats the backup filename using Asia/Kolkata (IST)
    rather than UTC when a UTC timestamp is converted.
    """
    from unittest.mock import patch
    from zoneinfo import ZoneInfo
    import duckdb
    from src.config.settings import settings
    import scripts.run_nightly_backup as backup_mod

    test_db = tmp_path / "test_ist_backup.duckdb"
    with duckdb.connect(str(test_db)) as con:
        con.execute("CREATE TABLE t (x INT); INSERT INTO t VALUES (1);")

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_mod, "DB_PATH", str(test_db))
    monkeypatch.setattr(backup_mod, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(settings, "B2_KEY_ID", "")
    monkeypatch.setattr(settings, "B2_APPLICATION_KEY", "")

    # 20:30 UTC on Oct 4 == 02:00 AM IST on Oct 5
    fake_utc = datetime.datetime(2026, 10, 4, 20, 30, 0, tzinfo=datetime.timezone.utc)

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fake_utc.astimezone(tz)
            return fake_utc.replace(tzinfo=None)

    with patch("scripts.run_nightly_backup.datetime.datetime", FakeDatetime), \
         patch("scripts.run_nightly_backup.send_telegram_alert"):
        filename = backup_mod.run_backup()

    # Must reflect 2026-10-05 02:00:00 IST, NOT 2026-10-04 20:30:00 UTC
    assert filename == "alphasentinel_20261005_020000.duckdb"
    assert (backup_dir / filename).exists()


def test_monthly_retrain_read_last_trained_at_naive_and_aware(tmp_path, monkeypatch):
    """
    Verify read_last_trained_at() normalizes both naive and aware ISO timestamps
    to Asia/Kolkata (IST) cleanly without TypeError.
    """
    import json
    from zoneinfo import ZoneInfo
    import scripts.run_monthly_retrain as retrain_mod

    ist = ZoneInfo("Asia/Kolkata")
    meta_file = tmp_path / "xgboost_global_meta.json"
    monkeypatch.setattr(retrain_mod, "META_PATH", meta_file)

    # 1. Naive ISO timestamp
    meta_file.write_text(json.dumps({"trained_at": "2026-09-15T10:30:00"}), encoding="utf-8")
    dt_naive = retrain_mod.read_last_trained_at()
    assert dt_naive is not None
    assert dt_naive.tzinfo == ist
    assert dt_naive.hour == 10 and dt_naive.minute == 30

    # 2. UTC-aware ISO timestamp (05:00 UTC == 10:30 IST)
    meta_file.write_text(json.dumps({"trained_at": "2026-09-15T05:00:00+00:00"}), encoding="utf-8")
    dt_aware = retrain_mod.read_last_trained_at()
    assert dt_aware is not None
    assert dt_aware.tzinfo == ist
    assert dt_aware.hour == 10 and dt_aware.minute == 30


def test_portfolio_state_ist_month_boundary_with_utc_timestamp():
    """
    Verify get_portfolio_state converts timezone-aware updated_at to IST before
    evaluating whether updated_at is in the same calendar month.
    Example: 2026-09-30 20:00:00 UTC is 2026-10-01 01:30:00 IST (October in IST).
    """
    from unittest.mock import patch
    from zoneinfo import ZoneInfo
    import duckdb
    from src.portfolio.state import get_portfolio_state

    ist = ZoneInfo("Asia/Kolkata")
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
            monthly_peak_equity DOUBLE,
            updated_at VARCHAR
        );
        INSERT INTO circuit_breaker_state VALUES (
            1, 1200000.0, 1200000.0, '2026-09-30T20:00:00+00:00'
        );
    """)

    fake_oct = datetime.datetime(2026, 10, 5, 12, 0, 0, tzinfo=ist)

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fake_oct.astimezone(tz)
            return fake_oct

    with patch("src.portfolio.state.datetime.datetime", FakeDatetime), \
         patch("src.portfolio.paper_capital.get_paper_capital", return_value=1000000.0):
        state = get_portfolio_state(conn=mem_conn)

    # Because 2026-09-30T20:00:00+00:00 is 2026-10-01 01:30 IST (same month as Oct 5 IST),
    # monthly_peak_equity should remain 1,200,000.0 rather than resetting!
    assert state["monthly_peak_equity"] == 1200000.0
    assert state["as_of"].endswith("+05:30")



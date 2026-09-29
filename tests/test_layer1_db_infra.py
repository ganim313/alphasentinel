"""
Layer 1 Forensic Regression Tests: Database, Schema, Infrastructure
"""
import datetime
import math
import pytest
from src.db.session import get_read_connection, get_write_connection, init_db
from src.db.queue_writer import db_write, db_transaction
from src.config.settings import settings, get_market_cap_tier
from src.utils.holidays import is_nse_holiday

def test_market_cap_tier_edge_cases():
    assert get_market_cap_tier(None) == 'MICRO'
    assert get_market_cap_tier(float('nan')) == 'MICRO'
    assert get_market_cap_tier(-100.0) == 'MICRO'
    assert get_market_cap_tier(500.0) == 'MICRO'
    assert get_market_cap_tier(1500.0) == 'SMALL'
    assert get_market_cap_tier(6000.0) == 'MID'
    assert get_market_cap_tier(25000.0) == 'LARGE'

def test_nse_holiday_weekends_and_dates():
    assert is_nse_holiday(datetime.date(2026, 9, 19)) is True
    assert is_nse_holiday(datetime.date(2026, 9, 20)) is True
    assert is_nse_holiday(datetime.date(2026, 1, 26)) is True
    assert is_nse_holiday(datetime.date(2026, 9, 16))  is False

def test_thread_local_write_reentrancy():
    with db_transaction() as conn1:
        db_write('SELECT 1;')
        with get_write_connection() as conn2:
            assert conn1 is conn2

def test_timezone_setting():
    with get_read_connection() as conn:
        tz = conn.execute("SELECT current_setting('TimeZone');").fetchone()[0]
        assert tz == 'Asia/Kolkata'


"""
Unit Test for DuckDB Initialization & Single-Writer Queue.
"""

import time
import pytest
from src.db.session import init_db, get_read_connection
from src.db.queue_writer import db_write


def test_db_initialization_and_queue():
    # 1. Initialize schema
    init_db()
    
    # 2. Test reading default circuit breaker state
    with get_read_connection() as conn:
        res = conn.execute("SELECT id, is_halted FROM circuit_breaker_state WHERE id = 1;").fetchone()
        assert res is not None
        assert res[0] == 1
        assert res[1] is False

    try:
        # 3. Test submitting a write query via the queue
        db_write(
            "INSERT OR REPLACE INTO screener_candidates (id, scan_date, symbol, pattern_type, trigger_price, adtv_20d, circuit_band, is_t2t, status) "
            "VALUES (?, CURRENT_DATE, ?, ?, ?, ?, ?, ?, ?);",
            ("TEST_ID_1", "TEST_STOCK", "VCP_STAGE2", 150.5, 7500000.0, 20.0, False, "PENDING"),
            sync=True
        )

        # 4. Verify data via read connection
        with get_read_connection() as conn:
            row = conn.execute("SELECT symbol, trigger_price, status FROM screener_candidates WHERE id = 'TEST_ID_1';").fetchone()
            assert row is not None
            assert row[0] == "TEST_STOCK"
            assert row[1] == 150.5
            assert row[2] == "PENDING"
            
        print("\n[PASS] DuckDB Schema and Single-Writer Queue verified successfully!")
    finally:
        db_write("DELETE FROM screener_candidates WHERE id = 'TEST_ID_1';", sync=True)


if __name__ == "__main__":
    test_db_initialization_and_queue()


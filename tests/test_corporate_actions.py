"""
Unit Tests for Corporate Actions Retroactive Adjustments & >25% Price Jump Quarantine Tripwire.
Verifies:
1. Retroactive stock split price division and quantity multiplication.
2. Unexplained price jumps > 25% trigger quarantine tripwire and record in quarantined_stocks.
3. Explained price jumps with approved corporate actions within 5 days are NOT quarantined.
4. Normal price movements (<= 25%) are NOT quarantined.
"""

from datetime import date, timedelta
import pandas as pd
import pytest
from src.db.session import init_db, get_read_connection
from src.db.queue_writer import db_write
from src.ingestion.corporate_actions import record_corporate_action, apply_pending_corporate_actions
from src.ingestion.bhavcopy import (
    ingest_bhavcopy_dataframe,
    is_stock_quarantined,
    has_approved_corporate_action,
    quarantine_symbol,
    validate_and_quarantine_bhavcopy_jumps
)


def test_stock_split_retroactive_adjustment():
    init_db()
    symbol = "TEST_SPLIT_CO"
    
    # 0. Clean up any previous test artifacts
    db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
    
    try:
        # 1. Insert pre-split historical data (Price = 1000.0, Qty = 100)
        db_write("""
            INSERT OR REPLACE INTO bhavcopy_daily (
                symbol, trade_date, series, open_price, high_price, low_price, 
                close_price, prev_close, total_traded_qty, total_traded_val, 
                delivery_qty, delivery_pct, split_multiplier
            ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0);
        """, (symbol, date(2026, 1, 10), 1000.0, 1050.0, 990.0, 1000.0, 980.0, 100, 100000.0, 50, 50.0), sync=True)

        # 2. Record a 10:1 stock split on 2026-01-15 (Ex-date)
        action_id = record_corporate_action(
            symbol=symbol,
            action_type="SPLIT",
            ex_date=date(2026, 1, 15),
            ratio_from=10.0,
            ratio_to=1.0 # multiplier = 0.1
        )

        # 3. Apply the pending corporate actions
        apply_pending_corporate_actions()

        # 4. Verify that historical price on 2026-01-10 was divided by 10 (1000.0 -> 100.0)
        # and quantity was multiplied by 10 (100 -> 1000)
        with get_read_connection() as conn:
            row = conn.execute("""
                SELECT close_price, total_traded_qty, split_multiplier 
                FROM bhavcopy_daily 
                WHERE symbol = ? AND trade_date = ?;
            """, (symbol, date(2026, 1, 10))).fetchone()
            
            assert row is not None
            assert abs(row[0] - 100.0) < 1e-4  # Adjusted close price
            assert row[1] == 1000              # Adjusted volume
            assert abs(row[2] - 0.1) < 1e-4    # Multiplier recorded

    finally:
        db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)


def test_unexplained_price_jump_triggers_quarantine_tripwire():
    """
    Test that an unexplained price jump > 25% without a matching corporate action
    automatically triggers the quarantine tripwire during Bhavcopy ingestion.
    """
    symbol = "TEST_JUMP_UNEXPLAINED"
    trade_date = date(2026, 5, 20)
    
    # Clean up test artifacts
    db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)
    
    try:
        # Construct Bhavcopy DataFrame with +35% price jump (prev_close=100.0, close=135.0)
        df = pd.DataFrame([{
            "SYMBOL": symbol,
            "SERIES": "EQ",
            "OPEN": 130.0,
            "HIGH": 140.0,
            "LOW": 128.0,
            "CLOSE": 135.0,
            "PREVCLOSE": 100.0,
            "TOTTRDQTY": 50000,
            "TOTTRDVAL": 6750000.0,
            "DELIV_QTY": 25000,
            "DELIV_PER": 50.0
        }])
        
        # Ingest Bhavcopy
        rows_ingested = ingest_bhavcopy_dataframe(df, trade_date)
        assert rows_ingested == 1
        
        # Verify symbol is quarantined
        assert is_stock_quarantined(symbol), f"Stock {symbol} should have been quarantined"
        
        # Verify details in quarantined_stocks table
        with get_read_connection() as conn:
            q_row = conn.execute("""
                SELECT symbol, trade_date, prev_close, close_price, pct_jump, reason
                FROM quarantined_stocks
                WHERE symbol = ? AND trade_date = ?;
            """, (symbol, trade_date)).fetchone()
            
            assert q_row is not None
            assert q_row[0] == symbol
            assert q_row[1] == trade_date
            assert abs(q_row[2] - 100.0) < 1e-4
            assert abs(q_row[3] - 135.0) < 1e-4
            assert abs(q_row[4] - 0.35) < 1e-4
            assert "UNEXPLAINED_PRICE_JUMP" in q_row[5]

    finally:
        db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)


def test_explained_price_jump_with_corporate_action_not_quarantined():
    """
    Test that a >25% price drop (e.g. 50% split) WITH an approved entry in corporate_actions
    is recognized as explained and NOT quarantined.
    """
    symbol = "TEST_JUMP_EXPLAINED"
    trade_date = date(2026, 6, 15)
    
    # Clean up test artifacts
    db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)
    
    try:
        # Record an approved 1:1 Bonus / Split action within 5 days
        record_corporate_action(
            symbol=symbol,
            action_type="SPLIT",
            ex_date=trade_date,
            ratio_from=2.0,
            ratio_to=1.0  # multiplier = 0.5
        )
        
        assert has_approved_corporate_action(symbol, trade_date)
        
        # Ingest Bhavcopy with 50% drop (prev_close=200.0, close=100.0 -> -50%)
        df = pd.DataFrame([{
            "SYMBOL": symbol,
            "SERIES": "EQ",
            "OPEN": 102.0,
            "HIGH": 105.0,
            "LOW": 98.0,
            "CLOSE": 100.0,
            "PREVCLOSE": 200.0,
            "TOTTRDQTY": 100000,
            "TOTTRDVAL": 10000000.0,
            "DELIV_QTY": 60000,
            "DELIV_PER": 60.0
        }])
        
        rows = ingest_bhavcopy_dataframe(df, trade_date)
        assert rows == 1
        
        # Verify symbol is NOT quarantined because corporate action explains the jump
        assert not is_stock_quarantined(symbol), f"Stock {symbol} should NOT be quarantined (has corporate action)"
        
        with get_read_connection() as conn:
            q_count = conn.execute(
                "SELECT COUNT(*) FROM quarantined_stocks WHERE symbol = ?", (symbol,)
            ).fetchone()[0]
            assert q_count == 0

    finally:
        db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)


def test_normal_price_movement_not_quarantined():
    """
    Test that a normal price movement (<= 25%) does not trigger the tripwire.
    """
    symbol = "TEST_NORMAL_MOVE"
    trade_date = date(2026, 7, 10)
    
    db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)
    
    try:
        # 5% price gain (prev_close=100.0, close=105.0)
        df = pd.DataFrame([{
            "SYMBOL": symbol,
            "SERIES": "EQ",
            "OPEN": 101.0,
            "HIGH": 106.0,
            "LOW": 100.0,
            "CLOSE": 105.0,
            "PREVCLOSE": 100.0,
            "TOTTRDQTY": 20000,
            "TOTTRDVAL": 2100000.0,
            "DELIV_QTY": 12000,
            "DELIV_PER": 60.0
        }])
        
        rows = ingest_bhavcopy_dataframe(df, trade_date)
        assert rows == 1
        
        assert not is_stock_quarantined(symbol)
        
    finally:
        db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
        db_write("DELETE FROM quarantined_stocks WHERE symbol = ?", (symbol,), sync=True)

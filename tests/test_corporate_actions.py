"""
Unit Test for Corporate Actions Retroactive Split/Bonus Adjustments.
"""

from datetime import date
import pytest
from src.db.session import init_db, get_read_connection
from src.db.queue_writer import db_write
from src.ingestion.corporate_actions import record_corporate_action, apply_pending_corporate_actions


def test_stock_split_retroactive_adjustment():
    init_db()
    symbol = "TEST_SPLIT_CO"
    
    # 0. Clean up any previous test artifacts
    db_write("DELETE FROM corporate_actions WHERE symbol = ?", (symbol,), sync=True)
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?", (symbol,), sync=True)
    
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

    print("\n[PASS] Retroactive Corporate Action Split Adjustment verified successfully!")


if __name__ == "__main__":
    test_stock_split_retroactive_adjustment()

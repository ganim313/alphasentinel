import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import sqlite3
import pandas as pd
from unittest import mock
from src.db.session import get_write_connection

@mock.patch("scripts.run_eod_reconciliation.get_read_connection")
@mock.patch("scripts.run_eod_reconciliation.db_write")
@mock.patch("scripts.run_eod_reconciliation.is_system_halted", return_value=False)
@mock.patch("scripts.run_drawdown_check.check_drawdown")
@mock.patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", return_value=None)
@mock.patch("src.ingestion.bhavcopy.ingest_bhavcopy_dataframe")
def test_eod_risk_offloader_logic(
    mock_ingest,
    mock_fetch,
    mock_check_dd,
    mock_halted,
    mock_db_write,
    mock_get_conn
):
    from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline
    
    # Mock DuckDB connection and fetchall
    mock_conn = mock.MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    
    import datetime
    today = datetime.datetime.now().date()
    
    def execute_side_effect(query, params=None):
        mock_result = mock.MagicMock()
        if "SELECT MAX(trade_date) FROM bhavcopy_daily" in query and "JOIN" not in query:
            mock_result.fetchone.return_value = [today]
        elif "SELECT p.id, p.symbol, p.entry_price" in query:
            mock_result.fetchall.return_value = [
                # 1. Normal Position
                ("POS_1", "RELIANCE", 100.0, 90.0, 120.0, 102.0, 95.0, 105.0, 80.0, 120.0, 50),
                # 2. Excessive Risk Position (ltp is 94, entry is 100 -> -6% risk. stop is 90)
                ("POS_2", "TCS", 100.0, 90.0, 120.0, 94.0, 92.0, 101.0, 80.0, 120.0, 50),
                # 3. Hit Lower Circuit Position (ltp == lower_c)
                ("POS_3", "INFY", 100.0, 80.0, 120.0, 85.0, 85.0, 95.0, 85.0, 110.0, 50),
            ]
        elif "SELECT c.id, c.symbol, c.trigger_price" in query:
            mock_result.fetchall.return_value = []
        elif "SELECT pt.trade_id, pt.symbol, pt.entry_price" in query:
            mock_result.fetchall.return_value = []
        else:
            mock_result.fetchall.return_value = []
            mock_result.fetchone.return_value = None
        return mock_result
        
    mock_conn.execute.side_effect = execute_side_effect
    
    # Run pipeline
    run_eod_reconciliation_pipeline()
    
    # Check db_write calls
    writes = [call for call in mock_db_write.call_args_list]
    
    def check_write(pos_id, substring):
        for call in writes:
            query = call[0][0]
            params = call[0][1]
            if pos_id in params and substring in query:
                return True
        return False
        
    assert check_write("POS_2", "MARKED_FOR_CLOSURE")
    assert check_write("POS_3", "MARKED_FOR_CLOSURE")
    assert not check_write("POS_1", "MARKED_FOR_CLOSURE")

if __name__ == "__main__":
    pytest.main(["-v", __file__])

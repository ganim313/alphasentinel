import datetime
import pytest
from src.ingestion.corporate_actions import record_corporate_action, apply_pending_corporate_actions
from src.ingestion.tradingview import get_tradingview_technical_ratings
from src.ingestion.macro_feeds import fetch_macro_weather_data
from src.ingestion.fyers_client import fyers_client
from src.db.session import get_read_connection
from src.db.queue_writer import db_write, db_transaction

def test_corporate_action_math():
    today = datetime.date.today()
    
    # 1:10 split (1 old -> 10 new)
    id1 = record_corporate_action('TEST_SPLIT', 'SPLIT', today, 1.0, 10.0)
    with get_read_connection() as conn:
        m1 = conn.execute('SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?', (id1,)).fetchone()[0]
        assert round(m1, 4) == 0.1000
    
    # 5:1 reverse split (5 old -> 1 new)
    id2 = record_corporate_action('TEST_REV_SPLIT', 'SPLIT', today, 5.0, 1.0)
    with get_read_connection() as conn:
        m2 = conn.execute('SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?', (id2,)).fetchone()[0]
        assert round(m2, 4) == 5.0000
    
    # 2:1 bonus (2 bonus shares for 1 existing -> total 3)
    id3 = record_corporate_action('TEST_BONUS', 'BONUS', today, 2.0, 1.0)
    with get_read_connection() as conn:
        m3 = conn.execute('SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?', (id3,)).fetchone()[0]
        assert round(m3, 4) == round(1.0 / 3.0, 4)

def test_tradingview_clean_symbol_prefix():
    res = get_tradingview_technical_ratings('NSE:INFY')
    assert res['symbol'] == 'INFY'
    res2 = get_tradingview_technical_ratings('BSE:TCS.BO')
    assert res2['symbol'] == 'TCS'

def test_fyers_market_open_returns_bool():
    status = fyers_client.is_market_open()
    assert isinstance(status, bool)

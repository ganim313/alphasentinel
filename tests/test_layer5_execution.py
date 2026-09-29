"""
Unit test suite for Layer 5: Execution, Compliance, and Telegram Notification.
"""

import pytest
import datetime
from zoneinfo import ZoneInfo
from src.execution.compliance import IndianMarketCompliance
from src.execution.order_manager import PaperBroker, execute_trade
from src.notification.telegram_bot import is_system_halted, set_system_halt_state, send_telegram_alert
from src.notification.trade_card import format_telegram_trade_card
from src.db.session import get_write_connection, init_db


def test_compliance_market_open_naive_and_aware_datetime():
    ist = ZoneInfo("Asia/Kolkata")
    
    # 1. Tuesday at 11:00 AM IST (market open)
    tue_open_naive = datetime.datetime(2026, 3, 10, 11, 0, 0)
    assert IndianMarketCompliance.is_market_open(tue_open_naive) is True

    # 2. Tuesday at 11:00 AM IST timezone-aware
    tue_open_aware = datetime.datetime(2026, 3, 10, 11, 0, 0, tzinfo=ist)
    assert IndianMarketCompliance.is_market_open(tue_open_aware) is True

    # 3. Sunday at 11:00 AM IST (weekend -> market closed)
    sun_closed = datetime.datetime(2026, 3, 8, 11, 0, 0)
    assert IndianMarketCompliance.is_market_open(sun_closed) is False

    # 4. Tuesday at 8:00 AM IST (pre-market -> market closed)
    early_closed = datetime.datetime(2026, 3, 10, 8, 0, 0)
    assert IndianMarketCompliance.is_market_open(early_closed) is False


def test_order_manager_nan_guards():
    # NaN price must be rejected
    res = PaperBroker.place_order("TEST_NAN", float("nan"), 5.0, 100)
    assert res == ""

    # NaN ATR must be rejected
    res = PaperBroker.place_order("TEST_NAN", 100.0, float("nan"), 100)
    assert res == ""


def test_order_manager_halt_guard():
    set_system_halt_state(True, reason="UNIT_TEST_LAYER5_HALT")
    try:
        res = execute_trade("TEST_HALT", 100.0, 5.0, 100)
        assert res == ""
    finally:
        set_system_halt_state(False, reason="UNIT_TEST_LAYER5_RESUME")


def test_order_manager_idempotency():
    init_db()
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_IDEMPOTENT'")

    # First order should succeed
    trade_id_1 = PaperBroker.place_order(
        symbol="TEST_IDEMPOTENT",
        price=100.0,
        atr=3.0,
        quantity=50
    )
    assert trade_id_1 != ""

    # Second order for same symbol while OPEN should return existing ID without creating duplicate
    trade_id_2 = PaperBroker.place_order(
        symbol="TEST_IDEMPOTENT",
        price=102.0,
        atr=3.0,
        quantity=50
    )
    assert trade_id_2 == trade_id_1

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_IDEMPOTENT'")


def test_trade_card_formatting():
    card = format_telegram_trade_card({
        "symbol": "TATA_TEST",
        "trigger_price": 500.0,
        "stop_loss_price": 475.0,
        "target_1_price": 550.0,
        "target_2_price": 580.0,
        "suggested_shares": 100,
        "risk_verdict": "APPROVE",
        "conviction_score": 8.5
    })
    assert "TATA_TEST" in card
    assert "₹500.00" in card
    assert "-5.0%" in card
    assert "+10.0%" in card

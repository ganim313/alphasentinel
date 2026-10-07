"""
Unit Test Suite for FYERS Holdings Guardian & Settlement State Machine.
Requirement R2 & Mufti Taqi Usmani Bay' qabl al-Qabd Invariants.
"""

import os
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List
from zoneinfo import ZoneInfo
import duckdb
import pytest

from src.portfolio.fyers_guardian import (
    SettlementStatus,
    ExitPriorityRule,
    count_trading_days,
    evaluate_settlement,
    generate_gtt_oco_payload,
    evaluate_exit_rule,
    evaluate_exit_hierarchy,
    reconcile_and_evaluate_holdings,
    log_guardian_event
)
from src.ingestion.fyers_client import FyersClient
from scripts.fyers_auth import refresh_fyers_token


class MockFyersClient:
    """Mock Fyers client for testing holdings, positions, and GTT orders."""
    def __init__(self, token_path: str = ".fyers_token"):
        self.token_path = token_path
        self._cached_token = "MOCK_TOKEN_INITIAL"
        self._token_mtime = 0.0
        self.holdings_data: List[Dict[str, Any]] = []
        self.positions_data: List[Dict[str, Any]] = []
        self.placed_gtt_orders: List[Dict[str, Any]] = []

    def reload_token(self) -> str:
        if os.path.exists(self.token_path):
            current_mtime = os.path.getmtime(self.token_path)
            if current_mtime > self._token_mtime:
                with open(self.token_path, "r", encoding="utf-8") as f:
                    self._cached_token = f.read().strip()
                self._token_mtime = current_mtime
        return self._cached_token

    def get_holdings(self) -> List[Dict[str, Any]]:
        return [h for h in self.holdings_data if h.get("quantity", 0) > 0]

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions_data)

    def place_gtt_oco_order(self, symbol: str, qty: int, stop_loss: float, target: float) -> Dict[str, Any]:
        order = {
            "symbol": symbol,
            "qty": qty,
            "stop_loss": stop_loss,
            "target": target,
            "status": "PLACED_365D",
            "placed_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        }
        self.placed_gtt_orders.append(order)
        return order


@pytest.fixture
def in_memory_db():
    """Create in-memory DuckDB database with full schema and migration 003 columns."""
    conn = duckdb.connect(":memory:")
    
    # Core schema tables needed for portfolio testing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            candidate_id VARCHAR,
            sector VARCHAR,
            exchange VARCHAR DEFAULT 'NSE',
            entry_date DATE NOT NULL,
            entry_price DOUBLE NOT NULL,
            quantity INTEGER NOT NULL,
            current_ltp DOUBLE NOT NULL,
            peak_high DOUBLE,
            atr DOUBLE,
            unrealized_pnl DOUBLE DEFAULT 0.0,
            trailing_stop_loss DOUBLE NOT NULL,
            target_1 DOUBLE NOT NULL,
            target_2 DOUBLE NOT NULL,
            risk_rupees DOUBLE NOT NULL,
            portfolio_allocation_pct DOUBLE NOT NULL,
            status VARCHAR DEFAULT 'OPEN',
            execution_type VARCHAR DEFAULT 'PAPER',
            exit_date DATE,
            exit_price DOUBLE,
            realized_pnl DOUBLE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            settlement_status VARCHAR DEFAULT 'SETTLING_T0_T1',
            can_exit BOOLEAN DEFAULT FALSE,
            gtt_placed BOOLEAN DEFAULT FALSE,
            gtt_placed_at TIMESTAMPTZ,
            purification_due_inr DOUBLE DEFAULT 0.0
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS guardian_log (
            id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            symbol VARCHAR,
            action VARCHAR,
            rule VARCHAR,
            details JSON,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bhavcopy_daily (
            symbol VARCHAR NOT NULL,
            trade_date DATE NOT NULL,
            open_price DOUBLE NOT NULL,
            high_price DOUBLE NOT NULL,
            low_price DOUBLE NOT NULL,
            close_price DOUBLE NOT NULL,
            last_price DOUBLE,
            prev_close DOUBLE,
            total_traded_qty BIGINT,
            total_traded_val DOUBLE,
            delivery_qty BIGINT,
            delivery_pct DOUBLE,
            PRIMARY KEY (symbol, trade_date)
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS shariah_universe (
            symbol VARCHAR PRIMARY KEY,
            fyers_symbol VARCHAR,
            sector VARCHAR,
            debt_to_assets DOUBLE,
            cash_to_assets DOUBLE,
            interest_income_ratio DOUBLE,
            illiquid_ratio DOUBLE,
            is_compliant BOOLEAN DEFAULT TRUE,
            screened_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)

    return conn


# ==============================================================================
# 1. T+2 Qabd Settlement State Machine (Day 0, Day 1, Day 2)
# ==============================================================================

def test_day0_trade_date_lock():
    """Verify Day 0 positions evaluate to SETTLING_T0_T1 with can_exit = False."""
    status, can_exit = evaluate_settlement(trading_days_held=0, holding_type="T0")
    assert status == SettlementStatus.SETTLING_T0_T1
    assert can_exit is False


def test_day1_t1_lock():
    """Verify Day 1 positions evaluate to SETTLING_T0_T1 with can_exit = False."""
    status, can_exit = evaluate_settlement(trading_days_held=1, holding_type="T1")
    assert status == SettlementStatus.SETTLING_T0_T1
    assert can_exit is False


def test_holding_type_t1_overrides_days_held():
    """Verify broker 'T1' tag keeps can_exit = False even if 2 calendar days elapsed."""
    status, can_exit = evaluate_settlement(trading_days_held=2, holding_type="T1")
    assert status == SettlementStatus.SETTLING_T0_T1
    assert can_exit is False


def test_day2_morning_transition_to_settled():
    """Verify Day 2 morning transitions to SETTLED_DEMAT and can_exit = True."""
    status, can_exit = evaluate_settlement(trading_days_held=2, holding_type="HLD")
    assert status == SettlementStatus.SETTLED_DEMAT
    assert can_exit is True


def test_count_trading_days_skips_weekends():
    """Verify trading days counter skips Saturdays and Sundays."""
    friday = date(2026, 10, 2)
    saturday = date(2026, 10, 3)
    sunday = date(2026, 10, 4)
    monday = date(2026, 10, 5)
    tuesday = date(2026, 10, 6)

    assert count_trading_days(friday, saturday) == 0
    assert count_trading_days(friday, sunday) == 0
    assert count_trading_days(friday, monday) == 1  # T1
    assert count_trading_days(friday, tuesday) == 2  # T2 (Settled)


def test_count_trading_days_skips_holidays():
    """Verify exchange holidays are skipped in trading days counter."""
    # Dussehra is 2026-10-20 (Tuesday). 2026-10-19 is Monday.
    monday = date(2026, 10, 19)
    wednesday = date(2026, 10, 21)
    
    # 2026-10-20 is hardcoded in HARDCODED_NSE_HOLIDAYS
    days = count_trading_days(monday, wednesday)
    assert days == 1  # Tuesday skipped as holiday; Wednesday is session 1


# ==============================================================================
# 2. Day 2 Morning FYERS GTT OCO Order Lodging
# ==============================================================================

def test_gtt_oco_payload_structure():
    """Verify 365-day FYERS GTT OCO payload format."""
    payload = generate_gtt_oco_payload(
        symbol="INFY",
        qty=50,
        stop_loss=1450.0,
        target=1750.0
    )
    assert payload["symbol"] == "NSE:INFY-EQ"
    assert payload["qty"] == 50
    assert payload["stop_loss"] == 1450.0
    assert payload["target"] == 1750.0
    assert payload["validity"] == "365D"
    assert payload["status"] == "PLACED_365D"
    assert payload["side"] == -1
    assert payload["type"] == 3


def test_reconciliation_lodges_gtt_oco_on_settlement(in_memory_db):
    """Verify that Day 2 transition triggers 365-day GTT OCO order and sets gtt_placed = True."""
    conn = in_memory_db
    client = MockFyersClient()
    
    # Setup open position on Day 0 (Monday 2026-10-05)
    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_001', 'TCS', DATE '2026-10-05', 3000.0, 10, 3050.0,
            2820.0, 3360.0, 3600.0, 1800.0, 3.0, 'OPEN', 'PAPER',
            'SETTLING_T0_T1', FALSE, FALSE
        )
    """)

    # At Day 1 (Tuesday 2026-10-06): Still settling
    client.holdings_data = [{"symbol": "NSE:TCS-EQ", "quantity": 10, "holdingType": "T1"}]
    res_d1 = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 6))
    assert res_d1["settled_count"] == 0
    assert res_d1["settling_count"] == 1
    assert len(client.placed_gtt_orders) == 0

    pos_d1 = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 'POS_001'").fetchone()
    assert pos_d1[0] == "SETTLING_T0_T1"
    assert pos_d1[1] is False
    assert pos_d1[2] is False

    # At Day 2 (Wednesday 2026-10-07): Settled!
    client.holdings_data = [{"symbol": "NSE:TCS-EQ", "quantity": 10, "holdingType": "HLD"}]
    res_d2 = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert res_d2["settled_count"] == 1
    assert len(client.placed_gtt_orders) == 1
    assert "TCS" in res_d2["gtt_lodged_symbols"]

    pos_d2 = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 'POS_001'").fetchone()
    assert pos_d2[0] == "SETTLED_DEMAT"
    assert pos_d2[1] is True
    assert pos_d2[2] is True

    # Verify GTT logged to guardian_log
    log_row = conn.execute("SELECT action, rule FROM guardian_log WHERE symbol = 'TCS' AND action = 'GTT_OCO_LODGED'").fetchone()
    assert log_row is not None
    assert log_row[0] == "GTT_OCO_LODGED"


# ==============================================================================
# 3. Nightly Reconciliation & Manual Demat Buy Auto-Import
# ==============================================================================

def test_reconciliation_auto_imports_manual_demat_buys(in_memory_db):
    """Verify 19:30 Holdings Guardian discovers untracked Demat buys and auto-imports them."""
    conn = in_memory_db
    client = MockFyersClient()
    client.holdings_data = [
        {"symbol": "NSE:TITAN-EQ", "quantity": 25, "costPrice": 3200.0, "ltp": 3250.0, "holdingType": "HLD"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert "TITAN" in res["manual_imports"]

    imported = conn.execute("""
        SELECT symbol, quantity, entry_price, execution_type, settlement_status, can_exit 
        FROM positions WHERE symbol = 'TITAN'
    """).fetchone()

    assert imported[0] == "TITAN"
    assert imported[1] == 25
    assert imported[2] == 3200.0
    assert imported[3] == "MANUAL_IMPORT"
    assert imported[4] == "SETTLED_DEMAT"
    assert imported[5] is True

    # Verify log entry
    log_entry = conn.execute("SELECT action, rule FROM guardian_log WHERE symbol = 'TITAN'").fetchone()
    assert log_entry[0] == "MANUAL_IMPORT"


def test_zero_quantity_holdings_not_imported(in_memory_db):
    """Verify broker holdings with quantity 0 are ignored during reconciliation."""
    conn = in_memory_db
    client = MockFyersClient()
    client.holdings_data = [
        {"symbol": "NSE:ZEROQTY-EQ", "quantity": 0, "costPrice": 500.0, "holdingType": "HLD"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert len(res["manual_imports"]) == 0
    count = conn.execute("SELECT count(*) FROM positions WHERE symbol = 'ZEROQTY'").fetchone()[0]
    assert count == 0


# ==============================================================================
# 4. 9-Rule Priority Exit Hierarchy (P1 to P9)
# ==============================================================================

def test_p1_hard_stop_breach():
    """Verify P1 Hard Stop fires when LTP <= trailing_stop_loss."""
    res = evaluate_exit_hierarchy(
        ltp=94.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0
    )
    assert res.rule == ExitPriorityRule.P1_HARD_STOP
    assert res.action == "EXIT"


def test_p2_50_sma_breakdown():
    """Verify P2 50-SMA Breakdown fires when Close < 50 SMA and LTP > Stop."""
    res = evaluate_exit_hierarchy(
        ltp=97.0,
        trailing_stop_loss=94.0,
        entry_price=100.0,
        close=97.0,
        sma_50=99.0
    )
    assert res.rule == ExitPriorityRule.P2_50_SMA_BREAKDOWN
    assert res.action == "EXIT"


def test_p3_climax_extension_trim():
    """Verify P3 Climax Trim fires when High >= 20 EMA + 3.5 ATR."""
    ema_20 = 500.0
    atr_14 = 20.0
    climax_high = ema_20 + (3.5 * atr_14)  # 570.0
    
    res = evaluate_exit_hierarchy(
        ltp=565.0,
        trailing_stop_loss=480.0,
        entry_price=480.0,
        quantity=100,
        high=575.0,
        ema_20=ema_20,
        atr_14=atr_14,
        volume=300000,
        avg_volume_20=100000,
        weak_close=True
    )
    assert res.rule == ExitPriorityRule.P3_CLIMAX_TRIM
    assert res.action == "TRIM_50"
    assert res.trim_quantity == 50


def test_p4_chandelier_trail():
    """Verify P4 Chandelier Trail fires when Gain >= 2R."""
    entry = 100.0
    init_stop = 95.0
    r_dist = 5.0
    peak_2r = entry + (2.0 * r_dist)  # 110.0
    atr = 2.0

    res = evaluate_exit_hierarchy(
        ltp=111.0,
        trailing_stop_loss=95.0,
        entry_price=entry,
        initial_stop_loss=init_stop,
        peak_close=112.0,
        atr_14=atr
    )
    assert res.rule == ExitPriorityRule.P4_CHANDELIER_TRAIL
    assert res.action == "TRAIL_STOP"
    expected_new_stop = max(95.0, round(112.0 - (2.5 * atr), 2))  # 112 - 5 = 107.0
    assert res.new_stop_loss == expected_new_stop


def test_p5_breakeven_ratchet():
    """Verify P5 Breakeven Ratchet fires when Gain >= 1R and < 2R."""
    entry = 100.0
    init_stop = 95.0
    r_dist = 5.0
    peak_1r = entry + (1.2 * r_dist)  # 106.0 (< 110 for 2R)

    res = evaluate_exit_hierarchy(
        ltp=105.0,
        trailing_stop_loss=95.0,
        entry_price=entry,
        initial_stop_loss=init_stop,
        peak_close=peak_1r
    )
    assert res.rule == ExitPriorityRule.P5_BREAKEVEN_RATCHET
    assert res.action == "RATCHET_BREAKEVEN"
    assert res.new_stop_loss == round(entry * 1.003, 2)  # 100.3


def test_p6_distribution_days_tighten():
    """Verify P6 Distribution Tighten fires when distribution days >= 4."""
    res = evaluate_exit_hierarchy(
        ltp=102.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        distribution_days_15=4,
        low_5d=98.5
    )
    assert res.rule == ExitPriorityRule.P6_DISTRIBUTION_TIGHTEN
    assert res.action == "TIGHTEN_STOP_5D_LOW"
    assert res.new_stop_loss == 98.5


def test_p7_rs_decay_tighten():
    """Verify P7 RS Decay fires when RS percentile < 50."""
    res = evaluate_exit_hierarchy(
        ltp=102.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        rs_percentile=45.0,
        ema_21=98.0
    )
    assert res.rule == ExitPriorityRule.P7_RS_DECAY_TIGHTEN
    assert res.action == "TIGHTEN_STOP_21_EMA"
    assert res.new_stop_loss == 98.0


def test_p8_time_stop():
    """Verify P8 Time Stop fires when held >= 20 sessions and gain < 1R."""
    res = evaluate_exit_hierarchy(
        ltp=101.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        trading_days_held=21
    )
    assert res.rule == ExitPriorityRule.P8_TIME_STOP
    assert res.action == "EXIT"


def test_p9_shariah_drift_flag_only():
    """Verify P9 Shariah Drift generates Telegram flag only with ZERO forced liquidation."""
    res = evaluate_exit_hierarchy(
        ltp=102.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        is_shariah_compliant=False
    )
    assert res.rule == ExitPriorityRule.P9_SHARIAH_DRIFT
    assert res.action == "FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION"
    assert res.new_stop_loss is None
    assert res.trim_quantity is None


# ==============================================================================
# 5. Priority Ordering & Settlement Lock Guard
# ==============================================================================

def test_priority_hierarchy_p1_takes_precedence_over_p2():
    """Verify P1 Hard Stop fires first even when P2 50-SMA breakdown is also true."""
    res = evaluate_exit_hierarchy(
        ltp=93.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        close=93.0,
        sma_50=99.0
    )
    assert res.rule == ExitPriorityRule.P1_HARD_STOP


def test_settlement_lock_prevents_exit_during_t0_t1(in_memory_db):
    """Verify position on Day 0/1 produces ZERO exit alerts even if price breaches stop loss."""
    conn = in_memory_db
    client = MockFyersClient()

    # Position entered today (Day 0) with entry 100, stop 95.
    # LTP drops to 90 (breaches stop).
    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_LOCKED', 'LOCKED_STOCK', DATE '2026-10-07', 100.0, 10, 90.0,
            95.0, 110.0, 120.0, 50.0, 1.0, 'OPEN', 'PAPER',
            'SETTLING_T0_T1', FALSE, FALSE
        )
    """)
    client.holdings_data = [
        {"symbol": "NSE:LOCKED_STOCK-EQ", "quantity": 10, "ltp": 90.0, "holdingType": "T0"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert res["settling_count"] == 1
    assert res["settled_count"] == 0
    # Bay' qabl al-Qabd prohibition: Zero exit alerts allowed!
    assert len(res["exit_alerts"]) == 0

    pos_status = conn.execute("SELECT status, can_exit FROM positions WHERE id = 'POS_LOCKED'").fetchone()
    assert pos_status[0] == "OPEN"  # Still OPEN, not closed
    assert pos_status[1] is False


# ==============================================================================
# 6. FYERS Client & Auth Token Integration
# ==============================================================================

def test_fyers_client_dynamic_token_reload(tmp_path):
    """Verify FyersClient dynamically picks up new token written by fyers_auth."""
    token_file = tmp_path / ".fyers_token"
    token_file.write_text("SESSION_TOKEN_1", encoding="utf-8")

    client = FyersClient(token_path=str(token_file))
    assert client.reload_token() == "SESSION_TOKEN_1"

    # Refresh token via auth module
    time.sleep(0.01)
    refresh_fyers_token(token="SESSION_TOKEN_2_REFRESHED", token_path=token_file)

    assert client.reload_token() == "SESSION_TOKEN_2_REFRESHED"


def test_fyers_client_get_holdings_and_positions():
    """Verify FyersClient get_holdings and get_positions work with mock data."""
    client = FyersClient()
    client.holdings_data = [
        {"symbol": "NSE:HDFCBANK-EQ", "quantity": 15, "holdingType": "HLD"},
        {"symbol": "NSE:ZERO-EQ", "quantity": 0, "holdingType": "HLD"}
    ]
    client.positions_data = [
        {"symbol": "NSE:INFY-EQ", "netQty": 20}
    ]

    holdings = client.get_holdings()
    assert len(holdings) == 1
    assert holdings[0]["symbol"] == "NSE:HDFCBANK-EQ"

    positions = client.get_positions()
    assert len(positions) == 1
    assert positions[0]["netQty"] == 20

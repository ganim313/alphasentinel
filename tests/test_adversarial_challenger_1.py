"""
Adversarial Stress Test Suite — Challenger 1
Independent Empirical Verification of:
1. Risk Parity Math & Position Sizing (Edge bounds, zero/negative ATR, boundary 8.0%, heat ceiling)
2. T+2 Qabd Settlement State Machine (Weekends, multi-day holidays, non-exit on Day 0/1, Day 2 transition)
3. Holdings Guardian 9-Rule Priority Hierarchy (Sequential pairwise precedence, P9 Shariah drift non-liquidation)
"""

import math
from datetime import date
import duckdb
import pytest

from src.risk.arbiter import calculate_deterministic_risk_and_position
from src.portfolio.fyers_guardian import (
    SettlementStatus,
    ExitPriorityRule,
    count_trading_days,
    evaluate_settlement,
    evaluate_exit_hierarchy,
    reconcile_and_evaluate_holdings,
)


class MockFyersClient:
    """Mock FYERS client for empirical adversarial testing."""
    def __init__(self):
        self.holdings_data = []
        self.positions_data = []
        self.placed_gtt_orders = []

    def reload_token(self):
        return "MOCK_TOKEN_OK"

    def get_holdings(self):
        return list(self.holdings_data)

    def get_positions(self):
        return list(self.positions_data)

    def place_gtt_oco_order(self, symbol: str, qty: int, stop_loss: float, target: float):
        order = {
            "symbol": symbol,
            "qty": qty,
            "stop_loss": stop_loss,
            "target": target,
            "status": "PLACED_365D"
        }
        self.placed_gtt_orders.append(order)
        return order


@pytest.fixture
def test_db():
    """In-memory DuckDB database fixture with full schema for adversarial tests."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE positions (
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
        CREATE TABLE guardian_log (
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
        CREATE TABLE bhavcopy_daily (
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
        CREATE TABLE shariah_universe (
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
# 1. RISK PARITY MATH & POSITION SIZING ADVERSARIAL CHALLENGES
# ==============================================================================

def test_adversarial_zero_and_negative_atr():
    """
    Challenge: Provide atr_14 = 0.0 and atr_14 = -5.0.
    Expected: Arbiter must NOT crash with division by zero or negative stop.
    It should fall back gracefully to 3% trigger price proxy.
    """
    for bad_atr in [0.0, -1.0, -5.5]:
        res = calculate_deterministic_risk_and_position(
            symbol="TEST_ATR",
            trigger_price=100.0,
            current_price=100.0,
            atr_14=bad_atr,
            base_low_10d=None,
            regime_risk_pct=1.0,
            portfolio_capital_rupees=10_00_000.0,
            open_positions=[]
        )
        assert res["verdict"] == "APPROVE"
        assert res["stop_loss_price"] > 0
        assert res["stop_loss_price"] < 100.0
        # When atr fallback is trigger * 0.03 = 3.0, 2.5 * 3.0 = 7.5 -> Stop = 92.5 (7.5% distance)
        assert res["stop_distance_pct"] == 7.5
        assert res["suggested_shares"] > 0


def test_adversarial_nan_atr_and_nan_base_low():
    """
    Challenge: Provide NaN for atr_14 and base_low_10d.
    Expected: Graceful numeric fallback without propagating NaN.
    """
    res = calculate_deterministic_risk_and_position(
        symbol="TEST_NAN",
        trigger_price=200.0,
        current_price=200.0,
        atr_14=float("nan"),
        base_low_10d=float("nan"),
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res["verdict"] == "APPROVE"
    assert not math.isnan(res["stop_loss_price"])
    assert not math.isnan(res["suggested_shares"])
    assert res["suggested_shares"] > 0


def test_adversarial_negative_and_zero_base_low():
    """
    Challenge: Provide base_low_10d <= 0 (e.g. -100.0, 0.0).
    Expected: Arbiter ignores invalid base low and falls back cleanly to ATR stop.
    """
    for invalid_base in [-100.0, -0.01, 0.0]:
        res = calculate_deterministic_risk_and_position(
            symbol="TEST_BASE_LOW",
            trigger_price=100.0,
            current_price=100.0,
            atr_14=2.0,
            base_low_10d=invalid_base,
            regime_risk_pct=1.0,
            portfolio_capital_rupees=10_00_000.0,
            open_positions=[]
        )
        assert res["verdict"] == "APPROVE"
        # ATR stop: 100 - (2.5 * 2.0) = 95.0
        assert res["stop_loss_price"] == 95.0
        assert res["stop_distance_pct"] == 5.0


def test_adversarial_exact_8_percent_boundary():
    """
    Challenge: Stop distance exactly at 8.00%.
    Trigger = 100.0, Stop = 92.0 -> Distance = 8.00%.
    Expected: APPROVE (rule says reject only if > 8.0%).
    """
    res = calculate_deterministic_risk_and_position(
        symbol="EXACT_8",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=3.2,  # 100 - 2.5 * 3.2 = 92.0 (exactly 8.0% stop)
        base_low_10d=None,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res["verdict"] == "APPROVE"
    assert res["stop_distance_pct"] == 8.0
    assert res["stop_loss_price"] == 92.0
    assert res["suggested_shares"] > 0


def test_adversarial_just_over_8_percent_rejection():
    """
    Challenge: Stop distance just over 8.00% (e.g. 8.01%, 8.1%).
    Expected: REJECT due to volatility exceeding 8.0%.
    """
    # 8.01% stop: Trigger 100.0, Stop 91.99 -> ATR = (100 - 91.99)/2.5 = 3.204
    res = calculate_deterministic_risk_and_position(
        symbol="OVER_8",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=3.204,
        base_low_10d=None,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0
    assert res["stop_distance_pct"] > 8.0
    assert "exceeds max allowed stop" in res["rejection_reason"]


def test_adversarial_extreme_volatility_rejections():
    """
    Challenge: Stop distance at 15.0%, 25.0%, 50.0%.
    Expected: REJECT with zero shares allocated.
    """
    for dist in [15.0, 25.0, 50.0]:
        atr = (dist / 100.0 * 100.0) / 2.5
        res = calculate_deterministic_risk_and_position(
            symbol=f"EXTREME_{dist}",
            trigger_price=100.0,
            current_price=100.0,
            atr_14=atr,
            base_low_10d=None,
            regime_risk_pct=1.0,
            portfolio_capital_rupees=10_00_000.0,
            open_positions=[]
        )
        assert res["verdict"] == "REJECT"
        assert res["suggested_shares"] == 0


def test_adversarial_unchoked_allocation_strict_cap_at_16_percent():
    """
    Challenge: Extremely tight stop (e.g. 1.0% stop distance).
    Raw risk sizing: 1% risk budget / 1% stop = 100% portfolio allocation!
    Expected: Position sizing MUST NOT exceed 16.0% maximum allocation ceiling.
    """
    res = calculate_deterministic_risk_and_position(
        symbol="TIGHT_STOP",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=0.4,  # Stop = 100 - 2.5*0.4 = 99.0 -> 1.0% stop
        base_low_10d=99.0,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res["verdict"] == "APPROVE"
    # Allocation must be strictly capped at 16.0% (₹1,60,000 = 1600 shares)
    assert res["portfolio_allocation_pct"] <= 16.0
    assert res["suggested_shares"] == 1600
    assert res["position_value_rupees"] == 160_000.0


def test_adversarial_portfolio_heat_ceiling_multiple_positions():
    """
    Stress-test: Multiple open positions with existing heat = 4.4% (₹44,000 open risk).
    New candidate has risk budget of 1.0% (₹10,000).
    Max heat ceiling is 5.0% (₹50,000). Available = ₹6,000.
    With risk/sh = ₹6.0, candidate must be dynamically scaled down by heat ceiling
    from 1200 shares (vol-targeted) to exactly 1000 shares to keep aggregate heat <= 5.0%.
    """
    open_pos = [
        {"symbol": "P1", "risk_rupees": 11_000.0},
        {"symbol": "P2", "risk_rupees": 11_000.0},
        {"symbol": "P3", "risk_rupees": 11_000.0},
        {"symbol": "P4", "risk_rupees": 11_000.0},
    ]  # Total: ₹44,000 (4.4% of ₹10L)

    res = calculate_deterministic_risk_and_position(
        symbol="P5_SCALED",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.4,  # SL = 94.0, risk/sh = ₹6.0
        base_low_10d=None,
        regime_risk_pct=1.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=10_00_000.0,
        adtv_20d=50_000_000.0,
        open_positions=open_pos
    )

    assert res["verdict"] in ("APPROVE", "APPROVE_WITH_WARNING")
    # Remaining risk: 50,000 - 44,000 = 6,000. Max shares by heat = floor(6000 / 6) = 1000 shares.
    assert res["suggested_shares"] == 1000
    assert res["shares_to_buy"] == 1000
    assert res["portfolio_heat_pct_after"] == 5.0
    assert res["risk_rupees"] == 6000.0



def test_adversarial_portfolio_heat_existing_breach_rejects():
    """
    Stress-test: What if existing positions suffered a gap down and open heat is 5.5% (> 5.0%)?
    Expected: Immediate REJECT of new candidate with zero shares.
    """
    over_limit_pos = [{"symbol": "CRASHED_POS", "risk_rupees": 55_000.0}]
    res = calculate_deterministic_risk_and_position(
        symbol="NEW_CANDIDATE",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.0,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=over_limit_pos
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0
    assert "heat ceiling reached" in res["rejection_reason"].lower()


# ==============================================================================
# 2. T+2 QABD SETTLEMENT STATE MACHINE ADVERSARIAL CHALLENGES
# ==============================================================================

def test_adversarial_weekend_rollovers():
    """
    Stress-test: Position bought on Thursday 2026-10-08:
    - Friday 2026-10-09: Day 1 (T1) -> SETTLING_T0_T1, can_exit = False
    - Saturday 2026-10-10: Weekend -> Days held = 1 -> SETTLING_T0_T1, can_exit = False
    - Sunday 2026-10-11: Weekend -> Days held = 1 -> SETTLING_T0_T1, can_exit = False
    - Monday 2026-10-12: Day 2 (T2) -> SETTLED_DEMAT, can_exit = True
    """
    thursday = date(2026, 10, 8)
    friday = date(2026, 10, 9)
    saturday = date(2026, 10, 10)
    sunday = date(2026, 10, 11)
    monday = date(2026, 10, 12)

    assert count_trading_days(thursday, friday) == 1
    st, exit_ok = evaluate_settlement(count_trading_days(thursday, friday))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    assert count_trading_days(thursday, saturday) == 1
    st, exit_ok = evaluate_settlement(count_trading_days(thursday, saturday))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    assert count_trading_days(thursday, sunday) == 1
    st, exit_ok = evaluate_settlement(count_trading_days(thursday, sunday))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    assert count_trading_days(thursday, monday) == 2
    st, exit_ok = evaluate_settlement(count_trading_days(thursday, monday))
    assert st == SettlementStatus.SETTLED_DEMAT and exit_ok


def test_adversarial_multiday_nse_holidays():
    """
    Stress-test: Position bought before multi-day market holiday window.
    2026-10-01 (Thursday): Buy date.
    2026-10-02 (Friday): Mahatma Gandhi Jayanti (Hardcoded NSE holiday).
    2026-10-03 (Saturday): Weekend.
    2026-10-04 (Sunday): Weekend.
    2026-10-05 (Monday): Session 1 (T1) -> SETTLING_T0_T1.
    2026-10-06 (Tuesday): Session 2 (T2) -> SETTLED_DEMAT.
    """
    buy_date = date(2026, 10, 1)
    fri_holiday = date(2026, 10, 2)
    sun_weekend = date(2026, 10, 4)
    mon_session1 = date(2026, 10, 5)
    tue_session2 = date(2026, 10, 6)

    # Gandhi Jayanti is a holiday -> trading days = 0
    assert count_trading_days(buy_date, fri_holiday) == 0
    st, exit_ok = evaluate_settlement(count_trading_days(buy_date, fri_holiday))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    # Over weekend -> trading days = 0
    assert count_trading_days(buy_date, sun_weekend) == 0
    st, exit_ok = evaluate_settlement(count_trading_days(buy_date, sun_weekend))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    # Monday -> trading days = 1 (T1)
    assert count_trading_days(buy_date, mon_session1) == 1
    st, exit_ok = evaluate_settlement(count_trading_days(buy_date, mon_session1))
    assert st == SettlementStatus.SETTLING_T0_T1 and not exit_ok

    # Tuesday -> trading days = 2 (T2 Settled)
    assert count_trading_days(buy_date, tue_session2) == 2
    st, exit_ok = evaluate_settlement(count_trading_days(buy_date, tue_session2))
    assert st == SettlementStatus.SETTLED_DEMAT and exit_ok


def test_adversarial_day0_day1_catastrophic_crash_cannot_exit(test_db):
    """
    CRITICAL INVARIANT TEST:
    Under Mufti Muhammad Taqi Usmani's Bay' qabl al-Qabd prohibition,
    if a stock crashes -50% on Day 0 or Day 1, can it be exited?
    ABSOLUTELY NOT. can_exit must remain False, zero exit alerts, zero GTT orders.
    """
    conn = test_db
    client = MockFyersClient()

    # Position bought today at 100.0, stop 94.0.
    # Stock crashes to 50.0 (catastrophic breach of stop loss).
    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_CRASH', 'CRASH_STOCK', DATE '2026-10-07', 100.0, 100, 50.0,
            94.0, 112.0, 120.0, 600.0, 1.0, 'OPEN', 'PAPER',
            'SETTLING_T0_T1', FALSE, FALSE
        )
    """)
    client.holdings_data = [
        {"symbol": "NSE:CRASH_STOCK-EQ", "quantity": 100, "ltp": 50.0, "holdingType": "T0"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))

    # Assertions
    assert res["settling_count"] == 1
    assert res["settled_count"] == 0
    assert len(res["exit_alerts"]) == 0
    assert len(client.placed_gtt_orders) == 0

    # DB state check: MUST STILL BE OPEN AND can_exit = False
    row = conn.execute("SELECT status, can_exit, settlement_status FROM positions WHERE id = 'POS_CRASH'").fetchone()
    assert row[0] == "OPEN"
    assert row[1] is False
    assert row[2] == "SETTLING_T0_T1"


def test_adversarial_broker_t1_override_on_day2(test_db):
    """
    Stress-test: 2 trading days elapsed, but broker holdings report holdingType == 'T1'.
    Broker's physical demat status takes precedence: position remains locked in SETTLING_T0_T1.
    """
    conn = test_db
    client = MockFyersClient()

    # Entry was 2 trading days ago
    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_DELAY', 'DELAY_STOCK', DATE '2026-10-05', 100.0, 50, 102.0,
            94.0, 112.0, 120.0, 300.0, 0.5, 'OPEN', 'PAPER',
            'SETTLING_T0_T1', FALSE, FALSE
        )
    """)
    # Broker delayed settlement
    client.holdings_data = [
        {"symbol": "NSE:DELAY_STOCK-EQ", "quantity": 50, "ltp": 102.0, "holdingType": "T1"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert res["settling_count"] == 1
    assert res["settled_count"] == 0
    assert len(res["gtt_lodged_symbols"]) == 0

    row = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 'POS_DELAY'").fetchone()
    assert row[0] == "SETTLING_T0_T1"
    assert row[1] is False
    assert row[2] is False


def test_adversarial_day2_morning_transition_and_gtt_idempotency(test_db):
    """
    Verify Day 2 morning transition:
    1. First run on Day 2 lodges GTT OCO order and sets gtt_placed = True.
    2. Second run on same day does NOT lodge duplicate GTT OCO orders (idempotency).
    """
    conn = test_db
    client = MockFyersClient()

    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_IDEMP', 'IDEMP_STOCK', DATE '2026-10-05', 100.0, 50, 105.0,
            94.0, 112.0, 120.0, 300.0, 0.5, 'OPEN', 'PAPER',
            'SETTLING_T0_T1', FALSE, FALSE
        )
    """)
    client.holdings_data = [
        {"symbol": "NSE:IDEMP_STOCK-EQ", "quantity": 50, "ltp": 105.0, "holdingType": "HLD"}
    ]

    # Run 1: Lodges GTT OCO
    res1 = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert len(client.placed_gtt_orders) == 1
    assert "IDEMP_STOCK" in res1["gtt_lodged_symbols"]

    # Run 2: Idempotent check
    res2 = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))
    assert len(client.placed_gtt_orders) == 1  # No duplicate order placed!
    assert len(res2["gtt_lodged_symbols"]) == 0


# ==============================================================================
# 3. HOLDINGS GUARDIAN 9-RULE PRIORITY HIERARCHY ADVERSARIAL CHALLENGES
# ==============================================================================

def test_adversarial_priority_p1_over_p2():
    """Verify P1 Hard Stop fires first when BOTH P1 (LTP <= Stop) and P2 (Close < 50 SMA) are met."""
    res = evaluate_exit_hierarchy(
        ltp=90.0,
        trailing_stop_loss=95.0,  # P1 met
        entry_price=100.0,
        close=90.0,
        sma_50=98.0               # P2 met
    )
    assert res.rule == ExitPriorityRule.P1_HARD_STOP
    assert res.action == "EXIT"


def test_adversarial_priority_p2_over_p3():
    """Verify P2 50-SMA Breakdown fires first when BOTH P2 (Close < 50 SMA) and P3 (Climax Trim) are met."""
    res = evaluate_exit_hierarchy(
        ltp=95.0,
        trailing_stop_loss=90.0,  # P1 not met
        entry_price=100.0,
        close=95.0,
        sma_50=98.0,              # P2 met
        high=130.0,
        ema_20=100.0,
        atr_14=5.0                # 100 + 3.5*5 = 117.5 < 130.0 -> P3 also met!
    )
    assert res.rule == ExitPriorityRule.P2_50_SMA_BREAKDOWN
    assert res.action == "EXIT"


def test_adversarial_priority_p3_over_p4():
    """Verify P3 Climax Trim fires first when BOTH P3 (Climax Trim) and P4 (Chandelier Trail) are met."""
    res = evaluate_exit_hierarchy(
        ltp=125.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        high=130.0,
        ema_20=100.0,
        atr_14=5.0,               # P3 met: 130 >= 100 + 3.5*5 = 117.5
        peak_close=125.0          # P4 met: 125 >= 100 + 2*5 = 110.0 (+2R)
    )
    assert res.rule == ExitPriorityRule.P3_CLIMAX_TRIM
    assert res.action == "TRIM_50"


def test_adversarial_priority_p4_over_p5():
    """Verify P4 Chandelier Trail fires first when Gain >= 2R (P4 met AND P5 +1R met)."""
    res = evaluate_exit_hierarchy(
        ltp=112.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        peak_close=112.0,         # Gain = 12 = 2.4R (> 2R so both P4 and P5 trigger conditions hold)
        atr_14=2.0
    )
    assert res.rule == ExitPriorityRule.P4_CHANDELIER_TRAIL
    assert res.action == "TRAIL_STOP"


def test_adversarial_priority_p5_over_p6():
    """Verify P5 Breakeven Ratchet fires first when +1R is reached AND distribution days >= 4."""
    res = evaluate_exit_hierarchy(
        ltp=106.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        peak_close=106.0,         # +1.2R (P5 met)
        distribution_days_15=5,   # P6 met
        low_5d=98.0
    )
    assert res.rule == ExitPriorityRule.P5_BREAKEVEN_RATCHET
    assert res.action == "RATCHET_BREAKEVEN"


def test_adversarial_priority_p6_over_p7():
    """Verify P6 Distribution Days fires first when distribution days >= 4 AND RS percentile < 50."""
    res = evaluate_exit_hierarchy(
        ltp=102.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        peak_close=102.0,
        distribution_days_15=4,   # P6 met
        low_5d=98.0,
        rs_percentile=35.0,       # P7 met
        ema_21=97.0
    )
    assert res.rule == ExitPriorityRule.P6_DISTRIBUTION_TIGHTEN
    assert res.action == "TIGHTEN_STOP_5D_LOW"


def test_adversarial_priority_p7_over_p8():
    """Verify P7 RS Decay fires first when RS < 50 AND Days held >= 20 with gain < 1R."""
    res = evaluate_exit_hierarchy(
        ltp=101.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        peak_close=101.0,
        rs_percentile=40.0,       # P7 met
        ema_21=97.0,
        trading_days_held=25      # P8 met
    )
    assert res.rule == ExitPriorityRule.P7_RS_DECAY_TIGHTEN
    assert res.action == "TIGHTEN_STOP_21_EMA"


def test_adversarial_priority_p8_over_p9():
    """Verify P8 Time Stop fires first when Days held >= 20 with gain < 1R AND Shariah non-compliant."""
    res = evaluate_exit_hierarchy(
        ltp=101.0,
        trailing_stop_loss=95.0,
        entry_price=100.0,
        initial_stop_loss=95.0,
        trading_days_held=22,     # P8 met
        is_shariah_compliant=False # P9 met
    )
    assert res.rule == ExitPriorityRule.P8_TIME_STOP
    assert res.action == "EXIT"


def test_adversarial_shariah_drift_p9_zero_forced_liquidation(test_db):
    """
    CRITICAL SHARIAH COMPLIANCE TEST:
    When a stock fails quarterly Shariah sync (is_shariah_compliant = False)
    and no other technical exit rule fires:
    1. Rule P9 must fire.
    2. Action must be FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION.
    3. Position in DuckDB must NOT be changed to MARKED_FOR_CLOSURE or CLOSED.
    4. ZERO shares must be liquidated or trimmed.
    5. Trailing stop loss must NOT be modified.
    """
    conn = test_db
    client = MockFyersClient()

    conn.execute("""
        INSERT INTO positions (
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            portfolio_allocation_pct, status, execution_type,
            settlement_status, can_exit, gtt_placed
        ) VALUES (
            'POS_SHARIAH_DRIFT', 'DRIFT_CORP', DATE '2026-10-01', 100.0, 100, 103.0,
            95.0, 112.0, 120.0, 500.0, 1.0, 'OPEN', 'PAPER',
            'SETTLED_DEMAT', TRUE, TRUE
        )
    """)
    # Insert failing Shariah status into shariah_universe
    conn.execute("""
        INSERT INTO shariah_universe (symbol, is_compliant)
        VALUES ('DRIFT_CORP', FALSE)
    """)

    client.holdings_data = [
        {"symbol": "NSE:DRIFT_CORP-EQ", "quantity": 100, "ltp": 103.0, "holdingType": "HLD"}
    ]

    res = reconcile_and_evaluate_holdings(conn, client, as_of_date=date(2026, 10, 7))

    assert len(res["exit_alerts"]) == 1
    alert = res["exit_alerts"][0]
    assert alert["symbol"] == "DRIFT_CORP"
    assert alert["rule"] == "P9_SHARIAH_DRIFT"
    assert alert["action"] == "FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION"

    # Verify database position integrity:
    row = conn.execute("""
        SELECT status, quantity, trailing_stop_loss, current_ltp 
        FROM positions WHERE id = 'POS_SHARIAH_DRIFT'
    """).fetchone()

    # Position is STILL OPEN, NOT LIQUIDATED
    assert row[0] == "OPEN"
    assert row[1] == 100
    assert row[2] == 95.0
    assert row[3] == 103.0

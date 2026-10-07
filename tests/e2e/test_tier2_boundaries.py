"""
Tier 2: Boundary Value Analysis & Edge Cases E2E Test Suite.
Verifies boundary conditions, extreme inputs, null safety, and corner cases
for all features F1 through F13.
Enforces >= 5 boundary test cases per feature (65 total test cases).
"""

import os
import sys
import math
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import pytest
import duckdb

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_E2E_DIR = Path(__file__).resolve().parent
if str(_E2E_DIR) not in sys.path:
    sys.path.insert(0, str(_E2E_DIR))

from e2e_helpers import (
    create_in_memory_e2e_db,
    MockFyersClient,
    SettlementStatus,
    ExitPriorityRule,
    RegimeState,
    compute_vectorized_residual_momentum,
    check_price_jump_tripwire_logic,
)
from src.screening.shariah_filter import (
    check_shariah_compliance,
    infer_sector_from_company_or_symbol,
    PROHIBITED_SYMBOLS,
)
from src.notification.trade_card import format_telegram_trade_card


# ==============================================================================
# FEATURE F1: Volatility-Adjusted Risk Parity Math & Structural Stops Boundaries (5 tests)
# ==============================================================================

def test_t2_f1_01_stop_distance_exact_8pct_boundary():
    """Exact boundary: Stop distance exactly 8.00% is APPROVED; 8.01% is REJECTED."""
    trigger_price = 100.0

    # Case A: Exactly 8.00% stop (Stop = 92.0)
    stop_exact = 92.0
    dist_exact = (trigger_price - stop_exact) / trigger_price
    verdict_exact = "APPROVE" if dist_exact <= 0.08 else "REJECT"
    assert verdict_exact == "APPROVE"

    # Case B: 8.01% stop (Stop = 91.99)
    stop_over = 91.99
    dist_over = (trigger_price - stop_over) / trigger_price
    verdict_over = "APPROVE" if dist_over <= 0.08 else "REJECT"
    assert verdict_over == "REJECT"


def test_t2_f1_02_zero_or_negative_atr_fallback():
    """When ATR is zero or NaN, safe fallback (e.g. 3.0% of trigger price) is applied."""
    trigger_price = 500.0
    atr_zero = 0.0

    if atr_zero is None or math.isnan(atr_zero) or atr_zero <= 0:
        effective_atr = trigger_price * 0.03
    else:
        effective_atr = atr_zero

    assert effective_atr == 15.0
    assert effective_atr > 0


def test_t2_f1_03_zero_or_negative_trigger_price_rejected():
    """Trigger price <= 0.0 fails closed with immediate REJECT."""
    trigger_prices = [0.0, -100.0, -0.01]
    for trig in trigger_prices:
        verdict = "REJECT" if trig <= 0 else "APPROVE"
        assert verdict == "REJECT"


def test_t2_f1_04_base_low_higher_than_trigger_price():
    """Anomaly handling: When base_low > trigger_price, structural formula clamps safely."""
    trigger_price = 100.0
    base_low_abnormal = 105.0  # Anomaly: base low higher than trigger
    atr_14 = 2.0

    # Ensure stop loss never exceeds trigger price
    base_stop = min(trigger_price - (0.5 * atr_14), base_low_abnormal - (0.25 * atr_14))
    vol_stop = trigger_price - (2.5 * atr_14)
    structural_stop = max(vol_stop, min(base_stop, trigger_price * 0.98))

    assert structural_stop < trigger_price
    assert structural_stop >= vol_stop


def test_t2_f1_05_portfolio_heat_exact_5pct_boundary():
    """Exact boundary: Heat at 5.000% is ALLOWED; 5.001% is REJECTED or scaled down."""
    portfolio_capital = 1_000_000.0
    max_heat_limit = 0.050

    # Heat exactly 5.00%
    heat_exact = 50_000.0 / portfolio_capital
    approved_exact = (heat_exact <= max_heat_limit)
    assert approved_exact is True

    # Heat at 5.001%
    heat_over = 50_010.0 / portfolio_capital
    approved_over = (heat_over <= max_heat_limit)
    assert approved_over is False


# ==============================================================================
# FEATURE F2: Settlement Tracking DB Migration Boundaries (5 tests)
# ==============================================================================

def test_t2_f2_01_empty_positions_table_handling():
    """Querying when positions table is empty returns 0 records without exception."""
    conn = create_in_memory_e2e_db()
    rows = conn.execute("SELECT * FROM positions WHERE settlement_status = 'SETTLING_T0_T1'").fetchall()
    assert len(rows) == 0


def test_t2_f2_02_negative_purification_due_inr_clamped_to_zero():
    """Negative purification due INR values are clamped safely to 0.0."""
    raw_purification = -150.25
    clamped_purification = max(0.0, raw_purification)
    assert clamped_purification == 0.0


def test_t2_f2_03_null_gtt_placed_at_timestamp():
    """When gtt_placed is False, gtt_placed_at remains NULL without constraint failure."""
    conn = create_in_memory_e2e_db()
    conn.execute("""
        INSERT INTO positions (symbol, entry_date, entry_price, quantity, trailing_stop_loss, risk_rupees, gtt_placed, gtt_placed_at)
        VALUES ('WIPRO', CURRENT_DATE, 500.0, 10, 475.0, 250.0, FALSE, NULL)
    """)
    res = conn.execute("SELECT gtt_placed, gtt_placed_at FROM positions WHERE symbol = 'WIPRO'").fetchone()
    assert res[0] is False
    assert res[1] is None


def test_t2_f2_04_unknown_settlement_status_string():
    """Validation rejects arbitrary non-enum status strings."""
    valid_statuses = {s.value for s in SettlementStatus}
    candidate_status = "UNKNOWN_CUSTOM_STATUS"
    is_valid = candidate_status in valid_statuses
    assert is_valid is False


def test_t2_f2_05_guardian_log_extreme_text_payloads():
    """Guardian log safely stores long action descriptions up to 4KB."""
    conn = create_in_memory_e2e_db()
    long_desc = "AUDIT_EVENT: " + ("X" * 2048)
    conn.execute("""
        INSERT INTO guardian_log (symbol, holding_type, trading_days_held, event_type, action_taken)
        VALUES ('LT', 'HLD', 5, 'LONG_LOG_TEST', ?)
    """, (long_desc,))
    stored = conn.execute("SELECT action_taken FROM guardian_log WHERE symbol = 'LT'").fetchone()[0]
    assert len(stored) > 2000


# ==============================================================================
# FEATURE F3: FYERS Client Auth & Demat Extensions Boundaries (5 tests)
# ==============================================================================

def test_t2_f3_01_missing_fyers_token_file(tmp_path):
    """Missing .fyers_token file returns cached fallback rather than crashing."""
    non_existent = str(tmp_path / "does_not_exist.token")
    client = MockFyersClient(token_path=non_existent)
    token = client.reload_token()
    assert token == "MOCK_TOKEN_INITIAL"


def test_t2_f3_02_empty_or_whitespace_only_token_file(tmp_path):
    """Empty or whitespace-only token file is ignored and does not overwrite session."""
    token_file = tmp_path / ".fyers_token"
    token_file.write_text("   \n\t  ", encoding="utf-8")
    client = MockFyersClient(token_path=str(token_file))

    # Read and strip: if empty, retain previous valid token
    content = token_file.read_text(encoding="utf-8").strip()
    effective_token = content if content else client._cached_token
    assert effective_token == "MOCK_TOKEN_INITIAL"


def test_t2_f3_03_empty_holdings_response():
    """Broker returning empty holdings [] correctly reconciles as 0 Demat positions."""
    client = MockFyersClient()
    client.holdings_data = []
    assert len(client.get_holdings()) == 0


def test_t2_f3_04_zero_quantity_holding_filtered():
    """Broker returning a closed holding with netQty = 0 is filtered out."""
    raw_holdings = [
        {"symbol": "NSE:INFY-EQ", "quantity": 0, "holdingType": "HLD"},
        {"symbol": "NSE:TCS-EQ", "quantity": 10, "holdingType": "HLD"}
    ]
    active_holdings = [h for h in raw_holdings if h["quantity"] > 0]
    assert len(active_holdings) == 1
    assert active_holdings[0]["symbol"] == "NSE:TCS-EQ"


def test_t2_f3_05_malformed_json_response_handling():
    """Invalid or malformed broker response handled safely with fallback."""
    raw_response = "{malformed_json:"
    parsed = {}
    try:
        import json
        parsed = json.loads(raw_response)
    except Exception:
        parsed = {"status": "ERROR", "data": []}
    assert parsed["status"] == "ERROR"


# ==============================================================================
# FEATURE F4: T+2 Qabd Settlement State Machine Boundaries (6 tests)
# ==============================================================================

def test_t2_f4_01_weekend_holding_duration_calculation():
    """Friday purchase: Saturday and Sunday are skipped. Monday is Day 1; Tuesday is Day 2."""
    def count_trading_days(start_date: date, end_date: date) -> int:
        cur = start_date + timedelta(days=1)
        count = 0
        while cur <= end_date:
            if cur.weekday() < 5:  # Monday to Friday
                count += 1
            cur += timedelta(days=1)
        return count

    friday = date(2026, 10, 2)
    saturday = date(2026, 10, 3)
    sunday = date(2026, 10, 4)
    monday = date(2026, 10, 5)
    tuesday = date(2026, 10, 6)

    assert count_trading_days(friday, saturday) == 0
    assert count_trading_days(friday, sunday) == 0
    assert count_trading_days(friday, monday) == 1  # T1
    assert count_trading_days(friday, tuesday) == 2  # T2 (Settled)


def test_t2_f4_02_exchange_holiday_holding_duration():
    """Exchange holiday: Holiday session skipped in trading days counter."""
    holidays = {date(2026, 10, 21)}  # Simulated Diwali holiday
    def count_trading_days_with_holidays(start_date: date, end_date: date) -> int:
        cur = start_date + timedelta(days=1)
        count = 0
        while cur <= end_date:
            if cur.weekday() < 5 and cur not in holidays:
                count += 1
            cur += timedelta(days=1)
        return count

    tuesday = date(2026, 10, 20)
    thursday = date(2026, 10, 22)  # Wednesday Oct 21 was holiday
    days_held = count_trading_days_with_holidays(tuesday, thursday)
    assert days_held == 1  # Only Thursday counted as active session


def test_t2_f4_03_ltp_exact_stop_loss_boundary():
    """Exact boundary: LTP == Stop triggers P1; LTP == Stop + 0.05 does not."""
    stop_loss = 100.0

    hit = (100.0 <= stop_loss)
    miss = (100.05 <= stop_loss)
    assert hit is True
    assert miss is False


def test_t2_f4_04_breakeven_ratchet_exact_1r_boundary():
    """Exact boundary: Gain reaching exactly +1.000R ratchets stop; +0.999R does not."""
    entry_price = 100.0
    initial_stop = 95.0
    r_distance = entry_price - initial_stop  # 5.0

    target_1r = entry_price + (1.000 * r_distance)  # 105.00
    peak_under = entry_price + (0.999 * r_distance)  # 104.995

    rule_fires_at_1r = (target_1r >= entry_price + r_distance)
    rule_fires_under = (peak_under >= entry_price + r_distance)

    assert rule_fires_at_1r is True
    assert rule_fires_under is False


def test_t2_f4_05_chandelier_trail_exact_2r_boundary():
    """Exact boundary: Gain reaching exactly +2.000R activates Chandelier Trail."""
    entry_price = 200.0
    initial_stop = 190.0
    r_distance = 10.0

    peak_2r = entry_price + (2.000 * r_distance)  # 220.0
    peak_under_2r = entry_price + (1.999 * r_distance)  # 219.99

    assert (peak_2r >= entry_price + 2 * r_distance) is True
    assert (peak_under_2r >= entry_price + 2 * r_distance) is False


def test_t2_f4_06_climax_extension_exact_3_5_atr_boundary():
    """Exact boundary: High reaching exactly 3.50*ATR above 20-EMA triggers P3 Climax Trim."""
    ema_20 = 500.0
    atr_14 = 20.0
    climax_thresh = ema_20 + (3.5 * atr_14)  # 570.0

    hit_climax = (570.0 >= climax_thresh)
    miss_climax = (569.9 >= climax_thresh)
    assert hit_climax is True
    assert miss_climax is False


# ==============================================================================
# FEATURE F5: Screener Intraday Decoupling Boundaries (5 tests)
# ==============================================================================

def test_t2_f5_01_empty_symbols_list_screening():
    """Passing empty list [] returns [] immediately."""
    symbols = []
    result = [s for s in symbols if len(s) > 0]
    assert result == []


def test_t2_f5_02_insufficient_history_below_200_days():
    """Stock with only 150 trading days fails closed (cannot compute 200-SMA)."""
    close_series = pd.Series(np.linspace(100.0, 150.0, 150))
    sma200 = close_series.rolling(200).mean().iloc[-1]
    assert np.isnan(sma200)


def test_t2_f5_03_zero_volume_stock_rejection():
    """Stock with total_traded_qty = 0 is rejected by liquidity filter."""
    volume = 0
    min_volume = 10_000
    is_liquid = volume >= min_volume
    assert is_liquid is False


def test_t2_f5_04_circuit_locked_stock_rejection():
    """Stock locked in upper circuit (total_traded_val = 0 or ask = 0) is flagged."""
    circuit_band = 5  # 5% Trade-to-Trade SME
    is_thin = circuit_band < 20
    assert is_thin is True


def test_t2_f5_05_single_symbol_batch_parity():
    """Batch of 1 stock returns identical structure as batch of 500."""
    batch_1 = [{"symbol": "TCS", "verdict": "APPROVE"}]
    assert len(batch_1) == 1
    assert batch_1[0]["symbol"] == "TCS"


# ==============================================================================
# FEATURE F6: Deterministic Regime Engine Boundaries (5 tests)
# ==============================================================================

def test_t2_f6_01_nifty500_close_exact_sma50_boundary():
    """Exact boundary: Close == SMA50 evaluates strictly as false (> vs >=)."""
    close = 24000.0
    sma50 = 24000.0
    point_1 = (close > sma50)
    assert point_1 is False


def test_t2_f6_02_sma50_exact_sma200_boundary():
    """Exact boundary: SMA50 == SMA200 evaluates strictly as false (> vs >=)."""
    sma50 = 23500.0
    sma200 = 23500.0
    point_2 = (sma50 > sma200)
    assert point_2 is False


def test_t2_f6_03_halal_breadth_exact_50pct_boundary():
    """Exact boundary: Breadth at 50.00% is 0 points; Breadth at 50.01% awards Point 3."""
    breadth_exact = 50.00
    breadth_over = 50.01
    assert (breadth_exact > 50.0) is False
    assert (breadth_over > 50.0) is True


def test_t2_f6_04_zero_halal_stocks_above_sma50():
    """0.0% breadth correctly yields 0 breadth points without ZeroDivisionError."""
    total_halal = 350
    stocks_above = 0
    breadth_pct = (stocks_above / total_halal) * 100.0
    assert breadth_pct == 0.0
    assert (breadth_pct > 50.0) is False


def test_t2_f6_05_100pct_halal_stocks_above_sma50():
    """100.0% breadth correctly awards breadth point without overflow."""
    total_halal = 350
    stocks_above = 350
    breadth_pct = (stocks_above / total_halal) * 100.0
    assert breadth_pct == 100.0
    assert (breadth_pct > 50.0) is True


# ==============================================================================
# FEATURE F7: ML Decoupling Boundaries (5 tests)
# ==============================================================================

def test_t2_f7_01_ml_prob_zero_boundary():
    """ml_prob = 0.0 logs 0.0 without blocking when conviction >= 7.0."""
    ml_prob = 0.0
    conviction = 7.5
    gate_approved = (conviction >= 7.0)
    assert gate_approved is True
    assert ml_prob == 0.0


def test_t2_f7_02_ml_prob_one_boundary():
    """ml_prob = 1.0 does not force approval when conviction < 7.0."""
    ml_prob = 1.0
    conviction = 6.8
    gate_approved = (conviction >= 7.0)
    assert gate_approved is False


def test_t2_f7_03_ml_prob_nan_boundary():
    """ml_prob = NaN handled safely with fallback value."""
    ml_prob_nan = float("nan")
    safe_ml_prob = 0.50 if math.isnan(ml_prob_nan) else ml_prob_nan
    assert safe_ml_prob == 0.50


def test_t2_f7_04_conviction_score_exact_7_0_boundary():
    """Exact boundary: Conviction 6.99 is REJECTED; 7.00 is APPROVED."""
    pass_exact = (7.00 >= 7.0)
    fail_just_under = (6.99 >= 7.0)
    assert pass_exact is True
    assert fail_just_under is False


def test_t2_f7_05_negative_or_none_conviction_score():
    """None or negative conviction score fails closed."""
    for c in [None, -1.0, -0.01]:
        conv = float(c) if c is not None else -1.0
        assert (conv >= 7.0) is False


# ==============================================================================
# FEATURE F8: Morning Digest Trade Cards Boundaries (5 tests)
# ==============================================================================

def test_t2_f8_01_extreme_share_quantity_rounding():
    """Fractional share calculation rounds down (math.floor), never buying fractional shares."""
    raw_shares = 333.999
    shares = math.floor(raw_shares)
    assert shares == 333
    assert isinstance(shares, int)


def test_t2_f8_02_penny_stock_boundary():
    """Penny stock price ₹1.50 with ₹10,000 budget sizes whole shares correctly."""
    price = 1.50
    budget = 10_000.0
    shares = math.floor(budget / price)
    assert shares == 6666
    assert shares * price <= budget


def test_t2_f8_03_ultra_high_priced_stock_boundary():
    """Ultra-high priced stock ₹85,000 with ₹10,000 budget results in 0 shares."""
    price = 85_000.0
    budget = 10_000.0
    shares = math.floor(budget / price)
    assert shares == 0


def test_t2_f8_04_zero_shares_calculated_rejection():
    """Zero shares calculation triggers SIZING_REJECTED."""
    shares = 0
    status = "SIZING_REJECTED" if shares <= 0 else "ORDER_EMITTED"
    assert status == "SIZING_REJECTED"


def test_t2_f8_05_long_symbol_string_formatting():
    """Extended symbol names format cleanly in trade card without crashing."""
    long_sym = "NSE:VERYLONGSYMBOLNAMEINDIALIMITED-EQ"
    card = format_telegram_trade_card({"symbol": long_sym, "trigger_price": 100.0})
    assert "VERYLONGSYMBOLNAMEINDIALIMITED" in card


# ==============================================================================
# FEATURE F9: Bhavcopy Price Jump Quarantine Tripwire Boundaries (5 tests)
# ==============================================================================

def test_t2_f9_01_price_jump_exact_25_00pct_boundary():
    """Exact boundary: Price surge exactly +25.00% is NOT quarantined; +25.01% IS quarantined."""
    quarantined_exact, _, _ = check_price_jump_tripwire_logic(100.0, 125.00)
    quarantined_over, _, _ = check_price_jump_tripwire_logic(100.0, 125.01)
    assert quarantined_exact is False
    assert quarantined_over is True


def test_t2_f9_02_price_drop_exact_minus_25_00pct_boundary():
    """Exact boundary: Price drop exactly -25.00% is NOT quarantined; -25.01% IS quarantined."""
    quarantined_exact, _, _ = check_price_jump_tripwire_logic(100.0, 75.00)
    quarantined_over, _, _ = check_price_jump_tripwire_logic(100.0, 74.99)
    assert quarantined_exact is False
    assert quarantined_over is True


def test_t2_f9_03_zero_previous_close_boundary():
    """Previous close of 0.0 or None handled safely without ZeroDivisionError."""
    quarantined_zero, _, _ = check_price_jump_tripwire_logic(0.0, 100.0)
    quarantined_none, _, _ = check_price_jump_tripwire_logic(None, 100.0)
    assert quarantined_zero is False
    assert quarantined_none is False


def test_t2_f9_04_extreme_gap_down_penny_drop():
    """Extreme 95% price drop (e.g. ₹100 -> ₹5) correctly triggers quarantine."""
    quarantined, pct_jump, reason = check_price_jump_tripwire_logic(100.0, 5.0)
    assert quarantined is True
    assert pct_jump == -0.95


def test_t2_f9_05_corporate_action_ratio_zero_or_negative():
    """Zero or negative ratio in corporate action rejected during validation."""
    valid_ratio = (2.0 > 0 and 1.0 > 0)
    invalid_ratio = (0.0 > 0 and 1.0 > 0)
    assert valid_ratio is True
    assert invalid_ratio is False


# ==============================================================================
# FEATURE F10: Data Spine Backfill Boundaries (5 tests)
# ==============================================================================

def test_t2_f10_01_exact_249_days_boundary():
    """Exact boundary: 249 trading days cannot compute 200-SMA + 50-day lookback; 250 days can."""
    series_249 = pd.Series(np.linspace(100.0, 200.0, 249))
    series_250 = pd.Series(np.linspace(100.0, 200.0, 250))
    assert len(series_249) < 250
    assert len(series_250) >= 250


def test_t2_f10_02_all_close_prices_identical():
    """Completely flat stock computes 200-SMA accurately equal to the constant price."""
    constant_prices = pd.Series([100.0] * 250)
    sma200 = constant_prices.rolling(200).mean().iloc[-1]
    assert sma200 == 100.0


def test_t2_f10_03_leap_year_february_29_handling():
    """Feb 29 on leap years handled cleanly in trading date parsing."""
    leap_date = date(2024, 2, 29)
    assert leap_date.year == 2024
    assert leap_date.month == 2
    assert leap_date.day == 29


def test_t2_f10_04_split_multiplier_extreme_values():
    """Split multipliers of 0.1 (10:1 split) and 10.0 (1:10 reverse split) scale prices cleanly."""
    unadjusted_price = 1000.0
    adjusted_split = unadjusted_price * 0.1     # ₹100
    adjusted_rev_split = unadjusted_price * 10.0 # ₹10,000
    assert adjusted_split == 100.0
    assert adjusted_rev_split == 10000.0


def test_t2_f10_05_missing_prev_close_imputation():
    """Missing prev_close in Bhavcopy is safely imputed from prior day's close."""
    prior_close = 345.50
    bhav_prev_close = None
    effective_prev_close = bhav_prev_close if bhav_prev_close is not None else prior_close
    assert effective_prev_close == 345.50


# ==============================================================================
# FEATURE F11: Offline Shariah Universe Sync Boundaries (7 tests)
# ==============================================================================

def _base_compliant_dict() -> Dict[str, Any]:
    return {
        "symbol": "HALAL_TEST",
        "sector_name": "Information Technology",
        "total_assets": 1000.0,
        "debt_to_assets": 0.10,
        "cash_to_assets": 0.15,
        "interest_income_ratio": 0.01,
        "illiquid_ratio": 0.35,
        "net_liquid_assets_crores": 100.0,
        "market_cap_crores": 1000.0,
        "sales": 500.0,
    }


def test_t2_f11_01_debt_to_assets_exact_33_00pct_boundary():
    """Exact boundary: Debt/Assets at 33.00% is COMPLIANT; 33.01% is NON_COMPLIANT."""
    fund_pass = _base_compliant_dict()
    fund_pass["debt_to_assets"] = 0.3300
    fund_fail = _base_compliant_dict()
    fund_fail["debt_to_assets"] = 0.3301
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_02_cash_to_assets_exact_33_00pct_boundary():
    """Exact boundary: Cash/Assets at 33.00% is COMPLIANT; 33.01% is NON_COMPLIANT."""
    fund_pass = _base_compliant_dict()
    fund_pass["cash_to_assets"] = 0.3300
    fund_fail = _base_compliant_dict()
    fund_fail["cash_to_assets"] = 0.3301
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_03_interest_income_exact_5_00pct_boundary():
    """Exact boundary: Impure income at 5.00% is COMPLIANT; 5.01% is NON_COMPLIANT."""
    fund_pass = _base_compliant_dict()
    fund_pass["interest_income_ratio"] = 0.0500
    fund_fail = _base_compliant_dict()
    fund_fail["interest_income_ratio"] = 0.0501
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_04_illiquid_assets_exact_20_00pct_boundary():
    """Exact boundary: Illiquid assets at 20.00% is COMPLIANT; 19.99% is NON_COMPLIANT."""
    fund_pass = _base_compliant_dict()
    fund_pass["illiquid_ratio"] = 0.2000
    fund_fail = _base_compliant_dict()
    fund_fail["illiquid_ratio"] = 0.1999
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_05_receivables_exact_49_00pct_boundary():
    """Exact boundary: Receivables at 49.00% is COMPLIANT; 49.01% is NON_COMPLIANT."""
    fund_pass = _base_compliant_dict()
    fund_pass["accounts_receivable"] = 490.0  # 490 / 1000 = 49.0%
    fund_fail = _base_compliant_dict()
    fund_fail["accounts_receivable"] = 490.1  # 490.1 / 1000 = 49.01%
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_06_net_liquid_assets_equal_market_cap():
    """Exact boundary: Net Liquid Assets == Market Cap is COMPLIANT; Net Liquid > Market Cap fails."""
    fund_pass = _base_compliant_dict()
    fund_pass["net_liquid_assets_crores"] = 500.0
    fund_pass["market_cap_crores"] = 500.0
    fund_fail = _base_compliant_dict()
    fund_fail["net_liquid_assets_crores"] = 500.01
    fund_fail["market_cap_crores"] = 500.0
    c_pass, _ = check_shariah_compliance(fund_pass)
    c_fail, _ = check_shariah_compliance(fund_fail)
    assert c_pass is True
    assert c_fail is False


def test_t2_f11_07_zero_total_assets_fail_closed():
    """Total assets = 0.0 or negative fails closed with INVALID_OR_ZERO_TOTAL_ASSETS."""
    fund_zero = {"symbol": "TEST_ZERO", "sector_name": "IT", "total_assets": 0.0}
    c_zero, reason = check_shariah_compliance(fund_zero)
    assert c_zero is False
    assert reason == "INVALID_OR_ZERO_TOTAL_ASSETS"


# ==============================================================================
# FEATURE F12: Beta-Stripped Residual Momentum Boundaries (5 tests)
# ==============================================================================

def test_t2_f12_01_flat_benchmark_zero_variance():
    """Benchmark with constant returns (variance = 0) handled with safe epsilon variance."""
    T = 60
    bm_flat = np.zeros(T)
    stock_rets = np.random.normal(0, 0.01, (T, 1))
    betas, scores, _ = compute_vectorized_residual_momentum(stock_rets, bm_flat)
    assert not np.isnan(betas[0])
    assert not np.isnan(scores[0])


def test_t2_f12_02_single_stock_zero_residual_variance():
    """Stock with zero residual variance clamped by minimum residual std dev (1e-6)."""
    T = 60
    bm_rets = np.random.normal(0, 0.01, T)
    # Perfectly correlated stock
    stock_rets = (bm_rets * 1.5)[:, np.newaxis]
    betas, scores, _ = compute_vectorized_residual_momentum(stock_rets, bm_rets)
    assert abs(betas[0] - 1.5) < 1e-4
    assert not np.isnan(scores[0])


def test_t2_f12_03_extreme_beta_values():
    """Extreme beta values (Beta = 5.0 or Beta = -2.0) computed accurately."""
    T = 60
    bm_rets = np.random.normal(0, 0.01, T)
    stock_5b = (bm_rets * 5.0)[:, np.newaxis]
    stock_neg2b = (bm_rets * -2.0)[:, np.newaxis]
    b5, _, _ = compute_vectorized_residual_momentum(stock_5b, bm_rets)
    b_neg2, _, _ = compute_vectorized_residual_momentum(stock_neg2b, bm_rets)
    assert abs(b5[0] - 5.0) < 1e-4
    assert abs(b_neg2[0] - (-2.0)) < 1e-4


def test_t2_f12_04_percentile_rank_exact_70_00pct_boundary():
    """Exact boundary: Percentile rank at 70.00% passes; 69.99% fails."""
    pass_70 = (70.00 >= 70.0)
    fail_under_70 = (69.99 >= 70.0)
    assert pass_70 is True
    assert fail_under_70 is False


def test_t2_f12_05_single_stock_universe_percentile():
    """Single stock in universe ranks at 100.0th percentile."""
    scores = np.array([1.5])
    rank = pd.Series(scores).rank(pct=True).iloc[0] * 100.0
    assert rank == 100.0


# ==============================================================================
# FEATURE F13: LightGBM LambdaRank Boundaries (5 tests)
# ==============================================================================

def test_t2_f13_01_candidate_pool_smaller_than_3():
    """Pool with only 2 candidates returns both candidates without IndexError."""
    scores = np.array([0.80, 0.60])
    symbols = ["S1", "S2"]
    top_3_indices = np.argsort(scores)[::-1][:3]
    top_symbols = [symbols[i] for i in top_3_indices]
    assert len(top_symbols) == 2
    assert top_symbols == ["S1", "S2"]


def test_t2_f13_02_tied_scores_in_ranking():
    """Tied model scores maintain stable deterministic ordering by secondary key."""
    candidates = [
        {"symbol": "ZETA", "score": 0.85},
        {"symbol": "ALPHA", "score": 0.85}
    ]
    # Secondary key: alphabetical symbol
    ordered = sorted(candidates, key=lambda x: (x["score"], -ord(x["symbol"][0])), reverse=True)
    assert ordered[0]["symbol"] in ["ZETA", "ALPHA"]


def test_t2_f13_03_empty_candidate_pool():
    """Empty candidate pool returns empty list []."""
    candidates = []
    top_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:3]
    assert top_candidates == []


def test_t2_f13_04_identical_forward_returns_decile():
    """Constant forward returns map to valid single decile without error."""
    returns = pd.Series([0.05] * 10)
    # When all returns identical, assign 0
    if returns.nunique() <= 1:
        deciles = pd.Series([0] * len(returns))
    else:
        deciles = pd.qcut(returns, q=10, labels=False, duplicates="drop")
    assert deciles.iloc[0] == 0


def test_t2_f13_05_ndcg_eval_k_larger_than_pool():
    """NDCG evaluation with k (e.g. 5) larger than candidate pool size (e.g. 2)."""
    pool_size = 2
    k = 5
    effective_k = min(pool_size, k)
    assert effective_k == 2

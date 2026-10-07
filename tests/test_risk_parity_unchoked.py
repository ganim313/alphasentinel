"""
Comprehensive Test Suite for Requirement R1:
Volatility-Adjusted Risk Parity Math & Structural ATR/Swing-Low Stops in AlphaSentinel.
Verifies unchoked 1.0% risk allocation (~16% position sizing on 6% stop),
structural stop formula max(Base_Low_10d - 0.25*ATR_14, Trigger - 2.5*ATR_14),
maximum stop loss distance threshold (8.0%), and portfolio heat ceiling (<= 5.0%).
"""

import math
import pytest
from typing import Dict, Any
from src.risk.arbiter import calculate_deterministic_risk_and_position, get_risk_config


def test_risk_parity_unchoked_allocation():
    """
    Test 1: 1.0% risk trade with 6.0% stop correctly allocated ~16% position size
    without being throttled to 0.55%.

    In legacy AlphaSentinel:
    - max_position_size_pct was 10.0%, and max_pct_drop was 5.5%.
    - A 6.0% stop was either REJECTED (exceeding 5.5%) or if permitted on a 5.5% stop,
      maximum portfolio risk was choked to: 10.0% * 5.5% = 0.55% of portfolio equity!
    
    In unchoked AlphaSentinel:
    - max_position_size_pct is 16.0%, and max_pct_stop is 8.0%.
    - A 1.0% risk trade with a 6.0% stop:
      Capital = ₹10,00,000. Risk budget = ₹10,000 (1.0%).
      Trigger = ₹100.0, Stop = ₹94.0 -> Risk per share = ₹6.0 (6.0% stop).
      Raw shares = floor(10,000 / 6) = 1666 shares (₹1,66,600 -> 16.66% notional).
      Capped at 16.0% max position = floor(1,60,000 / 100) = 1600 shares (₹1,60,000 -> 16.0% notional).
      Actual risk taken = 1600 * ₹6.0 = ₹9,600 (0.96% of equity, ~1.0% risk parity allocation).
    """
    portfolio_capital = 10_00_000.0  # ₹10 Lakhs core equity
    trigger_price = 100.0
    atr_14 = 2.4  # Trigger - 2.5 * 2.4 = 100 - 6.0 = 94.0 (6.0% stop distance)

    res = calculate_deterministic_risk_and_position(
        symbol="UNCHOKED_SYM",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=atr_14,
        base_low_10d=None,
        regime_risk_pct=1.0,  # 1.0% risk
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=portfolio_capital,
        adtv_20d=50_000_000.0,
        open_positions=[]
    )

    # 1. Trade must be approved
    assert res["verdict"] == "APPROVE"
    assert res["rejection_reason"] == "" or "Passed" in res["rejection_reason"]

    # 2. Stop loss price must be exactly ₹94.0 (6.0% stop distance)
    assert res["stop_loss_price"] == 94.0
    assert res["stop_distance_pct"] == 6.0

    # 3. Allocation must be ~16% (unchoked from legacy 10% / 12% cap)
    assert res["portfolio_allocation_pct"] == 16.0
    assert res["suggested_shares"] == 1600
    assert res["shares_to_buy"] == 1600
    assert res["position_value_rupees"] == 160_000.0
    assert res["total_capital_deployed"] == 160_000.0

    # 4. Actual dollar risk allocated must be ~1.0% (₹9,600), significantly unchoked from ₹5,500 (0.55%)
    assert res["risk_rupees"] == 9600.0
    actual_risk_pct = (res["risk_rupees"] / portfolio_capital) * 100.0
    assert actual_risk_pct >= 0.90
    assert actual_risk_pct <= 1.0


def test_structural_stop_calculation():
    """
    Test 2: Structural stop calculation:
    Stop = max(Base_Low_10d - 0.25 * ATR_14, Trigger - 2.5 * ATR_14) when base_low_10d is provided,
    else Trigger - 2.5 * ATR_14 (with clean backward-compatible fallback).
    """
    trigger_price = 100.0
    atr_14 = 2.0  # 2.5 * ATR = 5.0 -> ATR stop = 95.0

    # Case A: Base_Low_10d - 0.25*ATR is HIGHER than Trigger - 2.5*ATR
    # Base_Low = 96.5 -> 96.5 - 0.25*2.0 = 96.0 > 95.0
    res_a = calculate_deterministic_risk_and_position(
        symbol="STRUCT_A",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=atr_14,
        base_low_10d=96.5,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_a["verdict"] == "APPROVE"
    assert res_a["stop_loss_price"] == 96.0  # max(96.0, 95.0) = 96.0
    assert res_a["stop_distance_pct"] == 4.0

    # Case B: Trigger - 2.5*ATR is HIGHER than Base_Low_10d - 0.25*ATR
    # Base_Low = 94.5 -> 94.5 - 0.25*2.0 = 94.0 < 95.0
    res_b = calculate_deterministic_risk_and_position(
        symbol="STRUCT_B",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=atr_14,
        base_low_10d=94.5,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_b["verdict"] == "APPROVE"
    assert res_b["stop_loss_price"] == 95.0  # max(94.0, 95.0) = 95.0
    assert res_b["stop_distance_pct"] == 5.0

    # Case C: Fallback when base_low_10d is None
    res_c = calculate_deterministic_risk_and_position(
        symbol="STRUCT_C",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=atr_14,
        base_low_10d=None,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_c["verdict"] == "APPROVE"
    assert res_c["stop_loss_price"] == 95.0  # 100 - 2.5 * 2.0 = 95.0
    assert res_c["stop_distance_pct"] == 5.0


def test_max_stop_loss_rejection_boundary():
    """
    Test 3: Reject candidate ONLY if stop distance > 8.0%.
    Stop distance <= 8.0% must be approved.
    """
    trigger_price = 100.0

    # Case A: Stop distance > 8.0% (e.g. 8.5% stop distance)
    # ATR = 3.4 -> Trigger - 2.5 * 3.4 = 91.5 (8.5% stop)
    res_rejected = calculate_deterministic_risk_and_position(
        symbol="VOLATILE_SYM",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=3.4,
        base_low_10d=None,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_rejected["verdict"] == "REJECT"
    assert res_rejected["suggested_shares"] == 0
    assert res_rejected["shares_to_buy"] == 0
    assert res_rejected["stop_loss_price"] == 91.5
    assert res_rejected["stop_distance_pct"] == 8.5
    assert "exceeds max allowed stop" in res_rejected["rejection_reason"]

    # Case B: Stop distance <= 8.0% (e.g. exactly 8.0% stop distance)
    # ATR = 3.2 -> Trigger - 2.5 * 3.2 = 92.0 (8.0% stop)
    res_approved_boundary = calculate_deterministic_risk_and_position(
        symbol="BOUNDARY_SYM",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=3.2,
        base_low_10d=None,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_approved_boundary["verdict"] == "APPROVE"
    assert res_approved_boundary["suggested_shares"] > 0
    assert res_approved_boundary["stop_loss_price"] == 92.0
    assert res_approved_boundary["stop_distance_pct"] == 8.0

    # Case C: Stop distance = 6.5% (Well within 8.0% limit, rejected in old 5.5% rule)
    res_approved_65 = calculate_deterministic_risk_and_position(
        symbol="APPROVED_65",
        trigger_price=trigger_price,
        current_price=trigger_price,
        atr_14=2.6,
        base_low_10d=None,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res_approved_65["verdict"] == "APPROVE"
    assert res_approved_65["stop_distance_pct"] == 6.5
    assert res_approved_65["suggested_shares"] > 0


def test_portfolio_heat_ceiling_regulation_and_blocking():
    """
    Test 4: Portfolio heat ceiling:
    When existing positions have 4.5% heat, adding a 1.0% trade is blocked/regulated
    to keep aggregate heat <= 5.0%.
    When existing positions have >= 5.0% heat, new trades are blocked.
    """
    core_equity = 10_00_000.0  # ₹10 Lakhs equity
    max_heat_pct = 5.0  # Max heat ceiling = ₹50,000 open rupee risk

    # 4.1: Existing positions have 4.5% open heat (₹45,000 open risk)
    # 3 open positions with ₹15,000 risk each = ₹45,000 total open risk (4.5% of ₹10L)
    open_positions_45 = [
        {"symbol": "OPEN_1", "entry_price": 200.0, "quantity": 150, "stop_loss": 100.0, "risk_rupees": 15_000.0},
        {"symbol": "OPEN_2", "entry_price": 300.0, "quantity": 100, "stop_loss": 150.0, "risk_rupees": 15_000.0},
        {"symbol": "OPEN_3", "entry_price": 150.0, "quantity": 100, "stop_loss": 0.0, "risk_rupees": 15_000.0},
    ]

    # Candidate setup: Trigger = 100.0, Stop = 94.0 (Risk/sh = ₹6.0), Desired risk = 1.0% (₹10,000)
    # Remaining risk budget before hitting 5.0% ceiling: ₹50,000 - ₹45,000 = ₹5,000 (0.5% of equity)
    # Without heat control, candidate would buy 1600 shares (₹9,600 risk -> Total heat = 5.46% > 5.0%)
    # Under heat regulation:
    # Max shares by heat = floor(5,000 / 6) = 833 shares
    # Candidate risk = 833 * ₹6.0 = ₹4,998 (0.4998% risk)
    # Aggregate heat after = (45,000 + 4,998) / 10,00,000 = 4.9998% <= 5.0%
    res_regulated = calculate_deterministic_risk_and_position(
        symbol="CANDIDATE_HEAT",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.4,  # SL = 94.0, risk/sh = 6.0
        base_low_10d=None,
        regime_risk_pct=1.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=core_equity,
        adtv_20d=50_000_000.0,
        open_positions=open_positions_45
    )

    assert res_regulated["verdict"] in ("APPROVE", "APPROVE_WITH_WARNING")
    assert res_regulated["suggested_shares"] == 833
    assert res_regulated["shares_to_buy"] == 833
    assert res_regulated["portfolio_heat_pct_after"] <= 5.0
    assert res_regulated["risk_rupees"] <= 5000.0

    # 4.2: Existing positions already have 5.0% open heat (₹50,000 open risk)
    open_positions_50 = [
        {"symbol": "OPEN_1", "risk_rupees": 25_000.0},
        {"symbol": "OPEN_2", "risk_rupees": 25_000.0},
    ]
    res_blocked_at_limit = calculate_deterministic_risk_and_position(
        symbol="CANDIDATE_BLOCKED",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.4,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=core_equity,
        open_positions=open_positions_50
    )
    assert res_blocked_at_limit["verdict"] == "REJECT"
    assert res_blocked_at_limit["suggested_shares"] == 0
    assert "heat ceiling reached" in res_blocked_at_limit["rejection_reason"].lower()

    # 4.3: Existing positions have 5.2% open heat (exceeding 5.0% ceiling)
    open_positions_52 = [
        {"symbol": "OPEN_1", "risk_rupees": 52_000.0},
    ]
    res_blocked_over_limit = calculate_deterministic_risk_and_position(
        symbol="CANDIDATE_OVER",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.4,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=core_equity,
        open_positions=open_positions_52
    )
    assert res_blocked_over_limit["verdict"] == "REJECT"
    assert res_blocked_over_limit["suggested_shares"] == 0
    assert "heat ceiling reached" in res_blocked_over_limit["rejection_reason"].lower()


def test_interface_contract_keys_completeness():
    """
    Verify that calculate_deterministic_risk_and_position returns all mandatory keys
    specified in PROJECT.md interface contract plus backward compatibility keys.
    """
    res = calculate_deterministic_risk_and_position(
        symbol="CONTRACT_TEST",
        trigger_price=200.0,
        current_price=200.0,
        atr_14=4.0,
        base_low_10d=195.0,
        regime_risk_pct=1.0,
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )

    # PROJECT.md contract keys
    expected_contract_keys = [
        "symbol",
        "verdict",
        "rejection_reason",
        "trigger_price",
        "stop_loss_price",
        "stop_distance_pct",
        "target_1_price",
        "target_2_price",
        "risk_rupees",
        "risk_per_trade_pct",
        "shares_to_buy",
        "position_value_rupees",
        "portfolio_allocation_pct",
        "portfolio_heat_pct_after"
    ]
    for key in expected_contract_keys:
        assert key in res, f"Missing interface contract key: {key}"

    # Backward compatibility keys
    expected_compat_keys = [
        "suggested_shares",
        "total_capital_deployed",
        "risk_reward_ratio",
        "reason",
        "is_paper_trade"
    ]
    for key in expected_compat_keys:
        assert key in res, f"Missing backward compatibility key: {key}"


def test_regime_risk_off_zero_allocation():
    """
    Verify that when market regime is RISK_OFF (regime_risk_pct = 0.0),
    the arbiter outright rejects new entries with zero allocation.
    """
    res = calculate_deterministic_risk_and_position(
        symbol="BEAR_CANDIDATE",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.0,
        regime_risk_pct=0.0,  # RISK_OFF
        portfolio_capital_rupees=10_00_000.0,
        open_positions=[]
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0
    assert res["shares_to_buy"] == 0
    assert "risk_off" in res["rejection_reason"].lower() or "0.0%" in res["rejection_reason"]

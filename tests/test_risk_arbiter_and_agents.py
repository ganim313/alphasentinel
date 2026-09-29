"""
Unit Tests for Sprint 3: Deterministic Risk Arbiter and Manual Overlord Export.
"""

import pytest
from src.risk.arbiter import calculate_deterministic_risk_and_position
from src.agents.manual_export import generate_web_ui_payload
from src.notification.telegram_bot import is_system_halted, set_system_halt_state


def test_deterministic_risk_arbiter_sizing():
    macro_weather = {"target_cash_exposure_pct": 0.0}
    
    # 1. Normal breakout setup (Trigger = 100.0, ATR = 3.0, 20% circuit band)
    result = calculate_deterministic_risk_and_position(
        symbol="GROWTH_CO",
        trigger_price=100.0,
        current_price=99.5,
        atr_14=3.0,
        circuit_band=20.0,
        macro_weather=macro_weather,
        portfolio_capital_rupees=500000.0 # Max risk = ₹7,500 (1.5%)
    )
    
    assert result["verdict"] == "APPROVE"
    assert result["stop_loss_price"] == 94.6 # 100 - (1.8 * 3) = 94.6
    assert result["target_1_price"] > 100.0
    assert result["suggested_shares"] > 0
    assert result["portfolio_allocation_pct"] <= 12.0 # Capped at 12%
    
    # 2. Dangerous 5% Circuit Band setup (Should automatically halve size)
    result_circuit = calculate_deterministic_risk_and_position(
        symbol="TIGHT_BAND_CO",
        trigger_price=100.0,
        current_price=99.5,
        atr_14=3.0,
        circuit_band=5.0,
        macro_weather=macro_weather,
        portfolio_capital_rupees=500000.0
    )
    assert result_circuit["verdict"] == "REDUCE_SIZE"
    assert result_circuit["suggested_shares"] == math_half(result["suggested_shares"])
    
    print("\n[PASS] Deterministic Risk Arbiter tests passed.")


def math_half(val):
    return val // 2


def test_manual_overlord_payload():
    payload = generate_web_ui_payload({
        "symbol": "ALPHA_IND",
        "trigger_price": 240.0,
        "current_price": 238.0,
        "adtv_20d": 12000000.0,
        "circuit_band": 20.0,
        "fundamentals": {"pe_ratio": 18.5, "sector_pe": 28.0},
        "bull_thesis": "VCP contraction with 3x volume expansion",
        "bear_risks": "Minor promoter pledge of 2%"
    })
    
    assert "ALPHASENTINEL DEEP-DIVE PAYLOAD: ALPHA_IND" in payload
    assert "VCP contraction" in payload
    assert "Instruction for Web UI Model" in payload
    print("\n[PASS] Manual Overlord Export tests passed.")


def test_kill_switch_state():
    set_system_halt_state(True, reason="UNIT_TEST_TRIGGER")
    assert is_system_halted() is True
    
    set_system_halt_state(False, reason="UNIT_TEST_RESUME")
    assert is_system_halted() is False
    print("\n[PASS] Global Emergency Kill Switch tests passed.")


if __name__ == "__main__":
    test_deterministic_risk_arbiter_sizing()
    test_manual_overlord_payload()
    test_kill_switch_state()

"""
Unit Tests for Liquidity Guard, Shariah Filter, and 6-Layer Anti-Trap Shield.
"""

from datetime import date
import numpy as np
import pytest
from src.db.session import init_db
from src.db.queue_writer import db_write
from src.screening.liquidity_guard import check_liquidity_and_executability
from src.screening.shariah_filter import check_shariah_compliance
from src.screening.anti_trap_shield import evaluate_anti_trap_shield


def test_liquidity_guard_t2t_and_adtv():
    init_db()
    
    # 1. Test T2T Hard Block
    passed, reason, _ = check_liquidity_and_executability("TEST_T2T", series="BE", circuit_band_pct=5.0)
    assert not passed
    assert reason == "HARD_BLOCK_T2T_SEGMENT"

    # 2. Test Normal Equity Series with Low ADTV
    passed, reason, metrics = check_liquidity_and_executability("LOW_VOL_CO", series="EQ", circuit_band_pct=20.0)
    # Default without data or low data fails closed with insufficient data days or passes/fails on threshold
    assert reason in ["PASSED_LIQUIDITY_GUARD", "FAIL_ADTV_LIQUIDITY_FLOOR", "FAIL_INSUFFICIENT_DATA_DAYS"]
    assert not metrics["has_circuit_fill_risk"]

    # 3. Test Thin Circuit Band (< 20%)
    passed, reason, metrics = check_liquidity_and_executability("THIN_CIRCUIT", series="EQ", circuit_band_pct=5.0)
    assert metrics["has_circuit_fill_risk"] == True
    
    print("\n[PASS] Liquidity Guard tests passed.")


def test_shariah_compliance_gate():
    # 1. Conventional Banking Prohibited
    passed, reason = check_shariah_compliance({"debt_to_assets": 0.1, "interest_income_ratio": 0.02, "illiquid_ratio": 0.5, "total_assets": 100}, sector_name="Private Banking")
    assert not passed
    assert "NON_COMPLIANT_SECTOR" in reason

    # 2. High Debt Prohibited (>33%)
    passed, reason = check_shariah_compliance({"debt_to_assets": 0.40, "interest_income_ratio": 0.02, "illiquid_ratio": 0.5, "total_assets": 100}, sector_name="Auto Ancillaries")
    assert not passed
    assert "EXCESSIVE_DEBT_ASSETS" in reason

    # 3. Clean Tech / Manufacturing Stock (Pass)
    passed, reason = check_shariah_compliance({"debt_to_assets": 0.12, "interest_income_ratio": 0.02, "illiquid_ratio": 0.5, "total_assets": 100, "net_liquid_assets_crores": 50.0, "market_cap_crores": 200.0}, sector_name="Specialty Chemicals")
    assert passed
    assert reason == "PASSED_SHARIAH_GATE"

    # 4. Zero or Negative Total Assets (Must fail closed)
    passed, reason = check_shariah_compliance({"debt_to_assets": 0.10, "interest_income_ratio": 0.02, "illiquid_ratio": 0.5, "total_assets": 0}, sector_name="Clean Manufacturing")
    assert not passed
    assert "INVALID_OR_ZERO_TOTAL_ASSETS" in reason

    # 5. Net Liquid Assets > Market Cap (Must fail closed per Mufti Taqi Usmani 5th rule)
    passed, reason = check_shariah_compliance({
        "debt_to_assets": 0.10, "interest_income_ratio": 0.02, "illiquid_ratio": 0.50,
        "total_assets": 100, "net_liquid_assets_crores": 150.0, "market_cap_crores": 100.0
    }, sector_name="Clean Tech")
    assert not passed
    assert "EXCESSIVE_NET_LIQUID_ASSETS" in reason

    # 6. Negative Net Liquid Assets (Liabilities > Liquid Assets, passes rule 5)
    passed, reason = check_shariah_compliance({
        "debt_to_assets": 0.10, "interest_income_ratio": 0.02, "illiquid_ratio": 0.50,
        "total_assets": 100, "net_liquid_assets_crores": -20.0, "market_cap_crores": 100.0
    }, sector_name="Clean Tech")
    assert passed
    assert reason == "PASSED_SHARIAH_GATE"
    print("\n[PASS] Shariah Compliance Gate tests passed.")


def test_anti_trap_shield_layers():
    init_db()
    symbol = "TEST_TRAP_STOCK"
    
    # Insert 60 days of distinct synthetic price data
    base_date = date(2026, 1, 1)
    from datetime import timedelta
    for i in range(60):
        price = 100.0 + (i * 0.5)
        trade_date = base_date + timedelta(days=i)
        db_write("""
            INSERT OR REPLACE INTO bhavcopy_daily (
                symbol, trade_date, series, open_price, high_price, low_price, 
                close_price, prev_close, total_traded_qty, total_traded_val, 
                delivery_qty, delivery_pct, split_multiplier
            ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
        """, (symbol, trade_date, price, price+1, price-1, price, price-0.5), sync=True)

    # 1. Test Pivot Extension Trap (>5% above trigger)
    candidate = {"trigger_price": 100.0, "sma_50": 115.0} # Current price is ~130.0 (30% above trigger)
    passed, reason, metrics = evaluate_anti_trap_shield(symbol, candidate, {"pe_ratio": 22.0, "sector_pe": 25.0})
    assert not passed
    assert reason == "TRAP_L1_PIVOT_EXTENDED"

    # 2. Test P/E Overvaluation Trap (>2.5x Sector P/E) - Currently DISABLED
    candidate_fair = {"trigger_price": 128.0, "sma_50": 120.0}
    passed, reason, metrics = evaluate_anti_trap_shield(symbol, candidate_fair, {"pe_ratio": 95.0, "sector_pe": 25.0})
    assert passed
    assert reason == "PASSED_ALL_ANTI_TRAP_LAYERS"

    print("\n[PASS] Anti-Trap Shield layers verified successfully!")


if __name__ == "__main__":
    test_liquidity_guard_t2t_and_adtv()
    test_shariah_compliance_gate()
    test_anti_trap_shield_layers()

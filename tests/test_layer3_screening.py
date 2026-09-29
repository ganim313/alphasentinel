import pytest
import pandas as pd
import numpy as np
from src.screening.anti_trap_shield import evaluate_anti_trap_shield
from src.screening.liquidity_guard import check_liquidity_and_executability
from src.screening.shariah_filter import check_shariah_compliance
from src.screening.ml_features import engineer_live_tick

def test_anti_trap_none_handling():
    funds = {
        "pledge_trend_3m": None,
        "promoter_pledged_pct": None,
        "recent_news_count": None
    }
    candidate = {
        "symbol": "TEST_SYM",
        "trigger_price": 128.0,
        "sma_20": 120.0,
        "sma_50": 115.0
    }
    passed, reason, metrics = evaluate_anti_trap_shield(
        symbol="TEST_SYM",
        candidate=candidate,
        fundamentals=funds,
        live_price=130.0,
        live_volume=100000
    )
    assert isinstance(passed, bool)

def test_liquidity_guard_fail_closed_short_history():
    # A non-existent or empty symbol has 0 data_days in DuckDB
    passed, reason, metrics = check_liquidity_and_executability(
        symbol="NONEXISTENT_NEW_IPO",
        series="EQ",
        circuit_band_pct=20.0,
        market_cap_tier="SMALL"
    )
    assert passed is False
    assert reason == "FAIL_INSUFFICIENT_DATA_DAYS"

def test_liquidity_guard_t2t_and_tight_circuit():
    # T2T series
    passed, reason, metrics = check_liquidity_and_executability(
        symbol="ANY_SYM",
        series="BE",
        circuit_band_pct=5.0,
        market_cap_tier="SMALL"
    )
    assert passed is False
    assert "T2T" in reason

def test_shariah_component_fallback_and_receivables():
    funds = {
        "sales": 1000.0,
        "borrowings": 200.0,
        "total_assets": 1000.0,
        "fixed_assets": 400.0,
        "cwip": 50.0,
        "inventories": 100.0,
        "intangible_assets": 0.0,
        "interest_income": 10.0,
        "market_cap_crores": 5000.0,
        "net_liquid_assets_crores": 300.0,
        "accounts_receivable": 250.0
    }
    passed, reason = check_shariah_compliance(funds, sector_name="IT Services")
    assert passed is True
    assert reason == "PASSED_SHARIAH_GATE"

    funds["accounts_receivable"] = 600.0
    passed_rec, reason_rec = check_shariah_compliance(funds, sector_name="IT Services")
    assert passed_rec is False
    assert "EXCESSIVE_RECEIVABLES" in reason_rec

def test_engineer_live_tick_volume_alias():
    df = pd.DataFrame({
        "trade_date": [pd.Timestamp("2026-09-14")],
        "close_price": [100.0],
        "high_price": [105.0],
        "low_price": [95.0],
        "volume": [50000]
    })
    res = engineer_live_tick(df, live_price=102.0, live_volume=60000)
    assert len(res) == 2
    assert "volume" in res.columns

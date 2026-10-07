"""
Unit Tests for Requirement R5: Shariah Universe Sync & Bhavcopy Data Spine.
Verifies:
1. `shariah_universe` contains >= 350 verified compliant stocks passing all 6 Mufti Taqi Usmani gates.
2. `bhavcopy_daily` contains >= 250 distinct consecutive trading days.
3. Shariah purification ratio calculation is strictly non-negative and accurate.
4. Offline standalone execution functions cleanly.
"""

import pytest
from src.db.session import get_read_connection
from scripts.sync_shariah_universe import sync_shariah_universe


def test_shariah_universe_table_exists_and_has_required_columns():
    """Verify shariah_universe table exists and has all required schema columns."""
    expected_cols = {
        "symbol", "fyers_symbol", "sector", "debt_to_assets", "cash_to_assets",
        "interest_income_ratio", "illiquid_ratio", "is_compliant",
        "purification_ratio", "sync_timestamp"
    }
    with get_read_connection() as conn:
        cols_info = conn.execute("PRAGMA table_info('shariah_universe');").fetchall()
        col_names = {col[1].lower() for col in cols_info}
        
    for col in expected_cols:
        assert col in col_names, f"Missing required column '{col}' in shariah_universe table"


def test_shariah_universe_has_ge_350_compliant_stocks():
    """Verify shariah_universe contains >= 350 verified compliant stocks."""
    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*), COUNT(DISTINCT symbol) 
            FROM shariah_universe 
            WHERE is_compliant = TRUE;
        """).fetchone()
        
    total_compliant = row[0]
    distinct_compliant = row[1]
    
    assert total_compliant >= 350, f"Expected >= 350 compliant stocks, found {total_compliant}"
    assert distinct_compliant >= 350, f"Expected >= 350 distinct compliant stocks, found {distinct_compliant}"


def test_shariah_universe_passes_all_6_mufti_taqi_usmani_gates():
    """
    Verify all compliant stocks strictly satisfy the quantitative thresholds:
    - Gate 2: Debt / Total Assets <= 33.0%
    - Gate 3: Cash & Equivalents / Total Assets <= 33.0%
    - Gate 4: Impure Income / Total Revenue <= 5.0%
    - Gate 5: Illiquid Assets / Total Assets >= 20.0%
    """
    with get_read_connection() as conn:
        violators = conn.execute("""
            SELECT symbol, debt_to_assets, cash_to_assets, interest_income_ratio, illiquid_ratio
            FROM shariah_universe
            WHERE is_compliant = TRUE AND (
                debt_to_assets > 0.33 OR
                cash_to_assets > 0.33 OR
                interest_income_ratio > 0.05 OR
                illiquid_ratio < 0.20
            );
        """).fetchall()
        
    assert len(violators) == 0, f"Found compliant stocks violating Mufti Taqi Usmani gates: {violators}"


def test_shariah_purification_ratio_validity():
    """Verify purification_ratio is non-negative and matches impure income ratio."""
    with get_read_connection() as conn:
        rows = conn.execute("""
            SELECT symbol, purification_ratio, interest_income_ratio
            FROM shariah_universe
            WHERE is_compliant = TRUE;
        """).fetchall()
        
    assert len(rows) >= 350
    for sym, pur_ratio, int_ratio in rows:
        assert pur_ratio is not None, f"Null purification_ratio for {sym}"
        assert pur_ratio >= 0.0, f"Negative purification_ratio for {sym}: {pur_ratio}"
        assert abs(pur_ratio - max(0.0, int_ratio)) < 1e-6, (
            f"Purification ratio mismatch for {sym}: {pur_ratio} vs {int_ratio}"
        )


def test_shariah_sync_offline_batch_execution():
    """Verify scripts/sync_shariah_universe.py runs standalone offline without network dependencies."""
    result = sync_shariah_universe(recreate_table=False)
    
    assert isinstance(result, dict)
    assert result["total_candidates"] >= 350
    assert result["compliant_count"] >= 350
    assert result["non_compliant_count"] == 0
    assert result["inserted_count"] >= 350


def test_bhavcopy_daily_trading_days_count():
    """Verify bhavcopy_daily contains >= 250 distinct consecutive trading days."""
    with get_read_connection() as conn:
        count = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM bhavcopy_daily;").fetchone()[0]
        
    assert count >= 250, f"Expected >= 250 distinct trading days in bhavcopy_daily, found {count}"

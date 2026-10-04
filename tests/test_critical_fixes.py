"""
Regression tests for critical quant, ML, and corporate action fixes (FIN-01, FIN-02, M-03).
"""
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pytest

from src.db.session import init_db, get_read_connection
from src.db.queue_writer import db_write
from src.screening.mean_reversion_screener import evaluate_mean_reversion, evaluate_mean_reversion_batch
from src.ingestion.corporate_actions import record_corporate_action


def test_model_training_no_bfill_lookahead_bias():
    """Verify scripts/run_model_training.py does not use .bfill() on market_regime or benchmark_rsi."""
    script_path = Path(__file__).parent.parent / "scripts" / "run_model_training.py"
    source = script_path.read_text(encoding="utf-8")
    assert ".bfill()" not in source, "Lookahead bias (.bfill()) detected in scripts/run_model_training.py"


def test_mr_screener_rejects_downtrend_falling_knife():
    """Verify mean reversion screener rejects oversold stocks trading below their 200-DMA."""
    init_db()
    sym = "TEST_MR_DOWN"
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,), sync=True)

    base_date = date(2025, 1, 1)
    prices = np.linspace(250.0, 100.0, 200)
    try:
        for i, p in enumerate(prices):
            td = base_date + timedelta(days=i)
            price = float(p)
            db_write("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val,
                    delivery_qty, delivery_pct, split_multiplier
                ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
            """, (sym, td, price, price + 1.0, price - 1.0, price, price + 0.5), sync=True)

        assert evaluate_mean_reversion(sym) is False
        assert evaluate_mean_reversion_batch([sym])[sym] is False
    finally:
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,), sync=True)


def test_mr_screener_accepts_uptrend_pullback():
    """Verify mean reversion screener accepts oversold pullbacks that remain above their 200-DMA."""
    init_db()
    sym = "TEST_MR_UP"
    db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,), sync=True)

    base_date = date(2025, 1, 1)
    uptrend = np.linspace(100.0, 250.0, 185)
    pullback = np.linspace(248.0, 215.0, 15)
    prices = np.concatenate([uptrend, pullback])

    try:
        for i, p in enumerate(prices):
            td = base_date + timedelta(days=i)
            price = float(p)
            db_write("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val,
                    delivery_qty, delivery_pct, split_multiplier
                ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
            """, (sym, td, price, price + 1.0, price - 1.0, price, price), sync=True)

        assert evaluate_mean_reversion(sym) is True
        assert evaluate_mean_reversion_batch([sym])[sym] is True
    finally:
        db_write("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,), sync=True)


def test_corporate_action_rev_ticker_not_inverted():
    """Verify NSE tickers containing 'REV' (like REVATHI) are not treated as reverse splits."""
    init_db()
    sym = "REVATHI"
    ex_dt = date(2026, 1, 15)
    action_id = record_corporate_action(sym, "SPLIT", ex_dt, 1.0, 10.0)
    try:
        with get_read_connection() as conn:
            row = conn.execute(
                "SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?;",
                (action_id,)
            ).fetchone()
        assert row is not None
        assert pytest.approx(row[0], rel=1e-6) == 0.1
    finally:
        db_write("DELETE FROM corporate_actions WHERE id = ?;", (action_id,), sync=True)

"""
Unit Tests for Deterministic Market Regime Engine (3-Point Breadth Score).
Validates:
  Point 1: Nifty 500 Close > SMA50
  Point 2: Nifty 500 SMA50 > SMA200
  Point 3: Universe Breadth (% Halal EQ stocks > own SMA50) > 50%

Scoring & Regime Map:
  Score 3 = RISK_ON (1.0% risk, allow_new_entries = True)
  Score 2 = NEUTRAL (0.5% risk, allow_new_entries = True)
  Score <= 1 = RISK_OFF (0.0% risk, allow_new_entries = False)

Fail-Closed verification for missing tables, insufficient history, and missing dates.
"""

import datetime
import duckdb
import pytest
from src.screening.regime_engine import (
    compute_market_regime,
    get_current_regime,
    RegimeState,
)


def _create_bhavcopy_schema(conn: duckdb.DuckDBPyConnection):
    """Creates standard bhavcopy_daily table schema."""
    conn.execute("""
        CREATE TABLE bhavcopy_daily (
            symbol VARCHAR,
            trade_date DATE,
            series VARCHAR,
            open_price DOUBLE,
            high_price DOUBLE,
            low_price DOUBLE,
            close_price DOUBLE,
            total_traded_qty BIGINT,
            total_traded_val DOUBLE,
            delivery_pct DOUBLE
        );
    """)


def test_regime_engine_score_3_risk_on():
    """
    Score 3 (RISK_ON):
    - Close > SMA50 (Point 1 = True)
    - SMA50 > SMA200 (Point 2 = True)
    - Breadth > 50% (Point 3 = True)
    Expects: score = 3, regime = 'RISK_ON', risk_per_trade_pct = 1.0, allow_new_entries = True.
    """
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    start_date = datetime.date(2026, 1, 1)
    num_bars = 220
    dates = [start_date + datetime.timedelta(days=i) for i in range(num_bars)]

    # 1. Benchmark MONIFTY500 in steady uptrend: Close (320) > SMA50 (~295) > SMA200 (~210)
    for i, d in enumerate(dates):
        price = 100.0 + (i * 1.0)
        conn.execute("""
            INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', ?, ?, ?, ?, 10000, 1000000.0, 50.0)
        """, [d, price, price + 1.0, price - 1.0, price])

    # 2. Universe stocks: 4 stocks, 3 in uptrends (above SMA50) -> Breadth = 75% > 50%
    for i, d in enumerate(dates):
        # Stock A: uptrend (Close > SMA50)
        p_a = 50.0 + (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_A', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_a, p_a + 1.0, p_a - 1.0, p_a])
        # Stock B: uptrend (Close > SMA50)
        p_b = 80.0 + (i * 0.4)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_B', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_b, p_b + 1.0, p_b - 1.0, p_b])
        # Stock C: uptrend (Close > SMA50)
        p_c = 120.0 + (i * 0.6)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_C', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_c, p_c + 1.0, p_c - 1.0, p_c])
        # Stock D: downtrend (Close < SMA50)
        p_d = 200.0 - (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_D', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_d, p_d + 1.0, p_d - 1.0, p_d])

    state = compute_market_regime(conn)

    assert state.regime == "RISK_ON"
    assert state.score == 3
    assert state.risk_per_trade_pct == 1.0
    assert state.allow_new_entries is True
    assert state.details["point_1_close_gt_sma50"] is True
    assert state.details["point_2_sma50_gt_sma200"] is True
    assert state.details["point_3_breadth_gt_50"] is True
    assert state.breadth_pct == 75.0
    assert state.nifty500_close > state.nifty500_sma50
    assert state.nifty500_sma50 > state.nifty500_sma200


def test_regime_engine_score_2_neutral():
    """
    Score 2 (NEUTRAL):
    - Close > SMA50 (Point 1 = True)
    - SMA50 < SMA200 (Point 2 = False: e.g. bear-market relief rally)
    - Breadth > 50% (Point 3 = True)
    Expects: score = 2, regime = 'NEUTRAL', risk_per_trade_pct = 0.5, allow_new_entries = True.
    """
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    start_date = datetime.date(2026, 1, 1)
    num_bars = 220
    dates = [start_date + datetime.timedelta(days=i) for i in range(num_bars)]

    # Benchmark: deep downtrend from 300 to 100, then fast rally in last 30 bars to 140
    # Day 0..169: 300 down to 100
    # Day 170..219: rally from 100 up to 140
    # Result: Close (140) > SMA50 (~115), but SMA200 is heavily influenced by 300..150 (~180).
    for i, d in enumerate(dates):
        if i < 170:
            price = 300.0 - (i * (200.0 / 170.0))  # 300 -> 100
        else:
            price = 100.0 + ((i - 170) * (40.0 / 50.0))  # 100 -> 140
        conn.execute("""
            INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', ?, ?, ?, ?, 10000, 1000000.0, 50.0)
        """, [d, price, price + 1.0, price - 1.0, price])

    # Universe: 4 stocks, 3 in uptrend (Breadth = 75%)
    for i, d in enumerate(dates):
        p_a = 50.0 + (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_A', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_a, p_a + 1.0, p_a - 1.0, p_a])
        p_b = 80.0 + (i * 0.4)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_B', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_b, p_b + 1.0, p_b - 1.0, p_b])
        p_c = 120.0 + (i * 0.6)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_C', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_c, p_c + 1.0, p_c - 1.0, p_c])
        p_d = 200.0 - (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_D', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_d, p_d + 1.0, p_d - 1.0, p_d])

    state = compute_market_regime(conn)

    assert state.regime == "NEUTRAL"
    assert state.score == 2
    assert state.risk_per_trade_pct == 0.5
    assert state.allow_new_entries is True
    assert state.details["point_1_close_gt_sma50"] is True
    assert state.details["point_2_sma50_gt_sma200"] is False
    assert state.details["point_3_breadth_gt_50"] is True


def test_regime_engine_score_1_or_0_risk_off():
    """
    Score <= 1 (RISK_OFF):
    - Close < SMA50 (Point 1 = False)
    - Breadth <= 50% (Point 3 = False)
    Expects: score <= 1, regime = 'RISK_OFF', risk_per_trade_pct = 0.0, allow_new_entries = False.
    """
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    start_date = datetime.date(2026, 1, 1)
    num_bars = 220
    dates = [start_date + datetime.timedelta(days=i) for i in range(num_bars)]

    # Benchmark in clear downtrend: Close (100) < SMA50 (~125)
    for i, d in enumerate(dates):
        price = 320.0 - (i * 1.0)
        conn.execute("""
            INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', ?, ?, ?, ?, 10000, 1000000.0, 50.0)
        """, [d, price, price + 1.0, price - 1.0, price])

    # Universe: only 1 out of 4 in uptrend -> Breadth = 25% <= 50%
    for i, d in enumerate(dates):
        p_a = 50.0 + (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_A', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_a, p_a + 1.0, p_a - 1.0, p_a])
        p_b = 180.0 - (i * 0.4)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_B', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_b, p_b + 1.0, p_b - 1.0, p_b])
        p_c = 220.0 - (i * 0.6)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_C', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_c, p_c + 1.0, p_c - 1.0, p_c])
        p_d = 200.0 - (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('STOCK_D', ?, 'EQ', ?, ?, ?, ?, 5000, 500000.0, 50.0)",
                     [d, p_d, p_d + 1.0, p_d - 1.0, p_d])

    state = compute_market_regime(conn)

    assert state.regime == "RISK_OFF"
    assert state.score <= 1
    assert state.risk_per_trade_pct == 0.0
    assert state.allow_new_entries is False
    assert state.details["point_1_close_gt_sma50"] is False
    assert state.details["point_3_breadth_gt_50"] is False


def test_regime_engine_fail_closed_empty_db():
    """Fail-closed on empty DB with no tables: returns Score 0 RISK_OFF."""
    conn = duckdb.connect(":memory:")
    state = compute_market_regime(conn)

    assert state.regime == "RISK_OFF"
    assert state.score == 0
    assert state.risk_per_trade_pct == 0.0
    assert state.allow_new_entries is False
    assert state.details["fail_closed"] is True


def test_regime_engine_fail_closed_missing_benchmark():
    """Fail-closed when bhavcopy_daily lacks benchmark symbol: returns Score 0 RISK_OFF."""
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    d = datetime.date(2026, 6, 1)
    conn.execute("INSERT INTO bhavcopy_daily VALUES ('ONLY_EQUITY_CO', ?, 'EQ', 100.0, 105.0, 95.0, 102.0, 1000, 100000.0, 50.0)", [d])

    state = compute_market_regime(conn)

    assert state.regime == "RISK_OFF"
    assert state.score == 0
    assert state.risk_per_trade_pct == 0.0
    assert state.allow_new_entries is False
    assert state.details["fail_closed"] is True


def test_regime_engine_fail_closed_insufficient_history():
    """Fail-closed when benchmark history < 50 bars: returns Score 0 RISK_OFF."""
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    start_date = datetime.date(2026, 1, 1)
    for i in range(25):  # only 25 days (< 50)
        d = start_date + datetime.timedelta(days=i)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', 100.0, 105.0, 95.0, 102.0, 1000, 100000.0, 50.0)", [d])

    state = compute_market_regime(conn)

    assert state.regime == "RISK_OFF"
    assert state.score == 0
    assert state.risk_per_trade_pct == 0.0
    assert state.allow_new_entries is False
    assert state.details["fail_closed"] is True


def test_regime_engine_fail_closed_missing_date():
    """Fail-closed when as_of_date is prior to available benchmark data: returns Score 0 RISK_OFF."""
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    start_date = datetime.date(2026, 6, 1)
    for i in range(60):
        d = start_date + datetime.timedelta(days=i)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', 100.0, 105.0, 95.0, 102.0, 1000, 100000.0, 50.0)", [d])

    # Date prior to any benchmark rows
    state = compute_market_regime(conn, as_of_date="2025-01-01")

    assert state.regime == "RISK_OFF"
    assert state.score == 0
    assert state.risk_per_trade_pct == 0.0
    assert state.allow_new_entries is False
    assert state.details["fail_closed"] is True


def test_regime_engine_respects_shariah_universe_table():
    """When shariah_universe table exists, breadth evaluates only compliant constituents."""
    conn = duckdb.connect(":memory:")
    _create_bhavcopy_schema(conn)

    conn.execute("""
        CREATE TABLE shariah_universe (
            symbol VARCHAR PRIMARY KEY,
            is_compliant BOOLEAN
        );
    """)
    conn.execute("INSERT INTO shariah_universe VALUES ('HALAL_STOCK', TRUE), ('NON_HALAL_STOCK', FALSE);")

    start_date = datetime.date(2026, 1, 1)
    num_bars = 60
    dates = [start_date + datetime.timedelta(days=i) for i in range(num_bars)]

    for i, d in enumerate(dates):
        # Benchmark uptrend
        p_bm = 100.0 + i
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, 'EQ', ?, ?, ?, ?, 1000, 100000.0, 50.0)",
                     [d, p_bm, p_bm + 1.0, p_bm - 1.0, p_bm])
        # HALAL_STOCK uptrend (above SMA50)
        p_h = 50.0 + (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('HALAL_STOCK', ?, 'EQ', ?, ?, ?, ?, 1000, 100000.0, 50.0)",
                     [d, p_h, p_h + 1.0, p_h - 1.0, p_h])
        # NON_HALAL_STOCK downtrend (should be excluded by shariah_universe table)
        p_nh = 200.0 - (i * 0.5)
        conn.execute("INSERT INTO bhavcopy_daily VALUES ('NON_HALAL_STOCK', ?, 'EQ', ?, ?, ?, ?, 1000, 100000.0, 50.0)",
                     [d, p_nh, p_nh + 1.0, p_nh - 1.0, p_nh])

    state = compute_market_regime(conn)

    # Eligible universe is only 1 stock (HALAL_STOCK), which is above SMA50 -> 100% breadth
    assert state.details["universe_source"] == "shariah_universe"
    assert state.details["eligible_universe_count"] == 1
    assert state.breadth_pct == 100.0
    assert state.details["point_3_breadth_gt_50"] is True


def test_get_current_regime_helper():
    """Validates get_current_regime helper delegates correctly with conn argument."""
    conn = duckdb.connect(":memory:")
    state = get_current_regime(conn)
    assert isinstance(state, RegimeState)
    assert state.regime == "RISK_OFF"

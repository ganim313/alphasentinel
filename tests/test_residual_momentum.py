"""
Unit Tests for Beta-Stripped Residual Momentum (Requirement R6).

Verifies:
1. Vectorized execution time < 100ms across 350+ stocks x 60 bars.
2. High-beta bank correlated movement does not inflate non-banking residual momentum.
3. Candidate ranking below 70th percentile is rejected by VCP screener; >= 70th percentile passes.
4. Mathematical recovery of OLS beta and idiosyncratic residual properties.
5. Integration with DuckDB active Halal universe.
"""

import time
from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest
import duckdb
from unittest.mock import patch

from src.screening.vcp_screener import (
    compute_vectorized_residual_momentum,
    compute_universe_residual_momentum,
    evaluate_minervini_vcp_batch
)


def test_test1_vectorized_execution_time_under_100ms():
    """
    Test 1: Vectorized execution time MUST compute in < 100ms across 350+ stocks x 60 bars.
    """
    np.random.seed(42)
    T, N = 60, 400  # 60 daily bars, 400 stocks
    bm_rets = np.random.normal(0.0005, 0.01, T)
    stock_rets = np.random.normal(0.0005, 0.015, (T, N))

    t0 = time.perf_counter()
    betas, scores, ranks = compute_vectorized_residual_momentum(stock_rets, bm_rets)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 100.0, f"Vectorized calculation took {elapsed_ms:.2f}ms, exceeding 100ms threshold"
    assert betas.shape == (N,)
    assert scores.shape == (N,)
    assert ranks.shape == (N,)
    assert 0.0 <= ranks.min() <= ranks.max() <= 100.0


def test_test2_high_beta_bank_correlation_does_not_inflate_non_banking_residual_momentum():
    """
    Test 2: High-beta bank correlated movement does not inflate non-banking residual momentum.
    
    Demonstrates that during a banking-led benchmark rally, a high-beta stock moving purely with the
    benchmark without firm-specific alpha has ~0 residual momentum score, while a non-banking stock
    with lower beta but positive idiosyncratic outperformance achieves a higher residual score.
    """
    T = 60
    # Benchmark exhibits strong upward drift (e.g. banking rally)
    np.random.seed(101)
    bm_rets = np.random.normal(0.015, 0.008, T)  # Strong benchmark rally

    # Stock 1 (Simulated Bank Proxy): High beta = 1.85, 0 idiosyncratic alpha
    stock_bank = 1.85 * bm_rets + np.random.normal(0.0, 0.0005, T)

    # Stock 2 (Simulated Shariah Leader): Lower beta = 0.65, strong positive idiosyncratic catalyst
    idiosyncratic_alpha = np.zeros(T)
    idiosyncratic_alpha[-30:] = 0.012  # +1.2% daily idiosyncratic return in last 30 bars
    stock_shariah = 0.65 * bm_rets + idiosyncratic_alpha + np.random.normal(0.0, 0.001, T)

    # Conventional raw return over 60 days
    bank_cum_return = np.prod(1 + stock_bank) - 1.0
    shariah_cum_return = np.prod(1 + stock_shariah) - 1.0

    # Stock Bank had higher total return due to high beta exposure
    assert bank_cum_return > shariah_cum_return, "Bank return should be higher under raw return"

    # Compute Beta-Stripped Residual Momentum
    stock_matrix = np.column_stack([stock_bank, stock_shariah])
    betas, scores, ranks = compute_vectorized_residual_momentum(stock_matrix, bm_rets)

    # Betas properly separated
    assert betas[0] > 1.6  # High beta captured
    assert betas[1] < 0.8  # Low beta captured

    # Crucial property: Bank has ~0 residual score, Shariah leader has high positive residual score
    bank_res_score = scores[0]
    shariah_res_score = scores[1]

    assert shariah_res_score > bank_res_score, (
        f"Shariah stock residual ({shariah_res_score:.2f}) must exceed Bank residual ({bank_res_score:.2f})"
    )
    assert ranks[1] > ranks[0], "Shariah leader must rank higher in residual momentum"


def test_test3_candidate_ranking_below_70th_pct_rejected_ge_70th_passes():
    """
    Test 3: Candidate ranking below 70th percentile is rejected by VCP screener; >= 70th percentile passes.
    """
    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE bhavcopy_daily (
            symbol VARCHAR, trade_date DATE, close_price DOUBLE,
            high_price DOUBLE, low_price DOUBLE, total_traded_qty BIGINT,
            delivery_pct DOUBLE, series VARCHAR, is_asm BOOLEAN, is_gsm BOOLEAN
        );
        CREATE TABLE positions (
            status VARCHAR, realized_pnl DOUBLE, unrealized_pnl DOUBLE, entry_price DOUBLE
        );
        CREATE TABLE shariah_universe (
            symbol VARCHAR, fyers_symbol VARCHAR, sector VARCHAR,
            is_compliant BOOLEAN
        );
    """)

    # Populate 10 universe stocks to form a clear cross-sectional distribution
    base_d = date(2025, 12, 1)
    num_bars = 185
    dates = [base_d + timedelta(days=i) for i in range(num_bars)]

    symbols = [f"STOCK_{i:02d}" for i in range(10)]
    # Mark all compliant in shariah_universe
    for s in symbols:
        mem_conn.execute("INSERT INTO shariah_universe VALUES (?, ?, 'Specialty Chem', TRUE)", (s, s))

    # STOCK_09: Strong idiosyncratic outperformance in last 30 bars (Top rank)
    # STOCK_00: Severe idiosyncratic decay in last 30 bars (Bottom rank)
    for i, d in enumerate(dates):
        # Benchmark MONIFTY500
        bm_price = 100.0 + (i * 0.1)
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, ?, ?, ?, 500000, 50.0, 'EQ', FALSE, FALSE)",
            (d, bm_price, bm_price + 0.5, bm_price - 0.5)
        )

        for s_idx, s in enumerate(symbols):
            if i < 165:
                # Normal Stage 2 uptrend
                c_p = 100.0 + (i * 0.75)
                vol = 50000
            else:
                # Consolidation base at highs
                c_p = 224.0 + (s_idx * 0.2)
                # Differentiate the last 30 bars of returns:
                # Higher index stocks get higher upward drift in last 30 bars
                drift = (s_idx - 5) * 0.05 * (i - 165)
                c_p += drift
                vol = 5000 if i >= 180 else 40000

            h_p = c_p + 1.0
            l_p = c_p - 1.0
            mem_conn.execute(
                "INSERT INTO bhavcopy_daily VALUES (?, ?, ?, ?, ?, ?, 55.0, 'EQ', FALSE, FALSE)",
                (s, d, c_p, h_p, l_p, vol)
            )

    with patch("src.utils.benchmark_provider.get_market_regime", return_value=1):
        # Screen all 10 candidates
        results = evaluate_minervini_vcp_batch(
            symbols,
            mem_conn,
            live_prices={s: 224.0 for s in symbols}
        )

    # Verify that only stocks with rank >= 70.0 pass the screener
    passed_symbols = [r["symbol"] for r in results]

    for r in results:
        assert r["residual_momentum_rank"] >= 70.0, (
            f"Candidate {r['symbol']} passed with rank {r['residual_momentum_rank']:.1f} < 70.0"
        )
        assert "residual_momentum_score" in r
        assert "beta" in r

    # STOCK_09 must pass (top leader)
    assert "STOCK_09" in passed_symbols
    # STOCK_00 must be rejected (bottom laggard)
    assert "STOCK_00" not in passed_symbols


def test_ols_beta_exact_recovery():
    """
    Verifies OLS beta formula recovers ground-truth betas from synthetic series.
    """
    T = 60
    np.random.seed(777)
    bm_rets = np.random.normal(0.001, 0.01, T)

    target_betas = [0.35, 0.75, 1.25, 2.10]
    stock_cols = []
    for b in target_betas:
        rets = b * bm_rets + np.random.normal(0.0, 0.0001, T)
        stock_cols.append(rets)

    stock_matrix = np.column_stack(stock_cols)
    betas, scores, ranks = compute_vectorized_residual_momentum(stock_matrix, bm_rets)

    for estimated, target in zip(betas, target_betas):
        assert abs(estimated - target) < 0.05, f"Expected {target}, got {estimated}"


def test_zero_residual_variance_clamped():
    """
    Verifies zero residual variance is clamped by minimum std dev floor without ZeroDivisionError.
    """
    T = 60
    bm_rets = np.linspace(-0.01, 0.01, T)
    # Stock has exact linear relationship: Y = 1.5 * x + 0.001
    stock_rets = 1.5 * bm_rets + 0.001

    betas, scores, ranks = compute_vectorized_residual_momentum(stock_rets[:, np.newaxis], bm_rets)
    assert abs(betas[0] - 1.5) < 1e-4
    assert np.isfinite(scores[0])
    assert ranks[0] == 100.0


def test_compute_universe_residual_momentum_duckdb_integration():
    """
    Tests DuckDB integration with compute_universe_residual_momentum.
    """
    mem_conn = duckdb.connect(":memory:")
    mem_conn.execute("""
        CREATE TABLE bhavcopy_daily (
            symbol VARCHAR, trade_date DATE, close_price DOUBLE, series VARCHAR
        );
        CREATE TABLE shariah_universe (
            symbol VARCHAR, is_compliant BOOLEAN
        );
    """)

    base_d = date(2026, 1, 1)
    for i in range(65):
        d = base_d + timedelta(days=i)
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES ('MONIFTY500', ?, ?, 'EQ')",
            (d, 100.0 + i)
        )
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES ('STOCK_A', ?, ?, 'EQ')",
            (d, 50.0 + (i * 1.2))
        )
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES ('STOCK_B', ?, ?, 'EQ')",
            (d, 80.0 + (i * 0.4))
        )

    mem_conn.execute("INSERT INTO shariah_universe VALUES ('STOCK_A', TRUE), ('STOCK_B', TRUE)")

    res_map = compute_universe_residual_momentum(mem_conn)
    assert "STOCK_A" in res_map
    assert "STOCK_B" in res_map
    assert "beta" in res_map["STOCK_A"]
    assert "residual_score" in res_map["STOCK_A"]
    assert "percentile_rank" in res_map["STOCK_A"]

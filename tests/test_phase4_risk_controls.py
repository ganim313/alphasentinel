"""
Phase 4 Risk Controls Hardening Verification Test Suite.
Verifies all 9 components (P4-1 to P4-9) across:
1. Portfolio Correlation Guard (Soft limit Pearson > 0.65 check & fail-open resilience)
2. LLM Gateway Per-Provider Circuit Breaker (300s cooldown on timeout / 429)
3. VCP Regime Bypass Rule (RS > 15.0 with volume dry-up at 50% size)
4. Anti-Trap Layer 6 Degraded Mode (Scraper unavailable + price run > 15%)
5. Lower Circuit Exit Guard in Paper Broker & Sentinel (Real-world exit lock detection)
6. AWAITING_TRIGGER Intraday Polling Daemon (Auto-executes breakouts during market hours)
7. Promoter Pledge History Persistence (Persisting scraped fundamentals for Layer 4)
8. EOD Risk Offload Production Wiring
9. Daily Equity Curve Snapshot
"""

import time
import math
import datetime
from unittest.mock import patch, MagicMock
import pytest
import numpy as np
import pandas as pd

from src.db.session import init_db, get_read_connection, get_write_connection
from src.db.queue_writer import db_write
from src.config.settings import settings
from src.risk.correlation_guard import evaluate_correlation_guard
from src.agents.debate_graph import deterministic_risk_node
import src.agents.llm_gateway as llm_gateway
from src.screening.vcp_screener import evaluate_minervini_vcp_batch
from src.screening.anti_trap_shield import evaluate_anti_trap_shield
from src.execution.order_manager import check_lower_circuit_trap, PaperBroker
from scripts.run_sentinel import run_sentinel_check
from scripts.run_trigger_watcher import check_and_execute_triggers
from src.ingestion.screener_scraper import scrape_screener_fundamentals
from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist and clean up test fixtures."""
    init_db()
    with get_read_connection() as conn:
        saved_today_eq = conn.execute(
            "SELECT trade_date, total_equity, core_equity, unrealized_pnl "
            "FROM equity_curve WHERE trade_date = CURRENT_DATE"
        ).fetchall()
    yield
    # Cleanup after test
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM screener_candidates WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM promoter_pledge_history WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM fundamentals_cache WHERE symbol LIKE 'TEST_%'")
        conn.execute("DELETE FROM equity_curve WHERE trade_date = CURRENT_DATE")
        for row in saved_today_eq:
            conn.execute(
                "INSERT OR REPLACE INTO equity_curve (trade_date, total_equity, core_equity, unrealized_pnl) "
                "VALUES (?, ?, ?, ?)",
                list(row),
            )


# -------------------------------------------------------------------------
# P4-1: Portfolio Correlation Guard Tests
# -------------------------------------------------------------------------

def test_correlation_guard_rejects_correlated_candidate():
    """
    Asserts candidate with >0.65 average Pearson correlation with open positions
    returns passed=False and rejects in deterministic_risk_node.
    """
    today = datetime.date.today()
    cand_sym = "TEST_CORR_CAND"
    open_sym = "TEST_CORR_OPEN"

    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol IN (?, ?)", (cand_sym, open_sym))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol IN (?, ?)", (cand_sym, open_sym))
        
        # Insert open position with all required NOT NULL columns
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status
            ) VALUES (
                'pos_corr_test', ?, CURRENT_DATE, 100.0, 50, 100.0,
                2.0, 95.0, 110.0, 120.0, 250.0, 5.0, 'OPEN'
            );
        """, (open_sym,))

        # Insert 65 days of correlated percentage returns (Pearson ~ 1.0, std > 0)
        base_date = today - datetime.timedelta(days=75)
        curr_p_open = 100.0
        curr_p_cand = 50.0
        # Time-varying factor so daily return pct_change is not zero-variance
        factors = [1.0 + 0.02 * math.sin(i * 0.4) for i in range(65)]
        for i in range(65):
            t_date = base_date + datetime.timedelta(days=i)
            curr_p_open *= factors[i]
            curr_p_cand *= factors[i]
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0);
            """, (open_sym, t_date, curr_p_open, curr_p_open, curr_p_open, curr_p_open))
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0);
            """, (cand_sym, t_date, curr_p_cand, curr_p_cand, curr_p_cand, curr_p_cand))

    passed, reason, metrics = evaluate_correlation_guard(cand_sym, threshold=0.65)
    assert passed is False
    assert "CORR_GUARD_REJECTED" in reason
    assert metrics.get("avg_pairwise_corr", 0) > 0.65

    # Check deterministic_risk_node rejects
    node_res = deterministic_risk_node({
        "symbol": cand_sym,
        "trigger_price": 60.0,
        "current_price": 60.0
    })
    assert node_res["risk_verdict"] == "REJECT"
    assert "CORR_GUARD_REJECTED" in node_res["rejection_reason"]


def test_correlation_guard_allows_uncorrelated_candidate():
    """Asserts candidate with <=0.65 correlation returns passed=True."""
    today = datetime.date.today()
    cand_sym = "TEST_UNCORR_CAND"
    open_sym = "TEST_UNCORR_OPEN"

    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol IN (?, ?)", (cand_sym, open_sym))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol IN (?, ?)", (cand_sym, open_sym))
        
        # Insert open position with all required NOT NULL columns
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status
            ) VALUES (
                'pos_uncorr_test', ?, CURRENT_DATE, 100.0, 50, 100.0,
                2.0, 95.0, 110.0, 120.0, 250.0, 5.0, 'OPEN'
            );
        """, (open_sym,))

        # Insert 65 days of orthogonal/uncorrelated returns (Pearson ~ 0)
        base_date = today - datetime.timedelta(days=75)
        curr_p_open = 100.0
        curr_p_cand = 50.0
        factors_open = [1.0 + 0.02 * math.sin(i * 0.4) for i in range(65)]
        factors_cand = [1.0 + 0.02 * math.cos(i * 0.4) for i in range(65)]
        for i in range(65):
            t_date = base_date + datetime.timedelta(days=i)
            curr_p_open *= factors_open[i]
            curr_p_cand *= factors_cand[i]
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0);
            """, (open_sym, t_date, curr_p_open, curr_p_open, curr_p_open, curr_p_open))
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0);
            """, (cand_sym, t_date, curr_p_cand, curr_p_cand, curr_p_cand, curr_p_cand))

    passed, reason, metrics = evaluate_correlation_guard(cand_sym, threshold=0.65)
    assert passed is True
    assert "CORR_GUARD_PASSED" in reason
    assert metrics.get("avg_pairwise_corr", 0) <= 0.65


def test_correlation_guard_fails_open_safely():
    """Asserts missing history or zero open positions safely passes (fails open)."""
    with get_read_connection() as conn:
        saved_positions_df = conn.execute("SELECT * FROM positions WHERE symbol NOT LIKE 'TEST_%'").df()

    try:
        # 1. No open positions in DB for candidate
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions")
        
        passed, reason, metrics = evaluate_correlation_guard("TEST_EMPTY_PORT")
        assert passed is True
        assert "CORR_GUARD_SKIPPED" in reason

        # 2. Open position exists but candidate has insufficient history (<15 days)
        with get_write_connection() as conn:
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, current_ltp,
                    atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                    portfolio_allocation_pct, status
                ) VALUES (
                    'pos_short_hist', 'TEST_OPEN_1', CURRENT_DATE, 100.0, 50, 100.0,
                    2.0, 95.0, 110.0, 120.0, 250.0, 5.0, 'OPEN'
                );
            """)
            for i in range(5):
                t_date = datetime.date.today() - datetime.timedelta(days=i)
                conn.execute("""
                    INSERT INTO bhavcopy_daily (
                        symbol, trade_date, open_price, high_price, low_price, close_price,
                        total_traded_qty, total_traded_val
                    ) VALUES ('TEST_SHORT', ?, 100.0, 102.0, 99.0, 100.0, 10000, 1000000.0);
                """, (t_date,))

        passed, reason, metrics = evaluate_correlation_guard("TEST_SHORT")
        assert passed is True
        assert "CORR_GUARD_SKIPPED" in reason
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE symbol LIKE 'TEST_%'")
            if not saved_positions_df.empty:
                conn.register("saved_pos_df", saved_positions_df)
                conn.execute("INSERT OR REPLACE INTO positions SELECT * FROM saved_pos_df")
                conn.unregister("saved_pos_df")


# -------------------------------------------------------------------------
# P4-2: LLM Per-Provider Circuit Breaker Tests
# -------------------------------------------------------------------------

def test_llm_gateway_circuit_breaker_activates_on_timeout():
    """Asserts provider failure marks provider unhealthy and subsequent calls skip it immediately."""
    llm_gateway._provider_failure_ts.clear()
    primary = settings.PRIMARY_LLM

    assert llm_gateway._is_provider_healthy(primary) is True

    # Simulate timeout on litellm
    mock_litellm = MagicMock()
    mock_litellm.completion.side_effect = Exception("Request timed out (timeout error)")
    with patch.dict("sys.modules", {"litellm": mock_litellm}):
        res = llm_gateway.execute_llm_completion([{"role": "user", "content": "test"}])
        assert res is not None  # Fallback text returned
        assert llm_gateway._is_provider_healthy(primary) is False

    # Second call should skip primary provider immediately without calling litellm for it
    mock_litellm.completion.reset_mock()
    with patch.dict("sys.modules", {"litellm": mock_litellm}):
        llm_gateway.execute_llm_completion([{"role": "user", "content": "test"}])
        called_models = [call.kwargs.get("model") for call in mock_litellm.completion.call_args_list]
        assert primary not in called_models

    llm_gateway._provider_failure_ts.clear()


def test_llm_gateway_circuit_breaker_cooldown_recovery():
    """Asserts that after 300s cooldown the provider circuit breaker closes (recovers)."""
    llm_gateway._provider_failure_ts.clear()
    test_model = "test/mock-llm"

    # Mark unhealthy
    llm_gateway._mark_provider_unhealthy(test_model, "rate limit 429")
    assert llm_gateway._is_provider_healthy(test_model) is False

    # Simulate time elapsed > 300s
    llm_gateway._provider_failure_ts[test_model] = time.monotonic() - 305.0
    assert llm_gateway._is_provider_healthy(test_model) is True

    llm_gateway._provider_failure_ts.clear()


# -------------------------------------------------------------------------
# P4-3: VCP Regime Bypass Rule Tests
# -------------------------------------------------------------------------

def test_vcp_regime_bypass_allows_high_rs_at_half_size():
    """
    Asserts rs_score > 15.0 with volume dryup returns regime_bypass_size_reduction = 0.5
    when regime filter fails.
    """
    sym = "TEST_VCP_BYPASS"
    today = datetime.date.today()
    num_bars = 240
    dates = [today - datetime.timedelta(days=num_bars - i) for i in range(num_bars)]

    # Build Stage 2 base (>200 bars for sma_200):
    records = []
    for i, d in enumerate(dates):
        if i >= 220:
            # Low volatility consolidation base near highs (140.0)
            c_p = 140.0 + (i % 2) * 0.1
        else:
            # Steady uptrend from 30.0 to 140.0 (ensuring 60d return > 15%)
            c_p = 30.0 + (i * 0.5)

        # Volume dryup on last 5 bars (< 0.85 of 20-day average)
        if i >= 235:
            v_val = 500
        else:
            v_val = 5000

        records.append({
            "symbol": sym,
            "trade_date": d,
            "series": "EQ",
            "open_price": c_p,
            "high_price": c_p + 1.0,
            "low_price": c_p - 1.0,
            "close_price": c_p,
            "total_traded_qty": v_val,
            "total_traded_val": v_val * c_p,
            "delivery_pct": 50.0
        })

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        for r in records:
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, total_traded_qty, total_traded_val, delivery_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                r["symbol"], r["trade_date"], r["series"], r["open_price"], r["high_price"],
                r["low_price"], r["close_price"], r["total_traded_qty"], r["total_traded_val"], r["delivery_pct"]
            ))

    with get_read_connection() as conn:
        # Mock regime as failed (regime_passed = False), benchmark return = 0.0 (pd.Series)
        with patch("src.utils.benchmark_provider.get_market_regime", return_value=0):
            with patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.0] * 100)):
                res = evaluate_minervini_vcp_batch([sym], conn)

    assert len(res) == 1
    cand = res[0]
    assert cand["symbol"] == sym
    assert cand["rs_score"] > 15.0
    assert cand["volume_dryup"] is True
    assert cand["regime_bypass_size_reduction"] == 0.5


def test_vcp_regime_bypass_rejects_low_rs():
    """Asserts rs_score <= 15.0 is rejected when regime filter fails."""
    sym = "TEST_VCP_LOW_RS"
    today = datetime.date.today()
    num_bars = 240
    dates = [today - datetime.timedelta(days=num_bars - i) for i in range(num_bars)]

    records = []
    for i, d in enumerate(dates):
        if i >= 220:
            c_p = 140.0 + (i % 2) * 0.1
            v_val = 500
        else:
            c_p = 50.0 + (i * 0.4)
            v_val = 5000

        records.append({
            "symbol": sym,
            "trade_date": d,
            "series": "EQ",
            "open_price": c_p,
            "high_price": c_p + 1.0,
            "low_price": c_p - 1.0,
            "close_price": c_p,
            "total_traded_qty": v_val,
            "total_traded_val": v_val * c_p,
            "delivery_pct": 50.0
        })

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        for r in records:
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, total_traded_qty, total_traded_val, delivery_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                r["symbol"], r["trade_date"], r["series"], r["open_price"], r["high_price"],
                r["low_price"], r["close_price"], r["total_traded_qty"], r["total_traded_val"], r["delivery_pct"]
            ))

    with get_read_connection() as conn:
        # Mock benchmark return high (e.g. 1% daily return over 60d = ~81% return), making rs_score <= 15.0
        with patch("src.utils.benchmark_provider.get_market_regime", return_value=0):
            with patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.01] * 100)):
                res = evaluate_minervini_vcp_batch([sym], conn)

    assert len(res) == 0


# -------------------------------------------------------------------------
# P4-4: Anti-Trap Layer 6 Degraded Mode Tests
# -------------------------------------------------------------------------

def test_anti_trap_layer6_degraded_mode_rejects_high_run():
    """Asserts recent_news_count is None with 3-day run > 15% rejects with TRAP_L6_DEGRADED_MODE_FOMO_SUSPECTED."""
    sym = "TEST_TRAP_DEG_REJECT"
    today = datetime.date.today()

    # Insert 55 days of data
    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        for i in range(55):
            t_date = today - datetime.timedelta(days=55 - i)
            # Setup: prices around 110 for days 35-51 so 20-DMA is ~110 (dist_20 < 15%)
            # Day 52 (3d ago): 100.0
            # Day 53 (2d ago): 108.0
            # Day 54 (1d ago): 116.0
            # Current/live price: 121.0 -> run_3d_pct = (121 - 100)/100 = 21% > 15%
            if i == 52:
                c_p = 100.0
            elif i == 53:
                c_p = 108.0
            elif i == 54:
                c_p = 116.0
            elif i >= 35:
                c_p = 110.0
            else:
                c_p = 100.0

            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val, delivery_pct
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0, 30.0);
            """, (sym, t_date, c_p, c_p + 1.0, c_p - 1.0, c_p))

    candidate = {"trigger_price": 120.0, "sma_50": 108.0}
    fundamentals = {"recent_news_count": None, "pledge_trend_3m": 0.0, "promoter_pledged_pct": 0.0}

    passed, reason, metrics = evaluate_anti_trap_shield(sym, candidate, fundamentals, live_price=121.0)
    assert passed is False
    assert reason == "TRAP_L6_DEGRADED_MODE_FOMO_SUSPECTED"
    assert metrics["run_3d_pct"] > 15.0


def test_anti_trap_layer6_degraded_mode_allows_calm_stock():
    """Asserts recent_news_count is None with 3-day run <= 15% passes."""
    sym = "TEST_TRAP_DEG_PASS"
    today = datetime.date.today()

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        for i in range(55):
            t_date = today - datetime.timedelta(days=55 - i)
            c_p = 100.0 + (i * 0.1)  # slow calm rise
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val, delivery_pct
                ) VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000.0, 30.0);
            """, (sym, t_date, c_p, c_p + 0.5, c_p - 0.5, c_p))

    candidate = {"trigger_price": 105.0, "sma_50": 102.0}
    fundamentals = {"recent_news_count": None, "pledge_trend_3m": 0.0, "promoter_pledged_pct": 0.0}

    passed, reason, metrics = evaluate_anti_trap_shield(sym, candidate, fundamentals, live_price=105.5)
    assert passed is True
    assert reason == "PASSED_ALL_ANTI_TRAP_LAYERS"


# -------------------------------------------------------------------------
# P4-5: Lower Circuit Exit Guard Tests
# -------------------------------------------------------------------------

def test_order_manager_detects_lower_circuit_trap():
    """Asserts check_lower_circuit_trap detects stock trapped at or below Lower Circuit."""
    sym = "TEST_LC_TRAP"
    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        conn.execute("""
            INSERT INTO bhavcopy_daily (
                symbol, trade_date, open_price, high_price, low_price, close_price,
                lower_circuit, upper_circuit, circuit_band_pct, total_traded_qty, total_traded_val
            ) VALUES (?, CURRENT_DATE, 90.0, 95.0, 90.0, 90.0, 90.0, 110.0, 10, 10000, 1000000.0);
        """, (sym,))

    # Price at LC (90.0) -> Trapped
    status_trapped = check_lower_circuit_trap(sym, current_price=90.0)
    assert status_trapped["is_trapped"] is True
    assert status_trapped["lower_circuit"] == 90.0

    # Price above LC (95.0) -> Not trapped
    status_free = check_lower_circuit_trap(sym, current_price=95.0)
    assert status_free["is_trapped"] is False


def test_sentinel_marks_closure_on_lower_circuit_trap():
    """Asserts Sentinel sets status = 'MARKED_FOR_CLOSURE' when stop-loss breached at lower circuit."""
    sym = "TEST_SENTINEL_LC"
    pos_id = "pos_sentinel_lc"

    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        
        # Open position with SL at 95.0 and all required NOT NULL fields
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status
            ) VALUES (?, ?, CURRENT_DATE, 100.0, 50, 92.0, 2.0, 95.0, 110.0, 120.0, 250.0, 5.0, 'OPEN');
        """, (pos_id, sym))

        # Bhavcopy lower circuit is 90.0
        conn.execute("""
            INSERT INTO bhavcopy_daily (
                symbol, trade_date, open_price, high_price, low_price, close_price,
                lower_circuit, circuit_band_pct, total_traded_qty, total_traded_val
            ) VALUES (?, CURRENT_DATE, 90.0, 92.0, 90.0, 90.0, 90.0, 10, 10000, 1000000.0);
        """, (sym,))

    # Mock yfinance to return price at lower circuit (90.0)
    mock_df = pd.DataFrame({
        "Close": [90.0],
        "High": [91.0],
        "Low": [90.0]
    })
    
    with patch("yfinance.download", return_value=mock_df):
        with patch("src.notification.telegram_bot.send_telegram_alert") as mock_tg:
            run_sentinel_check()

    with get_read_connection() as conn:
        row = conn.execute("SELECT status, current_ltp FROM positions WHERE id = ?", (pos_id,)).fetchone()
    
    assert row is not None
    assert row[0] == "MARKED_FOR_CLOSURE"
    assert row[1] == 90.0


# -------------------------------------------------------------------------
# P4-6: AWAITING_TRIGGER Intraday Watcher Tests
# -------------------------------------------------------------------------

def test_trigger_watcher_polls_and_executes_breakout():
    """Asserts check_and_execute_triggers() triggers paper orders and updates candidate status to APPROVED."""
    sym = "TEST_TRIG_WATCH"
    cand_id = "cand_trig_watch_1"

    with get_write_connection() as conn:
        conn.execute("DELETE FROM screener_candidates WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        
        # Insert AWAITING_TRIGGER candidate with trigger 150.0 and adtv_20d
        conn.execute("""
            INSERT INTO screener_candidates (
                id, scan_date, symbol, trigger_price, pattern_type, sector, market_cap_tier, circuit_band, adtv_20d, status
            ) VALUES (?, CURRENT_DATE, ?, 150.0, 'MINERVINI_VCP_STAGE2', 'Technology', 'SMALL', 20.0, 10000000.0, 'AWAITING_TRIGGER');
        """, (cand_id, sym))

        # Insert bhavcopy row for ATR calculation
        conn.execute("""
            INSERT INTO bhavcopy_daily (
                symbol, trade_date, open_price, high_price, low_price, close_price,
                total_traded_qty, total_traded_val
            ) VALUES (?, CURRENT_DATE, 145.0, 152.0, 144.0, 148.0, 50000, 7400000.0);
        """, (sym,))

    # Mock yfinance returning live price hitting breakout trigger (High: 153.0 >= 150.0)
    mock_df = pd.DataFrame({
        "Close": [151.0],
        "High": [153.0]
    })

    with patch("yfinance.download", return_value=mock_df), \
         patch("scripts.run_trigger_watcher.send_telegram_alert"), \
         patch("src.notification.telegram_bot.send_telegram_alert"):
        executed = check_and_execute_triggers()

    assert executed == 1

    with get_read_connection() as conn:
        cand_status = conn.execute("SELECT status FROM screener_candidates WHERE id = ?", (cand_id,)).fetchone()[0]
        pos_row = conn.execute("SELECT id, status, entry_price FROM positions WHERE symbol = ?", (sym,)).fetchone()

    assert cand_status == "APPROVED"
    assert pos_row is not None
    assert pos_row[1] == "OPEN"
    assert pos_row[2] > 0


# -------------------------------------------------------------------------
# P4-7: Promoter Pledge History Persistence Tests
# -------------------------------------------------------------------------

def test_promoter_pledge_history_persisted_by_scraper():
    """Asserts scraper persists scraped pledge records to promoter_pledge_history table."""
    sym = "TEST_PLEDGE_PERSIST"
    
    # Ensure no stale cache entry prevents scraping
    with get_write_connection() as conn:
        conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM promoter_pledge_history WHERE symbol = ?", (sym,))

    mock_html = """
    <html>
        <body>
            <ul id="top-ratios">
                <li><span class="name">Stock P/E</span><span class="number">22.5</span></li>
                <li><span class="name">Market Cap</span><span class="number">1,500</span></li>
                <li><span class="name">ROCE</span><span class="number">18.5</span></li>
                <li><span class="name">Debt to equity</span><span class="number">0.15</span></li>
                <li><span class="name">Pledged percentage</span><span class="number">8.75</span></li>
            </ul>
        </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("requests.get", return_value=mock_resp):
        with patch("yfinance.Ticker"):
            funds = scrape_screener_fundamentals(sym)

    assert funds["promoter_pledged_pct"] == 8.75

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT pledge_pct FROM promoter_pledge_history
            WHERE symbol = ?
            ORDER BY quarter_end_date DESC LIMIT 1;
        """, (sym,)).fetchone()

    assert row is not None
    assert float(row[0]) == 8.75


# -------------------------------------------------------------------------
# P4-8 & P4-9: EOD Risk Offload & Equity Curve Daily Snapshot Tests
# -------------------------------------------------------------------------

def test_eod_reconciliation_records_daily_equity_curve_and_offload():
    """Asserts EOD reconciliation writes to equity_curve and executes evaluate_eod_risk_offload()."""
    sym = "TEST_EOD_OFFLOAD"
    pos_id = "pos_eod_offload_1"

    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM equity_curve WHERE trade_date = CURRENT_DATE")

        # Open position with all required NOT NULL fields
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status
            ) VALUES (
                ?, ?, CURRENT_DATE, 100.0, 100, 102.0, 3.0, 95.0, 110.0, 120.0, 500.0, 5.0, 'OPEN'
            );
        """, (pos_id, sym))

        # Current bhavcopy
        conn.execute("""
            INSERT INTO bhavcopy_daily (
                symbol, trade_date, open_price, high_price, low_price, close_price,
                circuit_band_pct, total_traded_qty, total_traded_val
            ) VALUES (?, CURRENT_DATE, 101.0, 103.0, 100.5, 102.0, 20, 10000, 1000000.0);
        """, (sym,))

    offload_called = False
    
    with patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", return_value=None):
        with patch("scripts.run_drawdown_check.check_drawdown"):
            with patch("src.risk.arbiter.evaluate_eod_risk_offload") as mock_offload:
                mock_offload.return_value = {
                    "verdict": "REDUCE_POSITION",
                    "suggested_shares": 50,
                    "shares_to_sell": 50,
                    "reason": "Test macro risk offload"
                }
                with patch("src.notification.telegram_bot.send_telegram_alert"):
                    run_eod_reconciliation_pipeline()
                    offload_called = mock_offload.called

    assert offload_called is True

    # Assert daily snapshot in equity_curve
    with get_read_connection() as conn:
        eq_row = conn.execute("""
            SELECT trade_date, total_equity, core_equity, unrealized_pnl
            FROM equity_curve
            WHERE trade_date = CURRENT_DATE;
        """).fetchone()

    assert eq_row is not None
    assert eq_row[1] > 0  # total_equity > 0

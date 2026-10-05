"""
Regression tests for critical quant, ML, and corporate action fixes (FIN-01, FIN-02, M-03).
"""
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pytest

from src.db.session import init_db, get_read_connection, get_write_connection
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
    base_date = date(2025, 1, 1)
    prices = np.linspace(250.0, 100.0, 200)
    rows = [
        (sym, base_date + timedelta(days=i), float(p), float(p) + 1.0, float(p) - 1.0, float(p), float(p) + 0.5)
        for i, p in enumerate(prices)
    ]
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
            conn.executemany("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val,
                    delivery_qty, delivery_pct, split_multiplier
                ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
            """, rows)

        assert evaluate_mean_reversion(sym) is False
        assert evaluate_mean_reversion_batch([sym])[sym] is False
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))


def test_mr_screener_accepts_uptrend_pullback():
    """Verify mean reversion screener accepts oversold pullbacks that remain above their 200-DMA."""
    init_db()
    sym = "TEST_MR_UP"
    base_date = date(2025, 1, 1)
    uptrend = np.linspace(100.0, 250.0, 185)
    pullback = np.linspace(248.0, 215.0, 15)
    prices = np.concatenate([uptrend, pullback])
    rows = [
        (sym, base_date + timedelta(days=i), float(p), float(p) + 1.0, float(p) - 1.0, float(p), float(p))
        for i, p in enumerate(prices)
    ]
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
            conn.executemany("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val,
                    delivery_qty, delivery_pct, split_multiplier
                ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 10000, 1000000.0, 5000, 50.0, 1.0);
            """, rows)

        assert evaluate_mean_reversion(sym) is True
        assert evaluate_mean_reversion_batch([sym])[sym] is True
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))


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


def test_deterministic_risk_node_returns_total_capital_deployed():
    """Verify deterministic_risk_node includes total_capital_deployed in its returned state dict."""
    from unittest.mock import patch
    from src.agents.debate_graph import deterministic_risk_node

    mock_arbiter_res = {
        "verdict": "APPROVE",
        "suggested_shares": 100,
        "stop_loss_price": 190.0,
        "target_1_price": 220.0,
        "target_2_price": 235.0,
        "risk_reward_ratio": 2.0,
        "total_capital_deployed": 20000.0,
        "portfolio_allocation_pct": 2.0,
        "rejection_reason": "Passed all quantitative gates."
    }

    with patch("src.risk.correlation_guard.evaluate_correlation_guard", return_value=(True, "PASSED", {})), \
         patch("src.agents.debate_graph.calculate_deterministic_risk_and_position", return_value=mock_arbiter_res):
        res = deterministic_risk_node({
            "symbol": "TEST_CAP_DEP",
            "trigger_price": 200.0,
            "current_price": 200.0,
            "fundamentals": {"atr_14": 5.0},
            "circuit_band": 20.0,
            "adtv_20d": 10_000_000.0,
            "market_cap_tier": "LARGE"
        })

    assert "total_capital_deployed" in res
    assert res["total_capital_deployed"] == 20000.0
    assert res["suggested_shares"] == 100


def test_debate_nodes_use_mean_reversion_prompt_framing():
    """Verify bull_analyst_node, bear_hunter_node, and research_judge_node use mean-reversion framing when pattern_type == 'MEAN_REVERSION'."""
    from unittest.mock import patch
    from src.agents.debate_graph import bull_analyst_node, bear_hunter_node, research_judge_node

    init_db()
    sym = "TEST_MR_DEBATE"
    state = {
        "symbol": sym,
        "pattern_type": "MEAN_REVERSION",
        "mr_signal": True,
        "vcp_signal": False,
        "trigger_price": 250.0,
        "current_price": 250.0,
        "stop_loss_price": 240.0,
        "target_1_price": 270.0,
        "target_2_price": 285.0,
        "suggested_shares": 40,
        "adtv_20d": 15_000_000.0,
        "circuit_band": 20.0,
        "fundamentals": {"pe_ratio": 18.0, "roce_pct": 22.0, "profit_growth_pct": 15.0},
        "macro_weather": {"market_regime": "BULLISH_FAVORABLE", "us_vix": 15.0},
        "tv_technical_rating": {"recommendation": "NEUTRAL"},
        "risk_verdict": "APPROVE",
        "rejection_reason": ""
    }

    try:
        with patch("src.agents.debate_graph.execute_llm_completion") as mock_llm:
            mock_llm.return_value = "• Oversold RSI bounce above 200-DMA\n• Strong ROCE\n• Asymmetric pullback"
            bull_out = bull_analyst_node(state)
            bull_messages = mock_llm.call_args[0][0]
            bull_prompt = bull_messages[1]["content"]
            assert "Oversold 200-DMA Structural Uptrend Pullback" in bull_prompt
            assert "lacking a VCP Stage 2 volume breakout" in bull_prompt

            state["bull_thesis"] = bull_out["bull_thesis"]
            mock_llm.return_value = "• 200-DMA breakdown risk\n• Sector headwind\n• Falling knife check"
            bear_out = bear_hunter_node(state)
            bear_messages = mock_llm.call_args[0][0]
            bear_prompt = bear_messages[1]["content"]
            assert "Oversold 200-DMA Structural Uptrend Pullback" in bear_prompt

            state["bear_risks"] = bear_out["bear_risks"]
            mock_llm.return_value = "SYNTHESIS: Strong mean reversion pullback above 200-DMA.\nCONVICTION_SCORE: 8.0"
            judge_out = research_judge_node(state)
            judge_messages = mock_llm.call_args[0][0]
            judge_prompt = judge_messages[1]["content"]
            assert "Oversold 200-DMA Structural Uptrend Pullback" in judge_prompt
            assert "Pattern: MEAN_REVERSION" in judge_prompt
            assert judge_out["conviction_score"] == 8.0
    finally:
        db_write("DELETE FROM agent_memory WHERE symbol = ?;", (sym,), sync=True)


def test_ml_features_uses_canonical_benchmark_provider():
    """Verify ml_features._get_benchmark_data() uses get_benchmark_ohlc and defaults missing market_regime to 0."""
    from unittest.mock import patch
    import pandas as pd
    import src.screening.ml_features as ml_feat

    dates = pd.date_range("2025-01-01", periods=80, freq="B")
    mock_bench_df = pd.DataFrame({
        "Close": np.linspace(20000.0, 22000.0, 80)
    }, index=dates)

    ml_feat._benchmark_cache = None
    try:
        with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=mock_bench_df) as mock_get_bench:
            bench = ml_feat._get_benchmark_data()
            mock_get_bench.assert_called_once()
            assert bench is not None
            assert "rsi" in bench.columns
            assert "regime" in bench.columns

        # Also verify duplicate / same-day benchmark timestamps normalize and deduplicate cleanly
        ml_feat._benchmark_cache = None
        dup_dates = pd.DatetimeIndex(list(dates[:40]) + [dates[39] + pd.Timedelta(hours=15), dates[39]] + list(dates[40:]))
        dup_bench_df = pd.DataFrame({
            "Close": np.linspace(20000.0, 22000.0, len(dup_dates))
        }, index=dup_dates)
        with patch("src.utils.benchmark_provider.get_benchmark_ohlc", return_value=dup_bench_df):
            sym_df = pd.DataFrame({
                "trade_date": dates,
                "close_price": np.linspace(100.0, 120.0, 80),
                "high_price": np.linspace(101.0, 121.0, 80),
                "low_price": np.linspace(99.0, 119.0, 80),
                "total_traded_qty": [10000] * 80
            })
            feat_df_dup = ml_feat.extract_quantitative_features(sym_df)
            assert len(feat_df_dup) == 80
            assert not feat_df_dup["market_regime"].isna().any()

        # Also verify fallback to market_regime = 0 when benchmark is unavailable
        ml_feat._benchmark_cache = None
        with patch("src.utils.benchmark_provider.get_benchmark_ohlc", side_effect=RuntimeError("Offline")):
            sym_df = pd.DataFrame({
                "trade_date": dates,
                "close_price": np.linspace(100.0, 120.0, 80),
                "high_price": np.linspace(101.0, 121.0, 80),
                "low_price": np.linspace(99.0, 119.0, 80),
                "total_traded_qty": [10000] * 80
            })
            feat_df = ml_feat.extract_quantitative_features(sym_df)
            assert (feat_df["market_regime"] == 0).all()
    finally:
        ml_feat._benchmark_cache = None


def test_live_preview_mean_reversion_trigger_price_and_state_input():
    """Verify MEAN_REVERSION candidate in run_live_preview.py gets trigger_price == current_price and passes pattern_type into state_input."""
    import datetime
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from scripts.run_live_preview import run_live_preview_pipeline

    init_db()
    sym = "TEST_MR_PREVIEW"
    base_date = datetime.date(2026, 9, 1)

    with get_read_connection() as conn:
        saved_mw_df = conn.execute("SELECT * FROM macro_weather WHERE scan_date = CURRENT_DATE").df()

    with get_write_connection() as conn:
        conn.execute("DELETE FROM macro_weather WHERE scan_date = CURRENT_DATE;")
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
        conn.execute("DELETE FROM screener_candidates WHERE symbol = ?;", (sym,))
        conn.execute("DELETE FROM debate_transcripts WHERE symbol = ?;", (sym,))
        for i in range(25):
            d = base_date + datetime.timedelta(days=i)
            conn.execute("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val, circuit_band_pct
                ) VALUES (?, ?, 'EQ', 240.0, 245.0, 235.0, 240.0, 239.0, 50000, 12000000.0, 20.0);
            """, (sym, d))

    fake_now = datetime.datetime(
        2026, 10, 7, 15, 15, 0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    )

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now

    mock_macro = {
        "us_vix": 26.0, "sp500_pct_change": -1.5, "crude_oil_price": 80.0,
        "crude_oil_pct_change": 1.0, "usdinr_price": 86.0, "usdinr_pct_change": 0.1,
        "polymarket_risk_score": 0.5, "market_regime": "HIGH_RISK",
        "macro_weather_score": 0.35, "target_cash_exposure_pct": 70.0, "source": "TEST"
    }

    captured_state_inputs = []
    mock_debate_app = MagicMock()

    def fake_invoke(state_in, config=None):
        captured_state_inputs.append(dict(state_in))
        out = dict(state_in)
        out.update({
            "risk_verdict": "REJECT",
            "conviction_score": 5.0,
            "rejection_reason": "Test reject"
        })
        return out

    mock_debate_app.invoke.side_effect = fake_invoke
    captured_alerts = []

    try:
        with patch("scripts.run_live_preview.is_system_halted", return_value=False), \
             patch("scripts.run_live_preview.is_nse_holiday", return_value=False), \
             patch("scripts.run_live_preview.datetime.datetime", FakeDatetime), \
             patch("scripts.run_live_preview.fetch_macro_weather_data", return_value=mock_macro), \
             patch("scripts.run_live_preview.get_active_universe", return_value=[(sym, "EQ", 20.0)]), \
             patch("scripts.run_live_preview.evaluate_minervini_vcp_batch", return_value=[]), \
             patch("scripts.run_live_preview.evaluate_mean_reversion_batch", return_value={sym: True}), \
             patch("scripts.run_live_preview.evaluate_ml_probability", return_value=0.72), \
             patch("scripts.run_live_preview.yf.download", return_value=pd.DataFrame()), \
             patch("scripts.run_live_preview.scrape_screener_fundamentals", return_value={"sector_name": "IT", "market_cap_crores": 5000.0}), \
             patch("scripts.run_live_preview.check_shariah_compliance", return_value=(True, "PASSED_SHARIAH_GATE")), \
             patch("scripts.run_live_preview.evaluate_anti_trap_shield", return_value=(True, "PASSED", {})), \
             patch("scripts.run_live_preview.get_tradingview_technical_ratings", return_value={"recommendation": "BUY"}), \
             patch("scripts.run_live_preview.build_debate_graph", return_value=mock_debate_app), \
             patch("src.notification.telegram_bot.send_telegram_alert", side_effect=lambda msg: captured_alerts.append(msg)):

            run_live_preview_pipeline()

        assert len(captured_state_inputs) == 1
        st = captured_state_inputs[0]
        assert st["symbol"] == sym
        assert st["pattern_type"] == "MEAN_REVERSION"
        assert st["trigger_price"] == st["current_price"] == 240.0
        assert st["mr_signal"] is True
        assert st["vcp_signal"] is False

        # Verify 3:15 PM Telegram scan summary accurately classifies HIGH_RISK as Defensive
        assert len(captured_alerts) >= 1
        assert "🔴 Defensive (HIGH_RISK / Market Correction)" in captured_alerts[-1]
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
            conn.execute("DELETE FROM screener_candidates WHERE symbol = ?;", (sym,))
            conn.execute("DELETE FROM debate_transcripts WHERE symbol = ?;", (sym,))
            if not saved_mw_df.empty:
                conn.register("saved_mw_df", saved_mw_df)
                conn.execute("INSERT OR REPLACE INTO macro_weather SELECT * FROM saved_mw_df")
                conn.unregister("saved_mw_df")


def test_eod_reconciliation_skips_nse_holidays_and_omits_duplicate_drawdown():
    """
    Verify run_eod_reconciliation_pipeline skips weekday NSE holidays (e.g. 2026-10-02 Gandhi Jayanti),
    does not invoke duplicate check_drawdown(), and fetch_bhavcopy_with_retry_and_fallback short-circuits
    when fyers_client.model is None.
    """
    import datetime
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline
    from src.ingestion.bhavcopy import fetch_bhavcopy_with_retry_and_fallback
    from src.ingestion.fyers_client import fyers_client

    fetched_dates = []
    fake_now = datetime.datetime(
        2026, 10, 5, 18, 30, 0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    )

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now

    mock_conn = MagicMock()

    def exec_side_effect(query, params=None):
        m = MagicMock()
        if "SELECT MAX(trade_date)" in query and "JOIN" not in query:
            # Last ingested date was Thursday 2026-10-01; Friday 2026-10-02 is Gandhi Jayanti (NSE holiday)
            m.fetchone.return_value = [datetime.date(2026, 10, 1)]
        else:
            m.fetchall.return_value = []
            m.fetchone.return_value = None
        return m

    mock_conn.execute.side_effect = exec_side_effect
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_conn

    with patch("scripts.run_eod_reconciliation.datetime", FakeDatetime), \
         patch("scripts.run_eod_reconciliation.get_read_connection", return_value=mock_ctx), \
         patch("scripts.run_eod_reconciliation.db_write"), \
         patch("scripts.run_eod_reconciliation.is_system_halted", return_value=False), \
         patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", side_effect=lambda d: fetched_dates.append(d) or None), \
         patch("scripts.run_drawdown_check.check_drawdown") as mock_dd:
        run_eod_reconciliation_pipeline()

    # Friday 2026-10-02 (Gandhi Jayanti) and Sat/Sun (Oct 3-4) must be skipped; only Monday 2026-10-05 fetched
    assert datetime.date(2026, 10, 2) not in fetched_dates
    assert fetched_dates == [datetime.date(2026, 10, 5)]
    mock_dd.assert_not_called()

    # Verify fetch_bhavcopy_with_retry_and_fallback returns None immediately when fyers_client.model is None
    mock_im_conn = MagicMock()
    mock_im_conn.execute.return_value.df.return_value = pd.DataFrame({"symbol": ["RELIANCE", "TCS", "INFY"]})
    mock_im_ctx = MagicMock()
    mock_im_ctx.__enter__.return_value = mock_im_conn

    with patch("jugaad_data.nse.bhavcopy_save", side_effect=RuntimeError("404 Not Found")), \
         patch("src.db.session.get_read_connection", return_value=mock_im_ctx), \
         patch.object(fyers_client, "model", None), \
         patch.object(fyers_client, "fetch_historical_data") as mock_hist:
        res = fetch_bhavcopy_with_retry_and_fallback(datetime.date(2026, 10, 2), max_retries=1)
        assert res is None
        mock_hist.assert_not_called()


def test_vcp_screener_150_bar_min_periods_for_182_day_corpus():
    """
    Verify evaluate_minervini_vcp_batch (and evaluate_vcp_stage2_batch) qualifies a Stage 2 VCP stock
    with 182 trading days (< 200 bars) using rolling(200, min_periods=150), while rejecting < 150 bars.
    """
    import duckdb
    import pandas as pd
    from unittest.mock import patch
    from src.screening.vcp_screener import evaluate_minervini_vcp_batch, evaluate_vcp_stage2_batch

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
    """)

    base_d = date(2025, 12, 26)
    # 182 bars: first 170 bars steady uptrend from 100 to 220 with normal swing, last 12 bars tight contraction at ~222 with volume dryup
    for i in range(182):
        d = base_d + timedelta(days=i)
        if i < 170:
            c_p = 100.0 + (i * 0.70) + ((i % 3 - 1) * 1.8)
            vol = 50000
        else:
            c_p = 222.0 + ((i % 2) * 0.15)
            vol = 5000
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES (?, ?, ?, ?, ?, ?, 55.0, 'EQ', FALSE, FALSE)",
            ("TEST_VCP_182", d, c_p, c_p + 1.0, c_p - 1.0, vol)
        )

    # Also insert a 140-bar symbol (< 150 minimum rows)
    for i in range(140):
        d = base_d + timedelta(days=i)
        c_p = 100.0 + (i * 0.8)
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES (?, ?, ?, ?, ?, ?, 55.0, 'EQ', FALSE, FALSE)",
            ("TEST_VCP_140", d, c_p, c_p + 1.0, c_p - 1.0, 10000 if i >= 120 else 50000)
        )

    with patch("src.utils.benchmark_provider.get_market_regime", return_value=1), \
         patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.0005] * 100)):
        res = evaluate_vcp_stage2_batch(
            ["TEST_VCP_182", "TEST_VCP_140"],
            mem_conn,
            live_prices={"TEST_VCP_182": 222.15, "TEST_VCP_140": 212.0}
        )

    assert len(res) == 1
    assert res[0]["symbol"] == "TEST_VCP_182"
    assert res[0]["sma_200"] > 0
    assert res[0]["sma_150"] > res[0]["sma_200"]


def test_screener_scraper_sector_extraction_balance_sheet_and_etf_pledge_guard():
    """
    Verify screener_scraper extracts sector_name from /market/ links (and preserves prohibited sub-industries),
    parses Inventory and Trade receivables, skips promoter_pledge_history inserts when ratios is empty (ETFs),
    and computes pledge_trend_3m against prior-date records across repeat same-day scrapes.
    """
    from unittest.mock import patch, MagicMock
    from src.ingestion.screener_scraper import fetch_screener_fundamentals

    init_db()
    sym_co = "TEST_SCRAPE_SEC"
    sym_etf = "TEST_ETF_EMPTY"

    with get_write_connection() as conn:
        for s in (sym_co, sym_etf):
            conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (s,))
            conn.execute("DELETE FROM promoter_pledge_history WHERE symbol = ?", (s,))
        # Seed a prior pledge record 45 days ago at 2.5%
        conn.execute("""
            INSERT INTO promoter_pledge_history (symbol, quarter_end_date, pledge_pct)
            VALUES (?, CURRENT_DATE - INTERVAL '45 days', 2.5)
        """, (sym_co,))

    html_co = """
    <html><body>
        <ul id="top-ratios">
            <li><span class="name">Stock P/E</span><span class="number">24.0</span></li>
            <li><span class="name">Market Cap</span><span class="number">4,200</span></li>
            <li><span class="name">ROCE</span><span class="number">21.0</span></li>
            <li><span class="name">Debt to equity</span><span class="number">0.10</span></li>
            <li><span class="name">Pledged percentage</span><span class="number">6.0</span></li>
        </ul>
        <section id="peers">
            <p class="sub">
                <a href="/market/IN08/" title="Broad Sector">Information Technology</a>
                <a href="/market/IN08/IN0801/" title="Sector">Information Technology</a>
                <a href="/market/IN08/IN0801/IN080101/" title="Industry">IT - Software</a>
            </p>
        </section>
        <section id="profit-loss">
            <table>
                <tr><td>Sales</td><td>1000</td><td>1200</td></tr>
                <tr><td>Other Income</td><td>10</td><td>15</td></tr>
            </table>
        </section>
        <section id="balance-sheet">
            <table>
                <tr><td>Borrowings</td><td>50</td><td>60</td></tr>
                <tr><td>Other Liabilities</td><td>100</td><td>140</td></tr>
                <tr><td>Fixed Assets</td><td>300</td><td>350</td></tr>
                <tr><td>CWIP</td><td>10</td><td>20</td></tr>
                <tr><td>Inventory</td><td>80</td><td>90</td></tr>
                <tr><td>Trade receivables</td><td>110</td><td>130</td></tr>
                <tr><td>Total Assets</td><td>900</td><td>1000</td></tr>
            </table>
        </section>
    </body></html>
    """

    resp_co = MagicMock(status_code=200, text=html_co)
    resp_etf = MagicMock(status_code=200, text="<html><body><ul id='top-ratios'></ul></body></html>")

    try:
        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("requests.get", return_value=resp_co), \
             patch("yfinance.Ticker"):
            funds1 = fetch_screener_fundamentals(sym_co)

        assert funds1["sector_name"] == "Information Technology"
        assert funds1["inventories"] == 90.0
        assert funds1["trade_receivables"] == 130.0
        assert funds1["accounts_receivable"] == 130.0
        assert pytest.approx(funds1["pledge_trend_3m"], rel=1e-6) == 3.5  # 6.0 - 2.5

        # Clear fundamentals_cache and re-scrape on the same day: pledge_trend_3m must still be 3.5, NOT 0.0
        with get_write_connection() as conn:
            conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (sym_co,))

        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("requests.get", return_value=resp_co), \
             patch("yfinance.Ticker"):
            funds2 = fetch_screener_fundamentals(sym_co)
        assert pytest.approx(funds2["pledge_trend_3m"], rel=1e-6) == 3.5

        # Scrape ETF with empty ratios: must NOT insert into promoter_pledge_history
        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("requests.get", return_value=resp_etf), \
             patch("yfinance.Ticker"):
            fetch_screener_fundamentals(sym_etf)

        with get_read_connection() as conn:
            etf_pledge_rows = conn.execute(
                "SELECT COUNT(*) FROM promoter_pledge_history WHERE symbol = ?", (sym_etf,)
            ).fetchone()[0]
        assert etf_pledge_rows == 0
    finally:
        with get_write_connection() as conn:
            for s in (sym_co, sym_etf):
                conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (s,))
                conn.execute("DELETE FROM promoter_pledge_history WHERE symbol = ?", (s,))


def test_live_preview_rejects_mean_reversion_when_live_tick_drops_below_sma200():
    """
    Verify Pass 3 in run_live_preview_pipeline rejects a MEAN_REVERSION candidate whose
    3:15 PM live tick drops at or below its 200-DMA (e.g. SHANKARA 124.40 -> 117.90 < sma_200=122.92).
    """
    import datetime
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from scripts.run_live_preview import run_live_preview_pipeline

    init_db()
    sym = "TEST_SHANKARA_MR"
    base_date = datetime.date(2026, 3, 1)

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
        conn.execute("DELETE FROM screener_candidates WHERE symbol = ?;", (sym,))
        for i in range(160):
            d = base_date + datetime.timedelta(days=i)
            # 160 bars: first 145 bars around 122.5, last 15 bars pullback from 135 to 124.40 (SMA_200 ~ 122.9)
            c_p = 122.5 if i < 145 else (135.0 - (i - 145) * 0.75)
            conn.execute("""
                INSERT OR REPLACE INTO bhavcopy_daily (
                    symbol, trade_date, series, open_price, high_price, low_price,
                    close_price, prev_close, total_traded_qty, total_traded_val, circuit_band_pct
                ) VALUES (?, ?, 'EQ', ?, ?, ?, ?, ?, 50000, 15000000.0, 20.0);
            """, (sym, d, c_p, c_p + 1.0, c_p - 1.0, c_p, c_p))

    fake_now = datetime.datetime(
        2026, 10, 7, 15, 15, 0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    )

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now

    # Live 3:15 PM tick drops to 117.90 (below SMA_200 ~ 123.1)
    live_tick_df = pd.DataFrame({"Close": [117.90]})
    mock_debate_app = MagicMock()

    try:
        with patch("scripts.run_live_preview.is_system_halted", return_value=False), \
             patch("scripts.run_live_preview.is_nse_holiday", return_value=False), \
             patch("scripts.run_live_preview.datetime.datetime", FakeDatetime), \
             patch("scripts.run_live_preview.get_active_universe", return_value=[(sym, "EQ", 20.0)]), \
             patch("scripts.run_live_preview.evaluate_minervini_vcp_batch", return_value=[]), \
             patch("scripts.run_live_preview.evaluate_ml_probability", return_value=0.80), \
             patch("scripts.run_live_preview.yf.download", return_value=live_tick_df), \
             patch("scripts.run_live_preview.scrape_screener_fundamentals") as mock_scrape, \
             patch("scripts.run_live_preview.build_debate_graph", return_value=mock_debate_app), \
             patch("src.notification.telegram_bot.send_telegram_alert"):
            run_live_preview_pipeline()

        # Candidate must be rejected in Pass 3 before Pass 4 (scrape) and Pass 5 (debate)
        mock_scrape.assert_not_called()
        mock_debate_app.invoke.assert_not_called()
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?;", (sym,))
            conn.execute("DELETE FROM screener_candidates WHERE symbol = ?;", (sym,))


def test_trigger_watcher_chronological_atr_intraday_max_high_and_arbiter_targets():
    """
    Verify check_and_execute_triggers computes Wilder's ATR on chronologically ascending bhavcopy rows,
    detects breakouts via high_series.max() across intraday 5m bars, passes DB macro_weather and
    candidate adtv_20d to Arbiter, and uses Arbiter's stop_loss_price / target_1_price / target_2_price.
    """
    import pandas as pd
    from unittest.mock import patch
    from scripts.run_trigger_watcher import check_and_execute_triggers
    from src.utils.technical_indicators import atr as calc_atr

    init_db()
    sym = "TEST_TW_CHRONO"
    cand_id = "cand_tw_chrono_1"
    base_d = date(2026, 9, 1)

    highs, lows, closes = [], [], []
    with get_write_connection() as conn:
        conn.execute("DELETE FROM screener_candidates WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))
        conn.execute("""
            INSERT INTO screener_candidates (
                id, scan_date, symbol, trigger_price, pattern_type, sector,
                market_cap_tier, circuit_band, adtv_20d, status
            ) VALUES (?, CURRENT_DATE, ?, 200.0, 'MINERVINI_VCP_STAGE2', 'Technology', 'MID', 20.0, 25000000.0, 'AWAITING_TRIGGER');
        """, (cand_id, sym))

        # Early bars have wide range (20.0), recent bars have tight range (2.0) -> ASC vs DESC Wilder's ATR diverge sharply
        for i in range(20):
            d = base_d + timedelta(days=i)
            rng = 20.0 if i < 10 else 2.0
            c_p = 195.0
            h_p = c_p + rng / 2.0
            l_p = c_p - rng / 2.0
            highs.append(h_p)
            lows.append(l_p)
            closes.append(c_p)
            conn.execute("""
                INSERT INTO bhavcopy_daily (
                    symbol, trade_date, open_price, high_price, low_price, close_price,
                    total_traded_qty, total_traded_val
                ) VALUES (?, ?, ?, ?, ?, ?, 100000, 25000000.0);
            """, (sym, d, c_p, h_p, l_p, c_p))

    expected_chrono_atr = float(calc_atr(pd.Series(highs), pd.Series(lows), pd.Series(closes)).iloc[-1])
    wrong_desc_atr = float(calc_atr(pd.Series(highs[::-1]), pd.Series(lows[::-1]), pd.Series(closes[::-1])).iloc[-1])
    assert abs(expected_chrono_atr - wrong_desc_atr) > 1.0

    # Intraday 5m bars: earlier bar spiked to 201.5 (>= 200.0 trigger), latest bar High is 199.8, Close is 200.2
    mock_intraday = pd.DataFrame({
        "Close": [199.0, 201.0, 200.2],
        "High": [199.5, 201.5, 199.8],
    })

    mock_arbiter_res = {
        "suggested_shares": 25,
        "stop_loss_price": 191.25,
        "target_1_price": 217.50,
        "target_2_price": 230.65,
    }

    try:
        with patch("scripts.run_trigger_watcher.is_system_halted", return_value=False), \
             patch("scripts.run_trigger_watcher.yf.download", return_value=mock_intraday), \
             patch("scripts.run_trigger_watcher.calculate_deterministic_risk_and_position", return_value=mock_arbiter_res) as mock_arb, \
             patch("src.execution.order_manager.PaperBroker.place_order", return_value="ORD_TW_1") as mock_order, \
             patch("scripts.run_trigger_watcher.send_telegram_alert"):
            executed = check_and_execute_triggers()

        assert executed == 1
        arb_kwargs = mock_arb.call_args.kwargs
        assert pytest.approx(arb_kwargs["atr_14"], rel=1e-6) == expected_chrono_atr
        assert arb_kwargs["adtv_20d"] == 25000000.0

        order_kwargs = mock_order.call_args.kwargs
        assert order_kwargs["initial_stop"] == 191.25
        assert order_kwargs["target_1"] == 217.50
        assert order_kwargs["target_2"] == 230.65
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM screener_candidates WHERE symbol = ?", (sym,))
            conn.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym,))


def test_settings_fallback_llm_1_and_scheduler_stdout_tail_on_success(caplog):
    """Verify FALLBACK_LLM_1 defaults to groq/llama-3.3-70b-versatile and run_script logs stdout tail on success."""
    from unittest.mock import patch, MagicMock
    from src.config.settings import Settings
    from scripts.run_scheduler import run_script

    assert Settings().FALLBACK_LLM_1 == "groq/llama-3.3-70b-versatile"

    mock_proc = MagicMock(
        returncode=0,
        stdout="Line 1\nLine 2: Step completed\nFinal summary: 3 candidates approved\n",
        stderr=""
    )
    with patch("scripts.run_scheduler.subprocess.run", return_value=mock_proc), \
         caplog.at_level("INFO", logger="master_scheduler"):
        ok = run_script("run_live_preview.py", timeout_seconds=10)

    assert ok is True
    assert "Final summary: 3 candidates approved" in caplog.text



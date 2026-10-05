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



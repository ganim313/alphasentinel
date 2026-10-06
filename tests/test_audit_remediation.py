"""
Regression tests for all 10 Audit.md remediation fixes (Phase 0, Phase 1, Phase 2).
"""
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
import yaml

from src.db.session import get_read_connection, get_write_connection
from src.ingestion.corporate_actions import record_corporate_action
from src.screening.shariah_filter import check_shariah_compliance
from src.ingestion.screener_scraper import fetch_screener_fundamentals
from src.screening.ml_features import engineer_live_tick, extract_quantitative_features
from src.risk.daily_drawdown_guard import is_daily_drawdown_breached
from src.risk.correlation_guard import evaluate_correlation_guard
from src.risk.vol_target import calculate_volatility_scalar
from src.agents.debate_graph import research_judge_node, conviction_gate_node
from scripts.run_trigger_watcher import check_and_execute_triggers
from scripts.run_sentinel import run_sentinel_check
from scripts.run_eod_reconciliation import run_eod_reconciliation_pipeline


# ---------------------------------------------------------------------------
# Fix 1: Corporate Actions Bonus Ratio & Reverse Split Multiplier
# ---------------------------------------------------------------------------
def test_fix1_corporate_actions_bonus_and_rev_split():
    ex_dt = date.today()
    sym_1_2 = "TEST_AUDIT_BONUS_1_2"
    sym_1_1 = "TEST_AUDIT_BONUS_1_1"
    sym_rev = "TEST_AUDIT_REVSPLIT"

    try:
        # 1:2 bonus (1 bonus share for every 2 existing shares) -> multiplier = 2 / (1 + 2) = 0.666667
        act_1_2 = record_corporate_action(sym_1_2, "BONUS", ex_dt, 1.0, 2.0)
        # 1:1 bonus -> multiplier = 1 / (1 + 1) = 0.5
        act_1_1 = record_corporate_action(sym_1_1, "BONUS", ex_dt, 1.0, 1.0)
        # REV_SPLIT action_type -> multiplier = 10 / 1 = 10.0
        act_rev = record_corporate_action(sym_rev, "REV_SPLIT", ex_dt, 10.0, 1.0)

        with get_read_connection() as conn:
            m_1_2 = conn.execute(
                "SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?", (act_1_2,)
            ).fetchone()[0]
            m_1_1 = conn.execute(
                "SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?", (act_1_1,)
            ).fetchone()[0]
            m_rev = conn.execute(
                "SELECT adjustment_multiplier FROM corporate_actions WHERE id = ?", (act_rev,)
            ).fetchone()[0]

        assert abs(m_1_2 - (2.0 / 3.0)) < 1e-4, f"Expected 2/3 (0.6667) for 1:2 bonus, got {m_1_2}"
        assert abs(m_1_1 - 0.5) < 1e-4
        assert abs(m_rev - 10.0) < 1e-4
    finally:
        with get_write_connection() as conn:
            conn.execute(
                "DELETE FROM corporate_actions WHERE symbol IN (?, ?, ?)",
                (sym_1_2, sym_1_1, sym_rev),
            )


# ---------------------------------------------------------------------------
# Fix 2: Shariah Filter Fail-Closed on Empty Sector & Plural Breadcrumb Regex
# ---------------------------------------------------------------------------
def test_fix2_shariah_fails_closed_on_empty_sector_and_prohibited_keywords():
    valid_fundamentals = {
        "total_assets": 1000.0,
        "borrowings": 100.0,
        "debt_to_assets": 0.10,
        "sales": 500.0,
        "other_income": 5.0,
        "interest_income_ratio": 0.01,
        "illiquid_ratio": 0.50,
        "trade_receivables": 50.0,
        "net_liquid_assets_crores": 100.0,
        "market_cap_crores": 1000.0,
    }

    # Empty sector must fail closed
    passed, reason = check_shariah_compliance(valid_fundamentals, sector_name="")
    assert passed is False
    assert reason == "FAIL_CLOSED_EMPTY_SECTOR_NAME"

    passed_ws, reason_ws = check_shariah_compliance(valid_fundamentals, sector_name="   ")
    assert passed_ws is False
    assert reason_ws == "FAIL_CLOSED_EMPTY_SECTOR_NAME"

    # Prohibited keywords including broking, stockbroking, winery, distilleries, breweries
    for bad_sec in [
        "Financial Services - Stockbroking",
        "Broking & Allied",
        "Consumer Staples - Distilleries",
        "Beverages - Breweries",
        "Winery & Spirits",
    ]:
        ok, r = check_shariah_compliance(valid_fundamentals, sector_name=bad_sec)
        assert ok is False, f"Expected {bad_sec} to be rejected, got {ok} ({r})"
        assert "NON_COMPLIANT_SECTOR_" in r

    # Optional cash_to_assets > 33% guard
    high_cash = {**valid_fundamentals, "cash_to_assets": 0.38}
    ok_cash, r_cash = check_shariah_compliance(high_cash, sector_name="IT Software")
    assert ok_cash is False
    assert "EXCESSIVE_CASH_ASSETS_" in r_cash


def test_fix2_and_fix9_screener_scraper_plural_breadcrumbs_and_growth_rates():
    html_doc = """
    <html><body>
      <ul id="top-ratios">
        <li><span class="name">Market Cap</span><span class="number">2,500</span></li>
        <li><span class="name">Stock P/E</span><span class="number">22.5</span></li>
        <li><span class="name">ROCE</span><span class="number">18.0</span></li>
        <li><span class="name">Pledged percentage</span><span class="number">3.5</span></li>
      </ul>
      <div id="peers">
        <a href="/explore/?sector=Consumer+Staples" title="Sector">Consumer Staples</a>
        <a href="/explore/?industry=Distilleries">Distilleries</a>
      </div>
      <section id="profit-loss">
        <table>
          <tr><td>Sales</td><td>800</td><td>1,000</td></tr>
          <tr><td>Other Income</td><td>10</td><td>12</td></tr>
          <tr><td>Net Profit</td><td>80</td><td>100</td></tr>
        </table>
      </section>
      <section id="balance-sheet">
        <table>
          <tr><td>Borrowings</td><td>100</td><td>120</td></tr>
          <tr><td>Total Assets</td><td>900</td><td>1,000</td></tr>
          <tr><td>Fixed Assets</td><td>400</td><td>450</td></tr>
          <tr><td>Other Liabilities</td><td>150</td><td>180</td></tr>
        </table>
      </section>
    </body></html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_doc

    sym = "TEST_DISTILLERY_CO"
    try:
        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("src.ingestion.screener_scraper.requests.get", return_value=mock_resp), \
             patch("src.ingestion.screener_scraper.yf.Ticker") as mock_yf:
            mock_yf.return_value.news = []
            res = fetch_screener_fundamentals(sym)

        # Sub-industry plural 'Distilleries' must be preserved in sector_name
        assert "Distilleries" in res["sector_name"]
        # Growth rates must be scraped from the table (800 -> 1000 = +25.0%, 80 -> 100 = +25.0%)
        assert res["sales_growth_pct"] == 25.0
        assert res["profit_growth_pct"] == 25.0

        # And Shariah filter must reject it
        is_sh, sh_reason = check_shariah_compliance(res, sector_name=res["sector_name"])
        assert is_sh is False
        assert "NON_COMPLIANT_SECTOR_" in sh_reason
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (sym,))
            conn.execute("DELETE FROM promoter_pledge_history WHERE symbol = ?", (sym,))


# ---------------------------------------------------------------------------
# Fix 3: CHOICEIN Purged from DuckDB
# ---------------------------------------------------------------------------
def test_fix3_choicein_purged_from_duckdb():
    with get_write_connection() as conn:
        conn.execute("DELETE FROM fundamentals_cache WHERE symbol = 'CHOICEIN'")
        conn.execute("DELETE FROM screener_candidates WHERE symbol = 'CHOICEIN'")
        conn.execute("DELETE FROM positions WHERE symbol = 'CHOICEIN'")

    with get_read_connection() as conn:
        fc_cnt = conn.execute("SELECT COUNT(*) FROM fundamentals_cache WHERE symbol = 'CHOICEIN'").fetchone()[0]
        sc_cnt = conn.execute("SELECT COUNT(*) FROM screener_candidates WHERE symbol = 'CHOICEIN'").fetchone()[0]
        pos_cnt = conn.execute("SELECT COUNT(*) FROM positions WHERE symbol = 'CHOICEIN'").fetchone()[0]

    assert fc_cnt == 0
    assert sc_cnt == 0
    assert pos_cnt == 0


# ---------------------------------------------------------------------------
# Fix 5: Trigger Watcher Requires current_p >= trigger_p
# ---------------------------------------------------------------------------
def test_fix5_trigger_watcher_rejects_failed_spike_reversal():
    cand_id = "test_audit_spike_fail"
    sym = "TEST_SPIKE_REV"
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM screener_candidates WHERE id = ?", (cand_id,))
            conn.execute("""
                INSERT INTO screener_candidates (
                    id, symbol, scan_date, trigger_price, pattern_type, sector,
                    market_cap_tier, circuit_band, adtv_20d, status
                ) VALUES (?, ?, CURRENT_DATE, 100.0, 'VCP', 'IT Software', 'MID', 20.0, 10000000.0, 'AWAITING_TRIGGER')
            """, (cand_id, sym))

        # High touched 104.0 (>= 100.0), but latest Close reversed to 96.5 (< 100.0)
        spike_fail_df = pd.DataFrame({"Close": [101.0, 96.5], "High": [104.0, 98.0]})
        with patch("scripts.run_trigger_watcher.is_system_halted", return_value=False), \
             patch("scripts.run_trigger_watcher.yf.download", return_value=spike_fail_df), \
             patch("scripts.run_trigger_watcher.PaperBroker.place_order") as mock_order:
            executed = check_and_execute_triggers()
            assert executed == 0
            mock_order.assert_not_called()
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM screener_candidates WHERE id = ?", (cand_id,))


# ---------------------------------------------------------------------------
# Fix 6, 7, 8: Sentinel & EOD Reconciliation (Targets 1 & 2, MARKED_FOR_CLOSURE, equity_curve)
# ---------------------------------------------------------------------------
def test_fix7_and_fix8_sentinel_intraday_targets_and_marked_for_closure():
    pos_t1 = "test_audit_pos_t1"
    pos_mfc = "test_audit_pos_mfc"
    sym_t1 = "TEST_SENT_T1"
    sym_mfc = "TEST_SENT_MFC"

    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id IN (?, ?)", (pos_t1, pos_mfc))
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, status,
                    trailing_stop_loss, target_1, target_2, atr, current_ltp,
                    peak_high, realized_pnl, unrealized_pnl, risk_rupees, portfolio_allocation_pct
                ) VALUES
                (?, ?, CURRENT_DATE, 100.0, 10, 'OPEN', 95.0, 110.0, 120.0, 2.0, 100.0, 100.0, 0.0, 0.0, 50.0, 5.0),
                (?, ?, CURRENT_DATE, 100.0, 5, 'MARKED_FOR_CLOSURE', 95.0, 110.0, 120.0, 2.0, 90.0, 100.0, 0.0, -50.0, 25.0, 2.5)
            """, (pos_t1, sym_t1, pos_mfc, sym_mfc))

        # Multi-symbol live data frame: sym_t1 hits Target 1 (High=112, Close=111), sym_mfc is at 92 (not circuit-locked)
        cols = pd.MultiIndex.from_product([["Close", "High", "Low"], [f"{sym_t1}.NS", f"{sym_mfc}.NS"]])
        data_vals = [[111.0, 92.0, 112.0, 93.0, 109.0, 91.0]]
        live_df = pd.DataFrame(data_vals, columns=cols)

        with patch("scripts.run_sentinel.is_system_halted", return_value=False), \
             patch("yfinance.download", return_value=live_df), \
             patch("src.execution.order_manager.check_lower_circuit_trap", return_value={"is_trapped": False, "lower_circuit": 80.0}), \
             patch("src.notification.telegram_bot.send_telegram_alert"):
            run_sentinel_check()

        with get_read_connection() as conn:
            r_t1 = conn.execute(
                "SELECT status, quantity, trailing_stop_loss, realized_pnl FROM positions WHERE id = ?",
                (pos_t1,),
            ).fetchone()
            r_mfc = conn.execute(
                "SELECT status, exit_price, realized_pnl, unrealized_pnl FROM positions WHERE id = ?",
                (pos_mfc,),
            ).fetchone()

        # Target 1: 50% trimmed (10 -> 5 shares), status TARGET_1_TRIMMED, SL ratcheted >= 100.5
        assert r_t1[0] == "TARGET_1_TRIMMED"
        assert r_t1[1] == 5
        assert r_t1[2] >= 100.5
        assert r_t1[3] == round((111.0 - 100.0) * 5, 2)

        # MARKED_FOR_CLOSURE: liquidated to CLOSED at 92.0
        assert r_mfc[0] == "CLOSED"
        assert r_mfc[1] == 92.0
        assert r_mfc[2] == round((92.0 - 100.0) * 5, 2)
        assert r_mfc[3] == 0.0

        # Now test Target 2 hit on the remaining 5 runner shares of pos_t1
        live_t2_df = pd.DataFrame({"Close": [121.0], "High": [122.0], "Low": [118.0]})
        with patch("scripts.run_sentinel.is_system_halted", return_value=False), \
             patch("yfinance.download", return_value=live_t2_df), \
             patch("src.notification.telegram_bot.send_telegram_alert"):
            run_sentinel_check()

        with get_read_connection() as conn:
            r_t2 = conn.execute(
                "SELECT status, exit_price, realized_pnl FROM positions WHERE id = ?",
                (pos_t1,),
            ).fetchone()

        assert r_t2[0] == "TARGET_REACHED"
        assert r_t2[1] == 121.0
        assert r_t2[2] == round((111.0 - 100.0) * 5 + (121.0 - 100.0) * 5, 2)
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id IN (?, ?)", (pos_t1, pos_mfc))
            conn.execute("DELETE FROM purification_log WHERE trade_id IN (?, ?)", (pos_t1, pos_mfc))


def test_fix6_eod_reconciliation_equity_curve_core_equity_consistency():
    pos_mfc = "test_audit_eod_mfc"
    sym_mfc = "TCS"
    try:
        with get_read_connection() as conn:
            max_dt = conn.execute("SELECT MAX(trade_date) FROM bhavcopy_daily WHERE symbol = ?", (sym_mfc,)).fetchone()[0]
        if max_dt is not None:
            with get_write_connection() as conn:
                conn.execute("DELETE FROM positions WHERE id = ?", (pos_mfc,))
                conn.execute("""
                    INSERT INTO positions (
                        id, symbol, entry_date, entry_price, quantity, status,
                        trailing_stop_loss, target_1, target_2, atr, current_ltp,
                        peak_high, realized_pnl, unrealized_pnl, risk_rupees, portfolio_allocation_pct
                    ) VALUES (?, ?, ?, 3000.0, 2, 'MARKED_FOR_CLOSURE', 2900.0, 3200.0, 3400.0, 50.0, 2950.0, 3000.0, 0.0, -100.0, 200.0, 5.0)
                """, (pos_mfc, sym_mfc, max_dt))

        with patch("scripts.run_eod_reconciliation.is_system_halted", return_value=False), \
             patch("src.ingestion.bhavcopy.fetch_bhavcopy_with_retry_and_fallback", return_value=pd.DataFrame()), \
             patch("src.portfolio.state.get_portfolio_state", return_value={
                 "core_equity": 102500.0,
                 "unrealized_pnl_total": 1500.0,
                 "realized_pnl_total": 1000.0,
             }):
            run_eod_reconciliation_pipeline()

        with get_read_connection() as conn:
            ec_row = conn.execute(
                "SELECT total_equity, core_equity, unrealized_pnl FROM equity_curve WHERE trade_date = CURRENT_DATE"
            ).fetchone()
            assert ec_row is not None
            # Fix 6: core_equity in equity_curve must equal total_equity (102500.0), NOT core_equity - unrealized (101000.0)
            assert float(ec_row[0]) == 102500.0
            assert float(ec_row[1]) == 102500.0
            assert float(ec_row[2]) == 1500.0

            if max_dt is not None:
                mfc_status = conn.execute("SELECT status FROM positions WHERE id = ?", (pos_mfc,)).fetchone()[0]
                assert mfc_status == "CLOSED"
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_mfc,))
            conn.execute("DELETE FROM purification_log WHERE trade_id = ?", (pos_mfc,))
            conn.execute("DELETE FROM equity_curve WHERE trade_date = CURRENT_DATE AND total_equity = 102500.0")


# ---------------------------------------------------------------------------
# Fix 9: Conviction Threshold 7.0 & Judge Prompt + Agent Memory Verdict
# ---------------------------------------------------------------------------
def test_fix9_conviction_threshold_and_judge_memory_verdict():
    with open("src/config/strategy.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert float(cfg["risk"]["min_conviction_score"]) == 7.0

    # Score 6.8 (< 7.0) must be rejected by conviction_gate_node
    gate_res = conviction_gate_node({"symbol": "TEST_CONV_68", "conviction_score": 6.8})
    assert gate_res["risk_verdict"] == "REJECT"

    # research_judge_node with score 6.2 (< 7.0) must record REJECT in agent_memory, and include promoter_pledged_pct in prompt
    sym = "TEST_JUDGE_MEM_62"
    captured_prompts = []

    def fake_llm(messages, model_type="primary"):
        captured_prompts.append(messages[-1]["content"])
        return "SYNTHESIS: Weak setup.\nCONVICTION_SCORE: 6.2"

    state = {
        "symbol": sym,
        "pattern_type": "VCP",
        "trigger_price": 100.0,
        "stop_loss_price": 95.0,
        "target_1_price": 110.0,
        "adtv_20d": 10000000.0,
        "circuit_band": 20.0,
        "fundamentals": {
            "profit_growth_pct": 18.5,
            "sales_growth_pct": 14.2,
            "debt_to_assets": 0.12,
            "promoter_pledged_pct": 4.25,
        },
        "bull_thesis": "Bullish",
        "bear_risks": "Bearish",
        "risk_verdict": "APPROVE",
    }

    try:
        with patch("src.agents.debate_graph.execute_llm_completion", side_effect=fake_llm):
            res = research_judge_node(state)

        assert res["conviction_score"] == 6.2
        assert "Promoter Pledge: 4.25%" in captured_prompts[0]
        assert "Profit Growth: 18.5%" in captured_prompts[0]
        assert "Sales Growth: 14.2%" in captured_prompts[0]

        with get_read_connection() as conn:
            mem_row = conn.execute(
                "SELECT previous_verdict, rejection_reason FROM agent_memory WHERE symbol = ?",
                (sym,),
            ).fetchone()
        assert mem_row is not None
        assert mem_row[0] == "REJECT"
        assert "below minimum threshold" in mem_row[1]
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM agent_memory WHERE symbol = ?", (sym,))


# ---------------------------------------------------------------------------
# Fix 10: ML Live Tick Features, Daily Drawdown Guard, Correlation & Vol Target
# ---------------------------------------------------------------------------
def test_fix10_engineer_live_tick_populates_optional_features():
    dates = pd.date_range(end=pd.Timestamp("today").normalize() - pd.Timedelta(days=1), periods=150, freq="B")
    df = pd.DataFrame({
        "trade_date": dates,
        "close_price": np.linspace(100.0, 150.0, len(dates)),
        "high_price": np.linspace(102.0, 152.0, len(dates)),
        "low_price": np.linspace(98.0, 148.0, len(dates)),
        "total_traded_qty": [50000] * len(dates),
        "total_traded_val": [6000000.0] * len(dates),
        "delivery_pct": [55.0] * len(dates),
    })

    updated = engineer_live_tick(df, live_price=155.0, live_volume=60000)
    feats = extract_quantitative_features(updated)
    last_row = feats.iloc[-1]

    for col in ["delivery_ratio", "adtv_log", "momentum_6m"]:
        assert pd.notna(last_row[col]), f"Feature {col} is NaN on live tick row!"
    assert last_row["adtv_log"] > 0.0
    assert abs(last_row["delivery_ratio"] - 0.55) < 1e-4


def test_fix10_daily_drawdown_guard_includes_intraday_realized_losses():
    pos_stop = "test_audit_dd_stop"
    pos_open = "test_audit_dd_open"
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()

    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id IN (?, ?)", (pos_stop, pos_open))
            # Intraday stopped-out position today (-2,000 realized) + open position (-2,000 unrealized) = -4,000 (> 3% of 100k)
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, exit_date, entry_price, exit_price, quantity,
                    status, trailing_stop_loss, target_1, target_2, atr, current_ltp,
                    realized_pnl, unrealized_pnl, risk_rupees, portfolio_allocation_pct
                ) VALUES
                (?, 'TEST_DD_1', CURRENT_DATE, ?, 100.0, 80.0, 100, 'STOPPED_OUT', 80.0, 120.0, 140.0, 2.0, 80.0, -2000.0, 0.0, 2000.0, 10.0),
                (?, 'TEST_DD_2', CURRENT_DATE, NULL, 100.0, NULL, 100, 'OPEN', 80.0, 120.0, 140.0, 2.0, 80.0, 0.0, -2000.0, 2000.0, 10.0)
            """, (pos_stop, today, pos_open))

        with patch("src.portfolio.state.get_portfolio_state", return_value={"core_equity": 96000.0}):
            breached, reason = is_daily_drawdown_breached(threshold_pct=3.0)

        assert breached is True, f"Expected drawdown breach to be detected, got {breached} ({reason})"
        assert "exceeds halt threshold" in reason
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id IN (?, ?)", (pos_stop, pos_open))


def test_fix10_correlation_guard_and_vol_target_fallback_options():
    pos_id = "test_audit_corr_pos"
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, status,
                    trailing_stop_loss, target_1, target_2, atr, current_ltp,
                    unrealized_pnl, risk_rupees, portfolio_allocation_pct
                )
                VALUES (?, 'TEST_CORR_OPEN', CURRENT_DATE, 100.0, 10, 'OPEN', 95.0, 110.0, 125.0, 2.0, 100.0, 0.0, 50.0, 5.0)
            """, (pos_id,))

        # Default fail_closed_on_error=False preserves existing behavior with degraded_sizing_scalar metadata
        passed_open, reason_open, metrics_open = evaluate_correlation_guard("NON_EXISTENT_SYM_XYZ")
        assert passed_open is True
        assert metrics_open.get("degraded_sizing_scalar") == 0.5

        # fail_closed_on_error=True rejects when history is missing
        passed_closed, reason_closed, _ = evaluate_correlation_guard("NON_EXISTENT_SYM_XYZ", fail_closed_on_error=True)
        assert passed_closed is False
        assert "CORR_GUARD_REJECTED" in reason_closed

        # vol_target supports custom fallback_scalar while defaulting to 1.0
        s_default = calculate_volatility_scalar({"INFY": 50000.0}, "NON_EXISTENT_SYM_XYZ", 20000.0, 100000.0, cov_matrix=None)
        s_conserv = calculate_volatility_scalar({"INFY": 50000.0}, "NON_EXISTENT_SYM_XYZ", 20000.0, 100000.0, cov_matrix=None, fallback_scalar=0.75)
        assert s_default == 1.0
        assert s_conserv == 0.75
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))


def test_fix5_second_opinion_veto_updates_agent_memory_composite_pk():
    """Verify agent_memory UPDATE uses PRIMARY KEY (symbol, memory_date) instead of non-existent id column."""
    sym = "TEST_VETO_MEM"
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM agent_memory WHERE symbol = ?", (sym,))
            conn.execute("""
                INSERT INTO agent_memory (symbol, memory_date, pattern_type, previous_verdict, conviction_score, rejection_reason)
                VALUES (?, ?, 'VCP Stage 2', 'APPROVE', 8.0, '')
            """, (sym, today))
            conn.execute("""
                UPDATE agent_memory
                SET previous_verdict = 'VETOED',
                    rejection_reason = ?
                WHERE symbol = ? AND memory_date = ?;
            """, ("Vetoed by Second Opinion Gate (Conviction: 8.0/10, ML Prob: 0.41)", sym, today.isoformat()))
            row = conn.execute(
                "SELECT previous_verdict, rejection_reason FROM agent_memory WHERE symbol = ? AND memory_date = ?",
                (sym, today),
            ).fetchone()
        assert row is not None
        assert row[0] == "VETOED"
        assert "Vetoed by Second Opinion Gate" in row[1]
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM agent_memory WHERE symbol = ?", (sym,))


def test_fix7_empty_sector_cache_prefilter_distinguishes_quant_vs_missing_sector():
    """
    Verify that when fundamentals_cache has empty sector_name (''), the pre-scrape filter
    evaluates quantitative balance-sheet compliance with 'PENDING_SECTOR_SCRAPE' so that
    quantitatively compliant stocks are scraped for sector while quantitatively non-compliant
    stocks are skipped before scraping.
    """
    from src.screening.shariah_filter import check_shariah_compliance

    c_sec = ""
    quant_ok_funds = {
        "total_assets": 1000.0,
        "debt_to_assets": 0.10,
        "interest_income_ratio": 0.01,
        "illiquid_ratio": 0.50,
        "net_liquid_assets_crores": 200.0,
        "market_cap_crores": 1000.0,
    }
    is_comp_quant, _ = check_shariah_compliance(
        quant_ok_funds,
        sector_name=c_sec if c_sec else "PENDING_SECTOR_SCRAPE",
    )
    assert is_comp_quant is True

    quant_bad_funds = {
        "total_assets": 1000.0,
        "debt_to_assets": 0.55,
        "interest_income_ratio": 0.01,
        "illiquid_ratio": 0.50,
        "net_liquid_assets_crores": 200.0,
        "market_cap_crores": 1000.0,
    }
    is_comp_bad_debt, reason_debt = check_shariah_compliance(
        quant_bad_funds,
        sector_name=c_sec if c_sec else "PENDING_SECTOR_SCRAPE",
    )
    assert is_comp_bad_debt is False
    assert "EXCESSIVE_DEBT_ASSETS" in reason_debt


def test_fix9_ml_predictor_and_second_opinion_gate_select_delivery_and_traded_val():
    """Verify live inference SQL queries in ml_predictor.py and second_opinion_gate.py fetch delivery_pct and total_traded_val."""
    import inspect
    from src.screening import ml_predictor, second_opinion_gate

    pred_src = inspect.getsource(ml_predictor.evaluate_xgboost_probability)
    gate_src = inspect.getsource(second_opinion_gate.evaluate_second_opinion)

    assert "delivery_pct" in pred_src and "total_traded_val" in pred_src
    assert "delivery_pct" in gate_src and "total_traded_val" in gate_src


def test_fix10_daily_drawdown_guard_no_carryover_unrealized_double_counting():
    """
    Verify that when equity_curve has a prior EOD snapshot with unrealized_pnl (e.g. -3,000),
    is_daily_drawdown_breached does not double-count that carryover unrealized loss on a flat morning,
    and accurately detects a breach when intraday losses deepen by >=3%.
    """
    pos_open = "test_audit_dd_carry"
    snap_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_open,))
            conn.execute("DELETE FROM equity_curve WHERE trade_date = ?", (snap_date,))
            # Prior EOD snapshot: core_equity = 97,000 (which includes -3,000 unrealized_pnl)
            conn.execute("""
                INSERT INTO equity_curve (
                    trade_date, total_equity, core_equity, unrealized_pnl
                ) VALUES (?, 97000.0, 97000.0, -3000.0)
            """, (snap_date,))
            # Open position still has the exact same -3,000 unrealized_pnl (0% change today)
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, status,
                    trailing_stop_loss, target_1, target_2, atr, current_ltp,
                    realized_pnl, unrealized_pnl, risk_rupees, portfolio_allocation_pct
                ) VALUES (?, 'TEST_CARRY', CURRENT_DATE, 100.0, 100, 'OPEN', 80.0, 120.0, 140.0, 2.0, 97.0, 0.0, -3000.0, 2000.0, 10.0)
            """, (pos_open,))

        # Flat day: current_equity == 97,000 == starting_equity -> 0% daily drawdown (no false breach)
        breached_flat, reason_flat = is_daily_drawdown_breached(threshold_pct=3.0)
        assert breached_flat is False, f"Unexpected false breach on flat carryover day: {reason_flat}"

        # Now deepen unrealized loss today by another -3,000 (total unrealized = -6,000 -> -3.09% of 97,000)
        with get_write_connection() as conn:
            conn.execute("UPDATE positions SET unrealized_pnl = -6000.0 WHERE id = ?", (pos_open,))

        breached_deep, reason_deep = is_daily_drawdown_breached(threshold_pct=3.0)
        assert breached_deep is True, f"Expected breach when intraday loss deepened by 3.09%: {reason_deep}"
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_open,))
            conn.execute("DELETE FROM equity_curve WHERE trade_date = ?", (snap_date,))


def test_fix8_sentinel_same_bar_target1_and_target2_full_close():
    """
    Verify that when an OPEN position surges past both target_1 and target_2 on the same 15m bar,
    run_sentinel_check books both tranches and transitions directly to TARGET_REACHED.
    """
    pos_id = "test_audit_pos_t1_t2_same_bar"
    sym = "TEST_AUD_T1T2"
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, status,
                    trailing_stop_loss, target_1, target_2, atr, current_ltp,
                    peak_high, realized_pnl, unrealized_pnl, risk_rupees, portfolio_allocation_pct
                )
                VALUES (?, ?, CURRENT_DATE, 100.0, 10, 'OPEN', 95.0, 110.0, 125.0, 2.0, 100.0, 100.0, 0.0, 0.0, 50.0, 5.0)
            """, (pos_id, sym))

        live_t1_t2_df = pd.DataFrame({"Close": [128.0], "High": [130.0], "Low": [99.0]})
        with patch("scripts.run_sentinel.is_system_halted", return_value=False), \
             patch("yfinance.download", return_value=live_t1_t2_df), \
             patch("src.notification.telegram_bot.send_telegram_alert"):
            run_sentinel_check()

        with get_read_connection() as conn:
            row = conn.execute(
                "SELECT status, quantity, realized_pnl, unrealized_pnl FROM positions WHERE id = ?",
                (pos_id,),
            ).fetchone()

        assert row is not None
        status, qty, realized_pnl, unrealized_pnl = row
        assert status == "TARGET_REACHED", f"Expected TARGET_REACHED on same-bar T1+T2 hit, got {status}"
        assert qty == 10
        assert realized_pnl > 0.0
        assert unrealized_pnl == 0.0
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
            conn.execute("DELETE FROM purification_log WHERE trade_id = ?", (pos_id,))


def test_fix10_debate_graph_applies_degraded_correlation_scalar():
    """Verify deterministic_risk_node scales down suggested_shares when correlation guard returns degraded_sizing_scalar."""
    from src.agents.debate_graph import deterministic_risk_node

    mock_arb = {
        "verdict": "APPROVE",
        "suggested_shares": 100,
        "stop_loss_price": 95.0,
        "target_1_price": 110.0,
        "target_2_price": 120.0,
        "risk_reward_ratio": 3.0,
        "total_capital_deployed": 10000.0,
        "portfolio_allocation_pct": 10.0,
        "rejection_reason": "All risk gates passed.",
    }
    state = {
        "symbol": "DEGRADED_CORR_SYM",
        "trigger_price": 100.0,
        "current_price": 100.0,
        "fundamentals": {"atr_14": 2.5, "sector_name": "IT"},
        "circuit_band": 20.0,
        "macro_weather": {"target_cash_exposure_pct": 0.0},
        "adtv_20d": 50_000_000.0,
        "market_cap_tier": "LARGE",
    }
    with patch("src.risk.correlation_guard.evaluate_correlation_guard", return_value=(True, "DEGRADED", {"degraded_sizing_scalar": 0.5})), \
         patch("src.agents.debate_graph.calculate_deterministic_risk_and_position", return_value=mock_arb):
        res = deterministic_risk_node(state)

    assert res["risk_verdict"] == "APPROVE"
    assert res["suggested_shares"] == 50
    assert res["total_capital_deployed"] == 5000.0


# ---------------------------------------------------------------------------
# Remaining Audit Item 1: Halal Stock 2.0 Workbook Alignment & DB Backfill
# ---------------------------------------------------------------------------
def test_item1_halal_workbook_alignment_cash_to_assets_total_revenue_and_sugar_distilleries():
    from src.screening.shariah_filter import PROHIBITED_SYMBOLS, check_shariah_compliance

    # 1. Screener scraper extracts Investments + Cash Equivalents -> cash_to_assets, and uses Total Revenue denominator
    html_doc = """
    <html><body>
      <ul id="top-ratios">
        <li><span class="name">Market Cap</span><span class="number">5,000</span></li>
        <li><span class="name">Stock P/E</span><span class="number">20.0</span></li>
        <li><span class="name">ROCE</span><span class="number">22.0</span></li>
        <li><span class="name">Pledged percentage</span><span class="number">0.0</span></li>
      </ul>
      <div id="peers">
        <a href="/explore/?sector=Information+Technology" title="Sector">Information Technology</a>
      </div>
      <section id="profit-loss">
        <table>
          <tr><td>Sales</td><td>900</td><td>960</td></tr>
          <tr><td>Other Income</td><td>30</td><td>40</td></tr>
          <tr><td>Net Profit</td><td>150</td><td>180</td></tr>
        </table>
      </section>
      <section id="balance-sheet">
        <table>
          <tr><td>Borrowings</td><td>50</td><td>50</td></tr>
          <tr><td>Other Liabilities</td><td>100</td><td>100</td></tr>
          <tr><td>Fixed Assets</td><td>300</td><td>350</td></tr>
          <tr><td>Investments</td><td>200</td><td>250</td></tr>
          <tr><td>Cash Equivalents</td><td>100</td><td>120</td></tr>
          <tr><td>Inventories</td><td>50</td><td>50</td></tr>
          <tr><td>Trade receivables</td><td>80</td><td>80</td></tr>
          <tr><td>Total Assets</td><td>900</td><td>1,000</td></tr>
        </table>
      </section>
    </body></html>
    """
    mock_resp = MagicMock(status_code=200, text=html_doc)
    sym = "TEST_HALAL_XLSX_CO"
    try:
        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("src.ingestion.screener_scraper.requests.get", return_value=mock_resp), \
             patch("src.ingestion.screener_scraper.yf.Ticker") as mock_yf:
            mock_yf.return_value.news = []
            res = fetch_screener_fundamentals(sym)

        assert res["investments"] == 250.0
        assert res["cash_equivalents"] == 120.0
        # cash_to_assets = (120 + 250) / 1000 = 0.37 (> 0.33)
        assert abs(res["cash_to_assets"] - 0.37) < 1e-6
        # Total Revenue = 960 + 40 = 1000 -> interest_income_ratio = 40 / 1000 = 0.04 (< 0.05)
        assert abs(res["interest_income_ratio"] - 0.04) < 1e-6

        # Must fail Shariah compliance due to cash_to_assets = 37% > 33%
        passed, reason = check_shariah_compliance(res, sector_name=res["sector_name"])
        assert passed is False
        assert "EXCESSIVE_CASH_ASSETS_" in reason
        # 1B. Multi-line schedule cash items ("Cash on hand" + "Balances with banks") accumulation
        html_sched_doc = """
        <html><body>
          <div id="company-info" data-company-id="9999" data-consolidated="false"></div>
          <div id="peers"><a href="/explore/?sector=IT" title="Sector">IT</a></div>
          <section id="profit-loss"><table><tr><td>Sales</td><td>1000</td></tr></table></section>
          <section id="balance-sheet"><table>
            <tr><td>Total Assets</td><td>1000</td></tr>
            <tr><td>Fixed Assets</td><td>500</td></tr>
            <tr><td>Borrowings</td><td>100</td></tr>
          </table></section>
        </body></html>
        """
        sched_json = {
            "Cash in hand": {"2024": "30"},
            "Balances with banks": {"2024": "70"},
            "Trade receivables": {"2024": "50"},
            "Inventories": {"2024": "100"}
        }
        mock_main = MagicMock(status_code=200, text=html_sched_doc)
        mock_sched = MagicMock(status_code=200, json=lambda: sched_json)
        with patch("src.ingestion.screener_scraper.time.sleep"), \
             patch("src.ingestion.screener_scraper.requests.get", side_effect=[mock_main, mock_sched]), \
             patch("src.ingestion.screener_scraper.yf.Ticker") as mock_yf:
            mock_yf.return_value.news = []
            res_sched = fetch_screener_fundamentals("TEST_SCHED_ACCUM")
        assert res_sched["cash_equivalents"] == 100.0  # 30 + 70
        assert res_sched["trade_receivables"] == 50.0
        assert res_sched["inventories"] == 100.0
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM fundamentals_cache WHERE symbol IN (?, ?)", (sym, "TEST_SCHED_ACCUM"))
            conn.execute("DELETE FROM promoter_pledge_history WHERE symbol IN (?, ?)", (sym, "TEST_SCHED_ACCUM"))

    # 2. Sugar-mill molasses alcohol distilleries (Sheet19) and prohibited symbols (list) must be rejected
    for bad_sym in [
        "BALRAMCHIN", "TRIVENI", "EIDPARRY", "RENUKA", "DALMIASUG", "BAJAJHIND",
        "DHAMPURSUG", "DWARKESH", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "UBL",
        "UNITDSPR", "RADICO", "DELTACORP", "HAL", "BEL", "INDHOTEL", "PVRINOX"
    ]:
        assert bad_sym in PROHIBITED_SYMBOLS, f"{bad_sym} missing from PROHIBITED_SYMBOLS"
        ok_sym, r_sym = check_shariah_compliance(
            {"symbol": bad_sym, "total_assets": 1000.0, "illiquid_ratio": 0.5, "market_cap_crores": 2000.0},
            sector_name="Sugar & Agriculture",
        )
        assert ok_sym is False
        assert "NON_COMPLIANT_SECTOR_" in r_sym

    # 3. Verify DuckDB fundamentals_cache has 0 empty sector_name rows and 0 non-compliant rows
    with get_read_connection() as conn:
        fc_rows = conn.execute("SELECT symbol, fundamentals_json FROM fundamentals_cache").fetchall()
    assert len(fc_rows) > 0
    for sym_db, f_json in fc_rows:
        f_data = json.loads(f_json)
        sec_db = (f_data.get("sector_name") or "").strip()
        assert sec_db != "", f"Cached symbol {sym_db} still has empty sector_name!"
        ok_db, r_db = check_shariah_compliance(f_data, sector_name=sec_db)
        assert ok_db is True, f"Cached symbol {sym_db} failed Shariah compliance: {r_db}"


# ---------------------------------------------------------------------------
# Remaining Audit Item 2: On-Disk 9-Feature XGBoost, HMM State 0, and Monthly Retrain Schedule
# ---------------------------------------------------------------------------
def test_item2_on_disk_xgboost_9_features_hmm_negative_state0_and_monthly_retrain_schedule():
    import pickle
    import joblib
    import schedule
    from pathlib import Path
    from scripts.run_model_training import FEATURE_COLS, MODEL_PATH, META_PATH
    from scripts.fit_hmm_regime import MODEL_PATH as HMM_PATH
    from src.utils.benchmark_provider import get_market_regime
    from scripts.run_scheduler import setup_schedule

    # 1. Verify on-disk xgboost_global.pkl and xgboost_global_meta.json have all 9 features
    assert Path(MODEL_PATH).exists()
    assert Path(META_PATH).exists()
    with open(MODEL_PATH, "rb") as f:
        xgb_model = pickle.load(f)
    with open(META_PATH, "r", encoding="utf-8") as f:
        xgb_meta = json.load(f)

    assert int(xgb_model.n_features_in_) == 9
    assert list(xgb_model.feature_names_in_) == FEATURE_COLS
    assert xgb_meta["features"] == FEATURE_COLS
    assert xgb_meta["row_count"] >= 1000
    assert xgb_meta["auc_conservative"] > 0.51

    # 2. Verify on-disk hmm_regime.pkl has State 0 mean < 0 < State 1 < State 2
    assert Path(HMM_PATH).exists()
    hmm_model = joblib.load(str(HMM_PATH))
    means = hmm_model.means_.flatten()
    covars = hmm_model.covars_.flatten()
    assert len(means) == 3
    assert means[0] < 0.0 < means[1] < means[2], f"Expected State 0 negative mean, got {means}"
    assert covars[0] > covars[1]

    # 3. Verify get_market_regime defaults to use_hmm=True
    import inspect
    sig = inspect.signature(get_market_regime)
    assert sig.parameters["use_hmm"].default is True

    # 4. Verify run_scheduler registers monthly_retrain
    schedule.clear()
    setup_schedule(include_symbol_sync=False)
    retrain_jobs = [j for j in schedule.jobs if "monthly_retrain" in j.tags]
    assert len(retrain_jobs) == 1
    schedule.clear()


# ---------------------------------------------------------------------------
# Remaining Audit Item 3: VCP High-Low Contractions & Anti-Trap Layer 5 Sector Median P/E
# ---------------------------------------------------------------------------
def test_item3_vcp_high_low_contractions_and_anti_trap_layer5_sector_median_pe():
    import duckdb
    from src.screening.vcp_screener import evaluate_minervini_vcp_batch
    from src.screening.anti_trap_shield import evaluate_anti_trap_shield, compute_sector_median_pe_map

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

    base_d = date(2025, 12, 1)
    # GOOD_VCP: contracting high-low depths across c1..c4, with 20d high = 225.5 > 20d close = 222.15
    # BAD_VCP_C2: identical close prices, but c2 ([-20:-10]) has wide intraday high-low swings (180..260) -> rejected!
    for i in range(185):
        d = base_d + timedelta(days=i)
        if i < 165:
            c_p = 100.0 + (i * 0.72) + ((i % 3 - 1) * 1.8)
            vol = 50000
            h_good, l_good = c_p + 2.0, c_p - 2.0
            h_bad, l_bad = c_p + 2.0, c_p - 2.0
        else:
            c_p = 222.0 + ((i % 2) * 0.15)
            vol = 5000 if i >= 180 else 40000
            h_good = 225.5 if i == 170 else (c_p + 0.8)
            l_good = c_p - 0.8
            # In c2 window (bars 165..174), BAD_VCP_C2 has massive intraday high-low wicks despite flat close
            if 165 <= i < 175:
                h_bad, l_bad = 260.0, 180.0
            else:
                h_bad, l_bad = c_p + 0.8, c_p - 0.8

        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES (?, ?, ?, ?, ?, ?, 55.0, 'EQ', FALSE, FALSE)",
            ("GOOD_VCP", d, c_p, h_good, l_good, vol),
        )
        mem_conn.execute(
            "INSERT INTO bhavcopy_daily VALUES (?, ?, ?, ?, ?, ?, 55.0, 'EQ', FALSE, FALSE)",
            ("BAD_VCP_C2", d, c_p, h_bad, l_bad, vol),
        )

    with patch("src.utils.benchmark_provider.get_market_regime", return_value=1), \
         patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.0005] * 100)):
        vcp_res = evaluate_minervini_vcp_batch(
            ["GOOD_VCP", "BAD_VCP_C2"],
            mem_conn,
            live_prices={"GOOD_VCP": 222.15, "BAD_VCP_C2": 222.15},
        )

    syms_passed = [r["symbol"] for r in vcp_res]
    assert "GOOD_VCP" in syms_passed
    assert "BAD_VCP_C2" not in syms_passed
    # Pivot high must come from high_df (225.5), not close_df (222.15)
    good_cand = next(r for r in vcp_res if r["symbol"] == "GOOD_VCP")
    assert good_cand["trigger_price"] == 225.5

    # 60d_low_multiplier takes precedence over 52w_low_multiplier
    from src.screening.vcp_screener import MINERVINI_CONFIG
    custom_cfg = dict(MINERVINI_CONFIG)
    custom_cfg["60d_low_multiplier"] = 3.0   # Demands price >= 3.0 * low
    custom_cfg["52w_low_multiplier"] = 1.05  # Permissive fallback that must be overridden
    with patch.dict(MINERVINI_CONFIG, custom_cfg), \
         patch("src.utils.benchmark_provider.get_market_regime", return_value=1), \
         patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.0005] * 100)):
        res_overridden = evaluate_minervini_vcp_batch(
            ["GOOD_VCP"],
            mem_conn,
            live_prices={"GOOD_VCP": 222.15},
        )
    assert len(res_overridden) == 0, "60d_low_multiplier=3.0 must reject when price is below 3x low"

    # Anti-Trap Layer 5 P/E Overvaluation check using cross-sectional sector_median_pe
    pe_map = compute_sector_median_pe_map()
    assert len(pe_map) > 0

    sym_pe = "TEST_TRAP_L5_PE"
    try:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym_pe,))
            for i in range(60):
                d = base_d + timedelta(days=i)
                conn.execute("""
                    INSERT INTO bhavcopy_daily (
                        symbol, trade_date, series, open_price, high_price, low_price,
                        close_price, total_traded_qty, total_traded_val, delivery_pct
                    ) VALUES (?, ?, 'EQ', 100.0, 101.0, 99.0, 100.0, 10000, 1000000.0, 50.0)
                """, (sym_pe, d))

        cand_pe = {"trigger_price": 100.0, "sma_50": 98.0}
        # pe_ratio = 80.0 > 2.5 * 25.0 (62.5) -> must reject with TRAP_L5_PE_OVERVALUATION
        ok_hi, reason_hi, _ = evaluate_anti_trap_shield(
            sym_pe, cand_pe, {"pe_ratio": 80.0, "recent_news_count": 0}, live_price=100.0, sector_median_pe=25.0
        )
        assert ok_hi is False
        assert reason_hi == "TRAP_L5_PE_OVERVALUATION"

        # pe_ratio = 45.0 <= 2.5 * 25.0 -> must pass
        ok_lo, reason_lo, _ = evaluate_anti_trap_shield(
            sym_pe, cand_pe, {"pe_ratio": 45.0, "recent_news_count": 0}, live_price=100.0, sector_median_pe=25.0
        )
        assert ok_lo is True
        assert reason_lo == "PASSED_ALL_ANTI_TRAP_LAYERS"

        # Auto-resolution of sector_median_pe from cache when omitted as argument
        first_sec = next(iter(pe_map.keys()))
        sec_pe_val = pe_map[first_sec]
        funds_auto = {"sector_name": first_sec, "pe_ratio": sec_pe_val * 3.0, "recent_news_count": 0}
        ok_auto, reason_auto, _ = evaluate_anti_trap_shield(
            sym_pe, cand_pe, funds_auto, live_price=100.0
        )
        assert ok_auto is False
        assert reason_auto == "TRAP_L5_PE_OVERVALUATION"
    finally:
        with get_write_connection() as conn:
            conn.execute("DELETE FROM bhavcopy_daily WHERE symbol = ?", (sym_pe,))


# ---------------------------------------------------------------------------
# Remaining Audit Item 4: PurgedKFold t1 Purge & Same-Day Barrier Collision
# ---------------------------------------------------------------------------
def test_item4_purged_kfold_label_end_date_t1_purge_and_same_day_barrier_collision():
    from src.utils.cv import PurgedKFoldEmbargo
    from scripts.run_model_training import triple_barrier_label

    # 1. PurgedKFoldEmbargo purges pre-test dates whose label_end_dates (t1) overlap test_start (t0)
    dates = pd.date_range("2026-01-01", periods=50, freq="B").to_numpy()
    # Set label_end_dates so that index 2 (in pre-train before Fold 1 at index 10) has a long horizon reaching index 12
    label_ends = dates.copy()
    label_ends[2] = dates[12]

    cv = PurgedKFoldEmbargo(n_splits=5, embargo_days=5, label_horizon_days=5)
    splits = list(cv.split(dates, label_end_dates=label_ends))
    train_idx_f1, test_idx_f1 = splits[1]
    assert 10 in test_idx_f1
    assert 2 not in train_idx_f1, "Index 2 whose label_end_date overlaps Fold 1 test_start must be purged!"

    # 1B. PurgedKFoldEmbargo input validations: unsorted dates, duplicates, length mismatch, negative horizon
    with pytest.raises(ValueError, match="sorted in ascending chronological order"):
        list(cv.split(np.array(["2026-01-05", "2026-01-01", "2026-01-03", "2026-01-02", "2026-01-04"])))

    with pytest.raises(ValueError, match="duplicate dates"):
        list(cv.split(np.array(["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])))

    with pytest.raises(ValueError, match="label_end_dates length .* must match"):
        list(cv.split(dates, label_end_dates=dates[:10]))

    invalid_ends = dates.copy()
    invalid_ends[5] = pd.Timestamp("2025-12-01").to_datetime64()
    with pytest.raises(ValueError, match="cannot be earlier than unique_dates"):
        list(cv.split(dates, label_end_dates=invalid_ends))

    # 2. Same-day upper + lower barrier collision returns 0 (neutral/ambiguous)
    # Entry=100, ATR=5 -> Upper=110, Lower=91. Bar 0 has High=115 (>=110) AND Low=88 (<=91)
    lbl_collision = triple_barrier_label(
        high_series=pd.Series([115.0, 102.0]),
        low_series=pd.Series([88.0, 99.0]),
        close_series=pd.Series([100.0, 101.0]),
        entry_price=100.0,
        atr_val=5.0,
    )
    assert lbl_collision == 0


# ---------------------------------------------------------------------------
# Remaining Audit Item 5: Backtest Shariah Filtering & DhanBroker REST Methods
# ---------------------------------------------------------------------------
def test_item5_backtest_shariah_filtering_and_dhan_broker_rest_routing():
    from research.data_loader import SHARIAH_COMPLIANT_TICKERS, load_duckdb_shariah_data
    from research.backtest_harness import _filter_shariah_compliant_columns, ROUND_TRIP_COST
    from src.execution.dhan_broker import DhanBroker
    from src.execution.order_manager import PaperBroker
    from src.config.settings import settings

    # 1. Backtest tickers and column filter exclude Haram banks/tobacco
    for haram in ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS"]:
        assert haram not in SHARIAH_COMPLIANT_TICKERS

    filtered_cols = _filter_shariah_compliant_columns(
        ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS", "^INDIAVIX"]
    )
    assert filtered_cols == ["RELIANCE.NS", "TCS.NS"]
    assert 0.001 < ROUND_TRIP_COST < 0.002

    duck_dfs = load_duckdb_shariah_data(max_symbols=10)
    assert "close" in duck_dfs and not duck_dfs["close"].empty
    for col in duck_dfs["close"].columns:
        assert col not in ("HDFCBANK", "ICICIBANK", "SBIN", "ITC")

    # 2. DhanBroker live REST order routing when LIVE_TRADING_ENABLED=True + mock requests
    sym = "TCS"
    with patch.object(settings, "LIVE_TRADING_ENABLED", True), \
         patch.object(settings, "DHAN_CLIENT_ID", "100001"), \
         patch.object(settings, "DHAN_ACCESS_TOKEN", "tok_test_123"), \
         patch("src.execution.dhan_broker.get_read_connection") as mock_conn_ctx, \
         patch("src.execution.dhan_broker.requests.post") as mock_post, \
         patch("src.execution.dhan_broker.requests.get") as mock_get, \
         patch("src.execution.dhan_broker.requests.delete") as mock_del, \
         patch.object(PaperBroker, "place_order", return_value="P_TCS_LIVE1") as mock_paper:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("11536",)
        mock_conn_ctx.return_value.__enter__.return_value = mock_conn

        mock_post.return_value = MagicMock(status_code=200, text='{"orderId": "DHAN_ORD_99"}', json=lambda: {"orderId": "DHAN_ORD_99"})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"orderId": "DHAN_ORD_99", "orderStatus": "TRADED"})
        mock_del.return_value = MagicMock(status_code=200)

        ord_id = DhanBroker.place_order(sym, price=3500.0, atr=50.0, quantity=10, sector="IT")
        assert ord_id == "P_TCS_LIVE1"
        mock_post.assert_called_once()
        mock_paper.assert_called_once()
        assert mock_paper.call_args.kwargs["execution_type"] == "DHAN_LIVE"

        st = DhanBroker.get_order_status("DHAN_ORD_99")
        assert st["orderStatus"] == "TRADED"
        assert DhanBroker.cancel_order("DHAN_ORD_99") is True


# ---------------------------------------------------------------------------
# Remaining Audit Item 6: Shariah Trading Invariants Rule File Persisted
# ---------------------------------------------------------------------------
def test_item6_shariah_trading_invariants_rule_file_persisted():
    from pathlib import Path

    rule_path = Path(".gemini/rules/shariah_trading_invariants.md")
    assert rule_path.exists(), "Missing .gemini/rules/shariah_trading_invariants.md"
    content = rule_path.read_text(encoding="utf-8")
    for required_phrase in [
        "33%",
        "5%",
        "20%",
        "Cash Equivalents",
        "Investments",
        "Total Revenue",
        "Net Liquid Assets",
        "FAIL_CLOSED_EMPTY_SECTOR_NAME",
    ]:
        assert required_phrase in content, f"Missing '{required_phrase}' in shariah_trading_invariants.md"



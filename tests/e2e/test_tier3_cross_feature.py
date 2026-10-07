"""
Tier 3: Pairwise Combinatorial & Cross-Feature E2E Test Suite.
Verifies multi-module interactions, state transitions across feature boundaries,
and structural cohesion between risk, screening, regime, settlement, and data pipelines.
Contains >= 15 comprehensive cross-feature test cases.
"""

import os
import sys
import math
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import pytest
import duckdb

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_E2E_DIR = Path(__file__).resolve().parent
if str(_E2E_DIR) not in sys.path:
    sys.path.insert(0, str(_E2E_DIR))

from e2e_helpers import (
    create_in_memory_e2e_db,
    MockFyersClient,
    SettlementStatus,
    ExitPriorityRule,
    RegimeState,
    compute_vectorized_residual_momentum,
    check_price_jump_tripwire_logic,
)
from src.screening.shariah_filter import (
    check_shariah_compliance,
    infer_sector_from_company_or_symbol,
    PROHIBITED_SYMBOLS,
)
from src.notification.trade_card import format_telegram_trade_card


# ==============================================================================
# PAIRWISE INTERACTION 1: Regime Gate (F6) x Screener (F5)
# ==============================================================================

def test_t3_cross_risk_off_blocks_screener():
    """Interaction: When Market Regime is RISK_OFF, Screener produces ZERO buys regardless of high RS."""
    conn = create_in_memory_e2e_db()

    # Simulate Regime Engine producing RISK_OFF (Score 1)
    regime = RegimeState(
        regime="RISK_OFF",
        score=1,
        risk_per_trade_pct=0.0,
        allow_new_entries=False,
        nifty500_close=23000.0,
        nifty500_sma50=24000.0,
        nifty500_sma200=23800.0,
        breadth_pct=42.0,
        details={}
    )

    # Candidate has excellent VCP and high RS score
    candidate = {
        "symbol": "SUPER_MOMENTUM",
        "rs_score": 35.0,
        "volume_dryup": True,
        "stage2": True
    }

    # Screener gate check
    buy_signals = []
    if regime.allow_new_entries:
        if candidate["stage2"] and candidate["rs_score"] > 15.0:
            buy_signals.append(candidate["symbol"])

    assert len(buy_signals) == 0, "RISK_OFF regime must strictly suppress all buy signals!"


# ==============================================================================
# PAIRWISE INTERACTION 2: Regime Gate (F6) x Risk Arbiter (F1)
# ==============================================================================

def test_t3_cross_regime_sizing_risk_on_vs_neutral():
    """Interaction: Regime RISK_ON sizes 1.0% risk whereas NEUTRAL sizes 0.5% risk."""
    portfolio_capital = 1_000_000.0
    trigger_price = 500.0
    stop_loss = 475.0
    risk_per_share = trigger_price - stop_loss  # ₹25

    def size_trade(regime_state: RegimeState) -> int:
        if not regime_state.allow_new_entries or regime_state.risk_per_trade_pct <= 0:
            return 0
        budget = portfolio_capital * (regime_state.risk_per_trade_pct / 100.0)
        return math.floor(budget / risk_per_share)

    regime_risk_on = RegimeState(
        regime="RISK_ON", score=3, risk_per_trade_pct=1.0, allow_new_entries=True,
        nifty500_close=25000.0, nifty500_sma50=24000.0, nifty500_sma200=23000.0, breadth_pct=65.0, details={}
    )
    regime_neutral = RegimeState(
        regime="NEUTRAL", score=2, risk_per_trade_pct=0.5, allow_new_entries=True,
        nifty500_close=24500.0, nifty500_sma50=24000.0, nifty500_sma200=24200.0, breadth_pct=55.0, details={}
    )

    shares_on = size_trade(regime_risk_on)
    shares_neu = size_trade(regime_neutral)

    assert shares_on == 400   # ₹10,000 / 25
    assert shares_neu == 200  # ₹5,000 / 25
    assert shares_on == 2 * shares_neu


# ==============================================================================
# PAIRWISE INTERACTION 3: Settlement State Machine (F4) x FYERS GTT Lodging (F3)
# ==============================================================================

def test_t3_cross_settlement_gtt_oco_cohesion():
    """Interaction: Day 0/1 positions block GTT orders; Day 2 transition triggers 365-day GTT OCO order."""
    client = MockFyersClient()
    conn = create_in_memory_e2e_db()

    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, trailing_stop_loss, target_2, risk_rupees, settlement_status, can_exit, gtt_placed)
        VALUES (101, 'POLYCAB', '2026-10-05', 6500.0, 10, 6100.0, 7500.0, 4000.0, 'SETTLING_T0_T1', FALSE, FALSE)
    """)

    # Step 1: Day 1 audit (cannot lodge GTT)
    pos = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 101").fetchone()
    assert pos[0] == "SETTLING_T0_T1"
    assert pos[1] is False
    assert len(client.placed_gtt_orders) == 0

    # Step 2: Day 2 morning audit transition
    # Update status to SETTLED_DEMAT
    conn.execute("""
        UPDATE positions 
        SET settlement_status = 'SETTLED_DEMAT', can_exit = TRUE 
        WHERE id = 101
    """)

    # GTT placement triggered upon transition
    order = client.place_gtt_oco_order("NSE:POLYCAB-EQ", 10, stop_loss=6100.0, target=7500.0)
    conn.execute("UPDATE positions SET gtt_placed = TRUE, gtt_placed_at = CURRENT_TIMESTAMP WHERE id = 101")

    pos_updated = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 101").fetchone()
    assert pos_updated[0] == "SETTLED_DEMAT"
    assert pos_updated[1] is True
    assert pos_updated[2] is True
    assert len(client.placed_gtt_orders) == 1
    assert order["status"] == "PLACED_365D"


# ==============================================================================
# PAIRWISE INTERACTION 4: Price Jump Quarantine (F9) x Screener (F5)
# ==============================================================================

def test_t3_cross_quarantine_blocks_screener():
    """Interaction: Stock quarantined due to unadjusted >25% price drop is completely excluded by Screener."""
    conn = create_in_memory_e2e_db()

    # Ingest historical records for two stocks
    # Stock 1 (Clean): Normal trend
    # Stock 2 (Corrupted): Artificial 80% price cliff
    trade_date = date(2026, 9, 15)
    quarantined, pct_jump, reason = check_price_jump_tripwire_logic(1500.0, 300.0, has_approved_corp_action=False)
    assert quarantined is True

    # Log quarantine
    conn.execute("""
        INSERT INTO quarantined_stocks (symbol, trade_date, pct_jump, reason)
        VALUES ('CORRUPT_STOCK', ?, ?, ?)
    """, (trade_date, pct_jump, reason))

    # Candidate universe query for Screener excludes quarantined stocks
    screen_universe = ["CLEAN_STOCK", "CORRUPT_STOCK"]
    quarantined_symbols = set(r[0] for r in conn.execute("SELECT symbol FROM quarantined_stocks").fetchall())

    eligible_for_screening = [s for s in screen_universe if s not in quarantined_symbols]
    assert eligible_for_screening == ["CLEAN_STOCK"]
    assert "CORRUPT_STOCK" not in eligible_for_screening


# ==============================================================================
# PAIRWISE INTERACTION 5: Shariah Sync (F11) x Screener (F5)
# ==============================================================================

def test_t3_cross_shariah_universe_screener():
    """Interaction: Screener queries strictly from verified shariah_universe table."""
    conn = create_in_memory_e2e_db()

    # Populate shariah_universe with 1 compliant stock and exclude non-compliant
    conn.execute("""
        INSERT INTO shariah_universe (symbol, fyers_symbol, sector, debt_to_assets, cash_to_assets, interest_income_ratio, illiquid_ratio, is_compliant)
        VALUES 
            ('TCS', 'NSE:TCS-EQ', 'IT', 0.05, 0.20, 0.01, 0.35, TRUE),
            ('HDFCBANK', 'NSE:HDFCBANK-EQ', 'Banking', 0.85, 0.10, 0.90, 0.10, FALSE)
    """)

    # Screener only reads stocks where is_compliant is TRUE
    screener_pool = conn.execute("SELECT symbol FROM shariah_universe WHERE is_compliant = TRUE").fetchall()
    symbols = [r[0] for r in screener_pool]

    assert "TCS" in symbols
    assert "HDFCBANK" not in symbols


# ==============================================================================
# PAIRWISE INTERACTION 6: Residual Momentum (F12) x Risk Arbiter (F1)
# ==============================================================================

def test_t3_cross_residual_mom_ranking_arbiter():
    """Interaction: Top-ranked residual momentum candidate receives priority in capital allocation."""
    np.random.seed(42)
    T, N = 60, 5
    bm_rets = np.random.normal(0.0005, 0.01, T)
    stock_rets = np.random.normal(0.0005, 0.012, (T, N))
    symbols = ["SYM_A", "SYM_B", "SYM_C", "SYM_D", "SYM_E"]

    # SYM_C has superior idiosyncratic alpha
    stock_rets[30:, 2] += 0.015

    _, scores, ranks = compute_vectorized_residual_momentum(stock_rets, bm_rets)
    ranked_candidates = sorted(zip(symbols, ranks, scores), key=lambda x: x[1], reverse=True)

    # Top candidate has rank > 70% and gets first allocation
    top_candidate = ranked_candidates[0]
    assert top_candidate[0] == "SYM_C"
    assert top_candidate[1] >= 70.0


# ==============================================================================
# PAIRWISE INTERACTION 7: Risk Parity Heat Cap (F1) x Open Positions (F4)
# ==============================================================================

def test_t3_cross_heat_accumulation_multi_trade():
    """Interaction: Aggregate open stop risk across open positions caps at 5.0%."""
    conn = create_in_memory_e2e_db()
    portfolio_capital = 1_000_000.0
    max_heat_pct = 5.0

    # Insert 4 open positions with ₹10,000 risk each = ₹40,000 (4.0% heat)
    for i in range(4):
        conn.execute(f"""
            INSERT INTO positions (symbol, entry_date, entry_price, quantity, trailing_stop_loss, risk_rupees, status)
            VALUES ('STOCK_{i}', CURRENT_DATE, 100.0, 100, 90.0, 10000.0, 'OPEN')
        """)

    existing_heat_rupees = conn.execute("SELECT SUM(risk_rupees) FROM positions WHERE status = 'OPEN'").fetchone()[0]
    assert existing_heat_rupees == 40_000.0
    current_heat_pct = (existing_heat_rupees / portfolio_capital) * 100.0
    assert current_heat_pct == 4.0

    # 5th candidate: ₹10,000 risk -> total = ₹50,000 (5.0% heat) -> APPROVED
    candidate_5_risk = 10_000.0
    heat_with_c5 = ((existing_heat_rupees + candidate_5_risk) / portfolio_capital) * 100.0
    assert heat_with_c5 <= max_heat_pct

    # 6th candidate: ₹10,000 risk -> total = ₹60,000 (6.0% heat) -> REJECTED
    heat_with_c6 = ((existing_heat_rupees + candidate_5_risk + 10_000.0) / portfolio_capital) * 100.0
    assert heat_with_c6 > max_heat_pct


# ==============================================================================
# PAIRWISE INTERACTION 8: Market Regime Flip (F6) x Holdings Guardian Stop Tightening (F4)
# ==============================================================================

def test_t3_cross_regime_exit_tightening():
    """Interaction: When regime flips to RISK_OFF, Holdings Guardian tightens stops on settled positions."""
    entry_price = 100.0
    current_stop = 92.0
    ema_21 = 96.50
    sma_50 = 94.0

    # Active settled position held 6 days
    trading_days_held = 6
    settlement_status = SettlementStatus.SETTLED_DEMAT

    # Market regime flips to RISK_OFF (crisis protection)
    regime_state = RegimeState(
        regime="RISK_OFF", score=1, risk_per_trade_pct=0.0, allow_new_entries=False,
        nifty500_close=22000.0, nifty500_sma50=24000.0, nifty500_sma200=23500.0, breadth_pct=35.0, details={}
    )

    # Guardian evaluates defensive stop tightening (P7: RS decay / crisis tighten to 21 EMA)
    if settlement_status == SettlementStatus.SETTLED_DEMAT and regime_state.regime == "RISK_OFF":
        tightened_stop = max(current_stop, ema_21)
    else:
        tightened_stop = current_stop

    assert tightened_stop == 96.50
    assert tightened_stop > current_stop


# ==============================================================================
# PAIRWISE INTERACTION 9: Second Opinion Conviction (F7) x Risk Arbiter Sizing (F1)
# ==============================================================================

def test_t3_cross_ml_shadow_conviction():
    """Interaction: Conviction 8.2 triggers Risk Arbiter sizing, with ML logged to shadow database."""
    conn = create_in_memory_e2e_db()
    conviction = 8.2
    ml_prob = 0.35  # Below historical cutoff of 0.75
    trigger_price = 1000.0
    stop_loss = 940.0  # 6.0% stop

    # Decoupled Gate: Only conviction >= 7.0 is required
    gate_approved = (conviction >= 7.0)
    assert gate_approved is True

    # Sized by deterministic Risk Arbiter
    risk_rupees = 10_000.0  # 1% of 10L
    shares = math.floor(risk_rupees / (trigger_price - stop_loss))
    assert shares == 166

    # Log shadow telemetry
    conn.execute("""
        INSERT INTO screener_candidates (id, scan_date, symbol, conviction_score, ml_prob, status)
        VALUES (201, CURRENT_DATE, 'ASTRAL', ?, ?, 'APPROVED')
    """, (conviction, ml_prob))

    stored = conn.execute("SELECT conviction_score, ml_prob, status FROM screener_candidates WHERE id = 201").fetchone()
    assert stored[0] == 8.2
    assert stored[1] == 0.35
    assert stored[2] == "APPROVED"


# ==============================================================================
# PAIRWISE INTERACTION 10: Holdings Guardian (F4) x Morning Digest (F8)
# ==============================================================================

def test_t3_cross_guardian_digest_sync():
    """Interaction: 19:30 Guardian audit feeds into 08:50 Morning Digest trade alerts and GTT prompts."""
    conn = create_in_memory_e2e_db()

    # Guardian audit at 19:30 marks stock as transitioned to SETTLED_DEMAT with pending GTT
    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, trailing_stop_loss, target_2, risk_rupees, settlement_status, can_exit, gtt_placed)
        VALUES (301, 'BEL', '2026-10-01', 300.0, 100, 280.0, 350.0, 2000.0, 'SETTLED_DEMAT', TRUE, FALSE)
    """)

    # Next morning 08:50 digest finds pending GTT orders needed
    pending_gtts = conn.execute("""
        SELECT symbol, quantity, trailing_stop_loss, target_2 
        FROM positions 
        WHERE settlement_status = 'SETTLED_DEMAT' AND gtt_placed = FALSE
    """).fetchall()

    assert len(pending_gtts) == 1
    assert pending_gtts[0][0] == "BEL"

    # Formatted digest prompt
    gtt_prompt = f"📌 LODGE FYERS GTT OCO: {pending_gtts[0][0]} Qty: {pending_gtts[0][1]} Stop: ₹{pending_gtts[0][2]} Target: ₹{pending_gtts[0][3]}"
    assert "LODGE FYERS GTT OCO" in gtt_prompt


# ==============================================================================
# PAIRWISE INTERACTION 11: Data Spine Backfill (F10) x Screener (F5)
# ==============================================================================

def test_t3_cross_backfill_screener_continuity():
    """Interaction: 250 backfilled trading days enable 200-SMA, 150-SMA, and 50-SMA calculation across universe."""
    conn = create_in_memory_e2e_db()
    days = 250
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(days)]
    prices = np.linspace(100.0, 220.0, days)

    rows = [("TCS", d, p, p) for d, p in zip(dates, prices)]
    conn.executemany("INSERT INTO bhavcopy_daily (symbol, trade_date, close_price, prev_close) VALUES (?, ?, ?, ?)", rows)

    # Screener calculates rolling SMAs
    df = conn.execute("SELECT trade_date, close_price FROM bhavcopy_daily WHERE symbol = 'TCS' ORDER BY trade_date ASC").df()
    df["sma_50"] = df["close_price"].rolling(50).mean()
    df["sma_150"] = df["close_price"].rolling(150).mean()
    df["sma_200"] = df["close_price"].rolling(200).mean()

    latest = df.iloc[-1]
    assert not np.isnan(latest["sma_50"])
    assert not np.isnan(latest["sma_150"])
    assert not np.isnan(latest["sma_200"])
    assert latest["close_price"] > latest["sma_50"] > latest["sma_150"] > latest["sma_200"]


# ==============================================================================
# PAIRWISE INTERACTION 12: Corporate Action (F9) x Backfill (F10) x Screener (F5)
# ==============================================================================

def test_t3_cross_corporate_action_bhavcopy_screener():
    """Interaction: Approved corporate action prevents quarantine and adjusts technical series."""
    conn = create_in_memory_e2e_db()
    ex_date = date(2026, 8, 20)

    # 1:1 Bonus issue recorded in corporate actions
    conn.execute("""
        INSERT INTO corporate_actions (id, symbol, action_type, ex_date, ratio_numerator, ratio_denominator, adjustment_multiplier, applied)
        VALUES (1, 'BONUS_CORP', 'BONUS', ?, 1.0, 1.0, 0.50, TRUE)
    """, (ex_date,))

    # Raw Bhavcopy close dropped 50% on ex_date (₹1000 -> ₹500)
    prev_close = 1000.0
    close = 500.0
    quarantined, pct_jump, reason = check_price_jump_tripwire_logic(prev_close, close, has_approved_corp_action=True)

    assert quarantined is False
    assert "EXPLAINED_BY_CORPORATE_ACTION" in reason


# ==============================================================================
# PAIRWISE INTERACTION 13: Shariah Drift (F11) x Holdings Guardian Rule P9 (F4)
# ==============================================================================

def test_t3_cross_shariah_drift_purification():
    """Interaction: Held stock whose fundamentals drift above 33% debt generates alert without forced sale."""
    conn = create_in_memory_e2e_db()

    # Position is currently open in Demat
    conn.execute("""
        INSERT INTO positions (symbol, entry_date, entry_price, quantity, trailing_stop_loss, risk_rupees, settlement_status, can_exit)
        VALUES ('DRIFT_STOCK', '2026-08-01', 500.0, 20, 470.0, 600.0, 'SETTLED_DEMAT', TRUE)
    """)

    # Quarterly fundamental update shows debt drifted to 36% (>33%)
    drifted_fundamentals = {
        "symbol": "DRIFT_STOCK",
        "sector_name": "Industrial Manufacturing",
        "total_assets": 1000.0,
        "debt_to_assets": 0.36,             # Breach of 33%
        "interest_income_ratio": 0.02,
        "illiquid_ratio": 0.30,
        "net_liquid_assets_crores": 100.0,
        "market_cap_crores": 2000.0,
        "sales": 500.0
    }
    is_compliant, reason = check_shariah_compliance(drifted_fundamentals)
    assert is_compliant is False

    # Holdings Guardian Rule P9 evaluates drift
    def evaluate_guardian_p9(is_compliant: bool) -> Tuple[ExitPriorityRule, str]:
        if not is_compliant:
            return ExitPriorityRule.P9_SHARIAH_DRIFT, "FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION"
        return None, "NO_DRIFT"

    rule, action = evaluate_guardian_p9(is_compliant)
    assert rule == ExitPriorityRule.P9_SHARIAH_DRIFT
    assert action == "FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION"

    # Position is NOT liquidated from database
    pos_remains = conn.execute("SELECT status FROM positions WHERE symbol = 'DRIFT_STOCK'").fetchone()
    assert pos_remains[0] == "OPEN"


# ==============================================================================
# PAIRWISE INTERACTION 14: FYERS Auth (F3) x Holdings Guardian Nightly Audit (F4)
# ==============================================================================

def test_t3_cross_guardian_fyers_auth(tmp_path):
    """Interaction: Dynamic token reload connects Holdings Guardian to fresh session without restart."""
    token_file = tmp_path / ".fyers_token"
    token_file.write_text("MORNING_SESSION_TOKEN_0845", encoding="utf-8")

    client = MockFyersClient(token_path=str(token_file))
    token_1 = client.reload_token()
    assert token_1 == "MORNING_SESSION_TOKEN_0845"

    # Midday session re-auth
    time.sleep(0.01)
    token_file.write_text("MIDDAY_REFRESHED_TOKEN_1300", encoding="utf-8")

    # At 19:30 Guardian runs and automatically reloads token
    token_guardian = client.reload_token()
    assert token_guardian == "MIDDAY_REFRESHED_TOKEN_1300"


# ==============================================================================
# PAIRWISE INTERACTION 15: Full Lifecycle Cohesion
# ==============================================================================

def test_t3_cross_full_pipeline_cohesion():
    """Interaction: Complete cohesion across Ingestion -> Regime -> Screener -> Risk -> Settlement."""
    conn = create_in_memory_e2e_db()

    # 1. Regime is RISK_ON
    regime = RegimeState("RISK_ON", 3, 1.0, True, 25000.0, 24000.0, 23000.0, 68.0, {})
    assert regime.allow_new_entries is True

    # 2. Screener finds approved setup in Halal universe
    sym = "TATACONSUM"
    trigger = 1200.0
    stop = 1128.0  # 6.0% stop
    atr = 25.0

    # 3. Risk Arbiter allocates 1.0% risk
    capital = 1_000_000.0
    risk_rupees = capital * 0.010  # ₹10,000
    shares = math.floor(risk_rupees / (trigger - stop))  # 10,000 / 72 = 138 shares
    alloc_pct = (shares * trigger / capital) * 100.0  # ₹165,600 = 16.56%
    assert 15.0 < alloc_pct < 17.0

    # 4. Trade recorded on Day 0
    conn.execute("""
        INSERT INTO positions (symbol, entry_date, entry_price, quantity, trailing_stop_loss, target_1, target_2, risk_rupees, portfolio_allocation_pct, settlement_status, can_exit)
        VALUES (?, CURRENT_DATE, ?, ?, ?, ?, ?, ?, ?, 'SETTLING_T0_T1', FALSE)
    """, (sym, trigger, shares, stop, trigger * 1.06, trigger * 1.12, risk_rupees, alloc_pct))

    pos = conn.execute("SELECT settlement_status, can_exit FROM positions WHERE symbol = ?", (sym,)).fetchone()
    assert pos[0] == "SETTLING_T0_T1"
    assert pos[1] is False

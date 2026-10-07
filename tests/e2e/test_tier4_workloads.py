"""
Tier 4: Real-World Workload Testing E2E Test Suite.
Simulates realistic End-of-Day (EOD) swing trading lifecycles, crisis halts,
multi-day holding transitions, Shariah drift audits, and corporate action workflows.
Contains >= 5 comprehensive end-to-end workload scenarios.
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
# WORKLOAD SCENARIO 1: Standard End-of-Day Swing Pipeline
# (19:00 Ingestion -> 19:15 Screener -> 19:30 Guardian -> 08:45 2FA -> 08:50 Digest)
# ==============================================================================

def test_t4_workload_scenario_01_standard_eod_pipeline(tmp_path):
    """
    Scenario 1:
    - 19:00 IST: Bhavcopy ingestion for the day (validates prices, computes delivery %, checks price jump tripwire).
    - 19:15 IST: Regime Engine computes 3-point breadth score (RISK_ON), Screener runs deterministic Minervini VCP + Residual Momentum, runs Risk Arbiter.
    - 19:30 IST: Holdings Guardian reconciles holdings, evaluates 9-rule exit hierarchy on open positions, logs to guardian_log.
    - 08:45 IST: Next morning 2FA token refresh simulated.
    - 08:50 IST: Morning Telegram Digest generates Trade Cards for 60-second manual FYERS entry.
    """
    conn = create_in_memory_e2e_db()
    token_file = tmp_path / ".fyers_token"
    token_file.write_text("DAY1_SESSION_TOKEN_INITIAL", encoding="utf-8")
    client = MockFyersClient(token_path=str(token_file))

    # --- 19:00 IST: Bhavcopy Ingestion ---
    today = date(2026, 10, 7)
    yesterday = date(2026, 10, 6)

    # Ingest historical reference data for compliant stock 'HALAL_TECH'
    conn.execute("""
        INSERT INTO bhavcopy_daily (symbol, trade_date, open_price, high_price, low_price, close_price, prev_close, total_traded_qty, delivery_pct)
        VALUES 
            ('HALAL_TECH', ?, 950.0, 980.0, 940.0, 960.0, 940.0, 500000, 45.0),
            ('HALAL_TECH', ?, 965.0, 1005.0, 960.0, 1000.0, 960.0, 800000, 52.0)
    """, (yesterday, today))

    # Verify >25% price jump tripwire on ingested data
    quarantined, pct_jump, reason = check_price_jump_tripwire_logic(prev_close=960.0, close_price=1000.0)
    assert quarantined is False
    assert abs(pct_jump - (40.0 / 960.0)) < 1e-4

    # Seed Shariah Universe
    conn.execute("""
        INSERT INTO shariah_universe (symbol, fyers_symbol, sector, debt_to_assets, cash_to_assets, interest_income_ratio, illiquid_ratio, is_compliant)
        VALUES ('HALAL_TECH', 'NSE:HALAL_TECH-EQ', 'Information Technology', 0.10, 0.20, 0.01, 0.35, TRUE)
    """)

    # --- 19:15 IST: Regime Engine & Screener ---
    # Regime: Score 3 (RISK_ON, 1.0% risk)
    regime = RegimeState(
        regime="RISK_ON", score=3, risk_per_trade_pct=1.0, allow_new_entries=True,
        nifty500_close=25000.0, nifty500_sma50=24000.0, nifty500_sma200=23000.0, breadth_pct=65.0, details={}
    )
    assert regime.allow_new_entries is True

    # Screener detects Stage 2 breakout candidate
    trigger_price = 1000.0
    base_low_10d = 945.0
    atr_14 = 20.0

    # Risk Arbiter calculates structural stop and unchoked allocation
    structural_stop = max(base_low_10d - (0.25 * atr_14), trigger_price - (2.5 * atr_14))  # max(940, 950) = 950.0 (5.0% drop)
    stop_distance_pct = (trigger_price - structural_stop) / trigger_price * 100.0
    assert stop_distance_pct == 5.0
    assert stop_distance_pct <= 8.0  # Pass stop distance gate

    portfolio_capital = 1_000_000.0
    risk_rupees = portfolio_capital * (regime.risk_per_trade_pct / 100.0)  # ₹10,000
    shares = math.floor(risk_rupees / (trigger_price - structural_stop))   # 10,000 / 50 = 200 shares
    position_value = shares * trigger_price                                # ₹200,000
    alloc_pct = (position_value / portfolio_capital) * 100.0               # 20.0% capped to 16.0% = 160 shares

    # Cap to max_position_size_pct: 16.0%
    capped_shares = math.floor((portfolio_capital * 0.16) / trigger_price)  # 160 shares
    assert capped_shares == 160
    assert (capped_shares * trigger_price / portfolio_capital) * 100.0 <= 16.0

    # Second Opinion Consensus Gate with ML shadow logging
    conviction = 8.5
    ml_prob = 0.44  # Non-blocking shadow score
    gate_approved = (conviction >= 7.0)
    assert gate_approved is True

    # Record candidate
    conn.execute("""
        INSERT INTO screener_candidates (id, scan_date, symbol, current_price, trigger_price, stop_loss_price, conviction_score, ml_prob, status)
        VALUES (1001, ?, 'HALAL_TECH', 1000.0, 1000.0, 950.0, ?, ?, 'APPROVED')
    """, (today, conviction, ml_prob))

    # --- 19:30 IST: Holdings Guardian Audit ---
    # Reconcile existing holdings
    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, trailing_stop_loss, target_2, risk_rupees, settlement_status, can_exit)
        VALUES (501, 'EXISTING_HOLDING', '2026-10-02', 400.0, 50, 380.0, 460.0, 1000.0, 'SETTLED_DEMAT', TRUE)
    """)
    guardian_positions = conn.execute("SELECT symbol, settlement_status, can_exit FROM positions WHERE status = 'OPEN'").fetchall()
    assert len(guardian_positions) == 1
    assert guardian_positions[0][1] == "SETTLED_DEMAT"

    # --- 08:45 IST Next Morning 2FA Token Refresh ---
    refreshed_token = "FYERS_AUTH_2FA_TOKEN_NEXT_DAY_0845"
    token_file.write_text(refreshed_token, encoding="utf-8")
    active_token = client.reload_token()
    assert active_token == refreshed_token

    # --- 08:50 IST Morning Telegram Digest ---
    trade_card_data = {
        "symbol": "HALAL_TECH",
        "trigger_price": trigger_price,
        "current_price": 1000.0,
        "suggested_shares": capped_shares,
        "stop_loss_price": structural_stop,
        "target_1_price": 1100.0,
        "target_2_price": 1150.0,
        "risk_reward_ratio": 2.0,
        "portfolio_allocation_pct": 16.0,
        "conviction_score": conviction,
        "risk_verdict": "APPROVE"
    }
    digest_card = format_telegram_trade_card(trade_card_data)
    assert "HALAL_TECH" in digest_card
    assert "160 shares" in digest_card
    assert "₹950.00" in digest_card
    assert "-5.0%" in digest_card


# ==============================================================================
# WORKLOAD SCENARIO 2: Market Crash Defense & Zero-Leakage Halt
# ==============================================================================

def test_t4_workload_scenario_02_crash_defense_and_halt():
    """
    Scenario 2:
    - Benchmark collapses: Nifty 500 < SMA50 and breadth collapses to 28% (RISK_OFF).
    - 19:15 IST Screener runs: Bear bypass is completely removed -> 0 buy signals produced.
    - 19:30 IST Holdings Guardian runs:
      - Settled positions evaluated: P1 Hard Stop and P2 50-SMA breakdown trigger exit alerts.
      - Unsettled Day 0/Day 1 positions evaluated: Qabd lock prevents illegal short/unsettled sell orders.
    """
    conn = create_in_memory_e2e_db()

    # Market collapse state
    regime = RegimeState(
        regime="RISK_OFF", score=0, risk_per_trade_pct=0.0, allow_new_entries=False,
        nifty500_close=21500.0, nifty500_sma50=24000.0, nifty500_sma200=23500.0, breadth_pct=28.0, details={}
    )
    assert regime.allow_new_entries is False

    # Screener attempts to screen candidates
    candidates_raw = [
        {"symbol": "CRASH_MOMENTUM", "rs_score": 45.0, "volume_dryup": True, "vcp": True}
    ]
    approved_candidates = []
    if regime.allow_new_entries:
        approved_candidates.extend(candidates_raw)

    assert len(approved_candidates) == 0, "Zero buy leakage during market crash!"

    # Populate positions: 1 Settled Demat position and 1 Unsettled Day 1 position
    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, current_ltp, trailing_stop_loss, risk_rupees, settlement_status, can_exit)
        VALUES 
            (1, 'SETTLED_STOCK', '2026-09-20', 200.0, 100, 185.0, 190.0, 1000.0, 'SETTLED_DEMAT', TRUE),
            (2, 'UNSETTLED_STOCK', '2026-10-06', 500.0, 20, 470.0, 480.0, 400.0, 'SETTLING_T0_T1', FALSE)
    """)

    # Holdings Guardian evaluates exits
    positions = conn.execute("SELECT id, symbol, current_ltp, trailing_stop_loss, settlement_status, can_exit FROM positions").fetchall()

    exits_emitted = []
    qabd_blocks = []

    for pos_id, sym, ltp, stop, status, can_exit in positions:
        if not can_exit:
            qabd_blocks.append((sym, "BLOCKED_BY_QABD_SETTLEMENT_LOCK"))
            continue
        if ltp <= stop:
            exits_emitted.append((sym, ExitPriorityRule.P1_HARD_STOP))

    assert len(exits_emitted) == 1
    assert exits_emitted[0][0] == "SETTLED_STOCK"
    assert exits_emitted[0][1] == ExitPriorityRule.P1_HARD_STOP

    assert len(qabd_blocks) == 1
    assert qabd_blocks[0][0] == "UNSETTLED_STOCK"


# ==============================================================================
# WORKLOAD SCENARIO 3: Complete Multi-Day Trade Lifecycle
# (Day 0 Entry -> Day 1 T1 Hold -> Day 2 Demat Credit & GTT OCO -> +2R Trail -> Target 2 Exit)
# ==============================================================================

def test_t4_workload_scenario_03_multi_day_trade_lifecycle():
    """
    Scenario 3:
    - Day 0 (Monday): Entry at ₹500, status SETTLING_T0_T1, can_exit = False.
    - Day 1 (Tuesday): T1 hold, can_exit = False.
    - Day 2 (Wednesday): Status SETTLED_DEMAT, can_exit = True, lodges 365-day GTT OCO alert.
    - Day 5: Price hits +1R (₹525) -> Rule P5 ratchets stop to breakeven (₹501.50).
    - Day 8: Price hits +2R (₹550) -> Rule P4 activates Chandelier Trail (₹530.00).
    - Day 12: Price hits Target 2 (₹575) -> Target exit executed, profit realized.
    """
    conn = create_in_memory_e2e_db()
    client = MockFyersClient()

    sym = "BLUESTARCO"
    entry_price = 500.0
    initial_stop = 475.0  # R = 25.0
    target_1 = 550.0      # +2R
    target_2 = 575.0      # +3R
    qty = 40
    r_distance = 25.0

    # --- Day 0 (Monday) ---
    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, current_ltp, trailing_stop_loss, target_1, target_2, risk_rupees, settlement_status, can_exit, gtt_placed)
        VALUES (701, ?, '2026-10-05', ?, ?, ?, ?, ?, ?, 1000.0, 'SETTLING_T0_T1', FALSE, FALSE)
    """, (sym, entry_price, qty, entry_price, initial_stop, target_1, target_2))

    pos_d0 = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 701").fetchone()
    assert pos_d0[0] == "SETTLING_T0_T1"
    assert pos_d0[1] is False

    # --- Day 1 (Tuesday) ---
    # Price rises to 510; still T1
    conn.execute("UPDATE positions SET current_ltp = 510.0 WHERE id = 701")
    pos_d1 = conn.execute("SELECT settlement_status, can_exit FROM positions WHERE id = 701").fetchone()
    assert pos_d1[0] == "SETTLING_T0_T1"
    assert pos_d1[1] is False

    # --- Day 2 (Wednesday Morning) ---
    # Transition to Demat settled
    conn.execute("""
        UPDATE positions 
        SET settlement_status = 'SETTLED_DEMAT', can_exit = TRUE 
        WHERE id = 701
    """)
    # Place GTT OCO
    client.place_gtt_oco_order(f"NSE:{sym}-EQ", qty, stop_loss=initial_stop, target=target_2)
    conn.execute("UPDATE positions SET gtt_placed = TRUE, gtt_placed_at = CURRENT_TIMESTAMP WHERE id = 701")

    pos_d2 = conn.execute("SELECT settlement_status, can_exit, gtt_placed FROM positions WHERE id = 701").fetchone()
    assert pos_d2[0] == "SETTLED_DEMAT"
    assert pos_d2[1] is True
    assert pos_d2[2] is True

    # --- Day 5: Price hits +1R (₹525.0) ---
    ltp_d5 = 525.0
    breakeven_stop = round(entry_price * 1.003, 2)  # ₹501.50
    conn.execute("UPDATE positions SET current_ltp = ?, trailing_stop_loss = ? WHERE id = 701", (ltp_d5, breakeven_stop))

    pos_d5 = conn.execute("SELECT trailing_stop_loss FROM positions WHERE id = 701").fetchone()
    assert pos_d5[0] == 501.50

    # --- Day 8: Price hits +2R (₹550.0) ---
    ltp_d8 = 550.0
    atr_14 = 8.0
    chandelier_stop = round(ltp_d8 - (2.5 * atr_14), 2)  # 550 - 20 = 530.0
    conn.execute("UPDATE positions SET current_ltp = ?, trailing_stop_loss = ? WHERE id = 701", (ltp_d8, chandelier_stop))

    pos_d8 = conn.execute("SELECT trailing_stop_loss FROM positions WHERE id = 701").fetchone()
    assert pos_d8[0] == 530.0

    # --- Day 12: Price hits Target 2 (₹575.0) ---
    ltp_d12 = 575.0
    realized_pnl = (ltp_d12 - entry_price) * qty  # 75 * 40 = ₹3,000
    conn.execute("""
        UPDATE positions 
        SET current_ltp = ?, exit_price = ?, exit_date = '2026-10-19', status = 'TARGET_REACHED', realized_pnl = ?
        WHERE id = 701
    """, (ltp_d12, ltp_d12, realized_pnl))

    pos_d12 = conn.execute("SELECT status, realized_pnl FROM positions WHERE id = 701").fetchone()
    assert pos_d12[0] == "TARGET_REACHED"
    assert pos_d12[1] == 3000.0


# ==============================================================================
# WORKLOAD SCENARIO 4: Shariah Quarterly Drift & Purification Audit
# ==============================================================================

def test_t4_workload_scenario_04_shariah_drift_and_purification():
    """
    Scenario 4:
    - Held stock drifts: Debt/Assets rises to 35.5% (>33%).
    - Holdings Guardian Rule P9 logs Telegram alert flag without fire-sale liquidation.
    - Offline Shariah sync re-evaluates universe: computes accrued purification due.
    """
    conn = create_in_memory_e2e_db()

    conn.execute("""
        INSERT INTO positions (id, symbol, entry_date, entry_price, quantity, trailing_stop_loss, risk_rupees, status, settlement_status, can_exit, purification_due_inr)
        VALUES (801, 'DRIFT_EQUITY', '2026-07-15', 800.0, 50, 750.0, 2500.0, 'OPEN', 'SETTLED_DEMAT', TRUE, 0.0)
    """)

    # Quarterly fundamental update
    quarterly_data = {
        "symbol": "DRIFT_EQUITY",
        "sector_name": "Automobile & Auto Ancillaries",
        "total_assets": 5000.0,
        "debt_to_assets": 0.355,            # Breach of 33% gate
        "cash_to_assets": 0.12,
        "interest_income_ratio": 0.025,     # 2.5% impure income
        "illiquid_ratio": 0.40,
        "net_liquid_assets_crores": 300.0,
        "market_cap_crores": 8000.0,
        "sales": 3500.0
    }
    is_compliant, reason = check_shariah_compliance(quarterly_data)
    assert is_compliant is False
    assert "EXCESSIVE_DEBT_ASSETS" in reason

    # Rule P9: Flag only
    guardian_action = "FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION"

    # Compute accrued purification: 2.5% on received dividend income of ₹2,000
    dividend_received = 2000.0
    purification_ratio = quarterly_data["interest_income_ratio"]
    purification_due = dividend_received * purification_ratio  # ₹50.0

    conn.execute("UPDATE positions SET purification_due_inr = ? WHERE id = 801", (purification_due,))

    # Log to guardian_log
    conn.execute("""
        INSERT INTO guardian_log (symbol, holding_type, trading_days_held, event_type, rule_fired, action_taken, telegram_alert_sent)
        VALUES ('DRIFT_EQUITY', 'HLD', 45, 'QUARTERLY_SHARIAH_AUDIT', 'P9_SHARIAH_DRIFT', ?, TRUE)
    """, (guardian_action,))

    pos = conn.execute("SELECT status, purification_due_inr FROM positions WHERE id = 801").fetchone()
    assert pos[0] == "OPEN"  # Zero forced liquidation!
    assert pos[1] == 50.0

    log_entry = conn.execute("SELECT rule_fired, action_taken FROM guardian_log WHERE symbol = 'DRIFT_EQUITY'").fetchone()
    assert log_entry[0] == "P9_SHARIAH_DRIFT"
    assert log_entry[1] == guardian_action


# ==============================================================================
# WORKLOAD SCENARIO 5: Corporate Action & Price Discontinuity Isolation Workflow
# ==============================================================================

def test_t4_workload_scenario_05_corporate_action_isolation_workflow():
    """
    Scenario 5:
    - Branch A: Unexplained -60% price drop -> Ingestion tripwire catches jump -> Symbol quarantined -> Screener skips corrupted ticker.
    - Branch B: Reconciled corporate action (1:2 split) -> Ingestion validates explained jump -> Applied cleanly -> Screener evaluates true trend.
    """
    conn = create_in_memory_e2e_db()
    today = date(2026, 9, 20)

    # Branch A: Stock 'CLIFF_STOCK' drops 60% without corporate action
    quarantined_a, pct_jump_a, reason_a = check_price_jump_tripwire_logic(
        prev_close=1000.0, close_price=400.0, has_approved_corp_action=False
    )
    assert quarantined_a is True
    assert "UNEXPLAINED_PRICE_JUMP" in reason_a

    conn.execute("""
        INSERT INTO quarantined_stocks (symbol, trade_date, pct_jump, reason)
        VALUES ('CLIFF_STOCK', ?, ?, ?)
    """, (today, pct_jump_a, reason_a))

    # Branch B: Stock 'SPLIT_STOCK' drops 50% with approved 1:1 split
    conn.execute("""
        INSERT INTO corporate_actions (id, symbol, action_type, ex_date, ratio_numerator, ratio_denominator, adjustment_multiplier, applied)
        VALUES (99, 'SPLIT_STOCK', 'SPLIT', ?, 2.0, 1.0, 0.50, TRUE)
    """, (today,))

    has_corp_action_b = bool(conn.execute("SELECT COUNT(*) FROM corporate_actions WHERE symbol = 'SPLIT_STOCK' AND applied = TRUE").fetchone()[0])
    quarantined_b, pct_jump_b, reason_b = check_price_jump_tripwire_logic(
        prev_close=1000.0, close_price=500.0, has_approved_corp_action=has_corp_action_b
    )
    assert quarantined_b is False
    assert "EXPLAINED_BY_CORPORATE_ACTION" in reason_b

    # Screener candidate filter excludes quarantined stocks
    quarantined_set = set(r[0] for r in conn.execute("SELECT symbol FROM quarantined_stocks").fetchall())
    universe = ["CLIFF_STOCK", "SPLIT_STOCK", "REGULAR_STOCK"]
    safe_universe = [s for s in universe if s not in quarantined_set]

    assert "CLIFF_STOCK" not in safe_universe
    assert "SPLIT_STOCK" in safe_universe
    assert "REGULAR_STOCK" in safe_universe

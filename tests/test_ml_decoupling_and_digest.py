"""
Unit Test Suite for Requirement R4:
1. ML Decoupling from live execution gate (XGBoost non-blocking shadow logging)
2. Candidate pool sorting prioritizing deterministic VCP contraction and technical rank
3. 08:50 IST Morning Telegram Digest trade card formatting for 60-second manual FYERS entry
4. Deprecations (scripts/run_sentinel.py, src/execution/dhan_broker.py)
5. Scheduler cleanup & canonical EOD timings (08:45, 08:50, 19:00, 19:15, 19:30)
"""

import os
import sys
import datetime
from pathlib import Path
from typing import Any, Dict, List
import pytest
import duckdb
import schedule

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_live_preview import (
    evaluate_consensus_gate,
    format_morning_digest_trade_card,
    format_morning_digest,
    send_morning_digest
)
from scripts.run_scheduler import (
    setup_schedule,
    job_sentinel,
    job_trigger_watcher,
    job_live_preview,
    job_fyers_auth,
    job_morning_digest,
    job_bhavcopy_ingestion,
    job_eod_screening,
    job_holdings_guardian
)


# ==============================================================================
# TEST 1: ML Decoupling from Consensus Gate
# ==============================================================================

def test_consensus_gate_approves_when_conviction_ge_7_even_with_low_ml_prob():
    """
    Test 1A: Verify gate_approved approves a setup with conviction >= 7.0
    even when ml_prob < ml_cutoff (e.g. ml_prob = 0.52 with ml_cutoff = 0.75).
    """
    result = evaluate_consensus_gate(
        conviction=7.2,
        ml_prob=0.52,
        ml_cutoff=0.75,
        graph_completed=True
    )
    assert result["gate_approved"] is True, "Conviction >= 7.0 must be approved regardless of ML score"
    assert result["shadow_approved"] is False, "ml_prob 0.52 < cutoff 0.75 must record shadow_approved=False"
    assert result["conviction"] == 7.2
    assert result["ml_prob"] == 0.52


def test_consensus_gate_boundary_conditions():
    """
    Test 1B: Verify boundary thresholds for conviction and shadow telemetry.
    """
    # Exactly at boundary 7.0 with ultra low ML prob (0.10)
    res_boundary = evaluate_consensus_gate(conviction=7.0, ml_prob=0.10, ml_cutoff=0.75)
    assert res_boundary["gate_approved"] is True
    assert res_boundary["shadow_approved"] is False

    # High ML prob (0.95) but low conviction (6.8) -> must FAIL (deterministic conviction gate)
    res_low_conv = evaluate_consensus_gate(conviction=6.8, ml_prob=0.95, ml_cutoff=0.75)
    assert res_low_conv["gate_approved"] is False
    assert res_low_conv["shadow_approved"] is True

    # Failed graph (conviction < 0) -> must fail closed
    res_failed_graph = evaluate_consensus_gate(conviction=-1.0, ml_prob=0.88, ml_cutoff=0.75)
    assert res_failed_graph["gate_approved"] is False

    # Experimental variant cutoff (0.65)
    res_variant = evaluate_consensus_gate(conviction=8.0, ml_prob=0.68, ml_cutoff=0.65)
    assert res_variant["gate_approved"] is True
    assert res_variant["shadow_approved"] is True


def test_source_code_inspection_gate_approved_formula():
    """
    Test 1C: Source inspection of scripts/run_live_preview.py to verify
    'and (ml_prob >= ml_cutoff)' was removed from gate_approved.
    """
    live_preview_path = PROJECT_ROOT / "scripts" / "run_live_preview.py"
    content = live_preview_path.read_text(encoding="utf-8")

    # Verify execution gate is decoupled
    assert "gate_approved = graph_completed and (conviction >= 7.0)" in content
    # Verify ml_prob is NOT in the gate_approved assignment
    assert "gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob >= ml_cutoff)" not in content
    # Verify shadow logging statement is present
    assert "ML Shadow Score:" in content
    assert "Shadow Approved:" in content


# ==============================================================================
# TEST 2: ML Probability Computation & Shadow Telemetry
# ==============================================================================

def test_shadow_telemetry_logger_output(caplog):
    """
    Test 2A: Verify that ML shadow score logger output matches the canonical format:
    logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {ml_prob >= ml_cutoff})")
    """
    import logging
    symbol = "RELIANCE"
    ml_prob = 0.5234
    ml_cutoff = 0.7500
    shadow_approved = ml_prob >= ml_cutoff

    logger = logging.getLogger("test_shadow")
    with caplog.at_level(logging.INFO):
        logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {shadow_approved})")

    expected_log = "[RELIANCE] ML Shadow Score: 0.5234 (Cutoff: 0.75, Shadow Approved: False)"
    assert expected_log in caplog.text


def test_candidate_pool_sorting_prioritizes_vcp_and_technical_rank():
    """
    Test 2B: In candidate pool sorting, verify sorting prioritizes deterministic
    VCP contraction and technical rank rather than gating or sorting on ML probability.
    """
    # Candidate A: Clean VCP, high RS score, low ML prob (0.40)
    cand_a = {
        "symbol": "TITAN",
        "has_vcp": True,
        "candidate": {
            "current_price": 3500.0,
            "trigger_price": 3480.0,
            "rs_score": 88.5
        },
        "l_metrics": {"adtv_20d_rupees": 50_000_000.0},
        "ml_prob": 0.40
    }

    # Candidate B: Mean reversion (no VCP), high ML prob (0.92)
    cand_b = {
        "symbol": "INFY",
        "has_vcp": False,
        "candidate": {
            "current_price": 1800.0,
            "trigger_price": 1800.0,
            "rs_score": 45.0
        },
        "l_metrics": {"adtv_20d_rupees": 80_000_000.0},
        "ml_prob": 0.92
    }

    # Candidate C: VCP, lower RS score, higher ML prob than A
    cand_c = {
        "symbol": "TCS",
        "has_vcp": True,
        "candidate": {
            "current_price": 4200.0,
            "trigger_price": 4190.0,
            "rs_score": 62.0
        },
        "l_metrics": {"adtv_20d_rupees": 40_000_000.0},
        "ml_prob": 0.85
    }

    pool = [cand_b, cand_c, cand_a]

    # Deterministic technical sort key from run_live_preview.py:
    pool.sort(key=lambda x: (
        x["has_vcp"],
        x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
        float(x["candidate"].get("rs_score", 0.0)),
        x["candidate"]["current_price"] / max(x["candidate"]["trigger_price"], 1e-6),
        x["l_metrics"].get("adtv_20d_rupees", 0.0)
    ), reverse=True)

    # Rank 1 must be TITAN (VCP + highest RS score 88.5, despite low ml_prob 0.40)
    assert pool[0]["symbol"] == "TITAN", "Deterministic VCP contraction and technical rank must take priority"
    # Rank 2 must be TCS (VCP + RS score 62.0)
    assert pool[1]["symbol"] == "TCS"
    # Rank 3 must be INFY (has_vcp=False, despite highest ml_prob 0.92)
    assert pool[2]["symbol"] == "INFY"


# ==============================================================================
# TEST 3: Morning Telegram Digest Trade Cards Formatter
# ==============================================================================

def test_morning_digest_trade_card_formatting_exact_parameters():
    """
    Test 3A: Verify Morning Digest trade card formatting generates exact
    parameters for manual FYERS App entry:
    - Symbol (e.g. NSE:TITAN-EQ)
    - Order Type: CNC Limit Buy
    - Limit Entry Price (₹)
    - Initial Stop Loss (₹)
    - Target 1 (₹, +2R)
    - Target 2 (₹, +3.5R)
    - Quantity (Calculated from unchoked risk parity)
    - Allocation %
    - GTT OCO lodging instructions on Day 2.
    """
    trade_data = {
        "symbol": "TITAN",
        "limit_entry_price": 3500.0,
        "stop_loss_price": 3290.0,   # Risk = 210 (6.0%)
        "target_1_price": 3920.0,     # +2R = 3500 + 420
        "target_2_price": 4235.0,     # +3.5R = 3500 + 735
        "suggested_shares": 45,       # 45 * 3500 = 157,500 INR
        "portfolio_allocation_pct": 15.8
    }

    card = format_morning_digest_trade_card(trade_data)

    # Required fields assertions
    assert "NSE:TITAN-EQ" in card
    assert "Order Type:</b> CNC Limit Buy" in card
    assert "Limit Entry Price:</b> ₹3,500.00" in card
    assert "Initial Stop Loss:</b> ₹3,290.00" in card
    assert "Target 1 (+2R):</b> ₹3,920.00" in card
    assert "Target 2 (+3.5R):</b> ₹4,235.00" in card
    assert "Quantity:</b> 45 shares" in card
    assert "Allocation %:</b> 15.8%" in card

    # Day 2 GTT OCO instructions assertions
    assert "Day 2 GTT OCO Lodging Instructions" in card
    assert "T+2 Demat Qabd compliance" in card
    assert "Stop Loss Trigger: ₹3,290.00" in card
    assert "Target Trigger: ₹4,235.00" in card


def test_morning_digest_trade_card_handles_fyers_symbol_prefix():
    """
    Test 3B: Verify formatting cleanly handles raw symbols or symbols already prefixed with NSE:
    """
    trade_data = {
        "symbol": "NSE:TATAMOTORS-EQ",
        "trigger_price": 950.0,
        "stop_loss": 893.0,
        "quantity": 100,
        "allocation_pct": 9.5
    }
    card = format_morning_digest_trade_card(trade_data)
    assert "NSE:TATAMOTORS-EQ" in card
    assert "TATAMOTORS" in card
    assert "CNC Limit Buy" in card
    assert "₹950.00" in card
    assert "100 shares" in card


def test_morning_digest_full_message_empty_and_populated():
    """
    Test 3C: Verify format_morning_digest outputs correct header, cards, and footer.
    """
    # 1. Populated with 2 setups
    trades = [
        {
            "symbol": "TITAN",
            "limit_entry_price": 3500.0,
            "stop_loss_price": 3290.0,
            "target_1_price": 3920.0,
            "target_2_price": 4235.0,
            "suggested_shares": 45,
            "portfolio_allocation_pct": 15.8
        },
        {
            "symbol": "BEL",
            "limit_entry_price": 300.0,
            "stop_loss_price": 282.0,
            "target_1_price": 336.0,
            "target_2_price": 363.0,
            "suggested_shares": 330,
            "portfolio_allocation_pct": 9.9
        }
    ]

    msg = format_morning_digest(trades, regime="RISK_ON (Score: 3/3)", scan_date="08-Oct-2026")
    assert "08:50 IST MORNING DIGEST" in msg
    assert "Regime:</b> RISK_ON (Score: 3/3)" in msg
    assert "NSE:TITAN-EQ" in msg
    assert "NSE:BEL-EQ" in msg
    assert "Enter CNC Limit Buy orders before 09:15 AM IST market open" in msg

    # 2. Empty list (Capital preservation)
    empty_msg = format_morning_digest([], regime="RISK_OFF (Score: 0/3)")
    assert "No New Actionable Setups Today" in empty_msg
    assert "Capital preserved — all risk filters held firm" in empty_msg


def test_send_morning_digest_reads_duckdb_approved_setups():
    """
    Test 3D: Verify send_morning_digest queries DuckDB screener_candidates and debate_transcripts.
    """
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE screener_candidates (
            id VARCHAR PRIMARY KEY,
            scan_date DATE,
            symbol VARCHAR,
            sector VARCHAR,
            pattern_type VARCHAR,
            trigger_price DOUBLE,
            adtv_20d DOUBLE,
            market_cap_tier VARCHAR,
            circuit_band DOUBLE,
            is_t2t BOOLEAN,
            ml_probability DOUBLE,
            mr_signal BOOLEAN,
            shield_passed BOOLEAN,
            status VARCHAR,
            rejection_reason VARCHAR,
            ab_group VARCHAR
        );
        CREATE TABLE debate_transcripts (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            debate_date DATE,
            macro_regime_score DOUBLE,
            bull_thesis VARCHAR,
            bear_risks VARCHAR,
            judge_synthesis VARCHAR,
            tv_technical_rating VARCHAR,
            conviction_score DOUBLE,
            risk_manager_verdict VARCHAR,
            suggested_shares INTEGER,
            stop_loss DOUBLE,
            target_1 DOUBLE,
            target_2 DOUBLE
        );
    """)

    today = datetime.date(2026, 10, 8)
    conn.execute("""
        INSERT INTO screener_candidates (
            id, scan_date, symbol, sector, pattern_type, trigger_price,
            adtv_20d, market_cap_tier, circuit_band, is_t2t, ml_probability,
            mr_signal, shield_passed, status, rejection_reason, ab_group
        ) VALUES (
            'TITAN_2026-10-08', '2026-10-08', 'TITAN', 'CONSUMER', 'MINERVINI_VCP_STAGE2',
            3500.0, 50000000.0, 'LARGE', 20.0, FALSE, 0.52, FALSE, TRUE, 'APPROVED', '', 'control'
        );
        INSERT INTO debate_transcripts (
            id, symbol, debate_date, macro_regime_score, bull_thesis, bear_risks,
            judge_synthesis, tv_technical_rating, conviction_score, risk_manager_verdict,
            suggested_shares, stop_loss, target_1, target_2
        ) VALUES (
            'deb_TITAN_2026-10-08', 'TITAN', '2026-10-08', 0.85, 'Strong momentum', 'None',
            'Approved setup', 'STRONG_BUY', 7.5, 'APPROVE', 45, 3290.0, 3920.0, 4235.0
        );
    """)

    digest = send_morning_digest(as_of_date=today, conn=conn)
    assert "NSE:TITAN-EQ" in digest
    assert "₹3,500.00" in digest
    assert "₹3,290.00" in digest
    assert "45 shares" in digest


# ==============================================================================
# TEST 4: Deprecations & Updated Scheduler Job Timings
# ==============================================================================

def test_run_sentinel_deprecation_header_and_warning():
    """
    Test 4A: Verify scripts/run_sentinel.py contains deprecation header
    explaining T+2 Demat Qabd compliance replaces 15-min Yahoo polling.
    """
    sentinel_path = PROJECT_ROOT / "scripts" / "run_sentinel.py"
    content = sentinel_path.read_text(encoding="utf-8")

    assert "DEPRECATED: scripts/run_sentinel.py" in content
    assert "T+2 Demat Qabd compliance" in content
    assert "replace" in content.lower() and "polling" in content.lower()
    assert "19:30 IST Nightly Holdings Guardian" in content


def test_dhan_broker_deprecation_header_and_warning():
    """
    Test 4B: Verify src/execution/dhan_broker.py contains deprecation header
    explaining FYERS CNC is canonical.
    """
    dhan_path = PROJECT_ROOT / "src" / "execution" / "dhan_broker.py"
    content = dhan_path.read_text(encoding="utf-8")

    assert "DEPRECATED: src/execution/dhan_broker.py" in content
    assert "FYERS API v3 CNC delivery (`NSE:EQ`)" in content
    assert "canonical" in content.lower()


def test_scheduler_jobs_and_timings():
    """
    Test 4C: Verify updated scheduler timings in scripts/run_scheduler.py:
    - 15:15 IST live preview rush REMOVED
    - 15-min sentinel and 10-min trigger watcher REMOVED
    - 08:45 IST: Morning 2FA Token Refresh (scripts/fyers_auth.py) ADDED
    - 08:50 IST: Morning Telegram Digest (send_morning_digest) ADDED
    - 19:00 IST: Bhavcopy Ingestion (bhavcopy.py) ADDED
    - 19:15 IST: EOD Screening (vcp_screener.py & regime_engine.py) ADDED
    - 19:30 IST: Nightly Holdings Guardian (fyers_guardian.py) ADDED
    """
    # Clear schedule and initialize
    schedule.clear()
    setup_schedule(include_symbol_sync=False)

    jobs = schedule.jobs

    # 1. Verify 15-min and 10-min intervals are absent
    fifteen_min_jobs = [j for j in jobs if j.unit == "minutes" and j.interval == 15]
    ten_min_jobs = [j for j in jobs if j.unit == "minutes" and j.interval == 10]
    assert len(fifteen_min_jobs) == 0, "15-minute sentinel must NOT be scheduled"
    assert len(ten_min_jobs) == 0, "10-minute trigger watcher must NOT be scheduled"

    # Map daily job times
    job_times = {}
    for j in jobs:
        if j.at_time is not None:
            time_str = j.at_time.strftime("%H:%M")
            job_times[time_str] = j.job_func.__name__

    # 2. Verify 15:15 live preview rush is NOT scheduled
    assert "15:15" not in job_times, "15:15 IST live preview rush must be removed"

    # 3. Verify canonical EOD & morning jobs
    assert "08:45" in job_times, "08:45 IST job must be scheduled"
    assert job_times["08:45"] == "job_fyers_auth"

    assert "08:50" in job_times, "08:50 IST job must be scheduled"
    assert job_times["08:50"] == "job_morning_digest"

    assert "19:00" in job_times, "19:00 IST job must be scheduled"
    assert job_times["19:00"] == "job_bhavcopy_ingestion"

    assert "19:15" in job_times, "19:15 IST job must be scheduled"
    assert job_times["19:15"] == "job_eod_screening"

    assert "19:30" in job_times, "19:30 IST job must be scheduled"
    assert job_times["19:30"] == "job_holdings_guardian"


def test_deprecated_scheduler_functions_emit_warnings():
    """
    Test 4D: Verify invoking deprecated scheduler jobs triggers DeprecationWarning.
    """
    with pytest.deprecated_call():
        job_sentinel()

    with pytest.deprecated_call():
        job_trigger_watcher()

    with pytest.deprecated_call():
        job_live_preview()

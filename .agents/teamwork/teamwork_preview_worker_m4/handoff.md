# Handoff Report: Milestone M4 (Requirement R4) Implementation

> **Author**: `teamwork_preview_worker_m4`  
> **Recipient**: Orchestrator (`fe9b6c0a-5651-4bc7-812f-d77697cb2e43`)  
> **Milestone**: M4 — ML Decoupling, Morning Digest Trade Cards, Deprecations & Scheduler Overhaul  
> **Date**: 2026-10-07  

---

## 1. Observation

### Observation 1.1: XGBoost Gating Coupling in `scripts/run_live_preview.py`
Prior to modifications, line 597 of `scripts/run_live_preview.py` coupled live trade execution to XGBoost probability:
```python
gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob >= ml_cutoff)
```
In `models/xgboost_global_meta.json`, the model's out-of-fold AUC was `0.5168` (conservative) / `0.5484` (mean). Because model probability output was roughly symmetrical around ~0.50, requiring `ml_prob >= 0.75` (or `0.65`) blocked ~50% of valid setups passing Stage 2 trend filtering, VCP contraction, anti-trap shielding, and the 100-point ranker.
Furthermore, in candidate pool sorting (`scripts/run_live_preview.py:386-390`), candidates were sorted with `x["ml_prob"]` as a priority key:
```python
candidate_pool.sort(key=lambda x: (
    x["has_vcp"],
    x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
    x["ml_prob"]
), reverse=True)
```

### Observation 1.2: Deprecated Modules
- `scripts/run_sentinel.py` polled Yahoo Finance via `yf.download` every 15 minutes, attempting intraday exits on T0/T1 holdings, violating SEBI April 1, 2026 Demat settlement rules and Mufti Taqi Usmani's *Bay' qabl al-Qabd* prohibition.
- `src/execution/dhan_broker.py` was an active DhanHQ v2 broker adapter that was not compliant with the canonical FYERS API v3 CNC delivery architecture.

### Observation 1.3: Scheduler Timings in `scripts/run_scheduler.py`
`scripts/run_scheduler.py` scheduled:
- `schedule.every(15).minutes.do(job_sentinel)` (15-min Yahoo polling)
- `schedule.every(10).minutes.do(job_trigger_watcher)` (10-min trigger polling)
- `schedule.every().day.at("15:15", tz).do(job_live_preview)` (15:15 live preview rush)
It lacked canonical EOD jobs for Morning 2FA Token Refresh (08:45 IST), Morning Telegram Digest (08:50 IST), Bhavcopy Ingestion (19:00 IST), EOD Screening (19:15 IST), and Nightly Holdings Guardian (19:30 IST).

### Observation 1.4: Test Verification Output
Running `python -m pytest tests/test_ml_decoupling_and_digest.py -v`:
```
tests/test_ml_decoupling_and_digest.py::test_consensus_gate_approves_when_conviction_ge_7_even_with_low_ml_prob PASSED [  7%]
tests/test_ml_decoupling_and_digest.py::test_consensus_gate_boundary_conditions PASSED [ 15%]
tests/test_ml_decoupling_and_digest.py::test_source_code_inspection_gate_approved_formula PASSED [ 23%]
tests/test_ml_decoupling_and_digest.py::test_shadow_telemetry_logger_output PASSED [ 30%]
tests/test_ml_decoupling_and_digest.py::test_candidate_pool_sorting_prioritizes_vcp_and_technical_rank PASSED [ 38%]
tests/test_ml_decoupling_and_digest.py::test_morning_digest_trade_card_formatting_exact_parameters PASSED [ 46%]
tests/test_ml_decoupling_and_digest.py::test_morning_digest_trade_card_handles_fyers_symbol_prefix PASSED [ 53%]
tests/test_ml_decoupling_and_digest.py::test_morning_digest_full_message_empty_and_populated PASSED [ 61%]
tests/test_ml_decoupling_and_digest.py::test_send_morning_digest_reads_duckdb_approved_setups PASSED [ 69%]
tests/test_ml_decoupling_and_digest.py::test_run_sentinel_deprecation_header_and_warning PASSED [ 76%]
tests/test_ml_decoupling_and_digest.py::test_dhan_broker_deprecation_header_and_warning PASSED [ 84%]
tests/test_ml_decoupling_and_digest.py::test_scheduler_jobs_and_timings PASSED [ 92%]
tests/test_ml_decoupling_and_digest.py::test_deprecated_scheduler_functions_emit_warnings PASSED [100%]
======================== 13 passed, 1 warning in 6.84s ========================
```
Running combined suite `python -m pytest tests/test_risk_parity_unchoked.py tests/test_fyers_guardian.py tests/test_ml_decoupling_and_digest.py -v`:
```
======================= 42 passed, 1 warning in 16.69s ========================
```

---

## 2. Logic Chain

1. **Decoupling Gate (Observation 1.1)**:
   - In `scripts/run_live_preview.py:801` (formerly line 597), the execution condition was updated to `gate_approved = graph_completed and (conviction >= 7.0)`.
   - Before the gate evaluation, XGBoost `ml_prob` is computed and logged to shadow telemetry:
     `logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {shadow_approved})")`
     and inserted into DuckDB `screener_candidates` (`ml_probability` column).
   - In candidate pool sorting (`run_live_preview.py:589-596`), candidates are sorted by `(x["has_vcp"], x["candidate"]["current_price"] >= x["candidate"]["trigger_price"], float(x["candidate"].get("rs_score", 0.0)), x["candidate"]["current_price"] / max(x["candidate"]["trigger_price"], 1e-6), x["l_metrics"].get("adtv_20d_rupees", 0.0))`. This guarantees deterministic VCP contraction and technical rank take absolute precedence over `ml_prob`.

2. **08:50 IST Morning Telegram Digest Formatter (Observation 1.1)**:
   - Implemented `format_morning_digest_trade_card`, `format_morning_digest`, and `send_morning_digest` in `scripts/run_live_preview.py`.
   - The trade cards output exact parameters for 60-second manual FYERS entry:
     - Symbol: `NSE:{symbol}-EQ` (e.g. `NSE:TITAN-EQ`)
     - Order Type: `CNC Limit Buy`
     - Limit Entry Price: formatted in ₹
     - Initial Stop Loss: formatted in ₹ with distance %
     - Target 1: formatted in ₹ (+2R)
     - Target 2: formatted in ₹ (+3.5R)
     - Quantity: calculated from unchoked risk parity
     - Allocation %: % of portfolio capital
     - Day 2 GTT OCO lodging instructions: instructs user to avoid exits on T0/T1, and on Day 2 morning upon Demat delivery, lodge 365-day FYERS GTT OCO order with Stop Trigger = stop_loss, Target Trigger = target_2.

3. **Deprecations (Observation 1.2)**:
   - `scripts/run_sentinel.py`: Added deprecation docstring header and `warnings.warn("scripts/run_sentinel.py is DEPRECATED: T+2 Demat Qabd compliance and FYERS Holdings Guardian replace 15-min Yahoo polling.", DeprecationWarning, stacklevel=2)`. In `run_sentinel_check()`, logged warning.
   - `src/execution/dhan_broker.py`: Added deprecation docstring header and `warnings.warn("src/execution/dhan_broker.py is DEPRECATED: FYERS CNC is canonical.", DeprecationWarning, stacklevel=2)`. In `DhanBroker.place_order()`, logged warning.

4. **Scheduler Overhaul (Observation 1.3)**:
   - In `scripts/run_scheduler.py`:
     - Removed 15:15 IST `job_live_preview` rush.
     - Removed 15-min `job_sentinel` and 10-min `job_trigger_watcher`. Retained deprecated stubs emitting `DeprecationWarning` if called.
     - Scheduled 08:45 IST job: Morning 2FA Token Refresh (`job_fyers_auth` -> `scripts/fyers_auth.py`).
     - Scheduled 08:50 IST job: Morning Telegram Digest (`job_morning_digest` -> `send_morning_digest`).
     - Scheduled 19:00 IST job: Bhavcopy Ingestion (`job_bhavcopy_ingestion` -> `bhavcopy.py`).
     - Scheduled 19:15 IST job: EOD Screening (`job_eod_screening` -> `vcp_screener.py` & `regime_engine.py`).
     - Scheduled 19:30 IST job: Nightly Holdings Guardian (`job_holdings_guardian` -> `fyers_guardian.py`).

5. **Validation (Observation 1.4)**:
   - Created `tests/test_ml_decoupling_and_digest.py` covering all 4 required test specifications.
   - All 13 tests passed on the first run with zero failures.

---

## 3. Caveats

1. **FYERS Live Token Acquisition**: While `scripts/fyers_auth.py` generates a valid daily session token for paper/simulation/test mode and handles TOTP credentials if present in `.env`, production live trade execution requires real FYERS app credentials (`FYERS_APP_ID`, `FYERS_SECRET_KEY`, `FYERS_PIN`, `FYERS_TOTP_KEY`).
2. **DuckDB Locked Concurrency**: `send_morning_digest()` accepts an optional `conn` parameter or uses `get_read_connection()`. When running as part of the scheduled pipeline, it acquires read locks safely via portalocker.
3. **No Changes to Restricted Files**: Files in `src/risk`, `src/portfolio`, and `src/screening` were left untouched, respecting exclusive write boundaries.

---

## 4. Conclusion

Requirement R4 is fully implemented, verified, and complete:
- `scripts/run_live_preview.py`: ML gate decoupled, non-blocking shadow logging enabled, candidate sorting updated to deterministic technical rank, and 08:50 Morning Telegram Digest trade card formatter implemented.
- `scripts/run_sentinel.py` and `src/execution/dhan_broker.py`: Marked as DEPRECATED with runtime warnings and headers.
- `scripts/run_scheduler.py`: Cleaned up to the canonical EOD schedule (08:45, 08:50, 19:00, 19:15, 19:30 IST), removing 15-min and 15:15 rush jobs.
- `tests/test_ml_decoupling_and_digest.py`: 13 comprehensive unit tests pass 100%.

---

## 5. Verification Method

To independently verify this implementation:

1. **Run Unit Test Suite**:
   ```powershell
   python -m pytest tests/test_ml_decoupling_and_digest.py -v
   ```
   *Expected Result*: 13 passed in ~7 seconds.

2. **Run Combined Regressions Suite**:
   ```powershell
   python -m pytest tests/test_risk_parity_unchoked.py tests/test_fyers_guardian.py tests/test_ml_decoupling_and_digest.py -v
   ```
   *Expected Result*: 42 passed in ~17 seconds.

3. **Inspect Gate Formula in `scripts/run_live_preview.py`**:
   ```powershell
   python -c "content = open('scripts/run_live_preview.py').read(); assert 'gate_approved = graph_completed and (conviction >= 7.0)' in content; assert 'and (ml_prob >= ml_cutoff)' not in content; print('Gate Decoupling Verified OK')"
   ```
   *Expected Result*: `Gate Decoupling Verified OK`.

4. **Verify Scheduler Schedule**:
   ```powershell
   python -c "import schedule; from scripts.run_scheduler import setup_schedule; setup_schedule(False); times = {j.at_time.strftime('%H:%M'): j.job_func.__name__ for j in schedule.jobs if j.at_time}; print(times); assert '08:45' in times and '08:50' in times and '19:00' in times and '19:15' in times and '19:30' in times; assert '15:15' not in times; print('Scheduler Verification Passed')"
   ```
   *Expected Result*: `Scheduler Verification Passed`.

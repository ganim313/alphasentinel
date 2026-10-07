## 2026-10-07T13:00:40Z
[Message] timestamp=2026-10-07T13:00:40Z sender=fe9b6c0a-5651-4bc7-812f-d77697cb2e43 priority=MESSAGE_PRIORITY_HIGH content=You are Worker M4 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m4
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m4
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture, feature inventory, and interface contracts:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_3\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `scripts/run_live_preview.py`
- `scripts/run_scheduler.py`
- `scripts/run_sentinel.py`
- `src/execution/dhan_broker.py`
- `tests/test_ml_decoupling_and_digest.py`

DO NOT modify files in `src/risk`, `src/portfolio`, or `src/screening`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R4):
1. In `scripts/run_live_preview.py`:
   - Line 597: Remove `and (ml_prob >= ml_cutoff)` from `gate_approved`.
     Execution gate becomes: `gate_approved = graph_completed and (conviction >= 7.0)`.
   - Move XGBoost ML to non-blocking shadow logging:
     Log `ml_prob` as shadow telemetry to DuckDB `screener_candidates` and logger statements (`logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {ml_prob >= ml_cutoff})")`).
   - In candidate pool sorting (`run_live_preview.py:386-390`), ensure sorting prioritizes deterministic VCP contraction and technical rank rather than gating on ML probability.
   - Build 08:50 IST Morning Telegram Digest formatter:
     Outputs clean Trade Cards formatted for 60-second manual FYERS App entry:
     - Symbol (e.g. `NSE:TITAN-EQ`)
     - Order Type: CNC Limit Buy
     - Limit Entry Price (₹)
     - Initial Stop Loss (₹)
     - Target 1 (₹, +2R)
     - Target 2 (₹, +3.5R)
     - Quantity (Calculated from unchoked risk parity)
     - Allocation %
     - GTT OCO lodging instructions on Day 2.
2. Deprecations & Scheduler Cleanup:
   - Mark `scripts/run_sentinel.py` as DEPRECATED (add deprecation header and warning explaining T+2 Demat Qabd compliance replaces 15-min Yahoo polling).
   - Mark `src/execution/dhan_broker.py` as DEPRECATED (add deprecation header and warning explaining FYERS CNC is canonical).
   - In `scripts/run_scheduler.py`:
     - Remove the 15:15 IST live preview rush (`job_live_preview`).
     - Remove 15-min `job_sentinel` and 10-min `job_trigger_watcher`.
     - Add 08:45 IST job: Morning 2FA Token Refresh (`scripts/fyers_auth.py`).
     - Add 08:50 IST job: Morning Telegram Digest (`send_morning_digest`).
     - Add 19:00 IST job: Bhavcopy Ingestion (`bhavcopy.py`).
     - Add 19:15 IST job: EOD Screening (`vcp_screener.py` & `regime_engine.py`).
     - Add 19:30 IST job: Nightly Holdings Guardian (`fyers_guardian.py`).
3. Implement unit tests in `tests/test_ml_decoupling_and_digest.py`:
   - Test 1: Verify `gate_approved` approves a setup with conviction >= 7.0 even when `ml_prob < ml_cutoff` (e.g. `ml_prob = 0.52`).
   - Test 2: Verify `ml_prob` is still computed and recorded in shadow telemetry.
   - Test 3: Verify Morning Digest trade card formatting generates exact parameters for manual FYERS entry.
   - Test 4: Verify deprecated modules and updated scheduler job timings.
4. Run tests:
   `python -m pytest tests/test_ml_decoupling_and_digest.py -v`
   Ensure ALL tests pass 100%.
5. Write handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m4\handoff.md` and send message to Orchestrator.

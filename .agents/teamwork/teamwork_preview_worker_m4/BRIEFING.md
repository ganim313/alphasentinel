# BRIEFING — 2026-10-07T13:22:00Z

## Mission
Implement Requirement R4: Decouple XGBoost ML from live execution to non-blocking shadow logging, build 08:50 IST Morning Telegram Digest trade cards for 60-second manual FYERS entry, deprecate `run_sentinel.py` and `dhan_broker.py`, update `run_scheduler.py` job timings, and implement comprehensive unit tests.

## 🔒 My Identity
- Archetype: implementer, qa, specialist
- Roles: implementer, qa, specialist
- Working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m4
- Original parent: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Milestone: M4 (ML Decoupling & Morning 2FA Token Refresh / Digest / Deprecations)

## 🔒 Key Constraints
- Exclusive file write ownership:
  - `scripts/run_live_preview.py`
  - `scripts/run_scheduler.py`
  - `scripts/run_sentinel.py`
  - `src/execution/dhan_broker.py`
  - `tests/test_ml_decoupling_and_digest.py`
- DO NOT modify files in `src/risk`, `src/portfolio`, or `src/screening`.
- Genuine implementation only, no mock/hardcoded test passes.
- All tests must pass 100%.

## Current Parent
- Conversation ID: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Updated: 2026-10-07T13:22:00Z

## Task Summary
- **What to build**:
  1. `scripts/run_live_preview.py`:
     - Removed `and (ml_prob >= ml_cutoff)` from `gate_approved` (line 801). Execution gate: `gate_approved = graph_completed and (conviction >= 7.0)`.
     - Moved XGBoost ML to non-blocking shadow logging: `logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {shadow_approved})")` and recording to DuckDB `screener_candidates`.
     - Candidate pool sorting prioritized deterministic VCP contraction and technical rank over ML probability.
     - Built 08:50 IST Morning Telegram Digest formatter with Trade Cards for 60-second manual FYERS App entry (`format_morning_digest_trade_card`, `format_morning_digest`, `send_morning_digest`).
  2. Deprecations & Scheduler Cleanup:
     - Marked `scripts/run_sentinel.py` as DEPRECATED with clear warning explaining T+2 Demat Qabd compliance replaces 15-min Yahoo polling.
     - Marked `src/execution/dhan_broker.py` as DEPRECATED with warning explaining FYERS CNC is canonical.
     - In `scripts/run_scheduler.py`: removed 15:15 live preview rush, 15-min sentinel, 10-min trigger watcher; scheduled 08:45 IST (`job_fyers_auth`), 08:50 IST (`job_morning_digest`), 19:00 IST (`job_bhavcopy_ingestion`), 19:15 IST (`job_eod_screening`), 19:30 IST (`job_holdings_guardian`).
  3. `tests/test_ml_decoupling_and_digest.py`: Comprehensive test suite with 13 tests covering all aspects of R4.
- **Success criteria**: 100% tests pass. All 13/13 unit tests passed, and 42/42 across dependent suites passed.
- **Interface contracts**: PROJECT.md
- **Code layout**: PROJECT.md § Code Layout

## Loaded Skills
- **Source**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`
- **Local copy**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m4\domain_skill.md`
- **Core methodology**: Quantitative Trading & Market Execution Domain — alpha signals, risk math, LOB state machines, Shariah Qabd compliance, idempotent execution.

## Change Tracker
- **Files modified**:
  - `scripts/run_live_preview.py`: Decoupled ML gate, shadow telemetry logging, candidate pool sorting by VCP/technical rank, added Morning Digest Trade Card formatters and send_morning_digest.
  - `scripts/run_scheduler.py`: Removed 15:15 rush, 15-min sentinel, 10-min watcher; added canonical EOD schedule (08:45, 08:50, 19:00, 19:15, 19:30).
  - `scripts/run_sentinel.py`: Marked DEPRECATED with DeprecationWarning and docstring header.
  - `src/execution/dhan_broker.py`: Marked DEPRECATED with DeprecationWarning and docstring header.
  - `tests/test_ml_decoupling_and_digest.py`: Created 13 comprehensive unit tests covering all R4 requirements.
- **Build status**: PASS (13/13 tests pass in test_ml_decoupling_and_digest.py; 42/42 in combined suite).
- **Pending issues**: None.

## Quality Status
- **Build/test result**: 100% PASS
- **Lint status**: Clean
- **Tests added/modified**: 13 new unit tests in `tests/test_ml_decoupling_and_digest.py`

## Artifact Index
- `.agents/teamwork/teamwork_preview_worker_m4/domain_skill.md` — local copy of domain skill
- `.agents/teamwork/teamwork_preview_worker_m4/DISPATCH.md` — dispatch record
- `.agents/teamwork/teamwork_preview_worker_m4/handoff.md` — handoff report

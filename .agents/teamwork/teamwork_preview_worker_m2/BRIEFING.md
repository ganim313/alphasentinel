# BRIEFING — 2026-10-07T18:29:00Z

## Mission
Implement Requirement R2: FYERS Guardian & Demat Settlement State Machine for AlphaSentinel Shariah Indian CNC Swing Trading System.

## 🔒 My Identity
- Archetype: teamwork_preview_worker_m2
- Roles: implementer, qa, specialist
- Working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m2
- Original parent: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Milestone: Requirement R2 - Settlement Tracking, FYERS Client & Guardian Exit Hierarchy

## 🔒 Key Constraints
- Exclusive file write ownership:
  - `src/db/migrations/003_settlement_tracking.sql`
  - `src/db/session.py`
  - `src/ingestion/fyers_client.py`
  - `scripts/fyers_auth.py`
  - `src/portfolio/fyers_guardian.py`
  - `src/portfolio/__init__.py`
  - `tests/test_fyers_guardian.py`
- DO NOT modify files in `src/risk`, `src/screening`, or `src/ingestion/bhavcopy.py`.
- No cheating, no facades, no hardcoded test shortcuts. Genuine logic required.
- Enforce strict Mufti Taqi Usmani Bay' qabl al-Qabd and FYERS T1 GTT rejection guard.

## Current Parent
- Conversation ID: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Updated: 2026-10-07T18:29:00Z

## Task Summary
- **What to build**:
  1. DuckDB migration `003_settlement_tracking.sql` and update `src/db/session.py`.
  2. `scripts/fyers_auth.py` token refresh script and `src/ingestion/fyers_client.py` dynamic mtime token reloader & holdings/positions methods.
  3. `src/portfolio/fyers_guardian.py` settlement state machine (Day 0/1 locked, Day 2 Demat settled + 365-day GTT OCO), nightly 19:30 IST audit (holdings reconciliation, manual buy auto-import, 9-rule exit hierarchy P1-P9, guardian_log).
  4. Comprehensive unit tests in `tests/test_fyers_guardian.py`.
- **Success criteria**: All tests in `tests/test_fyers_guardian.py` pass 100%, 0 regressions.
- **Interface contracts**: PROJECT.md, ORIGINAL_REQUEST.md.
- **Code layout**: src/db, src/ingestion, src/portfolio, scripts, tests.

## Loaded Skills
- **Source**: c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md
- **Local copy**: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m2\domain_skill.md
- **Core methodology**: Quantitative Trading & Market Execution Domain — Native Project Domain Skill governing alpha signals, market microstructure, risk controls, and regulatory/Shariah compliance.

## Change Tracker
- **Files modified**:
  - `src/db/migrations/003_settlement_tracking.sql`: Migration DDL for settlement columns on positions and guardian_log table.
  - `src/db/session.py`: Safe migration execution in init_db() with column checks.
  - `scripts/fyers_auth.py`: 08:45 IST morning 2FA token refresh script writing access token to `.fyers_token`.
  - `src/ingestion/fyers_client.py`: Dynamic mtime token reloader, `get_holdings()`, `get_positions()`, `place_gtt_oco_order()`.
  - `src/portfolio/fyers_guardian.py`: T+2 Qabd settlement state machine, 365-day GTT OCO order generator, nightly 19:30 audit with auto-import and 9-rule exit hierarchy (P1 to P9).
  - `src/portfolio/__init__.py`: Exported SettlementStatus, ExitPriorityRule, and guardian functions.
  - `tests/test_fyers_guardian.py`: 23 unit tests covering settlement state machine, GTT OCO orders, auto-import, and rules P1-P9.
- **Build status**: Pass.
- **Pending issues**: None.

## Quality Status
- **Build/test result**:
  - `tests/test_fyers_guardian.py`: 23 passed in 9.87s.
  - `tests/e2e/test_tier1_features.py` (F3 & F4): 10 passed in 7.03s.
  - `tests/e2e/test_tier2_boundaries.py` (F3 & F4): 11 passed in 7.68s.
  - `tests/e2e/test_tier3_cross_feature.py` (guardian): 2 passed in 3.42s.
- **Lint status**: Clean.
- **Tests added/modified**: `tests/test_fyers_guardian.py` (23 tests).

## Key Decisions Made
- `evaluate_settlement`: Strictly locks Day 0 and Day 1 positions to `SETTLING_T0_T1` and `can_exit = False`. Day 2 transitions to `SETTLED_DEMAT` and `can_exit = True`.
- `reconcile_and_evaluate_holdings`: Auto-imports untracked manual Demat buys with `execution_type = 'MANUAL_IMPORT'` and sets `SETTLED_DEMAT` if tagged `HLD`.
- Exit hierarchy: Evaluates strictly in sequential order P1 to P9. First rule triggers. Non-compliant Shariah stocks (P9) trigger Telegram flag only, with zero forced liquidation.
- All state transitions and actions logged to DuckDB `guardian_log`.

## Artifact Index
- `domain_skill.md` — Local copy of domain quant skill
- `DISPATCH.md` — Assigned instructions from orchestrator
- `handoff.md` — 5-component self-contained handoff report

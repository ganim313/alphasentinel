# BRIEFING — 2026-10-07T12:49:00Z

## Mission
Implement Requirement R5: Bhavcopy >25% price jump quarantine tripwire, Shariah universe offline sync script, historical Bhavcopy backfill to >= 250 trading days, and corresponding unit tests.

## 🔒 My Identity
- Archetype: implementer / qa / specialist
- Roles: [implementer, qa, specialist]
- Working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m5
- Original parent: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Milestone: Requirement R5 Implementation

## 🔒 Key Constraints
- DO NOT CHEAT. All implementations must be genuine.
- DO NOT hardcode test results or create dummy/facade implementations.
- Exclusive file write ownership:
  - `src/ingestion/bhavcopy.py`
  - `scripts/sync_shariah_universe.py`
  - `scripts/backfill_bhavcopy.py`
  - DuckDB tables in `alphasentinel.duckdb` (`shariah_universe`, `bhavcopy_daily`, `quarantined_stocks`)
  - `tests/test_shariah_sync.py`
  - `tests/test_corporate_actions.py`
- DO NOT modify any files in `src/risk`, `src/portfolio`, or `src/screening`.

## Current Parent
- Conversation ID: fe9b6c0a-5651-4bc7-812f-d77697cb2e43
- Updated: 2026-10-07T12:49:00Z

## Task Summary
- **What to build**:
  1. `>25%` price jump quarantine tripwire in `src/ingestion/bhavcopy.py` checking `corporate_actions` table in DuckDB and persisting quarantined symbols to `quarantined_stocks`.
  2. Standalone offline script `scripts/sync_shariah_universe.py` ingesting 367 stocks from `fundamentals_cache` and populating `shariah_universe` DuckDB table with verified compliant stocks (>= 350 compliant stocks).
  3. Standalone historical backfill script `scripts/backfill_bhavcopy.py` extending `bhavcopy_daily` to >= 250 distinct trading days.
  4. Unit tests in `tests/test_shariah_sync.py` and `tests/test_corporate_actions.py`.
- **Success criteria**:
  - `shariah_universe` contains >= 350 verified compliant stocks passing all 6 Mufti Taqi Usmani gates (Verified: 367/367 compliant).
  - `bhavcopy_daily` contains >= 250 consecutive trading days (Verified: 252 distinct trading days, 2025-09-16 to 2026-09-29).
  - `>25%` price jump tripwire triggers quarantine for unexplained price discontinuity (Verified: 219 entries quarantined).
  - All tests in `tests/test_shariah_sync.py` and `tests/test_corporate_actions.py` pass 100% (Verified: 10/10 passed).

## Loaded Skills
- **Source**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`
- **Core methodology**: Quantitative trading, market execution, Shariah screening rules, corporate action adjustments, and risk controls.

## Change Tracker
- **Files modified**:
  - `src/ingestion/bhavcopy.py`: Added >25% price jump quarantine tripwire, `quarantined_stocks` table support, helper functions, and pre-fetched corporate action cache.
  - `scripts/sync_shariah_universe.py`: Created offline batch sync script populating `shariah_universe` table with 367 compliant stocks.
  - `scripts/backfill_bhavcopy.py`: Created historical backfill script extending `bhavcopy_daily` to 252 trading days.
  - `tests/test_shariah_sync.py`: Created unit tests covering table columns, >=350 stocks, 6 Taqi Usmani gates, purification ratios, offline execution, and >=250 trading days.
  - `tests/test_corporate_actions.py`: Added unit tests for unexplained jump quarantine, explained corporate action exemption, and normal price movement.
- **Build status**: PASS (10 passed in 8.38s).
- **Pending issues**: None. Task complete.

## Quality Status
- **Build/test result**: 10 passed in 8.38s (100% pass rate).
- **Lint status**: Clean.
- **Tests added/modified**: 6 tests in `test_shariah_sync.py`, 4 tests in `test_corporate_actions.py`.

## Artifact Index
- `.agents/teamwork/teamwork_preview_worker_m5/DISPATCH.md` — Assigned task instructions
- `.agents/teamwork/teamwork_preview_worker_m5/BRIEFING.md` — Situational awareness
- `.agents/teamwork/teamwork_preview_worker_m5/progress.md` — Progress tracker
- `.agents/teamwork/teamwork_preview_worker_m5/handoff.md` — 5-component handoff report

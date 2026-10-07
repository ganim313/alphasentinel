## 2026-10-07T12:13:08Z
You are Worker M5 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m5
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m5
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture and feature inventory:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_3\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `src/ingestion/bhavcopy.py`
- `scripts/sync_shariah_universe.py`
- `scripts/backfill_bhavcopy.py`
- DuckDB tables in `alphasentinel.duckdb` (`shariah_universe`, `bhavcopy_daily`)
- `tests/test_shariah_sync.py`
- `tests/test_corporate_actions.py`

DO NOT modify any files in `src/risk`, `src/portfolio`, or `src/screening`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R5):
1. In `src/ingestion/bhavcopy.py`:
   - Implement the `>25%` price jump quarantine tripwire:
     During Bhavcopy ingestion or validation, calculate daily jump `pct_jump = (close_price - prev_close) / prev_close`.
     If `abs(pct_jump) > 0.25`:
       Check if an approved entry exists in table `corporate_actions` for this symbol on or near this date.
       If unexplained, quarantine the symbol (e.g. record in `quarantined_stocks` table or log warning/quarantine flag), and raise/log alert.
2. Build `scripts/sync_shariah_universe.py`:
   - Standalone offline monthly batch script.
   - Creates DuckDB table `shariah_universe` if not exists:
     `symbol VARCHAR PRIMARY KEY, fyers_symbol VARCHAR, sector VARCHAR, debt_to_assets DOUBLE, cash_to_assets DOUBLE, interest_income_ratio DOUBLE, illiquid_ratio DOUBLE, is_compliant BOOLEAN, purification_ratio DOUBLE, sync_timestamp TIMESTAMPTZ`
   - Ingests all 367 stocks pre-cached in `fundamentals_cache`.
   - Runs each through `check_shariah_compliance()` in `src/screening/shariah_filter.py` across all 6 Mufti Taqi Usmani gates.
   - Calculates `purification_ratio = max(0.0, float(data.get("interest_income_ratio") or 0.0))`.
   - Populates `shariah_universe` with verified compliant stocks (must verify >= 350 compliant stocks; survey proved 367/367 pass!).
   - Runs cleanly standalone offline without blocking the EOD pipeline.
3. Backfill `bhavcopy_daily` in `alphasentinel.duckdb`:
   - Build `scripts/backfill_bhavcopy.py`:
     Extend historical trading days in `bhavcopy_daily` from current 179 days to >= 250 consecutive trading days for stocks (e.g. 2024-2025 historical data via NSE archives or synthetic/clean seed where historical delivery % is skipped per Master Improvement Plan decision Q3).
     Ensure no unadjusted >25% discontinuities enter unquarantined.
   - Run `python scripts/backfill_bhavcopy.py` to ensure `bhavcopy_daily` has >= 250 distinct trading days.
   - Run `python scripts/sync_shariah_universe.py` to populate `shariah_universe`.
4. Implement unit tests in `tests/test_shariah_sync.py` and `tests/test_corporate_actions.py`:
   - Test 1: Verify `shariah_universe` contains >= 350 verified compliant stocks passing all 6 Mufti Taqi Usmani gates.
   - Test 2: Verify `bhavcopy_daily` contains >= 250 consecutive trading days.
   - Test 3: Verify >25% price jump tripwire triggers quarantine for unexplained price discontinuity.
5. Run tests:
   `python -m pytest tests/test_shariah_sync.py tests/test_corporate_actions.py -v`
   Ensure ALL tests pass 100%.
6. Write your complete handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m5\handoff.md` and send message to Orchestrator.

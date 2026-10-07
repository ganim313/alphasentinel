## 2026-10-07T12:13:08Z
You are Worker M3 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m3
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m3
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture and feature inventory:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_2\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `src/screening/regime_engine.py`
- `src/screening/vcp_screener.py` (decoupling live quotes and removing bear bypass ONLY; do not touch residual momentum yet)
- `src/screening/__init__.py`
- `tests/test_regime_engine.py`
- `tests/test_phase4_risk_controls.py` (updating test to assert 0 buy candidates in RISK_OFF)

DO NOT modify any other files in `src/risk`, `src/portfolio`, `src/ingestion`, or `scripts/`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R3):
1. In `src/screening/vcp_screener.py`:
   - Remove live intraday quote fetching from lines 51–59 (`missing_symbols = ... fyers_client.get_live_quotes(missing_symbols)`). Screener runs 100% deterministically from EOD Bhavcopy without intraday network calls.
   - Remove live funds call from lines 81–88 or ensure it defaults cleanly to config capital without broker API calls.
   - Permanently remove the bear-market bypass in lines 244–250 (`if not regime_passed: ... RS_BYPASS_THRESHOLD = 15.0`). When market regime is `RISK_OFF`, screener must produce ZERO buy signals.
   - Remove `regime_bypass_size_reduction` or fix it to `1.0`.
2. Create `src/screening/regime_engine.py`:
   - Implement deterministic 3-point breadth score:
     1. Point 1: Nifty 500 Close > SMA50
     2. Point 2: Nifty 500 SMA50 > SMA200
     3. Point 3: Universe Breadth (% Halal EQ stocks > own SMA50) > 50%
   - Scoring & Regime Map:
     - Score 3 = `RISK_ON` (1.0% risk per trade, allow new entries = True)
     - Score 2 = `NEUTRAL` (0.5% risk per trade, allow new entries = True)
     - Score <= 1 = `RISK_OFF` (0.0% risk per trade, allow new entries = False)
   - Interface:
     `compute_market_regime(conn: duckdb.DuckDBPyConnection, as_of_date: Optional[str] = None) -> RegimeState`
     and helper `get_current_regime()`.
   - Support querying `MONIFTY500` or benchmark data from `bhavcopy_daily` in DuckDB.
   - Fail-closed behavior: if data is missing, insufficient, or benchmark cannot be evaluated, return Score 0 (`RISK_OFF`, 0% risk, allow new entries = False).
3. Update `tests/test_phase4_risk_controls.py`:
   - Update `test_vcp_regime_bypass_allows_high_rs_at_half_size` to `test_vcp_regime_bypass_removed_zero_entries_in_risk_off`: verify that when regime is RISK_OFF (0), `evaluate_minervini_vcp_batch()` returns `[]` regardless of RS score or volume dryup.
4. Implement `tests/test_regime_engine.py`:
   - Test Score 3 (`RISK_ON`): Close > SMA50, SMA50 > SMA200, Breadth > 50%.
   - Test Score 2 (`NEUTRAL`): Close > SMA50, SMA50 < SMA200, Breadth > 50%.
   - Test Score <= 1 (`RISK_OFF`): Close < SMA50 or Breadth <= 50%.
   - Test Fail-Closed: empty DB or missing dates returns RISK_OFF with zero new entries.
5. Run tests:
   `python -m pytest tests/test_layer3_screening.py tests/test_screening_and_anti_trap.py tests/test_phase4_risk_controls.py tests/test_regime_engine.py -v`
   Ensure ALL tests pass 100%.
6. Write your complete handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m3\handoff.md` and send message to Orchestrator.

## 2026-10-07T12:37:05Z
You are Worker M2 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m2
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m2
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture, feature inventory, and interface contracts:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_1\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `src/db/migrations/003_settlement_tracking.sql`
- `src/db/session.py`
- `src/ingestion/fyers_client.py`
- `scripts/fyers_auth.py`
- `src/portfolio/fyers_guardian.py`
- `src/portfolio/__init__.py`
- `tests/test_fyers_guardian.py`

DO NOT modify files in `src/risk`, `src/screening`, or `src/ingestion/bhavcopy.py`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R2):
1. Create `src/db/migrations/003_settlement_tracking.sql`:
   - DDL statements to alter table `positions` in DuckDB adding:
     - `settlement_status VARCHAR DEFAULT 'SETTLING_T0_T1'`
     - `can_exit BOOLEAN DEFAULT FALSE`
     - `gtt_placed BOOLEAN DEFAULT FALSE`
     - `gtt_placed_at TIMESTAMPTZ`
     - `purification_due_inr DOUBLE DEFAULT 0.0`
   - DDL statement creating table `guardian_log`:
     `CREATE TABLE IF NOT EXISTS guardian_log (id VARCHAR PRIMARY KEY, timestamp TIMESTAMPTZ, symbol VARCHAR, action VARCHAR, rule VARCHAR, details JSON, created_at TIMESTAMPTZ);`
   - Update `src/db/session.py:init_db()` to apply these columns and table safely with IF NOT EXISTS checks.
2. Implement `scripts/fyers_auth.py` and extend `src/ingestion/fyers_client.py`:
   - `scripts/fyers_auth.py`: 08:45 IST morning 2FA token refresh script writing access token to `.fyers_token`.
   - `src/ingestion/fyers_client.py`:
     - Implement dynamic `reload_token()` that tracks `.fyers_token` file modification time (`mtime`) and updates the token/model when refreshed.
     - Implement `get_holdings() -> List[Dict[str, Any]]` calling `self.model.holdings()`.
     - Implement `get_positions() -> List[Dict[str, Any]]` calling `self.model.positions()`.
     - Gracefully handle mock/test environments where `fyersModel` or token is mock/simulated.
3. Build `src/portfolio/fyers_guardian.py`:
   - Enforce strict Mufti Taqi Usmani *Bay' qabl al-Qabd* prohibition and FYERS T1 GTT rejection guard:
     - Compute trading days held via `src/utils/holidays.py:is_nse_holiday`.
     - If `trading_days_held < 2` or `holdingType == 'T1'` or `holdingType == 'T0'`:
       Set `settlement_status = 'SETTLING_T0_T1'` and `can_exit = False`.
       Zero sell alerts or GTT orders allowed.
     - On `trading_days_held >= 2` and `holdingType != 'T1'`:
       Set `settlement_status = 'SETTLED_DEMAT'` and `can_exit = True`.
   - On Day 2 morning: generate alert / payload to lodge 365-day FYERS GTT OCO order (`Stop = initial_stop`, `Target = target_2`) and record `gtt_placed = True`.
   - Nightly 19:30 IST audit:
     - Query `fyers_client.get_holdings()`.
     - Reconcile against DuckDB `positions`.
     - Auto-import manual Demat buys (records newly discovered Demat holdings into `positions` with `execution_type = 'MANUAL_IMPORT'`).
     - Evaluate 9-rule priority exit hierarchy (strictly in order P1 to P9, first match triggers):
       1. P1: Hard Stop Breach (`LTP <= trailing_stop_loss` -> EXIT)
       2. P2: 50-SMA Breakdown (`Close < 50 SMA` -> EXIT)
       3. P3: +3.5 ATR Trim (High stretched > 3.5 ATR above 20 EMA on >= 2.5x volume with weak close -> TRIM 50%)
       4. P4: +2R Chandelier Trail (Highest close >= Entry + 2R -> Trail Stop = max(Current Stop, Peak Close - 2.5*ATR))
       5. P5: +1R Breakeven Ratchet (Highest close >= Entry + 1R -> Move Stop = Entry * 1.003)
       6. P6: Distribution Days (>= 4 distribution days in 15 sessions -> Tighten Stop to 5-day Low)
       7. P7: RS Decay (RS Percentile < 50 -> Tighten Stop to 21 EMA)
       8. P8: 20d Time Stop (Days held >= 20 and gain < 1R -> Time Stop EXIT)
       9. P9: Shariah Drift Flag (If held stock fails quarterly sync -> Telegram flag only, zero forced liquidation)
     - Record all state changes, evaluations, and alerts to `guardian_log` in DuckDB.
4. Build `tests/test_fyers_guardian.py`:
   - Unit tests confirming Day 0 and Day 1 evaluate to `can_exit = False`.
   - Day 2 transitions to `SETTLED_DEMAT` and `can_exit = True`, generating GTT OCO alert.
   - Reconciliation with `fyers.holdings()` and manual Demat import.
   - Tests for each rule P1 through P9, especially P9 Shariah drift (flag only, no liquidation).
5. Run tests:
   `python -m pytest tests/test_fyers_guardian.py -v`
   Ensure ALL tests pass 100%.
6. Write your complete handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m2\handoff.md` and send message to Orchestrator.

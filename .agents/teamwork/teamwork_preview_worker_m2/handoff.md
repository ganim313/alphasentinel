# Handoff Report — Requirement R2: T+2 Qabd Settlement State Machine & FYERS Guardian

**Agent**: `teamwork_preview_worker_m2`  
**Working Directory**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m2`  
**Recipient**: Orchestrator (`fe9b6c0a-5651-4bc7-812f-d77697cb2e43`)  
**Mission**: Requirement R2 — T+2 Qabd Settlement State Machine, FYERS Client Extensions & Holdings Guardian  

---

## 1. Observation

1. **Database Schema & Migrations**:
   - `positions` table was missing columns: `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr`.
   - `guardian_log` table did not exist in `alphasentinel.duckdb` or `src/db/schema.sql`.
   - Created `src/db/migrations/003_settlement_tracking.sql` with DDL statements altering table `positions` and creating table `guardian_log`.
   - Updated `src/db/session.py:init_db()` to safely apply these columns and create `guardian_log` with non-destructive `IF NOT EXISTS` column introspection.
   - Verified schema via DuckDB inspection:
     - `positions` contains: `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr`.
     - `guardian_log` exists with columns: `id`, `timestamp`, `symbol`, `action`, `rule`, `details`, `created_at`.

2. **FYERS Authentication & Client**:
   - Created `scripts/fyers_auth.py` supporting 08:45 IST morning token refresh writing access tokens to `.fyers_token`.
   - Extended `src/ingestion/fyers_client.py`:
     - Dynamic `reload_token()` tracks `.fyers_token` modification time (`mtime`) and refreshes `self.access_token` and `self.model`.
     - Added `get_holdings() -> List[Dict[str, Any]]` calling `self.model.holdings()` and filtering active holdings.
     - Added `get_positions() -> List[Dict[str, Any]]` calling `self.model.positions()`.
     - Added `place_gtt_oco_order()` to support 365-day FYERS GTT OCO order lodging.
     - Handled `FyersClient.__new__(cls, *args, **kwargs)` and singleton re-entrancy for test mocks.

3. **Holdings Guardian & Settlement State Machine (`src/portfolio/fyers_guardian.py`)**:
   - Enforced Mufti Taqi Usmani *Bay' qabl al-Qabd* prohibition and FYERS T1 GTT rejection guard:
     - `count_trading_days(start_date, end_date)` uses `src/utils/holidays.py:is_nse_holiday` to skip weekends and official exchange holidays.
     - If `trading_days_held < 2` or `holdingType in ('T1', 'T0')`: `settlement_status = 'SETTLING_T0_T1'` and `can_exit = False`. Zero sell alerts or exit orders allowed.
     - On `trading_days_held >= 2` and `holdingType != 'T1'`: `settlement_status = 'SETTLED_DEMAT'` and `can_exit = True`.
   - On Day 2 morning transition: generates alert and lodges 365-day FYERS GTT OCO order (`Stop = initial_stop`, `Target = target_2`), setting `gtt_placed = True`.
   - Nightly 19:30 IST audit (`reconcile_and_evaluate_holdings`):
     - Reloads FYERS token dynamically.
     - Reconciles broker holdings against DuckDB `positions`.
     - Auto-imports untracked manual Demat buys with `execution_type = 'MANUAL_IMPORT'` and `settlement_status = 'SETTLED_DEMAT'`.
     - Evaluates 9-rule priority exit hierarchy in strict sequential order (P1 to P9):
       1. P1: Hard Stop Breach (`LTP <= trailing_stop_loss` -> EXIT)
       2. P2: 50-SMA Breakdown (`Close < 50 SMA` -> EXIT)
       3. P3: +3.5 ATR Trim (High stretched > 3.5 ATR above 20 EMA -> TRIM 50%)
       4. P4: +2R Chandelier Trail (Highest close >= Entry + 2R -> Trail Stop = max(Current Stop, Peak Close - 2.5*ATR))
       5. P5: +1R Breakeven Ratchet (Highest close >= Entry + 1R -> Move Stop = Entry * 1.003)
       6. P6: Distribution Days (>= 4 distribution days in 15 sessions -> Tighten Stop to 5-day Low)
       7. P7: RS Decay (RS Percentile < 50 -> Tighten Stop to 21 EMA)
       8. P8: 20d Time Stop (Days held >= 20 and gain < 1R -> Time Stop EXIT)
       9. P9: Shariah Drift Flag (Stock fails quarterly sync -> Telegram flag only, ZERO forced liquidation)
     - Logs all events to `guardian_log` in DuckDB.
   - Updated `src/portfolio/__init__.py` to export `SettlementStatus`, `ExitPriorityRule`, and `reconcile_and_evaluate_holdings`.

4. **Test Suite Verification**:
   - Built `tests/test_fyers_guardian.py` containing 23 unit tests across all settlement and exit rules.
   - Test execution results:
     - `pytest tests/test_fyers_guardian.py -v`: 23 passed in 9.87s.
     - `pytest tests/e2e/test_tier1_features.py -k "f3 or f4" -v`: 10 passed in 7.03s.
     - `pytest tests/e2e/test_tier2_boundaries.py -k "f3 or f4" -v`: 11 passed in 7.68s.
     - `pytest tests/e2e/test_tier3_cross_feature.py -k "guardian or fyers" -v`: 2 passed in 3.42s.

---

## 2. Logic Chain

1. **Mufti Taqi Usmani Constructive Possession Invariant**:
   - Under AAOIFI Standard No. 21 and Justice Mufti Muhammad Taqi Usmani's *Fiqh al-Buyu'*, sale of shares prior to constructive legal possession (*Qabd*) is strictly impermissible (*Bay' qabl al-Qabd*).
   - In Indian rolling settlement, shares credit to the client's CDSL Demat account on T+1 night, meaning legal possession is only perfected on the morning of **T+2** (Day 2).
   - Therefore, on Day 0 and Day 1, `settlement_status` must evaluate to `SETTLING_T0_T1` and `can_exit` must be `False`.
   - Any attempt to trigger an exit or lodge a sell alert before Day 2 is blocked.

2. **FYERS T1 GTT Rejection Guard**:
   - FYERS API rejects GTT sell orders on holdings tagged `holdingType == 'T1'`.
   - By locking GTT order placement until Day 2 morning when `holdingType != 'T1'` and `trading_days_held >= 2`, orders are only placed when the exchange and broker accept them.

3. **Settled Demat Import Logic**:
   - Holdings discovered in broker holdings tagged `HLD` were purchased earlier directly through Demat; they are marked `execution_type = 'MANUAL_IMPORT'` and `settlement_status = 'SETTLED_DEMAT'` with `can_exit = True`.

4. **Exit Hierarchy Precedence**:
   - Sequential evaluation ensures capital preservation:
     - P1 (Hard Stop) takes highest priority; if stop is hit, position exits immediately.
     - P2 (50-SMA) guards against macro trend breakdown before trailing stops activate.
     - P3 (Climax Trim) locks in 50% profit when price goes parabolic.
     - P4 & P5 protect open profits via Chandelier trailing and breakeven ratcheting.
     - P6 & P7 tighten stops when market structure deteriorates.
     - P8 exits stagnant positions after 20 days.
     - P9 handles Shariah compliance drift by notifying the investor via Telegram while strictly avoiding forced fire-sale liquidation.

---

## 3. Caveats

1. **FYERS API Rate Limits & Token Expiry**:
   - Live FYERS v3 token requires active 2FA credentials or daily login at 08:45 IST via `scripts/fyers_auth.py`. If credentials expire during market hours, `FyersClient` raises `AuthenticationError` and falls back gracefully.
2. **Historical Bhavcopy Data in Testing**:
   - In offline test environments without live Bhavcopy rows, `evaluate_exit_hierarchy` falls back gracefully to position-level metrics (`current_ltp`, `entry_price`, `trailing_stop_loss`, `atr`).

---

## 4. Conclusion

Requirement R2 is 100% complete and fully verified.
- Migration `003_settlement_tracking.sql` and `src/db/session.py` apply all necessary columns and tables.
- `scripts/fyers_auth.py` and `src/ingestion/fyers_client.py` implement dynamic mtime token reloading, holdings/positions retrieval, and GTT order lodging.
- `src/portfolio/fyers_guardian.py` enforces the T+2 Qabd state machine and executes the 19:30 IST audit with the complete 9-rule exit hierarchy.
- All 23 unit tests in `tests/test_fyers_guardian.py` pass cleanly alongside E2E test suites with zero regressions.

---

## 5. Verification Method

To independently verify this implementation, run:

```powershell
python -m pytest tests/test_fyers_guardian.py -v
python -m pytest tests/e2e/test_tier1_features.py -k "f3 or f4" -v
python -m pytest tests/e2e/test_tier2_boundaries.py -k "f3 or f4" -v
python -m pytest tests/e2e/test_tier3_cross_feature.py -k "guardian or fyers" -v
```

Files to inspect:
- `src/db/migrations/003_settlement_tracking.sql`
- `src/db/session.py`
- `src/ingestion/fyers_client.py`
- `scripts/fyers_auth.py`
- `src/portfolio/fyers_guardian.py`
- `src/portfolio/__init__.py`
- `tests/test_fyers_guardian.py`

# Survey Explorer 1 Handoff Report: R1 & R2 Deep Architectural Survey

**Agent**: `teamwork_preview_explorer_survey_1`  
**Working Directory**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_1`  
**Target Requirements**:  
- **R1**: Phase 1 Bug Fix 1: Volatility-Adjusted Risk Parity Math (`src/risk/arbiter.py` & `src/config/strategy.yaml`)  
- **R2**: Phase 1 Bug Fix 2: T+2 Qabd Settlement State Machine & Holdings Guardian (`src/portfolio/fyers_guardian.py`, `003_settlement_tracking.sql`, DB migration)  

---

## 1. Observation

### 1.1 Current State of Risk Parity Math (R1)
- **`src/config/strategy.yaml` (Lines 20–39)**:
  ```yaml
  risk:
    max_position_size_pct: 10.0
    max_adtv_participation_pct: 1.5
    adtv_participation_caps:
      LARGE: 5.0
      MID: 2.0
      SMALL: 1.0
      MICRO: 0.5
      DEFAULT: 1.5
    stop_loss:
      atr_multiplier: 1.8
      max_pct_drop: 5.5
    profit_targets:
      target_1_rr: 2.0
      target_2_rr: 3.5
    sector_exposure:
      max_open_positions: 3
      max_portfolio_pct: 25.0
    min_conviction_score: 7.0
    daily_drawdown_halt_pct: 3.0
  ```
  - `max_pct_drop` is hardcoded to `5.5%`.
  - `max_position_size_pct` is hardcoded to `10.0%`.
  - Keys `risk_per_trade_pct: 1.0`, `risk_per_trade_neutral_pct: 0.5`, `max_pct_stop: 8.0`, `max_portfolio_heat_pct: 5.0`, `max_open_positions: 6`, `max_positions_per_sector: 2` are **completely missing**.

- **`src/risk/arbiter.py` (Lines 25–36, 143–192)**:
  - Function signature:
    ```python
    def calculate_deterministic_risk_and_position(
        symbol: str,
        trigger_price: float,
        current_price: Optional[float] = None,
        atr_14: float = 0.0,
        circuit_band: float = 20.0,
        macro_weather: Optional[Dict[str, Any]] = None,
        portfolio_capital_rupees: float = 10_00_000.0,
        adtv_20d: float = 0.0,
        sector: str = "",
        market_cap_tier: str = "LARGE"
    ) -> Dict[str, Any]:
    ```
    - Parameter `base_low_10d` is **absent** from the signature.
    - Parameter `regime_risk_pct` is **absent** from the signature.
  - Stop calculation logic (Lines 143–168):
    ```python
    atr_mult = RISK_CONFIG.get("stop_loss", {}).get("atr_multiplier", 1.8)
    max_drop = RISK_CONFIG.get("stop_loss", {}).get("max_pct_drop", 5.5) / 100.0
    atr_stop = round(trigger_price - (atr_mult * atr_14), 2)
    pct_stop = round(trigger_price * (1.0 - max_drop), 2)
    if atr_stop < pct_stop:
        return {
            "symbol": symbol, "verdict": "REJECT",
            "rejection_reason": f"Stock is too volatile. Required ATR stop ({atr_stop}) exceeds max allowed drop ({pct_stop}).", ...
        }
    stop_loss = max(atr_stop, pct_stop)
    ```
    - Rejects any candidate where stop distance exceeds `5.5%`.
    - Does NOT compute `Stop = max(Base_Low_10d - 0.25*ATR_14, Trigger - 2.5*ATR_14)`.
    - Does NOT enforce the `8.0%` maximum stop rejection limit.
  - Sizing and Portfolio Heat logic (Lines 184–192):
    ```python
    max_trade_risk_rupees = portfolio_capital_rupees * (settings.MAX_PORTFOLIO_RISK_PER_TRADE_PCT / 100.0)
    raw_shares = math.floor(max_trade_risk_rupees / risk_per_share)
    max_pos_pct = RISK_CONFIG.get("max_position_size_pct", 10.0) / 100.0
    max_position_value = portfolio_capital_rupees * max_pos_pct
    max_shares_by_value = math.floor(max_position_value / trigger_price)
    ```
    - Position value is hard-capped at 10% of portfolio.
    - Aggregate portfolio heat (sum of open stop risk across all positions $\le 5.0\%$ of core equity) is **completely unmonitored**.

---

### 1.2 Current State of Settlement Logic & Holdings Guardian (R2)
- **`src/portfolio/fyers_guardian.py`**:
  - File does **NOT exist**.
- **`src/execution/compliance.py` (Lines 58–83)**:
  - Only contains `calculate_margin()` based on standard broker margin (80% day 0, 20% T+1).
  - Contains **NO** logic for T+2 Qabd possession, `settlement_status`, `can_exit`, or holdingType checks.
- **`scripts/run_sentinel.py` (Lines 80–165)**:
  - Checks live stop losses intraday via Yahoo Finance every 15 minutes.
  - Does NOT check holding age or settlement status; would execute stop sells on Day 0 or Day 1.
- **`scripts/run_eod_reconciliation.py` (Lines 220–221)**:
  - Line 220: `is_same_day_entry = (entry_date is not None and trade_date is not None and str(entry_date) == str(trade_date))`.
  - Only bypasses stop-loss on Day 0 (`is_same_day_entry`). On Day 1 (`T1`), it allows stop outs and target executions, violating *Bay' qabl al-Qabd* and FYERS T1 GTT rejection limits.
- **`src/ingestion/fyers_client.py` (Lines 1–220)**:
  - Has `get_live_quotes()`, `get_market_depth()`, `fetch_historical_data()`, `get_funds()`, and `is_market_open()`.
  - **Missing**: `reload_token()` (dynamic mtime-based reload of `.fyers_token`).
  - **Missing**: `get_holdings() -> List[Dict]`.
  - **Missing**: `get_positions() -> List[Dict]`.
- **`scripts/fyers_auth.py`**:
  - File does **NOT exist**.

---

### 1.3 Current Database Schema in `alphasentinel.duckdb` & Migrations
- Querying `alphasentinel.duckdb` directly:
  - `SHOW TABLES` returns 20 tables:
    `agent_memory`, `bhavcopy_daily`, `circuit_breaker_state`, `corporate_actions`, `debate_transcripts`, `delisted_stocks`, `equity_curve`, `fundamentals_cache`, `instrument_master`, `macro_weather`, `nse_holiday_cache`, `paper_capital_config`, `paper_portfolios`, `paper_trades`, `positions`, `promoter_pledge_history`, `purification_log`, `runner_archetypes`, `screener_candidates`, `strategy_version`.
  - `DESCRIBE positions` shows:
    `id`, `symbol`, `exchange`, `entry_date`, `entry_price`, `quantity`, `current_ltp`, `unrealized_pnl`, `trailing_stop_loss`, `target_1`, `target_2`, `risk_rupees`, `portfolio_allocation_pct`, `status`, `execution_type`, `exit_date`, `exit_price`, `realized_pnl`, `created_at`, `sector`, `atr`, `peak_high`, `candidate_id`.
  - **Columns missing in `positions`**:
    - `settlement_status` (VARCHAR DEFAULT 'SETTLING_T0')
    - `can_exit` (BOOLEAN DEFAULT FALSE)
    - `gtt_placed` (BOOLEAN DEFAULT FALSE)
    - `gtt_placed_at` (TIMESTAMPTZ)
    - `purification_due_inr` (DOUBLE DEFAULT 0.0)
  - **Tables missing**:
    - `guardian_log` does NOT exist in `alphasentinel.duckdb` or `src/db/schema.sql`.
    - `shariah_universe` does NOT exist in `alphasentinel.duckdb` or `src/db/schema.sql`.
- **`003_settlement_tracking.sql`**:
  - Directory `src/db/migrations/` does **NOT exist**.
  - No migration SQL file exists anywhere in the repository.

---

### 1.4 Existing Unit Tests
- Tested via `python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py -v`:
  - 11 tests passed in 7.00s.
- **Specific Hardcoded Assertions in Existing Tests that Conflict with R1 Changes**:
  1. `tests/test_financial_logic_fixes.py:33`:
     `assert res["portfolio_allocation_pct"] <= 12.0`
     If allocation increases up to 16.0% (as required when unchoking 1% risk on a 6.25% stop), this assertion will fail unless updated to `<= 16.0`.
  2. `tests/test_risk_arbiter_and_agents.py:26`:
     `assert result["stop_loss_price"] == 94.6 # 100 - (1.8 * 3) = 94.6`
     `assert result["portfolio_allocation_pct"] <= 12.0`
     If the stop formula is changed unconditionally without keeping fallback for missing `base_low_10d`, the expected stop price changes from 94.6 to 92.5 (100 - 2.5*3).
- **Tests Currently Missing**:
  - Zero tests for T+2 Qabd settlement state lock (`can_exit = False` on Day 0 and Day 1).
  - Zero tests for FYERS holdingType T1 handling.
  - Zero tests for 9-rule priority exit hierarchy (P1 to P9).
  - Zero tests for GTT OCO alert prompt on Day 2 morning.
  - Zero tests for unchoked 1% risk sizing on 6–8% base stops (`test_risk_parity_unchoked`).
  - Zero tests for portfolio heat cap ($\le 5.0\%$).

---

## 2. Logic Chain

1. **R1 Risk Math Contradiction**:
   - *Premise 1*: Sizing risk in rupees is calculated as $\text{raw\_shares} = \lfloor \frac{\text{Core Equity} \times \text{Risk \%}}{\text{Trigger} - \text{Stop}} \rfloor$.
   - *Premise 2*: Total position value is capped by $\text{max\_position\_size\_pct} \times \text{Core Equity}$.
   - *Premise 3*: In `strategy.yaml`, `max_pct_drop: 5.5%` and `max_position_size_pct: 10.0%`.
   - *Deduction*: The maximum dollar risk that could ever be taken is $10.0\% \times 5.5\% = 0.55\%$ of Core Equity. Any attempt to allocate institutional $1.0\%$ or $1.5\%$ portfolio risk per trade is mathematically throttled by the $10\%$ notional cap and $5.5\%$ drop rejection.
   - *Resolution*: Increasing `max_position_size_pct` to `16.0%` and `max_pct_stop` to `8.0%` allows a $1.0\%$ risk budget to bind naturally: $\frac{1.0\%}{6.25\%} = 16.0\%$ notional allocation.

2. **R1 Structural Stop Formula Alignment**:
   - VCP bases in Indian cash equities routinely form structural cheat pivots with support at the 10-day base low minus volatility buffer: $\text{Stop} = \max(\text{Base\_Low}_{10\text{d}} - 0.25\times\text{ATR}_{14}, \text{Trigger} - 2.5\times\text{ATR}_{14})$.
   - The current code uses $\text{Trigger} - 1.8\times\text{ATR}_{14}$, which is an arbitrary tight drop that gets stopped out by normal intraday noise.
   - Rejection condition must strictly be: $\text{Stop Distance} = \frac{\text{Trigger} - \text{Stop}}{\text{Trigger}} > 0.08$ (8.0%).

3. **R1 Portfolio Heat Ceiling**:
   - Sizing individual trades at 1.0% risk with up to 6 open positions creates potential catastrophic aggregate drawdown if all 6 hit stops simultaneously.
   - A global ceiling of $\text{max\_portfolio\_heat\_pct} = 5.0\%$ guarantees that the sum of open rupee risk across all open positions $\le 5.0\%$ of core equity at all times.

4. **R2 T+2 Qabd Settlement State Machine**:
   - *Shariah Invariant*: Under AAOIFI Standard No. 21 and Justice Mufti Muhammad Taqi Usmani's rulings, shares cannot be sold before constructive legal possession (*Qabd*). In the Indian rolling settlement mechanism, shares credit to the client's CDSL Demat account on T+1 night, meaning constructive possession is only realized on the morning of **T+2** (Day 2).
   - *Microstructure Invariant*: FYERS API rejects GTT sell orders on holdings tagged with `holdingType == 'T1'`.
   - *Deduction*: Day 0 (trade date) and Day 1 (T+1) must enforce `settlement_status = 'SETTLING_T0_T1'` and `can_exit = False`.
   - Only on Day 2 morning (`trading_days_held >= 2` and `holdingType != 'T1'`) does the position transition to `settlement_status = 'SETTLED_DEMAT'` and `can_exit = True`.
   - At this precise moment (Day 2 morning), the Holdings Guardian generates the 365-day FYERS GTT OCO alert (`Stop = initial_stop`, `Target = target_2`).

5. **R2 9-Rule Priority Exit Hierarchy**:
   - Settled positions must be evaluated strictly using the priority queue (first match fires):
     1. **P1 (Hard Stop Breach)**: `LTP <= trailing_stop_loss` $\rightarrow$ `EXIT`
     2. **P2 (50-SMA Breakdown)**: `Close < 50 SMA` $\rightarrow$ `EXIT`
     3. **P3 (+3.5 ATR Climax Extension)**: High stretched $> 3.5\times\text{ATR}_{14}$ above 20 EMA on $\ge 2.5\times$ volume with weak close $\rightarrow$ `TRIM 50%`
     4. **P4 (+2R Chandelier Trail)**: Highest close $\ge \text{Entry} + 2R \rightarrow \text{Trail Stop} = \max(\text{Current Stop}, \text{Peak Close} - 2.5\times\text{ATR}_{14})$
     5. **P5 (+1R Breakeven Ratchet)**: Highest close $\ge \text{Entry} + 1R \rightarrow \text{Move Stop} = \text{Entry} \times 1.003$
     6. **P6 (Distribution Days $\ge 4$)**: $\ge 4$ distribution days in 15 sessions $\rightarrow \text{Tighten Stop to 5-day Low}$
     7. **P7 (RS Decay)**: RS Percentile $< 50 \rightarrow \text{Tighten Stop to 21 EMA}$
     8. **P8 (20d Time Stop)**: Days held $\ge 20$ and gain $< 1R \rightarrow \text{Time Stop EXIT}$
     9. **P9 (Shariah Drift Flag)**: Quarterly compliance ratio breach $\rightarrow \text{Telegram FLAG ONLY}$ (zero forced selling)
   - Every state transition must be logged to `guardian_log` in DuckDB.

---

## 3. Caveats

1. **FYERS API `holdingType` Strings**:
   - In FYERS API v3 responses, unsettled delivery holdings are marked with `holdingType: "T1"` or `holdingType: "T0"`, while settled holdings are marked `"HLD"`. The state machine must handle both explicit FYERS `holdingType` strings and offline date-based calculation (`count_nse_trading_days >= 2`) gracefully.
2. **Backward Compatibility of Existing Tests**:
   - `tests/test_financial_logic_fixes.py` and `tests/test_risk_arbiter_and_agents.py` currently assert `portfolio_allocation_pct <= 12.0` and exact stop price `94.6` based on $1.8 \times \text{ATR}$. Modifying `arbiter.py` will require updating these test assertions or providing backward-compatible defaults when `base_low_10d` is omitted.
3. **DuckDB Migration Execution**:
   - DuckDB does not support some complex DDL alter operations in a single string; all statements in `003_settlement_tracking.sql` must be executed individually or via `session.py:init_db()`.
4. **Offline Trading Days Counter**:
   - Must use `src/utils/holidays.py:is_nse_holiday` to accurately count exchange trading sessions, properly excluding weekends and official exchange holidays.

---

## 4. Conclusion

1. **R1 is clearly scoped and ready for implementation**:
   - Update `src/config/strategy.yaml`:
     - `max_pct_stop: 8.0`
     - `max_position_size_pct: 16.0`
     - `max_portfolio_heat_pct: 5.0`
     - `risk_per_trade_pct: 1.0`
     - `risk_per_trade_neutral_pct: 0.5`
     - `max_open_positions: 6`
     - `max_positions_per_sector: 2`
   - Refactor `src/risk/arbiter.py`:
     - Add `base_low_10d: Optional[float] = None` and `regime_risk_pct: Optional[float] = None` to `calculate_deterministic_risk_and_position`.
     - Implement structural stop: `stop_price = max(base_low_10d - 0.25*atr_14, trigger_price - 2.5*atr_14)` if `base_low_10d` provided, else `trigger_price - 2.5*atr_14`.
     - Reject if `(trigger_price - stop_price) / trigger_price > 0.08`.
     - Enforce `max_portfolio_heat_pct: 5.0` against existing open risk in DuckDB `positions`.
     - Enforce `16.0%` notional cap.

2. **R2 requires creating three critical components**:
   - Create `src/db/migrations/003_settlement_tracking.sql` and update `src/db/session.py:init_db()` to add columns `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr` to `positions`, and create the `guardian_log` table with its sequence.
   - Enhance `src/ingestion/fyers_client.py`:
     - Implement `reload_token()` (checks `.fyers_token` mtime).
     - Implement `get_holdings() -> List[Dict]`.
     - Implement `get_positions() -> List[Dict]`.
   - Build `src/portfolio/fyers_guardian.py`:
     - T+2 Qabd state machine (`count_nse_trading_days`, `SETTLING_T0_T1` vs `SETTLED_DEMAT`, `can_exit`).
     - GTT OCO order prompt generator (365-day validity, Stop=initial_stop, Target=target_2).
     - 19:30 IST audit reconciliation with DuckDB `positions` and auto-import of manual Demat buys.
     - 9-rule priority exit hierarchy (P1 to P9) with `guardian_log` auditing and Telegram alerts.
     - Schedule at 19:30 IST in `scripts/run_scheduler.py`.

3. **Test Suite Requirements**:
   - Create `tests/test_risk_parity_unchoked.py` (or add to `test_arbiter.py`).
   - Create `tests/test_fyers_guardian.py` covering T+2 Qabd lock, Day 2 GTT OCO alert, reconciliation, and all 9 priority rules (P1 to P9).

---

## 5. Verification Method

1. **Verify R1 Risk Math**:
   ```powershell
   python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py -v
   ```
   Add and run:
   ```powershell
   python -m pytest tests/test_guardian.py tests/test_risk_parity.py -v
   ```
2. **Verify DuckDB Migration**:
   ```powershell
   python -c "import duckdb; conn = duckdb.connect('alphasentinel.duckdb', read_only=True); print(conn.execute('DESCRIBE positions').fetchall()); print(conn.execute('DESCRIBE guardian_log').fetchall())"
   ```
   *Expected*: Columns `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr` present in `positions`; table `guardian_log` exists.
3. **Verify Holdings Guardian Dry Run**:
   ```powershell
   python -m src.portfolio.fyers_guardian --dry-run
   ```
   *Expected*: Reconciles DuckDB positions against FYERS holdings, confirms `can_exit = False` for positions held $<2$ days, evaluates 9-rule exit state machine on settled positions without throwing exceptions.

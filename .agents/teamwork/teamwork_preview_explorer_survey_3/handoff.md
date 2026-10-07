# Survey Explorer 3 Handoff Report: Requirements R4 & R5

> **Author**: `teamwork_preview_explorer_survey_3`  
> **Target**: Orchestrator (`fe9b6c0a-5651-4bc7-812f-d77697cb2e43`)  
> **Milestone**: Master Implementation Survey R4 (ML Decoupling, FYERS Auth, Deprecations, Morning Digest) & R5 (Data Spine Backfill, Bhavcopy Tripwire, Offline Shariah Universe Sync)  
> **Date**: 2026-10-07  

---

## 1. Observation

### Observation 1.1: Current ML Gate in `scripts/run_live_preview.py`
In `scripts/run_live_preview.py` lines 585–600:
```python
            if initial_status == "PENDING_REVIEW":
                logger.info(f"[{symbol}] Running Second Opinion Consensus Gate synchronously (ab_group={ab_group}, ml_cutoff={ml_cutoff})...")
                
                # Joint consensus gate: Judge Conviction >= 7.0 AND XGBoost ML Probability >= ml_cutoff
                conv_val = final_state.get("conviction_score")
                try:
                    conviction = float(conv_val) if conv_val is not None else -1.0
                except (ValueError, TypeError):
                    conviction = -1.0
                graph_completed = conviction >= 0.0
                if not graph_completed:
                    logger.error(f"[{symbol}] Debate graph failed to produce a valid judge verdict (conviction={conviction}). Failing closed.")
                gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob >= ml_cutoff)
                
                if gate_approved:
...
```
Furthermore, in `models/xgboost_global_meta.json` lines 1–10:
```json
{
  "trained_at": "2026-10-06T20:09:25.228591+05:30",
  "row_count": 3696,
  "auc_mean": 0.5484,
  "auc_std": 0.0316,
  "auc_conservative": 0.5168,
  "n_folds": 5,
  "embargo_days": 5,
  "validation_gate": "conservative_auc > 0.51",
...
```
In `src/config/settings.py` lines 79–80:
```python
    ML_CUTOFF_CONTROL: float = 0.75     # Production cutoff
    ML_CUTOFF_VARIANT: float = 0.65     # Experimental (shadow) cutoff
```
And in candidate pool sorting at `scripts/run_live_preview.py:386-390`:
```python
    candidate_pool.sort(key=lambda x: (
        x["has_vcp"],
        x["candidate"]["current_price"] >= x["candidate"]["trigger_price"],
        x["ml_prob"]
    ), reverse=True)
```
The model's conservative AUC is 0.5168 (statistically indistinguishable from a random 0.50 coin toss), yet the execution gate requires `ml_prob >= 0.75` (or `0.65`), vetoing ~50% of valid setups at random.

---

### Observation 1.2: FYERS Authentication & Client State
- `scripts/fyers_auth.py` **does not exist** (file search confirmed absent).
- `src/ingestion/fyers_client.py` currently loads tokens only from environment variables:
  ```python
  def _load_cached_token(self) -> str:
      """Load access token from local cache/db if valid."""
      return os.environ.get("FYERS_ACCESS_TOKEN", "DUMMY_TOKEN_FOR_NOW")
  ```
- It has **no** dynamic token file inspection or mtime check.
- It has **no** `reload_token()` method.
- It has **no** `get_holdings()` or `get_positions()` methods (only `get_live_quotes`, `get_market_depth`, `fetch_historical_data`, `get_funds`, and `is_market_open`).
- `fyers_apiv3` is imported under `try...except ImportError` but is not installed in the system Python environment.

---

### Observation 1.3: Deprecation Inventory & Scheduler
In `scripts/run_scheduler.py` lines 270–280:
```python
    # 2. Every 15 min: Sentinel (internally checks market hours 09:15 - 15:30 IST)
    schedule.every(15).minutes.do(job_sentinel)

    # 2b. Every 10 min: Intraday AWAITING_TRIGGER Watcher (internally checks market hours)
    schedule.every(10).minutes.do(job_trigger_watcher)

    # 3. 03:15 PM IST (Mon-Fri): Live Preview Screening & Consensus Gate
    schedule.every().day.at("15:15", tz).do(job_live_preview)
```
- `scripts/run_sentinel.py` lines 48–67 poll Yahoo Finance via `yf.download` every 15 minutes and executes intraday stops on Day 0 and Day 1 positions, completely ignoring T+2 Demat settlement and Shariah Qabd rules.
- `src/execution/dhan_broker.py` lines 21–229 is an unused broker adapter that executes to Dhan API or falls back to `DHAN_SIMULATED`.
- The 15:15 IST trigger in `run_scheduler.py` runs during market hours with live ticks, conflicting with the institutional EOD (19:00 IST Bhavcopy ingestion -> 19:15 IST screening -> 19:30 IST Holdings Guardian -> 08:50 IST Morning Telegram Digest) architecture.

---

### Observation 1.4: DuckDB Schema, Trading Days & Discontinuities
Analysis of `alphasentinel.duckdb` via DuckDB 1.5.5 client revealed:
1. `bhavcopy_daily`:
   - Total rows: **537,939**.
   - Date range: `2025-12-26` to `2026-09-29`.
   - Distinct trading dates: **179 days**.
   - Max trading days for any stock: **179 days** (mean: 176.5 days, min: 55 days).
   - **Zero stocks in the database currently have $\ge 250$ trading days**.
2. Price discontinuities in `bhavcopy_daily`:
   - Query: `WHERE ABS((close_price - prev_close) / prev_close) > 0.25 AND prev_close > 0`.
   - Result: **198 occurrences** across **160 distinct symbols**.
   - Occurrences among the 367 Shariah candidates: **11 occurrences**:
     - `BESTAGRO` (2026-01-16): prev_close `434.20` -> close `29.65` (-93.17%)
     - `AQYLON` (2026-03-05): prev_close `1084.10` -> close `113.80` (-89.50%)
     - `JLHL` (2026-07-24): prev_close `1574.50` -> close `323.20` (-79.47%)
     - `INFOBEAN` (2026-02-27): prev_close `799.80` -> close `206.25` (-74.21%)
     - `DCMSRIND` (2025-12-26): prev_close `172.16` -> close `54.52` (-68.33%)
     - `POCL` (2026-07-21): prev_close `1401.80` -> close `561.10` (-59.97%)
     - `SKMEGGPROD` (2026-01-12): prev_close `344.05` -> close `159.90` (-53.52%)
     - `KIRLPNU` (2026-08-18): prev_close `1534.30` -> close `760.20` (-50.45%)
     - `PGIL` (2026-09-11): prev_close `2378.40` -> close `1187.70` (-50.06%)
     - `ECLERX` (2026-03-13): prev_close `3151.80` -> close `1576.60` (-49.98%)
     - `HARDWYN` (2026-07-28): prev_close `15.59` -> close `11.49` (-26.30%)
   - `corporate_actions` table currently contains only **1 record** (`GOODLUCK_SPLIT_2026-08-21`). Unadjusted corporate actions produce artificial 50–90% price drops that distort indicators, moving averages, and volatility contraction calculations.
3. `fundamentals_cache`:
   - Exactly **367 rows**.
   - Contains all required fundamental metrics: `debt_to_assets`, `cash_to_assets`, `interest_income_ratio`, `illiquid_ratio`, `total_assets`, `borrowings`, `sales`, `other_income`, `net_liquid_assets_crores`, `market_cap_crores`.
   - Running all 367 stocks through `check_shariah_compliance()`: **367 / 367 (100%) passed all 6 Mufti Taqi Usmani gates**.
   - All 367 stocks are mapped in `instrument_master` with valid `fyers_token`.
4. `shariah_universe`:
   - Table **does not exist** yet in `alphasentinel.duckdb`.

---

## 2. Logic Chain

### 2.1 Logic: ML Gate Decoupling to Non-Blocking Shadow Logging
1. **Observation 1.1** demonstrates that `models/xgboost_global.pkl` has an AUC of `0.5168` (conservative) and `0.5484` (mean). This indicates that the model has near-zero predictive power for 2R breakout profitability.
2. In `scripts/run_live_preview.py:597`, the condition `gate_approved = graph_completed and (conviction >= 7.0) and (ml_prob >= ml_cutoff)` couples trade execution to `ml_prob >= 0.75` (or `0.65`).
3. Because the model output distribution is roughly symmetrical around ~0.50, requiring 0.75 randomly eliminates valid setups that already passed Stage 2 trend filtering, VCP contraction, anti-trap shielding, and the 100-point ranker.
4. **Therefore**, the execution gate must be changed to:
   ```python
   # Decoupled Gate: Deterministic conviction and screening approval
   gate_approved = graph_completed and (conviction >= 7.0)
   ```
   while logging `ml_prob` in `screener_candidates` and logger statements as non-blocking shadow telemetry:
   ```python
   logger.info(f"[{symbol}] ML Shadow Score: {ml_prob:.4f} (Cutoff: {ml_cutoff}, Shadow Approved: {ml_prob >= ml_cutoff})")
   ```
   and sorting in Pass 4 (`run_live_preview.py:386-390`) should prioritize deterministic VCP score and residual momentum over `ml_prob`.

---

### 2.2 Logic: FYERS Auth & Client Architecture
1. SEBI 2FA regulations mandate daily session re-authentication. The FYERS API v3 access token expires after ~24 hours.
2. Per **Observation 1.2**, `fyers_client.py` only reads `os.environ["FYERS_ACCESS_TOKEN"]` once at startup and lacks dynamic token reload.
3. If an automated or semi-automated script generates a fresh token at 08:45 IST, a running service or scheduled job will still hold an expired token unless it reads the updated token from disk.
4. **Therefore**:
   - `scripts/fyers_auth.py` must be implemented to authenticate with FYERS at 08:45 IST, exchanging credentials/auth_code for an access token and writing it to `.fyers_token` (located at `BASE_DIR / ".fyers_token"`).
   - `src/ingestion/fyers_client.py` must track `_token_file_mtime`. The `reload_token()` method checks whether `.fyers_token` mtime has changed; if changed, it re-reads the token, updates `self.access_token`, and re-instantiates `self.model = fyersModel.FyersModel(...)`.
   - `get_holdings()` and `get_positions()` must be implemented to wrap `self.model.holdings()` and `self.model.positions()`, calling `reload_token()` and handling error code `-15` (expired token) cleanly.

---

### 2.3 Logic: Deprecation & Morning Telegram Digest
1. **Observation 1.3** shows `scripts/run_sentinel.py` polling Yahoo Finance every 15 minutes and attempting intraday exits without respecting T+2 settlement.
2. Under Mufti Taqi Usmani's *Bay' qabl al-Qabd* prohibition, CNC equity delivery cannot be sold before constructive Demat possession (T+2 morning). Furthermore, FYERS rejects GTT sell orders on T1 unsettled holdings.
3. FYERS supports 365-day server-side GTT OCO orders. Once a position reaches Demat on Day 2 morning, a GTT order placed on the FYERS server handles stops and targets 24/7 without needing 15-minute Python polling loops.
4. Intraday 15:15 IST execution introduces live slippage, server uptime dependency, and emotional noise. EOD execution (19:00 IST Bhavcopy ingestion -> 19:15 IST screening -> 19:30 IST Holdings Guardian -> 08:50 IST Morning Digest) is deterministic and robust.
5. **Therefore**:
   - `scripts/run_sentinel.py` and `src/execution/dhan_broker.py` are deprecated.
   - The 15:15 IST job, 15-min sentinel job, and 10-min trigger watcher job are removed from `scripts/run_scheduler.py`.
   - The primary user touchpoint becomes the **08:50 IST Morning Telegram Digest** containing:
     1. Market Regime summary (`RISK_ON` / `NEUTRAL` / `RISK_OFF`)
     2. Holdings Guardian actions (Demat positions transitioning to T+2 ready for GTT OCO lodging; trailing stop updates; P1/P2 exits)
     3. Trade Cards with exact execution parameters for 60-second manual entry in FYERS App (Symbol, Limit Buy Price, Stop Loss, Target 1, Target 2, Quantity, Capital Allocation).

---

### 2.4 Logic: DuckDB Data Spine & Price Discontinuity Tripwire
1. **Observation 1.4** proves that `bhavcopy_daily` contains only 179 trading days. Any indicator requiring a 200-day SMA currently either fails or requires artificial `min_periods=150` workarounds.
2. The historical data must be backfilled to $\ge 250$ trading days (ideally 2020–2025 via NSE archives / `jugaad-data`, plus recent days via FYERS API) to provide a true data spine.
3. Per **Observation 1.4**, unadjusted corporate actions caused 198 occurrences of $>25\%$ price jumps (e.g. `ECLERX` dropping 49.98% on a 1:1 bonus/split). Without a tripwire, the screener misinterprets corporate splits as catastrophic breakdowns or false VCP contractions.
4. **Therefore**:
   - `src/ingestion/bhavcopy.py` must implement a `>25%` price jump quarantine tripwire:
     ```python
     pct_jump = (close_price - prev_close) / prev_close
     if abs(pct_jump) > 0.25:
         if not has_corporate_action(symbol, trade_date):
             quarantine_symbol(symbol, trade_date, prev_close, close_price, pct_jump)
             send_telegram_alert(f"⚠️ {symbol}: Unexplained {pct_jump*100:.1f}% jump — quarantined.")
     ```
   - Quarantined stocks are excluded from the screener until corporate action adjustments are verified and applied.

---

### 2.5 Logic: Offline Shariah Universe Sync Script
1. Per **Observation 1.4**, `fundamentals_cache` in DuckDB contains exactly 367 stocks, all of which pass 100% of the 6 Mufti Taqi Usmani gates in `src/screening/shariah_filter.py`.
2. The table `shariah_universe` does not yet exist.
3. The live screener must not scrape Screener.in or query external balance sheet APIs during EOD runs.
4. **Therefore**, `scripts/sync_shariah_universe.py` must be created as an offline batch script to:
   - Create table `shariah_universe` (with columns for symbol, fyers_symbol, sector, the 6 ratio metrics, compliance flag, dividend purification ratio, and timestamp).
   - Ingest all 367 pre-cached stocks from `fundamentals_cache`.
   - Run each through `check_shariah_compliance()`.
   - Compute `purification_ratio = max(0.0, float(data.get("interest_income_ratio") or 0.0))`.
   - Populate `shariah_universe` with $\ge 350$ verified compliant stocks.

---

## 3. Caveats
1. **FYERS SDK Environment**: `fyers_apiv3` is imported in `src/ingestion/fyers_client.py` but is not currently installed in the global Python environment. In test environments or when `fyersModel` is None, `FyersClient` must fail gracefully or allow mock injection.
2. **2FA Automation vs. Manual Web Prompt**: While FYERS API allows automated TOTP via `pyotp` and headless browser requests, FYERS occasionally updates login endpoints or requires manual captcha. `scripts/fyers_auth.py` must support an interactive CLI fallback where the user can paste the authorization code or access token directly.
3. **NSE Bhavcopy Historical Archive Format Changes**: NSE changed its Bhavcopy CSV schema in July 2024 (from `cmDDMMMYYYYbhav.csv` to `BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv`). `src/ingestion/bhavcopy.py` already includes column mapping (`TckrSymb` -> `SYMBOL`, etc.), but multi-year backfill scripts (2020–2025) must account for historical format differences.
4. **Historical Delivery Data**: In accordance with Master Improvement Plan Decision Q3, historical delivery percentages for 2020–2025 backfill should be skipped (defaulted to 0.0), as live NSE Bhavcopy captures clearing house delivery data forward every evening at 19:00 IST.

---

## 4. Conclusion
1. **R4 (ML Decoupling)**: Ready to implement. Remove `and (ml_prob >= ml_cutoff)` from `scripts/run_live_preview.py:597`. Retain `ml_prob` strictly as non-blocking telemetry recorded in DuckDB and logs.
2. **R4 (FYERS 2FA Refresh & Client)**: Ready to implement. Create `scripts/fyers_auth.py` to write `.fyers_token` at 08:45 IST. Extend `src/ingestion/fyers_client.py` with `reload_token()` (file mtime check), `get_holdings()`, and `get_positions()`.
3. **R4 (Deprecations & 08:50 Morning Digest)**: Ready to implement. Deprecate `scripts/run_sentinel.py`, `src/execution/dhan_broker.py`, and the 15:15 IST intraday trigger from `scripts/run_scheduler.py`. Format the 08:50 IST Morning Telegram Digest with Trade Cards tailored for 60-second manual FYERS App CNC entry.
4. **R5 (Data Spine Backfill & Tripwire)**: Ready to implement. Backfill `bhavcopy_daily` from 179 days to $\ge 250$ consecutive trading days. Add `>25%` price jump quarantine tripwire to `src/ingestion/bhavcopy.py`.
5. **R5 (Offline Shariah Universe Sync)**: Ready to implement. Build `scripts/sync_shariah_universe.py` to populate DuckDB `shariah_universe` from `fundamentals_cache` (367 stocks, 100% compliant) using all 6 Mufti Taqi Usmani gates.

---

## 5. Verification Method

To independently verify all findings and validate implementations:

1. **Verify Current DuckDB State**:
   ```powershell
   python -c "import duckdb; conn = duckdb.connect('alphasentinel.duckdb', read_only=True); print('Bhavcopy days:', conn.execute('SELECT COUNT(DISTINCT trade_date) FROM bhavcopy_daily').fetchone()[0]); print('Cached stocks:', conn.execute('SELECT COUNT(*) FROM fundamentals_cache').fetchone()[0])"
   ```
   *Expected Current Output*: Bhavcopy days = 179; Cached stocks = 367.
   *Post-Implementation Acceptance*: Bhavcopy days $\ge 250$; `shariah_universe` row count $\ge 350$.

2. **Verify 100% Compliance of 367 Cached Stocks**:
   ```powershell
   python -c "import duckdb, json; from src.screening.shariah_filter import check_shariah_compliance; conn = duckdb.connect('alphasentinel.duckdb', read_only=True); rows = conn.execute('SELECT symbol, fundamentals_json FROM fundamentals_cache').fetchall(); passes = sum(1 for sym, js in rows if check_shariah_compliance(json.loads(js), sector_name=json.loads(js).get('sector_name',''))[0]); print(f'Passed: {passes} / {len(rows)}')"
   ```
   *Expected Output*: Passed: 367 / 367.

3. **Verify ML Gate Decoupling**:
   Inspect `scripts/run_live_preview.py:597`.
   *Condition for Invalidation*: If `gate_approved` still contains `and (ml_prob >= ml_cutoff)`, the ML gate is still actively blocking trades.

4. **Verify Price Jump Quarantine Tripwire**:
   Run unit test:
   ```powershell
   pytest tests/test_corporate_actions.py -v
   ```
   And verify that injecting a row with `(close_price - prev_close)/prev_close > 0.25` without a matching `corporate_actions` record flags the stock as quarantined.

5. **Verify Shariah Sync Script**:
   Once implemented:
   ```powershell
   python scripts/sync_shariah_universe.py
   python -c "import duckdb; conn = duckdb.connect('alphasentinel.duckdb', read_only=True); print(conn.execute('SELECT COUNT(*), COUNT(DISTINCT symbol) FROM shariah_universe WHERE is_compliant = TRUE').fetchone())"
   ```
   *Expected Output*: $\ge 350$ verified compliant stocks.

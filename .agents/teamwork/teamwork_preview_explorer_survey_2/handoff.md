# Handoff Report: Survey of Requirements R3 & R6
**Explorer**: Survey Explorer 2 (`teamwork_preview_explorer_survey_2`)  
**Target Milestone**: Master Implementation — Requirements R3 & R6  
**Parent Orchestrator**: `fe9b6c0a-5651-4bc7-812f-d77697cb2e43`  
**Date**: 2026-10-07T12:15:00Z  

---

## 1. Observation

### 1.1 `src/screening/vcp_screener.py` Live Intraday Quote Fetching & Network Coupling
- **File**: `c:\Users\Md Ganim\Desktop\trading agents\src\screening\vcp_screener.py`
- **Lines 51–59**:
  ```python
  # If live_prices are not fully provided, fetch from Fyers
  missing_symbols = [s for s in symbols if s not in live_prices]
  if missing_symbols:
      try:
          from src.ingestion.fyers_client import fyers_client
          fyers_quotes = fyers_client.get_live_quotes(missing_symbols)
          live_prices.update(fyers_quotes)
      except Exception as e:
          logger.error(f"Failed to fetch Fyers quotes in screener: {e}")
  ```
- **Lines 81–88**:
  ```python
  try:
      from src.ingestion.fyers_client import fyers_client
      from src.config.settings import settings
      base_cap = fyers_client.get_funds() if fyers_client else settings.ALGO_ALLOCATED_CAPITAL
  except Exception:
      base_cap = 1000000.0
  ```
- **Invocation Context** in `scripts/run_live_preview.py:236-238`:
  `vcp_results_list = evaluate_minervini_vcp_batch(liquid_symbols, conn, batch_size=500)` calls the batch screener **without** `live_prices`.
- Consequently, `missing_symbols` contains all liquid universe symbols (300+ stocks). When executed, the screener triggers an external REST API round-trip (`fyers_client.get_live_quotes`) across hundreds of symbols during technical screening.

### 1.2 `src/screening/vcp_screener.py` Bear-Market Bypass
- **File**: `c:\Users\Md Ganim\Desktop\trading agents\src\screening\vcp_screener.py`
- **Lines 244–253**:
  ```python
  if not regime_passed:
      RS_BYPASS_THRESHOLD = 15.0
      if rs_score > RS_BYPASS_THRESHOLD and volume_dryup:
          logger.info(f"[{sym}] Regime BYPASS: RS={rs_score:.1f} > {RS_BYPASS_THRESHOLD} + vol dryup confirmed. Allowing at 50% size.")
          regime_bypass_size_reduction = 0.5
      else:
          continue
  else:
      regime_bypass_size_reduction = 1.0
  ```
- **Existing Test in `tests/test_phase4_risk_controls.py:278-343`**:
  ```python
  def test_vcp_regime_bypass_allows_high_rs_at_half_size():
      ...
      with patch("src.utils.benchmark_provider.get_market_regime", return_value=0):
          with patch("src.utils.benchmark_provider.get_benchmark_returns", return_value=pd.Series([0.0] * 100)):
              res = evaluate_minervini_vcp_batch([sym], conn)
      assert len(res) == 1
      cand = res[0]
      assert cand["rs_score"] > 15.0
      assert cand["volume_dryup"] is True
      assert cand["regime_bypass_size_reduction"] == 0.5
  ```
- This test verifies that even when `get_market_regime()` returns `0` (Risk-Off / Crisis), if `rs_score > 15.0`, a buy candidate is approved.
- In `scripts/run_live_preview.py:499-501`:
  ```python
  bypass_factor = candidate.get("regime_bypass_size_reduction", 1.0)
  if bypass_factor < 1.0:
      cand_macro["target_cash_exposure_pct"] = max(cand_macro.get("target_cash_exposure_pct", 0.0), 50.0)
  ```
  The candidate passes through to the debate graph and execution gate at half size rather than being blocked.

### 1.3 Status of `src/screening/regime_engine.py` & Current Regime Implementation
- `src/screening/regime_engine.py` **does NOT exist**.
- The current regime logic is located in `src/utils/benchmark_provider.py`:
  - `BENCHMARK_SYMBOL = QUANT_ALPHA_CONFIG.get("benchmark_symbol", "^NSEI")` (configured as `^CRSLDX` in `src/config/strategy.yaml:11`).
  - `get_benchmark_ohlc()` downloads data via `yfinance.Ticker(BENCHMARK_SYMBOL).history(period="400d")`.
  - `get_hmm_market_regime()` loads `models/hmm_regime.pkl` (3-state Gaussian HMM: 0=Crisis, 1=Choppy, 2=Calm).
  - `get_market_regime(use_hmm=True)` evaluates `1 if (sma_regime == 1 and hmm_state > 0) else 0`.
- Issues identified in Forensic Audit and Master Improvement Plan:
  1. Relies on external network (`yfinance`) for live EOD runs.
  2. The 1D return Gaussian HMM has near-zero drift separation power in Nifty and can flip states chaotically.
  3. Lacks internal Shariah universe market breadth (% of Halal EQ stocks > their own 50-DMA).

### 1.4 Beta-Stripped Residual Momentum in `src/screening/vcp_screener.py`
- Current Relative Strength implementation in `vcp_screener.py:238-243`:
  ```python
  rs_score = 0.0
  if len(sym_close) >= rs_period and benchmark_rs_data is not None:
      stock_return = (current_price - sym_close.iloc[-rs_period]) / sym_close.iloc[-rs_period]
      rs_score = round((stock_return - benchmark_rs_data) * 100, 2)
  ```
  This is a raw price return difference over 60 days. Because Nifty 500 has ~35% weight in conventional banking/NBFCs (which are prohibited in the Shariah universe), raw relative strength is distorted by banking-led market swings.
- We benchmarked a pure vectorized NumPy matrix OLS calculation of 60-day beta and 30-day cumulative idiosyncratic residual score across $N=400$ stocks on 60 days:
  ```python
  xc = x - x.mean()
  Yc = Y - Y.mean(axis=0)
  var_x = np.sum(xc**2)
  betas = (xc @ Yc) / var_x
  alphas = Y.mean(axis=0) - betas * x.mean()
  residuals = Y - (np.outer(x, betas) + alphas)
  cum_res = np.sum(residuals[-30:, :], axis=0)
  res_std = np.maximum(np.std(residuals, axis=0, ddof=2), 1e-6)
  score = cum_res / res_std
  ranks = pd.Series(score).rank(pct=True) * 100.0
  ```
  **Measured execution time**: **3.55 ms** (well below the <100ms requirement).

### 1.5 Status of LightGBM LambdaRank & Dependencies
- `lightgbm` is **NOT installed** in the active Python 3.13 environment (`ModuleNotFoundError: No module named 'lightgbm'`).
- `lightgbm` is **NOT listed** in `pyproject.toml` dependencies.
- The current ML system uses `models/xgboost_global.pkl` with binary classification (`triple_barrier_label`), trained in `scripts/run_model_training.py`.
- In `models/xgboost_global_meta.json`:
  `auc_mean: 0.5484`, `auc_conservative: 0.5168` (coin flip).
- DuckDB `bhavcopy_daily` currently has **179 distinct trading dates** (Dec 26, 2025 – Sep 29, 2026).
- LambdaRank requires multi-year history (~1,250 query dates $\times$ 10–15 candidate setups = ~18,000 instances) to train reliably. Hence it is designated for **Phase 2**.

---

## 2. Logic Chain

1. **Why remove live quote fetching from `vcp_screener.py`**:
   - `bhavcopy_daily` already contains the official closing price (`close_price`), volume, and delivery % for the session.
   - For an EOD screening job scheduled at 19:15 IST, making intraday REST calls to FYERS for hundreds of tickers introduces network latency, rate limit failures, and token expiration risks.
   - Removing lines 51–59 and defaulting `current_price` to `sym_close.iloc[-1]` makes the screener 100% deterministic, offline-capable, and immune to broker API downtime.

2. **Why permanently eliminate the bear-market bypass**:
   - In Indian Cash Equities (`CNC` delivery only), short selling is prohibited for overnight holds, and intraday exits are locked for 2 days due to T+2 *Bay' qabl al-Qabd* settlement rules.
   - In a declining benchmark market (`RISK_OFF`), over 80% of breakout attempts fail within 2–5 days.
   - Allowing high-RS stocks into positions during a crash traps capital in falling mid/small-caps with zero ability to exit on Day 0 or Day 1.
   - When the market regime is `RISK_OFF`, the system must produce **zero buy signals**. Lines 244–250 must be replaced by a clean rejection/halt.

3. **Why replace HMM with `src/screening/regime_engine.py` (3-Point Breadth Score)**:
   - The HMM model in `benchmark_provider.py` depends on `yfinance`, introduces hidden state transition instability, and does not observe the actual breadth of the Shariah tradeable universe.
   - The 3-point breadth model is fully deterministic:
     - Point 1: `Nifty 500 Close > 50-day SMA` (Primary price trend).
     - Point 2: `Nifty 500 50-day SMA > 200-day SMA` (Trend quality/golden cross regime).
     - Point 3: `Universe Breadth (% Halal EQ stocks > own 50-day SMA) > 50%` (Internal universe health).
   - Scoring & Regime Map:
     - Score 3 = `RISK_ON` (1.0% risk per trade, max 3 new entries/week).
     - Score 2 = `NEUTRAL` (0.5% risk per trade, max 1 new entry/week).
     - Score $\le 1$ = `RISK_OFF` (0% risk, zero new entries allowed).
   - This directly protects capital and regulates portfolio heat deterministically.

4. **Why Beta-Stripped Residual Momentum is mathematically necessary**:
   - The Nifty 500 index contains ~35% weight in conventional banks and NBFCs.
   - Shariah compliance filters out all conventional financial institutions.
   - Therefore, a stock's raw return minus benchmark return is biased: during a banking rally, non-financial momentum stocks look artificially weak; during a banking crash, non-financial stocks appear artificially strong.
   - Decomposing stock returns via OLS against Nifty 500 ($R_{i, t} = \alpha_i + \beta_i R_{m, t} + \epsilon_{i, t}$) isolates the idiosyncratic alpha residual $\epsilon_{i, t}$.
   - The residual momentum score $\frac{\sum_{t=T-29}^T \epsilon_{i, t}}{\text{std}(\epsilon_{i, 1..60})}$ measures pure firm-specific price strength. Requiring $\ge 70\text{th}$ percentile ensures selection of true leaders.

5. **Phasing of Signal Upgrades (Phase 1 vs Phase 2)**:
   - **Phase 1**:
     - Remove bear-market bypass and intraday quote calls from `vcp_screener.py`.
     - Build `src/screening/regime_engine.py`.
     - Remove the 0.51 AUC XGBoost gate from live execution in `scripts/run_live_preview.py:597`.
     - Implement Beta-Stripped Residual Momentum in `vcp_screener.py` requiring $\ge 70\text{th}$ percentile.
   - **Phase 2**:
     - Add `lightgbm` to `pyproject.toml`.
     - Once Bhavcopy is backfilled to $\ge 1,250$ trading days (R5), build `scripts/train_lambdarank.py` grouping by `trade_date`, labeling forward 5-day return deciles, and optimizing NDCG@3.
     - Deploy `models/lgbm_lambdarank.pkl` to rank candidates cross-sectionally and output the Top 3 setups each evening.

---

## 3. Caveats

1. **Benchmark Ticker in DuckDB**:
   - `bhavcopy_daily` currently holds equity stocks (including `MONIFTY500` - Motilal Oswal Nifty 500 ETF, with 179 rows). It does not currently store a separate `NIFTY500` index row.
   - When calculating Point 1 and Point 2 in `regime_engine.py`, the engine can query `MONIFTY500` directly from `bhavcopy_daily` (which trades on NSE EQ and mirrors Nifty 500 1:1), or use benchmark data populated by the ingestion pipeline.
2. **History Length for 200-SMA in Regime Engine**:
   - DuckDB currently has 179 trading days. A 200-SMA requires $\ge 200$ trading days.
   - Until R5 historical backfill is executed (target $\ge 250$ trading days), Point 2 (`SMA50 > SMA200`) will fail closed unless evaluated on backfilled data or using available history with a documented fallback during initial bootstrap.
3. **Existing Test Invalidation**:
   - `tests/test_phase4_risk_controls.py::test_vcp_regime_bypass_allows_high_rs_at_half_size` is explicitly designed to test that the bypass works. Removing lines 244–250 from `vcp_screener.py` will cause this test to fail. The test must be rewritten to assert that zero candidates are returned when the regime is Risk-Off.
4. **LightGBM Wheel Availability on Python 3.13**:
   - The environment is running Python 3.13.5 on Windows. Ensure `pip install lightgbm` installs cleanly or pre-compiled wheels exist for Python 3.13 on win_amd64 before Phase 2.

---

## 4. Conclusion

1. **R3 Deliverables**:
   - **`src/screening/vcp_screener.py`**:
     - Delete lines 51–59 (Fyers live quote fetching).
     - Delete lines 244–250 (bear-market bypass). If `regime_passed` is `False`, the screener must immediately halt and return `[]`.
     - Remove `regime_bypass_size_reduction` or fix it to `1.0`.
   - **`src/screening/regime_engine.py` (New Module)**:
     - Implement `compute_market_regime(benchmark_df, universe_df)` and `get_current_regime(conn, as_of_date)`.
     - Implement the 3-point breadth score with strict fail-closed defaults.
     - Return structured `RegimeState` (Score 3 = `RISK_ON`, 1.0% risk; Score 2 = `NEUTRAL`, 0.5% risk; Score $\le 1$ = `RISK_OFF`, 0% risk, zero new entries).
     - Export from `src/screening/__init__.py`.

2. **R6 Deliverables**:
   - **Beta-Stripped Residual Momentum in `src/screening/vcp_screener.py`**:
     - Add vectorized `compute_beta_stripped_residual_momentum()` using NumPy matrix algebra (<5ms).
     - Compute cross-sectional idiosyncratic residual score over 60-day OLS / 30-day sum.
     - Gate: Candidate must rank in $\ge 70\text{th}$ percentile of the active Halal universe.
   - **LightGBM LambdaRank (Phase 2)**:
     - Add `lightgbm` dependency.
     - Design training script `scripts/train_lambdarank.py` using Purged Group K-Fold cross-validation, forward 5-day deciles, and NDCG@3 optimization.
     - Wire model inference to rank surviving setups and output the Top 3 trade cards.

---

## 5. Verification Method

### 5.1 Unit Tests to Run & Add

1. **Verify Existing Screening & Anti-Trap Tests Pass**:
   ```powershell
   python -m pytest tests/test_layer3_screening.py tests/test_screening_and_anti_trap.py -v
   ```

2. **Verify Bear-Market Bypass Removal**:
   ```powershell
   # After removing lines 244-250 and updating test_phase4_risk_controls.py:
   python -m pytest tests/test_phase4_risk_controls.py -k "test_vcp_regime" -v
   ```
   **Expected**: When `get_market_regime() == 0`, `evaluate_minervini_vcp_batch()` returns `[]` regardless of `rs_score` or `volume_dryup`.

3. **Verify Zero Network Calls in Screener**:
   - Run `evaluate_minervini_vcp_batch()` with `fyers_client.model = None` and network disconnected or socket patched to raise `RuntimeError`.
   - Screener must execute completely using only the DuckDB connection without raising network errors.

4. **Verify `regime_engine.py` 3-Point Scoring**:
   Create `tests/test_regime_engine.py`:
   - Test Score 3 (`RISK_ON`): Benchmark > SMA50, SMA50 > SMA200, 60% of universe > SMA50 $\to$ `score == 3`, `risk == 1.0%`.
   - Test Score 2 (`NEUTRAL`): Benchmark > SMA50, SMA50 < SMA200, 60% of universe > SMA50 $\to$ `score == 2`, `risk == 0.5%`.
   - Test Score 1/0 (`RISK_OFF`): Benchmark < SMA50, SMA50 < SMA200 $\to$ `score <= 1`, `risk == 0.0%`, `allow_new_entries == False`.
   - Test Fail-Closed: Insufficient data or missing benchmark $\to$ `RISK_OFF`.

5. **Verify Beta-Stripped Residual Momentum**:
   - Vectorized benchmark test: 400 stocks $\times$ 60 days must execute in $<100$ms (our benchmark achieved ~3.5ms).
   - Percentile test: Verify that synthetic high-beta banking correlation does not inflate non-banking residual momentum.
   - Threshold test: Verify candidate with residual momentum $< 70\text{th}$ percentile is rejected by VCP screener.

6. **Invalidation Conditions**:
   - If any buy signal is generated when `regime == "RISK_OFF"`.
   - If `vcp_screener.py` attempts a network request to `fyers_quotes` or `get_live_quotes`.
   - If residual momentum calculation takes $>100$ms.

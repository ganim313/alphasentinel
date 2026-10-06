# AlphaSentinel — Independent System Audit

**Audit date:** 6 Oct 2026
**Scope:** full repository snapshot (`repomix-output.xml`, 231 files): `src/`, `scripts/`, `research/`, `dashboard/`, `deployment/`, `tests/`, design docs, and the earlier `Audit/AlphaSentinel_Master_Audit_Report.md`.
**Perspectives applied:** quantitative researcher, risk manager, market-microstructure/execution, Shariah-compliance analyst, ML engineer, backend/SRE/security engineer.

---

## 0. Executive Verdict

> **Not ready to trade real capital. It is also not yet a valid *paper-trading experiment*: the simulator is too optimistic and too buggy for its results to be evidence of anything.**

The architecture is more disciplined than most retail quant systems: deterministic risk arbiter with LLMs given no capital authority, fail-closed kill switch, circuit-band awareness, Shariah screening as a first-class gate, purged cross-validation intent, and a large test suite. Several defects from the earlier audit have also been fixed (see §3).

The problems that remain are about **whether the system has an edge, and whether its measurements can be trusted**:

| # | Headline problem | Consequence |
|---|---|---|
| 1 | The production strategy (Stage-2/VCP + XGBoost + LLM + arbiter) has **never been backtested**. The only backtest uses 10 large-cap stocks (3 are banks, which the system itself would reject as non-Shariah), 2019–2023 data, and *different* algorithms. | No evidence of positive expectancy. |
| 2 | The ML gate (`ml_prob >= 0.75`) is **statistically unreachable** for any realistic model. A simulation with the same hyper-parameters never produced a probability above 0.70, even with AUC 0.57. | Either zero trades are ever approved, or someone lowers the cutoff blindly. |
| 3 | The ML label (2.0 / 1.8 ATR barrier, 5 days) does **not match the traded strategy** (stop 1.8 ATR, T1 3.6 ATR, T2 6.3 ATR, trailing stop). It also trains on the whole NSE universe, but is applied only to pre-screened setups. | The model predicts something other than what the system trades. |
| 4 | The paper simulator is biased upward: entry at trigger rather than live price, **no exit slippage, no brokerage/STT/stamp/GST**, fills on touch, and an **end-of-day look-ahead bug on trailing stops**. | Paper P&L will not survive contact with a real broker. |
| 5 | The **3 % daily-drawdown kill-switch is not wired into production**; the lifetime/CPPI controls are mis-specified. | Risk controls are weaker than documented. |
| 6 | **Corporate-action handling is incomplete and contains an inverted-sign bug** for reverse splits; corrupts both features and labels. | Silent data corruption. |
| 7 | The LLM debate receives almost no real information (earnings-growth, pledge fields are never populated) and its "conviction score" has never been validated against outcomes. | An expensive, unvalidated gate with real veto power. |
| 8 | The Shariah layer **fails open on scrape/parse errors**, is checked only at entry (never re-screened while holding), and the Dhan payload uses `productType: MARGIN` (leverage = interest). | Compliance guarantees are weaker than claimed. |

**Readiness scorecard (0–10, evidence-based):**

| Domain | Score | One-line reason |
|---|:--:|---|
| Architecture / design intent | 7 | Clear tiering; deterministic risk primacy; good separation of concerns |
| Strategy validity (alpha evidence) | 1 | No backtest of the real strategy; no demonstrated edge |
| ML model quality & validation | 2 | Label/strategy mismatch, unreachable gate, weak CV metric, artifact not versioned |
| Data integrity | 3 | Corporate-action gaps, destructive adjustment, unofficial sources, no DQ checks |
| Risk management | 4 | Good ideas; key guards unwired or mis-specified; no portfolio heat limit |
| Execution & paper realism | 3 | Optimistic fills, look-ahead in EOD reconciliation, live path is a stub |
| Shariah compliance | 5 | Strong intent; fail-open parsing, entry-only checks, methodology drift |
| LLM/agent layer | 3 | Little real input, unvalidated scoring, correlated agents |
| Operations / SRE / security | 4 | Single-threaded scheduler, no catch-up, exposed dashboard, unpinned deploys |
| Testing | 5 | Many unit tests; no end-to-end/replay/look-ahead tests |
| **Overall** | **~3.5 / 10** | Promising skeleton; **not trade-ready** |

---

## 1. How this audit was done (and its limits)

**What I did**
- Read the code paths end-to-end: ingestion → universe → liquidity → screeners → anti-trap → ML → LangGraph debate → risk arbiter → order manager → sentinel → EOD reconciliation → portfolio state → drawdown/CPPI/vol-target → scheduler/deploy.
- Cross-checked each documented claim (architecture spec, PRD, `Continuous_Improvement_Loop.md`) against the code.
- Re-verified the findings of the earlier audit against the current code.
- Ran executable checks in a sandbox (see Appendix A): ML probability-range simulation, label-vs-strategy geometry, transaction-cost recomputation, reverse-split multiplier, and part of the test suite.

**What I could not verify**
- `models/` is git-ignored, so **the deployed XGBoost artifact, its metadata and AUC are not in the snapshot**. All ML statements are about code and about what *any* such model can do, not about your specific file. (The earlier audit reported AUC 0.50 on 100 rows; confirm the current file.)
- No live DuckDB, no live market data, no broker/LLM/Telegram connectivity. Behaviour that depends on external services is analysed from code, not observed.
- Test suite: 214 tests. In my sandbox, 4 test modules could not be collected (missing `langgraph`, `moto`), and of the remaining 151 tests, 133 passed, 16 failed, 2 skipped. The failures looked environment-related (missing optional deps, DuckDB lock contention in the sandbox); I did not treat them as defects. **Passing tests are not evidence of correctness here** (see F6): most findings below sit in code that has passing tests.

**Severity scale**
- **P0** — invalidates results or can cause uncontrolled loss; fix before any further paper-trading is counted.
- **P1** — material correctness/risk issue; fix before live capital.
- **P2** — important quality/robustness issue.
- **P3** — hygiene / long-term.

---

## 2. System Understanding

**Purpose.** A personal, $0-budget, autonomous swing-trading assistant for **Shariah-compliant NSE small/mid-caps**. It scans after the open of the last hour, decides, sizes and (in paper mode) "executes" trades, manages stops and targets, logs Shariah purification amounts, and reports via Telegram and a Streamlit dashboard. Capital: ₹10 L paper portfolio; `PAPER_TRADING_MODE` is forced by a settings validator unless `EXECUTION_ENV != PAPER`.

**Intended output.** Per day: 0–3 approved trade cards (entry, stop, T1/T2, size, thesis), intraday stop management, EOD reconciliation, equity curve and risk metrics, purification report.

**Pipeline (as implemented)**

```
06:00 symbol_sync (Fyers master)           08:30 premarket: macro "weather" -> macro_weather table, corporate actions (yfinance splits)
09:15–15:30 every 15 min: sentinel (yfinance 15m bars -> trailing stop / stop-out)
09:15–15:30 every 10 min: trigger watcher (AWAITING_TRIGGER -> buy if 5m high >= trigger)
15:15 run_live_preview (thread, 20 min timeout):
   universe (bhavcopy, last 5 days) -> liquidity (flat ₹25 L ADTV, circuit >=5%)
   -> VCP/Stage-2 batch + mean-reversion batch -> top-15 by heuristic
   -> XGBoost prob (top 15) -> yfinance live tick -> Shariah (Screener.in scrape) -> top-3
   -> per candidate: anti-trap shield -> TradingView rating -> LangGraph:
        [correlation guard + deterministic risk arbiter] -> Bull -> Bear -> Judge -> conviction gate (6.5)
   -> inline "second opinion": conviction >= 7.0 AND ml_prob >= 0.75 (control) / 0.65 (variant)
   -> PaperBroker.place_order (entry at trigger + flat slippage) -> Telegram card
18:30 EOD: bhavcopy ingest -> reconcile stops/targets vs daily OHLC -> purification log -> equity_curve
19:00 drawdown check (lifetime HWM 6% kill switch, monthly 4% warning)
Weekly: evaluator (Sharpe/DSR), feedback loop (win-rate prompt text).  Nightly: DB backup.  Monthly: HMM refit.
```

**Key layers and the files that own them:** ingestion (`src/ingestion/*`), screening (`src/screening/*`), ML (`ml_features.py`, `ml_predictor.py`, `scripts/run_model_training.py`), agents (`src/agents/*`), risk (`src/risk/*`, `src/portfolio/state.py`), execution (`src/execution/order_manager.py`, `scripts/run_sentinel.py`, `run_eod_reconciliation.py`, `run_trigger_watcher.py`), orchestration (`scripts/run_scheduler.py`, `deployment/*`), UI (`dashboard/app.py`, `src/notification/*`).

---

## 3. Status of Earlier-Audit Findings

| Earlier finding | Current state |
|---|---|
| Pre-seeded `conviction_score=7.0` | **Fixed** — now `-1.0`, and the gate fails closed if the graph did not complete |
| Train/serve benchmark skew (synthetic index) | **Largely fixed** — shared `benchmark_provider`; residual skew in `min_periods` (see A4) |
| RSI inconsistency | **Fixed** — canonical `wilders_rsi` (`technical_indicators.py`) |
| VCP used close for 52-week high/low | **Fixed** — uses intraday high/low |
| `symbol_sync` never scheduled | **Fixed** — 06:00 job |
| `AWAITING_TRIGGER` never polled | **Partly fixed** — watcher exists, but see B6 (buys with no re-validation) |
| Macro snapshot unused | **Fixed** — read from DB, live fetch as fallback |
| `evaluate_second_opinion()` orphaned | **Still orphaned**; production uses an inline gate. Its daily-drawdown pre-check therefore never runs (C1) |
| Shield layer 4 (pledge) never fires | **Partly fixed** — a writer exists, but it is fail-open and slow to build history (D5) |
| `delisted_stocks` never written | **Still true** — no writer anywhere in the repo |
| Dhan broker non-functional | **Still true** — even with `LIVE_TRADING_ENABLED=True` it logs "NOT SENT TO API" (B8) |
| Retraining / feedback loop "structural fiction" | **Still true** (E2) |
| Single `^NSEI`-vs-`^CRSLDX` inconsistency | Now centralised, but still depends on unofficial Yahoo data (D3) |

---

## 4. Findings

Each finding lists **Where**, **Weakness**, **Why it matters**, **Fix / better option**.

### A. Strategy & Alpha Validity

#### A1 — No validated edge; the backtest does not test the production strategy · **P0**
**Where:** `research/backtest_harness.py`, `research/algos/*`, `research/data/*.csv`.
**Weakness**
- Universe: 10 mega-caps (RELIANCE, TCS, HDFCBANK, INFY, HINDUNILVR, ICICIBANK, SBIN, BHARTIARTL, ITC, LT) + India VIX. Production trades small/micro caps; 2 of the 10 are banks and ITC is tobacco-linked — all of which `shariah_filter` would reject.
- Data ends **29-Dec-2023** (1 235 rows). Nothing from 2024–2026 (the regime the system will actually trade).
- The "algorithms" are proxies (SMA stack + 20-day breakout; RSI<30; a per-stock XGBoost on 4 features), not the production VCP screener, anti-trap shield, arbiter, ML model, or debate.
- Single 50/50 split. The "walk-forward" mode does **not** retrain per window; the ML algo still trains on the first 50 % of each cumulative slice.
- Cost model understates reality: STT on **delivery trades is charged on both buy and sell** (0.1 % each), but only the sell side is modelled (round-trip cost computed 0.193 %, should be ≈0.29 %; the docstring says 0.13–0.15 %). Costs are also spread as `trades / N_stocks`, so a portfolio fully in one stock pays 1/10 of the true cost. No slippage/impact at all.
- Equal-weight, no stops/targets/position sizing — so the arbiter, ATR stops and trailing logic (the actual P&L drivers) are untested.
- No survivorship control, no benchmark for the *small-cap Shariah* opportunity set.

**Why it matters:** there is no evidence that any component adds value after costs.
**Fix / better option**
1. Build a **point-in-time, event-driven backtester** on your own `bhavcopy_daily` (full universe incl. delisted/suspended names, raw prices + adjustment factors, series/circuit/ASM-GSM flags as they were on each date).
2. Replay the **exact production code path** day by day (screeners → shield → sizing → entry/exit rules), with the same cost+slippage model as the paper broker (§B1).
3. Use **walk-forward with retraining**, ≥ 6–8 years incl. 2018–19 small-cap drawdown, 2020 crash, 2022, and 2024–26.
4. Report net-of-cost **R-multiple expectancy, profit factor, SQN, MAE/MFE, max DD, time-under-water, turnover**, with bootstrap CIs (block bootstrap, since trades cluster in time).
5. Benchmarks: **Nifty Smallcap 250**, **Nifty 500 Shariah**, and a passive Shariah ETF. If the system cannot beat the investable passive alternative net of costs, that is the answer.
6. Ablations: (a) VCP alone, (b) + shield, (c) + ML ranker, (d) + LLM veto. Keep a layer only if it improves out-of-sample expectancy.

#### A2 — The ML gate is statistically unreachable · **P0**
**Where:** `scripts/run_live_preview.py` (`gate_approved = … ml_prob >= ml_cutoff`), `settings.ML_CUTOFF_CONTROL = 0.75`, `ML_CUTOFF_VARIANT = 0.65`; docs say `> 0.50`.
**Weakness:** with 100–150 depth-4 trees at learning-rate 0.03, XGBoost outputs on a noisy financial target stay close to the base rate. In my simulation (same hyper-parameters, 9 features, 45 k training rows; Appendix A.1):

| True signal | Test AUC | P99 prob | Max prob | Share ≥ 0.50 | Share ≥ 0.75 |
|---|---|---|---|---|---|
| none | 0.495 | 0.50 | 0.58 | 0.8 % | **0 %** |
| weak | 0.529 | 0.53 | 0.63 | 4.0 % | **0 %** |
| strong (unrealistic for daily equities) | 0.574 | 0.61 | 0.70 | 23.8 % | **0 %** |

**Why it matters:** the live gate cannot pass in any realistic regime. It will produce permanent "VETOED", and the temptation will be to lower the cutoff by hand (a form of unrecorded parameter tuning). Also, `ml_predictor` returns **0.0 silently** when the model file is missing or features are NaN — indistinguishable from "bearish".
**Fix / better option**
- Treat ML as a **ranker/meta-labeller**, not an absolute-probability gate: use *cross-sectional percentile* of the score (e.g. top 20 % of today's screened candidates) and/or a calibrated **expected R** estimate (isotonic or Platt calibration on out-of-fold predictions; check reliability curve and Brier score).
- Choose the cutoff from the out-of-fold precision/expectancy curve, not from a round number. Store the chosen cutoff + data hash in the model card.
- Return `None`/raise on missing model or NaN features; emit a Telegram alert and mark candidates `ML_UNAVAILABLE`, not `VETOED`.
- Reconcile the three different numbers in docs/settings/code (0.50 / 0.65 / 0.75).

#### A3 — Label does not match the traded strategy; training population ≠ inference population · **P0**
**Where:** `run_model_training.py::triple_barrier_label`, `extract_features_and_labels`; `arbiter.py`, `strategy.yaml`; `run_sentinel.py`.
**Weakness**
- Label: upper barrier = entry + **2.0 ATR**, lower = entry − **1.8 ATR**, horizon **5 bars**, and *timeouts are labelled 1 if the 5th close is even marginally above entry*.
- Trade: stop = 1.8 ATR; **T1 = 2R = 3.6 ATR**, **T2 = 3.5R = 6.3 ATR**, 50 % trim, ATR-trailing runner, **no 5-day time limit**.
- So "win" in training ≈ "didn't lose 1.8 ATR and ended up ≥ 0 within a week", which is not what pays in the live rules. Timeouts above entry by 0.01 % count as wins, adding label noise.
- Training rows = **every EQ symbol on every day** (including illiquid, circuit-locked names); inference rows = only stocks that already passed Stage-2/VCP/liquidity/Shariah. The model's score distribution on the selected subset is therefore uncalibrated.
- Label ATR uses the same bar's close as entry; live entry is at 3:15 PM — minor, but unmodelled.

**Fix / better option — meta-labelling (López de Prado)**
1. Generate training events **only where the production screener fires** (same code, point-in-time).
2. Label each event by **simulating the real exit rules** (stop, T1 trim, trailing runner, costs, slippage, gap fills). Target: realised R-multiple (regression) or `R > 0.5` (classification). Drop the "timeout = sign of close" rule; use fractional R at time-exit.
3. Weight samples by **average uniqueness** (overlapping holding windows) — events within a week are strongly dependent.
4. Evaluate by **per-date cross-sectional rank IC** and top-quintile expectancy, not pooled AUC.

#### A4 — Feature definitions differ between train and serve; some features are dead · **P1**
**Where:** `ml_features.py` vs `run_model_training.py`.
- `sharpe_raw`: training `min_periods=10`, inference `min_periods=40`.
- `dist_high`: training `min_periods=10`, inference `20`.
- `delivery_ratio`: the training SQL and the inference SQL **do not select `delivery_pct`** → constant 0.5 in both → zero information (and the docs claim it is used).
- `sharpe_rank` is a logistic transform of Sharpe, not a rank (contradicts docs/name).
- `market_regime` and `rel_rsi`'s benchmark leg are **identical for every stock on a date**: a tree can use them as a time proxy, inflating pooled AUC with regime effects while adding nothing to stock selection.
- Docs claim DART booster, monotone constraints and "5-day cross-sectional alpha"; code uses default `gbtree`, no constraints, binary triple-barrier label.

**Fix:** one shared feature module imported by both trainer and predictor; unit test `train_features(df) == serve_features(df)` on random slices; replace logistic "rank" with true cross-sectional percentile ranks per date; drop or populate dead features; add monotone constraints if you want to keep claiming them; delete claims that are not implemented.

#### A5 — Validation metric and gate are weak · **P1**
**Where:** `run_model_training.py` (pooled `roc_auc_score`, gate `mean − std > 0.51`), `utils/cv.py`.
- Pooled AUC across all symbols and dates is dominated by *which day it is* (regime features) rather than *which stock is better*.
- Gate 0.51 is within sampling noise for tens of thousands of correlated rows.
- Folds are contiguous blocks but training uses both earlier and later data; purge/embargo is 5 *dates*, matching the label horizon but not the cross-sectional dependence.
- Final model refits on 100 % of data; no hold-out, no champion/challenger test; `run_monthly_retrain.py` (a) is **not scheduled**, (b) gates on "20 labeled trades in `agent_memory`" even though the trainer never reads `agent_memory`.
- Pickle loading of an XGBoost model (`pickle.load`) is version-fragile and unsafe if the file is replaced.

**Fix:** per-date rank-IC (mean IC > 0.02 with t-stat > 2 over 60+ dates), top-minus-bottom decile spread, calibration plots; nested walk-forward (train ≤ T, validate T…T+k, roll), final hold-out of the latest 6 months never used for tuning; champion/challenger promotion rule; save with `Booster.save_model("*.json")`, write a **model card** (data hash, feature-list hash, code commit, metrics, cutoff) and assert it at load time; schedule retraining and make its trigger data-driven (drift/PSI), not trade-count-driven.

#### A6 — "VCP" is a proxy, and the entry logic is contradictory · **P1**
**Where:** `vcp_screener.py`.
- Implemented: Minervini trend template + `vol_5d < 0.85 × vol_20d` + `σ_10d < 0.75 × σ_30d`. Not implemented: successive contractions with decreasing depth (T1 > T2 > T3), minimum base length, tight-closes/range-contraction measure, RS **percentile** vs the universe (code uses 60-day excess return vs index), earnings/sales acceleration, and **breakout volume confirmation** (Minervini/O'Neil require volume expansion ≥ ~40–50 % over average on the pivot day).
- The system requires *dry-up before* the signal and then buys on the trigger **without any intraday volume confirmation** — it cannot tell a real breakout from a drift through the pivot.
- Pivot = max **close** of last 20 days; the 52-week check uses intraday highs — two different pivot concepts.
- Regime bypass (`RS > 15` in a down-market) buys at "50 % size", but the size reduction is implemented by *forcing target cash exposure ≥ 50 %* in the macro dict — a roundabout, untested side effect.

**Fix:** implement pivots from swing highs/lows (zig-zag or ATR-based), measure contraction depth sequence, require breakout-day relative volume (RVOL ≥ 1.4 at 3:15 PM adjusted for time-of-day curve) and close-in-upper-range; use RS percentile (e.g. ≥ 80) over 3/6/12-month blends; keep the 20-day close pivot only if it beats swing-based pivots in the A1 backtest.

#### A7 — Candidate ranking and Shariah ordering distort selection · **P2**
**Where:** `run_live_preview.py`.
- `raw_candidates` are re-sorted by `(has_vcp, price≥trigger, price/trigger, ADTV)`, discarding the screener's own `rs_score` ordering, then **truncated to 15 before** the Shariah filter. If the top 15 are non-compliant, **no trade is possible that day**, regardless of better compliant names ranked 16–40.
**Fix:** pre-compute a **Shariah-compliant universe** nightly/weekly (compliance changes slowly, quarterly), intersect it *first*, rank by a documented score (RS percentile × ML rank × liquidity), then take the top N.

#### A8 — Mean-reversion sleeve is unvalidated and mismatched · **P2**
RSI(14) < 30 and close > 200-DMA: no regime gate, no time stop, no volume/earnings check, exits are the VCP stop/targets whereas the harness tests "exit when RSI>70 or close>SMA20". `trigger_price = current_price` makes the breakout test trivially true.
**Fix:** either drop it until validated or run it as a separate sleeve with its own exits (time stop 5–7 days, target = mean), risk budget and ablation.

#### A9 — Regime/macro layer is crude and fails open · **P2**
**Where:** `macro_feeds.py`, `benchmark_provider.py`.
- Each yfinance leg has its own `try/except` that substitutes benign defaults (VIX 16.5, 0 % change). A partial outage therefore yields `BULLISH_FAVORABLE` / 0 % cash. Only a *total* failure falls back to defensive.
- Uses **US VIX** and S&P/crude/USDINR; the spec promised India VIX, GIFT Nifty and FII flows — not implemented. Thresholds are hand-set constants.
- Binary SMA-50 regime; the HMM exists (`get_hmm_market_regime`) but `use_hmm` is never set to True anywhere, and the HMM is 1-D on index returns (no volatility/breadth), refit monthly with full-sample Viterbi.
**Fix:** fail closed per-leg (missing leg ⇒ penalty or cached-last-good with staleness limit); add India VIX, market breadth (% of Nifty 500 above 50/200 DMA, new highs–lows), small-cap vs large-cap relative strength, FII/DII net flows (NSE daily). Convert regime to a **continuous risk scalar** (e.g. breadth-and-vol composite) and validate in the A1 backtest before using it.

---

### B. Execution & Paper-Trading Realism

#### B1 — Fill model is optimistic and internally inconsistent · **P0**
**Where:** `order_manager.py`, `run_live_preview.py`, `run_sentinel.py`, `run_eod_reconciliation.py`.
- Entry: `execute_paper_trade(price=candidate["trigger_price"])`. If the stock is already 3 % above trigger at 3:15 PM, the paper fill is still at *trigger + flat slippage*. Stops/targets are computed from the trigger as well.
- Slippage: flat 0.1 % / 1.0 % / 1.5 % by ADTV bucket (bucket comments are wrong: `500_000_000` is ₹50 Cr), unrelated to order size; separate from the VCP screener's own impact formula. **No exit slippage at all.**
- **No brokerage, STT (0.1 % both sides on delivery), stamp duty, exchange/SEBI charges or GST** in realised P&L.
- Limit "price-chaser" described in docs is not implemented.
- Targets fill whenever the day's high **touches** target (`high_p >= target_1`); stops fill exactly at the stop. Real small-cap limit orders need trade-through, and stop-market orders in thin books slip several percent.
- Cash is not enforced: the arbiter checks only that ≥ 5 % cash remains *before* the trade; it does not clamp the new position to available cash.

**Why it matters:** on a ~5 % risk distance, 1–3 % of unmodelled exit slippage plus ~0.3 % costs is 20–70 % of 1R. Paper expectancy will be materially overstated.
**Fix / better option**
- One shared **execution simulator** used by backtest *and* paper: fills at `max(limit, next-bar VWAP proxy)`, participation-based impact `slip = spread/2 + k·σ_daily·√(Q/ADV)` (k ≈ 0.5–1.0, calibrate), applied on **both** entry and exit, tick-size rounding, circuit-band checks using *today's* band (see B4), full Indian charges (brokerage, STT both sides, stamp on buy, exchange, SEBI, GST, DP charge on sell ≈ ₹13–16 per scrip).
- Assume stops fill at `min(stop, next print) − extra slippage` and targets only on trade-through (high ≥ target + 1 tick) with volume at that price.
- Clamp order size to available cash.

#### B2 — EOD reconciliation has look-ahead on ratcheted stops · **P0**
**Where:** `run_eod_reconciliation.py` Case A; interacts with `run_sentinel.py`.
The sentinel raises `trailing_stop_loss` intraday from peaks. At 18:30 the reconciler compares the **whole day's low** to the **end-of-day (highest) stop**. If a stock dips in the morning (stop was lower), rallies and ratchets the stop to ₹105, the day's morning low of ₹95 satisfies `low <= stop` and the position is recorded as `STOPPED_OUT` at ₹105, although it was never stopped (it is also exited at a price it never traded at relative to sequence).
**Fix:** reconcile in chronological order using **intraday bars** (5/15-min) and the stop in force at each bar; or, at daily resolution, evaluate against the **stop as of the previous close** only, and update the stop after the day's bar. Persist a `stop_history` table. Add a regression test with a V-shaped day.

#### B3 — Sentinel is blind between bars and uses an unofficial feed · **P1**
**Where:** `run_sentinel.py`.
- It reads only `iloc[-1]` of each 15-min series (last, possibly incomplete, bar). A stop breached in an earlier bar since the previous run is missed; new peaks in earlier bars do not ratchet the trail.
- Source is `yfinance` (unofficial, rate-limited, can lag); 3 failed downloads halt the entire system (`set_system_halt_state`) — safe but self-denial of service for a transient outage.
- Stops are *simulated*; in live trading they must be **broker-side orders** (SL-M/GTT/bracket) because a 15-minute polling loop cannot protect against gaps or circuit sequences.
**Fix:** process **all bars since last check**; use a broker/vendor quote feed (Fyers/Kite) with timestamps and staleness check; in live mode place exchange-resident stop orders and reconcile broker state, treat the sentinel as a secondary watchdog.

#### B4 — Circuit-limit checks use stale limits · **P1**
**Where:** `order_manager.py` (`upper_circuit` from the latest stored row), `check_lower_circuit_trap`.
The stored `upper_circuit` is *that row's own day's* limit (yesterday's close₋₁ × band). Today's limit is `yesterday_close × (1 + band)`. Using the stale value mis-states whether entry/exit is feasible. The band itself is **synthesised** at ingest (`20` if missing, `5` for BE/BZ/SM) rather than taken from NSE's price-band file, so real 2 %/5 %/10 % bands can be recorded as 20 %.
**Fix:** ingest NSE's daily price-band file; compute today's limits from the latest close; treat missing band as *unknown ⇒ reject*, not 20 %.

#### B5 — `MARKED_FOR_CLOSURE` positions become unmanaged "zombies" · **P1**
**Where:** `run_sentinel.py`, `run_eod_reconciliation.py`, `arbiter.py`, `correlation_guard.py`.
Positions are set to `MARKED_FOR_CLOSURE` (lower-circuit lock, or EOD "risk ≤ −5 %") and **nothing in code ever closes them**. The sentinel only selects `OPEN/TARGET_1_TRIMMED`, so they are no longer monitored, and the arbiter/sector cap/correlation guard exclude them, yet `portfolio/state.py` still counts their unrealised P&L in equity. Exposure is hidden from the very controls that should see it.
**Fix:** treat it as an *exit-pending* state that is monitored every cycle, counted in exposure/sector/correlation, and closed by an explicit exit routine with its own slippage model; alert if pending > 1 day.

#### B6 — Trigger watcher buys without re-validation · **P1**
**Where:** `run_trigger_watcher.py`.
`AWAITING_TRIGGER` candidates (approved at 3:15 PM) can fire for up to **5 days later**: it checks only that a 5-minute **high** since creation touched the trigger, then buys at the *current* price — even if the stock spiked and has since fallen back below the trigger. It does not re-run the anti-trap shield, Shariah status, regime, ML score or debate; it uses the **latest macro row of any date**; sizing is done at the trigger price but the fill is at the current price; and it runs inline in the scheduler thread with no timeout.
**Fix:** require `last >= trigger` *now* and a time/volume confirmation; expire candidates after 1 session (or re-score); re-run cheap checks (halt, regime, shield, Shariah flag, liquidity); size at the actual fill price; run in its own process with a timeout.

#### B7 — Decision latency versus the 15:30 close · **P1**
**Where:** `run_live_preview.py`, `run_scheduler.py`.
Starts 15:15. Serial Screener.in scraping (1–3.5 s sleeps ×15), TradingView, up to 3 candidates × 3 LLM calls each with a 15 s timeout and a 3-model waterfall, then order placement; the thread allows 20 minutes. There is **no "market still open"/deadline check before placing the order**, and live ticks come from a single `yf.download(period="1d")` call.
**Fix:** do heavy work **before** the open or the previous evening (screen on EOD data, Shariah, fundamentals, LLM thesis for the next-day watchlist). At 15:10–15:20 only: refresh price/volume, confirm trigger + RVOL, re-run deterministic gates, place order. Hard deadline 15:20; skip if breached.

#### B8 — Live execution path is a stub and would be non-compliant · **P1**
**Where:** `order_manager.py::DhanBroker`.
- Even with `LIVE_TRADING_ENABLED=True` the code logs `DHAN ORDER SIMULATION (NOT SENT TO API)` and calls `PaperBroker`. No HTTP call, no auth, no order-status polling, no partial-fill/rejection handling, no idempotency key, no broker-position reconciliation, no T+1/settlement handling (the `calculate_margin` 80/20 rule is invented).
- Payload uses `productType: "MARGIN"` and `boProfitValue/boStopLossValue` — a margin/bracket product. For a Shariah swing portfolio it must be **CNC (delivery), no MTF, no leverage, no shorting, no derivatives**, since margin funding carries interest.
- `fyers_client` token is read from an env var `FYERS_ACCESS_TOKEN` defaulting to `"DUMMY_TOKEN_FOR_NOW"`; there is no OAuth refresh flow (tokens expire daily).
**Fix:** build a proper `BrokerAdapter` interface (place/modify/cancel/status/positions/funds), an **order state machine** (NEW → ACK → PARTIAL → FILLED/REJECTED/CANCELLED), client-order-ids for idempotency, startup + intraday **broker↔DB reconciliation**, daily token refresh job, hard `product=CNC` assertion, a max-order-value and max-orders-per-day circuit-breaker, and a 4-week **live-shadow** stage (orders generated and compared with the broker's LTP but not sent) before any real order.

---

### C. Risk Management

#### C1 — The daily 3 % kill-switch is not in the production path, and its logic is flawed · **P0**
**Where:** `daily_drawdown_guard.py`, `second_opinion_gate.py`, `run_live_preview.py`, `run_eod_reconciliation.py`.
- `is_daily_drawdown_breached` is called only from `evaluate_second_opinion()`, which has **zero production callers**; `run_live_preview` implements its own inline gate without it.
- Even if called: the "day-open equity" is read from `equity_curve.core_equity` for *today*, but today's row is written at 18:30 (after the 3:15 run) and stores **realised-only equity** (`core_eq − unrealized`), while the current-equity side adds the **cumulative** unrealised P&L of all open positions (not today's change). It also fails open on any error.
**Fix:** snapshot true day-open mark-to-market equity at 09:10; compute live equity from current prices each sentinel cycle; wire the check into (a) the order gate, (b) the trigger watcher, (c) sentinel (switch to exit-only/de-risk mode). Persist breaches in a table. Test with a synthetic −3 % day.

#### C2 — No portfolio-level heat limit; sizing parameters conflict · **P1**
**Where:** `arbiter.py`, `strategy.yaml`, `settings.py`.
- Controls are per-trade and per-sector (≤ 3 open per Screener sector, ≤ 25 % capital). There is **no global max position count, total open-risk ("heat") cap, or beta/cluster exposure cap**.
- Risk budget `MAX_PORTFOLIO_RISK_PER_TRADE_PCT = 1.5 %` is almost never binding: with a 5.5 % max stop, 1.5 % / 5.5 % ≈ 27 % position, but the **10 % position cap** binds first → actual risk ≈ 0.3–0.55 % of equity per trade. Together with a 5 % cash floor, up to ~9–10 positions can coexist; combined open risk is unmanaged.
- ADTV participation caps (LARGE 5 %, MID 2 %, SMALL 1 %, MICRO 0.5 %) × the ADTV floors (₹5 Cr / 1.5 Cr / 50 L / 25 L) give maximum positions of roughly ₹25 L / ₹3 L / ₹50 k / **₹12.5 k**. For SMALL/MICRO that is 1–5 % of a ₹10 L book: too small to matter, while the liquidity guard's own tier floors are never applied in production (the live pipeline hard-codes a flat ₹25 L ADTV floor; `check_liquidity_and_executability` is imported but never called).
- Cash is not clamped (B1). Gap risk is not in sizing (C7).

**Fix / better option:** state the risk policy explicitly and implement it as a single function: (1) target **risk per trade** (e.g. 0.5–0.75 % of equity), (2) **portfolio heat** ≤ 4–6 % of equity (sum of stop-distance × shares), (3) max 6–8 positions, (4) per-cluster cap using correlation clusters rather than Screener sector labels, (5) size = min(risk-based, % cap, liquidity-based "days to exit" cap), where liquidity cap is "can exit 100 % within 1–2 sessions at ≤ 10 % of ADV *in the stop-out scenario*". Align the ADTV floors with the capital you actually deploy; if the strategy is only feasible in LARGE/MID names, say so.

#### C3 — CPPI is mis-implemented; lifetime 6 % kill-switch is a one-way door · **P1**
**Where:** `risk/cppi.py`, `run_drawdown_check.py`, `settings.py`.
- `CPPI_MULTIPLIER = 3.0` is defined but **never used**. The code computes `exposure = cushion / (HWM × 6 %)`, a linear de-risking ramp, not CPPI (`exposure = m × cushion / equity`).
- The kill-switch halts at **6 % drawdown from the lifetime HWM**, the same level at which CPPI reaches 0. For a stop-based small-cap momentum book, drawdowns of 6 % are within *normal* variability (a handful of correlated stop-outs); expect the system to halt itself early and repeatedly. After a halt the HWM remains, so on resume CPPI keeps exposure at 0 until equity recovers — which cannot happen while flat.
- HWM and monthly peak are updated once a day at 19:00 (EOD), so intraday peaks/troughs are missed.
**Fix:** tiered de-risking, e.g. DD 4 % → size ×0.5, 7 % → ×0.25 and no new names, 10 % → halt + mandatory review; time-based or equity-recovery-based **re-entry rule**; calibrate thresholds from the backtest distribution of drawdowns (e.g. 95th-percentile expected max DD) instead of picking round numbers; track HWM on MTM intraday.

#### C4 — Correlation guard and vol targeting are weak · **P2**
- `correlation_guard`: average Pearson correlation to open positions on ≤ 60 daily returns (overlap often < 60 after `dropna`), threshold 0.65, **fails open on any error**; average correlation hides one very-high-correlation holding.
- `vol_target`: needs ≥ 2 assets, sample covariance on 60 days (noisy, rank-deficient for >~8 names), fails open to scalar 1.0; target 15 % annualised is lower than the stock-level vol of typical small caps (40–60 %), so it will constantly bind once ≥ 2 names exist, in an unvalidated way.
**Fix:** use **max** and **marginal-risk-contribution** correlation checks, Ledoit-Wolf shrinkage covariance or a factor model (market, size, momentum, sector), EWMA vol; fail **closed** (or reduce size by 50 %) when data is missing.

#### C5 — Stop/target design is untested and filters out the leaders · **P2**
`atr_multiplier = 1.8` with `max_pct_drop = 5.5 %` **rejects** any stock whose 1.8 ATR stop exceeds 5.5 % (ATR% > 3.05 %). Many true small-cap leaders have ATR% of 3–6 %; the filter selects low-volatility names. The trailing stop (1.8 ATR below the running peak) is tight for Stage-2 shakeouts, and T1 at 2R with a 50 % trim and breakeven+0.5 % ratchet caps the right tail that pays for the strategy.
**Fix:** sweep stop (1.5–3.0 ATR), trail (2–4 ATR or 10/21-EMA close-based), time-stop, T1/T2 in the A1 backtest with nested walk-forward; count **every** configuration tried in the DSR trial count (§H1).

#### C6 — Gap/overnight risk is not part of sizing · **P2**
Small-cap names can gap through stops by the full circuit band (5–20 %). Sizing assumes the stop is honoured. Use **gap-adjusted risk** = max(stop distance, empirical 95–99 % overnight loss for that stock/tier) when sizing; stress-test the book against a "−circuit band on every name" scenario.

---

### D. Data Layer

#### D1 — Corporate actions are incomplete, wrong in one case, and destructive · **P0**
**Where:** `ingestion/corporate_actions.py`, `scripts/run_corporate_actions.py`.
- **Coverage:** only yfinance `splits`, last **14 days**, and only for open positions + last-7-day candidates (or top-50 by turnover). Bonus issues, rights, demergers, scheme-of-arrangement and any split in a non-focus symbol are **never adjusted**, yet the VCP screener, 252-day high, SMA-200, ATR and **all ML training labels** run on the full history. A bonus 1:1 shows as a fake −50 % crash → corrupts features and triggers lower-barrier labels.
- **Bug (verified, Appendix A.4):** `record_corporate_action` for `SPLIT` computes `min(from,to)/max(from,to)`. yfinance reports reverse splits as factors < 1 (e.g. 0.1). The script passes `ratio_from=1, ratio_to=0.1` → multiplier **0.1**, i.e. history is scaled **down 10×** instead of **up 10×** (a 100× error). Forward splits are correct.
- **Destructive:** `UPDATE bhavcopy_daily SET close_price = close_price × m …` overwrites raw data irreversibly; there is no raw/adjusted separation or audit trail; position `atr` and `risk_rupees` are not adjusted when `quantity`, entry and stop are.
**Fix / better option**
- **Detect from data, for free:** bhavcopy gives `PREVCLOSE` which the exchange has already adjusted for corporate actions. If `close[t−1] / prev_close[t]` deviates from 1 beyond tick noise, the ratio *is* the adjustment factor. Cross-check with NSE's corporate-actions feed.
- Keep **raw prices immutable** + a `adjustment_factors(symbol, ex_date, factor, source)` table; compute adjusted series at read time (`adj = raw × cumulative_factor_after_date`). Reversible, auditable, testable.
- Run for the **entire** universe, daily, and alarm on any unexplained |return| > band or > 25 % without an action record.
- Also adjust position-level fields (ATR, risk_rupees, peak) consistently.

#### D2 — Bhavcopy ingestion has silent-failure modes and no data-quality gate · **P1**
**Where:** `bhavcopy.py`, `run_eod_reconciliation.py`.
- `INSERT OR IGNORE`: if a partial or preliminary file is ingested at 18:30, later corrected data is **ignored forever**.
- Fyers fallback loops one API call per symbol (2 000+ calls) and fakes `SERIES='EQ'`, no delivery; daily-candle timestamps vs `trade_date` alignment is unchecked.
- No validation: OHLC consistency (`low ≤ open,close ≤ high`), zero/negative prices, volume 0 with price change, duplicate symbols, row-count sanity vs previous day, symbol changes/renames/mergers, stale symbols.
- `delisted_stocks` has **no writer**, so survivorship protection is nominal. Delisted/suspended names remain "active" if they traded within the last 5 days; names that vanish are simply not scanned.
**Fix:** staged ingestion (`raw → validated → published`) with row-count/price-jump/OHLC checks and an `ingest_audit` table; **upsert with version/checksum** rather than ignore; re-pull yesterday's file next morning to catch revisions; maintain a symbol-lifecycle table (rename, suspension, delisting) from NSE masters; block trading and alert when DQ checks fail.

#### D3 — Production decisions depend on unofficial, unlicensed endpoints · **P1**
yfinance is used for the **benchmark/regime (`^CRSLDX`)**, macro, live ticks at the decision time, stop monitoring, splits, and news. Screener.in is scraped (ToS and Cloudflare risk). TradingView-TA uses an unofficial scanner endpoint. Polymarket is polled with a 2 s timeout. None offers an SLA or schema stability, and breakage typically manifests as *missing data* that the code often converts into a default (see D4).
**Fix:** primary = broker/exchange feed (Fyers/Kite/Dhan market-data with documented terms), secondary = secondary vendor; for index history use NSE/niftyindices official downloads; keep yfinance only as a monitored last-resort fallback with **staleness and cross-source divergence checks** (e.g. compare close to bhavcopy within 0.5 %).

#### D4 — Fundamentals scraper is fail-open on parse errors · **P1**
**Where:** `screener_scraper.py`.
- `get_row_last_val` returns **0.0** when a section/row is missing or unparsable. `borrowings = 0` ⇒ debt-to-assets 0 ⇒ "debt-free ⇒ compliant"; `other_income = 0` ⇒ impure income 0. Only `total_assets ≤ 0` is rejected, so a site layout change that breaks *some* rows but not *total assets* produces **false compliance**.
- Hard-fallback dict contains `recent_news_count: 0`, `promoter_pledged_pct: 0`, `pledge_trend_3m: 0` ⇒ anti-trap passes silently.
- P&L "last column" is TTM, balance sheet "last column" is the last fiscal year-end (up to 12 months stale) — mixed periods.
- Cache TTL 7 days regardless of results calendar; `news_count` cached up to 7 days.
- No integrity checks (assets = liabilities + equity, segment sums, market cap = price × shares).
**Fix:** use `None` (never 0.0) for missing fields; make missing ⇒ `UNKNOWN` ⇒ not tradable; add reconciliation checks; prefer **official XBRL results and shareholding-pattern filings (BSE/NSE)** or a licensed data vendor; refresh on **results dates** rather than a fixed TTL; store point-in-time snapshots (with "known-as-of" date) for honest backtests.

#### D5 — Anti-trap shield layers 4 and 6 are weak signals · **P2**
- L6 (FOMO): `yfinance.Ticker.news` returns a fixed-size list (~10) of recent headlines irrespective of age, so `news_count ≥ 3` is almost always true and the rule reduces to "3-day return > 15 %". The count is also served from a ≤ 7-day cache.
- L4 (pledge): history is a daily snapshot of one scraped ratio, labelled `quarter_end_date`; the "3-month trend" is computed vs. a ≥ 30-day-old snapshot and defaults to 0 when none exists ⇒ for a newly scraped symbol the layer passes. Only ~15 symbols/day are ever scraped, so history builds slowly.
- L2B "intraday churning": uses *yesterday's* delivery % against *today's* live volume.
**Fix:** source pledge history from the quarterly shareholding filings (pledge % per quarter, free); use timestamped news with a recency window (or drop L6); make "unknown" ⇒ reject for risk layers; validate each layer's marginal benefit in the A1 backtest (event-study of rejected vs accepted names).

#### D6 — Calendar logic · **P3**
Holiday list is hard-coded for 2026–27 and cannot be verified from the repo; `weekday() ≥ 5` rejects special weekend sessions (Budget day/Muhurat variants). Fetch the exchange holiday/trading-session calendar, reconcile against it, and alert on mismatch.

---

### E. LLM / Agent Layer

#### E1 — The debate has little real information and an unvalidated verdict · **P1**
**Where:** `debate_graph.py`, `llm_gateway.py`, `screener_scraper.py`.
- Prompts reference `profit_growth_pct`, `sales_growth_pct`, and the judge reads `fundamentals['pledged_pct']`, but the scraper **never populates** these keys (it emits `promoter_pledged_pct`; no growth fields). The LLMs therefore see `N/A` for earnings momentum — exactly what the Bull prompt is told to argue about. News headlines are not passed in. The agents are mostly generating plausible prose from priors (hallucination risk), not analysing evidence.
- All three agents use the same model family at temperature 0.2 ⇒ errors are correlated; "adversarial" is nominal.
- The conviction score is parsed by regex from free text, single sample, an unpinned model alias (`gemini/gemini-flash-latest`) so behaviour changes without notice. The 6.5 gate (yaml), 7.0 gate (inline live gate), and 7.0 (docs) disagree.
- When all providers fail, the gateway returns the *same canned sentence* for bull/bear/judge; the judge regex then fails → 5.0 → reject (safe), but the failure is silent in Telegram/metrics.
- No evidence that conviction predicts outcomes; no logging that allows testing it (the `agent_memory` outcome join is contaminated, §E2).
**Fix / better option**
- Feed **structured, verifiable facts**: last 4 quarters' sales/profit growth, margin trend, results-date proximity, bulk/block deals, pledge change, promoter/FII holding change, recent exchange announcements (BSE/NSE feeds), liquidity metrics.
- Make the LLM a **veto-only auditor with a typed JSON schema** (e.g., `{"red_flags":[{"type":"EARNINGS_AT_RISK|GOVERNANCE|LITIGATION|PROMOTER_ACTIVITY|…","evidence":"…","severity":1-3}]}`), validated by Pydantic; reject on any severity-3 flag with evidence. No free-text number.
- **Earn authority**: run it in *shadow* for ≥ 100 decisions, then measure whether LLM-vetoed trades had worse realised R than approved ones (with CIs). If not significant, remove it (saves latency and a failure mode).
- Pin model versions; log prompts/responses/model id/token counts; alert when the deterministic fallback text is used.

#### E2 — The "learning loop" does not learn, and its labels are contaminated · **P2**
**Where:** `run_feedback_loop.py`, `run_eod_reconciliation.py`, `run_monthly_retrain.py`, `Continuous_Improvement_Loop.md`.
- Weekly feedback = "if win-rate < 40 % over ≥ 5 trades, inject a warning". Five trades say nothing statistically (95 % CI on a win rate with n = 5 spans most of 0–100 %), and win-rate is the wrong statistic for a 2R/3.5R strategy (profitable at ~35 % win-rate).
- On a stop-out or target the reconciler runs `UPDATE agent_memory SET outcome_label=… WHERE symbol=? AND outcome_label IS NULL` — this labels **every** unlabeled memory row for that symbol, including debates for days when no trade was taken or the trade was rejected.
- `agent_memory` has `INSERT OR REPLACE` per (symbol, date), `kronos_score` is set equal to conviction (field is a leftover), and the trainer never uses it.
- "RLHF / genetic-programming alpha factory" in the improvement doc is not implemented (and would be high overfitting risk with current data volume).
**Fix:** link outcomes by `candidate_id/position_id`, store the full decision snapshot (features, scores, config hash) at decision time, and compute outcomes by simulation for **all** candidates (taken or not) → this is your *counterfactual dataset* for training the meta-model. Replace win-rate prompts with: rolling expectancy (R), drift monitors (PSI on features, score distribution), and a human-reviewed weekly report. If you want automated feature discovery, do it offline with strict multiple-testing control (DSR/PBO) — never "auto-deploy".

#### E3 — "Shadow mode" is not shadow · **P3**
`SHADOW_MODE=True` routes ~20 % of symbol-days to a *variant* with a different ML cutoff (0.65) that **actually trades**. It is a live canary with no power (a handful of trades), not a shadow evaluation. Log counterfactual decisions without affecting capital, or randomise properly and pre-register the sample size.

---

### F. Engineering, Operations & Security

#### F1 — Persistence design · **P2**
- DuckDB is an analytical, single-writer store used also for transactional state (positions, kill-switch, queue). Every `db_write` opens a connection under a file lock and checkpoints on close; this serialises the scheduler, sentinel, dashboard, watcher and backups and adds latency/lock timeouts (120 s).
- Hand-rolled migrations (`init_db` splits SQL on `;` and runs `ALTER`s) with no versioning; a semicolon inside a comment/string will break the bootstrap.
- `run_nightly_backup.py` copies the DB file; it uses a fixed path rather than `settings.DUCKDB_PATH`.
**Fix:** keep DuckDB/Parquet for **market-data analytics**; move **state** (positions, orders, candidates, halt flag, audit log) to SQLite-WAL or Postgres with proper transactions; adopt Alembic/yoyo migrations; make the kill-switch an atomic row/flag file checked by every process; write backups from a consistent snapshot and **test restores** monthly.

#### F2 — Observability and control plane · **P1**
- Telegram is **outbound only**: the docs/architecture promise `/status /positions /halt /resume`, but there is no command listener (no `getUpdates`/`CommandHandler` anywhere, although `python-telegram-bot` is in `requirements.txt`). The only manual halt is the Streamlit dashboard.
- Dashboard binds `0.0.0.0:8501` over plain HTTP with one shared password compared with `==`, no lockout/rate-limit/2FA, and it can resume/halt the system. (`.env.example` mentions Tailscale, but nothing enforces it.)
- No heartbeat / dead-man's switch: if the scheduler dies at 15:10 the day is silently skipped; there is no "expected job did not run" alert. `keep_alive.py` burns CPU to defeat Oracle's idle-reclamation policy — fragile, possibly against the free-tier terms, and a sign the host has no SLA for a trading process.
**Fix:** authenticated Telegram command handler (allow-list user-id, 2-step confirm for `/resume`), bind dashboard to localhost behind Tailscale/Cloudflare Access with TOTP; add a `job_runs` ledger with **expected-run reconciliation** and an external heartbeat (healthchecks.io-style) that alerts on missing pings; run on a paid small VPS with a real SLA once real money is involved.

#### F3 — Scheduler design · **P2**
Single-threaded `schedule` loop: the trigger watcher and several jobs run **inline**, so a slow job delays the sentinel; there is no catch-up for missed runs after restart; `run_monthly_retrain.py` is not registered at all; the 08:30 job runs two subprocesses serially; the Sunday DB maintenance and backups can overlap with writes. Both the systemd scheduler and a crontab path are documented.
**Fix:** one orchestrator (APScheduler with persistent job store, systemd timers, or Prefect), every job idempotent, with timeouts, retry policy, misfire handling, and a run ledger; pick **one** (systemd *or* cron) and delete the other from docs.

#### F4 — Reproducibility & deployment hygiene · **P2**
- `deploy_update.sh` does `git reset --hard origin/main` on the production host and `pip install -r requirements.txt` (unpinned `>=`), **not** the lock file; dev/test packages (`pytest`, `moto`) ship to prod; no tests, canary, or rollback.
- Model artifacts are git-ignored → no registry, no hash, no way to know which model produced a decision (the earlier audit's "model provenance unknown" persists). Decisions in `screener_candidates` don't store model version/feature hash/config hash.
**Fix:** CI that runs tests + a **replay test** on tagged commits; deploy from tagged releases with the lock file (`pip install --require-hashes` or uv), blue/green or at least `pip check` + smoke test + auto-rollback; add `model_id`, `config_hash`, `code_commit` columns to decision tables.

#### F5 — Configuration drift · **P2**
Thresholds live in 5+ places and disagree:

| Parameter | Places and values |
|---|---|
| ADTV floor | yaml tiers (₹5 Cr/1.5 Cr/50 L/25 L); live pipeline flat ₹25 L; docs ₹50 L |
| Conviction | yaml 6.5; inline gate 7.0; docs 7.0 |
| ML cutoff | docs 0.50; settings 0.75/0.65 |
| Stop ATR | yaml 1.8; hard-coded 1.8 in sentinel and order manager |
| Targets | docs 3R/6R; yaml 2.0R/3.5R; Telegram "2R/3.5R" |
| Max position | yaml 10 %; VCP screener `assumed_capital = equity × 12 %` |
| Market-cap tiers | `settings.get_market_cap_tier` (₹ Cr) vs inline ADTV-bucket fallback |

**Fix:** one typed config object (Pydantic) loaded once, validated at startup (fail fast on contradictions), printed in the daily summary and hashed into every decision record; generate docs from config; delete duplicated constants.

#### F6 — Test strategy gives false confidence · **P3**
214 tests are organised by remediation "phase", mostly mocking collaborators. The defects above (look-ahead in reconciliation, unwired kill-switch, unreachable ML gate, inverted reverse-split, label mismatch) sit under green tests. Missing: a **golden-day replay**, **no-look-ahead property tests** (perturb future bars and assert identical decisions), feature-parity tests, simulation invariants (cash never negative, exposure ≤ cap, stop never lowered), mutation testing for the risk layer, and chaos tests (provider returns empty/NaN/partial).

#### F7 — Repository hygiene · **P3**
`.agency/` playbooks/templates (33 documents), `scratch/`, `Copy of halal stock 2.0.xlsx`, `trading-agents-guide.pdf`, a root `test_duckdb.py`, four IDE rule dialects. Design docs are marked `status: complete` while several specified features (India VIX, FII flow, DART+monotone XGBoost, interactive Telegram, limit price-chaser, 3R/6R targets) are absent. Move governance material out of the production repo and keep one *generated* architecture doc that matches the code.

---

### G. Shariah-Compliance Layer

#### G1 — Methodology must be explicit and consistent · **P1**
The code claims "Usmani fatwa" but mixes standards: debt/**total assets** ≤ 33 % (book-value), impure income ÷ **sales** (not total income), illiquid-asset ≥ 20 %, plus an AAOIFI 49 % receivables test, plus a net-liquid-assets test. Boards differ materially (S&P, Meezan, AAOIFI, MSCI use market-cap-based averages and different thresholds). Decide, document and version **one** standard and its thresholds; apply **the stricter** of book- and market-cap-based debt where your board allows; use total income (revenue + other income) as denominator for impure income, with a documented treatment of dividend and interest income. Have the rule-set reviewed by your Shariah advisor.

#### G2 — Compliance is checked once, at entry · **P1**
`check_shariah_compliance` is called only from `run_live_preview.py` before the debate. A holding whose quarterly results later breach 33 % debt/5 % impure income is **never re-screened**, and the cache (7 days, fixed TTL) can hold a stale pass. The earlier audit flagged the stale cache; the structural gap is larger.
**Fix:** a `compliance_status` table (symbol, as-of date, source filings date, each ratio, verdict, evidence). Re-screen when new results/shareholding are filed; **auto-flag open positions** that turn non-compliant with an exit-within-N-days workflow; quarterly full-universe refresh; keep a manual override/approved-list from your board (the repo's Excel can seed this) and make it the authoritative *business-activity* screen.

#### G3 — Business-activity screen is coarse · **P2**
Keyword match on a single sector/industry label (`finance`, `hotel`, `media`, `club` …) both over-excludes (e.g. fintech software, hospitality-adjacent suppliers) and under-excludes (conglomerates with a non-permissible segment > 5 % revenue). Add **segment-revenue** data (XBRL) and a per-company override list.

#### G4 — Parse failures can produce false compliance · **P1**
See D4 (0.0 defaults). Add `UNKNOWN` states and require every ratio input to come from a validated field.

#### G5 — Purification and live product type · **P2**
Purification is computed as `realised profit × other_income/sales` with a 5 % default when missing; scholars typically apply purification to **dividends received** (and treat trading gains differently); document the opinion you follow and compute per-holding-period/per-dividend accordingly. For live trading, enforce **CNC only, no MTF/margin, no shorting, no F&O** (see B8); idle cash should not be placed in interest-bearing sweep products.

---

### H. Performance Measurement & Statistics

#### H1 — Metrics are mis-computed · **P1**
**Where:** `portfolio/state.py`, `portfolio/metrics.py`, `run_evaluator.py`, `run_eod_reconciliation.py`.
- `annualized_sharpe` (portfolio state) is computed from daily realised P&L **only on days with exits** (sparse series), ×√252 ⇒ overstated Sharpe; ignores unrealised P&L.
- `equity_curve` stores `core_equity = core_eq − unrealized` (realised-only), and the evaluator uses it for Sharpe/max-drawdown ⇒ drawdowns excluding open-position losses are understated.
- **DSR** is dimensionally inconsistent: it compares an annualised Sharpe with `√(2 ln N)` (a z-score scale), uses annualised SR in a variance formula defined for per-period SR, and `n_trials` counts only training-config rows (1 for most runs) while dozens of hand-tuned parameters were tried. `pbo = 1 − dsr` is **not** a probability of backtest overfitting (PBO requires CSCV across a family of strategy variants).
- Sample sizes are not controlled: the "1-month paper gate" typically yields < 10 trades.
**Fix:** daily **mark-to-market** equity (store both realised and total), time-weighted returns, Sharpe/Sortino/Calmar on that series; proper DSR (Bailey & López de Prado: benchmark `SR₀ = √V[SR̂]·((1−γ)Φ⁻¹(1−1/N)+γΦ⁻¹(1−1/(Ne)))` with per-period SR and an honest `N`), real PBO via CSCV over the parameter grid, and trade-level statistics (expectancy in R, SQN, profit factor, MAE/MFE).

#### H2 — Sample size needed before trusting paper results · **P1**
To detect a true expectancy of +0.30 R with per-trade R-multiple standard deviation ≈ 1.3, at 5 % significance and 80 % power: `n ≈ ((1.645 + 0.84)·1.3/0.30)² ≈ 116` independent trades. If the system fires 1–3 trades a week, that is **~9–18 months**, not one month. Make the paper stage a pre-registered experiment: fixed parameters, frozen code (tagged), minimum 100–120 trades *or* 9–12 months, then compare to the Nifty Smallcap 250 / Nifty 500 Shariah benchmark on the same dates.

---

## 5. What Is Good (keep it)

1. **Deterministic risk authority.** LLMs cannot size or place orders.
2. **Fail-closed halt** on unreadable kill-switch state; sentinel stays in exit-only mode while halted.
3. **Microstructure awareness**: circuit bands, T2T/BE/BZ block, ASM/GSM columns, lower-circuit trap and "pessimistic fill" intent in EOD.
4. **Purged-CV and triple-barrier intent**, DSR/PBO scaffolding — the right instincts; they need the corrections above.
5. **Paper mode enforced** by a validator plus a `LIVE_TRADING_ENABLED` gate.
6. **Process locking** (`portalocker`) on the scheduler and the DB.
7. **Shariah as a gate, not an afterthought**, with fail-closed behaviour on zero total assets.
8. A real test suite and visible remediation history.

---

## 6. Prioritised Roadmap

### Phase 0 — "Stop the bleeding" (≈ 1–2 weeks; do before counting any more paper results)
1. **B2** fix EOD look-ahead; add V-shaped-day test. **B1** add exit slippage + full Indian charges + entry at live price; clamp to cash.
2. **C1** wire a correct daily-drawdown guard into the order gate, watcher and sentinel.
3. **D1** fix reverse-split multiplier; detect corporate actions from `prev_close` discontinuity for the whole universe; make adjustments non-destructive.
4. **A2** replace absolute 0.75 cutoff with a rank/EV rule; return `None` + alert when model missing.
5. **D4/G4** replace `0.0` defaults with `None`/`UNKNOWN`; unknown ⇒ not tradable.
6. **B5** manage `MARKED_FOR_CLOSURE` positions (monitor, count in exposure, exit routine).
7. **B6** make the trigger watcher re-validate and expire after one session.
8. Freeze a **model card** + config hash on every decision record.

### Phase 1 — "Know whether it works" (≈ 3–6 weeks)
1. **A1** event-driven point-in-time backtester replaying production logic with the shared execution/cost model; ablations; benchmarks; DSR/PBO done properly (**H1**).
2. **A3/A4/A5** meta-labelling retrain: same feature module, strategy-consistent labels, uniqueness weights, per-date rank-IC validation, calibration, JSON model + model card; schedule retrain with champion/challenger.
3. **D2/D3** data-quality gate, official calendar/band files, secondary quote source; replace the Screener scrape with filings/vendor data for Shariah ratios.
4. **C2/C3** explicit risk policy: heat cap, global position limit, tiered drawdown de-risking calibrated by backtest drawdown distribution.
5. **F2** authenticated Telegram commands, dashboard behind VPN + 2FA, heartbeat + job-run ledger.

### Phase 2 — "Make it production-grade" (≈ 1–3 months)
1. Pre-open/evening pipeline architecture (**B7**); 3:10–3:20 PM confirmation step only.
2. **B8** real broker adapter with order state machine and broker↔DB reconciliation; 4-week live-shadow; CNC-only enforcement.
3. **E1/E2** structured-JSON LLM auditor in shadow; outcome-linked counterfactual dataset; drift monitors.
4. **F1/F3/F4** state store split, migrations, one orchestrator, pinned/tagged deploys with rollback, restore tests.
5. **G1/G2** compliance table with continuous re-screening of holdings; board-approved methodology document.

### Phase 3 — "Edge enhancement" (after Phase 1 shows a positive net expectancy)
- Cross-sectional ranking model (LightGBM `lambdarank`/regression on forward R) with sector/size-neutralised features, delivery %, relative-volume, earnings-drift, accumulation/distribution; monotone constraints; ensembling with a simple linear baseline.
- Continuous regime/breadth scalar; volatility-managed sizing; stop/target/time-stop optimisation under nested walk-forward.
- Capacity analysis (how much capital can the liquid compliant universe absorb?).

### Go-live gates (all must be true)
| Gate | Criterion |
|---|---|
| Statistical | ≥ 100 net-of-cost paper trades **or** ≥ 9 months; expectancy > +0.2 R with 90 % CI lower bound > 0; DSR > 0.95 with honest trial count |
| Realism | Paper-vs-"live-shadow" slippage within 25 % of simulator; zero reconciliation breaks for 4 consecutive weeks |
| Risk | Kill-switch and daily-DD drills executed successfully (halt from Telegram + dashboard); worst simulated day within policy |
| Data | 0 unexplained price jumps; corporate-action coverage audit passed; DQ gate alert drill passed |
| Compliance | Board-approved methodology; holdings re-screen verified; CNC-only enforced in code |
| Ops | 30 days with no missed scheduled run; restore test passed; deploy/rollback rehearsed |
| Capital | Start at ≤ 10 % of intended capital for 3 months |

---

## 7. Recommended Target Design (summary of "better options")

| Layer | Today | Recommended |
|---|---|---|
| Universe | All bhavcopy symbols, last-5-day filter; Shariah applied late | Nightly **eligible universe** table = Shariah ∩ liquidity ∩ not ASM/GSM ∩ not suspended ∩ band known |
| Prices | Mutable adjusted table | Immutable raw + adjustment-factor table; adjusted at read time |
| Signals | Stage-2 + dry-up proxy; MR sleeve | Swing-pivot VCP with contraction sequence + RVOL breakout + RS percentile; MR only if separately validated |
| ML | Pooled-AUC XGBoost, absolute cutoff | Meta-labelled ranker on screener events; per-date IC; calibrated expected-R; percentile gate |
| LLM | 3 correlated agents, free-text score | Structured veto-only auditor on verified facts; promoted only if shadow evidence supports it |
| Sizing | per-trade + sector; conflicting caps | Risk policy: per-trade risk, portfolio heat, max positions, cluster caps, days-to-exit liquidity cap, gap-adjusted risk |
| Drawdown control | 6 % lifetime halt, mis-specified CPPI | Tiered de-risking calibrated from backtest; recovery-based re-entry |
| Execution | Trigger-price fills, no exit costs | Shared simulator + broker adapter with order state machine; exchange-resident stops |
| State/Ops | DuckDB for everything; single-threaded scheduler | DuckDB/Parquet for analytics; SQLite-WAL/Postgres for state; one orchestrator with run ledger + heartbeat |
| Measurement | Sparse-day Sharpe, realised-only equity, mislabeled DSR/PBO | Daily MTM equity; R-multiple statistics; proper DSR/PBO; pre-registered paper study |

---

## Appendix A — Reproducible Checks Run During the Audit

**A.1 ML probability range (XGBoost, 150 trees, depth 4, lr 0.03, subsample 0.8, colsample 0.8; 9 Gaussian features, base-rate ≈ 45 %).** Output table in A2: maximum probability 0.58/0.63/0.70 for AUC 0.495/0.529/0.574; **0 % of test rows ≥ 0.75** in every case.

**A.2 Label vs trade geometry.** Label upper/lower = **+2.0 / −1.8 ATR**; live stop = 1.8 ATR, **T1 = 3.6 ATR**, **T2 = 6.3 ATR** (2R and 3.5R × 1.8 ATR).

**A.3 Cost model.** Harness round-trip cost recomputed from its own constants = **0.1927 %** (docstring claims 0.13–0.15 %); with STT on both legs for delivery = **≈ 0.293 %**. The harness divides trade cost by the number of universe stocks, so a single-position portfolio is charged 1/10 of the true cost. PaperBroker slippage per side = 0.1 % / 1.0 % / 1.5 % (round trip 0.2 % / 2 % / 3 %) applied on entry only.

**A.4 Reverse-split multiplier.** For `SPLIT` with `ratio_from = 1`, `ratio_to = 0.1` the function returns `min/max = 0.1`; the correct history multiplier is **10.0**. Forward 10-for-1 (`ratio_to = 10`) returns 0.1 (correct).

**A.5 Wiring audit (grep).** `is_daily_drawdown_breached` → only `second_opinion_gate.py`; `evaluate_second_opinion` → no callers; `check_liquidity_and_executability` → imported in `run_live_preview.py`, never called; `get_hmm_market_regime`/`use_hmm=True` → never invoked with HMM enabled; `INSERT INTO delisted_stocks` → none; `profit_growth_pct` / `sales_growth_pct` → read by prompts, never produced by the scraper; `run_monthly_retrain` → not scheduled; Telegram inbound handlers → none.

**A.6 Tests.** 4 modules not collectable in sandbox (missing `langgraph`, `moto`); of the remaining 151 tests: 133 passed, 16 failed (env-related), 2 skipped. Not treated as defects.

---

*This report evaluates code and design as of the supplied snapshot. Items marked "verify" depend on artifacts that were not in the snapshot (model file, database, live feeds). Nothing here is investment, legal, or religious-ruling advice; the Shariah methodology in particular should be confirmed with your qualified scholar.*

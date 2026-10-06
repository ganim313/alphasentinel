# AlphaSentinel — Quant, Strategy & Engineering Readiness Audit

**Audit date:** 2026-10-06
**Scope:** whole repository as packed in `repomix-output.xml` (231 files; ~18.6k lines of Python in `src/`, `scripts/`, `research/`, `dashboard/`, `tests/`, plus `deployment/`, `notebooks/`, config and docs)
**Question asked:** *Is the system ready to trade correctly? What is weak, and what should replace or fix it — from a quant-expert and a developer point of view?*

---

## 0. How to read this report

**Evidence tags** (so you can tell fact from judgement):

| Tag | Meaning |
|---|---|
| ✅ Code | I read the code path and the behaviour follows directly from it |
| 🧮 Sim | I reproduced it with a small numerical experiment (Appendix A) |
| ❓ Verify | Depends on runtime data/artifacts that were **not** in the dump (DuckDB contents, `models/`, `.env`, logs). Treat as a hypothesis to check |

**Severity:** **Critical** = invalidates results or can lose capital · **High** = materially wrong behaviour or risk · **Medium** = degrades quality/robustness · **Low** = hygiene.

**Limits of this audit.** `models/`, the DuckDB file, `.env` and logs are git-ignored, so I could not inspect the deployed XGBoost/HMM artifacts, actual data distributions, or live run history. I did not execute the 214-test suite. Findings marked ❓ should be confirmed with the one-line checks given in Appendix B.

---

## 1. Executive verdict

### 1.1 Bottom line

> **Not ready for live capital — and, in its current state, the paper-trading run cannot be used as evidence that the strategy works.**
> The architecture is thoughtful (deterministic risk authority over LLMs, fail-closed gates, purged CV, Shariah-first filtering). But several defects sit *underneath* the layers that were built with care: the data layer feeds the models wrong inputs, paper fills/exits are optimistic and internally inconsistent, the only backtest tests a different strategy on a different universe, and the ML/LLM gates are either unreachable or unvalidated. Polishing the upper layers will not help until these are fixed.

### 1.2 The seven findings that matter most

| # | Finding | Why it is decisive | Sev. |
|---|---|---|---|
| 1 | **There is no backtest of the system that actually runs.** The only harness tests 3 *proxy* strategies on **10 Nifty large-caps** (incl. banks), no ADTV/Shariah/ML/risk layers (H1) | The micro/small-cap edge has never been measured | Critical |
| 2 | **Corporate actions are adjusted only for open positions / recent candidates (or the top-50 names)**; the other ~1,500 names used for screening and ML training stay unadjusted (F1) | Splits/bonuses become fake −50…−90 % crashes → corrupt labels, features, ATR, VCP | Critical |
| 3 | **Circuit bands and ASM/GSM flags are never sourced** — `circuit_band_pct` silently defaults to 20, `is_asm/is_gsm` are always FALSE (F2) | Every circuit-band risk rule and the ASM/GSM exclusion is inert for real micro-caps | High |
| 4 | **Triple-barrier label is ≈ a coin flip**: 🧮 on a no-edge random walk ~50 % of rows are "wins", >half of them from *timeouts*; and the **0.75 ML cut-off is unreachable** for any realistically calibrated model (B1, B4) | The ML gate either vetoes everything (no trades ⇒ no evidence) or only passes over-confident noise | Critical |
| 5 | **Paper fills are optimistic and the stop logic is self-contradictory**: entry booked at the pivot (not the market), no exit slippage, no transaction costs, two stop engines with different data (E1, E2) | Paper P&L is biased upward and not reproducible | Critical |
| 6 | **The daily-drawdown guard is dead code and mathematically wrong**; the lifetime kill-switch is tuned so tightly (6 %) that normal volatility halts the system, and one flag mixes "risk halt" with "Yahoo had an outage" (D3, D4) | Either no loss limit when needed, or long unintended halts | High |
| 7 | **Public, unencrypted dashboard (port 8501 opened to the world) controls the kill-switch and capital** (I1) | Anyone who guesses one password can resume trading or reset the portfolio | High |

### 1.3 What is already good (keep it)

- **Authority design is right:** LLMs can only *veto*; capital allocation is deterministic Python (`risk/arbiter.py`). Debate failure now fails closed (`conviction_score = -1.0` sentinel).
- **Many fail-closed defaults:** Shariah gate on missing data, benchmark provider raises instead of passing through, `is_system_halted()` fails closed on DB error, Dhan routing refuses unmapped security IDs.
- **Real statistical hygiene attempts:** purged K-fold with embargo (`utils/cv.py`), strategy-trial registry (`strategy_version`), stop-first label priority, canonical RSI/ATR module, a single `benchmark_provider`.
- **Operational scaffolding:** idempotent DB bootstrap, process lock on the scheduler, nightly backup job, per-job Telegram alerts, systemd units, timezone pinned to IST.
- **Awareness of microstructure** (lower-circuit trap, ADTV participation caps, T2T/BE exclusion) — the *ideas* are right; the data feeding them is the problem (F2).

### 1.4 Scorecard

| Domain | Score /10 | Reason in one line |
|---|:--:|---|
| Architecture & separation of concerns | 7 | Clean layering; LLM advisory only |
| Strategy logic (VCP/MR/regime) | 4 | Entry lacks volume confirmation; screen runs on yesterday's close; config keys silently ignored |
| ML model & validation | 2 | Degenerate label, wrong training population, unreachable cutoff, constant feature |
| LLM debate layer | 3 | Unvalidated marginal value; latency risk; prompt key mismatch |
| Risk & portfolio construction | 4 | Risk budget never binds; no cash/exposure cap; guards fail open or are dead |
| Execution & position lifecycle | 3 | Optimistic fills, zombie status, dual stop engines, live path not implemented |
| Data layer | 4 | Corporate actions, circuit bands, ASM/GSM, freshness gates missing |
| Shariah compliance | 5 | Fails closed, but fragile scraping, entry-only screening, methodology to confirm |
| Backtest / research validity | 2 | Proxy strategy, 10 large-caps, understated costs, cosmetic statistics |
| Operations, security, observability | 4 | Good start; exposed dashboard, single-threaded scheduler, no dead-man switch |
| **Overall** | **≈ 3.8** | Promising skeleton, **not evidence-grade** |

---

## 2. What the system is (intended behaviour and outputs)

### 2.1 Purpose

*AlphaSentinel* is an autonomous, **$0-budget, Shariah-first swing-trading OS for Indian small/micro-cap NSE equities**, currently in **paper-trading mode** on a ₹10 lakh notional portfolio. It is meant to:

1. Ingest NSE end-of-day data (Bhavcopy) into DuckDB.
2. Screen for Minervini Stage-2 / VCP breakouts (and an RSI<30-above-200DMA mean-reversion variant) on a liquid, non-T2T universe.
3. Filter by Shariah ratios (scraped from Screener.in), an "anti-trap" shield, and an XGBoost probability.
4. Run a LangGraph Bull → Bear → Judge LLM debate that outputs a conviction score.
5. Size and place the trade with a deterministic risk arbiter; manage it with a 15-minute stop sentinel and an EOD reconciler; report via Telegram and a Streamlit dashboard.
6. Learn over time (monthly retrain, weekly feedback loop, "Alpha Factory" genetic-programming research).

### 2.2 Daily timeline (as scheduled in `scripts/run_scheduler.py`)

| IST | Job | Output |
|---|---|---|
| 06:00 | Fyers instrument-master sync | `instrument_master` |
| 08:30 | Pre-market macro radar + corporate-action scan (yfinance) | `macro_weather` row; splits recorded/applied |
| every 15 min (09:15–15:30) | Sentinel: trailing stops, stop-outs (yfinance 15-min bars) | updates `positions` |
| every 10 min | AWAITING_TRIGGER watcher (yfinance 5-min bars) | intraday entries |
| **15:15** | Live preview: liquidity → VCP/MR → ML (top 15) → live tick → Shariah → anti-trap → LLM debate → risk → order | paper entries, Telegram trade cards |
| 18:30 | EOD: ingest Bhavcopy, reconcile stops/targets (T1 trim 50 %, T2 runner), purification log, equity snapshot | `equity_curve`, `purification_log` |
| 19:00 | Drawdown check (lifetime HWM 6 % kill, monthly 4 % warn) | halt flag / alerts |
| weekly / monthly | Evaluator (Sharpe, DSR), feedback loop, HMM refit, backup, DB maintenance, purification report | JSON metrics, `agent_memory` |

### 2.3 The decision funnel

```
~2,000 NSE EQ symbols (bhavcopy_daily)
  └─ active (traded in last 5d, not in delisted_stocks*)                 *table is never populated
      └─ liquidity: ADTV ≥ ₹25L, band ≥ 5% (synthetic!), price ≥ ₹10
          └─ VCP template + vol dry-up + vol contraction  |  RSI<30 & >200DMA
              └─ top-15 by (has_vcp, price≥trigger, ratio, ADTV)  →  XGBoost prob (veto only)
                  └─ live tick (Yahoo, 15-min delayed) → Shariah (Screener.in) → top-3
                      └─ anti-trap shield (6 layers)
                          └─ deterministic risk (sector cap, corr guard, ATR stop, 10% cap, CPPI, vol-target)
                              └─ Bull → Bear → Judge (conviction ≥ 6.5 gate, then ≥ 7.0 & ML ≥ 0.75)
                                  └─ breakout confirmed? → paper order  |  else AWAITING_TRIGGER
```

### 2.4 Intended outputs

Paper positions with stop/targets, Telegram trade cards and summaries, a Streamlit dashboard (portfolio, kill-switch, capital controls), monthly Shariah purification reports, weekly performance JSON (win-rate, Sharpe, DSR), and an `agent_memory` feedback record per debate.

---

## 3. Status versus the earlier in-repo audit (`Audit/AlphaSentinel_Master_Audit_Report.md`, 2026-09-22)

The repo has moved since that report. I re-checked each of its headline claims against the current code so effort is not wasted:

| Earlier claim | Status now | Note |
|---|---|---|
| IND-1: `conviction_score` pre-seeded at 7.0 approves failed debates | **Fixed** | Seeded `-1.0`; gate fails closed (`run_live_preview`) |
| Train/serve benchmark skew (synthetic index vs `^NSEI`) | **Fixed** (benchmark) / **Open** (other skew) | Single `benchmark_provider`; but feature `min_periods` etc. still differ (B6) |
| VCP 52-week range from closes | **Fixed** | Uses OHLC high/low; **but** pivot still = max of 20 *closes* (A1) |
| RSI inconsistency | **Fixed** | Canonical `wilders_rsi`; one stale duplicate in `research/algos` |
| Macro snapshot never consumed | **Fixed** | `run_live_preview` reads `macro_weather` first |
| `run_db_maintenance` bypasses lock | **Fixed** | Uses portalocker |
| Drawdown base capital hard-coded | **Fixed** | Reads `portfolio_state` |
| Sector cap vs static ₹10 L | **Mostly fixed** | Uses live equity, but still assumes a hard-coded 10 % candidate size |
| Pledge history never written | **Fixed (partly)** | Scraper now writes it, but trend is ≥30 d not 3 m and blind for new symbols (G2) |
| AWAITING_TRIGGER never polled | **Fixed** | Watcher exists — but enters on a *touch* of the pivot (E7) |
| Holiday list 2026 only | **Mostly fixed** | 2027 added (provisional lunar dates) (F8) |
| `evaluate_second_opinion()` orphaned | **Still true** | Module not imported anywhere ⇒ daily-DD guard is dead code (D3) |
| `delisted_stocks` never populated | **Still true** | No writer anywhere (F7) |
| DhanBroker non-functional | **Still true** | Even with `LIVE_TRADING_ENABLED=True` it logs "NOT SENT TO API" (E4) |
| Deployed model AUC 0.50 on 100 rows | ❓ **Cannot verify** | `models/` not in dump; training pipeline has since been rebuilt, but see Part B |
| Dual orchestrators | **Partly** | Scheduler has a lock; the runbook still documents crontab (doc drift) |

**New in this audit** (not in the earlier report): F1, F2, B1, B2, B4, B5, D1–D4, D6, D7, E1–E3, E5–E8, H1–H4, I1, I3–I6, plus most of Part C and G.

---

# PART A — Strategy & signal logic

### A1 — Breakout is bought without breakout confirmation  `High` ✅ Code
**Where:** `screening/vcp_screener.py`, `scripts/run_live_preview.py`, `scripts/run_trigger_watcher.py`
**Weakness:**
- The screen *requires* volume dry-up (`vol_5d < 0.85 × vol_20d`) and volatility contraction — pre-breakout conditions — then the system buys when price ≥ `trigger_price`, where the pivot is the **max of the last 20 closes**. A genuine VCP/O'Neil breakout needs a **volume surge on the breakout bar** (commonly ≥ +40–50 % vs the 50-day average). `live_volumes` is accepted by `evaluate_minervini_vcp_batch` but never used.
- The trigger watcher fires when *any* 5-minute **high** since candidate creation ≥ pivot, then places the order at the *current* price (which may already have faded back below the pivot). A single illiquid print triggers an entry.

**Fix / better option:** require (a) projected full-day volume ≥ 1.5× 50-day ADV using an intraday volume-profile curve, (b) price *holding* ≥ pivot for N minutes or a close-based confirmation, (c) `current ≥ pivot` and `≤ pivot × 1.03` at order time, (d) a limit order at pivot + buffer with a maximum chase. Re-run the anti-trap and liquidity checks at trigger time, not only at debate time.

### A2 — Trend template deviates from Minervini and silently ignores your YAML  `High` ✅ Code
**Where:** `config/strategy.yaml` vs `vcp_screener.py`
**Weakness:**
- YAML defines `60d_low_multiplier`, `60d_high_multiplier`, `trend_dma_period`; the code reads `52w_low_multiplier` / `52w_high_multiplier`. The keys never match, so **hard-coded defaults (1.25 / 0.75) always apply** and the YAML is decorative. (Minervini's rule is ≥ 30 % above the 52-week low, i.e. 1.30.)
- The "200-DMA" uses `min_periods=150`, so ~7-month-old listings pass as Stage 2.
- **No relative-strength rank.** RS is `stock 60d return − benchmark 60d return`, used only for sorting (and for the regime bypass). Minervini/IBD require an RS *rating* (percentile across the universe, ≥ 70–80).

**Fix:** load config through a typed schema (`pydantic`, `extra="forbid"`) so a mismatched key raises at startup; set 200 full bars; add an IBD-style RS rating (weighted 3/6/9/12-month returns → universe percentile) with a minimum threshold; unit-test that changing a YAML value changes behaviour.

### A3 — The 15:15 "live" screen is really yesterday's screen on a 15-minute-delayed price  `High` ✅ Code / ❓ Verify
**Where:** `vcp_screener.py` (live prices), `run_live_preview.py` Pass 3, `fyers_client.py`
**Weakness:**
- Template checks use `live_prices`, fetched from Fyers. `FyersClient` reads its token only from the `FYERS_ACCESS_TOKEN` env var and Fyers tokens expire daily; there is no automated login, so `get_live_quotes` normally returns `{}` and the screener falls back to **last EOD close**. The Yahoo tick is applied afterwards to only the top-15 and **does not re-run the template, pivot or regime logic** — a stock that broke below its 50-DMA at 14:00 still passes.
- Yahoo NSE quotes are normally delayed (❓ check the timestamp of the last bar you receive), so "3:15 PM live" may be a ~3:00 PM price.
- The whole pipeline (Screener.in scraping 1–3.5 s per symbol, 3 candidates × 3 LLM calls with a 15 s timeout and a 3-model waterfall) is launched at 15:15 with a 20-minute timeout — it can place paper orders **after the 15:30 close**.

**Fix / better option (simplest, most robust for a $0 stack):** move the decision to **end-of-day signal → next-session execution**. Compute signals after the Bhavcopy lands (evening), run ML/LLM/Shariah checks offline with no time pressure, store an *order plan* (limit price, max gap, expiry), and execute at/after the next open with a gap filter. This removes the delayed-quote, latency and look-ahead hazards in one move. If you keep intraday decisions, take quotes from the broker feed with automated token refresh and enforce a hard cut-off (e.g. no new orders after 15:22).

### A4 — Mean-reversion strategy is half-built  `Medium` ✅ Code
**Where:** `mean_reversion_screener.py`, `run_live_preview.py`
**Weakness:** MR candidates get `trigger_price = current price` and are then managed with breakout parameters (1.8 ATR stop, 2R/3.5R targets, trailing from peak). The backtest proxy exits on RSI>70 or close>SMA20 — **live ≠ backtest**. No time-stop, no handling of "falling knife" micro-caps (news-driven selloffs, ASM stage moves). It also ranks below VCP and is cut by the top-15 truncation, so it rarely trades.
**Fix:** either drop MR until it has its own validated exit logic (time-stop 3–5 days, exit on SMA10/20 reclaim, half size, no averaging down), or define and test it as a separate strategy with its own risk budget.

### A5 — Regime filter is crude, mis-benchmarked, and the HMM is wired to nothing  `Medium` ✅ Code
**Where:** `utils/benchmark_provider.py`, `scripts/fit_hmm_regime.py`
**Weakness:** regime = `Close ≥ SMA50` of **Nifty 500 (`^CRSLDX`)** — a large-cap-dominated index — for a micro/small-cap book. `get_market_regime(use_hmm=False)` is the only call path; the monthly HMM refit job produces a pickle **nothing consumes**. The HMM is also fit on 1-D index returns over the whole window and decoded with Viterbi over the full sequence (look-ahead if used in backtests).
**Fix:** build **breadth from your own universe** (% of liquid names above 50/200-DMA, new-high/new-low ratio, equal-weight small-cap index vs its 200-DMA, India VIX), and turn it into a *continuous exposure scalar* rather than a binary switch. Either wire the HMM in after walk-forward validation (fit only on data prior to each decision date) or delete the job.

### A6 — Liquidity gate is duplicated and the tiered version is bypassed  `Medium` ✅ Code
**Where:** `run_live_preview.py` vs `screening/liquidity_guard.py`, `strategy.yaml`
**Weakness:** `check_liquidity_and_executability` (tier-specific ADTV floors from YAML + bid-ask spread check) is **imported but never called** in the pipeline. The pipeline uses a hand-rolled version with a flat ₹25 L floor for every tier, and ADTV tier thresholds appear in three places with different values (`strategy.yaml`, `run_live_preview`, `order_manager`).
**Fix:** one liquidity service, one config, called from one place; include a spread/impact estimate and test that each tier floor is enforced.

---

# PART B — Machine-learning model & validation

> The earlier audit said the deployed model was trained on 100 rows with AUC 0.50. The training script has since been rebuilt (purged CV, gate). I cannot inspect the artifact (❓), so the points below assess the **pipeline**, which determines what any retrained model can be.

### B1 — The "triple-barrier" label is mostly a 5-day coin flip  `Critical` 🧮 Sim
**Where:** `scripts/run_model_training.py::triple_barrier_label`
**Weakness:** barriers are +2.0 ATR / −1.8 ATR within 5 bars; if neither is touched the label is decided by the **sign of the terminal close** and mapped `1` if positive. On a random walk with *zero edge* (Appendix A-3), the "win" base rate is **≈ 50 %**, of which only ~23 pp are real upper-barrier hits and **~27 pp are timeouts that happened to close up**; stop-first outcomes are ~24 %. The model is therefore largely predicting "will the stock be up in 5 days" — a noisy, low-information target — not "will the setup reach 2 ATR before 1.8 ATR".
**Fix / better option:**
- Treat timeouts as their own class (3-class) or drop them; or label by **realised R-multiple at the time barrier**.
- Apply López de Prado **sample weights by label uniqueness** (windows overlap on every day).
- Switch to **meta-labeling** (B2): label only *events* where the rule-based setup fired.

### B2 — Trained on the wrong population  `Critical` ✅ Code
**Where:** `run_model_training.py` (SQL: every `series='EQ'` symbol-day) vs deployment (`run_live_preview.py`)
**Weakness:** the model learns P(win | *any* stock on *any* day) but is applied only to candidates that already passed VCP, liquidity, Shariah and trap filters. Distribution shift is guaranteed; the AUC measured in CV says nothing about lift **inside** the setup population.
**Fix:** **meta-labeling** — generate events with the same screener used live (same universe, liquidity and trend filters), label each event with the realised outcome of the live exit rules, and train/evaluate only on those. Report lift (precision, expectancy) of the top decile vs all events.

### B3 — The validation gate is statistically weak and economically blind  `High` ✅ Code
**Where:** `run_model_training.py` (gate: `mean_auc − std_auc > 0.51`), `utils/cv.py`
**Weakness:**
- AUC 0.51 is meaningless economically; AUC is pooled across symbols *and* dates, so a time-varying `market_regime` feature alone can create AUC without any stock-selection skill.
- Rows overlap (every day × every stock, 5-day labels) so the effective sample is far smaller than the row count.
- No calibration check, no net-of-cost expectancy, no stability across folds/sectors/years.
- CV is contiguous K-fold (trains on the future to predict the past); fine as a leakage check but not a deployment-faithful test.

**Fix:** per-date **cross-sectional rank IC** (mean and IC-IR), **top-decile net expectancy in R after costs**, Brier score + reliability curve, and a **walk-forward with refit** (or Combinatorial Purged CV). Promote a model only if net expectancy > 0 in ≥ 4 of 5 folds and the bootstrap lower bound > 0; deflate by an honest trial count (B7).

### B4 — The 0.75 probability cut-off is unreachable  `Critical` 🧮 Sim
**Where:** `settings.ML_CUTOFF_CONTROL = 0.75`, variant `0.65`; gate in `run_live_preview.py`
**Weakness:** with a ~50 % base rate and realistic signal strength, a *calibrated* classifier almost never emits p ≥ 0.75. Appendix A-4: at AUC 0.53 → P(p ≥ 0.75) ≈ 0; at AUC 0.55 → ~4×10⁻¹⁰; even AUC 0.65 → ~2.6 %. Either the ML veto blocks essentially everything (so the paper run produces **no trades and no information**), or the model is over-confident/overfit. The `0.65` "shadow variant" has the same problem.
**Fix:** choose thresholds by **rank** (e.g. top 20–30 % of the day's setups) or by **calibrated expected-R** (isotonic/Platt on out-of-fold predictions), and publish the cutoff-vs-trades-per-month curve before fixing a number. Log `ml_probability` for *every* candidate so the cutoff can be evaluated retrospectively.

### B5 — A dead feature and misnamed features  `High` ✅ Code
**Where:** `run_model_training.py`, `screening/ml_predictor.py`, `ml_features.py`
**Weakness:** `delivery_ratio` is **constant 0.5** in both training and inference — neither SQL query selects `delivery_pct`, so the code falls to the "neutral" branch. The delivery signal (a genuine edge candidate in Indian small-caps) is never used. `sharpe_rank` is a sigmoid of annualised Sharpe, not a rank. `market_regime` is identical for every stock on a date.
**Fix:** select `delivery_pct` (and keep it consistent in both paths); convert features to **per-date cross-sectional percentile ranks**; add setup-specific features (base depth/length, number of contractions, dry-up ratio, distance-to-pivot, breakout relative volume, RS rating, sector RS, delivery trend, ASM/GSM flag).

### B6 — Train/serve mismatch remains  `High` ✅ Code
**Where:** `extract_features_and_labels` (train) vs `extract_quantitative_features` (serve)
**Weakness:** same feature, different warm-up: `dist_high` `min_periods` 10 vs 20; `ema_dist` EMA without vs with `min_periods=10`; Sharpe window `min_periods` 10 vs 40; final model 150 trees vs 100 in CV; NaN→0 fills differ by path.
**Fix:** one `FeaturePipeline` class imported by both training and inference, plus a **golden-file test** asserting identical features for the same (symbol, date) from both entry points.

### B7 — Model governance: unversioned pickle, ambiguous failure value, unscheduled retrain  `Medium` ✅ Code
**Where:** `ml_predictor.py`, `run_monthly_retrain.py`, `run_scheduler.py`, `.gitignore`
**Weakness:** pickle loaded at import; missing model, short history or NaN features all return **`0.0`** (indistinguishable from "bad signal"); no model hash/feature-schema logged per inference; `models/` is git-ignored so artifacts aren't reproducible; `run_monthly_retrain.py` is not in `setup_schedule()` (only documented as a cron line); the retrain trigger counts `agent_memory` rows, which include rejected debates (see C3). `n_trials` for DSR counts only distinct ML configs, not thresholds/features/labels/rules you tried.
**Fix:** model registry (manifest with SHA-256, feature list, training window, metrics, git commit), `predict()` returns `None`/raises on failure and the caller decides, log model hash with every score, champion/challenger promotion with the economic gate above, schedule the retrain, and count *all* researcher degrees of freedom in `n_trials`.

### B8 — Performance and tuning  `Low` ✅ Code
Python loops with `iloc` for labels and RSI/ATR recursion will not scale to millions of rows; no early stopping, class weights, monotone constraints or hyper-parameter search. Vectorise with NumPy/numba; add early stopping on the purged validation fold.

### B9 — ML cannot influence selection  `Medium` ✅ Code
Only the top-15 by a hand-built sort key (`has_vcp`, price≥trigger, ratio, ADTV) get an ML score, and ML only vetoes. Rank *all* candidates with a composite (RS rating, ML score, liquidity) before truncating.

---

# PART C — LLM debate layer

### C1 — Marginal value is untested; latency and drift are real  `High` ✅ Code
**Where:** `agents/debate_graph.py`, `agents/llm_gateway.py`
**Weakness:** three sequential free-tier LLM calls per candidate (alias `gemini-flash-latest` can change under you; Llama-70B and a Qwen ":free" model as fallbacks) reasoning over ~10 numbers the system already has. The Judge sees no information the Bull/Bear did not (no filings, no news text, no price series). Conviction is regex-parsed free text. Each run yields a *different* veto pattern, so it randomly thins trades — and with so few trades (G/H) you cannot tell whether it helps.
**Fix / better option:** run the LLM **in shadow** — log the conviction for *every* candidate (including ones it vetoed) and compute avoided-loss vs missed-gain over ≥ 60–100 setups before letting it gate anything. Use LLMs where they add information: **reading announcements/filings** (auditor resignation, pledge invocation, SEBI/ASM actions, litigation, large block deals) with a strict JSON schema and Pydantic validation, temperature 0, pinned model IDs, run in the evening rather than at 15:15.

### C2 — Prompt/key mismatches feed the Judge "N/A"  `Medium` ✅ Code
`research_judge_node` reads `fundamentals['pledged_pct']`; the scraper writes `promoter_pledged_pct` — the Judge always sees `N/A` for pledge. Add a typed `Fundamentals` model shared by scraper and prompts.

### C3 — The feedback loop labels the wrong rows and uses a meaningless trigger  `Medium` ✅ Code
**Where:** `run_eod_reconciliation.py`, `run_feedback_loop.py`
**Weakness:** on any exit it runs `UPDATE agent_memory SET outcome_label=… WHERE symbol=? AND outcome_label IS NULL` — that labels **every** unlabelled memory row for that symbol (including debates that were rejected and never traded) with the later trade's outcome. The weekly loop injects a "WARNING" when win-rate < 40 % with n ≥ 5 — a 5-trade win-rate has a ±40 pp confidence band, and a 40 % threshold ignores payoff (a 2R target breaks even near 33 % before costs). `historical_memory` in the graph state is always `[]`.
**Fix:** key outcomes by `candidate_id`/`position_id`; judge strategy health in **R-multiples with confidence intervals** and a minimum n; or remove prompt injection until there is enough data.

### C4 — Silent LLM degradation  `Low` ✅ Code
When all providers fail the gateway returns a boilerplate string; the judge then parses no score → 5.0 → rejected (fail-closed, good) but with no alert and junk saved to memory. Alert on provider exhaustion; skip persisting.

---

# PART D — Risk & portfolio construction

### D1 — The 1.5 % per-trade risk budget never binds  `High` 🧮 Sim
**Where:** `risk/arbiter.py`
**Weakness:** shares = `min(risk_budget / stop_distance, 10 % × equity / price, ADTV cap)`. Because the ATR stop is capped at 5.5 %, `risk_budget/stop` is 3–5× larger than the 10 % notional cap, so **the 10 % cap always binds** (Appendix A-1): realised risk per trade is only 0.27–0.54 % of equity, not 1.5 %. Sizing is effectively "flat 10 % × scalars", independent of volatility, and higher-vol names (>5.5 % stop) are simply rejected.
**Fix:** decide the real risk intent (e.g. 0.5–0.75 % of equity per trade) and size = `risk_budget / stop_distance`, then apply notional/ADTV/sector/portfolio-heat caps. Track **portfolio heat** (Σ open risk) and cap it (e.g. ≤ 4–5 % of equity).

### D2 — No cash or gross-exposure check at order time  `High` ✅ Code
**Weakness:** the arbiter only verifies that cash is ≥ 5 % of equity **before** sizing, then can size a 10 % position — pushing cash negative (implicit leverage, contrary to a Shariah/cash-delivery mandate). There is no cap on **total open positions** (only 3 per sector), no gross-exposure cap, and same-day candidates are not netted against each other. `MARKED_FOR_CLOSURE` positions are excluded from the cash calculation yet counted in equity (E3).
**Fix:** enforce `cost + fees ≤ available_cash − reserve`, a max-positions cap (e.g. 8–12), a max-gross cap tied to regime, and compute against positions *plus* orders queued today.

### D3 — Daily-drawdown guard is dead code and wrong where used  `High` ✅ Code
**Where:** `risk/daily_drawdown_guard.py`, `screening/second_opinion_gate.py`
**Weakness:** the guard is imported only by `second_opinion_gate.py`, and **nothing imports that module**; production uses an inline gate in `run_live_preview.py` that never calls it. Where the guard *would* run its maths is wrong: day-open equity comes from `equity_curve.core_equity`, which the EOD job writes as **realised-only** equity (`core_eq − unrealized`), or falls back to the live equity (which already includes unrealised P&L); it then adds the **cumulative** `unrealized_pnl` of every open position again as "today's change". It ignores today's realised losses and it fails open on any exception.
**Fix:** snapshot `day_open_equity` at 09:15 (new column/table), compute `intraday_equity = day_open + realised_today + Δunrealised_today`, and call the guard from **every** entry path (live preview, trigger watcher, `execute_trade`). Fail closed on error for entries (not for exits).

### D4 — Kill-switch design: tight, shared, hard to recover  `High` ✅ Code
**Where:** `run_drawdown_check.py`, `risk/cppi.py`, `telegram_bot.py`, `run_sentinel.py`, `run_premarket.py`
**Weakness:**
- One `is_halted` flag serves **risk halts** and **data-outage halts** (Yahoo failure in the sentinel, macro-feed failure at 08:30, bhavcopy ingestion failure). A transient Yahoo outage halts the whole system until a human clicks Resume.
- The lifetime-HWM kill is 6 % and the CPPI floor is the same 94 % line. Small-cap momentum books routinely draw down far more than 6 % without anything being wrong, so the system will spend long periods halted. After a halt, resuming without resetting the HWM re-halts at the next 19:00 check.
- Below the floor, "exposure = 0" blocks new entries, so the only path back is existing positions.
- The Telegram `/HALT_ALL` command is advertised but **no inbound command handler exists**; the only control is the dashboard (I1).

**Fix:** separate halt types (`DATA_OUTAGE` auto-clears when the feed recovers; `RISK` needs acknowledgement); **tiered drawdown policy** (e.g. −5 % → half size, −8 % → quarter size, −12 % → flat and review) with a time-based review/reset; evaluate intraday for existing positions; implement authenticated Telegram admin commands (the `TELEGRAM_ADMIN_USER_ID` setting is currently unused).

### D5 — "CPPI" is not CPPI  `Medium` ✅ Code
`CPPI_MULTIPLIER = 3.0` is defined and **never used**. `exposure = min(1, cushion / (6 % × HWM))` is a linear scalar on **new** entries only; existing positions are never trimmed. Either implement true CPPI (`exposure = m × cushion`, rebalanced, including trims) or rename it "drawdown scaler" to avoid false confidence.

### D6 — Volatility targeting mostly fails open  `Medium` ✅ Code
**Where:** `risk/vol_target.py`
**Weakness:** returns `1.0` when < 2 assets (the first position is never scaled), when the covariance cannot be built, and on any exception. The covariance uses `pct_change().dropna()` across all symbols with `total_traded_qty > 0`, so for illiquid micro-caps nearly every day is dropped → "< 15 overlapping days" → fail-open. Sample covariance on 60 days with no shrinkage is noisy. It scales only the *candidate*, not the book.
**Fix:** Ledoit–Wolf/OAS shrinkage or a simple factor model, EWMA vols, zero-fill no-trade days, a **conservative default** (e.g. 60 % annual vol, ρ = 0.5) when data is missing, and apply the scaler at portfolio level.

### D7 — Correlation guard dilutes concentration and fails open  `Medium` ✅ Code
**Where:** `risk/correlation_guard.py`
**Weakness:** it averages the candidate's correlation across *all* open positions — one 0.9-correlated duplicate among five positions averages 0.18 and passes. `ffill(limit=3).dropna()` drops illiquid names → "insufficient history" → **pass**.
**Fix:** use the **max** pairwise correlation and the correlation to the *book* return series; cap cluster/sector-factor exposure (hierarchical clustering on returns); use weekly returns or Spearman to damp thin-trading noise; fail closed for illiquid names.

### D8 — Fail-open defaults in sizing inputs  `Medium` ✅ Code
Missing `macro_weather` ⇒ `target_cash_exposure_pct = 0` ⇒ full size. Sizing and stop use `trigger_price`, not the actual fill (E1). `portfolio_capital_rupees * 0.10` is hard-coded in the sector-cap test. Make defaults conservative and read all numbers from the config.

---

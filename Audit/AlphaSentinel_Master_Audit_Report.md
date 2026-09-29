# AlphaSentinel — Master Audit Synthesis Report

> **Orchestrated by:** Antigravity (Claude Sonnet 4.6 Thinking)  
> **Date:** 2026-09-22  
> **Agents deployed:** 4 (DeepSeek Audit Analyzer · Recheck Audit Analyzer · Chat Audit Analyzer · System Architect Analyst)  
> **Audits reviewed:** 3 (DeepSeek 2-pass · AlphaSentinel_System_Recheck_v2 · Chat-System Optimization Audit)  
> **Source files read:** All major files in `src/`, `scripts/`, `models/`, `dashboard/`, `tests/`, `research/`

---

## System Identity (Ground Truth)

**AlphaSentinel** — "Autonomous Quant Trading OS for Indian Small & Micro-Caps (\$0 Budget)"  
NSE equities only | ₹10L paper portfolio | Shariah-first | Minervini Stage 2 VCP + XGBoost + LangGraph LLM debate  
**Current state: mandatory paper-trading mode** (`PAPER_TRADING_MODE=True` enforced by settings validator).  
Live capital risk is structurally zero today. All failures are operational/accuracy failures, not financial-loss risks.

---

## Part 1 — Audit Validity Assessment

### 1.1 AlphaSentinel_System_Recheck_v2.md
**Verdict: Most reliable audit. ~90% of claims code-verified.**

This is the only audit that explicitly re-verified every claim against the live codebase using grep/direct file reads before publishing. Its findings are the most empirically grounded.

| Claim | Verified by Architect? | Verdict |
|---|:---:|---|
| `evaluate_second_opinion()` never called in production | ✅ | **CONFIRMED** |
| Dual orchestrators (`run_scheduler.py` vs crontab) undocumented | ✅ | **CONFIRMED** |
| `run_db_maintenance.py` bypasses portalocker | ✅ C18 | **CONFIRMED** |
| `init_db()` only runs on first DB creation | ✅ | **CONFIRMED** |
| Dashboard status is hardcoded string | ✅ | **CONFIRMED** |
| Drawdown check hardcodes `capital_base = 1000000.0` | ✅ BUG-8 | **CONFIRMED** |
| Prior DB locking finding (#3) was WRONG | ✅ | **CONFIRMED** — portalocker correctly implemented |
| `evaluate_eod_risk_offload()` never called | ✅ | **CONFIRMED** |
| Shariah pledge table never populated | ✅ N6 | **CONFIRMED** |
| `xgboost_global_meta.json` proves model pre-dates AUC gate | ✅ **AUC = 0.50** | **CONFIRMED — worse than stated** |
| Model provenance unknown | ✅ | **CONFIRMED — trained on 100 rows** |

**One notable gap:** The Recheck audit describes the Shariah scraping fallback as potentially passing non-compliant stocks. The architect finds that `total_assets = 0.0` in the fallback causes an `INVALID_OR_ZERO_TOTAL_ASSETS` early rejection — the Shariah gate actually **fails closed** on hard fallback. However, stale DB cache (7-day TTL) can still serve old passing data during a scraping outage.

---

### 1.2 DeepSeek-AlphaSentinel System Audit (1).md
**Verdict: Excellent depth, ~80% of specific code claims verified. Some effort estimates are optimistic.**

Two-pass audit with 44 unique findings. The second pass reads actual code line-by-line, producing high-confidence specific bugs.

| Claim | Verified by Architect? | Verdict |
|---|:---:|---|
| **N1: Train-serve skew — training uses synthetic index, inference uses ^NSEI** | ✅ | **CONFIRMED CRITICAL** |
| **N2: Fyers fallback broken — `symbol_sync.py` never scheduled** | ✅ | **CONFIRMED** |
| **N3: Pre-market macro snapshot never consumed by afternoon pipeline** | ✅ | **CONFIRMED** |
| **N4: VCP regime bypass rule (RS>15 + vol dryup) never implemented** | ✅ | **CONFIRMED** |
| **F2: Sentinel uses 15-min delayed yfinance, not real-time Fyers** | ✅ | **CONFIRMED** |
| **C2: Sector cap uses static ₹10L not current equity** | ✅ | **CONFIRMED** |
| **C10: `interest_income_ratio` uses wrong formula (`other_income/sales` vs `max(other_income, interest_income)/sales`)** | ✅ | **CONFIRMED** |
| **C11: VCP uses close price for 52-week high/low, not intraday high/low** | ✅ BUG-5 | **CONFIRMED** |
| **C18: `run_db_maintenance.py` bypasses portalocker** | ✅ | **CONFIRMED** |
| N5: `agent_memory` table never written | ✅ | **CONFIRMED** |
| N8: `AWAITING_TRIGGER` candidates never polled intraday | ✅ | **CONFIRMED** |
| N9: `delisted_stocks` table never populated | ✅ | **CONFIRMED** |
| N10: `paper_portfolios` table unused | ✅ | **CONFIRMED** |
| N12: `post_mortem_lab.py` references non-existent `sc.kronos_breakout_prob` column | Plausible | **LIKELY** — needs runtime test |
| F5: Binary SMA50 regime filter too simplistic | ✅ | **CONFIRMED** |
| N14: Pre-market macro snapshot not consumed | ✅ | **CONFIRMED** |
| "6-layer anti-trap shield comprehensive" (Section 3, marked ✅ Valid) | ❌ CONFLICT | **WRONG — Layer 4 never fires** (pledge table empty) |
| Effort estimate: "Purged K-Fold in 4 hours" | ❌ | **LIKELY UNDERESTIMATED 3–5×** |

**Internal inconsistency confirmed:** DeepSeek praises the anti-trap shield as comprehensive in Section 3 but reveals in N6 that Layer 4 (promoter pledge) never fires. This contradiction exists within the same document.

---

### 1.3 Chat-System Optimization Audit (1).txt
**Verdict: Conceptually sound, methodologically weak. The "multi-agent reanalysis" is a rhetorical device.**

> [!CAUTION]
> This document claims to perform a "multi-agent reanalysis with a team of specialized agents." In reality, it is **a single AI simulating 14 roles sequentially in one response**. There is no adversarial challenge, no independent signal, and the "cross-agent consensus" is manufactured by the same voice. This must be treated as a single-model analysis, not an independent validation.

| Claim | Verified by Architect? | Verdict |
|---|:---:|---|
| Missing model returns 0.0 — ambiguous failure signal | ✅ | **CONFIRMED** |
| AUC gate of 0.53 is dangerously weak | ✅ — **AUC is 0.50** | **CONFIRMED AND WORSE** |
| Slippage model too simplistic (no market impact) | ✅ | **CONFIRMED** |
| Upper circuit check at entry, no lower circuit check at exit | ✅ | **CONFIRMED** |
| Win-rate 40% threshold statistically unsound | ✅ | **CONFIRMED** |
| 3-day outcome metric too noisy | ✅ | **CONFIRMED** |
| `.duckdb.lock` committed to repo | ✅ | **CONFIRMED** |
| No portfolio-level covariance/VaR | ✅ | **CONFIRMED** |
| Conviction score from free-text LLM | ✅ | **CONFIRMED** |
| No feature store — train/serve skew | ✅ N1 | **CONFIRMED** |
| VIX > 22 forces signal to zero | ✅ (hardcoded in settings) | **CONFIRMED** |
| yfinance used for production benchmark | ✅ | **CONFIRMED** |
| LLM fallback degradation silent | ✅ C6 | **CONFIRMED** |
| "Static 50% train-test split" | ✅ (partially) | **CONFIRMED — single split with 5-day embargo, no K-Fold** |
| Kill-switch lacks strong auth | Partially | **PARTIALLY CONFIRMED — Telegram /HALT_ALL has no secondary auth** |
| Universe hardcoded / survivorship bias | ✅ BUG-11 | **CONFIRMED — all bhavcopy_daily symbols, `delisted_stocks` never consulted** |
| No symbol normalization | Partially | **PLAUSIBLE** — needs more investigation |
| "Multi-agent team" conducted reanalysis | ❌ | **FALSE — single AI roleplay** |

---

## Part 2 — Major Conflicts Between Audit Assumptions and System Reality

> [!WARNING]
> These are cases where an audit made a claim that the codebase directly contradicts.

| # | Audit | Claim | Reality |
|---|---|---|---|
| **CF-1** | Chat | "Multi-agent team" independently validated findings | **FALSE.** Same AI simulated all 14 "agents." No adversarial independence. |
| **CF-2** | Recheck v2 | Prior finding #3 (DB locking) was correct | **FALSE.** Portalocker with proper LOCK_SH/LOCK_EX was already implemented. The prior audit was factually wrong. |
| **CF-3** | Chat | Shariah scraping fallback silently passes non-compliant stocks | **PARTIALLY FALSE.** Hard fallback (`total_assets=0.0`) triggers `INVALID_OR_ZERO_TOTAL_ASSETS` early rejection. Shariah gate **fails closed** on hard fallback. Stale DB cache (7-day TTL) is the real risk vector. |
| **CF-4** | DeepSeek | Anti-trap shield is "comprehensive" (6 layers working) | **WRONG.** Layer 4 (promoter pledge) never fires because `promoter_pledge_history` is never written. It is a 5/6-layer shield in practice. |
| **CF-5** | All 3 audits | AUC gate at 0.53 is "too weak" | **WORSE THAN STATED.** The deployed model's actual AUC is **0.50** (trained on 100 rows). It pre-dates the gate entirely. The gate is irrelevant for the current model. |
| **CF-6** | Recheck v2 | Both "opinions" in the second-opinion gate use same model | **CONFIRMED** — but the deeper finding from the Architect is that the initial `AgentState` pre-seeds `conviction_score: 7.0`, creating an entirely separate bypass path. |
| **CF-7** | DeepSeek | SHADOW_MODE flag is "Medium" severity dead code | **UNDERSTATED.** The flag is completely unused in the entire codebase — not just the A/B harness. No code reads it anywhere. |
| **CF-8** | Chat | "Monthly drawdown circuit breaker" checks monthly loss | **FALSE.** The breaker computes drawdown from an **all-time high-water-mark**, never reset monthly. The name is semantically wrong. |
| **CF-9** | DeepSeek | Fyers free tier provides real-time NSE LTP | **UNVERIFIED ASSUMPTION.** Fyers data policy changes periodically. This needs confirmation before switching the sentinel to Fyers quotes. |
| **CF-10** | All 3 audits | Dhan integration is "structured but gated" | **MORE BROKEN THAN DESCRIBED.** DhanBroker builds the correct JSON payload but never sends an HTTP request — it logs "DHAN ORDER SIMULATION" and routes to PaperBroker. `EXECUTION_ENV=DHAN` does NOT enable live trading; it only labels orders as `DHAN_SIMULATED`. |

---

## Part 3 — Consensus Critical Findings (All Audits Agree)

These findings appear across multiple audits AND are confirmed by the codebase architect. Fix these first.

| Rank | Finding | Audits | Code Confirmed |
|---|---|---|---|
| 🔴 **C1** | Deployed XGBoost model is statistically random (AUC=0.50, 100 rows) | R+D | ✅ `xgboost_global_meta.json` |
| 🔴 **C2** | Dual orchestrators: `run_scheduler.py` vs crontab, mutually undocumented | R+D+C | ✅ `run_scheduler.py` |
| 🔴 **C3** | Train-serve feature skew: training uses synthetic equal-weight index, inference uses ^NSEI | D+C | ✅ `ml_features.py` + `run_model_training.py` |
| 🔴 **C4** | `evaluate_second_opinion()` is completely orphaned; production gate uses same model twice | R+D | ✅ zero call sites in production |
| 🔴 **C5** | Pre-market macro snapshot written but never consumed by 3:15 PM pipeline | D | ✅ `run_live_preview.py` uses live fetch |
| 🔴 **C6** | `run_db_maintenance.py` bypasses portalocker — DB corruption risk | R+D | ✅ raw `duckdb.connect()` |
| 🟠 **C7** | No portfolio-level correlation or VaR — 3 "safe" positions can be 1 concentrated bet | D+C | ✅ `arbiter.py` is trade-centric only |
| 🟠 **C8** | Promoter pledge anti-trap layer (L4) never fires — table never written | R+D | ✅ `promoter_pledge_history` empty |
| 🟠 **C9** | `AWAITING_TRIGGER` candidates never polled intraday — approved setups sit forever | D | ✅ no polling daemon found |
| 🟠 **C10** | Shariah `interest_income_ratio` uses wrong formula (`other_income/sales` vs PRD spec) | D | ✅ `screener_scraper.py` |
| 🟠 **C11** | VCP screener uses close-price for 52-week high/low pivot (should be intraday high/low) | D+Arch | ✅ `vcp_screener.py:227` |
| 🟠 **C12** | Universe query returns ALL historical bhavcopy symbols; `delisted_stocks` never consulted | D+C | ✅ `run_live_preview.py:76` |
| 🟡 **C13** | Drawdown check hardcodes ₹10L base capital instead of reading from settings | R+D+Arch | ✅ `run_drawdown_check.py:26` |
| 🟡 **C14** | Sector cap evaluated against static ₹10L starting capital, not current mark-to-market equity | D+Arch | ✅ `arbiter.py` |
| 🟡 **C15** | `agent_memory` table defined but never written — continuous improvement loop is structural fiction | D | ✅ no INSERT into `agent_memory` |

---

## Part 4 — My Independent Audit (New Findings Not in External Audits)

> [!IMPORTANT]
> The following findings were discovered through the Architect agent's ground-truth code read and are **NOT present in any of the three external audits**.

### 🔴 IND-1: Silent Approval Bug via Pre-Seeded `conviction_score = 7.0`
**Location:** `scripts/run_live_preview.py:344`  
**Severity: CRITICAL**

The `AgentState` is initialized with `conviction_score: 7.0`. The second-opinion gate checks `conviction >= 7.0`. If the LangGraph debate graph fails entirely before the `research_judge_node` runs (LLM error, graph exception, network timeout) and the graph short-circuits, the returned state has `conviction_score = 7.0` — which **passes the gate**.

This means: **a trade can be approved with a conviction score that was never actually generated by any agent.** A candidate that the judge would have scored 3.0 passes because the graph errored at the right moment.

- The judge's regex fallback correctly defaults to 5.0 (below the 7.0 gate) — but this only activates if the judge node runs.
- If the graph errors **before** the judge node, the fallback mechanism is never reached.
- No counter or log exists for "conviction score from pre-seed vs from judge."

**Fix:** Initialize `conviction_score: 0.0` (or -1.0) in the state. A gate failure should be a reject, not a pass.

---

### 🔴 IND-2: DhanBroker is Completely Non-Functional — Silently
**Location:** `src/execution/order_manager.py:161`  
**Severity: HIGH**

`DhanBroker.place_order()` builds the correct Dhan Super Order JSON, logs `"DHAN ORDER SIMULATION (NOT SENT TO API)"`, and then calls `PaperBroker.place_order()`, storing the result with `execution_type = 'DHAN_SIMULATED'`. There is no HTTP request to the Dhan API anywhere in the class.

**The risk:** A developer setting `EXECUTION_ENV=DHAN` believing they have enabled live trading. The system will appear to trade (paper positions are created), but no actual orders are placed. This could lead to real capital sitting idle while the system reports "live" positions.

---

### 🟠 IND-3: Benchmark Symbol Config/Code Mismatch
**Location:** `src/config/strategy.yaml` + `src/screening/vcp_screener.py:62`  
**Severity: MEDIUM**

`strategy.yaml` specifies `benchmark_symbol: "^CRSLDX"` (NSE 500 Index). The code reads this value via `QUANT_ALPHA_CONFIG.get("benchmark_symbol", "^NSEI")`. If the YAML loads correctly, `^CRSLDX` is used — but yfinance may not have historical data for this ticker, causing the Nifty SMA comparison to fail and `regime_passed` to default to `True` (pass-through). This silently disables the regime filter entirely.

Additionally, the ML training script computes `market_regime` using a synthetic equal-weight index (all bhavcopy stocks), while the VCP screener uses `^CRSLDX`/`^NSEI`. These three different "market regime" definitions (training, VCP, drawdown check) are completely inconsistent.

---

### 🟠 IND-4: Screener.in Stale Cache is the Real Shariah Risk (Not Hard Fallback)
**Location:** `src/ingestion/screener_scraper.py`, `fundamentals_cache` table  
**Severity: MEDIUM**

External audits worried about the hard fallback passing non-compliant stocks. The Architect confirms the hard fallback actually **fails closed** (zero total assets → INVALID rejection). But the real risk is different: the `fundamentals_cache` table has a **7-day TTL**. If a company's Shariah status changes (e.g., debt ratio crosses 33% threshold mid-quarter), the cache serves stale "pass" data for up to 7 days. For a system with Shariah compliance as a first-class religious obligation, a 7-day stale compliance window is a design gap.

---

### 🟠 IND-5: RSI Algorithm Inconsistency Between Modules
**Location:** `src/screening/mean_reversion_screener.py` vs `src/screening/ml_features.py`  
**Severity: MEDIUM**

- `mean_reversion_screener.py`: RSI computed with `.rolling(14).mean()` (Wilder's original SMA)
- `ml_features.py`: RSI computed with `.ewm(alpha=1/14, adjust=False).mean()` (EWM approximation)

These give different values for the same data. A stock near RSI=30 may be above 30 in the EWM variant (no ML signal) but below 30 in the SMA variant (mean reversion trigger), or vice versa. The `rel_rsi` ML feature is also computed using the EWM version but compared against the SMA version's output in screening logic — no single canonical RSI exists.

---

### 🟡 IND-6: `run_scheduler.py` is Single-Threaded — One Failed Job Blocks All Subsequent Jobs
**Location:** `scripts/run_scheduler.py`  
**Severity: MEDIUM**

The Python `schedule` library runs jobs sequentially in a single thread. The `run_live_preview.py` pipeline (which includes sequential Screener.in scraping for up to 100 symbols × 1–3.5s each = up to 350 seconds) could block the scheduler loop. If a job overruns its slot, the next scheduled job is delayed or skipped entirely. There is no job timeout, no threading, and no skipped-job alerting.

---

### 🟡 IND-7: Holiday List is Hard-Coded for 2026 Only
**Location:** `src/utils/holidays.py`  
**Severity: LOW-MEDIUM**

`HARDCODED_NSE_HOLIDAYS` only covers 2026. The sentinel fires every 15 minutes during market hours and uses `is_nse_holiday()` for gating. In 2027, the list expires silently — the sentinel will fire on NSE holidays, attempting live quotes that return empty. No startup warning is generated when the current year has no holiday data.

---

### 🟡 IND-8: `portfolio_allocation_pct` Stored Against Initial Capital, Not Current Equity
**Location:** `src/execution/order_manager.py:94`  
**Severity: LOW**

The stored `portfolio_allocation_pct` in the `positions` table is calculated as `(executed_price × qty) / ALGO_ALLOCATED_CAPITAL`. After a 20% portfolio drawdown, a ₹1L position is stored as "10% allocation" but represents 12.5% of actual current equity. The risk arbiter uses mark-to-market equity for sizing but the stored allocation percentage misleads any reporting or dashboard display.

---

## Part 5 — Audit Conflict Map (Audits Disagreeing With Each Other)

| Topic | Recheck v2 | DeepSeek | Chat | Ground Truth |
|---|---|---|---|---|
| AUC gate adequacy | "Model pre-dates gate" | "Gate of 0.53 too weak" | "Gate dangerously weak" | **AUC = 0.50** — model is random, gate irrelevant |
| Shariah fallback behavior | "Passes stocks" | Not addressed | "Passes stocks" | **Fails closed** on hard fallback; stale cache is real risk |
| Anti-trap shield completeness | "Layer 4 pledge never fires" | "Shield comprehensive ✅" then "pledge never fires ❌" | Not specific | **5/6 layers only** — pledge table empty |
| DB locking | Prior finding "#3" correct | C18: bypass confirmed | Not addressed | **Portalocker correctly implemented in session.py; only `run_db_maintenance.py` bypasses** |
| Second-opinion gate | "Orphaned function, inline gate uses same model" | Not directly | "Gate uses same model" | **Both correct AND new finding: conviction pre-seeded at 7.0** |
| DhanBroker status | "Structurally gated off" | "Needs live routing" | "Not ready" | **Completely non-functional — no HTTP calls at all** |
| Multi-agent analysis quality | N/A | N/A | Claims "14 specialist agents" | **Single AI roleplay — no adversarial independence** |

---

## Part 6 — Prioritized Action Plan

> [!NOTE]
> Ordered by impact × ease. Items in the same tier can be parallelized. Tier 0 is the minimum bar before any paper-to-live transition discussion.

### 🔴 Tier 0 — Fix Before Trusting Any System Output (This Week)

| # | Action | File | Effort |
|---|---|---|---|
| **T0-1** | Initialize `conviction_score: 0.0` (not 7.0) in AgentState | `run_live_preview.py:344` | 1 line |
| **T0-2** | Retrain XGBoost with `purged_kfold(n_splits=5, embargo=5)` on full dataset (not 100 rows) | `scripts/run_model_training.py` | 2–4 hours |
| **T0-3** | Fix train-serve benchmark skew: both training and inference must use same benchmark | `run_model_training.py` + `ml_features.py` | 2 hours |
| **T0-4** | Fix `interest_income_ratio` formula: `max(other_income, interest_income) / sales` | `ingestion/screener_scraper.py` | 15 min |
| **T0-5** | Fix VCP 52-week high/low to use actual OHLC high/low columns, not close | `screening/vcp_screener.py:227` | 30 min |
| **T0-6** | Add `symbol_sync.sync_instrument_master()` to scheduler at 06:00 AM | `scripts/run_scheduler.py` | 1 hour |
| **T0-7** | Wrap `run_db_maintenance.py` connection in portalocker harness | `scripts/run_db_maintenance.py` | 30 min |

### 🟠 Tier 1 — Fix This Month (Reliability & Correctness)

| # | Action | File | Effort |
|---|---|---|---|
| **T1-1** | **Pick ONE orchestrator.** Commit to `run_scheduler.py` or crontab. Delete the other. Update runbook. | `07_deployment_runbook.md` | Decision + 2h |
| **T1-2** | Wire `run_live_preview.py` to read from `macro_weather` table (with live fetch as fallback) | `scripts/run_live_preview.py` | 2 hours |
| **T1-3** | Add intraday `AWAITING_TRIGGER` polling daemon — check every 15min during market hours | `scripts/run_trigger_watcher.py` (new) | 3 hours |
| **T1-4** | Implement promoter pledge writer: scrape from Screener.in company page into `promoter_pledge_history` | `ingestion/screener_scraper.py` | 3 hours |
| **T1-5** | Make `init_db()` run unconditionally at every script entry point | `src/db/session.py` | 1 hour |
| **T1-6** | Consolidate ADTV participation caps into `strategy.yaml` alongside `liquidity_tiers` | `strategy.yaml` + `arbiter.py` | 1 hour |
| **T1-7** | Add Telegram alert when drawdown check itself fails (break the silent failure loop) | `scripts/run_drawdown_check.py` | 30 min |
| **T1-8** | Read `drawdown capital_base` from `settings.ALGO_ALLOCATED_CAPITAL`, not hardcoded | `scripts/run_drawdown_check.py:26` | 5 min |
| **T1-9** | Fix `market_regime` variable: create a single canonical `BenchmarkProvider` used by ALL modules | New `src/utils/benchmark_provider.py` | 2 hours |
| **T1-10** | Reduce fundamentals cache TTL or add Shariah-specific cache invalidation on quarter boundaries | `src/ingestion/screener_scraper.py` | 1 hour |
| **T1-11** | Add Telegram alert when bhavcopy Fyers fallback returns empty DataFrame | `src/ingestion/bhavcopy.py` | 30 min |
| **T1-12** | Update `HARDCODED_NSE_HOLIDAYS` for 2027 and add startup warning when year has no holiday data | `src/utils/holidays.py` | 1 hour |

### 🟡 Tier 2 — Next Month (Robustness & Intelligence)

| # | Action | Effort |
|---|---|---|
| **T2-1** | Build shared `portfolio_state.py` module — single source of truth for equity, drawdown, allocation | 1 day |
| **T2-2** | Add `correlation_guard.py`: reject new entry if avg pairwise 60-day Pearson corr with open positions > 0.65 | 4 hours |
| **T2-3** | Replace regex conviction parsing with structured JSON LLM output + Pydantic validation | 3 hours |
| **T2-4** | Implement VCP regime bypass rule: `if not regime_passed and rs_score > 15.0 and vol_dryup: allow with 50% size` | 1 hour |
| **T2-5** | Add triple-barrier labeling to training: upper=2×ATR, lower=1.5×ATR, time=5d | 4–8 hours |
| **T2-6** | Canonicalize RSI: pick ONE algorithm (EWM) and use it in all modules | 1 hour |
| **T2-7** | Filter `delisted_stocks` from universe query at pipeline start | `run_live_preview.py` | 30 min |
| **T2-8** | Implement `sector_capital` using `core_equity` (mark-to-market), not static ₹10L | `arbiter.py` | 1 hour |
| **T2-9** | Add per-provider LLM circuit breaking (5-min skip flag on timeout) | `agents/llm_gateway.py` | 2 hours |
| **T2-10** | Add model version hash logged at every inference call | `screening/ml_features.py` | 30 min |
| **T2-11** | Schedule `run_evaluator.py` weekly (currently dead code — not scheduled) | `run_scheduler.py` | 15 min |
| **T2-12** | Wire `run_feedback_loop.py` output into Bull/Bear agent prompt context | `agents/debate_graph.py` | 2 hours |

### 🔵 Tier 3 — Strategic Improvements (Quarter 2)

| # | Action |
|---|---|
| **T3-1** | Replace binary SMA50 regime filter with 3-state Gaussian HMM (calm/choppy/crisis) using `hmmlearn` |
| **T3-2** | Add full Indian transaction cost model (STT, stamp duty, exchange charges, GST, brokerage) to backtester |
| **T3-3** | Add portfolio-level volatility targeting: `L_t = min(1, σ_target / σ̂_p,t)` |
| **T3-4** | Add CPPI-style drawdown control instead of binary 6% halt |
| **T3-5** | Nightly DuckDB snapshot to Backblaze B2 / Cloudflare R2 (both free tier) |
| **T3-6** | Implement proper Shadow Mode A/B framework using the existing (but unused) `SHADOW_MODE` flag |
| **T3-7** | Add Deflated Sharpe Ratio + Probability of Backtest Overfitting (PBO) to evaluator |
| **T3-8** | Point-in-time fundamentals validation (filing-date aligned Shariah checks) |
| **T3-9** | Schedule periodic ML model retraining (monthly) with champion/challenger promotion gate |

---

## Part 7 — Things External Audits Got Wrong

> [!NOTE]
> Explicitly documenting audit errors so they are not acted upon incorrectly.

1. **"Prior finding #3 (DB locking) is correct"** (Recheck v2 lineage) → **FALSE.** Portalocker LOCK_SH/LOCK_EX was correctly implemented before the audit was written. The original finding was a false positive.

2. **"Anti-trap shield is comprehensive ✅"** (DeepSeek, Section 3 validation table) → **WRONG.** Layer 4 never fires. Same audit later contradicts this in N6.

3. **"Shariah scraping fallback silently passes non-compliant stocks"** (Chat + Recheck) → **PARTIALLY WRONG.** Hard fallback triggers `total_assets=0.0` → `INVALID_OR_ZERO_TOTAL_ASSETS` rejection. The system fails closed on hard fallback. Stale 7-day cache is the actual risk vector.

4. **"Multi-agent specialized team independently validated the system"** (Chat Audit Round 2) → **FALSE.** Single AI simulating 14 roles. No independent signal. Treat all Round 2 "consensus" findings with the same skepticism as Round 1 findings.

5. **"Effort: Purged K-Fold + triple-barrier labeling = 8 hours total"** (DeepSeek) → **LIKELY 2–4× UNDERESTIMATED.** Requires rewriting feature engineering, retraining, re-validating, updating model metadata format, and updating tests.

6. **"LLM fallback deterministic string produces conviction=5.0 which blocks trades"** (DeepSeek C6 framing) → **PARTIALLY WRONG.** The 5.0 default only activates if the judge node runs and the regex fails. If the graph errors before the judge node, the pre-seeded `conviction_score=7.0` passes the gate (IND-1 above).

---

## Part 8 — System Health Scorecard

| Domain | Score | Key Issue |
|---|---|---|
| **Architecture & Design** | 7/10 | LangGraph DAG is well-structured; deterministic risk primacy is excellent |
| **ML Model Quality** | 1/10 | AUC=0.50, 100 training rows — random noise |
| **Statistical Validation** | 2/10 | Single split, no K-Fold, train-serve benchmark skew |
| **Risk Management** | 5/10 | 9-layer stack conceptually strong; pledge layer dead, intraday drawdown blind |
| **Data Pipeline** | 4/10 | Good sources; Fyers fallback broken, macro snapshot unused, stale cache risks |
| **Operational Reliability** | 3/10 | Dual orchestrators, silent job failures, scheduler single-threaded |
| **Shariah Compliance** | 6/10 | First-class gate with correct fail-closed; formula bug + stale cache gap |
| **Execution Layer** | 5/10 | Paper broker correct; DhanBroker non-functional; silent approval bug dangerous |
| **Observability** | 3/10 | Good Telegram alerts; many job failures silent; dashboard status hardcoded |
| **Code Quality** | 6/10 | Well-structured; recurring "written but never consumed" pattern; dead tables |
| **Overall** | **4.2/10** | Architecturally promising, methodologically incomplete, not paper-to-live ready |

---

## Summary

AlphaSentinel is **architecturally ahead of most retail quant systems** — its deterministic risk arbiter with LLM-advisory-only design, Shariah-first filtering, circuit band awareness, and multi-layer anti-trap shield show genuine systems-engineering discipline.

However, the three audits collectively identified — and the ground-truth codebase confirms — that the system has a **deep layer of "written but never consumed" code**: the second-opinion function, the promoter pledge table, the agent memory table, the macro weather snapshot, the EOD risk offloader, the AWAITING_TRIGGER watcher, the delisted stocks survivorship guard, the Shadow Mode flag, the paper portfolios table, and the MCP server client. The system's documented capabilities substantially exceed its actual operating capabilities.

The single most critical finding across all four analyses: **the deployed XGBoost model is statistically random** (AUC=0.50, trained on 100 rows). Every ML-based decision in the system is currently noise. Combined with the pre-seeded `conviction_score=7.0` silent approval bug (IND-1), the system can approve trades without a genuine ML signal and without a genuine judge evaluation.

**Before any paper-to-live transition:** T0-1 through T0-7 are non-negotiable. T1-1 (orchestrator choice) must be resolved to know if risk controls are even reliably scheduled.

---

*Generated by Antigravity agent orchestration | 4 specialized subagents | 2026-09-22*

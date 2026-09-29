# AlphaSentinel — System Recheck & Improvement Report (v2)

## 0. Scope and method

This is a fresh code-level recheck, not a re-summary of the four documents already in `Audit docs/` (`AlphaSentinel_FixPack_and_Improvements.md`, `AlphaSentinel_System_Recheck_and_Improvement_Report.md`, and two DeepSeek exports). Those four were read in full first. Then, instead of taking their claims at face value, this pass re-verified each one against the actual current code — grepping every table/column/function they mention, and reading the real implementation of every script and module in `src/`, `scripts/`, and `dashboard/`.

**The single most important discovery of this recheck is that the codebase has moved on substantially since those four documents were written.** There is a test file, `tests/test_phase6_institutional_remediations.py`, explicitly named after a remediation phase, and its contents match: a large fraction of the prior P0/P1 findings have genuinely been fixed, and fixed well. Treating this system as "none of the fixes have landed" (which is what all four existing documents currently assume) would be inaccurate and would waste effort re-litigating solved problems.

At the same time, digging into *how* those fixes were implemented surfaced a new layer of issues — mostly seams between the newly-fixed pieces, rather than the original bugs themselves. That is the main content of this report.

Structure, per the request:
1. Status of prior findings (are they still valid?)
2. What is already good
3. What can still be improved (new findings)
4. New approaches worth considering
5. Risk/trade-off framing (folded into each item)
6. Priority verdict — what's worth doing

---

## 1. Status of prior audit findings

| # | Prior finding | Prior severity | Current status | Evidence |
|---|---|---|---|---|
| 1 | Three disconnected trade tables (`paper_portfolio`, `paper_trades`, `positions`); nothing ever wrote to `positions` | P0 / critical | **RESOLVED.** `order_manager.py` now writes exclusively to `positions`, with an idempotency guard against duplicate fills. `paper_trades` no longer exists anywhere in the code. `paper_portfolios` is still in `schema.sql` but is dead (no reads or writes) — cosmetic cleanup only. | `grep` for `INSERT INTO positions`, `paper_portfolio`, `paper_trades` across the repo |
| 2 | Anti-trap shield could be bypassed by an unvalidated ML probability override | P0 | **RESOLVED.** `run_live_preview.py` now treats an anti-trap failure as an unconditional hard block; the code comment literally says "ML Override disabled." | `scripts/run_live_preview.py` (candidate loop, anti-trap check) |
| 3 | `get_read_connection()`/`get_write_connection()` both take the same exclusive lock, serializing all reads behind writes | High | **Finding was incorrect / already resolved at the time of writing.** Current code uses `portalocker.LOCK_SH` for reads and `LOCK_EX` only for writes — a proper read/write-aware scheme. | `src/db/session.py` |
| 4 | Circuit band hardcoded to a flat 20% everywhere; real NSE circuit data never ingested | P1 | **Substantially resolved.** `bhavcopy.py` now tries to read real `UPPER_CIRCUIT`/`LOWER_CIRCUIT`/`CIRCUIT_BAND_PCT` fields, and only falls back to a series-based heuristic (5% for BE/BZ/SM, 20% for EQ) when they're missing. `run_live_preview.py` and `arbiter.py` now consume a real per-symbol value instead of a literal `20.0`. Residual caveat below (§3.10). | `src/ingestion/bhavcopy.py` lines ~99–129 |
| 5 | Flat ADTV liquidity floor mismatched between `vcp_screener.py` and `settings.py` (~30x inconsistency); tiering didn't exist | P1/P2 | **RESOLVED.** A single `liquidity_tiers` map now lives in `strategy.yaml` (LARGE/MID/SMALL/MICRO), consumed by `liquidity_guard.py`. `vcp_screener.py` no longer applies its own separate floor — liquidity filtering happens once, upstream, before VCP pattern evaluation. | `src/config/strategy.yaml`, `src/screening/liquidity_guard.py`, `src/screening/vcp_screener.py` |
| 6 | ML model never validated on held-out data; silent fallback to synthetic/random training data | **Called the single most important finding** | **RESOLVED, and done well.** `run_model_training.py` now does a chronological (not random) 80/20 split by date, with an explicit **5-day embargo gap** between train and test that matches the 5-day forward-return label horizon — this is a real purge/embargo, not just a naive split. It computes out-of-sample AUC and **refuses to serialize the model** if AUC ≤ 0.53 or is NaN. It writes a metadata sidecar (`xgboost_global_meta.json`) with training date, row count, and AUC. No synthetic-data fallback remains — insufficient/single-class data now raises loudly instead. | `scripts/run_model_training.py` lines 90–184 |
| 7 | Dashboard shows no Sharpe, drawdown, or win-rate | P1 (partially) | **Display-level fix landed; methodology issues remain (new, see §3.4/§3.5).** The dashboard now reads `dashboard/portfolio_metrics.json` and shows all three. `run_evaluator.py` was rewritten to query `positions` and compute them. But the specific math used has new problems described below. | `dashboard/app.py` lines 150–195, `scripts/run_evaluator.py` |
| 8 | Second-opinion gate is a polling daemon with a hardcoded `market_regime = 1` and a fabricated `sharpe_rank`, causing train/serve skew | Critical | **The underlying bug is genuinely fixed — but the fixed code is now disconnected from production (new finding, see §3.3).** `market_regime` is now computed from real Nifty data; `sharpe_rank` now uses the exact same formula as training (verified by `test_phase6...`). The daemon/polling architecture was replaced with a synchronous function, `evaluate_second_opinion()`. However, that function is called from nowhere except its own test file. | `src/screening/second_opinion_gate.py`, `src/screening/ml_features.py`, `grep evaluate_second_opinion` |
| 9 | `Telegram.is_system_halted()` fails **open** (returns `False`/not-halted) on a DB read error | Critical | **RESOLVED, and thoughtfully.** It now retries once after 0.5s, and if that also fails, explicitly returns `True` (halted) with a "failing closed for capital preservation" log line. | `src/notification/telegram_bot.py` lines 25–40 |
| 10 | EOD reconciliation contained a dead "shadow simulator" path keyed on a status string (`'APPROVE'`/`'APPROVE_WITH_WARNING'`) that never matched real position statuses | Medium | **RESOLVED** — that code path is gone; EOD reconciliation now operates uniformly on `positions.status IN ('OPEN','TARGET_1_TRIMMED')`. | `scripts/run_eod_reconciliation.py` |
| 11 | No portfolio-level drawdown circuit breaker exists at all | **Tier A, urgent** | **Partially built, not reliably wired (new finding, see §3.2).** `scripts/run_drawdown_check.py` now exists and does implement a halt check against `MAX_MONTHLY_DRAWDOWN_PCT`. But it is absent from the documented crontab in the deployment runbook, its "Monthly" framing doesn't match its actual all-time-high-water-mark logic, and its data source (`unrealized_pnl`) is only refreshed once a day. | `scripts/run_drawdown_check.py`, `.agency/.../07_deployment_runbook.md` |
| 12 | `evaluate_eod_risk_offload()` is fully implemented but never called from anywhere | Low/Medium | **Still valid, unresolved.** Confirmed zero call sites outside its own definition. | `src/risk/arbiter.py` line 281, `grep evaluate_eod_risk_offload` |
| 13 | Shariah promoter-pledge trend not checked (Priority 3) | Medium | **Partially implemented, still not gating (updated finding).** `screener_scraper.py` now computes `pledge_trend_3m` from a `promoter_pledge_history` table — but nothing ever inserts into that table, so the value is always 0 in practice, and `shariah_filter.py`'s `check_shariah_compliance()` still doesn't reference pledge data at all. | `src/ingestion/screener_scraper.py` lines 204–217, `src/screening/shariah_filter.py` (full read, no "pledge" reference) |
| 14 | Regime filter is a binary Nifty-500-vs-50DMA gate rather than a continuous blended score | Medium | **Still valid, unresolved.** `vcp_screener.py`'s `regime_passed` is still a hard True/False gate. | `src/screening/vcp_screener.py` lines 63–80 |
| 15 | Backtest harness uses a static 50/50 split with no embargo and no transaction-cost modeling | Medium | **Still valid, and now inconsistent with production (new angle, see §3.11).** `research/backtest_harness.py` is unchanged — no embargo, no walk-forward, no slippage model — while the live training script right next to it now has all three. | `research/backtest_harness.py` line 55 |
| 16 | No scheduled retraining cadence for the ML model | Medium | **Still valid, unresolved.** Not present in `run_scheduler.py`'s job list or the documented crontab. | `scripts/run_scheduler.py` |

**Bottom line on prior findings:** roughly two-thirds of the P0/P1 items are now resolved, several of them (the training validation gate especially) to a genuinely sophisticated standard. The remaining open items are accurately described in the existing documents and don't need to be re-derived here. What follows is new.

---

## 2. What is already good

Worth stating plainly, since a "be critical" brief can otherwise read as if nothing works:

- **The ML training gate is well-built.** Chronological split + 5-day purge/embargo matching the label horizon + an AUC floor that blocks shipping a bad model + fail-loud on insufficient data is a legitimate, textbook-correct defense against the two classic quant-ML failure modes (look-ahead leakage and silently shipping noise). This is better than what a lot of small trading systems have.
- **`order_manager.py`'s idempotency guard** (checks for an existing OPEN position on the same symbol before inserting a new one) is good defense-in-depth — it happens to also mitigate the worst-case consequence of the dual-scheduler problem below (duplicate trades), even though it wasn't necessarily designed with that in mind.
- **The circuit-halt fail-closed logic** (`is_system_halted()`) is a genuinely careful piece of code: retry-then-fail-closed is the right shape, better than either "fail closed immediately on any hiccup" (too trigger-happy) or "fail open" (dangerous).
- **The judge LLM's conviction-score parsing** defaults to a neutral **5.0** (below the 7.0 approval gate) if the model's output can't be parsed — not 0, not 10, not a crash. That's a deliberately safe default, and it's the kind of detail that's easy to get wrong.
- **`risk_router`'s cost gate** — skip the entire multi-agent LLM debate if the deterministic risk arbiter already rejects the setup — is a sensible, cheap cost control that's easy to overlook.
- **The sector cap logic in `arbiter.py`** now checks not just open positions but same-day pending `screener_candidates` too, which closes a same-day race condition (two candidates in the same sector both getting approved in one run before either lands in `positions`). It also enforces a 25% sector-capital cap in addition to a position-count cap.
- **The "equity insolvency" and cash-floor guards** in `arbiter.py` (reject new trades if core equity ≤ 0, or if available cash would drop below 5%) are a real, if basic, portfolio-level safety net that goes beyond per-trade risk sizing.
- **`liquidity_guard.py`'s real-time bid-ask spread check** (reject if spread > 2% via the Fyers quote) is a genuine execution-quality safeguard that none of the four prior documents mention.
- **The Dhan live-broker integration is safe by construction.** `DhanBroker.place_order()` never actually reaches Dhan's API — it logs the would-be payload and routes the trade through the paper simulator regardless, with an explicit "never default to a hardcoded fallback security ID" guard. Live capital risk is structurally impossible today even if `EXECUTION_ENV` were flipped by mistake.
- **`run_scheduler.py`'s subprocess-per-job model** (each job runs as `subprocess.run([sys.executable, script_path])` rather than as an in-process function call inside a long-running daemon) is a good architectural choice: fresh interpreter, fresh module-level caches, one job's crash can't take down the scheduler or leak state into the next job.

---

## 3. New findings — what can still be improved

These are things none of the four existing documents identify, surfaced by reading the actual current implementation rather than the design docs.

### 3.1 Two competing, mutually undocumented orchestrators (highest-value single finding)

`scripts/run_scheduler.py` is a full "Master Autonomous Scheduler Daemon" built on the Python `schedule` library. It schedules premarket, sentinel, live-preview, EOD reconciliation, drawdown check, DB maintenance, and monthly purification — including three jobs (`run_drawdown_check.py`, `run_db_maintenance.py`) that the deployment runbook says are never scheduled at all.

The problem: **`run_scheduler.py` does not appear anywhere in `07_deployment_runbook.md`, and the runbook's own crontab (5 cron entries + 2 systemd services) has zero awareness of it.** `schedule` is a declared dependency in `requirements.txt`, so this isn't abandoned scratch work — it's real, intentional code that was simply never reconciled with the deployment documentation. This leaves the system in one of two states, and it's impossible to tell which from the code alone:

- **Only the crontab is deployed** → the drawdown breaker, DB maintenance, and the weekly feedback loop this scheduler doesn't even include never run at all.
- **Both are deployed** → core jobs (`run_premarket.py`, `run_live_preview.py`, `run_eod_reconciliation.py`, `run_sentinel.py`) fire twice at slightly different times each day (e.g. live preview at 15:15 in both, but EOD reconciliation at 18:00 via cron vs. 18:30 via the scheduler) — doubling LLM API spend, doubling Telegram messages, and creating a real (if partially mitigated by the idempotency guard) DB write-contention risk.

**Fix:** pick one. Given `run_scheduler.py` is strictly more complete (it's the only place `run_drawdown_check.py` and `run_db_maintenance.py` are wired up at all), the natural choice is to retire the crontab, run `run_scheduler.py` as the one systemd service, and update the deployment runbook to match. This is a documentation-and-decision task, not a code-writing task — cheap, and it resolves several downstream findings below for free.

### 3.2 The drawdown circuit breaker: real but currently unreliable

Layering on top of §3.1: even assuming `run_scheduler.py` is what's live, `run_drawdown_check.py` has its own issues:

- It computes a `start_of_month` variable and then **never uses it.** The function is described as a "Monthly Drawdown Circuit Breaker" and reads `MAX_MONTHLY_DRAWDOWN_PCT`, but what it actually computes is drawdown from an **all-time high-water-mark**, never reset monthly. That's a legitimate risk metric, but it's not what the name or the config key says it is — worth either renaming the setting to `MAX_LIFETIME_DRAWDOWN_PCT`, or actually implementing a monthly reset if that was the intent.
- Its equity calculation sums `realized_pnl` (all statuses) plus `unrealized_pnl` (open positions). `unrealized_pnl` on `positions` is **only refreshed once per day, at 18:30 by `run_eod_reconciliation.py`** — `run_sentinel.py`, which runs every 15 minutes during market hours, updates `current_ltp` and trailing stops but never touches `unrealized_pnl`. As currently sequenced in `run_scheduler.py` (EOD recon 18:30 → drawdown check 19:00) this happens to work out fine same-day. But it means the breaker has **no intraday visibility** — a sharp intraday move that reverses by end-of-day would never be seen, and if the sequencing ever drifts (manual runs, schedule changes), the breaker would silently evaluate stale data.
- Any failure inside the script (e.g. a missing column from an unapplied migration — see §3.6) is caught by a bare `except Exception` and only logged, not escalated to Telegram. A broken drawdown breaker fails **silently**, which is the worst way for a safety mechanism to fail — it *looks* like it's working (the job "succeeds") while structurally providing no protection.

### 3.3 The properly-fixed second-opinion model is orphaned; production uses a weaker substitute

This is the most interesting single finding. The old `second_opinion_gate.py` (train/serve skew, `market_regime` hardcoded to 1, polling daemon) has genuinely been rewritten and fixed: it now shares `ml_features.py` with the training pipeline (confirmed identical `sharpe_rank`/`market_regime` formulas via `test_phase6...`), runs synchronously, and fails closed on insufficient data (`len(df) < 50`).

But `evaluate_second_opinion()` is called from **nowhere** except its own test file. Instead, `run_live_preview.py` implements its own, different "gate" inline:

```python
gate_approved = (conviction >= 7.0) and (ml_prob > 0.50)
```

`ml_prob` here is the **same** Pass-1 probability from `ml_predictor.py` — and `second_opinion_gate.py`'s `MODEL_PATH` points at the same `xgboost_global.pkl`. So even where the two do overlap conceptually, they were never actually two independent models. The net effect: the entire "second, independently-trained model cross-checking the first" concept — which is what makes a "second opinion" statistically meaningful rather than just re-asking the same model — has quietly been dropped in favor of "require the LLM judge to also agree." That's not unreasonable as a design on its own, but it:
1. Loses the data-sufficiency safeguard (`len(df) < 50`) that only exists in the orphaned function.
2. Leaves genuinely good, tested code sitting dead in the repo, which is exactly the "written but never consumed" pattern the prior System Recheck report already flagged elsewhere (its §3.5) — this is a fresh, larger instance of the same habit.

**This needs a decision, not just a code change:** either (a) retire `second_opinion_gate.py` and its test file, since it's not actually providing model diversity, and rename the inline check honestly as a "dual-consensus" gate rather than a "second opinion," or (b) actually train a second, differently-specified model (different features, different algorithm, or a different training window) and wire `evaluate_second_opinion()` in for real. Option (a) is nearly free; option (b) is more work but is the only way to get the statistical benefit the original design intended.

### 3.4 Three mutually inconsistent "drawdown" numbers in the same codebase

- `run_drawdown_check.py`: **percentage** drawdown from an all-time-high **total equity** (capital base + realized + unrealized PnL).
- `run_evaluator.py`: **absolute rupees**, computed only from the **cumulative realized PnL of closed trades** — ignores open positions and the capital base entirely.
- `research/backtest_harness.py`: a third, presumably equity-curve-based methodology used only in offline research.

If someone reads "Max Drawdown: ₹5,000" on the dashboard and mentally checks it against the "halt if drawdown > 6%" circuit breaker rule, they're comparing two numbers that don't share a denominator, an inclusion set, or even a unit. This is the exact "signals computed independently that can disagree" anti-pattern the System Recheck report already flagged once (its §3.6, on duplicated holiday-checking logic) — it has recurred, in a more consequential place, in code written specifically to fix an earlier version of the same underlying problem. That's a signal about the codebase's habits, not just this one metric: **there's no single shared "portfolio state" module that Sharpe/drawdown/exposure calculations all pull from**, so every new consumer reinvents its own version.

### 3.5 The evaluator's "Sharpe Ratio" isn't a Sharpe ratio in the conventional sense

`run_evaluator.py` computes `mean(per-trade return %) / std(per-trade return %)` across closed trades, with no annualization and no time-indexing. A genuine Sharpe ratio is computed on a **periodic (e.g. daily) equity-curve return series** and annualized (typically × √252). Per-trade dispersion and annualized time-series dispersion are not the same statistic and don't sit on the same scale — a strategy that trades rarely with fat per-trade returns can show a deceptively high "trade Sharpe" that would look mediocre as a real annualized Sharpe, and vice versa. Labeling this number "Sharpe Ratio" on the dashboard risks the reader benchmarking it against the conventional "Sharpe > 1 is good" heuristic, which doesn't apply here. This is fixable cheaply by reusing whatever equity-curve methodology `backtest_harness.py` already has (once that itself is put on solid footing — see §3.11) rather than a bespoke per-trade formula.

### 3.6 The schema-migration mechanism is fragile and easy to silently skip

`init_db()` contains six incremental "non-destructive migration" blocks (adding columns like `debate_transcripts`, `bhavcopy_daily.upper_circuit`, `circuit_breaker_state.high_water_mark`, etc.) — but it is **only invoked from `get_read_connection()`/`get_write_connection()` when the database file doesn't already exist.** Once a DB file exists in production, `init_db()` never runs again automatically; the deployment runbook's step 4 (manually running `python -c "from src.db.session import init_db; init_db()"`) is a one-time, easy-to-forget instruction. Every column added going forward depends on someone remembering to do this again after every deploy. Given `init_db()`'s statements are already fully idempotent (`IF NOT EXISTS` / explicit column-existence checks), the safe fix is nearly free: call it unconditionally at the top of every script's entry point (or once at scheduler startup) instead of gating it behind "file doesn't exist." The overhead is a handful of `PRAGMA table_info` calls — negligible next to the risk of a script silently querying a column that was never added to a live database (which, per the bare `except Exception` pattern seen throughout, tends to fail silently rather than loudly).

### 3.7 `run_db_maintenance.py` bypasses the shared locking layer

Every other read/write path in the system goes through `src/db/session.py`'s `get_read_connection()`/`get_write_connection()`, which coordinate via a `portalocker` file lock. `run_db_maintenance.py` instead opens a **raw** `duckdb.connect(str(db_path))` directly, runs `PRAGMA force_checkpoint` and `VACUUM`, and closes it — without ever touching the shared lock. The code's own comment acknowledges the risk ("Requires exclusive access, so ensure no queue writers are active") but nothing enforces it. In practice this is scheduled for 01:00 AM on a day nothing else should be running, so today's real-world risk is low — but it's the one place in the codebase that could actually corrupt or deadlock the database, precisely because it's the one place that doesn't use the shared abstraction everything else was built around. Cheap fix: acquire the same exclusive `portalocker` lock (or route through `get_write_connection()`) before connecting.

### 3.8 Tier-based risk knobs are split across two different places — the exact anti-pattern that caused the original bug

The original ADTV mismatch (prior finding #5) happened because liquidity thresholds lived in two disconnected places that drifted apart. That's now fixed for liquidity floors (`strategy.yaml`'s `liquidity_tiers`). But `arbiter.py`'s per-tier **ADTV participation caps** (5% for LARGE, 2% MID, 1% SMALL, 0.5% MICRO) are hardcoded directly in Python, in a completely different location from `strategy.yaml`'s tier definitions, with `strategy.yaml`'s own `max_adtv_participation_pct` only used as an obscure fallback for unrecognized tier strings. This is a smaller-scale recurrence of exactly the pattern that caused the earlier, more severe bug — worth consolidating into one place (extend `liquidity_tiers` in `strategy.yaml` into a dict of `{floor, adtv_participation_pct}` per tier) before it drifts the same way.

### 3.9 Unknown provenance for the currently-shipped model

The new training pipeline is solid, but it's prospective. There is no `xgboost_global_meta.json` anywhere in the repository, while `xgboost_global.pkl` is present — meaning **the currently-deployed model was very likely trained before the validation-gate code existed**, and nobody can currently answer "did the live model actually clear the 0.53 AUC bar?" from what's on disk. This isn't a code bug, but it is a live operational gap: the new safety gate only protects models trained *from now on*. Recommend triggering one retrain run under the current code specifically to backfill this provenance before relying on the "validated model" claim for the model currently in production.

### 3.10 Circuit-band synthesis is a coarse two-bucket fallback

The series-based fallback (5% for BE/BZ/SM, 20% for everything else) is a reasonable default, but it's binary — it can't represent the 2% and 10% circuit bands NSE actually applies to specific stocks under ASM/GSM surveillance. This only matters in the (unverified from the code alone) case where the real `UPPER_CIRCUIT`/`CIRCUIT_BAND_PCT` fields are rarely or never present in the actual ingested Bhavcopy source — worth a quick empirical check of the last few weeks of ingested data (`SELECT COUNT(*) FROM bhavcopy_daily WHERE upper_circuit IS NOT NULL` vs total) to see how often the fallback is actually being exercised in practice, since that determines whether this is a live gap or a dormant one.

### 3.11 The backtest harness didn't inherit the rigor added to live training

`run_model_training.py` now has a proper embargo/purge and a validation gate. `research/backtest_harness.py`, sitting right next to it, still uses a static 50/50 split with no embargo and no transaction-cost/slippage modeling. These two pieces of code answer closely related questions (does this strategy actually work?) with inconsistent rigor — whatever backtest numbers justified the strategy in the first place were produced under weaker methodology than what now gates the live model.

### 3.12 No alerting on scheduler job failures

`run_scheduler.py` logs failed jobs (non-zero exit code, timeout) to a local failure log but never pushes to Telegram — the system's own primary notification channel for everything else (trade cards, halt state). A crashed `run_eod_reconciliation.py` or `run_drawdown_check.py` job is currently only discoverable by manually reading log files or the dashboard's log tab.

### 3.13 Minor: dashboard status label is not derived from anything

`dashboard/app.py` hardcodes `"🟢 SYSTEM STATUS: ACTIVE (CRON RUNNING)"` whenever the system isn't halted — a static string, not a heartbeat check against either orchestration mechanism. Combined with §3.1, this means the one piece of UI a human would check to confirm "is anything actually running" can't actually tell them that.

### 3.14 Web UI export tab still fabricates some fields

The `tab3` manual-export payload now correctly pulls real `trigger_price`, `adtv_20d`, and `circuit_band` from the selected candidate — an improvement over before. But `current_price` is still synthetically derived as `trigger_price * 0.99` rather than the stock's actual current price, and `fundamentals` is a hardcoded generic dict (`pe_ratio: 21.0, sector_pe: 30.0, ...`) regardless of which stock is selected. Low severity (this is a manual/fallback export path, not the live pipeline), but worth finishing now that the real data is already one query away.

---

## 4. New approaches worth considering

These go beyond fixing what exists, per the brief's ask to look past the current approach.

- **A single shared "portfolio state" module.** One function that computes current equity, drawdown (defined once, consistently), and exposure, called by `run_drawdown_check.py`, `run_evaluator.py`, `arbiter.py`'s sector-capital check, and the dashboard, instead of four independent SQL queries against `positions`. Directly resolves §3.4, and prevents the next version of that bug.
- **Purged / walk-forward cross-validation in the backtest harness** (the López de Prado "combinatorial purged cross-validation" style already alluded to conceptually in the training script's embargo logic), extended from a single split to multiple rolling folds. More expensive to compute, but gives a distribution of out-of-sample performance rather than one point estimate — meaningfully more informative for deciding whether the strategy is real.
- **A job-runner wrapper with built-in Telegram alerting**, used by both entry points (whichever orchestrator is kept) — a thin decorator around each script's `main()` that catches exceptions, logs, and pushes a Telegram alert on failure. Removes the need to hand-roll error handling per script and closes §3.12 for every job at once, including future ones.
- **Fractional-Kelly position sizing as an overlay**, not a replacement, on the existing ATR-based risk sizing. Right now sizing is purely risk-per-trade (fixed % of capital at the stop-loss distance) with no reference to the edge (win rate × payoff ratio) the ML model or historical trade log implies. A conservative (e.g. quarter-Kelly) overlay, capped by the existing ATR/ADTV/circuit-band limits (never loosening them, only ever tightening), would let position size respond to *conviction* as well as *volatility* — something the current design doesn't do at all. No Kelly logic exists in the codebase today.
- **A continuous regime score instead of the binary Nifty gate** (already flagged in the existing System Recheck report — reinforcing it here because §3.11's backtest gap makes it more urgent: a binary regime flag is one more place where a static threshold can be back-tested to look good in-sample without being robust out-of-sample).
- **GARCH-family volatility forecasting** as an input to the ATR stop-loss and position sizing, in place of (or alongside) realized historical ATR. Realized ATR is backward-looking by construction; a simple GARCH(1,1) forecast captures volatility clustering (today's vol is a better predictor of tomorrow's vol than a 14-day trailing average) and would make stop distances and sizing more responsive heading into a volatility regime change rather than after one. This is a genuine methodological upgrade, not just a bug fix — no prior document proposed this specific technique.
- **Provider-level circuit breaking in the LLM gateway.** The current waterfall retries the same ordered list of three providers on every single call. If Gemini is down for an hour, every call in that hour still tries Gemini first and waits out its 15s timeout before falling back — burning latency (and, if the underlying API meters failed calls, possibly quota) for no benefit. A short-lived (e.g. 5-minute) per-provider "skip this one, it just failed" flag would remove that cost with minimal complexity.

---

## 5. Priority verdict — what's worth doing

**Tier A — do this month (cheap, high value, mostly decisions + wiring, not new algorithms):**
1. Resolve the dual-orchestrator ambiguity (§3.1) — pick `run_scheduler.py`, retire the crontab, update the runbook. This one decision also fixes the "drawdown check isn't scheduled" and "DB maintenance isn't scheduled" complaints from the prior audits, for free.
2. Fix the drawdown breaker's "Monthly" mislabeling and add a Telegram alert on its own failure (§3.2).
3. Wrap `run_db_maintenance.py`'s connection in the shared locking module (§3.7) — small, removes the one real corruption risk in the codebase.
4. Make a real decision on the second-opinion gate (§3.3): retire the orphaned code and rename the inline check honestly, or commit to training a genuinely independent second model. Leaving it as-is (well-built code nobody calls) is the worst of the three options.
5. Make `init_db()` idempotent-and-always-run rather than run-once-if-missing (§3.6) — a few lines, removes an entire class of future "forgot to migrate prod" bugs.
6. Consolidate the tier-based ADTV participation caps into `strategy.yaml` alongside `liquidity_tiers` (§3.8) — prevents a second version of the original bug.

**Tier B — worth doing, less urgent:**
- Build the shared portfolio-state/metrics module and point the evaluator, drawdown check, and dashboard at it (§3.4/§3.5) — turns three inconsistent numbers into one trustworthy one.
- Bring the backtest harness up to the same embargo/walk-forward standard as the now-fixed training script (§3.11).
- Schedule periodic model retraining, and backfill provenance for the currently-shipped model (§3.9/prior §16).
- General job-failure alerting wrapper (§3.12/new approach).
- Finish the manual export tab's remaining fake fields (§3.14) — low effort, low value, but cheap to close out.

**Tier C — good ideas, not urgent (bigger lift, real but secondary value):**
- Fractional-Kelly sizing overlay.
- GARCH-based volatility forecasting for stops/sizing.
- Continuous multi-factor regime scoring in place of the binary gate.
- Purged walk-forward cross-validation (multi-fold) in the backtest harness.
- Provider-level circuit breaking in the LLM gateway.

**Explicitly not worth doing right now:**
- The genetic-programming "Alpha Discovery V2" factory proposed in the DeepSeek documents. The prior FixPack already correctly scoped this out until the paper-trading validation period produces real performance data — that reasoning still holds, and arguably holds *more* strongly now, since several of the metrics (Sharpe, drawdown) that would be needed to judge whether a new alpha factory is even necessary are only now becoming trustworthy (once §3.4/§3.5 are fixed).
- Enabling live Dhan execution. It's correctly gated off today; nothing in this recheck changes that assessment, and the drawdown breaker (the thing that would need to be bulletproof before real capital is at risk) is itself not yet reliably wired in (§3.2).
- Vectorizing the mean-reversion screener for speed. At the current universe size this isn't a bottleneck; revisit only if the tradable universe grows an order of magnitude.

# AlphaSentinel Shariah Indian CNC Swing Trading System
# End-to-End (E2E) Test Infrastructure & Quality Assurance Specification

> **System**: AlphaSentinel Institutional Cash Equities Swing Engine (`NSE:EQ` Delivery Only)  
> **Regulatory Basis**: SEBI April 1, 2026 Regulations + AAOIFI / Justice Mufti Muhammad Taqi Usmani Shariah Total-Assets Framework  
> **Architecture**: Fully Deterministic End-of-Day (EOD) Pipeline (19:00 Bhavcopy -> 19:15 Screener -> 19:30 Guardian -> 08:45 2FA -> 08:50 Morning Digest)  
> **Document Owner**: E2E Test Suite Architect (`teamwork_preview_test_writer_e2e`)  
> **Target Status**: Institutional-Grade Verification Harness  

---

## 1. Testing Methodology

The AlphaSentinel test suite implements a 4-tier opaque-box quality assurance framework combining four formal software testing methodologies:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           ALPHASENTINEL 4-TIER E2E TEST HARNESS               │
├───────────────────┬───────────────────────────────────┬───────────────────────┤
│ Tier              │ Methodology                       │ Focus Area            │
├───────────────────┼───────────────────────────────────┼───────────────────────┤
│ Tier 1: Features  │ Category-Partition Method         │ Feature Isolation     │
│ Tier 2: Boundary  │ Boundary Value Analysis (BVA)     │ Extremes & Discontinuity│
│ Tier 3: Cross     │ Pairwise Combinatorial Testing    │ Multi-Feature Cohesion │
│ Tier 4: Workloads │ Real-World Workload Simulation    │ E2E Production Cycles │
└───────────────────┴───────────────────────────────────┴───────────────────────┘
```

### 1.1 Category-Partition Method (Ostrand & Balcer)
Each functional feature $F_i$ is systematically partitioned into functional categories:
1. **Input Parameters**: Trigger prices, ATR volatility, base lows, financial ratios, market regime scores, benchmark series.
2. **Environmental State**: Portfolio cash buffer, existing positions heat, Demat settlement state, corporate action registry, benchmark trend.
3. **Equivalence Classes**: Valid partitions where the system is expected to behave uniformly (e.g., stops in $[0\%, 8\%]$, debt ratio in $[0\%, 33\%]$).
4. **Partition Choices**: Explicit selections tested in isolation to verify deterministic state transitions and mathematical correctness.

### 1.2 Boundary Value Analysis (BVA)
Quantitative trading engines fail at numerical and state boundaries. BVA tests the exact mathematical edges:
- **Stop-loss limit**: $7.99\%$, $8.00\%$, $8.01\%$.
- **Price jump tripwire**: $24.99\%$, $25.00\%$, $25.01\%$.
- **Portfolio heat limit**: $4.99\%$, $5.00\%$, $5.01\%$.
- **Shariah ratio gates**: Debt/Assets at $32.99\%$, $33.00\%$, $33.01\%$; Impure income at $4.99\%$, $5.00\%$, $5.01\%$; Net Liquid Assets vs Market Capitalization equality.
- **Settlement calendar**: Trade date ($T_0$), Next trading day ($T_1$), Demat credit morning ($T_2$), weekend boundaries, and official exchange holidays.

### 1.3 Pairwise Combinatorial Testing
Single-feature tests often fail to catch multi-module side effects. Pairwise combinatorial testing verifies orthogonal interactions across independent dimensions:
- Market Regime (`RISK_ON`, `NEUTRAL`, `RISK_OFF`) $\times$ Sizing Factor ($1.0\%$, $0.5\%$, $0.0\%$).
- Settlement State (`SETTLING_T0_T1`, `SETTLED_DEMAT`) $\times$ Exit Priority Rules ($P_1$ through $P_9$).
- Data Quality (Clean Bhavcopy, Corrupted Price Jump) $\times$ Screener Admission (Quarantined vs Filtered).
- Universe Compliance (Verified Shariah, Non-compliant Drift) $\times$ Risk Allocation & Purification.

### 1.4 Real-World Workload Testing
Realistic temporal simulations recreate the exact cron schedule of the trading system:
1. **19:00 IST**: Bhavcopy ingestion with data sanitization, delivery %, and $>25\%$ price jump quarantine tripwire.
2. **19:15 IST**: Deterministic 3-point Market Regime evaluation and offline Minervini VCP + Beta-Stripped Residual Momentum screening.
3. **19:30 IST**: Nightly Holdings Guardian audit, Demat reconciliation, T+2 Qabd settlement enforcement, and 9-rule priority exit evaluation.
4. **08:45 IST**: Next morning SEBI 2FA token refresh simulation.
5. **08:50 IST**: Morning Telegram Digest generation producing 60-second manual FYERS App trade cards and 365-day GTT OCO alerts.

---

## 2. Feature Inventory & Coverage Mapping

The test harness provides comprehensive coverage for all 13 core features enumerated in `PROJECT.md § Feature Inventory`:

| Feature ID | Feature Name | Requirement | Description | Target Milestone |
|:----------:|:-------------|:-----------:|:------------|:----------------:|
| **F1** | Volatility-Adjusted Risk Parity Math | R1 | Unchoke 1.0% risk by raising `max_position_size_pct: 16.0`, `max_pct_stop: 8.0`, structural stop `Stop = max(Base_Low_10d - 0.25*ATR_14, Trigger - 2.5*ATR_14)`, and 5.0% portfolio heat ceiling in `arbiter.py` & `strategy.yaml`. | M1 |
| **F2** | Settlement Tracking DB Migration | R2 | Create `003_settlement_tracking.sql` adding `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr` to `positions`, and creating `guardian_log` table in DuckDB. | M2 |
| **F3** | FYERS Client Auth & Demat Extensions | R2, R4 | Implement `scripts/fyers_auth.py` (08:45 IST refresh), dynamic `reload_token()` (mtime check), `get_holdings()`, and `get_positions()` in `fyers_client.py`. | M2, M4 |
| **F4** | T+2 Qabd Settlement State Machine & Holdings Guardian | R2 | Build `src/portfolio/fyers_guardian.py`: enforce `can_exit = False` on T0/T1, transition to `SETTLED_DEMAT` on Day 2 morning with 365-day GTT OCO alert, 19:30 IST audit reconciliation, manual Demat buy import, and 9-rule priority exit hierarchy (P1-P9). | M2 |
| **F5** | Screener Intraday Decoupling & Bear Bypass Removal | R3 | In `src/screening/vcp_screener.py`, remove live intraday quote fetching (lines 51-59) for 100% Bhavcopy run, permanently remove bear-market bypass (lines 244-250) so `RISK_OFF` produces 0 buys, update tests. | M3 |
| **F6** | Deterministic Regime Engine | R3 | Build `src/screening/regime_engine.py`: 3-point breadth score (Nifty 500 > SMA50, SMA50 > SMA200, % Halal EQ > SMA50 > 50%). Score 3 = `RISK_ON` (1.0% risk), Score 2 = `NEUTRAL` (0.5% risk), Score <= 1 = `RISK_OFF` (0% risk, zero buys). | M3 |
| **F7** | ML Decoupling to Non-Blocking Shadow Logging | R4 | In `scripts/run_live_preview.py:597`, remove `and (ml_prob >= ml_cutoff)` from `gate_approved`; keep XGBoost as non-blocking shadow telemetry logged to DB and console. | M4 |
| **F8** | Deprecations & 08:50 Morning Digest Trade Cards | R4 | Deprecate `run_sentinel.py`, `dhan_broker.py`, and 15:15 rush from `run_scheduler.py`. Format 08:50 IST Morning Telegram Digest trade cards for 60-second manual FYERS entry. | M4 |
| **F9** | Bhavcopy Price Jump Quarantine Tripwire | R5 | Add >25% unexplained price jump quarantine tripwire to `src/ingestion/bhavcopy.py`. | M5 |
| **F10** | Data Spine Backfill (>=250 Trading Days) | R5 | Backfill `bhavcopy_daily` in `alphasentinel.duckdb` to >= 250 consecutive trading days without unadjusted >25% discontinuities. | M5 |
| **F11** | Offline Shariah Universe Sync Script | R5 | Create `scripts/sync_shariah_universe.py` populating DuckDB `shariah_universe` from `fundamentals_cache` (367 stocks) using 6 Mufti Taqi Usmani gates (>= 350 verified stocks). | M5 |
| **F12** | Beta-Stripped Residual Momentum | R6 | Add vectorized 60-day OLS against Nifty 500, cumulative 30-day idiosyncratic residual over residual std dev (<100ms), requiring >= 70th percentile of Halal universe in `vcp_screener.py`. | M6 |
| **F13** | LightGBM LambdaRank Signal Upgrade | R6 | Design Phase 2 LightGBM LambdaRank cross-sectional ranker (forward 5-day deciles, NDCG@3) to output Top 3 setups each evening. | M6 |

---

## 3. Exact Coverage Thresholds

The E2E Test Suite enforces the following quantitative quality gates across the repository:

| Tier | Suite Path | Focus | Minimum Target | Actual Target in Suite |
|:----:|:-----------|:------|:--------------:|:----------------------:|
| **Tier 1** | `tests/e2e/test_tier1_features.py` | Feature Isolation (Happy Path) | $\ge 5$ tests per feature ($F_1 - F_{13}$) | **$\ge 65$ test cases** |
| **Tier 2** | `tests/e2e/test_tier2_boundaries.py` | Boundary Value Analysis & Edge Cases | $\ge 5$ boundary tests per feature ($F_1 - F_{13}$) | **$\ge 65$ test cases** |
| **Tier 3** | `tests/e2e/test_tier3_cross_feature.py` | Pairwise Combinatorial Interactions | All key feature pairings | **$\ge 15$ test cases** |
| **Tier 4** | `tests/e2e/test_tier4_workloads.py` | Real-World Production Workloads | $\ge 5$ complete lifecycles | **$\ge 5$ comprehensive scenarios** |
| **Total** | Master Suite Runner | Unified Suite | Robust Coverage | **$\ge 150$ total test cases** |

---

## 4. Test Infrastructure Architecture & Execution Harness

### 4.1 Master Test Runner (`tests/test_e2e_suite.py`)
The suite provides a rich CLI runner that can execute all tiers or individual tiers with structured reporting:
```bash
# Run entire 4-tier E2E suite with summary reporting
python tests/test_e2e_suite.py

# Run specific tier
python tests/test_e2e_suite.py --tier 1
python tests/test_e2e_suite.py --tier 2
python tests/test_e2e_suite.py --tier 3
python tests/test_e2e_suite.py --tier 4

# Run via standard pytest
pytest tests/e2e/ -v
```

### 4.2 Database Isolation & In-Memory DuckDB Engine
- In accordance with `tests/conftest.py`, running E2E tests will never dispatch HTTP requests to live Telegram servers and will never pollute production DuckDB tables.
- All E2E test suites leverage dedicated in-memory DuckDB connections (`duckdb.connect(":memory:")`) or isolated test tables to guarantee test independence and concurrency safety.
- Tables are initialized with canonical schemas identical to `src/db/schema.sql` and `003_settlement_tracking.sql`.

### 4.3 Deterministic Broker & Mock Adapters
- External FYERS REST API calls (`get_holdings`, `get_positions`, `reload_token`, `get_live_quotes`) are mocked using deterministic test doubles providing canonical responses.
- Real-time network calls are explicitly forbidden during screening; all screening operates purely on EOD Bhavcopy data.

### 4.4 Shariah & SEBI Compliance Assertions
Every test adheres to institutional compliance principles:
1. **SEBI Cash Equities (`NSE:EQ`) Delivery Rule**: Margin leverage is zero. Positions must be 100% funded in cash.
2. **SEBI T+1 / T+2 Settlement Cycle**: Shares purchased on Day $T_0$ settle into Demat on $T_1$ night. Legal constructive possession (*Qabd*) is recognized on $T_2$ morning. Exits on $T_0$ and $T_1$ are prohibited.
3. **Justice Mufti Muhammad Taqi Usmani 6-Gate Compliance**:
   - Primary business activity must be permissible.
   - $\text{Total Debt} / \text{Total Assets} \le 33.0\%$.
   - $(\text{Cash} + \text{Interest Investments}) / \text{Total Assets} \le 33.0\%$.
   - $\text{Impure Income} / \text{Total Revenue} \le 5.0\%$.
   - $\text{Illiquid Assets} / \text{Total Assets} \ge 20.0\%$ (and $\text{Receivables} / \text{Total Assets} \le 49.0\%$).
   - $\text{Net Liquid Assets} \le \text{Market Capitalization}$.
4. **Shariah Drift (Rule P9)**: Held stocks that fail subsequent quarterly syncs trigger Telegram warnings only; forced distress liquidation is strictly avoided.

---

## 5. Traceability Matrix

| Feature | Tier 1 (Features) | Tier 2 (Boundaries) | Tier 3 (Cross-Feature) | Tier 4 (Workloads) |
|:--------|:------------------|:--------------------|:-----------------------|:-------------------|
| **F1** (Risk Parity & Stop) | `test_t1_f1_*` | `test_t2_f1_*` | `test_t3_cross_regime_sizing`, `test_t3_cross_heat_accumulation` | Scenarios 1, 3 |
| **F2** (Settlement Migration) | `test_t1_f2_*` | `test_t2_f2_*` | `test_t3_cross_migration_persistence` | Scenarios 1, 3 |
| **F3** (FYERS Client & Auth) | `test_t1_f3_*` | `test_t2_f3_*` | `test_t3_cross_guardian_fyers_auth` | Scenarios 1, 3 |
| **F4** (Holdings Guardian & T+2) | `test_t1_f4_*` | `test_t2_f4_*` | `test_t3_cross_settlement_gtt_oco`, `test_t3_cross_regime_exit_tightening` | Scenarios 1, 2, 3, 4 |
| **F5** (Decoupled Screener & No Bypass)| `test_t1_f5_*` | `test_t2_f5_*` | `test_t3_cross_risk_off_blocks_screener` | Scenarios 1, 2 |
| **F6** (3-Point Regime Engine) | `test_t1_f6_*` | `test_t2_f6_*` | `test_t3_cross_regime_sizing`, `test_t3_cross_risk_off_blocks_screener` | Scenarios 1, 2 |
| **F7** (ML Shadow Logging) | `test_t1_f7_*` | `test_t2_f7_*` | `test_t3_cross_ml_shadow_conviction` | Scenario 1 |
| **F8** (Morning Digest Trade Cards)| `test_t1_f8_*` | `test_t2_f8_*` | `test_t3_cross_guardian_digest_sync` | Scenarios 1, 3 |
| **F9** (Bhavcopy Jump Tripwire) | `test_t1_f9_*` | `test_t2_f9_*` | `test_t3_cross_quarantine_blocks_screener` | Scenarios 1, 5 |
| **F10** (Data Spine 250d Backfill) | `test_t1_f10_*` | `test_t2_f10_*` | `test_t3_cross_backfill_screener_continuity` | Scenario 1 |
| **F11** (Offline Shariah Sync) | `test_t1_f11_*` | `test_t2_f11_*` | `test_t3_cross_shariah_universe_screener` | Scenarios 1, 4 |
| **F12** (Beta-Stripped Residual Mom)| `test_t1_f12_*` | `test_t2_f12_*` | `test_t3_cross_residual_mom_ranking_arbiter` | Scenario 1 |
| **F13** (LightGBM LambdaRank Upgrade)| `test_t1_f13_*` | `test_t2_f13_*` | `test_t3_cross_lambdarank_top3_selection` | Scenario 1 |

---

## 6. Verification and Acceptance Criteria

The E2E Test Suite passes when:
1. All four test suite modules (`test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_cross_feature.py`, `test_tier4_workloads.py`) execute without uncaught exceptions or import crashes.
2. The master runner `python tests/test_e2e_suite.py` exits with status `0`.
3. Progressive testability skips or validates planned/completed milestone modules cleanly without masking failures.
4. All mathematical, structural, settlement, and regulatory invariants pass with $100\%$ determinism.

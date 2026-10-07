# Project: AlphaSentinel Shariah Indian CNC Swing Trading System

## Architecture
Institutional-grade, fully deterministic End-of-Day (EOD) Swing Trading System for Indian Cash Equities (`NSE:EQ` delivery only, CNC, zero leverage/margin/F&O/shorting) integrating FYERS API v3, SEBI April 1, 2026 regulations, and Justice Mufti Muhammad Taqi Usmani's Shariah Total-Assets compliance framework.

### Core Pipelines & Timing
1. **08:45 IST**: Morning 2FA Token Refresh (`scripts/fyers_auth.py` -> `.fyers_token`).
2. **08:50 IST**: Morning Telegram Digest (`scripts/run_live_preview.py` trade cards for 60-second manual FYERS App CNC entry + GTT OCO lodging alerts).
3. **09:15 - 15:30 IST**: Market Hours (Orders executed server-side via FYERS GTT OCO or manual CNC limit).
4. **19:00 IST**: EOD NSE Bhavcopy ingestion with >25% price jump quarantine (`src/ingestion/bhavcopy.py`).
5. **19:15 IST**: Market Regime Engine 3-point breadth score (`src/screening/regime_engine.py`) and Bhavcopy-only deterministic VCP + Beta-Stripped Residual Momentum screening (`src/screening/vcp_screener.py`).
6. **19:30 IST**: Nightly Holdings Guardian (`src/portfolio/fyers_guardian.py`): reconciles `fyers.holdings()`, enforces T+2 Qabd possession, evaluates 9-rule priority exit hierarchy (P1-P9), and auto-imports manual Demat buys.
7. **Monthly / Quarterly Offline**: Shariah Universe Sync (`scripts/sync_shariah_universe.py` via 6 Mufti Taqi Usmani gates).

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1: Volatility-Adjusted Risk Parity Math | Unchoke 1.0% risk by raising `max_position_size_pct: 16.0`, `max_pct_stop: 8.0`, structural stop `Stop = max(Base_Low_10d - 0.25*ATR_14, Trigger - 2.5*ATR_14)`, and 5.0% portfolio heat ceiling in `arbiter.py` & `strategy.yaml` | M1 | ORIGINAL_REQUEST §R1 |
| 2 | R2: Settlement Tracking DB Migration | Create `003_settlement_tracking.sql` adding `settlement_status`, `can_exit`, `gtt_placed`, `gtt_placed_at`, `purification_due_inr` to `positions`, and creating `guardian_log` table in DuckDB | M2 | ORIGINAL_REQUEST §R2 |
| 3 | R2: FYERS Client Auth & Demat Extensions | Implement `scripts/fyers_auth.py` (08:45 IST refresh), dynamic `reload_token()` (mtime check), `get_holdings()`, and `get_positions()` in `fyers_client.py` | M2 | ORIGINAL_REQUEST §R2, §R4 |
| 4 | R2: T+2 Qabd Settlement State Machine & Holdings Guardian | Build `src/portfolio/fyers_guardian.py`: enforce `can_exit = False` on T0/T1, transition to `SETTLED_DEMAT` on Day 2 morning with 365-day GTT OCO alert, 19:30 IST audit reconciliation, manual Demat buy import, and 9-rule priority exit hierarchy (P1-P9) | M2 | ORIGINAL_REQUEST §R2 |
| 5 | R3: Screener Intraday Decoupling & Bear Bypass Removal | In `src/screening/vcp_screener.py`, remove live intraday quote fetching (lines 51-59) for 100% Bhavcopy run, permanently remove bear-market bypass (lines 244-250) so `RISK_OFF` produces 0 buys, update tests | M3 | ORIGINAL_REQUEST §R3 |
| 6 | R3: Deterministic Regime Engine | Build `src/screening/regime_engine.py`: 3-point breadth score (Nifty 500 > SMA50, SMA50 > SMA200, % Halal EQ > SMA50 > 50%). Score 3 = `RISK_ON` (1.0% risk), Score 2 = `NEUTRAL` (0.5% risk), Score <= 1 = `RISK_OFF` (0% risk, zero buys) | M3 | ORIGINAL_REQUEST §R3 |
| 7 | R4: ML Decoupling to Non-Blocking Shadow Logging | In `scripts/run_live_preview.py:597`, remove `and (ml_prob >= ml_cutoff)` from `gate_approved`; keep XGBoost as non-blocking shadow telemetry logged to DB and console | M4 | ORIGINAL_REQUEST §R4 |
| 8 | R4: Deprecations & 08:50 Morning Digest Trade Cards | Deprecate `run_sentinel.py`, `dhan_broker.py`, and 15:15 rush from `run_scheduler.py`. Format 08:50 IST Morning Telegram Digest trade cards for 60-second manual FYERS entry | M4 | ORIGINAL_REQUEST §R4 |
| 9 | R5: Bhavcopy Price Jump Quarantine Tripwire | Add >25% unexplained price jump quarantine tripwire to `src/ingestion/bhavcopy.py` | M5 | ORIGINAL_REQUEST §R5 |
| 10 | R5: Data Spine Backfill (>=250 Trading Days) | Backfill `bhavcopy_daily` in `alphasentinel.duckdb` to >= 250 consecutive trading days without unadjusted >25% discontinuities | M5 | ORIGINAL_REQUEST §R5 |
| 11 | R5: Offline Shariah Universe Sync Script | Create `scripts/sync_shariah_universe.py` populating DuckDB `shariah_universe` from `fundamentals_cache` (367 stocks) using 6 Mufti Taqi Usmani gates (>= 350 verified stocks) | M5 | ORIGINAL_REQUEST §R5 |
| 12 | R6: Beta-Stripped Residual Momentum | Add vectorized 60-day OLS against Nifty 500, cumulative 30-day idiosyncratic residual over residual std dev (<100ms), requiring >= 70th percentile of Halal universe in `vcp_screener.py` | M6 | ORIGINAL_REQUEST §R6 |
| 13 | R6: LightGBM LambdaRank Signal Upgrade | Design Phase 2 LightGBM LambdaRank cross-sectional ranker (forward 5-day deciles, NDCG@3) to output Top 3 setups each evening | M6 | ORIGINAL_REQUEST §R6 |
| 14 | E2E Testing Suite & Infrastructure | Systematic 4-tier E2E opaque-box test suite covering Tiers 1-4 across all 13 features, verified runner, publishing `TEST_READY.md` | E2E | Dual Track Requirement |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Test infra, runner, and 4-tier opaque-box test suite (Tiers 1-4) publishing `TEST_READY.md` | Survey | DONE (153/153 pass, TEST_READY.md published) |
| M1 | Volatility-Adjusted Risk Parity Math | F1: `src/config/strategy.yaml`, `src/risk/arbiter.py`, unchoking 1.0% risk, structural stop, 5.0% heat cap | None | DONE (17/17 pass, unchoked risk & stop formula) |
| M2 | T+2 Qabd Settlement State Machine & Holdings Guardian | F2, F3, F4: `003_settlement_tracking.sql`, `fyers_client.py`, `fyers_auth.py`, `fyers_guardian.py` | M1 | DONE (23/23 pass, T+2 Qabd & Guardian verified) |
| M3 | Regime Gate & Bear-Market Bypass Removal | F5, F6: `src/screening/vcp_screener.py`, `src/screening/regime_engine.py` | None | DONE (31/31 pass, regime engine & screener decoupled) |
| M4 | ML Decoupling & Morning 2FA Token Refresh | F3, F7, F8: `scripts/run_live_preview.py`, deprecations, 08:50 Morning Digest | M2, M3 | DONE (13/13 pass, ML decoupled & digest verified) |
| M5 | Data Spine Backfill & Offline Shariah Universe Sync | F9, F10, F11: `src/ingestion/bhavcopy.py`, `alphasentinel.duckdb`, `scripts/sync_shariah_universe.py` | None | DONE (252 days, 367 stocks, 10/10 tests pass) |
| M6 | High-Alpha Signal Upgrades | F12, F13: Beta-Stripped Residual Momentum in `vcp_screener.py` & LightGBM LambdaRank | M3, M5 | DONE (11/11 pass, Beta-Stripped Mom & LambdaRank verified) |
| M_FINAL | Final Integration & Adversarial Hardening | Pass 100% E2E test suite (Tiers 1-4) + Phase 2 adversarial coverage hardening (Tier 5) + Forensic Audit | E2E, M1-M6 | PLANNED |

---

## Interface Contracts

### 1. `src/risk/arbiter.py` ↔ `src/screening/vcp_screener.py` & `run_live_preview.py`
```python
def calculate_deterministic_risk_and_position(
    symbol: str,
    trigger_price: float,
    current_price: Optional[float] = None,
    atr_14: float = 0.0,
    base_low_10d: Optional[float] = None,
    regime_risk_pct: Optional[float] = None,  # 1.0 (RISK_ON), 0.5 (NEUTRAL), 0.0 (RISK_OFF)
    circuit_band: float = 20.0,
    macro_weather: Optional[Dict[str, Any]] = None,
    portfolio_capital_rupees: float = 10_00_000.0,
    adtv_20d: float = 0.0,
    sector: str = "",
    market_cap_tier: str = "LARGE",
    open_positions: Optional[List[Dict[str, Any]]] = None  # for aggregate heat calculation
) -> Dict[str, Any]:
    # Returns {
    #   "symbol": symbol,
    #   "verdict": "APPROVE" | "REJECT",
    #   "rejection_reason": str,
    #   "trigger_price": float,
    #   "stop_loss_price": float,
    #   "stop_distance_pct": float,
    #   "target_1_price": float,
    #   "target_2_price": float,
    #   "risk_rupees": float,
    #   "risk_per_trade_pct": float,
    #   "shares_to_buy": int,
    #   "position_value_rupees": float,
    #   "portfolio_allocation_pct": float,
    #   "portfolio_heat_pct_after": float
    # }
```

### 2. `src/screening/regime_engine.py` ↔ `vcp_screener.py` & Pipelines
```python
class RegimeState(NamedTuple):
    regime: str  # "RISK_ON" | "NEUTRAL" | "RISK_OFF"
    score: int   # 3, 2, 1, 0
    risk_per_trade_pct: float  # 1.0, 0.5, 0.0
    allow_new_entries: bool    # True, True, False
    nifty500_close: float
    nifty500_sma50: float
    nifty500_sma200: float
    breadth_pct: float         # % Halal EQ stocks > own SMA50
    details: Dict[str, Any]

def compute_market_regime(conn: duckdb.DuckDBPyConnection, as_of_date: Optional[str] = None) -> RegimeState: ...
```

### 3. `src/portfolio/fyers_guardian.py` ↔ FYERS API & DuckDB
```python
class SettlementStatus(str, Enum):
    SETTLING_T0_T1 = "SETTLING_T0_T1"
    SETTLED_DEMAT = "SETTLED_DEMAT"

class ExitPriorityRule(str, Enum):
    P1_HARD_STOP = "P1_HARD_STOP"
    P2_50_SMA_BREAKDOWN = "P2_50_SMA_BREAKDOWN"
    P3_CLIMAX_TRIM = "P3_CLIMAX_TRIM"
    P4_CHANDELIER_TRAIL = "P4_CHANDELIER_TRAIL"
    P5_BREAKEVEN_RATCHET = "P5_BREAKEVEN_RATCHET"
    P6_DISTRIBUTION_TIGHTEN = "P6_DISTRIBUTION_TIGHTEN"
    P7_RS_DECAY_TIGHTEN = "P7_RS_DECAY_TIGHTEN"
    P8_TIME_STOP = "P8_TIME_STOP"
    P9_SHARIAH_DRIFT = "P9_SHARIAH_DRIFT"

def reconcile_and_evaluate_holdings(conn: duckdb.DuckDBPyConnection, fyers_client: Any, as_of_date: Optional[str] = None) -> Dict[str, Any]: ...
```

---

## Code Layout
```
c:\Users\Md Ganim\Desktop\trading agents\
├── src\
│   ├── config\
│   │   ├── strategy.yaml                 (M1: risk caps, stop formula, portfolio heat)
│   │   └── settings.py
│   ├── db\
│   │   ├── migrations\
│   │   │   └── 003_settlement_tracking.sql (M2: settlement state & guardian_log DDL)
│   │   ├── session.py                    (M2: migration execution)
│   │   └── schema.sql
│   ├── risk\
│   │   └── arbiter.py                    (M1: structural stop, 16% cap, 5% heat)
│   ├── portfolio\
│   │   └── fyers_guardian.py             (M2: T+2 Qabd state machine & 9-rule exit)
│   ├── screening\
│   │   ├── vcp_screener.py               (M3: no network, no bear bypass; M6: residual mom)
│   │   ├── regime_engine.py              (M3: 3-point breadth score)
│   │   └── shariah_filter.py             (M5: 6 Taqi Usmani gates)
│   └── ingestion\
│   │   ├── fyers_client.py               (M2/M4: dynamic reload, get_holdings, get_positions)
│   │   └── bhavcopy.py                   (M5: >25% jump quarantine tripwire)
├── scripts\
│   ├── fyers_auth.py                     (M2/M4: 08:45 IST morning 2FA token refresh)
│   ├── sync_shariah_universe.py          (M5: offline monthly batch sync)
│   ├── backfill_bhavcopy.py              (M5: historical backfill >=250 days)
│   ├── run_live_preview.py               (M4: ML decoupling to shadow logging, morning digest)
│   └── run_scheduler.py                  (M4: deprecate 15:15 rush, wire guardian at 19:30)
├── tests\
│   ├── test_e2e_suite.py                 (E2E runner)
│   ├── e2e\
│   │   ├── test_tier1_features.py        (Tier 1: Feature coverage >=5 per feature)
│   │   ├── test_tier2_boundaries.py      (Tier 2: Boundary & corner cases)
│   │   ├── test_tier3_cross_feature.py   (Tier 3: Pairwise combinations)
│   │   └── test_tier4_workloads.py       (Tier 4: Realistic EOD swing trading workloads)
│   ├── test_risk_parity_unchoked.py      (M1)
│   ├── test_fyers_guardian.py            (M2)
│   ├── test_regime_engine.py             (M3)
│   ├── test_shariah_sync.py              (M5)
│   └── test_residual_momentum.py         (M6)
└── alphasentinel.duckdb                  (Database spine)
```

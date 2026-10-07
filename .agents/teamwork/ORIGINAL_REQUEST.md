# Original User Request

## Initial Request — 2026-10-07T11:47:32Z

# Teamwork Project Prompt — Master Implementation

> Status: Launched  
> Goal: Multi-agent execution of the AlphaSentinel Shariah Indian CNC Swing Trading System  
> Requested team: Full multi-agent team (Lead Architect, Quantitative Researcher, Market Microstructure Specialist, Risk Strategist, Execution Engineer, Financial/Regulatory Critic, Code Integrity Guardian)

Build and refactor an institutional-grade, fully deterministic End-of-Day (EOD) Swing Trading System for Indian Cash Equities (`NSE:EQ` delivery only, CNC, zero leverage/margin/F&O/shorting) integrating FYERS API v3, SEBI April 1, 2026 regulations, and Justice Mufti Muhammad Taqi Usmani's Shariah Total-Assets compliance framework.

Working directory: `c:\Users\Md Ganim\Desktop\trading agents`  
Integrity mode: development  

## Reference Material
- Master Improvement Plan: [`C:\Users\Md Ganim\.gemini\antigravity\brain\dbf4a2b9-d917-4e9a-af93-e78bae3e62e3\master_improvement_plan.md`](file:///C:/Users/Md%20Ganim/.gemini/antigravity/brain/dbf4a2b9-d917-4e9a-af93-e78bae3e62e3/master_improvement_plan.md)
- Forensic Audit Document: [`Audit/Gemini-Branch • FYERS Access Limitations-20261007-1221.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/Gemini-Branch%20%E2%80%A2%20FYERS%20Access%20Limitations-20261007-1221.md)
- Primary Database: [`alphasentinel.duckdb`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/alphasentinel.duckdb)
- Agency Domain Specialists: `.agency/active/domain_agents/` (`financial_regulatory_critic.md`, `market_microstructure_specialist.md`, `portfolio_risk_strategist.md`, `quantitative_researcher.md`)

## Requirements

### R1. Phase 1 Bug Fix 1: Volatility-Adjusted Risk Parity Math (`src/risk/arbiter.py` & `strategy.yaml`)
- Fix the risk math contradiction: replace `max_pct_stop: 5.5` with `8.0` in `src/config/strategy.yaml`.
- Increase `max_position_size_pct` from `10.0` to `16.0` to unchoke the 1.0% portfolio risk allocation.
- Add `max_portfolio_heat_pct: 5.0` (sum of open stop risk across all positions $\le 5.0\%$ of core equity).
- Ensure structural stop formula: $\text{Stop} = \max(\text{Base\_Low}_{10\text{d}} - 0.25\times\text{ATR}_{14}, \text{Trigger} - 2.5\times\text{ATR}_{14})$. Reject only if stop distance $> 8.0\%$.

### R2. Phase 1 Bug Fix 2: T+2 Qabd Settlement State Machine & Holdings Guardian (`src/portfolio/fyers_guardian.py`)
- Enforce strict Mufti Taqi Usmani *Bay' qabl al-Qabd* prohibition and FYERS T1 GTT rejection guard:
  - If `trading_days_held < 2` or `holdingType == 'T1'`: set `settlement_status = 'SETTLING_T0_T1'` and `can_exit = False`. Zero sell alerts or GTT orders allowed.
  - On `trading_days_held >= 2`: set `settlement_status = 'SETTLED_DEMAT'` and `can_exit = True`.
- On Day 2 morning: generate alert to lodge 365-day FYERS GTT OCO order (`Stop = initial_stop`, `Target = target_2`).
- Nightly 19:30 IST audit: query `fyers.holdings()`, reconcile against DuckDB `positions`, auto-import manual Demat buys, and evaluate 9-rule priority exit hierarchy (P1 Hard Stop, P2 50-SMA Breakdown, P3 +3.5 ATR Trim, P4 +2R Chandelier Trail, P5 +1R Breakeven Ratchet, P6 Distribution Days, P7 RS Decay, P8 20d Time Stop, P9 Shariah Drift Flag).
- Shariah Drift (P9): If a held stock fails quarterly sync, send Telegram flag only; no forced liquidation.
- Create DB migration `003_settlement_tracking.sql` with `settlement_status`, `can_exit`, `gtt_placed`, and `guardian_log` table.

### R3. Phase 1 Bug Fix 3: Regime Gate & Bear-Market Bypass Removal (`src/screening/vcp_screener.py` & `regime_engine.py`)
- Permanently remove the bear-market bypass in `src/screening/vcp_screener.py:244-250` (zero new entries allowed during `RISK_OFF`).
- Remove live intraday quote fetching from `src/screening/vcp_screener.py:51-59`; screener runs 100% on EOD Bhavcopy.
- Create `src/screening/regime_engine.py` with 3-point breadth score:
  1. Nifty 500 Close > SMA50
  2. Nifty 500 SMA50 > SMA200
  3. Universe Breadth (% Halal EQ stocks > own SMA50) > 50%
  Score 3 = `RISK_ON` (1.0% risk), Score 2 = `NEUTRAL` (0.5% risk), Score $\le 1$ = `RISK_OFF` (0% risk).

### R4. Phase 1 Bug Fix 4: ML Decoupling & Morning 2FA Token Refresh
- Remove `ml_prob >= ml_cutoff` gate from the live execution decision in `scripts/run_live_preview.py:597`; move XGBoost to non-blocking shadow logging.
- Create `scripts/fyers_auth.py` for 08:45 IST 2FA morning token refresh to `.fyers_token`.
- Extend `src/ingestion/fyers_client.py` with dynamic `reload_token()` (mtime check), `get_holdings()`, and `get_positions()`.
- Deprecate `scripts/run_sentinel.py`, `src/execution/dhan_broker.py`, and the 15:15 IST intraday live preview rush.
- Format Morning Telegram Digest at 08:50 IST with Trade Cards (Symbol, Limit Entry, Stop, Quantity, Allocation) for 60-second manual FYERS App entry.

### R5. Data Spine Backfill & Offline Shariah Universe Sync (`scripts/sync_shariah_universe.py`)
- Backfill `bhavcopy_daily` in `alphasentinel.duckdb` (2020–2025 via NSE archives / `jugaad-data`, recent via FYERS API) to provide $\ge 250$ trading days for live 200-SMA screening. (Skip delivery % for 2020–2025 backfill; live Bhavcopy captures it forward).
- Add $>25\%$ unexplained price jump quarantine tripwire in `src/ingestion/bhavcopy.py`.
- Build `scripts/sync_shariah_universe.py` as an offline monthly batch script populating DuckDB `shariah_universe` from `fundamentals_cache` (367 stocks pre-cached) using all 6 Mufti Taqi Usmani gates in `src/screening/shariah_filter.py`.

### R6. High-Alpha Signal Upgrades (Beta-Stripped Residual Momentum & LambdaRank)
- Add **Beta-Stripped Residual Momentum** to `src/screening/vcp_screener.py`: 60-day OLS against Nifty 500, cumulative 30-day idiosyncratic residual over residual standard deviation, required $\ge 70\text{th}$ percentile of Halal universe. (Eliminates the 35% banking contamination from Shariah momentum).
- Phase 2: Train LightGBM LambdaRank (`objective="lambdarank"`, forward 5d deciles, NDCG@3) to output the Top 3 setups each evening.

## Acceptance Criteria

### Data & Universe Verification
- [ ] DuckDB `shariah_universe` populated with $\ge 350$ verified compliant stocks passing all 6 Mufti Taqi Usmani gates.
- [ ] `bhavcopy_daily` contains $\ge 250$ consecutive trading days without unadjusted $>25\%$ discontinuities.
- [ ] `scripts/sync_shariah_universe.py` runs standalone offline without blocking the EOD pipeline.

### Screening & Strategy Logic
- [ ] VCP screener runs 100% deterministically from `bhavcopy_daily` with zero intraday network calls.
- [ ] Bear-market bypass is removed: zero buy signals produced when Market Regime is `RISK_OFF`.
- [ ] Beta-Stripped Residual Momentum computes vectorized in $<100$ms and ranks $\ge 70\text{th}$ percentile.

### Risk & Settlement Compliance
- [ ] Unit test confirms a 1.0% risk trade with a 6.0% stop is correctly allocated without being capped at 0.55%.
- [ ] Positions on Day 0 and Day 1 (`T1`) evaluate to `can_exit = False` under `IndianMarketCompliance` and `fyers_guardian.py`.
- [ ] On Day 2 (`T+2` morning), position transitions to `SETTLING_DEMAT` and `can_exit = True`, triggering FYERS GTT OCO prompt.
- [ ] Holdings Guardian successfully executes `fyers.holdings()` and reconciles open positions against DuckDB.

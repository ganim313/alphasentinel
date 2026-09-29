---
template_id: "05"
phase: 4
assigned_role: "05_backend_engineer"
support_roles: ["06_database_engineer", "04_frontend_engineer", "07_qa_sdet_engineer"]
context_from: ["03_requirements_engineering.md", "04_system_design_architecture.md"]
outputs_to: ["06_testing_uat_signoff.md"]
status: in_progress
version: "2.0.0"
last_updated: "2026-09-04"
---

# Technical SDLC & Implementation Execution Plan

> [!IMPORTANT]
> **CANONICAL ALIGNMENT NOTICE:**  
> This SDLC Execution Plan directly tracks the implementation and remediation of the AlphaSentinel OS codebase. All tasks, directory structures, database schemas, and mathematical gates map 1:1 to the **Master PRD** (`03_requirements_engineering.md`) and **System Architecture** (`04_system_design_architecture.md`).

---

## 1. Environment & Runtime Strategy
- **Runtime:** Python 3.13+ (`C:\Users\Public\anaconda3\python.exe` / `uv` virtual environment).
- **Target OS:** Windows 11 Workstation (Dev/Execution) & Linux ARM64 (Oracle Cloud Always-Free A1 4 vCPU / 24GB RAM).
- **Database:** Embedded DuckDB (`alphasentinel.duckdb`) with process-safe single-writer file locking (`portalocker.Lock`).
- **AI & LLM Services:** `litellm` multi-provider waterfall (`Gemini 1.5 Flash` $\rightarrow$ `DeepSeek-R1` $\rightarrow$ `Groq Llama-3.3` $\rightarrow$ Deterministic Math).
- **Shariah Sovereign Rule:** 5-Rule Usmani Benchmark (`Copy of halal stock 2.0.xlsx`).

---

## 2. Actual Codebase Architecture & File Inventory

```
alphasentinel/
├── .agency/
│   └── active/
│       ├── product_design/
│       │   └── 03_requirements_engineering.md       # Master Single Source of Truth PRD
│       └── engineering/
│           ├── 04_system_design_architecture.md     # Master HLD & LLD Specification
│           └── 05_technical_sdlc_execution.md       # Active SDLC Execution Plan
│
├── config/
│   └── strategy.yaml                                # Strategy parameters & risk thresholds
│
├── models/
│   ├── xgboost_global.pkl                           # 6-Feature Trained Model
│   └── xgboost_global_meta.json                     # Training metadata & Out-of-Sample AUC
│
├── src/
│   ├── agents/                                      # LangGraph Multi-Agent Engine
│   │   ├── debate_graph.py                          # Adversarial StateGraph (Risk -> Bull -> Bear -> Judge)
│   │   ├── llm_gateway.py                           # LiteLLM resilient waterfall client
│   │   ├── manual_export.py                         # Text dump bridge for Web UI LLMs
│   │   ├── state.py                                 # AgentState TypedDict schema
│   │   └── tools.py                                 # Agent evaluation utilities
│   │
│   ├── config/
│   │   └── settings.py                              # Pydantic BaseSettings & env loader
│   │
│   ├── db/                                          # DuckDB OLAP Engine
│   │   ├── schema.sql                               # Complete 12-table production DDL
│   │   ├── session.py                               # Thread/Process-safe connection manager
│   │   └── queue_writer.py                          # Atomic transaction & write wrappers
│   │
│   ├── execution/                                   # Execution & Market Compliance
│   │   ├── compliance.py                            # NSE market hours & T+1 margin settlement
│   │   └── order_manager.py                         # Limit order price-chaser & position logging
│   │
│   ├── ingestion/                                   # Tier 1 Market Data Scrapers
│   │   ├── bhavcopy.py                              # NSE Bhavcopy archive & yfinance fallback
│   │   ├── corporate_actions.py                     # Split/Bonus retroactive price adjuster
│   │   ├── macro_feeds.py                           # GIFT Nifty, US VIX, and Weather score
│   │   ├── screener_scraper.py                      # Screener.in headless scraper with DB cache
│   │   └── tradingview.py                           # tradingview-ta 26-indicator consensus
│   │
│   ├── notification/                                # Telegram Alerts & Formatting
│   │   ├── telegram_bot.py                          # Async dispatcher, kill-switch & alerts
│   │   └── trade_card.py                            # Institutional Markdown Trade Cards
│   │
│   ├── risk/                                        # Capital & Volatility Management
│   │   └── arbiter.py                               # Pure Python deterministic risk arbiter
│   │
│   ├── screening/                                   # Tier 2 & Tier 3 Quantitative Gating
│   │   ├── anti_trap_shield.py                      # 6-Layer pre-flight distribution blocker
│   │   ├── liquidity_guard.py                       # ADTV floor, series BE block, circuit bands
│   │   ├── mean_reversion_screener.py               # Secondary technical signal generator
│   │   ├── ml_features.py                           # 6 Minervini VCP feature extractor
│   │   ├── ml_predictor.py                          # Global XGBoost probability inference
│   │   ├── second_opinion_gate.py                   # Consensus gate (Conviction >= 7 & ML > 0.50)
│   │   ├── shariah_filter.py                        # 5-Rule Mufti Taqi Usmani compliance gate
│   │   └── vcp_screener.py                          # Vectorized Minervini Stage 2 & VCP screener
│   │
│   └── utils/
│       └── holidays.py                              # Gazetted NSE Trading Holidays
│
├── scripts/                                         # Autonomous Cron & Daemon Runners
│   ├── generate_purification_report.py              # Monthly Shariah charity statement
│   ├── keep_alive.py                                # Synthetic load maintainer (>10% CPU)
│   ├── run_corporate_actions.py                     # Weekend split/bonus retroactive adjuster
│   ├── run_db_maintenance.py                        # Vacuum, checkpoint & archive routine
│   ├── run_drawdown_check.py                        # Monthly 6.0% circuit breaker monitor
│   ├── run_eod_reconciliation.py                    # 06:00 PM Bhavcopy reconciliation & 3R/6R exits
│   ├── run_evaluator.py                             # Shadow & Paper portfolio performance auditor
│   ├── run_feedback_loop.py                         # Dynamic prompt injection learning loop
│   ├── run_live_preview.py                          # 03:15 PM EOD live screener & debate
│   ├── run_model_training.py                        # XGBoost 6-feature trainer & AUC validator
│   ├── run_premarket.py                             # 08:45 AM Pre-market macro radar
│   └── run_sentinel.py                              # 15-Minute intraday trailing stop sentinel
│
└── tests/                                           # Automated Pytest Suite
    ├── test_corporate_actions.py
    ├── test_db_queue.py
    ├── test_debate_and_tradingview.py
    ├── test_eod_risk_offloader.py
    ├── test_financial_logic_fixes.py
    ├── test_risk_arbiter_and_agents.py
    ├── test_screening_and_anti_trap.py
    └── test_second_opinion_gate.py
```

---

## 3. Codebase Audit Remediation: 19-Flaw Implementation Plan

| # | File Path | Defect / Vulnerability | Planned Remediation Action | Status |
| :- | :--- | :--- | :--- | :--- |
| **01** | `src/db/schema.sql` | Missing columns in `bhavcopy_daily` (`split_multiplier`, `upper_circuit`, `lower_circuit`, `circuit_band_pct`) | Update DDL to add all 4 columns with default values | ✅ Completed |
| **02** | `src/db/schema.sql` | Missing tables `corporate_actions` & `purification_log` | Add complete DDL for both tables | ✅ Completed |
| **03** | `src/db/session.py` | Missing automated column migration for missing `bhavcopy_daily` columns | Add non-destructive `PRAGMA table_info` checks & ALTER TABLE | ✅ Completed |
| **04** | `src/ingestion/bhavcopy.py` | `safe_float` & `safe_int` return `pd.DataFrame()` on error, crashing DuckDB binding | Return `None` on all exceptions and missing values | ✅ Completed |
| **05** | `src/screening/shariah_filter.py` | Negative or zero `total_assets` bypasses illiquid asset ratio check | Enforce strict `total_assets > 0` validation or fail closed | ✅ Completed |
| **06** | `src/screening/shariah_filter.py` | Missing 5th Shariah rule: `net_liquid_assets <= market_cap` | Implement Net Liquid Assets rule matching Usmani fatwa | ✅ Completed |
| **07** | `src/ingestion/screener_scraper.py`| Missing fallback keys for `other_income` / `interest` and Net Liquid Assets calculation | Add fallback parsing and compute `net_liquid_assets_crores` | ✅ Completed |
| **08** | `src/screening/vcp_screener.py` | N+1 DB queries in screening loop for slippage calculation | Pull portfolio equity once outside the loop | ✅ Completed |
| **09** | `src/screening/vcp_screener.py` | Truncated 60-day lookbacks instead of 252-day true Minervini template | Restore 252-day lookbacks for 52W high/low & SMA 150/200 | ✅ Completed |
| **10** | `src/screening/vcp_screener.py` | Slippage portfolio calculation mutates candidate result | Keep simulation math separate from candidate attributes | ✅ Completed |
| **11** | `scripts/run_model_training.py` | Generic 11-indicator feature set drifted from Minervini strategy | Refactored to 6 strategy-aligned features | ✅ Completed |
| **12** | `src/screening/ml_features.py` | Generic 11-indicator feature set | Rewritten to output 6 strategy-aligned features | ✅ Completed |
| **13** | `src/screening/ml_predictor.py` | Hardcoded `LIMIT 60` in SQL query truncating historical lookback | Update query to fetch 252+ days for true 52W high computation | ✅ Completed |
| **14** | `src/screening/ml_predictor.py` | `expected_features` fallback defaulted to old 11 indicators | Updated to expect 6 strategy-aligned features | ✅ Completed |
| **15** | `src/agents/debate_graph.py` | Default conviction score fallback was 6.5 instead of strict regex | Enforce strict regex parsing with explicit error logging | ✅ Completed |
| **16** | `scripts/run_live_preview.py` | Second opinion gate only checked `ml_prob > 0.50`, ignoring `conviction >= 7.0` | Enforce joint condition: `conviction >= 7.0` AND `ml_prob > 0.50` | ✅ Completed |
| **17** | `scripts/run_live_preview.py` | Hardcoded flat ₹100,000 sizing overriding Risk Arbiter calculation | Use `final_state['suggested_shares']` from Deterministic Arbiter | ✅ Completed |
| **18** | `scripts/run_eod_reconciliation.py`| 100% position liquidation at Target 1 instead of 50% partial exit & BE ratchet | Sell 50% at 3R, ratchet SL to Breakeven + 0.5%, trail to 6R | ✅ Completed |
| **19** | `scripts/run_eod_reconciliation.py`| Missing purification logging on realized profitable exits | Insert profit & impure income records into `purification_log` | ✅ Completed |

---

## 4. Definition of Done (DoD)
1. [x] Single Source of Truth PRD (`03_requirements_engineering.md`) complete and mathematically rigorous.
2. [x] Master HLD/LLD Specification (`04_system_design_architecture.md`) complete and reverse-engineered.
3. [ ] All 19 Code Flaws remediated across database, ingestion, screening, ML, debate, and execution layers.
4. [ ] Full pytest test suite passing with 100% green status.
5. [ ] End-to-end dry run of 03:15 PM screener, 15m Sentinel, and 06:00 PM reconciliation executing without warnings.

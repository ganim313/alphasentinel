# AlphaSentinel: Current System State, Methods, Algorithms & Models

**Document Type:** Technical System State & Architecture Blueprint  
**Target Audience:** Quantitative Researchers, Algorithmic Trading Systems Architects, and LLM Engineering Peers  
**System Status:** Production Greenfield (Phase 7 Complete, 237/237 Automated Unit & Integration Tests Passing)  
**Execution Environment:** Dual-Mode (Simulated Paper Trading Engine + Live Dhan Broker API)  
**Market Universe:** National Stock Exchange of India (NSE) Equities (Large, Mid, Small, and Micro-Cap)

---

## 1. System Overview & Core Technology Stack

AlphaSentinel is an institutional-grade quantitative trading operating system designed for Indian equities. It decouples trade generation, adversarial stress-testing, mathematical risk allocation, and order execution into discrete, deterministically gated pipeline stages.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Point-in-Time Data Layer                             │
│  NSE Bhavcopy (EOD) ──► Corporate Actions (Splits) ──► Screener.in Fundamentals │
│  Fyers Level-2 Depth ──► Global Macro Feeds (VIX, Crude, USDINR) ──► DuckDB WAL │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     Multi-Stage Alpha Screening Pipeline                        │
│  1. Shariah Compliance Gate (6 Quantitative Ratios + Symbol Blacklist)          │
│  2. Liquidity & Executability Guard (ADTV Floors, Circuit Bands, T2T Filter)    │
│  3. Setup Discovery (Vectorized Minervini Stage 2 VCP / Oversold Mean Reversion)│
│  4. 6-Layer Pre-Flight Anti-Trap Shield (Climax, Churning, Pledge, Median P/E)  │
│  5. Second-Opinion ML Consensus Gate (Global XGBoost Champion, Prob > 0.50)     │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                 Adversarial Multi-Agent Debate Graph (LangGraph)                │
│  Deterministic Risk Arbiter ──► Bull Analyst ──► Bear Trap Hunter ──► Judge     │
│  (Pure Python Math / Caps)      (Upside Thesis)  (Downside Stress)    (Conviction)
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      Mathematical Risk & Portfolio Engine                       │
│  ATR-14 Dynamic Stop Loss & Sizing ──► CPPI Drawdown Scalar (0.94 Floor)        │
│  Annualized Portfolio Volatility Targeting ──► Pairwise Correlation Guard       │
│  Intraday Daily Drawdown Kill-Switch (3%) ──► 3:00 PM EOD Risk Offloader        │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       Execution & Surveillance Engines                          │
│  PaperBroker / DhanBroker (Price-Chaser Limit, Slippage & Circuit Lock Guard)   │
│  15-Minute Sentinel (Chandelier Trailing Stops, 50% T1 Partial, T2 Runner Exit) │
│  Lower Circuit Lock Handler (MARKED_FOR_CLOSURE Safe Queue)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Technologies
- **Runtime:** Python 3.13 with vectorized NumPy and Pandas.
- **Database Engine:** Embedded DuckDB (`src/db/session.py`, `src/db/queue_writer.py`) using Write-Ahead Logging (WAL) and a dedicated single-writer background queue worker (`db_write()`) to eliminate SQLite/DuckDB lock contention under concurrent workloads.
- **Machine Learning & Probabilistic Frameworks:** XGBoost (`xgboost_global.pkl`), `hmmlearn` Gaussian Hidden Markov Models (`hmm_regime.pkl`), Scikit-learn, SciPy (Deflated Sharpe Ratio / PBO).
- **Agent Orchestration:** LangGraph stateful `StateGraph` with `MemorySaver` in-memory checkpoints (`src/agents/debate_graph.py`).
- **Broker & Market Data Integrations:** Fyers API (live quotes, Level 2 market depth), Dhan API (bracket/limit order execution), Yahoo Finance (`yfinance` for global macro and fallback data).

---

## 2. Point-in-Time Data & Ingestion Architecture

### 2.1 Bhavcopy Ingestion & Split Adjustment (`src/ingestion/bhavcopy.py`)
- Ingests daily NSE Bhavcopy zip archives, normalizes headers, and calculates:
  - `total_traded_val = close_price * total_traded_qty`
  - `delivery_pct = (delivery_qty / total_traded_qty) * 100`
  - `circuit_band_pct`, `upper_circuit`, `lower_circuit`
- **Corporate Action Adjustments (`src/ingestion/corporate_actions.py`):** Calculates split and bonus multipliers ($M_{adj} = \frac{Ratio_{From}}{Ratio_{To}}$) and retroactively scales historical OHLC series while preserving point-in-time integrity in `bhavcopy_daily`.

### 2.2 Fundamentals Scraping & Cache (`src/ingestion/screener_scraper.py`)
- Scrapes point-in-time financial statements and ratios from Screener.in with an enforced 7-day TTL stored in table `fundamentals_cache`.
- Ingests: Market Cap, P/E, ROCE, Sales Growth, Profit Growth, Debt-to-Equity, Promoter Pledging %, Cash & Equivalents, Borrowings, Total Assets, Trade Receivables, and Illiquid Assets.

### 2.3 Global Macro Weather Feed (`src/ingestion/macro_feeds.py`)
- Gathers real-time external macro signals stored in `macro_weather`:
  - **US VIX & S&P 500 Daily % Change**
  - **Brent Crude Oil Spot & % Change**
  - **USD/INR Exchange Rate & % Change**
  - **Polymarket Geopolitical / Macro Risk Score**
- Outputs a composite `macro_weather_score` and a recommended `target_cash_exposure_pct` ($0\%$ to $100\%$).

---

## 3. Screening & Alpha Generation Pipelines

### 3.1 Vectorized Minervini Stage 2 & VCP Screener (`src/screening/vcp_screener.py`)
Identifies high-momentum institutional accumulation setups using Mark Minervini's Volatility Contraction Pattern (VCP) across batches of up to 500 symbols:

1. **Minervini Stage 2 Trend Template Criteria:**
   $$\text{Price} > \text{SMA}_{50} > \text{SMA}_{150} > \text{SMA}_{200}$$
   $$\text{Price} \ge 1.25 \times \text{Low}_{252d} \quad \text{and} \quad \text{Price} \ge 0.75 \times \text{High}_{252d}$$
   $$\text{SMA}_{200}(t) \ge \text{SMA}_{200}(t - 20) \quad (\text{200-DMA trending up for } \ge 1 \text{ month})$$
2. **VCP Volatility Contraction & Volume Dry-Up:**
   $$\text{Vol}_{5d} < 0.85 \times \text{Vol}_{20d} \quad (\text{Volume Dry-up})$$
   $$\sigma_{10d}(\text{Returns}) < 0.75 \times \sigma_{30d}(\text{Returns}) \quad (\text{Volatility Contraction})$$
3. **4-Stage High-Low Depth Contraction Verification:**
   Evaluates intraday High-Low ranges across 4 successive backward slices ($C_1: [-40, -20]$, $C_2: [-20, -10]$, $C_3: [-10, -5]$, $C_4: [-5, 0]$):
   $$\text{Depth}(h, l) = \frac{\max(h) - \min(l)}{\max(h)}$$
   $$\text{Contraction Verified} \iff C_2 \le 1.05 C_1 \land C_3 \le 1.05 C_2 \land C_4 \le 1.05 C_3 \land C_4 \le C_1$$
4. **Relative Strength (RS) vs Benchmark (`^CRSLDX` / NIFTY 500):**
   $$RS = (\text{Return}_{Stock, 60d} - \text{Return}_{Benchmark, 60d}) \times 100$$
   - **Regime Bypass Logic:** If benchmark is below its 50-DMA, setups are strictly rejected unless $RS > 15.0$ with confirmed volume dry-up, in which case entry is allowed at a 50% position scalar.

### 3.2 Vectorized Mean-Reversion Screener (`src/screening/mean_reversion_screener.py`)
Captures structural pullbacks ("Buy the Dip in a Bull Trend"):
- **Wilder's 14-Period RSI:** Implemented via optimized 1D NumPy array calculations.
- **Entry Criteria:** $\text{RSI}_{14} < 30.0$ AND $\text{Close} > \text{SMA}_{200}$ (with minimum 150 bars of history).
- **Time-Travel Bug Fix:** Appends today's live price tick in Asia/Kolkata timezone to avoid stale EOD data.

### 3.3 Shariah Compliance Gate (`src/screening/shariah_filter.py`)
Screens out non-compliant business activities and leveraged financial structures based on the Shariah standard of Justice Mufti Muhammad Taqi Usmani and the *Copy of halal stock 2.0.xlsx* benchmark:
1. **Explicit Symbol Blacklist:** Hard-blocks banks, conventional NBFCs, brokerages, sugar mills operating molasses distilleries, tobacco, defense/munitions, and hospitality (e.g., `HDFCBANK`, `ICICIBANK`, `ITC`, `HAL`, `BEL`, `BALRAMCHIN`).
2. **Permissible Business Activity:** Regex boundary scan across company sector descriptions.
3. **Financial Ratios:**
   - $\frac{\text{Total Debt}}{\text{Total Assets}} \le 33.0\%$
   - $\frac{\text{Cash \& Interest-Bearing Investments}}{\text{Total Assets}} \le 33.0\%$
   - $\frac{\text{Impure / Interest Income}}{\text{Total Revenue}} \le 5.0\%$
   - $\frac{\text{Illiquid Assets}}{\text{Total Assets}} \ge 20.0\%$
   - $\frac{\text{Trade Receivables}}{\text{Total Assets}} \le 49.0\%$ (AAOIFI Standard 21)
   - $\text{Net Liquid Assets} \le \text{Market Capitalization}$ (Mufti Taqi Usmani 5th Rule)

### 3.4 6-Layer Pre-Flight Anti-Trap Shield (`src/screening/anti_trap_shield.py`)
Vetoes manipulative operator traps before any LLM tokens are expended:
- **Layer 1 (Pivot Extension Trap):** Rejects candidates trading $> 5.0\%$ above the consolidation pivot high.
- **Layer 2 (Climax Run Trap):** Rejects if 10-day price run $> 40\%$, current volume $> 3.0 \times \text{Vol}_{10d}$, and upper wick $> 50\%$ of candle range.
- **Layer 2B (Intraday Churning Trap):** Rejects if current volume $> 2.0 \times \text{Vol}_{10d}$ but delivery percentage $< 15.0\%$.
- **Layer 3 (Moving Average Distance Guard):** Rejects if price is $> 15\%$ above 20-EMA or $> 30\%$ above 50-SMA.
- **Layer 4 (Promoter Pledge Guard):** Hard rejection if promoter pledging increased over the last 3 months, or if total pledging $> 15.0\%$.
- **Layer 5 (P/E Overvaluation Filter):** Dynamically computes cross-sectional median P/E across the sector from `fundamentals_cache`; rejects if $\text{Stock P/E} > 2.5 \times \text{Sector Median P/E}$.
- **Layer 6 (FOMO Saturation):** Rejects if news count $\ge 3$ within a 3-day price run $> 15\%$, or if scraper fails during a $> 15\%$ run.

### 3.5 Liquidity & Executability Guard (`src/screening/liquidity_guard.py`)
- **T2T Hard Block:** Automatically rejects Trade-to-Trade symbols (`series IN ('BE', 'BZ', 'T2T')`).
- **30-Day Median ADTV Floors:**
  - Large Cap: $\ge ₹5.0\text{ Cr}$
  - Mid Cap: $\ge ₹1.5\text{ Cr}$
  - Small Cap: $\ge ₹50\text{ Lakhs}$
  - Micro Cap: $\ge ₹25\text{ Lakhs}$
- **Circuit Band Risk:** Rejects stocks with daily price bands $\le 2\%$; flags $\le 5\%$ bands for position sizing reduction.
- **Fyers Level 2 Depth Spread:** Rejects if $\frac{\text{Best Ask} - \text{Best Bid}}{\text{Best Bid}} \times 100 > 2.0\%$.

---

## 4. Machine Learning & Statistical Models

### 4.1 Global Champion XGBoost Classifier (`src/screening/ml_features.py`, `src/screening/ml_predictor.py`)
- **Model File:** `models/xgboost_global.pkl`
- **Inference Objective:** Predicts the probability of a positive forward return over a 5-day horizon.
- **Dual Consensus Gate (`second_opinion_gate.py`):** Requires $\text{Prob} > 0.50$ and Research Judge Conviction $\ge 7.0$.
- **Feature Set (9 Quant Features):**
  1. `sharpe_rank`: Normalized annualized 60-day Sharpe ratio proxy:
     $$\text{Sharpe}_{raw} = \frac{\mu_{ret, 60d}}{\sigma_{ret, 60d} + 1e-6}, \quad \text{sharpe\_rank} = \frac{1}{1 + e^{-\text{Sharpe}_{raw} \times \sqrt{252}}}$$
  2. `dist_high`: Distance to 252-day high ($\frac{\text{Close}}{\text{High}_{252d}} - 1$).
  3. `market_regime`: Binary macro regime from canonical benchmark ($1 = \text{Risk On}, 0 = \text{Risk Off}$).
  4. `rel_rsi`: Relative RSI differential ($\text{RSI}_{Stock, 14} - \text{RSI}_{Benchmark, 14}$).
  5. `ema_dist`: Percentage distance from the 20-day exponential moving average.
  6. `vol_cluster`: 20-day standard deviation of percentage returns.
  7. `delivery_ratio`: Delivery percentage normalized to $[0, 1]$.
  8. `adtv_log`: Log-transformed 20-day Average Daily Traded Value ($\ln(1 + \text{ADTV})$).
  9. `momentum_6m`: 126-day price return percentage.

### 4.2 3-State Gaussian Hidden Markov Model (HMM) (`scripts/fit_hmm_regime.py`, `src/utils/benchmark_provider.py`)
- **Model File:** `models/hmm_regime.pkl`
- **Target Series:** Daily log-returns of the canonical market benchmark ($\ln \frac{P_t}{P_{t-1}}$).
- **Architecture:** 3-state Gaussian HMM with diagonal covariance matrix.
- **State Canonical Ordering:**
  - **State 0 (Crisis / High Volatility):** Anchored to the lowest mean return and highest empirical tail variance ($\mu_0 < 0$, $\sigma_0 = \max(\sigma)$).
  - **State 1 (Choppy / Neutral):** Near-zero drift sideways regime.
  - **State 2 (Calm / Bull):** Positive mean return, low volatility regime.
- **Production Decoding (`get_hmm_market_regime`):** Decodes the current market state from the most recent return sequence. When combined with the 50-DMA filter, any State 0 reading immediately halts new long entries.

### 4.3 Deflated Sharpe Ratio (DSR) & PBO (`src/portfolio/metrics.py`)
Based on Bailey & Lopez de Prado (2014), guards against backtest overfitting and selection bias across $N$ strategy trials:
$$E[\max(SR_N)] \approx \sqrt{2 \ln N} \quad (N > 1)$$
$$\text{Var}(SR) = 1 - \gamma_3 \cdot SR + \frac{\gamma_4 - 1}{4} SR^2$$
$$z = \frac{(SR - E[\max(SR_N)]) \sqrt{T}}{\sqrt{\text{Var}(SR)}}$$
$$\text{DSR} = \Phi(z), \quad \text{PBO} = 1 - \text{DSR}$$
Where $\gamma_3$ is the skewness, $\gamma_4$ is the Pearson kurtosis of daily returns, and $T$ is the observation length in years. DSR $> 0.95$ confirms statistical validity beyond trial mining.

---

## 5. Multi-Agent LLM Consensus & Adversarial Debate

The system implements a stateful LangGraph directed acyclic graph (`src/agents/debate_graph.py`) where LLM agents analyze setups, but have **zero direct authority over capital allocation**.

```
Candidate Setup ──► [Deterministic Risk Node] (Python Math)
                          │
                          ▼ (Approved)
                    [Bull Analyst Node] (3-Bullet Upside Thesis)
                          │
                          ▼
                    [Bear Trap Hunter Node] (3-Bullet Downside Stress)
                          │
                          ▼
                    [Research Judge Node] (2-Sentence Synthesis + Conviction 1-10)
                          │
                          ▼
             [Dual Consensus Decision Gate]
             Conviction >= 7.0 AND ML Prob > 0.50
```

1. **Deterministic Risk Node:** Runs before any LLM prompt. Evaluates portfolio equity, sector limits, cash reserves, and correlation. Rejects immediately if risk budgets are breached.
2. **Bull Analyst Node:** Pattern-aware specialist (adapts prompts for VCP Breakouts vs 200-DMA Mean Reversion dips). Formulates a 3-bullet catalyst and accumulation thesis incorporating weekly strategy feedback memory.
3. **Bear Trap Hunter Node:** Adversarially stress-tests the Bull Thesis against promoter pledging, valuation saturation, macro regime headwinds, and liquidity constraints.
4. **Research Judge Node:** Reconciles the debate against ground-truth financial statements and technical metrics, outputting an executive synthesis and a numeric Conviction Score ($1.0 - 10.0$).
5. **Historical Feedback Loop (`agent_memory`):** Logs every debate transcript and tracks 3-day and 7-day post-trade outcomes with Triple-Barrier labeling ($1 = \text{Target hit}$, $-1 = \text{Stop hit}$, $0 = \text{Time-out}$). Retrains agents with feedback memory.

---

## 6. Portfolio Construction & Mathematical Risk Engine

### 6.1 Deterministic Position Sizing & ATR Stop Loss (`src/risk/arbiter.py`)
- **Base Stop Loss:**
  $$\text{Stop Loss} = \max(\text{Trigger} - 1.8 \times \text{ATR}_{14}, \, \text{Trigger} \times (1 - 0.055))$$
  - Rejection Rule: If $1.8 \times \text{ATR}_{14}$ stop is below the $5.5\%$ maximum drop threshold, the stock is declared too volatile and rejected.
- **Profit Targets:**
  $$\text{Target 1} = \text{Trigger} + 2.0 \times \text{Risk Per Share}$$
  $$\text{Target 2} = \text{Trigger} + 3.5 \times \text{Risk Per Share}$$
- **Capital Constraints & Sizing:**
  - Maximum trade risk: $1.0\%$ of core equity (`MAX_PORTFOLIO_RISK_PER_TRADE_PCT`).
  - Maximum position size cap: $10.0\%$ of core equity.
  - Sector concentration cap: $\le 3$ open positions and $\le 25\%$ total portfolio capital per sector.
  - Cash floor: Minimum $5.0\%$ cash reserve required at all times.
  - ADTV Participation Cap: Position volume capped at $5.0\%$ (Large), $2.0\%$ (Mid), $1.0\%$ (Small), $0.5\%$ (Micro) of 20-day median ADTV.

### 6.2 CPPI Drawdown Control (`src/risk/cppi.py`)
Scales position sizes down as core equity approaches the drawdown floor ($94\%$ of High-Water Mark):
$$\text{Floor}_t = 0.94 \times \text{HWM}_t$$
$$\text{Cushion}_t = \max(0, \text{Core Equity}_t - \text{Floor}_t)$$
$$\text{Multiplier}_{\text{CPPI}} = \min\left(1.0, \, \frac{\text{Cushion}_t}{\text{HWM}_t \times (1 - 0.94)}\right)$$
When Cushion is depleted, $\text{Multiplier}_{\text{CPPI}} = 0.0$, enforcing an automatic trading halt.

### 6.3 Portfolio Volatility Targeting (`src/risk/vol_target.py`)
Computes an annual volatility scalar $L_t \in (0, 1]$ to scale down candidate shares when the proposed portfolio's annualized volatility exceeds the annual target ($\sigma_{\text{target}} = 15\%$):
$$\mathbf{w} = \left[\frac{\text{Position Value}_i}{\text{Core Equity}}\right]$$
$$\sigma_{\text{portfolio}} = \sqrt{\mathbf{w}^T \mathbf{\Sigma}_{252d} \mathbf{w}}$$
$$L_t = \min\left(1.0, \, \frac{\sigma_{\text{target}}}{\sigma_{\text{portfolio}}}\right) \quad (\text{clipped to } [0.1, 1.0])$$

### 6.4 Portfolio Correlation Guard (`src/risk/correlation_guard.py`)
Calculates the 60-day Pearson return correlation between a candidate stock and all currently open portfolio positions:
$$\bar{\rho} = \frac{1}{K} \sum_{k=1}^K \text{Corr}(R_{\text{candidate}}, R_k)$$
Rejects the candidate if $\bar{\rho} > 0.65$ to prevent hidden factor/sector concentration in momentum clusters.

### 6.5 Daily Drawdown Kill-Switch (`src/risk/daily_drawdown_guard.py`)
Computes the intraday drawdown percentage relative to the day-open core equity snapshot:
$$\text{Drawdown}_{\text{intraday}} = \frac{\text{Core Equity}_{\text{open}} - \text{Core Equity}_{\text{current}}}{\text{Core Equity}_{\text{open}}} \times 100$$
If $\text{Drawdown}_{\text{intraday}} \ge 3.0\%$, all new order entries are hard-blocked for the remainder of the session.

### 6.6 3:00 PM EOD Risk Offloader (`evaluate_eod_risk_offload`)
Evaluates open positions 30 minutes before market close:
- Scales down positions by $50\%$ if daily price band $\le 5.0\%$ to avoid overnight gap-and-lock illiquidity.
- Scales down exposure if macro weather targets $\ge 50\%$ cash.

---

## 7. Execution Engine & Active Surveillance

### 7.1 Order Routing & Execution Safeguards (`src/execution/order_manager.py`)
- **Idempotency Guard:** Checks active trade database before placing orders to eliminate duplicate fills.
- **Estimated Slippage Model:**
  $$\text{Slippage} = \begin{cases} 0.10\% & \text{ADTV} > ₹50\text{ Cr (Large)} \\ 1.00\% & \text{ADTV} > ₹5\text{ Cr (Small)} \\ 1.50\% & \text{ADTV} \le ₹5\text{ Cr (Micro)} \end{cases}$$
- **Upper Circuit Fill Protection:** If $\text{Executed Price} = \text{Trigger Price} \times (1 + \text{Slippage}) \ge \text{Upper Circuit}$, the order is immediately aborted.

### 7.2 15-Minute Trailing Stop-Loss Sentinel (`scripts/run_sentinel.py`)
Runs continuously during market hours ($9:15\text{ AM} - 3:30\text{ PM}\text{ IST}$):
1. **Lower Circuit Lock Trap:** If an open position breaches stop-loss but the current price is locked at or within $0.2\%$ of the lower circuit band, market exits are impossible. Rather than failing silently, the position status is updated to `MARKED_FOR_CLOSURE` and a high-priority alert is sent for After-Market Order (AMO) liquidation.
2. **Stop-Out Execution:** Executes market sell when $\text{Low} \le \text{Trailing Stop}$. Updates realized PnL and sends Telegram alert.
3. **Profit Target 1 (Partial Booking & Breakeven Ratchet):** When $\text{High} \ge \text{Target 1}$, closes $50\%$ of shares, updates position status to `TARGET_1_TRIMMED`, and ratchets the trailing stop to breakeven ($\text{Entry Price} \times 1.002$).
4. **Profit Target 2 (Runner Full Exit):** When $\text{High} \ge \text{Target 2}$, liquidates remaining shares, logs Shariah dividend/capital gain purification, and records `WIN` outcome in `agent_memory`.
5. **Chandelier Trailing Ratchet:**
   $$\text{New Stop} = \max(\text{Current Stop}, \, \text{Peak High} - 1.8 \times \text{ATR}_{14})$$
   Guarantees stops only ratchet upwards.

---

## 8. Summary of Active Database Entities (`src/db/schema.sql`)

| Table Name | Primary Role |
| :--- | :--- |
| `bhavcopy_daily` | Split-adjusted EOD OHLCV, delivery %, circuits, and surveillance flags (`is_asm`, `is_gsm`). |
| `corporate_actions` | Register of splits, bonuses, and rights with calculated adjustment ratios. |
| `positions` | Active and historical portfolio positions with entry, SL, T1, T2, PnL, and status. |
| `purification_log` | Shariah impure income and capital gain donation tracking per closed trade. |
| `screener_candidates` | Screener signals with pattern type, ADTV, ML probabilities, and rejection codes. |
| `debate_transcripts` | Full transcripts of LangGraph multi-agent debates with conviction scores. |
| `agent_memory` | Longitudinal feedback memory and triple-barrier trade outcomes for prompt tuning. |
| `fundamentals_cache` | 7-day TTL JSON store of balance sheet, income statement, and promoter data. |
| `circuit_breaker_state` | High-water mark, monthly peak equity, and emergency kill-switch status. |
| `macro_weather` | EOD snapshot of global macro risk metrics, VIX, crude oil, and cash targets. |
| `equity_curve` | Historical daily portfolio total and core equity snapshots. |
| `paper_capital_config` | Dynamic paper capital configuration. |

---

## 9. Test Verification & Codebase Integrity

- **Automated Test Suite:** Full suite running across `tests/` covering database queue writers, ingestion pipelines, screeners, anti-trap shield, ML predictor, LangGraph debate graphs, risk arbiter, CPPI, Vol Target, and sentinel execution.
- **Test Result:** **237 passed, 0 failed** in 160.42 seconds.
- **Verification Command:** `pytest tests/ -q`

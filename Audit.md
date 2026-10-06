# AlphaSentinel — Master Quantitative, Shariah & Systems Engineering Audit

**Audit Date:** 6 October 2026  
**Auditor:** Quantitative Systems Specialist, Risk Arbiter & Islamic Finance Engineer  
**System Evaluated:** AlphaSentinel — Autonomous Algorithmic Swing Trading OS for NSE Small & Micro-Caps  
**Authoritative Shariah Benchmark:** Justice Mufti Muhammad Taqi Usmani Fatwa & [`Copy of halal stock 2.0.xlsx`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Copy%20of%20halal%20stock%202.0.xlsx)  
**Scope:** Complete repository codebase (231 files, ~19,000 lines of Python across `src/`, `scripts/`, `models/`, `research/`, `dashboard/`, `tests/`), active DuckDB database ([`alphasentinel.duckdb`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/alphasentinel.duckdb)), serialized ML artifacts ([`models/xgboost_global.pkl`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/xgboost_global.pkl), [`models/hmm_regime.pkl`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/hmm_regime.pkl)), and 4 prior audits located in the [`Audit/`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/) directory.

---

## 0. Executive Verdict & Readiness Scorecard

### 🛑 Master Verdict: NO-GO FOR LIVE TRADING

> **Live Capital Readiness Score: 0.0 / 10 (CRITICAL BLOCKER — STRICT NO-GO)**  
> **Paper Trading Validity Score: 3.2 / 10 (SEVERELY BIASED EXPERIMENT)**

AlphaSentinel demonstrates strong conceptual and architectural ambitions: deterministic risk primacy over LLM outputs, fail-closed kill switches, circuit-band awareness, Purged K-Fold cross-validation intent, and an extensive 214-test verification suite. However, under institutional forensic analysis, **the system cannot be deployed with real capital under any circumstances**. Furthermore, **its current paper trading execution is fundamentally unscientific**: phantom fills, lookback execution prices, unmanaged zombie trades, accounting double-counting, and broken corporate action adjustments inflate and distort simulated performance.

From a Shariah compliance perspective, while the intent is noble and the Usmani criteria are partially codified, **active non-compliant assets (e.g., conventional financial broking and wealth management firm `CHOICEIN`) have bypassed screening into DuckDB storage due to scraper regex omissions and empty sector cache fail-opens**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM READINESS SCORECARD                              │
├──────────────────────────────────┬───────┬─────────────────────────────────────────────┤
│ Domain                           │ Score │ Primary Failure Mode                        │
├──────────────────────────────────┼───────┼─────────────────────────────────────────────┤
│ 1. Shariah Compliance (Usmani)   │ 3.0   │ Scraper plural regex bug, empty sector leak │
│ 2. Quantitative Strategy & Alpha │ 1.5   │ Backtest on mega-cap banks; unproven edge   │
│ 3. Machine Learning & Regime     │ 2.0   │ 98-row AUC 0.50 model, 6-feature freeze lock│
│ 4. Risk Engine & Accounting      │ 3.0   │ Double-counted unrealized PnL, dead daily DD│
│ 5. Execution Realism & Sentinel  │ 2.5   │ Fill at trigger price; zombie -5% positions │
│ 6. Multi-Agent LLM Debate        │ 3.5   │ Missing scraper growth stats (N/A in prompt)│
│ 7. Data Pipeline & Microstructure│ 4.0   │ 1:2 bonus inversion; inactive ASM/GSM/Pledge│
│ 8. Software Architecture & Tests │ 6.5   │ Clean modular design, 214 tests passing     │
├──────────────────────────────────┼───────┼─────────────────────────────────────────────┤
│ OVERALL COMPOSITE                │ 3.2   │ STRICT NO-GO FOR REAL CAPITAL               │
└──────────────────────────────────┴───────┴─────────────────────────────────────────────┘
```

---

## 1. Forensic Fact-Checking & Validation of the 4 Prior Audits in `Audit/`

Four previous audit documents exist in [`Audit/`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/):
1. [`Audit/Audit.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/Audit.md) (DeepSeek-based detailed system audit)
2. [`Audit/DeepSeek-Chat-Exporter.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/DeepSeek-Chat-Exporter.md) (Full raw export of DeepSeek analysis)
3. [`Audit/Audit (1).md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/Audit%20%281%29.md) (Qwen3.8-Max audit)
4. [`Audit/chat-export-1791263757770.json`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/chat-export-1791263757770.json) (Raw JSON export of Qwen audit)

*(Note: An earlier historical baseline [`Audit/AlphaSentinel_Master_Audit_Report.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/AlphaSentinel_Master_Audit_Report.md) dated 2026-09-22 is also preserved for complete audit provenance).*

### 1.1 Comparative Empirical Accuracy
- **DeepSeek Audits ([`Audit/Audit.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/Audit.md), [`Audit/DeepSeek-Chat-Exporter.md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/DeepSeek-Chat-Exporter.md)): ~85% Valid.**  
  DeepSeek correctly identified core mathematical issues: the 3:15 PM trigger fill optimism in [`scripts/run_live_preview.py:561`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L561), the lookahead stop reconciliation, the backtest divergence on 10 Nifty mega-caps, and the statistical impossibility of the `ml_prob >= 0.75` gate.
- **Qwen Audits ([`Audit/Audit (1).md`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/Audit%20%281%29.md), [`Audit/chat-export-1791263757770.json`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Audit/chat-export-1791263757770.json)): ~40–45% Valid.**  
  While identifying broad conceptual issues (Dhan stub, lack of portfolio VaR), Qwen committed multiple factual hallucinations regarding the physical state of the repository, table schemas, and job scheduling.

### 1.2 Proof of the 10 Major Factual Hallucinations in Prior Audits

| # | Hallucination in Prior Audits | Actual Codebase & Physical Reality | Empirical Proof |
|---|-------------------------------|-----------------------------------|-----------------|
| **1** | *"Model file `models/hmm_regime.pkl` does not exist or is missing"* | The file **exists** (1,323 bytes). Prior audits failed to open it using standard `pickle.load()` (raising `_pickle.UnpicklingError: invalid load key, '\x0a'`) because it was serialized via `joblib.dump()`. | Inspecting [`scripts/fit_hmm_regime.py:54`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/fit_hmm_regime.py#L54) reveals `joblib.dump(raw_model, model_path)`. Executing `joblib.load('models/hmm_regime.pkl')` successfully deserializes the 3-state `GaussianHMM`. |
| **2** | *"`fundamentals_cache` schema is corrupt and missing columns"* | The schema in [`src/db/schema.sql:149-153`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/db/schema.sql#L149-L153) and DuckDB perfectly match: `symbol VARCHAR PRIMARY KEY`, `fundamentals_json TEXT`, `updated_at TIMESTAMPTZ`. | DuckDB pragma confirms 3 columns. The fundamentals are cleanly serialized as a unified JSON blob inside `fundamentals_json`. |
| **3** | *"`labeled_outcomes` table is missing and broken"* | **No such table was ever defined in the system architecture.** Prior audits fabricated this table name. | The system schema in [`src/db/schema.sql:130-146`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/db/schema.sql#L130-L146) tracks labels inside `agent_memory` (`outcome_label`, `triple_barrier_label`, `outcome_3d_pct`) and `screener_candidates`. |
| **4** | *"Feature pipeline injects synthetic Gaussian noise into price signals"* | **Completely fabricated by prior LLM audit.** No Gaussian noise injection exists in [`src/screening/ml_features.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/ml_features.py). | Mathematical features use Wilder's RSI, 20-day return rolling std (`vol_cluster`), 20-day EMA distance, and distance to 252-day high. |
| **5** | *"`symbol_sync.py`, `run_evaluator.py`, `run_feedback_loop.py` are dead code and never scheduled"* | **False.** All jobs are explicitly scheduled in [`scripts/run_scheduler.py:258-288`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_scheduler.py#L258-L288). | Lines 258, 285, 288 register `job_symbol_sync` at 06:00, `job_weekly_evaluator` at Sunday 20:00, and `job_weekly_feedback_loop` at Sunday 20:30. |
| **6** | *"`AWAITING_TRIGGER` status in `screener_candidates` is never polled intraday"* | **False.** It is actively polled by `job_trigger_watcher` every 10 minutes. | [`scripts/run_scheduler.py:267`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_scheduler.py#L267) registers `schedule.every(10).minutes.do(job_trigger_watcher)` which calls [`scripts/run_trigger_watcher.py:34`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_trigger_watcher.py#L34). |
| **7** | *"Active trades are stored in table `trade_ledger`"* | `trade_ledger` does **not exist**. | Live/paper positions are stored in `positions`, and paper order executions log to `paper_trades`. |
| **8** | *"Shariah gate should use AAOIFI Market Capitalization denominator"* | **Erroneous and contrary to the user's explicit mandate.** AAOIFI uses Market Cap; Mufti Taqi Usmani and [`Copy of halal stock 2.0.xlsx`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Copy%20of%20halal%20stock%202.0.xlsx) strictly mandate **Total Assets**. | Recommending Market Cap introduces equity bubble distortions and contradicts classical Islamic Fiqh rules specified in the project benchmark. |
| **9** | *"DuckDB lacks concurrency control and suffers unmitigated race conditions"* | DuckDB file writes are guarded by `portalocker` in [`src/db/session.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/db/session.py) with a 120-second timeout lock. | Single-writer serialized locks are enforced via file locking on `alphasentinel.duckdb.lock`. |
| **10** | *"Prompt key mismatches prevent the Bull/Bear agents from functioning"* | The prompt dictionary keys match `AgentState` in [`src/agents/debate_graph.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/agents/debate_graph.py). | The real bug is that scraped fundamentals omit growth statistics, passing `'N/A'`, not that the dictionary keys mismatch. |

---

## 2. Deep Shariah Compliance Evaluation (Mufti Taqi Usmani Fatwa & `Copy of halal stock 2.0.xlsx`)

### 2.1 The Fiqh Framework: Taqi Usmani Fatwa vs. AAOIFI
Prior audits advised shifting to AAOIFI Standard No. 21, which computes financial ratios against Market Capitalization:
$$\text{Debt Ratio}_{\text{AAOIFI}} = \frac{\text{Total Interest-Bearing Debt}}{\text{12-Month Trailing Average Market Capitalization}} \le 30\%$$

**Why this was rejected by Justice Mufti Muhammad Taqi Usmani:**
1. **Speculative Decoupling:** Market Capitalization reflects volatile market sentiment, speculative multiples, and liquidity bubbles, not the tangible economic substance of the enterprise.
2. **Inverted Solvency:** In a market bubble, a company's market capitalization can inflate 10x while debt remains constant, falsely categorizing a heavily indebted firm as "Halal". Conversely, in a market panic, a fundamentally sound firm with negligible debt can see its market cap collapse, falsely categorizing it as "Haram".
3. **Classical Fiqh Foundation:** In Islamic jurisprudence, a share represents an undivided proportionate ownership (*Musha'*) in the **real underlying assets** of the company. Therefore, financial leverage must be measured against the **Total Assets** (*Majmu' al-Mawjudat*).

### 2.2 The Authoritative Shariah Compliance Gates

Cross-checking [`Copy of halal stock 2.0.xlsx`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/Copy%20of%20halal%20stock%202.0.xlsx) (sheets: `Shariah`, `Sheet1`, `list`, `nse stock`, `Sheet19`), the system must strictly adhere to the following quantitative and qualitative gates:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           MUFTI TAQI USMANI AUTHORITATIVE SHARIAH COMPLIANCE GATES                     │
├────┬─────────────────────────────┬───────────────────────────────┬────────────┬────────────────────────┤
│ #  │ Compliance Gate             │ Authoritative Formula         │ Threshold  │ Excel Sheet & Cell Ref │
├────┼─────────────────────────────┼───────────────────────────────┼────────────┼────────────────────────┤
│ 1  │ Permissible Core Business   │ Industry & Activity Screening │ Halal Core │ Sheet1: G89:G92, list  │
│ 2  │ Interest-Bearing Debt       │ Total Debt / Total Assets     │ ≤ 33.0%    │ Sheet1: E68, F68       │
│    │                             │                               │ (≤ 37.0%)  │ Sheet19 variant formula│
│ 3  │ Cash + Interest Investments │ Cash & Investments / Assets   │ ≤ 33.0%    │ Sheet1: D/B*100 ≤ 33%  │
│ 4  │ Impure / Non-Sharia Income  │ Impure Income / Total Revenue │ ≤ 5.0%     │ Sheet1: G7, H7, F7     │
│ 5  │ Illiquid Assets Requirement │ Illiquid Assets / Total Assets│ ≥ 20.0%    │ Sheet1: E71, F71       │
│ 6  │ Net Liquid Assets vs MCap   │ Net Liquid Assets < MCap      │ Pass/Fail  │ Sheet1: F78, F80, H78  │
│ 7  │ Purification of Impure PnL  │ Proportionate Sadaqah Donation│ Mandated   │ Shariah: Row 23 (R23)  │
└────┴─────────────────────────────┴───────────────────────────────┴────────────┴────────────────────────┘
```

#### Detailed Mathematical Definitions:
1. **Rule 1: Permissible Business Activity (Qualitative Gate)**  
   The core operations must not violate Shariah principles.
   - *Strict Prohibitions:* Conventional banking, non-banking financial companies (NBFCs), interest broking, conventional insurance, breweries, distilleries, wineries, alcohol trading, tobacco/cigarettes, gambling/casinos, commercial entertainment/cinema/music broadcasting, hotels/bars, pork, cloning, and sugar mills operating commercial molasses distilleries (`list` sheet rows 2–7).
2. **Rule 2: Debt to Total Assets Ratio**  
   $$\text{Debt Ratio} = \frac{\text{Short-Term Borrowings} + \text{Long-Term Borrowings}}{\text{Total Assets}} \le 33.0\% \quad (\text{Strict Baseline: Sheet1: F68})$$
   *Note on the 37% Variant:* In certain regional fatwas and alternative sheets (`Sheet19`), the formula `=IF((C/B)*100>37, "NO", "YES")` reflects a ceiling of $\le 37\%$. However, per Justice Mufti Taqi Usmani's primary guidance and `Sheet1:F68`, the strict conservative standard is $\le 33.0\%$.
3. **Rule 3: Cash & Interest-Bearing Investments to Total Assets Ratio**  
   $$\text{Cash & Investments Ratio} = \frac{\text{Cash & Bank Balances} + \text{Interest-Bearing Short/Long-Term Investments}}{\text{Total Assets}} \le 33.0\%$$
   *Formula from sheet:* `=IF((D/B)*100>33, "NO", "YES")`. If a company holds excess cash or liquid interest securities $> 33\%$, it functions primarily as a financial intermediary rather than an operating business.
4. **Rule 4: Impure / Non-Operating Income Ratio**  
   $$\text{Impure Income Ratio} = \frac{\text{Interest Income} + \text{Dividends from Haram Investments}}{\text{Total Gross Revenue}} \le 5.0\%$$
   *(Sheet1: Row 7, Formula: `=E7/D9*100`, Threshold: `=IF(G7<=5, "Pass", "Fail")`).*
5. **Rule 5: Illiquid Assets Ratio (The Core Usmani Condition)**  
   Under classical Fiqh rules of *Sarf* (currency exchange), if an entity consists predominantly of cash and receivables, its shares can only be transacted at absolute par value (face value). To permit trading shares at market prices (above or below par), the company must possess substantial illiquid, tangible assets:
   $$\text{Illiquid Assets} = \text{Gross Fixed Assets} + \text{Capital Work-in-Progress (CWIP)} + \text{Inventories} + \text{Intangibles}$$
   $$\text{Illiquid Ratio} = \frac{\text{Illiquid Assets}}{\text{Total Assets}} \ge 20.0\% \quad (\text{Sheet1: Row 71, Formula: } =IF(E71 \ge 20, \text{"Pass"}, \text{"Fail"}))$$
6. **Rule 6: Net Liquid Assets vs. Market Capitalization**  
   $$\text{Net Liquid Assets} = \text{Total Assets} - \text{Illiquid Assets} - \text{Total External Liabilities}$$
   $$\text{Net Liquid Assets per Share} < \text{Market Price per Share} \iff \text{Total Net Liquid Assets} < \text{Market Capitalization}$$
   *(Sheet1: Row 78/80: `=IF(F78 < F80, "Pass", "Fail")`).* If net liquid assets exceed market capitalization, buying the share is equivalent to buying discounted cash with surplus assets—a direct form of *Riba al-Fadl*.
7. **Rule 7: Mandatory Purification Math (Sadaqah Disposal)**  
   Per `Shariah!R23`:
   $$\text{Purification Donation (INR)} = \text{Dividend or Capital Gain (INR)} \times \frac{\text{Impure Income}}{\text{Total Gross Revenue}}$$
   *Cell Formula:* `=if(Sheet1!G93<>"Compliant","",iferror(if(AND(T25<>"",T21<>""),("Donate Divident/Profit Rs."&int(T25%*T21)),""),""))`. All impure gains must be physically donated to the poor without intention of spiritual reward (*Niyyah of Thawab*).
8. **Sugar Mills Operating Molasses Distilleries:**  
   Sugar mills in India crush sugarcane and produce molasses as an inevitable byproduct. Many listed sugar mills (e.g. Balrampur Chini, Triveni Engineering, Dwarikesh) operate integrated commercial distilleries that ferment molasses into potable alcohol (rectified spirit, extra neutral alcohol, country liquor, and IMFL) in addition to ethanol. Under Mufti Taqi Usmani's rulings, any company generating commercial revenues from potable alcohol is strictly non-compliant, regardless of whether its primary industry is tagged as "Sugar".

---

### 2.3 Critical Shariah Vulnerabilities in the Codebase

#### Vulnerability S-01: The Live Scraper Plural Regex Defect
**Location:** [`src/ingestion/screener_scraper.py:170-175`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/screener_scraper.py#L170-L175)  
**Root Cause:** The scraper extracts breadcrumbs into `sector_candidates`, then attempts to detect prohibited industries using raw string inclusion against singular keywords:
```python
# Current defective code:
from src.screening.shariah_filter import PROHIBITED_SECTORS
for cand_txt in sector_candidates:
    cand_low = cand_txt.lower()
    if any(p in cand_low for p in PROHIBITED_SECTORS) and cand_txt not in sector_name:
        sector_name = f"{sector_name} - {cand_txt}" if sector_name else cand_txt
        break
```
Because `PROHIBITED_SECTORS` contains `"brewery"`, `"distillery"`, `"winery"`, but Screener.in tags companies with `"Breweries"`, `"Distilleries"`, `"Wineries"`:
- `"brewery" in "breweries"` $\to$ **`False`**
- `"distillery" in "distilleries"` $\to$ **`False`**
- `"winery" in "wineries"` $\to$ **`False`**

Consequently, companies operating commercial distilleries or breweries are assigned generic industry titles (e.g., `"Beverages"` or `"Sugar"`), completely evading the sector filter!

#### Vulnerability S-02: Empty Sector Cache Fail-Open Bug
**Location:** [`src/screening/shariah_filter.py:34-41`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/shariah_filter.py#L34-L41)  
If Screener.in fails to return breadcrumbs, `sector_name` is set to `""`.
In [`check_shariah_compliance()`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/shariah_filter.py#L23):
```python
sector_lower = sector_name.lower()
for prohibited in PROHIBITED_SECTORS:
    ...
    if re.search(pattern, sector_lower):
        return False, f"NON_COMPLIANT_SECTOR_{prohibited.upper()}"
```
When `sector_name = ""`, no keyword triggers. If the balance sheet numbers happen to meet the debt and income thresholds, a prohibited business passes through undetected.

#### Vulnerability S-03: Active Haram Asset in DuckDB (`CHOICEIN`)
**Location:** [`alphasentinel.duckdb`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/alphasentinel.duckdb) (`fundamentals_cache`)  
Forensic inspection of the live database revealed:
```json
{
  "symbol": "CHOICEIN",
  "sector_name": "",
  "debt_to_assets": 0.2548,
  "illiquid_ratio": 0.1131,
  "interest_income_ratio": 0.0259,
  "net_liquid_assets_crores": 1268.0,
  "market_cap_crores": 16527.0
}
```
*(Note on prior audit claims: Prior audits claimed `CHOICEIN` was present in `trade_ledger`. In reality, `trade_ledger` does not exist; `CHOICEIN` was stored in `fundamentals_cache`).*  
**Fatal Violations:**
1. **Core Business Prohibited:** Choice International Limited is a conventional financial services, equity broking, wealth management, and NBFC institution.
2. **Illiquid Ratio Breach:** `illiquid_ratio = 11.31%`, which is far below the mandatory **20.0%** Usmani requirement.
3. **How it bypassed the gate:** `sector_name` was stored as `""`, evading the broking keyword screen.

---

## 3. Layer-by-Layer Forensic Breakdown: Weaknesses, Code Fixes & Quant Alternatives

---

### Layer 1: Ingestion, Screening, Microstructure & Anti-Trap Shield

#### Weakness 1.1: The Top-15 Starvation Bug
- **Location:** [`scripts/run_live_preview.py:293-364`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L293-L364)
- **Defect:** After technical screening, candidates are sorted by momentum and arbitrarily truncated to the top 15:
  ```python
  candidate_pool = raw_candidates[:15]
  ```
  Only then are these 15 evaluated for Shariah compliance:
  ```python
  for item in candidate_pool:
      is_sh, sh_reason = check_shariah_compliance(funds, sector_name=sec)
  ```
  If 13 or 14 of the top 15 technical momentum leaders are conventional banks, NBFCs, or high-debt firms (common in Indian bull runs), the pipeline starves down to 0–1 trades. Highly compliant setups sitting at rank 16 or 18 are discarded without ever being inspected.
- **Code Fix:** Filter candidates by Shariah compliance iteratively or pre-filter the liquid universe using `fundamentals_cache` before technical truncation.
- **Quant Alternative:** Construct a persistent `shariah_universe_master` table updated weekly. Technical screening should execute **only** on the pre-approved Shariah universe.

#### Weakness 1.2: VCP Range Calculation from Close Prices
- **Location:** [`src/screening/vcp_screener.py:117-135`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/vcp_screener.py#L117-L135)
- **Defect:** While 52-week extremes use `high_df` and `low_df`, moving average and consolidation depth metrics rely on `close_df`. Intraday whipsaws and supply-tail rejections (which invalidate genuine Minervini contractions) are smoothed out.
- **Code Fix:** Incorporate true average true range (ATR) and intra-candle contraction ratios:
  $$\text{Contraction Ratio}_t = \frac{\text{High}_{t} - \text{Low}_{t}}{\text{SMA}(\text{High} - \text{Low}, 20)} \le 0.60$$

#### Weakness 1.3: Inactive ASM/GSM, Pledge & P/E Shields
- **Location:** [`src/screening/anti_trap_shield.py:111-132`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/anti_trap_shield.py#L111-L132), [`src/db/schema.sql:26-27`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/db/schema.sql#L26-L27)
- **Defect:**
  1. `bhavcopy_daily` sets `is_asm` and `is_gsm` default to `FALSE`. Standard NSE Bhavcopy files do not contain surveillance flags; these are issued via separate circulars. Thus, ASM/GSM checks are permanently inactive.
  2. `Layer 4` promoter pledge trend checks `fundamentals.get("pledge_trend_3m")`, which defaults to 0.0 because promoter pledge history is never populated.
  3. `Layer 5` P/E filter is explicitly disabled by developer comments ("Value investing metrics are irrelevant for momentum swings").

---

### Layer 2: Machine Learning Alpha Engine & Regime Detection

#### Weakness 2.1: The 6-Feature Legacy Lock
- **Location:** [`scripts/run_model_training.py:270-287`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_model_training.py#L270-L287)
- **Defect:** When retraining the model, the script attempts to inspect the existing champion model:
  ```python
  if MODEL_PATH.exists():
      with open(MODEL_PATH, "rb") as _f:
          _existing_model = pickle.load(_f)
      existing_features = getattr(_existing_model, 'feature_names_in_', None)
      if existing_features is not None and len(existing_features) < len(FEATURE_COLS):
          effective_feature_cols = list(existing_features)
  ```
  Because the serialized model on disk ([`models/xgboost_global.pkl`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/xgboost_global.pkl)) was trained on the old 6-feature set, **this block permanently locks any future retraining to 6 features**, completely ignoring `delivery_ratio`, `adtv_log`, and `momentum_6m`.
- **Code Fix:** Remove this backward-compatibility lock. Retraining must always utilize the full 9-feature institutional specification.

#### Weakness 2.2: The 98-Row Artifact & Statistically Unreachable Threshold
- **Location:** [`models/xgboost_global_meta.json`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/xgboost_global_meta.json), [`scripts/run_live_preview.py:537`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L537)
- **Defect:**
  - The model was trained on **exactly 98 rows** (`"row_count": 98`).
  - The live preview enforces `ml_prob >= 0.75` for control and `0.65` for variant.
  - In a properly calibrated binary classifier with balanced target distribution, tree models rarely output probabilities above $0.70$ without severe over-fitting. A threshold of $0.75$ either vetoes 100% of legitimate trades or forces the system to trade only on extreme data anomalies.

#### Weakness 2.3: Triple-Barrier Same-Day Barrier Collision & Timeout Skew
- **Location:** [`scripts/run_model_training.py:105-122`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_model_training.py#L105-L122)
- **Defect:**
  ```python
  for i in range(window_len):
      h = float(high_series.iloc[i])
      l = float(low_series.iloc[i])
      if l <= lower_barrier:
          return -1
      if h >= upper_barrier:
          return 1
  ```
  On a volatile expansion day where both the high and low cross the barriers, checking `l <= lower_barrier` first assumes the stop loss was hit first. On daily EOD data without intraday ticks, the true path is unknowable.
  Furthermore, on timeouts:
  ```python
  terminal_close = float(close_series.iloc[window_len - 1])
  if terminal_close > entry_price:
      return 1
  ```
  If a stock is flat at $+0.02\%$ after 5 days, it is classified as $+1$ (Win), identical to a $+15\%$ explosive breakout.

#### Weakness 2.4: Row-Index PurgedKFold Leakage
- **Location:** [`src/utils/cv.py:33-46`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/utils/cv.py#L33-L46), [`scripts/run_model_training.py:333-338`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_model_training.py#L333-L338)
- **Defect:** While `PurgedKFoldEmbargo` correctly groups dates when given `unique_dates`, it computes static indices based solely on date order:
  ```python
  embargo_lo = max(0, test_start - self.embargo_days)
  embargo_hi = min(n, test_end + self.embargo_days)
  ```
  Because the triple-barrier label window spans up to 5 trading days ($t+1$ to $t+5$), observations in the training set immediately preceding `test_start` have labels that depend directly on price action occurring inside the test fold.
  More critically, if `cv.split` is called on row indices (or if calendar dates are not aligned across symbols), observations on the same calendar day across different stocks leak across training and test splits, artificially inflating cross-validation AUC while collapsing out-of-sample generalization.
- **Code Fix:** Implement sample-specific label timestamp tracking ($t_0, t_1$) per López de Prado: purge any training observation $i$ where $t_{1, i} \ge t_{0, \text{test}}$, and embargo any training observation following the test window.

#### Weakness 2.5: Missing Live Tick `total_traded_val` & Turnover Blindness
- **Location:** [`scripts/run_live_preview.py:315-335`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L315-L335)
- **Defect:** At 3:15 PM, the live preview pulls live quotes via `yf.download(cand_tickers_ns, period="1d")`. It extracts only `Close` to update `current_price`. It **completely ignores live volume and live traded value**:
  $$\text{Live Turnover} = \text{Close}_{\text{live}} \times \text{Volume}_{\text{live}}$$
  The ₹25 Lakhs ADTV filter ran only on yesterday's historical Bhavcopy. If an illiquid micro-cap experiences a severe liquidity freeze today (trading only ₹40,000 all session), the system remains completely blind and attempts to execute a ₹100,000 order into an illiquid trap.

#### Weakness 2.6: Disconnected Bull-Biased HMM
- **Location:** [`models/hmm_regime.pkl`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/hmm_regime.pkl), [`scripts/fit_hmm_regime.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/fit_hmm_regime.py)
- **Defect:** Deserializing [`models/hmm_regime.pkl`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/models/hmm_regime.pkl) via `joblib.load()` reveals the fitted state means:
  $$\mu = [0.000246, \; 0.000329, \; 0.001178]$$
  **All three states have positive daily mean returns.** The model was fit during a sustained bull run. State 0, intended to represent a crisis or bear regime, has a positive mean return ($+0.025\%$/day). The HMM has never seen a true bear market and is completely incapable of detecting market distress.

---

### Layer 3: Risk Management, Accounting & Corporate Actions

#### Weakness 3.1: Inverted `equity_curve.core_equity` Accounting Bug
- **Location:** [`scripts/run_eod_reconciliation.py:438-442`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_eod_reconciliation.py#L438-L442), [`src/portfolio/state.py:107-126`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/portfolio/state.py#L107-L126)
- **Defect:**
  In [`run_eod_reconciliation.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_eod_reconciliation.py):
  ```python
  db_write("""
      INSERT OR REPLACE INTO equity_curve (
          trade_date, total_equity, core_equity, unrealized_pnl
      ) VALUES (CURRENT_DATE, ?, ?, ?);
  """, (total_eq, core_eq - unrealized, unrealized))
  ```
  `equity_curve.core_equity` is stored as **realized-only equity** (`core_eq - unrealized`).
  However, in [`src/portfolio/state.py:107`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/portfolio/state.py#L107):
  ```python
  core_equity = initial_capital + realized_pnl_total + unrealized_pnl_total
  ```
  And then to recover High-Water Mark:
  ```python
  eq_res = db_conn.execute("SELECT MAX(core_equity) FROM equity_curve;").fetchone()
  ```
  `state.py` compares its live `core_equity` (which includes unrealized gains) against the historical `equity_curve.core_equity` (which stripped unrealized gains). This systemic mismatch corrupts the lifetime High-Water Mark and drawdown calculations.

#### Weakness 3.2: Broken Daily Drawdown Guard
- **Location:** [`src/risk/daily_drawdown_guard.py:68-111`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/risk/daily_drawdown_guard.py#L68-L111)
- **Defect:**
  1. The guard queries `equity_curve` for today's opening equity:
     ```python
     row = conn.execute("SELECT core_equity FROM equity_curve WHERE trade_date = ?", (today,)).fetchone()
     ```
     Because `equity_curve` is written only at 18:30 EOD, this query **always returns `None` during trading hours**.
  2. It falls back to `get_portfolio_state()`, where `core_equity = initial_capital + realized_pnl + unrealized_pnl`.
  3. It then re-adds `todays_unrealized_pnl`:
     ```python
     current_equity = starting_equity + todays_unrealized_pnl
     ```
     This **double-counts unrealized PnL**.
  4. More critically, it queries `unrealized_pnl` only from `positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')`. Any position stopped out intraday with realized losses is completely omitted. If 3 positions hit stop-loss intraday for a $-9\%$ loss, the daily drawdown guard detects $0\%$ drawdown.

#### Weakness 3.3: EOD Case D -5% "Zombie Trade" Generator
- **Location:** [`scripts/run_eod_reconciliation.py:356-360`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_eod_reconciliation.py#L356-L360)
- **Defect:**
  ```python
  if risk_pct <= -5.0 or (lower_c is not None and ltp <= lower_c):
      db_write("""
          UPDATE positions SET status = 'MARKED_FOR_CLOSURE', current_ltp = ?, unrealized_pnl = ? WHERE id = ?;
      """, (ltp, unrealized_pnl, pos_id))
  ```
  If a stock experiences normal small-cap volatility and drops $-5.1\%$ from entry (even when its ATR stop is set at $-7.5\%$), it is converted to `MARKED_FOR_CLOSURE`.
  **Nothing in the codebase ever closes `MARKED_FOR_CLOSURE` positions.**
  [`scripts/run_sentinel.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_sentinel.py) only queries `WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')`. The position becomes a permanent unmonitored zombie.

#### Weakness 3.4: 1:2 Bonus Ratio Inversion
- **Location:** [`src/ingestion/corporate_actions.py:43-45`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/corporate_actions.py#L43-L45)
- **Defect:**
  ```python
  elif act == "BONUS":
      total_shares = ratio_from + ratio_to
      multiplier = (min(ratio_from, ratio_to) / total_shares) if total_shares > 0 else 1.0
  ```
  In a standard **1:2 bonus** (1 new share for every 2 held):
  - `ratio_from = 1`, `ratio_to = 2`. Total shares = 3.
  - The correct adjustment factor for historical prices is:
    $$\text{Multiplier} = \frac{\text{Old Shares}}{\text{New Total Shares}} = \frac{2}{1 + 2} = \frac{2}{3} \approx 0.6667$$
  - The code computes:
    $$\text{Multiplier} = \frac{\min(1, 2)}{1 + 2} = \frac{1}{3} \approx 0.3333$$
  **Historical prices are slashed by 50% too much**, creating fake $+100\%$ breakouts on historical charts, corrupting ML labels and technical indicators.

#### Weakness 3.5: Fail-Open Correlation & Volatility Targeting Guards
- **Location:** [`src/risk/correlation_guard.py:97-100`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/risk/correlation_guard.py#L97-L100), [`src/risk/vol_target.py:89-105`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/risk/vol_target.py#L89-L105)
- **Defect:**
  In [`correlation_guard.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/risk/correlation_guard.py):
  ```python
  # Fails OPEN (allows trade) on infrastructure/data errors — this is a soft risk guard.
  if df.empty or len(returns) < 15:
      return True, "CORR_GUARD_SKIPPED: insufficient overlapping history.", {}
  except Exception as exc:
      return True, f"CORR_GUARD_ERROR (failing open): {exc}", {}
  ```
  In [`vol_target.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/risk/vol_target.py):
  ```python
  if len(symbols) < 2 or cov_matrix is None:
      return 1.0  # Returns 1.0 (100% position size) when data is missing!
  ```
  If data is absent, history is brief, or queries fail, both modules allow 100% full sizing. In institutional risk management, risk guards must strictly **fail CLOSED** (halt trade or scale down to minimum size).

---

### Layer 4: Multi-Agent LLM Debate Engine

#### Weakness 4.1: Missing Fundamentals Feeding "N/A" to LLM Prompts
- **Location:** [`src/agents/debate_graph.py:151-155`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/agents/debate_graph.py#L151-L155), [`src/ingestion/screener_scraper.py:194-220`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/screener_scraper.py#L194-L220)
- **Defect:** The Bull and Bear prompt templates explicitly ask the LLM to assess:
  ```
  - QoQ Profit Growth: {funds.get('profit_growth_pct', 'N/A')}%
  - Profit Growth: {fundamentals.get('profit_growth_pct', 'N/A')}% | Sales Growth: {fundamentals.get('sales_growth_pct', 'N/A')}%
  ```
  [`screener_scraper.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/screener_scraper.py) parses balance sheet assets, sales, and borrowings, but **never scrapes profit growth or sales growth percentage fields**.
  The LLM agents are fed `'N/A'` for the primary momentum criteria they are instructed to debate.

#### Weakness 4.2: Premature `agent_memory` APPROVE Persistence
- **Location:** [`src/agents/debate_graph.py:321-337`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/agents/debate_graph.py#L321-L337)
- **Defect:** In `research_judge_node`, before `conviction_gate_node` executes and before live preview checks `gate_approved`, a record is inserted into `agent_memory`:
  ```python
  state.get("risk_verdict", "APPROVE")
  ```
  If the candidate is subsequently rejected for low conviction ($< 7.0$) or low ML score, `agent_memory` already recorded `previous_verdict = 'APPROVE'`. Future runs reading historical memory believe the system previously endorsed the trade.

#### Weakness 4.3: Conviction Threshold Drift
- **Location:** [`src/agents/debate_graph.py:360`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/agents/debate_graph.py#L360) vs [`scripts/run_live_preview.py:537`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L537)
- **Defect:** `conviction_gate_node` enforces `threshold = 6.5`, but `run_live_preview.py` requires `conviction >= 7.0`. Trades passing the graph gate are subsequently killed by the runner.

---

### Layer 5: Execution, Sentinel, Trigger Watcher & Backtesting

#### Weakness 5.1: Faded Intraday High Execution Bug
- **Location:** [`scripts/run_trigger_watcher.py:118-122`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_trigger_watcher.py#L118-L122)
- **Defect:**
  ```python
  current_p = float(close_series.iloc[-1])
  high_p = float(high_series.max())
  if high_p >= trigger_p:
      # Places order at current_p!
      order_id = broker.place_order(symbol=sym, price=current_p, ...)
  ```
  If a stock spikes above the trigger price at 10:00 AM (e.g. ₹105 vs trigger ₹100), but by 13:00 PM collapses into a trap wick at ₹92:
  `high_p >= trigger_p` is **still True**! The watcher triggers an order and buys at ₹92 right in the middle of a collapsing breakdown.
- **Code Fix:** Require breakout confirmation: `if current_p >= trigger_p and high_p >= trigger_p:`.

#### Weakness 5.2: Sentinel Blind to Profit Targets (T1 & T2)
- **Location:** [`scripts/run_sentinel.py:31-38`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_sentinel.py#L31-L38)
- **Defect:** The 15-minute sentinel queries:
  ```sql
  SELECT id, symbol, entry_price, trailing_stop_loss, atr, quantity, status, peak_high, realized_pnl
  FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED');
  ```
  **It never queries `target_1` or `target_2`.**
  Target 1 trims and Target 2 runner exits are evaluated **only once per day at 18:30 PM** in [`scripts/run_eod_reconciliation.py`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_eod_reconciliation.py).
  If a small-cap surges $+8\%$ to Target 1 at 11:00 AM and retraces by 15:30 PM, the sentinel fails to take profits. The position remains untrimmed.

#### Weakness 5.3: 3:15 PM Order Fill at Trigger Price (Paper Optimism)
- **Location:** [`scripts/run_live_preview.py:561`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L561)
- **Defect:**
  ```python
  trade_id = execute_paper_trade(
      symbol=symbol, 
      price=candidate["trigger_price"],  # <-- DEFECT!
      ...
  )
  ```
  At 3:15 PM, if the breakout stock has moved from the trigger of ₹100 up to ₹104.50, the order is booked at **₹100**. This gifts the paper portfolio an immediate $+4.5\%$ free unrealized gain.
- **Code Fix:** Execute at `price = max(candidate["current_price"], candidate["trigger_price"]) * (1.0 + slippage_pct)`.

#### Weakness 5.4: Backtest Harness Complete Disconnection
- **Location:** [`research/backtest_harness.py:9-33`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/research/backtest_harness.py#L9-L33), [`research/data_loader.py:6-9`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/research/data_loader.py#L6-L9)
- **Defect:** As explicitly documented in the backtest module header:
  - Backtest runs on **10 Nifty mega-caps** (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `HINDUNILVR`, `ICICIBANK`, `SBIN`, `BHARTIARTL`, `ITC`, `LT`).
  - Three of these stocks (`HDFCBANK`, `ICICIBANK`, `SBIN`) are conventional commercial banks that the Shariah gate would reject.
  - `ITC` is a tobacco conglomerate.
  - The backtest does not apply the Shariah filter, does not apply the 6-layer anti-trap shield, does not apply the XGBoost model, and does not run the LLM debate.
  - **There is zero statistical evidence that the production strategy has positive expectancy.**

---

## 4. Actionable Remediation Plan & Implementation Blueprint

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ALPHASENTINEL REMEDIATION ROADMAP (4 PHASES)                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 0: IMMEDIATE HOTFIXES (Days 1–2) — Zero Capital Risk                             │
│ • Fix 1:2 bonus ratio multiplier in corporate_actions.py                               │
│ • Fix plural regex in screener_scraper.py and block empty sector fail-opens            │
│ • Purge non-compliant assets (CHOICEIN) from DuckDB cache                              │
│ • Correct 3:15 PM fill price in run_live_preview.py to live market price               │
│ • Require current_price >= trigger_price in run_trigger_watcher.py                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: ACCOUNTING & SHARIAH RESTORATION (Week 1)                                     │
│ • Re-align equity_curve and state.py core_equity definitions                           │
│ • Eliminate zombie MARKED_FOR_CLOSURE logic; implement automated closure routine       │
│ • Wire Target 1 and Target 2 monitoring into run_sentinel.py                           │
│ • Scrape profit_growth_pct and sales_growth_pct in screener_scraper.py                 │
│ • Remove 6-feature legacy lock in run_model_training.py                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: QUANTITATIVE ALPHA & RISK ENGINE RE-ARCHITECTURE (Week 2)                     │
│ • Re-order live preview: Shariah filter BEFORE technical candidate pool truncation     │
│ • Fix daily drawdown guard: query opening equity + intraday realized & unrealized PnL  │
│ • Convert correlation & vol guards to fail CLOSED on missing data                      │
│ • Calibrate HMM regime on 5-year log returns including bear markets                    │
│ • Align conviction threshold to 7.0 universally across graph and runner                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: INSTITUTIONAL ML & WALK-FORWARD BACKTEST OVERHAUL (Weeks 3–4)                 │
│ • Re-train XGBoost on full NSE universe (>15,000 samples) with 9 features              │
│ • Implement PurgedKFold with sample-level label end timestamps                         │
│ • Re-write research/backtest_harness.py on true Shariah small-cap universe (2020–2026) │
│ • Complete DhanHQ API live order routing with hardware kill switch                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Phase 0: Immediate Critical Hotfixes

#### Code Fix P0-1: Correct Bonus Ratio Multiplier
In [`src/ingestion/corporate_actions.py:43-45`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/corporate_actions.py#L43-L45):
```python
# REPLACE:
elif act == "BONUS":
    total_shares = ratio_from + ratio_to
    multiplier = (min(ratio_from, ratio_to) / total_shares) if total_shares > 0 else 1.0

# WITH:
elif act == "BONUS":
    # In Indian convention 'X:Y' bonus means X bonus shares for every Y existing shares.
    # New total shares = ratio_to + ratio_from. Existing shares = ratio_to.
    total_shares = ratio_from + ratio_to
    multiplier = (ratio_to / total_shares) if total_shares > 0 else 1.0
```

#### Code Fix P0-2: Shariah Scraper Plural Regex & Fail-Closed Sector
In [`src/ingestion/screener_scraper.py:170-175`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/ingestion/screener_scraper.py#L170-L175):
```python
# REPLACE with proper word-boundary and inflection regex matching:
import re
from src.screening.shariah_filter import PROHIBITED_SECTORS

for cand_txt in sector_candidates:
    cand_low = cand_txt.lower()
    for prohibited in PROHIBITED_SECTORS:
        pattern = rf'\b{prohibited[:-1]}(?:y|ies)\b' if prohibited.endswith("y") else rf'\b{prohibited}(?:s|es)?\b'
        if re.search(pattern, cand_low):
            sector_name = f"{sector_name} - {cand_txt}" if sector_name else cand_txt
            break
```

In [`src/screening/shariah_filter.py:34`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/src/screening/shariah_filter.py#L34):
```python
# Add fail-closed guard against empty sector name:
if not sector_name or not sector_name.strip():
    return False, "FAIL_CLOSED_EMPTY_SECTOR_NAME"
```

#### Code Fix P0-3: Purge Haram Assets from DuckDB
Execute database purge command:
```sql
DELETE FROM fundamentals_cache WHERE symbol = 'CHOICEIN';
DELETE FROM screener_candidates WHERE symbol = 'CHOICEIN';
```

#### Code Fix P0-4: Realistic 3:15 PM Paper Execution Fill Price
In [`scripts/run_live_preview.py:560-562`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_live_preview.py#L560-L562):
```python
# REPLACE:
trade_id = execute_paper_trade(
    symbol=symbol, 
    price=candidate["trigger_price"], 
    ...
)

# WITH:
fill_price = max(float(candidate["current_price"]), float(candidate["trigger_price"]))
trade_id = execute_paper_trade(
    symbol=symbol, 
    price=fill_price, 
    ...
)
```

#### Code Fix P0-5: Faded Intraday High Breakout Confirmation
In [`scripts/run_trigger_watcher.py:121`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_trigger_watcher.py#L121):
```python
# REPLACE:
if high_p >= trigger_p:

# WITH:
# Require that the live price currently sustains the breakout, not just a faded morning spike:
if current_p >= trigger_p and high_p >= trigger_p:
```

---

### 4.2 Phase 1: Accounting, Risk & Execution Realism

#### Code Fix P1-1: Eliminate Zombie Trades & Fix Case D
In [`scripts/run_eod_reconciliation.py:352-364`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_eod_reconciliation.py#L352-L364):
- Remove the arbitrary $-5\%$ closure trigger. Stop losses must be governed solely by the disciplined ATR trailing framework.
- If a stock is genuinely trapped at lower circuit, flag it and execute an automated market-on-open (AMO) exit order on the next trading session.

#### Code Fix P1-2: Wire Profit Targets into Sentinel
In [`scripts/run_sentinel.py:32-38`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_sentinel.py#L32-L38):
- Include `target_1` and `target_2` in the position query.
- When `high_price >= target_1` on an `OPEN` position, execute the 50% partial trim and ratchet the remaining stop to breakeven immediately intraday, rather than waiting for 18:30 EOD.

---

### 4.3 Phase 2: Quantitative Alpha & ML Pipeline Overhaul

#### Code Fix P2-1: Remove 6-Feature Legacy Lock
In [`scripts/run_model_training.py:270-287`](file:///c:/Users/Md%20Ganim/Desktop/trading%20agents/scripts/run_model_training.py#L270-L287):
Delete lines 270–287 entirely. Ensure `effective_feature_cols = FEATURE_COLS` (all 9 institutional features).

#### Quant Alternative: Micro-Cap Purged Cross-Validation
Retrain XGBoost across 5 years of historical Bhavcopy data (>20,000 samples) utilizing the canonical `PurgedKFoldEmbargo` with:
- Grouping strictly by unique trading dates.
- Minimum out-of-sample sample size per fold $\ge 2,500$ observations.
- Dynamic label end timestamp ($t_1$) tracking.
- Target: Upper barrier $+3.0$ ATR, Lower barrier $-1.8$ ATR, 10-day horizon.

---

## 5. Go / No-Go Verification Criteria for Live Capital Deployment

Before `PAPER_TRADING_MODE` is disabled and real capital is routed to a broker, the system must satisfy 100% of the following verification criteria:

- [ ] **Shariah Integrity:** Zero non-compliant assets in `fundamentals_cache`, `screener_candidates`, or `positions`.
- [ ] **Accounting Alignment:** `equity_curve` and `state.py` report mathematically identical High-Water Mark and drawdown values across 30 consecutive trading sessions.
- [ ] **Drawdown Protection:** Simulated intraday $-3\%$ breach triggers immediate full session freeze.
- [ ] **Sentinel Target Execution:** Intraday Target 1 trim verified on live 15-minute ticks.
- [ ] **ML Statistical Power:** Retrained XGBoost demonstrates conservative out-of-sample ROC-AUC $> 0.56$ across 5 purged folds with 5-day embargo.
- [ ] **Institutional Backtest:** Full strategy backtest on 2020–2026 Shariah-compliant NSE small/micro-cap universe achieves Sharpe Ratio $> 1.2$ after deducting $0.25\%$ round-trip transaction and impact costs.
- [ ] **Execution Safety:** DhanHQ broker integration passes end-to-end integration tests with sub-second order cancellation and automated kill-switch verified.

---
*Report Authoritatively Compiled by AlphaSentinel Principal Quant & Systems Auditor.*

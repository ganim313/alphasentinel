# AlphaSentinel Shariah Trading & Quantitative Invariants

These invariants govern all screening, scraping, backtesting, database caching, and order execution modules in AlphaSentinel and align strictly with **Mufti Taqi Usmani's Islamic Finance Screening Principles** and the canonical **`Copy of halal stock 2.0.xlsx`** reference workbook.

## 1. Qualitative Business Activity Screen (Fail-Closed)
- **Fail-Closed on Missing Sector**: Any symbol with an empty, whitespace-only, or unresolved `sector_name` MUST fail closed (`FAIL_CLOSED_EMPTY_SECTOR_NAME`).
- **Prohibited Sectors & Sub-Industries**:
  - Conventional Banking, NBFCs, Microfinance, Housing Finance, Leasing, Stockbroking, Wealth Management, Asset Management, and Insurance (`bank`, `nbfc`, `finance`, `financial`, `insurance`, `broking`, `stockbroking`, `lending`).
  - Alcohol, Breweries, Distilleries, Wineries, and **Sugar-Mill Molasses Alcohol Distilleries** (`alcohol`, `brewery`, `distillery`, `winery`, `liquor`, `spirits`, plus explicit `PROHIBITED_SYMBOLS` from `Sheet19` and `list`).
  - Tobacco, Cigarettes, Gutkha, Pan Masala (`tobacco`, `cigarette`).
  - Gambling, Casinos, Lotteries, Betting, Gaming (`gambling`, `casino`, `betting`, `lottery`).
  - Pork & Non-Halal Meat Processing (`pork`, `bacon`, `ham`, `swine`).
  - Conventional Media, Cinema, Entertainment, and Non-Compliant Hospitality (`entertainment`, `cinema`, `media`, `broadcasting`, `hotel`, `hospitality`, `resort`).
  - Conventional Weapons & Defence Munitions (`weapons`, `defense`, `defence`, `arms`, `ammunition`).

## 2. Quantitative Financial Ratio Screens (Mufti Taqi Usmani / `Copy of halal stock 2.0.xlsx`)
1. **Interest-Bearing Debt to Total Assets (< 33%)**:
   $$\frac{\text{Total Borrowings}}{\text{Total Assets}} < 33\% \quad (< 0.33)$$
2. **Impure / Non-Compliant Income to Total Revenue (< 5%)**:
   $$\frac{\text{Other Income (Impure Income Proxy)}}{\text{Total Revenue } (\text{Sales} + \text{Other Income})} < 5\% \quad (< 0.05)$$
   - *Critical Scraper Rule*: Never map Screener.in's P&L `"Interest"` row to Interest Income—on Screener.in, P&L `"Interest"` is **Interest Expense (Finance Cost)**. Always use `Other Income` as the conservative numerator proxy.
3. **Illiquid Assets to Total Assets (>= 20%)**:
   $$\frac{\text{Fixed Assets} + \text{CWIP} + \text{Inventories} + \text{Intangible Assets}}{\text{Total Assets}} \ge 20\% \quad (\ge 0.20)$$
4. **Cash & Interest-Bearing Investments to Total Assets (<= 33%)**:
   $$\frac{\text{Cash Equivalents} + \text{Investments}}{\text{Total Assets}} \le 33\% \quad (\le 0.33)$$
5. **Net Liquid Assets vs. Market Capitalization**:
   $$\text{Net Liquid Assets } (\text{Total Assets} - \text{Illiquid Assets} - \text{Total Liabilities}) \le \text{Market Cap}$$
6. **Accounts Receivable to Total Assets (< 49%)**:
   $$\frac{\text{Trade Receivables}}{\text{Total Assets}} < 49\% \quad (< 0.49)$$

## 3. Database, ML, and Backtest Hygiene Invariants
- `fundamentals_cache`, `screener_candidates`, and `positions` in `alphasentinel.duckdb` must never retain rows that fail `check_shariah_compliance()`.
- Research backtests (`research/data_loader.py`, `research/backtest_harness.py`) must exclude all Haram symbols (`PROHIBITED_SYMBOLS` including `HDFCBANK`, `ICICIBANK`, `SBIN`, `ITC`) and deduct realistic Indian equity delivery round-trip transaction costs.
- Live order execution (`src/execution/dhan_broker.py`, `src/execution/order_manager.py`) must remain gated behind `LIVE_TRADING_ENABLED=False` and `PAPER_TRADING_MODE=True` by default, and fail closed if `dhan_security_id` is unmapped.

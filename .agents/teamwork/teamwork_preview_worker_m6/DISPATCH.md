## 2026-10-07T12:51:02Z
You are Worker M6 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m6
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m6
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture, feature inventory, and interface contracts:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_2\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `src/screening/vcp_screener.py` (adding Beta-Stripped Residual Momentum calculation and filter)
- `scripts/train_lambdarank.py`
- `tests/test_residual_momentum.py`
- `tests/test_lambdarank.py`

DO NOT modify files in `src/risk`, `src/portfolio`, `src/ingestion`, or `scripts/fyers_auth.py`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R6):
1. In `src/screening/vcp_screener.py`:
   - Implement **Beta-Stripped Residual Momentum**:
     - 60-day OLS of stock daily returns against Nifty 500 benchmark returns (`MONIFTY500` or benchmark in `bhavcopy_daily`):
       $R_{i, t} = \alpha_i + \beta_i R_{m, t} + \epsilon_{i, t}$
     - Calculate cumulative 30-day idiosyncratic residual over residual standard deviation:
       $\text{score}_i = \frac{\sum_{t=T-29}^T \epsilon_{i, t}}{\text{std}(\epsilon_{i, 1..60})}$
     - Calculate cross-sectional percentile rank across the active Halal equity universe (`shariah_universe` in DuckDB).
     - Gate requirement: candidate MUST rank in $\ge 70\text{th}$ percentile of the Halal universe. (Eliminates the 35% banking contamination from conventional benchmark momentum).
     - Vectorized performance requirement: MUST compute in $<100$ms for the entire universe (Survey 2 proved NumPy matrix implementation clocks ~3.5ms).
2. Implement Phase 2 LightGBM LambdaRank in `scripts/train_lambdarank.py`:
   - Cross-sectional ranking model (`objective="lambdarank"`, metric="ndcg", eval_at=[1, 3], grouped by `trade_date`).
   - Labels: forward 5-day return deciles (0 to 9).
   - Ranking inference function `rank_top_setups(candidates, top_n=3)` to output the Top 3 setups each evening.
   - Include fallback / mock handling if `lightgbm` C library is not installed in the system.
3. Implement unit tests in `tests/test_residual_momentum.py` and `tests/test_lambdarank.py`:
   - Test 1: Vectorized execution time $<100$ms across 350+ stocks x 60 bars.
   - Test 2: High-beta bank correlated movement does not inflate non-banking residual momentum.
   - Test 3: Candidate ranking below 70th percentile is rejected by VCP screener; >= 70th percentile passes.
   - Test 4: LambdaRank query-grouping and Top 3 setup ranking logic.
4. Run tests:
   `python -m pytest tests/test_residual_momentum.py tests/test_lambdarank.py -v`
   Ensure ALL tests pass 100%.
5. Write handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m6\handoff.md` and send message to Orchestrator.

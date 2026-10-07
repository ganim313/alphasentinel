## 2026-10-07T11:52:39Z
You are Survey Explorer 3 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_explorer_survey_3
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_3
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

Your focus is surveying requirements R4 and R5 in depth:
- R4: Phase 1 Bug Fix 4: ML Decoupling & Morning 2FA Token Refresh (`scripts/run_live_preview.py`, `scripts/fyers_auth.py`, `src/ingestion/fyers_client.py`, deprecations, 08:50 IST Morning Telegram Digest trade cards)
- R5: Data Spine Backfill & Offline Shariah Universe Sync (`scripts/sync_shariah_universe.py`, `src/ingestion/bhavcopy.py`, DuckDB `shariah_universe`, `bhavcopy_daily`)

Also inspect reference materials:
- `C:\Users\Md Ganim\.gemini\antigravity\brain\dbf4a2b9-d917-4e9a-af93-e78bae3e62e3\master_improvement_plan.md`
- `Audit/Gemini-Branch • FYERS Access Limitations-20261007-1221.md`
- `.agency/active/domain_agents/financial_regulatory_critic.md`
- `.agency/active/domain_agents/market_microstructure_specialist.md`

Do NOT modify or write source code files (you are an Explorer).
Investigate and document:
1. Exact current state of ML gate (`ml_prob >= ml_cutoff`) in `scripts/run_live_preview.py:597`: how to decouple XGBoost to non-blocking shadow logging.
2. FYERS authentication and client implementation: `scripts/fyers_auth.py` for 08:45 IST 2FA morning token refresh to `.fyers_token`. Dynamic `reload_token()` (mtime check), `get_holdings()`, and `get_positions()` in `src/ingestion/fyers_client.py`.
3. Deprecation plan for `scripts/run_sentinel.py`, `src/execution/dhan_broker.py`, and 15:15 IST intraday live preview rush. Format for Morning Telegram Digest at 08:50 IST with Trade Cards (Symbol, Limit Entry, Stop, Quantity, Allocation) for manual FYERS App entry.
4. DuckDB `alphasentinel.duckdb`: check current schema and content of `bhavcopy_daily`, `shariah_universe`, and `fundamentals_cache` (367 pre-cached stocks). Check consecutive trading days count and price discontinuities.
5. Ingestion pipeline: `src/ingestion/bhavcopy.py`, adding >25% unexplained price jump quarantine tripwire.
6. Offline monthly batch script: `scripts/sync_shariah_universe.py` populating DuckDB `shariah_universe` from `fundamentals_cache` using all 6 Mufti Taqi Usmani gates in `src/screening/shariah_filter.py`.
7. Existing test suites, dependencies, and interfaces.

Write your findings to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_3\handoff.md`.
Maintain `progress.md` in your working directory.
When finished, send a message to the orchestrator (Recipient: fe9b6c0a-5651-4bc7-812f-d77697cb2e43).

## 2026-10-07T11:52:39Z
[Message] timestamp=2026-10-07T11:52:39Z sender=fe9b6c0a-5651-4bc7-812f-d77697cb2e43 priority=MESSAGE_PRIORITY_HIGH
You are Survey Explorer 1 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_explorer_survey_1
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_1
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

Your focus is surveying requirements R1 and R2 in depth:
- R1: Phase 1 Bug Fix 1: Volatility-Adjusted Risk Parity Math (`src/risk/arbiter.py` & `src/config/strategy.yaml` or `strategy.yaml`)
- R2: Phase 1 Bug Fix 2: T+2 Qabd Settlement State Machine & Holdings Guardian (`src/portfolio/fyers_guardian.py`, `003_settlement_tracking.sql`, DB migration)

Also inspect the reference materials:
- `C:\Users\Md Ganim\.gemini\antigravity\brain\dbf4a2b9-d917-4e9a-af93-e78bae3e62e3\master_improvement_plan.md`
- `Audit/Gemini-Branch • FYERS Access Limitations-20261007-1221.md`
- `.agency/active/domain_agents/portfolio_risk_strategist.md`
- `.agency/active/domain_agents/financial_regulatory_critic.md`
- `.agency/active/domain_agents/market_microstructure_specialist.md`

Do NOT modify or write source code files (you are an Explorer).
Investigate and document:
1. Exact current state of risk parity math in `src/risk/arbiter.py` and strategy yaml files: `max_pct_stop`, `max_position_size_pct`, `max_portfolio_heat_pct`, structural stop formula: Stop = max(Base_Low_10d - 0.25*ATR_14, Trigger - 2.5*ATR_14), and reject condition (stop distance > 8.0%).
2. Exact current state of settlement logic, T+2 Qabd enforcement, FYERS holdingType checks, GTT OCO order generation (365-day FYERS GTT OCO: Stop=initial_stop, Target=target_2 on Day 2 morning), 19:30 IST audit reconciliation with DuckDB `positions`, auto-import manual Demat buys, 9-rule priority exit hierarchy (P1 to P9), and P9 Shariah drift flag in `src/portfolio/fyers_guardian.py`.
3. Existing DB schema in `alphasentinel.duckdb` and existing migrations for settlement tracking (`003_settlement_tracking.sql`).
4. Existing unit tests for risk and portfolio settlement, and identify what tests pass/fail or need creation.
5. All required interface contracts, error conditions, and dependencies.

Write your findings to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_1\handoff.md`.
Maintain `progress.md` in your working directory.
When finished, send a message to the orchestrator (Recipient: fe9b6c0a-5651-4bc7-812f-d77697cb2e43).

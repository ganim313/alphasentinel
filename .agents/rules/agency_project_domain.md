---
trigger: model_decision
description: "Activate when working on AlphaSentinel domain logic, Quantitative Trading & Market Execution Domain workflows (quant, alpha, signal, factor, backtest, order book, lob, slippage, execution, twap, risk, var, cvar, drawdown, kelly), domain requirements, specialized calculations, or domain critic sign-off."
---
# 🎯 Project-Specific Permanent Domain Specialists (`Quantitative Trading & Market Execution Domain`)

This workspace has **permanent native domain specialist agents** synthesized via the `/grill-me` Domain Agent Architect (`domain_forge.py`) to work alongside the 25 core development agents.

## Active Project Domain Roster (`.agency/active/domain_agents/`)
- **`.agency/active/domain_agents/quantitative_researcher.md`** (`DOM-01` — **Principal Quantitative Researcher & Alpha Strategist**): Design alpha signals, factor models, regime-detection filters, and walk-forward backtesting pipelines with zero lookahead or survivorship bias. *(Active Phases: [1, 2, 3, 4, 5])*
- **`.agency/active/domain_agents/market_microstructure_specialist.md`** (`DOM-02` — **Market Microstructure & Order Execution Specialist**): Architect low-latency market data ingestion, limit order book (LOB) state machines, slippage simulation, and idempotent order execution lifecycles. *(Active Phases: [2, 3, 4, 5, 6])*
- **`.agency/active/domain_agents/portfolio_risk_strategist.md`** (`DOM-03` — **Portfolio Risk, VaR & Capital Allocation Strategist**): Govern pre-trade and real-time risk controls, Value-at-Risk (VaR/CVaR), position sizing, margin utilization, and automated drawdown circuit breakers. *(Active Phases: [1, 2, 3, 4, 5, 6])*
- **`.agency/active/domain_agents/financial_regulatory_critic.md`** (`DOM-04` — **Quant Overfitting, Tail-Risk & Regulatory Compliance Critic** *(Domain Adversarial Critic)*): Adversarially audit all trading algorithms, execution pipelines, and risk engines for data leakage, curve-fitting, duplicate order submission bugs, and regulatory non-compliance. *(Active Phases: [1, 2, 3, 4, 5, 6, 7])*

## Mandatory Operating Protocol
1. **Domain-First Co-Ownership:** When drafting PRDs (`03`), System Architecture (`04`), Data/ML Models (`24`/`25`), UI/UX (`10`), or QA Test Plans (`06`), load and apply the heuristics in `.agency/active/domain_agents/<role>.md`.
2. **Layer 0 & Layer 1 Verification:**
   - Run `python .agency/scripts/laya_engine.py --route "<task>"` to see both the Core Agency Pod and the matched Project Domain Specialist(s).
   - Run `python .agency/scripts/ripwire_engine.py --recall "<domain_term>"` before editing domain modules.
3. **Domain Critic Gate:** Before completing any phase deliverable, run the project's dedicated **Domain Adversarial Critic** charter in `.agency/active/domain_agents/` alongside `@oversight/master_critic.md` and `@oversight/code_integrity_guardian.md`.

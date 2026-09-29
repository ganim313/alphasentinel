---
template_id: "02"
phase: 1
assigned_role: "10_legal_operations_officer"
context_from: ["01_proposal_sow.md"]
outputs_to: ["03_requirements_engineering.md"]
status: completed
---
# Master Project Agreement & Risk Governance Charter: AlphaSentinel

**Product:** AlphaSentinel (Autonomous Quant Trading OS)  
**Legal & Governance Lead:** `@10_legal_operations_officer`  
**Owner / Principal Operator:** Proprietary Capital Account  
**Status:** Completed & Approved  

---

## 1. Operating Charter & Scope of Authority

This Agreement and Risk Governance Charter sets forth the operational boundaries, liability constraints, and capital risk rules governing the autonomous execution of the **AlphaSentinel** platform.

1. **System Autonomy Boundaries:**
   - AlphaSentinel is empowered to ingest market data, screen technical and fundamental setups, run multi-agent debates, and generate trade cards and risk sizing recommendations.
   - The platform operates under a **Strict Paper-Trading Default** (`PAPER_TRADING_MODE=true`). No automated live capital order routing is permitted without explicit human validation.

2. **Deterministic Risk Arbiter Primacy:**
   - Large Language Models (LLMs) and heuristic agents act solely as narrative researchers and forensic trap analysts.
   - LLMs possess ZERO capital allocation authority. All position sizing, stop-loss calculations, and sector limits are calculated exclusively by deterministic Python mathematical modules.
   - Maximum capital risk per position is capped at 1.5% of total portfolio value. Maximum concurrent portfolio heat is strictly bounded.

3. **Emergency Circuit Breaker & Kill-Switch:**
   - A global kill-switch (`/HALT_ALL`) is integrated into both the Telegram bot and Streamlit UI.
   - When triggered, all scanning and analysis jobs instantly halt, open paper orders are cancelled, and system status switches to `HALTED`.

---

## 2. Intellectual Property & Code Ownership

- 100% of all software source code, proprietary indicator implementations, database schemas, and AI agent prompts belong exclusively to the project principal.
- The project utilizes permissive open-source packages (DuckDB, Pandas, NumPy, VectorBT, LangGraph) in strict compliance with their respective open-source licenses.

---

## 3. Financial Risk Disclosure & Disclaimer

- The software is provided as a personal algorithmic research and execution platform.
- Quantitative models, machine learning predictions, and agentic debates do not guarantee future profitability.
- The principal acknowledges that equity markets, particularly Indian small-cap and micro-cap securities, carry substantial volatility, liquidity risks, and potential capital loss.

---

## ✍️ Human Lead Decision & Sign-Off Block

* **Key Decision 1 (Risk Governance Rules):** Deterministic risk arbiter primacy and 1.5% max risk cap enforced.
* **Key Decision 2 (Paper Trading Mandate):** 30-Day paper trading validation period approved before any live capital consideration.
* **Key Decision 3 (Kill-Switch Protocol):** `/HALT_ALL` emergency freeze operationalized.

* **Human Lead Sign-Off:** ✅ Approved (2026-08-24)
* **Human Overrides / Adjustments:** Governance Charter active for all project phases.

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [x] Deliverable has been reviewed against requirements.
- [x] No placeholder blocks remain unfilled.
- [x] Human Lead has explicitly signed off above.
- [x] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [x] 02_msa_contract.md

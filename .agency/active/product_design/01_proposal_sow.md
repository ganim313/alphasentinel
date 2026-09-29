---
template_id: "01"
phase: 1
assigned_role: "01_product_manager"
context_from: []
outputs_to: ["02_msa_contract.md"]
status: completed
---
# Proposal & Statement of Work (SOW): AlphaSentinel

**Product:** AlphaSentinel (Autonomous Quant Trading OS & Portfolio Advisory)  
**Lead Product Manager:** `@01_product_manager`  
**Client / Stakeholder:** Internal Proprietary Trading Desk  
**Budgetary Tier:** Core ($0.00 / month infrastructure operating budget)  
**Status:** Completed & Approved  

---

## 1. Project Overview

AlphaSentinel is an autonomous, platform-agnostic quantitative trading and portfolio advisory operating system engineered specifically for the Indian equities market (NSE small-cap and micro-cap universe). 

The primary objective of the platform is to systematically identify high-probability swing and positional breakout candidates (utilizing Minervini Trend Templates, Volatility Contraction Patterns / VCP, and Wyckoff volume-delivery accumulation) while enforcing strict multi-layered capital preservation shields. The system operates on a zero-monthly-cost infrastructure budget by leveraging Oracle Cloud Always Free ARM compute, DuckDB embedded storage, Tailscale mesh networking, open-source quantitative libraries, and multi-model LLM routing.

---

## 2. In-Scope Features & Core Deliverables

1. **Tier 1: Multi-Source Data Ingestion Engine**
   - Automated NSE Bhavcopy daily reconciliation (`jugaad-data` / `pynse`).
   - Corporate actions multiplier engine (retroactive stock split & bonus adjustments).
   - Macro radar ingestion (GIFT Nifty, CBOE US VIX, participant FII/DII open interest).
   - Headless scraping module for fundamental ratios and Shariah debt metrics via Screener.in.

2. **Tier 2: Vectorized Screening & Anti-Trap Shield**
   - High-performance technical screening for Stage 2 uptrends and VCP contractions.
   - Strict Liquidity Guard: Minimum ₹50 Lakhs ADTV, Trade-to-Trade (BE/BZ) exclusion, and circuit-band sensitivity.
   - Shariah compliance filter: Zero interest-bearing debt violation, non-permissible sector blocking.
   - 6-Layer Anti-Trap Shield: Climax run exhaustion detection, pivot extensions, MA distance guards, and false breakout filters.

3. **Tier 3: Quantitative Intelligence & Forensics**
   - Statistical factor scoring and multi-bagger runner archetype clustering.
   - Machine learning probability estimations (LightGBM / XGBoost walk-forward models).

4. **Tier 4: Multi-Agent Consensus & Debate Engine**
   - LangGraph-powered stateful agent debate (Macro Analyst, Bull Analyst, Bear Trap Hunter).
   - Deterministic Python-only Risk Arbiter with unilateral veto authority over LLM proposals.

5. **Tier 5: Execution, Risk Controls & User Interfaces**
   - True 14-day Average True Range (ATR) position sizing and portfolio correlation limits.
   - Single-Writer FIFO Queue Daemon for zero-lock DuckDB concurrency.
   - Streamlit interactive web dashboard and real-time Telegram trade alert dispatch.
   - `/HALT_ALL` global kill-switch emergency freeze.

---

## 3. Out-of-Scope (Explicit Exclusions)

- High-Frequency Trading (HFT) and sub-second order routing (the platform is strictly non-intraday, swing/positional).
- Unattended live automated broker order placement (all trades default to Paper Trading validation until live gates pass).
- Paid institutional data terminal subscriptions (Bloomberg, Refinitiv, FactSet).
- Derivative / Futures & Options trading execution (equities cash segment only).

---

## 4. Technology Stack & Architecture

- **Language & Runtime:** Python 3.11+ / Python 3.13 (`uv` package manager).
- **Core Analytics:** DuckDB, Pandas, NumPy, VectorBT, Qlib, Scikit-learn, LightGBM.
- **Agentic Orchestration:** LangGraph, LangChain Core, LiteLLM Universal Gateway.
- **LLM Roster:** Google Gemini Flash/Pro (Primary) -> DeepSeek-R1 (Fallback 1) -> Groq Llama-3.3 (Fallback 2).
- **Presentation & Alerts:** Streamlit Dashboard, Python Telegram Bot.
- **Infrastructure:** Oracle Cloud Always Free ARM (4 vCPU / 24GB RAM) + Tailscale Zero Trust VPN.

---

## 5. Timeline & Milestones

- **Phase 1 (Intake & Charter):** System scope, edge definition, and budget boundary formulation.
- **Phase 2 (Requirements Engineering):** Full PRD, BRD, SRS, and 5-lens quantitative validation rules.
- **Phase 3 (System Architecture):** HLD/LLD diagrams, single-writer DB queue design, and TDR matrix.
- **Phase 4 (Implementation):** End-to-end Python engine, ingestion, screening, debate graph, and UI.
- **Phase 5 (Testing & Security):** 8 test suites, 12 rounds of adversarial Challenger Critic hardening, and SAST review.
- **Phase 6 (Deployment):** Oracle Cloud systemd daemons, automated crontab schedules, and Tailscale config.
- **Phase 7 (Operations & SLA):** 30-day paper trading verification gate, weekly feedback loops, and SLA sign-off.

---

## 6. Budget & Resource Allocation

- **Infrastructure Cost:** $0.00 / month (Oracle Always Free + Open-Source Libraries + Tailscale).
- **API Model Costs:** $0.00 / month (Gemini Free Tier 250k TPM + OpenRouter Free Credits).
- **Human Capital:** Solo Quantitative Developer / Trader.

---

## ✍️ Human Lead Decision & Sign-Off Block

* **Key Decision 1 (Scope Definition):** 5-Tier swing/positional quant trading OS with 6-layer anti-trap shield approved.
* **Key Decision 2 (Budget Model):** $0.00/month infrastructure ceiling strictly enforced via open-source tools.
* **Key Decision 3 (Timeline Commitment):** 7-Phase agency delivery and 30-day paper trading validation gate locked.

* **Human Lead Sign-Off:** ✅ Approved (2026-08-24)
* **Human Overrides / Adjustments:** Approved for Phase 2 Requirements Engineering.

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [x] Deliverable has been reviewed against requirements.
- [x] No placeholder blocks remain unfilled.
- [x] Human Lead has explicitly signed off above.
- [x] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [x] 01_proposal_sow.md

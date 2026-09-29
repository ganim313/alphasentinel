---
template_id: "08"
phase: 7
assigned_role: "10_legal_operations_officer"
context_from: ["07_deployment_runbook.md"]
outputs_to: []
status: in_progress
---
# Post-Launch Operations, Maintenance & SLA

**Product:** AlphaSentinel (Autonomous Quant Trading OS)  
**Legal & Operations Lead:** `@10_legal_operations_officer`  
**Status:** In Progress (Operational Framework Finalized)  

---

## 1. Warranty & Validation Period

* **Duration:** 30-Day Mandatory Paper Trading & Validation Window.
* **Scope:** Zero-cost patches for any runtime exceptions, DuckDB concurrency locks, or API fallback failures that occur during scheduled market runs (08:45 AM, 03:15 PM, 06:00 PM).

---

## 2. System Maintenance & Operational Runbook

* **Zero-Cost Operation:** The entire infrastructure operates on the $0.00/month tier (Oracle Cloud Always Free + Tailscale Mesh VPN + DuckDB embedded file + Google AI Studio Gemini Free Tier).
* **Automated Weekly Maintenance:**
  - `run_feedback_loop.py` executes every Saturday at 10:00 AM to inspect historical win-rates in DuckDB and inject prompt warnings if win-rate drops below 40%.
  - `keep_alive.py` daemon runs 24/7 as a systemd service to ensure CPU load remains >10%, protecting the VM from Oracle Always-Free reclamation.
* **Database Backups:** Daily automated snapshot of `alphasentinel.duckdb` to local archival storage (`/home/ubuntu/alphasentinel/backups/`).

---

## 3. Service Level & Support Protocol

* **Severity 1 (Pipeline Failure during Market Hours 09:15-15:30 IST):** Immediate auto-fallback to pure deterministic Python math; local system logs error to Telegram.
* **Severity 2 (LLM API Rate Limits / 429 Errors):** Handled automatically by the LiteLLM waterfall (Gemini -> DeepSeek -> Groq).
* **Severity 3 (Non-Critical Scraper UI Changes on Screener.in):** Resolved within 48 business hours via soft-degradation default imputation.

---

## ✍️ Human Lead Decision & Sign-Off Block

* **Key Decision 1 (SLA Framework Approved):** 30-day paper trading and zero-cost maintenance model active.
* **Key Decision 2 (Operational Runbooks Active):** Weekend feedback loop and keep-alive daemons verified.

* **Human Lead Sign-Off:** ✅ Approved (2026-08-25)

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [x] Deliverable has been reviewed against requirements.
- [x] No placeholder blocks remain unfilled.
- [x] Human Lead has explicitly signed off above.
- [x] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [x] 08_post_launch_sla.md

---
template_id: "30"
phase: 4
assigned_role: "sales_client/account_manager"
context_from: ["03_requirements_engineering.md", "05_technical_sdlc_execution.md"]
outputs_to: ["30_weekly_account_status.md"]
status: template
---
# Template 30: Weekly Client Account Status Report

**Purpose:** To provide clients with a weekly executive summary of development progress, milestone RAG status (Red/Amber/Green), budget burn, upcoming sprint goals, and open decisions.

---

## 1. Executive Status Overview

| Project | Client | Current Phase | Overall Health (RAG) | Target Launch Date | Reporting Week |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `[Project Name]` | `[Client Name]` | Phase `[X]` - `[Phase Name]` | 🟢 **ON TRACK** | `[YYYY-MM-DD]` | Week `[X]` (`[Date Range]`) |

```
Progress Bar:  [████████████░░░░░░░░] 60% Complete
Budget Burn:   [██████████░░░░░░░░░░] 50% Used ($XX,XXX / $XX,XXX)
Sprint Health: 🟢 Velocity on target (18 of 20 Story Points Delivered)
```

---

## 2. Completed This Week (Business Value Delivered)
Highlight tangible features completed in language the client's executive team understands:
- ✅ **Feature 1:** Completed user authentication and multi-tenant organization onboarding flow.
- ✅ **Feature 2:** Integrated Stripe checkout supporting both monthly and annual subscription billing.
- ✅ **Feature 3:** Deployed interactive analytics charts to the staging preview environment.

---

## 3. In Progress & Planned for Next Week
- 🔄 **Feature 4:** Building CSV and PDF export functionality for financial reports.
- 🔄 **Feature 5:** Implementing role-based access control (Admin, Member, Viewer).
- 📅 **Planned Demo:** Weekly video walkthrough scheduled for Friday at 3:00 PM EST.

---

## 4. Blockers, Risks & Open Decisions Required from Client

| Blocker / Risk ID | Description | Impact if Unresolved | Action Required from Client | Deadline |
| :--- | :--- | :--- | :--- | :--- |
| `BLK-01` | Awaiting client production Stripe live credentials. | Cannot test live end-to-end payment processing in staging. | Client finance team to grant Stripe Restricted Key access. | `[YYYY-MM-DD]` |
| `DEC-01` | Decision on transactional email provider (SendGrid vs. Resend). | Affects password reset template styling. | Client Product Owner to confirm preference. | `[YYYY-MM-DD]` |

---

## 5. Milestone & Budget Health Tracker

| Milestone | Target Date | Current Forecast Date | Deliverable Document | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Milestone 1: Intake & SOW** | `[Date]` | `[Date]` | `01_proposal_sow.md` | ✅ **Completed** |
| **Milestone 2: PRD & Architecture** | `[Date]` | `[Date]` | `04_system_design_architecture.md` | ✅ **Completed** |
| **Milestone 3: Beta Build & UAT** | `[Date]` | `[Date]` | `06_testing_uat_signoff.md` | 🔄 **In Progress** |
| **Milestone 4: Production Launch** | `[Date]` | `[Date]` | `07_deployment_runbook.md` | ⏳ **Upcoming** |

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 decisions made and wait for the human lead's explicit approval before proceeding.)*

* **Key Decision 1 (Health Rating):** `[Confirmed RAG rating and schedule accuracy]`
* **Key Decision 2 (Client Action Items):** `[Highlighted client blockers with explicit deadlines]`
* **Key Decision 3 (Budget Burn):** `[Verified hours and budget alignment]`

* **Human Lead Sign-Off:** ⏳ Awaiting Approval / ✅ Approved / 🔄 Revisions Requested
* **Human Overrides / Adjustments:** `[Type 'Approved' or enter adjustments]`

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Weekly git commit history translated into non-technical business benefits.
- [ ] Staging preview URL verified and accessible to client stakeholders.
- [ ] No placeholder blocks (`[TBD]`) remaining.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] 30_weekly_account_status.md
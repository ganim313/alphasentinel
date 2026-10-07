---
template_id: "27"
phase: 2
assigned_role: "product_design/user_researcher"
context_from: ["product_design/01_proposal_sow.md", "sales_client/13_client_intake_questionnaire.md"]
outputs_to: ["product_design/03_requirements_engineering.md", "product_design/10_ui_ux_handoff.md"]
status: template
---
# Template 27: User Personas & Customer Journey Maps

**Purpose:** To define target user archetypes, jobs-to-be-done (JTBD), emotional journey stages, friction points, and moment-of-truth actions that shape the software product design.

---

## 1. Primary User Persona Archetype

### 👤 Persona Profile: `[Persona Name / e.g. Sarah, The Operations Lead]`
- **Role / Title:** `[Job Title & Department]`
- **Demographics:** `[Experience level, tech proficiency, working environment]`
- **Core Motivation:** `[What single outcome makes them look like a hero to their team?]`
- **Core Frustration:** `[What manual, broken process makes their daily job miserable today?]`

```
┌───────────────────────────────────────────────┐
│ "I just want a dashboard that doesn't require │
│ 5 exports and 3 hours in Excel to understand  │
│ what my team accomplished this week."        │
└───────────────────────────────────────────────┘
```

### 🎯 Jobs to Be Done (JTBD)
- **When I:** `[Encounter this specific trigger or scenario...]`
- **I want to:** `[Perform this specific action in the software...]`
- **So that I can:** `[Achieve this quantifiable business benefit...]`

---

## 2. Secondary User Persona Archetype

### 👤 Persona Profile: `[Secondary Persona / e.g. Marcus, The End Client / Consumer]`
- **Role / Relationship:** `[Account Holder / End User / Executive Stakeholder]`
- **Technical Savviness:** `[Low / Moderate / Power User]`
- **Key Goal:** `[Fast self-serve access, zero friction onboarding, transparent status]`
- **Dealbreakers:** `[Slow load times, confusing terminology, lack of mobile responsiveness]`

---

## 3. End-to-End User Journey Map

| Journey Phase | User Action / Goal | Emotional State | System Touchpoint | Friction Point / Risk | UX Opportunity / Design Solution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Discovery & Landing** | Evaluates software value proposition | 🧐 Skeptical | Landing Page Hero | Unclear pricing or feature set | Interactive demo & ROI calculator |
| **2. Onboarding & Setup** | Signs up & creates workspace | 😃 Hopeful | Auth & Onboarding Wizard | Too many upfront configuration steps | 3-step progressive onboarding with defaults |
| **3. First Value (Aha!)** | Completes first core workflow | 🤩 Delighted | Main Dashboard / Canvas | Confusing empty state | Pre-populated template or sample data |
| **4. Daily Habit** | Uses tool to manage daily tasks | 😎 Productive | Core Tool Views | Repetitive manual data entry | Keyboard shortcuts & smart auto-complete |
| **5. Collaboration** | Invites teammates & shares report | 🤝 Empowered | Share Dialog & Email Invite | Teammate permissions confusion | 1-click workspace join links with RBAC |

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (Primary Persona Target):** `[Core target user profile and JTBD focus]`
* **Key Decision 2 (Aha-Moment Path):** `[Fastest user path from signup to first core value]`
* **Key Decision 3 (Friction Mitigations):** `[Key UX solutions designed to eliminate drop-off]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Type 'Approved' or enter adjustments]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] User personas validated against intake questionnaire notes.
- [ ] Journey map covers all 5 critical lifecycle phases.
- [ ] No placeholder markers (`[TBD]`) remaining.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `product_design/27_user_persona_journey.md`
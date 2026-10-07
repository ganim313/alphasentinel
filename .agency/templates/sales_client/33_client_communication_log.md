---
template_id: "33"
phase: 1
assigned_role: "sales_client/account_manager"
context_from: []
outputs_to: ["product_design/01_proposal_sow.md"]
status: template
---
# Template 33: Client Communication Log

**Purpose:** A single source of truth for every client interaction. Protects against "he said / she said" disputes and provides context for future team members.

---

## 1. Project Contact Directory
| Role | Name | Email | Phone | Timezone |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Decision Maker** | | | | |
| **Technical Liaison** | | | | |
| **Finance / Billing** | | | | |

## 2. Communication Log

| Date | Channel | Participants | Summary | Action Items | Sentiment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Email | PM → Client | Kickoff meeting scheduled | Client to send brand assets | 🟢 Positive |
| YYYY-MM-DD | Video Call | Team + Client | PRD walkthrough | Client to approve PRD by Friday | 🟡 Neutral |
| YYYY-MM-DD | Slack | Dev → Client | Bug report clarification | Client to provide reproduction steps | 🔴 Concerned |

## 3. Decision Registry
**Critical decisions made outside of formal deliverables:**

| Date | Decision | Decision Maker | Impact |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | "Use Stripe instead of PayPal" | Client | Changes payment flow in PRD |
| YYYY-MM-DD | "Launch delayed by 1 week" | Mutual | Timeline extended, no cost change |

## 4. Escalation History
| Date | Issue | Resolution | Time to Resolve |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Client unhappy with initial design | Free revision round offered | 3 days |

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Note 1: e.g., Client communication log verified for Phase 1 kickoff.]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] `sales_client/33_client_communication_log.md`

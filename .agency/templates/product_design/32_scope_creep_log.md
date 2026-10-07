---
template_id: "32"
phase: 4
assigned_role: "product_design/product_manager"
context_from: ["product_design/03_requirements_engineering.md"]
outputs_to: ["finance_ops/14_change_order_form.md"]
status: template
---
# Template 32: Scope Creep Log

**Purpose:** Every "small request" from a client during development is scope creep. This log documents them so they can be converted into paid Change Orders or politely deferred.

> **Agency Rule:** If it's not in the signed PRD, it's not free.

---

## 1. Original Scope Boundary
**Source Document:** `03_requirements_engineering.md` (Signed off: YYYY-MM-DD)
**Original Feature Count:** `0`
**Original Quote:** `$0`

## 2. Creep Request Log

| ID | Date | Requested By | Description | Impact | Decision | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CR-01 | YYYY-MM-DD | Client | "Can we add Apple Sign-In?" | +5h, +$500 | Change Order #001 | 💰 Billed |
| CR-02 | YYYY-MM-DD | Client | "Make the dashboard real-time" | +12h, +$1200 | Deferred to Phase 2 | ⏳ Deferred |
| CR-03 | YYYY-MM-DD | Internal | "Add dark mode" (not in PRD) | +8h | Absorbed (goodwill) | ✅ Absorbed |

## 3. Change Order Tracker
| Change Order # | Linked Creep ID | Amount | Invoice Status |
| :--- | :--- | :--- | :--- |
| #001 | CR-01 | $500 | Paid |
| #002 | CR-02 | — | Pending Approval |

## 4. Creep Impact Summary
- **Total Requests:** `0`
- **Billed as Change Orders:** `$0`
- **Deferred to Phase 2:** `0 items`
- **Absorbed (Goodwill/Error):** `0h`
- **Revenue Recovered:** `$0` (% of total creep value)

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
* `[Note 1: e.g., All scope creep items classified via Laya Scope Creep Classifier and converted to Change Orders.]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] `product_design/32_scope_creep_log.md`

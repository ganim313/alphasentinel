---
template_id: "14"
phase: 2
assigned_role: "product_design/product_manager"
context_from: ["product_design/01_proposal_sow.md", "product_design/32_scope_creep_log.md"]
outputs_to: ["product_design/03_requirements_engineering.md"]
status: template
---
# Template 14: Change Order Form

**Purpose:** When a client says "Can we just add X real quick?" during development, you send them this document. It turns scope creep into profitable extra work. Never do out-of-scope work for free.

---

## 1. Change Request Details
* **Project Name:** [e.g., Noon Fish Delivery App]
* **Change Order Number:** #001
* **Date Requested:** [Date]

## 2. Description of Changes
*Describe exactly what the client requested that is not in the original PRD.*
* **Original Scope:** The app supports standard Email/Password and Google OAuth login.
* **Requested Change:** Add "Sign in with Apple" and "Sign in with Facebook" functionality.

## 3. Impact on Timeline
*How does this delay the original delivery date?*
* This change requires UI redesign for the login screen, new database schema mapping, and Apple Developer account integration.
* **Timeline Extension:** Adds +5 business days to the final delivery date.

## 4. Impact on Cost
*How much will this cost?*
* Estimated Development Hours: 15 hours.
* Hourly Rate: $100/hr
* **Additional Cost:** $1,500.00

## 5. Approval Signatures
By signing below, the Client approves the additional cost and timeline extension. Work on this feature will not commence until this document is signed and the invoice for this Change Order is paid.

*(Signature of Client)* 
*(Signature of Agency)*

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 change-order impact decisions and wait for the human lead's explicit approval before updating the PRD.)*

* **Key Decision 1 (Out-of-Scope Classification):** `[Confirmed requested feature is outside signed SOW/PRD scope]`
* **Key Decision 2 (Timeline Extension):** `[Approved business day extension added to target delivery date]`
* **Key Decision 3 (Commercial Fee & Pre-Payment):** `[Confirmed additional hours, hourly rate, and payment-before-work gate]`

* **Human Lead Sign-Off:** ⏳ Awaiting Approval / ✅ Approved / 🔄 Revisions Requested
* **Human Overrides / Adjustments:** `[Type 'Approved' or enter adjustments]`

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Human Lead has explicitly signed off above.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 14_change_order_form.md

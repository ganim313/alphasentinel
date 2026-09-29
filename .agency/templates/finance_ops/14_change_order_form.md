---
template_id: "14"
phase: 2
assigned_role: "01_product_manager"
context_from: []
outputs_to: ["03_requirements_engineering.md"]
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

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 14_change_order_form.md

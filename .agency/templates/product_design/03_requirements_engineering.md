---
template_id: "03"
phase: 2
assigned_role: "product_design/product_manager"
context_from: ["product_design/01_proposal_sow.md", "sales_client/13_client_intake_questionnaire.md"]
outputs_to: ["engineering/04_system_design_architecture.md"]
status: template
---
# Template 03: Requirements Engineering (BRD, PRD, SRS)

**Purpose:** Translating vague client wishes into strict engineering documents. Do not start coding until the client signs off on the PRD.

---

## 1. Business Requirements Document (BRD)
*Written for the CEO/Stakeholders.*
* **Business Objective:** What is the financial or operational goal of this software? (e.g., "Reduce manual data entry time by 50%").
* **Target Audience:** Who are the end users? (e.g., "Restaurant managers aged 30-50").
* **Key Performance Indicators (KPIs):** How will we measure success post-launch?

## 2. Product Requirements Document (PRD)
*Written for the Product/Engineering Team.*
* **User Roles:** (e.g., `Guest`, `Customer`, `City_Admin`, `Master_Admin`).
* **Core User Flows / Use Cases:**
  * *Use Case 1:* "A Customer browses the catalog, adds 2 items to the cart, and checks out via WhatsApp."
  * *Use Case 2:* "A City_Admin logs in, views orders assigned *only* to their city, and marks an order as 'Delivered'."
* **Feature Specifications:** 
  *(CRITICAL: For every single feature listed above, you MUST generate a detailed table. Do not summarize.)*

  | Feature Name | Acceptance Criteria | Failure/Error States | Permissions Required | Validation Rules |
  | :--- | :--- | :--- | :--- | :--- |
  | `[Feature 1]` | `[Specific criteria]` | `[What happens if it fails?]` | `[Who can do this?]` | `[e.g., Min 8 chars]` |
  | `[Feature 2]` | `[Specific criteria]` | `[What happens if it fails?]` | `[Who can do this?]` | `[e.g., Unique email]` |
## 3. Software Requirements Specification (SRS)
*Written strictly for Developers.*
* **Non-Functional Requirements:**
  * **Performance:** "API latency must remain under 200ms at the 95th percentile."
  * **Security:** "All user passwords must be hashed using bcrypt. API must be protected by rate-limiting (100 req/min)."
  * **Availability:** "The system must target 99.9% uptime."
* **External Integrations:** Specifications for third-party APIs (e.g., Stripe API keys required, Firebase config needed).

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 requirements trade-offs and wait for the human lead's explicit approval before proceeding to Architecture.)*

* **Key Decision 1 (MVP Feature Boundary):** `[Explicitly what is in MVP vs what is cut/deferred to Phase 2]`
* **Key Decision 2 (Non-Functional Commitments):** `[Agreed SLAs: e.g., <200ms latency, 99.9% uptime, WCAG AA]`
* **Key Decision 3 (Third-Party Dependencies):** `[External SDKs/APIs required: e.g., Stripe, Supabase, Twilio]`

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
- [ ] 03_requirements_engineering.md

---
template_id: "06"
phase: 5
assigned_role: "07_qa_sdet_engineer"
context_from: ["05_technical_sdlc_execution.md"]
outputs_to: ["07_deployment_runbook.md"]
status: template
---
# Template 06: Testing Pyramid & Client UAT

**Purpose:** Ensure the software is bug-free before launch and get formal client approval that the delivered software matches the PRD.

---

## 1. The Engineering Testing Pyramid
* **Unit Tests (Jest / Vitest):** High volume. Test individual functions and utilities (e.g., formatting dates, calculating tax).
* **Integration Tests:** Medium volume. Test database interactions and API endpoints (e.g., "Does `POST /api/orders` write a row to PostgreSQL?").
* **End-to-End (E2E) Tests (Playwright / Cypress):** Low volume. Simulate a real user clicking through the browser to complete core business flows (e.g., "User logs in, adds item to cart, and checks out successfully").

## 2. User Acceptance Testing (UAT) Handover
*Deploy the final code to the Staging Environment and invite the client to test.*

**Client UAT Instructions:**
1. Log in to `staging.clientdomain.com` using the provided test credentials.
2. Attempt to complete your core business workflows (place an order, edit a product, etc.).
3. Log any issues in the provided shared spreadsheet.

**Rules of UAT:**
* **Bugs:** If a feature listed in the PRD is broken or behaving incorrectly, it is a Bug. We fix this for free during the UAT window.
* **Feature Requests:** If you want to change the color of a button, add a new field, or alter the workflow, this is a Feature Request. It will be scheduled for Phase 2 or billed via a Change Order.

## 3. Formal UAT Sign-Off (Template)
*(Require the client to reply to an email with this statement)*:

> "I, [Client Name], have tested the software on the staging environment. I confirm that all features outlined in the original Product Requirements Document (PRD) are present and functioning correctly. I approve this version for deployment to Production."---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the test suite and UAT readiness metrics and wait for the human lead's explicit approval before proceeding to Deployment.)*

* **Key Decision 1 (Automated Test Pass Rate):** `[Unit, Integration, and Playwright E2E test results — e.g., 100% passing in CI]`
* **Key Decision 2 (Outstanding Non-Critical Issues):** `[Known minor visual bugs or edge cases accepted for post-launch patch]`
* **Key Decision 3 (Client Staging Approval):** `[Confirmation of client UAT acceptance on staging environment]`

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
- [ ] 06_testing_uat_signoff.md

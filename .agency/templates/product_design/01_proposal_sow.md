---
template_id: "01"
phase: 1
assigned_role: "01_product_manager"
context_from: ["13_client_intake_questionnaire.md"]
outputs_to: ["02_msa_contract.md"]
status: template
---
# Template 01: Proposal & Statement of Work (SOW)

**Purpose:** To define exactly what is being built, how much it will cost, and the estimated timeline. This prevents "scope creep".

---

## 1. Project Overview
Provide a 2-3 paragraph summary of the client's problem and the custom software solution you are providing.

## 2. In-Scope Features (Deliverables)
List out exactly what you are building. If it is not on this list, it is not included in the price.
- [ ] Feature 1 (e.g., User Authentication via Email/Password)
- [ ] Feature 2 (e.g., Stripe Payment Integration)
- [ ] Feature 3 (e.g., Admin Dashboard with CRUD capabilities)

## 3. Out-of-Scope (Explicit Exclusions)
Protect yourself by listing things the client might *assume* are included but aren't.
- [x] No Mobile App (Web App only)
- [x] No Data Migration from legacy systems
- [x] No Third-Party Logistics API integration

## 4. Tech Stack
- Frontend: `[Next.js / React]`
- Backend: `[Express / Node.js]`
- Database: `[PostgreSQL / Supabase]`

## 5. Timeline & Milestones
- **Week 1-2:** Design & Requirements Sign-off
- **Week 3-6:** Core Development (Beta)
- **Week 7:** UAT & Testing
- **Week 8:** Deployment

## 6. Investment & Payment Schedule
Total Cost: `$X,XXX`
- 30% Deposit to commence work
- 30% Upon Design Approval
- 30% Upon Code Freeze / UAT start
- 10% Final payment prior to Production Deployment

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 decisions made and wait for the human lead's explicit approval before proceeding to MSA/PRD.)*

* **Key Decision 1 (Scope Definition):** `[Summary of included core features vs. excluded out-of-scope items]`
* **Key Decision 2 (Pricing Basis):** `[Estimated hours, hourly rate, and total project price]`
* **Key Decision 3 (Timeline Commitment):** `[Target MVP delivery date and milestone deadlines]`

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
- [ ] 01_proposal_sow.md

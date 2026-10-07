---
template_id: "15"
phase: 3
assigned_role: "engineering/solutions_architect"
context_from: ["engineering/04_system_design_architecture.md"]
outputs_to: ["engineering/05_technical_sdlc_execution.md"]
status: template
---
# Template 15: Developer Onboarding Protocol

**Purpose:** When your agency grows and you need to hire a subcontractor or junior developer to help write code, you must grant them access without compromising the client's production data or security.

---

## 1. Legal & Non-Disclosure (NDA)
Before inviting the developer to GitHub:
- [ ] Subcontractor signs an Independent Contractor Agreement clearly stating that all code written is "Work for Hire" and owned by your agency.
- [ ] Subcontractor signs an NDA (Non-Disclosure Agreement) forbidding them from sharing the client's name or code publicly.

## 2. Access Provisioning (The Principle of Least Privilege)
Never give a subcontractor "Admin" access unless absolutely necessary.
- [ ] **GitHub/GitLab:** Add developer to the repository with `Read` or `Write` access. Never `Maintain` or `Admin`. Protect the `main` branch so they cannot merge their own Pull Requests.
- [ ] **Database (Supabase/PostgreSQL):** *Never* give access to the Production database. Provide them with a local Docker setup or a dedicated `staging-dev` database URL.
- [ ] **Third-Party Keys:** Provide them with *Test* API keys for Stripe, Cloudinary, Firebase. Never expose live production keys in `.env` files shared with subcontractors.

## 3. Environment Setup & Testing
Provide the developer with the repository `README.md` and verify they can:
- [ ] Successfully run `npm install` and `npm run dev` locally.
- [ ] Connect to the local/staging database.
- [ ] Run the local test suite `npm test` and verify all tests pass on their machine.

## 4. Workflow Orientation
Ensure they understand the agency's strict SDLC rules:
- [ ] Code must be written on `feat/` or `fix/` branches.
- [ ] All code must pass ESLint and Prettier before a PR is opened.
- [ ] They must request a code review from the Lead Engineer (You) before any code is merged.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 developer onboarding & access controls and wait for the human lead's explicit approval before granting repository access.)*

* **Key Decision 1 (NDA & Work-for-Hire):** `[Confirmed signed contractor agreement and NDA on file]`
* **Key Decision 2 (Least-Privilege Boundaries):** `[Confirmed main branch protection and zero production DB/API key exposure]`
* **Key Decision 3 (Local Build Verification):** `[Verified clean local setup and passing test suite in <15 minutes]`

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
- [ ] 15_developer_onboarding.md

---
template_id: "05"
phase: 4
assigned_role: "engineering/backend_engineer"
context_from: ["engineering/04_system_design_architecture.md"]
outputs_to: ["engineering/06_testing_uat_signoff.md"]
status: template
---
# Template 05: Technical SDLC & Agile Execution

**Purpose:** Setting up the environment, version control, and sprint cycles for actual coding.

---

## 1. Environment Strategy
Set up strict isolation between testing and production:
- **Local Environment:** Developer's machine (`localhost:3000`).
- **Development Server:** Automatically deployed from the `dev` branch for internal developer testing.
- **Staging Server:** Automatically deployed from the `main` branch. This is the exact replica of Production where the client will conduct UAT.
- **Production Server:** The live URL (e.g., `www.clientdomain.com`).

## 2. Version Control & Branching Strategy
- We follow **Feature Branching**:
  1. Check out a new branch: `git checkout -b feat/user-auth`
  2. Write code and push to origin.
  3. Open a **Pull Request (PR)** against the `dev` or `main` branch.
- **Never push directly to `main` or `staging`.**

## 3. CI/CD Pipeline (GitHub Actions / GitLab CI)
- **Continuous Integration (CI):** On every PR creation, the server automatically runs:
  - Linters (e.g., ESLint).
  - Formatters (e.g., Prettier).
  - Unit Tests (e.g., Jest).
  *If any step fails, the PR is blocked from merging.*
- **Continuous Deployment (CD):** Once a PR is approved and merged into `main`, the CD pipeline automatically builds and deploys the code to Vercel/Netlify/AWS.

## 4. Agile Sprint Execution
- Break the WBS down into 1 or 2-week Sprints.
- Manage tasks on a Kanban board (Jira, Linear, Trello):
  - `Backlog` -> `To Do` -> `In Progress` -> `In Review (PR)` -> `QA` -> `Done`
- Require a strict **Definition of Done (DoD)** before moving a card to `Done`.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 SDLC implementation decisions and wait for the human lead's explicit approval before proceeding to Phase 5 Testing.)*

* **Key Decision 1 (Branching & CI Gating):** `[Confirmed PR review rules, linter/typecheck gates, and staging branch strategy]`
* **Key Decision 2 (Contract & Schema Parity):** `[Verified Frontend and Backend implementations match 04_system_design_architecture.md with 0 drift]`
* **Key Decision 3 (Sprint Deliverable Completeness):** `[Confirmation that all MVP features in the sprint backlog are implemented and unit-tested]`

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
- [ ] 05_technical_sdlc_execution.md

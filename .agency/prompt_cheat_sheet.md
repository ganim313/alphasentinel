# Agency Playbook: Prompt Cheat Sheet

> **How to use this**: This is your daily driver. Load these roles and prompts into **ANY AI model or platform** (Antigravity 2.0, Cursor, Kimi, Codex, Claude Code, ChatGPT) using the `@filename.md` notation.
> 
> 💡 **Model Tip (Antigravity 2.0)**: Use **Claude 3.7 Sonnet (Thinking)** for Architecture & Security (`@02`, `@08`, `@critic`), **Gemini Pro** for massive docs & legacy codebase indexing (`@01`, `@10`), and **Gemini Flash** for fast UI/code generation (`@03`, `@04`).

---

## 🔄 Daily Start / Chat Resume (Run This First)
When starting a fresh chat or resuming work on an existing project:
> *"Run the `@session-resumer.md` skill to read the project state and tell me where we left off."*

---

## ⚡ The 3-Tier Task Routing Protocol (How, What & When to Execute)

| Task Complexity | When to Use | Protocol & Role Combination | What to Do |
| :--- | :--- | :--- | :--- |
| **Tier 1: Micro-Task / Bug / Hotfix** | Fixing a typo, CSS padding, broken null check, single error | **Zero Role-Swapping (0 Ceremony)** | Ask your AI directly in IDE: *"Fix this error in [file]: [paste error]"*. Do NOT generate docs or switch roles. |
| **Tier 2: Minor Feature / Change Order** | Adding a new endpoint, export button, filter dropdown, small workflow | **Fast 2-Role Lane** | 1. Spec: `@01_product_manager.md` (2-min requirements)<br/>2. Build: `@04_frontend_engineer.md` / `@05_backend_engineer.md`<br/>3. Check: `@challenger_critic.md` |
| **Tier 3: Full System Build / New Product** | Green-field SaaS, new client build, legacy takeover, mobile app | **Full 10-Role Pipeline** | Follow the complete step-by-step lifecycle from Phase 0 to Phase 7 using the dedicated roles below. |

---

## ✍️ How to Supervise & Approve Your AI Team (Human Sign-Off)
Every AI role pauses at the end of its deliverable with a **'✍️ Human Lead Decision & Sign-Off Block'** listing its top 3 choices. You control the outcome with 1-line replies:

* **To Approve & Proceed:** > *"Approved. Proceed to next phase."*
* **To Request Adjustments:** > *"Modify Decision 1: Use Supabase Postgres instead of MySQL, then proceed."*
* **To Cut Scope:** > *"Reject Decision 2: Cut mobile app from MVP. Web-only for Phase 1."*

---

## 👤 Individual Industry Role Invocations
Load an individual Staff/Principal-level professional on demand:

* **Product Manager:** > *"Act as `@01_product_manager.md` to discover and write the requirements for [feature/idea]."*
* **Solutions Architect:** > *"Act as `@02_solutions_architect.md` to design the system architecture and OpenAPI contracts."*
* **UI/UX Designer:** > *"Act as `@03_ui_ux_designer.md` to establish design tokens, 8pt grid, and visual hierarchy."*
* **Frontend Engineer:** > *"Act as `@04_frontend_engineer.md` to implement the client UI for Web/Mobile."*
* **Backend Engineer:** > *"Act as `@05_backend_engineer.md` to build the API endpoints, transactions, and server logic."*
* **Database Engineer:** > *"Act as `@06_database_engineer.md` to design the SQL migrations, indexes, and RLS policies."*
* **QA & SDET Engineer:** > *"Act as `@07_qa_sdet_engineer.md` to write Playwright E2E suites and test edge cases."*
* **Security Auditor:** > *"Act as `@08_security_auditor.md` to run penetration tests and verify zero secret leaks."*
* **DevOps & SRE Engineer:** > *"Act as `@09_devops_sre_engineer.md` to build the CI/CD pipeline and deployment runbook."*
* **Legal & Operations Officer:** > *"Act as `@10_legal_operations_officer.md` to audit contract risks and calculate SOW pricing."*
* **The Challenger (Critic):** > *"Act as `@challenger_critic.md` to ruthlessly attack and stress-test this code/architecture."*

---

## Phase 0: Pre-Project (Idea → PRD)
Use these BEFORE any client work starts. Turn vague ideas into buildable specs.

**A. For YOUR OWN product idea (Stress-test first):**
> "Run the `@business-model-analyst.md` skill. Here is my idea: *[DESCRIBE YOUR IDEA IN 2 SENTENCES]*"

**B. For a CLIENT who has a vague requirement:**
> "Run the `@prd-discovery-agent.md` skill. The client's raw requirement is: *[PASTE CLIENT'S WORDS]*"

**C. When you have a transcript but no PRD yet:**
> "Run the `@client-intake-parser.md` skill on these notes: *[PASTE NOTES]*. Then run `@prd-discovery-agent.md` to convert the intake into a full PRD."

---


## Phase 1: Intake & Strategy
When you first talk to a client and need to generate the initial paperwork.

**1. Extracting Meeting Notes:**
> "Run the `client-intake-parser` skill on these raw meeting notes: *[PASTE YOUR NOTES HERE]*"

**2. Calculating Pricing & SOW:**
> "Run the `proposal-pricing-calculator` skill to generate the Statement of Work based on the intake questionnaire."

**3. Creating a Brand Strategy (Optional):**
> "Run the `brand-identity-architect` skill to generate a brand positioning statement and tone of voice for this client."

---

## Phase 2 & 3: Requirements & Architecture
Translating the SOW into technical blueprints.

**4. Writing the PRD:**
> "Draft the Product Requirements Document (`03_requirements_engineering.md`) based on the approved SOW."

**5. Debating & Justifying the Tech Stack (Critical Gate):**
> "Run the `@tech-stack-adviser.md` skill on `03_requirements_engineering.md`. Challenge my proposed tech choices (Frontend, Backend, Database, Cloud) across Velocity, Cost, Complexity, and Scalability."

**6. Generating Architecture Diagrams:**
> "Run the `architecture-diagrammer` skill to generate the Mermaid.js ERD and System Design based on the PRD."

---

## Phase 4: Implementation (Parallel Build Fork)
Building the actual product simultaneously against the OpenAPI contract.

**7. Frontend Stream (UI with Mock Data):**
> *"Act as `@04_frontend_engineer.md` and `@03_ui_ux_designer.md`. Build the client UI components adhering strictly to the OpenAPI route types in `04_system_design_architecture.md` using typed mock data."*

**8. Backend Stream (APIs, Transactions & DB):**
> *"Act as `@05_backend_engineer.md` and `@06_database_engineer.md`. Implement the database migrations, Prisma/SQL schemas, and API controllers matching the OpenAPI spec in `04_system_design_architecture.md`."*

**9. Stealing a Design System (Optional):**
> *"Run the `skillui-generator` against [INSERT URL HERE] to extract their design system for our components."*

**10. Writing the Weekly Client Update (Every Friday):**
> *"Run the `client-update-generator` skill based on this week's git commits to draft a progress email for the client."*

---

## Phase 5 & 6: Testing & Deployment
Auditing the code before going live.

**9. The Hacker Pentest (Strix):**
> "Run the `@strix-security-auditor.md` skill against this codebase to find and patch vulnerabilities."

**10. General Quality Audit:**
> "Run the `testing-coverage-audit`, `performance-audit`, and `wcag-accessibility-auditor` skills on the codebase."

**11. Mobile App Testing (If Applicable):**
> "Run the `android-cli` skill to boot up the virtual device emulator so I can test the UI."

---

## Phase 7: Handoff & Legal
Protecting yourself before giving the code to the client.

**12. Legal Audit:**
> "Generate the final SLA documents. Then run the `legal-risk-flagging` skill to audit them and ensure I am not accidentally promising 100% bug-free code or unlimited revisions."

---

## Special Cases

**13. Onboarding an Old / Legacy Project:**
> "Run the `@legacy-project-onboarder.md` skill to reverse-engineer this existing codebase into our formal agency documentation (PRD, Architecture, Runbook)."

**14. Mapping a Massive Codebase:**
> "Run the `@repowise-codebase-mapper.md` skill to index this massive codebase so you can understand it without running out of memory."

**15. Creating a Brand New Skill:**
> "Run the `workflow-skill-creator` to watch what I just did and package it into a new reusable skill file."

**16. Production App Is Crashing:**
> "Run the `@crash-debugger.md` skill. Here is the full error stack trace: *[PASTE STACK TRACE]*"

---

## Parallel Cross-Checking & Adversarial Review (The Critic)
Use these at ANY phase to have a dedicated red-team agent stress-test your work before moving forward.

**20. Cross-Checking a PRD or Requirements:**
> "Run the `@devils-advocate-critic.md` skill on `03_requirements_engineering.md`. Identify missing edge cases, ambiguous scope, and potential client dispute traps."

**21. Stress-Testing Architecture & Database Schema:**
> "Run the `@devils-advocate-critic.md` skill on `04_system_design_architecture.md`. Attack the database relations, indexing strategy, and API error states."

**22. Code Review & Vulnerability Hunting:**
> "Run the `@devils-advocate-critic.md` skill on `[path/to/file.ts]`. Try to break the logic, find race conditions, or exploit authentication/authorization gaps."

**23. Contract & Statement of Work Risk Audit:**
> "Run the `@devils-advocate-critic.md` skill on `01_proposal_sow.md` and `02_msa_contract.md`. Find any clause that exposes me to unlimited liability or unpaid scope creep."

---

## 🧠 Continuous Self-Learning Protocol (/learn)
Turn Antigravity into your self-improving Hermes agent. Run this after solving hard bugs or complex setups so every future project inherits the learning:

**24. Saving a Bug Fix or Solution Permanently:**
> *"Run the `@continuous-learner.md` skill on the fix we just applied to [file/bug]. Extract the rule and permanently upgrade `@crash-debugger.md`."*

**25. Using the Antigravity Slash Command:**
> You can also type `/learn` in the chat UI:
> *`/learn: Remember that in Supabase with Prisma, connection pooling requires pgbouncer=true in DATABASE_URL.`*

---

## Infrastructure & Automation Scripts

**24. Check Live Project Status & Progress Dashboard:**
```bash
python .agency/scripts/status.py
```

**25. Validate Phase & Auto-Advance to Next Phase:**
```bash
python .agency/scripts/validate_phase.py --advance
```

**26. Starting a Brand New Client Project (60 seconds):**
```bash
# Run from the agency_playbook directory
./bootstrap.sh "Client Name" "project-slug"
# Example:
./bootstrap.sh "Acme Corp" "acme-corp-app"
```

**27. Pushing Project to GitHub After Bootstrap:**
```bash
cd ../project-slug
gh repo create project-slug --private --source=. --push
```



# 🏚️ Runbook: Legacy Codebase Takeover & Brownfield Rescue

**Trigger:** Onboarding onto an existing, undocumented, fragile, or failing codebase built by a previous team or agency (`entry_mode: "brownfield_rescue"`).
**Objective:** Establish a deterministic safety net, map architectural landmines via Ripwire Layer 0, and stabilize deployments without breaking existing production revenue.

---

## 🕵️ Phase 1: Forensic Discovery & Structural Recall (Days 1–2)
**Active Role:** `@.agency/agents/engineering/devops_sre_engineer.md` & `@.agency/agents/engineering/solutions_architect.md`

1. **Zero-Copy Agency Initialization & Ripwire Recall:**
   - Initialize the workspace (`python agency.py init --entry-mode brownfield_rescue`) and run `python .agency/scripts/ripwire_engine.py --recall "architecture"` and `--doc-drift` to build the deterministic dependency graph, symbol centrality map, and documentation drift report.
   - Read `@.agency/skills/legacy-project-onboarder/SKILL.md` and `@.agency/skills/repowise-codebase-mapper/SKILL.md`.
2. **Access & Environment Audit:**
   - Verify access to Git repositories, cloud hosting, CI/CD pipelines, DNS, and secret managers.
   - Document local setup procedures in `.agency/templates/engineering/15_developer_onboarding.md`.
3. **Dependency & Secret Scan:**
   - Invoke `@.agency/agents/engineering/security_auditor.md` using `@.agency/skills/strix-security-auditor/SKILL.md` (`.agents/plugins/agency-playbook/skills/strix-security-auditor/SKILL.md`).
   - Check for hardcoded API keys in Git history, expired SSL certificates, and critical CVEs in `.agency/templates/engineering/09_security_compliance.md`.
4. **Database & Backup Verification:**
   - Invoke `@.agency/agents/engineering/database_engineer.md` to confirm automated daily database backups are enabled and test a restore into staging (`.agency/templates/engineering/17_disaster_recovery_bcp.md`).

---

## 🗺️ Phase 2: Architectural Mapping (Days 3–4)
**Active Role:** `@.agency/agents/engineering/solutions_architect.md`

1. **Reverse-Engineer the System:**
   - Map the actual data model (ERD), external third-party integrations, and critical business flows using `@.agency/skills/architecture-diagrammer/SKILL.md`.
   - Document findings in `.agency/templates/engineering/04_system_design_architecture.md`, highlighting **Technical Debt Landmines**.
2. **Critic Review:**
   - Run `@.agency/agents/oversight/master_critic.md` and `python .agency/scripts/laya_engine.py --score-deliverable .agency/templates/engineering/04_system_design_architecture.md` to prioritize which landmines pose an immediate existential threat.

---

## 🧪 Phase 3: The Characterization Safety Net (Days 5–7)
**Active Role:** `@.agency/agents/engineering/qa_sdet_engineer.md`

> **The Golden Rule of Legacy Code:** *Never refactor code that does not have an automated test proving its current behavior.*

1. **Smoke & E2E Tests First:**
   - Write Playwright/Cypress E2E tests or API integration tests covering the top 3 revenue-generating user flows and record results in `.agency/templates/engineering/06_testing_uat_signoff.md`.
2. **CI Pipeline Gate:**
   - Configure CI so smoke tests and `python .agency/scripts/ripwire_engine.py --quality-delta` run on every Pull Request.

---

## 🔧 Phase 4: Incremental Strangler-Fig Refactoring
**Active Roles:** `@.agency/agents/engineering/backend_engineer.md` & `@.agency/agents/engineering/frontend_engineer.md`
**Oversight:** `@.agency/agents/oversight/code_integrity_guardian.md`

1. **No "Big Bang" Rewrites:** Do not rewrite the entire app from scratch unless authorized by the Human Lead in `.agency/templates/engineering/04_system_design_architecture.md`.
2. **Boy Scout Rule:** Refactor incrementally inside the boundary of feature tickets or bug fixes, using `python .agency/scripts/ripwire_engine.py --pack-task "<module>" --partition 2` and `--plan-lanes 2` to isolate safe file ownership boundaries.

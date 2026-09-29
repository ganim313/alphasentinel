# 🤖 Agency Playbook — Claude Code Directives

This project is orchestrated using the **Agency Playbook AI Engineering Operating System** (`.agency/`).

## ⚡ Daily Command Center
- **Status Dashboard:** `python .agency/scripts/status.py`
- **Validate Deliverables:** `python .agency/scripts/validate_phase.py`
- **Auto-Advance Phase:** `python .agency/scripts/validate_phase.py --advance`
- **Transpile IDE Rules:** `python .agency/scripts/transpile_rules.py --target all`
- **Active State File:** `.agency/active/project_state.yml`

## 👥 Department Pods & Role Charters
- `@01_product_manager.md` — Product discovery, PRDs, client intake
- `@02_solutions_architect.md` — System design, OpenAPI contracts, HLD/LLD
- `@03_ui_ux_designer.md` & `@04_frontend_engineer.md` — Client UI, 8pt grid, WCAG AA
- `@05_backend_engineer.md` & `@06_database_engineer.md` — APIs, DB migrations, RLS
- `@07_qa_sdet_engineer.md` & `@08_security_auditor.md` — Playwright E2E, SAST security
- `@09_devops_sre_engineer.md` — CI/CD pipelines, Docker, runbooks
- `@10_legal_operations_officer.md` — SOWs, MSAs, SLAs, client handoff
- `@master_critic.md` — Adversarial audit and red-teaming

## 🚦 Strict Operational Rules
1. Never produce placeholder deliverables containing `[TBD]`, `[TODO]`, or empty sections.
2. For Tier 1 bug fixes, make direct surgical edits without role-swapping ceremony.
3. For Tier 3 full system builds, adhere strictly to the 7-Phase SDLC in `project_state.yml`.

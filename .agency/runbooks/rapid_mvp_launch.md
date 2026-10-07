# 🚀 Runbook: Rapid MVP Launch & Feature Addition Track

**Trigger:** Building a lean greenfield MVP or adding a scoped feature/change order to an existing application (`entry_mode: "feature_addition"`).
**Objective:** Compress the 7-Phase Agency Lifecycle into a high-velocity track without sacrificing security, code integrity, or commercial scope control.

---

## ⏱️ Step 1: Lean Scope, Change Order & Architecture Lock (Hours 0–4)
**Active Roles:** `@.agency/agents/product_design/product_manager.md` + `@.agency/agents/engineering/solutions_architect.md`

1. **Scope & Change Order Gate:**
   - Run `python .agency/scripts/laya_engine.py --classify-scope "<request>"` to verify whether the feature is in-scope or requires `.agency/templates/product_design/32_scope_creep_log.md` and `.agency/templates/finance_ops/14_change_order_form.md`.
   - Define the core user journey and Gherkin acceptance criteria in `.agency/templates/product_design/03_requirements_engineering.md`.
2. **Proven Tech Stack & Contracts:**
   - Read `@.agency/skills/tech-stack-adviser/SKILL.md` and `@.agency/skills/architecture-diagrammer/SKILL.md`.
   - Document the schema and API contracts in `.agency/templates/engineering/04_system_design_architecture.md`.
3. **Critic & Human Sign-Off Gate:**
   - Run `@.agency/agents/oversight/master_critic.md` and obtain **Human Lead Sign-Off**.

---

## 🎨 Step 2: Component-First UI Assembly (Hours 4–12)
**Active Roles:** `@.agency/agents/product_design/ui_ux_designer.md` + `@.agency/agents/engineering/frontend_engineer.md`
**Skills:** `@.agency/skills/senior-designer-ui/SKILL.md` & `@.agency/skills/skillui-generator/SKILL.md`

1. Document component tokens and layout specs in `.agency/templates/product_design/10_ui_ux_handoff.md`.
2. Implement all 4 interactive states for every view: **Loading, Empty, Error, and Populated**.

---

## ⚙️ Step 3: Parallel Vertical Slice Implementation (Hours 12–36)
**Active Roles:** `@.agency/agents/engineering/backend_engineer.md`, `@.agency/agents/engineering/database_engineer.md`, `@.agency/agents/engineering/frontend_engineer.md`
**Oversight:** `@.agency/agents/oversight/code_integrity_guardian.md`

1. Run `python .agency/scripts/ripwire_engine.py --plan-lanes 3` and `--merge-scout` to isolate parallel file ownership.
2. Build database migrations, API routes, authentication, and UI integration, recording progress in `.agency/templates/engineering/05_technical_sdlc_execution.md`.
3. Run `python .agency/scripts/ripwire_engine.py --quality-delta` and `python .agency/scripts/laya_engine.py --screen-code .` after each slice.

---

## 🚢 Step 4: Smoke Test & Production Ship (Hours 36–48)
**Active Roles:** `@.agency/agents/engineering/qa_sdet_engineer.md` + `@.agency/agents/engineering/devops_sre_engineer.md`

1. Complete E2E verification in `.agency/templates/engineering/06_testing_uat_signoff.md` and deployment checklist in `.agency/templates/engineering/07_deployment_runbook.md`.
2. Run `python agency.py validate --advance` and launch!

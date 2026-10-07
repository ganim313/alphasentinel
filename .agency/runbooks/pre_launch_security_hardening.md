# 🔐 Runbook: Pre-Launch Security & Production Hardening

**Trigger:** 48–72 hours prior to a major production launch or when responding to a security audit (`entry_mode: "security_incident"`).
**Objective:** Verify zero critical vulnerabilities, enforce infrastructure resilience, and obtain final Go/No-Go authorization.

---

## 🛡️ Step 1: Application & API Security Audit
**Active Role:** `@.agency/agents/engineering/security_auditor.md`
**Skill:** `@.agency/skills/strix-security-auditor/SKILL.md` (`.agents/plugins/agency-playbook/skills/strix-security-auditor/SKILL.md`)

- [ ] **Authentication & Session Management:** Verify JWT expiration, secure/HttpOnly cookies, CSRF protection, and brute-force rate limiting.
- [ ] **Authorization (IDOR & BOLA):** Test that User A cannot read or mutate User B's resources by swapping UUIDs/IDs or Tenant headers.
- [ ] **Input Validation & Injection:** Confirm all API endpoints validate payloads via strict schemas (Zod/Pydantic) and parameterized queries.
- [ ] **Secrets Hygiene:** Confirm `.env` files are gitignored and zero secrets exist in source bundles (`python .agency/scripts/laya_engine.py --screen-code .`).
- [ ] **Third-Party Vendor Risk:** Audit external processors in `.agency/templates/finance_ops/20_third_party_risk_assessment.md`.

**Deliverable:** Complete `.agency/templates/engineering/09_security_compliance.md`.

---

## ⚙️ Step 2: Infrastructure, Observability & Disaster Recovery
**Active Role:** `@.agency/agents/engineering/devops_sre_engineer.md` & `@.agency/agents/engineering/database_engineer.md`

- [ ] **Database Readiness:** Connection pooling active; automated backups enabled; Point-in-Time Recovery (PITR) verified in `.agency/templates/engineering/17_disaster_recovery_bcp.md`.
- [ ] **Zero-Downtime Deployments:** Health check endpoints (`/healthz`) verify DB connectivity before routing traffic; rollback procedure takes `< 5 minutes`.

**Deliverable:** Complete `.agency/templates/engineering/07_deployment_runbook.md`.

---

## 🧪 Step 3: Accessibility, Performance & E2E Sign-Off
**Active Roles:** `@.agency/agents/engineering/qa_sdet_engineer.md` & `@.agency/agents/product_design/ui_ux_designer.md`
**Skill:** `@.agency/skills/wcag-accessibility-auditor/SKILL.md`

- [ ] **Critical Path E2E:** 100% pass rate on automated Playwright E2E tests in staging (`.agency/templates/engineering/06_testing_uat_signoff.md`).
- [ ] **WCAG 2.1 AA Compliance:** Complete accessibility audit in `.agency/templates/engineering/19_accessibility_audit_wcag.md`.
- [ ] **Layer 0 & Layer 1 Gate:** Run `python .agency/scripts/ripwire_engine.py --quality-delta --doc-drift` and `python .agency/scripts/laya_engine.py --screen-code .` with zero blocking alerts.

---

## ⚖️ Step 4: Final Critic Gate & Human Go/No-Go
**Active Roles:** `@.agency/agents/oversight/master_critic.md` & `@.agency/agents/oversight/code_integrity_guardian.md`

1. Run `python agency.py validate` across all Phase 5 and Phase 6 deliverables.
2. Present the final readiness summary to the **Human Lead** for explicit sign-off before flipping production traffic.

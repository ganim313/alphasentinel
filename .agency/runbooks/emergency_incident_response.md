# 🚨 Runbook: Emergency Incident Response & Urgent Bugfix (SEV-1 / SEV-2)

**Trigger:** Production system is down, experiencing severe 500 crashes, or suffering an active security incident (`entry_mode: "urgent_bugfix"`).
**Objective:** Restore service (MTTR minimization) safely, prevent data corruption, and document root cause without bureaucratic delay.

---

## ⚡ Phase 0: Immediate Triage (Minutes 0–15)
**Active Role:** `@.agency/agents/engineering/devops_sre_engineer.md` (Incident Commander)
**Support Role:** `@.agency/agents/engineering/backend_engineer.md`

1. **Declare Incident:** Open a dedicated Incident Channel and start a live timeline in `.agency/templates/product_design/12_project_post_mortem.md`.
2. **Assess Blast Radius via Ripwire Layer 0:**
   - Read `@.agency/skills/crash-debugger/SKILL.md`.
   - Run `python .agency/scripts/ripwire_engine.py --from-trace "<stack_trace_or_error>"` and `--recall "<symbol>"` to locate exact fault symbols and blast-radius callers.
3. **The 5-Minute Rollback Rule:**
   - Did a deployment, config change, or feature flag toggle occur in the last 2 hours?
   - **YES:** Execute an immediate rollback per `.agency/templates/engineering/07_deployment_runbook.md`.
   - **NO:** Proceed to Phase 1 (Containment).

---

## 🛡️ Phase 1: Containment & Surgical Hotfix (Minutes 15–60)
**Active Role:** `@.agency/agents/engineering/backend_engineer.md` & `@.agency/agents/engineering/security_auditor.md`

1. **Shed Load / Isolate Fault:**
   - Enable rate-limiting, block malicious IPs at the WAF, or disable the failing queue consumer via feature flag.
2. **Database Protection (`@.agency/agents/engineering/database_engineer.md`):**
   - Terminate runaway queries (`pg_terminate_backend`). Never run destructive queries without a snapshot.
3. **Draft Surgical Hotfix:**
   - Write the minimum viable patch in `.agency/templates/engineering/05_technical_sdlc_execution.md`.
   - Run `python .agency/scripts/ripwire_engine.py --edit-check <file>` and `python .agency/scripts/laya_engine.py --screen-code <file>` to ensure the hotfix introduces zero regressions.
   - Invoke `@.agency/agents/oversight/code_integrity_guardian.md` and `@.agency/agents/oversight/master_critic.md` for an expedited review.

---

## 🔍 Phase 2: Verification & Recovery
**Active Role:** `@.agency/agents/engineering/qa_sdet_engineer.md`

1. **Regression Test:** Add an automated regression test reproducing the exact stack trace in `.agency/templates/engineering/06_testing_uat_signoff.md`.
2. **Verify Metrics:** Confirm error rates and latency have returned to baseline for at least 15 consecutive minutes.

---

## 📝 Phase 3: Blameless Post-Mortem (Within 24–48 Hours)
**Active Role:** `@.agency/agents/engineering/devops_sre_engineer.md`
**Critic Gate:** `@.agency/agents/oversight/master_critic.md`

1. Complete `.agency/templates/product_design/12_project_post_mortem.md`.
2. Run `python .agency/scripts/laya_engine.py --score-deliverable .agency/templates/product_design/12_project_post_mortem.md` and obtain **Human Lead Sign-Off**.

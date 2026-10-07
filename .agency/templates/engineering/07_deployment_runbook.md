---
template_id: "07"
phase: 6
assigned_role: "engineering/devops_sre_engineer"
context_from: ["engineering/05_technical_sdlc_execution.md", "engineering/06_testing_uat_signoff.md"]
outputs_to: ["finance_ops/08_post_launch_sla.md", "finance_ops/16_final_handoff_release.md"]
status: template
---
# Template 07: Deployment Runbook & Handoff

**Purpose:** Safely transitioning the software from your control to the live production internet.

> [!CAUTION]
> **CRITICAL AGENCY RULE:** Never execute the Deployment Runbook or hand over administrative passwords until the final milestone invoice has been paid in full and the money has cleared your bank account.

---

## 1. Pre-Deployment Checklist
- [ ] Final 10% payment received.
- [ ] UAT Sign-off received via email.
- [ ] Production Environment Variables (.env) securely injected into the production host.
- [ ] Database migrated to the production schema.
- [ ] Production API keys generated (e.g., Live Stripe keys instead of test keys).
- [ ] Domain Name (DNS) configured to point to the production server.

## 2. The Deployment Runbook
*(CRITICAL: You must explicitly define every single Environment Variable required, and write out the exact configuration files or shell scripts needed. Do not summarize.)*

### Environment Variables (.env)
| Variable Key | Description | Required? | Where to get it |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Postgres connection string | Yes | Supabase Dashboard |
| `STRIPE_SECRET` | Live Stripe Key | Yes | Stripe Dashboard |

### Build & Deploy Configuration
* **Dockerfile / CI Pipeline:** (You MUST write the exact `Dockerfile` or `.github/workflows/deploy.yml` code block required to deploy this app).
* **Execution Steps:** Document the exact terminal commands required to deploy.
  1. `[Command 1]`
  2. `[Command 2]`

## 3. Handoff Deliverables
Provide the client with a secure document (e.g., 1Password link or encrypted PDF) containing:
1. **Source Code:** Transfer ownership of the GitHub repository to their organization.
2. **Infrastructure Access:** Hand over admin access to Vercel, Supabase, Cloudflare, etc.
3. **Documentation:**
   * `README.md` (Developer setup guide).
   * `STAFF_MANUAL.md` (End-user instructions for their employees).


---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the deployment readiness checklist and wait for the human lead's explicit approval before triggering the live production release.)*

* **Key Decision 1 (Environment Variables Verified):** `[All production secrets verified in cloud hosting dashboard]`
* **Key Decision 2 (Database Migration Plan):** `[Confirmation of zero-downtime non-destructive schema migration]`
* **Key Decision 3 (Rollback Trigger & Plan):** `[Documented 1-click rollback command ready if health check fails]`

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
- [ ] 07_deployment_runbook.md

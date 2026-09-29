---
template_id: "08"
phase: 7
assigned_role: "10_legal_operations_officer"
context_from: ["07_deployment_runbook.md"]
outputs_to: []
status: template
---
# Template 08: Post-Launch Retainer & SLA

**Purpose:** Software requires upkeep. This template secures recurring monthly revenue (MRR) for your agency by offering maintenance services.

---

## 1. The Warranty Period
* Standard inclusion: A 14-day or 30-day post-launch warranty.
* During this period, any critical bugs that escaped UAT will be patched free of charge. No new features will be added.

## 2. Annual Maintenance Contract (AMC) / Monthly Retainer
*Pitch this to the client as an "insurance policy" for their new asset.*

**Cost:** `$XXX / month`

**What is Included:**
* **Hosting Management:** We manage the Vercel and Supabase billing limits and infrastructure.
* **Security Patches:** We run `npm audit` monthly to patch critical vulnerabilities in open-source dependencies.
* **Routine Backups:** Automated weekly database backups.
* **Minor Tweaks Bucket:** Includes [X] hours per month of minor text changes or UI tweaks (unused hours do not roll over).

## 3. Service Level Agreement (SLA)
If the client pays for the premium retainer, guarantee response times:
* **Severity 1 (System Offline):** Guaranteed developer response within 4 hours.
* **Severity 2 (Core Feature Broken but system online):** Guaranteed response within 12 hours.
* **Severity 3 (Minor UI bug):** Guaranteed response within 48 business hours.


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 08_post_launch_sla.md

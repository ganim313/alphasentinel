---
template_id: "17"
phase: 3
assigned_role: "09_devops_sre_engineer"
context_from: ["04_system_design_architecture.md"]
outputs_to: []
status: template
---
# Template 17: Disaster Recovery & Business Continuity Plan (BCP)

**Purpose:** A formal emergency protocol. When production goes down or data is lost, engineers execute this runbook rather than panicking. Required by many enterprise clients.

---

## 1. Risk Assessment & RTO/RPO
Define the acceptable limits for system downtime.
* **Recovery Time Objective (RTO):** How long can the system be completely offline? (e.g., "Maximum 4 hours downtime").
* **Recovery Point Objective (RPO):** How much data is acceptable to lose? (e.g., "Maximum 24 hours of data loss").

## 2. Backup Strategy
* **Database Backups:** PostgreSQL backups run daily at 02:00 AM via Supabase automated backups. Point-in-Time Recovery (PITR) enabled.
* **Asset Backups:** Cloudinary images are mirrored/backed up to an AWS S3 Cold Storage bucket weekly.

## 3. Incident Response Protocol (Step-by-Step)
If the primary server (e.g., Vercel) goes down globally:
1. **Acknowledge:** Engineer on-call logs into the Status page and sets banner: "Investigating Outage."
2. **Diagnose:** Check Sentry and hosting provider status pages.
3. **Failover (If necessary):** If the primary host is permanently down, deploy the latest `main` branch to the secondary fallback host (e.g., AWS Amplify/Netlify) and update Cloudflare DNS records.
4. **Restore Database (If corrupted):** Navigate to Supabase Dashboard -> Backups -> Restore to the latest healthy snapshot (PITR).
5. **Resolve:** Update Status page to "Operational" and draft a Post-Incident Report.

## 4. Post-Incident Report (PIR)
Required within 48 hours of any downtime exceeding 1 hour.
- What caused the outage?
- How was it fixed?
- What engineering steps are being taken to ensure this specific failure never happens again?


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 17_disaster_recovery_bcp.md

---
template_id: "20"
phase: 5
assigned_role: "engineering/security_auditor"
context_from: ["engineering/04_system_design_architecture.md"]
outputs_to: ["engineering/09_security_compliance.md"]
status: template
---
# Template 20: Third-Party Risk Assessment

**Purpose:** Modern apps rely heavily on external APIs (BaaS). You must document the risk to the client if these third-party companies go bankrupt, raise their prices exponentially, or suffer a massive outage.

---

## 1. Core Infrastructure Dependencies
List every third-party service the application relies on to function.

### Service 1: Supabase (Database & Auth)
* **Risk Level:** High (Single Point of Failure).
* **Impact of Outage:** The entire application goes offline; users cannot log in or view products.
* **Mitigation Strategy:** Supabase uses standard PostgreSQL under the hood. If Supabase shuts down, we can export the SQL schema and data and migrate it to AWS RDS or a raw DigitalOcean Droplet within 48 hours.

### Service 2: Cloudinary (Image CDN)
* **Risk Level:** Medium.
* **Impact of Outage:** The site loads, but all product images are broken.
* **Mitigation Strategy:** We maintain local backups of all raw product images. If Cloudinary fails, we can point the image domains to an AWS S3 bucket as a fallback.

### Service 3: Resend / SendGrid (Transactional Emails)
* **Risk Level:** Low.
* **Impact of Outage:** Order confirmation emails are delayed or fail to send.
* **Mitigation Strategy:** Email delivery is abstracted behind a generic `EmailService` class in the code. We can swap the API key to a fallback provider (e.g., Mailgun) within 15 minutes of an outage.

## 2. Vendor Lock-in Assessment
* Evaluate how deeply tied the codebase is to proprietary SDKs.
* *Example:* "We use Next.js, which is heavily optimized for Vercel. However, we are not using Vercel-specific proprietary features (like Vercel KV), meaning the app can be containerized using Docker and deployed anywhere if necessary."

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Note 1: e.g., Approved vendor lock-in mitigation strategies and fallback SLAs.]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] `finance_ops/20_third_party_risk_assessment.md`

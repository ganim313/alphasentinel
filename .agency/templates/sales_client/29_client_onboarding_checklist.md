---
template_id: "29"
phase: 1
assigned_role: "sales_client/account_manager"
context_from: ["product_design/01_proposal_sow.md", "finance_ops/02_msa_contract.md"]
outputs_to: ["product_design/03_requirements_engineering.md"]
status: template
---
# Template 29: Client Onboarding Checklist & Kickoff Protocol

**Purpose:** To orchestrate the formal kickoff meeting, secure all required third-party environment credentials, establish communication cadences, and align stakeholders on project governance.

---

## 1. Project Stakeholder Directory

| Role | Name | Organization | Email / Contact | Slack / Communication Handle | Primary Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Client Executive Sponsor** | `[Name]` | Client Org | `[Email]` | `@handle` | Final Budget & Contract Approvals |
| **Client Product Owner** | `[Name]` | Client Org | `[Email]` | `@handle` | Weekly Sprint Demos & Acceptance |
| **Agency Lead Architect** | `[Name]` | Agency Org | `[Email]` | `@handle` | Technical Architecture & Delivery |
| **Agency Account Manager**| `[Name]` | Agency Org | `[Email]` | `@handle` | Status Reporting & Scope Alignment |

---

## 2. Third-Party Access & Infrastructure Checklist

| Service / Resource | Access Method | Target Environment | Status | Assigned To |
| :--- | :--- | :--- | :--- | :--- |
| **Source Control (GitHub/GitLab)** | Invite Agency Org / Team | Private Repository | `[✅ Received / ⏳ Pending]` | Client Tech Lead |
| **Cloud Hosting (AWS/GCP/Vercel)** | IAM Role / Org Team Member | Staging & Prod Accounts | `[✅ Received / ⏳ Pending]` | Client DevOps |
| **Database (Supabase/RDS)** | DB Connection String & IAM | Staging Database | `[✅ Received / ⏳ Pending]` | Client Tech Lead |
| **Auth Provider (Clerk/Auth0)** | Admin Dashboard Invite | Dev / Staging Tenant | `[✅ Received / ⏳ Pending]` | Client Tech Lead |
| **Payment Gateway (Stripe)** | Developer / Restricted API Key | Test Mode Account | `[✅ Received / ⏳ Pending]` | Client Finance |
| **Shared Slack / Teams Channel** | Connect / Shared Channel | Dedicated `#proj-client` | `[✅ Received / ⏳ Pending]` | Agency Account Lead |

---

## 3. Kickoff Meeting Agenda (60 Minutes)
1. **00-10m: Introductions & Project Vision:** Executive sponsor reaffirms the primary business outcome.
2. **10-25m: Scope Boundaries & SOW Review:** Walkthrough of approved deliverables vs. out-of-scope items.
3. **25-40m: Engineering SDLC & Demo Cadence:** Explanation of weekly Friday async video demos and GitHub PR flows.
4. **40-50m: Communication Protocol & Escalations:** Guidelines on Slack response times (under 4 hours during business hours).
5. **50-60m: Q&A and Next Steps:** Sign-off on sprint 1 milestones.

---

## 4. Communication & Escalation Protocols
- **Daily Async Updates:** Posted in client Slack channel by 10:00 AM local time.
- **Weekly Progress Report:** Formal executive update email and `30_weekly_account_status.md` every Friday.
- **Urgent Blockers / P0 Emergencies:** Direct telephone or Slack `@here` mention with `< 1 hour` SLA.
- **Scope Change Requests:** Handled formally via `14_change_order_form.md`; zero informal scope promises in chat.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (Access Readiness):** `[Confirmation that all critical developer credentials have been provisioned]`
* **Key Decision 2 (Communication Cadence):** `[Agreement on daily Slack check-ins and Friday demo schedule]`
* **Key Decision 3 (Escalation Path):** `[Confirmed contact channels for executive decision makers]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Type 'Approved' or enter adjustments]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] All required API keys and cloud repository invites verified by engineering.
- [ ] Kickoff meeting notes recorded and distributed to all participants.
- [ ] No placeholder markers (`[TBD]`) remaining.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `sales_client/29_client_onboarding_checklist.md`
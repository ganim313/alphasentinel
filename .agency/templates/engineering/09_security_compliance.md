---
template_id: "09"
phase: 5
assigned_role: "engineering/security_auditor"
context_from: ["engineering/04_system_design_architecture.md"]
outputs_to: ["engineering/07_deployment_runbook.md"]
status: template
---
# Template 09: Security & Compliance Audit Checklist

**Purpose:** Ensure the software protects user data and defends against common attacks before deploying to production.

---

## 1. Application Security (OWASP Top 10)
Execute this checklist before UAT begins.
- [ ] **Injection:** Are SQL databases protected via ORMs/Query Builders (e.g., Prisma, Supabase RLS) to prevent SQL Injection?
- [ ] **Authentication:** Are passwords hashed securely (e.g., bcrypt/argon2)? Are session tokens (JWTs) stored in secure, `HttpOnly` cookies rather than `localStorage`?
- [ ] **Cross-Site Scripting (XSS):** Are inputs sanitized? Does the frontend framework (React/Next.js) automatically escape user-generated content?
- [ ] **Rate Limiting:** Is `express-rate-limit` (or similar) applied to authentication and sensitive endpoints to prevent brute-force attacks?
- [ ] **Security Headers:** Are HTTP security headers implemented via `Helmet` (e.g., Strict-Transport-Security, Content-Security-Policy)?

## 2. Infrastructure Security
- [ ] **Secrets Management:** Are all `.env` files completely excluded from GitHub (`.gitignore`)?
- [ ] **CORS Settings:** Is Cross-Origin Resource Sharing explicitly restricted to the production client domain?
- [ ] **Database Access:** Is the database locked behind a VPC or IP-allowlist so it cannot be queried directly from the public internet?

## 3. Data Privacy & Compliance
- [ ] **GDPR / CCPA:** Does the app have a "Cookie Consent" banner?
- [ ] **Data Deletion:** Is there a process for users to request account deletion (Right to be Forgotten)?
- [ ] **PII Handling:** Are Personally Identifiable Information (PII) fields (like phone numbers or credit cards) encrypted at rest?

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 security audit findings and wait for the human lead's explicit approval before proceeding to Deployment.)*

* **Key Decision 1 (OWASP & RLS Posture):** `[Confirmed zero Critical/High SQLi, XSS, IDOR, or missing tenant RLS vulnerabilities]`
* **Key Decision 2 (Secret & Header Hygiene):** `[Verified zero leaked secrets in git history and strict CSP/HSTS headers]`
* **Key Decision 3 (Data Privacy & PII):** `[Confirmed encryption at rest and GDPR/CCPA deletion workflow compliance]`

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
- [ ] 09_security_compliance.md

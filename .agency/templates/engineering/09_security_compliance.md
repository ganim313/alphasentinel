---
template_id: "09"
phase: 5
assigned_role: "08_security_auditor"
context_from: ["04_system_design_architecture.md"]
outputs_to: []
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

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 09_security_compliance.md

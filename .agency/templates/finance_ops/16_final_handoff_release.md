---
template_id: "16"
phase: 7
assigned_role: "10_legal_operations_officer"
context_from: ["07_deployment_runbook.md"]
outputs_to: ["12_project_post_mortem.md"]
status: template
---
# Template 16: Final Legal Handoff & Release of Liability

**Purpose:** The final document signed by the client when the project concludes. It transfers the intellectual property to them and legally protects you from being sued if the software crashes a year from now.

---

## 1. Project Conclusion Statement
This document acknowledges the successful completion and delivery of the custom software project: **[Project Name]**.

## 2. Transfer of Intellectual Property (IP)
Upon the clearing of the final invoice payment of `$XXX` on `[Date]`, **[Agency Name]** formally transfers all Intellectual Property rights, source code ownership, and administrative credentials for the aforementioned project to **[Client Name]**.

## 3. Acknowledgement of Deliverables
The Client confirms receipt of the following:
- [ ] Full Source Code Repository access.
- [ ] Administrative access to hosting platforms (Vercel, AWS, Supabase).
- [ ] Administrative access to third-party integrations (Stripe, Cloudinary).
- [ ] Technical Setup Documentation and End-User Manuals.

## 4. Release of Liability & Warranty Expiration
The Client acknowledges that the software has successfully passed User Acceptance Testing (UAT) and operates as described in the Product Requirements Document (PRD).

Unless an active Annual Maintenance Contract (AMC) or Service Level Agreement (SLA) is signed, **[Agency Name]** is under no obligation to provide future bug fixes, security patches, or server maintenance. The Developer provides the software "as-is" and is fully released from liability regarding any future data loss, server downtime, or third-party API deprecations.

---
**Agency Representative:**
Signature: _______________________ Date: _________

**Client Representative:**
Signature: _______________________ Date: _________


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 16_final_handoff_release.md

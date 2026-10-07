---
template_id: "02"
phase: 1
assigned_role: "finance_ops/legal_operations_officer"
context_from: ["product_design/01_proposal_sow.md"]
outputs_to: ["product_design/03_requirements_engineering.md"]
status: template
---
# Template 02: Master Services Agreement (MSA)

**Purpose:** The legally binding contract that protects your Intellectual Property and ensures you get paid. *(Note: Have a local attorney review this for your jurisdiction).*

---

## 1. Parties
This Agreement is entered into by and between **[Your Agency Name]** ("Developer") and **[Client Name]** ("Client").

## 2. Services Rendered
Developer agrees to provide software development services as explicitly defined in the attached Statement of Work (SOW). Any features requested outside the SOW require a paid "Change Order".

## 3. Payment Terms
Invoices are due Net-15 days from receipt. Work will halt if invoices remain unpaid past the due date. A late fee of 5% applies to overdue invoices.

## 4. Intellectual Property (The Golden Rule)
Developer retains all copyright and intellectual property rights to the source code **until the final invoice is paid in full**. Upon receipt of final payment, full IP ownership transfers to the Client. Developer may reuse open-source components or generic backend libraries.

## 5. Termination
Either party may terminate this agreement with 14 days written notice. If Client terminates early, Developer retains the initial deposit and will bill for all hours worked up to the termination date.

## 6. Limitation of Liability
Developer provides the software "as-is" upon final delivery. Developer is not liable for indirect, incidental, or consequential damages (including lost profits) arising from the use of the software.

*(Signatures of both parties)*

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 legal & commercial terms and wait for the human lead's explicit approval before proceeding to Requirements.)*

* **Key Decision 1 (IP Transfer Gate):** `[Confirmed IP ownership remains with Agency until 100% of final payment clears]`
* **Key Decision 2 (Payment & Late Terms):** `[Net-15 invoice schedule, 30/30/30/10 milestones, and 5% late fee clause]`
* **Key Decision 3 (Liability Cap):** `[Limitation of liability capped at total contract value; zero consequential damages]`

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
- [ ] 02_msa_contract.md

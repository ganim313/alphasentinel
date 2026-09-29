---
template_id: "02"
phase: 1
assigned_role: "10_legal_operations_officer"
context_from: ["01_proposal_sow.md"]
outputs_to: ["03_requirements_engineering.md"]
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

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 02_msa_contract.md

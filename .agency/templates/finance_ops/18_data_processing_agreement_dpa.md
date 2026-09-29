---
template_id: "18"
phase: 1
assigned_role: "10_legal_operations_officer"
context_from: ["02_msa_contract.md"]
outputs_to: []
status: template
---
# Template 18: Data Processing Agreement (DPA)

**Purpose:** If you are building software that handles personal user data (emails, phone numbers, addresses), and your agency is managing the hosting/database, you act as a "Data Processor" under GDPR and CCPA. This legal document is mandatory for enterprise compliance.

---

## 1. Roles & Responsibilities
* **Data Controller:** [Client Name] (They own the data and decide *why* it is collected).
* **Data Processor:** [Agency Name] (We store and manage the data on their behalf).

## 2. Details of Processing
* **Nature of Data:** The software collects names, email addresses, phone numbers, and physical delivery addresses.
* **Duration of Processing:** The Processor will hold this data for the duration of the active Annual Maintenance Contract (AMC). Upon contract termination, the Processor will return or securely destroy all data within 30 days.

## 3. Security Obligations of the Processor
The Processor (Agency) agrees to:
- Implement industry-standard security measures (e.g., hashing passwords, encrypting PII at rest).
- Ensure any sub-processors (e.g., Supabase, Vercel) also comply with GDPR standards.
- Notify the Data Controller (Client) within **72 hours** of discovering any data breach.

## 4. Sub-Processors Used
The Client authorizes the use of the following third-party infrastructure to process data:
- **Supabase / AWS:** Database hosting.
- **Vercel:** Application hosting.
- **Resend/SendGrid:** Transactional email delivery.

*(Signatures of both parties required before processing live data)*


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 18_data_processing_agreement_dpa.md

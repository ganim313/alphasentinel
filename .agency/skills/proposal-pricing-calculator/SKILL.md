---
name: proposal-pricing-calculator
description: "Generates a scoped Statement of Work and calculates estimated pricing based on feature breakdown."
---

# Proposal & Pricing Calculator Skill

## Trigger
Use this skill when the client intake is complete and the user requests a proposal or Statement of Work (SOW).

## Instructions
1. **Read Inputs**: Read the completed `.agency/active/13_client_intake_questionnaire.md`.
2. **Feature Breakdown**: Break down the client's requested solution into discrete, buildable features (e.g., "Auth System", "Payment Integration", "Admin Dashboard").
3. **Estimate Effort**: For each feature, estimate the number of development hours required. Use your historical knowledge of standard tech stacks (Next.js, Node, Postgres).
4. **Calculate Pricing (Geographic Market Rates)**: 
   - **STOP** and explicitly ask the user: *"What is the target country for this client? I will base the pricing on local market rates."*
   - Once the user provides the country, use your web browsing or research capabilities to rigorously search for the current standard software development agency rates in that specific country.
   - Present the researched hourly/project rate to the user for approval.
   - Once approved, multiply the estimated hours by the researched local rate to generate a subtotal for each feature.
5. **Draft SOW**: Use `.agency/templates/01_proposal_sow.md`. Populate the document, ensuring you list both the "In-Scope Features" with their line-item costs, and explicitly list "Out-of-Scope" items to protect the agency.
6. **Output**: Save to `.agency/active/01_proposal_sow.md`.

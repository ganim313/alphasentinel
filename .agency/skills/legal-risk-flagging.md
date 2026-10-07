---
name: legal-risk-flagging
description: Audits generated contracts (MSA, SLA, SOW) to flag liabilities or over-promises before presenting to the client.
---

# Legal Risk Flagger Skill

## Trigger
Use this skill after generating the MSA (`02_msa_contract.md`), SOW (`01_proposal_sow.md`), or SLA (`08_post_launch_sla.md`), before human review.

## Instructions
1. **Audit Scope**: Read the target contract document thoroughly.
2. **Identify Risks**: Scan for the following high-risk agency anti-patterns:
   - Promises of "100% bug-free" software.
   - Response time guarantees under 24h without a paid retainer.
   - IP transfer clauses that fire *before* final payment is cleared.
   - Ambiguous SOW scope that opens the door to scope creep (e.g., "admin panel" vs. "admin panel with user CRUD").
   - Unlimited revisions clauses.
   - Liability clauses that hold the agency responsible for data breaches caused by the client.
   - Missing Intellectual Property (IP) ownership clause (if not stated, the client might own nothing).
3. **Report**: Generate a risk report as a Markdown table, sorted by severity:

   | Risk ID | Severity | Exact Quote from Document | Why It's Dangerous | Suggested Rewrite |
   | :--- | :--- | :--- | :--- | :--- |
   | R-01 | 🔴 Critical | `"..."` | `[Explanation]` | `"[Safe rewrite]"` |
   | R-02 | 🟡 Medium | `"..."` | `[Explanation]` | `"[Safe rewrite]"` |

4. **Auto-Fix**: After presenting the report, ask the user: "Do you want me to apply all Critical fixes automatically?"  Apply all accepted fixes directly to the document.


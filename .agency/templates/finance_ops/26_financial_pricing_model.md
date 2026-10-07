---
template_id: "26"
phase: 1
assigned_role: "finance_ops/finance_strategist"
context_from: ["product_design/01_proposal_sow.md", "sales_client/13_client_intake_questionnaire.md"]
outputs_to: ["finance_ops/02_msa_contract.md"]
status: template
---
# Template 26: Financial Pricing & Burn Rate Model

**Purpose:** To define project unit economics, cost of goods sold (COGS), third-party SaaS/hosting overhead, profit margins, cash flow milestones, and agency burn rate forecasting.

---

## 1. Project Financial Summary

| Metric | Amount (USD) | % of Total SOW | Notes / Assumptions |
| :--- | :--- | :--- | :--- |
| **Total Contract Value (TCV)** | `$XX,XXX` | 100% | Fixed bid / milestone-based agreement |
| **Direct Engineering Labor** | `$XX,XXX` | `~50%` | Estimated `XXX` developer hours @ `$XX/hr` cost |
| **Third-Party Infrastructure & APIs** | `$X,XXX` | `~10%` | Cloud hosting, LLM tokens, database, auth APIs |
| **Project Contingency Reserve** | `$X,XXX` | `~10%` | Buffer for scope clarification and edge-case testing |
| **Gross Profit Margin Target** | `$XX,XXX` | `~30% - 40%` | Net agency gross profit |

## 2. Infrastructure & Third-Party COGS Breakdown

| Service / Tool | Estimated Monthly Cost | Annual Cost | Billed Directly to Client? |
| :--- | :--- | :--- | :--- |
| **Cloud Hosting (Vercel / AWS)** | `$XX / month` | `$XXX` | Yes (Client Account) |
| **Managed Database (Supabase / RDS)** | `$XX / month` | `$XXX` | Yes (Client Account) |
| **AI / LLM API Tokens (OpenAI / Anthropic)** | `$XXX / month` | `$X,XXX` | Yes (Client API Key) |
| **Authentication & Email (Clerk / Resend)** | `$XX / month` | `$XXX` | Yes (Client Account) |
| **Payment Gateway (Stripe Fees)** | `2.9% + $0.30/tx` | Variable | Yes (Direct from transaction) |

## 3. Milestone Billing & Cash Flow Schedule

| Milestone # | Trigger Event | Deliverable Output | % Due | Amount (USD) | Payment Terms |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **M1: Deposit** | SOW / MSA Execution | Project Kickoff & Repo Init | 30% | `$X,XXX` | Due upon invoice |
| **M2: Architecture** | PRD & HLD Approval | `03_requirements` & `04_system_design` | 30% | `$X,XXX` | Net 14 Days |
| **M3: Code Freeze** | Beta Build & UAT Start | `06_testing_uat_signoff.md` | 30% | `$X,XXX` | Net 14 Days |
| **M4: Final Handoff**| Production Deployment | `16_final_handoff_release.md` | 10% | `$X,XXX` | Prior to DNS handover |

## 4. Labor Allocation & Burn Rate Forecast

```
Sprint 1 (Weeks 1-2): [████████░░░░] 40 Hours (Discovery & Architecture)
Sprint 2 (Weeks 3-4): [████████████] 80 Hours (Core Backend & DB Engineering)
Sprint 3 (Weeks 5-6): [████████████] 80 Hours (Frontend UI & API Integration)
Sprint 4 (Weeks 7-8): [██████░░░░░░] 40 Hours (QA, Security Audit & Launch)
Total Estimated Effort: 240 Hours
```

## 5. Scope Creep & Hourly Overage Rates
- **Hourly Overage Rate:** `$XXX / hour` for out-of-scope work approved via `14_change_order_form.md`.
- **Minimum Billing Increment:** 0.5 hours.
- **SLA Maintenance Tier:** `$X,XXX / month` post-launch retainer for ongoing bug fixes and updates.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (Gross Margin):** `[Confirmed gross profit margin target (>= 35%)]`
* **Key Decision 2 (Milestone Structure):** `[Agreement on 30/30/30/10 milestone payment triggers]`
* **Key Decision 3 (Client COGS Pass-through):** `[Explicit agreement that client provides cloud/API billing credentials]`

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
- [ ] Milestone payment percentages sum to exactly 100%.
- [ ] COGS estimates verified against cloud pricing calculators.
- [ ] Out-of-scope change order rate explicitly stated.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `finance_ops/26_financial_pricing_model.md`
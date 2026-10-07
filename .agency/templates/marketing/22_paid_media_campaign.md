---
template_id: "22"
phase: 6
assigned_role: "marketing/paid_media_buyer"
context_from: ["marketing/11_go_to_market_analytics.md", "marketing/21_seo_audit_strategy.md"]
outputs_to: ["finance_ops/08_post_launch_sla.md"]
status: template
---
# Template 22: Paid Media Campaign Plan

**Purpose:** To define paid advertising channels, budget allocations, target audience segments, ad copy variants, UTM tracking taxonomy, and unit economics (CAC/LTV) for client growth campaigns.

---

## 1. Campaign Objectives & Target Economics
Define the core KPIs, target customer acquisition cost (CAC), and payback period:
- **Primary Campaign Goal:** `[Lead Generation / Self-Serve SaaS Signups / Demo Bookings]`
- **Target Monthly Ad Spend:** `$X,XXX / month`
- **Target Blended CAC:** `$XX.XX`
- **Target Payback Period:** `[< 3 Months / < 6 Months]`
- **Expected Conversion Rate (Landing Page):** `[3% - 7%]`

## 2. Channel Strategy & Budget Allocation

| Channel | Monthly Budget | Target CPC / CPM | Expected Leads/Signups | Target Audience Segment |
| :--- | :--- | :--- | :--- | :--- |
| **Google Search (PPC)** | `$X,XXX` (40%) | `$X.XX CPC` | `XX` | High-intent solution seekers |
| **Meta Ads (FB/IG)** | `$X,XXX` (35%) | `$XX.XX CPM` | `XX` | Lookalikes & interest retargeting |
| **LinkedIn Ads** | `$X,XXX` (25%) | `$XX.XX CPC` | `XX` | B2B Decision Makers (VPs, CTOs, PMs) |

## 3. Creative & Ad Copy Matrix

| Ad ID | Channel | Ad Format | Headline (`< 30 chars`) | Primary Text / Body Copy | Call to Action (CTA) | Destination URL + UTM |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AD-01` | Google | Responsive Search | `[Headline 1]` | `[Compelling benefit-driven copy]` | Start Free Trial | `https://[app.com]?utm_source=google&utm_medium=cpc&utm_campaign=launch` |
| `AD-02` | Meta | Video / Carousel | `[Headline 2]` | `[Problem/Agitate/Solution copy]` | Book a Demo | `https://[app.com]?utm_source=meta&utm_medium=paid_social&utm_campaign=prospecting` |

## 4. Pixel & Conversion Tracking Taxonomy
Specify the server-side and client-side tracking events required:
- **Meta Pixel / Conversions API (CAPI):** `PageView`, `ViewContent`, `Lead`, `CompleteRegistration`, `Purchase`
- **Google Tag Manager / GA4:** `conversion_lead`, `conversion_trial_start`, `conversion_checkout_complete`
- **LinkedIn Insight Tag:** `Event: Demo_Requested`, `Event: Account_Created`

## 5. Retargeting & Nurture Funnel
- **Top of Funnel (TOF):** Cold awareness via high-value problem demonstration.
- **Middle of Funnel (MOF):** Case studies, product tours, and customer testimonials.
- **Bottom of Funnel (BOF):** 14-day abandoned checkout/trial retargeting with urgency discount or executive consultation offer.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (Channel Allocation):** `[Budget split across Google, Meta, and LinkedIn]`
* **Key Decision 2 (CAC Target):** `[Approved target CAC and conversion thresholds]`
* **Key Decision 3 (Pixel Setup):** `[Server-side tracking & conversion event taxonomy]`

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
- [ ] Tracking pixels and conversion events verified via Tag Assistant / Pixel Helper.
- [ ] UTM parameters standardized and verified in destination URLs.
- [ ] Ad copy variants reviewed for brand tone and compliance.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `marketing/22_paid_media_campaign.md`
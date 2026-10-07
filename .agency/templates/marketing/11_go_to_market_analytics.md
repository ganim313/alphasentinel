---
template_id: "11"
phase: 7
assigned_role: "marketing/growth_hacker"
context_from: ["product_design/01_proposal_sow.md", "engineering/07_deployment_runbook.md"]
outputs_to: []
status: template
---
# Template 11: Go-To-Market & Analytics Setup

**Purpose:** Preparing the software to be discovered by search engines and tracked for business metrics immediately upon launch.

---

## 1. Technical SEO Checklist
If the site cannot be crawled by Google, it will not make money.
- [ ] **Meta Tags:** Every page must have a unique `<title>` and `<meta name="description">`.
- [ ] **Open Graph (OG) Tags:** Ensure `<meta property="og:image">` is set so the link looks attractive when shared on WhatsApp, Twitter, or LinkedIn.
- [ ] **Sitemap:** Generate an `sitemap.xml` file (dynamic if products change frequently).
- [ ] **Robots.txt:** Ensure `robots.txt` exists and does not accidentally block search engines from crawling the production site (e.g., remove `Disallow: /`).
- [ ] **Canonical Links:** Ensure canonical tags are present to avoid duplicate content penalties.

## 2. Web Analytics & Tracking
You must be able to measure traffic and user behavior on Day 1.
- [ ] **Google Analytics (GA4):** Setup and verify the tracking tag.
- [ ] **Event Tracking (Mixpanel / Amplitude):** Implement custom tracking for core business events:
  - `User Signed Up`
  - `Added Item to Cart` (include product ID and price).
  - `Completed Checkout` (include total value for ROI tracking).
- [ ] **Error Monitoring Integration:** Ensure Sentry (or equivalent) environment is set to `production` so errors are caught silently.

## 3. Marketing Readiness
- [ ] **Favicon:** Ensure the browser tab icon is updated to the client's logo.
- [ ] **404 Page:** Create a custom, branded 404 Error page that redirects users back to the home page or catalog.
- [ ] **Email Delivery (SendGrid/Resend):** Verify production domains so transactional emails (e.g., "Order Confirmed") do not go to the customer's Spam folder.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 GTM & analytics decisions and wait for the human lead's explicit approval before closing Phase 7.)*

* **Key Decision 1 (SEO & Crawlability):** `[Verified meta tags, OG images, sitemap.xml, and production robots.txt]`
* **Key Decision 2 (Conversion Telemetry):** `[Confirmed GA4/PostHog/Mixpanel funnel events and Sentry error monitoring]`
* **Key Decision 3 (Domain & Deliverability):** `[Verified SPF/DKIM/DMARC records for transactional email delivery]`

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
- [ ] 11_go_to_market_analytics.md

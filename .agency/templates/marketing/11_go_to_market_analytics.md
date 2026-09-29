---
template_id: "11"
phase: 7
assigned_role: "10_legal_operations_officer"
context_from: ["01_proposal_sow.md"]
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

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 11_go_to_market_analytics.md

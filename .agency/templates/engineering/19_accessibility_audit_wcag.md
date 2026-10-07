---
template_id: "19"
phase: 5
assigned_role: "product_design/ui_ux_designer"
context_from: ["product_design/10_ui_ux_handoff.md"]
outputs_to: ["engineering/06_testing_uat_signoff.md"]
status: template
---
# Template 19: Accessibility (a11y) Audit Checklist

**Purpose:** Ensuring the application is usable by people with disabilities. Failure to meet basic accessibility standards (WCAG 2.1 AA) can result in lawsuits for your clients, especially in the US and Europe.

---

## 1. Visual Accessibility
- [ ] **Color Contrast:** All text has a minimum contrast ratio of 4.5:1 against its background. (Use tools like WebAIM Contrast Checker).
- [ ] **No Color-Only Indicators:** Error states (like a wrong password) do not rely solely on turning the text red. They must also include an icon or text like "Error:".
- [ ] **Focus States:** Every interactive element (button, link, input) has a clear, highly visible focus ring when navigated via keyboard.

## 2. Screen Reader Compatibility
- [ ] **Semantic HTML:** The layout uses proper structural tags (`<header>`, `<nav>`, `<main>`, `<article>`) rather than just `<div>` soup.
- [ ] **ARIA Labels:** Buttons without text (e.g., a magnifying glass icon for search) have an `aria-label="Search"`.
- [ ] **Image Alt Text:** All informative images have descriptive `alt` text. Decorative images (like a background pattern) have empty `alt=""` attributes so screen readers ignore them.

## 3. Keyboard Navigation
- [ ] **Tab Order:** The user can navigate through the entire shopping flow (Add to Cart -> Checkout) using *only* the `Tab` and `Enter` keys.
- [ ] **Skip Links:** A visually hidden "Skip to main content" link is available for keyboard users to bypass long navigation menus.

## 4. Tooling Integration
- [ ] Install `eslint-plugin-jsx-a11y` in the Next.js project to catch accessibility errors during development.
- [ ] Run Lighthouse Accessibility Audits during the CI/CD pipeline and block deployment if the score drops below 90.

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Note 1: e.g., Verified WCAG 2.1 AA contrast and keyboard navigation across checkout flows.]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] `engineering/19_accessibility_audit_wcag.md`

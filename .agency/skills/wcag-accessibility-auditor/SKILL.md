---
name: wcag-accessibility-auditor
description: "Audits web applications for WCAG 2.1 AA compliance, keyboard navigation, color contrast, and ARIA screen reader attributes."
---

# WCAG 2.1 AA Accessibility Auditor Skill

## Trigger
Use in Phase 4/5 or when completing `19_accessibility_audit_wcag.md`.

---

## Instructions

1. **Color Contrast Verification:**
   - Standard text: Minimum contrast ratio of **4.5:1** against its background.
   - Large text (18pt+ or bold 14pt+): Minimum ratio of **3:1**.
   - Interactive UI elements (buttons, border inputs): Minimum ratio of **3:1**.
2. **Keyboard Navigation & Focus Management:**
   - Every interactive element (button, link, modal, dropdown) must be reachable via `Tab` and triggerable via `Enter` or `Space`.
   - Never suppress outline styling with `outline: none` without providing a custom `:focus-visible` ring (e.g. `focus-visible:ring-2 focus-visible:ring-offset-2`).
   - Modals and drawers must trap focus and close on `Escape`.
3. **Semantic HTML & Screen Reader ARIA:**
   - Non-text content (images, icons) must have meaningful `alt` text or `aria-label` (or `aria-hidden="true"` if purely decorative).
   - Form inputs must have explicit `<label htmlFor="...">` associations.
   - Custom toggle buttons must use `role="switch"` and `aria-checked="true/false"`.
4. **Generate Output:**
   Populate `.agency/active/19_accessibility_audit_wcag.md` with audit score and code fixes for any violations.

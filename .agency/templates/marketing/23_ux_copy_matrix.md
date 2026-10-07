---
template_id: "23"
phase: 4
assigned_role: "marketing/copywriter"
context_from: ["product_design/03_requirements_engineering.md", "product_design/10_ui_ux_handoff.md"]
outputs_to: ["engineering/05_technical_sdlc_execution.md"]
status: template
---
# Template 23: UX Copy & Content Matrix

**Purpose:** To define brand voice, microcopy inventory, call-to-action (CTA) button variants, empty states, error messages, and onboarding tooltips to ensure an intuitive and delightful user interface.

---

## 1. Brand Voice & Tone Spectrum
Define the core personality traits of the interface copy:
- **Tone Vector:** `[Confident, Clear, Empathetic, Technical / Conversational]`
- **Writing Rules:**
  - Active voice over passive voice (`"Save changes"` vs `"Changes will be saved"`).
  - Front-load important keywords in notifications and labels.
  - Plain language over technical jargon (unless writing for specialized developer tools).
  - Sentence case for buttons and navigation items.

## 2. Microcopy Matrix: Navigation & Primary Actions

| Component Key | Element Type | Default Text | Hover / Secondary Text | Context / Route |
| :--- | :--- | :--- | :--- | :--- |
| `nav_dashboard` | Navigation Link | Dashboard | View your metrics overview | Global Header |
| `btn_primary_cta` | Primary Button | Get Started Free | No credit card required | Landing Hero |
| `btn_save_settings`| Action Button | Save Changes | Saving... / Saved! | Settings Panel |
| `btn_export_csv` | Action Button | Export to CSV | Downloads raw data | Reports Table |

## 3. Empty States & First-Time User Experience (FTUX)

| Screen / View | Illustration Key | Empty State Headline | Body Copy / Value Prop | Action Button CTA |
| :--- | :--- | :--- | :--- | :--- |
| **No Projects** | `ill_empty_folder` | No projects yet | Create your first project to start tracking deliverables. | Create Project |
| **No Invoices** | `ill_empty_wallet` | Clean slate! | Your generated invoices will appear here once billed. | New Invoice |
| **No Activity** | `ill_empty_clock` | Quiet for now | Team commits and updates will stream here automatically. | Invite Team Member |

## 4. Error Messages & Recovery Actions

| Error Code / Scenario | Technical Error | User-Facing Message | Clear Recovery Action |
| :--- | :--- | :--- | :--- |
| `AUTH_INVALID_CRED` | `401 Unauthorized` | Incorrect email or password. | Double-check your credentials or click "Forgot Password". |
| `RATE_LIMIT_EXCEEDED` | `429 Too Many Requests` | You're moving fast! Please wait a moment. | Retry in 30 seconds or upgrade your API plan. |
| `NETWORK_TIMEOUT` | `504 Gateway Timeout` | Connection timed out. | Check your internet connection and refresh the page. |

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (Brand Tone):** `[Approved voice and tone parameters]`
* **Key Decision 2 (Primary CTAs):** `[Core conversion button wording across funnel]`
* **Key Decision 3 (Error Handling Copy):** `[User-friendly error recovery messages]`

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
- [ ] Microcopy keys mapped directly to i18n / localization dictionary.
- [ ] Error messages provide clear, actionable recovery paths.
- [ ] No placeholder text (`[Lorem Ipsum]`, `[TBD]`) remains in the matrix.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `marketing/23_ux_copy_matrix.md`
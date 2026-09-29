---
template_id: "10"
phase: 3
assigned_role: "03_ui_ux_designer"
context_from: ["03_requirements_engineering.md"]
outputs_to: ["05_technical_sdlc_execution.md"]
status: template
---
# Template 10: UI/UX Design Handoff Protocol

**Purpose:** A smooth transition from the Design phase (Figma) to the Engineering phase without losing visual fidelity or confusing developers.

---

## 1. Design System & Global Tokens
Before developers write a single CSS class, the following must be documented in the design file:
- [ ] **Color Palette:** Hex codes defined for Primary, Secondary, Success, Warning, Error, and Backgrounds.
- [ ] **Typography Scale:** Font families, weights, line-heights, and base sizes (e.g., H1, H2, Body, Caption).
- [ ] **Spacing System:** Padding and margin multiples (e.g., 4px, 8px, 16px, 24px).
- [ ] *Action:* Developers translate these directly into `tailwind.config.ts` or CSS variables.

## 2. Component States
Every interactive element in the design must account for user interactions. Designers must provide:
- [ ] **Buttons:** Default, Hover, Active/Pressed, Disabled, and Loading states.
- [ ] **Input Fields:** Default, Focused, Populated, Error, and Disabled states.
- [ ] **Empty States:** What does the Shopping Cart look like when it has 0 items? What does the Dashboard look like for a new user?

## 3. Responsive Breakpoints
Developers cannot guess how a desktop design looks on a phone.
- [ ] Mobile Layout (< 768px)
- [ ] Tablet Layout (768px - 1024px)
- [ ] Desktop Layout (> 1024px)

## 4. Asset Export
- [ ] All icons exported as pure SVGs (optimized).
- [ ] Complex graphics exported as WebP or highly compressed PNGs.
- [ ] A dedicated folder or cloud link containing all required marketing assets.

## 5. The Handoff Meeting
- Conduct a 30-minute sync where the Designer walks the Lead Engineer through the Figma prototype, explaining any complex animations, sticky headers, or transitions.


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 10_ui_ux_handoff.md

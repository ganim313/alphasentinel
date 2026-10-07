---
name: senior-designer-ui
description: "A persona-based skill that forces the coding agent to apply high-end, premium UI/UX principles (inspired by Owl-Listener designer skills) instead of default "developer design"."
---

# Senior Designer UI Skill

## Trigger
Attach this skill whenever generating or refactoring frontend code in Phase 4 (Implementation).

## Instructions
When writing frontend components (React, HTML/CSS, Tailwind), you must abandon default browser stylings and strictly adhere to the following premium design principles:

### 1. Typography Hierarchy
- Never use default font sizes. Establish a clear scale (e.g., 12px, 14px, 16px, 20px, 24px, 32px).
- Headlines must have tight tracking (letter-spacing: -0.02em to -0.04em) and tight line-height (1.1 to 1.2).
- Body text must be highly legible (line-height: 1.5 to 1.7) with softer contrast (e.g., text-gray-600 instead of pure black).

### 2. Spacing & Whitespace (The 8pt Grid)
- Every margin and padding MUST be a multiple of 8px (or 4px for micro-adjustments).
- Elements that belong together must be grouped tightly (e.g., 8px apart), while separate conceptual groups need generous whitespace (e.g., 32px or 48px apart).

### 3. Depth & Borders
- Avoid harsh, 1px solid black borders. Use subtle borders (e.g., `border-gray-200` or `border-white/10` in dark mode).
- Use soft, multi-layered box-shadows for elevation, not harsh drop-shadows.

### 4. Interactive States
- Every clickable element MUST have a defined `:hover`, `:focus-visible`, and `:active` state.
- Include micro-interactions (e.g., `transition-all duration-200 ease-in-out`).

**Action**: Review the component you just built and refactor it to meet these 4 rules before returning it to the user.

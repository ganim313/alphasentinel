---
name: session-resumer
description: Instantly reads the active project state and deliverables to catch up a fresh AI chat on where the project left off and identify the exact next action.
---

# Session Resumer & Context Loader Skill

## Trigger
Use this skill whenever you open a new chat window, switch AI platforms, or resume work on an existing project after a break.

---

## Instructions

1. **Read Project State:** Read `.agency/active/project_state.yml` to extract:
   - Project Name & Client Name
   - `current_phase` and its status (`pending`, `in_progress`, `completed`)
   - `assigned_role` for the active phase
2. **Scan Active Artifacts:** Check what files exist in `.agency/active/` (e.g. `01_proposal_sow.md`, `03_requirements_engineering.md`, `04_system_design_architecture.md`).
3. **Assess Recent Work:** Read the last generated deliverable to understand the latest technical decisions made.
4. **Generate Executive Briefing:** Output a clean 4-point summary in the chat:

---

## Output Format

### 🚀 Project Context Briefing
* **Project:** `[Project Name]` | **Client:** `[Client Name]`
* **Current Phase:** Phase `[X]` — `[Phase Name]`
* **Status:** `[🟢 In Progress / 🟡 Blocked / 🔵 Ready for Next Phase]`
* **Last Completed Deliverable:** `[e.g. 03_requirements_engineering.md (PRD Signed Off)]`

### 📋 Immediate Next Step
* **Role to Assume:** `@.agency/agents/[department]/[assigned_role].md`
* **Action Required:** `[One-sentence description of the exact next deliverable to produce or code to write]`
* **Suggested Command to Run:**
  > `"[Exact prompt you can copy-paste to continue immediately]"`

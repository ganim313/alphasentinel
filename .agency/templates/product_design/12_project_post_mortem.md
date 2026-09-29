---
template_id: "12"
phase: 8
assigned_role: "10_legal_operations_officer"
context_from: ["16_final_handoff_release.md"]
outputs_to: []
status: template
---
# Template 12: Project Post-Mortem (Retrospective)

**Purpose:** An internal agency meeting held 1-2 weeks after launching a project. The goal is to reflect on what happened and improve operations for the next client. Blame is forbidden; the focus is entirely on process improvement.

---

## 1. Meeting Setup
* **Attendees:** All engineers, designers, and project managers who touched the project. (Do not invite the client).
* **Duration:** 45 - 60 minutes.
* **Format:** Everyone adds sticky notes to a virtual board (Miro, FigJam) before the meeting begins.

## 2. The Core Discussion (Start, Stop, Continue)

### What Went Well? (Continue doing this)
* Identify processes, tools, or communication methods that made the project successful.
* *Example:* "Using Supabase saved us 40 hours of backend setup. We should use it for the next project."

### What Went Wrong? (Stop doing this)
* Identify bottlenecks, scope creep incidents, or technical failures.
* *Example:* "We started coding before the client approved the final Figma designs, which led to a massive UI rewrite in Week 3."

### What Can We Improve? (Start doing this)
* Actionable steps to fix the things that went wrong.
* *Example:* "Next time, we will enforce the PRD and UI Sign-Off templates strictly before allocating developers."

## 3. Business & Profitability Review
* **Estimated vs. Actual Hours:** Did we estimate 100 hours but actually work 250 hours? If so, why were we off?
* **Profit Margin:** Was this project profitable based on our fixed-price contract? If not, we need to raise our prices or improve estimation accuracy.

## 4. Action Items
* Assign specific tasks based on the "Start doing this" discussion.
* *Example:* "Ahmed will update our standard `package.json` boilerplate to include better ESLint rules before the next project begins."


---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 12_project_post_mortem.md

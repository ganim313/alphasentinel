---
name: client-update-generator
description: Translates technical git commits and task completions into a polished, non-technical weekly update email for the client.
---

# Client Update Generator Skill

## Trigger
Use this skill weekly during active development (Phases 4-6) to maintain client communication.

## Instructions
1. **Gather Data**: 
   - Read the git commit history for the past week (run `git log --since="1 week ago" --oneline`).
   - Review `.agency/active/project_state.yml` for current phase progress.
   - Check `.agency/active/05_technical_sdlc_execution.md` for sprint goal.
2. **Assess Status**: Before writing, determine one of three statuses:
   - 🟢 **On Track**: All sprint goals met or ahead of schedule.
   - 🟡 **At Risk**: Slightly behind but recoverable without client action.
   - 🔴 **Blocked**: Client action is required to unblock progress.
3. **Translate to Business Value**: Never use technical jargon. Always translate:
   - BAD: "Refactored auth middleware to use JWT RS256 rotation."
   - GOOD: "Significantly hardened the platform's security against unauthorized access."
4. **Generate TWO outputs**:

   **A. Client Email (External):** Professional, reassuring, and concise.
   - Subject line: `[Project Name] — Weekly Progress Update, [Date]`
   - Status badge (🟢 On Track / 🟡 At Risk / 🔴 Blocked)
   - The TL;DR: 1-2 sentences on overall status.
   - What We Completed This Week (3-5 translated bullets).
   - What We Are Doing Next Week (2-3 bullets).
   - Blockers/Needs — only include if 🔴 Blocked. Be specific and action-oriented.

   **B. Internal Memo (For your own records):** Technical, honest, blunt.
   - Actual tickets completed with raw commit hashes.
   - True sprint velocity vs. estimate.
   - Internal blockers and their root cause.


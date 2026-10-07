---
name: continuous-learner
description: "Analyzes recently solved problems, bug fixes, or architecture decisions and updates the agency's skills and templates so future projects automatically get smarter."
---

# Continuous Self-Learner Skill (Hermes Protocol)

## Purpose
This skill gives your AI engineering team **persistent procedural memory**. Whenever you solve a complex bug, handle an unexpected client situation, or discover an optimization, this skill extracts the lesson and permanently upgrades your `.agency/skills/` or `.agency/templates/`.

---

## When to Run
- Immediately after fixing a difficult production bug or race condition.
- After discovering a subtle flaw during an architecture review.
- After completing a project Post-Mortem (`12_project_post_mortem.md`).
- When you want the AI to remember a personal preference or engineering pattern.

---

## Instructions

1. **Extract the Core Pattern:** Identify the root cause, the exact fix applied, and the generalized engineering rule (e.g., *"When using Prisma with Supabase Connection Pooling, PgBouncer requires `?pgbouncer=true` in the connection string"*).
2. **Identify the Target Skill or Role:** Determine which file in `.agency/` should permanently store this rule:
   - Security flaws $\rightarrow$ `.agency/skills/strix-security-auditor.md` or `.agency/agents/engineering/security_auditor.md`
   - Crash bugs $\rightarrow$ `.agency/skills/crash-debugger.md`
   - Database / ORM issues $\rightarrow$ `.agency/agents/engineering/database_engineer.md`
   - PRD / Scope issues $\rightarrow$ `.agency/skills/prd-discovery-agent.md`
3. **Apply Additive Knowledge Update:** Inject the new rule under a dedicated `### Learned Engineering Rules & Edge Cases` section in the target file.
4. **Report Upgrade:** Output a clean 3-bullet summary:
   * **Pattern Learned:** `[One-sentence rule]`
   * **File Upgraded:** `[Link to modified skill/agent file]`
   * **Future Impact:** `[How future projects will automatically avoid this problem]`

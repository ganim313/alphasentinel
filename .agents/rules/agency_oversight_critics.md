---
trigger: model_decision
description: "Activate when performing adversarial red-team audits, pre-merge code integrity reviews, placeholder checks, or phase gate sign-off verifications."
---
# Agency Department Charter: Oversight

When working in this domain, summon or embody the corresponding `.agency/agents/` specialist:

- **`@oversight/master_critic`** (`.agency/agents/oversight/master_critic.md` — ID `24`): System-wide Principal Adversarial Auditor that red-teams all deliverables and code before persistence to prevent hallucinations, scope traps, and logic flaws.
- **`@oversight/code_integrity_guardian`** (`.agency/agents/oversight/code_integrity_guardian.md` — ID `25`): Principal Codebase Protector that audits proposed source diffs via Ripwire and Laya to prevent destructive overwrites, lazy truncation, and regressions.

## Operational Directives
1. Use `python .agency/scripts/ripwire_engine.py --recall "<query>"` for zero-bloat context lookup.
2. Score completed deliverables via `python .agency/scripts/laya_engine.py --score-deliverable <path>`.
3. Never emit `[TBD]` or `[TODO]` placeholders; always include the `## ✍️ Human Lead Decision & Sign-Off Block`.

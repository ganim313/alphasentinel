---
name: prd-discovery-agent
description: "Transforms vague client ideas or rough personal product concepts into a complete, detailed PRD through a structured Socratic interview with the AI."
---

# PRD Discovery Agent Skill

## Trigger
Use this skill when:
- A client says something like "I want an app like X" or "I want to automate my business."
- You have a rough product idea in your head and want to turn it into a buildable spec.
- The `.agency/active/03_requirements_engineering.md` does not exist yet or is incomplete.

## CRITICAL RULE
You are acting as a **Principal Product Manager at a top-tier software consultancy**. Your job is NOT to write what the user says — your job is to **extract what they actually need** by challenging assumptions, uncovering hidden requirements, and discovering edge cases they haven't thought of yet.

Do NOT attempt to write the PRD until you have completed ALL interview phases below. Ask one question at a time. Wait for the answer before proceeding.

---

## Phase 1: Business Context Interview (Run First)
Ask these questions one at a time. Do not skip any.

1. "In one sentence, what problem does this product solve — and for whom?"
2. "Who is the **paying customer** in this system? Is it the same person as the end user, or are they different?"
3. "How does your target user solve this problem today without your product? What is their current workaround?"
4. "Name 2-3 direct competitors or similar products. What is the single reason someone would choose your product over theirs?"
5. "What does success look like exactly 6 months after launch? Give me a specific metric."
6. "What is the absolute minimum version of this product that would be useful? (The MVP, not the dream version.)"

---

## Phase 2: Feature Deep-Dive (Run After Phase 1)
For each feature the user mentioned in Phase 1:

1. "Walk me through the exact step-by-step flow a user would take to use `[Feature X]`. Start from the moment they open the app."
2. "What should happen if `[Feature X]` fails or the user makes a mistake?"
3. "Who has permission to access `[Feature X]`? Is it all users, or only specific roles (Admin, Premium, etc.)?"
4. "Is there any data that `[Feature X]` must NOT expose to certain users?"

---

## Phase 3: Technical Constraints (Run After Phase 2)
1. "Do you have any existing infrastructure we must integrate with? (e.g., existing database, existing auth system, third-party APIs)"
2. "Are there any regulatory requirements? (e.g., GDPR, HIPAA, data residency)"
3. "What is your expected user volume at launch vs. at scale? (e.g., 100 users → 10,000 users)"
4. "What is the hard deadline for the MVP?"

---

## PRD Generation (Run Only After All Phases Are Complete)
Once all questions have been answered:
1. Synthesize all answers into a complete, detailed PRD using `.agency/templates/03_requirements_engineering.md`.
2. Fill in every section exhaustively. Do NOT leave any placeholder text.
3. Save to `.agency/active/03_requirements_engineering.md`.
4. Present a summary of the key decisions and any assumptions made, and ask the user to confirm them before the PRD is considered final.

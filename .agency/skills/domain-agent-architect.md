---
name: domain-agent-architect
description: "Conducts a /grill-me one-question-at-a-time Socratic discovery interview (after scanning any Intake/PRD docs) to identify a project's domain nature and permanently materialize native project-specific domain specialist agents, Antigravity 2.0 rules, skills, Laya routing, and 7-Phase critic gates."
---

# 🎯 Domain Agent Architect (`/grill-me` Dynamic Project Specialist Generator)

## Trigger
Activate this skill automatically when:
1. A new project workspace is initialized (`domain_discovery_completed: false` in `.agency/active/project_state.yml` or `.agency/active/domain_agents/` is empty).
2. The user starts Phase 1 (Discovery/Intake) or Phase 2 (PRD) on a project and needs dedicated **non-development domain specialists** (e.g., *Syllabus Designer & Exam Strategist* for an exam preparation dashboard; *Quant Researcher, Market Microstructure & Risk Strategist* for a trading platform; *Vertical Workflow & SaaS Pricing Strategist* for a B2B SaaS product).
3. The user invokes `/grill-me` to design or refine the project's custom domain agent roster.

---

## Core Principle: Zero Central Pollution + Full Per-Project Native Permanence
- **Never** write project-specific domain agents into the central `.agency/agents/` folder (which houses the 25 core Software & Growth Agency development agents).
- Instead, interview the user `/grill-me` style and materialize **permanent native domain agents** inside the project's isolated `.agency/active/domain_agents/`, `.agents/rules/agency_project_domain.md`, `.agents/skills/`, and `.agency/active/project_state.yml`.

---

## Step-by-Step `/grill-me` Execution Protocol

### Step 1: Scan Existing Project Context First (Do Not Ask What Is Already Known)
Run the context scanner to inspect `.agency/active/project_state.yml`, `13_client_intake_questionnaire.md`, and `03_requirements_engineering.md`:
```bash
python .agency/scripts/domain_forge.py --scan
python .agency/scripts/domain_forge.py --grill-questions --description "<known project summary>"
```

### Step 2: Walk the Decision Tree One Question at a Time (`ask_question`)
Following the `/grill-me` protocol, use the `ask_question` tool **one question at a time**, always placing your `(Recommended)` option first:

1. **Question 1 — Domain Nature & Non-Dev Specialist Roster:**
   - Propose the exact `3–4` non-development Domain Specialist roles tailored to the project's domain (e.g., Syllabus/Curriculum Architect, Exam Pattern Strategist, Psychometric IRT Assessment Designer for EdTech; Quant Researcher, Market Microstructure Specialist, Portfolio Risk Strategist for Trading; Vertical Workflow Strategist, SaaS Pricing Economist, Customer Activation Architect for SaaS).
2. **Question 2 — Adversarial Domain Critic & Red-Lines:**
   - Propose the project's dedicated **Domain Adversarial Critic** (e.g., *Subject-Matter & Pedagogy Critic*, *Quant Overfitting & Regulatory Compliance Critic*, *Domain Logic & Tenant Isolation Critic*) and ask which domain failure modes it must block before any phase advances.
3. **Question 3 — Co-Ownership & Final Confirmation:**
   - Present the final roster and their co-owned deliverables across Phases 1–7 for explicit user approval.

### Step 3: Materialize the Native Permanent Agents
Once the user approves the roster in the `/grill-me` interview:
1. Save the confirmed specification to `.agency/active/domain_spec.json` (or pass `--description` / `--domain`).
2. Run the deterministic generator:
   ```bash
   python agency.py forge-domain --spec .agency/active/domain_spec.json
   ```
   *(Or `python .agency/scripts/domain_forge.py --spec .agency/active/domain_spec.json`)*
3. Verify that the following files are permanently created in the project workspace:
   - `.agency/active/domain_agents/<role_slug>.md` (`>= 45` lines each, with YAML frontmatter and Layer 0/1 commands)
   - `.agents/rules/agency_project_domain.md` (`trigger: model_decision`, `< 12,000` chars)
   - `.agents/skills/domain-<domain_slug>/SKILL.md`
   - `.agency/active/project_state.yml` (`domain_discovery_completed: true`, `domain_co_owners`, and `domain_critic`)
4. Test routing a domain query through Laya Layer 1:
   ```bash
   python agency.py route "<domain-specific task for this project>"
   ```

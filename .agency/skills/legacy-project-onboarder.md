---
name: Legacy Project Onboarder
description: Reverse-engineers an existing or mid-flight codebase to automatically generate the missing agency documentation (PRD, Architecture, Runbooks).
---

# Legacy Project Onboarder Skill

## Trigger
Use this skill when you copy the `.agency/` folder into a project that is already partially or fully built, and you need to generate the formal documentation retroactively.

## Instructions
**CRITICAL RULE**: Do NOT write shallow summaries. You are acting as a Staff-Level Technical Product Manager and Enterprise Architect. Your output must be exhaustively detailed, industry-standard, and highly technical. 

1. **Analyze Codebase**: Deeply scan the existing source code, package.json/requirements.txt, database schemas, and API routes. (If the codebase is massive, ask the user to run the `repowise-codebase-mapper` skill first).
2. **Reverse-Engineer the PRD (Phase 2)**: 
   - **DO NOT Summarize.** Write a highly detailed `03_requirements_engineering.md`.
   - List EVERY individual feature, EVERY user flow, EVERY user role (Admin, User, etc.), and exactly what they can do.
   - Include edge cases, validation logic found in the code, and specific business rules.
3. **Reverse-Engineer the Architecture (Phase 3)**:
   - **DO NOT just list the tech stack.** You must write a comprehensive `04_system_design_architecture.md`.
   - **Data Models:** Extract every single database table, every column, foreign key, and data type.
   - **API Layer:** Document all API endpoints, controllers, and authentication flows.
   - **Mermaid Diagrams:** You MUST generate a complex Mermaid.js Entity-Relationship Diagram (ERD) mapping every table, AND a Sequence Diagram showing the most complex user flow (e.g., checkout or auth).
4. **Generate Deployment Runbook (Phase 6)**:
   - Write `07_deployment_runbook.md` detailing exact infrastructure needs, environment variables required, Docker build steps, and hosting configuration.
5. **State Update**: Once generated, instruct the user to update `project_state.yml` to the current phase (e.g., Phase 4 or 7).

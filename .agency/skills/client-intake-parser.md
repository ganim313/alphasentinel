---
name: client-intake-parser
description: Extracts client requirements from raw meeting transcripts or emails and populates the formal Intake Questionnaire.
---

# Client Intake Parser Skill

## Trigger
Use this skill when the user provides raw, unstructured client context (e.g., meeting transcripts, email threads, Slack exports) and requests to start the project intake phase.

## Instructions
1. **Analyze Context**: Read the provided raw text thoroughly. Do not rush — read every line carefully.
2. **Extract Entities**: Identify and map the following. If any cannot be found, explicitly mark as `[NEEDS CLARIFICATION]`:
   - Client name, company, and industry
   - Core business problem being solved
   - Desired features and user types
   - Hard budget ceiling (never assume)
   - Hard deadline (never assume)
   - Technical preferences or existing infrastructure (e.g., "we already use AWS")
3. **Risk Assessment**: After extraction, assess the project's risk level and write a short **Risk Register** at the top of the output document:

   | Risk Factor | Severity | Mitigation |
   | :--- | :--- | :--- |
   | `[e.g., Vague scope]` | `High/Medium/Low` | `[Suggested action]` |

4. **Map to Template**: Populate `.agency/templates/13_client_intake_questionnaire.md` with extracted data.
5. **Output**: Save to `.agency/active/13_client_intake_questionnaire.md`.
6. **Mandatory Follow-up**: Present the user with:
   - A list of all `[NEEDS CLARIFICATION]` items as a ready-to-send follow-up question email draft.
   - The Risk Register summary.


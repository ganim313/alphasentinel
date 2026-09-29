---
name: SkillUI Generator
description: Uses the open-source SkillUI tool to reverse-engineer a target website's design system into a usable skill file for your agents.
---

# SkillUI Generator Skill

## Trigger
Use this skill during Phase 3 (Architecture) or Phase 4 (Implementation) when the client requests a UI that looks like an existing website (e.g., "Make it look like Stripe" or "Copy the vibe of Vercel").

## Instructions
1. **Tool Execution**: Run the SkillUI CLI tool against the user-provided target URL. 
   - Execute: `npx skillui [TARGET_URL]`
   - *Note: If the command requires specific flags based on current SkillUI docs, apply them.*
2. **Process Output**: The tool will generate a `.skill` file containing the extracted design tokens (colors, typography, spacing, border-radii).
3. **Integration**: Move the generated `.skill` file into the `.agency/skills/` directory.
4. **Activation**: Instruct the developer agent (e.g., Cursor) to read the new `.skill` file. Tell the agent: "Apply these design tokens to all frontend components built moving forward."
5. **Validation**: Generate a quick dummy component (like a Button or Card) to verify the extracted tokens match the target website's aesthetic.

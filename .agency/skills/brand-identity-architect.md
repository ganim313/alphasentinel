---
name: Brand Identity Architect
description: Generates a comprehensive brand strategy (voice, positioning, messaging) for clients who lack a brand identity (inspired by arnabbagxd Brand-building-skills).
---

# Brand Identity Architect Skill

## Trigger
Use this skill during Phase 1 (Intake) or Phase 2 (Requirements) if the client does not have established brand guidelines.

## Instructions
1. **Analyze Input**: Read the `.agency/active/13_client_intake_questionnaire.md` to understand the client's industry, target audience, and core product.
2. **Generate Positioning**: Write a 2-sentence Positioning Statement. (e.g., "For [Target Audience] who [Need], [Product] is a [Category] that provides [Key Benefit]. Unlike [Alternative], we [Unique Differentiator].")
3. **Define Brand Voice**: 
   - Select 3 adjectives that describe the brand's personality (e.g., "Authoritative, Approachable, Witty").
   - Provide a "Do say / Don't say" table with 5 examples of copy.
4. **Messaging Matrix**: 
   - Define the Core Value Proposition.
   - List 3 Supporting Pillars (Features/Benefits) and a 1-sentence elevator pitch for each.
5. **Output**: Create a new markdown file `.agency/active/brand_guidelines.md` and populate it with this data. Instruct downstream agents (like the PRD writer or UI designer) to read this file to ensure tone and aesthetics match the brand.

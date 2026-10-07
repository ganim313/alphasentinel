---
name: architecture-diagrammer
description: "Generates system architecture, Entity-Relationship, and Sequence diagrams from a Product Requirements Document (PRD)."
---

# Architecture Diagrammer Skill

## Trigger
Use this skill during Phase 3 (Architecture) when generating the System Design document.

## Instructions
1. **Read PRD**: Thoroughly analyze `.agency/active/03_requirements_engineering.md`.
2. **Identify Entities**: Extract ALL data models mentioned or implied in the PRD. You must act as a Staff-Level Database Architect. Do not skip any entities.
3. **Generate ERD**: Write an EXHAUSTIVE Mermaid.js Entity-Relationship Diagram (`erDiagram`). You MUST include every single table, every column, and strict data types (`string`, `int`, `uuid`). Do not summarize or provide a "high-level" overview.
4. **Identify Flows**: Extract the primary user journeys.
5. **Generate Sequence Diagrams**: Write highly detailed Mermaid.js Sequence Diagrams (`sequenceDiagram`) for the 2-3 most critical user flows. You MUST include authentication checks, database interactions, and third-party API calls in the sequence.
6. **Draft Architecture**: Populate `.agency/templates/04_system_design_architecture.md` with these diagrams and save to `.agency/active/04_system_design_architecture.md`. Ensure Mermaid blocks are enclosed in ````mermaid ... ```` markdown codeblocks.

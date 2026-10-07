---
name: repowise-codebase-mapper
description: Uses the RepoWise tool to index and map massive legacy codebases so AI agents can understand them without blowing up their context window.
---

# RepoWise Codebase Mapper Skill

## Trigger
Use this skill at the very beginning of Phase 4 (Implementation) ONLY IF you are taking over a large, existing client codebase. Do not use for greenfield (from scratch) projects.

## Instructions
1. **Tool Execution**: Run the RepoWise CLI tool to index the repository.
   - Execute: `npx repowise init` (or current equivalent command based on docs).
2. **Map Generation**: RepoWise will generate an intelligence map of the codebase (typically creating a `.repowise` folder or similar index).
3. **Agent Integration**: Instruct the active coding agent (Cursor/Antigravity) to query the RepoWise index whenever searching for logic. 
   - *Example Prompt*: "Before writing the new auth feature, use RepoWise to find all existing instances of JWT token validation in the codebase."
4. **Dependency Auditing**: Ask RepoWise to output a summary of the most complex/tangled dependencies in the repository so the user knows where the "danger zones" are before starting work.

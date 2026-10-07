# Agency Playbook Operating System (Antigravity 2.0 + Ripwire L0 + Laya L1)

This workspace is governed by the **Agency Playbook Multi-Agent Operating System** (`.agency/`).

## 3-Layer Intelligence Hierarchy
1. **Layer 0 — Ripwire Structural & Doc Graph (`ripwire_engine.py` / `ripwire` MCP):**
   - Run `python .agency/scripts/ripwire_engine.py --recall "<query>"` before reading full files.
   - Use `--pack-task "<task>" --partition=3` and `--plan-lanes=3` before spawning parallel pods.
   - Run `--merge-scout` and `--doc-drift` prior to phase advancement.
2. **Layer 1 — Laya System-1 Typed Decision Engine (`laya_engine.py` / `laya` MCP):**
   - Route incoming user requests via `python .agency/scripts/laya_engine.py --route "<task>"`.
   - Score deliverables against the 4-dimension agency rubric (`--score-deliverable <file>`).
   - Classify client scope requests via `--classify-scope "<request>"`.
   - Screen code for lazy placeholders via `--screen-code <path>`.
3. **Layer 2 — System-2 Department Agents & Critics (`.agency/agents/`):**
   - 25 specialized role charters across 6 departments (`product_design`, `engineering`, `data_ai`, `marketing`, `finance_ops`, `sales_client`) + `oversight` (`master_critic.md`, `code_integrity_guardian.md`).

## 3-Tier Task Routing Protocol
- **Tier 1 (Micro-Task / Bug / Hotfix):** Direct surgical edit or Scenario B (`urgent_bugfix` runbook). Zero ceremony.
- **Tier 2 (Feature Addition / Change Order):** Scenario C (`feature_addition`). Update `32_scope_creep_log.md` / `14_change_order_form.md`, implement, and verify with `@oversight/code_integrity_guardian`.
- **Tier 3 (Full System Build / Enterprise Rescue):** Full 7-Phase SDLC tracked in `.agency/active/project_state.yml`.

## Mandatory Quality & Governance Rules
- **Zero Placeholders:** Never leave `[TBD]`, `[TODO]`, `[Insert ...]`, or `// ... rest of code` in any deliverable or source file.
- **Human Lead Sign-Off Gate:** Every deliverable in `.agency/active/` must contain a completed `## ✍️ Human Lead Decision & Sign-Off Block` before running `python agency.py validate --advance`.
- **Zero-Copy Isolation:** Shared intelligence lives in `.agency/{agents,skills,templates,runbooks,scripts}`; project-specific state lives strictly in `.agency/active/`.

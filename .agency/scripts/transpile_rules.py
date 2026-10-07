#!/usr/bin/env python3
"""
Multi-IDE & Antigravity 2.0 Native Plugin Transpiler (.agency/scripts/transpile_rules.py)
========================================================================================
Dynamically compiles canonical `.agency/` agents (25), skills (20), templates (33),
and Layer 0 (Ripwire) + Layer 1 (Laya) intelligence configurations into:
  - Antigravity 2.0 (`--target antigravity`):
      * `.agents/plugins/agency-playbook/plugin.json`
      * `.agents/plugins/agency-playbook/mcp_config.json`
      * `.agents/plugins/agency-playbook/hooks.json`
      * `.agents/plugins/agency-playbook/rules/AGENTS.md` (<4KB, no YAML frontmatter)
      * `.agents/plugins/agency-playbook/skills/<skill-name>/SKILL.md`
      * `.agents/rules/agency_*.md` (scoped `trigger: model_decision` department rules)
      * `.agents/plugins.json`, `.agents/skills.json`, `.agents/hooks.json`
      * `.ignore` and `.cursorignore` with `!.agency/` negation
  - Cursor (`--target cursor`): `.cursor/rules/agency_*.mdc`
  - Claude Code (`--target claude`): `CLAUDE.md`
  - Windsurf (`--target windsurf`): `.windsurfrules`
  - Aider (`--target aider`): `CONVENTIONS.md`

Usage:
    python .agency/scripts/transpile_rules.py --target all
    python .agency/scripts/transpile_rules.py --target antigravity
    python .agency/scripts/transpile_rules.py --clean
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
AGENCY_DIR = SCRIPT_DIR.parent
ROOT_DIR = AGENCY_DIR.parent

RULE_FILES = [
    "agency_engineering.md",
    "agency_product_design.md",
    "agency_data_ai.md",
    "agency_marketing_growth.md",
    "agency_finance_sales_ops.md",
    "agency_oversight_critics.md",
    "venture_council.md",
]


DEPARTMENT_RULE_SPECS: Dict[str, Dict[str, Any]] = {
    "agency_engineering.md": {
        "department": "engineering",
        "description": (
            "Activate when designing system architecture, writing frontend (React/Next.js), "
            "backend APIs, database migrations/RLS, mobile apps, QA/Playwright tests, "
            "security audits, or DevOps CI/CD pipelines."
        ),
        "globs": [
            "src/**/*.{ts,tsx,js,jsx,py,go,rs}",
            "app/**/*",
            "prisma/**/*",
            "migrations/**/*",
            "tests/**/*",
        ],
    },
    "agency_product_design.md": {
        "department": "product_design",
        "description": (
            "Activate when drafting PRDs, SOW proposals, user personas, usability test "
            "reports, UI/UX design tokens, 8pt grid layouts, WCAG accessibility, or "
            "tracking scope creep."
        ),
        "globs": [
            ".agency/templates/product_design/**/*",
            ".agency/active/product_design/**/*",
            "src/components/**/*",
        ],
    },
    "agency_data_ai.md": {
        "department": "data_ai",
        "description": (
            "Activate when building LLM/RAG pipelines, ML model architectures, vector "
            "embeddings, prompt evaluation benchmarks, or SQL analytics dashboards."
        ),
        "globs": [
            ".agency/templates/data_ai/**/*",
            ".agency/active/data_ai/**/*",
            "**/*.sql",
        ],
    },
    "agency_marketing_growth.md": {
        "department": "marketing",
        "description": (
            "Activate when working on technical SEO, Schema.org JSON-LD, Core Web Vitals, "
            "landing page conversion copywriting, UTM tracking, or paid media campaigns."
        ),
        "globs": [
            ".agency/templates/marketing/**/*",
            ".agency/active/marketing/**/*",
        ],
    },
    "agency_finance_sales_ops.md": {
        "department": "finance_ops",
        "extra_departments": ["sales_client"],
        "description": (
            "Activate when drafting MSAs, DPAs, SLAs, change orders, financial pricing & "
            "burn models, timesheets, client intake questionnaires, or weekly status reports."
        ),
        "globs": [
            ".agency/templates/finance_ops/**/*",
            ".agency/templates/sales_client/**/*",
            ".agency/active/finance_ops/**/*",
            ".agency/active/sales_client/**/*",
        ],
    },
    "agency_oversight_critics.md": {
        "department": "oversight",
        "description": (
            "Activate when performing adversarial red-team audits, pre-merge code integrity "
            "reviews, placeholder checks, or phase gate sign-off verifications."
        ),
        "globs": [
            ".agency/agents/oversight/**/*",
            ".agency/active/**/*",
        ],
    },
}

HOOK_SHIM_CODE = '''#!/usr/bin/env python3
"""Forwarding shim for Antigravity 2.0 hooks when CWD is .agents/ or .agents/plugins/agency-playbook/."""
import importlib.util
import pathlib
import runpy
import sys

_THIS = pathlib.Path(__file__).resolve()
_TARGET = None
for parent in [_THIS.parent, *_THIS.parents]:
    candidate = parent / ".agency" / "scripts" / "agency_hooks.py"
    if (
        candidate.is_file()
        and candidate.resolve() != _THIS
        and ".agents" not in candidate.parts
    ):
        _TARGET = candidate
        break

if _TARGET:
    if __name__ == "__main__":
        runpy.run_path(str(_TARGET), run_name="__main__")
        sys.exit(0)
    else:
        _spec = importlib.util.spec_from_file_location("real_agency_hooks", str(_TARGET))
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            for _k, _v in _mod.__dict__.items():
                if not _k.startswith("__"):
                    globals()[_k] = _v
else:
    if __name__ == "__main__":
        print("{}")
'''


def discover_agents(agency_dir: Path) -> List[Dict[str, str]]:
    """Dynamically discover all 25 agent charters and parse their YAML frontmatter."""
    agents_dir = agency_dir / "agents"
    roster: List[Dict[str, str]] = []
    if not agents_dir.exists():
        return roster

    for md_file in sorted(agents_dir.rglob("*.md")):
        rel_role = md_file.relative_to(agents_dir).as_posix()
        role_id = rel_role[:-3] if rel_role.endswith(".md") else rel_role
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm: Dict[str, str] = {}
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"').strip("'")
        roster.append(
            {
                "agent_id": fm.get("agent_id", "00"),
                "role": fm.get("role", md_file.stem.replace("_", " ").title()),
                "department": fm.get("department", md_file.parent.name),
                "description": fm.get("description", ""),
                "path": f".agency/agents/{rel_role}",
                "short_ref": f"@{role_id}",
            }
        )
    roster.sort(key=lambda x: (x["agent_id"], x["path"]))
    return roster


def discover_skills(agency_dir: Path) -> List[Dict[str, str]]:
    """Discover all skills in `.agency/skills/` and normalize their hyphenated names."""
    skills_dir = agency_dir / "skills"
    skills: List[Dict[str, str]] = []
    if not skills_dir.exists():
        return skills

    seen = set()
    for md_file in sorted(skills_dir.glob("*.md")):
        slug = re.sub(r"^\d+[-_]", "", md_file.stem.lower()).replace("_", "-")
        if slug in seen:
            continue
        seen.add(slug)
        text = md_file.read_text(encoding="utf-8", errors="replace")
        desc = f"Specialized agency skill for {slug.replace('-', ' ')}."
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        body = text
        if m:
            body = text[m.end():]
            for line in m.group(1).splitlines():
                if line.strip().startswith("description:"):
                    desc = line.split(":", 1)[1].strip().strip('"').strip("'")
        skills.append(
            {
                "name": slug,
                "description": desc,
                "body": body.strip(),
                "source_file": md_file.as_posix(),
            }
        )
    return skills


def _hook_cmd(event: str) -> str:
    return f"python .agency/scripts/agency_hooks.py --event {event}"


def build_plugin_hooks_json(enabled: bool = True) -> Dict[str, Any]:
    """
    Build Antigravity 2.0 compliant `hooks.json`:
      - Top-level key is the hook suite name (`"agency-lifecycle-guard"`), plus `"hooks"`
        mirror for schema inspection compatibility.
      - `"agency-lifecycle-guard"` has `"enabled": True` (when enabled=True), while `"hooks"`
        mirror has `"enabled": False` so hooks do not fire twice.
      - `PreInvocation` and `Stop` are flat arrays of handler objects.
      - `PreToolUse` and `PostToolUse` are grouped matcher arrays.
    """
    events_spec: Dict[str, Any] = {
        "enabled": enabled,
        "PreInvocation": [
            {
                "type": "command",
                "command": _hook_cmd("PreInvocation"),
                "timeout": 5,
            }
        ],
        "PreToolUse": [
            {
                "matcher": "run_command|write_to_file|replace_file_content",
                "hooks": [
                    {
                        "type": "command",
                        "command": _hook_cmd("PreToolUse"),
                        "timeout": 5,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "write_to_file|replace_file_content",
                "hooks": [
                    {
                        "type": "command",
                        "command": _hook_cmd("PostToolUse"),
                        "timeout": 5,
                    }
                ],
            }
        ],
        "Stop": [
            {
                "type": "command",
                "command": _hook_cmd("Stop"),
                "timeout": 5,
            }
        ],
    }
    hooks_spec = dict(events_spec)
    hooks_spec["enabled"] = False
    return {
        "agency-lifecycle-guard": events_spec,
        "hooks": hooks_spec,
    }


def build_mcp_config_json() -> Dict[str, Any]:
    """Build Antigravity 2.0 `mcp_config.json` wiring Ripwire L0 and Laya L1 MCP servers."""
    return {
        "mcpServers": {
            "ripwire": {
                "command": "ripwire",
                "args": [".", "--mcp"],
                "env": {
                    "RIPWIRE_INDEX_MARKDOWN": "1",
                    "RIPWIRE_VERSION": "0.6.5",
                },
            },
            "laya": {
                "command": "laya-mcp-server",
                "args": [],
                "env": {
                    "LAYA_MODEL_TIER": "system1-fast",
                    "LAYA_MULTILINGUAL": "1",
                },
            },
        }
    }


def build_agents_md() -> str:
    """
    Build standalone `AGENTS.md` (<4KB, NO YAML frontmatter per Antigravity 2.0 spec).
    """
    content = """# Agency Playbook Operating System (Antigravity 2.0 + Ripwire L0 + Laya L1)

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
"""
    assert len(content.encode("utf-8")) < 4000, "AGENTS.md must stay strictly under 4KB"
    return content


def generate_antigravity_plugin(root_dir: Path = ROOT_DIR, clean: bool = False) -> None:
    """Generate the complete Antigravity 2.0 `.agents/` hierarchy and `.agency/skills/<name>/SKILL.md`."""
    agency_dir = root_dir / ".agency"
    agents_dot_dir = root_dir / ".agents"
    plugin_dir = agents_dot_dir / "plugins" / "agency-playbook"

    if clean:
        if agents_dot_dir.exists():
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            plugin_dir.mkdir(parents=True, exist_ok=True)
            rules_dir = agents_dot_dir / "rules"
            if rules_dir.exists():
                for rf in rules_dir.glob("agency_*.md"):
                    try:
                        rf.unlink()
                    except OSError:
                        pass
            for f in [agents_dot_dir / "plugins.json", agents_dot_dir / "skills.json"]:
                if f.exists():
                    try:
                        f.unlink()
                    except OSError:
                        pass
            print("[*] Cleaned Agency Playbook Antigravity 2.0 plugin and rules (preserved venture rules).")
        return

    (plugin_dir / "rules").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "skills").mkdir(parents=True, exist_ok=True)
    (agents_dot_dir / "rules").mkdir(parents=True, exist_ok=True)

    # Ensure venture_council.md is preserved / restored in .agents/rules/
    venture_rule_src = root_dir / ".venture" / "rules" / "venture_council.md"
    venture_rule_dst = agents_dot_dir / "rules" / "venture_council.md"
    if venture_rule_src.is_file() and not venture_rule_dst.exists():
        shutil.copy2(venture_rule_src, venture_rule_dst)

    # Ensure CWD-relative hook forwarding shims exist inside .agents/ and plugin_dir
    for shim_base in (agents_dot_dir, plugin_dir):
        shim_path = shim_base / ".agency" / "scripts" / "agency_hooks.py"
        shim_path.parent.mkdir(parents=True, exist_ok=True)
        shim_path.write_text(HOOK_SHIM_CODE, encoding="utf-8")

    # Discover skills first so plugin.json can list all 20 skill names
    skills = discover_skills(agency_dir)

    # 1. plugin.json
    plugin_json = {
        "name": "agency-playbook",
        "version": "2.0.0",
        "description": "Antigravity 2.0 Multi-Agent Software Engineering OS powered by Ripwire (L0) and Laya (L1).",
        "rules": "rules/AGENTS.md",
        "hooks": "hooks.json",
        "mcpConfig": "mcp_config.json",
        "skills": [sk["name"] for sk in skills],
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(plugin_json, indent=2) + "\n", encoding="utf-8")

    # 2. mcp_config.json
    mcp_cfg = build_mcp_config_json()
    (plugin_dir / "mcp_config.json").write_text(json.dumps(mcp_cfg, indent=2) + "\n", encoding="utf-8")

    # 3. hooks.json (enabled in plugin, present in .agents/hooks.json with enabled=False to avoid duplicate runs)
    (plugin_dir / "hooks.json").write_text(
        json.dumps(build_plugin_hooks_json(enabled=True), indent=2) + "\n", encoding="utf-8"
    )
    (agents_dot_dir / "hooks.json").write_text(
        json.dumps(build_plugin_hooks_json(enabled=False), indent=2) + "\n", encoding="utf-8"
    )

    # 4. rules/AGENTS.md (<4KB, no YAML frontmatter)
    agents_md_content = build_agents_md()
    (plugin_dir / "rules" / "AGENTS.md").write_text(agents_md_content, encoding="utf-8")

    # 5. Scoped department rules in .agents/rules/agency_*.md (trigger: model_decision)
    roster = discover_agents(agency_dir)
    for filename, spec in DEPARTMENT_RULE_SPECS.items():
        depts = {spec["department"]} | set(spec.get("extra_departments", []))
        dept_agents = [a for a in roster if a["department"] in depts]
        lines = [
            "---",
            "trigger: model_decision",
            f'description: "{spec["description"]}"',
            "---",
            f"# Agency Department Charter: {spec['department'].replace('_', ' ').title()}",
            "",
            "When working in this domain, summon or embody the corresponding `.agency/agents/` specialist:",
            "",
        ]
        for ag in dept_agents:
            lines.append(f"- **`{ag['short_ref']}`** (`{ag['path']}` — ID `{ag['agent_id']}`): {ag['description']}")
        lines.extend(
            [
                "",
                "## Operational Directives",
                "1. Use `python .agency/scripts/ripwire_engine.py --recall \"<query>\"` for zero-bloat context lookup.",
                "2. Score completed deliverables via `python .agency/scripts/laya_engine.py --score-deliverable <path>`.",
                "3. Never emit `[TBD]` or `[TODO]` placeholders; always include the `## ✍️ Human Lead Decision & Sign-Off Block`.",
                "",
            ]
        )
        (agents_dot_dir / "rules" / filename).write_text("\n".join(lines), encoding="utf-8")

    # 6. Skills directories (<skill-name>/SKILL.md) in both .agency/skills/ and .agents/plugins/agency-playbook/skills/
    skill_manifest_entries: List[Dict[str, str]] = []
    for sk in skills:
        skill_content = (
            f"---\n"
            f"name: {sk['name']}\n"
            f'description: "{sk["description"]}"\n'
            f"---\n\n"
            f"{sk['body']}\n"
        )
        plugin_skill_dir = plugin_dir / "skills" / sk["name"]
        plugin_skill_dir.mkdir(parents=True, exist_ok=True)
        (plugin_skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        agency_skill_dir = agency_dir / "skills" / sk["name"]
        agency_skill_dir.mkdir(parents=True, exist_ok=True)
        (agency_skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        skill_manifest_entries.append(
            {
                "name": sk["name"],
                "path": f".agents/plugins/agency-playbook/skills/{sk['name']}/SKILL.md",
                "description": sk["description"],
            }
        )

    # 7. .agents/plugins.json and .agents/skills.json (with Antigravity 2.0 `entries` + metadata)
    plugins_manifest = {
        "entries": [
            {"path": ".agents/plugins"}
        ],
        "plugins": [
            {
                "name": "agency-playbook",
                "path": ".agents/plugins/agency-playbook",
                "enabled": True,
            }
        ],
    }
    (agents_dot_dir / "plugins.json").write_text(json.dumps(plugins_manifest, indent=2) + "\n", encoding="utf-8")
    (agents_dot_dir / "skills.json").write_text(
        json.dumps(
            {
                "entries": skill_manifest_entries,
                "skills": skill_manifest_entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # 8. .ignore and .cursorignore with !.agency/ negation so symlinked/junctioned .agency is indexed
    ignore_content = (
        "# Ensure Ripwire, Antigravity, and Cursor index .agency, .venture, and .agents across junctions/symlinks\n"
        "!.agency/\n"
        "!.agency/**\n"
        "!.agents/\n"
        "!.agents/**\n"
        "!.venture/\n"
        "!.venture/**\n"
    )
    (root_dir / ".ignore").write_text(ignore_content, encoding="utf-8")
    (root_dir / ".cursorignore").write_text(ignore_content, encoding="utf-8")

    print("  [✓] Antigravity 2.0 Plugin & Scoped Rules Generated: .agents/plugins/agency-playbook/")


def generate_cursor_rules(root_dir: Path = ROOT_DIR, clean: bool = False) -> None:
    cursor_dir = root_dir / ".cursor" / "rules"
    if clean and cursor_dir.exists():
        for file in cursor_dir.glob("agency_*.mdc"):
            file.unlink()
        print("[*] Cleaned existing agency Cursor rules.")
        return

    cursor_dir.mkdir(parents=True, exist_ok=True)
    roster = discover_agents(root_dir / ".agency")

    core_content = """---
description: "Core Agency Operating System: Ripwire L0, Laya L1, 3-Tier routing protocol, and sign-off standards."
globs: []
alwaysApply: true
---

# 🏛️ Agency Playbook Core Constitution

This project is governed by the **Agency Playbook AI Engineering Operating System** (`.agency/`).

## ⚡ 3-Layer Intelligence & Routing
- **Layer 0 (Ripwire):** `python .agency/scripts/ripwire_engine.py --recall "<query>"`
- **Layer 1 (Laya):** `python .agency/scripts/laya_engine.py --route "<task>"`
- **Layer 2 (25 Agents):** `.agency/agents/<department>/<role>.md`

## 🛡️ Anti-Hallucination & Quality Standards
- **Zero Placeholder Deliverables:** Never produce files containing `[TBD]`, `[TODO]`, or empty sections.
- **Contract-First Delivery:** Adhere strictly to schemas in `.agency/active/engineering/04_system_design_architecture.md`.
- **Mandatory Sign-Off:** Every deliverable in `.agency/active/` must include `## ✍️ Human Lead Decision & Sign-Off Block`.
"""
    (cursor_dir / "agency_core.mdc").write_text(core_content, encoding="utf-8")

    for filename, spec in DEPARTMENT_RULE_SPECS.items():
        mdc_name = filename.replace(".md", ".mdc")
        depts = {spec["department"]} | set(spec.get("extra_departments", []))
        dept_agents = [a for a in roster if a["department"] in depts]
        globs_json = json.dumps(spec["globs"])
        agent_bullets = "\n".join(
            f"- `{a['short_ref']}` (`{a['path']}`): {a['description']}" for a in dept_agents
        )
        mdc_text = f"""---
description: "{spec['description']}"
globs: {globs_json}
alwaysApply: false
---

# Department Pod: {spec['department'].replace('_', ' ').title()}

## Assigned Specialists
{agent_bullets}
"""
        (cursor_dir / mdc_name).write_text(mdc_text, encoding="utf-8")

    print("  [✓] Cursor Rules Generated: .cursor/rules/agency_*.mdc")


def generate_claude_md(root_dir: Path = ROOT_DIR, clean: bool = False) -> None:
    target = root_dir / "CLAUDE.md"
    if clean:
        if target.exists():
            target.unlink()
            print("[*] Removed CLAUDE.md.")
        return

    roster = discover_agents(root_dir / ".agency")
    agent_lines = "\n".join(
        f"- `{a['path']}` (`#{a['agent_id']}` — **{a['role']}**): {a['description']}"
        for a in roster
    )

    content = f"""# 🤖 Agency Playbook — Claude Code & Antigravity 2.0 Directives

This project is orchestrated using the **Agency Playbook AI Engineering Operating System** (`.agency/` and `.agents/plugins/agency-playbook/`).

## ⚡ Daily Command Center (`agency.py`)
- **Unified CLI:** `python agency.py status` | `python agency.py validate --advance` | `python agency.py doctor`
- **Layer 0 (Ripwire Engine):** `python .agency/scripts/ripwire_engine.py --recall "<query>"` | `--doc-drift` | `--quality-delta`
- **Layer 1 (Laya Decision Engine):** `python .agency/scripts/laya_engine.py --route "<task>"` | `--score-deliverable <file>`
- **Transpile IDE & Plugin Rules:** `python .agency/scripts/transpile_rules.py --target all`
- **Active State Machine:** `.agency/active/project_state.yml` (7 Phases, 33 Templates)

## 👥 25-Agent Roster (`.agency/agents/<department>/<role>.md`)
{agent_lines}

## 🚦 Strict Operational Rules
1. Never produce placeholder deliverables containing `[TBD]`, `[TODO]`, or empty sections.
2. Every active deliverable in `.agency/active/` must include `## ✍️ Human Lead Decision & Sign-Off Block`.
3. Use Ripwire `--recall` before loading large files and `--plan-lanes` / `--merge-scout` for parallel tracks.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Claude Code Directives Generated: CLAUDE.md")


def generate_windsurf_rules(root_dir: Path = ROOT_DIR, clean: bool = False) -> None:
    target = root_dir / ".windsurfrules"
    if clean:
        if target.exists():
            target.unlink()
        return

    content = """# Windsurf Cascade Rules — Agency Playbook Operating System

1. Project State: Active tracking file is located at `.agency/active/project_state.yml`.
2. Layer 0 Context: Run `python .agency/scripts/ripwire_engine.py --recall "<query>"` for structural lookup.
3. Layer 1 Routing: Run `python .agency/scripts/laya_engine.py --route "<task>"` for pod selection.
4. Quality Gate: Zero placeholder tokens (`[TBD]`, `[TODO]`) and mandatory `## ✍️ Human Lead Decision & Sign-Off Block`.
5. Validation: Verify phase completion with `python agency.py validate --advance`.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Windsurf Rules Generated: .windsurfrules")


def generate_aider_conventions(root_dir: Path = ROOT_DIR, clean: bool = False) -> None:
    target = root_dir / "CONVENTIONS.md"
    if clean:
        if target.exists():
            target.unlink()
        return

    content = """# Aider Coding Conventions — Agency Playbook

- Architecture: Follow contract-first patterns. Adhere to schemas defined in `.agency/active/`.
- Layer 0 & Layer 1: Use `.agency/scripts/ripwire_engine.py` and `.agency/scripts/laya_engine.py` for recall and rubric checks.
- Code Quality: Clean, modular, type-safe code with zero unresolved TODO markers.
- Governance: Update `.agency/active/` documentation and sign-off blocks when altering architecture or data models.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Aider Conventions Generated: CONVENTIONS.md")


def transpile_all(
    target: str = "all",
    root_dir: Path = ROOT_DIR,
    clean: bool = False,
) -> None:
    if target in {"all", "antigravity"}:
        generate_antigravity_plugin(root_dir=root_dir, clean=clean)
    if target in {"all", "cursor"}:
        generate_cursor_rules(root_dir=root_dir, clean=clean)
    if target in {"all", "claude"}:
        generate_claude_md(root_dir=root_dir, clean=clean)
    if target in {"all", "windsurf"}:
        generate_windsurf_rules(root_dir=root_dir, clean=clean)
    if target in {"all", "aider"}:
        generate_aider_conventions(root_dir=root_dir, clean=clean)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transpile Agency Playbook rules to Antigravity 2.0 and multi-IDE native configurations."
    )
    parser.add_argument(
        "--target",
        choices=["all", "antigravity", "cursor", "claude", "windsurf", "aider"],
        default="all",
        help="Target IDE/agent configuration to generate.",
    )
    parser.add_argument("--workspace", default=None, help="Target workspace directory.")
    parser.add_argument("--clean", action="store_true", help="Remove generated IDE configuration files.")
    args = parser.parse_args(argv)

    ws = Path(args.workspace).resolve() if args.workspace else ROOT_DIR
    print("\n🚀 Agency Playbook Multi-IDE & Antigravity 2.0 Transpiler")
    print("=" * 62)
    transpile_all(target=args.target, root_dir=ws, clean=args.clean)
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())

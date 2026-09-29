#!/usr/bin/env python3
"""
Lean Multi-IDE Transpiler for Agency Playbook
=============================================
Compiles canonical .agency/ rules, pod charters, and skills into tool-native formats:
  - Cursor: Scoped .cursor/rules/*.mdc (with intelligent globs to prevent context pollution)
  - Claude Code: Project root CLAUDE.md
  - Windsurf: Project root .windsurfrules
  - Aider: Project root CONVENTIONS.md

Usage:
    python .agency/scripts/transpile_rules.py --target all
    python .agency/scripts/transpile_rules.py --target cursor
    python .agency/scripts/transpile_rules.py --target claude
    python .agency/scripts/transpile_rules.py --clean
"""

import os
import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
AGENCY_DIR = SCRIPT_DIR.parent
ROOT_DIR = AGENCY_DIR.parent

def generate_cursor_rules(clean=False):
    cursor_dir = ROOT_DIR / ".cursor" / "rules"
    
    if clean and cursor_dir.exists():
        for file in cursor_dir.glob("agency_*.mdc"):
            file.unlink()
        print("[*] Cleaned existing agency Cursor rules.")
        return

    cursor_dir.mkdir(parents=True, exist_ok=True)

    rules = {
        "agency_core.mdc": {
            "description": "Core Agency Operating System: 3-Tier routing protocol, quality gates, and sign-off standards.",
            "globs": [],
            "alwaysApply": True,
            "content": """# 🏛️ Agency Playbook Core Constitution

This project is governed by the **Agency Playbook AI Engineering Operating System** (`.agency/`).

## ⚡ 3-Tier Task Routing Protocol
1. **Tier 1 (Micro-Task / Bug / Hotfix):** 0 Ceremony. Direct edit in IDE. Zero document generation or role swapping.
2. **Tier 2 (Minor Feature / Change Order):** Fast 2-Role Lane (<15 min). `@product_manager` (2-min spec) -> `@frontend_engineer` or `@backend_engineer` -> `@master_critic`.
3. **Tier 3 (Full System Build):** Complete 7-Phase lifecycle following `.agency/active/project_state.yml`.

## 🛡️ Anti-Hallucination & Quality Standards
- **Zero Placeholder Deliverables:** Never produce files containing `[TBD]`, `[TODO]`, `[FILL THIS]`, or empty sections.
- **Contract-First Delivery:** All frontend/backend integrations must adhere strictly to OpenAPI schemas in `04_system_design_architecture.md`.
- **Definition of Done:** Every non-trivial deliverable requires clean formatting, zero unresolved assumptions, and passes validation.
"""
        },
        "agency_frontend.mdc": {
            "description": "Frontend UI/UX directives, design token systems, 8pt grid, and accessibility standards.",
            "globs": ["src/**/*.{tsx,jsx,vue,svelte,css,scss,html}", "app/**/*.{tsx,jsx,css}", "components/**/*.{tsx,jsx,ts,js}"],
            "alwaysApply": False,
            "content": """# 🎨 Agency Frontend & UI/UX Charter

You are executing within the **Frontend & UI/UX Pod** (`@03_ui_ux_designer.md` and `@04_frontend_engineer.md`).

## 📐 Design & Layout Tenets
- **8pt Grid & Consistent Spacing:** Use strict multi-step scales (`4px`, `8px`, `16px`, `24px`, `32px`).
- **Semantic HTML & WCAG 2.1 AA:** Ensure proper `aria-label`, interactive keyboard navigation, and high contrast ratios.
- **Responsive-First:** Fluid layouts with mobile-first breakpoints; no rigid horizontal pixel overflows.
- **State Completeness:** Every interactive view MUST implement all 4 states: Loading, Error, Empty, and Success.
"""
        },
        "agency_backend.mdc": {
            "description": "Backend API, service layer, transaction handling, and OpenAPI validation standards.",
            "globs": ["src/**/*.{ts,js,py,go,rs}", "api/**/*", "controllers/**/*", "models/**/*", "services/**/*", "routes/**/*"],
            "alwaysApply": False,
            "content": """# ⚙️ Agency Backend & API Engineering Charter

You are executing within the **Backend & Systems Pod** (`@05_backend_engineer.md`).

## 🔌 API & Reliability Rules
- **Contract Compliance:** Strict adherence to OpenAPI schemas; validate all inbound request bodies with Zod or Pydantic.
- **Idempotency & Transactions:** All mutation operations that touch multiple tables must run inside database transactions.
- **Error Handling:** Standardized error response envelope: `{ error: { code: string, message: string, details?: any } }`.
- **Zero Secrets in Code:** Never hardcode API keys or credentials; read strictly from validated environment configs.
"""
        },
        "agency_database.mdc": {
            "description": "Database schema, migrations, indexing, and Row-Level Security (RLS) standards.",
            "globs": ["prisma/**/*", "drizzle/**/*", "migrations/**/*", "schema.sql", "src/db/**/*", "supabase/**/*"],
            "alwaysApply": False,
            "content": """# 🗄️ Agency Database & Storage Charter

You are executing within the **Database Engineering Pod** (`@06_database_engineer.md`).

## 🛡️ Data & Migration Standards
- **Non-Destructive Migrations:** Never generate destructive drop operations without explicit data backup scripts.
- **Index Optimization:** Always index foreign keys and columns frequently queried in `WHERE` / `JOIN` / `ORDER BY` clauses.
- **Row-Level Security (RLS):** For multi-tenant databases (e.g. Supabase/Postgres), every table MUST have explicit tenant-isolated RLS policies.
"""
        },
        "agency_qa_security.mdc": {
            "description": "Testing, SDET automation, Playwright E2E, and security vulnerability standards.",
            "globs": ["test/**/*", "tests/**/*", "**/*.spec.*", "**/*.test.*", "cypress/**/*", "playwright.config.*"],
            "alwaysApply": False,
            "content": """# 🧪 Agency QA & Security Auditor Charter

You are executing within the **QA & Security Red-Team Pod** (`@07_qa_sdet_engineer.md` and `@08_security_auditor.md`).

## 🔍 Testing & Security Rules
- **Test Real User Flows:** Write resilient tests that assert user-visible outcomes, not brittle internal implementation details.
- **OWASP Top 10 Red-Teaming:** Audit against SQL injection, XSS, broken object-level authorization (BOLA/IDOR), and CSRF.
- **Deterministic Assertions:** No flaky `sleep()` waits; use deterministic state-based waiting (`waitForSelector`, `expect.poll`).
"""
        }
    }

    for filename, rule in rules.items():
        filepath = cursor_dir / filename
        globs_formatted = str(rule["globs"]).replace("'", '"') if rule["globs"] else "[]"
        always_apply_str = "true" if rule["alwaysApply"] else "false"

        file_content = f"""---
description: "{rule['description']}"
globs: {globs_formatted}
alwaysApply: {always_apply_str}
---

{rule['content']}
"""
        filepath.write_text(file_content, encoding="utf-8")
        print(f"  [✓] Cursor Rule Generated: .cursor/rules/{filename}")

def generate_claude_md(clean=False):
    target = ROOT_DIR / "CLAUDE.md"
    if clean:
        if target.exists():
            target.unlink()
            print("[*] Removed CLAUDE.md.")
        return

    content = """# 🤖 Agency Playbook — Claude Code Directives

This project is orchestrated using the **Agency Playbook AI Engineering Operating System** (`.agency/`).

## ⚡ Daily Command Center
- **Status Dashboard:** `python .agency/scripts/status.py`
- **Validate Deliverables:** `python .agency/scripts/validate_phase.py`
- **Auto-Advance Phase:** `python .agency/scripts/validate_phase.py --advance`
- **Transpile IDE Rules:** `python .agency/scripts/transpile_rules.py --target all`
- **Active State File:** `.agency/active/project_state.yml`

## 👥 Department Pods & Role Charters
- `@01_product_manager.md` — Product discovery, PRDs, client intake
- `@02_solutions_architect.md` — System design, OpenAPI contracts, HLD/LLD
- `@03_ui_ux_designer.md` & `@04_frontend_engineer.md` — Client UI, 8pt grid, WCAG AA
- `@05_backend_engineer.md` & `@06_database_engineer.md` — APIs, DB migrations, RLS
- `@07_qa_sdet_engineer.md` & `@08_security_auditor.md` — Playwright E2E, SAST security
- `@09_devops_sre_engineer.md` — CI/CD pipelines, Docker, runbooks
- `@10_legal_operations_officer.md` — SOWs, MSAs, SLAs, client handoff
- `@master_critic.md` — Adversarial audit and red-teaming

## 🚦 Strict Operational Rules
1. Never produce placeholder deliverables containing `[TBD]`, `[TODO]`, or empty sections.
2. For Tier 1 bug fixes, make direct surgical edits without role-swapping ceremony.
3. For Tier 3 full system builds, adhere strictly to the 7-Phase SDLC in `project_state.yml`.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Claude Code Directives Generated: CLAUDE.md")

def generate_windsurf_rules(clean=False):
    target = ROOT_DIR / ".windsurfrules"
    if clean:
        if target.exists():
            target.unlink()
            print("[*] Removed .windsurfrules.")
        return

    content = """# Windsurf Cascade Rules — Agency Playbook Operating System

1. Project State: Active tracking file is located at `.agency/active/project_state.yml`.
2. Architecture Contract: Code must match OpenAPI schemas in `.agency/active/engineering/04_system_design_architecture.md`.
3. Quality Gate: No placeholder tokens `[TBD]`, `[TODO]`, or empty stubs in deliverables.
4. Validation: Verify phase completion with `python .agency/scripts/validate_phase.py`.
5. Error Handling: When encountering build/runtime errors, run `@crash-debugger.md` to analyze root cause.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Windsurf Rules Generated: .windsurfrules")

def generate_aider_conventions(clean=False):
    target = ROOT_DIR / "CONVENTIONS.md"
    if clean:
        if target.exists():
            target.unlink()
            print("[*] Removed CONVENTIONS.md.")
        return

    content = """# Aider Coding Conventions — Agency Playbook

- Architecture: Follow contract-first patterns. Adhere to schemas defined in `.agency/active/`.
- Code Quality: Clean, modular, type-safe code with zero unresolved TODO markers.
- Testing: All new endpoints and business logic require unit or integration tests.
- Security: Never hardcode credentials. Use environment variables strictly.
- State: Update `.agency/active/` documentation when altering architecture or data models.
"""
    target.write_text(content, encoding="utf-8")
    print("  [✓] Aider Conventions Generated: CONVENTIONS.md")

def main():
    parser = argparse.ArgumentParser(description="Transpile Agency Playbook rules to multi-IDE native configurations.")
    parser.add_argument("--target", choices=["all", "cursor", "claude", "windsurf", "aider"], default="all", help="Target IDE configuration to generate.")
    parser.add_argument("--clean", action="store_true", help="Remove generated IDE configuration files.")
    args = parser.parse_args()

    print("\n🚀 Agency Playbook Multi-IDE Transpiler")
    print("=" * 55)

    if args.target in ["all", "cursor"]:
        generate_cursor_rules(clean=args.clean)
    if args.target in ["all", "claude"]:
        generate_claude_md(clean=args.clean)
    if args.target in ["all", "windsurf"]:
        generate_windsurf_rules(clean=args.clean)
    if args.target in ["all", "aider"]:
        generate_aider_conventions(clean=args.clean)

    print("=" * 55)
    action = "Cleaned" if args.clean else "Successfully generated"
    print(f"🎉 {action} configurations for target: {args.target.upper()}\n")

if __name__ == "__main__":
    main()

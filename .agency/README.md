# Agency Playbook: AI Engineering Team Operating System

Welcome to the **Agency Playbook**! This system transforms your software delivery process into an autonomous, platform-agnostic virtual engineering organization.

---

## 📁 System Architecture Overview

```
.agency/
├── README.md              # System overview
├── prompt_cheat_sheet.md  # YOUR DAILY DRIVER (3-Tier Protocol, Prompts & Scripts)
├── active/                # The working directory for the active project
│   └── project_state.yml  # State machine tracking phases, roles, and deliverables
├── agents/                # 8 Engineering Pods + Master Critic & Oversight Roles
├── runbooks/              # 4 Pre-packaged Scenario Squads (MVP, Incident, Legacy, Hardening)
│   ├── rapid_mvp_launch.md
│   ├── emergency_incident_response.md
│   ├── legacy_codebase_takeover.md
│   └── pre_launch_security_hardening.md
├── scripts/               # Automation, transpilation, and validation tools
│   ├── status.py          # Live terminal project dashboard & progress bar
│   ├── transpile_rules.py # Multi-IDE compiler (Cursor .mdc, Claude Code, Windsurf, Aider)
│   └── validate_phase.py  # Anti-empty validator & 1-click phase advance (--advance)
├── skills/                # 19 Standalone Portable Skills (SAST, WCAG, Diagrams, etc.)
├── teams/
│   └── TEAMS.md           # Master Engineering Org Chart & Department Map
└── templates/             # 30 Production Deliverable Templates across 6 Departments
```

---

## 🚀 How to Run a Project (The Standard 4-Step Flow)

### 1. Initialize State
When starting or resuming a project:
* Run the terminal dashboard: `python .agency/scripts/status.py`
* Transpile rules to your IDE: `python .agency/scripts/transpile_rules.py --target all`
* Or summon the AI session resumer in chat: `Run @session-resumer.md`

### 2. Summon the Active Role or Runbook
Summon the Staff/Principal lead for your current phase (e.g. `@01_product_manager.md`), or launch a scenario runbook directly from `.agency/runbooks/`.

### 3. Executive Review & Human Sign-Off
At the end of every deliverable, the AI pauses at the **`✍️ Human Lead Decision & Sign-Off Block`** presenting the top 3 choices.
Approve with a simple 1-line reply (`"Approved"` or `"Modify Decision 1: Use Supabase"`).

### 4. Validate & Auto-Advance
Once signed off, advance the project state in one command:
```bash
python .agency/scripts/validate_phase.py --advance
```

---

## ⚡ The 3-Tier Task Routing Protocol
* **Tier 1 (Hotfix / Small Bug):** 0 Ceremony. Direct edit in IDE (`"Fix error in auth.ts"`). Zero role swapping.
* **Tier 2 (Minor Feature / Change):** Fast 2-Role Lane (<15 min). `@01_product_manager` (2-min spec) $\rightarrow$ `@04_frontend` or `@05_backend` $\rightarrow$ `@master_critic`.
* **Tier 3 (Full System Build):** Complete 7-Phase lifecycle or Scenario Runbook execution.

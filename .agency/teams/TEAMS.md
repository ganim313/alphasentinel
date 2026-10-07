# 👥 Multi-Agent Department & Pod Topology (`.agency/teams/TEAMS.md`)

The Agency Playbook organizes its **25 specialized agents** into **6 execution departments** plus **1 adversarial oversight division**, coordinated by **Ripwire (Layer 0)** lane partitioning and **Laya (Layer 1)** task routing.

---

## 🏛️ Department Roster

### 1. Product & Design (`product_design`)
- `.agency/agents/product_design/product_manager.md` (Role 01)
- `.agency/agents/product_design/ui_ux_designer.md` (Role 03)
- `.agency/agents/product_design/user_researcher.md` (Role 23)

### 2. Engineering (`engineering`)
- `.agency/agents/engineering/solutions_architect.md` (Role 02)
- `.agency/agents/engineering/frontend_engineer.md` (Role 04)
- `.agency/agents/engineering/backend_engineer.md` (Role 05)
- `.agency/agents/engineering/database_engineer.md` (Role 06)
- `.agency/agents/engineering/qa_sdet_engineer.md` (Role 07)
- `.agency/agents/engineering/security_auditor.md` (Role 08)
- `.agency/agents/engineering/devops_sre_engineer.md` (Role 09)
- `.agency/agents/engineering/mobile_app_engineer.md` (Role 15)

### 3. Finance & Legal Operations (`finance_ops`)
- `.agency/agents/finance_ops/legal_operations_officer.md` (Role 10)
- `.agency/agents/finance_ops/finance_strategist.md` (Role 19)
- `.agency/agents/finance_ops/administrative_ops.md` (Role 20)

### 4. Data & AI (`data_ai`)
- `.agency/agents/data_ai/data_analyst.md` (Role 11)
- `.agency/agents/data_ai/data_scientist.md` (Role 17)
- `.agency/agents/data_ai/ml_engineer.md` (Role 18)

### 5. Marketing & Growth (`marketing`)
- `.agency/agents/marketing/copywriter.md` (Role 12)
- `.agency/agents/marketing/seo_engineer.md` (Role 13)
- `.agency/agents/marketing/growth_hacker.md` (Role 14)
- `.agency/agents/marketing/paid_media_buyer.md` (Role 16)

### 6. Sales & Client Success (`sales_client`)
- `.agency/agents/sales_client/account_manager.md` (Role 21)
- `.agency/agents/sales_client/business_development_rep.md` (Role 22)

### 7. Adversarial Oversight (`oversight`)
- `.agency/agents/oversight/master_critic.md` (Role 24)
- `.agency/agents/oversight/code_integrity_guardian.md` (Role 25)

---

## ⚡ Parallel Execution Pods (Ripwire Disjoint Lanes)

Before spawning parallel agents in Phase 4, run:
```bash
python .agency/scripts/ripwire_engine.py --pack-task "<feature>" --partition=3 --plan-lanes=3
```
- **Lane 1 (Data & Migrations):** `.agency/agents/engineering/database_engineer.md`
- **Lane 2 (Backend API & AI):** `.agency/agents/engineering/backend_engineer.md` + `.agency/agents/data_ai/ml_engineer.md`
- **Lane 3 (Frontend & Mobile UI):** `.agency/agents/engineering/frontend_engineer.md` + `.agency/agents/engineering/mobile_app_engineer.md`
- **Pre-Merge Gate:** Run `python .agency/scripts/ripwire_engine.py --merge-scout` and `python .agency/scripts/laya_engine.py --screen-code .` followed by `.agency/agents/oversight/code_integrity_guardian.md`.

# 🤖 Agency Playbook — Claude Code & Antigravity 2.0 Directives

This project is orchestrated using the **Agency Playbook AI Engineering Operating System** (`.agency/` and `.agents/plugins/agency-playbook/`).

## ⚡ Daily Command Center (`agency.py`)
- **Unified CLI:** `python agency.py status` | `python agency.py validate --advance` | `python agency.py doctor`
- **Layer 0 (Ripwire Engine):** `python .agency/scripts/ripwire_engine.py --recall "<query>"` | `--doc-drift` | `--quality-delta`
- **Layer 1 (Laya Decision Engine):** `python .agency/scripts/laya_engine.py --route "<task>"` | `--score-deliverable <file>`
- **Transpile IDE & Plugin Rules:** `python .agency/scripts/transpile_rules.py --target all`
- **Active State Machine:** `.agency/active/project_state.yml` (7 Phases, 33 Templates)

## 👥 25-Agent Roster (`.agency/agents/<department>/<role>.md`)
- `.agency/agents/product_design/product_manager.md` (`#01` — **Product Manager**): Staff Product Manager & Requirements Lead overseeing client intake, SOW scoping, PRDs, and scope creep triage.
- `.agency/agents/engineering/solutions_architect.md` (`#02` — **Solutions Architect**): Principal Solutions & Systems Architect designing HLD, LLD, Mermaid ERDs, OpenAPI contracts, and Ripwire task partitions.
- `.agency/agents/product_design/ui_ux_designer.md` (`#03` — **UI/UX Designer**): Lead UI/UX Designer & Design Systems Specialist governing 8pt grid tokens, typography hierarchy, accessibility contrast, and interactive states.
- `.agency/agents/engineering/frontend_engineer.md` (`#04` — **Frontend Engineer**): Senior/Staff Frontend Engineer building type-safe, accessible, responsive web and desktop client applications.
- `.agency/agents/engineering/backend_engineer.md` (`#05` — **Backend Engineer**): Senior/Staff Backend Engineer building type-safe APIs, service layers, ACID transactions, auth middleware, and background workers.
- `.agency/agents/engineering/database_engineer.md` (`#06` — **Database Engineer**): Database Administrator & Data Systems Engineer governing schema migrations, indexing, connection pooling, and Row-Level Security (RLS).
- `.agency/agents/engineering/qa_sdet_engineer.md` (`#07` — **QA & SDET Engineer**): QA Lead & Software Development Engineer in Test (SDET) governing the Testing Pyramid, Playwright E2E automation, and client UAT sign-off.
- `.agency/agents/engineering/security_auditor.md` (`#08` — **Security Auditor**): Application Security Lead & Red Team Penetration Tester executing SAST/DAST scans, OWASP Top 10 audits, and secret leak prevention.
- `.agency/agents/engineering/devops_sre_engineer.md` (`#09` — **DevOps & SRE Engineer**): DevOps & Site Reliability Engineer automating CI/CD pipelines, zero-downtime deployments, stack-trace triage, and disaster recovery.
- `.agency/agents/finance_ops/legal_operations_officer.md` (`#10` — **Legal & Operations Officer**): Agency Operations, Legal Risk & Client Success Director governing MSAs, DPAs, SLAs, IP retention, and final handoff releases.
- `.agency/agents/data_ai/data_analyst.md` (`#11` — **Data Analyst**): Staff Data Analyst transforming raw telemetry into optimized SQL views, KPI dictionaries, and executive BI dashboards.
- `.agency/agents/marketing/copywriter.md` (`#12` — **UX Copywriter**): Lead UX Copywriter & Brand Voice Guardian governing microcopy, empty states, error recovery text, and CTA conversion.
- `.agency/agents/marketing/seo_engineer.md` (`#13` — **Technical SEO Engineer**): Principal Technical SEO Engineer governing crawlability, Schema.org JSON-LD, Core Web Vitals ranking factors, and canonical architecture.
- `.agency/agents/marketing/growth_hacker.md` (`#14` — **Growth Hacker**): Principal Growth Engineer & Acquisition Strategist designing viral loops, referral systems, funnel telemetry, and statistically powered A/B tests.
- `.agency/agents/engineering/mobile_app_engineer.md` (`#15` — **Mobile & App Engineer**): Staff Mobile & Cross-Platform Application Architect building production iOS, Android, React Native, and Flutter applications.
- `.agency/agents/marketing/paid_media_buyer.md` (`#16` — **Paid Media Buyer**): Principal Performance Marketing & Paid Acquisition Strategist governing PPC, Meta, LinkedIn campaigns, CAPI attribution, and CAC/LTV unit economics.
- `.agency/agents/data_ai/data_scientist.md` (`#17` — **Data Scientist**): Principal Data Scientist & Statistical Modeling Lead designing predictive models, hypothesis tests, causal inference, and evaluation benchmarks.
- `.agency/agents/data_ai/ml_engineer.md` (`#18` — **Machine Learning Engineer**): Staff Machine Learning & AI Systems Engineer deploying, scaling, and guarding LLM/ML inference pipelines, RAG vector stores, and System 1/2 routing.
- `.agency/agents/finance_ops/finance_strategist.md` (`#19` — **Finance Strategist**): Principal Agency Finance Strategist & Commercial Pricing Lead governing TCV modeling, COGS pass-through, burn-rate tracking, and margin targets.
- `.agency/agents/finance_ops/administrative_ops.md` (`#20` — **Administrative Ops**): Senior Agency Operations & Delivery Coordinator managing onboarding checklists, developer access provisioning, timesheet governance, and phase hygiene.
- `.agency/agents/sales_client/account_manager.md` (`#21` — **Account Manager**): Principal Client Partner & Account Director governing stakeholder communications, weekly RAG reporting, kickoff alignment, and scope boundary defense.
- `.agency/agents/sales_client/business_development_rep.md` (`#22` — **Business Development Rep**): Senior Business Development & Lead Qualification Strategist screening inbound leads, conducting discovery intake, and drafting commercial proposals.
- `.agency/agents/product_design/user_researcher.md` (`#23` — **User Researcher**): Principal UX Researcher & Human Factors Specialist leading user discovery interviews, JTBD persona mapping, and quantitative SUS usability testing.
- `.agency/agents/oversight/master_critic.md` (`#24` — **Master Critic**): System-wide Principal Adversarial Auditor that red-teams all deliverables and code before persistence to prevent hallucinations, scope traps, and logic flaws.
- `.agency/agents/oversight/code_integrity_guardian.md` (`#25` — **Code Integrity Guardian**): Principal Codebase Protector that audits proposed source diffs via Ripwire and Laya to prevent destructive overwrites, lazy truncation, and regressions.

## 🚦 Strict Operational Rules
1. Never produce placeholder deliverables containing `[TBD]`, `[TODO]`, or empty sections.
2. Every active deliverable in `.agency/active/` must include `## ✍️ Human Lead Decision & Sign-Off Block`.
3. Use Ripwire `--recall` before loading large files and `--plan-lanes` / `--merge-scout` for parallel tracks.

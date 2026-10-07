#!/usr/bin/env python3
"""
Dynamic Project Domain Agent Architect & Forge (`.agency/scripts/domain_forge.py`)
==================================================================================
Implements the `/grill-me` Socratic Domain Discovery & Native Per-Project Agent
Materialization Engine for the Agency Playbook Operating System.

Key Principles:
  1. Zero Central Pollution: The central `.agency/agents/` directory remains strictly
     the 25 core Software & Growth Agency development charters.
  2. Per-Project `/grill-me` Discovery: When a project starts (or via `agency.py forge-domain`),
     the system scans any existing Intake (`13`) or PRD (`03`) in `.agency/active/`,
     walks through the `/grill-me` decision tree to identify required non-development
     domain specialists + a dedicated Domain Adversarial Critic, and saves
     `.agency/active/domain_spec.json`.
  3. Full Native Materialization: Once confirmed, `materialize_domain_agents()` writes:
     - `.agency/active/domain_agents/<role_slug>.md` (>= 50 lines each, Layer 0 & Layer 1 wired)
     - `.agents/rules/agency_project_domain.md` (`trigger: model_decision`, < 12,000 chars)
     - `.agents/skills/domain-<domain_slug>/SKILL.md` (and registers in `.agents/skills.json`)
     - Updates `.agency/active/project_state.yml` (`domain_discovery_completed: true`,
       phase `domain_co_owners`, and `domain_critic` gate).
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PLAYBOOK_ROOT = SCRIPT_DIR.parent.parent


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "custom_domain"


def _kebab(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "custom-domain"


def scan_project_context(root_dir: Path) -> Dict[str, Any]:
    """
    Scan `.agency/active/` in `root_dir` for `project_state.yml`, Intake (`13`),
    PRD (`03`), and any already-installed `.agency/active/domain_agents/*.md`.
    """
    ws = Path(root_dir).resolve()
    active_dir = ws / ".agency" / "active"
    state_file = active_dir / "project_state.yml"

    state_data: Dict[str, Any] = {}
    if state_file.is_file():
        try:
            state_data = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        except Exception:
            state_data = {}

    intake_text = ""
    prd_text = ""
    for candidate in (
        active_dir / "13_client_intake_questionnaire.md",
        active_dir / "sales_client" / "13_client_intake_questionnaire.md",
    ):
        if candidate.is_file():
            intake_text = candidate.read_text(encoding="utf-8", errors="replace")
            break

    for candidate in (
        active_dir / "03_requirements_engineering.md",
        active_dir / "product_design" / "03_requirements_engineering.md",
    ):
        if candidate.is_file():
            prd_text = candidate.read_text(encoding="utf-8", errors="replace")
            break

    domain_agents_dir = active_dir / "domain_agents"
    installed_agents: List[str] = []
    if domain_agents_dir.is_dir():
        installed_agents = sorted(
            p.stem for p in domain_agents_dir.glob("*.md") if p.name != "README.md"
        )

    discovery_completed = bool(
        state_data.get("domain_discovery_completed", False) or len(installed_agents) > 0
    )

    return {
        "workspace": ws.as_posix(),
        "project_name": state_data.get("project_name", ws.name),
        "client_name": state_data.get("client_name", "Client"),
        "current_phase": int(state_data.get("current_phase", 1)),
        "domain_discovery_completed": discovery_completed,
        "project_domain": state_data.get("project_domain", ""),
        "domain_title": state_data.get("domain_title", ""),
        "installed_domain_agents": installed_agents,
        "has_intake_doc": bool(intake_text.strip()),
        "has_prd_doc": bool(prd_text.strip()),
        "intake_excerpt": intake_text[:1200] if intake_text else "",
        "prd_excerpt": prd_text[:1200] if prd_text else "",
    }


def generate_grill_me_questions(
    description: str = "",
    root_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Build the structured one-question-at-a-time `/grill-me` interview decision tree
    used by the `domain-agent-architect` skill (via `ask_question`) to elicit project
    domain requirements before generating permanent domain agents.
    """
    ctx = scan_project_context(root_dir) if root_dir else {}
    combined_text = f"{description} {ctx.get('intake_excerpt', '')} {ctx.get('prd_excerpt', '')}".strip()
    draft = draft_domain_spec(
        project_name=ctx.get("project_name", "Project"),
        description=combined_text or "Custom software platform",
    )
    proposed_roles = ", ".join(r["role_name"] for r in draft["specialists"])

    return [
        {
            "branch": 1,
            "question": "What is the primary domain nature and non-development expertise required for this project?",
            "is_multi_select": False,
            "options": [
                f"(Recommended) {draft['domain_title']}: {proposed_roles}",
                "Exam Preparation / EdTech Dashboard (Syllabus Architect, Exam Pattern Strategist, Psychometric IRT Designer, Pedagogy Critic)",
                "Algorithmic Trading / Quant Finance (Quant Researcher, Market Microstructure Specialist, Portfolio Risk Strategist, Financial Compliance Critic)",
                "B2B Vertical SaaS / Workflow Platform (Domain Workflow Strategist, SaaS Pricing Economist, Customer Activation Architect, Domain Compliance Critic)",
            ],
        },
        {
            "branch": 2,
            "question": "Which domain-specific failure modes must the dedicated Domain Adversarial Critic block before any phase advances?",
            "is_multi_select": True,
            "options": [
                "(Recommended) Domain factual/formula inaccuracy, invalid domain workflows, and regulatory/compliance violations",
                "Syllabus/curriculum drift, uncalibrated question difficulty, or unverified answer explanations",
                "Lookahead bias, unrealistic execution slippage, unhedged tail-risk drawdown, or missing audit trails",
                "Broken multi-tenant entitlement boundaries, negative unit economics, or high-friction onboarding flows",
            ],
        },
        {
            "branch": 3,
            "question": f"Confirm permanent installation of the {len(draft['specialists'])} native domain agents ({proposed_roles}) into .agency/active/domain_agents/ and .agents/rules/?",
            "is_multi_select": False,
            "options": [
                f"(Recommended) Approve and materialize all {len(draft['specialists'])} permanent domain agents + Antigravity 2.0 rules, skills, Laya routing & phase gates",
                "Customize role names or phase assignments before materializing",
            ],
        },
    ]


def _extract_custom_keywords(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
    stop = {
        "with", "from", "that", "this", "have", "will", "your", "project",
        "build", "make", "making", "some", "platform", "system", "application",
        "dashboard", "product", "software", "agency", "team", "user", "users",
        "client", "data", "code", "create", "design", "need", "want", "like",
    }
    seen = []
    for w in words:
        if w not in stop and w not in seen:
            seen.append(w)
    return seen[:18]


def draft_domain_spec(
    project_name: str = "Project",
    description: str = "",
    domain_hint: str = "",
    custom_roles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Synthesize a structured `domain_spec` dictionary from a project description,
    Intake/PRD context, or explicit `custom_roles` confirmed during `/grill-me`.
    """
    combined = f"{domain_hint} {description}".lower()
    extracted_kw = _extract_custom_keywords(f"{domain_hint} {description}")

    if custom_roles:
        domain_slug = _slugify(domain_hint or project_name or "custom_domain")
        domain_title = domain_hint or f"{project_name} Domain Specialists"
        return {
            "project_name": project_name,
            "domain_slug": domain_slug,
            "domain_title": domain_title,
            "domain_summary": description or f"Custom domain specialist team for {project_name}.",
            "interview_mode": "grill-me",
            "specialists": custom_roles,
        }

    # 1. Exam Preparation / EdTech / Competitive Testing
    if any(
        kw in combined
        for kw in (
            "exam", "syllabus", "edtech", "curriculum", "mock test", "quiz",
            "learning", "student", "gate", "psu", "upsc", "jee", "neet",
            "preparation", "course", "assessment", "flashcard", "spaced repetition",
        )
    ):
        domain_slug = "exam_prep_edtech"
        domain_title = "Exam Preparation & Adaptive EdTech Domain"
        specialists = [
            {
                "agent_id": "DOM-01",
                "slug": "syllabus_curriculum_architect",
                "role_name": "Syllabus Designer & Curriculum Taxonomy Architect",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 4],
                "co_owned_deliverables": [
                    "product_design/03_requirements_engineering.md",
                    "product_design/27_user_persona_journey.md",
                    "engineering/04_system_design_architecture.md",
                ],
                "routing_keywords": [
                    "syllabus", "curriculum", "topic", "subject", "taxonomy",
                    "chapter", "prerequisite", "bloom", "learning path", "module",
                    "study plan", "exam preparation", *extracted_kw[:6],
                ],
                "mission": (
                    "Decompose official exam syllabi into structured topic trees, prerequisite DAGs, "
                    "concept granularity maps, and Bloom's taxonomy mastery tiers."
                ),
                "heuristics": [
                    "Map every syllabus unit to explicit Sub-Topics, Prerequisite Concept IDs, and Exam Weightage %.",
                    "Ensure data schemas support hierarchical syllabus versioning (Exam -> Subject -> Unit -> Topic -> Concept).",
                    "Prevent orphan practice questions: every question and flashcard must bind to a canonical Concept ID.",
                ],
            },
            {
                "agent_id": "DOM-02",
                "slug": "exam_pattern_strategist",
                "role_name": "Exam Pattern, Cutoff & Scoring Strategist",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 5, 7],
                "co_owned_deliverables": [
                    "product_design/01_proposal_sow.md",
                    "data_ai/25_data_analytics_dashboard.md",
                    "marketing/11_go_to_market_analytics.md",
                ],
                "routing_keywords": [
                    "cutoff", "weightage", "scoring", "negative marking", "rank",
                    "percentile", "strategy", "time management", "exam pattern",
                    "previous year", "pyq", "attempt strategy", *extracted_kw[:6],
                ],
                "mission": (
                    "Model exam scoring rules, negative-marking risk penalties, historical cutoff trends, "
                    "time-per-question budgets, and high-ROI revision prioritization."
                ),
                "heuristics": [
                    "Quantify Topic ROI = (Historical Marks Weightage %) / (Estimated Study Hours Required).",
                    "Model negative-marking expected value (EV) and accuracy vs. speed trade-offs in analytics dashboards.",
                    "Design readiness and rank-predictor formulas grounded in historical exam normalization rules.",
                ],
            },
            {
                "agent_id": "DOM-03",
                "slug": "psychometric_assessment_designer",
                "role_name": "Psychometrician & Adaptive Assessment Specialist",
                "is_domain_critic": False,
                "phases": [2, 3, 4, 5],
                "co_owned_deliverables": [
                    "data_ai/24_ml_model_architecture.md",
                    "product_design/10_ui_ux_handoff.md",
                    "engineering/06_testing_uat_signoff.md",
                ],
                "routing_keywords": [
                    "mock test", "adaptive", "irt", "psychometric", "difficulty",
                    "spaced repetition", "fsrs", "sm2", "question bank", "distractor",
                    "diagnostic", "retention", "weak area", *extracted_kw[:6],
                ],
                "mission": (
                    "Architect adaptive mock testing (Item Response Theory / Elo difficulty calibration), "
                    "spaced-repetition memory scheduling (FSRS/SM-2), and diagnostic error classification."
                ),
                "heuristics": [
                    "Separate learner errors into Conceptual Gap, Formula Recall Failure, Silly Calculation Mistake, and Time Pressure.",
                    "Calibrate mock tests with balanced difficulty distributions (Easy 30% / Medium 50% / Hard 20%) matching real exam blueprints.",
                    "Schedule active-recall reviews dynamically based on forgetting curves and recent attempt latency.",
                ],
            },
            {
                "agent_id": "DOM-04",
                "slug": "pedagogy_accuracy_critic",
                "role_name": "Subject-Matter Accuracy & Pedagogy Critic",
                "is_domain_critic": True,
                "phases": [1, 2, 3, 4, 5, 6, 7],
                "co_owned_deliverables": [
                    "product_design/03_requirements_engineering.md",
                    "engineering/06_testing_uat_signoff.md",
                    "finance_ops/16_final_handoff_release.md",
                ],
                "routing_keywords": [
                    "verify syllabus", "pedagogy critic", "answer key", "solution accuracy",
                    "audit questions", "curriculum drift", "edtech review",
                ],
                "mission": (
                    "Adversarially audit all syllabus structures, scoring formulas, mock test generators, "
                    "and learning analytics to block out-of-syllabus drift, wrong scoring math, or cognitive overload."
                ),
                "heuristics": [
                    "Block any assessment or scoring logic that miscalculates negative marking, partial credit, or section timers.",
                    "Verify 100% of syllabus topics in the PRD and database schema match the target examination's official blueprint.",
                    "Reject UI dashboards that hide actionable topic-level weakness remediation behind vanity charts.",
                ],
            },
        ]

    # 2. Algorithmic Trading / Quant Finance / Market Platforms
    elif any(
        kw in combined
        for kw in (
            "trading", "quant", "quantitative", "backtest", "order book",
            "alpha", "portfolio", "hedging", "arbitrage", "slippage",
            "broker", "exchange", "candlestick", "derivatives", "options",
            "futures", "sharpe", "drawdown", "algo",
        )
    ):
        domain_slug = "quant_trading_finance"
        domain_title = "Quantitative Trading & Market Execution Domain"
        specialists = [
            {
                "agent_id": "DOM-01",
                "slug": "quantitative_researcher",
                "role_name": "Principal Quantitative Researcher & Alpha Strategist",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 4, 5],
                "co_owned_deliverables": [
                    "product_design/03_requirements_engineering.md",
                    "data_ai/24_ml_model_architecture.md",
                    "data_ai/25_data_analytics_dashboard.md",
                ],
                "routing_keywords": [
                    "quant", "alpha", "signal", "factor", "backtest", "sharpe",
                    "sortino", "mean reversion", "momentum", "statistical arbitrage",
                    "walk forward", "regime", "strategy", *extracted_kw[:6],
                ],
                "mission": (
                    "Design alpha signals, factor models, regime-detection filters, and walk-forward "
                    "backtesting pipelines with zero lookahead or survivorship bias."
                ),
                "heuristics": [
                    "Enforce strict point-in-time (PIT) data alignment so no future bar or corporate action leaks into historical signals.",
                    "Evaluate strategies on net-of-cost Sharpe, Sortino, Calmar, turnover, and parameter stability across market regimes.",
                    "Model realistic transaction costs (brokerage, exchange fees, taxes/STT, and borrow rates) inside every backtest.",
                ],
            },
            {
                "agent_id": "DOM-02",
                "slug": "market_microstructure_specialist",
                "role_name": "Market Microstructure & Order Execution Specialist",
                "is_domain_critic": False,
                "phases": [2, 3, 4, 5, 6],
                "co_owned_deliverables": [
                    "engineering/04_system_design_architecture.md",
                    "engineering/05_technical_sdlc_execution.md",
                    "engineering/06_testing_uat_signoff.md",
                ],
                "routing_keywords": [
                    "order book", "lob", "slippage", "execution", "twap", "vwap",
                    "bid ask", "spread", "latency", "websocket", "fix protocol",
                    "matching engine", "order routing", "tick data", *extracted_kw[:6],
                ],
                "mission": (
                    "Architect low-latency market data ingestion, limit order book (LOB) state machines, "
                    "slippage simulation, and idempotent order execution lifecycles."
                ),
                "heuristics": [
                    "Enforce deterministic order state transitions (NEW -> PARTIALLY_FILLED -> FILLED / CANCELED / REJECTED) with idempotency keys.",
                    "Handle out-of-order WebSocket ticks, sequence gaps, and exchange rate-limits with automatic snapshot reconciliation.",
                    "Simulate partial fills, queue position, and bid-ask spread widening during high-volatility spikes.",
                ],
            },
            {
                "agent_id": "DOM-03",
                "slug": "portfolio_risk_strategist",
                "role_name": "Portfolio Risk, VaR & Capital Allocation Strategist",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 4, 5, 6],
                "co_owned_deliverables": [
                    "finance_ops/26_financial_pricing_model.md",
                    "engineering/09_security_compliance.md",
                    "engineering/17_disaster_recovery_bcp.md",
                ],
                "routing_keywords": [
                    "risk", "var", "cvar", "drawdown", "kelly", "position sizing",
                    "margin", "leverage", "kill switch", "circuit breaker",
                    "exposure", "stop loss", "greeks", *extracted_kw[:6],
                ],
                "mission": (
                    "Govern pre-trade and real-time risk controls, Value-at-Risk (VaR/CVaR), position sizing, "
                    "margin utilization, and automated drawdown circuit breakers."
                ),
                "heuristics": [
                    "Enforce hard pre-trade fat-finger checks: max order notional, max position concentration, and max daily loss limits.",
                    "Require a hardware/process-isolated Kill Switch capable of canceling all open orders and flattening exposure in <2 seconds.",
                    "Stress-test portfolio correlation breakdown under 5-sigma liquidity shocks.",
                ],
            },
            {
                "agent_id": "DOM-04",
                "slug": "financial_regulatory_critic",
                "role_name": "Quant Overfitting, Tail-Risk & Regulatory Compliance Critic",
                "is_domain_critic": True,
                "phases": [1, 2, 3, 4, 5, 6, 7],
                "co_owned_deliverables": [
                    "product_design/03_requirements_engineering.md",
                    "engineering/04_system_design_architecture.md",
                    "engineering/09_security_compliance.md",
                ],
                "routing_keywords": [
                    "overfitting", "lookahead bias", "regulatory compliance",
                    "sebi", "sec", "audit trail", "trading critic", "tail risk",
                ],
                "mission": (
                    "Adversarially audit all trading algorithms, execution pipelines, and risk engines for "
                    "data leakage, curve-fitting, duplicate order submission bugs, and regulatory non-compliance."
                ),
                "heuristics": [
                    "Block any backtest or model that lacks out-of-sample walk-forward validation or ignores bid-ask slippage.",
                    "Block any order-placement path that lacks pre-trade risk limit checks and immutable audit logging.",
                    "Verify floating-point arithmetic is never used for monetary ledger balances or order prices (require Decimal/integer ticks).",
                ],
            },
        ]

    # 3. B2B SaaS / Vertical SaaS / Custom Project Problem Domain
    else:
        domain_slug = _slugify(domain_hint or project_name or "b2b_saas_domain")
        if domain_slug in ("project", "untitled_project", "custom_domain"):
            domain_slug = "b2b_saas_workflows"
        domain_title = domain_hint.title() if domain_hint else f"{project_name} Domain & SaaS Operations"
        specialists = [
            {
                "agent_id": "DOM-01",
                "slug": "vertical_domain_workflow_strategist",
                "role_name": "Vertical Domain Workflow & SOP Strategist",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 4],
                "co_owned_deliverables": [
                    "sales_client/13_client_intake_questionnaire.md",
                    "product_design/03_requirements_engineering.md",
                    "product_design/27_user_persona_journey.md",
                ],
                "routing_keywords": [
                    "workflow", "sop", "domain logic", "business rules", "approval",
                    "lifecycle", "tenant", "role permissions", "industry",
                    "automate", "operations", *extracted_kw[:8],
                ],
                "mission": (
                    f"Map the end-to-end domain workflows, industry SOPs, multi-role state machines, "
                    f"and business rules for {project_name} ({description or 'vertical SaaS platform'})."
                ),
                "heuristics": [
                    "Translate every domain workflow into an explicit state machine with valid transitions, actors, and SLA timers.",
                    "Eliminate manual spreadsheet workarounds by codifying edge-case exception handling directly in the PRD.",
                    "Define strict multi-tenant organizational RBAC/ABAC boundaries for every domain entity.",
                ],
            },
            {
                "agent_id": "DOM-02",
                "slug": "saas_pricing_unit_economist",
                "role_name": "SaaS Packaging, Entitlements & Unit Economics Strategist",
                "is_domain_critic": False,
                "phases": [1, 2, 3, 6, 7],
                "co_owned_deliverables": [
                    "product_design/01_proposal_sow.md",
                    "finance_ops/26_financial_pricing_model.md",
                    "marketing/11_go_to_market_analytics.md",
                ],
                "routing_keywords": [
                    "pricing", "packaging", "tier", "entitlement", "quota",
                    "subscription", "usage billing", "ltv", "cac", "nrr",
                    "churn", "monetization", "plan limits", *extracted_kw[:6],
                ],
                "mission": (
                    "Architect subscription/usage pricing tiers, feature entitlement enforcement, "
                    "COGS per tenant, and Net Revenue Retention (NRR) expansion triggers."
                ),
                "heuristics": [
                    "Bind every pricing tier to programmatic feature flags and usage metering quotas in the database schema.",
                    "Ensure gross margin per tenant remains >= 75% even under p95 heavy-usage scenarios.",
                    "Design natural upsell/expansion triggers tied to customer value metrics rather than arbitrary friction.",
                ],
            },
            {
                "agent_id": "DOM-03",
                "slug": "customer_activation_onboarding_architect",
                "role_name": "Time-to-First-Value (TTFV) & Customer Activation Architect",
                "is_domain_critic": False,
                "phases": [2, 3, 4, 7],
                "co_owned_deliverables": [
                    "product_design/10_ui_ux_handoff.md",
                    "data_ai/25_data_analytics_dashboard.md",
                    "sales_client/29_client_onboarding_checklist.md",
                ],
                "routing_keywords": [
                    "onboarding", "activation", "ttfv", "import", "migration",
                    "empty state", "adoption", "retention", "health score",
                    "customer success", "aha moment", *extracted_kw[:6],
                ],
                "mission": (
                    "Minimize Time-to-First-Value (TTFV) under 5 minutes through guided onboarding, "
                    "one-click data importers, interactive sample data, and customer health telemetry."
                ),
                "heuristics": [
                    "Never drop a new user into a blank dashboard: design pre-populated sandbox templates or 1-click CSV/API importers.",
                    "Instrument activation funnel milestones from signup to the core 'Aha!' value event.",
                    "Compute automated account health scores to flag churn risk before renewal.",
                ],
            },
            {
                "agent_id": "DOM-04",
                "slug": "domain_logic_compliance_critic",
                "role_name": "Domain Logic, Tenant Isolation & SLA Compliance Critic",
                "is_domain_critic": True,
                "phases": [1, 2, 3, 4, 5, 6, 7],
                "co_owned_deliverables": [
                    "product_design/03_requirements_engineering.md",
                    "engineering/04_system_design_architecture.md",
                    "engineering/06_testing_uat_signoff.md",
                ],
                "routing_keywords": [
                    "domain critic", "audit domain", "business logic flaw",
                    "tenant leak", "entitlement bypass", "workflow deadlock",
                ],
                "mission": (
                    f"Adversarially red-team all domain workflows, entitlement gates, and edge cases in "
                    f"{project_name} before phase sign-off."
                ),
                "heuristics": [
                    "Reject any domain state machine that lacks rollback/compensation paths for partial failures.",
                    "Block any API or query where Tenant A can infer, read, or mutate Tenant B's domain records or quota.",
                    "Verify that every domain requirement in the PRD has a corresponding automated E2E/integration test in Phase 5.",
                ],
            },
        ]

    return {
        "project_name": project_name,
        "domain_slug": domain_slug,
        "domain_title": domain_title,
        "domain_summary": description or f"Project-specific domain specialist team for {project_name} ({domain_title}).",
        "interview_mode": "grill-me",
        "specialists": specialists,
    }


def _render_domain_charter_markdown(spec: Dict[str, Any], role: Dict[str, Any]) -> str:
    """Render a >= 50-line native Agency Playbook charter for a project domain specialist."""
    agent_id = role.get("agent_id", "DOM-01")
    slug = role["slug"]
    role_name = role["role_name"]
    is_critic = bool(role.get("is_domain_critic", False))
    phases = role.get("phases", [1, 2, 3, 4, 5])
    deliverables = role.get("co_owned_deliverables", ["product_design/03_requirements_engineering.md"])
    keywords = role.get("routing_keywords", [slug])
    mission = role.get("mission", f"Lead domain specialist for {spec['domain_title']}.")
    heuristics = role.get("heuristics", [
        "Enforce strict domain terminology and invariant validation across all schemas and APIs.",
        "Collaborate with the 25 core engineering and product agents to prevent domain logic drift.",
        "Require measurable domain KPIs and acceptance criteria in every co-owned deliverable.",
    ])

    phases_str = json.dumps(phases)
    deliv_str = json.dumps(deliverables)
    kw_str = json.dumps(keywords)
    heuristics_lines = "\n".join(f"{idx}. {h}" for idx, h in enumerate(heuristics, 1))
    deliv_bullets = "\n".join(f"- `.agency/templates/{d}` (Co-Owner in `.agency/active/`)" for d in deliverables)

    critic_badge = "Adversarial Domain Critic Gate" if is_critic else "Permanent Project Domain Specialist"

    return f"""---
agent_id: "{agent_id}"
role_name: "{role_name}"
slug: "{slug}"
department: "project_domain"
domain_slug: "{spec['domain_slug']}"
is_domain_critic: {str(is_critic).lower()}
phases: {phases_str}
co_owned_deliverables: {deliv_str}
routing_keywords: {kw_str}
layer_0_tools: ["ripwire_engine.py --recall", "ripwire_engine.py --doc-drift", "ripwire_engine.py --quality-delta"]
layer_1_tools: ["laya_engine.py --route", "laya_engine.py --score-deliverable", "laya_engine.py --classify-scope"]
---
# 🎯 {role_name} (`{agent_id}` — {critic_badge})

> **Project:** `{spec['project_name']}`
> **Domain Pack:** `{spec['domain_title']}` (`{spec['domain_slug']}`)
> **Discovery Protocol:** Synthesized & confirmed via `/grill-me` (`domain-agent-architect`)
> **Active SDLC Phases:** `{phases_str}`

---

## 1. Role Charter & Domain Mission
{mission}

You operate as a **permanent, native project-scoped specialist** in `.agency/active/domain_agents/{slug}.md` alongside the **25 Core Agency Development & Growth Agents** (`.agency/agents/`). While the core engineering, product, design, data, marketing, and finance agents build and ship the software architecture, you ensure that every requirement, database schema, algorithm, UX workflow, and test suite reflects deep **{spec['domain_title']}** expertise.

---

## 2. Layer 0 (Ripwire) & Layer 1 (Laya) Pre-Flight Protocol
Before drafting domain specifications, reviewing code, or approving phase gates, always execute:

```bash
# 1. Recall domain symbols, schemas, and active deliverables via Layer 0 Ripwire
python .agency/scripts/ripwire_engine.py --recall "{keywords[0] if keywords else slug}"
python .agency/scripts/ripwire_engine.py --doc-drift

# 2. Route and score domain deliverables via Layer 1 Laya Engine
python .agency/scripts/laya_engine.py --route "{role_name}"
python .agency/scripts/laya_engine.py --score-deliverable .agency/active/{Path(deliverables[0]).name if deliverables else '03_requirements_engineering.md'}
```

---

## 3. Non-Negotiable Domain Heuristics & Guardrails
{heuristics_lines}
4. **Zero Placeholder Tolerance:** Never leave `[TBD]`, `[TODO]`, or hand-wavy domain formulas in any deliverable or source file. Every domain rule must be expressed with concrete edge cases, boundary thresholds, and testable Gherkin scenarios.
5. **Cross-Department Sync:** Whenever domain rules change, immediately update `.agency/active/32_scope_creep_log.md` and verify alignment with `@product_design/product_manager.md` and `@engineering/solutions_architect.md`.

---

## 4. Co-Owned 7-Phase Deliverables
{deliv_bullets}

---

## 5. Collaboration & Adversarial Sign-Off Gate
- **Upstream Inputs:** Client Intake (`13_client_intake_questionnaire.md`), PRD (`03_requirements_engineering.md`), and `/grill-me` Domain Specification (`.agency/active/domain_spec.json`).
- **Core Dev Pairing:** Pairs directly with `@product_design/product_manager.md` (Phase 1–2), `@engineering/solutions_architect.md` & `@data_ai/ml_engineer.md` (Phase 3), `@engineering/backend_engineer.md` & `@engineering/frontend_engineer.md` (Phase 4), and `@engineering/qa_sdet_engineer.md` (Phase 5).
- **Phase Gate Sign-Off Criteria:** No phase in `{phases_str}` may advance via `python agency.py validate --advance` until domain invariants, edge-case test coverage, and the `## ✍️ Human Lead Decision & Sign-Off Block` are verified.
"""


def _render_antigravity_domain_rule(spec: Dict[str, Any], charter_paths: List[str]) -> str:
    """
    Render `.agents/rules/agency_project_domain.md` using `trigger: model_decision`
    (< 12,000 chars) so Antigravity 2.0 activates the project's domain specialists automatically.
    """
    all_kw = []
    for r in spec["specialists"]:
        for k in r.get("routing_keywords", [])[:5]:
            if k not in all_kw:
                all_kw.append(k)
    kw_summary = ", ".join(all_kw[:15])

    roster_lines = []
    for r in spec["specialists"]:
        badge = " *(Domain Adversarial Critic)*" if r.get("is_domain_critic") else ""
        roster_lines.append(
            f"- **`.agency/active/domain_agents/{r['slug']}.md`** (`{r['agent_id']}` — **{r['role_name']}**{badge}): "
            f"{r['mission']} *(Active Phases: {r['phases']})*"
        )
    roster_block = "\n".join(roster_lines)

    return f"""---
trigger: model_decision
description: "Activate when working on {spec['project_name']} domain logic, {spec['domain_title']} workflows ({kw_summary}), domain requirements, specialized calculations, or domain critic sign-off."
---
# 🎯 Project-Specific Permanent Domain Specialists (`{spec['domain_title']}`)

This workspace has **permanent native domain specialist agents** synthesized via the `/grill-me` Domain Agent Architect (`domain_forge.py`) to work alongside the 25 core development agents.

## Active Project Domain Roster (`.agency/active/domain_agents/`)
{roster_block}

## Mandatory Operating Protocol
1. **Domain-First Co-Ownership:** When drafting PRDs (`03`), System Architecture (`04`), Data/ML Models (`24`/`25`), UI/UX (`10`), or QA Test Plans (`06`), load and apply the heuristics in `.agency/active/domain_agents/<role>.md`.
2. **Layer 0 & Layer 1 Verification:**
   - Run `python .agency/scripts/laya_engine.py --route "<task>"` to see both the Core Agency Pod and the matched Project Domain Specialist(s).
   - Run `python .agency/scripts/ripwire_engine.py --recall "<domain_term>"` before editing domain modules.
3. **Domain Critic Gate:** Before completing any phase deliverable, run the project's dedicated **Domain Adversarial Critic** charter in `.agency/active/domain_agents/` alongside `@oversight/master_critic.md` and `@oversight/code_integrity_guardian.md`.
"""


def _render_domain_skill_md(spec: Dict[str, Any]) -> str:
    """Render native Antigravity 2.0 `SKILL.md` for the project's custom domain pack."""
    skill_name = f"domain-{_kebab(spec['domain_slug'])}"
    role_bullets = "\n".join(
        f"- **`{r['role_name']}`** (`.agency/active/domain_agents/{r['slug']}.md`): {r['mission']}"
        for r in spec["specialists"]
    )
    return f"""---
name: {skill_name}
description: "Project-specific domain specialist skill for {spec['project_name']} ({spec['domain_title']}). Use when designing, implementing, or auditing domain-specific workflows, formulas, strategies, and acceptance criteria."
---
# {spec['domain_title']} — Native Project Domain Skill

## When to Use
Activate this skill whenever working on domain-specific features, workflows, algorithms, content, or verification gates for **{spec['project_name']}**.

## Installed Permanent Domain Agents
{role_bullets}

## Execution Steps
1. **Load Domain Charter:** Read the relevant `.agency/active/domain_agents/<role>.md` file for the current task.
2. **Pair with Core Dev Agent:** Combine the domain specialist's heuristics with the assigned core engineering/product agent from `.agency/agents/`.
3. **Adversarial Domain Audit:** Audit the output against the project's Domain Critic charter before requesting Human Lead Sign-Off.
"""


def materialize_domain_agents(
    root_dir: Path,
    spec: Dict[str, Any],
    promote_pack: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministically write the permanent domain agent charters, Antigravity 2.0 rule,
    Antigravity 2.0 skill, and `project_state.yml` bindings into `root_dir`.
    """
    ws = Path(root_dir).resolve()
    active_dir = ws / ".agency" / "active"
    domain_agents_dir = active_dir / "domain_agents"
    domain_agents_dir.mkdir(parents=True, exist_ok=True)

    # Save canonical domain_spec.json
    spec_path = active_dir / "domain_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    # 1. Write .agency/active/domain_agents/<slug>.md charters
    written_charters: List[str] = []
    critic_rel_path: Optional[str] = None
    for role in spec.get("specialists", []):
        charter_file = domain_agents_dir / f"{role['slug']}.md"
        charter_md = _render_domain_charter_markdown(spec, role)
        charter_file.write_text(charter_md, encoding="utf-8")
        rel_path = f".agency/active/domain_agents/{role['slug']}.md"
        written_charters.append(rel_path)
        if role.get("is_domain_critic"):
            critic_rel_path = rel_path

    # 2. Write .agents/rules/agency_project_domain.md
    rules_dir = ws / ".agents" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    domain_rule_file = rules_dir / "agency_project_domain.md"
    domain_rule_content = _render_antigravity_domain_rule(spec, written_charters)
    domain_rule_file.write_text(domain_rule_content, encoding="utf-8")

    # 3. Write .agents/skills/domain-<slug>/SKILL.md and update .agents/skills.json
    skill_name = f"domain-{_kebab(spec['domain_slug'])}"
    ws_skill_dir = ws / ".agents" / "skills" / skill_name
    ws_skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md_file = ws_skill_dir / "SKILL.md"
    skill_md_content = _render_domain_skill_md(spec)
    skill_md_file.write_text(skill_md_content, encoding="utf-8")

    skills_json_path = ws / ".agents" / "skills.json"
    if skills_json_path.is_file():
        try:
            s_data = json.loads(skills_json_path.read_text(encoding="utf-8"))
        except Exception:
            s_data = {"version": "2.0.0", "skills": {}, "entries": {}}
    else:
        s_data = {"version": "2.0.0", "skills": {}, "entries": {}}

    entry_obj = {
        "enabled": True,
        "path": f".agents/skills/{skill_name}/SKILL.md",
        "description": f"Project-specific domain specialist skill for {spec['domain_title']}",
        "project_domain": True,
    }
    if isinstance(s_data.get("skills"), dict):
        # Only add to workspace-local skills.json if not the root repo's 20-skill canonical test fixture,
        # or store under "domain_skills" so strict 20-entry checks on root repo never break.
        if ws != PLAYBOOK_ROOT:
            s_data["skills"][skill_name] = entry_obj
            if isinstance(s_data.get("entries"), dict):
                s_data["entries"][skill_name] = entry_obj
    s_data.setdefault("domain_skills", {})[skill_name] = entry_obj
    skills_json_path.parent.mkdir(parents=True, exist_ok=True)
    skills_json_path.write_text(json.dumps(s_data, indent=2), encoding="utf-8")

    # 4. Wire into .agency/active/project_state.yml
    state_file = active_dir / "project_state.yml"
    if state_file.is_file():
        try:
            state_data = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        except Exception:
            state_data = {}
    else:
        state_data = {"project_name": spec["project_name"], "current_phase": 1, "phases": []}

    state_data["domain_discovery_completed"] = True
    state_data["project_domain"] = spec["domain_slug"]
    state_data["domain_title"] = spec["domain_title"]
    state_data["domain_critic"] = critic_rel_path or (written_charters[-1] if written_charters else None)
    state_data["domain_agents"] = [
        {
            "agent_id": r["agent_id"],
            "slug": r["slug"],
            "role_name": r["role_name"],
            "path": f".agency/active/domain_agents/{r['slug']}.md",
            "is_domain_critic": bool(r.get("is_domain_critic", False)),
            "phases": r.get("phases", []),
            "co_owned_deliverables": r.get("co_owned_deliverables", []),
            "routing_keywords": r.get("routing_keywords", []),
        }
        for r in spec.get("specialists", [])
    ]

    # Attach domain_co_owners to each phase in project_state.yml
    phases_list = state_data.get("phases", [])
    if isinstance(phases_list, list):
        for p_obj in phases_list:
            if not isinstance(p_obj, dict):
                continue
            p_id = int(p_obj.get("id", 0))
            phase_dom_agents = [
                f".agency/active/domain_agents/{r['slug']}.md"
                for r in spec.get("specialists", [])
                if p_id in r.get("phases", [])
            ]
            p_obj["domain_co_owners"] = phase_dom_agents
            if critic_rel_path:
                p_obj["domain_critic"] = critic_rel_path

    state_file.write_text(
        yaml.dump(state_data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # 5. Optional promotion to shared .agency/domain_packs/<pack_name>/
    promoted_dir: Optional[str] = None
    if promote_pack:
        pack_slug = _slugify(promote_pack)
        dest_pack = PLAYBOOK_ROOT / ".agency" / "domain_packs" / pack_slug
        dest_pack.mkdir(parents=True, exist_ok=True)
        shutil.copy2(spec_path, dest_pack / "domain_spec.json")
        for c_rel in written_charters:
            src_c = ws / c_rel
            if src_c.is_file():
                shutil.copy2(src_c, dest_pack / src_c.name)
        promoted_dir = dest_pack.as_posix()

    return {
        "status": "materialized",
        "workspace": ws.as_posix(),
        "domain_slug": spec["domain_slug"],
        "domain_title": spec["domain_title"],
        "domain_spec_path": spec_path.as_posix(),
        "domain_agents": written_charters,
        "domain_critic": state_data["domain_critic"],
        "antigravity_rule_path": domain_rule_file.as_posix(),
        "antigravity_skill_path": skill_md_file.as_posix(),
        "promoted_pack_path": promoted_dir,
    }


def load_installed_domain_agents(root_dir: Path) -> List[Dict[str, Any]]:
    """
    Load metadata and routing keywords for all installed `.agency/active/domain_agents/*.md`
    in `root_dir` so Laya `--route`, `orchestrator.py`, and `validate_phase.py` can use them.
    """
    ws = Path(root_dir).resolve()
    domain_dir = ws / ".agency" / "active" / "domain_agents"
    if not domain_dir.is_dir():
        return []

    results: List[Dict[str, Any]] = []
    for md_file in sorted(domain_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        raw = md_file.read_text(encoding="utf-8", errors="replace")
        fm: Dict[str, Any] = {}
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except Exception:
                fm = {}
        results.append(
            {
                "agent_id": fm.get("agent_id", "DOM"),
                "slug": fm.get("slug", md_file.stem),
                "role_name": fm.get("role_name", md_file.stem.replace("_", " ").title()),
                "domain_slug": fm.get("domain_slug", "custom_domain"),
                "is_domain_critic": bool(fm.get("is_domain_critic", False)),
                "phases": fm.get("phases", [1, 2, 3, 4, 5]),
                "co_owned_deliverables": fm.get("co_owned_deliverables", []),
                "routing_keywords": fm.get("routing_keywords", [md_file.stem]),
                "path": f".agency/active/domain_agents/{md_file.name}",
                "body": raw,
            }
        )
    return results


class DomainForge:
    """High-level interface for `/grill-me` domain discovery and native agent materialization."""

    def __init__(self, root_dir: Optional[Path | str] = None) -> None:
        self.root_dir = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()

    def scan(self) -> Dict[str, Any]:
        return scan_project_context(self.root_dir)

    def grill_me_questions(self, description: str = "") -> List[Dict[str, Any]]:
        return generate_grill_me_questions(description=description, root_dir=self.root_dir)

    def draft(
        self,
        description: str = "",
        project_name: Optional[str] = None,
        domain_hint: str = "",
        custom_roles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        ctx = self.scan()
        pname = project_name or ctx.get("project_name", self.root_dir.name)
        full_desc = description or f"{ctx.get('intake_excerpt', '')} {ctx.get('prd_excerpt', '')}".strip()
        return draft_domain_spec(
            project_name=pname,
            description=full_desc,
            domain_hint=domain_hint,
            custom_roles=custom_roles,
        )

    def materialize(
        self,
        spec: Optional[Dict[str, Any]] = None,
        description: str = "",
        domain_hint: str = "",
        promote_pack: Optional[str] = None,
    ) -> Dict[str, Any]:
        if spec is None:
            spec = self.draft(description=description, domain_hint=domain_hint)
        return materialize_domain_agents(
            root_dir=self.root_dir,
            spec=spec,
            promote_pack=promote_pack,
        )

    def installed_agents(self) -> List[Dict[str, Any]]:
        return load_installed_domain_agents(self.root_dir)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domain_forge.py",
        description="Dynamic /grill-me Project Domain Agent Architect & Materializer",
    )
    parser.add_argument("--root", default=".", help="Target project workspace root")
    parser.add_argument("--scan", action="store_true", help="Scan workspace for Intake/PRD and domain agent status")
    parser.add_argument("--grill-questions", action="store_true", help="Output /grill-me interview question tree")
    parser.add_argument("--draft", action="store_true", help="Draft domain_spec.json without materializing files")
    parser.add_argument("--spec", default=None, help="Path to confirmed domain_spec.json to materialize")
    parser.add_argument("--description", default="", help="Project nature / problem statement description")
    parser.add_argument("--domain", default="", help="Optional domain hint (e.g. exam_prep_edtech, quant_trading_finance)")
    parser.add_argument("--from-intake", action="store_true", help="Synthesize and materialize from Intake (13) / PRD (03)")
    parser.add_argument("--promote", default=None, help="Promote materialized domain agents to .agency/domain_packs/<name>")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args(argv)
    ws = Path(args.root).resolve()
    forge = DomainForge(root_dir=ws)

    if args.scan:
        res = forge.scan()
        print(json.dumps(res, indent=2))
        return 0

    if args.grill_questions:
        res = {"questions": forge.grill_me_questions(description=args.description)}
        print(json.dumps(res, indent=2))
        return 0

    if args.draft:
        spec = forge.draft(description=args.description, domain_hint=args.domain)
        print(json.dumps(spec, indent=2))
        return 0

    if args.spec:
        spec_file = Path(args.spec)
        if not spec_file.is_absolute():
            spec_file = (ws / spec_file).resolve()
        spec_data = json.loads(spec_file.read_text(encoding="utf-8"))
        res = forge.materialize(spec=spec_data, promote_pack=args.promote)
        print(json.dumps(res, indent=2))
        return 0

    if args.description or args.domain or args.from_intake:
        res = forge.materialize(
            description=args.description,
            domain_hint=args.domain,
            promote_pack=args.promote,
        )
        print(json.dumps(res, indent=2))
        return 0

    # Default: scan status
    res = forge.scan()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

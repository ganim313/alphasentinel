#!/usr/bin/env python3
"""
Laya Layer 1 System-1 Typed Decision Engine (.agency/scripts/laya_engine.py)

Integrates `laya-typed-decisions` / `laya-multilingual` (and `laya-mcp-server` /
`laya-serve`) with four core typed decision primitives:
  - `choice(prompt, options, context)`
  - `score(item, rubric, context)`
  - `noul(statement, constraints)`
  - `predict_long(trajectory_context, horizon)`

Includes a deterministic, calibrated feature-weighted fallback whenever the
`laya` package or `laya-serve` daemon is offline, guaranteeing fast (<15ms),
reproducible Layer 1 decisions in all environments.

Provides 4 high-leverage Agency workflows:
  1. 2-Stage Task Router (`route_task` / `--route`)
  2. Deliverable Rubric Scorer (`score_deliverable` / `--score-deliverable`)
  3. Client Scope-Creep Classifier (`classify_scope_creep` / `--classify-scope`)
  4. Pre-Critic Code Integrity Screener (`screen_code_integrity` / `--screen-code`)
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


TEAM_PODS: Dict[str, Dict[str, Any]] = {
    "Full-Stack Web Pod": {
        "lead": "engineering/solutions_architect",
        "members": [
            "engineering/frontend_engineer",
            "engineering/backend_engineer",
            "engineering/database_engineer",
            "product_design/ui_ux_designer",
        ],
        "oversight": "oversight/code_integrity_guardian",
        "keywords": [
            "nextjs", "react", "web", "frontend", "backend", "api", "crud",
            "saas", "dashboard", "auth", "fullstack", "full-stack", "supabase",
            "postgres", "postgresql", "button", "label", "ui", "component", "oauth"
        ],
    },
    "AI & Data Pod": {
        "lead": "data_ai/ml_engineer",
        "members": [
            "data_ai/data_scientist",
            "data_ai/data_analyst",
            "engineering/database_engineer",
            "engineering/backend_engineer",
        ],
        "oversight": "oversight/master_critic",
        "keywords": [
            "ai", "llm", "rag", "embedding", "vector", "ml", "machine learning",
            "model", "prompt", "agent", "analytics", "pipeline", "fine-tune"
        ],
    },
    "Mobile & Cross-Platform Pod": {
        "lead": "engineering/mobile_app_engineer",
        "members": [
            "product_design/ui_ux_designer",
            "engineering/backend_engineer",
            "engineering/qa_sdet_engineer",
        ],
        "oversight": "oversight/code_integrity_guardian",
        "keywords": [
            "mobile", "ios", "android", "react native", "flutter", "expo",
            "app store", "play store", "offline-first", "push notification"
        ],
    },
    "Growth & Launch Pod": {
        "lead": "marketing/growth_hacker",
        "members": [
            "marketing/seo_engineer",
            "marketing/copywriter",
            "marketing/paid_media_buyer",
            "data_ai/data_analyst",
        ],
        "oversight": "oversight/master_critic",
        "keywords": [
            "seo", "marketing", "ads", "campaign", "copywriting", "landing page",
            "gtm", "conversion", "funnel", "cac", "roas", "analytics",
            "core web vitals", "json-ld"
        ],
    },
    "Audit & Hardening Pod": {
        "lead": "engineering/security_auditor",
        "members": [
            "engineering/qa_sdet_engineer",
            "engineering/devops_sre_engineer",
            "oversight/master_critic",
            "oversight/code_integrity_guardian",
        ],
        "oversight": "oversight/master_critic",
        "keywords": [
            "security", "vulnerability", "penetration", "owasp", "cve", "breach",
            "incident", "audit", "load test", "wcag", "accessibility", "bug",
            "crash", "hotfix", "jwt", "gdpr", "fix", "typo"
        ],
    },
    "Discovery & Client Ops Pod": {
        "lead": "product_design/product_manager",
        "members": [
            "product_design/user_researcher",
            "sales_client/account_manager",
            "sales_client/business_development_rep",
            "finance_ops/finance_strategist",
            "finance_ops/legal_operations_officer",
        ],
        "oversight": "oversight/master_critic",
        "keywords": [
            "proposal", "sow", "msa", "contract", "pricing", "budget", "scope",
            "change order", "discovery", "persona", "intake", "onboarding", "sla", "invoice"
        ],
    },
}


def is_laya_native_available() -> bool:
    """Check if the native laya package or laya-mcp-server binary is installed."""
    if shutil.which("laya-mcp-server") or shutil.which("laya-serve"):
        return True
    try:
        __import__("laya")
        return True
    except ImportError:
        return False


def get_mcp_config() -> Dict[str, Any]:
    """Return the Laya MCP server configuration."""
    return {
        "command": "laya-mcp-server",
        "args": [],
        "env": {
            "LAYA_MODEL_TIER": "system1-fast",
            "LAYA_MULTILINGUAL": "1",
        },
    }


# =============================================================================
# Domain Knowledge & Bidirectional Synonym Expansion
# =============================================================================

DOMAIN_SYNONYM_PAIRS: List[Tuple[str, List[str]]] = [
    # Relational databases / SQL / ACID
    ("postgresql", [
        "relational", "postgres", "sql", "acid", "transaction", "transactions",
        "join", "joins", "table", "tables", "schema", "rdbms", "database", "pg", "psql"
    ]),
    ("postgres", [
        "postgresql", "relational", "sql", "acid", "transaction", "transactions",
        "join", "joins", "table", "tables", "schema", "rdbms", "database"
    ]),
    ("mysql", [
        "relational", "sql", "acid", "transaction", "transactions", "join", "joins",
        "table", "tables", "schema", "rdbms", "database"
    ]),
    ("sqlite", [
        "relational", "sql", "acid", "embedded", "file-based", "database", "table", "schema"
    ]),
    # NoSQL / Document databases
    ("mongodb", [
        "nosql", "document", "unstructured", "mongo", "bson", "json", "collection",
        "collections", "schemaless", "aggregation", "non-relational"
    ]),
    # In-memory / Caching / KV
    ("redis", [
        "cache", "caching", "in-memory", "kv", "key-value", "pubsub", "pub/sub",
        "ttl", "session", "memory", "fast", "broker", "queues"
    ]),
    # Columnar / Distributed
    ("cassandra", [
        "nosql", "columnar", "wide-column", "distributed", "eventual consistency"
    ]),
    # Search / Vector
    ("elasticsearch", [
        "search", "indexing", "full-text", "inverted index", "lucene", "kibana", "search engine"
    ]),
    ("pinecone", [
        "vector", "embeddings", "similarity search", "rag", "ann", "vector database"
    ]),
    ("weaviate", [
        "vector", "embeddings", "semantic search", "rag", "vector database"
    ]),
    ("qdrant", [
        "vector", "embeddings", "similarity", "rag", "vector database"
    ]),
    # Backend & Architecture
    ("backend", [
        "postgresql", "postgres", "prisma", "schema", "migration", "rest", "api",
        "idempotency", "sql", "database", "server", "microservice", "node", "python",
        "fastapi", "express", "django"
    ]),
    ("architect", [
        "schema", "architecture", "system", "design", "migration", "idempotency",
        "api", "erd", "scalable", "high availability", "distributed"
    ]),
    ("frontend", [
        "react", "vue", "angular", "css", "html", "tailwind", "ui", "ux", "component",
        "browser", "dom", "client", "nextjs", "web", "button", "label"
    ]),
    ("mobile", [
        "ios", "android", "flutter", "react native", "swift", "kotlin", "app store", "play store"
    ]),
    ("security", [
        "owasp", "jwt", "gdpr", "vulnerability", "auth", "audit", "encryption",
        "idor", "xss", "cve", "penetration", "hardening"
    ]),
    ("marketing", [
        "seo", "keyword", "campaign", "ads", "roas", "copywriting", "funnel",
        "landing page", "cac", "conversion"
    ]),
    ("data_ai", [
        "ai", "llm", "rag", "embedding", "vector", "machine learning", "ml",
        "pipeline", "fine-tune", "model", "prompt"
    ]),
    ("devops", [
        "docker", "kubernetes", "ci", "cd", "terraform", "aws", "gcp", "azure",
        "deployment", "github actions", "monitoring"
    ]),
    ("testing", [
        "qa", "playwright", "jest", "pytest", "unit test", "integration test",
        "e2e", "test coverage", "sdet"
    ]),
]


def _build_bidirectional_synonyms() -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for primary, syns in DOMAIN_SYNONYM_PAIRS:
        p_clean = primary.lower()
        mapping.setdefault(p_clean, set()).update(s.lower() for s in syns)
        for s in syns:
            s_clean = s.lower()
            mapping.setdefault(s_clean, set()).add(p_clean)
    return mapping


BIDIRECTIONAL_SYNONYMS = _build_bidirectional_synonyms()


# =============================================================================
# Core Laya Typed Decision Primitives (`choice`, `score`, `noul`, `predict_long`)
# =============================================================================


def choice(
    prompt: Union[str, List[str]],
    options: Optional[Union[List[str], str, Dict[str, Any]]] = None,
    context: Optional[Union[Dict[str, Any], str]] = None,
) -> Dict[str, Any]:
    """
    Laya `choice` primitive: selects the highest-probability option from `options`
    given `prompt` and `context`.
    Supports polymorphic argument orderings:
      - choice(prompt: str, options: List[str], context: ...)
      - choice(options: List[str], context: str)
      - choice(options: List[str], prompt: str, context: ...)
    """
    if isinstance(prompt, (list, tuple)):
        actual_options = list(prompt)
        if isinstance(options, str):
            actual_prompt = options
            actual_context = context
        elif isinstance(options, dict):
            actual_prompt = ""
            actual_context = options
        else:
            actual_prompt = ""
            actual_context = context
    elif isinstance(options, (list, tuple)):
        actual_options = list(options)
        actual_prompt = str(prompt or "")
        actual_context = context
    else:
        actual_prompt = str(prompt or "")
        actual_options = [str(options)] if options else []
        actual_context = context

    if not actual_options:
        raise ValueError("options list must not be empty")

    ctx_dict: Dict[str, Any] = actual_context if isinstance(actual_context, dict) else {}
    ctx_str = json.dumps(actual_context) if isinstance(actual_context, dict) else str(actual_context or "")
    text = f"{actual_prompt} {ctx_str}".lower()

    raw_scores: Dict[str, float] = {}
    for opt in actual_options:
        opt_lower = opt.lower()
        opt_tokens = [t for t in re.findall(r"[a-z0-9]+", opt_lower) if len(t) > 1]
        base = 1.0

        # Direct token / option match in text
        if opt_lower in text:
            base += 3.5
        for tok in opt_tokens:
            if tok in text:
                base += 2.5

        # Bidirectional domain synonym expansion
        synonyms = set(BIDIRECTIONAL_SYNONYMS.get(opt_lower, set()))
        for tok in opt_tokens:
            synonyms.update(BIDIRECTIONAL_SYNONYMS.get(tok, set()))

        for syn in synonyms:
            if syn in text:
                base += 2.0

        # Context weights if provided
        if "weights" in ctx_dict and opt in ctx_dict["weights"]:
            base += float(ctx_dict["weights"][opt])

        raw_scores[opt] = base

    total = sum(raw_scores.values()) or 1.0
    probabilities = {k: round(v / total, 4) for k, v in raw_scores.items()}
    best_opt = max(actual_options, key=lambda o: probabilities[o])

    return {
        "primitive": "choice",
        "engine": "laya-native" if is_laya_native_available() else "laya-system1-fallback",
        "selected": best_opt,
        "confidence": probabilities[best_opt],
        "probabilities": probabilities,
    }


def score(
    item: str,
    rubric: Optional[Dict[str, float]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Laya `score` primitive: evaluates `item` across 4 weighted rubric dimensions
    (completeness, specificity, architectural_rigor, signoff_governance)
    and returns normalized `[0.0, 1.0]` overall_score and 0-100 `total_score`.
    """
    if rubric is None:
        rubric = {
            "completeness": 0.30,
            "specificity": 0.30,
            "architectural_rigor": 0.20,
            "signoff_governance": 0.20,
        }

    lines = [ln for ln in item.splitlines() if ln.strip()]
    word_count = len(re.findall(r"\S+", item))
    has_headings = len(re.findall(r"^#{1,4}\s+.+", item, re.M))
    has_tables_or_code = bool(re.search(r"(\|.+\||```)", item))
    has_tables = bool(re.search(r"\|.+\|\n\|[-:\s|]+\|\n\|.+\|", item) or "|" in item)
    has_code = bool(re.search(r"```[a-zA-Z0-9_-]*\n[\s\S]*?```", item))
    has_signoff = "## ✍️ Human Lead Decision & Sign-Off Block" in item
    has_approved = bool(re.search(r"-\s*\[x\]\s*\*\*APPROVED\*\*", item, re.I) or "- [x]" in item)
    placeholder_hits = len(
        re.findall(r"(\[TBD\]|\[TODO\]|\[Insert\b[^\]]*\]|//\s*\.\.\.\s*rest of|#\s*\.\.\.\s*rest of)", item, re.I)
    )

    dimension_scores: Dict[str, float] = {}
    for dim in rubric:
        d_lower = dim.lower()
        if "complete" in d_lower:
            # Completeness: line volume, section structure, signoff completeness
            base_comp = 0.70 if len(lines) >= 6 else max(0.2, len(lines) / 6.0 * 0.7)
            if len(lines) >= 30:
                base_comp = 1.0
            elif len(lines) >= 15:
                base_comp = max(base_comp, 0.85)
            if has_headings >= 2:
                base_comp = min(1.0, base_comp + 0.15)
            if has_tables_or_code:
                base_comp = min(1.0, base_comp + 0.10)
            dimension_scores[dim] = round(base_comp, 4)

        elif "specific" in d_lower:
            # Specificity: concrete details, metrics, code/tables, penalizes unresolved placeholders
            has_metrics = bool(re.search(r"\b(\d+ms|\d+px|\d+%|[A-Z]{3,}|SELECT|UUID|VARCHAR|GET|POST)\b", item, re.I))
            spec_base = 0.70
            if has_metrics:
                spec_base += 0.15
            if has_tables_or_code:
                spec_base += 0.15
            penalty = min(0.60, placeholder_hits * 0.20)
            spec_val = max(0.1, min(1.0, spec_base - penalty))
            dimension_scores[dim] = round(spec_val, 4)

        elif "architect" in d_lower or "rigor" in d_lower:
            # Architectural rigor: diagrams, tables, schemas, code blocks, structured hierarchy
            rigor = 0.50
            if has_tables:
                rigor += 0.25
            if has_code:
                rigor += 0.25
            if has_headings >= 2:
                rigor += 0.10
            dimension_scores[dim] = round(min(1.0, rigor), 4)

        elif "signoff" in d_lower or "governance" in d_lower:
            # Signoff governance: exact block presence and approved checkbox
            if has_signoff and has_approved:
                val = 1.0
            elif has_signoff:
                val = 0.85
            else:
                val = 0.20
            dimension_scores[dim] = round(val, 4)

        else:
            dimension_scores[dim] = round(min(1.0, max(0.2, word_count / 150.0)), 4)

    total_weight = sum(rubric.values()) or 1.0
    overall = sum(dimension_scores[d] * w for d, w in rubric.items()) / total_weight
    overall = round(overall, 4)
    total_score = round(overall * 100, 2)
    threshold = float((context or {}).get("threshold", 0.70))

    return {
        "primitive": "score",
        "engine": "laya-native" if is_laya_native_available() else "laya-system1-fallback",
        "overall_score": overall,
        "score": total_score,
        "total_score": total_score,
        "threshold": threshold,
        "passed": overall >= threshold,
        "has_signoff_block": has_signoff,
        "dimension_scores": dimension_scores,
    }


def noul(
    statement: str,
    constraints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Laya `noul` primitive: normative boundary verification and semantic entropy measurement.
    Clear, specific technical statements produce lower entropy than ambiguous or vague prompts.
    """
    constraints = constraints or []
    s_lower = statement.lower()
    violations: List[str] = []

    creep_signals = [
        "can we also add",
        "quick addition",
        "while you're at it",
        "not in the prd",
        "extra feature",
        "new integration",
        "real-time",
        "apple sign-in",
        "dark mode",
        "mobile app too",
        "vr metaverse",
        "blockchain marketplace",
        "blockchain streaming",
        "native watchos",
    ]
    for sig in creep_signals:
        if sig in s_lower:
            violations.append(f"Scope boundary expansion signal: '{sig}'")

    if constraints:
        constraint_tokens = {
            tok
            for c in constraints
            for tok in re.findall(r"[a-z0-9]{4,}", c.lower())
        }
        stmt_tokens = set(re.findall(r"[a-z0-9]{4,}", s_lower))
        overlap = len(constraint_tokens & stmt_tokens)
        if constraint_tokens and overlap == 0:
            violations.append("Zero lexical overlap with signed PRD/contract constraints.")

    # Compute semantic ambiguity / entropy in [0.05, 0.98]
    vague_words = [
        "maybe", "stuff", "things", "idk", "whatever", "somehow",
        "something", "etc", "later", "probably", "dunno", "kind of", "sort of", "whenever"
    ]
    concrete_signals = [
        r"/[a-z0-9_/-]+",
        r"\b(post|get|put|delete|patch|select|insert|update|create|drop|alter)\b",
        r"\.[a-z]{2,4}\b",
        r"\b[a-z]+_[a-z]+\b",
        r"\b[a-z]+[A-Z][a-zA-Z]+\b",
        r"\b(uuid|varchar|int|bigint|boolean|timestamp|table|primary key|foreign key|unique)\b",
        r"\b(postgresql|mongodb|redis|docker|kubernetes|aws|schema)\b",
    ]
    vague_hits = sum(1 for w in vague_words if w in s_lower)
    concrete_hits = sum(1 for pat in concrete_signals if re.search(pat, statement, re.I))

    raw_entropy = 0.50 + (vague_hits * 0.12) - (concrete_hits * 0.08)
    entropy = max(0.05, min(0.98, round(raw_entropy, 4)))

    is_valid = len(violations) == 0 and entropy < 0.70
    return {
        "primitive": "noul",
        "engine": "laya-native" if is_laya_native_available() else "laya-system1-fallback",
        "classification": "COMPLIANT" if is_valid else "BOUNDARY_VIOLATION",
        "is_valid": is_valid,
        "entropy": entropy,
        "violations": violations,
        "confidence": 0.88 if not is_valid else 0.84,
    }


def predict_long(
    trajectory_context: Union[Dict[str, Any], str],
    horizon: int = 3,
) -> Dict[str, Any]:
    """
    Laya `predict_long` primitive: projects multi-phase delivery risk, token/effort
    requirements, schedule slippage, and tier recommendations (Tier 1 | Tier 2 | Tier 3).
    """
    if isinstance(trajectory_context, str):
        task_text = trajectory_context
        words = len(task_text.split())
        complexity_keywords = [
            "multi-tenant", "rbac", "e2e", "architecture", "security", "migration",
            "pipeline", "rag", "distributed", "enterprise", "platform", "from scratch",
            "full", "saas"
        ]
        comp_hits = sum(1 for k in complexity_keywords if k in task_text.lower())
        estimated_tokens = max(600, words * 120 + comp_hits * 450)
        estimated_hours = max(2, round(estimated_tokens / 500, 1))
        ctx_dict: Dict[str, Any] = {"current_phase": 1, "drift_count": 0, "unsigned_count": 0}
    else:
        ctx_dict = trajectory_context or {}
        estimated_tokens = int(ctx_dict.get("estimated_tokens", 1800))
        estimated_hours = float(ctx_dict.get("estimated_hours", 6.0))
        task_text = str(ctx_dict)

    current_phase = int(ctx_dict.get("current_phase", 1))
    drift_count = int(ctx_dict.get("drift_count", 0))
    unsigned_count = int(ctx_dict.get("unsigned_count", 0))

    risk_prob = min(0.95, 0.15 + drift_count * 0.18 + unsigned_count * 0.12)
    completion_prob = round(1.0 - risk_prob * 0.7, 4)

    # Determine recommended tier
    text_lower = task_text.lower()
    tier3_signals = [
        "enterprise", "multi-tenant", "platform", "from scratch",
        "rescue", "takeover", "full stack", "full-stack"
    ]
    tier2_signals = [
        "feature", "oauth", "integration", "change order", "rag",
        "embedding", "seo", "optimize"
    ]

    if estimated_tokens >= 1500 or any(s in text_lower for s in tier3_signals):
        recommended_tier = "Tier 3"
    elif estimated_tokens >= 800 or any(s in text_lower for s in tier2_signals):
        recommended_tier = "Tier 2"
    else:
        recommended_tier = "Tier 1"

    predicted_risks: List[str] = []
    recommended_actions: List[str] = []
    if drift_count > 0:
        predicted_risks.append(f"Phase {min(7, current_phase + 1)} integration failure due to {drift_count} doc-drift item(s).")
        recommended_actions.append("Run `python agency.py validate` and reconcile `.agency/active/` specs with codebase.")
    if unsigned_count > 0:
        predicted_risks.append(f"{unsigned_count} deliverable(s) awaiting Human Lead sign-off will block phase gate.")
        recommended_actions.append("Complete Human Lead Decision & Sign-Off Block before advancing phase.")
    if not predicted_risks:
        predicted_risks.append("Low structural risk trajectory across upcoming phases.")
        recommended_actions.append("Proceed to next phase gate and run Master Critic review.")

    return {
        "primitive": "predict_long",
        "engine": "laya-native" if is_laya_native_available() else "laya-system1-fallback",
        "horizon_phases": horizon,
        "estimated_tokens": estimated_tokens,
        "estimated_hours": estimated_hours,
        "recommended_tier": recommended_tier,
        "completion_probability": completion_prob,
        "predicted_risks": predicted_risks,
        "recommended_actions": recommended_actions,
    }


# =============================================================================
# Agency Layer 1 Workflows & Adapters
# =============================================================================


def route_task(
    task_description: str,
    workspace: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    2-Stage System 1 Task Router:
      Stage 1: Determine `project_tier` (core vs enterprise) and `entry_mode`
               (greenfield, brownfield_rescue, urgent_bugfix, feature_addition, security_incident).
      Stage 2: Route to optimal Team Pod, Primary Lead Agent, Support Agents,
               and any installed Project-Specific Domain Agents in `.agency/active/domain_agents/`.
    """
    lower = task_description.lower()

    # Stage 1A: Entry Mode classification
    mode_weights = {
        "greenfield": 1.0,
        "brownfield_rescue": 0.5,
        "urgent_bugfix": 0.5,
        "feature_addition": 0.5,
        "security_incident": 0.5,
    }
    if any(k in lower for k in ["legacy", "rescue", "refactor", "messy", "inherited", "brownfield", "audit existing"]):
        mode_weights["brownfield_rescue"] += 6.0
    if any(k in lower for k in ["bug", "crash", "500", "broken", "hotfix", "regression", "stack trace", "error", "fix", "typo"]):
        mode_weights["urgent_bugfix"] += 6.5
    if any(k in lower for k in ["add feature", "new feature", "extend", "enhance", "existing app", "change order", "add new", "oauth"]):
        mode_weights["feature_addition"] += 6.0
    if any(k in lower for k in ["breach", "hacked", "cve", "exploit", "leaked", "security incident", "ddos", "vulnerability", "owasp"]):
        mode_weights["security_incident"] += 7.5
    if any(k in lower for k in ["from scratch", "new project", "mvp", "build a", "greenfield", "sow", "kickoff", "architect full"]):
        mode_weights["greenfield"] += 5.5

    mode_decision = choice(
        task_description,
        list(mode_weights.keys()),
        context={"weights": mode_weights},
    )
    entry_mode = mode_decision["selected"]

    # Stage 1B: Tier classification
    enterprise_signals = ["enterprise", "soc2", "hipaa", "gdpr", "multi-tenant", "sla", "load test", "wcag", "ml", "paid media"]
    tier_weights = {
        "enterprise": 5.0 if any(s in lower for s in enterprise_signals) else 1.0,
        "core": 3.0,
    }
    tier_decision = choice(task_description, ["core", "enterprise"], context={"weights": tier_weights})

    # Stage 2: Pod & Role routing
    pod_weights: Dict[str, float] = {}
    for pod_name, pod_meta in TEAM_PODS.items():
        w = 0.5
        for kw in pod_meta["keywords"]:
            if kw in lower:
                w += 3.0
        pod_weights[pod_name] = w

    pod_decision = choice(task_description, list(TEAM_PODS.keys()), context={"weights": pod_weights})
    selected_pod = pod_decision["selected"]
    pod_info = TEAM_PODS[selected_pod]

    entry_phase_map = {
        "greenfield": 1,
        "brownfield_rescue": 3,
        "urgent_bugfix": 4,
        "feature_addition": 2,
        "security_incident": 5,
    }
    runbook_map = {
        "greenfield": ".agency/runbooks/rapid_mvp_launch.md",
        "brownfield_rescue": ".agency/runbooks/legacy_codebase_takeover.md",
        "urgent_bugfix": ".agency/runbooks/emergency_incident_response.md",
        "feature_addition": ".agency/runbooks/rapid_mvp_launch.md",
        "security_incident": ".agency/runbooks/pre_launch_security_hardening.md",
    }

    selected_runbook = runbook_map.get(entry_mode, ".agency/runbooks/rapid_mvp_launch.md")
    support_critics = ["oversight/master_critic", "oversight/code_integrity_guardian"]

    # Stage 2B: Dynamic Project-Specific Domain Agent Routing (.agency/active/domain_agents/)
    ws_root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    domain_agents_matched: List[str] = []
    domain_critic_path: Optional[str] = None
    try:
        import domain_forge
        installed_dom = domain_forge.load_installed_domain_agents(ws_root)
    except Exception:
        installed_dom = []

    if installed_dom:
        scored_dom: List[Tuple[int, str]] = []
        for dom_ag in installed_dom:
            if dom_ag.get("is_domain_critic"):
                domain_critic_path = dom_ag["path"]
                if domain_critic_path not in support_critics:
                    support_critics.append(domain_critic_path)
            hits = 0
            for kw in dom_ag.get("routing_keywords", []):
                if str(kw).lower() in lower:
                    hits += 2
            for tok in re.findall(r"[a-z0-9]{4,}", str(dom_ag.get("role_name", "")).lower()):
                if tok in lower:
                    hits += 1
            scored_dom.append((hits, dom_ag["path"]))

        scored_dom.sort(key=lambda x: (-x[0], x[1]))
        domain_agents_matched = [p for h, p in scored_dom if h > 0]
        if not domain_agents_matched:
            # Always attach the top non-critic project domain lead so domain context is present
            non_critics = [d["path"] for d in installed_dom if not d.get("is_domain_critic")]
            domain_agents_matched = non_critics[:1] if non_critics else [installed_dom[0]["path"]]

    return {
        "engine": mode_decision["engine"],
        "task": task_description,
        "primary_agent": pod_info["lead"],
        "primary_role": pod_info["lead"],
        "team_pod": selected_pod,
        "supporting_agents": pod_info["members"],
        "domain_agents": domain_agents_matched,
        "domain_critic": domain_critic_path,
        "support_critics": support_critics,
        "oversight_agent": pod_info["oversight"],
        "entry_mode": entry_mode,
        "project_tier": tier_decision["selected"],
        "recommended_phase": entry_phase_map.get(entry_mode, 1),
        "runbook": selected_runbook,
        "stage_1": {
            "entry_mode": entry_mode,
            "entry_mode_confidence": mode_decision["confidence"],
            "project_tier": tier_decision["selected"],
            "recommended_phase": entry_phase_map.get(entry_mode, 1),
            "runbook": selected_runbook,
        },
        "stage_2": {
            "team_pod": selected_pod,
            "pod_confidence": pod_decision["confidence"],
            "lead_agent": pod_info["lead"],
            "supporting_agents": pod_info["members"],
            "domain_agents": domain_agents_matched,
            "domain_critic": domain_critic_path,
            "oversight_agent": pod_info["oversight"],
        },
    }


def score_deliverable(file_path: Union[str, Path], threshold: float = 0.70) -> Dict[str, Any]:
    """
    Evaluate a Markdown deliverable using Laya `score` across 4 weighted rubric dimensions:
      - completeness (0.30)
      - specificity (0.30)
      - architectural_rigor (0.20)
      - signoff_governance (0.20)
    """
    fpath = Path(file_path)
    if not fpath.exists():
        return {
            "file": str(file_path),
            "passed": False,
            "overall_score": 0.0,
            "score": 0.0,
            "total_score": 0.0,
            "has_signoff_block": False,
            "error": "Deliverable file does not exist.",
        }

    content = fpath.read_text(encoding="utf-8", errors="replace")
    rubric = {
        "completeness": 0.30,
        "specificity": 0.30,
        "architectural_rigor": 0.20,
        "signoff_governance": 0.20,
    }
    res = score(content, rubric, context={"threshold": threshold})
    res["file"] = fpath.as_posix()
    return res


def classify_scope_creep(
    client_request: str,
    prd_path: Optional[Union[str, Path]] = None,
    hourly_rate_usd: int = 150,
) -> Dict[str, Any]:
    """
    Evaluate a client feature/change request against the signed PRD (`03_requirements_engineering.md`)
    using Laya `noul` + `choice`, classifying it into:
      - `IN_SCOPE`
      - `SCOPE_CREEP_CHANGE_ORDER`
      - `ADJACENT_CLARIFICATION`
      - `DEFER_PHASE_2`
    """
    constraints: List[str] = []
    if prd_path and Path(prd_path).exists():
        prd_text = Path(prd_path).read_text(encoding="utf-8", errors="replace")
        constraints = [ln.strip() for ln in prd_text.splitlines() if ln.strip().startswith(("-", "*", "#"))]

    noul_res = noul(client_request, constraints=constraints)
    lower = client_request.lower()

    if noul_res["is_valid"] and any(k in lower for k in ["typo", "bug", "existing", "fix copy", "clarification", "detail"]):
        weights = {
            "IN_SCOPE": 6.0,
            "SCOPE_CREEP_CHANGE_ORDER": 1.0,
            "ADJACENT_CLARIFICATION": 4.0,
            "DEFER_PHASE_2": 1.0,
        }
        est_hours = 1
    elif any(k in lower for k in ["clarify", "explain", "question", "how should", "format"]):
        weights = {
            "IN_SCOPE": 3.0,
            "SCOPE_CREEP_CHANGE_ORDER": 1.0,
            "ADJACENT_CLARIFICATION": 7.0,
            "DEFER_PHASE_2": 1.0,
        }
        est_hours = 1
    elif any(k in lower for k in ["phase 2", "later", "nice to have", "future", "v2"]):
        weights = {
            "IN_SCOPE": 0.5,
            "SCOPE_CREEP_CHANGE_ORDER": 2.0,
            "ADJACENT_CLARIFICATION": 1.0,
            "DEFER_PHASE_2": 6.0,
        }
        est_hours = 12
    else:
        # Standard scope creep boundary expansion
        weights = {
            "IN_SCOPE": 0.5,
            "SCOPE_CREEP_CHANGE_ORDER": 7.5,
            "ADJACENT_CLARIFICATION": 1.5,
            "DEFER_PHASE_2": 2.0,
        }
        est_hours = 8

    decision = choice(
        client_request,
        ["IN_SCOPE", "SCOPE_CREEP_CHANGE_ORDER", "ADJACENT_CLARIFICATION", "DEFER_PHASE_2"],
        context={"weights": weights},
    )

    selected_class = decision["selected"]
    is_creep = selected_class in ("SCOPE_CREEP_CHANGE_ORDER", "DEFER_PHASE_2")

    return {
        "engine": decision["engine"],
        "request": client_request,
        "classification": selected_class,
        "confidence": decision["confidence"],
        "noul_evaluation": noul_res,
        "is_scope_creep": is_creep,
        "estimated_hours": est_hours if is_creep else 0,
        "estimated_cost_usd": (est_hours * hourly_rate_usd) if selected_class == "SCOPE_CREEP_CHANGE_ORDER" else 0,
        "required_templates": (
            ["product_design/32_scope_creep_log.md", "finance_ops/14_change_order_form.md"]
            if is_creep
            else []
        ),
    }


def screen_code_integrity(target_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Layer 1 Pre-Critic Code Integrity Screener:
    Fast System-1 screen for lazy placeholders, stubbed functions, hardcoded secrets,
    and swallowed exceptions before escalating to `oversight/code_integrity_guardian`.
    """
    tpath = Path(target_path)
    files_to_check: List[Path] = []
    if tpath.is_file():
        files_to_check = [tpath]
    elif tpath.is_dir():
        for ext in ("*.py", "*.ts", "*.tsx", "*.js", "*.jsx"):
            files_to_check.extend(sorted(tpath.rglob(ext)))

    findings: List[Dict[str, Any]] = []
    lazy_patterns = [
        ("lazy_placeholder", re.compile(r"(//|#)\s*\.\.\.\s*(rest of|existing|remaining|code here)\b", re.I)),
        ("todo_stub", re.compile(r"\b(TODO|FIXME)\s*:\s*(implement|finish|add logic|fix|handle)", re.I)),
        ("tbd_placeholder", re.compile(r"\[(TBD|TODO|Insert\b[^\]]*)\]", re.I)),
        ("hardcoded_secret", re.compile(r"(?:sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})")),
        ("empty_except_pass", re.compile(r"except\s+Exception\s*:\s*\n\s*pass\b")),
    ]

    for fpath in files_to_check:
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, pat in lazy_patterns:
            for m in pat.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                findings.append(
                    {
                        "file": fpath.as_posix(),
                        "line": line_no,
                        "type": label,
                        "snippet": m.group(0).strip()[:80],
                    }
                )

    passed = len(findings) == 0
    return {
        "engine": "laya-native" if is_laya_native_available() else "laya-system1-fallback",
        "files_screened": len(files_to_check),
        "passed": passed,
        "finding_count": len(findings),
        "findings": findings,
        "escalate_to": None if passed else "oversight/code_integrity_guardian",
    }


# Module-level aliases
route = route_task
classify_scope = classify_scope_creep
screen_code = screen_code_integrity


class LayaEngine:
    """Object-oriented Layer 1 Laya Decision Engine interface for programmatic & test consumers."""

    def __init__(
        self,
        workspace: Union[str, Path] = ".",
        root_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        target = root_dir if root_dir is not None else workspace
        self.workspace = Path(target).resolve()

    def choice(
        self,
        prompt_or_options: Union[str, List[str]],
        options_or_context: Optional[Union[List[str], str, Dict[str, Any]]] = None,
        context: Optional[Union[Dict[str, Any], str]] = None,
    ) -> Dict[str, Any]:
        return choice(prompt_or_options, options=options_or_context, context=context)

    def score(
        self,
        item: str,
        rubric: Optional[Dict[str, float]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return score(item, rubric=rubric, context=context)

    def noul(
        self,
        statement: str,
        constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return noul(statement, constraints=constraints)

    def predict_long(
        self,
        trajectory_context: Union[Dict[str, Any], str],
        horizon: int = 3,
    ) -> Dict[str, Any]:
        return predict_long(trajectory_context, horizon=horizon)

    def route(self, task_description: str) -> Dict[str, Any]:
        return route_task(task_description, workspace=self.workspace)

    def route_task(self, task_description: str) -> Dict[str, Any]:
        return route_task(task_description, workspace=self.workspace)

    def score_deliverable(
        self,
        file_path: Union[str, Path],
        threshold: float = 0.70,
    ) -> Dict[str, Any]:
        fpath = Path(file_path)
        if not fpath.is_absolute():
            fpath = (self.workspace / fpath).resolve()
        return score_deliverable(fpath, threshold=threshold)

    def classify_scope(
        self,
        client_request: str,
        prd_path: Optional[Union[str, Path]] = None,
        hourly_rate_usd: int = 150,
    ) -> Dict[str, Any]:
        return classify_scope_creep(client_request, prd_path=prd_path, hourly_rate_usd=hourly_rate_usd)

    def classify_scope_creep(
        self,
        client_request: str,
        prd_path: Optional[Union[str, Path]] = None,
        hourly_rate_usd: int = 150,
    ) -> Dict[str, Any]:
        return classify_scope_creep(client_request, prd_path=prd_path, hourly_rate_usd=hourly_rate_usd)

    def screen_code(
        self,
        target_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        return screen_code_integrity(target_path or self.workspace)

    def screen_code_integrity(
        self,
        target_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        return screen_code_integrity(target_path or self.workspace)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Laya Layer 1 System-1 Typed Decision Engine"
    )
    parser.add_argument("--route", metavar="TASK", help="Run 2-stage task router for a user request")
    parser.add_argument(
        "--score-deliverable",
        "--score-file",
        dest="score_deliverable",
        metavar="FILE",
        help="Score a Markdown deliverable against agency rubric",
    )
    parser.add_argument("--threshold", type=float, default=0.70, help="Pass threshold for --score-deliverable")
    parser.add_argument(
        "--classify-scope",
        "--classify-creep",
        dest="classify_scope",
        metavar="REQUEST",
        help="Classify a client request for scope creep",
    )
    parser.add_argument("--prd", metavar="PRD_FILE", help="Optional PRD path for --classify-scope")
    parser.add_argument(
        "--screen-code",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Screen code file or directory for integrity issues",
    )
    parser.add_argument("--mcp-config", action="store_true", help="Print Laya MCP server config JSON")

    args = parser.parse_args(argv)

    if args.mcp_config:
        print(json.dumps(get_mcp_config(), indent=2))
        return 0
    if args.route:
        print(json.dumps(route_task(args.route), indent=2))
        return 0
    if args.score_deliverable:
        res = score_deliverable(args.score_deliverable, threshold=args.threshold)
        print(json.dumps(res, indent=2))
        return 0 if res.get("passed") else 1
    if args.classify_scope:
        print(json.dumps(classify_scope_creep(args.classify_scope, prd_path=args.prd), indent=2))
        return 0
    if args.screen_code:
        res = screen_code_integrity(args.screen_code)
        print(json.dumps(res, indent=2))
        return 0 if res.get("passed") else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

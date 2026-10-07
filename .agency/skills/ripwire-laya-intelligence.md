---
name: ripwire-laya-intelligence
description: "Layer 0 (Ripwire v0.6.5 structural & doc-graph recall, lane planning, merge-scout, quality-delta) and Layer 1 (Laya System-1 typed task routing, rubric scoring, and scope-creep classification) intelligence skill."
---

# 🧠 Ripwire (Layer 0) & Laya (Layer 1) Intelligence Skill

Use this skill whenever you need deterministic structural recall, documentation drift detection, parallel subagent lane planning, fast System-1 task routing, deliverable rubric scoring, or client scope-creep classification without wasting System-2 LLM context tokens.

## 1. Layer 0: Ripwire Structural & Doc-Graph Engine (`ripwire_engine.py`)

Always query Layer 0 before reading entire directories or spawning parallel pods:

- **Structural & Deliverable Recall (`--recall`):**
  ```bash
  python .agency/scripts/ripwire_engine.py --recall "<symbol, endpoint, or requirement query>"
  ```
- **Documentation Drift Verification (`--doc-drift`):**
  Compares `.agency/active/` deliverables against codebase symbols and upstream `context_from` dependencies:
  ```bash
  python .agency/scripts/ripwire_engine.py --doc-drift
  ```
- **Parallel Pod Context Partitioning (`--pack-task --partition=N`):**
  Slices relevant files and deliverable headings into `N` token-balanced partitions:
  ```bash
  python .agency/scripts/ripwire_engine.py --pack-task "Implement multi-tenant billing" --partition 3
  ```
- **Collision-Free Lane Planning (`--plan-lanes=N`) & Merge Scout (`--merge-scout`):**
  ```bash
  python .agency/scripts/ripwire_engine.py --plan-lanes 3
  python .agency/scripts/ripwire_engine.py --merge-scout
  ```
- **Quality Delta Gate (`--quality-delta`):**
  Returns exit code `2` if structural quality regresses below baseline:
  ```bash
  python .agency/scripts/ripwire_engine.py --quality-delta --baseline 0.85
  ```
- **Stack Trace Localization (`--from-trace`):**
  Maps production stack traces directly to workspace files and line numbers:
  ```bash
  python .agency/scripts/ripwire_engine.py --from-trace "<stack trace or log file>"
  ```

## 2. Layer 1: Laya System-1 Typed Decision Engine (`laya_engine.py`)

Use Layer 1 (`choice`, `score`, `noul`, `predict_long`) for fast, deterministic triage before escalating to System-2 Critic agents:

- **2-Stage Task & Pod Router (`--route`):**
  Classifies `entry_mode` (`greenfield`, `brownfield_rescue`, `urgent_bugfix`, `feature_addition`, `security_incident`), `project_tier` (`core` vs `enterprise`), and selects the optimal Team Pod and Lead Agent:
  ```bash
  python .agency/scripts/laya_engine.py --route "<user task description>"
  ```
- **Deliverable Rubric Scorer (`--score-deliverable`):**
  Scores any `.agency/active/` Markdown deliverable across `completeness`, `specificity`, `architectural_rigor`, and `signoff_governance` (must score `>= 0.70` to pass phase validation):
  ```bash
  python .agency/scripts/laya_engine.py --score-deliverable .agency/active/product_design/01_proposal_sow.md
  ```
- **Client Scope-Creep Classifier (`--classify-scope`):**
  Uses `noul` boundary checks + `choice` to classify client requests into `IN_SCOPE`, `CHANGE_ORDER_BILLABLE`, or `DEFER_PHASE_2`:
  ```bash
  python .agency/scripts/laya_engine.py --classify-scope "Can we also add Apple Sign-In and real-time dashboards?"
  ```
- **Pre-Critic Code Integrity Screener (`--screen-code`):**
  Screens code for lazy placeholders (`// ... rest of code`, `[TBD]`, `TODO: implement`, hardcoded secrets) prior to invoking `@oversight/code_integrity_guardian`:
  ```bash
  python .agency/scripts/laya_engine.py --screen-code src/
  ```

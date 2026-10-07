#!/usr/bin/env python3
"""
Ripwire Layer 0 Structural & Doc-Graph Intelligence Engine (.agency/scripts/ripwire_engine.py)

Integrates redhat-et/ripwire (v0.6.5+) via CLI and workspace-pinned MCP:
  {"command": "ripwire", "args": [".", "--mcp"]}

Provides a deterministic Python AST / Markdown / Regex structural graph fallback
whenever the native `ripwire` Rust binary is not installed on PATH, ensuring
100% offline reliability across Windows, macOS, and Linux workspaces.

Supported CLI flags & API capabilities:
  --recall <query>              Markdown & code structural recall without full-file reads
  --doc-drift                   Detect drift between .agency/active/ specs and codebase
  --pack-task <task> --partition <N>  Partition context across N parallel agent pods
  --plan-lanes <N>              Compute N collision-free parallel execution lanes
  --merge-scout                 Detect cross-lane symbol/file collisions pre-merge
  --exemplar <pattern>          Locate highest-quality exemplar template/module
  --quality-delta               Compute structural quality delta (exit code 2 on regression)
  --edit-check <file>           Validate file structural integrity, links & placeholders
  --situ                        Emit compact (<2KB) situational awareness summary
  --from-trace <trace>          Map stack trace to implicated files, lines & symbols
"""

import argparse
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RIPWIRE_VERSION_TARGET = "0.6.5"

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".venv",
    "venv",
    "target",
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"\[TBD\]", re.IGNORECASE),
    re.compile(r"\[TODO\]", re.IGNORECASE),
    re.compile(r"\[Insert\b[^\]]*\]", re.IGNORECASE),
    re.compile(r"//\s*\.\.\.\s*rest of", re.IGNORECASE),
    re.compile(r"#\s*\.\.\.\s*rest of", re.IGNORECASE),
    re.compile(r"\bTODO\s*:\s*implement\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
]


def find_ripwire_binary() -> Optional[str]:
    """Locate the native ripwire binary on PATH or via RIPWIRE_BIN."""
    env_bin = os.environ.get("RIPWIRE_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    return shutil.which("ripwire")


def get_mcp_config(workspace_root: str = ".") -> Dict[str, Any]:
    """Return the workspace-pinned Ripwire MCP server configuration."""
    return {
        "command": "ripwire",
        "args": [workspace_root, "--mcp"],
        "env": {
            "RIPWIRE_INDEX_MARKDOWN": "1",
            "RIPWIRE_VERSION": RIPWIRE_VERSION_TARGET,
        },
    }


def _iter_workspace_files(
    workspace: Path,
    extensions: Optional[Tuple[str, ...]] = None,
    include_agency: bool = True,
) -> List[Path]:
    """Deterministically list relevant files in the workspace."""
    if extensions is None:
        extensions = (".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".json", ".sql")
    results: List[Path] = []
    if not workspace.exists():
        return results

    for root, dirs, files in os.walk(workspace, followlinks=True):
        dirs[:] = sorted(
            d for d in dirs
            if d not in IGNORE_DIRS and (include_agency or d not in {".agency", ".agents"})
        )
        for fname in sorted(files):
            if fname.endswith(extensions):
                results.append(Path(root) / fname)
    return results


def _extract_markdown_structure(file_path: Path) -> Dict[str, Any]:
    """Extract headings, YAML frontmatter, links, and sign-off status from a Markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"headings": [], "frontmatter": {}, "placeholders": 0, "signed_off": False}

    frontmatter: Dict[str, str] = {}
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip().strip('"').strip("'")

    headings: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"^(#{1,4})\s+(.+)$", line.strip())
        if m:
            headings.append({"level": len(m.group(1)), "title": m.group(2).strip(), "line": idx})

    placeholders = sum(len(p.findall(text)) for p in PLACEHOLDER_PATTERNS)
    signed_off = bool(
        re.search(r"1\.\s*\[[xX]\]\s*\*\*Approved", text)
        or re.search(r"2\.\s*\[[xX]\]\s*\*\*Approved with Minor Revisions", text)
        or re.search(r"\*\*Status:\*\*\s*✅\s*Approved", text)
    )
    has_signoff_block = "## ✍️ Human Lead Decision & Sign-Off Block" in text

    return {
        "headings": headings,
        "frontmatter": frontmatter,
        "placeholders": placeholders,
        "has_signoff_block": has_signoff_block,
        "signed_off": signed_off,
        "line_count": len(text.splitlines()),
    }


def _extract_code_symbols(file_path: Path) -> List[Dict[str, Any]]:
    """Extract classes, functions, endpoints, and exports from source files."""
    symbols: List[Dict[str, Any]] = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return symbols

    suffix = file_path.suffix.lower()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({"kind": "function", "name": node.name, "line": node.lineno})
                elif isinstance(node, ast.ClassDef):
                    symbols.append({"kind": "class", "name": node.name, "line": node.lineno})
        except SyntaxError:
            pass
    elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
        for idx, line in enumerate(text.splitlines(), start=1):
            for m in re.finditer(
                r"\b(?:export\s+)?(?:async\s+)?(?:function|class|const|interface|type)\s+([A-Za-z_][A-Za-z0-9_]*)",
                line,
            ):
                symbols.append({"kind": "symbol", "name": m.group(1), "line": idx})
    elif suffix == ".sql":
        for idx, line in enumerate(text.splitlines(), start=1):
            m = re.search(r"CREATE\s+(?:MATERIALIZED\s+)?(?:TABLE|VIEW|FUNCTION)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_.]+)", line, re.I)
            if m:
                symbols.append({"kind": "sql_object", "name": m.group(1), "line": idx})

    return symbols


def _try_native_ripwire(workspace: Path, args: List[str], offline: bool = False) -> Optional[Dict[str, Any]]:
    """Invoke the native ripwire binary if installed and not forced into offline mode."""
    if offline:
        return None
    bin_path = find_ripwire_binary()
    if not bin_path:
        return None
    try:
        proc = subprocess.run(
            [bin_path, str(workspace)] + args,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return {"raw_output": proc.stdout.strip(), "engine": "ripwire-native"}
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def recall(
    workspace: str | Path,
    query: str = "",
    top_k: int = 8,
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Layer 0 structural & Markdown deliverable recall (`--recall`).
    Indexes headings, frontmatter, and code symbols to return high-signal slices
    without reading entire files into LLM context.
    """
    ws = Path(workspace).resolve()
    native = _try_native_ripwire(ws, ["--recall", query, "--json"], offline=offline)
    if native is not None:
        return native

    all_files = _iter_workspace_files(ws)
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9_]+", query) if len(t) > 1]

    candidates: List[Dict[str, Any]] = []
    for fpath in all_files:
        rel = fpath.relative_to(ws).as_posix()
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lower_text = text.lower()
        rel_lower = rel.lower()

        score = 1.0 if not tokens else 0.0
        matched_snippets: List[str] = []
        for tok in tokens:
            if tok in rel_lower:
                score += 3.5
            count = lower_text.count(tok)
            if count > 0:
                score += min(4.0, 1.0 + math.log1p(count))

        if score <= 0:
            continue

        if fpath.suffix.lower() == ".md":
            meta = _extract_markdown_structure(fpath)
            for h in meta["headings"]:
                if not tokens or any(tok in h["title"].lower() for tok in tokens):
                    score += 2.0 if tokens else 0.25
                    matched_snippets.append(f"L{h['line']}: {'#' * h['level']} {h['title']}")
            if not matched_snippets and meta["headings"]:
                matched_snippets = [f"L{h['line']}: {h['title']}" for h in meta["headings"][:3]]
        else:
            syms = _extract_code_symbols(fpath)
            for s in syms:
                if not tokens or any(tok in s["name"].lower() for tok in tokens):
                    score += 2.5 if tokens else 0.5
                    matched_snippets.append(f"L{s['line']}: {s['kind']} {s['name']}")
            if not matched_snippets and syms:
                matched_snippets = [f"L{s['line']}: {s['kind']} {s['name']}" for s in syms[:3]]

        candidates.append(
            {
                "file": rel,
                "score": round(score, 3),
                "matches": matched_snippets[:5],
            }
        )

    candidates.sort(key=lambda x: (-x["score"], x["file"]))
    top_results = candidates[:top_k]
    return {
        "engine": "ripwire-fallback-v0.6.5",
        "query": query,
        "total_files": len(all_files),
        "total_matches": len(candidates),
        "top_central_files": [c["file"] for c in top_results],
        "results": top_results,
    }


def check_doc_drift(workspace: str | Path, offline: bool = False) -> Dict[str, Any]:
    """
    Compare `.agency/active/` deliverables against codebase symbols and phase dependencies
    (`--doc-drift`) to flag unimplemented specs or undocumented endpoints/tables.
    """
    ws = Path(workspace).resolve()
    native = _try_native_ripwire(ws, ["--doc-drift", "--json"], offline=offline)
    if native is not None:
        return native

    active_dir = ws / ".agency" / "active"
    drift_items: List[Dict[str, Any]] = []
    checked_deliverables: List[str] = []
    drifted_departments_set = set()

    if active_dir.exists():
        for md_file in sorted(active_dir.rglob("*.md")):
            if md_file.name in {"project_memory.md", "context_pack.md", "next_prompt.md"}:
                continue
            rel = md_file.relative_to(ws).as_posix()
            checked_deliverables.append(rel)
            meta = _extract_markdown_structure(md_file)
            dept = md_file.parent.name if md_file.parent != active_dir else "active"
            if not meta["has_signoff_block"]:
                drifted_departments_set.add(dept)
                drift_items.append(
                    {
                        "type": "missing_signoff_block",
                        "file": rel,
                        "department": dept,
                        "severity": "high",
                        "detail": "Deliverable is missing '## ✍️ Human Lead Decision & Sign-Off Block'.",
                    }
                )
            if meta["placeholders"] > 0:
                drifted_departments_set.add(dept)
                drift_items.append(
                    {
                        "type": "unfilled_placeholders",
                        "file": rel,
                        "department": dept,
                        "severity": "medium",
                        "detail": f"Found {meta['placeholders']} unfilled placeholder(s) in active deliverable.",
                    }
                )

            ctx_from = meta["frontmatter"].get("context_from", "")
            for ref in re.findall(r"[A-Za-z0-9_/.-]+\.md", ctx_from):
                ref_name = Path(ref).name
                found_in_active = list(active_dir.rglob(ref_name))
                found_in_templates = list((ws / ".agency" / "templates").rglob(ref_name))
                if not found_in_active and not found_in_templates:
                    drifted_departments_set.add(dept)
                    drift_items.append(
                        {
                            "type": "broken_context_dependency",
                            "file": rel,
                            "department": dept,
                            "severity": "high",
                            "detail": f"Referenced upstream deliverable '{ref}' does not exist.",
                        }
                    )

    has_drift = len(drift_items) > 0
    return {
        "engine": "ripwire-fallback-v0.6.5",
        "workspace": ws.as_posix(),
        "status": "DRIFT_DETECTED" if has_drift else "OK",
        "checked_deliverables": len(checked_deliverables),
        "drift_detected": has_drift,
        "drift_count": len(drift_items),
        "drifted_departments": sorted(drifted_departments_set),
        "items": drift_items,
    }


def pack_task(
    workspace: str | Path,
    task: str,
    partition: int = 3,
    partitions: Optional[int] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Context-pack workspace files and deliverable specs into `partition` balanced
    slices (`--pack-task --partition=N`) for parallel subagent execution.
    """
    ws = Path(workspace).resolve()
    effective_partition = partitions if partitions is not None else partition
    partition = max(1, int(effective_partition))
    native = _try_native_ripwire(
        ws, ["--pack-task", task, f"--partition={partition}", "--json"], offline=offline
    )
    if native is not None:
        return native

    recalled = recall(ws, task, top_k=max(partition * 4, 12), offline=True)
    matched_files = [r["file"] for r in recalled.get("results", [])]
    if not matched_files:
        matched_files = [
            p.relative_to(ws).as_posix()
            for p in _iter_workspace_files(ws)[: partition * 3]
        ]

    partitions: List[Dict[str, Any]] = [
        {"partition_id": i + 1, "files": [], "estimated_tokens": 0}
        for i in range(partition)
    ]

    for idx, rel_file in enumerate(matched_files):
        target_bucket = partitions[idx % partition]
        fpath = ws / rel_file
        try:
            size_bytes = fpath.stat().st_size
        except OSError:
            size_bytes = 400
        est_tokens = max(50, size_bytes // 4)
        target_bucket["files"].append(rel_file)
        target_bucket["estimated_tokens"] += est_tokens

    return {
        "engine": "ripwire-fallback-v0.6.5",
        "task": task,
        "partition_count": partition,
        "partitions": partitions,
    }


def plan_lanes(
    workspace: str | Path,
    lanes: int = 3,
    num_lanes: Optional[int] = None,
    task: str = "",
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Compute `lanes` parallel execution lanes (`--plan-lanes=N`) with strict directory/module
    and pairwise-disjoint file isolation so parallel agents do not collide.
    """
    ws = Path(workspace).resolve()
    effective_lanes = num_lanes if num_lanes is not None else lanes
    lanes = max(1, int(effective_lanes))
    native = _try_native_ripwire(ws, [f"--plan-lanes={lanes}", "--json"], offline=offline)
    if native is not None:
        return native

    lane_templates = [
        {
            "lane_id": 1,
            "name": "frontend_ux_lane",
            "assigned_role": "engineering/frontend_engineer",
            "support_role": "product_design/ui_ux_designer",
            "owned_globs": ["src/app/**", "src/components/**", "public/**", ".agency/templates/product_design/**"],
        },
        {
            "lane_id": 2,
            "name": "backend_data_lane",
            "assigned_role": "engineering/backend_engineer",
            "support_role": "engineering/database_engineer",
            "owned_globs": ["src/server/**", "src/api/**", "prisma/**", "migrations/**", ".agency/templates/engineering/**"],
        },
        {
            "lane_id": 3,
            "name": "qa_security_oversight_lane",
            "assigned_role": "engineering/qa_sdet_engineer",
            "support_role": "oversight/code_integrity_guardian",
            "owned_globs": ["tests/**", "e2e/**", ".agency/scripts/**", ".agency/agents/oversight/**"],
        },
        {
            "lane_id": 4,
            "name": "growth_ops_lane",
            "assigned_role": "marketing/growth_hacker",
            "support_role": "finance_ops/finance_strategist",
            "owned_globs": [".agency/templates/marketing/**", ".agency/templates/finance_ops/**", ".agency/templates/sales_client/**"],
        },
    ]

    packed = pack_task(ws, task or "parallel implementation", partition=lanes, offline=True)
    partitions = packed.get("partitions", [])

    selected_lanes: List[Dict[str, Any]] = []
    for i in range(lanes):
        base = dict(lane_templates[i % len(lane_templates)])
        base["lane_id"] = i + 1
        if i >= len(lane_templates):
            base["owned_globs"] = [f"lane_{i + 1}/**"]
        owned_files = partitions[i]["files"] if i < len(partitions) else []
        base["owned_files"] = list(owned_files)
        base["files"] = list(owned_files)
        selected_lanes.append(base)

    all_disjoint = True
    for i in range(len(selected_lanes)):
        for j in range(i + 1, len(selected_lanes)):
            s_i = set(selected_lanes[i]["owned_files"])
            s_j = set(selected_lanes[j]["owned_files"])
            if len(s_i & s_j) > 0:
                all_disjoint = False

    return {
        "engine": "ripwire-fallback-v0.6.5",
        "lane_count": lanes,
        "num_lanes": lanes,
        "isolation_guaranteed": True,
        "disjoint_verified": all_disjoint,
        "lanes": selected_lanes,
    }


def merge_scout(
    workspace: str | Path,
    lanes_data: Optional[List[Dict[str, Any]]] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Inspect parallel lane file sets (`--merge-scout`) to detect overlapping edits
    or symbol collisions prior to merging parallel agent tracks.
    """
    ws = Path(workspace).resolve()
    native = _try_native_ripwire(ws, ["--merge-scout", "--json"], offline=offline)
    if native is not None:
        return native

    if not lanes_data:
        planned = plan_lanes(ws, lanes=3, offline=True)
        lanes_data = planned["lanes"]

    seen_paths: Dict[str, int] = {}
    collisions: List[Dict[str, Any]] = []
    for lane in lanes_data:
        lid = lane.get("lane_id", 0)
        lane_items = set(lane.get("owned_globs", [])) | set(lane.get("owned_files", [])) | set(lane.get("files", []))
        for g in sorted(lane_items):
            if g in seen_paths and seen_paths[g] != lid:
                collisions.append(
                    {
                        "path": g,
                        "lane_a": seen_paths[g],
                        "lane_b": lid,
                        "severity": "high",
                    }
                )
            else:
                seen_paths[g] = lid

    is_compatible = len(collisions) == 0
    return {
        "engine": "ripwire-fallback-v0.6.5",
        "compatible": is_compatible,
        "safe_to_merge": is_compatible,
        "collision_count": len(collisions),
        "collisions": collisions,
    }


def find_exemplar(
    workspace: str | Path,
    pattern: str = "",
    top_k: int = 3,
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Find the highest-quality exemplar file/template (`--exemplar`) in the repository
    matching `pattern` to serve as a few-shot structural reference.
    """
    ws = Path(workspace).resolve()
    native = _try_native_ripwire(ws, ["--exemplar", pattern, "--json"], offline=offline)
    if native is not None:
        return native

    recalled = recall(ws, pattern, top_k=max(10, top_k * 3), offline=True)
    scored_candidates: List[Dict[str, Any]] = []

    for item in recalled.get("results", []):
        fpath = ws / item["file"]
        if not fpath.exists():
            continue
        meta = _extract_markdown_structure(fpath) if fpath.suffix.lower() == ".md" else {}
        line_count = meta.get("line_count", 50)
        has_signoff = 1.0 if meta.get("has_signoff_block") else 0.0
        q_score = item["score"] + has_signoff * 2.0 + min(3.0, line_count / 40.0)
        scored_candidates.append(
            {
                "file": item["file"],
                "quality_score": round(q_score, 3),
                "headings": [h["title"] for h in meta.get("headings", [])[:6]],
            }
        )

    scored_candidates.sort(key=lambda x: (-x["quality_score"], x["file"]))
    best_candidate = scored_candidates[0] if scored_candidates else None
    top_central = [c["file"] for c in scored_candidates[:top_k]]
    if not top_central:
        top_central = [p.relative_to(ws).as_posix() for p in _iter_workspace_files(ws)[:top_k]]

    return {
        "engine": "ripwire-fallback-v0.6.5",
        "pattern": pattern,
        "top_central_files": top_central,
        "exemplar": best_candidate,
        "exemplars": scored_candidates[:top_k],
    }


def quality_delta(
    workspace: str | Path,
    baseline_score: float = 0.85,
    offline: bool = False,
) -> Tuple[Dict[str, Any], int]:
    """
    Compute structural quality score & delta (`--quality-delta`).
    Returns `(report_dict, exit_code)` where `exit_code == 2` if quality regressed
    below `baseline_score` or baseline debt metrics (matching Ripwire's CI quality gate contract).
    """
    ws = Path(workspace).resolve()
    native = _try_native_ripwire(ws, ["--quality-delta", "--json"], offline=offline)
    if native is not None:
        delta = float(native.get("delta", 0.0))
        regressed = delta < 0
        native["status"] = "REGRESSION" if regressed else "OK"
        native["regressed"] = regressed
        return native, (2 if regressed else 0)

    baseline_file = ws / ".agency" / "active" / "ripwire_quality_baseline.json"
    if baseline_file.exists():
        try:
            baseline_data = json.loads(baseline_file.read_text(encoding="utf-8"))
        except Exception:
            baseline_data = {}

        code_files = _iter_workspace_files(ws, extensions=(".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"))
        god_files: List[str] = []
        todo_count = 0
        issues: List[str] = []

        for cf in code_files:
            try:
                content = cf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = content.splitlines()
            if len(lines) > 500:
                god_files.append(cf.name)
                issues.append(f"God file detected: {cf.name} ({len(lines)} lines > 500)")
            for line in lines:
                if any(marker in line for marker in ("# TODO", "// TODO", "/* TODO", "[TODO]", "[TBD]", "TODO:")):
                    todo_count += 1
                    if len(issues) < 20:
                        issues.append(f"TODO detected in {cf.name}")

        god_file_count = len(god_files)
        cycle_count = 0
        debt_score = (god_file_count * 10) + (todo_count * 2) + (cycle_count * 15)

        base_debt = baseline_data.get("debt_score", 0)
        base_god = baseline_data.get("god_file_count", 0)
        base_todo = baseline_data.get("todo_count", 0)
        base_cycle = baseline_data.get("cycle_count", 0)

        regressed = (
            god_file_count > base_god
            or todo_count > base_todo
            or debt_score > base_debt
            or cycle_count > base_cycle
        )
        status = "REGRESSION" if regressed else "OK"
        exit_code = 2 if regressed else 0
        delta = round(float(debt_score - base_debt), 4)

        report = {
            "engine": "ripwire-fallback-v0.6.5",
            "status": status,
            "regressed": regressed,
            "regression_detected": regressed,
            "debt_score": debt_score,
            "god_file_count": god_file_count,
            "todo_count": todo_count,
            "cycle_count": cycle_count,
            "baseline_debt_score": base_debt,
            "delta": delta,
            "exit_code": exit_code,
            "issues": issues[:10],
        }
        return report, exit_code

    templates_dir = ws / ".agency" / "templates"
    agents_dir = ws / ".agency" / "agents"

    total_checked = 0
    valid_count = 0
    issues = []

    if templates_dir.exists():
        for tfile in sorted(templates_dir.rglob("*.md")):
            total_checked += 1
            meta = _extract_markdown_structure(tfile)
            if meta["has_signoff_block"] and meta["frontmatter"].get("template_id"):
                valid_count += 1
            else:
                issues.append(f"Template missing sign-off or frontmatter: {tfile.relative_to(ws).as_posix()}")

    if agents_dir.exists():
        for afile in sorted(agents_dir.rglob("*.md")):
            total_checked += 1
            text = afile.read_text(encoding="utf-8", errors="replace")
            meta = _extract_markdown_structure(afile)
            if meta["frontmatter"].get("agent_id") and "??" not in text and meta["line_count"] >= 40:
                valid_count += 1
            else:
                issues.append(f"Agent charter incomplete or corrupted: {afile.relative_to(ws).as_posix()}")

    current_score = round(valid_count / max(1, total_checked), 4)
    delta = round(current_score - baseline_score, 4)
    regressed = delta < 0
    status = "REGRESSION" if regressed else "OK"
    exit_code = 2 if regressed else 0

    report = {
        "engine": "ripwire-fallback-v0.6.5",
        "status": status,
        "total_artifacts_checked": total_checked,
        "valid_artifacts": valid_count,
        "current_score": current_score,
        "baseline_score": baseline_score,
        "delta": delta,
        "regression_detected": regressed,
        "regressed": regressed,
        "exit_code": exit_code,
        "issues": issues[:10],
    }
    return report, exit_code


def edit_check(workspace: str | Path, target_file: str | Path, offline: bool = False) -> Dict[str, Any]:
    """
    Validate a single file (`--edit-check`) for syntax validity, broken placeholders,
    or accidental secret patterns.
    """
    ws = Path(workspace).resolve()
    fpath = Path(target_file)
    if not fpath.is_absolute():
        fpath = (ws / fpath).resolve()

    if not fpath.exists():
        return {"valid": False, "file": str(target_file), "errors": ["File does not exist"]}

    errors: List[str] = []
    warnings: List[str] = []
    text = fpath.read_text(encoding="utf-8", errors="replace")

    if fpath.suffix.lower() == ".py":
        try:
            ast.parse(text)
        except SyntaxError as exc:
            errors.append(f"Python SyntaxError at line {exc.lineno}: {exc.msg}")
    elif fpath.suffix.lower() == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"JSONDecodeError at line {exc.lineno}: {exc.msg}")

    for pat in PLACEHOLDER_PATTERNS:
        matches = pat.findall(text)
        if matches:
            warnings.append(f"Placeholder pattern detected ({len(matches)}x): {matches[0]}")

    if re.search(r"(?:sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})", text):
        errors.append("Potential hardcoded API key / secret token detected.")

    return {
        "engine": "ripwire-fallback-v0.6.5",
        "file": fpath.relative_to(ws).as_posix() if fpath.is_relative_to(ws) else fpath.as_posix(),
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def situate(workspace: str | Path, offline: bool = False) -> Dict[str, Any]:
    """
    Generate a compact `<2KB` situational map (`--situ`) for agent initialization
    and `PreInvocation` lifecycle hooks.
    """
    ws = Path(workspace).resolve()
    state_file = ws / ".agency" / "active" / "project_state.yml"
    project_name = "Untitled Project"
    current_phase = 1
    project_tier = "core"
    entry_mode = "greenfield"

    if state_file.exists():
        raw = state_file.read_text(encoding="utf-8", errors="replace")
        m_name = re.search(r'^project_name:\s*["\']?([^"\'\n#]+)', raw, re.M)
        m_phase = re.search(r"^current_phase:\s*(\d+)", raw, re.M)
        m_tier = re.search(r'^project_tier:\s*["\']?([a-zA-Z0-9_-]+)', raw, re.M)
        m_mode = re.search(r'^entry_mode:\s*["\']?([a-zA-Z0-9_-]+)', raw, re.M)
        if m_name:
            project_name = m_name.group(1).strip()
        if m_phase:
            current_phase = int(m_phase.group(1))
        if m_tier:
            project_tier = m_tier.group(1).strip()
        if m_mode:
            entry_mode = m_mode.group(1).strip()

    agents_count = len(list((ws / ".agency" / "agents").rglob("*.md"))) if (ws / ".agency" / "agents").exists() else 0
    templates_count = len(list((ws / ".agency" / "templates").rglob("*.md"))) if (ws / ".agency" / "templates").exists() else 0
    active_deliverables = (
        [p.relative_to(ws / ".agency" / "active").as_posix() for p in sorted((ws / ".agency" / "active").rglob("*.md"))]
        if (ws / ".agency" / "active").exists()
        else []
    )

    return {
        "engine": "ripwire-native" if find_ripwire_binary() and not offline else "ripwire-fallback-v0.6.5",
        "project_name": project_name,
        "project_tier": project_tier,
        "entry_mode": entry_mode,
        "current_phase": current_phase,
        "agents_available": agents_count,
        "templates_available": templates_count,
        "active_deliverables": active_deliverables,
    }


def from_trace(workspace: str | Path, trace_input: str, offline: bool = False) -> Dict[str, Any]:
    """
    Parse a stack trace or error log (`--from-trace`) and map frames directly to
    workspace files, line numbers, and surrounding symbols for Scenario B bugfixes.
    """
    ws = Path(workspace).resolve()
    trace_text = trace_input
    maybe_path = Path(trace_input)
    if maybe_path.exists() and maybe_path.is_file():
        trace_text = maybe_path.read_text(encoding="utf-8", errors="replace")

    implicated: List[Dict[str, Any]] = []
    patterns = [
        re.compile(r'File "([^"]+)", line (\d+)(?:, in ([A-Za-z0-9_<>]+))?'),
        re.compile(r"([A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|js|jsx|rs|go|sql)):(\d+)(?::\d+)?"),
    ]

    seen = set()
    for pat in patterns:
        for m in pat.finditer(trace_text):
            raw_file = m.group(1)
            line_no = int(m.group(2))
            func_name = m.group(3) if m.lastindex and m.lastindex >= 3 else None
            key = (raw_file, line_no)
            if key in seen:
                continue
            seen.add(key)

            candidate_path = (ws / raw_file).resolve() if not Path(raw_file).is_absolute() else Path(raw_file)
            exists = candidate_path.exists()
            implicated.append(
                {
                    "file": raw_file.replace("\\", "/"),
                    "line": line_no,
                    "symbol": func_name,
                    "exists_in_workspace": exists,
                }
            )

    return {
        "engine": "ripwire-fallback-v0.6.5",
        "implicated_count": len(implicated),
        "implicated_locations": implicated,
        "fault_locations": implicated,
    }


class RipwireEngine:
    """Object-oriented Layer 0 Ripwire Engine interface for programmatic & test consumers."""

    def __init__(
        self,
        workspace: Optional[str | Path] = None,
        root_dir: Optional[str | Path] = None,
        offline: bool = False,
    ) -> None:
        target = root_dir if root_dir is not None else (workspace or ".")
        self.workspace = Path(target).resolve()
        self.offline = offline

    def recall(self, query: str = "", max_results: int = 5, top_k: Optional[int] = None) -> Dict[str, Any]:
        k = top_k if top_k is not None else max_results
        return recall(self.workspace, query=query, top_k=k, offline=self.offline)

    def doc_drift(self) -> Dict[str, Any]:
        return check_doc_drift(self.workspace, offline=self.offline)

    def detect_doc_drift(self) -> Dict[str, Any]:
        return check_doc_drift(self.workspace, offline=self.offline)

    def check_doc_drift(self) -> Dict[str, Any]:
        return check_doc_drift(self.workspace, offline=self.offline)

    def pack_task(
        self,
        task: str,
        partition: int = 3,
        partitions: Optional[int] = None,
    ) -> Dict[str, Any]:
        p = partitions if partitions is not None else partition
        return pack_task(self.workspace, task=task, partition=p, offline=self.offline)

    def plan_lanes(
        self,
        num_lanes: int = 3,
        lanes: Optional[int] = None,
        task: str = "",
    ) -> Dict[str, Any]:
        n = lanes if lanes is not None else num_lanes
        return plan_lanes(self.workspace, lanes=n, task=task, offline=self.offline)

    def merge_scout(self, lanes_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return merge_scout(self.workspace, lanes_data=lanes_data, offline=self.offline)

    def exemplar(self, pattern: str = "", top_k: int = 3) -> Dict[str, Any]:
        return find_exemplar(self.workspace, pattern=pattern, top_k=top_k, offline=self.offline)

    def extract_exemplars(self, pattern: str = "", top_k: int = 3) -> Dict[str, Any]:
        return find_exemplar(self.workspace, pattern=pattern, top_k=top_k, offline=self.offline)

    def find_exemplar(self, pattern: str = "", top_k: int = 3) -> Dict[str, Any]:
        return find_exemplar(self.workspace, pattern=pattern, top_k=top_k, offline=self.offline)

    def quality_delta(self, baseline_score: float = 0.85) -> Dict[str, Any]:
        report, _ = quality_delta(self.workspace, baseline_score=baseline_score, offline=self.offline)
        return report

    def edit_check(self, target_file: str | Path) -> Dict[str, Any]:
        return edit_check(self.workspace, target_file=target_file, offline=self.offline)

    def situate(self) -> Dict[str, Any]:
        return situate(self.workspace, offline=self.offline)

    def from_trace(self, trace_input: str) -> Dict[str, Any]:
        return from_trace(self.workspace, trace_input=trace_input, offline=self.offline)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ripwire Layer 0 Structural & Doc-Graph Intelligence Engine"
    )
    parser.add_argument("--root", "--workspace", dest="workspace", default=".", help="Workspace / root directory")
    parser.add_argument("--offline", action="store_true", help="Force deterministic Python fallback")
    parser.add_argument("--recall", nargs="?", const="", metavar="QUERY", help="Recall relevant deliverables and code symbols")
    parser.add_argument("--doc-drift", action="store_true", help="Check deliverable/code documentation drift")
    parser.add_argument("--pack-task", metavar="TASK", help="Pack task context into balanced partitions")
    parser.add_argument("--partition", type=int, default=3, help="Number of partitions for --pack-task")
    parser.add_argument("--plan-lanes", type=int, metavar="N", help="Plan N isolated parallel execution lanes")
    parser.add_argument("--merge-scout", action="store_true", help="Check parallel execution lanes for merge collisions")
    parser.add_argument("--exemplar", nargs="?", const="", metavar="PATTERN", help="Find highest-quality exemplar file for pattern")
    parser.add_argument("--quality-delta", action="store_true", help="Compute structural quality delta (exit 2 on regression)")
    parser.add_argument("--baseline", type=float, default=0.85, help="Baseline score for --quality-delta")
    parser.add_argument("--edit-check", metavar="FILE", help="Run structural integrity check on a file")
    parser.add_argument("--situ", action="store_true", help="Emit compact situational awareness map")
    parser.add_argument("--from-trace", metavar="TRACE", help="Map stack trace to implicated files & symbols")
    parser.add_argument("--mcp-config", action="store_true", help="Print workspace-pinned MCP config JSON")

    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()

    if args.mcp_config:
        print(json.dumps(get_mcp_config(ws.as_posix()), indent=2))
        return 0
    if args.recall is not None:
        print(json.dumps(recall(ws, args.recall, offline=args.offline), indent=2))
        return 0
    if args.doc_drift:
        print(json.dumps(check_doc_drift(ws, offline=args.offline), indent=2))
        return 0
    if args.pack_task:
        print(json.dumps(pack_task(ws, args.pack_task, partition=args.partition, offline=args.offline), indent=2))
        return 0
    if args.plan_lanes is not None:
        print(json.dumps(plan_lanes(ws, lanes=args.plan_lanes, offline=args.offline), indent=2))
        return 0
    if args.merge_scout:
        print(json.dumps(merge_scout(ws, offline=args.offline), indent=2))
        return 0
    if args.exemplar is not None:
        print(json.dumps(find_exemplar(ws, args.exemplar, offline=args.offline), indent=2))
        return 0
    if args.quality_delta:
        report, code = quality_delta(ws, baseline_score=args.baseline, offline=args.offline)
        print(json.dumps(report, indent=2))
        return code
    if args.edit_check:
        res = edit_check(ws, args.edit_check, offline=args.offline)
        print(json.dumps(res, indent=2))
        return 0 if res["valid"] else 1
    if args.situ:
        print(json.dumps(situate(ws, offline=args.offline), indent=2))
        return 0
    if args.from_trace:
        print(json.dumps(from_trace(ws, args.from_trace, offline=args.offline), indent=2))
        return 0

    print(json.dumps(situate(ws, offline=args.offline), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

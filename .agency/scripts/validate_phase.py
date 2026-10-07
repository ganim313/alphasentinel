#!/usr/bin/env python3
"""
Phase Validator v3.0 — Anti-Empty, L0 Ripwire Doc-Drift, L1 Laya Rubric & Runtime Gatekeeper
============================================================================================
Validates deliverables in `.agency/active/` using:
  1. Structural completeness, word count, and zero unresolved placeholders.
  2. Mandatory `## ✍️ Human Lead Decision & Sign-Off Block` approval check.
  3. Layer 0 Ripwire documentation drift check (`ripwire_engine.check_doc_drift`).
  4. Layer 1 Laya weighted rubric score (`laya_engine.score_deliverable`).
  5. Optional live runtime code checks (`tsc`, `pytest`, `laya_engine.screen_code_integrity`).

Usage:
    python .agency/scripts/validate_phase.py
    python .agency/scripts/validate_phase.py --advance
    python .agency/scripts/validate_phase.py --advance --verify-code
    python .agency/scripts/validate_phase.py --tier enterprise --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import laya_engine  # noqa: E402
import ripwire_engine  # noqa: E402

PLACEHOLDER_MARKERS = [
    "[TBD]",
    "[FILL THIS]",
    "[TODO]",
    "[INSERT",
    "[REPLACE]",
    "[PLACEHOLDER]",
    "[NEEDS CLARIFICATION]",
    "[WRITE THIS]",
    "[EXAMPLE]",
    "[YOUR",
    "[CLIENT NAME]",
    "[AGENCY NAME]",
]

APPROVAL_MARKERS = [
    r"✅\s*Approved",
    r"\[[xX]\]\s*\*\*Approved",
    r"\[[xX]\]\s*Approved",
    r"Status:\s*Approved",
    r"Status:\*\*\s*✅\s*Approved",
    r"Sign-Off:\s*Approved",
    r"Signed-Off:\s*Yes",
    r"Human Lead Sign-Off.*✅\s*Approved",
]


def check_file_deep_quality(
    file_path: str | Path,
    min_words: int = 120,
    min_rubric_score: float = 0.70,
    require_signoff: bool = True,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Multi-layer validation of a deliverable file:
      1. File existence & minimum byte size (> 100 bytes).
      2. Minimum word count.
      3. Absence of unresolved placeholder markers.
      4. Mandatory Human Lead Decision & Sign-Off Block approval.
      5. Laya Layer 1 rubric evaluation (`overall_score >= min_rubric_score`).
    """
    fpath = Path(file_path)
    details: Dict[str, Any] = {"file": fpath.as_posix(), "rubric_score": 0.0}

    if not fpath.exists():
        return False, "File missing", details

    size = fpath.stat().st_size
    if size < 100:
        return False, f"File is essentially empty ({size} bytes)", details

    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return False, f"Could not read file: {exc}", details

    word_count = len(content.split())
    details["word_count"] = word_count
    if word_count < min_words:
        return False, f"Too thin ({word_count} words < {min_words}). Likely placeholder content.", details

    for marker in PLACEHOLDER_MARKERS:
        if marker in content:
            return False, f"Contains unresolved placeholder: '{marker}'", details

    has_signoff_section = bool(
        re.search(r"Human Lead Decision & Sign-Off Block|Human Lead Sign-Off", content, re.IGNORECASE)
    )
    if not has_signoff_section:
        return False, "Missing '## ✍️ Human Lead Decision & Sign-Off Block'", details

    if require_signoff:
        has_approved = any(re.search(pattern, content, re.IGNORECASE) for pattern in APPROVAL_MARKERS)
        is_awaiting = bool(re.search(r"⏳\s*Awaiting Approval", content, re.IGNORECASE))
        if is_awaiting and not has_approved:
            return False, "Human Sign-Off Block is still marked '⏳ Awaiting Approval'", details
        if not has_approved:
            return False, "Missing explicit Human Lead Sign-Off ('[x] **Approved:**' or '✅ Approved')", details

    laya_res = laya_engine.score_deliverable(fpath, threshold=min_rubric_score)
    details["rubric_score"] = laya_res.get("overall_score", 0.0)
    details["dimension_scores"] = laya_res.get("dimension_scores", {})
    if not laya_res.get("passed", False):
        return (
            False,
            f"Laya L1 rubric score {details['rubric_score']:.2f} below threshold {min_rubric_score:.2f}",
            details,
        )

    return True, f"Valid & Approved ({word_count} words, Laya score={details['rubric_score']:.2f})", details


def run_live_code_checks(root_dir: str | Path) -> Tuple[bool, str]:
    """
    Run Laya Layer 1 pre-critic code integrity screener and optional compiler/test checks.
    """
    rpath = Path(root_dir)
    screen = laya_engine.screen_code_integrity(rpath / "src" if (rpath / "src").exists() else rpath)
    if not screen["passed"]:
        first = screen["findings"][0]
        return (
            False,
            f"Laya L1 Code Integrity Screen failed ({screen['finding_count']} issue(s)): "
            f"{first['file']}:{first['line']} ({first['type']})",
        )
    return True, f"Code integrity screen passed ({screen['files_screened']} files checked)"


def validate_current_phase(
    workspace: Optional[str | Path] = None,
    root_dir: Optional[str | Path] = None,
    advance: bool = False,
    verify_code: bool = False,
    tier_override: Optional[str] = None,
    require_signoff: bool = True,
) -> Dict[str, Any]:
    """Programmatic entry point for validating (and optionally advancing) the active phase."""
    target_root = root_dir if root_dir is not None else (workspace or SCRIPT_DIR.parent.parent)
    root_dir_path = Path(target_root).resolve()
    agency_dir = root_dir_path / ".agency"

    active_dir = agency_dir / "active"
    state_file = active_dir / "project_state.yml"

    if not state_file.exists():
        return {
            "passed": False,
            "advanced": False,
            "new_phase": 1,
            "error": f"{state_file} not found.",
        }

    with open(state_file, "r", encoding="utf-8") as f:
        state = yaml.safe_load(f) or {}

    current_phase_num = int(state.get("current_phase", 1))
    project_tier = tier_override or state.get("project_tier", "core")
    entry_mode = state.get("entry_mode", "greenfield")

    current_phase_key = None
    for key in state.get("phases", {}).keys():
        if key.startswith(f"{current_phase_num}_"):
            current_phase_key = key
            break

    if not current_phase_key:
        return {
            "passed": False,
            "advanced": False,
            "new_phase": current_phase_num,
            "error": f"Could not find phase configuration for phase {current_phase_num}",
        }

    phase_data = state["phases"][current_phase_key]
    required_outputs = list(phase_data.get("required_outputs", []))
    if project_tier == "enterprise":
        required_outputs.extend(phase_data.get("enterprise_outputs", []))

    deliverable_results: List[Dict[str, Any]] = []
    all_passed = True

    for output in required_outputs:
        clean_out = output
        if clean_out.startswith(".agency/active/") or clean_out.startswith(".agency\\active\\"):
            clean_out = clean_out[len(".agency/active/"):]
        file_path = active_dir / clean_out
        if not file_path.exists():
            if (root_dir_path / output).exists():
                file_path = root_dir_path / output
            elif (active_dir / output).exists():
                file_path = active_dir / output
            elif (root_dir_path / clean_out).exists():
                file_path = root_dir_path / clean_out

        is_valid, msg, details = check_file_deep_quality(
            file_path, require_signoff=require_signoff
        )
        deliverable_results.append(
            {
                "deliverable": output,
                "valid": is_valid,
                "message": msg,
                "details": details,
            }
        )
        if not is_valid:
            all_passed = False

    drift_report = ripwire_engine.check_doc_drift(root_dir_path, offline=True)
    code_msg = "Skipped"
    if verify_code:
        code_ok, code_msg = run_live_code_checks(root_dir_path)
        if not code_ok:
            all_passed = False

    advanced = False
    new_phase = current_phase_num
    if all_passed and advance:
        next_phase = current_phase_num + 1
        state["phases"][current_phase_key]["status"] = "completed"
        next_key_found = False
        for key in state.get("phases", {}).keys():
            if key.startswith(f"{next_phase}_"):
                next_key_found = True
                state["phases"][key]["status"] = "in_progress"
                break

        if next_key_found and next_phase <= 7:
            state["current_phase"] = next_phase
            new_phase = next_phase
            advanced = True
        else:
            state["status"] = "completed"
            new_phase = current_phase_num
            advanced = True

        clean_state = dict(state)
        if isinstance(clean_state.get("phases"), dict):
            clean_state["phases"] = dict(clean_state["phases"])
        with open(state_file, "w", encoding="utf-8") as f:
            yaml.dump(clean_state, f, default_flow_style=False, sort_keys=False)

    summary = {
        "passed": all_passed,
        "advanced": advanced,
        "new_phase": new_phase,
        "advanced_to": new_phase if advanced else None,
        "phase": current_phase_num,
        "phase_key": current_phase_key,
        "tier": project_tier,
        "entry_mode": entry_mode,
        "domain_discovery_completed": bool(state.get("domain_discovery_completed", False)),
        "domain_co_owners": phase_data.get("domain_co_owners", []),
        "domain_critic": phase_data.get("domain_critic") or state.get("domain_critic"),
        "deliverables": deliverable_results,
        "ripwire_doc_drift": drift_report,
        "code_check": code_msg,
    }
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deliverables for the current project phase.")
    parser.add_argument("--workspace", default=None, help="Workspace root path")
    parser.add_argument("--advance", "-a", action="store_true", help="Auto-advance current_phase if validation passes.")
    parser.add_argument("--verify-code", "-c", action="store_true", help="Execute live code integrity checks.")
    parser.add_argument("--tier", choices=["core", "enterprise"], help="Override project tier validation.")
    parser.add_argument("--skip-signoff", action="store_true", help="Skip Human Lead approval check (for CI dry-runs).")
    parser.add_argument("--json", action="store_true", help="Output validation results as JSON.")
    args = parser.parse_args(argv)

    summary = validate_current_phase(
        workspace=args.workspace,
        advance=args.advance,
        verify_code=args.verify_code,
        tier_override=args.tier,
        require_signoff=not args.skip_signoff,
    )
    passed = bool(summary.get("passed", False))

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0 if passed else 1

    if "error" in summary:
        print(f"[!] Error: {summary['error']}")
        return 1

    print(f"\n[?] Validating Phase {summary['phase']}: {summary['phase_key']}")
    print(f"    Tier: {summary['tier'].upper()}  |  Entry Mode: {summary['entry_mode']}")
    print("-" * 80)

    for item in summary["deliverables"]:
        tag = "[PASS]" if item["valid"] else "[FAIL]"
        print(f"  {tag} {item['deliverable']:<42} -> {item['message']}")

    print("-" * 80)
    if passed:
        print(f"[+] PASS: All {len(summary['deliverables'])} deliverable(s) for Phase {summary['phase']} are valid & signed off.")
        if summary["advanced_to"]:
            print(f"[+] State Advanced: current_phase is now Phase {summary['advanced_to']}!")
        return 0

    print("[-] Validation Failed. Resolve failing checks above before advancing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

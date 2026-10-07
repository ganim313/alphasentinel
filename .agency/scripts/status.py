#!/usr/bin/env python3
"""
Agency Project Dashboard v3.0 (Antigravity 2.0 + Ripwire L0 + Laya L1)
======================================================================
Live terminal progress dashboard with budget burn tracking, 33-template
deliverable awareness, Ripwire Layer 0 structural telemetry, and Laya Layer 1
readiness status.

Usage:
    python .agency/scripts/status.py
    python .agency/scripts/status.py --json
    python agency.py status
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def render_progress_bar(percent: int, width: int = 30) -> str:
    percent = max(0, min(100, int(percent)))
    filled = int(width * (percent / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent}%"


def format_hours(hours: float | int) -> str:
    if not hours:
        return "—"
    return f"{hours}h"


class PhaseDict(dict):
    """
    Dictionary of phases that supports:
      - String key access: state["phases"]["1_intake_and_proposal"]
      - Integer 0-based index access: state["phases"][0]
      - len(state["phases"]) == 7
      - Iteration over keys / items / values
    """

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            keys = list(self.keys())
            if 0 <= key < len(keys) or -len(keys) <= key < 0:
                return super().__getitem__(keys[key])
            raise IndexError(f"Phase index {key} out of range (0-{len(keys)-1})")
        if isinstance(key, slice):
            keys = list(self.keys())
            return [super().__getitem__(k) for k in keys[key]]
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if isinstance(key, int):
            keys = list(self.keys())
            if 0 <= key < len(keys) or -len(keys) <= key < 0:
                return super().__getitem__(keys[key])
            return default
        return super().get(key, default)


try:
    yaml.SafeDumper.add_representer(PhaseDict, yaml.representer.SafeRepresenter.represent_dict)
    yaml.Dumper.add_representer(PhaseDict, yaml.representer.SafeRepresenter.represent_dict)
except Exception:
    pass


def load_project_state(
    state_path: Optional[str | Path] = None,
    root_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Load `project_state.yml` and return its parsed YAML dictionary with 0-indexed phases."""
    target = root_dir if root_dir is not None else state_path
    if target is None:
        fpath = SCRIPT_DIR.parent / "active" / "project_state.yml"
    else:
        fpath = Path(target)
        if fpath.is_dir():
            fpath = fpath / ".agency" / "active" / "project_state.yml"
            if not fpath.exists():
                alt = Path(target) / "active" / "project_state.yml"
                if alt.exists():
                    fpath = alt

    if not fpath.exists():
        raise FileNotFoundError(f"{fpath} not found. Run 'python agency.py init' or './bootstrap.ps1'.")

    with open(fpath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_phases = data.get("phases", {})
    if isinstance(raw_phases, dict):
        tier = data.get("project_tier", "core")
        for key, pdata in raw_phases.items():
            if isinstance(pdata, dict):
                req_outputs = list(pdata.get("required_outputs", []))
                if tier == "enterprise":
                    req_outputs.extend(pdata.get("enterprise_outputs", []))
                deliverables = []
                for out in req_outputs:
                    deliverables.append(
                        {
                            "name": Path(out).stem,
                            "output": f".agency/active/{out}",
                            "file": out,
                        }
                    )
                pdata["deliverables"] = deliverables
        data["phases"] = PhaseDict(raw_phases)

    return data


def get_status_report(workspace: Optional[str | Path] = None) -> Dict[str, Any]:
    """Build structured status report for CLI and programmatic consumption."""
    if workspace:
        ws = Path(workspace).resolve()
        agency_dir = ws / ".agency"
    else:
        agency_dir = SCRIPT_DIR.parent
        ws = agency_dir.parent

    active_dir = agency_dir / "active"
    state_file = active_dir / "project_state.yml"
    state = load_project_state(state_file)

    project_name = state.get("project_name", "Untitled Project")
    client_name = state.get("client_name", "Unknown")
    current_phase = int(state.get("current_phase", 1))
    project_tier = state.get("project_tier", "core")
    entry_mode = state.get("entry_mode", "greenfield")
    overall_status = state.get("status", "in_progress")

    budget = state.get("budget", {}) or {}
    hours_est = budget.get("estimated_hours", budget.get("hours_estimated", 0))
    hours_log = budget.get("logged_hours", budget.get("hours_logged", 0))
    hourly_rate = budget.get("hourly_rate_usd", budget.get("hourly_rate", 150))
    total_quoted = budget.get("total_quoted_usd", budget.get("total_quoted", 0))

    phases = state.get("phases", {}) or {}
    total_phases = len(phases)
    completed_count = 0
    phase_rows: List[Dict[str, Any]] = []

    for key, data in phases.items():
        parts = key.split("_", 1)
        p_num = int(parts[0]) if parts[0].isdigit() else 0
        p_title = parts[1].replace("_", " ").title() if len(parts) > 1 else key

        if data.get("execution_mode") == "parallel_fork":
            tracks = data.get("parallel_tracks", {})
            role_str = " | ".join(
                [f"@{info.get('assigned_role', '')}" for _, info in tracks.items()]
            )
        else:
            role_str = f"@{data.get('assigned_role', 'Unassigned')}"

        req_outputs = list(data.get("required_outputs", []))
        if project_tier == "enterprise":
            req_outputs.extend(data.get("enterprise_outputs", []))

        existing_outputs = []
        for out in req_outputs:
            out_path = active_dir / out
            if out_path.exists() and out_path.stat().st_size > 100:
                existing_outputs.append(out)

        if len(existing_outputs) == len(req_outputs) and len(req_outputs) > 0:
            status_icon = "[✅ DONE]"
            completed_count += 1
        elif p_num == current_phase:
            status_icon = "[▶️ ACTIVE]"
        elif p_num < current_phase:
            status_icon = "[⏸️ PARTIAL]"
        else:
            status_icon = "[⏳ PENDING]"

        phase_rows.append(
            {
                "phase_num": p_num,
                "key": key,
                "title": p_title,
                "status_icon": status_icon,
                "role_display": role_str,
                "completed_docs": len(existing_outputs),
                "total_docs": len(req_outputs),
                "docs_summary": f"{len(existing_outputs)}/{len(req_outputs)} docs",
            }
        )

    percent = int((completed_count / total_phases) * 100) if total_phases > 0 else 0
    situ = ripwire_engine.situate(ws, offline=True)

    return {
        "project_name": project_name,
        "client_name": client_name,
        "current_phase": current_phase,
        "project_tier": project_tier,
        "entry_mode": entry_mode,
        "status": overall_status,
        "progress_percent": percent,
        "budget": {
            "total_quoted_usd": total_quoted,
            "hourly_rate_usd": hourly_rate,
            "estimated_hours": hours_est,
            "logged_hours": hours_log,
        },
        "intelligence": {
            "layer_0_ripwire": situ["engine"],
            "layer_1_laya": "laya-native" if laya_engine.is_laya_native_available() else "laya-system1-fallback",
            "agents_roster_count": situ["agents_available"],
            "templates_library_count": situ["templates_available"],
        },
        "phases": phase_rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Agency Playbook Live Status Dashboard")
    parser.add_argument("--workspace", default=None, help="Workspace root directory")
    parser.add_argument("--json", action="store_true", help="Output dashboard state as JSON")
    args = parser.parse_args(argv)

    try:
        report = get_status_report(args.workspace)
    except FileNotFoundError as exc:
        print(f"[!] Error: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    b = report["budget"]
    intel = report["intelligence"]

    print("\n" + "=" * 92)
    print(f"  AGENCY PROJECT DASHBOARD: {report['project_name'].upper()}")
    print(
        f"  Client: {report['client_name']}  |  Tier: {report['project_tier'].upper()}  |  "
        f"Entry: {report['entry_mode'].upper()}  |  Status: {report['status'].upper()}"
    )
    print(
        f"  Layer 0 (Ripwire): {intel['layer_0_ripwire']}  |  "
        f"Layer 1 (Laya): {intel['layer_1_laya']}  |  "
        f"Roster: {intel['agents_roster_count']} Agents / {intel['templates_library_count']} Templates"
    )
    print("=" * 92)

    if b["estimated_hours"] > 0 or b["total_quoted_usd"] > 0:
        print("\n  💰 BUDGET TRACKING")
        print(
            f"     Quoted: ${b['total_quoted_usd']:,}  |  Rate: ${b['hourly_rate_usd']}/hr  |  "
            f"Est: {format_hours(b['estimated_hours'])}  |  Logged: {format_hours(b['logged_hours'])}"
        )
        if b["estimated_hours"] > 0 and b["logged_hours"] > 0:
            burn_pct = int((b["logged_hours"] / b["estimated_hours"]) * 100)
            print(f"     Burn: {render_progress_bar(burn_pct, width=20)}")
        print("-" * 92)

    print(f"\n  Overall Progress: {render_progress_bar(report['progress_percent'])}")
    print("-" * 92)
    print(f" {'Phase':<7} | {'Phase Title':<24} | {'Status':<12} | {'Assigned Role / Track':<30} | {'Deliverables'}")
    print("-" * 92)

    for row in report["phases"]:
        active_marker = "→" if row["phase_num"] == report["current_phase"] else "  "
        role_short = row["role_display"][:30]
        print(
            f"{active_marker} P{row['phase_num']:<4} | {row['title']:<24} | "
            f"{row['status_icon']:<12} | {role_short:<30} | {row['docs_summary']}"
        )

    print("=" * 92)
    print("\n>> Quick Actions:")
    print("     Validate & Advance: python agency.py validate --advance")
    print("     Route a Task (L1):  python agency.py route \"<task description>\"")
    print("     Health Check:       python agency.py doctor\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

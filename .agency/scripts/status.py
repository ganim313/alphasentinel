#!/usr/bin/env python3
"""
Agency Project Dashboard v2.0
==============================
Live terminal progress dashboard with budget burn tracking.

Usage:
    python .agency/scripts/status.py
"""

import os
import sys
import yaml

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def render_progress_bar(percent, width=30):
    filled = int(width * (percent / 100))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent}%"

def format_hours(hours):
    if hours == 0:
        return "—"
    return f"{hours}h"

def main():
    agency_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    active_dir = os.path.join(agency_dir, "active")
    state_file = os.path.join(active_dir, "project_state.yml")

    if not os.path.exists(state_file):
        print(f"[!] Error: {state_file} not found. Is there an active project?")
        print("[!] Run: ./bootstrap.sh \"Client Name\" \"project-slug\"")
        sys.exit(1)

    with open(state_file, "r", encoding="utf-8") as f:
        state = yaml.safe_load(f)

    project_name = state.get("project_name", "Untitled Project")
    client_name = state.get("client_name", "Unknown")
    current_phase = state.get("current_phase", 1)
    project_tier = state.get("project_tier", "core")
    entry_mode = state.get("entry_mode", "greenfield")
    overall_status = state.get("status", "in_progress")

    budget = state.get("budget", {})
    hours_est = budget.get("hours_estimated", 0)
    hours_log = budget.get("hours_logged", 0)
    hourly_rate = budget.get("hourly_rate", 0)
    total_quoted = budget.get("total_quoted", 0)

    phases = state.get("phases", {})
    total_phases = len(phases)

    completed_count = 0
    phase_rows = []

    for key, data in phases.items():
        parts = key.split("_", 1)
        p_num = int(parts[0]) if parts[0].isdigit() else 0
        p_title = parts[1].replace("_", " ").title() if len(parts) > 1 else key

        # Handle parallel tracks vs single role
        if data.get("execution_mode") == "parallel_fork":
            tracks = data.get("parallel_tracks", {})
            role_str = " | ".join([f"@{info.get('assigned_role').replace('_engineer', '')}" for t, info in tracks.items()])
        else:
            role_str = f"@{data.get('assigned_role', 'Unassigned')}"

        req_outputs = list(data.get("required_outputs", []))
        if project_tier == "enterprise":
            req_outputs.extend(data.get("enterprise_outputs", []))

        # Check files on disk
        existing_outputs = []
        for out in req_outputs:
            out_path = os.path.join(active_dir, out)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
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

        phase_rows.append((p_num, p_title, status_icon, role_str, f"{len(existing_outputs)}/{len(req_outputs)} docs"))

    percent = int((completed_count / total_phases) * 100) if total_phases > 0 else 0

    print("\n" + "=" * 85)
    print(f"  AGENCY PROJECT DASHBOARD: {project_name.upper()}")
    print(f"  Client: {client_name}  |  Tier: {project_tier.upper()}  |  Entry: {entry_mode.upper()}")
    print(f"  Status: {overall_status.upper()}")
    print("=" * 85)

    # Budget block
    if hours_est > 0 or total_quoted > 0:
        print(f"\n  💰 BUDGET TRACKING")
        print(f"     Quoted: ${total_quoted:,}  |  Rate: ${hourly_rate}/hr  |  Est: {format_hours(hours_est)}  |  Logged: {format_hours(hours_log)}")
        if hours_est > 0 and hours_log > 0:
            burn_pct = int((hours_log / hours_est) * 100)
            print(f"     Burn: {render_progress_bar(burn_pct, width=20)}")
        print("-" * 85)

    print(f"\n  Overall Progress: {render_progress_bar(percent)}")
    print("-" * 85)
    print(f" {'Phase':<7} | {'Phase Title':<24} | {'Status':<12} | {'Assigned Role / Track':<24} | {'Deliverables'}")
    print("-" * 85)

    for p_num, title, status, role, docs in phase_rows:
        active_marker = "→" if p_num == current_phase else "  "
        print(f"{active_marker} P{p_num:<4} | {title:<24} | {status:<12} | {role:<24} | {docs}")

    print("=" * 85)

    # Print next action
    for key, data in phases.items():
        if key.startswith(f"{current_phase}_"):
            if data.get("execution_mode") == "parallel_fork":
                tracks = data.get("parallel_tracks", {})
                roles = ", ".join([f"@{info.get('assigned_role')}.md" for t, info in tracks.items()])
                print(f"\n>> Active Phase: Parallel Fork. Summon {roles} for Phase {current_phase}.")
            else:
                role = data.get("assigned_role", "product_design/product_manager")
                print(f"\n>> Active Command: Summon @{role}.md to work on Phase {current_phase}.")
            break

    print(f"\n>> Quick Actions:")
    print(f"     Validate & Advance: python .agency/scripts/validate_phase.py --advance")
    print()

if __name__ == "__main__":
    main()

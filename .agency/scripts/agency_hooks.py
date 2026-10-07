#!/usr/bin/env python3
"""
Antigravity 2.0 Lifecycle Hook Handler (.agency/scripts/agency_hooks.py)

Implements the official Antigravity 2.0 protojson hook contract across 4 events:
  1. `PreInvocation`:
     - Resolves `workspacePaths[0]` safely or uses optional `root_dir`.
     - Strictly gated on `invocationNum == 1` (returns `{}` on subsequent turns
       to prevent context bloat).
     - Injects compact (<2KB) situational context via `injectSteps: [{"ephemeralMessage": ...}]`.
  2. `PreToolUse`:
     - Guards against accidental execution of archived destructive root scripts
       (`generate_agents.py`, `migrate_templates.py`, `strip_blocks.py`).
     - Inspects tool calls (e.g. `write_to_file`, `replace_file_content`) for secret
       leaks (e.g. `sk-proj-`, API keys) and lazy placeholders (`TODO: implement later`,
       `// ... rest of code`, `[TBD]`, `[TODO]`).
     - Returns `{"decision": "deny", "reason": ...}` when blocked, and
       `{"decision": "allow"}` otherwise.
  3. `PostToolUse`:
     - Runs lightweight structural edit verification on modified files.
     - Always outputs `{}` on stdout per the Antigravity 2.0 `PostToolUse` contract.
  4. `Stop`:
     - Enforces a strict circuit breaker (`executionNum >= 3`) allowing exit so the agent
       can never enter an infinite stop-hook loop.
     - Returns `{"decision": "continue", "reason": ...}` to block premature stop
       when `enforceStrictStop` is set and high-severity drift exists, or
       `{"decision": "allow"}` otherwise.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import domain_forge  # noqa: E402
import ripwire_engine  # noqa: E402


DESTRUCTIVE_ARCHIVED_SCRIPTS = {
    "generate_agents.py",
    "migrate_templates.py",
    "strip_blocks.py",
}

SECRET_PATTERNS = [
    re.compile(r"sk-proj-[A-Za-z0-9_\-]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{50,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----"),
    re.compile(r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE),
]

LAZY_PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\s*:\s*(?:implement|finish|add\b|later|complete)", re.IGNORECASE),
    re.compile(r"//\s*\.\.\.\s*rest of code", re.IGNORECASE),
    re.compile(r"#\s*\.\.\.\s*rest of code", re.IGNORECASE),
    re.compile(r"/\*\s*\.\.\.\s*rest of code\s*\*/", re.IGNORECASE),
    re.compile(r"//\s*\.\.\.\s*rest of", re.IGNORECASE),
    re.compile(r"#\s*\.\.\.\s*rest of", re.IGNORECASE),
    re.compile(r"\[TODO\]", re.IGNORECASE),
    re.compile(r"\[TBD\]", re.IGNORECASE),
    re.compile(r"\[Insert\b[^\]]*\]", re.IGNORECASE),
]


def resolve_workspace_root(payload: Dict[str, Any], root_dir: Optional[Path] = None) -> Path:
    """Resolve workspacePaths[0] from Antigravity hook payload, falling back to root_dir, repo root, or CWD."""
    if root_dir is not None:
        return Path(root_dir).resolve()
    ws_paths = payload.get("workspacePaths")
    if isinstance(ws_paths, list) and len(ws_paths) > 0 and ws_paths[0]:
        candidate = Path(str(ws_paths[0]))
        if candidate.exists():
            return candidate.resolve()
    cwd = payload.get("cwd")
    if cwd and Path(str(cwd)).exists():
        return Path(str(cwd)).resolve()
    if SCRIPT_DIR.name == "scripts" and SCRIPT_DIR.parent.name == ".agency":
        return SCRIPT_DIR.parent.parent.resolve()
    return Path.cwd().resolve()


def handle_pre_invocation(
    payload: Dict[str, Any],
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Handle `PreInvocation`:
    Only inject situational context on `invocationNum == 1`.
    Uses Antigravity 2.0 `injectSteps: [{"ephemeralMessage": "..."}]` contract
    plus `additionalContext` for programmatic callers.
    """
    invocation_num = int(payload.get("invocationNum", 1))
    if invocation_num != 1:
        return {}

    ws = resolve_workspace_root(payload, root_dir=root_dir)
    situ = ripwire_engine.situate(ws, offline=True)
    dom_ctx = domain_forge.scan_project_context(ws)
    active_list = ", ".join(situ.get("active_deliverables", [])[:5]) or "none yet"

    if dom_ctx["domain_discovery_completed"]:
        dom_banner = (
            f"Domain Specialists Active ({dom_ctx['domain_title']}): "
            f"{', '.join(dom_ctx['installed_domain_agents'])}. "
        )
    else:
        dom_banner = (
            "Domain Discovery Pending: Activate `domain-agent-architect` skill (/grill-me interview) "
            "after checking Intake/PRD and run `python agency.py forge-domain` to install permanent project domain agents. "
        )

    context_msg = (
        f"[Agency OS | Phase {situ['current_phase']} | Tier: {situ['project_tier']} | "
        f"Mode: {situ['entry_mode']} | Engine: {situ['engine']}] "
        f"Active deliverables in .agency/active/: {active_list}. "
        f"{dom_banner}"
        f"Enforce Human Lead Sign-Off before advancing phases."
    )
    msg_clipped = context_msg[:1800]
    return {
        "injectSteps": [
            {
                "ephemeralMessage": msg_clipped,
            }
        ],
        "additionalContext": msg_clipped,
        "domain_discovery_completed": dom_ctx["domain_discovery_completed"],
    }


def _extract_tool_args(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tool arguments from Antigravity 2.0 `toolCall.args` or fallback `tool_input`."""
    tool_call = payload.get("toolCall") or payload.get("tool_call")
    if isinstance(tool_call, dict):
        args = tool_call.get("args")
        if isinstance(args, dict):
            return args
    args = payload.get("args")
    if isinstance(args, dict):
        return args
    tool_input = payload.get("tool_input") or payload.get("toolInput")
    if isinstance(tool_input, dict):
        return tool_input
    return {}


def _extract_content_strings(tool_args: Dict[str, Any]) -> List[str]:
    """Extract code/text strings that should be screened for secrets or lazy placeholders."""
    candidates: List[str] = []
    for key in (
        "CodeContent",
        "ReplacementContent",
        "TargetContent",
        "content",
        "new_content",
        "text",
        "code",
    ):
        val = tool_args.get(key)
        if isinstance(val, str) and val.strip():
            candidates.append(val)
    if not candidates:
        for v in tool_args.values():
            if isinstance(v, str) and ("\n" in v or len(v) > 20):
                candidates.append(v)
    return candidates


def handle_pre_tool_use(
    payload: Dict[str, Any],
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Handle `PreToolUse`:
    1. Blocks execution of archived destructive migration scripts.
    2. Inspects `write_to_file`, `replace_file_content`, and related tool arguments for:
       - Secret leaks (e.g. `sk-proj-...`, API keys).
       - Lazy placeholders (e.g. `TODO: implement later`, `// ... rest of code`).
    Returns `{"decision": "deny", "reason": ...}` when blocked, `{"decision": "allow"}` otherwise.
    """
    tool_args = _extract_tool_args(payload)
    cmd = str(tool_args.get("CommandLine") or tool_args.get("command") or "")

    for bad_script in DESTRUCTIVE_ARCHIVED_SCRIPTS:
        if bad_script in cmd and "--allow-archived" not in cmd:
            return {
                "decision": "deny",
                "reason": (
                    f"Blocked execution of archived destructive migration script '{bad_script}'. "
                    "See .agency/scripts/archive/README.md."
                ),
            }

    content_list = _extract_content_strings(tool_args)
    for text in content_list:
        for sec_pat in SECRET_PATTERNS:
            if sec_pat.search(text):
                return {
                    "decision": "deny",
                    "reason": "Security violation: hardcoded secret or API key detected in tool arguments (e.g. sk-proj-).",
                }
        for lazy_pat in LAZY_PLACEHOLDER_PATTERNS:
            if lazy_pat.search(text):
                return {
                    "decision": "deny",
                    "reason": "Quality gate violation: lazy placeholder detected (e.g. TODO: implement later). Full genuine implementation required.",
                }

    return {"decision": "allow"}


def handle_post_tool_use(
    payload: Dict[str, Any],
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Handle `PostToolUse`:
    Per Antigravity 2.0 spec, `PostToolUse` expects an empty JSON object `{}` on stdout.
    """
    ws = resolve_workspace_root(payload, root_dir=root_dir)
    tool_args = _extract_tool_args(payload)
    target_file = (
        tool_args.get("TargetFile")
        or tool_args.get("file_path")
        or tool_args.get("path")
    )
    if target_file:
        ripwire_engine.edit_check(ws, target_file, offline=True)
    return {}


def handle_stop(
    payload: Dict[str, Any],
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Handle `Stop`:
    Enforce circuit breaker `executionNum >= 3` so stop hooks never loop infinitely.
    Per Antigravity 2.0 spec, `decision: "continue"` blocks stop and re-enters the loop;
    any other value (e.g. `"allow"`) allows the agent to stop.
    """
    execution_num = int(payload.get("executionNum", 1))
    if execution_num >= 3:
        return {"decision": "allow"}

    ws = resolve_workspace_root(payload, root_dir=root_dir)
    drift = ripwire_engine.check_doc_drift(ws, offline=True)
    high_severity = [
        item for item in drift.get("items", []) if item.get("severity") == "high"
    ]
    if high_severity and payload.get("enforceStrictStop") is True:
        first_issue = high_severity[0]
        return {
            "decision": "continue",
            "reason": (
                f"[Agency Stop Gate (attempt {execution_num}/2)] "
                f"{first_issue['file']}: {first_issue['detail']}"
            ),
        }

    return {"decision": "allow"}


def process_hook_event(
    event_name: str,
    payload: Dict[str, Any],
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dispatch hook event to the corresponding handler."""
    event = event_name or payload.get("hook_event_name") or payload.get("hookEventName") or ""
    if event == "PreInvocation":
        return handle_pre_invocation(payload, root_dir=root_dir)
    if event == "PreToolUse":
        return handle_pre_tool_use(payload, root_dir=root_dir)
    if event == "PostToolUse":
        return handle_post_tool_use(payload, root_dir=root_dir)
    if event == "Stop":
        return handle_stop(payload, root_dir=root_dir)
    return {}


def _to_strict_protojson(event_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Strip non-protojson convenience keys before writing to stdout for Antigravity 2.0."""
    if event_name == "PreInvocation":
        if "injectSteps" in result:
            return {"injectSteps": result["injectSteps"]}
        return {}
    if event_name == "PostToolUse":
        return {}
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity 2.0 Agency Lifecycle Hook Handler")
    parser.add_argument(
        "--event",
        choices=["PreInvocation", "PreToolUse", "PostToolUse", "Stop"],
        default="",
        help="Hook lifecycle event name",
    )
    args = parser.parse_args(argv)

    raw_stdin = ""
    if not sys.stdin.isatty():
        try:
            raw_stdin = sys.stdin.read()
        except OSError:
            raw_stdin = ""

    payload: Dict[str, Any] = {}
    if raw_stdin.strip():
        try:
            payload = json.loads(raw_stdin)
        except json.JSONDecodeError:
            payload = {}

    event = args.event or payload.get("hook_event_name") or payload.get("hookEventName") or ""
    result = process_hook_event(event, payload)
    print(json.dumps(_to_strict_protojson(event, result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

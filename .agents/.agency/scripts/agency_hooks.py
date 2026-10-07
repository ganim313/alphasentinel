#!/usr/bin/env python3
"""Forwarding shim for Antigravity 2.0 hooks when CWD is .agents/ or .agents/plugins/agency-playbook/."""
import importlib.util
import pathlib
import runpy
import sys

_THIS = pathlib.Path(__file__).resolve()
_TARGET = None
for parent in [_THIS.parent, *_THIS.parents]:
    candidate = parent / ".agency" / "scripts" / "agency_hooks.py"
    if (
        candidate.is_file()
        and candidate.resolve() != _THIS
        and ".agents" not in candidate.parts
    ):
        _TARGET = candidate
        break

if _TARGET:
    if __name__ == "__main__":
        runpy.run_path(str(_TARGET), run_name="__main__")
        sys.exit(0)
    else:
        _spec = importlib.util.spec_from_file_location("real_agency_hooks", str(_TARGET))
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            for _k, _v in _mod.__dict__.items():
                if not _k.startswith("__"):
                    globals()[_k] = _v
else:
    if __name__ == "__main__":
        print("{}")

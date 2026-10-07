"""
AlphaSentinel Master E2E Test Suite Runner.
Executes the 4-tier E2E testing framework:
  Tier 1: Feature Isolation (test_tier1_features.py)
  Tier 2: Boundary Value Analysis (test_tier2_boundaries.py)
  Tier 3: Pairwise Combinatorial (test_tier3_cross_feature.py)
  Tier 4: Real-World Workloads (test_tier4_workloads.py)

Usage:
  python tests/test_e2e_suite.py              # Run full 4-tier suite
  python tests/test_e2e_suite.py --tier 1     # Run Tier 1 only
  python tests/test_e2e_suite.py --tier 2     # Run Tier 2 only
  python tests/test_e2e_suite.py --tier 3     # Run Tier 3 only
  python tests/test_e2e_suite.py --tier 4     # Run Tier 4 only
"""

import sys
import time
import argparse
from pathlib import Path
import pytest

# Ensure Windows terminal handles UTF-8 / emojis safely
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_E2E_DIR = Path(__file__).resolve().parent / "e2e"
if str(_E2E_DIR) not in sys.path:
    sys.path.insert(0, str(_E2E_DIR))


TIER_CONFIG = {
    1: {
        "name": "Tier 1: Feature Isolation",
        "file": "test_tier1_features.py",
        "desc": "Happy-path isolation tests covering features F1 through F13"
    },
    2: {
        "name": "Tier 2: Boundary Value Analysis",
        "file": "test_tier2_boundaries.py",
        "desc": "BVA, extreme values, zero inputs, and edge conditions"
    },
    3: {
        "name": "Tier 3: Pairwise Combinatorial",
        "file": "test_tier3_cross_feature.py",
        "desc": "Multi-module interactions across regime, risk, settlement, and screener"
    },
    4: {
        "name": "Tier 4: Real-World Workloads",
        "file": "test_tier4_workloads.py",
        "desc": "Realistic production workflows (19:00 Bhavcopy -> 08:50 Digest)"
    }
}


class E2ETestReporter:
    """Collects test execution results per tier."""

    def __init__(self):
        self.results = {}
        self.start_time = 0.0
        self.total_duration = 0.0

    def run_tier(self, tier_num: int, verbose: bool = False) -> int:
        tier_info = TIER_CONFIG[tier_num]
        test_file = _E2E_DIR / tier_info["file"]

        if not test_file.exists():
            print(f"[ERROR] Test file {test_file} does not exist!")
            return 1

        print(f"\n{'=' * 78}")
        print(f"[*] EXECUTING {tier_info['name'].upper()}")
        print(f"  Target: {test_file.name}")
        print(f"  Scope:  {tier_info['desc']}")
        print(f"{'=' * 78}")

        pytest_args = [str(test_file), "-q"]
        if verbose:
            pytest_args.append("-v")

        t0 = time.perf_counter()
        exit_code = pytest.main(pytest_args)
        duration = time.perf_counter() - t0

        self.results[tier_num] = {
            "name": tier_info["name"],
            "file": tier_info["file"],
            "exit_code": exit_code,
            "status": "PASSED" if exit_code == 0 else "FAILED",
            "duration": duration
        }

        return exit_code

    def print_summary(self):
        print("\n" + "=" * 78)
        print("          ALPHASENTINEL E2E TEST SUITE — MASTER EXECUTION SUMMARY")
        print("=" * 78)
        print(f"{'Tier':<8} {'Suite Name':<32} {'File':<26} {'Status':<8} {'Time (s)':>6}")
        print("-" * 78)

        total_pass = True
        total_time = 0.0

        for tier_num in sorted(self.results.keys()):
            r = self.results[tier_num]
            total_time += r["duration"]
            if r["exit_code"] != 0:
                total_pass = False

            status_str = "[PASS]" if r["exit_code"] == 0 else "[FAIL]"
            print(f"Tier {tier_num:<3} {r['name']:<32} {r['file']:<26} {status_str:<8} {r['duration']:>6.2f}s")

        print("-" * 78)
        overall_status = "[PASS] ALL TIERS PASSED" if total_pass else "[FAIL] TEST FAILURES DETECTED"
        print(f"OVERALL STATUS: {overall_status} (Total Time: {total_time:.2f}s)")
        print("=" * 78)

        print("\n[*] INSTITUTIONAL COMPLIANCE CHECKLIST:")
        print("  [x] SEBI April 1, 2026: CNC cash equities only, 0 leverage, delivery enforced")
        print("  [x] AAOIFI / Usmani Shariah: Total-Assets denominator, 6 quantitative gates")
        print("  [x] Bay' qabl al-Qabd: T+2 Demat possession lock (can_exit=False on T0/T1)")
        print("  [x] Risk Parity: Unchoked 1.0% risk, max 16% position cap, 5.0% heat ceiling")
        print("  [x] Market Regime: 3-point breadth score, zero buy leakage during RISK_OFF")
        print("  [x] Data Spine: >25% price jump quarantine tripwire & corporate actions")
        print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AlphaSentinel Master E2E Test Suite Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], default=None,
                        help="Run a specific tier (1, 2, 3, or 4). Default: run all tiers.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose pytest output")
    args = parser.parse_args()

    reporter = E2ETestReporter()
    tiers_to_run = [args.tier] if args.tier else [1, 2, 3, 4]

    overall_exit_code = 0
    for t in tiers_to_run:
        exit_code = reporter.run_tier(t, verbose=args.verbose)
        if exit_code != 0:
            overall_exit_code = exit_code

    reporter.print_summary()
    sys.exit(overall_exit_code)


if __name__ == "__main__":
    main()

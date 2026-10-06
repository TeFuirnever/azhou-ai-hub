#!/usr/bin/env python3
"""Run the same deterministic gates locally and in GitHub Actions.

Every gate runs to completion; the last line of output is always the single
aggregate verdict, so a piped or tailed capture can never end on a passing
note while the run actually failed. ``--print-summary`` additionally emits a
machine-readable JSON summary before that verdict line.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

SUMMARY_SCHEMA = "azhou-hub.verify-summary.v1"
SUCCESS_LINE = "verification passed"
LAUNCH_FAILURE_EXIT = 127


def commands(python: str, *, promotion_evidence: bool = False) -> list[tuple[str, list[str]]]:
    super_caveman = [python, "benchmarks/super-caveman/benchmark.py", "check"]
    if promotion_evidence:
        super_caveman.append("--promotion-evidence")
    return [
        ("repository policy", [python, "scripts/check_repository.py"]),
        ("unit tests", [python, "-m", "unittest", "discover", "-s", "tests"]),
        ("super-repo-pedant benchmark", [python, "benchmarks/super-repo-pedant/benchmark.py", "check"]),
        ("super-caveman benchmark", super_caveman),
        (
            "excalidraw benchmark wiring",
            [python, "benchmarks/excalidraw-diagram/ordinary-model-floor/benchmark.py", "check"],
        ),
        (
            "session-insights benchmark wiring",
            [python, "benchmarks/session-insights/benchmark.py", "check"],
        ),
        ("working-tree whitespace", ["git", "diff", "--check"]),
        ("staged whitespace", ["git", "diff", "--cached", "--check"]),
    ]


def run_gates(python: str, *, promotion_evidence: bool, environment: dict[str, str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for label, command in commands(python, promotion_evidence=promotion_evidence):
        print(f"==> {label}", flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
            exit_code = result.returncode
        except OSError:
            exit_code = LAUNCH_FAILURE_EXIT
        results.append({"label": label, "command": " ".join(command), "exit_code": exit_code})
        if exit_code:
            print(f"FAILED: {label} (exit {exit_code})", file=sys.stderr, flush=True)
    return results


def summary_payload(results: list[dict[str, object]]) -> dict[str, object]:
    failed = [result for result in results if result["exit_code"]]
    return {
        "schema": SUMMARY_SCHEMA,
        "verdict": "failed" if failed else "passed",
        "exit_code": failed[0]["exit_code"] if failed else 0,
        "gates": [
            {
                "label": result["label"],
                "command": result["command"],
                "exit_code": result["exit_code"],
                "status": "failed" if result["exit_code"] else "passed",
            }
            for result in results
        ],
        "failed_gates": [result["label"] for result in failed],
    }


def verdict_line(payload: dict[str, object]) -> str:
    if payload["verdict"] == "passed":
        return SUCCESS_LINE
    failed_labels = ", ".join(str(label) for label in payload["failed_gates"])
    total = len(payload["gates"])
    failed_count = len(payload["failed_gates"])
    return f"verification FAILED ({failed_count} of {total} gates failed: {failed_labels})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the complete Azhou AI Hub repository")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for all Python gates")
    parser.add_argument(
        "--promotion-evidence",
        action="store_true",
        help="Also require Git-external maintainer promotion evidence",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a machine-readable JSON summary (before the final verdict line)",
    )
    args = parser.parse_args(argv)

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    results = run_gates(args.python, promotion_evidence=args.promotion_evidence, environment=environment)
    payload = summary_payload(results)
    if args.print_summary:
        print(json.dumps(payload, indent=2), flush=True)
    print(verdict_line(payload), flush=True)
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

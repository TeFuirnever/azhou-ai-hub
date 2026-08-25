#!/usr/bin/env python3
"""Run the same deterministic gates locally and in GitHub Actions."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def commands(python: str) -> list[tuple[str, list[str]]]:
    return [
        ("repository policy", [python, "scripts/check_repository.py"]),
        ("unit tests", [python, "-m", "unittest", "discover", "-s", "tests"]),
        ("repo-pedant benchmark", [python, "benchmarks/repo-pedant/benchmark.py", "check"]),
        ("super-caveman benchmark", [python, "benchmarks/super-caveman/benchmark.py", "check"]),
        (
            "excalidraw benchmark wiring",
            [python, "benchmarks/excalidraw-diagram/ordinary-model-floor/benchmark.py", "check"],
        ),
        ("working-tree whitespace", ["git", "diff", "--check"]),
        ("staged whitespace", ["git", "diff", "--cached", "--check"]),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the complete Azhou AI Hub repository")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for all Python gates")
    args = parser.parse_args(argv)

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for label, command in commands(args.python):
        print(f"==> {label}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        if result.returncode:
            print(f"FAILED: {label} (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regression-rate signal for the coverage baseline job.

Computes, over a trailing window, the share of behavior-touching commits
that also carry test changes. A commit is behavior-touching when it
changes a non-Markdown path under ``skills/`` or ``scripts/`` outside
``tests/``; it carries tests when it also changes ``tests/``. The signal
is a measurement aid only: it asserts nothing and gates nothing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BEHAVIOR_ROOTS = ("skills/", "scripts/")
TEST_ROOT = "tests/"


def classify(paths: list[str]) -> tuple[bool, bool]:
    """Return (behavior_touching, carries_tests) for one commit's paths.

    Skill Markdown (``skills/**.md``) is the skill's behavior surface and
    counts; Markdown outside ``skills/`` is documentation and does not.
    """
    normalized = [p.replace("\\", "/") for p in paths]
    tests = any(p.startswith(TEST_ROOT) for p in normalized)
    behavior = any(
        p.startswith(BEHAVIOR_ROOTS)
        and not p.startswith(TEST_ROOT)
        and (p.startswith("skills/") or not p.endswith(".md"))
        for p in normalized
    )
    return behavior, tests


def commits_since(window_days: int, repo: Path) -> list[list[str]]:
    """Parse `git log` into per-commit path lists for the trailing window."""
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).date().isoformat()
    raw = subprocess.run(
        ["git", "-C", str(repo), "log", f"--since={since}T00:00:00+00:00",
         "--format=@%H", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout
    commits: list[list[str]] = []
    current: list[str] | None = None
    for line in raw.splitlines():
        if line.startswith("@"):
            current = []
            commits.append(current)
        elif line.strip() and current is not None:
            current.append(line.strip())
    return [paths for paths in commits if paths]


def rate(commits: list[list[str]]) -> dict[str, int | float | str]:
    behavior = 0
    carries = 0
    for paths in commits:
        touched, tests = classify(paths)
        if not touched:
            continue
        behavior += 1
        carries += 1 if tests else 0
    ratio: float | str = round(carries / behavior, 4) if behavior else "n/a"
    return {"behavior_commits": behavior, "carrying_tests": carries, "regression_rate": ratio}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=30, help="trailing window in days")
    parser.add_argument("--repo", default=".", help="repository root")
    args = parser.parse_args(argv)
    print(json.dumps(rate(commits_since(args.window, Path(args.repo)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

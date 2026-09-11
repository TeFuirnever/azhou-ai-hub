#!/usr/bin/env python3
"""Recall batteries for chain-of-thought leakage probes.

Probes are over-match by design: every hit needs semantic judgment against the
taxonomy's keep-list. A zero-hit result proves nothing until the probe matches
a known positive, and a noisy pattern proves nothing until it rejects a
near-miss negative. Calibration fixtures live in this repository's tests.

Files that fail strict UTF-8 decoding are skipped (binary content carries no prose). Exit codes: 0 clean, 1 findings, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "super-prose-standard.batteries.v1"
DEFAULT_EXCLUDES = {".git", ".azhou", ".omc", ".omx", "node_modules", "vendor", "__pycache__"}

# (probe id, compiled pattern, applies-to) — applies-to "zh" restricts a probe
# to Chinese-mirror surfaces (*.zh.md, *.zh-CN.md); all others scan every file.
PROBES: list[tuple[str, re.Pattern[str], str]] = [
    ("citation", re.compile(r"\(decision \d|\(audit [A-Z]\d|design §|plan §|design ledger|\(B ruling|\bP-I\b|\bT\d\b|\bW\d\b"), "all"),
    ("vantage", re.compile(r"\bthis PR\b|\bthis branch\b|\bthis stack\b|\bthis commit\b|\blater PRs?\b|\bprevious commits?\b", re.IGNORECASE), "all"),
    ("narration", re.compile(r"\bused to\b|\bno longer\b|\bpreviously\b|\bthe old\b|\bwas renamed\b|\bwas moved\b", re.IGNORECASE), "all"),
    ("stamp", re.compile(r"\bv1\b|this cut|cut \d|\btoday\b|\bfor now\b|roadmap", re.IGNORECASE), "all"),
    ("review", re.compile(r"rejected in review|review round|reviewer|as of v\d", re.IGNORECASE), "all"),
    ("hedge", re.compile(r"probably |should be enough|should suffice|it simply|is safe \u2014|is safe --", re.IGNORECASE), "all"),
    ("draft-section", re.compile(r"§\d"), "all"),
    ("zh-narration", re.compile(r"评审|上一?轮|旧版|老的|不再|以前|本版|遗留"), "zh"),
]


def iter_files(root: Path, excludes: set[str]) -> list[Path]:
    if root.is_file():
        return [root]
    collected: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in excludes for part in path.parts):
            continue
        collected.append(path)
    return collected


def scan(paths: list[Path], excludes: set[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in paths:
        is_zh = path.name.endswith((".zh.md", ".zh-CN.md"))
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary or undecodable files carry no prose to audit
        for probe_id, pattern, applies in PROBES:
            if applies == "zh" and not is_zh:
                continue
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    {
                        "path": str(path),
                        "line": line,
                        "probe": probe_id,
                        "excerpt": text[match.start() : min(match.end() + 30, len(text))].splitlines()[0],
                    }
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recall_batteries",
        description="Probe prose for chain-of-thought leakage; every hit needs semantic judgment.",
    )
    parser.add_argument("paths", nargs="+", help="files or directories to scan")
    parser.add_argument("--exclude", action="append", default=[], help="directory name to skip (repeatable; defaults: " + ", ".join(sorted(DEFAULT_EXCLUDES)) + ")")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args(argv)

    excludes = set(args.exclude) if args.exclude else DEFAULT_EXCLUDES
    files: list[Path] = []
    for raw in args.paths:
        root = Path(raw)
        if not root.exists():
            print(json.dumps({"schema": SCHEMA, "status": "usage-error", "error": f"path not found: {raw}"}, ensure_ascii=False))
            return 2
        files.extend(iter_files(root, excludes))
    findings = scan(files, excludes)
    report = {
        "schema": SCHEMA,
        "status": "fail" if findings else "pass",
        "scanned": len(files),
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2 if args.json else None))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

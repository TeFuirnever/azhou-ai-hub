#!/usr/bin/env python3
"""Derive the super-azhou-verify gate verdict from captured output plus exit code.

green (exit 0): exit code 0, last non-empty captured line is the gate's own
passing summary, no failure verdict line, and every identifiable Foundation
setup JSON result is intact and reports pass or dry_run.
red (exit 1): anything else; conflicting lines are printed.
Skip/unavailable lines are always listed so the receipt quotes them instead
of upgrading them to pass. Stdlib only; read-only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FAILURE_PATTERN = re.compile(r"(?i)\bfailed\b|failures?=\d+")
SKIP_PATTERN = re.compile(r"(?i)\bskipped\b|\bnot run\b|\bunavailable\b")


# Foundation emits schema_version as the first field of the setup result.
SETUP_RECEIPT_START = re.compile(
    r'(?m)^[ \t]*(\{)[ \t\r\n]*"schema_version"[ \t\r\n]*:[ \t\r\n]*'
    r'"azhou-ai-hub\.setup\.v1(?=["\r\n]|$)'
)


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value!r}")


def setup_conflicts(text: str) -> list[str]:
    conflicts = []
    decoder = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)
    for match in SETUP_RECEIPT_START.finditer(text):
        try:
            receipt, end = decoder.raw_decode(text, match.start(1))
        except (ValueError, RecursionError):
            conflicts.append("malformed or truncated Foundation setup receipt")
            continue
        line_end = text.find("\n", end)
        if text[end:line_end if line_end != -1 else len(text)].strip():
            conflicts.append("unexpected trailing content after Foundation setup receipt")
        if receipt.get("status") not in ("pass", "dry_run"):
            conflicts.append(f"non-passing Foundation setup receipt status: {receipt.get('status')!r}")
    return conflicts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--output-file")
    parser.add_argument("--success-marker", default="verification passed")
    args = parser.parse_args(argv)
    if args.output_file:
        text = open(args.output_file, encoding="utf-8", errors="replace").read()
    else:
        text = sys.stdin.read()
    lines = text.splitlines()
    non_empty = [line for line in lines if line.strip()]
    conflicts: list[str] = []
    if args.exit_code != 0:
        conflicts.append(f"exit code is {args.exit_code}, not 0")
    if not non_empty or non_empty[-1].strip() != args.success_marker:
        conflicts.append("last captured line is not the gate's passing summary")
    for line in lines:
        if FAILURE_PATTERN.search(line):
            conflicts.append(f"failure verdict line: {line.strip()}")
    conflicts.extend(setup_conflicts(text))
    skips = [line.strip() for line in lines if SKIP_PATTERN.search(line)]
    if conflicts:
        print("verdict: red")
        for item in conflicts:
            print(f"conflict: {item}")
        return 1
    print("verdict: green")
    for item in skips:
        print(f"skipped: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

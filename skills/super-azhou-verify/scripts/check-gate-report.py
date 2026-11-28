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
ARGPARSE_USAGE = re.compile(r"(?i)^usage:\s+\S")
ARGPARSE_ERROR = re.compile(r"(?i)^\S.*?: error:\s+\S")


# Foundation emits schema_version as the first field of the setup result.
SETUP_RECEIPT_START = re.compile(
    r'(?m)^[ \t]*(\{)[ \t\r\n]*"schema(?:_|\\u005[fF])version"[ \t\r\n]*:[ \t\r\n]*'
    r'"azhou-ai-hub\.setup\.v1(?=["\r\n]|$)'
)
SCHEMA_FIRST_PREFIX = re.compile(
    r'(?m)^[ \t]*(\{)[ \t\r\n]*"schema(?:_|\\u005[fF])?(?:version)?(?:"|\\|$)'
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


def setup_conflicts(text: str, *, depth: int = 0) -> list[str]:
    conflicts = []
    decoder = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)
    starts = {match.start(1) for match in SETUP_RECEIPT_START.finditer(text)}
    starts.update(match.start(1) for match in SCHEMA_FIRST_PREFIX.finditer(text))
    for start in sorted(starts):
        try:
            receipt, end = decoder.raw_decode(text, start)
        except (ValueError, RecursionError):
            conflicts.append("malformed or truncated Foundation setup receipt")
            continue
        if not isinstance(receipt, dict) or receipt.get("schema_version") != "azhou-ai-hub.setup.v1":
            continue
        line_end = text.find("\n", end)
        if text[end:line_end if line_end != -1 else len(text)].strip():
            conflicts.append("unexpected trailing content after Foundation setup receipt")
        if receipt.get("status") not in ("pass", "dry_run"):
            conflicts.append(f"non-passing Foundation setup receipt status: {receipt.get('status')!r}")

    # Some hosts place captured command output inside a JSON string or object.
    # Inspect only decoded string values that look like nested JSON, keeping
    # ordinary prose and expected negative-test messages out of the scan.
    if depth < 3:
        wrapper_decoder = json.JSONDecoder()

        def visit(value: object) -> None:
            if isinstance(value, str):
                nested = value.lstrip()
                if nested.startswith(("{", "[", '"')) and "schema" in nested:
                    conflicts.extend(setup_conflicts(value, depth=depth + 1))
            elif isinstance(value, dict):
                for nested_value in value.values():
                    visit(nested_value)
            elif isinstance(value, list):
                for nested_value in value:
                    visit(nested_value)

        for match in re.finditer(r"(?m)^[ \t]*[\{\[\"]", text):
            start = match.start() + len(match.group(0)) - 1
            try:
                value, _ = wrapper_decoder.raw_decode(text, start)
            except (ValueError, RecursionError):
                continue
            visit(value)
    return list(dict.fromkeys(conflicts))


def argparse_conflicts(lines: list[str]) -> list[str]:
    conflicts = []
    inside_gate_output = False
    for index, line in enumerate(lines):
        if line.startswith("==> "):
            inside_gate_output = True
            continue
        if not ARGPARSE_ERROR.match(line):
            continue
        # Sub-gates can intentionally exercise argparse rejection inside
        # passing tests. Their process status and the aggregate verdict are
        # authoritative for those marked sections; an outer CLI parse error
        # occurs before the verifier emits its first gate marker.
        if inside_gate_output:
            continue
        previous = index - 1
        while previous >= 0 and lines[previous][:1].isspace() and lines[previous].strip():
            previous -= 1
        if previous >= 0 and ARGPARSE_USAGE.match(lines[previous]):
            conflicts.append(f"argument parser error line: {line.strip()}")
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
    conflicts.extend(argparse_conflicts(lines))
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

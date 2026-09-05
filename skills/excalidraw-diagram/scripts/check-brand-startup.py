#!/usr/bin/env python3
"""Validate real excalidraw-diagram startup broadcast lines against the brand
value discipline: exact fixed prefix, field order, concrete values, and the
machine-stable literal `unresolved` as the only legal pending value (allowed
only before the requirement lock). Stdlib only; read-only."""

from __future__ import annotations

import argparse
import re
import sys

PREFIX = "🦊 阿舟 · Excalidraw Diagram 启动｜"
FIELDS = ("mode=", "deliverable=", "scope=")


def check(line: str, locked: bool) -> list[str]:
    errors: list[str] = []
    if not line.startswith(PREFIX):
        errors.append("fixed prefix mismatch")
        return errors
    body = line[len(PREFIX):]
    parts = body.split("｜")
    if [p.split("=", 1)[0] + "=" for p in parts if "=" in p] != list(FIELDS) or len(parts) != 3:
        errors.append(f"field order/count mismatch: expected mode|deliverable|scope, got {len(parts)} fields")
        return errors
    for part in parts:
        key, _, value = part.partition("=")
        if not value.strip():
            errors.append(f"empty value for {key}")
        if "<" in value or ">" in value:
            errors.append(f"template placeholder in {key}: {value}")
        if value.strip() == "unresolved" and key == "scope" and locked:
            errors.append("scope=unresolved after requirement lock")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locked", action="store_true", help="requirement lock has happened; unresolved is no longer allowed")
    parser.add_argument("lines", nargs="*", help="broadcast lines; stdin when omitted")
    args = parser.parse_args(argv)
    text = "\n".join(args.lines) if args.lines else sys.stdin.read()
    bad = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        errors = check(line, args.locked)
        if errors:
            bad += 1
            print(f"invalid: {line}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"ok: {line}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

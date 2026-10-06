#!/usr/bin/env python3
"""Record an unrouted ask-azhou routing miss.

When no canonical skill fits a request, the router records the miss instead
of waiting for the same natural-language failure to repeat before anyone
counts it. The privacy contract is count-plus-hash only: the store keeps a
SHA-256 of the request text with a counter and day stamps, and never the
text itself, so nothing conversational can leak into receipts, reports, or
Git. The store lives under ``<root>/.azhou/ask-azhou/`` — the Azhou
runtime-state namespace convention, git-ignored repository-wide.

Usage from the working checkout:

    python skills/ask-azhou/scripts/record_unrouted.py --prompt "<the request as asked>"
    python skills/ask-azhou/scripts/record_unrouted.py --stdin        # read the request from stdin
    python skills/ask-azhou/scripts/record_unrouted.py --summary      # aggregate only

Dependency-free; standard library only. Fails closed on any store it
cannot fully validate, leaving the previous store untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


SCHEMA = "ask-azhou.unrouted-telemetry.v1"
NAMESPACE_PARTS = (".azhou", "ask-azhou")
STORE_NAME = "unrouted-telemetry.json"
EVENT_KEYS = {"count", "first_seen", "last_seen"}


class TelemetryError(RuntimeError):
    """Raised when a request or store cannot be proven safe to process."""


def store_path(root: Path) -> Path:
    """Resolve the contained store path below one authorized root."""
    if root.is_symlink():
        raise TelemetryError(f"authorized root cannot be a symlink: {root}")
    if not root.is_dir():
        raise TelemetryError(f"authorized root is not a directory: {root}")
    resolved = root.resolve(strict=False)
    cursor = resolved
    for part in NAMESPACE_PARTS:
        cursor /= part
        if cursor.is_symlink():
            raise TelemetryError(f"telemetry path contains a symlink: {cursor}")
        if cursor.exists() and not cursor.is_dir():
            raise TelemetryError(f"telemetry path ancestor is not a directory: {cursor}")
    return cursor / STORE_NAME


def load_store(path: Path) -> dict:
    """Load the store, failing closed on any unsupported shape."""
    if not path.is_file():
        return {"schema": SCHEMA, "events": {}}
    if path.is_symlink():
        raise TelemetryError(f"telemetry store cannot be a symlink: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TelemetryError(f"telemetry store is unreadable; remove it explicitly to reset: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema", "events"}:
        raise TelemetryError(f"telemetry store schema is unsupported: {path}")
    if payload["schema"] != SCHEMA:
        raise TelemetryError(f"telemetry store schema mismatch in {path}: {payload['schema']!r}")
    events = payload["events"]
    if not isinstance(events, dict):
        raise TelemetryError(f"telemetry store events must be an object: {path}")
    for digest, event in events.items():
        if not isinstance(digest, str) or len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
            raise TelemetryError(f"telemetry store event key is not a sha256 digest: {path}")
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            raise TelemetryError(f"telemetry store event shape is unsupported: {path}")
        if not isinstance(event["count"], int) or isinstance(event["count"], bool) or event["count"] < 1:
            raise TelemetryError(f"telemetry store event count is invalid: {path}")
        for key in ("first_seen", "last_seen"):
            if not isinstance(event[key], str) or len(event[key]) != 10:
                raise TelemetryError(f"telemetry store event {key} is not a day stamp: {path}")
    return payload


def write_store(path: Path, payload: dict) -> None:
    """Publish the store atomically with user-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def digest_of(request: str) -> str:
    return hashlib.sha256(request.strip().encode("utf-8")).hexdigest()


def record(root: Path, request: str) -> tuple[Path, str, int]:
    if not request.strip():
        raise TelemetryError("refusing to record an empty request")
    path = store_path(root)
    payload = load_store(path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = digest_of(request)
    event = payload["events"].get(digest)
    if event is None:
        payload["events"][digest] = {"count": 1, "first_seen": today, "last_seen": today}
    else:
        event["count"] += 1
        event["last_seen"] = today
    write_store(path, payload)
    return path, digest, payload["events"][digest]["count"]


def summarize(root: Path) -> tuple[Path, dict]:
    path = store_path(root)
    return path, load_store(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="working checkout that owns the .azhou/ runtime state (default: current directory)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prompt", help="the unrouted request text; only its hash is stored")
    group.add_argument("--stdin", action="store_true", help="read the request text from stdin")
    parser.add_argument("--summary", action="store_true", help="print the aggregate instead of recording")
    args = parser.parse_args(argv)

    try:
        root = args.root.expanduser()
        if args.summary:
            path, payload = summarize(root)
            events = sorted(payload["events"].items(), key=lambda item: (-item[1]["count"], item[0]))
            total = sum(event["count"] for _, event in events)
            print(f"unrouted requests: {len(events)} distinct, {total} total, store={path}")
            for digest, event in events:
                print(
                    f"sha256={digest[:12]} count={event['count']} "
                    f"first={event['first_seen']} last={event['last_seen']}"
                )
            return 0
        if args.stdin:
            request = sys.stdin.read()
        elif args.prompt is not None:
            request = args.prompt
        else:
            parser.error("one of --prompt or --stdin is required to record")
            return 2
        path, digest, count = record(root, request)
        print(
            f"recorded unrouted request: sha256={digest[:12]} count={count} store={path} "
            "(only counts and hashes are stored)"
        )
        return 0
    except TelemetryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

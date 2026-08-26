#!/usr/bin/env python3
"""Codex-first, opt-in SessionStart adapter for Super Caveman.

``setup`` and ``uninstall`` change only one explicit Codex ``hooks.json``
scope. ``render`` consumes one Codex SessionStart event from stdin and emits
only Codex's documented JSON hook-output shape.  The adapter never reads
transcripts, contacts the network, or acts as a security gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = "super-caveman.codex-session-start.v1"
SUPPORTED_SOURCES = {"startup", "resume", "clear", "compact"}
OWN_MATCHER = "startup|resume|clear|compact"
HOOK_TIMEOUT_SECONDS = 5
MAX_CONTEXT_CHARS = 4_000


class AdapterError(RuntimeError):
    pass


def _absolute_path(path: str | Path) -> Path:
    """Normalize path segments without resolving symbolic links."""
    return Path(os.path.abspath(Path(path).expanduser()))


def _package_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _rules_digest() -> str:
    digest = hashlib.sha256()
    for name in ("SKILL.md", "references/modes.md"):
        path = _package_dir() / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"missing\0")
    return digest.hexdigest()


def _reject_symlink_components(path: Path, scope_root: Path) -> None:
    root = _absolute_path(scope_root)
    absolute = _absolute_path(path)
    if root.is_symlink():
        raise AdapterError(f"refusing symlink scope root: {root}")
    try:
        components = absolute.relative_to(root).parts
    except ValueError as exc:
        raise AdapterError(f"path escapes selected scope: {absolute}") from exc
    current = root
    for component in components:
        current /= component
        try:
            if current.is_symlink():
                raise AdapterError(f"refusing symlink path component: {current}")
        except OSError as exc:
            raise AdapterError(f"cannot inspect hooks path: {current}") from exc


def _hooks_path(args: argparse.Namespace) -> Path:
    root = _absolute_path(
        args.project_dir or os.getcwd() if args.scope == "project" else args.home_dir or Path.home()
    )
    standard = root / ".codex" / "hooks.json"
    path = _absolute_path(args.hooks_path) if args.hooks_path else standard
    if path != standard:
        raise AdapterError(f"hooks path must be the standard {args.scope} scope: {standard}")
    _reject_symlink_components(path.parent, root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe hooks file: {path}")
    return path


def _hook_command() -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} render"


def _is_ours(handler: Any) -> bool:
    return isinstance(handler, dict) and handler.get("type") == "command" and handler.get("command") == _hook_command()


def _is_replaced_legacy_handler(handler: Any) -> bool:
    """Recognize only the two prior global SessionStart commands we replace."""
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    normalized = command.lstrip()
    return normalized.startswith("echo 'CAVEMAN MODE ACTIVE. Rules:") or (
        normalized.startswith("sh ")
        and "/i-have-adhd/" in normalized
        and normalized.endswith("always-on.sh\"")
    )


def _load_hooks(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"cannot read valid JSON hooks: {path}") from exc
    if not isinstance(payload, dict):
        raise AdapterError("Codex hooks root must be a JSON object")
    return payload


def _owned_registration() -> dict[str, Any]:
    return {
        "matcher": OWN_MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(),
                "timeout": HOOK_TIMEOUT_SECONDS,
                "additionalContextLimit": 1024,
                "statusMessage": "Loading Super Caveman",
            }
        ],
    }


def _replace_owned(registrations: list[Any], replacement: dict[str, Any] | None) -> list[Any]:
    result: list[Any] = []
    for registration in registrations:
        if not isinstance(registration, dict) or registration.get("matcher") != OWN_MATCHER:
            result.append(registration)
            continue
        handlers = registration.get("hooks")
        if not isinstance(handlers, list):
            result.append(registration)
            continue
        kept = [handler for handler in handlers if not _is_ours(handler)]
        if kept:
            updated = dict(registration)
            updated["hooks"] = kept
            result.append(updated)
    if replacement is not None:
        result.append(replacement)
    return result


def _install(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AdapterError("Codex hooks field must be an object")
    starts = hooks.setdefault("SessionStart", [])
    if not isinstance(starts, list):
        raise AdapterError("Codex SessionStart hooks must be an array")
    hooks["SessionStart"] = _replace_owned(starts, _owned_registration())
    return payload


def _uninstall(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return payload
    starts = hooks.get("SessionStart")
    if isinstance(starts, list):
        cleaned = _replace_owned(starts, None)
        if cleaned:
            hooks["SessionStart"] = cleaned
        else:
            hooks.pop("SessionStart", None)
    if not hooks:
        payload.pop("hooks", None)
    return payload


def _reconcile_legacy(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove exact legacy global injections; never touch unrelated handlers."""
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return payload, 0
    starts = hooks.get("SessionStart")
    if not isinstance(starts, list):
        return payload, 0
    cleaned: list[Any] = []
    removed = 0
    for registration in starts:
        if not isinstance(registration, dict):
            cleaned.append(registration)
            continue
        handlers = registration.get("hooks")
        if not isinstance(handlers, list):
            cleaned.append(registration)
            continue
        kept = [handler for handler in handlers if not _is_replaced_legacy_handler(handler)]
        removed += len(handlers) - len(kept)
        if kept:
            updated = dict(registration)
            updated["hooks"] = kept
            cleaned.append(updated)
    if cleaned:
        hooks["SessionStart"] = cleaned
    else:
        hooks.pop("SessionStart", None)
    if not hooks:
        payload.pop("hooks", None)
    return payload, removed


def _atomic_write(path: Path, payload: dict[str, Any], scope_root: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _reject_symlink_components(path.parent, scope_root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe hooks file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".super-caveman-", suffix=".tmp", dir=str(path.parent))
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise AdapterError(f"atomic hooks write failed: {path}") from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _capsule(source: str) -> str:
    package = _package_dir()
    context = "\n".join(
        (
            "Super Caveman is active. active_mode=full.",
            "Apply: safety and explicit format first; action-first ADHD-friendly structure second; Caveman compression last.",
            "Lead with the result or next action. Number multi-step work. Keep current step visible. End with one concrete next action when work remains.",
            "Preserve exact code, commands, paths, numbers, dates, and requested detail. Do not compress safety, order, causality, or required artifacts.",
            "On 'stop super-caveman', 'stop caveman', 'stop adhd mode', or 'normal mode', confirm once and return to normal style.",
            f"Canonical rules: {package / 'SKILL.md'} and {package / 'references' / 'modes.md'}.",
            f"schema_version={SCHEMA_VERSION}",
            f"rules_digest={_rules_digest()}",
            f"event={source}",
        )
    )
    return context[:MAX_CONTEXT_CHARS]


def _render() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        source = event.get("source", "startup")
        if source not in SUPPORTED_SOURCES:
            source = "startup"
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": _capsule(source),
                    }
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    except Exception as exc:
        print("{}")
        print(f"super-caveman Codex adapter: {exc}", file=sys.stderr)
    return 0


def _scope_root(args: argparse.Namespace) -> Path:
    return _absolute_path(args.project_dir or os.getcwd() if args.scope == "project" else args.home_dir or Path.home())


def _scope_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", required=True, choices=("project", "user"))
    parser.add_argument("--hooks-path")
    parser.add_argument("--project-dir")
    parser.add_argument("--home-dir")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "uninstall", "reconcile-legacy"):
        _scope_parser(commands.add_parser(name))
    commands.add_parser("render")
    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            return _render()
        root = _scope_root(args)
        path = _hooks_path(args)
        payload = _load_hooks(path)
        removed = None
        if args.command == "setup":
            updated = _install(payload)
        elif args.command == "uninstall":
            updated = _uninstall(payload)
        else:
            updated, removed = _reconcile_legacy(payload)
        _atomic_write(path, updated, root)
        result: dict[str, Any] = {"ok": True, "command": args.command, "scope": args.scope, "hooks": str(path)}
        if removed is not None:
            result["removed_legacy_session_start_handlers"] = removed
        print(json.dumps(result))
        return 0
    except AdapterError as exc:
        print(f"super-caveman Codex adapter: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

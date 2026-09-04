#!/usr/bin/env python3
"""Codex-first, opt-in lifecycle adapter for Super Caveman.

``setup`` and ``uninstall`` change only one explicit Codex ``hooks.json``
scope, owning one SessionStart registration and one UserPromptSubmit
registration. ``render`` and ``prompt`` delegate to the canonical Claude
adapter handlers from the same package, so the capsule builder, mode
hierarchy and session state machine stay single-source; the emitted shape is
Codex's documented JSON hook output. The adapter never reads transcripts,
contacts the network, or acts as a security gate; handler output fails open.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_adapter  # noqa: E402  (same-package canonical handler module)

SCHEMA_VERSION = "super-caveman.codex-session-start.v1"
OWN_MATCHER = "startup|resume|clear|compact"
PROMPT_MATCHER = ".*"  # official docs: matcher is ignored for UserPromptSubmit
HOOK_TIMEOUT_SECONDS = 5

# One error contract with the canonical handler module this adapter reuses.
AdapterError = claude_adapter.AdapterError


def _absolute_path(path: str | Path) -> Path:
    """Normalize path segments without resolving symbolic links."""
    return Path(os.path.abspath(Path(path).expanduser()))


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


def _hook_command(sub: str) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} {sub}"


def _is_adapter_command(command: Any, sub: str = "render") -> bool:
    """Recognize the adapter by its lexical command shape, not its checkout."""
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) != 3 or not tokens[0] or tokens[2] != sub:
        return False
    return Path(tokens[1]).parts[-3:] == ("super-caveman", "scripts", "codex_adapter.py")


def _is_ours(registration: Any, handler: Any, matcher: str, sub: str) -> bool:
    """Require every stable registration and handler field to match."""
    if not isinstance(registration, dict) or registration.get("matcher") != matcher:
        return False
    return (
        isinstance(handler, dict)
        and handler.get("type") == "command"
        and handler.get("timeout") == HOOK_TIMEOUT_SECONDS
        and handler.get("additionalContextLimit") == 1024
        and handler.get("statusMessage") == "Loading Super Caveman"
        and _is_adapter_command(handler.get("command"), sub)
    )


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


def _owned_registration(matcher: str, sub: str) -> dict[str, Any]:
    return {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(sub),
                "timeout": HOOK_TIMEOUT_SECONDS,
                "additionalContextLimit": 1024,
                "statusMessage": "Loading Super Caveman",
            }
        ],
    }


def _replace_owned(
    entries: list[Any],
    matcher: str,
    sub: str,
    replacement: dict[str, Any] | None,
) -> list[Any]:
    result: list[Any] = []
    replacement_added = False
    for registration in entries:
        if not isinstance(registration, dict) or registration.get("matcher") != matcher:
            result.append(registration)
            continue
        handlers = registration.get("hooks")
        if not isinstance(handlers, list):
            result.append(registration)
            continue
        owned = [_is_ours(registration, handler, matcher, sub) for handler in handlers]
        if not any(owned):
            result.append(registration)
            continue
        if replacement is not None and any(owned) and not replacement_added:
            result.append(replacement)
            replacement_added = True
        kept = [handler for handler, is_owned in zip(handlers, owned) if not is_owned]
        if kept:
            updated = dict(registration)
            updated["hooks"] = kept
            result.append(updated)
    if replacement is not None:
        if not replacement_added:
            result.append(replacement)
    return result


def _install(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AdapterError("Codex hooks field must be an object")
    hooks["SessionStart"] = _replace_owned(
        _event_list(hooks, "SessionStart"), OWN_MATCHER, "render", _owned_registration(OWN_MATCHER, "render")
    )
    hooks["UserPromptSubmit"] = _replace_owned(
        _event_list(hooks, "UserPromptSubmit"), PROMPT_MATCHER, "prompt", _owned_registration(PROMPT_MATCHER, "prompt")
    )
    return payload


def _event_list(hooks: dict[str, Any], event: str) -> list[Any]:
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        raise AdapterError(f"Codex {event} hooks must be an array")
    return entries


def _uninstall(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return payload
    for event, matcher, sub in (
        ("SessionStart", OWN_MATCHER, "render"),
        ("UserPromptSubmit", PROMPT_MATCHER, "prompt"),
    ):
        entries = hooks.get(event)
        if isinstance(entries, list):
            cleaned = _replace_owned(entries, matcher, sub, None)
            if cleaned:
                hooks[event] = cleaned
            else:
                hooks.pop(event, None)
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
    enable = commands.add_parser("enable")
    enable.add_argument("--scope", required=True, choices=("project", "user"))
    enable.add_argument("--mode", required=True, choices=claude_adapter.MODES)
    enable.add_argument("--project-dir")
    enable.add_argument("--home-dir")
    disable = commands.add_parser("disable")
    disable.add_argument("--scope", required=True, choices=("project", "user"))
    disable.add_argument("--project-dir")
    disable.add_argument("--home-dir")
    for name in ("status", "render", "prompt"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--project-dir")
        cmd.add_argument("--home-dir")
    args = parser.parse_args(argv)
    home = getattr(args, "home_dir", None)
    project = getattr(args, "project_dir", None)
    try:
        if args.command == "render":
            return claude_adapter.run_render(home, project)
        if args.command == "prompt":
            return claude_adapter.run_prompt(home, project)
        if args.command == "enable":
            return claude_adapter.write_layer_cli(args)
        if args.command == "disable":
            return claude_adapter.write_layer_cli(args)
        if args.command == "status":
            print(json.dumps(claude_adapter.status_report(home, project), ensure_ascii=False, indent=2))
            return 0
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

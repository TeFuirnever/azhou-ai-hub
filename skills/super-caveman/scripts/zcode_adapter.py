#!/usr/bin/env python3
"""Opt-in zcode lifecycle adapter for Super Caveman.

``setup``/``uninstall`` manage one explicit zcode ``.zcode/cli/config.json``
scope: the two proven hook events (``SessionStart`` and ``UserPromptSubmit``)
under ``hooks.events``, plus ``hooks.enabled`` on setup. ``render``/``prompt``
reuse the canonical Claude adapter handlers from the same package so the
capsule builder, mode hierarchy and session state machine stay single-source.
``enable``/``disable``/``status`` reuse the canonical persistent-defaults
layer. The adapter never reads transcripts, contacts the network, or acts as
a security gate; handler output fails open.
"""

from __future__ import annotations

import argparse
import io
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

SCHEMA_VERSION = "super-caveman.zcode-adapter.v1"
MATCHER = ".*"

# One error contract with the canonical handler module this adapter reuses.
AdapterError = claude_adapter.AdapterError


def _normalize_event_stdin() -> None:
    """Bridge possible camelCase-only payloads to the canonical snake_case handlers.

    zcode 0.16.5 executes no hooks in headless ``-p`` mode (probe-verified
    2026-09-04), so the GUI-host payload casing could not be observed live;
    the canonical handlers read ``session_id`` while zcode documents camelCase
    envelopes, so bridge defensively and accept either casing.
    """
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.stdin = io.StringIO("{}")
        return
    if isinstance(event, dict):
        for camel, snake in (("sessionId", "session_id"),):
            if snake not in event and camel in event:
                event[snake] = event[camel]
    sys.stdin = io.StringIO(json.dumps(event, ensure_ascii=False))


def _absolute_path(path: str | Path) -> Path:
    """Normalize path segments without resolving symbolic links."""
    return Path(os.path.abspath(Path(path).expanduser()))


def _scope_root(args: argparse.Namespace) -> Path:
    if args.scope == "project":
        root = _absolute_path(args.project_dir or os.getcwd())
        if not root.is_dir():
            raise AdapterError("project scope requires a valid project directory")
        return root
    return _absolute_path(args.home_dir) if args.home_dir else Path.home()


def _config_path(args: argparse.Namespace) -> tuple[Path, Path]:
    root = _scope_root(args)
    standard = root / ".zcode" / "cli" / "config.json"
    path = _absolute_path(args.config_path) if args.config_path else standard
    if path != standard:
        raise AdapterError(f"config path must be the standard {args.scope} scope: {standard}")
    claude_adapter.reject_links(path.parent.parent, root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe config file: {path}")
    return path, root


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"cannot read valid JSON config: {path}") from exc
    if not isinstance(payload, dict):
        raise AdapterError("zcode config root must be a JSON object")
    return payload


def _atomic_write(path: Path, payload: dict[str, Any], scope_root: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    claude_adapter.reject_links(path.parent, scope_root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe config file: {path}")
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
        raise AdapterError(f"atomic config write failed: {path}") from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _hook_command(sub: str) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} {sub}"


def _owned_command(command: Any, sub: str) -> bool:
    """Recognize the adapter by its lexical command shape, not its checkout."""
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) != 3 or not tokens[0] or tokens[2] != sub:
        return False
    return Path(tokens[1]).parts[-3:] == ("super-caveman", "scripts", "zcode_adapter.py")


def _owned_handler(handler: Any, sub: str) -> bool:
    return (
        isinstance(handler, dict)
        and handler.get("type") == "command"
        and handler.get("async") is False
        and _owned_command(handler.get("command"), sub)
    )


def _owned_registration(entry: Any, sub: str) -> bool:
    if not isinstance(entry, dict) or entry.get("matcher") != MATCHER:
        return False
    handlers = entry.get("hooks")
    if not isinstance(handlers, list) or not handlers:
        return False
    return any(_owned_handler(item, sub) for item in handlers)


def _new_registration(sub: str) -> dict[str, Any]:
    return {
        "matcher": MATCHER,
        "hooks": [
            {
                "type": "command",
                "async": False,
                "command": _hook_command(sub),
            }
        ],
    }


def _replace_owned(entries: list[Any], sub: str, replacement: dict[str, Any] | None) -> list[Any]:
    result: list[Any] = []
    added = False
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("matcher") != MATCHER:
            result.append(entry)
            continue
        handlers = entry.get("hooks")
        if not isinstance(handlers, list):
            result.append(entry)
            continue
        owned = [_owned_handler(item, sub) for item in handlers]
        if not any(owned):
            result.append(entry)
            continue
        if replacement is not None and not added:
            result.append(replacement)
            added = True
        kept = [handler for handler, is_owned in zip(handlers, owned) if not is_owned]
        if kept:
            updated = dict(entry)
            updated["hooks"] = kept
            result.append(updated)
    if replacement is not None and not added:
        result.append(replacement)
    return result


def _apply_event(payload: dict[str, Any], event: str, sub: str, install: bool) -> None:
    """Install or remove this adapter's registrations for one hook event."""
    if install:
        hooks = payload.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise AdapterError("zcode config hooks field must be an object")
        hooks["enabled"] = True
        events = hooks.setdefault("events", {})
        if not isinstance(events, dict):
            raise AdapterError("zcode config hooks.events must be an object")
    else:
        hooks = payload.get("hooks")
        if not isinstance(hooks, dict):
            return
        events = hooks.get("events")
        if not isinstance(events, dict):
            return
    entries = events.get(event)
    if not isinstance(entries, list):
        entries = [] if install else None
    if entries is None:
        return
    updated = _replace_owned(entries, sub, _new_registration(sub) if install else None)
    if updated:
        events[event] = updated
    else:
        events.pop(event, None)
    if not events:
        hooks.pop("events", None)
        if not hooks:
            payload.pop("hooks", None)


def _setup_cli(args: argparse.Namespace) -> int:
    path, root = _config_path(args)
    payload = _load_config(path)
    _apply_event(payload, "SessionStart", "render", install=True)
    _apply_event(payload, "UserPromptSubmit", "prompt", install=True)
    _atomic_write(path, payload, root)
    print(json.dumps({"ok": True, "command": "setup", "scope": args.scope, "config": str(path)}))
    return 0


def _uninstall_cli(args: argparse.Namespace) -> int:
    path, root = _config_path(args)
    payload = _load_config(path)
    _apply_event(payload, "SessionStart", "render", install=False)
    _apply_event(payload, "UserPromptSubmit", "prompt", install=False)
    if path.exists() or payload:
        _atomic_write(path, payload, root)
    if args.purge_state:
        state = claude_adapter.state_dir_for(args.project_dir, None)
        if state is not None and state.exists():
            claude_adapter.drop_state_tree(state, claude_adapter.project_root(args.project_dir, None) or Path.home())
        if args.scope == "user":
            home = claude_adapter.user_root(args.home_dir)
            cfg = home / ".config" / "super-caveman"
            if cfg.exists():
                claude_adapter.drop_state_tree(cfg, home)
    print(json.dumps({"ok": True, "command": "uninstall", "scope": args.scope, "config": str(path)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "uninstall"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--scope", required=True, choices=("project", "user"))
        cmd.add_argument("--config-path")
        cmd.add_argument("--purge-state", action="store_true")
        cmd.add_argument("--project-dir")
        cmd.add_argument("--home-dir")
    enable = sub.add_parser("enable")
    enable.add_argument("--scope", required=True, choices=("project", "user"))
    enable.add_argument("--mode", required=True, choices=claude_adapter.MODES)
    enable.add_argument("--project-dir")
    enable.add_argument("--home-dir")
    disable = sub.add_parser("disable")
    disable.add_argument("--scope", required=True, choices=("project", "user"))
    disable.add_argument("--project-dir")
    disable.add_argument("--home-dir")
    for name in ("status", "render", "prompt"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project-dir")
        cmd.add_argument("--home-dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    home = getattr(args, "home_dir", None)
    project = getattr(args, "project_dir", None)
    try:
        if args.command == "setup":
            return _setup_cli(args)
        if args.command == "uninstall":
            return _uninstall_cli(args)
        if args.command == "enable":
            return claude_adapter.write_layer_cli(args)
        if args.command == "disable":
            return claude_adapter.write_layer_cli(args)
        if args.command == "status":
            print(json.dumps(claude_adapter.status_report(home, project), ensure_ascii=False, indent=2))
            return 0
        if args.command == "render":
            _normalize_event_stdin()
            return claude_adapter.run_render(home, project)
        if args.command == "prompt":
            _normalize_event_stdin()
            return claude_adapter.run_prompt(home, project)
    except AdapterError as exc:
        print(f"super-caveman zcode adapter: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

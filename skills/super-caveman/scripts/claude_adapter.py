#!/usr/bin/env python3
"""Opt-in Claude Code lifecycle adapter for Super Caveman.

``setup``/``uninstall`` manage one explicit Claude settings scope.
``enable``/``disable`` mutate one explicit persistent defaults layer.
``render`` consumes a Claude SessionStart event; ``prompt`` consumes a
UserPromptSubmit event and resolves the state hierarchy into at most one
bounded reinforcement.  The adapter never reads transcripts, contacts the
network, or acts as a security gate; response-style output fails open.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = "super-caveman.claude-adapter.v1"
CAPSULE_SCHEMA = "super-caveman.claude-capsule.v1"
STATE_SCHEMA = "super-caveman.adapter-state.v1"
SOURCES = ("startup", "resume", "clear", "compact")
START_MATCHER = "startup|resume|clear|compact"
TIMEOUT = 5
CAPSULE_LIMIT = 10_000
PROMPT_LIMIT = 1_024
SESSION_LIMIT_BYTES = 4_096
STATE_LIMIT_BYTES = 1_024
MODES = ("lite", "full", "ultra", "wenyan-lite", "wenyan-full", "wenyan-ultra")
OFF = "off"
ROUTES = ("commit", "review", "compress")
SID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
STOPS = ("stop super-caveman", "stop caveman", "stop adhd mode", "normal mode")
CMDS = ("/super-caveman", "/caveman")


class AdapterError(RuntimeError):
    pass


def abspath_raw(path: str | Path) -> Path:
    """Normalize without resolving symbolic links."""
    return Path(os.path.abspath(Path(path).expanduser()))


def pkg_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def rules_digest() -> str:
    digest = hashlib.sha256()
    for name in ("SKILL.md", "references/modes.md"):
        blob = pkg_dir() / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(blob.read_bytes())
        except OSError:
            digest.update(b"missing\0")
    return digest.hexdigest()


def reject_links(path: Path, root: Path) -> None:
    """Refuse symlinked components or paths escaping the scope root."""
    base = abspath_raw(root)
    if base.is_symlink():
        raise AdapterError(f"refusing symlink scope root: {base}")
    full = abspath_raw(path)
    try:
        parts = full.relative_to(base).parts
    except ValueError as exc:
        raise AdapterError(f"path escapes selected scope: {full}") from exc
    cursor = base
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise AdapterError(f"refusing symlink path component: {cursor}")


def atomic_write(path: Path, payload: dict[str, Any], root: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    reject_links(path.parent, root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe state file: {path}")
    keep_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".super-caveman-", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        os.fchmod(fd, keep_mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        raise AdapterError(f"atomic state write failed: {path}") from exc
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def drop_state_tree(path: Path, root: Path) -> int:
    """Remove a contained state tree entry by entry, refusing links."""
    target = abspath_raw(path)
    if not target.exists():
        return 0
    reject_links(target, root)
    if target.is_symlink() or not target.is_dir():
        raise AdapterError(f"refusing unsafe state tree: {target}")
    removed = 0
    for entry in sorted(target.rglob("*"), reverse=True):
        if entry.is_symlink() or entry.is_file():
            entry.unlink()
            removed += 1
        elif entry.is_dir():
            entry.rmdir()
            removed += 1
        else:
            raise AdapterError(f"refusing unsafe state entry: {entry}")
    target.rmdir()
    return removed


def load_json(path: Path | None, limit: int) -> tuple[dict[str, Any] | None, str | None]:
    """Read one bounded JSON state file; (None, reason) when unusable."""
    if path is None:
        return None, "unavailable"
    try:
        if path.is_symlink() or not path.is_file():
            return None, "missing"
        if path.stat().st_size > limit:
            return None, "oversized"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "unreadable"
    if not isinstance(payload, dict):
        return None, "invalid"
    return payload, None


def user_root(home_dir: str | None) -> Path:
    return abspath_raw(home_dir) if home_dir else Path.home()


def project_root(project_dir: str | None, cwd: str | None) -> Path | None:
    raw = project_dir or cwd
    if not raw:
        return None
    root = abspath_raw(raw)
    return root if root.is_dir() else None


def state_dir_for(project_dir: str | None, cwd: str | None) -> Path | None:
    root = project_root(project_dir, cwd)
    return None if root is None else root / ".azhou" / "super-caveman"


def defaults_path(home_dir: str | None, project_dir: str | None, cwd: str | None, layer: str) -> Path | None:
    if layer == "user":
        return user_root(home_dir) / ".config" / "super-caveman" / "defaults.json"
    state = state_dir_for(project_dir, cwd)
    return None if state is None else state / "defaults.json"


def session_path(project_dir: str | None, cwd: str | None, sid: str) -> Path | None:
    state = state_dir_for(project_dir, cwd)
    if state is None or not SID_RE.fullmatch(sid or ""):
        return None
    return state / "sessions" / f"{sid}.json"


def ok_defaults(payload: dict[str, Any] | None, layer: str) -> bool:
    return bool(
        isinstance(payload, dict)
        and payload.get("schema_version") == STATE_SCHEMA
        and payload.get("layer") == layer
        and payload.get("mode") in MODES + (OFF,)
    )


def ok_session(payload: dict[str, Any] | None, sid: str) -> bool:
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_SCHEMA:
        return False
    if not SID_RE.fullmatch(str(payload.get("session_id", ""))):
        return False
    return (
        payload.get("override_mode") in (None,) + MODES
        and payload.get("stopped") in (True, False)
        and payload.get("one_shot") in (None,) + ROUTES
        and payload.get("previous_mode") in (None,) + MODES
    )


def read_layer(layer: str, home_dir: str | None, project_dir: str | None, cwd: str | None) -> tuple[dict[str, Any] | None, str | None]:
    path = defaults_path(home_dir, project_dir, cwd, layer)
    payload, reason = load_json(path, STATE_LIMIT_BYTES)
    if payload is None or not ok_defaults(payload, layer):
        return None, reason or "invalid"
    return payload, None


def read_session(project_dir: str | None, cwd: str | None, sid: str) -> tuple[dict[str, Any] | None, str | None]:
    path = session_path(project_dir, cwd, sid)
    payload, reason = load_json(path, SESSION_LIMIT_BYTES)
    if payload is None:
        return None, reason
    if not ok_session(payload, sid):
        return None, "invalid"
    return payload, None


def fresh_session(sid: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "session_id": sid,
        "override_mode": None,
        "stopped": False,
        "one_shot": None,
        "previous_mode": None,
    }


def save_session(project_dir: str | None, cwd: str | None, session: dict[str, Any]) -> None:
    path = session_path(project_dir, cwd, session["session_id"])
    if path is None:
        raise AdapterError("no writable session state location")
    root = project_root(project_dir, cwd) or Path.cwd()
    atomic_write(path, session, root)


def resolve_mode(
    home_dir: str | None,
    project_dir: str | None,
    cwd: str | None,
    session: dict[str, Any] | None,
) -> tuple[str | None, str]:
    """Resolve the state hierarchy. Mode None means neutral (no shaping)."""
    if session is not None:
        if session.get("stopped"):
            return None, "session-stopped"
        override = session.get("override_mode")
        if override in MODES:
            return override, "session-override"
    project, _why = read_layer("project", home_dir, project_dir, cwd)
    if project is not None:
        mode = project["mode"]
        return (None, "project-off") if mode == OFF else (mode, "project-default")
    user, _why = read_layer("user", home_dir, project_dir, cwd)
    if user is not None:
        mode = user["mode"]
        return (None, "user-off") if mode == OFF else (mode, "user-default")
    return None, "neutral-core"


def write_layer(home_dir: str | None, project_dir: str | None, layer: str, mode: str) -> Path:
    if mode not in MODES + (OFF,):
        raise AdapterError(f"unsupported default mode: {mode}")
    payload = {
        "schema_version": STATE_SCHEMA,
        "layer": layer,
        "mode": mode,
        "rules_digest": rules_digest(),
    }
    if layer == "user":
        home = user_root(home_dir)
        path = home / ".config" / "super-caveman" / "defaults.json"
        atomic_write(path, payload, home)
        return path
    root = project_root(project_dir, None)
    if root is None:
        raise AdapterError("project scope requires a valid project directory")
    path = defaults_path(home_dir, project_dir, None, "project")
    atomic_write(path, payload, root)
    return path


def capsule_text(mode: str | None, why: str, source: str, sid: str) -> str:
    base = pkg_dir()
    if mode is None:
        lines = (
            f"Super Caveman adapter installed; response shaping is off ({why}).",
            "Enable a persistent default: `/super-caveman enable full project` (or `user`).",
            "Activate one session: `/super-caveman full`. Stop a session: `normal mode`.",
        )
    else:
        lines = (
            f"Super Caveman is active. active_mode={mode}.",
            "Apply: safety and explicit format first; action-first ADHD-friendly structure second; Caveman compression last.",
            "Lead with the result or next action. Number multi-step work. Keep current step visible. End with one concrete next action when work remains.",
            "Preserve exact code, commands, paths, numbers, dates, and requested detail. Do not compress safety, order, causality, or required artifacts.",
            "On 'stop super-caveman', 'stop caveman', 'stop adhd mode', or 'normal mode', confirm once and return to normal style.",
            f"Canonical rules: {base / 'SKILL.md'} and {base / 'references' / 'modes.md'}.",
        )
    tail = (
        f"schema_version={CAPSULE_SCHEMA}",
        f"rules_digest={rules_digest()}",
        f"event={source}",
        f"session={sid or 'unknown'}",
    )
    return "\n".join(lines + tail)[:CAPSULE_LIMIT]


def emit_context(event_name: str, context: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def run_render(home_dir: str | None = None, project_dir: str | None = None) -> int:
    """SessionStart handler: one capsule per delivered event, fail open."""
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        source = event.get("source", "startup")
        if source not in SOURCES:
            source = "startup"
        sid = str(event.get("session_id", ""))
        cwd = event.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else None
        try:
            if source == "startup":
                session = fresh_session(sid)
                save_session(project_dir, cwd, session)
            elif source == "resume":
                kept, bad = read_session(project_dir, cwd, sid)
                if bad is None:
                    session = kept
                else:
                    session = fresh_session(sid)
                    save_session(project_dir, cwd, session)
            elif source == "clear":
                session = fresh_session(sid)
                save_session(project_dir, cwd, session)
            else:  # compact preserves the current session state as-is
                session, _bad = read_session(project_dir, cwd, sid)
                if session is None:
                    session = fresh_session(sid)
                    save_session(project_dir, cwd, session)
        except AdapterError:
            session = None  # best-effort state; injection never fails closed
        mode, why = resolve_mode(home_dir, project_dir or cwd, None, session)
        context = capsule_text(mode, why, source, sid)
        emit_context("SessionStart", context)
        return 0
    except Exception as exc:
        print("{}")
        print(f"super-caveman Claude adapter: {exc}", file=sys.stderr)
        return 0


def settings_path(home_dir: str | None, project_dir: str | None, scope: str, hooks_path: str | None) -> tuple[Path, Path]:
    if scope == "project":
        root = project_root(project_dir, None)
        if root is None:
            raise AdapterError("project scope requires a valid project directory")
    else:
        root = user_root(home_dir)
    standard = root / ".claude" / "settings.json"
    path = abspath_raw(hooks_path) if hooks_path else standard
    if path != standard:
        raise AdapterError(f"settings path must be the standard {scope} scope: {standard}")
    reject_links(path.parent, root)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise AdapterError(f"refusing unsafe settings file: {path}")
    return path, root


def hook_command(sub: str) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} {sub}"


def owned_command(command: Any, sub: str) -> bool:
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) != 3 or not tokens[0] or tokens[2] != sub:
        return False
    return Path(tokens[1]).parts[-3:] == ("super-caveman", "scripts", "claude_adapter.py")


def owned_handler(handler: Any, sub: str) -> bool:
    return (
        isinstance(handler, dict)
        and handler.get("type") == "command"
        and handler.get("timeout") == TIMEOUT
        and owned_command(handler.get("command"), sub)
    )


def owned_registration(entry: Any, sub: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if sub == "render":
        if entry.get("matcher") != START_MATCHER:
            return False
    elif "matcher" in entry:
        return False
    handlers = entry.get("hooks")
    if not isinstance(handlers, list) or not handlers:
        return False
    return all(owned_handler(item, sub) for item in handlers)


def split_owned(entries: list[Any], sub: str) -> tuple[list[Any], list[Any]]:
    mine: list[Any] = []
    other: list[Any] = []
    for entry in entries:
        if owned_registration(entry, sub):
            mine.append(entry)
        else:
            other.append(entry)
    return mine, other


def load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"cannot read valid JSON settings: {path}") from exc
    if not isinstance(payload, dict):
        raise AdapterError("Claude settings root must be a JSON object")
    return payload


def new_registration(sub: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command(sub),
                "timeout": TIMEOUT,
            }
        ]
    }
    if sub == "render":
        entry["matcher"] = START_MATCHER
    return entry


def install_entry(payload: dict[str, Any], sub: str, event: str) -> dict[str, Any]:
    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AdapterError("Claude settings hooks field must be an object")
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        raise AdapterError(f"Claude {event} hooks must be an array")
    _mine, other = split_owned(entries, sub)
    hooks[event] = [*other, new_registration(sub)]
    return payload


def uninstall_entry(payload: dict[str, Any], sub: str, event: str) -> dict[str, Any]:
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return payload
    entries = hooks.get(event)
    if isinstance(entries, list):
        _mine, other = split_owned(entries, sub)
        if other:
            hooks[event] = other
        else:
            hooks.pop(event, None)
    if not hooks:
        payload.pop("hooks", None)
    return payload


def write_layer_cli(args: argparse.Namespace) -> int:
    mode = args.mode if args.command == "enable" else OFF
    path = write_layer(args.home_dir, args.project_dir, args.scope, mode)
    print(json.dumps({"ok": True, "command": args.command, "scope": args.scope, "mode": mode, "state": str(path)}))
    return 0


def status_report(home_dir: str | None, project_dir: str | None) -> dict[str, Any]:
    user, user_why = read_layer("user", home_dir, project_dir, None)
    project, project_why = read_layer("project", home_dir, project_dir, None)
    report: dict[str, Any] = {
        "package": "super-caveman",
        "package_version": None,
        "adapter_schema": SCHEMA_VERSION,
        "state_schema": STATE_SCHEMA,
        "rules_digest": rules_digest(),
        "defaults": {
            "user": ({"mode": user["mode"]} if user else {"mode": None, "reason": user_why}),
            "project": ({"mode": project["mode"]} if project else {"mode": None, "reason": project_why}),
        },
    }
    return report


ROUTE_CONTRACTS = {
    "commit": "Return paste-ready Conventional Commit text only; never stage or commit.",
    "review": "Return location, problem, fix; never approve or edit.",
    "compress": "Run guarded compression with recovery gates.",
}


def reinforce(mode: str | None, route: str | None) -> str | None:
    if route in ROUTES:
        text = (
            f"Super Caveman one-shot {route} route. {ROUTE_CONTRACTS[route]} "
            f"Session mode {mode} resumes after this turn."
        )
        return text[:PROMPT_LIMIT]
    if mode is None:
        return None
    return (
        f"Super Caveman active: mode={mode}. Action-first structure first; Caveman compression last. "
        "Preserve exact code, commands, numbers. Stop with 'normal mode'."
    )[:PROMPT_LIMIT]


def parse_trigger(prompt: str) -> tuple[str, list[str]]:
    lowered = prompt.strip().lower()
    if lowered in STOPS:
        return "stop", []
    tokens = prompt.strip().split()
    if tokens and tokens[0].lower() in CMDS:
        return "command", [t.lower() for t in tokens[1:]]
    return "plain", []


def run_prompt(home_dir: str | None, project_dir: str | None) -> int:
    """UserPromptSubmit handler: parse trigger, mutate session state, fail open."""
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        prompt = event.get("prompt")
        if not isinstance(prompt, str):
            prompt = ""
        sid = str(event.get("session_id", ""))
        cwd = event.get("cwd")
        cwd = cwd if isinstance(cwd, str) and cwd else None
        scope = project_dir or cwd
        kind, rest = parse_trigger(prompt)
        session, _bad = read_session(project_dir, cwd, sid)
        work = dict(session) if session else None
        dirty = False
        mode = None
        route = None
        text = None
        if kind == "stop":
            if work is None:
                work = fresh_session(sid)
            work["stopped"] = True
            work["override_mode"] = None
            work["one_shot"] = None
            work["previous_mode"] = None
            dirty = True
        elif kind == "command" and rest:
            head = rest[0]
            if head in MODES:
                if work is None:
                    work = fresh_session(sid)
                work["stopped"] = False
                work["override_mode"] = head
                dirty = True
                mode = head
            elif head == "enable" and len(rest) >= 3 and rest[1] in MODES and rest[2] in ("project", "user"):
                write_layer(home_dir, scope, rest[2], rest[1])
                text = f"Super Caveman persistent default enabled: mode={rest[1]} at {rest[2]} scope. New sessions start in this mode."
            elif head == "disable" and len(rest) >= 2 and rest[1] in ("project", "user"):
                write_layer(home_dir, scope, rest[1], OFF)
                text = f"Super Caveman persistent default disabled at {rest[1]} scope (mode=off). Session overrides still win for this session."
            elif head == "status":
                text = status_text(home_dir, project_dir, cwd, work)
            elif head == "help":
                text = help_text()
            elif head == "stats":
                text = stats_text()
            elif head in ROUTES:
                if work is None:
                    work = fresh_session(sid)
                if work.get("one_shot") not in ROUTES:
                    prev, _w = resolve_mode(home_dir, scope, None, work)
                    work["previous_mode"] = prev
                work["one_shot"] = head
                dirty = True
                mode = resolve_mode(home_dir, scope, None, work)[0]
                route = head
            else:
                mode, _w = resolve_mode(home_dir, scope, None, work)
        else:
            if work is not None and work.get("one_shot") in ROUTES:
                work["one_shot"] = None
                work["previous_mode"] = None
                dirty = True
            mode, _w = resolve_mode(home_dir, scope, None, work)
        if dirty and work is not None:
            save_session(project_dir, cwd, work)
        out = text if text is not None else reinforce(mode, route)
        if out is None:
            print("{}")
        else:
            emit_context("UserPromptSubmit", out)
        return 0
    except Exception as exc:
        print("{}")
        print(f"super-caveman Claude adapter: {exc}", file=sys.stderr)
        return 0


def status_text(home_dir: str | None, project_dir: str | None, cwd: str | None, session: dict[str, Any] | None) -> str:
    user, _u = read_layer("user", home_dir, project_dir, cwd)
    project, _p = read_layer("project", home_dir, project_dir, cwd)
    user_mode = user["mode"] if user else None
    project_mode = project["mode"] if project else None
    session_mode, why = resolve_mode(home_dir, project_dir or cwd, None, session)
    stop = bool(session and session.get("stopped"))
    parts = [
        "Super Caveman adapter status:",
        f"- persistent user default: {user_mode or 'unset'}",
        f"- persistent project default: {project_mode or 'unset'}",
        f"- session: stopped={stop}, override={session and session.get('override_mode') or 'none'}",
        f"- effective mode: {session_mode or 'neutral (no shaping)'} ({why})",
        f"- rules digest: {rules_digest()[:16]}...",
    ]
    return "\n".join(parts)[:PROMPT_LIMIT]


def help_text() -> str:
    return (
        "Super Caveman commands: /super-caveman [lite|full|ultra|wenyan-lite|wenyan-full|wenyan-ultra]; "
        "enable <mode> <project|user>; disable <project|user>; commit|review|compress (one-shot); "
        "status; help; stats. Stop phrases: stop super-caveman, stop caveman, stop adhd mode, normal mode."
    )[:PROMPT_LIMIT]


def stats_text() -> str:
    return (
        "No audited counters available. Exact statistics require host counters or an audited log; "
        "automatic private-log scanning stays out of scope."
    )[:PROMPT_LIMIT]


def setup_cli(args: argparse.Namespace) -> int:
    path, root = settings_path(args.home_dir, args.project_dir, args.scope, args.hooks_path)
    payload = load_settings(path)
    payload = install_entry(payload, "render", "SessionStart")
    payload = install_entry(payload, "prompt", "UserPromptSubmit")
    atomic_write(path, payload, root)
    print(json.dumps({"ok": True, "command": "setup", "scope": args.scope, "settings": str(path)}))
    return 0


def uninstall_cli(args: argparse.Namespace) -> int:
    path, root = settings_path(args.home_dir, args.project_dir, args.scope, args.hooks_path)
    payload = load_settings(path)
    payload = uninstall_entry(payload, "render", "SessionStart")
    payload = uninstall_entry(payload, "prompt", "UserPromptSubmit")
    if path.exists() or payload:
        atomic_write(path, payload, root)
    if args.purge_state:
        state = state_dir_for(args.project_dir, None)
        if state is not None and state.exists():
            drop_state_tree(state, project_root(args.project_dir, None) or Path.home())
        if args.scope == "user":
            home = user_root(args.home_dir)
            cfg = home / ".config" / "super-caveman"
            if cfg.exists():
                drop_state_tree(cfg, home)
    print(json.dumps({"ok": True, "command": "uninstall", "scope": args.scope, "settings": str(path)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "uninstall"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--scope", required=True, choices=("project", "user"))
        cmd.add_argument("--hooks-path")
        cmd.add_argument("--purge-state", action="store_true")
        cmd.add_argument("--project-dir")
        cmd.add_argument("--home-dir")
    enable = sub.add_parser("enable")
    enable.add_argument("--scope", required=True, choices=("project", "user"))
    enable.add_argument("--mode", required=True, choices=MODES)
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
            return setup_cli(args)
        if args.command == "uninstall":
            return uninstall_cli(args)
        if args.command == "enable":
            return write_layer_cli(args)
        if args.command == "disable":
            return write_layer_cli(args)
        if args.command == "status":
            print(json.dumps(status_report(home, project), ensure_ascii=False, indent=2))
            return 0
        if args.command == "render":
            return run_render(home, project)
        if args.command == "prompt":
            return run_prompt(home, project)
    except AdapterError as exc:
        print(f"super-caveman Claude adapter: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

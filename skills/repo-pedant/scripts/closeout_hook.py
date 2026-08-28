#!/usr/bin/env python3
"""Harness-neutral advisory and opt-in repo-pedant closeout hook."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import azhou_runtime_state


SCHEMA_VERSION = "repo-pedant.closeout-state.v1"
REMINDER = "🟡 阿舟提醒｜Repo Pedant 收尾尚未完成。完成当前收尾，或记录 hold 与 receipt。"
PRECOMPACT_REMINDER = "🧠 阿舟记忆检查｜存在未记录的 Repo Pedant 进展。压缩前写入 inventory 或 receipt。"
VALID_STATUSES = {"needs_closeout", "active", "complete", "held"}
STATE_FIELDS = {"schema_version", "repo_root", "session_id", "status", "progress", "unrecorded_progress", "receipt_digest"}


class HookError(ValueError):
    pass


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def load_input(max_bytes: int) -> tuple[dict[str, Any], bool]:
    raw = sys.stdin.buffer.read(max_bytes + 1)
    truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]
    if not raw.strip():
        return {}, truncated
    try:
        value = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}, truncated
    return (value if isinstance(value, dict) else {}), truncated


def load_closeout_state(workspace: Path, relative_state: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        return None, ["workspace_missing"]
    raw_candidate = workspace / relative_state
    if raw_candidate.is_symlink():
        return None, ["state_symlink_rejected"]
    candidate = raw_candidate.resolve()
    if not inside(candidate, workspace):
        return None, ["state_outside_workspace"]
    if not candidate.is_file():
        return None, []
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, ["state_invalid_json"]
    if not isinstance(value, dict):
        return None, ["state_not_object"]
    if set(value) - STATE_FIELDS:
        errors.append("state_unknown_fields")
    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append("state_schema_invalid")
    if value.get("status") not in VALID_STATUSES:
        errors.append("state_status_invalid")
    declared_root = value.get("repo_root")
    if not isinstance(declared_root, str) or Path(declared_root).expanduser().resolve() != workspace:
        errors.append("state_workspace_mismatch")
    progress = value.get("progress")
    if not isinstance(progress, int) or isinstance(progress, bool) or progress < 0:
        errors.append("state_progress_invalid")
    if not isinstance(value.get("session_id"), str):
        errors.append("state_session_invalid")
    if not isinstance(value.get("unrecorded_progress"), bool):
        errors.append("state_unrecorded_progress_invalid")
    receipt_digest = value.get("receipt_digest")
    if receipt_digest is not None and (not isinstance(receipt_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", receipt_digest)):
        errors.append("state_receipt_digest_invalid")
    return (None if errors else value), errors


def runtime_state_directory(value: Path | None, workspace: Path) -> Path:
    try:
        namespace = azhou_runtime_state.state_path(workspace, "repo-pedant")
        if value is None:
            return azhou_runtime_state.state_path(workspace, "repo-pedant", "hooks")
        raw = value.expanduser()
        relative = raw.resolve(strict=False).relative_to(workspace) if raw.is_absolute() else raw
        candidate = azhou_runtime_state.relative_path(workspace, relative)
        candidate.relative_to(namespace)
        return candidate
    except (ValueError, azhou_runtime_state.StateError) as exc:
        raise HookError("hook runtime state must stay inside .azhou/repo-pedant") from exc


def counter_path(directory: Path, workspace: Path, session_id: str) -> Path:
    digest = hashlib.sha256(f"{workspace}\0{session_id}".encode("utf-8")).hexdigest()[:24]
    return directory / f"{digest}.json"


def read_counter(path: Path) -> dict[str, int]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"blocks": 0, "last_progress": -1}
    if not isinstance(value, dict):
        return {"blocks": 0, "last_progress": -1}
    blocks = value.get("blocks", 0)
    last_progress = value.get("last_progress", -1)
    if not isinstance(blocks, int) or blocks < 0:
        blocks = 0
    if not isinstance(last_progress, int):
        last_progress = -1
    return {"blocks": blocks, "last_progress": last_progress}


def write_counter(path: Path, value: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def fixed_output(message: str, output_format: str, *, block: bool = False) -> str:
    if output_format == "plain":
        return message
    if block and output_format == "claude":
        return json.dumps({"decision": "block", "reason": message}, separators=(",", ":"))
    return json.dumps({"systemMessage": message}, separators=(",", ":"))


def evaluate_event(args: argparse.Namespace, hook_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    workspace = args.workspace.expanduser().resolve()
    state, state_errors = load_closeout_state(workspace, args.state)
    diagnostic = {
        "state_loaded": state is not None,
        "state_errors": state_errors,
        "action": "none",
        "truncated_input": False,
    }
    if state is None or state.get("status") in {"complete", "held"}:
        return "", diagnostic

    state_session = str(state.get("session_id") or "")
    input_session = str(hook_input.get("session_id") or hook_input.get("sessionId") or "")
    if state_session and input_session and state_session != input_session:
        diagnostic["action"] = "session_mismatch"
        return "", diagnostic

    if args.event == "precompact":
        if state.get("status") == "active" and state.get("unrecorded_progress") is True:
            diagnostic["action"] = "advisory"
            return fixed_output(PRECOMPACT_REMINDER, args.format), diagnostic
        return "", diagnostic

    if args.event != "stop":
        return "", diagnostic

    wants_gate = args.mode == "gate" and args.format == "claude"
    recursive = bool(hook_input.get("stop_hook_active") or hook_input.get("stopHookActive"))
    if wants_gate and not recursive:
        session_id = state_session or input_session or "unknown"
        private_dir = runtime_state_directory(args.runtime_state_dir, workspace)
        counters_file = counter_path(private_dir, workspace, session_id)
        counters = read_counter(counters_file)
        progress = int(state["progress"])
        advanced = counters["blocks"] == 0 or progress > counters["last_progress"]
        if counters["blocks"] < args.block_cap and advanced:
            write_counter(counters_file, {"blocks": counters["blocks"] + 1, "last_progress": progress})
            diagnostic["action"] = "block"
            return fixed_output(REMINDER, args.format, block=True), diagnostic
        diagnostic["action"] = "gate_degraded_stall_or_cap"

    if diagnostic["action"] == "none":
        diagnostic["action"] = "advisory"
    return fixed_output(REMINDER, args.format), diagnostic


def cmd_event(args: argparse.Namespace) -> int:
    if os.environ.get("REPO_PEDANT_DISABLED") == "1":
        return 0
    hook_input, truncated = load_input(args.max_input_bytes)
    if args.workspace_from_input:
        input_workspace = hook_input.get("cwd") or hook_input.get("workspace") or hook_input.get("workspace_root")
        if not isinstance(input_workspace, str) or not input_workspace:
            return 0
        args.workspace = Path(input_workspace)
    try:
        output, diagnostic = evaluate_event(args, hook_input)
    except (HookError, OSError, ValueError):
        return 0
    diagnostic["truncated_input"] = truncated
    if output:
        print(output)
    if args.diagnostic:
        print(json.dumps(diagnostic, ensure_ascii=False, separators=(",", ":")), file=sys.stderr)
    return 0


def parse_requirement(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise HookError("required environment must use NAME=VALUE")
    name, expected = value.split("=", 1)
    if not name or not name.replace("_", "").isalnum():
        raise HookError("invalid environment name")
    return name, expected


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    workspace = args.workspace.expanduser().resolve()
    state, state_errors = load_closeout_state(workspace, args.state)
    checks.append({"name": "workspace", "status": "pass" if workspace.is_dir() else "fail"})
    checks.append({"name": "state", "status": "pass" if state is not None else "warn", "details": state_errors})
    configs_with_hook: list[str] = []
    for config in args.config:
        path = config.expanduser().resolve()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            checks.append({"name": f"config:{path}", "status": "fail", "details": ["unreadable"]})
            continue
        if "closeout_hook.py" in text:
            configs_with_hook.append(str(path))
        checks.append({"name": f"config:{path}", "status": "pass"})
    checks.append(
        {
            "name": "duplicate_install",
            "status": "fail" if len(configs_with_hook) > 1 else "pass",
            "details": configs_with_hook,
        }
    )
    try:
        requirements = [parse_requirement(value) for value in args.require_env]
    except HookError as exc:
        checks.append({"name": "feature_flags", "status": "fail", "details": [str(exc)]})
        requirements = []
    for name, expected in requirements:
        checks.append(
            {
                "name": f"env:{name}",
                "status": "pass" if os.environ.get(name) == expected else "fail",
                "details": [f"expected={expected}"],
            }
        )
    failed = any(check["status"] == "fail" for check in checks)
    print(json.dumps({"valid": not failed, "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    event = subparsers.add_parser("event", help="evaluate one lifecycle event")
    event.add_argument("--event", choices=("stop", "precompact"), required=True)
    event.add_argument("--workspace", default=Path("."), type=Path)
    event.add_argument("--workspace-from-input", action="store_true", help="resolve workspace from bounded hook JSON cwd/workspace fields")
    event.add_argument("--state", default=".azhou/repo-pedant/closeout-state.json")
    event.add_argument("--mode", choices=("advisory", "gate"), default="advisory")
    event.add_argument("--format", choices=("plain", "claude", "codex", "json"), default="plain")
    event.add_argument("--block-cap", type=int, default=3)
    event.add_argument("--runtime-state-dir", type=Path)
    event.add_argument("--max-input-bytes", type=int, default=65536)
    event.add_argument("--diagnostic", action="store_true")
    event.set_defaults(func=cmd_event)
    doctor = subparsers.add_parser("doctor", help="diagnose state, feature flags, and duplicate hook installs")
    doctor.add_argument("--workspace", required=True, type=Path)
    doctor.add_argument("--state", default=".azhou/repo-pedant/closeout-state.json")
    doctor.add_argument("--config", action="append", default=[], type=Path)
    doctor.add_argument("--require-env", action="append", default=[])
    doctor.set_defaults(func=cmd_doctor)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if getattr(args, "block_cap", 1) < 1 or getattr(args, "max_input_bytes", 1) < 256:
        print("invalid positive bound", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

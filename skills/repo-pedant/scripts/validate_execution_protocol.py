#!/usr/bin/env python3
"""Validate Repo Pedant stage order, exact brand anchors, and verification timing."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "repo-pedant.execution.v1"
MODES = {"audit", "reconcile", "handoff", "evolve"}
RESULTS = {"passed", "failed"}
CHECK_STATUSES = {"passed", "not_applicable", "failed"}
REQUIRED_CHECKS = ("inventory", "readback", "tests", "links", "diff", "coverage")
BASE_STAGES = ("start", "scope", "inventory", "impact", "sync")
VERIFY_STAGES = {"verify_failure", "verify_success"}
ALL_STAGES = {*BASE_STAGES, *VERIFY_STAGES}
CHECK_ID = re.compile(r"[a-z][a-z0-9_-]*")
MESSAGE_PATTERNS = {
    "scope": re.compile(r"🧭 范围锁定｜authority=.+｜projects=[1-9][0-9]*"),
    "inventory": re.compile(r"🗂️ 清单完成｜files=[0-9]+｜holds=[0-9]+｜out_of_scope=[0-9]+"),
    "impact": re.compile(r"🕸️ 影响确认｜surfaces=[0-9]+｜consumers=[0-9]+"),
    "sync": re.compile(r"🧹 同步完成｜changed=(?:none|[0-9]+)"),
    "verify_failure": re.compile(r"❌ 验证失败｜check=([a-z][a-z0-9_-]*)｜impact=.+"),
}


class ProtocolError(ValueError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"unable to read execution protocol: {path} ({type(exc).__name__})") from exc


def validate_protocol(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["protocol: expected object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: expected {SCHEMA_VERSION}")

    mode = data.get("mode")
    if mode not in MODES:
        errors.append("mode: expected audit, reconcile, handoff, or evolve")
    scope = data.get("scope")
    if not isinstance(scope, str) or not scope.strip() or "｜" in scope:
        errors.append("scope: expected non-empty text without the field delimiter")
        scope = ""
    result = data.get("result")
    if result not in RESULTS:
        errors.append("result: expected passed or failed")

    checks = data.get("checks")
    check_ids: list[str] = []
    check_status: dict[str, str] = {}
    if not isinstance(checks, list) or not checks:
        errors.append("checks: expected non-empty array")
        checks = []
    for index, check in enumerate(checks):
        label = f"checks[{index}]"
        if not isinstance(check, dict):
            errors.append(f"{label}: expected object")
            continue
        check_id = check.get("id")
        if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
            errors.append(f"{label}.id: expected stable lowercase identifier")
            continue
        if check_id in check_status:
            errors.append(f"{label}.id: duplicate {check_id}")
            continue
        status = check.get("status")
        if status not in CHECK_STATUSES:
            errors.append(f"{label}.status: expected passed, not_applicable, or failed")
        evidence = check.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"{label}.evidence: exact command, artifact, or readback evidence required")
        if status == "not_applicable" and not str(check.get("reason", "")).strip():
            errors.append(f"{label}.reason: required for not_applicable")
        check_ids.append(check_id)
        check_status[check_id] = status
    missing_checks = [check_id for check_id in REQUIRED_CHECKS if check_id not in check_status]
    if missing_checks:
        errors.append(f"checks: missing fixed verification checks: {', '.join(missing_checks)}")

    events = data.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events: expected non-empty array")
        events = []
    stages: list[str] = []
    failure_checks: list[str] = []
    success_events: list[tuple[int, dict[str, Any]]] = []
    for index, event in enumerate(events):
        label = f"events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{label}: expected object")
            continue
        stage = event.get("stage")
        message = event.get("message")
        if stage not in ALL_STAGES:
            errors.append(f"{label}.stage: unknown stage")
            continue
        stages.append(stage)
        if not isinstance(message, str):
            errors.append(f"{label}.message: expected string")
            continue
        if stage == "start":
            expected = f"🦊 阿舟 · Repo Pedant 启动｜mode={mode}｜scope={scope}"
            if message != expected:
                errors.append(f"{label}.message: expected exact start anchor {expected}")
        elif stage == "verify_success":
            success_events.append((index, event))
        else:
            pattern = MESSAGE_PATTERNS[stage]
            match = pattern.fullmatch(message)
            if match is None:
                errors.append(f"{label}.message: expected exact {stage} anchor and field delimiters")
            elif stage == "verify_failure":
                failure_checks.append(match.group(1))

    base_sequence = [stage for stage in stages if stage in BASE_STAGES]
    if tuple(base_sequence) != BASE_STAGES:
        errors.append("events: fixed stages must appear exactly once in order: start, scope, inventory, impact, sync")
    if "sync" in stages:
        sync_index = stages.index("sync")
        if any(stage in VERIFY_STAGES for stage in stages[:sync_index]):
            errors.append("events: verification cannot precede sync completion")
    for check_id in failure_checks:
        if check_id not in check_status:
            errors.append(f"events.verify_failure: unknown check {check_id}")

    if result == "passed":
        failed = [check_id for check_id, status in check_status.items() if status == "failed"]
        if failed:
            errors.append(f"result: passed cannot contain failed checks: {', '.join(failed)}")
        if len(success_events) != 1:
            errors.append("events: passed result requires exactly one verify_success event")
        else:
            success_index, success = success_events[0]
            if success_index != len(events) - 1:
                errors.append("events.verify_success: success must be the last event after every required check")
            completed = success.get("completed_checks")
            if completed != check_ids:
                errors.append("events.verify_success.completed_checks: must exactly match every declared check in order")
            expected = f"✅ 验证通过｜checks={','.join(check_ids)}"
            if success.get("message") != expected:
                errors.append(f"events.verify_success.message: expected exact success anchor {expected}")
    elif result == "failed":
        if success_events:
            errors.append("events: failed result cannot contain verify_success")
        failed = [check_id for check_id, status in check_status.items() if status == "failed"]
        if not failed:
            errors.append("checks: failed result requires at least one failed check")
        if not events or not isinstance(events[-1], dict) or events[-1].get("stage") != "verify_failure":
            errors.append("events: failed result must end with verify_failure")
        elif failure_checks and failure_checks[-1] not in failed:
            errors.append("events.verify_failure: final failed check must have status failed")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "protocol",
        nargs="?",
        type=Path,
        default=Path(".azhou/repo-pedant/execution.json"),
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        errors = validate_protocol(read_json(args.protocol))
    except ProtocolError as exc:
        errors = [str(exc)]
    if args.format == "json":
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("\n".join(errors))
    else:
        print("valid execution protocol")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate repo-pedant benchmark cases and first-pass candidate runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


BENCHMARK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARK_ROOT.parents[1]
MANIFEST = BENCHMARK_ROOT / "manifest.json"
VALIDATOR_DIR = REPO_ROOT / "skills" / "repo-pedant" / "scripts"
sys.path.insert(0, str(VALIDATOR_DIR))

from validate_evidence_bundle import validate_receipt  # noqa: E402


CASE_FIELDS = {
    "schema_version",
    "id",
    "prompt",
    "expected_output",
    "fixture",
    "verify_command",
    "protected_paths",
    "required_outputs",
    "require_receipt",
}


class BenchmarkError(ValueError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"unable to read JSON: {path} ({type(exc).__name__})") from exc


def resolve_inside(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise BenchmarkError("path must be a non-empty string")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise BenchmarkError(f"path escapes benchmark boundary: {relative}") from exc
    return candidate


def validate_case(case: Any, case_path: Path) -> list[str]:
    errors: list[str] = []
    label = case_path.name
    if not isinstance(case, dict):
        return [f"{label}: expected object"]
    missing = sorted(CASE_FIELDS - set(case))
    if missing:
        errors.append(f"{label}: missing fields {', '.join(missing)}")
    unexpected = sorted(set(case) - CASE_FIELDS)
    if unexpected:
        errors.append(f"{label}: unexpected fields {', '.join(unexpected)}")
    if case.get("schema_version") != 1:
        errors.append(f"{label}: schema_version must be 1")
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        errors.append(f"{label}: id must be a non-empty string")
    elif case_path.name != f"{case_id}.case.json":
        errors.append(f"{label}: filename must match id")
    for field in ("prompt", "expected_output", "fixture"):
        if not isinstance(case.get(field), str) or not case[field].strip():
            errors.append(f"{label}: {field} must be a non-empty string")
    command = case.get("verify_command")
    if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
        errors.append(f"{label}: verify_command must be a non-empty string array")
    for field in ("protected_paths", "required_outputs"):
        values = case.get(field)
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            errors.append(f"{label}: {field} must be a non-empty string array")
        elif len(values) != len(set(values)):
            errors.append(f"{label}: {field} contains duplicates")
    if not isinstance(case.get("require_receipt"), bool):
        errors.append(f"{label}: require_receipt must be boolean")
    return errors


def load_cases() -> list[tuple[dict[str, Any], Path]]:
    manifest = read_json(MANIFEST)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise BenchmarkError("manifest schema_version must be 1")
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise BenchmarkError("manifest cases must be a non-empty array")
    cases: list[tuple[dict[str, Any], Path]] = []
    seen: set[str] = set()
    for entry in entries:
        path = resolve_inside(BENCHMARK_ROOT, entry)
        case = read_json(path)
        errors = validate_case(case, path)
        if errors:
            raise BenchmarkError("; ".join(errors))
        case_id = case["id"]
        if case_id in seen:
            raise BenchmarkError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        cases.append((case, path))
    return cases


def find_case(case_id: str) -> dict[str, Any]:
    for case, _ in load_cases():
        if case["id"] == case_id:
            return case
    raise BenchmarkError(f"unknown case: {case_id}")


def run_verify_command(case: dict[str, Any], candidate: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            case["verify_command"],
            cwd=candidate,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BenchmarkError(f"verify command could not complete ({type(exc).__name__})") from exc


def path_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_symlink():
        raise BenchmarkError(f"protected path cannot be a symlink: {path.name}")
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if path.is_dir():
        digest.update(b"dir\0")
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            if child.is_symlink():
                raise BenchmarkError(f"protected tree cannot contain symlink: {child.name}")
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    raise BenchmarkError(f"protected path missing: {path.name}")


def review_passed(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") == "passed"
        and isinstance(value.get("reviewer"), str)
        and bool(value["reviewer"].strip())
    )


def validate_run(run: Any, case_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(run, dict):
        return ["run: expected object"]
    if run.get("schema_version") != 1:
        errors.append("run.schema_version: must be 1")
    if run.get("case_id") != case_id:
        errors.append("run.case_id: does not match requested case")
    if run.get("attempt") != 1 or isinstance(run.get("attempt"), bool):
        errors.append("run.attempt: first-pass benchmark accepts exactly 1")
    for field in ("agent", "model"):
        if not isinstance(run.get(field), str) or not run[field].strip():
            errors.append(f"run.{field}: expected non-empty string")
    for field in ("human_review", "safety_review"):
        if not isinstance(run.get(field), dict):
            errors.append(f"run.{field}: expected object")
    return errors


def cmd_check(_: argparse.Namespace) -> int:
    try:
        cases = load_cases()
        errors: list[str] = []
        for case, path in cases:
            fixture = resolve_inside(BENCHMARK_ROOT, case["fixture"])
            if not fixture.is_dir():
                errors.append(f"{case['id']}: fixture directory missing")
                continue
            command_path = resolve_inside(fixture, case["verify_command"][0])
            if not command_path.is_file() or not os.access(command_path, os.X_OK):
                errors.append(f"{case['id']}: verify command missing or not executable")
            for value in case["protected_paths"]:
                try:
                    protected = resolve_inside(fixture, value)
                    path_digest(protected)
                except (BenchmarkError, OSError) as exc:
                    errors.append(f"{case['id']}: invalid protected path {value} ({type(exc).__name__})")
            for value in case["required_outputs"]:
                output = resolve_inside(fixture, value)
                if output.exists():
                    errors.append(f"{case['id']}: required output is baked into fixture: {value}")
            pristine = run_verify_command(case, fixture)
            if pristine.returncode == 0:
                errors.append(f"{case['id']}: pristine fixture unexpectedly passes")
            if path.parent != BENCHMARK_ROOT / "cases":
                errors.append(f"{case['id']}: case file must live under cases/")
    except BenchmarkError as exc:
        errors = [str(exc)]
        cases = []
    result = {"valid": not errors, "cases": len(cases), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        case = find_case(args.case)
        fixture = resolve_inside(BENCHMARK_ROOT, case["fixture"])
        candidate = args.candidate.resolve()
        if not candidate.is_dir():
            raise BenchmarkError("candidate directory missing")
        if candidate == fixture:
            raise BenchmarkError("candidate must be a copy, not the pristine fixture")
        run = read_json(args.run.resolve())
        run_errors = validate_run(run, case["id"])
        if run_errors:
            raise BenchmarkError("; ".join(run_errors))

        process = run_verify_command(case, candidate)
        protected_errors: list[str] = []
        for value in case["protected_paths"]:
            try:
                baseline_path = resolve_inside(fixture, value)
                candidate_path = resolve_inside(candidate, value)
                if path_digest(baseline_path) != path_digest(candidate_path):
                    protected_errors.append(value)
            except (BenchmarkError, OSError):
                protected_errors.append(value)

        missing_outputs: list[str] = []
        for value in case["required_outputs"]:
            try:
                output = resolve_inside(candidate, value)
            except BenchmarkError:
                missing_outputs.append(value)
                continue
            if not output.is_file():
                missing_outputs.append(value)

        receipt_errors: list[str] = []
        if case["require_receipt"]:
            response = resolve_inside(candidate, "response.md")
            if response.is_file():
                try:
                    receipt_errors = validate_receipt(response.read_text(encoding="utf-8"))
                except (OSError, UnicodeError):
                    receipt_errors = ["receipt.response: unable to read"]
            else:
                receipt_errors = ["receipt.response: missing"]

        gates = {
            "deterministic": process.returncode == 0,
            "protected_paths": not protected_errors,
            "required_outputs": not missing_outputs,
            "receipt": not receipt_errors,
            "human_review": review_passed(run.get("human_review")),
            "safety_review": review_passed(run.get("safety_review")),
        }
        result = {
            "schema_version": 1,
            "case_id": case["id"],
            "agent": run["agent"],
            "model": run["model"],
            "attempt": 1,
            "verify_return_code": process.returncode,
            "gates": gates,
            "protected_path_failures": protected_errors,
            "missing_outputs": missing_outputs,
            "receipt_errors": receipt_errors,
            "first_pass_usable": all(gates.values()),
        }
    except BenchmarkError as exc:
        print(json.dumps({"valid_invocation": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["first_pass_usable"] else 1


def cmd_report(args: argparse.Namespace) -> int:
    try:
        rows = []
        for line_number, line in enumerate(args.results.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or "first_pass_usable" not in value:
                raise BenchmarkError(f"results line {line_number}: invalid verify result")
            rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError, BenchmarkError) as exc:
        print(json.dumps({"valid": False, "errors": [f"unable to read results ({type(exc).__name__})"]}))
        return 2
    by_case: dict[str, dict[str, int]] = {}
    for row in rows:
        counts = by_case.setdefault(str(row.get("case_id", "unknown")), {"runs": 0, "usable": 0})
        counts["runs"] += 1
        counts["usable"] += int(row["first_pass_usable"] is True)
    print(json.dumps({"valid": True, "runs": len(rows), "usable": sum(v["usable"] for v in by_case.values()), "by_case": by_case}, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate manifest, cases, fixtures, and gates")
    check.set_defaults(func=cmd_check)
    verify = subparsers.add_parser("verify", help="verify one first-pass candidate")
    verify.add_argument("--case", required=True)
    verify.add_argument("--candidate", required=True, type=Path)
    verify.add_argument("--run", required=True, type=Path)
    verify.set_defaults(func=cmd_verify)
    report = subparsers.add_parser("report", help="aggregate verify-result JSONL")
    report.add_argument("--results", required=True, type=Path)
    report.set_defaults(func=cmd_report)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

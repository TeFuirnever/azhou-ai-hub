#!/usr/bin/env python3
"""Validate privacy-preserving repo-pedant history reports and receipts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "repo-pedant.history.v1"
RUNTIMES = ("codex", "claude", "zcode")
INVOCATION_KINDS = ("explicit_user", "skill_tool", "skill_file_read", "receipt_inferred")
OUTCOMES = ("aborted", "user_corrected", "tool_failure_signal", "receipt_emitted", "insufficient_evidence")
DIGEST_RE = re.compile(r"^[0-9a-f]{16}$")
TOP_FIELDS = {
    "schema_version",
    "generated_at",
    "skill_names",
    "privacy",
    "runtime_coverage",
    "runs_found",
    "outcome_counts",
    "runs",
}
PRIVACY_FIELDS = {
    "raw_text_included",
    "excerpts_redacted_and_truncated",
    "identifiers_hashed",
    "transcripts_treated_as_untrusted",
}
COVERAGE_FIELDS = {"files_scanned", "parse_errors", "runs_found", "limit_per_runtime"}
RUN_FIELDS = {
    "run_id",
    "runtime",
    "origin",
    "session_digest",
    "source_digest",
    "session_started_at",
    "request_digest",
    "invocation_kind",
    "assistant_messages",
    "tool_calls_heuristic",
    "mutation_calls_heuristic",
    "destructive_calls_heuristic",
    "failed_tool_outputs_heuristic",
    "user_corrections_heuristic",
    "aborted",
    "receipt_present",
    "outcome_signal",
}
EXCERPT_FIELDS = {"request_excerpt", "correction_excerpts"}
COUNTER_FIELDS = {
    "assistant_messages",
    "tool_calls_heuristic",
    "mutation_calls_heuristic",
    "destructive_calls_heuristic",
    "failed_tool_outputs_heuristic",
    "user_corrections_heuristic",
}
LEGACY_RECEIPT_HEADER = "## Repo-pedant receipt"
BRANDED_RECEIPT_HEADER = "## 🦊 阿舟 · Repo-pedant receipt"
BRANDED_RECEIPT_SCHEMA = "repo-pedant.receipt.v2"
BRAND_SLOGAN = "> 🧹 代码是唯一现役答案，其他都要对齐。"
LEGACY_RECEIPT_FIELDS = (
    "Mode",
    "Scope",
    "Current truth",
    "Changed",
    "Reminders",
    "Verified",
    "Holds",
    "Learning signal",
)
BRANDED_RECEIPT_FIELDS = (
    "Schema",
    "Status",
    "Mode",
    "Scope",
    "Current truth",
    "Changed",
    "Reminders",
    "Verified",
    "Holds",
    "Next action",
    "Learning signal",
)
RECEIPT_MODES = {"audit", "reconcile", "handoff", "evolve"}
RECEIPT_STATUSES = {"complete", "complete_with_holds", "audit_only", "failed"}


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _unexpected(actual: Iterable[str], allowed: set[str]) -> list[str]:
    return sorted(set(actual) - allowed)


def validate_report(
    data: Any,
    *,
    required_runtimes: Iterable[str] = (),
    allow_excerpts: bool = False,
) -> list[str]:
    """Return field-only diagnostics. Never include report values in errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["report: expected object"]

    missing = sorted(TOP_FIELDS - set(data))
    if missing:
        errors.append(f"report: missing fields {', '.join(missing)}")
    unexpected = _unexpected(data, TOP_FIELDS)
    if unexpected:
        errors.append(f"report: unexpected fields {', '.join(unexpected)}")

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version: unsupported value")
    if not _is_iso_datetime(data.get("generated_at")):
        errors.append("generated_at: expected ISO-8601 date-time")

    names = data.get("skill_names")
    if not isinstance(names, list) or not names or not all(isinstance(value, str) and value for value in names):
        errors.append("skill_names: expected non-empty string array")
    elif len(names) != len(set(names)):
        errors.append("skill_names: duplicate values")

    privacy = data.get("privacy")
    if not isinstance(privacy, dict):
        errors.append("privacy: expected object")
        privacy = {}
    else:
        missing = sorted(PRIVACY_FIELDS - set(privacy))
        if missing:
            errors.append(f"privacy: missing fields {', '.join(missing)}")
        unexpected = _unexpected(privacy, PRIVACY_FIELDS)
        if unexpected:
            errors.append(f"privacy: unexpected fields {', '.join(unexpected)}")
    for field in PRIVACY_FIELDS:
        if field in privacy and not _is_bool(privacy[field]):
            errors.append(f"privacy.{field}: expected boolean")
    raw_text_included = privacy.get("raw_text_included")
    excerpts_labeled = privacy.get("excerpts_redacted_and_truncated")
    if raw_text_included is True and not allow_excerpts:
        errors.append("privacy.raw_text_included: forbidden without --allow-excerpts")
    if excerpts_labeled is True and not allow_excerpts:
        errors.append("privacy.excerpts_redacted_and_truncated: forbidden without --allow-excerpts")
    if _is_bool(raw_text_included) and _is_bool(excerpts_labeled) and raw_text_included != excerpts_labeled:
        errors.append("privacy: raw-text and redacted-excerpt flags must match")
    if privacy.get("identifiers_hashed") is not True:
        errors.append("privacy.identifiers_hashed: must be true")
    if privacy.get("transcripts_treated_as_untrusted") is not True:
        errors.append("privacy.transcripts_treated_as_untrusted: must be true")

    coverage = data.get("runtime_coverage")
    if not isinstance(coverage, dict) or not coverage:
        errors.append("runtime_coverage: expected non-empty object")
        coverage = {}
    for runtime in required_runtimes:
        if runtime not in coverage:
            errors.append(f"runtime_coverage.{runtime}: required runtime missing")
    for runtime, details in coverage.items():
        if runtime not in RUNTIMES:
            errors.append(f"runtime_coverage.{runtime}: unsupported runtime")
            continue
        if not isinstance(details, dict):
            errors.append(f"runtime_coverage.{runtime}: expected object")
            continue
        missing = sorted(COVERAGE_FIELDS - set(details))
        if missing:
            errors.append(f"runtime_coverage.{runtime}: missing fields {', '.join(missing)}")
        unexpected = _unexpected(details, COVERAGE_FIELDS)
        if unexpected:
            errors.append(f"runtime_coverage.{runtime}: unexpected fields {', '.join(unexpected)}")
        for field in COVERAGE_FIELDS:
            if field in details and not _is_nonnegative_int(details[field]):
                errors.append(f"runtime_coverage.{runtime}.{field}: expected non-negative integer")
        if _is_nonnegative_int(details.get("limit_per_runtime")) and details["limit_per_runtime"] < 1:
            errors.append(f"runtime_coverage.{runtime}.limit_per_runtime: expected integer >= 1")

    runs = data.get("runs")
    if not isinstance(runs, list):
        errors.append("runs: expected array")
        runs = []
    seen_ids: set[str] = set()
    outcome_counter: Counter[str] = Counter()
    runtime_counter: Counter[str] = Counter()
    excerpt_present = False
    for index, run in enumerate(runs):
        prefix = f"runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix}: expected object")
            continue
        missing = sorted(RUN_FIELDS - set(run))
        if missing:
            errors.append(f"{prefix}: missing fields {', '.join(missing)}")
        unexpected = _unexpected(run, RUN_FIELDS | EXCERPT_FIELDS)
        if unexpected:
            errors.append(f"{prefix}: unexpected fields {', '.join(unexpected)}")

        for field in ("run_id", "session_digest", "source_digest"):
            if not isinstance(run.get(field), str) or not DIGEST_RE.fullmatch(run[field]):
                errors.append(f"{prefix}.{field}: expected 16 lowercase hex characters")
        request_digest = run.get("request_digest")
        if request_digest is not None and (not isinstance(request_digest, str) or not DIGEST_RE.fullmatch(request_digest)):
            errors.append(f"{prefix}.request_digest: expected null or 16 lowercase hex characters")
        run_id = run.get("run_id")
        if isinstance(run_id, str):
            if run_id in seen_ids:
                errors.append(f"{prefix}.run_id: duplicate")
            seen_ids.add(run_id)

        runtime = run.get("runtime")
        if runtime not in RUNTIMES:
            errors.append(f"{prefix}.runtime: unsupported runtime")
        else:
            runtime_counter[runtime] += 1
            if runtime not in coverage:
                errors.append(f"{prefix}.runtime: missing matching coverage entry")
        origin = run.get("origin")
        if origin is not None and not isinstance(origin, str):
            errors.append(f"{prefix}.origin: expected string or null")
        started = run.get("session_started_at")
        if started is not None and not _is_iso_datetime(started):
            errors.append(f"{prefix}.session_started_at: expected ISO-8601 date-time or null")
        if run.get("invocation_kind") not in INVOCATION_KINDS:
            errors.append(f"{prefix}.invocation_kind: unsupported value")
        for field in COUNTER_FIELDS:
            if not _is_nonnegative_int(run.get(field)):
                errors.append(f"{prefix}.{field}: expected non-negative integer")
        for field in ("aborted", "receipt_present"):
            if not _is_bool(run.get(field)):
                errors.append(f"{prefix}.{field}: expected boolean")
        outcome = run.get("outcome_signal")
        if outcome not in OUTCOMES:
            errors.append(f"{prefix}.outcome_signal: unsupported value")
        else:
            outcome_counter[outcome] += 1

        present = EXCERPT_FIELDS & set(run)
        if present:
            excerpt_present = True
            if not allow_excerpts:
                errors.append(f"{prefix}: excerpt fields forbidden without --allow-excerpts")
            if "request_excerpt" in run and not isinstance(run["request_excerpt"], str):
                errors.append(f"{prefix}.request_excerpt: expected string")
            corrections = run.get("correction_excerpts")
            if "correction_excerpts" in run and (
                not isinstance(corrections, list) or not all(isinstance(value, str) for value in corrections)
            ):
                errors.append(f"{prefix}.correction_excerpts: expected string array")

    if excerpt_present and privacy.get("excerpts_redacted_and_truncated") is not True:
        errors.append("privacy.excerpts_redacted_and_truncated: must be true when excerpt fields exist")
    if excerpt_present and privacy.get("raw_text_included") is not True:
        errors.append("privacy.raw_text_included: must be true when excerpt fields exist")

    runs_found = data.get("runs_found")
    if not _is_nonnegative_int(runs_found):
        errors.append("runs_found: expected non-negative integer")
    elif runs_found != len(runs):
        errors.append("runs_found: does not equal runs array length")

    coverage_total = 0
    for runtime, details in coverage.items():
        if runtime not in RUNTIMES or not isinstance(details, dict):
            continue
        found = details.get("runs_found")
        if _is_nonnegative_int(found):
            coverage_total += found
            if runtime_counter[runtime] != found:
                errors.append(f"runtime_coverage.{runtime}.runs_found: does not equal matching runs")
    if _is_nonnegative_int(runs_found) and coverage_total != runs_found:
        errors.append("runtime_coverage: runs_found total does not equal report runs_found")

    counts = data.get("outcome_counts")
    if not isinstance(counts, dict):
        errors.append("outcome_counts: expected object")
    else:
        unexpected = sorted(set(counts) - set(OUTCOMES))
        if unexpected:
            errors.append(f"outcome_counts: unsupported fields {', '.join(unexpected)}")
        if any(not _is_nonnegative_int(value) for value in counts.values()):
            errors.append("outcome_counts: expected non-negative integer values")
        expected_counts = dict(outcome_counter)
        if counts != expected_counts:
            errors.append("outcome_counts: does not equal outcomes computed from runs")

    return errors


def validate_receipt(text: str) -> list[str]:
    errors: list[str] = []
    legacy_headers = text.count(LEGACY_RECEIPT_HEADER)
    branded_headers = text.count(BRANDED_RECEIPT_HEADER)
    if legacy_headers + branded_headers != 1:
        errors.append("receipt.header: expected exactly one supported Repo-pedant receipt header")
    branded = branded_headers == 1 and legacy_headers == 0
    required_fields = BRANDED_RECEIPT_FIELDS if branded else LEGACY_RECEIPT_FIELDS
    fields: dict[str, list[str]] = {name: [] for name in required_fields}
    pattern = re.compile(r"^- (?P<name>[^:]+):\s*(?P<value>.*)$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match and match.group("name") in fields:
            fields[match.group("name")].append(match.group("value").strip())
    for field, values in fields.items():
        if len(values) != 1:
            errors.append(f"receipt.{field}: expected exactly once")
        elif not values[0]:
            errors.append(f"receipt.{field}: value is empty")
    modes = fields["Mode"]
    if len(modes) == 1 and modes[0] not in RECEIPT_MODES:
        errors.append("receipt.Mode: unsupported value")
    if not branded:
        return errors

    if text.count(BRAND_SLOGAN) != 1:
        errors.append("receipt.brand: expected exactly one canonical slogan")
    schemas = fields["Schema"]
    if len(schemas) == 1 and schemas[0] != BRANDED_RECEIPT_SCHEMA:
        errors.append("receipt.Schema: unsupported value")
    statuses = fields["Status"]
    if len(statuses) == 1 and statuses[0] not in RECEIPT_STATUSES:
        errors.append("receipt.Status: unsupported value")
        return errors
    if len(statuses) != 1:
        return errors

    status = statuses[0]
    mode = modes[0] if len(modes) == 1 else ""
    holds = fields["Holds"][0] if len(fields["Holds"]) == 1 else ""
    changed = fields["Changed"][0] if len(fields["Changed"]) == 1 else ""
    next_action = fields["Next action"][0] if len(fields["Next action"]) == 1 else ""
    has_holds = bool(holds) and holds.casefold() != "none"
    if status == "complete" and has_holds:
        errors.append("receipt.Status: complete requires Holds: none")
    if status == "complete_with_holds" and not has_holds:
        errors.append("receipt.Status: complete_with_holds requires a concrete hold")
    if status == "audit_only" and (mode != "audit" or changed.casefold() != "none"):
        errors.append("receipt.Status: audit_only requires Mode: audit and Changed: none")
    if status == "failed" and next_action.casefold() == "none":
        errors.append("receipt.Status: failed requires a concrete Next action")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="collector JSON report")
    parser.add_argument("--receipt", type=Path, help="optional Markdown response containing a receipt")
    parser.add_argument("--require-runtime", action="append", choices=RUNTIMES, default=[])
    parser.add_argument("--allow-excerpts", action="store_true", help="allow local redacted excerpt fields")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = json.loads(args.report.read_text(encoding="utf-8"))
        receipt_text = args.receipt.read_text(encoding="utf-8") if args.receipt else None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"input: unable to read or parse ({type(exc).__name__})"
        if args.format == "json":
            print(json.dumps({"valid": False, "errors": [message]}, ensure_ascii=False))
        else:
            print(f"INVALID\n- {message}")
        return 2

    errors = validate_report(
        data,
        required_runtimes=args.require_runtime,
        allow_excerpts=args.allow_excerpts,
    )
    if receipt_text is not None:
        errors.extend(validate_receipt(receipt_text))

    if args.format == "json":
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
    else:
        print("VALID")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

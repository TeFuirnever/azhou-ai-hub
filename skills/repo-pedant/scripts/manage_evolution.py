#!/usr/bin/env python3
"""Record bounded repo-pedant signals and validate isolated evolution candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SIGNAL_SCHEMA = "repo-pedant.evolution-signal.v1"
CANDIDATE_SCHEMA = "repo-pedant.evolution-candidate.v1"
EVALUATION_SCHEMA = "repo-pedant.evolution-evaluation.v1"
MECHANISM_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")
SEVERITIES = {"low", "medium", "high", "critical"}
OUTCOMES = {"success", "partial", "failure", "unknown"}
CATEGORIES = {"scope", "authority", "deletion", "stale_fact", "verification", "verbosity", "safety", "authorization", "privacy", "data_loss", "trigger", "inventory"}
SOURCES = {"user_feedback", "receipt", "check", "history", "hook", "synthetic", "manual_review"}
PROVENANCE = {"curated", "learned", "imported", "unknown"}
REQUIRED_CHECKS = {"schema", "privacy", "authorization", "size", "regression"}
FORBIDDEN_KEYS = {"raw_text", "transcript", "command", "tool_input", "tool_output", "secret", "prompt_body"}


class EvolutionError(ValueError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat(timespec="seconds")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvolutionError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def project_identity(project: Path) -> str:
    project = project.expanduser().resolve()
    try:
        process = subprocess.run(
            ["git", "-C", str(project), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        remote = process.stdout.strip() if process.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        remote = ""
    if remote:
        remote = re.sub(r"(?i)(https?://)[^/@]+@", r"\1", remote)
        basis = f"remote:{remote.removesuffix('.git')}"
    else:
        basis = f"path:{project}"
    return digest(basis)[:24]


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_state_root(project: Path, value: Path | None) -> Path:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise EvolutionError("project directory missing")
    candidate = value.expanduser() if value else project / ".repo-pedant" / "evolution"
    if not candidate.is_absolute():
        candidate = project / candidate
    raw = candidate.absolute()
    if raw.is_symlink():
        raise EvolutionError("evolution state root cannot be a symlink")
    candidate = raw.resolve()
    if not inside(candidate, project):
        raise EvolutionError("evolution state must stay inside the project")
    return candidate


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_KEYS or contains_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


def validate_signal(signal: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(signal, dict):
        return ["signal: expected object"]
    if signal.get("schema_version") != SIGNAL_SCHEMA:
        errors.append("schema_version")
    if not isinstance(signal.get("signal_id"), str) or not DIGEST_RE.fullmatch(signal["signal_id"]):
        errors.append("signal_id")
    for field in ("project_id", "session_digest", "evidence_digest"):
        if not isinstance(signal.get(field), str) or not re.fullmatch(r"[a-f0-9]{16,64}", signal[field]):
            errors.append(field)
    if signal.get("severity") not in SEVERITIES:
        errors.append("severity")
    if signal.get("outcome") not in OUTCOMES:
        errors.append("outcome")
    if signal.get("category") not in CATEGORIES:
        errors.append("category")
    if signal.get("source") not in SOURCES:
        errors.append("source")
    if signal.get("provenance") not in PROVENANCE:
        errors.append("provenance")
    if not isinstance(signal.get("mechanism"), str) or not MECHANISM_RE.fullmatch(signal["mechanism"]):
        errors.append("mechanism")
    if not isinstance(signal.get("runtime"), str) or not signal["runtime"].strip():
        errors.append("runtime")
    if signal.get("user_feedback") not in {"accepted", "corrected", "rejected", "none"}:
        errors.append("user_feedback")
    try:
        parse_time(signal.get("observed_at", ""))
    except EvolutionError:
        errors.append("observed_at")
    if contains_forbidden_key(signal):
        errors.append("forbidden_raw_field")
    return errors


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        try:
            import fcntl  # type: ignore

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(paths: Iterable[Path]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    parse_errors = 0
    for path in paths:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            parse_errors += 1
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            if validate_signal(value):
                parse_errors += 1
                continue
            rows.append(value)
    return rows, parse_errors


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def cmd_add_signal(args: argparse.Namespace) -> int:
    try:
        project = args.project.expanduser().resolve()
        state_root = safe_state_root(project, args.state_root)
        observed_at = args.observed_at or iso_now()
        parse_time(observed_at)
        basis = "\0".join((str(project), args.runtime, args.mechanism, args.session_id, args.evidence, observed_at))
        signal = {
            "schema_version": SIGNAL_SCHEMA,
            "signal_id": digest(basis),
            "observed_at": observed_at,
            "project_id": project_identity(project),
            "runtime": args.runtime,
            "session_digest": digest(args.session_id)[:24],
            "source": args.source,
            "provenance": args.provenance,
            "category": args.category,
            "mechanism": args.mechanism,
            "severity": args.severity,
            "outcome": args.outcome,
            "user_feedback": args.user_feedback,
            "evidence_digest": digest(args.evidence),
            "privacy": "digests-only",
            "authorization": "observation-only",
        }
        errors = validate_signal(signal)
        if errors:
            raise EvolutionError(f"invalid signal fields: {', '.join(errors)}")
        append_jsonl(state_root / "signals.jsonl", signal)
    except EvolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(signal, ensure_ascii=False, indent=2))
    return 0


def is_severe(signal: dict[str, Any]) -> bool:
    return signal["category"] in {"safety", "authorization", "privacy", "data_loss"} and signal["severity"] in {"high", "critical"}


def cmd_propose(args: argparse.Namespace) -> int:
    try:
        project = args.project.expanduser().resolve()
        state_root = safe_state_root(project, args.state_root)
        source_paths = [state_root / "signals.jsonl", *[path.expanduser().resolve() for path in args.include_signal_file]]
        signals, parse_errors = read_jsonl(source_paths)
        matching = [
            signal
            for signal in signals
            if signal["mechanism"] == args.mechanism and signal["outcome"] in {"partial", "failure"}
        ]
        sessions = {signal["session_digest"] for signal in matching}
        projects = {signal["project_id"] for signal in matching}
        severe = any(is_severe(signal) for signal in matching)
        if not (severe or len(sessions) >= 2):
            raise EvolutionError("candidate requires two independent ordinary failures or one severe safety failure")
        if args.scope == "global" and len(projects) < 2:
            raise EvolutionError("global candidate requires comparable evidence from at least two projects")
        created_at = iso_now()
        candidate_basis = "\0".join((args.mechanism, args.scope, args.change_summary, args.regression_id, created_at))
        candidate_id = digest(candidate_basis)[:24]
        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "candidate_id": candidate_id,
            "created_at": created_at,
            "status": "proposed",
            "scope": args.scope,
            "mechanism": args.mechanism,
            "change_summary": args.change_summary,
            "regression_id": args.regression_id,
            "signal_ids": sorted(signal["signal_id"] for signal in matching),
            "independent_sessions": len(sessions),
            "projects": len(projects),
            "severe_trigger": severe,
            "parse_errors": parse_errors,
            "origin": args.origin,
            "live_skill_modified": False,
        }
        structure_errors = validate_candidate_structure(candidate)
        if structure_errors:
            raise EvolutionError("; ".join(structure_errors))
        candidate_path = state_root / "candidates" / f"{candidate_id}.json"
        live_skill = (project / "skills" / "repo-pedant").resolve()
        if inside(candidate_path.resolve(), live_skill):
            raise EvolutionError("candidate path overlaps the live skill")
        write_json(candidate_path, candidate)
    except EvolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"candidate": str(candidate_path), **candidate}, ensure_ascii=False, indent=2))
    return 0


def validate_candidate_structure(candidate: Any) -> list[str]:
    if not isinstance(candidate, dict):
        return ["candidate must be an object"]
    errors: list[str] = []
    if candidate.get("schema_version") != CANDIDATE_SCHEMA:
        errors.append("candidate schema invalid")
    if not isinstance(candidate.get("candidate_id"), str) or not re.fullmatch(r"[a-f0-9]{24}", candidate["candidate_id"]):
        errors.append("candidate_id invalid")
    try:
        parse_time(candidate.get("created_at", ""))
    except EvolutionError:
        errors.append("candidate created_at invalid")
    if candidate.get("status") != "proposed":
        errors.append("candidate status invalid")
    if candidate.get("scope") not in {"project", "global"}:
        errors.append("candidate scope invalid")
    if not isinstance(candidate.get("mechanism"), str) or not MECHANISM_RE.fullmatch(candidate["mechanism"]):
        errors.append("candidate mechanism invalid")
    summary = candidate.get("change_summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 240 or "\n" in summary or "://" in summary:
        errors.append("candidate change_summary must be one bounded redacted line")
    if not isinstance(candidate.get("regression_id"), str) or not MECHANISM_RE.fullmatch(candidate["regression_id"]):
        errors.append("candidate regression_id invalid")
    signal_ids = candidate.get("signal_ids")
    if not isinstance(signal_ids, list) or not signal_ids or any(not isinstance(value, str) or not DIGEST_RE.fullmatch(value) for value in signal_ids):
        errors.append("candidate signal_ids invalid")
    if candidate.get("live_skill_modified") is not False:
        errors.append("candidate must not modify live skill")
    sessions = candidate.get("independent_sessions")
    projects = candidate.get("projects")
    severe = candidate.get("severe_trigger")
    if not isinstance(sessions, int) or isinstance(sessions, bool) or sessions < 1:
        errors.append("candidate independent_sessions invalid")
    if not isinstance(projects, int) or isinstance(projects, bool) or projects < 1:
        errors.append("candidate projects invalid")
    if not isinstance(severe, bool):
        errors.append("candidate severe_trigger invalid")
    elif severe is False and isinstance(sessions, int) and sessions < 2:
        errors.append("ordinary candidate lacks two independent failures")
    if candidate.get("scope") == "global" and isinstance(projects, int) and projects < 2:
        errors.append("global candidate lacks two-project corroboration")
    if not isinstance(candidate.get("parse_errors"), int) or isinstance(candidate.get("parse_errors"), bool) or candidate.get("parse_errors", -1) < 0:
        errors.append("candidate parse_errors invalid")
    if candidate.get("origin") not in PROVENANCE:
        errors.append("candidate origin invalid")
    if contains_forbidden_key(candidate):
        errors.append("candidate contains forbidden raw field")
    return errors


def cmd_archive(args: argparse.Namespace) -> int:
    """Archive only evidence already converted into a validated candidate."""
    try:
        project = args.project.expanduser().resolve()
        state_root = safe_state_root(project, args.state_root)
        raw_candidate_path = args.candidate.expanduser().absolute()
        if raw_candidate_path.is_symlink():
            raise EvolutionError("candidate must be a contained non-symlink proposal")
        candidate_path = raw_candidate_path.resolve()
        candidates_root = (state_root / "candidates").resolve()
        if not inside(candidate_path, candidates_root):
            raise EvolutionError("candidate must be a contained non-symlink proposal")
        candidate = load_json(candidate_path)
        structure_errors = validate_candidate_structure(candidate)
        if structure_errors:
            raise EvolutionError("; ".join(structure_errors))

        signals_path = state_root / "signals.jsonl"
        try:
            lines = signals_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise EvolutionError("live signal batch missing") from exc
        selected_ids = set(candidate["signal_ids"])
        archived_lines: list[str] = []
        retained_lines: list[str] = []
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                retained_lines.append(line)
                continue
            if isinstance(value, dict) and value.get("signal_id") in selected_ids and not validate_signal(value):
                archived_lines.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            else:
                retained_lines.append(line)
        if not archived_lines:
            raise EvolutionError("candidate has no validated signals in the live batch")

        archive_path = state_root / "archive" / f"processed-{candidate['candidate_id']}.jsonl"
        if archive_path.exists():
            raise EvolutionError("candidate evidence already archived")
        temporary_archive = archive_path.with_name(f".{archive_path.name}.{os.getpid()}.tmp")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_archive.write_text("\n".join(archived_lines) + "\n", encoding="utf-8")
        os.replace(temporary_archive, archive_path)

        temporary_live = signals_path.with_name(f".{signals_path.name}.{os.getpid()}.tmp")
        temporary_live.write_text(("\n".join(retained_lines) + "\n") if retained_lines else "", encoding="utf-8")
        os.replace(temporary_live, signals_path)
        candidate["archived_signal_count"] = len(archived_lines)
        candidate["evidence_archive"] = str(archive_path.relative_to(state_root))
        write_json(candidate_path, candidate)
    except EvolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"archived": len(archived_lines), "archive": str(archive_path)}, ensure_ascii=False))
    return 0


def preference_summary(votes: list[dict[str, Any]]) -> tuple[int, int, int]:
    return (
        sum(vote.get("preference") == "candidate" for vote in votes),
        sum(vote.get("preference") == "baseline" for vote in votes),
        sum(vote.get("preference") == "tie" for vote in votes),
    )


def validate_promotion(candidate: Any, evaluation: Any) -> list[str]:
    errors = validate_candidate_structure(candidate)
    if not isinstance(candidate, dict):
        return errors
    if not isinstance(evaluation, dict) or evaluation.get("schema_version") != EVALUATION_SCHEMA:
        return errors + ["evaluation schema invalid"]
    if contains_forbidden_key(evaluation):
        errors.append("evaluation contains forbidden raw field")
    if evaluation.get("candidate_id") != candidate.get("candidate_id"):
        errors.append("candidate_id mismatch")
    diff_sha = evaluation.get("diff_sha256")
    if not isinstance(diff_sha, str) or not DIGEST_RE.fullmatch(diff_sha):
        errors.append("diff_sha256 invalid")
    checks = evaluation.get("deterministic_checks")
    if not isinstance(checks, list):
        errors.append("deterministic_checks missing")
    else:
        by_name = {item.get("name"): item for item in checks if isinstance(item, dict)}
        missing = REQUIRED_CHECKS - set(by_name)
        if missing:
            errors.append(f"deterministic_checks missing: {', '.join(sorted(missing))}")
        if any(by_name.get(name, {}).get("status") != "passed" for name in REQUIRED_CHECKS):
            errors.append("deterministic_checks not all passed")
    votes = evaluation.get("paired_votes")
    if not isinstance(votes, list) or len(votes) < 3 or len(votes) % 2 == 0:
        errors.append("paired_votes requires odd N >= 3")
        votes = []
    else:
        judge_ids = [vote.get("judge_id") for vote in votes if isinstance(vote, dict)]
        if len(judge_ids) != len(votes) or len(set(judge_ids)) != len(votes) or any(not value for value in judge_ids):
            errors.append("paired_votes require unique judge_id values")
        orders = {vote.get("order") for vote in votes if isinstance(vote, dict)}
        if not {"baseline_first", "candidate_first"}.issubset(orders):
            errors.append("paired_votes must reverse A/B order")
        if any(vote.get("preference") not in {"candidate", "baseline", "tie"} for vote in votes if isinstance(vote, dict)):
            errors.append("paired_votes contain invalid preference")
        candidate_votes, baseline_votes, _ = preference_summary(votes)
        if candidate_votes <= baseline_votes:
            errors.append("candidate lacks paired majority")
    safety = evaluation.get("safety_review")
    if not isinstance(safety, dict) or safety.get("status") != "passed" or safety.get("regression_found") is not False:
        errors.append("safety review must pass with no regression")
    approval = evaluation.get("human_approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved" or not str(approval.get("reviewer", "")).strip():
        errors.append("exact human approval missing")
    elif approval.get("diff_sha256") != diff_sha:
        errors.append("human approval does not match exact diff")
    return errors


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvolutionError(f"unable to read JSON: {path} ({type(exc).__name__})") from exc


def cmd_gate(args: argparse.Namespace) -> int:
    try:
        candidate = load_json(args.candidate.expanduser().resolve())
        evaluation = load_json(args.evaluation.expanduser().resolve())
        errors = validate_promotion(candidate, evaluation)
    except EvolutionError as exc:
        errors = [str(exc)]
    print(json.dumps({"promotable": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def rate(rows: list[dict[str, Any]]) -> float | None:
    decided = [row for row in rows if row["outcome"] in {"success", "failure", "partial"}]
    if not decided:
        return None
    return sum(row["outcome"] == "success" for row in decided) / len(decided)


def cmd_health(args: argparse.Namespace) -> int:
    try:
        project = args.project.expanduser().resolve()
        state_root = safe_state_root(project, args.state_root)
        archive_paths = sorted((state_root / "archive").glob("*.jsonl")) if (state_root / "archive").is_dir() else []
        rows, parse_errors = read_jsonl([state_root / "signals.jsonl", *archive_paths])
        now = parse_time(args.now) if args.now else now_utc()
        recent = [row for row in rows if parse_time(row["observed_at"]) >= now - timedelta(days=7)]
        monthly = [row for row in rows if parse_time(row["observed_at"]) >= now - timedelta(days=30)]
        rate_7d = rate(recent)
        rate_30d = rate(monthly)
        declining = rate_7d is not None and rate_30d is not None and rate_30d - rate_7d >= args.warn_threshold
        result = {
            "schema_version": "repo-pedant.evolution-health.v1",
            "signals": len(rows),
            "parse_errors": parse_errors,
            "success_rate_7d": rate_7d,
            "success_rate_30d": rate_30d,
            "declining": declining,
            "action": "investigate" if declining else "none",
            "promotion_authority": False,
        }
    except EvolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    signal = subparsers.add_parser("add-signal", help="append one digests-only project-scoped signal")
    signal.add_argument("--project", required=True, type=Path)
    signal.add_argument("--state-root", type=Path)
    signal.add_argument("--runtime", required=True)
    signal.add_argument("--mechanism", required=True)
    signal.add_argument("--category", choices=sorted(CATEGORIES), required=True)
    signal.add_argument("--severity", choices=sorted(SEVERITIES), required=True)
    signal.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    signal.add_argument("--session-id", required=True)
    signal.add_argument("--evidence", required=True, help="local evidence identifier; stored as SHA-256 only")
    signal.add_argument("--source", choices=sorted(SOURCES), required=True)
    signal.add_argument("--provenance", choices=sorted(PROVENANCE), default="learned")
    signal.add_argument("--user-feedback", choices=("accepted", "corrected", "rejected", "none"), default="none")
    signal.add_argument("--observed-at")
    signal.set_defaults(func=cmd_add_signal)

    propose = subparsers.add_parser("propose", help="create an isolated candidate from corroborated failures")
    propose.add_argument("--project", required=True, type=Path)
    propose.add_argument("--state-root", type=Path)
    propose.add_argument("--include-signal-file", action="append", default=[], type=Path)
    propose.add_argument("--mechanism", required=True)
    propose.add_argument("--scope", choices=("project", "global"), default="project")
    propose.add_argument("--change-summary", required=True)
    propose.add_argument("--regression-id", required=True)
    propose.add_argument("--origin", choices=sorted(PROVENANCE), default="learned")
    propose.set_defaults(func=cmd_propose)

    archive = subparsers.add_parser("archive", help="archive a live signal batch only after validated candidate creation")
    archive.add_argument("--project", required=True, type=Path)
    archive.add_argument("--state-root", type=Path)
    archive.add_argument("--candidate", required=True, type=Path)
    archive.set_defaults(func=cmd_archive)

    gate = subparsers.add_parser("gate", help="validate deterministic, paired, safety, and human promotion evidence")
    gate.add_argument("--candidate", required=True, type=Path)
    gate.add_argument("--evaluation", required=True, type=Path)
    gate.set_defaults(func=cmd_gate)

    health = subparsers.add_parser("health", help="compute investigation-only 7d/30d health trends")
    health.add_argument("--project", required=True, type=Path)
    health.add_argument("--state-root", type=Path)
    health.add_argument("--now")
    health.add_argument("--warn-threshold", type=float, default=0.1)
    health.set_defaults(func=cmd_health)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if getattr(args, "warn_threshold", 0.1) < 0:
        print("warn threshold must be non-negative", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Collect privacy-preserving process and outcome signals for repository-cleanup skill runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RUNTIMES = ("codex", "claude", "zcode")
SYNTHETIC_PREFIXES = (
    "<recommended_plugins>",
    "<environment_context>",
    "<codex_internal_context",
    "<openviking-context",
    "# AGENTS.md instructions",
    "The following is the Codex agent history",
)
INJECTED_BODY_MARKERS = (
    "Base directory for this skill:",
    "<skill_content>",
    "# 洁癖 — Knowledge Base Neat-Freak",
    "# Repo Pedant\n",
)
CORRECTION_RE = re.compile(
    r"(?:不对|不是这个|不要|别这样|停止|先别|撤销|恢复|越界|误删|错了|漏了|wrong|stop|undo|revert|missed)",
    re.IGNORECASE,
)
DESTRUCTIVE_RE = re.compile(
    r"(?:\brm\s+-[a-zA-Z]*r|\bgit\s+(?:clean|reset\s+--hard)|\bunlink\b|rmtree|delete_project)",
    re.IGNORECASE,
)
MUTATION_RE = re.compile(
    r"(?:apply_patch|\bEdit\b|\bWrite\b|\bgit\s+mv\b|\bmv\s+|\brm\s+|unlink|rmtree)",
    re.IGNORECASE,
)
FAILED_OUTPUT_RE = re.compile(
    r'(?:(?:"exit_code"|"exitCode")\s*:\s*[1-9]\d*|"isError"\s*:\s*true|process exited with code [1-9]\d*)',
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+")
ABS_PATH_RE = re.compile(r"/(?:Users|home|private|tmp)/\S+")
SECRET_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,}|(?:token|api[_-]?key)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
RECEIPT_MARKERS = (
    "## 🦊 阿舟 · Repo-pedant receipt",
    "## Repo-pedant receipt",
    "## Repo Pedant receipt",
    "## Tidy receipt",
    "## 同步完成",
)
CLEANUP_REQUEST_RE = re.compile(
    r"(?:收尾|整理(?:一下|文档|仓库)?|同步(?:一下|文档)?|更新记忆|阶段(?:做完|完成)|交接|"
    r"wrap\s*up|tidy|sync(?:\s+up)?|clean\s+up\s+docs?|handoff)",
    re.IGNORECASE,
)


@dataclass
class Item:
    kind: str
    role: str = ""
    text: str = ""
    name: str = ""
    arguments: str = ""
    failed: bool = False


@dataclass
class ParsedSession:
    runtime: str
    session_id: str
    started_at: str | None
    origin: str | None
    items: list[Item]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") in {"text", "input_text", "output_text"}:
            value = block.get("text")
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def redact_excerpt(text: str, limit: int = 240) -> str:
    redacted = SECRET_RE.sub("<secret>", text)
    redacted = URL_RE.sub("<url>", redacted)
    redacted = ABS_PATH_RE.sub("<path>", redacted)
    redacted = " ".join(redacted.split())
    return redacted[:limit]


def parse_codex_file(path: Path) -> ParsedSession:
    session_id = path.stem
    started_at: str | None = None
    items: list[Item] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "session_meta":
                payload = record.get("payload", {})
                if isinstance(payload, dict):
                    session_id = str(payload.get("id", session_id))
                    timestamp = payload.get("timestamp")
                    if isinstance(timestamp, str):
                        started_at = timestamp
                continue
            if record.get("type") == "event_msg":
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                payload_type = payload.get("type")
                if payload_type == "user_message" and isinstance(payload.get("message"), str):
                    items.append(Item(kind="message", role="user", text=payload["message"]))
                elif payload_type == "agent_message" and isinstance(payload.get("message"), str):
                    items.append(Item(kind="message", role="assistant", text=payload["message"]))
                elif payload_type == "task_complete" and isinstance(payload.get("last_agent_message"), str):
                    items.append(Item(kind="message", role="assistant", text=payload["last_agent_message"]))
                continue
            if record.get("type") != "response_item":
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            payload_type = payload.get("type")
            if payload_type == "message":
                items.append(
                    Item(
                        kind="message",
                        role=str(payload.get("role", "")),
                        text=content_text(payload.get("content")),
                    )
                )
            elif payload_type in {"function_call", "custom_tool_call"}:
                arguments = payload.get("arguments", payload.get("input", ""))
                items.append(
                    Item(
                        kind="tool_call",
                        name=str(payload.get("name", payload_type)),
                        arguments=json_text(arguments),
                    )
                )
            elif payload_type in {"function_call_output", "custom_tool_call_output"}:
                output = payload.get("output", payload.get("content", ""))
                text = json_text(output)
                items.append(
                    Item(
                        kind="tool_output",
                        text=text,
                        failed=bool(FAILED_OUTPUT_RE.search(text)),
                    )
                )
    return ParsedSession("codex", session_id, started_at, None, items)


def parse_claude_file(path: Path) -> ParsedSession:
    session_id = path.stem
    started_at: str | None = None
    items: list[Item] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            record_type = record.get("type")
            if record_type not in {"user", "assistant"}:
                continue
            session_id = str(record.get("sessionId", session_id))
            timestamp = record.get("timestamp")
            if started_at is None and isinstance(timestamp, str):
                started_at = timestamp
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            role = str(message.get("role", record_type))
            content = message.get("content")
            if isinstance(content, str):
                items.append(Item(kind="message", role=role, text=content))
                continue
            if not isinstance(content, list):
                continue
            text = content_text(content)
            if text:
                items.append(Item(kind="message", role=role, text=text))
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "tool_use":
                    items.append(
                        Item(
                            kind="tool_call",
                            name=str(block.get("name", "tool_use")),
                            arguments=json_text(block.get("input", "")),
                        )
                    )
                elif block_type == "tool_result":
                    result = json_text(block.get("content", ""))
                    items.append(
                        Item(
                            kind="tool_output",
                            text=result,
                            failed=bool(block.get("is_error")) or bool(FAILED_OUTPUT_RE.search(result)),
                        )
                    )
    return ParsedSession("claude", session_id, started_at, None, items)


def epoch_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    seconds = value / 1000 if value > 10_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def parse_zcode_file(path: Path) -> ParsedSession:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError("zcode session must be a JSON object")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    session_id = str(meta.get("taskId") or meta.get("traceId") or path.stem)
    started_at = epoch_to_iso(meta.get("createdAt"))
    origin_value = meta.get("migrationSource")
    origin = str(origin_value) if origin_value else None
    items: list[Item] = []
    for message in data.get("messages", []):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", ""))
        text = content_text(message.get("content")) if isinstance(message.get("content"), list) else str(message.get("content", ""))
        if role and text:
            items.append(Item(kind="message", role=role, text=text))
    return ParsedSession("zcode", session_id, started_at, origin, items)


def parse_session(runtime: str, path: Path) -> ParsedSession:
    if runtime == "codex":
        return parse_codex_file(path)
    if runtime == "claude":
        return parse_claude_file(path)
    if runtime == "zcode":
        return parse_zcode_file(path)
    raise ValueError(f"unsupported runtime: {runtime}")


def contains_injected_body(text: str) -> bool:
    return any(marker in text for marker in INJECTED_BODY_MARKERS)


def is_synthetic_user(text: str) -> bool:
    stripped = text.lstrip()
    return (
        not stripped
        or stripped.startswith(SYNTHETIC_PREFIXES)
        or stripped.startswith("<skill>")
        or stripped.startswith("<turn_aborted>")
        or contains_injected_body(stripped)
    )


def is_control_abort(text: str) -> bool:
    return text.lstrip().startswith("<turn_aborted>")


def marker_pattern(name: str) -> re.Pattern[str]:
    escaped = re.escape(name.lower())
    return re.compile(
        rf"(?:"
        rf"<command-(?:name|message)>\s*/?{escaped}\s*</command-(?:name|message)>|"
        rf"<name>\s*{escaped}\s*</name>|"
        rf"\[\s*\${escaped}\s*\]\([^)]*\)|"
        rf"(?<![\w-])\${escaped}(?![\w-])|"
        rf"(?<![\w-])/{escaped}(?![\w-])"
        rf")",
        re.IGNORECASE,
    )


def user_skill_marker(text: str, names: set[str]) -> bool:
    stripped = text.lstrip()
    if (
        not stripped
        or stripped.startswith(SYNTHETIC_PREFIXES)
        or contains_injected_body(stripped)
    ):
        return False
    return any(marker_pattern(name).search(text) for name in names)


def skill_tool_marker(item: Item, names: set[str]) -> bool:
    if item.kind != "tool_call" or item.name.lower().replace("_", "-") not in {"skill", "use-skill", "read-skill"}:
        return False
    candidates: list[str] = []
    try:
        value = json.loads(item.arguments)
    except json.JSONDecodeError:
        value = item.arguments
    if isinstance(value, dict):
        for key in ("skill", "name", "command"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                candidates.append(candidate)
    elif isinstance(value, str):
        candidates.append(value)
    normalized = {candidate.strip().lower().lstrip("/$") for candidate in candidates}
    return bool(normalized & {name.lower() for name in names})


def skill_file_read_marker(item: Item, names: set[str]) -> bool:
    if item.kind != "tool_call":
        return False
    lowered = item.arguments.lower()
    return any(
        re.search(rf"(?:^|[/\\]){re.escape(name.lower())}[/\\]skill\.md(?![\w./-])", lowered)
        for name in names
    )


def is_invocation_marker(item: Item, names: set[str]) -> bool:
    return (
        item.kind == "message"
        and item.role == "user"
        and user_skill_marker(item.text, names)
    ) or skill_tool_marker(item, names)


def preceding_user_text(items: list[Item], index: int) -> str:
    for item in reversed(items[:index]):
        if item.kind == "message" and item.role == "user" and not is_synthetic_user(item.text):
            return item.text
    return ""


def marker_positions(items: list[Item], names: set[str]) -> list[int]:
    positions: list[int] = []
    for index, item in enumerate(items):
        explicit_marker = is_invocation_marker(item, names)
        inferred_read = skill_file_read_marker(item, names) and bool(
            CLEANUP_REQUEST_RE.search(preceding_user_text(items, index))
        )
        if not explicit_marker and not inferred_read:
            continue
        if positions:
            previous = positions[-1]
            distinct_request = any(
                candidate.kind == "message"
                and candidate.role == "user"
                and not is_synthetic_user(candidate.text)
                and not user_skill_marker(candidate.text, names)
                for candidate in items[previous + 1 : index]
            )
            if not distinct_request:
                continue
        positions.append(index)
    return positions


def receipt_request_positions(items: list[Item]) -> list[int]:
    """Infer legacy runs from stable assistant receipts when invocation metadata is absent."""
    positions: list[int] = []
    for receipt_index, item in enumerate(items):
        if (
            item.kind != "message"
            or item.role != "assistant"
            or not any(marker in item.text for marker in RECEIPT_MARKERS)
        ):
            continue
        for request_index in range(receipt_index - 1, -1, -1):
            candidate = items[request_index]
            if (
                candidate.kind == "message"
                and candidate.role == "user"
                and not is_synthetic_user(candidate.text)
            ):
                if not positions or positions[-1] != request_index:
                    positions.append(request_index)
                break
    return positions


def strip_marker(text: str, names: set[str]) -> str:
    value = text
    for name in names:
        value = marker_pattern(name).sub("", value)
    return value.strip(" \t\n&#x20;")


def preceding_request(items: list[Item], marker: int, names: set[str]) -> str:
    current = items[marker]
    if current.kind == "message" and not current.text.lstrip().startswith("<skill>"):
        remainder = strip_marker(current.text, names)
        if remainder:
            return remainder
    for item in reversed(items[:marker]):
        if item.kind == "message" and item.role == "user" and not is_synthetic_user(item.text):
            if not user_skill_marker(item.text, names):
                return item.text
    return ""


def conservative_outcome(*, aborted: bool, corrections: int, failed_outputs: int, receipt: bool) -> str:
    if aborted:
        return "aborted"
    if corrections:
        return "user_corrected"
    if failed_outputs:
        return "tool_failure_signal"
    if receipt:
        return "receipt_emitted"
    return "insufficient_evidence"


def analyze_window(
    *,
    path: Path,
    session: ParsedSession,
    names: set[str],
    start: int,
    end: int,
    include_excerpts: bool,
    invocation_kind: str | None = None,
) -> dict[str, Any]:
    request = preceding_request(session.items, start, names)
    assistant_messages = 0
    tool_calls = 0
    mutation_calls = 0
    destructive_calls = 0
    failed_tool_outputs = 0
    corrections: list[str] = []
    aborted = False
    receipt_present = False
    seen_assistant = False

    for item in session.items[start + 1 : end]:
        if item.kind == "message" and item.role == "assistant":
            assistant_messages += 1
            seen_assistant = True
            receipt_present = receipt_present or any(marker in item.text for marker in RECEIPT_MARKERS)
            continue
        if item.kind == "message" and item.role == "user":
            if is_control_abort(item.text):
                aborted = True
                break
            if is_synthetic_user(item.text) or user_skill_marker(item.text, names):
                continue
            if seen_assistant and CORRECTION_RE.search(item.text):
                corrections.append(item.text)
                if len(corrections) >= 3:
                    break
                continue
            if seen_assistant:
                break
        if item.kind == "tool_call":
            tool_calls += 1
            combined = f"{item.name}\n{item.arguments}"
            mutation_calls += int(bool(MUTATION_RE.search(combined)))
            destructive_calls += int(bool(DESTRUCTIVE_RE.search(combined)))
        elif item.kind == "tool_output":
            failed_tool_outputs += int(item.failed or bool(FAILED_OUTPUT_RE.search(item.text)))

    if invocation_kind is None:
        if skill_tool_marker(session.items[start], names):
            invocation_kind = "skill_tool"
        elif skill_file_read_marker(session.items[start], names):
            invocation_kind = "skill_file_read"
        else:
            invocation_kind = "explicit_user"
    run: dict[str, Any] = {
        "run_id": digest(f"{session.runtime}:{session.session_id}:{start}"),
        "runtime": session.runtime,
        "origin": session.origin,
        "session_digest": digest(session.session_id),
        "source_digest": digest(str(path)),
        "session_started_at": session.started_at,
        "request_digest": digest(request) if request else None,
        "invocation_kind": invocation_kind,
        "assistant_messages": assistant_messages,
        "tool_calls_heuristic": tool_calls,
        "mutation_calls_heuristic": mutation_calls,
        "destructive_calls_heuristic": destructive_calls,
        "failed_tool_outputs_heuristic": failed_tool_outputs,
        "user_corrections_heuristic": len(corrections),
        "aborted": aborted,
        "receipt_present": receipt_present,
        "outcome_signal": conservative_outcome(
            aborted=aborted,
            corrections=len(corrections),
            failed_outputs=failed_tool_outputs,
            receipt=receipt_present,
        ),
    }
    if include_excerpts:
        run["request_excerpt"] = redact_excerpt(request) if request else None
        run["correction_excerpts"] = [redact_excerpt(value) for value in corrections]
    return run


def session_files(runtime: str, root: Path) -> Iterable[Path]:
    candidates: list[Path] = []
    if runtime == "codex":
        for child in (root / "sessions", root / "archived_sessions"):
            if child.exists():
                candidates.extend(child.rglob("*.jsonl"))
    elif runtime == "claude":
        projects = root / "projects"
        if projects.exists():
            candidates.extend(projects.rglob("*.jsonl"))
    elif runtime == "zcode":
        sessions = root / "v2" / "sessions"
        if sessions.exists():
            candidates.extend(sessions.rglob("*.json"))
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def collect(
    roots: dict[str, Path],
    runtimes: Iterable[str],
    names: set[str],
    limit: int,
    include_excerpts: bool,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    coverage: dict[str, dict[str, int]] = {}
    for runtime in runtimes:
        runtime_runs: list[dict[str, Any]] = []
        scanned = 0
        parse_errors = 0
        for path in session_files(runtime, roots[runtime]):
            scanned += 1
            try:
                session = parse_session(runtime, path)
            except (OSError, ValueError, json.JSONDecodeError):
                parse_errors += 1
                continue
            positions = marker_positions(session.items, names)
            invocation_kind = None
            if not positions:
                positions = receipt_request_positions(session.items)
                invocation_kind = "receipt_inferred"
            for offset, start in enumerate(positions):
                end = positions[offset + 1] if offset + 1 < len(positions) else len(session.items)
                runtime_runs.append(
                    analyze_window(
                        path=path,
                        session=session,
                        names=names,
                        start=start,
                        end=end,
                        include_excerpts=include_excerpts,
                        invocation_kind=invocation_kind,
                    )
                )
                if len(runtime_runs) >= limit:
                    break
            if len(runtime_runs) >= limit:
                break
        runs.extend(runtime_runs)
        coverage[runtime] = {
            "files_scanned": scanned,
            "parse_errors": parse_errors,
            "runs_found": len(runtime_runs),
            "limit_per_runtime": limit,
        }

    outcome_counts: dict[str, int] = {}
    for run in runs:
        signal = run["outcome_signal"]
        outcome_counts[signal] = outcome_counts.get(signal, 0) + 1
    return {
        "schema_version": "repo-pedant.history.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skill_names": sorted(names),
        "privacy": {
            "raw_text_included": include_excerpts,
            "excerpts_redacted_and_truncated": include_excerpts,
            "identifiers_hashed": True,
            "transcripts_treated_as_untrusted": True,
        },
        "runtime_coverage": coverage,
        "runs_found": len(runs),
        "outcome_counts": outcome_counts,
        "runs": runs,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Repo-pedant history triage",
        "",
        f"- Skills: {', '.join(report['skill_names'])}",
        f"- Runs found: {report['runs_found']}",
        f"- Raw text included: {str(report['privacy']['raw_text_included']).lower()}",
        "- Every process and outcome signal is heuristic until raw-session verification.",
        "",
        "## Coverage",
        "",
        "| Runtime | Files scanned | Parse errors | Runs | Limit/runtime |",
        "|---|---:|---:|---:|---:|",
    ]
    for runtime, values in report["runtime_coverage"].items():
        lines.append(
            f"| {runtime} | {values['files_scanned']} | {values['parse_errors']} | "
            f"{values['runs_found']} | {values['limit_per_runtime']} |"
        )
    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| Run | Runtime | Invocation | Tools* | Mutations* | Destructive* | Failed* | Corrections* | Outcome* | Receipt |",
            "|---|---|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for run in report["runs"]:
        lines.append(
            "| {run_id} | {runtime} | {invocation_kind} | {tool_calls_heuristic} | "
            "{mutation_calls_heuristic} | {destructive_calls_heuristic} | "
            "{failed_tool_outputs_heuristic} | {user_corrections_heuristic} | "
            "{outcome_signal} | {receipt_present} |".format(**run)
        )
        if "request_excerpt" in run:
            lines.append(f"\n- `{run['run_id']}` request: {run['request_excerpt'] or '(none)'}")
            for excerpt in run.get("correction_excerpts", []):
                lines.append(f"  - correction: {excerpt}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="append", choices=(*RUNTIMES, "all"), default=[])
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--claude-home", type=Path, default=Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")))
    parser.add_argument("--zcode-home", type=Path, default=Path(os.environ.get("ZCODE_HOME", Path.home() / ".zcode")))
    parser.add_argument("--skill", default="repo-pedant")
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--limit", type=int, default=20, help="maximum matching runs per runtime")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--include-excerpts", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    requested = args.runtime or ["all"]
    args.runtimes = RUNTIMES if "all" in requested else tuple(dict.fromkeys(requested))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    names = {args.skill.lower(), "neat-freak", *(value.lower() for value in args.alias)}
    roots = {
        "codex": args.codex_home,
        "claude": args.claude_home,
        "zcode": args.zcode_home,
    }
    report = collect(roots, args.runtimes, names, args.limit, args.include_excerpts)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

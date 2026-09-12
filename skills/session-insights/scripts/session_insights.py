#!/usr/bin/env python3
"""session-insights: deterministic aggregate/report pipeline over local agent session stores.

Read-only observer: the CLI only reads harness session stores, never writes
into them, and never contacts the network. The Claude Code adapter parses
``<store-root>/projects/<encoded-cwd>/*.jsonl``; the Codex and zcode adapters
fail closed with an ``unsupported`` hold until their transcript formats are
verified. All metrics are UTC; the scan window and recency cap anchor to the
newest observed session timestamp in the store, never to wall-clock now, so a
static store always yields the same aggregate. Excerpts-off aggregate runs
reuse a disposable per-file metadata cache (mtime+size keyed, no transcript
text) under the invoking project's gitignored runtime-state namespace.

Exit codes: 0 success, 1 gate/validation failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DETECT_SCHEMA = "session-insights.detect.v1"
DISCOVER_SCHEMA = "session-insights.discover.v1"
METADATA_SCHEMA = "session-insights.metadata.v1"
AGGREGATE_SCHEMA = "session-insights.aggregate.v1"
RECEIPT_SCHEMA = "session-insights.report.v1"
CACHE_SCHEMA = "session-insights.metadata-cache.v1"

DEFAULT_DAYS = 30
DEFAULT_MAX_SESSIONS = 200
FIRST_PROMPT_LIMIT = 200
INTERRUPTION_MARKER = "[Request interrupted by user]"

HARNESSES = ("claude-code", "codex", "zcode")
SUPPORTED_HARNESSES = ("claude-code",)
UNSUPPORTED_HOLD = {name: f"{name} unsupported" for name in HARNESSES if name not in SUPPORTED_HARNESSES}

DEFAULT_HOME_DIRS = {
    "claude-code": ".claude",
    "codex": ".codex",
    "zcode": ".zcode",
}

OUTPUT_NAMESPACE = Path(".azhou") / "session-insights"
CACHE_FILENAME = "metadata-cache.json"

REVIEW_FOOTER = (
    "Review before sharing: this report aggregates local session metadata; when "
    "excerpts are enabled it may contain real prompt fragments — verify the "
    "redaction before sending it anywhere."
)

SECRET_SHAPES = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{10,}"),
    re.compile(r"-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}"),
)


class UsageFailure(Exception):
    """Gate/validation failure; reported on stderr with exit code 1."""


def emit_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def redact_text(text: str) -> str:
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    for pattern in SECRET_SHAPES:
        text = pattern.sub("[redacted-secret]", text)
    return text


def encode_project_path(project: str) -> str:
    """Best-effort Claude Code project-directory encoding (path separators and
    other non-alphanumerics become dashes)."""
    return re.sub(r"[^A-Za-z0-9]", "-", project)


def project_label(encoded: str) -> str:
    """Redact an encoded project directory name before it enters any artifact.

    The encoded name reversibly embeds the absolute working-directory path,
    which is user data. The home-directory portion collapses to ``~``; any
    other location keeps only its last two segments. A mangle mismatch shows
    less information, never more. Labels stay ASCII."""
    prefixes = set()
    home = Path.home()
    for candidate in (home, *_safe_resolved(home)):
        text = str(candidate)
        if text and text != candidate.anchor:
            prefixes.add(encode_project_path(text))
    for prefix in sorted(prefixes, key=len, reverse=True):
        if prefix and encoded.startswith(prefix):
            remainder = encoded[len(prefix):].lstrip("-")
            return "~/" + remainder if remainder else "~"
    segments = [segment for segment in encoded.split("-") if segment]
    if not segments:
        return "project"
    return ".../" + "-".join(segments[-2:])


def _safe_resolved(path: Path) -> tuple[Path, ...]:
    try:
        return (path.resolve(),)
    except OSError:
        return ()


def store_root(harness: str, override: str | None) -> Path:
    if override is not None:
        return Path(override)
    return Path.home() / DEFAULT_HOME_DIRS[harness]


def selected_harnesses(name: str) -> tuple[str, ...]:
    return HARNESSES if name == "all" else (name,)


def harness_store_present(harness: str, root: Path) -> bool:
    markers = {
        "claude-code": root / "projects",
        "codex": root / "sessions",
        "zcode": root / "v2" / "sessions",
    }
    return markers[harness].is_dir()


# --- metadata cache ------------------------------------------------------
#
# The cache makes the second aggregate run fast. It lives in the invoking
# project's gitignored runtime-state namespace (never inside the read-only
# session store), keys entries by per-file mtime+size, and stores only
# metadata and aggregate-grade fields: the first-prompt text (transcript
# text) is replaced by its SHA-256, which still pins repeated-prompt
# detection. Deleting the cache rebuilds it without changing any report.


def empty_metadata_cache() -> dict[str, Any]:
    return {"schema": CACHE_SCHEMA, "stores": {}}


def load_metadata_cache(base: Path) -> dict[str, Any]:
    try:
        payload = json.loads((base / OUTPUT_NAMESPACE / CACHE_FILENAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return empty_metadata_cache()
    if not isinstance(payload, dict) or payload.get("schema") != CACHE_SCHEMA:
        return empty_metadata_cache()
    if not isinstance(payload.get("stores"), dict):
        return empty_metadata_cache()
    return payload


def save_metadata_cache(base: Path, cache: dict[str, Any]) -> None:
    """Best-effort atomic publish; the cache is disposable, so write failure is silent."""
    target = base / OUTPUT_NAMESPACE / CACHE_FILENAME
    temporary = target.with_name(target.name + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        temporary.unlink(missing_ok=True)


def cache_store_key(harness: str, root: Path) -> str:
    try:
        resolved = str(root.resolve())
    except OSError:
        resolved = str(root)
    return hashlib.sha256(f"{harness}\n{resolved}".encode("utf-8")).hexdigest()


def cache_store_section(cache: dict[str, Any], harness: str, root: Path) -> dict[str, Any]:
    key = cache_store_key(harness, root)
    section = cache["stores"].get(key)
    if not isinstance(section, dict) or not isinstance(section.get("files"), dict):
        section = {"files": {}}
        cache["stores"][key] = section
    return section


def cached_metadata(entry: Any, mtime_ns: int, size: int) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("mtime_ns") != mtime_ns or entry.get("size") != size:
        return None
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return dict(metadata)


def cache_entry(metadata: dict[str, Any], mtime_ns: int, size: int) -> dict[str, Any]:
    stored = {key: value for key, value in metadata.items() if key not in ("project", "first_prompt")}
    return {"mtime_ns": mtime_ns, "size": size, "metadata": stored}


# --- Claude Code adapter -------------------------------------------------


def claude_session_files(root: Path, project: str | None) -> list[tuple[Path, str]]:
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        raise UsageFailure(f"claude-code store has no projects directory: {projects_dir.name} missing")
    if project is not None:
        encoded = encode_project_path(project)
        candidate = projects_dir / encoded
        if not candidate.is_dir():
            raise UsageFailure(f"project not found in claude-code store: {encoded}")
        dirs = [candidate]
    else:
        dirs = sorted(item for item in projects_dir.iterdir() if item.is_dir())
    files: list[tuple[Path, str]] = []
    for directory in dirs:
        for path in sorted(directory.glob("*.jsonl")):
            if path.is_file():
                files.append((path, directory.name))
    return files


def user_text(message: Any) -> str | None:
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content if content.strip() else None
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
        ]
        joined = "\n".join(part for part in parts if part.strip())
        return joined if joined.strip() else None
    return None


def parse_session_file(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "session_id": path.stem,
        "start": None,
        "end": None,
        "turns": 0,
        "user_messages": 0,
        "assistant_messages": 0,
        "tool_calls": {},
        "interruptions": 0,
        "errors": 0,
        "first_prompt": None,
        "message_timestamps": [],
        "message_lines": 0,
        "malformed_lines": 0,
        "skipped_lines": 0,
    }
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                parsed["malformed_lines"] += 1
                continue
            if not isinstance(record, dict):
                parsed["skipped_lines"] += 1
                continue
            if record.get("isSidechain") or record.get("isMeta"):
                parsed["skipped_lines"] += 1
                continue
            record_type = record.get("type")
            if record_type not in ("user", "assistant"):
                parsed["skipped_lines"] += 1
                continue
            parsed["message_lines"] += 1
            moment = parse_timestamp(record.get("timestamp"))
            if moment is not None:
                parsed["message_timestamps"].append(iso(moment))
                first_seen = moment if first_seen is None else min(first_seen, moment)
                last_seen = moment if last_seen is None else max(last_seen, moment)
            session_id = record.get("sessionId")
            if isinstance(session_id, str) and session_id and parsed["session_id"] == path.stem:
                parsed["session_id"] = session_id
            message = record.get("message")
            if record_type == "user":
                text = user_text(message)
                if text is None:
                    continue
                parsed["user_messages"] += 1
                if text.strip() == INTERRUPTION_MARKER:
                    parsed["interruptions"] += 1
                    continue
                parsed["turns"] += 1
                if parsed["first_prompt"] is None:
                    parsed["first_prompt"] = text.strip()[:FIRST_PROMPT_LIMIT]
            else:
                parsed["assistant_messages"] += 1
                if record.get("isApiErrorMessage") or record.get("error"):
                    parsed["errors"] += 1
                if isinstance(message, dict) and isinstance(message.get("content"), list):
                    for item in message["content"]:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            name = item.get("name")
                            if isinstance(name, str) and name:
                                parsed["tool_calls"][name] = parsed["tool_calls"].get(name, 0) + 1
    parsed["start"] = iso(first_seen) if first_seen else None
    parsed["end"] = iso(last_seen) if last_seen else None
    first_prompt = parsed["first_prompt"]
    parsed["first_prompt_sha256"] = (
        hashlib.sha256(first_prompt.encode("utf-8")).hexdigest() if first_prompt else None
    )
    return parsed


def scan_claude_store(
    root: Path,
    project: str | None,
    cache_store: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse every session file once; window/cap trimming happens afterwards so
    the anchor (newest observed timestamp) always reflects the whole store.

    When ``cache_store`` is given, files whose mtime+size still match their
    cache entry reuse the cached metadata instead of re-parsing, and the
    section is rewritten to exactly the files seen in this scan."""
    files = claude_session_files(root, project)
    cached_files = cache_store.get("files", {}) if cache_store is not None else {}
    sessions: list[dict[str, Any]] = []
    skipped_subagent = 0
    malformed_lines = 0
    digest = hashlib.sha256()
    tuples: list[str] = []
    used_entries: dict[str, Any] = {}
    for path, project_name in files:
        stat = path.stat()
        relative = path.relative_to(root).as_posix()
        path_hash = hashlib.sha256(relative.encode("utf-8")).hexdigest()
        tuples.append(f"{path_hash}:{stat.st_mtime_ns}:{stat.st_size}")
        parsed = cached_metadata(cached_files.get(path_hash), stat.st_mtime_ns, stat.st_size)
        if parsed is None:
            parsed = parse_session_file(path)
        parsed["project"] = project_label(project_name)
        if cache_store is not None:
            used_entries[path_hash] = cache_entry(parsed, stat.st_mtime_ns, stat.st_size)
        malformed_lines += parsed["malformed_lines"]
        if parsed["message_lines"] == 0:
            skipped_subagent += 1
            continue
        sessions.append(parsed)
    if cache_store is not None:
        cache_store["files"] = used_entries
    for entry in sorted(tuples):
        digest.update(entry.encode("utf-8"))
        digest.update(b"\n")
    scan = {
        "files_scanned": len(files),
        "malformed_lines": malformed_lines,
        "skipped_subagent_sessions": skipped_subagent,
        "file_count": len(files),
        "composite_sha256": digest.hexdigest(),
    }
    return sessions, scan


def session_recency(session: dict[str, Any]) -> str:
    return session.get("end") or session.get("start") or ""


def trim_sessions(
    sessions: list[dict[str, Any]], days: int, max_sessions: int
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    if not sessions:
        return [], None, None
    newest_raw = max(session_recency(session) for session in sessions)
    newest = parse_timestamp(newest_raw)
    if newest is None:
        raise UsageFailure("no parseable timestamps in store")
    window_start = newest - timedelta(days=days)
    in_window = [
        session
        for session in sessions
        if (moment := parse_timestamp(session_recency(session))) is not None and moment >= window_start
    ]
    in_window.sort(key=session_recency, reverse=True)
    return in_window[:max_sessions], iso(newest), iso(window_start)


def aggregate_sessions(
    sessions: list[dict[str, Any]],
    scan: dict[str, Any],
    days: int,
    max_sessions: int,
    include_excerpts: bool,
) -> dict[str, Any]:
    included, newest, window_start = trim_sessions(sessions, days, max_sessions)
    hour_histogram = [0] * 24
    active_days: set[str] = set()
    project_distribution: dict[str, int] = {}
    tool_calls: dict[str, int] = {}
    turns = 0
    user_messages = 0
    assistant_messages = 0
    interruptions = 0
    errors = 0
    prompt_counts: dict[str, int] = {}
    for session in included:
        project_distribution[session["project"]] = project_distribution.get(session["project"], 0) + 1
        turns += session["turns"]
        user_messages += session["user_messages"]
        assistant_messages += session["assistant_messages"]
        interruptions += session["interruptions"]
        errors += session["errors"]
        for name, count in session["tool_calls"].items():
            tool_calls[name] = tool_calls.get(name, 0) + count
        for stamp in session["message_timestamps"]:
            moment = parse_timestamp(stamp)
            if moment is None:
                continue
            hour_histogram[moment.hour] += 1
            active_days.add(moment.date().isoformat())
        prompt_hash = session.get("first_prompt_sha256")
        if prompt_hash:
            prompt_counts[prompt_hash] = prompt_counts.get(prompt_hash, 0) + 1
    repeated = sum(count - 1 for count in prompt_counts.values() if count > 1)
    section: dict[str, Any] = {
        "status": "ok",
        "newest_session_at": newest,
        "window_start": window_start,
        "session_count": len(included),
        "skipped_subagent_sessions": scan["skipped_subagent_sessions"],
        "files_scanned": scan["files_scanned"],
        "malformed_lines": scan["malformed_lines"],
        "active_days": len(active_days),
        "hour_histogram_utc": hour_histogram,
        "project_distribution": dict(
            sorted(project_distribution.items(), key=lambda item: (-item[1], item[0]))
        ),
        "tool_calls": dict(sorted(tool_calls.items(), key=lambda item: (-item[1], item[0]))),
        "turns": turns,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "interruptions": interruptions,
        "interruption_rate": round(interruptions / turns, 4) if turns else 0.0,
        "error_count": errors,
        "repeated_first_prompt_count": repeated,
        "inputs": {
            "file_count": scan["file_count"],
            "composite_sha256": scan["composite_sha256"],
        },
    }
    if include_excerpts:
        section["excerpts"] = [
            {
                "session_id": session["session_id"],
                "project": session["project"],
                "first_prompt": redact_text(session["first_prompt"]),
            }
            for session in included
            if session.get("first_prompt")
        ]
    return section


def build_aggregate(args: argparse.Namespace) -> dict[str, Any]:
    harnesses: dict[str, Any] = {}
    holds: list[str] = []
    # Excerpt runs bypass the cache: they need the first-prompt text, which
    # the cache deliberately never stores.
    cache = load_metadata_cache(Path.cwd()) if not args.include_excerpts else None
    for harness in selected_harnesses(args.harness):
        root = store_root(harness, args.store_root)
        if harness not in SUPPORTED_HARNESSES:
            hold = UNSUPPORTED_HOLD[harness]
            harnesses[harness] = {"status": "unsupported", "hold": hold}
            holds.append(hold)
            continue
        if not harness_store_present(harness, root):
            harnesses[harness] = {"status": "missing"}
            continue
        cache_store = cache_store_section(cache, harness, root) if cache is not None else None
        sessions, scan = scan_claude_store(root, args.project, cache_store)
        harnesses[harness] = aggregate_sessions(
            sessions, scan, args.days, args.max_sessions, args.include_excerpts
        )
    if cache is not None and cache["stores"]:
        save_metadata_cache(Path.cwd(), cache)
    aggregate: dict[str, Any] = {
        "schema": AGGREGATE_SCHEMA,
        "window_days": args.days,
        "max_sessions": args.max_sessions,
        "harnesses": harnesses,
        "holds": holds,
    }
    if args.project:
        aggregate["project"] = project_label(encode_project_path(args.project))
    return aggregate


# --- subcommands ---------------------------------------------------------


def cmd_detect(args: argparse.Namespace) -> int:
    harnesses: dict[str, Any] = {}
    for harness in selected_harnesses(args.harness):
        root = store_root(harness, args.store_root)
        present = harness_store_present(harness, root)
        if harness not in SUPPORTED_HARNESSES:
            harnesses[harness] = {
                "status": "unsupported",
                "store_present": present,
                "hold": UNSUPPORTED_HOLD[harness],
            }
            continue
        entry: dict[str, Any] = {"status": "available" if present else "missing"}
        if present:
            entry["session_files"] = len(claude_session_files(root, args.project))
        harnesses[harness] = entry
    emit_json({"schema": DETECT_SCHEMA, "harnesses": harnesses})
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    harness = args.harness
    if harness == "all":
        raise UsageFailure("discover requires one harness: pass --harness")
    if harness not in SUPPORTED_HARNESSES:
        emit_json(
            {
                "schema": DISCOVER_SCHEMA,
                "harness": harness,
                "status": "unsupported",
                "hold": UNSUPPORTED_HOLD[harness],
            }
        )
        return 0
    root = store_root(harness, args.store_root)
    if not harness_store_present(harness, root):
        emit_json({"schema": DISCOVER_SCHEMA, "harness": harness, "status": "missing", "sessions": []})
        return 0
    sessions, scan = scan_claude_store(root, args.project)
    rows = [
        {
            "session_id": session["session_id"],
            "project": session["project"],
            "start": session["start"],
            "end": session["end"],
        }
        for session in sorted(sessions, key=session_recency, reverse=True)
    ]
    emit_json(
        {
            "schema": DISCOVER_SCHEMA,
            "harness": harness,
            "status": "ok",
            "sessions": rows,
            "skipped_subagent_sessions": scan["skipped_subagent_sessions"],
            "files_scanned": scan["files_scanned"],
        }
    )
    return 0


def cmd_metadata(args: argparse.Namespace) -> int:
    harness = args.harness
    if harness == "all":
        raise UsageFailure("metadata requires one harness: pass --harness")
    if harness not in SUPPORTED_HARNESSES:
        emit_json(
            {
                "schema": METADATA_SCHEMA,
                "harness": harness,
                "status": "unsupported",
                "hold": UNSUPPORTED_HOLD[harness],
            }
        )
        return 0
    root = store_root(harness, args.store_root)
    if not harness_store_present(harness, root):
        emit_json({"schema": METADATA_SCHEMA, "harness": harness, "status": "missing", "sessions": []})
        return 0
    sessions, scan = scan_claude_store(root, args.project)
    emit_json(
        {
            "schema": METADATA_SCHEMA,
            "harness": harness,
            "status": "ok",
            "sessions": sessions,
            "skipped_subagent_sessions": scan["skipped_subagent_sessions"],
            "files_scanned": scan["files_scanned"],
            "malformed_lines": scan["malformed_lines"],
        }
    )
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    aggregate = build_aggregate(args)
    rendered = json.dumps(aggregate, ensure_ascii=False, indent=2)
    if args.out is not None:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


# --- report --------------------------------------------------------------


def read_aggregate(path: str | None) -> dict[str, Any]:
    try:
        if path is None or path == "-":
            payload = json.load(sys.stdin)
        else:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UsageFailure(f"cannot read aggregate JSON ({type(exc).__name__})") from exc
    if not isinstance(payload, dict) or payload.get("schema") != AGGREGATE_SCHEMA:
        raise UsageFailure(f"aggregate schema must be {AGGREGATE_SCHEMA}")
    if not isinstance(payload.get("harnesses"), dict):
        raise UsageFailure("aggregate harnesses must be an object")
    return payload


def bar(count: int, width: int = 20, peak: int = 1) -> str:
    if count <= 0 or peak <= 0:
        return ""
    return "█" * max(1, round(width * count / peak))


def render_ok_section(lines: list[str], harness: str, section: dict[str, Any], include_excerpts: bool) -> None:
    lines.append(f"## 📊 概览（{harness}）")
    lines.append("")
    lines.append(f"- 会话数: {section['session_count']}")
    lines.append(f"- 活跃天数（UTC）: {section['active_days']}")
    lines.append(f"- 用户轮次: {section['turns']}")
    lines.append(f"- 用户消息 / 助手消息: {section['user_messages']} / {section['assistant_messages']}")
    lines.append(f"- 扫描文件: {section['files_scanned']}（malformed 行 {section['malformed_lines']}）")
    lines.append(f"- 跳过的 subagent 会话: {section['skipped_subagent_sessions']}")
    lines.append(f"- 最新会话: {section['newest_session_at']}")
    lines.append(f"- 窗口起点: {section['window_start']}")
    lines.append("")

    histogram = section["hour_histogram_utc"]
    lines.append("## 🕒 时段分布（UTC）")
    lines.append("")
    peak = max(histogram) if histogram else 0
    for hour, count in enumerate(histogram):
        if count:
            lines.append(f"- {hour:02d}:00 {bar(count, peak=peak)} {count}")
    if not any(histogram):
        lines.append("- (no message timestamps)")
    lines.append("")

    lines.append("## 🗂️ 项目分布")
    lines.append("")
    for project, count in section["project_distribution"].items():
        lines.append(f"- `{project}`: {count} 个会话")
    if not section["project_distribution"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## 🔧 工具调用排行")
    lines.append("")
    for rank, (name, count) in enumerate(section["tool_calls"].items(), 1):
        lines.append(f"{rank}. `{name}` — {count}")
    if not section["tool_calls"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## 🧯 摩擦信号")
    lines.append("")
    lines.append(
        f"- 中断: {section['interruptions']}（interruption_rate {section['interruption_rate']}）"
    )
    lines.append(f"- API 错误: {section['error_count']}")
    lines.append(f"- 重复首条提示: {section['repeated_first_prompt_count']}")
    lines.append("")

    if include_excerpts:
        excerpts = section.get("excerpts")
        if excerpts is None:
            raise UsageFailure("aggregate was built without --include-excerpts; rebuild it first")
        lines.append("## 📎 首条提示摘录（已脱敏）")
        lines.append("")
        for excerpt in excerpts:
            lines.append(f"- `{excerpt['project']}` / {excerpt['session_id']}: {excerpt['first_prompt']}")
        if not excerpts:
            lines.append("- (none)")
        lines.append("")


def learning_signal(aggregate: dict[str, Any]) -> str:
    for section in aggregate["harnesses"].values():
        if section.get("status") != "ok":
            continue
        if section.get("repeated_first_prompt_count", 0) > 0:
            return "repeated_first_prompts observed"
        if section.get("interruption_rate", 0.0) >= 0.2:
            return "elevated interruption rate"
    return "none"


def report_date(aggregate: dict[str, Any]) -> str:
    newest = [
        section["newest_session_at"]
        for section in aggregate["harnesses"].values()
        if section.get("status") == "ok" and section.get("newest_session_at")
    ]
    if not newest:
        return "empty"
    moment = parse_timestamp(max(newest))
    return moment.date().isoformat() if moment else "empty"


def cmd_report(args: argparse.Namespace) -> int:
    aggregate = read_aggregate(args.aggregate)
    holds = [str(hold) for hold in aggregate.get("holds", [])]
    lines: list[str] = [
        "# 🦊 阿舟 · Session Insights 报告",
        "",
        "> 先有数字，再有故事。每个数字都来自 `session-insights.aggregate.v1`，报告不重算任何指标。",
        "",
        f"- window: 最近 {aggregate['window_days']} 天，锚定 store 内最新会话时间（非墙钟）",
        f"- session cap: {aggregate['max_sessions']}（最近优先）",
        "",
    ]
    for harness, section in aggregate["harnesses"].items():
        status = section.get("status")
        if status == "ok":
            render_ok_section(lines, harness, section, args.include_excerpts)
        elif status == "missing":
            lines.append(f"## {harness}")
            lines.append("")
            lines.append("- store missing; no metrics.")
            lines.append("")
    lines.append("## 🔒 Holds")
    lines.append("")
    for hold in holds:
        lines.append(f"- {hold}")
    if not holds:
        lines.append("- none")
    lines.append("")
    lines.append(f"> {REVIEW_FOOTER}")
    lines.append("")

    inputs = [
        {
            "harness": harness,
            "file_count": section["inputs"]["file_count"],
            "composite_sha256": section["inputs"]["composite_sha256"],
        }
        for harness, section in aggregate["harnesses"].items()
        if section.get("status") == "ok"
    ]
    body = "\n".join(lines)
    artifact_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if args.out is not None:
        out = Path(args.out)
    else:
        out = Path.cwd() / OUTPUT_NAMESPACE / f"report-{report_date(aggregate)}.md"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "pass",
        "inputs": inputs,
        "artifacts": [
            {
                "path": out.name,
                "sha256": artifact_digest,
                "bytes": len(body.encode("utf-8")),
            }
        ],
        "verification": "rendered from session-insights.aggregate.v1 input; no metric recomputed",
        "holds": holds,
        "next_action": (
            "verify codex/zcode transcript formats before claiming cross-harness coverage"
            if holds
            else "review before sharing"
        ),
        "learning_signal": learning_signal(aggregate),
    }
    document = body + "\n## 🧾 Receipt\n\n```json\n" + json.dumps(
        receipt, ensure_ascii=False, indent=2
    ) + "\n```\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    emit_json(receipt)
    return 0


# --- argument parsing ----------------------------------------------------


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--harness",
        choices=("all", *HARNESSES),
        default="all",
        help="harness to inspect (default: all)",
    )
    parser.add_argument(
        "--store-root",
        default=None,
        help="redirect the harness session store root (default: the harness home directory)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="narrow the scan to one project path (encoded to the store directory name)",
    )


def add_window(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="window in days (default: 30)")
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=DEFAULT_MAX_SESSIONS,
        help="recency cap, most recent first (default: 200)",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="report which harness stores are present")
    add_common(detect)
    detect.set_defaults(func=cmd_detect)

    discover = subparsers.add_parser("discover", help="list sessions without parsing metrics")
    add_common(discover)
    discover.set_defaults(func=cmd_discover)

    metadata = subparsers.add_parser("metadata", help="parse per-session metadata as JSON")
    add_common(metadata)
    metadata.set_defaults(func=cmd_metadata)

    aggregate = subparsers.add_parser("aggregate", help="write the aggregate JSON (single source of truth)")
    add_common(aggregate)
    add_window(aggregate)
    aggregate.add_argument("--out", default=None, help="write the aggregate JSON here instead of stdout")
    aggregate.add_argument(
        "--include-excerpts",
        action="store_true",
        help="store redacted first-prompt excerpts in the aggregate (default: off)",
    )
    aggregate.set_defaults(func=cmd_aggregate)

    report = subparsers.add_parser("report", help="render a Markdown report from an aggregate JSON")
    report.add_argument("--aggregate", default=None, help="aggregate JSON path (default: stdin)")
    report.add_argument(
        "--out",
        default=None,
        help="report path (default: <cwd>/.azhou/session-insights/report-<date>.md)",
    )
    report.add_argument(
        "--include-excerpts",
        action="store_true",
        help="render the redacted excerpts stored in the aggregate (default: off)",
    )
    report.set_defaults(func=cmd_report)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for name in ("days", "max_sessions"):
        value = getattr(args, name, None)
        if value is not None and value < 1:
            print(f"ERROR: --{name.replace('_', '-')} must be >= 1", file=sys.stderr)
            return 2
    try:
        return args.func(args)
    except UsageFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

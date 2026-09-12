#!/usr/bin/env python3
"""Benchmark integrity check for the session-insights aggregate/report pipeline.

Fixtures prove wiring only: synthetic Claude Code/Codex/zcode stores are built
at check time inside a temporary directory (nothing secret-shaped is checked
in), the CLI runs as a subprocess against them, and golden aggregates pin the
metric semantics. They are never evidence about model behavior.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "skills" / "session-insights" / "scripts" / "session_insights.py"
MANIFEST = Path(__file__).resolve().parent / "manifest.json"

S1 = "11111111-1111-1111-1111-111111111111"
S2 = "22222222-2222-2222-2222-222222222222"
S3 = "33333333-3333-3333-3333-333333333333"
S4 = "44444444-4444-4444-4444-444444444444"
S5 = "55555555-5555-5555-5555-555555555555"
S6 = "66666666-6666-6666-6666-666666666666"
ALPHA = "-Users-test-dev-alpha"
BETA = "-Users-test-dev-beta"

# Secret-shaped strings are assembled at check time so no credential shape is
# ever checked into the repository; the store only exists in a temp dir.
SEED_SK = "sk-" + "FAKE" * 12
SEED_GHP = "ghp" + "_" + "0123456789abcdef" * 3
SEED_AKIA = "AKIA" + "0" * 16
SEED_AIZA = "AIza" + "Ab1" * 12 + "Ab1"
SEED_PEM = "-----BEGIN " + "PRIVATE KEY-----"
SEEDED_SECRETS = (SEED_SK, SEED_GHP, SEED_AKIA, SEED_AIZA, SEED_PEM)

FIRST_PROMPT_SHARED = "帮我修复登录 bug"
EXCERPT_SENTINEL = "换个思路，先写最小复现"


def line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False)


def session_lines(session_id: str, records: list[dict]) -> str:
    for record in records:
        record.setdefault("sessionId", session_id)
    return "\n".join(line(record) for record in records) + "\n"


def build_store(root: Path) -> None:
    """Build the synthetic multi-harness store declared in manifest.json."""
    alpha = root / "projects" / ALPHA
    beta = root / "projects" / BETA
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)

    home = str(Path.home())
    long_prompt = (
        f"{SEED_PEM}\n请检查 {home}/project/config 里的密钥 {SEED_SK}、{SEED_GHP}、{SEED_AKIA}、{SEED_AIZA}\n"
        + "长尾说明" * 60
    )

    s1 = session_lines(
        S1,
        [
            {"type": "summary", "summary": "login fix"},
            {
                "type": "user",
                "timestamp": "2026-09-08T10:00:00Z",
                "message": {"role": "user", "content": FIRST_PROMPT_SHARED},
            },
            {
                "type": "assistant",
                "timestamp": "2026-09-08T10:00:05Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "看一下"},
                        {"type": "tool_use", "name": "Read", "input": {}},
                        {"type": "tool_use", "name": "Bash", "input": {}},
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-09-08T10:00:30Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "file body"}],
                },
            },
            {
                "type": "user",
                "isMeta": True,
                "timestamp": "2026-09-08T10:00:40Z",
                "message": {"role": "user", "content": "<command-message>/clear</command-message>"},
            },
            {
                "type": "assistant",
                "isApiErrorMessage": True,
                "timestamp": "2026-09-08T10:01:00Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "API Error: overloaded"}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-09-08T10:02:00Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "name": "Read", "input": {}}],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-09-08T10:03:00Z",
                "message": {"role": "user", "content": "再加一个回归测试"},
            },
        ],
    )
    s1 += "{this line is not json\n"
    (alpha / f"{S1}.jsonl").write_text(s1, encoding="utf-8")

    (alpha / f"{S2}.jsonl").write_text(
        session_lines(
            S2,
            [
                {
                    "type": "user",
                    "timestamp": "2026-09-09T09:00:00Z",
                    "message": {"role": "user", "content": "[Request interrupted by user]"},
                },
                {
                    "type": "user",
                    "timestamp": "2026-09-09T09:01:00Z",
                    "message": {"role": "user", "content": EXCERPT_SENTINEL},
                },
                {
                    "type": "assistant",
                    "error": "rate_limit",
                    "timestamp": "2026-09-09T09:02:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Error"}],
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-09-09T09:03:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": "Bash", "input": {}}],
                    },
                },
                {
                    "type": "user",
                    "timestamp": "2026-09-09T09:04:00Z",
                    "message": {"role": "user", "content": "[Request interrupted by user]"},
                },
            ],
        ),
        encoding="utf-8",
    )

    (alpha / f"{S3}.jsonl").write_text(
        session_lines(
            S3,
            [
                {
                    "type": "user",
                    "isSidechain": True,
                    "timestamp": "2026-09-09T08:00:00Z",
                    "message": {"role": "user", "content": "subagent task"},
                },
                {
                    "type": "assistant",
                    "isSidechain": True,
                    "timestamp": "2026-09-09T08:01:00Z",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
                },
            ],
        ),
        encoding="utf-8",
    )

    (alpha / f"{S4}.jsonl").write_text(
        session_lines(
            S4,
            [
                {
                    "type": "user",
                    "timestamp": "2026-09-09T18:00:00Z",
                    "message": {"role": "user", "content": FIRST_PROMPT_SHARED},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-09-09T18:05:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Read", "input": {}},
                            {"type": "tool_use", "name": "Grep", "input": {}},
                        ],
                    },
                },
            ],
        ),
        encoding="utf-8",
    )

    (beta / f"{S5}.jsonl").write_text(
        session_lines(
            S5,
            [
                {
                    "type": "user",
                    "timestamp": "2026-08-01T12:00:00Z",
                    "message": {"role": "user", "content": "八月的旧会话"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-08-01T12:01:00Z",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "好"}]},
                },
            ],
        ),
        encoding="utf-8",
    )

    (beta / f"{S6}.jsonl").write_text(
        session_lines(
            S6,
            [
                {
                    "type": "user",
                    "timestamp": "2026-09-07T22:30:00Z",
                    "message": {"role": "user", "content": long_prompt},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-09-07T22:31:00Z",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "收到"}]},
                },
            ],
        ),
        encoding="utf-8",
    )

    codex_dir = root / "sessions" / "2026" / "09" / "01"
    codex_dir.mkdir(parents=True)
    (codex_dir / "rollout-2026-09-01T00-00-00-aaaaaaaa.jsonl").write_text(
        line({"type": "turn_context", "timestamp": "2026-09-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    zcode_dir = root / "v2" / "sessions" / "deadbeefworkspace"
    zcode_dir.mkdir(parents=True)
    (zcode_dir / "claude-import-0123456789abcdef01234567.json").write_text(
        json.dumps({"meta": {"status": "done"}, "messages": []}, ensure_ascii=False),
        encoding="utf-8",
    )


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def cli_json(*args: str) -> dict:
    completed = run_cli(*args)
    if completed.returncode != 0:
        raise AssertionError(f"CLI exit {completed.returncode}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


GOLDEN_AGGREGATE: dict = {
    "status": "ok",
    "newest_session_at": "2026-09-09T18:05:00+00:00",
    "window_start": "2026-08-10T18:05:00+00:00",
    "session_count": 4,
    "skipped_subagent_sessions": 1,
    "files_scanned": 6,
    "malformed_lines": 1,
    "active_days": 3,
    "hour_histogram_utc": [
        0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 6, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0,
    ],
    "project_distribution": {
        ".../dev-alpha": 3,
        ".../dev-beta": 1,
    },
    "tool_calls": {"Read": 3, "Bash": 2, "Grep": 1},
    "turns": 5,
    "user_messages": 7,
    "assistant_messages": 7,
    "interruptions": 2,
    "interruption_rate": 0.4,
    "error_count": 2,
    "repeated_first_prompt_count": 1,
    "inputs": {"file_count": 6},
}
GOLDEN_DAYS60_SPOT = {"session_count": 5, "active_days": 4}
GOLDEN_CAP2_SPOT = {"session_count": 2}


def check_manifest(errors: list[str]) -> None:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"manifest: unreadable ({type(exc).__name__})")
        return
    if manifest.get("schema_version") != 1:
        errors.append("manifest: schema_version must be 1")
    if manifest.get("skill") != "session-insights":
        errors.append("manifest: skill must be session-insights")
    fixtures = manifest.get("fixtures", {})
    sessions = fixtures.get("claude_code_sessions", [])
    if len(sessions) != 6:
        errors.append("manifest: fixtures.claude_code_sessions must declare 6 sessions")
    for name in (S1, S2, S3, S4, S5, S6):
        if not any(name in entry.get("file", "") for entry in sessions):
            errors.append(f"manifest: fixture session not declared: {name}")
    for key in ("codex", "zcode"):
        if not fixtures.get(key):
            errors.append(f"manifest: fixtures.{key} must be declared")
    if not manifest.get("goldens"):
        errors.append("manifest: goldens inventory missing")


def cmd_check(_: argparse.Namespace) -> int:
    errors: list[str] = []
    check_manifest(errors)
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "store"
        build_store(store)

        aggregate = cli_json(
            "aggregate", "--harness", "all", "--store-root", str(store)
        )
        claude = aggregate["harnesses"]["claude-code"]
        digest_value = claude.get("inputs", {}).pop("composite_sha256", None)
        if not (isinstance(digest_value, str) and len(digest_value) == 64):
            errors.append("inputs.composite_sha256 missing or malformed")
        if claude != GOLDEN_AGGREGATE:
            errors.append(
                "golden aggregate drift:\n"
                + json.dumps({"expected": GOLDEN_AGGREGATE, "actual": claude}, ensure_ascii=False, indent=2)
            )
        for harness in ("codex", "zcode"):
            section = aggregate["harnesses"][harness]
            if section != {"status": "unsupported", "hold": f"{harness} unsupported"}:
                errors.append(f"fail-closed section drift for {harness}: {section}")
        if sorted(aggregate["holds"]) != ["codex unsupported", "zcode unsupported"]:
            errors.append(f"holds drift: {aggregate['holds']}")

        days60 = cli_json(
            "aggregate", "--harness", "claude-code", "--store-root", str(store),
            "--days", "60",
        )["harnesses"]["claude-code"]
        for key, expected in GOLDEN_DAYS60_SPOT.items():
            if days60.get(key) != expected:
                errors.append(f"--days 60 spot check failed: {key}={days60.get(key)} != {expected}")

        capped = cli_json(
            "aggregate", "--harness", "claude-code", "--store-root", str(store),
            "--max-sessions", "2",
        )["harnesses"]["claude-code"]
        for key, expected in GOLDEN_CAP2_SPOT.items():
            if capped.get(key) != expected:
                errors.append(f"--max-sessions 2 spot check failed: {key}={capped.get(key)} != {expected}")

        digest_first = digest_value
        digest_second = cli_json(
            "aggregate", "--harness", "claude-code", "--store-root", str(store)
        )["harnesses"]["claude-code"]["inputs"]["composite_sha256"]
        if digest_first != digest_second:
            errors.append("composite digest not stable across two runs on untouched files")

        touched = store / "projects" / ALPHA / f"{S1}.jsonl"
        with touched.open("a", encoding="utf-8") as handle:
            handle.write(line({"type": "summary", "summary": "appended noise"}) + "\n")
        os.utime(touched, None)
        digest_third = cli_json(
            "aggregate", "--harness", "claude-code", "--store-root", str(store)
        )["harnesses"]["claude-code"]["inputs"]["composite_sha256"]
        if digest_third == digest_first:
            errors.append("composite digest did not change after a fixture file content change")

        # --- incremental metadata cache (#167) ----------------------------
        cache_cwd = Path(directory) / "cache-cwd"
        cache_cwd.mkdir()
        cache_path = cache_cwd / ".azhou" / "session-insights" / "metadata-cache.json"

        def cached_aggregate(*extra: str) -> tuple[str, dict]:
            completed = subprocess.run(
                [
                    sys.executable, str(CLI), "aggregate",
                    "--harness", "claude-code", "--store-root", str(store), *extra,
                ],
                cwd=cache_cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise AssertionError(f"cached aggregate exit {completed.returncode}: {completed.stderr.strip()}")
            return completed.stdout, json.loads(completed.stdout)

        cold_out, cold = cached_aggregate()
        cold_section = cold["harnesses"]["claude-code"]
        if not cache_path.is_file():
            errors.append("cache: excerpts-off aggregate did not write the metadata cache")
        else:
            blob = cache_path.read_text(encoding="utf-8")
            try:
                cached_schema = json.loads(blob).get("schema")
            except ValueError:
                cached_schema = None
            if cached_schema != "session-insights.metadata-cache.v1":
                errors.append(f"cache: schema drift: {cached_schema}")
            if '"first_prompt"' in blob:
                errors.append("cache: stores the raw first-prompt text key")
            for needle in (FIRST_PROMPT_SHARED, EXCERPT_SENTINEL, *SEEDED_SECRETS, ALPHA, BETA):
                if needle in blob:
                    errors.append("cache: contains transcript text or store-identifying names")
                    break
            home_path = str(Path.home())
            if home_path != "/" and home_path in blob:
                errors.append("cache: contains the absolute home path")

        warm_out, _warm = cached_aggregate()
        if warm_out != cold_out:
            errors.append("cache: warm-cache output differs from the cold run")
        cache_path.unlink(missing_ok=True)
        rebuilt_out, _rebuilt = cached_aggregate()
        if rebuilt_out != cold_out:
            errors.append("cache: deleted-cache output differs from the cold run")
        cache_path.write_text("{corrupt", encoding="utf-8")
        corrupt_out, _corrupt = cached_aggregate()
        if corrupt_out != cold_out:
            errors.append("cache: a corrupt cache file changed the aggregate output")

        s2 = store / "projects" / ALPHA / f"{S2}.jsonl"
        with s2.open("a", encoding="utf-8") as handle:
            handle.write(
                line(
                    {
                        "type": "user",
                        "timestamp": "2026-09-09T09:05:00Z",
                        "message": {"role": "user", "content": "cache invalidation probe"},
                    }
                )
                + "\n"
            )
        _out, changed = cached_aggregate()
        if changed["harnesses"]["claude-code"]["turns"] != cold_section["turns"] + 1:
            errors.append("cache: a changed session file was not re-scanned")

        s7_id = "77777777-7777-7777-7777-777777777777"
        (store / "projects" / BETA / f"{s7_id}.jsonl").write_text(
            session_lines(
                s7_id,
                [
                    {
                        "type": "user",
                        "timestamp": "2026-09-08T12:00:00Z",
                        "message": {"role": "user", "content": "added session probe"},
                    }
                ],
            ),
            encoding="utf-8",
        )
        _out, added = cached_aggregate()
        if added["harnesses"]["claude-code"]["session_count"] != cold_section["session_count"] + 1:
            errors.append("cache: an added session file was not picked up")

        (store / "projects" / ALPHA / f"{S4}.jsonl").unlink()
        _out, removed = cached_aggregate()
        if removed["harnesses"]["claude-code"]["session_count"] != cold_section["session_count"]:
            errors.append("cache: a removed session file still affects the aggregate")

        excerpt_cwd = Path(directory) / "excerpt-cwd"
        excerpt_cwd.mkdir()
        excerpt_run = subprocess.run(
            [
                sys.executable, str(CLI), "aggregate",
                "--harness", "claude-code", "--store-root", str(store), "--include-excerpts",
            ],
            cwd=excerpt_cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if excerpt_run.returncode != 0:
            errors.append(f"cache: excerpts aggregate failed: {excerpt_run.stderr.strip()}")
        elif (excerpt_cwd / ".azhou" / "session-insights" / "metadata-cache.json").exists():
            errors.append("cache: an excerpts-on run wrote the metadata cache")
        else:
            excerpts = json.loads(excerpt_run.stdout)["harnesses"]["claude-code"].get("excerpts", [])
            if not any(FIRST_PROMPT_SHARED in entry.get("first_prompt", "") for entry in excerpts):
                errors.append("cache: excerpts-on run lost the first-prompt text")

        out_dir = Path(directory) / "out"
        plain_aggregate = out_dir / "aggregate.json"
        completed = run_cli(
            "aggregate", "--harness", "all", "--store-root", str(store),
            "--out", str(plain_aggregate),
        )
        if completed.returncode != 0:
            errors.append(f"aggregate --out failed: {completed.stderr.strip()}")
        plain_report = out_dir / "report-plain.md"
        receipt = cli_json(
            "report", "--aggregate", str(plain_aggregate), "--out", str(plain_report)
        )
        if receipt.get("schema") != "session-insights.report.v1":
            errors.append(f"receipt schema drift: {receipt.get('schema')}")
        text = plain_report.read_text(encoding="utf-8")
        home = str(Path.home())
        if home != "/" and home in text:
            errors.append("privacy: plain report contains the absolute home path")
        aggregate_text = json.dumps(aggregate, ensure_ascii=False)
        for surface, surface_text in (("aggregate", aggregate_text), ("plain report", text)):
            for encoded in (ALPHA, BETA):
                if encoded in surface_text:
                    errors.append(f"privacy: {surface} contains an encoded project directory name")
        for secret in SEEDED_SECRETS:
            if secret in text:
                errors.append("privacy: plain report contains a seeded secret-shaped string")
        if EXCERPT_SENTINEL in text or FIRST_PROMPT_SHARED in text:
            errors.append("privacy: excerpts-off report contains transcript text")
        for hold in ("codex unsupported", "zcode unsupported"):
            if hold not in text:
                errors.append(f"report missing hold line: {hold}")

        rich_aggregate = out_dir / "aggregate-excerpts.json"
        completed = run_cli(
            "aggregate", "--harness", "all", "--store-root", str(store),
            "--include-excerpts", "--out", str(rich_aggregate),
        )
        if completed.returncode != 0:
            errors.append(f"aggregate --include-excerpts failed: {completed.stderr.strip()}")
        rich_report = out_dir / "report-excerpts.md"
        cli_json(
            "report", "--aggregate", str(rich_aggregate),
            "--out", str(rich_report), "--include-excerpts",
        )
        rich_text = rich_report.read_text(encoding="utf-8")
        if FIRST_PROMPT_SHARED not in rich_text:
            errors.append("excerpts-on report lost the shared first prompt")
        if "[redacted-secret]" not in rich_text:
            errors.append("excerpts-on report shows no redaction marker")
        if home != "/" and home in rich_text:
            errors.append("privacy: excerpts-on report contains the absolute home path")
        if "~" not in rich_text:
            errors.append("excerpts-on report shows no home-path redaction")
        for secret in SEEDED_SECRETS:
            if secret in rich_text:
                errors.append("privacy: excerpts-on report contains a seeded secret-shaped string")
        if "Review before sharing" not in rich_text:
            errors.append("report missing the fixed review-before-sharing footer")
        for encoded in (ALPHA, BETA):
            if encoded in rich_text:
                errors.append("privacy: excerpts-on report contains an encoded project directory name")

        codex_only = cli_json("aggregate", "--harness", "codex", "--store-root", str(store))
        codex_section = codex_only["harnesses"]["codex"]
        numeric_keys = {"session_count", "active_days", "tool_calls", "turns"} & set(codex_section)
        if numeric_keys:
            errors.append(f"codex fail-closed section carries speculative metrics: {sorted(numeric_keys)}")

    verdict = {"valid": not errors, "errors": errors}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate manifest, fixtures, goldens, and negative controls")
    check.set_defaults(func=cmd_check)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Explicit host adapters for the neutral LLM Wiki core."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Sequence

import llm_wiki


TRIGGER_PATTERN = re.compile(
    r"\bwiki(?:\s+(?:this|add|lint|query))?\b",
    re.IGNORECASE,
)
INFORMATIONAL_PATTERNS = (
    re.compile(r"\b(?:what(?:'s|\s+is)|what\s+are|how\s+(?:to|do\s+i)\s+use|explain|explanation|tell\s+me\s+about|describe)\b", re.IGNORECASE),
    re.compile(r"(?:什么是|什麼是|怎(?:么|樣)用|如何使用|解释|說明|说明)"),
    re.compile(r"(?:뭐야|뭔데|무엇|어떻게|설명|사용법|알려\s?줘|소개)"),
    re.compile(r"(?:とは|って何|使い方|説明|教えて|知りたい)"),
)
ACTIVATION_PATTERN = re.compile(
    r"\b(?:use|run|start|enable|activate|invoke|trigger|launch)\b[^\n]{0,28}\bwiki\b",
    re.IGNORECASE,
)
QUOTED_SPAN_PATTERN = re.compile(
    r'"[^"\n]{1,400}"|\'[^\'\n]{1,400}\'|“[^”\n]{1,400}”|‘[^’\n]{1,400}’'
)
QUESTION_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:how\s+many|how\s+much|why|what\s+happened|what\s+went\s+wrong|cost|pricing)\b|(?:为什么|為什麼|왜|質問)",
    re.IGNORECASE,
)
DIAGNOSTIC_PATTERN = re.compile(
    r"(?:\bwiki\b[^\n]{0,48}\b(?:keeps?\s+(?:looping|re-?running)|has\s+(?:a\s+)?(?:bug|issue|problem|error)|is\s+(?:stuck|broken|failing)|loop(?:ing)?)\b|\b(?:bug|issue|problem|error)\b[^\n]{0,16}\b(?:with|in)\s+\bwiki\b)",
    re.IGNORECASE,
)
EVENT_ALIASES = {
    "session-start": "session-start",
    "sessionstart": "session-start",
    "pre-compact": "pre-compact",
    "precompact": "pre-compact",
    "session-end": "session-end",
    "sessionend": "session-end",
}


def matches_wiki_trigger(prompt: str) -> bool:
    """Return whether a prompt contains an actionable wiki trigger."""

    for match in TRIGGER_PATTERN.finditer(prompt):
        start = max(0, match.start() - 80)
        end = min(len(prompt), match.end() + 80)
        context = prompt[start:end]
        if ACTIVATION_PATTERN.search(context):
            return True
        if DIAGNOSTIC_PATTERN.search(context):
            continue
        line_start = prompt.rfind("\n", 0, match.start()) + 1
        line_end = prompt.find("\n", match.end())
        line = prompt[line_start : len(prompt) if line_end < 0 else line_end]
        if re.match(r"^\s*>\s", line) or re.match(r"^\s*\|(?:[^|\n]*\|){2,}\s*$", line):
            continue
        inside_quotes = any(span.start() <= match.start() < span.end() for span in QUOTED_SPAN_PATTERN.finditer(prompt))
        outside_quotes = QUOTED_SPAN_PATTERN.sub(" ", prompt)
        if inside_quotes and QUESTION_FOLLOWUP_PATTERN.search(outside_quotes):
            continue
        if any(pattern.search(context) for pattern in INFORMATIONAL_PATTERNS):
            continue
        return True
    return False


def _load_event(raw: str) -> dict[str, Any]:
    if not raw.strip():
        raise ValueError("hook input is empty")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("hook input must be a JSON object")
    return data


def run_host_hook(event: str, raw: str) -> dict[str, Any]:
    """Translate one command-hook lifecycle event to the neutral core."""

    normalized = event.strip().lower().replace("_", "-")
    canonical = EVENT_ALIASES.get(normalized)
    fallback: dict[str, Any] = {"continue": True, "suppressOutput": True}
    if canonical is None:
        return fallback

    try:
        data = _load_event(raw)
        root = Path(str(data.get("cwd") or Path.cwd())).expanduser().resolve()
        store = llm_wiki.WikiStore(root)
        _, receipt = llm_wiki.run_hook_event(
            canonical,
            store,
            data,
            limit=30,
        )
    except Exception:
        return fallback

    if canonical == "session-start":
        context = str(receipt.get("result", {}).get("additionalContext", "")).strip()
        if not context:
            return fallback
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    if canonical == "pre-compact":
        context = str(receipt.get("result", {}).get("additionalContext", "")).strip()
        if not context:
            return fallback
        return {"continue": True, "systemMessage": context}
    return {"continue": True}


def _command(python_path: Path, adapter: Path, event: str) -> str:
    return " ".join(
        shlex.quote(str(part))
        for part in (python_path, adapter, "host-hook", event)
    )


def render_hooks(skill_dir: Path, python_path: Path) -> dict[str, Any]:
    """Render explicit command-hook wiring without mutating host config."""

    skill_dir = skill_dir.expanduser().resolve()
    python_path = python_path.expanduser().resolve()
    adapter = skill_dir / "scripts" / "llm_wiki_adapter.py"

    def group(event: str, timeout: int) -> list[dict[str, Any]]:
        return [
            {
                # Hosts compile hook matchers as regular expressions; "*"
                # alone is invalid there ("nothing to repeat"), so match-all
                # is spelled ".*".
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": _command(python_path, adapter, event),
                        "timeout": timeout,
                    }
                ],
            }
        ]

    return {
        "hooks": {
            "SessionStart": group("session-start", 5),
            "PreCompact": group("pre-compact", 3),
            "SessionEnd": group("session-end", 30),
        }
    }


def render_mcp_config(skill_dir: Path, python_path: Path) -> dict[str, Any]:
    """Render portable stdio MCP configuration without installing it."""

    skill_dir = skill_dir.expanduser().resolve()
    python_path = python_path.expanduser().resolve()
    return {
        "mcpServers": {
            "llm-wiki": {
                "command": str(python_path),
                "args": [str(skill_dir / "scripts" / "llm_wiki_mcp.py")],
            }
        }
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    trigger = subparsers.add_parser("trigger")
    trigger.add_argument("prompt", nargs="+")

    hook = subparsers.add_parser("host-hook")
    hook.add_argument("event")

    for name in ("render-hooks", "render-mcp"):
        render = subparsers.add_parser(name)
        render.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
        render.add_argument("--python", type=Path, default=Path(sys.executable))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "trigger":
        payload = {
            "matched": matches_wiki_trigger(" ".join(args.prompt)),
            "skill": "llm-wiki",
        }
    elif args.command == "host-hook":
        payload = run_host_hook(args.event, sys.stdin.read())
    elif args.command == "render-hooks":
        payload = render_hooks(args.skill_dir, args.python)
    else:
        payload = render_mcp_config(args.skill_dir, args.python)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

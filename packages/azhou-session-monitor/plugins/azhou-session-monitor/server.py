"""Local stdio MCP App. Only numeric counters from the host-bound thread leave the reader."""
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
URI = "ui://azhou/session.html"
MIME = "text/html;profile=mcp-app"
TOOL = "session_performance"
ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)


def thread_id(meta):
    # openai/session is an anonymized correlation ID, unsuitable for local file lookup.
    fields = meta.get("x-codex-turn-metadata", {})
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except ValueError:
            fields = {}
    values = [meta.get("threadId")]
    if isinstance(fields, dict):
        values += [fields.get("thread_id"), fields.get("session_id")]
    ids = {str(x).lower() for x in values if x}
    if len(ids) == 1 and ID.fullmatch(next(iter(ids))):
        return ids.pop()
    return None


def nonnegative(value):
    return value if type(value) is int and value >= 0 else None


def rollout_path(home, sid):
    roots = (home / "sessions", home / "archived_sessions")
    suffix = re.compile(rf"-{re.escape(sid)}(?:_{ID.pattern})?\.jsonl$", re.I)
    paths = [p for root in roots if root.is_dir()
             for p in root.rglob(f"rollout-*-{sid}*.jsonl")
             if suffix.search(p.name) and p.is_file() and p.resolve() == p.absolute()]
    if len(paths) == 1:
        return paths[0]
    if paths:
        # Desktop can keep both an old rollout and a suffixed continuation.
        # Pick one only when the host's read-only index identifies the exact path.
        db = home / "state_5.sqlite"
        if db.is_file():
            try:
                connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.2)
                try:
                    row = connection.execute("SELECT rollout_path FROM threads WHERE id = ?", (sid,)).fetchone()
                finally:
                    connection.close()
            except sqlite3.Error:
                return None
            if row and isinstance(row[0], str) and Path(row[0]) in paths:
                return Path(row[0])
    return None


def snapshot(home, sid):
    if sid is None:
        return {"state": "unbound"}
    path = rollout_path(home, sid)
    if path is None:
        return {"state": "unavailable"}
    current = None
    totals = {}
    responses = set()
    last_completed = None
    result = {"state": "empty"}
    with path.open("rb") as events:
        first = json.loads(events.readline())
        if first.get("type") != "session_meta" or first.get("payload", {}).get("id") != sid:
            return {"state": "unavailable"}
        for line in events:
            if not line.endswith(b"\n"):
                break
            item = json.loads(line)
            p = item.get("payload")
            if not isinstance(p, dict):
                continue
            kind, event, turn = item.get("type"), p.get("type"), p.get("turn_id")
            if not isinstance(turn, str) or not turn:
                continue
            if kind == "event_msg" and event == "task_started":
                current, totals, responses = turn, {}, set()
                result = {"state": "running"}
            elif turn == current:
                if kind == "token_usage_record":
                    if isinstance(p.get("turn_token_usage"), dict):
                        totals = p["turn_token_usage"]
                    if p.get("response_id"):
                        responses.add(p["response_id"])
                elif kind == "event_msg" and event == "task_complete":
                    duration = nonnegative(p.get("duration_ms"))
                    output = nonnegative(totals.get("output_tokens"))
                    input_tokens = nonnegative(totals.get("input_tokens"))
                    cached = nonnegative(totals.get("cached_input_tokens"))
                    result = {"state": "complete", "cacheHitPercent":
                              round(100 * cached / input_tokens, 1)
                              if input_tokens and cached is not None and cached <= input_tokens else None, "durationMs": duration,
                              "ttftMs": nonnegative(p.get("time_to_first_token_ms")),
                              "outputTokens": output, "responses": len(responses) or None,
                              "effectiveTps": round(output * 1000 / duration, 1)
                              if output is not None and duration else None}
                    last_completed = result
                elif kind == "event_msg" and event == "turn_aborted":
                    result = {"state": "interrupted"}
    if last_completed and result is not last_completed:
        result["lastCompleted"] = last_completed
    return result


def dispatch(method, params, home):
    if method == "initialize":
        offered = params.get("protocolVersion")
        supported = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
        return {"protocolVersion": offered if offered in supported else supported[0],
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "azhou-session-monitor", "version": "0.1.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": TOOL, "description": "Read timing and usage for this conversation.",
                           "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                           "annotations": {"readOnlyHint": True, "openWorldHint": False},
                           "_meta": {"ui": {"resourceUri": URI}, "openai/outputTemplate": URI,
                                     "openai/ui": {"entrypoints": [{"type": "thread"}]}}}]}
    if method == "resources/list":
        return {"resources": [{"uri": URI, "name": "Session performance", "mimeType": MIME}]}
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/read" and params.get("uri") == URI:
        art = base64.b64encode((ROOT / "azhou.webp").read_bytes()).decode()
        html = (ROOT / "panel.html").read_text("utf8").replace("__ART__", art)
        return {"contents": [{"uri": URI, "mimeType": MIME, "text": html}]}
    if method == "tools/call" and params.get("name") == TOOL:
        if params.get("arguments"):
            raise ValueError("No arguments accepted")
        try:
            data = snapshot(home, thread_id(params.get("_meta", {})))
        except (OSError, ValueError):
            data = {"state": "unavailable"}
        return {"structuredContent": data, "content": [{"type": "text", "text": json.dumps(data)}]}
    raise KeyError(method)


def main():
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
    for line in sys.stdin:
        rid = None
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
                raise ValueError()
            if "id" not in msg:
                continue
            rid = msg["id"]
            result = dispatch(msg["method"], msg.get("params", {}), home)
            reply = {"result": result}
        except KeyError:
            reply = {"error": {"code": -32601, "message": "Unknown method or resource"}}
        except (TypeError, ValueError, AttributeError):
            reply = {"error": {"code": -32602, "message": "Invalid request"}}
        print(json.dumps({"jsonrpc": "2.0", "id": rid, **reply}), flush=True)


if __name__ == "__main__":
    main()

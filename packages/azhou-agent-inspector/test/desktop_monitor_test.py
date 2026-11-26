import base64
import importlib.util
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

spec = importlib.util.spec_from_file_location("monitor", Path(__file__).resolve().parents[1] / "plugins/azhou-agent-inspector/server.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class PanelTests(unittest.TestCase):
    def test_two_interleaved_calls_do_not_cross_threads(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            directory = home / "sessions/2026/11/24"
            directory.mkdir(parents=True)
            def fixture(output):
                sid = str(uuid4())
                events = [
                    ("session_meta", {"id": sid}),
                    ("event_msg", {"type":"task_started", "turn_id":"t"}),
                    ("token_usage_record", {"response_id":"r", "turn_id":"t","turn_token_usage":{"output_tokens":output}}),
                    ("event_msg", {"type":"task_complete","turn_id":"t","duration_ms":2000,"time_to_first_token_ms":200}),
                ]
                path = directory / f"rollout-sample-{sid}.jsonl"
                path.write_text("".join(json.dumps({"type":k,"payload":v})+"\n" for k,v in events))
                return sid
            a,b=fixture(6),fixture(20)
            def read(meta):
                return monitor.dispatch("tools/call", {"name":monitor.TOOL,"_meta":meta}, home)["structuredContent"]
            for sid, expected in [(a,3),(b,10),(a,3)]:
                self.assertEqual(expected,read({"threadId":sid})["effectiveTps"])
            self.assertEqual("unbound",read({"openai/session":a})["state"])
            self.assertEqual("unbound",read({"threadId":a,"x-codex-turn-metadata":{"thread_id":b}})["state"])
            self.assertEqual("unavailable",read({"threadId":str(uuid4())})["state"])

    def test_duplicate_rollouts_require_host_index_and_matching_header(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            sessions = home / "sessions"
            sessions.mkdir()
            sid = str(uuid4())
            old = sessions / f"rollout-sample-{sid}.jsonl"
            active = sessions / f"rollout-sample-{sid}_{uuid4()}.jsonl"
            old.touch()
            active.touch()
            self.assertIsNone(monitor.rollout_path(home, sid))
            with sqlite3.connect(home / "state_5.sqlite") as db:
                db.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
                db.execute("INSERT INTO threads VALUES (?, ?)", (sid, str(active)))
            self.assertEqual(active, monitor.rollout_path(home, sid))
            active.write_text(json.dumps({"type": "session_meta", "payload": {"id": str(uuid4())}}) + "\n")
            self.assertEqual("unavailable", monitor.snapshot(home, sid)["state"])

    def test_interrupted_turn_keeps_previous_counters_and_ignores_partial_append(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            sessions = home / "sessions"
            sessions.mkdir()
            sid = str(uuid4())
            path = sessions / f"rollout-sample-{sid}.jsonl"
            events = [
                ("session_meta", {"id": sid}),
                ("event_msg", {"type": "task_started", "turn_id": "first"}),
                ("event_msg", {"type": "token_count", "info": {
                    "total_token_usage": {"total_tokens": 800},
                    "last_token_usage": {"total_tokens": 60}, "model_context_window": 100,
                }}),
                ("token_usage_record", {"turn_id": "first", "response_id": "same",
                                        "turn_token_usage": {"output_tokens": 10}}),
                ("token_usage_record", {"turn_id": "first", "response_id": "same",
                                        "turn_token_usage": {"output_tokens": 60, "input_tokens": 80,
                                                             "cached_input_tokens": 20}}),
                ("event_msg", {"type": "task_complete", "turn_id": "first", "duration_ms": 2000,
                               "time_to_first_token_ms": 400}),
                ("event_msg", {"type": "task_started", "turn_id": "second"}),
            ]
            path.write_text("".join(json.dumps({"type": kind, "payload": payload}) + "\n"
                                    for kind, payload in events), encoding="utf8")
            running = monitor.snapshot(home, sid)
            self.assertEqual("running", running["state"])
            self.assertEqual({"state": "complete", "effectiveTps": 30.0, "ttftMs": 400,
                              "durationMs": 2000, "responses": 1, "outputTokens": 60,
                              "cacheHitPercent": 25.0, "contextUsagePercent": 60.0}, running["lastCompleted"])
            with path.open("a", encoding="utf8") as stream:
                stream.write(json.dumps({"type": "event_msg", "payload": {
                    "type": "turn_aborted", "turn_id": "second"}}) + "\n")
                stream.write('{"type": "partial')
            interrupted = monitor.snapshot(home, sid)
            self.assertEqual("interrupted", interrupted["state"])
            self.assertEqual(running["lastCompleted"], interrupted["lastCompleted"])
            # A rate-limit event can replay the preceding turn's cumulative usage.
            repeated = events[2][1]
            second = [*events, ("event_msg", repeated),
                      ("token_usage_record", {"turn_id": "second", "turn_token_usage": {"output_tokens": 1}}),
                      ("event_msg", {"type": "task_complete", "turn_id": "second", "duration_ms": 1000})]
            path.write_text("".join(json.dumps({"type": kind, "payload": payload}) + "\n"
                                    for kind, payload in second), encoding="utf8")
            self.assertNotIn("contextUsagePercent", monitor.snapshot(home, sid))

    def test_inspector_surfaces_report_the_same_release(self):
        package = monitor.ROOT.parents[1]
        manifests = [
            package / "hub-package.json",
            package / "plugins/zcode/.zcode-plugin/plugin.json",
            monitor.ROOT / ".codex-plugin/plugin.json",
        ]
        versions = [json.loads(path.read_text("utf8"))["version"] for path in manifests]
        marketplace = json.loads((package / "marketplace.json").read_text("utf8"))
        versions += [entry["version"] for entry in marketplace["plugins"] if entry["name"] == "azhou-agent-inspector"]
        self.assertEqual(4, len(versions))
        self.assertEqual(1, len(set(versions)), versions)
        version = versions[0]
        hello = monitor.dispatch("initialize", {}, None)
        self.assertEqual(version, hello["serverInfo"]["version"])
        html = monitor.dispatch("resources/read", {"uri": monitor.URI}, None)["contents"][0]["text"]
        self.assertIn(f'version: {json.dumps(version)}', html)
        self.assertNotIn("__PLUGIN_VERSION__", html)

    def test_resource_is_registered_and_self_contained(self):
        listed = monitor.dispatch("tools/list",{},None)["tools"][0]
        self.assertEqual([{"type":"thread"}],listed["_meta"]["openai/ui"]["entrypoints"])
        html = monitor.dispatch("resources/read",{"uri":monitor.URI},None)["contents"][0]["text"]
        for filename in ("azhou.webp", "wallpaper.webp"):
            data = base64.b64encode((monitor.ROOT / filename).read_bytes()).decode("ascii")
            self.assertIn(f"data:image/webp;base64,{data}", html)
        self.assertNotIn("__ART__", html)
        self.assertNotIn("__WALLPAPER__", html)

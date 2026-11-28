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

    def test_thread_binding_accepts_consistent_metadata_and_rejects_ambiguous_ids(self):
        sid, other = str(uuid4()), str(uuid4())
        self.assertEqual(monitor.thread_id({
            "threadId": sid.upper(),
            "x-codex-turn-metadata": json.dumps({"thread_id": sid, "session_id": sid}),
        }), sid)
        for meta in [
            {"openai/session": sid},
            {"threadId": "../" + sid},
            {"threadId": sid + "/extra"},
            {"threadId": sid, "x-codex-turn-metadata": {"session_id": other}},
            {"x-codex-turn-metadata": "{invalid"},
        ]:
            with self.subTest(meta=meta):
                self.assertIsNone(monitor.thread_id(meta))

    def test_foreign_turn_events_cannot_replace_bound_turn_counters(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            (home / "sessions").mkdir()
            sid = str(uuid4())
            events = [
                ("session_meta", {"id": sid}),
                ("event_msg", {"type": "task_started", "turn_id": "selected"}),
                ("token_usage_record", {"turn_id": "selected", "response_id": "selected-response",
                                       "turn_token_usage": {"output_tokens": 10}}),
                ("token_usage_record", {"turn_id": "other", "response_id": "foreign-private-response",
                                       "turn_token_usage": {"output_tokens": 9000}}),
                ("event_msg", {"type": "task_complete", "turn_id": "other", "duration_ms": 1}),
                ("event_msg", {"type": "turn_aborted", "turn_id": "other"}),
                ("event_msg", {"type": "task_complete", "turn_id": "selected", "duration_ms": 2000}),
            ]
            path = home / "sessions" / f"rollout-fixture-{sid}.jsonl"
            path.write_text("".join(json.dumps({"type": kind, "payload": payload}) + "\n"
                                    for kind, payload in events), encoding="utf8")
            result = monitor.dispatch("tools/call", {"name": monitor.TOOL, "_meta": {"threadId": sid}}, home)
            self.assertEqual(result["structuredContent"], {
                "state": "complete", "cacheHitPercent": None, "durationMs": 2000,
                "ttftMs": None, "outputTokens": 10, "responses": 1, "effectiveTps": 5.0,
            })
            self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
            self.assertNotIn("foreign-private-response", json.dumps(result))
            self.assertNotIn(sid, json.dumps(result))

    def test_invalid_counters_remain_unknown_instead_of_fabricating_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            (home / "sessions").mkdir()
            sid = str(uuid4())
            path = home / "sessions" / f"rollout-fixture-{sid}.jsonl"
            for value in [-1, True, 1.5, "12", None]:
                with self.subTest(value=value):
                    events = [
                        ("session_meta", {"id": sid}),
                        ("event_msg", {"type": "task_started", "turn_id": "t"}),
                        ("token_usage_record", {"turn_id": "t", "turn_token_usage": {
                            "output_tokens": value, "input_tokens": value, "cached_input_tokens": value,
                        }}),
                        ("event_msg", {"type": "task_complete", "turn_id": "t",
                                       "duration_ms": value, "time_to_first_token_ms": value}),
                    ]
                    path.write_text("".join(json.dumps({"type": kind, "payload": payload}) + "\n"
                                            for kind, payload in events), encoding="utf8")
                    result = monitor.snapshot(home, sid)
                    self.assertEqual(result["state"], "complete")
                    for name in ["durationMs", "ttftMs", "outputTokens", "cacheHitPercent", "effectiveTps"]:
                        self.assertIsNone(result[name], name)

    def test_zero_usage_is_valid_but_zero_duration_and_overcounted_cache_have_no_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            (home / "sessions").mkdir()
            sid = str(uuid4())
            path = home / "sessions" / f"rollout-fixture-{sid}.jsonl"
            for output, duration, input_tokens, cached, speed, hit in [
                (0, 1000, 10, 0, 0.0, 0.0),
                (10, 0, 0, 0, None, None),
                (10, 2000, 10, 11, 5.0, None),
            ]:
                with self.subTest(output=output, duration=duration, cached=cached):
                    events = [
                        ("session_meta", {"id": sid}),
                        ("event_msg", {"type": "task_started", "turn_id": "t"}),
                        ("token_usage_record", {"turn_id": "t", "turn_token_usage": {
                            "output_tokens": output, "input_tokens": input_tokens, "cached_input_tokens": cached,
                        }}),
                        ("event_msg", {"type": "task_complete", "turn_id": "t", "duration_ms": duration}),
                    ]
                    path.write_text("".join(json.dumps({"type": kind, "payload": payload}) + "\n"
                                            for kind, payload in events), encoding="utf8")
                    result = monitor.snapshot(home, sid)
                    self.assertEqual(result["outputTokens"], output)
                    self.assertEqual(result["durationMs"], duration)
                    self.assertEqual(result["effectiveTps"], speed)
                    self.assertEqual(result["cacheHitPercent"], hit)

    def test_malformed_rollout_is_unavailable_and_a_repaired_file_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            (home / "sessions").mkdir()
            sid = str(uuid4())
            path = home / "sessions" / f"rollout-fixture-{sid}.jsonl"
            meta = {"name": monitor.TOOL, "_meta": {"threadId": sid}}
            path.write_text('{"broken":\n', encoding="utf8")
            self.assertEqual(monitor.dispatch("tools/call", meta, home)["structuredContent"],
                             {"state": "unavailable"})
            path.write_text(json.dumps({"type": "session_meta", "payload": {"id": sid}}) + "\n",
                            encoding="utf8")
            self.assertEqual(monitor.dispatch("tools/call", meta, home)["structuredContent"], {"state": "empty"})

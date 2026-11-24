import importlib.util
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

spec = importlib.util.spec_from_file_location("monitor", Path(__file__).resolve().parents[1] / "plugins/azhou-session-monitor/server.py")
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

    def test_resource_is_registered_and_self_contained(self):
        listed = monitor.dispatch("tools/list",{},None)["tools"][0]
        self.assertEqual([{"type":"thread"}],listed["_meta"]["openai/ui"]["entrypoints"])
        html = monitor.dispatch("resources/read",{"uri":monitor.URI},None)["contents"][0]["text"]
        self.assertIn("data:image/webp;base64,UklG",html)
        self.assertNotIn("__ART__",html)

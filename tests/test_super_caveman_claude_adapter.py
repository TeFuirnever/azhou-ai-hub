from __future__ import annotations

import ast
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "skills" / "super-caveman" / "scripts" / "claude_adapter.py"
MATCHER = "startup|resume|clear|compact"


class ClaudeAdapterLifecycleTest(unittest.TestCase):
    """Lifecycle contract harness over normalized host events (#36, #38)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.proj = root / "proj"
        self.home = root / "home"
        self.proj.mkdir()
        self.home.mkdir()
        base = [sys.executable, str(ADAPTER)]
        self.base = base

    def adapter(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.base + list(args),
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            timeout=6,
        )

    def ok(self, *args: str, stdin: str = "") -> str:
        result = self.adapter(*args, stdin=stdin)
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def ctx(self, *args: str, stdin: str = "") -> str | None:
        out = self.ok(*args, stdin=stdin)
        payload = json.loads(out)
        return payload.get("hookSpecificOutput", {}).get("additionalContext")

    def event(self, prompt: str, sid: str = "s1") -> str:
        return json.dumps({"session_id": sid, "cwd": str(self.proj), "prompt": prompt})

    def start_event(self, source: str, sid: str = "s1") -> str:
        return json.dumps({"session_id": sid, "cwd": str(self.proj), "source": source, "transcript_path": "/private/x"})

    def test_setup_requires_explicit_scope(self) -> None:
        result = self.adapter("setup")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)

    def test_setup_registers_exact_owned_entries_and_preserves_unrelated(self) -> None:
        settings = self.proj / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({
            "model": "claude-sonnet-5",
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo unrelated"}]}],
                "SessionStart": [
                    {"matcher": "startup", "hooks": [{"type": "command", "command": "echo other", "timeout": 9}]}
                ],
            },
        }), encoding="utf-8")
        out = self.ok("setup", "--scope", "project", "--project-dir", str(self.proj), "--home-dir", str(self.home))
        payload = json.loads(settings.read_text())
        self.assertEqual("claude-sonnet-5", payload["model"])
        self.assertEqual([{"hooks": [{"type": "command", "command": "echo unrelated"}]}], payload["hooks"]["Stop"])
        self.assertEqual(
            [{"matcher": "startup", "hooks": [{"type": "command", "command": "echo other", "timeout": 9}]}],
            payload["hooks"]["SessionStart"][:-1],
        )
        owned = payload["hooks"]["SessionStart"][-1]
        self.assertEqual(MATCHER, owned["matcher"])
        self.assertEqual(1, len(owned["hooks"]))
        self.assertEqual(5, owned["hooks"][0]["timeout"])
        self.assertIn(" render", owned["hooks"][0]["command"])
        uprompt = payload["hooks"]["UserPromptSubmit"][-1]
        self.assertNotIn("matcher", uprompt)
        self.assertIn(" prompt", uprompt["hooks"][0]["command"])
        self.assertIn('"ok": true', out)

    def test_setup_is_idempotent_across_scopes_and_uninstall_is_exact(self) -> None:
        for scope, args in (
            ("project", ["--project-dir", str(self.proj)]),
            ("user", ["--home-dir", str(self.home)]),
        ):
            with self.subTest(scope=scope):
                self.ok("setup", "--scope", scope, *args)
                first = self._settings_bytes(scope)
                self.ok("setup", "--scope", scope, *args)
                self.assertEqual(first, self._settings_bytes(scope))
                self.ok("uninstall", "--scope", scope, *args)
                after = json.loads(self._settings_bytes(scope) or "{}")
                self.assertNotIn("SessionStart", after.get("hooks", {}))
                self.assertNotIn("UserPromptSubmit", after.get("hooks", {}))

    def _settings_bytes(self, scope: str) -> str:
        base = self.proj if scope == "project" else self.home
        path = base / ".claude" / "settings.json"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_render_injects_capsule_once_per_supported_event(self) -> None:
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                before = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                                  stdin=self.start_event(source, sid="sr"))
                self.assertIsNotNone(before)
                self.assertIn(f"event={source}", before)
                self.assertIn("rules_digest=", before)
                self.assertIn("schema_version=super-caveman.claude-capsule.v1", before)
                self.assertLessEqual(len(before), 10_000)
                # repeated legitimate delivery keeps injecting once per invocation
                again = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                                 stdin=self.start_event(source, sid="sr"))
                self.assertEqual(before, again)

    def test_render_neutral_capsule_names_off_state_and_enable_path(self) -> None:
        context = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                           stdin=self.start_event("startup", sid="sn"))
        self.assertIsNotNone(context)
        self.assertIn("response shaping is off", context)
        self.assertIn("/super-caveman enable full project", context)
        self.assertIn("event=startup", context)

    def test_resume_restores_session_and_rejects_corrupt_state(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "ultra",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        sid = "res-1"
        self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                stdin=self.event("/super-caveman lite", sid=sid))
        resumed = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                           stdin=self.start_event("resume", sid=sid))
        self.assertIn("active_mode=lite", resumed)
        # corrupt the session file; resume falls back deterministically
        path = self.proj / ".azhou" / "super-caveman" / "sessions" / f"{sid}.json"
        path.write_text("{not json", encoding="utf-8")
        fallback = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                            stdin=self.start_event("resume", sid=sid))
        self.assertIn("active_mode=ultra", fallback)
        self.assertFalse(path.is_symlink())

    def test_clear_resets_overrides_and_compact_preserves_state(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        sid = "cc-1"
        self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                stdin=self.event("/super-caveman ultra", sid=sid))
        clear = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                         stdin=self.start_event("clear", sid=sid))
        self.assertIn("active_mode=full", clear)  # back to the project default
        path = self.proj / ".azhou" / "super-caveman" / "sessions" / f"{sid}.json"
        self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                stdin=self.event("/super-caveman lite", sid=sid))
        compact = self.ctx("render", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                           stdin=self.start_event("compact", sid=sid))
        self.assertIn("active_mode=lite", compact)  # preserved through compaction

    def test_duplicate_setup_leaves_one_owned_registration_per_scope(self) -> None:
        self.ok("setup", "--scope", "project", "--project-dir", ".../dup" if False else str(self.proj), "--home-dir", str(self.home))
        self.ok("setup", "--scope", "project", "--project-dir", str(self.proj), "--home-dir", str(self.home))
        payload = json.loads(self._settings_bytes("project"))
        starts = payload["hooks"]["SessionStart"]
        self.assertEqual(1, sum(1 for e in starts if "claude_adapter.py" in json.dumps(e)))
        self.assertEqual(1, sum("claude_adapter.py" in json.dumps(e) for e in payload["hooks"]["UserPromptSubmit"]))

    def test_stop_phrases_change_only_current_session(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                stdin=self.event("stop super-caveman", sid="stop-1"))
        stopped = json.loads((self.proj / ".azhou" / "super-caveman" / "sessions" / "stop-1.json").read_text())
        self.assertTrue(stopped["stopped"])
        default = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                           stdin=self.event("plain", sid="stop-2"))
        self.assertIn("mode=full", default)  # other sessions unaffected; defaults unchanged
        self.ok("enable", "--scope", "user", "--mode", "lite",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                stdin=self.event("x", sid="stop-3"))
        still = self.ok("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                        stdin=self.event("y", sid="stop-3"))
        # project default (full) still outranks user default after enabling user layer
        self.assertIn("mode=full", still)
        defaults = json.loads((self.home / ".config" / "super-caveman" / "defaults.json").read_text())
        self.assertEqual("lite", defaults["mode"])  # stop never mutates persistent layers

    def test_prompt_output_limits_and_fail_open(self) -> None:
        c = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                     stdin=self.event("/super-caveman full", sid="lim-1"))
        self.assertLessEqual(len(c), 1_024)
        bad = self.adapter("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home), stdin="not-json")
        self.assertEqual(0, bad.returncode)
        self.assertEqual("{}", bad.stdout.strip())
        empty = self.adapter("prompt", stdin="")
        self.assertEqual(0, empty.returncode)
        self.assertEqual("{}", empty.stdout.strip())

    def test_reinforcement_never_reemits_startup_capsule(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        c = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                     stdin=self.event("work", sid="cap-1"))
        self.assertIn("mode=full", c)
        self.assertNotIn("Canonical rules", c)
        self.assertNotIn("schema_version=", c)
        self.assertNotIn("rules_digest=", c)

    def test_corrupt_and_missing_session_state_falls_back_deterministically(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "wenyan-full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        path = self.proj / ".azhou" / "super-caveman" / "sessions" / "corrupt.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"schema_version": "bogus"}', encoding="utf-8")
        c = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                     stdin=self.event("hello", sid="corrupt"))
        self.assertIn("mode=wenyan-full", c)

    def test_symlinked_session_state_is_rejected(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        path = self.proj / ".azhou" / "super-caveman" / "sessions" / "link.json"
        path.parent.mkdir(parents=True)
        outside = self.proj / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        path.symlink_to(outside)
        result = self.adapter("prompt", "--project-dir", str(self.proj),
                              "--home-dir", str(self.home),
                              stdin=self.event("/super-caveman ultra", sid="link"))
        self.assertEqual(0, result.returncode)
        self.assertEqual("{}", result.stdout.strip())  # fail open, no corruption of outside.json
        self.assertEqual("{}", outside.read_text(encoding="utf-8"))

    def test_symlinked_settings_rejected_and_custom_paths_rejected(self) -> None:
        settings = self.proj / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        target = self.proj / "target.json"
        target.write_text("{}", encoding="utf-8")
        settings.symlink_to(target)
        result = self.adapter("setup", "--scope", "project", "--project-dir", str(self.proj), "--home-dir", str(self.home))
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(settings.is_symlink())
        outside = self.proj / "elsewhere.json"
        outside.write_text("{}", encoding="utf-8")
        custom = self.adapter("setup", "--scope", "project", "--project-dir", str(self.proj),
                              "--home-dir", str(self.home), "--hooks-path", str(outside))
        self.assertNotEqual(0, custom.returncode)
        self.assertEqual("{}", outside.read_text(encoding="utf-8"))

    def test_registration_timeout_is_five_seconds_and_protocol_is_pure(self) -> None:
        self.ok("setup", "--scope", "project", "--project-dir", str(self.proj), "--home-dir", str(self.home))
        payload = json.loads(self._settings_bytes("project"))
        for event, sub in (("SessionStart", "render"), ("UserPromptSubmit", "prompt")):
            entry = payload["hooks"][event][-1]
            handler = entry["hooks"][0]
            self.assertEqual(5, handler["timeout"])
            self.assertEqual("command", handler["type"])
            self.assertIn(f" {sub}", handler["command"])

    def test_adapter_has_no_network_clients_or_urls(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertFalse({"requests", "urllib", "httpx", "socket", "smtplib"} & imports)
        self.assertNotRegex(source, r"https?://")

    def test_status_route_reports_layers_without_mutating(self) -> None:
        self.ok("enable", "--scope", "user", "--mode", "wenyan-ultra",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        before = sorted(p.name for p in (self.proj / ".azhou" / "super-caveman" / "sessions").glob("*.json")) if (self.proj / ".azhou" / "super-caveman" / "sessions").exists() else []
        c = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                     stdin=self.event("/super-caveman status", sid="stat-1"))
        self.assertIn("effective mode", c)
        self.assertIn("persistent user default: wenyan-ultra", c)
        after = sorted(p.name for p in (self.proj / ".azhou" / "super-caveman" / "sessions").glob("*.json")) if (self.proj / ".azhou" / "super-caveman" / "sessions").exists() else []
        self.assertEqual(before, after)

    def test_wenyan_and_compat_triggers_route_deterministically(self) -> None:
        for phrase, expect in (
            ("/caveman ultra", "mode=ultra"),
            ("/super-caveman wenyan-full", "mode=wenyan-full"),
            ("/super-caveman lite", "mode=lite"),
            ("/super-CAVEMAN FULL".lower(), "mode=full"),
        ):
            with self.subTest(phrase=phrase):
                sid = f"trig-{abs(hash(phrase)) % 10000}"
                c = self.ctx("prompt", "--project-dir", str(self.proj), "--home-dir", str(self.home),
                             stdin=self.event(phrase, sid=sid))
                self.assertIn(expect, c)

    def test_uninstall_purge_state_removes_only_adapter_state(self) -> None:
        self.ok("setup", "--scope", "project", "--project-dir", str(self.proj), "--home-dir", str(self.home))
        self.ok("enable", "--scope", "project", "--mode", "full",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        keeper = self.proj / "state-keeper.txt"
        keeper.write_text("keep me", encoding="utf-8")
        unrelated = self.proj / ".azhou" / "other-skill" / "state.json"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("{}", encoding="utf-8")
        self.ok("uninstall", "--scope", "project", "--purge-state",
                "--project-dir", str(self.proj), "--home-dir", str(self.home))
        self.assertFalse((self.proj / ".azhou" / "super-caveman").exists())
        self.assertTrue(keeper.exists())
        self.assertTrue(unrelated.exists())
        after = json.loads(self._settings_bytes("project"))
        self.assertNotIn("SessionStart", after.get("hooks", {}))
        self.assertNotIn("UserPromptSubmit", after.get("hooks", {}))


if __name__ == "__main__":
    unittest.main()

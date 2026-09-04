from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "skills" / "super-caveman" / "scripts" / "zcode_adapter.py"
CANONICAL = ROOT / "skills" / "super-caveman" / "scripts" / "claude_adapter.py"


class ZcodeAdapterContractTest(unittest.TestCase):
    """Deterministic zcode lifecycle-adapter contract over the isolated candidate."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.proj = root / "proj"
        self.home = root / "home"
        self.proj.mkdir()
        self.home.mkdir()

    def adapter(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ADAPTER), *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def ok(self, *args: str, stdin: str = "") -> str:
        done = self.adapter(*args, stdin=stdin)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def config(self) -> dict:
        return json.loads((self.home / ".zcode" / "cli" / "config.json").read_text(encoding="utf-8"))

    def seed_unrelated(self) -> None:
        path = self.home / ".zcode" / "cli" / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "model": "unrelated",
                    "hooks": {
                        "enabled": True,
                        "events": {
                            "PostToolUse": [
                                {
                                    "matcher": ".*",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "async": False,
                                            "command": "/bin/sh -c 'unrelated-bridge; exit 0'",
                                        }
                                    ],
                                }
                            ],
                            "SessionStart": [
                                {
                                    "matcher": ".*",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "async": False,
                                            "command": "/bin/sh -c 'unrelated-startup; exit 0'",
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def owned(self, event: str) -> list[dict]:
        entries = self.config()["hooks"]["events"].get(event, [])
        return [e for e in entries if e.get("matcher") == ".*" and any(
            "zcode_adapter.py" in h.get("command", "") for h in e.get("hooks", [])
        )]

    def test_setup_registers_two_events_and_preserves_unrelated(self) -> None:
        self.seed_unrelated()
        out = json.loads(self.ok("setup", "--scope", "user", "--home-dir", str(self.home)))
        self.assertTrue(out["ok"])
        cfg = self.config()
        self.assertTrue(cfg["hooks"]["enabled"])
        self.assertEqual(len(self.owned("SessionStart")), 1)
        self.assertEqual(len(self.owned("UserPromptSubmit")), 1)
        render_cmd = self.owned("SessionStart")[0]["hooks"][0]["command"]
        prompt_cmd = self.owned("UserPromptSubmit")[0]["hooks"][0]["command"]
        self.assertTrue(render_cmd.endswith(" render"))
        self.assertTrue(prompt_cmd.endswith(" prompt"))
        kept = cfg["hooks"]["events"]["PostToolUse"]
        self.assertEqual(len(kept), 1)
        self.assertIn("unrelated-bridge", kept[0]["hooks"][0]["command"])
        self.assertEqual(cfg["model"], "unrelated")

    def test_setup_is_idempotent_and_uninstall_is_exact(self) -> None:
        self.seed_unrelated()
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.assertEqual(len(self.owned("SessionStart")), 1)
        self.assertEqual(len(self.owned("UserPromptSubmit")), 1)
        self.ok("uninstall", "--scope", "user", "--home-dir", str(self.home))
        cfg = self.config()
        self.assertEqual(self.owned("SessionStart"), [])
        self.assertEqual(self.owned("UserPromptSubmit"), [])
        self.assertNotIn("UserPromptSubmit", cfg["hooks"]["events"])
        self.assertTrue(cfg["hooks"]["enabled"])
        self.assertIn("unrelated-startup", json.dumps(cfg["hooks"]["events"]["SessionStart"]))
        self.assertIn("unrelated-bridge", json.dumps(cfg["hooks"]["events"]["PostToolUse"]))
        self.assertEqual(cfg["model"], "unrelated")

    def test_uninstall_leaves_enabled_flag_untouched(self) -> None:
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.ok("uninstall", "--scope", "user", "--home-dir", str(self.home))
        cfg = self.config()
        self.assertNotIn("events", cfg["hooks"])
        self.assertTrue(cfg["hooks"]["enabled"])

    def test_project_scope_uses_project_root(self) -> None:
        self.ok("setup", "--scope", "project", "--project-dir", str(self.proj))
        path = self.proj / ".zcode" / "cli" / "config.json"
        self.assertTrue(path.is_file())
        cfg = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("SessionStart", cfg["hooks"]["events"])

    def test_nonstandard_config_path_rejected(self) -> None:
        self.seed_unrelated()
        before = (self.home / ".zcode" / "cli" / "config.json").read_text(encoding="utf-8")
        done = self.adapter(
            "setup", "--scope", "user", "--home-dir", str(self.home),
            "--config-path", str(self.home / "elsewhere.json"),
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("standard", done.stderr)
        self.assertEqual(
            (self.home / ".zcode" / "cli" / "config.json").read_text(encoding="utf-8"), before
        )

    def test_symlinked_config_rejected(self) -> None:
        real = self.home / "real-config.json"
        real.write_text("{}", encoding="utf-8")
        cli = self.home / ".zcode" / "cli"
        cli.mkdir(parents=True)
        (cli / "config.json").symlink_to(real)
        done = self.adapter("setup", "--scope", "user", "--home-dir", str(self.home))
        self.assertEqual(done.returncode, 2)

    def start_event(self, sid: str = "s1") -> str:
        # zcode payloads carry camelCase plus snake_case aliases.
        return json.dumps(
            {
                "source": "startup",
                "sessionId": sid,
                "session_id": sid,
                "cwd": str(self.proj),
                "mode": "default",
                "model": "test-model",
            }
        )

    def prompt_event(self, prompt: str, sid: str = "s1") -> str:
        return json.dumps(
            {
                "prompt": prompt,
                "sessionId": sid,
                "session_id": sid,
                "cwd": str(self.proj),
            }
        )

    def test_camelcase_only_payload_still_persists_session_state(self) -> None:
        # zcode documents camelCase envelopes; the canonical handlers read
        # snake_case. Headless -p fires no hooks (probe-verified 2026-09-04),
        # so the adapter bridges defensively and must work with either casing.
        camel_only = json.dumps(
            {
                "source": "startup",
                "sessionId": "camel1",
                "cwd": str(self.proj),
                "mode": "default",
                "model": "test-model",
            }
        )
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        done = self.adapter("render", "--project-dir", str(self.proj), stdin=camel_only)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = self.emit(done.stdout)
        self.assertIn("active_mode=full", payload["hookSpecificOutput"]["additionalContext"])
        state = json.loads(
            (self.proj / ".azhou" / "super-caveman" / "sessions" / "camel1.json").read_text(encoding="utf-8")
        )
        self.assertFalse(state["stopped"])
        stop_camel = json.dumps({"prompt": "stop super-caveman", "sessionId": "camel1", "cwd": str(self.proj)})
        self.adapter("prompt", "--project-dir", str(self.proj), stdin=stop_camel)
        state = json.loads(
            (self.proj / ".azhou" / "super-caveman" / "sessions" / "camel1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(state["stopped"])

    def emit(self, stdout: str) -> dict:
        return json.loads(stdout.strip().splitlines()[-1])

    def test_render_emits_capsule_and_writes_session_state(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        done = self.adapter("render", "--project-dir", str(self.proj), stdin=self.start_event())
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = self.emit(done.stdout)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("active_mode=full", context)
        self.assertIn("super-caveman.claude-capsule.v1", context)
        state = json.loads(
            (self.proj / ".azhou" / "super-caveman" / "sessions" / "s1.json").read_text(encoding="utf-8")
        )
        self.assertFalse(state["stopped"])

    def test_render_neutral_reports_off_without_shaping(self) -> None:
        done = self.adapter("render", "--project-dir", str(self.proj), stdin=self.start_event())
        payload = self.emit(done.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("response shaping is off", context)
        self.assertNotIn("active_mode=", context.replace("active_mode=None", ""))

    def test_prompt_stop_phrase_persists_then_plain_is_silent(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        self.adapter("render", "--project-dir", str(self.proj), stdin=self.start_event())
        self.adapter("prompt", "--project-dir", str(self.proj), stdin=self.prompt_event("stop super-caveman"))
        state = json.loads(
            (self.proj / ".azhou" / "super-caveman" / "sessions" / "s1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(state["stopped"])
        done = self.adapter("prompt", "--project-dir", str(self.proj), stdin=self.prompt_event("plain text"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.emit(done.stdout), {})

    def test_prompt_reinforcement_names_mode_and_stays_bounded(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        self.adapter("render", "--project-dir", str(self.proj), stdin=self.start_event())
        done = self.adapter("prompt", "--project-dir", str(self.proj), stdin=self.prompt_event("do the thing"))
        payload = self.emit(done.stdout)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("mode=full", context)
        self.assertLessEqual(len(context), 1024)

    def test_enable_disable_status_reuse_canonical_layer(self) -> None:
        self.ok("enable", "--scope", "user", "--mode", "lite", "--home-dir", str(self.home))
        layer = json.loads(
            (self.home / ".config" / "super-caveman" / "defaults.json").read_text(encoding="utf-8")
        )
        self.assertEqual(layer["mode"], "lite")
        self.assertEqual(layer["schema_version"], "super-caveman.adapter-state.v1")
        status = json.loads(self.ok("status", "--home-dir", str(self.home)))
        self.assertEqual(status["defaults"]["user"]["mode"], "lite")
        self.ok("disable", "--scope", "user", "--home-dir", str(self.home))
        status = json.loads(self.ok("status", "--home-dir", str(self.home)))
        self.assertEqual(status["defaults"]["user"]["mode"], "off")

    def test_adapter_declares_schema_and_reuses_canonical_handlers(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("super-caveman.zcode-adapter.v1", source)
        tree = ast.parse(source)
        imports = {
            node.names[0].name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) and node.names
        }
        self.assertIn("claude_adapter", imports)
        self.assertNotIn("Super Caveman is active.", source)  # capsule text stays single-source

    def test_adapter_has_no_network_clients_or_urls(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertNotIn("urllib", {alias.name for alias in node.names})
                self.assertNotIn("requests", {alias.name for alias in node.names})
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertFalse(node.module.startswith("urllib"), node.module)
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)

    def test_canonical_handler_module_is_unchanged_shared_source(self) -> None:
        # The adapter must reuse, not fork, the canonical handler contract.
        canonical = CANONICAL.read_text(encoding="utf-8")
        self.assertIn("def run_render(", canonical)
        self.assertIn("def run_prompt(", canonical)
        self.assertIn("def write_layer(", canonical)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "skills" / "super-caveman" / "scripts" / "codex_adapter.py"


class CodexAdapterLifecycleTest(unittest.TestCase):
    """Full-lifecycle contract for the Codex adapter per spec #115 (#36 hierarchy)."""

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

    def hooks(self) -> dict:
        return json.loads((self.home / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    def owned(self, event: str, sub: str) -> list[dict]:
        entries = self.hooks().get("hooks", {}).get(event, [])
        return [e for e in entries if any(
            "codex_adapter.py" in h.get("command", "") and h.get("command", "").endswith(f" {sub}")
            for h in e.get("hooks", [])
        )]

    def test_setup_registers_both_events_and_uninstall_is_exact(self) -> None:
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.assertEqual(len(self.owned("SessionStart", "render")), 1)
        self.assertEqual(len(self.owned("UserPromptSubmit", "prompt")), 1)
        self.ok("uninstall", "--scope", "user", "--home-dir", str(self.home))
        self.assertEqual(self.owned("SessionStart", "render"), [])
        self.assertEqual(self.owned("UserPromptSubmit", "prompt"), [])

    def test_setup_is_idempotent_across_both_events(self) -> None:
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.ok("setup", "--scope", "user", "--home-dir", str(self.home))
        self.assertEqual(len(self.owned("SessionStart", "render")), 1)
        self.assertEqual(len(self.owned("UserPromptSubmit", "prompt")), 1)

    def test_prompt_handler_runs_the_canonical_state_machine(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        self.adapter("render", stdin=json.dumps({"source": "startup", "session_id": "s1", "cwd": str(self.proj)}))
        stop = self.adapter(
            "prompt", stdin=json.dumps({"prompt": "stop super-caveman", "session_id": "s1", "cwd": str(self.proj)})
        )
        self.assertEqual(stop.returncode, 0, stop.stderr)
        state = json.loads(
            (self.proj / ".azhou" / "super-caveman" / "sessions" / "s1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(state["stopped"])
        plain = self.adapter(
            "prompt", stdin=json.dumps({"prompt": "plain text", "session_id": "s1", "cwd": str(self.proj)})
        )
        self.assertEqual(json.loads(plain.stdout.strip().splitlines()[-1]), {})

    def test_prompt_reinforcement_names_mode_and_is_bounded(self) -> None:
        self.ok("enable", "--scope", "project", "--mode", "full", "--project-dir", str(self.proj))
        self.adapter("render", stdin=json.dumps({"source": "startup", "session_id": "s2", "cwd": str(self.proj)}))
        done = self.adapter(
            "prompt", stdin=json.dumps({"prompt": "do the work", "session_id": "s2", "cwd": str(self.proj)})
        )
        payload = json.loads(done.stdout.strip().splitlines()[-1])
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("mode=full", context)
        self.assertLessEqual(len(context), 1024)

    def test_enable_disable_status_reuse_canonical_layers(self) -> None:
        self.ok("enable", "--scope", "user", "--mode", "lite", "--home-dir", str(self.home))
        layer = json.loads(
            (self.home / ".config" / "super-caveman" / "defaults.json").read_text(encoding="utf-8")
        )
        self.assertEqual(layer["mode"], "lite")
        status = json.loads(self.ok("status", "--home-dir", str(self.home)))
        self.assertEqual(status["defaults"]["user"]["mode"], "lite")
        self.ok("disable", "--scope", "user", "--home-dir", str(self.home))
        status = json.loads(self.ok("status", "--home-dir", str(self.home)))
        self.assertEqual(status["defaults"]["user"]["mode"], "off")

    def test_render_and_prompt_delegate_to_the_canonical_module(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("claude_adapter.run_render", source)
        self.assertIn("claude_adapter.run_prompt", source)
        self.assertNotIn("Super Caveman is active.", source)  # capsule stays single-source
        self.assertIn("claude_adapter.write_layer_cli", source)
        self.assertIn("claude_adapter.status_report", source)


if __name__ == "__main__":
    unittest.main()

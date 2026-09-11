from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "super-repo-pedant" / "scripts" / "closeout_hook.py"
SPEC = importlib.util.spec_from_file_location("closeout_hook", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CloseoutHookTest(unittest.TestCase):
    def write_state(self, workspace: Path, **overrides: object) -> Path:
        path = workspace / ".azhou" / "super-repo-pedant" / "closeout-state.json"
        path.parent.mkdir(parents=True)
        value = {
            "schema_version": MODULE.SCHEMA_VERSION,
            "repo_root": str(workspace.resolve()),
            "session_id": "session-1",
            "status": "active",
            "progress": 1,
            "unrecorded_progress": False,
            "receipt_digest": None,
        }
        value.update(overrides)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def args(self, workspace: Path, runtime: Path, **overrides: object) -> Namespace:
        value = {
            "workspace": workspace,
            "state": ".azhou/super-repo-pedant/closeout-state.json",
            "event": "stop",
            "mode": "advisory",
            "format": "plain",
            "runtime_state_dir": workspace / ".azhou" / "super-repo-pedant" / "hooks",
            "block_cap": 3,
        }
        value.update(overrides)
        return Namespace(**value)

    def test_no_state_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output, diagnostic = MODULE.evaluate_event(self.args(workspace, workspace / "cache"), {})
            self.assertEqual("", output)
            self.assertFalse(diagnostic["state_loaded"])

    def test_advisory_output_is_fixed_and_contains_no_state_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.write_state(workspace, session_id="must-not-leak")
            output, diagnostic = MODULE.evaluate_event(self.args(workspace, workspace / "cache", format="codex"), {})
            self.assertEqual({"systemMessage": MODULE.REMINDER}, json.loads(output))
            self.assertTrue(MODULE.REMINDER.startswith("🟡 阿舟提醒｜"))
            self.assertNotIn("must-not-leak", output)
            self.assertEqual("advisory", diagnostic["action"])

    def test_symlinked_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            workspace = base / "workspace"
            workspace.mkdir()
            outside = base / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            state = workspace / ".azhou" / "super-repo-pedant" / "closeout-state.json"
            state.parent.mkdir(parents=True)
            state.symlink_to(outside)
            output, diagnostic = MODULE.evaluate_event(self.args(workspace, base / "cache"), {})
            self.assertEqual("", output)
            self.assertIn("state_symlink_rejected", diagnostic["state_errors"])

    def test_claude_gate_blocks_only_with_progress_and_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            workspace = base / "workspace"
            workspace.mkdir()
            state = self.write_state(workspace)
            args = self.args(workspace, base / "cache", mode="gate", format="claude")

            first, first_diagnostic = MODULE.evaluate_event(args, {"session_id": "session-1"})
            self.assertEqual("block", first_diagnostic["action"])
            self.assertEqual("block", json.loads(first)["decision"])

            second, second_diagnostic = MODULE.evaluate_event(args, {"session_id": "session-1"})
            self.assertEqual("gate_degraded_stall_or_cap", second_diagnostic["action"])
            self.assertIn("systemMessage", json.loads(second))

            value = json.loads(state.read_text(encoding="utf-8"))
            value["progress"] = 2
            state.write_text(json.dumps(value), encoding="utf-8")
            third, third_diagnostic = MODULE.evaluate_event(args, {"session_id": "session-1"})
            self.assertEqual("block", third_diagnostic["action"])
            self.assertEqual("block", json.loads(third)["decision"])

    def test_codex_gate_degrades_to_advisory_and_recursion_never_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.write_state(workspace)
            cache = workspace / "cache"
            codex, _ = MODULE.evaluate_event(self.args(workspace, cache, mode="gate", format="codex"), {})
            recursive, _ = MODULE.evaluate_event(
                self.args(workspace, cache, mode="gate", format="claude"),
                {"stop_hook_active": True},
            )
            self.assertIn("systemMessage", json.loads(codex))
            self.assertIn("systemMessage", json.loads(recursive))

    def test_precompact_only_reminds_for_unrecorded_active_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.write_state(workspace, unrecorded_progress=True)
            output, diagnostic = MODULE.evaluate_event(
                self.args(workspace, workspace / "cache", event="precompact"),
                {},
            )
            self.assertEqual(MODULE.PRECOMPACT_REMINDER, output)
            self.assertTrue(output.startswith("🧠 阿舟记忆检查｜"))
            self.assertEqual("advisory", diagnostic["action"])

    def test_one_shot_disable_is_silent(self) -> None:
        args = Namespace(max_input_bytes=1024)
        with mock.patch.dict(os.environ, {"REPO_PEDANT_DISABLED": "1"}):
            self.assertEqual(0, MODULE.cmd_event(args))

    def render_hooks(self, **overrides: object) -> dict:
        value: dict = {"format": "claude", "mode": "advisory", "python": None, "python_windows": None}
        value.update(overrides)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(0, MODULE.cmd_render_hooks(Namespace(**value)))
        return json.loads(buffer.getvalue())

    def test_render_hooks_binds_running_interpreter_without_stale_placeholders(self) -> None:
        for host_format in ("claude", "codex"):
            with self.subTest(format=host_format):
                fragment = self.render_hooks(format=host_format)
                precompact = fragment["hooks"]["PreCompact"][0]["hooks"][0]["command"]
                stop = fragment["hooks"]["Stop"][0]["hooks"][0]["command"]
                for command in (precompact, stop):
                    self.assertTrue(command.startswith(shlex.quote(sys.executable)))
                    self.assertNotIn("||", command)
                    self.assertNotIn("/absolute/path/to/repo-pedant", command)
                    self.assertIn("--workspace-from-input", command)
                self.assertEqual(30, fragment["hooks"]["Stop"][0]["hooks"][0]["timeout"])

    def test_render_hooks_gate_changes_only_the_stop_command(self) -> None:
        fragment = self.render_hooks(format="claude", mode="gate")
        precompact = fragment["hooks"]["PreCompact"][0]["hooks"][0]["command"]
        stop = fragment["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertIn("--mode advisory", precompact)
        self.assertIn("--mode gate", stop)

    def test_render_hooks_codex_keeps_status_message_and_optional_windows_command(self) -> None:
        fragment = self.render_hooks(format="codex", python_windows="C:\\Tools\\python.exe")
        precompact_hook = fragment["hooks"]["PreCompact"][0]["hooks"][0]
        self.assertIn("阿舟 · Super Repo Pedant", precompact_hook["statusMessage"])
        self.assertTrue(precompact_hook["commandWindows"].startswith('"C:\\Tools\\python.exe"'))
        plain = self.render_hooks(format="claude")
        self.assertNotIn("commandWindows", plain["hooks"]["PreCompact"][0]["hooks"][0])
        self.assertNotIn("statusMessage", plain["hooks"]["PreCompact"][0]["hooks"][0])

    def test_render_hooks_accepts_explicit_python_override(self) -> None:
        fragment = self.render_hooks(format="claude", python="/opt/py/bin/python3.11")
        stop = fragment["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertTrue(stop.startswith(shlex.quote("/opt/py/bin/python3.11")))


if __name__ == "__main__":
    unittest.main()

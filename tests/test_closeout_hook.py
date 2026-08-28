from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "repo-pedant" / "scripts" / "closeout_hook.py"
SPEC = importlib.util.spec_from_file_location("closeout_hook", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CloseoutHookTest(unittest.TestCase):
    def write_state(self, workspace: Path, **overrides: object) -> Path:
        path = workspace / ".azhou" / "repo-pedant" / "closeout-state.json"
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
            "state": ".azhou/repo-pedant/closeout-state.json",
            "event": "stop",
            "mode": "advisory",
            "format": "plain",
            "runtime_state_dir": workspace / ".azhou" / "repo-pedant" / "hooks",
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
            state = workspace / ".azhou" / "repo-pedant" / "closeout-state.json"
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


if __name__ == "__main__":
    unittest.main()

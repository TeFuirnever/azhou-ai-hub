from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "spec-relay" / "scripts" / "relay_state.py"


class SpecRelayStateTest(unittest.TestCase):
    def _packet(self, directory: str) -> Path:
        path = Path(directory) / "packet.html"
        path.write_text(
            '<!doctype html><html><body><main data-review-id="REQ-001">Requirement</main></body></html>',
            encoding="utf-8",
        )
        return path

    def _run(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            check=check,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def _init(self, path: Path) -> None:
        self._run(
            "init",
            str(path),
            "--source-spec",
            "docs/spec.md",
            "--source-revision",
            "abc123",
            "--review-goal",
            "approve scope",
            "--review-status",
            "in_review",
        )

    def test_init_embeds_portable_state_and_visible_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            os.chmod(path, 0o640)
            self._init(path)
            text = path.read_text(encoding="utf-8")
            self.assertIn('id="spec-relay-state"', text)
            self.assertIn('"schema": "spec-relay.html-state.v1"', text)
            self.assertIn('id="spec-relay-feedback-ledger"', text)
            self.assertNotIn("阿舟", text)
            self.assertNotIn("🦊", text)
            for brand_color in ("#FA9439", "#FEF9EB", "#6F3810", "#FAA67C"):
                self.assertNotIn(brand_color, text)
            self.assertNotIn("<table", text)
            self.assertIn("grid-template-columns:minmax(0,1fr)", text)
            self.assertIn("@media(max-width:36rem)", text)
            self.assertIn("width:min(calc(100% - 2rem),72rem)", text)
            self.assertIn("var(--sr-fg) 68%", text)
            self.assertEqual(0o640, path.stat().st_mode & 0o777)
            state = json.loads(self._run("show", str(path)).stdout)
            self.assertTrue(state["packet_id"])
            self.assertEqual(0, state["state_revision"])
            result = self._run("validate", str(path))
            self.assertIn("feedback=0 unresolved=0", result.stdout)

    def test_comment_and_selection_round_trip_inside_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            comment = "Keep </script><script>alert(1)</script> & explain why"
            self._run(
                "add-feedback",
                str(path),
                "--feedback-id",
                "FB-001",
                "--expected-revision",
                "0",
                "--target",
                "REQ-001",
                "--comment",
                comment,
                "--selection",
                "Requirement",
                "--disposition",
                "accepted",
                "--rationale",
                "clarifies scope",
                "--owner",
                "product",
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("\\u003c/script\\u003e", text)
            self.assertIn("&lt;/script&gt;", text)
            state = json.loads(self._run("show", str(path)).stdout)
            self.assertEqual(comment, state["feedback"][0]["comment"])
            self.assertEqual("Requirement", state["feedback"][0]["selection"])
            self.assertEqual(1, state["state_revision"])
            self._run("validate", str(path))

    def test_deferred_feedback_is_carried_as_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._run(
                "add-feedback",
                str(path),
                "--feedback-id",
                "FB-002",
                "--expected-revision",
                "0",
                "--target",
                "REQ-001",
                "--comment",
                "Confirm the latency budget",
                "--disposition",
                "deferred",
                "--rationale",
                "benchmark pending",
                "--owner",
                "platform",
            )
            state = json.loads(self._run("show", str(path)).stdout)
            self.assertEqual(["FB-002"], state["unresolved"])
            self.assertIn('data-feedback-id="FB-002"', path.read_text(encoding="utf-8"))

    def test_duplicate_feedback_id_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            arguments = (
                "add-feedback",
                str(path),
                "--feedback-id",
                "FB-001",
                "--expected-revision",
                "0",
                "--target",
                "REQ-001",
                "--comment",
                "First",
                "--disposition",
                "accepted",
                "--rationale",
                "valid",
            )
            self._run(*arguments)
            before = path.read_bytes()
            second_arguments = list(arguments)
            second_arguments[second_arguments.index("0")] = "1"
            result = self._run(*second_arguments, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("duplicate feedback_id", result.stderr)
            self.assertEqual(before, path.read_bytes())

    def test_unresolved_target_without_selection_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            before = path.read_bytes()
            result = self._run(
                "add-feedback",
                str(path),
                "--feedback-id",
                "FB-003",
                "--expected-revision",
                "0",
                "--target",
                "REQ-999",
                "--comment",
                "Where is this requirement?",
                "--disposition",
                "needs_clarification",
                "--rationale",
                "target missing",
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("target does not resolve", result.stderr)
            self.assertEqual(before, path.read_bytes())

    def test_feedback_can_be_resolved_without_losing_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._run(
                "add-feedback",
                str(path),
                "--feedback-id",
                "FB-004",
                "--expected-revision",
                "0",
                "--target",
                "REQ-001",
                "--comment",
                "Confirm the latency budget",
                "--disposition",
                "deferred",
                "--rationale",
                "benchmark pending",
                "--created-at",
                "2026-08-24T08:00:00Z",
            )
            self._run(
                "update-feedback",
                str(path),
                "--feedback-id",
                "FB-004",
                "--expected-revision",
                "1",
                "--disposition",
                "accepted",
                "--rationale",
                "benchmark passed at 120ms",
                "--source-change",
                "docs/spec.md#latency",
                "--owner",
                "platform",
                "--updated-at",
                "2026-08-24T09:00:00Z",
            )
            state = json.loads(self._run("show", str(path)).stdout)
            item = state["feedback"][0]
            self.assertEqual([], state["unresolved"])
            self.assertEqual(2, state["state_revision"])
            self.assertEqual("2026-08-24T08:00:00Z", item["created_at"])
            self.assertEqual("2026-08-24T09:00:00Z", item["updated_at"])
            text = path.read_text(encoding="utf-8")
            self.assertIn("spec-relay-feedback-status--accepted", text)
            self.assertIn("benchmark passed at 120ms", text)
            self._run("validate", str(path))

    def test_handoff_metadata_can_move_with_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._run(
                "update-metadata",
                str(path),
                "--expected-revision",
                "0",
                "--source-revision",
                "def456",
                "--review-status",
                "approved",
                "--handoff-to",
                "engineering",
                "--updated-at",
                "2026-08-24T10:00:00Z",
            )
            state = json.loads(self._run("show", str(path)).stdout)
            self.assertEqual("def456", state["source"]["revision"])
            self.assertEqual("approved", state["source"]["review_status"])
            self.assertEqual("engineering", state["handoff_to"])
            self.assertEqual(1, state["state_revision"])
            self._run("validate", str(path))

    def test_stale_revision_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._run(
                "update-metadata",
                str(path),
                "--expected-revision",
                "0",
                "--handoff-to",
                "product",
            )
            before = path.read_bytes()
            result = self._run(
                "update-metadata",
                str(path),
                "--expected-revision",
                "0",
                "--handoff-to",
                "engineering",
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("stale state revision", result.stderr)
            self.assertEqual(before, path.read_bytes())

    def test_visible_ledger_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace("Review feedback", "Altered feedback", 1), encoding="utf-8")
            result = self._run("validate", str(path), check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("exact projection", result.stderr)
            self._run(
                "refresh-ledger",
                str(path),
                "--expected-revision",
                "0",
                "--updated-at",
                "2026-08-24T11:00:00Z",
            )
            state = json.loads(self._run("show", str(path)).stdout)
            self.assertEqual(1, state["state_revision"])
            self.assertNotIn("Altered feedback", path.read_text(encoding="utf-8"))
            self._run("validate", str(path))


if __name__ == "__main__":
    unittest.main()

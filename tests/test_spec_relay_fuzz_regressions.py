"""Regression tests for crash classes found by scripts/fuzz_relay_state.py.

Each test is a minimal reproducer of one crash class: the parser must reject
the packet with its own contract error (exit 1, spec-relay: prefix, no
traceback) instead of an unhandled exception.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "spec-relay" / "scripts" / "relay_state.py"
STATE_BLOCK = '<script type="application/json" id="spec-relay-state">'


class SpecRelayFuzzRegressionTest(unittest.TestCase):
    def _packet(self, directory: str) -> Path:
        path = Path(directory) / "packet.html"
        path.write_text(
            '<!doctype html><html><body><main data-review-id="REQ-001">R</main></body></html>',
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

    def _rewrite_state_payload(self, path: Path, payload: str) -> None:
        text = path.read_text(encoding="utf-8")
        start = text.index(STATE_BLOCK) + len(STATE_BLOCK)
        end = text.index("</script>", start)
        path.write_text(text[:start] + "\n" + payload + text[end:], encoding="utf-8")

    def _assert_contract_rejection(self, path: Path, before: bytes) -> None:
        result = self._run("validate", str(path), check=False)
        self.assertEqual(1, result.returncode)
        self.assertTrue(result.stderr.startswith("spec-relay: "))
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(before, path.read_bytes())

    def test_deeply_nested_state_json_is_rejected_as_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._rewrite_state_payload(path, "[" * 200_000 + "]" * 200_000)
            before = path.read_bytes()
            self._assert_contract_rejection(path, before)

    def test_oversized_int_literal_is_rejected_as_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            self._rewrite_state_payload(path, '{"state_revision": ' + "9" * 5000 + "}")
            before = path.read_bytes()
            self._assert_contract_rejection(path, before)

    def test_non_dict_feedback_item_is_rejected_as_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            payload = json.dumps(
                {
                    "feedback": [True],
                    "handoff_to": "engineering",
                    "packet_id": "p",
                    "schema": "spec-relay.html-state.v1",
                    "source": {
                        "review_goal": "g",
                        "review_status": "in_review",
                        "revision": "abc123",
                        "spec": "docs/spec.md",
                    },
                    "state_revision": 1,
                    "unresolved": [],
                    "updated_at": "2026-08-24T08:00:00Z",
                }
            )
            self._rewrite_state_payload(path, payload)
            before = path.read_bytes()
            self._assert_contract_rejection(path, before)

    def test_unhashable_feedback_values_are_rejected_as_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._packet(directory)
            self._init(path)
            payload = json.dumps(
                {
                    "feedback": [
                        {
                            "comment": "c",
                            "created_at": "2026-08-24T08:00:00Z",
                            "disposition": ["deferred"],
                            "feedback_id": "FB-001",
                            "owner": "platform",
                            "rationale": "r",
                            "selection": "none",
                            "source_change": "none",
                            "target": {"x": 1},
                            "updated_at": "2026-08-24T08:00:00Z",
                        }
                    ],
                    "handoff_to": "engineering",
                    "packet_id": "p",
                    "schema": "spec-relay.html-state.v1",
                    "source": {
                        "review_goal": "g",
                        "review_status": ["in_review"],
                        "revision": "abc123",
                        "spec": "docs/spec.md",
                    },
                    "state_revision": 1,
                    "unresolved": [],
                    "updated_at": "2026-08-24T08:00:00Z",
                }
            )
            self._rewrite_state_payload(path, payload)
            before = path.read_bytes()
            self._assert_contract_rejection(path, before)


if __name__ == "__main__":
    unittest.main()

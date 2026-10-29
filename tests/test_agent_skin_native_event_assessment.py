from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import integration_startup_animation as animation


NATIVE_TEST_BUNDLE = Path("/Applications/Agent Skin.app")
NATIVE_EVENT_SAMPLES_ENV = "AZHOU_AGENT_SKIN_NATIVE_EVENT_SAMPLES"


class NativeEventAssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sample_root = os.environ.get(NATIVE_EVENT_SAMPLES_ENV)
        if not sample_root:
            raise unittest.SkipTest(f"set {NATIVE_EVENT_SAMPLES_ENV} to run native producer integration tests")
        cls.sample_root = Path(sample_root)
        if cls.sample_root.is_symlink() or not cls.sample_root.is_dir():
            raise AssertionError(f"native event sample directory is missing or unsafe: {cls.sample_root}")

    def assess(self, filename: str, mode: str, returncode: int) -> dict[str, object]:
        output = (self.sample_root / filename).read_text(encoding="utf-8")
        self.assertTrue(output.strip(), f"native producer sample is empty: {filename}")
        return animation.assess_execution(
            mode,
            {"returncode": returncode, "stdout": output, "stderr": ""},
            NATIVE_TEST_BUNDLE,
            verified_bundle={"path": str(NATIVE_TEST_BUNDLE), "version": "0.8.0", "build": "9"},
        )

    def test_native_ready_sample_is_assessed_as_ready(self) -> None:
        result = self.assess("startup-ready.jsonl", "launch", 0)
        self.assertEqual("startup-ready", result["status"])
        self.assertEqual("ready", result["startup"]["status"])
        self.assertEqual([], result["event_errors"])

    def test_native_hot_activation_sample_is_not_injection(self) -> None:
        result = self.assess("target-activated.jsonl", "launch", 0)
        self.assertEqual("activated", result["status"])
        self.assertEqual("not-attempted", result["startup"]["injection"])
        self.assertFalse(result["startup"]["installed"])

    def test_native_probe_sample_proves_target_identity(self) -> None:
        result = self.assess("probe-success.jsonl", "probe", 0)
        self.assertEqual("behavior-passed", result["status"])
        self.assertEqual("not-run", result["startup"]["status"])
        self.assertEqual("not-attempted", result["wallpaper_status"])
        self.assertEqual([], result["event_errors"])

    def test_native_probe_missing_target_is_not_proven(self) -> None:
        result = self.assess("probe-failure.jsonl", "probe", 0)
        self.assertEqual("behavior-not-proven", result["status"])
        self.assertEqual("not-run", result["startup"]["status"])
        self.assertEqual("not-attempted", result["wallpaper_status"])
        self.assertEqual([], result["event_errors"])

    def test_native_skip_sample_remains_distinct_from_ready(self) -> None:
        result = self.assess("startup-skipped.jsonl", "launch", 0)
        self.assertEqual("skipped", result["status"])
        self.assertEqual("skipped", result["startup"]["status"])
        self.assertEqual("skip", result["startup"]["completion"]["cause"])

    def test_native_interruption_sample_preserves_partial_progress(self) -> None:
        result = self.assess("startup-interrupted.jsonl", "launch", 2)
        self.assertEqual("partial", result["status"])
        self.assertEqual("interrupted", result["startup"]["status"])

    def test_native_port_failure_sample_keeps_its_reason(self) -> None:
        result = self.assess("startup-port-error.jsonl", "launch", 1)
        self.assertEqual("behavior-not-proven", result["status"])
        self.assertEqual("failed", result["startup"]["status"])
        self.assertEqual("listener-mismatch", result["startup"]["reason"])
        self.assertIn(result["startup"]["operation"], {"socket", "close-on-exec", "bind-loopback", "getsockname"})
        self.assertGreater(result["startup"]["errno"], 0)

    def test_native_smoke_sample_proves_independent_playback(self) -> None:
        result = self.assess("smoke.jsonl", "smoke", 0)
        self.assertEqual("behavior-passed", result["status"])
        self.assertEqual("completed", result["playback_completion"])
        self.assertEqual("not-run", result["startup"]["status"])
        self.assertEqual([], result["event_errors"])


if __name__ == "__main__":
    unittest.main()

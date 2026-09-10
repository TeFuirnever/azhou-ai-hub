from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "session-insights" / "benchmark.py"
CLI = ROOT / "skills" / "session-insights" / "scripts" / "session_insights.py"


def load_benchmark_module():
    # Load under a unique name: other test modules import their own benchmark
    # modules, and sys.modules must not collide.
    spec = importlib.util.spec_from_file_location("session_insights_benchmark", BENCHMARK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class SessionInsightsBenchmarkTest(unittest.TestCase):
    def test_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BENCHMARK), "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])


class SessionInsightsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = load_benchmark_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.work = Path(self.tempdir.name)
        self.store = self.work / "store"
        self.benchmark.build_store(self.store)

    def aggregate(self, *extra: str) -> dict:
        result = run_cli(
            "aggregate", "--harness", "all", "--store-root", str(self.store), *extra
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_aggregate_golden_spot_checks(self) -> None:
        aggregate = self.aggregate()
        claude = aggregate["harnesses"]["claude-code"]
        self.assertEqual("ok", claude["status"])
        self.assertEqual(4, claude["session_count"])
        self.assertEqual(3, claude["active_days"])
        self.assertEqual({"Read": 3, "Bash": 2, "Grep": 1}, claude["tool_calls"])
        self.assertEqual(2, claude["interruptions"])
        self.assertEqual(0.4, claude["interruption_rate"])
        self.assertEqual(2, claude["error_count"])
        self.assertEqual(1, claude["repeated_first_prompt_count"])
        self.assertEqual(1, claude["skipped_subagent_sessions"])
        self.assertEqual(1, claude["malformed_lines"])
        self.assertEqual("2026-09-09T18:05:00+00:00", claude["newest_session_at"])

    def test_window_and_cap_anchor_to_store_not_wall_clock(self) -> None:
        widened = self.aggregate("--days", "60")["harnesses"]["claude-code"]
        self.assertEqual(5, widened["session_count"])
        capped = self.aggregate("--max-sessions", "2")["harnesses"]["claude-code"]
        self.assertEqual(2, capped["session_count"])

    def test_fail_closed_holds_for_codex_and_zcode(self) -> None:
        aggregate = self.aggregate()
        self.assertEqual(
            ["codex unsupported", "zcode unsupported"], sorted(aggregate["holds"])
        )
        for harness in ("codex", "zcode"):
            section = aggregate["harnesses"][harness]
            self.assertEqual("unsupported", section["status"])
            self.assertNotIn("session_count", section)

    def test_detect_and_metadata_surfaces(self) -> None:
        detected = run_cli("detect", "--harness", "all", "--store-root", str(self.store))
        self.assertEqual(0, detected.returncode, detected.stderr)
        payload = json.loads(detected.stdout)
        self.assertEqual("available", payload["harnesses"]["claude-code"]["status"])
        self.assertEqual(6, payload["harnesses"]["claude-code"]["session_files"])
        self.assertEqual("unsupported", payload["harnesses"]["codex"]["status"])

        metadata = run_cli(
            "metadata", "--harness", "claude-code", "--store-root", str(self.store)
        )
        self.assertEqual(0, metadata.returncode, metadata.stderr)
        sessions = json.loads(metadata.stdout)["sessions"]
        self.assertEqual(5, len(sessions))
        for session in sessions:
            prompt = session.get("first_prompt")
            if prompt:
                self.assertLessEqual(len(prompt), 200)

    def test_report_privacy_and_fail_closed_rendering(self) -> None:
        aggregate_path = self.work / "aggregate.json"
        result = run_cli(
            "aggregate", "--harness", "all", "--store-root", str(self.store),
            "--out", str(aggregate_path),
        )
        self.assertEqual(0, result.returncode, result.stderr)

        report_path = self.work / "report.md"
        result = run_cli("report", "--aggregate", str(aggregate_path), "--out", str(report_path))
        self.assertEqual(0, result.returncode, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual("session-insights.report.v1", receipt["schema"])
        self.assertEqual("pass", receipt["status"])
        text = report_path.read_text(encoding="utf-8")
        home = str(Path.home())
        if home != "/":
            self.assertNotIn(home, text)
        for secret in self.benchmark.SEEDED_SECRETS:
            self.assertNotIn(secret, text)
        self.assertNotIn(self.benchmark.EXCERPT_SENTINEL, text)
        self.assertIn("codex unsupported", text)
        self.assertIn("zcode unsupported", text)

    def test_report_default_output_lands_in_azhou_namespace(self) -> None:
        aggregate_path = self.work / "aggregate.json"
        result = run_cli(
            "aggregate", "--harness", "claude-code", "--store-root", str(self.store),
            "--out", str(aggregate_path),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        result = run_cli(
            "report", "--aggregate", str(aggregate_path), cwd=self.work
        )
        self.assertEqual(0, result.returncode, result.stderr)
        expected = self.work / ".azhou" / "session-insights" / "report-2026-09-09.md"
        self.assertTrue(expected.is_file())

    def test_report_rejects_foreign_schema(self) -> None:
        bad = self.work / "bad.json"
        bad.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
        result = run_cli("report", "--aggregate", str(bad), "--out", str(self.work / "x.md"))
        self.assertEqual(1, result.returncode)
        self.assertIn("aggregate schema must be", result.stderr)


if __name__ == "__main__":
    unittest.main()

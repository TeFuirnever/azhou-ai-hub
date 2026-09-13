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

    def test_fail_closed_hold_for_zcode_only(self) -> None:
        aggregate = self.aggregate()
        self.assertEqual(["zcode unsupported"], aggregate["holds"])
        zcode = aggregate["harnesses"]["zcode"]
        self.assertEqual("unsupported", zcode["status"])
        self.assertNotIn("session_count", zcode)

    def test_codex_golden_spot_checks(self) -> None:
        aggregate = self.aggregate()
        codex = aggregate["harnesses"]["codex"]
        self.assertEqual("ok", codex["status"])
        self.assertEqual(2, codex["session_count"])
        self.assertEqual(2, codex["active_days"])
        self.assertEqual({"Read": 1, "browser.click": 1}, codex["tool_calls"])
        self.assertEqual(1, codex["interruptions"])
        self.assertEqual(0.3333, codex["interruption_rate"])
        self.assertEqual(0, codex["error_count"])
        self.assertEqual(4, codex["skipped_subagent_sessions"])
        self.assertEqual(7, codex["files_scanned"])
        self.assertEqual(1, codex["malformed_lines"])
        self.assertEqual({".../dev-alpha": 1, ".../dev-beta": 1}, codex["project_distribution"])
        widened = self.aggregate("--harness", "codex", "--days", "60")["harnesses"]["codex"]
        self.assertEqual(3, widened["session_count"])
        capped = self.aggregate("--harness", "codex", "--max-sessions", "1")["harnesses"]["codex"]
        self.assertEqual(1, capped["session_count"])

    def test_mixed_run_keeps_per_harness_accounting_separate(self) -> None:
        aggregate = self.aggregate()
        claude = aggregate["harnesses"]["claude-code"]
        codex = aggregate["harnesses"]["codex"]
        self.assertEqual("2026-09-09T18:05:00+00:00", claude["newest_session_at"])
        self.assertEqual("2026-09-06T20:16:00+00:00", codex["newest_session_at"])
        self.assertNotIn("browser.click", claude["tool_calls"])
        self.assertNotIn("Grep", codex["tool_calls"])

    def test_detect_and_metadata_surfaces(self) -> None:
        detected = run_cli("detect", "--harness", "all", "--store-root", str(self.store))
        self.assertEqual(0, detected.returncode, detected.stderr)
        payload = json.loads(detected.stdout)
        self.assertEqual("available", payload["harnesses"]["claude-code"]["status"])
        self.assertEqual(6, payload["harnesses"]["claude-code"]["session_files"])
        self.assertEqual("available", payload["harnesses"]["codex"]["status"])
        self.assertEqual(7, payload["harnesses"]["codex"]["session_files"])
        self.assertEqual("unsupported", payload["harnesses"]["zcode"]["status"])

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

        codex_metadata = run_cli(
            "metadata", "--harness", "codex", "--store-root", str(self.store)
        )
        self.assertEqual(0, codex_metadata.returncode, codex_metadata.stderr)
        codex_payload = json.loads(codex_metadata.stdout)
        self.assertEqual("ok", codex_payload["status"])
        # metadata lists every parsed session without window trimming
        self.assertEqual(3, len(codex_payload["sessions"]))
        for session in codex_payload["sessions"]:
            self.assertNotIn("cwd", session)
            self.assertNotIn("thread_source", session)

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
        self.assertIn("zcode unsupported", text)
        self.assertNotIn("codex unsupported", text)

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


class SessionInsightsRoastTest(unittest.TestCase):
    """Roast tone (#164): presentation layer only, machine values byte-identical."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.work = Path(self.tempdir.name)
        aggregate_path = self.work / "aggregate.json"
        result = run_cli(
            "aggregate", "--harness", "all", "--store-root",
            str(self.build_store()), "--out", str(aggregate_path),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.aggregate_path = aggregate_path

    def build_store(self) -> Path:
        benchmark = load_benchmark_module()
        store = self.work / "store"
        benchmark.build_store(store)
        return store

    def render(self, *extra: str) -> tuple[subprocess.CompletedProcess[str], str]:
        out = self.work / f"report-{len(list(self.work.glob('report-*.md')))}.md"
        result = run_cli("report", "--aggregate", str(self.aggregate_path), "--out", str(out), *extra)
        self.assertEqual(0, result.returncode, result.stderr)
        return result, out.read_text(encoding="utf-8")

    def body(self, text: str) -> str:
        lines = text.splitlines(keepends=True)
        receipt_at = next(
            (index for index, line in enumerate(lines) if line.startswith("## ") and line.rstrip("\n").endswith("Receipt")),
            len(lines),
        )
        return "".join(lines[:receipt_at])

    def test_roast_section_keeps_machine_body_byte_identical(self) -> None:
        _plain_receipt, plain_text = self.render()
        _roast_receipt, roast_text = self.render("--tone", "roast")
        plain_lines = plain_text.splitlines(keepends=True)
        roast_lines = roast_text.splitlines(keepends=True)
        roast_start = next(
            index for index, line in enumerate(roast_lines)
            if line.startswith("## ") and line.rstrip("\n").endswith("roast")
        )
        roast_end = next(
            (index for index in range(roast_start + 1, len(roast_lines)) if roast_lines[index].startswith("## ")),
            len(roast_lines),
        )
        stripped = "".join(roast_lines[:roast_start] + roast_lines[roast_end:])
        self.assertEqual(self.body(plain_text), self.body(stripped))
        self.assertFalse(
            any(line.startswith("## ") and line.rstrip("\n").endswith("roast") for line in plain_lines)
        )

    def test_every_roast_line_cites_a_statistic_from_the_machine_body(self) -> None:
        import re

        _plain_receipt, plain_text = self.render()
        _roast_receipt, roast_text = self.render("--tone", "roast")
        roast_lines = roast_text.splitlines(keepends=True)
        roast_start = next(
            index for index, line in enumerate(roast_lines)
            if line.startswith("## ") and line.rstrip("\n").endswith("roast")
        )
        roast_end = next(
            (index for index in range(roast_start + 1, len(roast_lines)) if roast_lines[index].startswith("## ")),
            len(roast_lines),
        )
        rendered = [line for line in roast_lines[roast_start:roast_end] if line.startswith("- ")]
        self.assertTrue(rendered)
        plain_body = self.body(plain_text)
        for roast_line in rendered:
            numbers = re.findall(r"\d+(?:\.\d+)?", roast_line)
            self.assertTrue(numbers, f"roast line cites no statistic: {roast_line}")
            for number in numbers:
                self.assertIn(number, plain_body)

    def test_roast_receipt_machine_fields_match_report_tone(self) -> None:
        plain_result, _plain_text = self.render()
        roast_result, _roast_text = self.render("--tone", "roast")
        machine = lambda receipt: {key: value for key, value in receipt.items() if key != "artifacts"}
        self.assertEqual(machine(json.loads(plain_result.stdout)), machine(json.loads(roast_result.stdout)))

    def test_invalid_tone_is_a_usage_error(self) -> None:
        result = run_cli(
            "report", "--aggregate", str(self.aggregate_path), "--out", str(self.work / "x.md"),
            "--tone", "scream",
        )
        self.assertEqual(2, result.returncode)


class SessionInsightsCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = load_benchmark_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.work = Path(self.tempdir.name)
        self.store = self.work / "store"
        self.benchmark.build_store(self.store)
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()

    @property
    def cache_file(self) -> Path:
        return self.cwd / ".azhou" / "session-insights" / "metadata-cache.json"

    def aggregate(self, *extra: str) -> dict:
        result = run_cli(
            "aggregate", "--harness", "claude-code", "--store-root", str(self.store),
            *extra, cwd=self.cwd,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def claude(self, payload: dict) -> dict:
        return payload["harnesses"]["claude-code"]

    def test_warm_and_deleted_cache_match_cold_output(self) -> None:
        cold = self.aggregate()
        self.assertTrue(self.cache_file.is_file())
        warm = self.aggregate()
        self.assertEqual(cold, warm)
        self.cache_file.unlink()
        rebuilt = self.aggregate()
        self.assertEqual(cold, rebuilt)

    def test_corrupt_cache_is_rebuilt(self) -> None:
        cold = self.aggregate()
        self.cache_file.write_text("{corrupt", encoding="utf-8")
        rebuilt = self.aggregate()
        self.assertEqual(cold, rebuilt)
        self.assertEqual(
            "session-insights.metadata-cache.v1", json.loads(self.cache_file.read_text(encoding="utf-8"))["schema"]
        )

    def test_cache_carries_no_transcript_text(self) -> None:
        self.aggregate()
        blob = self.cache_file.read_text(encoding="utf-8")
        self.assertNotIn('"first_prompt"', blob)
        needles = [
            self.benchmark.FIRST_PROMPT_SHARED,
            self.benchmark.EXCERPT_SENTINEL,
            *self.benchmark.SEEDED_SECRETS,
            self.benchmark.ALPHA,
            self.benchmark.BETA,
        ]
        home = str(Path.home())
        if home != "/":
            needles.append(home)
        for needle in needles:
            self.assertNotIn(needle, blob)

    def test_changed_added_removed_sessions_rescan(self) -> None:
        base = self.claude(self.aggregate())

        alpha = self.store / "projects" / self.benchmark.ALPHA
        s1 = alpha / f"{self.benchmark.S1}.jsonl"
        with s1.open("a", encoding="utf-8") as handle:
            handle.write(
                self.benchmark.line(
                    {
                        "type": "user",
                        "timestamp": "2026-09-08T10:04:00Z",
                        "message": {"role": "user", "content": "cache invalidation probe"},
                    }
                )
                + "\n"
            )
        changed = self.claude(self.aggregate())
        self.assertEqual(base["turns"] + 1, changed["turns"])

        s7_id = "77777777-7777-7777-7777-777777777777"
        added_file = self.store / "projects" / self.benchmark.BETA / f"{s7_id}.jsonl"
        added_file.write_text(
            self.benchmark.session_lines(
                s7_id,
                [
                    {
                        "type": "user",
                        "timestamp": "2026-09-08T12:00:00Z",
                        "message": {"role": "user", "content": "added session probe"},
                    }
                ],
            ),
            encoding="utf-8",
        )
        added = self.claude(self.aggregate())
        self.assertEqual(base["session_count"] + 1, added["session_count"])

        (alpha / f"{self.benchmark.S4}.jsonl").unlink()
        removed = self.claude(self.aggregate())
        self.assertEqual(base["session_count"], removed["session_count"])

    def test_excerpt_runs_bypass_cache(self) -> None:
        payload = self.aggregate("--include-excerpts")
        self.assertFalse(self.cache_file.exists())
        excerpts = self.claude(payload)["excerpts"]
        self.assertTrue(
            any(self.benchmark.FIRST_PROMPT_SHARED in entry["first_prompt"] for entry in excerpts)
        )


if __name__ == "__main__":
    unittest.main()

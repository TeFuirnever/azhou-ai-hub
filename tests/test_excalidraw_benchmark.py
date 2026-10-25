from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "super-excalidraw-diagram" / "ordinary-model-floor" / "benchmark.py"
REFERENCE = BENCHMARK.parent / "fixtures" / "reference"


class ExcalidrawBenchmarkTest(unittest.TestCase):
    def test_external_benchmark_wires_to_runtime_skill(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BENCHMARK), "check"],
            cwd=ROOT,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("5 cases", result.stdout)

    def test_setup_is_harness_neutral_and_preview_first(self) -> None:
        setup = (ROOT / "skills" / "super-excalidraw-diagram" / "references" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("uv sync --frozen --dry-run", setup)
        self.assertIn("npm ci --dry-run --ignore-scripts", setup)
        self.assertIn("pipx install uv", setup)
        self.assertNotIn("~/.agents", setup)
        self.assertNotIn("~/.claude", setup)


class OrdinaryModelFloorEvidenceGateTest(unittest.TestCase):
    """verify and report must share one first-pass criterion and an exact matrix."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.work = Path(self.tempdir.name)
        self.reference_run = json.loads(
            (REFERENCE / "reference.run.json").read_text(encoding="utf-8")
        )

    def verify(self, run_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(BENCHMARK), "verify",
                "--case", str(BENCHMARK.parent / "cases" / "layered-architecture.case.json"),
                "--candidate", str(REFERENCE / "reference.architecture.excalidraw"),
                "--run", str(run_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False,
        )

    def write_run(self, name: str, mutate) -> Path:
        run = json.loads(json.dumps(self.reference_run))
        mutate(run)
        path = self.work / name
        path.write_text(json.dumps(run), encoding="utf-8")
        return path

    def test_verify_accepts_the_clean_reference_review(self) -> None:
        result = self.verify(self.write_run("clean.run.json", lambda run: None))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["firstPassUsable"])

    def test_verify_rejects_defects_on_a_passed_review(self) -> None:
        run = self.write_run(
            "defects.run.json",
            lambda run: run["visual_review"].update({"defects": ["synthetic clipped label"]}),
        )
        result = self.verify(run)
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)["firstPassUsable"])

    def test_verify_rejects_unresolved_holds_on_a_passed_review(self) -> None:
        run = self.write_run(
            "holds.run.json",
            lambda run: run["visual_review"].update({"holds": ["synthetic unresolved visual concern"]}),
        )
        result = self.verify(run)
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)["firstPassUsable"])

    def test_verify_and_report_agree_on_blank_string_holds(self) -> None:
        # A raw [""] hold is filtered out of the receipt's serialized holds;
        # the criterion must judge the normalized data so the receipt verify
        # rejected can never be counted usable by report.
        run = self.write_run("blank-holds.run.json", lambda r: r["visual_review"].update({"holds": [""]}))
        result = self.verify(run)
        self.assertEqual(1, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt["firstPassUsable"])
        payload = self.run_report([receipt], [receipt["case_id"]])
        self.assertEqual(0, payload["firstPassUsable"])
        self.assertEqual(1, payload["failureClusters"]["visual-review"])

    def run_report(self, rows: list[dict], case_ids: list[str]) -> dict:
        manifest = self.work / "manifest.json"
        results = self.work / "results.jsonl"
        manifest.write_text(json.dumps({"cases": [{"id": case_id} for case_id in case_ids]}), encoding="utf-8")
        results.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(BENCHMARK), "report",
                "--results", str(results), "--manifest", str(manifest),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def receipt(case_id: str, attempt: int = 1, **visual_review) -> dict:
        review = {"status": "passed", "reviewer": "named-reviewer", "defects": [], "holds": []}
        review.update(visual_review)
        return {
            "schema": 1,
            "case_id": case_id,
            "attempt": attempt,
            "status": "pass",
            "gates": {
                "semantic": {"pass": True},
                "deterministic": {"pass": True},
                "visual_review": review,
            },
        }

    def test_report_applies_the_same_visual_review_criterion_as_verify(self) -> None:
        payload = self.run_report(
            [
                self.receipt("case-a"),
                self.receipt("case-b", defects=["clipped label"]),
                self.receipt("case-c", holds=["unresolved concern"]),
                self.receipt("case-d", reviewer=""),
            ],
            ["case-a", "case-b", "case-c", "case-d"],
        )
        self.assertEqual(1, payload["firstPassUsable"])
        self.assertEqual(3, payload["failureClusters"]["visual-review"])

    def test_report_matrix_requires_exact_attempt1_coverage(self) -> None:
        case_ids = [f"case-{index}" for index in range(5)]
        rows = [self.receipt(case_id, attempt=2) for case_id in case_ids]
        rows.append(self.receipt("not-in-the-suite"))
        payload = self.run_report(rows, case_ids)
        self.assertFalse(payload["evidenceEligible"])
        self.assertEqual(0, payload["firstPassUsable"])

    def test_report_rejects_boolean_attempt_values(self) -> None:
        # JSON true compares equal to 1; a boolean attempt row must count as a
        # later attempt, never as attempt-1 evidence (review follow-up on
        # #311).
        case_ids = [f"case-{index}" for index in range(5)]
        rows = [self.receipt(case_id, attempt=True) for case_id in case_ids]
        payload = self.run_report(rows, case_ids)
        self.assertFalse(payload["evidenceEligible"])
        self.assertEqual(0, payload["firstPassUsable"])

    def test_report_accepts_an_exact_attempt1_matrix(self) -> None:
        case_ids = [f"case-{index}" for index in range(5)]
        payload = self.run_report([self.receipt(case_id) for case_id in case_ids], case_ids)
        self.assertTrue(payload["evidenceEligible"])
        self.assertEqual(5, payload["firstPassUsable"])

    def test_reviewer_must_be_a_real_string(self) -> None:
        # JSON null/false/0/[] all stringify to non-empty words; an unnamed
        # review can never count as identified (review follow-up on #311).
        for bad in (None, False, 0, [], {}):
            with self.subTest(reviewer=bad):
                run = self.write_run(
                    "unnamed.run.json",
                    lambda r: r["visual_review"].update({"reviewer": bad}),
                )
                result = self.verify(run)
                self.assertEqual(1, result.returncode)
                self.assertFalse(json.loads(result.stdout)["firstPassUsable"])
                payload = self.run_report([self.receipt("case-a", reviewer=bad)], ["case-a"])
                self.assertEqual(0, payload["firstPassUsable"])
                self.assertEqual(1, payload["failureClusters"]["visual-review"])


if __name__ == "__main__":
    unittest.main()

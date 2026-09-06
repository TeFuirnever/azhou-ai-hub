from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "prose-standard" / "scripts" / "recall_batteries.py"
FIXTURES = ROOT / "tests" / "fixtures" / "prose-standard"

# Findings inside the keep corpus that are the documented false-positive
# families (probe over-match is by design; these stay judged-keep).
DOCUMENTED_FALSE_POSITIVES = {
    ("external-standard.md", "stamp"),
    ("external-standard.md", "draft-section"),
    ("runtime-lifecycle.md", "narration"),
}


class RecallBatteriesTest(unittest.TestCase):
    def run_probe(self, *arguments: str) -> tuple[int, dict]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout)

    def test_help_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode)

    def test_every_leakage_fixture_hits_at_least_one_probe(self) -> None:
        code, report = self.run_probe(str(FIXTURES / "leakage"))
        self.assertEqual(1, code)
        self.assertEqual("fail", report["status"])
        hit_files = {Path(f["path"]).name for f in report["findings"]}
        for fixture in sorted((FIXTURES / "leakage").glob("*.md")):
            self.assertIn(fixture.name, hit_files, fixture.name)

    def test_keep_corpus_hits_only_documented_false_positives(self) -> None:
        code, report = self.run_probe(str(FIXTURES / "keep"))
        self.assertEqual(1, code)
        observed = {(Path(f["path"]).name, f["probe"]) for f in report["findings"]}
        self.assertEqual(DOCUMENTED_FALSE_POSITIVES, observed)

    def test_missing_path_is_a_usage_error(self) -> None:
        code, report = self.run_probe(str(FIXTURES / "does-not-exist"))
        self.assertEqual(2, code)
        self.assertEqual("usage-error", report["status"])

    def test_clean_scope_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "plain.md"
            sample.write_text("The verifier runs the full gate before any completion claim.\n", encoding="utf-8")
            code, report = self.run_probe(str(sample))
            self.assertEqual(0, code)
            self.assertEqual("pass", report["status"])
            self.assertEqual([], report["findings"])


if __name__ == "__main__":
    unittest.main()

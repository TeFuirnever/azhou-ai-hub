from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]


class SuperCavemanLifecycleBenchmarkTest(unittest.TestCase):
    def _benchmark(self):
        sys.path.insert(0, str(ROOT / "benchmarks" / "super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        return benchmark

    def test_spec_is_valid_and_bounded(self) -> None:
        spec = json.loads(
            (ROOT / "benchmarks" / "super-caveman" / "lifecycle-cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual("super-caveman-lifecycle-cases.v1", spec["schema"])
        self.assertTrue((ROOT / spec["adapter"]).is_file())
        ids = [case["id"] for case in spec["cases"]]
        self.assertEqual(len(ids), len(set(ids)), "case ids must be unique")
        for case in spec["cases"]:
            with self.subTest(case=case["id"]):
                self.assertLessEqual(len(case["event"]["command"]) + 0, 32)
                self.assertIsInstance(case["expect_contains"], list)
                self.assertIsInstance(case["expect_absent"], list)

        budgets = spec["budgets"]
        self.assertEqual(10000, budgets["capsule_max_chars"])
        self.assertEqual(1024, budgets["prompt_max_chars"])
        self.assertEqual(5, budgets["timeout_seconds"])

    def test_lifecycle_runner_passes_on_current_tree(self) -> None:
        benchmark = self._benchmark()
        self.assertEqual([], benchmark.lifecycle_errors())

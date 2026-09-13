from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SPEC = Path(__file__).resolve().parents[1] / "scripts" / "regression_rate.py"
spec = importlib.util.spec_from_file_location("regression_rate", SPEC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ClassifyTest(unittest.TestCase):
    def test_behavior_commit_without_tests(self) -> None:
        self.assertEqual((True, False), module.classify(["skills/eli5/SKILL.md"]))

    def test_behavior_commit_with_tests(self) -> None:
        self.assertEqual(
            (True, True),
            module.classify(["scripts/azhou_hub.py", "tests/test_azhou_hub.py"]),
        )

    def test_tests_only_commit_is_not_behavior(self) -> None:
        self.assertEqual((False, True), module.classify(["tests/test_azhou_hub.py"]))

    def test_docs_only_commit_is_not_behavior(self) -> None:
        self.assertEqual((False, False), module.classify(["docs/installation.md"]))

    def test_skill_markdown_is_behavior(self) -> None:
        # SKILL.md files are the skill surface: they count as behavior.
        self.assertEqual((True, False), module.classify(["skills/eli5/SKILL.md"]))
        self.assertTrue(module.classify(["skills/eli5/SKILL.md"])[0])


class RateTest(unittest.TestCase):
    def test_ratio_over_behavior_commits_only(self) -> None:
        result = module.rate([
            ["skills/eli5/SKILL.md", "tests/test_eli5.py"],
            ["skills/ask-azhou/SKILL.md"],
            ["docs/installation.md"],
        ])
        self.assertEqual(2, result["behavior_commits"])
        self.assertEqual(1, result["carrying_tests"])
        self.assertEqual(0.5, result["regression_rate"])

    def test_empty_window_reports_na(self) -> None:
        self.assertEqual(
            {"behavior_commits": 0, "carrying_tests": 0, "regression_rate": "n/a"},
            module.rate([]),
        )


if __name__ == "__main__":
    unittest.main()

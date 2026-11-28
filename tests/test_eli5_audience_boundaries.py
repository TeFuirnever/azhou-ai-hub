"""Boundary contracts for the ELI5 artifact's visible-word budgets."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "super-eli5" / "scripts" / "check_audience.py"
SPEC = importlib.util.spec_from_file_location("eli5_audience_boundaries", SCRIPT)
AUDIENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIENCE)


def artifact(body):
    return f"<html><head>{AUDIENCE.AUDIENCE_MARKER}</head><body>{body}</body></html>"


class Eli5AudienceBoundaryTest(unittest.TestCase):
    def assert_only_violation(self, body, words, check=None):
        verdict = AUDIENCE.assert_audience(artifact(body))
        self.assertEqual(words, verdict["artifact_checks"]["total_words"])
        self.assertEqual(check is None, verdict["pass"])
        self.assertEqual([] if check is None else [check], [item["check"] for item in verdict["violations"]])

    def test_sentence_budget_accepts_25_words_and_rejects_26(self):
        for words in (25, 26):
            with self.subTest(words=words):
                self.assert_only_violation("<p>" + "word " * words + "</p>", words,
                                           None if words == 25 else "sentence_word_budget")

    def test_block_budget_accepts_45_words_and_rejects_46_without_long_sentences(self):
        for words in (45, 46):
            with self.subTest(words=words):
                body = "<p>" + "word " * 22 + ". " + "word " * (words - 22) + ".</p>"
                self.assert_only_violation(body, words, None if words == 45 else "block_word_budget")

    def test_total_budget_accepts_350_words_and_rejects_351_without_dense_blocks(self):
        body = ("<p>" + "word " * 25 + ".</p>") * 14
        self.assert_only_violation(body, 350)
        self.assert_only_violation(body + "<p>extra</p>", 351, "total_word_budget")

    def test_script_style_and_comment_text_do_not_consume_visible_word_budgets(self):
        hidden_words = "implementation " * 400
        body = (f"<style>/* {hidden_words} */</style>"
                f'<script>const description = "{hidden_words}";</script>'
                f"<!-- {hidden_words} --><p>Two words.</p>")
        self.assert_only_violation(body, 2)


if __name__ == "__main__":
    unittest.main()

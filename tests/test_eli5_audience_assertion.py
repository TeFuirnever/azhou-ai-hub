"""Deterministic audience read-back assertion for the eli5 artifact (u14).

Covers three layers:

1. behavior - the assertion script passes compliant artifacts and fails
   named non-compliance with deterministic violations and exit codes;
2. determinism - identical input produces an identical verdict;
3. wiring - the SKILL.md receipt contract (eli5.receipt.v2), the cited
   script path, and the documented budgets match the script constants, so
   the receipt judgment layer cannot drift from the enforcement.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "eli5"
SCRIPT = PACKAGE / "scripts" / "check_audience.py"
SKILL_TEXT = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")

_SPEC = importlib.util.spec_from_file_location("eli5_check_audience", SCRIPT)
MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MODULE)


def _marker_line() -> str:
    return MODULE.AUDIENCE_MARKER


COMPLIANT_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{_marker_line()}
<title>How a toaster works</title>
</head>
<body>
<h1>How a toaster works</h1>
<p>Electricity flows through a hot wire.</p>
<p>The wire glows and toasts the bread.</p>
<svg width="80" height="40" role="img" aria-label="wire"><text x="4" y="8">hot wire</text></svg>
</body>
</html>
"""

COMPLIANT_CJK_HTML = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
{_marker_line()}
<title>烤面包机怎么工作</title>
</head>
<body>
<h1>烤面包机怎么工作</h1>
<p>电流流过发热的丝。</p>
<p>丝热了，面包就烤好。</p>
</body>
</html>
"""


def run_assertion(html: str | None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "artifact.html"
        if html is not None:
            path.write_text(html, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )


def violation_checks(result: subprocess.CompletedProcess[str]) -> list[str]:
    verdict = json.loads(result.stdout)
    return [item["check"] for item in verdict["violations"]]


class AudienceAssertionBehaviorTest(unittest.TestCase):
    def test_compliant_artifact_passes(self) -> None:
        result = run_assertion(COMPLIANT_HTML)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        verdict = json.loads(result.stdout)
        self.assertTrue(verdict["pass"])
        self.assertEqual([], verdict["violations"])
        self.assertEqual(MODULE.SCHEMA, verdict["schema"])
        self.assertTrue(verdict["artifact_checks"]["audience_marker"])
        self.assertTrue(verdict["artifact_checks"]["html_root"])

    def test_compliant_cjk_artifact_passes(self) -> None:
        result = run_assertion(COMPLIANT_CJK_HTML)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        verdict = json.loads(result.stdout)
        self.assertTrue(verdict["pass"])
        self.assertEqual([], verdict["violations"])

    def test_verdict_is_deterministic(self) -> None:
        first = run_assertion(COMPLIANT_HTML)
        second = run_assertion(COMPLIANT_HTML)
        self.assertEqual(0, first.returncode)
        self.assertEqual(first.returncode, second.returncode)
        first_verdict = json.loads(first.stdout)
        second_verdict = json.loads(second.stdout)
        # The artifact field carries each run's temp path; the verdict itself
        # (checks, schema, violations) must be identical across runs.
        first_verdict.pop("artifact")
        second_verdict.pop("artifact")
        self.assertEqual(first_verdict, second_verdict)

    def test_missing_audience_marker_is_named(self) -> None:
        stripped = COMPLIANT_HTML.replace(f"{_marker_line()}\n", "")
        result = run_assertion(stripped)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        verdict = json.loads(result.stdout)
        self.assertFalse(verdict["pass"])
        self.assertEqual(["audience_marker"], violation_checks(result))
        self.assertIn(MODULE.AUDIENCE_MARKER, verdict["violations"][0]["detail"])

    def test_missing_html_root_is_named(self) -> None:
        result = run_assertion(f"{_marker_line()}\n<p>Short text.</p>")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("html_root", violation_checks(result))

    def test_oversized_block_is_named(self) -> None:
        dense = COMPLIANT_HTML.replace(
            "<p>Electricity flows through a hot wire.</p>",
            f"<p>{'word ' * 60}</p>",
        )
        result = run_assertion(dense)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        checks = violation_checks(result)
        self.assertIn("block_word_budget", checks)
        verdict = json.loads(result.stdout)
        detail = next(
            item["detail"] for item in verdict["violations"] if item["check"] == "block_word_budget"
        )
        self.assertIn("60 words", detail)
        self.assertIn(str(MODULE.MAX_WORDS_PER_BLOCK), detail)

    def test_oversized_sentence_within_block_budget_is_named(self) -> None:
        sentence_only = COMPLIANT_HTML.replace(
            "<p>Electricity flows through a hot wire.</p>",
            f"<p>This is fine. {'extra ' * 29}end</p>",
        )
        result = run_assertion(sentence_only)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        checks = violation_checks(result)
        self.assertIn("sentence_word_budget", checks)
        self.assertNotIn("block_word_budget", checks)

    def test_total_word_budget_alone_is_named(self) -> None:
        block = " ".join(["w"] * 20)  # 20 words
        blocks = "".join(f"<p>{block}. {block}.</p>\n" for _ in range(10))
        body = f"<html><head>{_marker_line()}</head><body>\n{blocks}</body></html>"
        result = run_assertion(body)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        checks = violation_checks(result)
        self.assertIn("total_word_budget", checks)
        self.assertNotIn("block_word_budget", checks)
        self.assertNotIn("sentence_word_budget", checks)
        verdict = json.loads(result.stdout)
        self.assertGreater(verdict["artifact_checks"]["total_words"], MODULE.MAX_TOTAL_WORDS)

    def test_cjk_oversized_sentence_is_named(self) -> None:
        long_sentence = "电流从插座经过开关流到电阻丝于是电阻丝变得非常热面包就被烤好了"
        dense = COMPLIANT_CJK_HTML.replace(
            "<p>电流流过发热的丝。</p>", f"<p>{long_sentence}</p>"
        )
        result = run_assertion(dense)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        checks = violation_checks(result)
        self.assertIn("sentence_word_budget", checks)
        self.assertNotIn("block_word_budget", checks)

    def test_unreadable_artifact_fails_closed(self) -> None:
        result = run_assertion(None)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        verdict = json.loads(result.stdout)
        self.assertEqual(MODULE.SCHEMA, verdict["schema"])
        self.assertIn("error", verdict)
        self.assertIn("cannot read artifact", result.stderr)

    def test_svg_labels_count_toward_total_budget_only(self) -> None:
        labels = "".join(f"<text x='4' y='{index}'>{'label ' * 40}</text>" for index in range(12))
        svg_artifact = (
            f"<html><head>{_marker_line()}</head><body>"
            f"<svg>{labels}</svg><p>Short text.</p></body></html>"
        )
        result = run_assertion(svg_artifact)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        checks = violation_checks(result)
        self.assertIn("total_word_budget", checks)
        self.assertNotIn("block_word_budget", checks)
        self.assertNotIn("sentence_word_budget", checks)


class AudienceAssertionWiringTest(unittest.TestCase):
    def test_receipt_contract_is_v2_with_audience_field(self) -> None:
        self.assertIn("eli5.receipt.v2", SKILL_TEXT)
        self.assertNotIn("eli5.receipt.v1", SKILL_TEXT)
        self.assertIn("- audience_assertion: pass | fail", SKILL_TEXT)
        self.assertIn("scripts/check_audience.py", SKILL_TEXT)

    def test_cited_script_exists(self) -> None:
        cited = re.findall(r"scripts/check_audience\.py", SKILL_TEXT)
        self.assertTrue(cited)
        self.assertTrue(SCRIPT.is_file(), str(SCRIPT))

    def test_documented_budgets_match_script_constants(self) -> None:
        for constant in (
            MODULE.MAX_TOTAL_WORDS,
            MODULE.MAX_WORDS_PER_BLOCK,
            MODULE.MAX_WORDS_PER_SENTENCE,
        ):
            self.assertIn(str(constant), SKILL_TEXT)

    def test_documented_marker_matches_script_constant(self) -> None:
        self.assertIn(MODULE.AUDIENCE_MARKER, SKILL_TEXT)

    def test_receipt_judgment_rule_blocks_noncompliant_delivery(self) -> None:
        self.assertIn("never deliver with a failing assertion", SKILL_TEXT)
        self.assertIn("status: hold", SKILL_TEXT)
        self.assertIn("`status: pass` requires both a successful read-back and `audience_assertion: pass`", SKILL_TEXT)

    def test_provenance_records_the_assertion_as_an_addition(self) -> None:
        provenance = (PACKAGE / "references" / "provenance.md").read_text(encoding="utf-8")
        self.assertIn("scripts/check_audience.py", provenance)
        compatibility = (PACKAGE / "references" / "upstream-compatibility.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("deterministic audience read-back assertion", compatibility)


if __name__ == "__main__":
    unittest.main()

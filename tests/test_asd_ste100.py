"""Integrity suite for the asd-ste100 canonical skill.

Pins the vendored upstream baseline (TeFuirnever/asd-ste100-skill at the
immutable provenance commit), the hub wrapper layer (frontmatter contract,
brand protocol, receipt) and the deterministic linter behavior the receipt
depends on.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.check_repository import INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "asd-ste100"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_COMMIT = "32511c6992ecb5f1971e46a2943f2e6adceedafe"
UPSTREAM_SKILL_SHA256 = "39940a0db3d185416edfd757eff4c971006d8f59ad39715295b150b552344342"
UPSTREAM_LINT_SHA256 = "1b97b2d22ba50cde10654db56e1b98adf96d250dd3c8f693f8a81361b1084e85"
LOCAL_LINT_SHA256 = "1cfec74cfd45a472fe92855fb14580026eec440a0fdacc1effcebb1a7c35393d"
PINNED_SHA256 = {
    "scripts/ste-lint.py": LOCAL_LINT_SHA256,
    "references/writing-rules.md": "4b92c86bf803f9f54e069767d34dc7356fbb95fb52a3f28476093917c608c102",
    "examples/before-after.md": "d7bf2b4a390f1997a18790b243dd4c0670018d0d4d5183ec8ed44cbbf282bc52",
    "examples/linter-edge-cases.md": "b6cc08af876014453b0c72d26ee4bfaeed1e9a154b5046947392752911ce1774",
}

VIOLATING_TEXT = (
    "We have received your request and it is important to note that the "
    "seamless, robust configuration file upload functionality for the "
    "high pressure fuel pump inlet valve assembly may potentially help to "
    "improve things; reach out to the team to spin up the analysis.\n"
)
REWRITTEN_TEXT = (
    "We received your request. The configuration file upload may have "
    "failed. Contact the team. Start the analysis.\n"
)


class AsdSte100PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("asd-ste100", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)

    def test_upstream_description_baseline_is_retained(self) -> None:
        self.assertIn(
            "Use when English text must be parsed without a human to resolve ambiguity",
            self.text,
        )
        self.assertIn("Not for creative or marketing copy", self.text)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/asd-ste100/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.text)
        self.assertIn("raw evidence", self.text)
        self.assertIn("asd-ste100.receipt.v1", self.text)

    def test_provenance_pins_the_locked_upstream(self) -> None:
        provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_SKILL_SHA256, provenance)
        self.assertIn(UPSTREAM_LINT_SHA256, provenance)
        self.assertIn(LOCAL_LINT_SHA256, provenance)
        self.assertIsNotNone(re.search(r"^Classification: `faithful`", provenance, re.MULTILINE))
        self.assertIn("Skill-standard §2.3", provenance)
        self.assertIn("not free to redistribute", provenance)

    def test_local_linter_patches_are_recorded(self) -> None:
        compat = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        self.assertIn("locally patched", compat)
        self.assertIn("hard-wrapped", compat)
        self.assertIn("inflection", compat)

    def test_compatibility_map_preserves_capability_rows(self) -> None:
        compat = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, compat)
        self.assertIn("preserved byte-identical", compat)
        self.assertIn("preserved verbatim", compat)
        self.assertIn("A future removal or replacement needs", compat)

    def test_vendored_files_match_the_pinned_upstream_bytes(self) -> None:
        for relative, expected in PINNED_SHA256.items():
            data = (SKILL_DIR / relative).read_bytes()
            self.assertEqual(expected, hashlib.sha256(data).hexdigest(), relative)

    def test_license_copy_is_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "asd-ste100-skill-MIT.txt").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Dustin Yuchen Teng", license_text)
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Dustin Yuchen Teng", notices)
        self.assertIn("asd-ste100-skill-MIT.txt", notices)


class AsdSte100LinterTest(unittest.TestCase):
    def run_lint(self, *args: str, text: str | None = None) -> subprocess.CompletedProcess[bytes]:
        command = [sys.executable, str(SKILL_DIR / "scripts" / "ste-lint.py"), *args]
        if text is None:
            return subprocess.run(command, capture_output=True, check=False)
        return subprocess.run(command, input=text.encode("utf-8"), capture_output=True, check=False)

    def test_selftest_passes(self) -> None:
        result = self.run_lint("--selftest")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_violating_text_exits_one_and_the_rewrite_exits_zero(self) -> None:
        violating = self.run_lint(text=VIOLATING_TEXT)
        self.assertEqual(1, violating.returncode, violating.stdout + violating.stderr)
        rewritten = self.run_lint(text=REWRITTEN_TEXT)
        self.assertEqual(0, rewritten.returncode, rewritten.stdout + rewritten.stderr)

    def test_baseline_flag_tolerates_named_violations(self) -> None:
        result = self.run_lint("--baseline", "50", text=VIOLATING_TEXT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_json_report_is_structured(self) -> None:
        result = self.run_lint("--json", text=VIOLATING_TEXT)
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertIsInstance(payload, dict)
        for key in ("violations", "count", "hard_count", "baseline", "words"):
            self.assertIn(key, payload)
        self.assertGreater(payload["hard_count"], 0)

    def test_hedges_and_modality_are_never_flagged(self) -> None:
        result = self.run_lint(text="The request may have failed.\n")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_hard_wrapped_long_sentence_is_caught(self) -> None:
        wrapped = (
            "The agent performs a comprehensive configuration validation pass over the entire\n"
            "deployment directory before any restart, and it writes one very detailed report "
            "file for review before the restart can finally begin.\n"
        )
        result = self.run_lint(text=wrapped)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("long-sentence", result.stdout.decode("utf-8"))

    def test_silent_e_ing_forms_are_matched(self) -> None:
        result = self.run_lint(text="Delete the first file. Removing the second file.\n")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("synonym-rotation", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()

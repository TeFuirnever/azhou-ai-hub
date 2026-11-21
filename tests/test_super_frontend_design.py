"""Integrity suite for the super-frontend-design canonical skill.

Pins the vendored upstream baseline (anthropics/skills skills/frontend-design
at the immutable provenance commit), the hub wrapper layer (frontmatter
contract, brand protocol, receipt) and the retained license obligations.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from scripts.check_repository import INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-frontend-design"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_COMMIT = "41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f"
UPSTREAM_SKILL_SHA256 = "d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3"
UPSTREAM_LICENSE_SHA256 = "0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594"
PINNED_SHA256 = {
    "LICENSE.txt": UPSTREAM_LICENSE_SHA256,
}

UPSTREAM_TRIGGER_SENTENCES = (
    "Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one.",
    "Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.",
)
UPSTREAM_BODY_SECTIONS = (
    "## Ground your designs in the subject matter",
    "## Design principles",
    "## Process: plan, review against the brief, build, critique",
    "## Restraint and self-critique",
    "## More on writing in design",
)
UPSTREAM_INTRO_OPENING = "Approach this as the design lead at a design studio"
# The contiguous embedded upstream region: the pinned upstream file's tail from
# the intro sentence through upstream EOF (9,056 characters including the
# upstream trailing newline — the intro plus all five sections), embedded
# byte-identical between the brand protocol and the wrapper boundary sections.
UPSTREAM_BODY_CHARS = 9056
UPSTREAM_BODY_SHA256 = "2db4877f31dfe7ea245b55ee9cc2ddcb3ff022951f3d65031644c8b6e278bd86"
UPSTREAM_BODY_TAIL = "Let each written element do exactly one job.\n"
CARVE_NEIGHBORS = ("super-archify", "super-lavish", "super-eli5", "super-excalidraw-diagram")


class SuperFrontendDesignPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-frontend-design", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)

    def test_upstream_description_baseline_is_retained(self) -> None:
        description = re.search(r"^description:\s*\"(.*)\"$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1)), 1024)
        self.assertTrue(description.group(1).startswith("Azhou skill."))
        for sentence in UPSTREAM_TRIGGER_SENTENCES:
            self.assertIn(sentence, description.group(1))
        self.assertIn("Use when", description.group(1))
        self.assertIn("MUST trigger", description.group(1))
        for neighbor in CARVE_NEIGHBORS:
            self.assertIn(neighbor, description.group(1))

    def test_upstream_body_is_preserved_verbatim_in_order(self) -> None:
        self.assertIn(UPSTREAM_INTRO_OPENING, self.text)
        offsets = [self.text.index(section) for section in UPSTREAM_BODY_SECTIONS]
        self.assertEqual(sorted(offsets), offsets)

    def test_upstream_body_digest_is_pinned(self) -> None:
        # Binds the embedded upstream region itself, not just its headings: any
        # byte change inside the span (including the trailing newline boundary)
        # changes the digest and fails the suite.
        start = self.text.index(UPSTREAM_INTRO_OPENING)
        span = self.text[start : start + UPSTREAM_BODY_CHARS]
        self.assertEqual(
            UPSTREAM_BODY_SHA256, hashlib.sha256(span.encode("utf-8")).hexdigest()
        )
        self.assertTrue(span.endswith(UPSTREAM_BODY_TAIL))

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-frontend-design/SKILL.md"]
        self.assertEqual("Frontend Design", contract["display_name"])
        self.assertNotIn("brand_path", contract)
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.text)
        self.assertIn("raw evidence", self.text)
        self.assertIn("super-frontend-design.receipt.v1", self.text)

    def test_provenance_pins_the_locked_upstream(self) -> None:
        provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_SKILL_SHA256, provenance)
        self.assertIn(UPSTREAM_LICENSE_SHA256, provenance)
        self.assertIsNotNone(re.search(r"^Classification: `faithful`$", provenance, re.MULTILINE))
        self.assertIn("Skill-standard §2.3", provenance)
        self.assertIn("import review", provenance)
        self.assertIn("Reproducible source check", provenance)

    def test_compatibility_map_preserves_capability_rows(self) -> None:
        compat = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, compat)
        self.assertIn("preserved byte-identical", compat)
        self.assertIn("preserved verbatim", compat)
        self.assertIn(
            "A future removal or replacement needs a documented safety conflict "
            "or implementation disadvantage plus regression evidence.",
            compat,
        )

    def test_vendored_files_match_the_pinned_upstream_bytes(self) -> None:
        for relative, expected in PINNED_SHA256.items():
            data = (SKILL_DIR / relative).read_bytes()
            self.assertEqual(expected, hashlib.sha256(data).hexdigest(), relative)

    def test_license_copy_is_retained(self) -> None:
        licenses_copy = (ROOT / "LICENSES" / "Anthropic-Skills-Apache-2.0.txt").read_bytes()
        self.assertEqual(UPSTREAM_LICENSE_SHA256, hashlib.sha256(licenses_copy).hexdigest())
        package_license = (SKILL_DIR / "LICENSE.txt").read_bytes()
        self.assertEqual(licenses_copy, package_license)
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Anthropic-Skills-Apache-2.0.txt", notices)
        self.assertIn(UPSTREAM_COMMIT, notices)

    def test_upstream_license_is_the_bare_apache_text(self) -> None:
        license_text = (SKILL_DIR / "LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0, January 2004", license_text)
        self.assertIn("END OF TERMS AND CONDITIONS", license_text)
        self.assertNotIn("APPENDIX", license_text)
        self.assertNotIn("Copyright [yyyy]", license_text)

    def test_package_carries_only_the_contracted_files(self) -> None:
        files = sorted(
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        )
        self.assertEqual(
            [
                "LICENSE.txt",
                "SKILL.md",
                "references/provenance.md",
                "references/setup.md",
                "references/upstream-compatibility.md",
            ],
            files,
        )


if __name__ == "__main__":
    unittest.main()

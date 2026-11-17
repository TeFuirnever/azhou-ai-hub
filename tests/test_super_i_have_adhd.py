"""Integrity pins for the adopted super-i-have-adhd package.

The package imports the `i-have-adhd` Agent Skill from ayghri/i-have-adhd at
a frozen commit and classifies as adapted: the upstream instruction body is
kept verbatim inside the entry and the local layer appends five Azhou
presentation constraints. Following the super-lavish precedent, the pins live
in this test module instead of a separate manifest JSON: upstream baseline
digests are UPSTREAM_* constants, the repository's retained license copy is
checked byte-for-byte against the upstream LICENSE digest, and the frozen
instruction body is bound by digest.
"""

from __future__ import annotations

import hashlib
import re
import struct
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, SKILL_BRAND_CONTRACTS

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-i-have-adhd"
SKILL = SKILL_DIR / "SKILL.md"

# Upstream baseline: ayghri/i-have-adhd, frozen main HEAD (U0 snapshot).
UPSTREAM_COMMIT = "1ecea1993b7fce257ffbd686c070948b5e07eda6"
UPSTREAM_SKILL_SHA256 = "88955c019bbb1419ff4b49dbb1f80a867467de6233d7865af2e06a7d7b76c7d3"
UPSTREAM_LICENSE_SHA256 = "8acbb618089b738404f76ac60fca1aaa995d9a87995eddf95f0b777acd7f7d2c"

# The upstream instruction body as embedded in SKILL.md: everything below the
# upstream `# i-have-adhd` title, from its first sentence to its last.
FROZEN_BODY_FIRST = "The reader has ADHD. Output is not just brief."
FROZEN_BODY_LAST = "If yes, send."
FROZEN_BODY_SHA256 = "24a41f84841eead396469689c2c50abccd3774c4730f51edb98e16ee6b5dccdf"

DELTA_RULES = (
    "Conclusions keep their sources nearby",
    "Separate state changes from pending decisions",
    "Never create evidence",
    "Review Contract is optional",
    "No machine-local absolute paths",
)

PACKAGE_WHITELIST = (
    "SKILL.md",
    "references/brand-layer.md",
    "references/provenance.md",
    "references/setup.md",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_slice(text: str) -> str:
    start = text.index(FROZEN_BODY_FIRST)
    end = text.index(FROZEN_BODY_LAST, start) + len(FROZEN_BODY_LAST)
    return text[start:end]


class SuperIHaveAdhdPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        self.provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.setup = (SKILL_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        self.brand = (SKILL_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-i-have-adhd", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), ("both", "user-invoked orchestrator"))
        description = re.search(r"^description:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_description_starts_with_the_brand_marker_and_keeps_triggers(self) -> None:
        self.assertIn("Azhou skill.", self.frontmatter)
        self.assertIn("/i-have-adhd", self.frontmatter)
        self.assertIn("拆步", self.frontmatter)
        self.assertIn("stop adhd mode", self.frontmatter)

    def test_description_records_the_capability_carve_both_ways(self) -> None:
        self.assertIn("belong to super-eli5", self.frontmatter)
        self.assertIn("belong to super-arch-doc", self.frontmatter)
        self.assertIn("belong to super-imagegen", self.text)
        eli5 = (ROOT / "skills" / "super-eli5" / "SKILL.md").read_text(encoding="utf-8")
        arch_doc = (ROOT / "skills" / "super-arch-doc" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belongs to super-i-have-adhd", eli5)
        self.assertIn("belongs to super-i-have-adhd", arch_doc)

    def test_upstream_host_specific_frontmatter_is_not_copied(self) -> None:
        self.assertNotIn("disable-model-invocation", self.text)
        self.assertNotIn("metadata:", self.frontmatter)

    def test_frozen_instruction_body_is_bound_by_digest(self) -> None:
        frozen = _frozen_slice(self.text)
        self.assertEqual(FROZEN_BODY_SHA256, hashlib.sha256(frozen.encode("utf-8")).hexdigest())
        self.assertIn("## Output contract (frozen upstream instructions)", self.text)
        self.assertIn("## Azhou presentation delta", self.text)

    def test_delta_appends_exactly_five_constraints(self) -> None:
        delta = self.text.split("## Azhou presentation delta", 1)[1]
        for rule in DELTA_RULES:
            self.assertIn(rule, delta)
        self.assertEqual(5, len(re.findall(r"^\d\. \*\*", delta, re.MULTILINE)))

    def test_provenance_pins_the_frozen_source(self) -> None:
        self.assertIn(f"Immutable commit | `{UPSTREAM_COMMIT}`", self.provenance)
        self.assertIn(f"Upstream source SHA-256 | `{UPSTREAM_SKILL_SHA256}`", self.provenance)
        self.assertIn(f"Upstream LICENSE SHA-256 | `{UPSTREAM_LICENSE_SHA256}`", self.provenance)
        self.assertIn("provisional promote", self.provenance)
        self.assertIn("non-blind", self.provenance)
        self.assertIn("docs/specs/super-i-have-adhd-pilot.md", self.provenance)

    def test_provenance_reproducible_check_matches_the_pins(self) -> None:
        self.assertIn(UPSTREAM_COMMIT, self.provenance)
        self.assertIn(UPSTREAM_SKILL_SHA256, self.provenance)
        self.assertIn(UPSTREAM_LICENSE_SHA256, self.provenance)

    def test_provenance_declares_the_adapted_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("adapted", match.group(1))

    def test_license_copy_is_byte_identical_to_the_upstream_license(self) -> None:
        license_copy = ROOT / "LICENSES" / "I-have-Adhd-MIT.txt"
        self.assertTrue(license_copy.is_file())
        self.assertEqual(UPSTREAM_LICENSE_SHA256, _sha256(license_copy))

    def test_notice_section_is_registered(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## i-have-adhd", notices)
        self.assertIn("LICENSES/I-have-Adhd-MIT.txt", notices)

    def test_setup_records_the_zero_dependency_boundary(self) -> None:
        self.assertIn("instruction-only", self.setup)
        self.assertIn("Zero external runtime dependency", self.setup)
        self.assertIn("Verification equals loading", self.setup)

    def test_package_is_contract_only(self) -> None:
        actual = sorted(
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        )
        self.assertEqual(sorted(PACKAGE_WHITELIST), actual)

    def test_no_absolute_path_leak_in_package_surfaces(self) -> None:
        for surface, text in (
            ("SKILL.md", self.text),
            ("provenance.md", self.provenance),
            ("setup.md", self.setup),
            ("brand-layer.md", self.brand),
        ):
            self.assertNotIn("/Users/", text, f"{surface} carries a machine-local absolute path")

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-i-have-adhd/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-i-have-adhd/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-i-have-adhd/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_receipt_schema_is_stable(self) -> None:
        self.assertIn("schema: super-i-have-adhd.receipt.v1", self.brand)
        for status in ("complete", "complete_with_holds", "hold", "failed"):
            self.assertIn(status, self.brand)
        self.assertIn("state_changes", self.brand)
        self.assertIn("pending_decisions", self.brand)

    def test_showcase_effect_image_is_metadata_sanitized(self) -> None:
        # The generation pipeline embeds the scene prompt, local paths and
        # runtime identity in eXIf/iTXt/tEXt chunks; the published showcase
        # must carry none of them (sanitized before publishing, 2026-11-17).
        data = (ROOT / "assets" / "skills" / "super-i-have-adhd-effect.png").read_bytes()
        pos = 8
        present = []
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            present.append(data[pos + 4:pos + 8])
            pos += 12 + length
        for forbidden in (b"iTXt", b"tEXt", b"zTXt", b"eXIf"):
            self.assertNotIn(forbidden, present, f"metadata chunk must stay out of the shipped image: {forbidden}")
        self.assertIn(b"IHDR", present)
        self.assertIn(b"IEND", present)

    def test_provenance_binds_the_sanitized_shipment_and_the_approved_candidate(self) -> None:
        self.assertIn("838bdd4bcd4d50ce4e1249c47f4ad146a279286b4fe26036b1c6fd104502a8e2", self.provenance)
        self.assertIn("2e1cb65711936bcd3e6cb1cc95ea9bb837f36b35cd78280a19c7a104845f5676", self.provenance)
        self.assertIn("metadata-sanitized", self.provenance)
        self.assertIn("byte-identical", self.provenance)


if __name__ == "__main__":
    unittest.main()

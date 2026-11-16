"""Integrity pins for the contract-only super-imagegen package.

The package wraps the machine's already-installed private ``azhou-imagegen``
skill without vendoring any of it: no generation code, no prompt bodies, no
master or reference assets, no receipt stores, no weights. The pins below
hold the package to the contract-only shape, pin the registered private
baseline hashes in provenance, and keep the fail-closed setup and brand
contract in place.
"""

from __future__ import annotations

import hashlib
import re
import struct
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-imagegen"
SKILL = SKILL_DIR / "SKILL.md"

# Registered 2026-11-16 maintainer-host snapshot of the private install.
# Observation pins in provenance, never a redistribution.
BASELINE_DATE = "2026-11-16"
BASELINE_SKILL_MD_SHA256 = "0dcca3866f5ec6910040d639f92fc2b01785f6c3baeb9f6ec9f43e16d8b1a92d"
BASELINE_CLI_SHA256 = "681ea164c306d8ee3a0500e279485c5a256eb6c26ef3d565a9e294b405dad5d0"
BASELINE_LICENSE_SHA256 = "b2e167d36a6ccbdb21c49dd0bdad6449f24bbb6988a15629b3df11915a311b03"

PRIVATE_ROOT = Path.home() / ".agents" / "skills" / "azhou-imagegen"

ALLOWED_PACKAGE_FILES = {
    "SKILL.md",
    "references/setup.md",
    "references/provenance.md",
    "references/brand-layer.md",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuperImagegenPackageTest(unittest.TestCase):
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
        self.assertEqual("super-imagegen", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)

    def test_description_keeps_the_private_name_compatibility_trigger(self) -> None:
        self.assertIn("Azhou skill.", self.frontmatter)
        self.assertIn("azhou-imagegen", self.frontmatter)
        self.assertIn("still triggers this contract", self.frontmatter)

    def test_description_records_the_capability_carve_both_ways(self) -> None:
        self.assertIn("belong to super-archify", self.frontmatter)
        self.assertIn("belong to super-excalidraw-diagram", self.frontmatter)
        self.assertIn("belong to super-lavish", self.frontmatter)
        archify = (ROOT / "skills" / "super-archify" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belong to super-imagegen", archify)
        diagram = (ROOT / "skills" / "super-excalidraw-diagram" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("belong to super-imagegen", diagram)
        lavish = (ROOT / "skills" / "super-lavish" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belong to super-imagegen", lavish)

    def test_package_is_contract_only(self) -> None:
        actual = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        }
        self.assertEqual(ALLOWED_PACKAGE_FILES, actual)

    def test_no_private_capability_bytes_are_vendored(self) -> None:
        for forbidden in ("scripts", "config", "agents", "assets", "templates", "benchmarks"):
            self.assertFalse(
                (SKILL_DIR / forbidden).exists(),
                f"private runtime surface must stay outside the package: {forbidden}",
            )
        self.assertIn("not vendored", self.setup)
        self.assertIn("never carries", self.provenance)

    def test_provenance_pins_the_registered_private_baseline(self) -> None:
        self.assertIn(BASELINE_DATE, self.provenance)
        self.assertIn(f"`{BASELINE_SKILL_MD_SHA256}`", self.provenance)
        self.assertIn(f"`{BASELINE_CLI_SHA256}`", self.provenance)
        self.assertIn(f"`{BASELINE_LICENSE_SHA256}`", self.provenance)

    def test_provenance_declares_the_fidelity_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("original", match.group(1))
        self.assertIn("Skill-standard §2.3", self.provenance)

    def test_provenance_records_the_proprietary_boundary(self) -> None:
        self.assertIn("Proprietary", self.provenance)
        self.assertIn("non-commercial research and evaluation", self.provenance)
        self.assertIn("does not grant", self.provenance)

    def test_setup_and_entry_fail_closed_on_missing_runtime(self) -> None:
        self.assertIn("Fail closed", self.setup)
        self.assertIn("Do not fall back to another generator", self.setup)
        self.assertIn("--doctor --json", self.text)
        self.assertIn("--doctor --json", self.setup)
        self.assertIn("never downloads", self.setup.lower().replace("Never downloads", "never downloads"))

    def test_runtime_is_resolved_from_the_installed_skill_not_a_copy(self) -> None:
        self.assertIn("already-installed", self.text)
        self.assertIn("--help", self.text)
        self.assertIn("does not search development checkouts", self.text.replace(
            "it does not search development checkouts", "does not search development checkouts"
        ))

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-imagegen/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-imagegen/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-imagegen/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_receipt_schema_is_stable(self) -> None:
        self.assertIn("schema: super-imagegen.receipt.v1", self.brand)
        for status in ("complete", "complete_with_holds", "hold", "failed"):
            self.assertIn(status, self.brand)
        self.assertIn("human_review", self.brand)
        self.assertIn("candidate_state", self.brand)

    @unittest.skipUnless(
        PRIVATE_ROOT.is_dir(), "private azhou-imagegen install not present on this machine"
    )
    def test_private_install_matches_the_registered_baseline(self) -> None:
        for relative, digest in (
            ("SKILL.md", BASELINE_SKILL_MD_SHA256),
            ("scripts/azhou_gen.py", BASELINE_CLI_SHA256),
            ("LICENSE", BASELINE_LICENSE_SHA256),
        ):
            with self.subTest(path=relative):
                path = PRIVATE_ROOT / relative
                self.assertTrue(path.is_file(), f"missing private baseline file: {relative}")
                self.assertEqual(digest, _sha256(path), f"private baseline drifted: {relative}")

    def test_showcase_effect_image_is_metadata_sanitized(self) -> None:
        # The generation pipeline embeds the scene prompt, local paths and
        # runtime identity in eXIf/iTXt/tEXt chunks; the published showcase
        # must carry none of them (sanitized before publishing, 2026-11-16).
        data = (ROOT / "assets" / "skills" / "super-imagegen-effect.png").read_bytes()
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
        self.assertIn("e038db573f137dfe42341167dcdf1c2d6481387e7aa33e65dd3b2ec24f98f419", self.provenance)
        self.assertIn("6b2526dd43855c56a1c481dfc0c47cda68316fc46dc8cb5e15f5dc397d0c275a", self.provenance)
        self.assertIn("metadata-sanitized", self.provenance)
        self.assertIn("byte-identical", self.provenance)


if __name__ == "__main__":
    unittest.main()

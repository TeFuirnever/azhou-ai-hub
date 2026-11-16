"""Integrity pins for the adopted super-lavish package.

The package imports the generated `lavish` Agent Skill from kunchenguid/lavish-axi
at a locked release and invokes the external CLI through a locked npx baseline;
no Lavish application code is vendored. Following the asd-ste100 precedent, the
pins live in this test module instead of a separate manifest JSON: upstream
baseline digests are UPSTREAM_* constants, the repository's retained license
copy is checked byte-for-byte against the upstream LICENSE digest.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, SKILL_BRAND_CONTRACTS

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-lavish"
SKILL = SKILL_DIR / "SKILL.md"

# Upstream baseline: kunchenguid/lavish-axi, tag lavish-axi-v0.1.97.
UPSTREAM_COMMIT = "79aa0a18dba9c1a1dcec6db19d2ef4eb7643754b"
UPSTREAM_TAG = "lavish-axi-v0.1.97"
UPSTREAM_CLI_VERSION = "0.1.97"
UPSTREAM_SKILL_SHA256 = "00ea380ff3e993d58029e4467901333138726f734755e0eef254de2fe4c2f1ef"
UPSTREAM_LICENSE_SHA256 = "945016bd37e1ba7211622ef60ee1d23ab727896ba7710edd21e8fbe983863969"
UPSTREAM_NPM_INTEGRITY = (
    "sha512-Ux6/kePVt7DboZpROPKnrBNQaLtyaVDdC5wTT5X+roCR2e7AGI8Q4HDGbLFAXlm9zQlJO+SWRW9xHYHDI9F/UQ=="
)
UPSTREAM_TARBALL_SHA256 = "84e4d91c173e91b966c506da770a649d533766d93985739d26b8592143127662"

LOCKED_INVOCATION = f"lavish-axi@{UPSTREAM_CLI_VERSION}"
UNPINNED_NPX = re.compile(r"npx -y lavish-axi(?!@)")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuperLavishPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        self.provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.setup = (SKILL_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        self.compatibility = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(
            encoding="utf-8"
        )
        self.brand = (SKILL_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-lavish", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), ("both", "user-invoked orchestrator"))
        description = re.search(r"^description:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_description_keeps_the_rename_compatibility_trigger(self) -> None:
        self.assertIn("Azhou skill.", self.frontmatter)
        self.assertIn("Renamed from lavish (the old name still triggers this skill)", self.frontmatter)

    def test_description_records_the_capability_carve_both_ways(self) -> None:
        self.assertIn("belong to super-archify", self.text)
        self.assertIn("belong to super-excalidraw-diagram", self.text)
        archify = (ROOT / "skills" / "super-archify" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belongs to super-lavish", archify)

    def test_provenance_pins_the_locked_source(self) -> None:
        self.assertIn(f"Immutable commit | `{UPSTREAM_COMMIT}`", self.provenance)
        self.assertIn(f"Upstream tag | `{UPSTREAM_TAG}`", self.provenance)
        self.assertIn(f"Upstream source SHA-256 | `{UPSTREAM_SKILL_SHA256}`", self.provenance)
        self.assertIn(f"CLI baseline | `lavish-axi@{UPSTREAM_CLI_VERSION}`", self.provenance)
        self.assertIn(f"npm integrity | `{UPSTREAM_NPM_INTEGRITY}`", self.provenance)
        self.assertIn(f"npm tarball SHA-256 | `{UPSTREAM_TARBALL_SHA256}`", self.provenance)

    def test_provenance_reproducible_check_matches_the_pins(self) -> None:
        self.assertIn(UPSTREAM_COMMIT, self.provenance)
        self.assertIn(UPSTREAM_SKILL_SHA256, self.provenance)
        self.assertIn(UPSTREAM_TARBALL_SHA256, self.provenance)
        self.assertIn(UPSTREAM_NPM_INTEGRITY, self.provenance)

    def test_provenance_declares_the_fidelity_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertIn(match.group(1), ("original", "faithful", "adapted"))

    def test_license_copy_is_byte_identical_to_the_upstream_license(self) -> None:
        license_copy = ROOT / "LICENSES" / "Lavish-AXI-MIT.txt"
        self.assertTrue(license_copy.is_file())
        self.assertEqual(UPSTREAM_LICENSE_SHA256, _sha256(license_copy))

    def test_notice_section_is_registered(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## Lavish Editor", notices)
        self.assertIn("LICENSES/Lavish-AXI-MIT.txt", notices)

    def test_every_cli_invocation_uses_the_locked_baseline(self) -> None:
        for surface, text in (
            ("SKILL.md", self.text),
            ("setup.md", self.setup),
        ):
            self.assertIsNone(
                UNPINNED_NPX.search(text),
                f"{surface} carries an unpinned npx invocation",
            )
        self.assertIn(f"npx -y {LOCKED_INVOCATION} <html-file>", self.text)
        self.assertIn(LOCKED_INVOCATION, self.setup)

    def test_setup_fails_closed_on_missing_runtime(self) -> None:
        self.assertIn("Node 22+", self.setup)
        self.assertIn("Fail closed", self.setup)
        self.assertIn("Do not fall back to a different version", self.setup)

    def test_no_lavish_application_code_is_vendored(self) -> None:
        for forbidden in ("dist", "node_modules", "package.json", "package-lock.json"):
            self.assertFalse(
                (SKILL_DIR / forbidden).exists(),
                f"vendored runtime surface must stay outside the package: {forbidden}",
            )
        self.assertIn("not vendored", self.setup)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-lavish/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-lavish/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-lavish/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_receipt_schema_is_stable(self) -> None:
        self.assertIn("schema: super-lavish.receipt.v1", self.brand)
        for status in ("complete", "complete_with_holds", "hold", "failed"):
            self.assertIn(status, self.brand)

    def test_compatibility_map_keeps_the_retired_relay_surface_out(self) -> None:
        self.assertIn("Spec Relay relay mode and `relay_state.py`", self.compatibility)
        self.assertIn("retired with the 2026-11-09 retirement", self.compatibility)


if __name__ == "__main__":
    unittest.main()

"""Integrity pins for the adopted super-gh-axi package.

The package imports the generated `gh-axi` Agent Skill from kunchenguid/gh-axi
at a locked release and invokes the external CLI through a locked npx baseline;
no gh-axi application code is vendored. Following the super-lavish precedent,
the pins live in this test module instead of a separate manifest JSON: upstream
baseline digests are UPSTREAM_* constants, the repository's retained license
copy is checked byte-for-byte against the upstream LICENSE digest. The package
file whitelist follows the super-imagegen precedent.

The skill package text (SKILL.md and references/) is itself the pinned text
contract these tests intentionally pin: the documents_-style methods assert the
exact wording the instruction surface must carry. The showcase metadata,
chunk-whitelist and shipped-digest pins cover the showcase image landed here.
"""

from __future__ import annotations

import hashlib
import re
import struct
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-gh-axi"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_COMMIT = "5a526599c9fa5a76b650079f5e9dbb1c1874a6ce"
UPSTREAM_TAG = "gh-axi-v0.1.52"
UPSTREAM_CLI_VERSION = "0.1.52"
UPSTREAM_SKILL_SHA256 = "3d01b3112442275d52cc5847cb17543c710128f4591346e77eeecc30c45e76f3"
UPSTREAM_LICENSE_SHA256 = "945016bd37e1ba7211622ef60ee1d23ab727896ba7710edd21e8fbe983863969"
UPSTREAM_NPM_INTEGRITY = (
    "sha512-HWCP4xvRkvO2ESQSr2Vns8Z2BEiMBRqEkAs/BoQAFkGmyxhV0ZL7KnZSQ3M8oXhZnz+DgOGtose3QKaIqdYGSA=="
)
UPSTREAM_TARBALL_SHA256 = "af7a7b6ab5f2c1e0cd2fd10ac53cab0c59142501df70bdc26c8f4ca6bdaee41c"

SHOWCASE_SHIPPED_SHA256 = "64c17580947743509a2f0447d59e86482153ab8427b11c92ada7cab1c64ee7b8"
SHOWCASE_APPROVED_SHA256 = "ae0b014187fe8bf167eca8b2509ec685b65c133fcd3622049d387e61fff40f03"

LOCKED_INVOCATION = f"gh-axi@{UPSTREAM_CLI_VERSION}"
NPX_GH_AXI = re.compile(r"\bnpx(?:\s+-{1,2}[\w-]+(?:=\S+)?)*\s+gh-axi(?![\w-])(?:@[^\s`\"']*)?")
OFF_BASELINE_GH_AXI_SPEC = re.compile(rf"\bgh-axi@(?!{re.escape(UPSTREAM_CLI_VERSION)}(?![\w-]))")

RECEIPT_STATUSES = ("complete", "complete_with_holds", "hold", "failed")

ALLOWED_PACKAGE_FILES = {
    "SKILL.md",
    "references/setup.md",
    "references/provenance.md",
    "references/upstream-compatibility.md",
    "references/brand-layer.md",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuperGhAxiPackageTest(unittest.TestCase):
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
        self.assertEqual("super-gh-axi", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)
        self.assertEqual("model-invoked discipline", invocation.group(1).strip())
        description = re.search(r"^description:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_description_documents_the_rename_compatibility_trigger(self) -> None:
        self.assertIn("Azhou skill.", self.frontmatter)
        self.assertIn("Renamed from gh-axi (the old name still triggers this skill)", self.frontmatter)

    def test_package_is_contract_only(self) -> None:
        actual = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        }
        self.assertEqual(ALLOWED_PACKAGE_FILES, actual)

    def test_provenance_pins_the_locked_source(self) -> None:
        self.assertIn(f"Immutable commit | `{UPSTREAM_COMMIT}`", self.provenance)
        self.assertIn(f"Upstream tag | `{UPSTREAM_TAG}`", self.provenance)
        self.assertIn(f"Upstream source SHA-256 | `{UPSTREAM_SKILL_SHA256}`", self.provenance)
        self.assertIn(f"CLI baseline | `gh-axi@{UPSTREAM_CLI_VERSION}`", self.provenance)
        self.assertIn(f"npm integrity | `{UPSTREAM_NPM_INTEGRITY}`", self.provenance)
        self.assertIn(f"npm tarball SHA-256 | `{UPSTREAM_TARBALL_SHA256}`", self.provenance)

    def test_provenance_reproducible_check_matches_the_pins(self) -> None:
        block = self.provenance.split("## Reproducible source check", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"Expected SHA-256: `{UPSTREAM_SKILL_SHA256}`", block)
        self.assertIn(f"Expected tarball SHA-256: `{UPSTREAM_TARBALL_SHA256}`", block)
        self.assertIn(f"Expected npm `dist.integrity`: `{UPSTREAM_NPM_INTEGRITY}`", block)
        self.assertIn(f"https://registry.npmjs.org/gh-axi/-/gh-axi-{UPSTREAM_CLI_VERSION}.tgz", block)
        source_urls = re.findall(
            r"raw\.githubusercontent\.com/kunchenguid/gh-axi/([^/]+)/skills/gh-axi/SKILL\.md", block
        )
        self.assertTrue(source_urls, "the reproducible check must record its source recipe")
        self.assertEqual({UPSTREAM_COMMIT}, set(source_urls))

    def test_provenance_documents_the_fidelity_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("faithful", match.group(1))
        self.assertIn("Skill-standard §2.3", self.provenance)

    def test_license_copy_is_byte_identical_to_the_upstream_license(self) -> None:
        license_copy = ROOT / "LICENSES" / "Gh-Axi-MIT.txt"
        self.assertTrue(license_copy.is_file())
        self.assertEqual(UPSTREAM_LICENSE_SHA256, _sha256(license_copy))

    def test_notice_documents_the_gh_axi_entry(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## Gh Axi", notices)
        self.assertIn("LICENSES/Gh-Axi-MIT.txt", notices)

    def test_every_cli_invocation_uses_the_locked_baseline(self) -> None:
        for surface, text in (
            ("SKILL.md", self.text),
            ("setup.md", self.setup),
        ):
            for invocation in NPX_GH_AXI.findall(text):
                self.assertEqual(
                    f"npx -y {LOCKED_INVOCATION}",
                    invocation,
                    f"{surface} must invoke the CLI as npx -y {LOCKED_INVOCATION} only",
                )
            self.assertIsNone(
                OFF_BASELINE_GH_AXI_SPEC.search(text),
                f"{surface} pins a gh-axi spec outside the locked baseline",
            )
        self.assertIn(f"npx -y {LOCKED_INVOCATION} --help", self.text)
        self.assertIn(LOCKED_INVOCATION, self.setup)

    def test_setup_documents_fail_closed_behavior(self) -> None:
        self.assertIn("Node 20+", self.setup)
        self.assertIn("Fail closed", self.setup)
        self.assertIn("Do not fall back to a different version", self.setup)

    def test_no_gh_axi_application_code_is_vendored(self) -> None:
        for forbidden in ("dist", "node_modules", "package.json", "package-lock.json"):
            self.assertFalse(
                (SKILL_DIR / forbidden).exists(),
                f"vendored runtime surface must stay outside the package: {forbidden}",
            )
        self.assertIn("not vendored", self.setup)

    def test_compatibility_map_documents_the_translation_choices(self) -> None:
        self.assertIn("translated, not copied", self.compatibility)
        self.assertIn("model-invoked discipline", self.compatibility)
        self.assertIn("intentionally omitted", self.compatibility)
        self.assertIn("narrowed", self.compatibility)

    def test_showcase_effect_image_is_metadata_sanitized(self) -> None:
        # The generation pipeline embeds the scene prompt, local paths and
        # runtime identity in eXIf/iTXt/tEXt chunks; the published showcase
        # must carry none of them (sanitized before publishing, 2026-11-17).
        image = ROOT / "assets" / "skills" / "super-gh-axi-effect.png"
        self.assertEqual(SHOWCASE_SHIPPED_SHA256, _sha256(image))
        data = image.read_bytes()
        pos = 8
        present = []
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            present.append(data[pos + 4:pos + 8])
            pos += 12 + length
        self.assertIn(b"IDAT", present, "the shipped pixel stream must keep its IDAT bytes")
        self.assertEqual({b"IHDR", b"IDAT", b"IEND"}, set(present))

    def test_provenance_documents_the_sanitized_shipment_and_approved_candidate(self) -> None:
        self.assertIn(SHOWCASE_APPROVED_SHA256, self.provenance)
        self.assertIn(SHOWCASE_SHIPPED_SHA256, self.provenance)
        self.assertIn("metadata-sanitized", self.provenance)
        self.assertIn("byte-identical", self.provenance)
        self.assertIn("03-production-alert", self.provenance)
        self.assertIn("azhou-20261117T131932Z-gh-axi-showcase-s21", self.provenance)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-gh-axi/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-gh-axi/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-gh-axi/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_package_documents_the_status_vocabulary_and_receipt_schema(self) -> None:
        self.assertIn("schema: super-gh-axi.receipt.v1", self.brand)
        self.assertIn(f"status: {' | '.join(RECEIPT_STATUSES)}", self.brand)
        self.assertIn("auth_boundary", self.brand)
        dictionary = self.brand.split("## Status dictionary", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in dictionary.splitlines() if line.startswith("| `")]
        statuses = [re.match(r"\| `[^`]+` \| `([^`]+)` \|", line).group(1) for line in rows]
        self.assertEqual(list(RECEIPT_STATUSES), statuses)
        enumeration = ", ".join(f"`{status}`" for status in RECEIPT_STATUSES[:-1])
        self.assertIn(f"Keep {enumeration}, and `{RECEIPT_STATUSES[-1]}` distinct", self.text)


if __name__ == "__main__":
    unittest.main()

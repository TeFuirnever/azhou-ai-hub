"""Integrity pins for the adopted super-pdf package.

The package imports the `pdf` Agent Skill from anthropics/skills at the
immutable commit frozen by the 2026-11-18 import review (docskills-U0, R1
ruling): the upstream guide body is embedded verbatim below the entry's
wrapper, FORMS.md, REFERENCE.md and the eight scripts are vendored
byte-identical, and the license copy is retained byte-identical including the
upstream placeholder copyright line. Following the super-gh-axi and
super-i-have-adhd precedents, the pins live in this test module: upstream
baseline digests are UPSTREAM_* constants, the vendored file digests are
VENDORED_SHA256, and the embedded frozen body is bound by digest.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-pdf"
SKILL = SKILL_DIR / "SKILL.md"

# Upstream baseline: anthropics/skills, frozen by the 2026-11-18 import review
# (docs/research/2026-11-18-anthropics-skills-import-review.md, appendix A).
UPSTREAM_COMMIT = "e4bb5d960d87126ff3b3a8af1a104b7db67560ba"
UPSTREAM_SKILL_SHA256 = "d1c7caf5f35eb7d37877dd7fc33a095037be2b34fb5d2f7f4d43bde3165bb4ee"
UPSTREAM_LICENSE_SHA256 = "58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd"

# The upstream SKILL.md body as embedded in this package's SKILL.md:
# everything below the upstream `# PDF Processing Guide` title.
FROZEN_BODY_FIRST = "## Overview"
FROZEN_BODY_LAST = "- For troubleshooting guides, see REFERENCE.md"
FROZEN_BODY_SHA256 = "cccf2463a0d964fa7f619feea772f4364e90af87e18c23d6003596f0cf71ab61"

# Vendored byte-identical files (appendix A pins).
VENDORED_SHA256 = {
    "FORMS.md": "d5df5757e23634cd8a1a37e092af6c3b3b63afb3fd3ce86337fce9017cc3ee9f",
    "REFERENCE.md": "07af9a8f59e77e88fe9b238a403348244f38a4771c54911c412716d8f88f0ea9",
    "scripts/check_bounding_boxes.py": "0ced522402dd7b3c82a0be9518cf4e485fa9cc0467d7beab6ddb04cb36fcc3e1",
    "scripts/check_fillable_fields.py": "1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8",
    "scripts/convert_pdf_to_images.py": "7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d",
    "scripts/create_validation_image.py": "8fa9fd7962c9f940045b81cf6b991e7c1057c1838e3f9cc6d305007a222ffebf",
    "scripts/extract_form_field_info.py": "bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109",
    "scripts/extract_form_structure.py": "6814e3fe8f78c2b16d766c132b5a727ff7a31b71d76a7d46bd6e40fe50bc97c5",
    "scripts/fill_fillable_fields.py": "d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5",
    "scripts/fill_pdf_form_with_annotations.py": "8a56e063a49ed53c0b0e1d312ecf8023af76816ed139486ec3b539873de202fd",
}

# The upstream trigger surface the entry description must preserve (the
# closing conditional sentence plus every capability trigger word).
TRIGGER_SURFACE = (
    "reading or extracting text and tables from PDFs",
    "combining or merging multiple PDFs into one",
    "splitting PDFs apart",
    "rotating pages",
    "adding watermarks",
    "creating new PDFs",
    "filling PDF forms",
    "encrypting or decrypting PDFs",
    "extracting images",
    "OCR on scanned PDFs to make them searchable",
    "If the user mentions a .pdf file or asks to produce one, use this skill.",
)

# Fail-closed dependency contract surface (the upstream declares none).
SETUP_DEPENDENCIES = (
    "| `pypdf` |",
    "| `pdfplumber` |",
    "| `pdf2image` |",
    "| Pillow |",
    "reportlab",
    "| `pytesseract`",
    "the `tesseract` binary",
    "poppler-utils",
    "| `qpdf` |",
    "pdftk",
    "numpy",
    "pandas",
    "openpyxl",
    "pypdfium2",
    "ImageMagick (`magick`",
    "pdf-lib",
    "pdfjs-dist",
)

RECEIPT_STATUSES = ("complete", "complete_with_holds", "hold", "failed")

ALLOWED_PACKAGE_FILES = {
    "SKILL.md",
    "FORMS.md",
    "REFERENCE.md",
    "references/setup.md",
    "references/provenance.md",
    "references/brand-layer.md",
    *VENDORED_SHA256,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_slice(text: str) -> str:
    start = text.index(FROZEN_BODY_FIRST)
    end = text.index(FROZEN_BODY_LAST, start) + len(FROZEN_BODY_LAST)
    return text[start:end]


class SuperPdfPackageTest(unittest.TestCase):
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
        self.assertNotIn("license", keys, "the upstream host-specific license key must not be copied")
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-pdf", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)
        self.assertEqual("model-invoked discipline", invocation.group(1).strip())
        description = re.search(r'^description:\s*"(.*)"$', self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_description_preserves_the_upstream_trigger_surface(self) -> None:
        description = re.search(r'^description:\s*"(.*)"$', self.frontmatter, re.MULTILINE).group(1)
        for fragment in TRIGGER_SURFACE:
            self.assertIn(fragment, description, f"trigger fragment lost: {fragment}")
        self.assertIn("the upstream pdf skill", description)
        self.assertIn("the upstream name still triggers this skill", description)

    def test_frozen_upstream_body_is_verbatim(self) -> None:
        body = _frozen_slice(self.text)
        self.assertEqual(FROZEN_BODY_SHA256, hashlib.sha256(body.encode("utf-8")).hexdigest())

    def test_vendored_files_match_the_pinned_digests(self) -> None:
        for relative, digest in sorted(VENDORED_SHA256.items()):
            path = SKILL_DIR / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(digest, _sha256(path), relative)

    def test_package_file_whitelist(self) -> None:
        actual = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        }
        self.assertEqual(ALLOWED_PACKAGE_FILES, actual)

    def test_provenance_pins_the_locked_source(self) -> None:
        self.assertIn(f"Immutable commit | `{UPSTREAM_COMMIT}`", self.provenance)
        self.assertIn(f"Upstream SKILL.md SHA-256 | `{UPSTREAM_SKILL_SHA256}`", self.provenance)
        self.assertIn(f"Embedded body SHA-256 | `{FROZEN_BODY_SHA256}`", self.provenance)
        self.assertIn(f"Upstream LICENSE.txt SHA-256 | `{UPSTREAM_LICENSE_SHA256}`", self.provenance)
        for relative, digest in sorted(VENDORED_SHA256.items()):
            self.assertIn(digest[:8], self.provenance, f"provenance must cite the {relative} digest")

    def test_provenance_reproducible_check_matches_the_pins(self) -> None:
        block = self.provenance.split("## Reproducible source check", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"Expected SHA-256: `{UPSTREAM_SKILL_SHA256}`", block)
        self.assertIn(f"Expected SHA-256: `{UPSTREAM_LICENSE_SHA256}`", block)
        source_urls = re.findall(
            r"raw\.githubusercontent\.com/anthropics/skills/([^/]+)/skills/pdf/", block
        )
        self.assertTrue(source_urls, "the reproducible check must record its source recipe")
        self.assertEqual({UPSTREAM_COMMIT}, set(source_urls))

    def test_license_copy_is_byte_identical_to_the_upstream_license(self) -> None:
        license_copy = ROOT / "LICENSES" / "Pdf-Apache-2.0.txt"
        self.assertTrue(license_copy.is_file())
        self.assertEqual(UPSTREAM_LICENSE_SHA256, _sha256(license_copy))
        text = license_copy.read_text(encoding="utf-8")
        self.assertIn("Copyright [yyyy] [name of copyright owner]", text)
        self.assertNotIn("Copyright 2026 Anthropic", text)

    def test_provenance_records_the_placeholder_anomaly_and_ruling(self) -> None:
        self.assertIn("Placeholder copyright-line anomaly", self.provenance)
        self.assertIn("Copyright [yyyy] [name of copyright owner]", self.provenance)
        self.assertIn("e4bb5d960d", self.provenance)

    def test_notice_documents_the_pdf_entry(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## Pdf", notices)
        self.assertIn("LICENSES/Pdf-Apache-2.0.txt", notices)
        self.assertIn("Anthropic PBC, from anthropics/skills @ e4bb5d960d", notices)

    def test_setup_documents_fail_closed_dependencies(self) -> None:
        for dependency in SETUP_DEPENDENCIES:
            self.assertIn(dependency, self.setup, f"setup must name {dependency}")
        self.assertIn("Fail-closed", self.setup)
        self.assertIn("named hold", self.setup)
        self.assertIn("No dependency is vendored", self.setup)
        self.assertIn("Pillow", self.setup)
        self.assertIn("not declared anywhere in the upstream SKILL.md", self.setup)

    def test_provenance_documents_the_fidelity_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("faithful", match.group(1))
        self.assertIn("Skill-standard §2.3", self.provenance)

    def test_provenance_documents_the_no_carve_judgment(self) -> None:
        self.assertIn("adds no capability carve sentence", self.provenance)
        self.assertIn("every canonical description was read and judged at adoption, 2026-11-18", self.provenance)

    def test_provenance_documents_the_visual_deferral(self) -> None:
        self.assertIn("deferral", self.provenance.lower())
        self.assertIn("#478", self.provenance)
        self.assertIn("16→17", self.provenance)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-pdf/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-pdf/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-pdf/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_package_documents_the_status_vocabulary_and_receipt_schema(self) -> None:
        self.assertIn("schema: super-pdf.receipt.v1", self.brand)
        self.assertIn(f"status: {' | '.join(RECEIPT_STATUSES)}", self.brand)
        dictionary = self.brand.split("## Status dictionary", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in dictionary.splitlines() if line.startswith("| `")]
        statuses = [re.match(r"\| `[^`]+` \| `([^`]+)` \|", line).group(1) for line in rows]
        self.assertEqual(list(RECEIPT_STATUSES), statuses)
        enumeration = ", ".join(f"`{status}`" for status in RECEIPT_STATUSES[:-1])
        self.assertIn(f"Keep {enumeration}, and `{RECEIPT_STATUSES[-1]}` distinct", self.text)


if __name__ == "__main__":
    unittest.main()

"""Integrity pins for the adopted super-docx package.

The package imports the `docx` Agent Skill from anthropics/skills at the
immutable commit frozen by the 2026-11-18 import review (docskills-U0, R1
ruling; docx is the R2 second of the four document-format adoptions): the
upstream guide body is embedded verbatim below the entry's wrapper, the
four top-level scripts plus __init__, the five comment templates and the
50-file office/ shared subtree are vendored byte-identical, and the
license copy is retained byte-identical including the upstream
placeholder copyright line. Following the super-gh-axi, super-i-have-adhd
and super-pdf precedents, the pins live in this test module: upstream
baseline digests are UPSTREAM_* constants, the vendored file digests are
VENDORED_SHA256 (non-office) plus the office pins imported from the
office-subtree parity module, and the embedded frozen body is bound by
digest.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from scripts.check_repository import INSTALLABLE_SKILL_PATHS, INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS

try:  # canonical invocation: unittest discovery over the tests directory
    from test_office_subtree_parity import OFFICE_SUBTREE_SHA256
except ImportError:  # direct module invocation from the repository root
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_office_subtree_parity import OFFICE_SUBTREE_SHA256

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-docx"
SKILL = SKILL_DIR / "SKILL.md"

# Upstream baseline: anthropics/skills, frozen by the 2026-11-18 import review
# (docs/research/2026-11-18-anthropics-skills-import-review.md, appendix A).
UPSTREAM_COMMIT = "e4bb5d960d87126ff3b3a8af1a104b7db67560ba"
UPSTREAM_SKILL_SHA256 = "895d5aa6c4cd98e4aed4c995d846f056f3549086e79bcd6617afea6014f82288"
UPSTREAM_LICENSE_SHA256 = "58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd"

# The upstream SKILL.md body as embedded in this package's SKILL.md:
# everything below the upstream `# DOCX creation, editing, and analysis` title.
FROZEN_BODY_FIRST = "A `.docx` is a ZIP archive of XML files. Choose your approach by task:"
FROZEN_BODY_LAST = (
    "`docx` (npm, preinstalled — install only if `require('docx')` fails) · `pandoc` · "
    "LibreOffice (`soffice`) · `pdftoppm` (Poppler)"
)
FROZEN_BODY_SHA256 = "db55bfac2feea71c98ee174199b51d9664667a37162f1ee0ae5b9a76e0ba0ea0"

# Vendored byte-identical files outside the office/ subtree (appendix A pins).
# The 50 office/ files are pinned by tests/test_office_subtree_parity.py.
VENDORED_SHA256 = {
    "scripts/__init__.py": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
    "scripts/accept_changes.py": "0c991d2bc7304a1248e9f3bf9b1498f0b6e76641fc457e7cbd73c99b4eef3a74",
    "scripts/comment.py": "37d116e5f56bb142b208c6c6a4bbcf960495abf470ddb7c6675ccfac864ba3d7",
    "scripts/merge_runs.py": "3ab367fd7fba4647943d0aa5e65203b15458551410f5ffc821d902616a4b9f40",
    "scripts/templates/comments.xml": "a08ba83ee8790ac9e3dc61921f4988f19edd7e06ac09d6f1897a877c1581818d",
    "scripts/templates/commentsExtended.xml": "544eeecfeceed4b468fff163cd9c366d33641c8b8ab691ce002576197846afe8",
    "scripts/templates/commentsExtensible.xml": "bad10b3283e6ad6e7ef6d1ca5169683721ed690ee331282c65df04017e080631",
    "scripts/templates/commentsIds.xml": "db20f9616e004ec42ef736e80c2384e45db0f8d1194d31dc8b37c7d6ecdd6420",
    "scripts/templates/people.xml": "056f63aa1197fd8c9dda980c9f1b9ff016fd5fa4a462df8aec5f384f39d23e37",
}

# The upstream trigger surface the entry description must preserve: the
# capability verbs, the keyword list, the formatting face, every operation
# trigger, the deliverable sentence and the closing exclusion sentence.
TRIGGER_SURFACE = (
    "create, read, edit, or manipulate Word documents (.docx files) or Word templates (.dotx files)",
    "'Word doc', 'word document', '.docx', '.dotx'",
    "tables of contents, headings, page numbers, or letterheads",
    "extracting or reorganizing content from .docx or .dotx files",
    "inserting or replacing images in documents",
    "performing find-and-replace in Word files",
    "working with tracked changes or comments",
    "converting content into a polished Word document",
    "If the user asks for a 'report', 'memo', 'letter', 'template', or similar deliverable as a Word or .docx file, use this skill.",
    "Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation.",
)

# The bidirectional carve with super-pdf (judged 2026-11-19): this side
# claims Word-to-PDF conversion; the reverse sentence lands in super-pdf's
# local-layer description.
CARVE_SENTENCE = "Use when converting a Word document to PDF (soffice path); PDF-internal work belongs to super-pdf."
REVERSE_CARVE_SENTENCE = "Producing a PDF from a Word document belongs to super-docx."

# Fail-closed dependency contract surface: every dependency face named by
# references/setup.md, declared or undeclared upstream alike.
SETUP_DEPENDENCIES = (
    "Python 3.11+",
    "| Node.js |",
    "npm `docx` library",
    "| `pandoc` |",
    "LibreOffice (`soffice` on PATH)",
    "`pdftoppm` (Poppler)",
    "| `zip` |",
    "| `defusedxml` |",
    "| `lxml` |",
    "node --version",
    'node -e "require(\'docx\')"',
    "pandoc --version",
    "soffice --version",
    "pdftoppm -v",
    "defusedxml.__version__",
    "lxml.etree.__version__",
)

RECEIPT_STATUSES = ("complete", "complete_with_holds", "hold", "failed")

ALLOWED_PACKAGE_FILES = {
    "SKILL.md",
    "references/setup.md",
    "references/provenance.md",
    "references/brand-layer.md",
    *VENDORED_SHA256,
    *(f"scripts/office/{relative}" for relative in OFFICE_SUBTREE_SHA256),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_slice(text: str) -> str:
    start = text.index(FROZEN_BODY_FIRST)
    end = text.index(FROZEN_BODY_LAST, start) + len(FROZEN_BODY_LAST)
    return text[start:end]


class SuperDocxPackageTest(unittest.TestCase):
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
        self.assertEqual("super-docx", name.group(1).strip())
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
        self.assertIn("the upstream docx skill", description)
        self.assertIn("still triggers", description)
        self.assertIn(CARVE_SENTENCE, description)

    def test_frozen_upstream_body_is_verbatim(self) -> None:
        body = _frozen_slice(self.text)
        self.assertEqual(FROZEN_BODY_SHA256, hashlib.sha256(body.encode("utf-8")).hexdigest())

    def test_vendored_files_match_the_pinned_digests(self) -> None:
        for relative, digest in sorted(VENDORED_SHA256.items()):
            path = SKILL_DIR / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(digest, _sha256(path), relative)

    def test_office_subtree_is_vendored_inside_the_package(self) -> None:
        office_root = SKILL_DIR / "scripts" / "office"
        self.assertTrue(office_root.is_dir())
        self.assertEqual(50, len(OFFICE_SUBTREE_SHA256))
        for relative in OFFICE_SUBTREE_SHA256:
            self.assertTrue((office_root / relative).is_file(), relative)

    def test_package_file_whitelist(self) -> None:
        actual = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }
        self.assertEqual(ALLOWED_PACKAGE_FILES, actual)

    def test_provenance_pins_the_locked_source(self) -> None:
        self.assertIn(f"Immutable commit | `{UPSTREAM_COMMIT}`", self.provenance)
        self.assertIn(f"Upstream SKILL.md SHA-256 | `{UPSTREAM_SKILL_SHA256}`", self.provenance)
        self.assertIn(f"Embedded body SHA-256 | `{FROZEN_BODY_SHA256}`", self.provenance)
        self.assertIn(f"Upstream LICENSE.txt SHA-256 | `{UPSTREAM_LICENSE_SHA256}`", self.provenance)
        self.assertIn("61 blobs, 1,166,158 B", self.provenance)
        for relative, digest in sorted(VENDORED_SHA256.items()):
            self.assertIn(digest[:8], self.provenance, f"provenance must cite the {relative} digest")

    def test_provenance_pins_the_office_shared_subtree(self) -> None:
        self.assertIn("50-file `scripts/office/` shared subtree", self.provenance)
        self.assertIn("50 blobs, 1,109,154 B", self.provenance)
        self.assertIn("tests/test_office_subtree_parity.py", self.provenance)
        self.assertIn("import review §5", self.provenance)

    def test_provenance_reproducible_check_matches_the_pins(self) -> None:
        block = self.provenance.split("## Reproducible source check", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"Expected SHA-256: `{UPSTREAM_SKILL_SHA256}`", block)
        self.assertIn(f"Expected SHA-256: `{UPSTREAM_LICENSE_SHA256}`", block)
        source_urls = re.findall(
            r"raw\.githubusercontent\.com/anthropics/skills/([^/]+)/skills/docx/", block
        )
        self.assertTrue(source_urls, "the reproducible check must record its source recipe")
        self.assertEqual({UPSTREAM_COMMIT}, set(source_urls))

    def test_license_copy_is_byte_identical_to_the_upstream_license(self) -> None:
        license_copy = ROOT / "LICENSES" / "Docx-Apache-2.0.txt"
        self.assertTrue(license_copy.is_file())
        self.assertEqual(UPSTREAM_LICENSE_SHA256, _sha256(license_copy))
        text = license_copy.read_text(encoding="utf-8")
        self.assertIn("Copyright [yyyy] [name of copyright owner]", text)
        self.assertNotIn("Copyright 2026 Anthropic", text)

    def test_provenance_records_the_placeholder_anomaly_and_ruling(self) -> None:
        self.assertIn("Placeholder copyright-line anomaly", self.provenance)
        self.assertIn("Copyright [yyyy] [name of copyright owner]", self.provenance)
        self.assertIn("e4bb5d960d", self.provenance)

    def test_notice_documents_the_docx_entry(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## Docx", notices)
        self.assertIn("LICENSES/Docx-Apache-2.0.txt", notices)
        self.assertIn("Anthropic PBC, from anthropics/skills @ e4bb5d960d", notices)

    def test_setup_documents_fail_closed_dependencies(self) -> None:
        for dependency in SETUP_DEPENDENCIES:
            self.assertIn(dependency, self.setup, f"setup must name {dependency}")
        self.assertIn("Fail-closed", self.setup)
        self.assertIn("named hold", self.setup)
        self.assertIn("No dependency is vendored", self.setup)
        self.assertIn("**not declared anywhere in the upstream Dependencies line**", self.setup)
        self.assertIn("with no upstream declaration", self.setup)

    def test_setup_documents_the_office_subtree_and_script_inventory(self) -> None:
        self.assertIn("scripts/office/", self.setup)
        self.assertIn("50 files", self.setup)
        self.assertIn("test_office_subtree_parity.py", self.setup)
        self.assertIn("independently installable", self.setup)
        self.assertIn("exit 2 on missing arguments", self.setup)
        self.assertIn("`--help` with exit 0", self.setup)
        self.assertIn("no `--help`", self.setup)
        self.assertIn("no argument guard", self.setup)

    def test_provenance_documents_the_fidelity_classification(self) -> None:
        match = re.search(r"^Classification: `([^`]+)`", self.provenance, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("faithful", match.group(1))
        self.assertIn("Skill-standard §2.3", self.provenance)

    def test_bidirectional_carve_with_super_pdf_lands_on_both_sides(self) -> None:
        self.assertIn("Capability carve (bidirectional with super-pdf", self.provenance)
        self.assertIn("every canonical description", self.provenance.lower())
        self.assertIn("2026-11-19", self.provenance)
        self.assertIn(REVERSE_CARVE_SENTENCE, self.provenance)
        pdf_description = re.search(
            r'^description:\s*"(.*)"$',
            re.match(
                r"^---\n(?P<frontmatter>.*?)\n---\n",
                (ROOT / "skills" / "super-pdf" / "SKILL.md").read_text(encoding="utf-8"),
                re.DOTALL,
            ).group("frontmatter"),
            re.MULTILINE,
        ).group(1)
        self.assertIn(REVERSE_CARVE_SENTENCE, pdf_description)
        # The frozen super-pdf guide body keeps its pinned digest — the carve
        # touches the local-layer description only.
        self.assertIn(
            "its frozen guide untouched",
            self.provenance,
        )

    def test_provenance_documents_the_visual_deferral(self) -> None:
        self.assertIn("deferral", self.provenance.lower())
        self.assertIn("#478", self.provenance)
        self.assertIn("16→17", self.provenance)
        self.assertIn("17→18", self.provenance)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-docx/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        self.assertIn(contract["startup"], self.brand)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.brand)
        self.assertIn("raw evidence", self.brand)

    def test_gate_registration_covers_the_package(self) -> None:
        self.assertIn("skills/super-docx/SKILL.md", INSTALLABLE_SKILL_PATHS)
        self.assertIn("skills/super-docx/SKILL.md", SKILL_BRAND_CONTRACTS)

    def test_package_documents_the_status_vocabulary_and_receipt_schema(self) -> None:
        self.assertIn("schema: super-docx.receipt.v1", self.brand)
        self.assertIn(f"status: {' | '.join(RECEIPT_STATUSES)}", self.brand)
        dictionary = self.brand.split("## Status dictionary", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in dictionary.splitlines() if line.startswith("| `")]
        statuses = [re.match(r"\| `[^`]+` \| `([^`]+)` \|", line).group(1) for line in rows]
        self.assertEqual(list(RECEIPT_STATUSES), statuses)
        enumeration = ", ".join(f"`{status}`" for status in RECEIPT_STATUSES[:-1])
        self.assertIn(f"Keep {enumeration}, and `{RECEIPT_STATUSES[-1]}` distinct", self.text)


if __name__ == "__main__":
    unittest.main()

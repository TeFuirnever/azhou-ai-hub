"""Byte pins for the vendored Office shared subtree.

The upstream `anthropics/skills` docx/pptx/xlsx packages each carry a
byte-identical ``scripts/office/`` subtree (50 blobs, 1,109,154 B; import
review §5 proved the three copies equal by git blob SHA). This repository
adopts "one byte-identical copy per package" so every canonical package
stays independently installable, and this module is the mechanical pin:
the single pinning source is appendix A of the 2026-11-18 import review,
and each adopted package's ``scripts/office/`` copy is checked file-by-file
against it. Adding the xlsx (U3) or pptx (U4) adoption extends
``OFFICE_SUBTREE_PACKAGES`` with one entry; the per-package loop below then
covers the cross-package parity without a second manifest.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
IMPORT_REVIEW = ROOT / "docs" / "research" / "2026-11-18-anthropics-skills-import-review.md"

# The canonical office/ prefix inside the import review's appendix A. U0 §5
# records the executed correction: the authoritative path is
# skills/<pkg>/scripts/office/ (not skills/<pkg>/office/).
APPENDIX_OFFICE_PREFIX = "skills/docx/scripts/office/"
SHARED_ANNOTATION = "; shared: docx/pptx/xlsx"

# Import-review §5 pins for the subtree as a whole.
OFFICE_SUBTREE_PINNED_COUNT = 50
OFFICE_SUBTREE_PINNED_BYTES = 1_109_154

# Adopted packages carrying a vendored office/ copy, keyed by canonical
# package name. U2 (docx) lands the first entry; U3/U4 append theirs here —
# the shared loop below then enforces cross-package parity per package
# without duplicating the manifest.
OFFICE_SUBTREE_PACKAGES: dict[str, str] = {
    "super-docx": "skills/super-docx/scripts/office/",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_office_subtree_pins() -> dict[str, str]:
    """Return {office-relative path: SHA-256} from appendix A, failing closed.

    The appendix is the single pinning source (import review §9); the
    shared annotation is asserted so a silently re-scoped appendix cannot
    pass as the same manifest.
    """
    text = IMPORT_REVIEW.read_text(encoding="utf-8")
    appendix = text.split("## 附录 A", 1)[1]
    pins: dict[str, str] = {}
    for line in appendix.splitlines():
        match = re.match(rf"^{re.escape(APPENDIX_OFFICE_PREFIX)}(\S+)\s+([0-9a-f]{{64}})(.*)$", line)
        if match is None:
            continue
        relative, digest, tail = match.groups()
        if SHARED_ANNOTATION not in tail:
            raise AssertionError(f"office pin missing the three-package share annotation: {line}")
        pins[relative] = digest
    if len(pins) != OFFICE_SUBTREE_PINNED_COUNT:
        raise AssertionError(
            f"appendix A office section pins {len(pins)} files, expected {OFFICE_SUBTREE_PINNED_COUNT}"
        )
    return pins


OFFICE_SUBTREE_SHA256 = load_office_subtree_pins()


class OfficeSubtreeParityTest(unittest.TestCase):
    def test_pins_loaded_from_the_import_review(self) -> None:
        # The pinning source is the import review itself, not a copy of it.
        self.assertEqual(OFFICE_SUBTREE_PINNED_COUNT, len(OFFICE_SUBTREE_SHA256))
        self.assertEqual(
            "bcfa227707681ffbecc0f0af5c4e7155407b3baaf5cec5cdd41387c97cdd40c7",
            OFFICE_SUBTREE_SHA256["soffice.py"],
        )
        self.assertEqual(
            "8c10ec61d8e880877515019e1fe8fab9a1f590c9e50ed0631418e960aca1e313",
            OFFICE_SUBTREE_SHA256["validate.py"],
        )

    def test_adopted_packages_match_the_pinned_subtree_bytes(self) -> None:
        for package, office_root in sorted(OFFICE_SUBTREE_PACKAGES.items()):
            root = ROOT / office_root
            self.assertTrue(root.is_dir(), f"{package}: {office_root} missing")
            actual_files = {
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            }
            self.assertEqual(
                set(OFFICE_SUBTREE_SHA256),
                actual_files,
                f"{package}: office/ tree differs from the pinned manifest",
            )
            for relative, digest in sorted(OFFICE_SUBTREE_SHA256.items()):
                self.assertEqual(digest, _sha256(root / relative), f"{package}: {relative}")

    def test_adopted_office_subtree_keeps_the_pinned_size(self) -> None:
        for package, office_root in sorted(OFFICE_SUBTREE_PACKAGES.items()):
            root = ROOT / office_root
            total = sum(
                path.stat().st_size
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
            self.assertEqual(
                OFFICE_SUBTREE_PINNED_BYTES,
                total,
                f"{package}: office/ subtree byte total drifted from the §5 pin",
            )

    def test_office_copy_stays_inside_its_own_package(self) -> None:
        # Independent install (skill-standard §2): the vendored office files
        # contain no path reference reaching outside their own package
        # (verified 2026-11-19: zero "../" occurrences in the subtree), so a
        # single copied package carries its whole Office helper surface.
        for package, office_root in sorted(OFFICE_SUBTREE_PACKAGES.items()):
            for path in (ROOT / office_root).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    "../",
                    text,
                    f"{package}: {path.name} references paths outside the package",
                )


if __name__ == "__main__":
    unittest.main()

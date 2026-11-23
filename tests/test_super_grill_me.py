"""Package integrity tests for skills/super-grill-me."""

from __future__ import annotations

import hashlib
import struct
import unittest
from pathlib import Path

from scripts.check_repository import (
    INSTALLABLE_SKILL_PATHS,
    RENAMED_AWAY_SKILLS,
    SKILL_BRAND_CONTRACTS,
    check_skill_brand_contract,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = "skills/super-grill-me/SKILL.md"
PACKAGE = ROOT / "skills" / "super-grill-me"

UPSTREAM_COMMIT = "d1478fcb140db0b93c0c8df17bcfd311844749d0"
UPSTREAM_SKILL_SHA256 = "caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637"
UPSTREAM_LICENSE_SHA256 = "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"
LOCAL_SKILL_SHA256 = "72506fd4ae6bb92471f03a893ed63ec429e9033f56bfee2a7d3802d2ed241dc3"
SHOWCASE_SHIPPED_SHA256 = "1230068b932666f597f92f32bb54288150597f201ec353592c63f09d245526d5"

EXPECTED_FILES = frozenset(
    {
        "SKILL.md",
        "LICENSE",
        "references/provenance.md",
        "references/setup.md",
        "references/upstream-compatibility.md",
    }
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SuperGrillMePackageTest(unittest.TestCase):
    def test_license_is_the_upstream_root_license(self) -> None:
        local = (PACKAGE / "LICENSE").read_bytes()
        self.assertEqual(sha256(local), UPSTREAM_LICENSE_SHA256)
        self.assertEqual((ROOT / "LICENSES" / "Mattpocock-Skills-MIT.txt").read_bytes(), local)

    def test_package_file_set_is_exhaustive(self) -> None:
        present = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
        }
        self.assertEqual(present, set(EXPECTED_FILES))

    def test_provenance_records_the_upstream_anchor(self) -> None:
        provenance = (PACKAGE / "references" / "provenance.md").read_text(encoding="utf-8")
        for value in (UPSTREAM_COMMIT, UPSTREAM_SKILL_SHA256, UPSTREAM_LICENSE_SHA256):
            self.assertIn(value, provenance)

    def test_entry_matches_its_local_pin(self) -> None:
        self.assertEqual(sha256((PACKAGE / "SKILL.md").read_bytes()), LOCAL_SKILL_SHA256)

    def test_showcase_scene_is_metadata_sanitized(self) -> None:
        data = (ROOT / "assets" / "skills" / "super-grill-me-effect.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(sha256(data), SHOWCASE_SHIPPED_SHA256)
        chunk_types = []
        offset = 8
        while offset < len(data):
            (length,) = struct.unpack(">I", data[offset : offset + 4])
            chunk_types.append(data[offset + 4 : offset + 8])
            offset += 12 + length
        self.assertEqual(set(chunk_types), {b"IHDR", b"IDAT", b"IEND"})

    def test_repository_gate_accepts_the_package(self) -> None:
        errors = [error for error in check_skill_brand_contract(ROOT) if "super-grill-me" in error]
        self.assertEqual(errors, [])
        self.assertIn(SKILL_PATH, INSTALLABLE_SKILL_PATHS)
        self.assertEqual(RENAMED_AWAY_SKILLS.get("grill-me"), "super-grill-me")
        self.assertNotIn("brand_path", SKILL_BRAND_CONTRACTS[SKILL_PATH])


if __name__ == "__main__":
    unittest.main()

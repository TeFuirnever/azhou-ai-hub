from __future__ import annotations

import hashlib
import re
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
UPSTREAM_GRILL_ME_SHA256 = "caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637"
UPSTREAM_GRILLING_SHA256 = "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2"
UPSTREAM_LICENSE_SHA256 = "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"
UPSTREAM_SPAN_SHA256 = {
    "open": "21e744a90ca29f559723b3573f1b4ed2e29400f6160b35798343f69899c33220",
    "facts": "4ca3c4ec1305a1640a098bdc38cf527128174efa0f102f7ffb6bad17f3d92f40",
    "tail": "a49680e9d29e7f6fb031ce5674997f973c05d8e3e1890f6bcd4f07fcc483d7f5",
}
GL2_SENTENCE = (
    " On a harness without sub-agents, look the fact up yourself and say that it was "
    "not checked from an independent context window."
)
GL2_SENTENCE_SHA256 = "bacd5f8414ebbf1992c588ad608a674b2a3bc702c44d6f18c74098b1c8247d74"
LOCAL_SKILL_SHA256 = "05e356f839278a294af9ec5dfd831c6fd3b42fba58b42fd0e49312b1859ffd4d"
NOTHING_NAMED_ANCHOR = "🔒 阿舟暂停这一项（reason=nothing-named）"
SHOWCASE_SHIPPED_SHA256 = "1675128a0270a7c197beea639f0a218b50c8257ad4892850444b4ab399aa6461"

SPAN_OPEN_START = "Interview the user relentlessly"
SPAN_FACTS_START = "Finding _facts_ is your job"
SPAN_FACTS_END = "The _decisions_ are the user's: put each to them and wait."
SPAN_TAIL_START = "\n\nThe session is done when the frontier is empty"

EXPECTED_FILES = frozenset(
    {
        "SKILL.md",
        "LICENSE",
        "references/brand-layer.md",
        "references/provenance.md",
        "references/setup.md",
        "references/upstream-compatibility.md",
    }
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        for value in (UPSTREAM_COMMIT, UPSTREAM_GRILL_ME_SHA256, UPSTREAM_GRILLING_SHA256, UPSTREAM_LICENSE_SHA256):
            self.assertIn(value, provenance)

    def test_instruction_body_keeps_the_upstream_spans(self) -> None:
        text = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        open_start = text.index(SPAN_OPEN_START)
        facts_start = text.index(SPAN_FACTS_START)
        facts_end = text.index(SPAN_FACTS_END) + len(SPAN_FACTS_END)
        tail_start = text.index(SPAN_TAIL_START)
        self.assertEqual(sha256_text(text[open_start:facts_start]), UPSTREAM_SPAN_SHA256["open"])
        self.assertEqual(sha256_text(text[facts_start:facts_end]), UPSTREAM_SPAN_SHA256["facts"])
        self.assertEqual(text[facts_end:tail_start], GL2_SENTENCE)
        self.assertEqual(sha256_text(GL2_SENTENCE), GL2_SENTENCE_SHA256)
        self.assertEqual(sha256_text(text[tail_start:]), UPSTREAM_SPAN_SHA256["tail"])

    def test_entry_matches_its_local_pin(self) -> None:
        self.assertEqual(sha256((PACKAGE / "SKILL.md").read_bytes()), LOCAL_SKILL_SHA256)

    def test_entry_carries_the_hold_anchor_the_brand_layer_defines(self) -> None:
        """The nothing-named hold anchor is one protocol token.

        The stage table in the brand layer defines the token. The entry file
        must carry the same token once, or a model that reads only the entry
        broadcasts a hold the layer does not document.
        """
        layer = (PACKAGE / "references" / "brand-layer.md").read_text(encoding="utf-8")
        entry = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| the request named nothing to grill \| `([^`]+)` \|$", layer, re.MULTILINE)
        self.assertEqual(rows, [NOTHING_NAMED_ANCHOR])
        self.assertEqual(entry.count(NOTHING_NAMED_ANCHOR), 1)

    def test_repository_gate_accepts_the_package(self) -> None:
        errors = [error for error in check_skill_brand_contract(ROOT) if "super-grill-me" in error]
        self.assertEqual(errors, [])
        self.assertIn(SKILL_PATH, INSTALLABLE_SKILL_PATHS)
        self.assertEqual(RENAMED_AWAY_SKILLS.get("grill-me"), "super-grill-me")
        self.assertEqual(RENAMED_AWAY_SKILLS.get("grilling"), "super-grill-me")
        self.assertEqual(
            SKILL_BRAND_CONTRACTS[SKILL_PATH].get("brand_path"),
            "skills/super-grill-me/references/brand-layer.md",
        )

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


if __name__ == "__main__":
    unittest.main()

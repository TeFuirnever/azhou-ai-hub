"""Package integrity tests for skills/super-brainstorming.

The package adapts obra/superpowers tag v7.0.2 (commit 22f0b463...):
verbatim files are pinned against the upstream pin, local anchor-span
digests are pinned, and full local digests cover every byte of
the four delta files, whose upstream SHA-256 anchors are recorded in
provenance.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from scripts.check_repository import (
    INSTALLABLE_SKILL_PATHS,
    RENAMED_AWAY_SKILLS,
    SKILL_BRAND_CONTRACTS,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "super-brainstorming"

UPSTREAM_COMMIT = "22f0b463e7a5e579904dd6211a520321035526f7"

# SHA-256 of each upstream skills/brainstorming/ file at the pin, as recorded
# in references/provenance.md. Verbatim files assert equality; delta files
# use these as drift anchors only.
UPSTREAM_SHA256 = {
    "SKILL.md": "2c9ca71f94886f9ca9f4aef055f7cafb3e1a9bdf3aeebf8f4cb547c69405d207",
    "builder-check-prompt.md": "36d51a4723d6f0a3ce5811a0ea3b3a8424f07533947e1355f5d8cb8cce40c55e",
    "visual-companion.md": "6ffcb038b53254bd31debaa15e12dcd4ff24bd63d690e0b644ac6396701cf2e2",
    "scripts/server.cjs": "763abf96510e0b892a1141397b31aa82ef900cf87ed34dde94bc8782baf4a7ca",
    "scripts/start-server.sh": "314dd68dc00e8dd94c7491aca8a5f004c7fddffc161e2b07482f29f48d13659a",
    "scripts/stop-server.sh": "0b5ccbbd57f62d3ed88993f7940b5ee0e5c0fc9b21c550c623da4f6292e47daf",
    "scripts/frame-template.html": "6a8a4e58bd6a44b904e2e3c57de774481d909204597e1498de53f1b2fecc4c4e",
    "scripts/helper.js": "43c6d69954a46ec34a2a262bcc62a9a7e83e839c739f199cb72646d397c686e3",
}
UPSTREAM_LICENSE_SHA256 = "a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400"

VERBATIM_FILES = (
    "builder-check-prompt.md",
    "scripts/start-server.sh",
    "scripts/stop-server.sh",
    "scripts/helper.js",
)

DELTA_FILE_SHA256 = {
    "SKILL.md": "503b5fc3240e90145ad76b3db374d3c446e8ce636bcd84f1be0ca23e3ef36543",
    "visual-companion.md": "0d00eeb35af93d8d822f2cde5088992ca442f1df87fcb6080f31142c66ff461c",
    "scripts/server.cjs": "3a3452c0e6cf6671e8ad5472832668a35786fb3e932bd3f087bd1ca7fe04d832",
    "scripts/frame-template.html": "6b827d92843c0c2d2642c155add584d3bfbf9599d8810500e7fa59ba72e49c2a",
}

EXPECTED_FILES = frozenset(
    {
        "SKILL.md",
        "LICENSE",
        "builder-check-prompt.md",
        "visual-companion.md",
        "references/provenance.md",
        "references/setup.md",
        "references/brand-layer.md",
        "references/upstream-compatibility.md",
        "scripts/server.cjs",
        "scripts/start-server.sh",
        "scripts/stop-server.sh",
        "scripts/frame-template.html",
        "scripts/helper.js",
    }
)

# Local anchor-span digests pinned between anchors (sha256 of text between anchors).
SEGMENTS = {
    "SKILL.md": (
        ("## Red Flags", None, "014a99130262e31b5aeb5cbc60cf2d531ceaf70eed98e51969fe8ebdda4b4470"),
        ("## The Conversation", "## Play It Back", "460a430f91b9e47563c645e0628bb50ee381d62e3723026379a63b612c8b546c"),
    ),
    "visual-companion.md": (
        ("**Launching the server by platform:**", None, "295ba52fcba12be372f776fa2f0209f13ef190256fc95276a43515f9587baaa5"),
    ),
    "scripts/server.cjs": (
        ("function brandMarkup() {", None, "f76e4de24366cf94a9a0ca23dd024e54801ae130bb303ca4b1b1d07a1b4ff78d"),
    ),
    "scripts/frame-template.html": (
        ("<!DOCTYPE", "<style>", "ac79f21fff31d746f97bc28d783ace6a86c59ea08b6b42c8d550204c7aeffa68"),
    ),
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def segment_digest(text: str, start: str, end: str | None) -> str:
    begin = 0 if start is None else text.index(start)
    stop = len(text) if end is None else text.index(end)
    return sha256_text(text[begin:stop])


class SuperBrainstormingPackageTest(unittest.TestCase):
    def test_verbatim_files_match_upstream_pin(self) -> None:
        for relative in VERBATIM_FILES:
            with self.subTest(file=relative):
                local = (PACKAGE / relative).read_bytes()
                self.assertEqual(
                    hashlib.sha256(local).hexdigest(),
                    UPSTREAM_SHA256[relative],
                    f"{relative} drifted from the upstream pin {UPSTREAM_COMMIT[:12]}",
                )

    def test_license_matches_upstream_root_license(self) -> None:
        local = (PACKAGE / "LICENSE").read_bytes()
        self.assertEqual(hashlib.sha256(local).hexdigest(), UPSTREAM_LICENSE_SHA256)
        mirrored = (ROOT / "LICENSES" / "Obra-Superpowers-MIT.txt").read_bytes()
        self.assertEqual(mirrored, local)

    def test_package_file_set_is_exhaustive(self) -> None:
        present = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
        }
        self.assertEqual(present, set(EXPECTED_FILES))

    def test_provenance_records_upstream_drift_anchors(self) -> None:
        provenance = (PACKAGE / "references" / "provenance.md").read_text(encoding="utf-8")
        for relative, digest in UPSTREAM_SHA256.items():
            with self.subTest(file=relative):
                self.assertIn(digest, provenance)
        self.assertIn(UPSTREAM_LICENSE_SHA256, provenance)
        self.assertIn(UPSTREAM_COMMIT, provenance)

    def test_anchor_span_digests_are_pinned(self) -> None:
        for relative, segments in SEGMENTS.items():
            text = (PACKAGE / relative).read_text(encoding="utf-8")
            for start, end, digest in segments:
                with self.subTest(file=relative, start=start):
                    self.assertEqual(segment_digest(text, start, end), digest)

    def test_delta_files_match_full_local_digests(self) -> None:
        for relative, digest in DELTA_FILE_SHA256.items():
            with self.subTest(file=relative):
                local = (PACKAGE / relative).read_bytes()
                self.assertEqual(
                    hashlib.sha256(local).hexdigest(),
                    digest,
                    f"{relative} drifted from its pinned local bytes",
                )

    def test_skill_md_keeps_deltas_and_foundation(self) -> None:
        text = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Azhou skill. Renamed from brainstorming (the old name still triggers this skill).", text)
        self.assertIn("🦊 阿舟 · Brainstorming", text)
        self.assertNotIn("superpowers:writing-plans", text)
        self.assertNotIn("docs/superpowers/specs/", text)
        self.assertIn("Classification: `adapted`", (PACKAGE / "references" / "provenance.md").read_text(encoding="utf-8"))

    def test_brand_contract_registered(self) -> None:
        key = "skills/super-brainstorming/SKILL.md"
        self.assertIn(key, INSTALLABLE_SKILL_PATHS)
        self.assertIn(key, SKILL_BRAND_CONTRACTS)
        contract = SKILL_BRAND_CONTRACTS[key]
        self.assertEqual(contract["display_name"], "Brainstorming")
        self.assertIn("brand_path", contract)
        self.assertEqual(RENAMED_AWAY_SKILLS.get("brainstorming"), "super-brainstorming")

    def test_startup_line_consistent_between_contract_files(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-brainstorming/SKILL.md"]
        startup = contract["startup"]
        self.assertIn(startup, (PACKAGE / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn(startup, (PACKAGE / "references" / "brand-layer.md").read_text(encoding="utf-8"))

    def test_showcase_scene_is_metadata_sanitized(self) -> None:
        import struct

        scene = ROOT / "assets" / "skills" / "super-brainstorming-effect.png"
        data = scene.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "7a6885b4bdb3f12b4a7b56ab885f6e366a9a4428fb630121927dee14c36da412",
        )
        chunks = []
        offset = 8
        while offset < len(data):
            (length,) = struct.unpack(">I", data[offset : offset + 4])
            chunks.append(data[offset + 4 : offset + 8].decode("ascii"))
            offset += 12 + length
        self.assertEqual(set(chunks), {"IHDR", "IDAT", "IEND"})
        self.assertEqual(chunks[0], "IHDR")
        self.assertEqual(chunks[-1], "IEND")


if __name__ == "__main__":
    unittest.main()

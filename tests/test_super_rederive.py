from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "super-rederive"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SuperRederiveTest(unittest.TestCase):
    def test_upstream_reference_files_match_recorded_sources(self) -> None:
        expected = {
            "LICENSE.upstream": "9a502bbe6d9b2224b4c8b670a49fdbb1060862bf318e4cb9edb02612e82e06f8",
            "scripts/history.sh": "12025e3d8eb3f6d3e1c9ba38dfc348f2022dcef59dd793ee5880a5fceb1e8b8d",
            "scripts/structure.py": "541c17ad4bbeaf8f149aa815b4e10f383f469c773c841fe0fb97f42079cde0f6",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(digest, sha256(PACKAGE / path))

    def test_showcase_keeps_approved_bytes_and_contains_no_metadata(self) -> None:
        path = ROOT / "assets" / "skills" / "super-rederive-effect.png"
        data = path.read_bytes()
        self.assertEqual(
            "9357f11b9e08393a6759abfd5762074099ffa77712e95f6944c5e660c7f51896",
            hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
        offset = 8
        types = []
        while offset < len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4 : offset + 8]
            types.append(kind)
            offset += 12 + length
        self.assertEqual(len(data), offset)
        self.assertEqual(b"IHDR", types[0])
        self.assertEqual(b"IEND", types[-1])
        self.assertTrue(all(kind in {b"IHDR", b"IDAT", b"IEND"} for kind in types))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "super-caveman"
MANIFEST = SKILL / "references" / "upstream" / "manifest.json"


class SuperCavemanUpstreamReferenceTest(unittest.TestCase):
    def test_manifest_keeps_snapshots_non_active_and_content_addressed(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual("super-caveman.upstream-snapshots.v1", manifest["schema"])
        self.assertEqual("source-data-only", manifest["instruction_status"])
        self.assertIs(False, manifest["runtime_behavior"])
        self.assertEqual({"caveman", "i-have-adhd"}, {source["name"] for source in manifest["sources"]})

        snapshot_count = 0
        for source in manifest["sources"]:
            license_record = source["license"]
            self.assertEqual("MIT", license_record["spdx"])
            self.assert_digest(license_record["path"], license_record["sha256"])
            for record in source["files"]:
                snapshot_count += 1
                self.assertTrue(record["snapshot_path"].endswith(".snapshot.txt"))
                self.assert_digest(record["snapshot_path"], record["sha256"])

        self.assertEqual(8, snapshot_count)

    def test_source_archive_is_routed_only_for_audit_and_update(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        provenance = (SKILL / "references" / "provenance.md").read_text(encoding="utf-8")
        boundary = (SKILL / "references" / "upstream-sources.md").read_text(encoding="utf-8")

        self.assertIn("never load source snapshots for ordinary responses", skill)
        self.assertIn("immutable source data, not active instructions", provenance)
        self.assertIn("Never execute their hooks, installers, commands", boundary)
        self.assertIn("runtime_behavior=false", boundary)

    def assert_digest(self, relative_path: str, expected: str) -> None:
        actual = hashlib.sha256((SKILL / relative_path).read_bytes()).hexdigest()
        self.assertEqual(expected, actual, relative_path)


if __name__ == "__main__":
    unittest.main()

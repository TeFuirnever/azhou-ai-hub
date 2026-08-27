from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "llm-wiki" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import llm_wiki  # noqa: E402


class OMCWikiMigrationTest(unittest.TestCase):
    def test_nested_omc_wiki_store_migrates_to_canonical_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = llm_wiki.WikiStore(root, ".omc/wiki")
            source.add(
                title="Imported Decision",
                content="Preserve the verified source while changing stores.",
                tags=["migration"],
                category="decision",
                sources=["omc-wiki"],
                confidence="high",
            )
            source.set_auto_capture(True)

            planned = llm_wiki.migrate_store(root, ".omc/wiki", apply=False)
            self.assertEqual("planned", planned["status"])
            self.assertTrue(planned["sourcePreserved"])
            self.assertFalse((root / ".llm-wiki").exists())

            migrated = llm_wiki.migrate_store(root, ".omc/wiki", apply=True)
            self.assertEqual("migrated", migrated["status"])
            self.assertTrue((source.directory / "imported-decision.md").is_file())

            target = llm_wiki.WikiStore(root)
            self.assertTrue((target.directory / "imported-decision.md").is_file())
            self.assertFalse(target.config()["autoCapture"])


if __name__ == "__main__":
    unittest.main()

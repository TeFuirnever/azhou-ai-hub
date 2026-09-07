import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from legacy import legacy_slugify


class LegacySlugifyTest(unittest.TestCase):
    def test_slash_paths_become_dashes(self) -> None:
        self.assertEqual("accounts-42-statements", legacy_slugify("/accounts/42/statements"))

    def test_edges_are_trimmed(self) -> None:
        self.assertEqual("legacy-link", legacy_slugify("  Legacy Link!  "))


if __name__ == "__main__":
    unittest.main()

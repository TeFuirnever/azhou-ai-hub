from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENTRY = ROOT / "skills" / "lavish" / "SKILL.md"
REFERENCE = ROOT / "skills" / "lavish" / "references" / "artifact-mode.md"

# Frozen 2026-09-05: the 15,479-byte monolith entry is the only entry size
# associated with recorded context-overflow sessions on the zcode host; the
# safe frontier is the largest entry with no overflow association (11,981B),
# rounded up to the promotion budget.
ENTRY_BUDGET_BYTES = 12000


class LavishEntryBudgetTest(unittest.TestCase):
    def test_entry_within_load_budget(self) -> None:
        size = ENTRY.stat().st_size
        self.assertLessEqual(
            size,
            ENTRY_BUDGET_BYTES,
            f"lavish entry is {size} bytes; budget is {ENTRY_BUDGET_BYTES} "
            "(split detail into references, keep the entry scannable)",
        )

    def test_artifact_reference_is_wired(self) -> None:
        text = ENTRY.read_text(encoding="utf-8")
        self.assertIn("references/artifact-mode.md", text)
        reference = REFERENCE.read_text(encoding="utf-8")
        self.assertIn("## Artifact mode workflow", reference)
        self.assertIn("## Visual guidance", reference)
        self.assertIn("## Playbooks", reference)
        self.assertIn("## Commands and rules", reference)


if __name__ == "__main__":
    unittest.main()

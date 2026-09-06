from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "arch-doc"
SCAN_FILES = [SKILL / "SKILL.md", SKILL / "references" / "templates" / "PROVENANCE.md"]
SCRIPT_REF = re.compile(r"`((?:<skill-dir>/)?scripts/[\w./-]+\.py)")


class ArchDocScriptPathTest(unittest.TestCase):
    """Regression for doc-code drift: every referenced skill script must
    resolve inside the arch-doc package. The 2026-09-05 audit found the entry
    pointing at repo-root `scripts/verify_doc.py`, which never existed; the
    scripts live under the skill directory.
    """

    def test_referenced_scripts_resolve_inside_skill(self) -> None:
        checked: list[str] = []
        for path in SCAN_FILES:
            text = path.read_text(encoding="utf-8")
            for match in SCRIPT_REF.finditer(text):
                ref = match.group(1)
                checked.append(f"{path.name}:{ref}")
                relative = ref.replace("<skill-dir>/", "")
                target = SKILL / relative
                self.assertTrue(
                    target.is_file(),
                    f"{path.name} references `{ref}` but {target} does not exist",
                )
        self.assertGreaterEqual(len(checked), 3, "expected at least the verify_doc/new_doc references")

    def test_no_bare_repo_root_script_reference(self) -> None:
        for path in SCAN_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "`scripts/",
                text,
                f"{path.name} references a repo-root scripts path; use `<skill-dir>/scripts/...`",
            )


if __name__ == "__main__":
    unittest.main()

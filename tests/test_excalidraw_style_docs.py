"""Style-doc alignment: excalidraw-diagram docs match the hand-drawn gate defaults.

Red symptom (craft-audit 2026-09-05, evolution-level #2): references/design-system.md
marketed roughness 0 ("Default to 0") and fontFamily 3 (Cascadia) as the default
modern style, while SKILL.md §4, references/json-schema.md,
references/element-templates.md and scripts/check-handdrawn-style.py all pin the
hand-drawn defaults roughness 1 / fontFamily 1. Recorded verdict: the gate is live
behavior; the doc aligns to it and the modern style becomes user-named opt-in.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "excalidraw-diagram"


def assert_style_docs_aligned(skill_dir: Path) -> None:
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "默认使用 hand-drawn preset：元素 `roughness: 1`，文字 `fontFamily: 1`" in skill_md

    json_schema = (skill_dir / "references" / "json-schema.md").read_text(encoding="utf-8")
    assert "默认阿舟手绘风使用 `fontFamily: 1`" in json_schema

    element_templates = (skill_dir / "references" / "element-templates.md").read_text(encoding="utf-8")
    assert "默认交付风格：`roughness: 1`、文字 `fontFamily: 1`" in element_templates

    design_system = (skill_dir / "references" / "design-system.md").read_text(encoding="utf-8")
    assert "Default to 0" not in design_system
    assert "## Modern Aesthetics (opt-in)" in design_system
    assert "only when the user explicitly names it or an existing asset contract requires it" in design_system
    assert "**Default for every production deliverable.**" in design_system
    assert "check-handdrawn-style.py" in design_system
    assert "`roughness: 0`" in design_system
    assert "for the clean/modern preset" not in design_system
    assert "Deliverables & Export" not in design_system


class ExcalidrawStyleDocsAlignedTest(unittest.TestCase):
    def test_entry_and_reference_defaults_still_pin_handdrawn(self) -> None:
        skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("默认使用 hand-drawn preset：元素 `roughness: 1`，文字 `fontFamily: 1`", skill_md)
        json_schema = (SKILL_DIR / "references" / "json-schema.md").read_text(encoding="utf-8")
        self.assertIn("默认阿舟手绘风使用 `fontFamily: 1`", json_schema)
        element_templates = (SKILL_DIR / "references" / "element-templates.md").read_text(encoding="utf-8")
        self.assertIn("默认交付风格：`roughness: 1`、文字 `fontFamily: 1`", element_templates)

    def test_design_system_modern_aesthetics_is_optin_and_defaults_match_gate(self) -> None:
        assert_style_docs_aligned(SKILL_DIR)


if __name__ == "__main__":
    unittest.main()

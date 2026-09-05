"""Brand startup-line value discipline across multi-stage brand layers.

skill-standard §3.2 (2026-09-05) requires startup broadcasts to carry concrete
values, with the machine-stable literal `unresolved` as the only legal pending
marker and angle brackets reserved to contract examples. The discipline was
promoted for excalidraw-diagram (candidate 2774771204f20d4ca2a28369); this batch
rolls the same discipline into the remaining multi-stage brand layers
(llm-wiki, repo-pedant, arch-doc, super-caveman). The startup contract strings
come from scripts/check_repository.py and must keep matching each brand layer
verbatim - the discipline sections are additive-only.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

_spec = importlib.util.spec_from_file_location(
    "azhou_check_repository", ROOT / "scripts" / "check_repository.py")
check_repository = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_repository)

# super-caveman lands with its own promotion flow (its runtime tree is
# digest-bound by the super-caveman benchmark); extend BRAND_SKILLS and the
# maps below in that same promotion when its brand layer adds the discipline.
BRAND_SKILLS = ("llm-wiki", "repo-pedant", "arch-doc")

DISCIPLINE_HEADINGS = {
    "llm-wiki": "启动行取值纪律",
    "repo-pedant": "启动行取值纪律",
    "arch-doc": "启动行取值纪律",
}

RESOLVED_SCOPE_MARKERS = {
    "llm-wiki": "知识范围锁定",
    "repo-pedant": "范围锁定",
    "arch-doc": "回填具体值",
}


def brand_layer_text(skill: str) -> str:
    contract = check_repository.SKILL_BRAND_CONTRACTS[f"skills/{skill}/SKILL.md"]
    return (ROOT / contract["brand_path"]).read_text(encoding="utf-8")


class BrandStartupDisciplineTest(unittest.TestCase):
    def test_startup_contract_matches_brand_layers_verbatim(self) -> None:
        for skill in BRAND_SKILLS:
            with self.subTest(skill=skill):
                contract = check_repository.SKILL_BRAND_CONTRACTS[f"skills/{skill}/SKILL.md"]
                self.assertIn(contract["startup"], brand_layer_text(skill))

    def test_brand_layers_carry_startup_value_discipline(self) -> None:
        for skill in BRAND_SKILLS:
            with self.subTest(skill=skill):
                text = brand_layer_text(skill)
                self.assertIn(DISCIPLINE_HEADINGS[skill], text)
                self.assertIn("unresolved", text)

    def test_discipline_pairs_pending_marker_with_resolution_point(self) -> None:
        for skill in BRAND_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(RESOLVED_SCOPE_MARKERS[skill], brand_layer_text(skill))

    def test_excalidraw_discipline_stays_landed(self) -> None:
        text = brand_layer_text("excalidraw-diagram")
        self.assertIn("启动行取值纪律", text)
        self.assertIn("unresolved", text)
        contract = check_repository.SKILL_BRAND_CONTRACTS["skills/excalidraw-diagram/SKILL.md"]
        self.assertIn(contract["startup"], text)


if __name__ == "__main__":
    unittest.main()

"""Docs-to-code contracts and completion-criteria pins from the coverage audit.

These are characterization pins for surfaces the coverage audit found
under-tested after the 2026-09-05/06 evolution batches:

- ``skills/repo-pedant/references/setup.md`` documents ``inventory_knowledge.py``
  snapshot flags; the audit requires every documented flag to exist in the
  script's argparse (the repo already hit doc-code drift twice via dead script
  pointers).
- ``AGENTS.md`` names the latest super-caveman promotion record; the pin keeps
  that pointer mechanically fresh instead of relying on manual reconciles.
- The completion-criteria additions (excalidraw SKILL.md sections 1-3,
  repo-pedant SKILL.md sections 2-3, lavish ``artifact-mode.md`` steps 1-7)
  stay present; deleting a marker fails here.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SETUP_MD = ROOT / "skills" / "repo-pedant" / "references" / "setup.md"
INVENTORY_PY = ROOT / "skills" / "repo-pedant" / "scripts" / "inventory_knowledge.py"
AGENTS_MD = ROOT / "AGENTS.md"
RESULTS = ROOT / "benchmarks" / "super-caveman" / "results"
EXCALIDRAW_SKILL = ROOT / "skills" / "excalidraw-diagram" / "SKILL.md"
REPO_PEDANT_SKILL = ROOT / "skills" / "repo-pedant" / "SKILL.md"
ARTIFACT_MODE = ROOT / "skills" / "lavish" / "references" / "artifact-mode.md"


def documented_snapshot_flags(setup_text: str) -> set[str]:
    flags = set()
    for block in re.findall(r"```bash\n(.*?)```", setup_text, re.S):
        if "inventory_knowledge.py" in block:
            flags |= set(re.findall(r"--[a-z][a-z-]+", block))
    flags.discard("--help")
    return flags


def argparse_snapshot_flags(source: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"snapshot\.add_argument\(\s*\"(--[a-z][a-z-]+)\"", source, re.S)}


def excalidraw_sections_missing_criteria(skill_text: str) -> list[str]:
    missing = []
    for section in re.split(r"\n(?=## )", skill_text):
        match = re.match(r"## ([123])\. ", section)
        if match and "完成判据" not in section:
            missing.append(match.group(1))
    return missing


def repo_pedant_sections_missing_completion(skill_text: str) -> list[str]:
    missing = []
    for heading, body in re.findall(
        r"### (🕸️ 2\.[^\n]+|🧹 3\.[^\n]+)\n(.*?)(?=\n### |\n## )", skill_text, re.S
    ):
        if "**完成条件：**" not in body:
            missing.append(heading.split(".")[0].strip())
    return missing


def artifact_steps_missing_completion(artifact_text: str) -> list[str]:
    workflow = artifact_text.split("## Artifact mode workflow", 1)[1].split("\n## ", 1)[0]
    missing = []
    for step_line in [ln for ln in workflow.splitlines() if re.match(r"^\d+\. ", ln)]:
        number = int(step_line.split(".", 1)[0])
        start = workflow.index(step_line)
        next_match = re.search(rf"\n{number + 1}\. ", workflow[start + 1:])
        block = workflow[start : start + 1 + next_match.start()] if next_match else workflow[start:]
        if "Completion:" not in block:
            missing.append(str(number))
    return missing


def agents_md_promotion_is_current(agents_text: str, results_dir: Path) -> tuple[bool, str]:
    named = set(re.findall(r"revision-([0-9a-f]{8})", agents_text))
    if not named:
        return False, "AGENTS.md names no super-caveman revision"
    for revision in sorted(named):
        record = results_dir / f"revision-{revision}-exact-diff-approval.json"
        if not record.is_file():
            return False, f"record for revision-{revision} does not exist"
    passing = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(results_dir.glob("*-attempt-1-summary.json"))
        if json.loads(p.read_text(encoding="utf-8")).get("status") == "pass"
    ]
    for revision in sorted(named):
        if any(s.get("skill_tree_sha256", "").startswith(revision) for s in passing):
            return True, revision
    return False, f"none of {sorted(named)} is the current passing promotion"


class SetupDocsMatchArgparse(unittest.TestCase):
    def test_every_documented_snapshot_flag_exists_in_script(self) -> None:
        documented = documented_snapshot_flags(SETUP_MD.read_text(encoding="utf-8"))
        declared = argparse_snapshot_flags(INVENTORY_PY.read_text(encoding="utf-8"))
        self.assertTrue(documented, "no flags found in setup.md bash block")
        self.assertEqual(set(), documented - declared, "setup.md documents flags the script does not declare")

    def test_full_form_example_covers_the_flags_the_skill_entry_uses(self) -> None:
        skill_text = REPO_PEDANT_SKILL.read_text(encoding="utf-8")
        for flag in set(re.findall(r"--(global-instruction|output)\b", skill_text)):
            self.assertIn(f"--{flag}", SETUP_MD.read_text(encoding="utf-8"))


class AgentsMdPromotionPointer(unittest.TestCase):
    def test_agents_md_names_the_current_passing_promotion(self) -> None:
        ok, detail = agents_md_promotion_is_current(AGENTS_MD.read_text(encoding="utf-8"), RESULTS)
        self.assertTrue(ok, detail)

    def test_stale_revision_pointer_is_rejected(self) -> None:
        stale_summary = json.loads((RESULTS / "revision-e04ba7c3-attempt-1-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(stale_summary.get("status"), "superseded")
        stale_text = AGENTS_MD.read_text(encoding="utf-8").replace("93f38a6b", "e04ba7c3")
        ok, detail = agents_md_promotion_is_current(stale_text, RESULTS)
        self.assertFalse(ok, "a superseded-only promotion pointer must not pass")


class CompletionCriteriaPinned(unittest.TestCase):
    def test_excalidraw_sections_1_to_3_carry_completion_criteria(self) -> None:
        self.assertEqual([], excalidraw_sections_missing_criteria(EXCALIDRAW_SKILL.read_text(encoding="utf-8")))

    def test_repo_pedant_sections_2_and_3_carry_completion_conditions(self) -> None:
        self.assertEqual([], repo_pedant_sections_missing_completion(REPO_PEDANT_SKILL.read_text(encoding="utf-8")))

    def test_lavish_artifact_mode_steps_carry_completion_markers(self) -> None:
        self.assertEqual([], artifact_steps_missing_completion(ARTIFACT_MODE.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()

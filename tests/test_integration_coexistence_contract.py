"""Coexistence task-ownership contract across every rule authority (#338/#339).

The accepted coexistence spec distinguishes the host default configuration
from the current task's workflow owner. That distinction is real only while
every authority a user actually installs carries it — the Kit's managed
instruction block, its ``astra-orchestrator`` Skill, pstack's Codex mapping,
and the Hub access contract — and only if the Kit installer ships the updated
bytes into a target that no longer has this checkout. The phrase pins below
are rule anchors in the shipping files, not prompt strings, and the
installer round-trip proves the rules land in an installed home.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KIT_PACKAGE = ROOT / "packages" / "agent-orchestration-kit"
KIT_INSTRUCTIONS = KIT_PACKAGE / "profiles" / "azhou-balanced" / "AGENTS.md"
KIT_SKILL = KIT_PACKAGE / "profiles" / "azhou-balanced" / "agents" / "skills" / "astra-orchestrator" / "SKILL.md"
PSTACK_MAPPING = (ROOT / "packages" / "pstack-agent-harness" / "plugins" / "pstack" / "skills"
                  / "poteto-mode" / "references" / "codex-tools.md")
CONTRACT = ROOT / "docs" / "integrations.md"
INSTALLER = KIT_PACKAGE / "scripts" / "install_codex.py"
BEGIN = "<!-- ASTRA-LUNA-ORCHESTRATOR:BEGIN -->"
END = "<!-- ASTRA-LUNA-ORCHESTRATOR:END -->"

# Each entry maps a rule of the coexistence contract to the phrase that must
# carry it in each authority that ships it. A rule dropped from any required
# authority fails here, which is what keeps the three rule sources consistent.
RULES = {
    "an explicitly selected workflow owns the task": {
        KIT_INSTRUCTIONS: "that workflow owns the task's decomposition, stages, child dispatch, and verification",
        KIT_SKILL: "that workflow owns the task's decomposition, stages, child dispatch, and verification",
        PSTACK_MAPPING: "it owns the decomposition, stages, child dispatch, and verification",
        CONTRACT: "Only a task the user explicitly selected",
    },
    "selection is explicit, visibility is not takeover": {
        PSTACK_MAPPING: ("a Skill being visible in the directory, a model sheet existing, "
                         "or reference material loading is not selection"),
        CONTRACT: "a visible Skill, an existing model sheet, or loaded reference material does not take over",
    },
    "the orchestrator starts no second flow on a pstack-owned task": {
        KIT_INSTRUCTIONS: "start no second decomposition, delegation, or review flow on top of it",
        KIT_SKILL: "Start no second decomposition, delegation, or review flow on top of the selected workflow",
        PSTACK_MAPPING: "add no second flow on top",
    },
    "same-goal follow-ups keep the owner": {
        KIT_INSTRUCTIONS: "A status question or an added constraint within the same task keeps that owner",
        KIT_SKILL: "A status question or an added constraint within the same task keeps the selected workflow as owner",
        PSTACK_MAPPING: "A status question or an added constraint within the same task keeps pstack as the owner",
        CONTRACT: "A status question or an added constraint within the same task keeps pstack as owner",
    },
    "the next ordinary task returns to host defaults": {
        KIT_INSTRUCTIONS: "a new task after it finishes returns to these defaults",
        KIT_SKILL: "returns to these defaults; ownership does not persist across tasks",
        PSTACK_MAPPING: "ownership does not persist and pstack starts no background service to keep it",
        CONTRACT: "the next task returns to the host defaults",
    },
    "a mid-task switch first reaches a recoverable boundary": {
        KIT_INSTRUCTIONS: "first bring running children to a recoverable boundary and stop or finish them",
        KIT_SKILL: "first bring this skill's running children to a recoverable boundary",
        PSTACK_MAPPING: "bring pstack's running children to a recoverable boundary",
        CONTRACT: "a mid-task switch first waits for, stops, or closes running children",
    },
    "ordinary delegation selects named roles": {
        KIT_INSTRUCTIONS: "Ordinary delegation selects the named roles above",
        KIT_SKILL: "Normal delegation through this skill selects the named roles",
        CONTRACT: "Named custom role; the role TOML selects its model and effort",
    },
    "pstack dispatch is explicit and selects no named role": {
        KIT_SKILL: "do not attach a named role to them",
        PSTACK_MAPPING: "pass the explicit model and `reasoning_effort` from the sheet and select no named role",
        CONTRACT: "explicit model/effort from the selected pstack model policy, and no named custom role",
    },
    "a selected role file overrides explicit dispatch fields": {
        KIT_SKILL: "a selected custom-role file overrides the explicit fields it sets",
        PSTACK_MAPPING: "a selected custom-role file overrides the explicit fields it sets",
        CONTRACT: "a selected custom-role file overrides the explicit fields it sets",
    },
    "selecting a workflow never switches the root session model": {
        KIT_INSTRUCTIONS: "leave the active root model unchanged",
        KIT_SKILL: "Selecting a workflow never switches the active root session model",
        PSTACK_MAPPING: "Selecting a pstack workflow does not switch the active root session model",
        CONTRACT: "Selecting a pstack workflow never switches the active root session model",
    },
    "a rejected model falls back only declaredly and is reported": {
        PSTACK_MAPPING: "never report a fallback as the requested model succeeding",
        CONTRACT: "An explicitly rejected model falls back only to a sheet-declared, host-supported model",
    },
    "a capacity error is not a model rejection": {
        PSTACK_MAPPING: "A thread-limit error from `spawn_agent` is a capacity error, not a rejected model slug",
    },
    "constraints apply on both paths": {
        KIT_INSTRUCTIONS: "Permissions, concurrency limits, and project rules apply on every path",
        KIT_SKILL: "User instructions, project rules, permissions, and concurrency limits apply on both paths",
        PSTACK_MAPPING: "User instructions, project rules, permissions, and concurrency limits apply on both paths",
        CONTRACT: "user instructions, project rules, permissions, and concurrency limits apply on both paths",
    },
    "no orchestrator chains into another": {
        KIT_INSTRUCTIONS: "no orchestrator chains into another",
        KIT_SKILL: "This skill never chains into another orchestrator",
        PSTACK_MAPPING: "pstack never chains into another orchestrator",
        CONTRACT: "no orchestrator-to-orchestrator chain",
    },
    "the contract ships with the installation, not the checkout": {
        CONTRACT: "shipped by the installed artifacts themselves",
    },
}


def load_installer():
    spec = importlib.util.spec_from_file_location("coexistence_install_codex", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoexistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.cache: dict[Path, str] = {}

    def text(self, path: Path) -> str:
        if path not in self.cache:
            self.cache[path] = path.read_text(encoding="utf-8")
        return self.cache[path]

    def test_every_rule_is_carried_by_every_authority_that_ships_it(self):
        for rule, authorities in RULES.items():
            with self.subTest(rule=rule):
                self.assertTrue(authorities, "a rule with no authority is a dead entry")
                for path, phrase in authorities.items():
                    self.assertIn(phrase, self.text(path),
                                  f"{path.relative_to(ROOT)} no longer carries: {phrase}")

    def test_every_authority_is_part_of_the_contract(self):
        shipped = {path for authorities in RULES.values() for path in authorities}
        self.assertEqual(shipped, {KIT_INSTRUCTIONS, KIT_SKILL, PSTACK_MAPPING, CONTRACT})

    def test_kit_instructions_remain_exactly_one_managed_block(self):
        text = self.text(KIT_INSTRUCTIONS)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        self.assertLess(text.index(BEGIN), text.index(END))
        block = text[text.index(BEGIN):text.index(END) + len(END)]
        self.assertEqual(block.strip(), text.strip(),
                         "the managed block must remain the whole source file the installer validates")

    def test_installer_ships_the_coexistence_rules_without_this_checkout(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory(prefix="coexistence-install-") as name:
            base = Path(name).resolve()
            home = base / "codex-home"
            skills = base / "skills"
            plan = installer.build_plan(KIT_PACKAGE, home, skills)
            installer.apply_plan(plan)
            installed = (home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(installed.count(BEGIN), 1)
            self.assertIn("that workflow owns the task's decomposition, stages, child dispatch, and verification",
                          installed)
            installed_skill = (skills / "astra-orchestrator" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("do not attach a named role to them", installed_skill)
            self.assertIn("a selected custom-role file overrides the explicit fields it sets", installed_skill)


if __name__ == "__main__":
    unittest.main()

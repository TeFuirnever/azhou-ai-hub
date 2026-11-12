"""Release-surface checks for generated pstack host distributions.

These assertions cover the shipped plugin/skills layout; they do not pretend
to replace the removed old-port behavioral suite or real host invocation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "pstack-agent-harness"
HARNESS = PACKAGE / "harness" / "pstack"
EXPECTED_PLUGIN = "pstack-azhouzhou"
EXPECTED_VERSION = "0.15.37"
EXPECTED_SKILLS = 68
EXPECTED_COMMANDS = 41


def json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def skills_for(tree: str) -> set[str]:
    root = HARNESS / tree / "skills"
    return {p.name for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


class PstackDistributionContractTest(unittest.TestCase):
    def test_harness_ci_parity_detects_untracked_generator_outputs(self) -> None:
        # A clean git diff alone does not notice a newly generated file.
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("git diff --exit-code -- harness/", workflow)
        self.assertIn("git ls-files --others --exclude-standard -- harness/", workflow)
        self.assertIn('if [ -n "$untracked" ]; then', workflow)

    def test_four_generated_skill_trees_share_the_same_full_inventory(self) -> None:
        by_host = {host: skills_for(host) for host in
                   ("claude-code", "codex", "zcode", "skills-root")}
        reference = by_host["claude-code"]
        self.assertEqual(len(reference), EXPECTED_SKILLS)
        self.assertIn("poteto-mode", reference)
        self.assertIn("architect", reference)
        for host, skills in by_host.items():
            with self.subTest(host=host):
                self.assertEqual(skills, reference)

    def test_codex_native_plugin_names_and_exposes_41_prompts(self) -> None:
        tree = HARNESS / "codex"
        manifest = json_file(tree / ".codex-plugin/plugin.json")
        self.assertEqual((manifest["name"], manifest["version"]),
                         (EXPECTED_PLUGIN, EXPECTED_VERSION))
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["hooks"], "./hooks/codex-hooks.json")
        prompts = {p.stem for p in (tree / ".codex-plugin/prompts").glob("*.md")}
        self.assertEqual(len(prompts), EXPECTED_COMMANDS)
        self.assertTrue(prompts <= skills_for("codex"))
        registry = json_file(PACKAGE / ".agents/plugins/marketplace.json")
        entries = registry["plugins"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], EXPECTED_PLUGIN)
        self.assertEqual(entries[0]["source"]["path"], "./harness/pstack/codex")

    def test_claude_code_native_distribution_uses_the_new_identity(self) -> None:
        manifest = json_file(HARNESS / "claude-code/.claude-plugin/plugin.json")
        self.assertEqual((manifest["name"], manifest["version"]),
                         (EXPECTED_PLUGIN, EXPECTED_VERSION))
        registry = json_file(PACKAGE / ".claude-plugin/marketplace.json")
        self.assertEqual(registry["plugins"][0]["name"], EXPECTED_PLUGIN)
        self.assertEqual(registry["plugins"][0]["source"], "./harness/pstack/claude-code")

    def test_codex_agent_reference_is_resolved_from_adapter_not_child_cwd(self) -> None:
        tree = HARNESS / "codex"
        adapter = tree / "skills/poteto-mode/references/codex-tools.md"
        text = adapter.read_text(encoding="utf-8")
        relative = "../../../agents/comment-sicko.md"
        self.assertIn(relative, text)
        self.assertNotIn("poteto-mode/references/agents/comment-sicko.md", text)
        self.assertIn("resolved from this Codex adapter file", text)
        resolved = (adapter.parent / relative).resolve()
        self.assertEqual(resolved, tree / "agents/comment-sicko.md")
        self.assertTrue(resolved.is_file())

    def test_shared_skills_reviewer_uses_present_agent_or_blocks(self) -> None:
        tree = HARNESS / "skills-root"
        adapter = (tree / "docs/harness/skills-root.md").read_text(encoding="utf-8")
        self.assertIn("<pstack>/agents/comment-sicko.md", adapter)
        self.assertNotIn("poteto-mode/references/agents/comment-sicko.md", adapter)
        self.assertIn("if the required file is absent, block that reviewer", adapter)
        self.assertTrue((tree / "agents/comment-sicko.md").is_file())

    def test_muse_skills_fallback_uses_shipped_agent_or_blocks(self) -> None:
        source = PACKAGE / "hub-skills/poteto-mode/references/muse-tools.md"
        for host in ("claude-code", "codex", "zcode", "skills-root"):
            with self.subTest(host=host):
                tree = HARNESS / host
                adapter = tree / "skills/poteto-mode/references/muse-tools.md"
                guidance = adapter.read_text(encoding="utf-8")
                self.assertEqual(guidance, source.read_text(encoding="utf-8"))
                self.assertIn("`agents/comment-sicko.md` from the installed distribution root", guidance)
                self.assertIn("block the reviewer and report the missing file", guidance)
                self.assertNotIn("poteto-mode/references/agents/", guidance)
                self.assertTrue((adapter.parent / "../../../agents/comment-sicko.md").resolve().is_file())

    def test_distributed_namespace_instructions_match_native_registration(self) -> None:
        for host in ("claude-code", "codex", "zcode", "skills-root"):
            tree = HARNESS / host
            with self.subTest(host=host):
                readme = (tree / "README.md").read_text(encoding="utf-8")
                self.assertIn("/pstack-azhouzhou:poteto-mode", readme)
                self.assertNotIn("/pstack:poteto-mode", readme)
                helper = (tree / "skills/poteto-help/SKILL.md").read_text(encoding="utf-8")
                self.assertIn("pstack-azhouzhou@azhou-hub", helper)
                self.assertNotIn("pstack@cursor-plugins", helper)
                guide = (tree / "docs/guide/01-setup.md").read_text(encoding="utf-8")
                self.assertIn("/pstack-azhouzhou:setup-pstack", guide)
                self.assertNotIn("/pstack:setup-pstack", guide)
                copilot = (tree / "skills/poteto-mode/references/copilot-tools.md").read_text(encoding="utf-8")
                self.assertIn("pstack-azhouzhou:poteto-agent", copilot)
                self.assertNotIn("pstack:poteto-agent", copilot)
                muse = (tree / "skills/poteto-mode/references/muse-tools.md").read_text(encoding="utf-8")
                self.assertIn("plugin:pstack-azhouzhou:poteto-mode", muse)
                self.assertNotIn("plugin:pstack:poteto-mode", muse)
                self.assertIn("pstack-azhouzhou/poteto-agent", muse)
                self.assertIn("muse plugins approve pstack-azhouzhou", muse)
                self.assertIn("the setup-pstack Skill's Other runtimes table", muse)
                self.assertNotIn("setup-pstack-azhouzhou/SKILL.md", muse)
                copilot_setup = (tree / "skills/setup-pstack/copilot.md").read_text(encoding="utf-8")
                self.assertIn("You have pstack-azhouzhou.", copilot_setup)
                self.assertNotIn("You have pstack.", copilot_setup)
        claude = (HARNESS / "claude-code/docs/harness/claude-code.md").read_text(encoding="utf-8")
        self.assertIn("pstack-azhouzhou:comment-sicko", claude)
        self.assertNotIn("pstack:comment-sicko", claude)
        codex = (HARNESS / "codex/docs/harness/codex.md").read_text(encoding="utf-8")
        self.assertIn("$poteto-mode", codex)
        self.assertNotIn("/pstack:<name>", codex)
        zcode = (HARNESS / "zcode/docs/harness/zcode.md").read_text(encoding="utf-8")
        self.assertIn("zcode skills list", zcode)
        self.assertIn("/architect", zcode)
        self.assertNotIn("/pstack:<name>", zcode)

    def test_hub_portable_orchestration_overlays_preserve_recovery_and_gates(self) -> None:
        overlay = PACKAGE / "hub-skills/poteto-mode/playbooks"
        pristine = PACKAGE / "pstack/skills/poteto-mode/playbooks"
        for name in ("orchestrate.md", "autopilot-full.md"):
            source = (overlay / name).read_bytes()
            self.assertNotEqual(source, (pristine / name).read_bytes())
            for host in ("claude-code", "codex", "zcode", "skills-root"):
                with self.subTest(host=host, playbook=name):
                    generated = HARNESS / host / "skills/poteto-mode/playbooks" / name
                    self.assertEqual(generated.read_bytes(), source)
            content = source.decode("utf-8")
            self.assertIn("independent", content)
            self.assertIn("head SHA", content)
            self.assertIn("restart", content.lower())
        plan = (overlay / "orchestrate.md").read_text(encoding="utf-8")
        for term in ("no real Task", "local worktree", "standing orders",
                     "bounded stuck threshold", "at most", "No invented scheduler"):
            self.assertIn(term, plan)
        auto = (overlay / "autopilot-full.md").read_text(encoding="utf-8")
        self.assertIn("No auto-loop unless installed", auto)
        self.assertIn("stop at merge-ready", auto)

    def test_zcode_named_reviewer_uses_existing_agent_path(self) -> None:
        tree = HARNESS / "zcode"
        guide = (tree / "docs/harness/zcode.md").read_text(encoding="utf-8")
        self.assertIn("<pstack>/agents/comment-sicko.md", guide)
        self.assertNotIn("poteto-mode/references/agents/comment-sicko.md", guide)
        self.assertTrue((tree / "agents/comment-sicko.md").is_file())

    def test_statechart_scanner_helpers_remain_test_only_and_identical(self) -> None:
        # Security-review boundary: these are test oracles, not HTML sanitizers.
        # This asserts only static import separation, not arbitrary DOM safety.
        source = PACKAGE / "pstack/skills/statechart/scripts"
        flagged = ("labels.ts", "cli.test.ts", "differential.test.ts")
        for host in ("claude-code", "codex", "zcode", "skills-root"):
            generated = HARNESS / host / "skills/statechart/scripts"
            with self.subTest(host=host):
                for name in flagged:
                    self.assertEqual((source / "test" / name).read_bytes(),
                                     (generated / "test" / name).read_bytes())
                production = [f for f in generated.rglob("*.ts")
                              if "test" not in f.relative_to(generated).parts]
                self.assertGreater(len(production), 20)
                test_import = re.compile(
                    r"""(?:\bfrom\s+|\bimport\s*\(|\brequire\s*\()"""
                    r"""[\s'"]*[^'"]*(?:/test/|/test\.ts)"""
                )
                for file in production:
                    self.assertIsNone(test_import.search(file.read_text(encoding="utf-8")),
                                      f"{host}: production code imports test oracle {file}")

    def test_hub_distribution_version_is_distinct_from_immutable_upstream(self) -> None:
        pinned = json_file(PACKAGE / "pstack/plugin.json")
        hub = json_file(PACKAGE / "hub-package.json")
        native_marketplace = json_file(PACKAGE / ".claude-plugin/marketplace.json")
        self.assertEqual(pinned["version"], "0.15.36")
        self.assertEqual(hub["version"], EXPECTED_VERSION)
        self.assertNotEqual(hub["version"], pinned["version"])
        self.assertEqual(native_marketplace["plugins"][0]["version"], EXPECTED_VERSION)
        series = (PACKAGE / "patches/series").read_text(encoding="utf-8").splitlines()
        self.assertIn("0021-hub-distribution-version-0.15.37.patch", series)
        self.assertIn("0022-hub-claude-sheet-hook-path.patch", series)
        self.assertEqual(series[-1], "0023-hub-worktree-audit-preserve-untracked.patch")

    def test_codex_adapter_model_and_agent_paths_match_native_hook(self) -> None:
        source = (PACKAGE / "hub-adapters/codex.md").read_text(encoding="utf-8")
        built = (HARNESS / "codex/docs/harness/codex.md").read_text(encoding="utf-8")
        for label in ("sheet-declared", "host-supported", "Never silently inherit",
                      "<pstack>/agents/comment-sicko.md", "CODEX_HOME", "pstack-models.md"):
            self.assertIn(label, source)
            self.assertIn(label, built)
        self.assertNotIn("poteto-mode/references/agents/comment-sicko.md", built)
        self.assertNotIn("Other runtimes table", built)
        notes = (HARNESS / "codex/skills/poteto-mode/references/codex-tools.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("CODEX_HOME", notes)
        self.assertIn("pstack-models.md", notes)
        self.assertNotIn("setup-pstack's runtime table", notes)
        hook = (HARNESS / "codex/hooks/session-start.sh").read_text(encoding="utf-8")
        self.assertIn("CODEX_HOME", hook)
        self.assertIn("pstack-models.md", hook)
        self.assertTrue((HARNESS / "codex/agents/comment-sicko.md").is_file())

    def test_public_pstack_readmes_cover_five_maintained_harnesses(self) -> None:
        matrix = (ROOT / "docs/support-matrix.md").read_text(encoding="utf-8")
        self.assertIn("DeepSeek Harness", matrix)
        for name in ("README.md", "README.zh-CN.md"):
            content = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                rows = [line for line in content.splitlines()
                        if line.startswith("| `pstack` |")]
                self.assertEqual(len(rows), 1)
                for marker in ("pstack-azhouzhou", "0.15.37", "MiMo", "DeepSeek Harness"):
                    self.assertIn(marker, rows[0])
                self.assertTrue(any("DeepSeek Harness" in line and
                                    "pstack-azhouzhou" in line
                                    for line in content.splitlines() if "zcode" in line))

    def test_zcode_commands_plugin_is_flat_and_has_no_skills_or_hooks(self) -> None:
        tree = HARNESS / "zcode-plugin"
        registry = json_file(tree / "marketplace.json")
        self.assertEqual(registry["name"], "azhou-hub")
        self.assertEqual(len(registry["plugins"]), 1)
        self.assertEqual(registry["plugins"][0]["name"], EXPECTED_PLUGIN)
        payload = tree / EXPECTED_PLUGIN
        manifest = json_file(payload / ".zcode-plugin/plugin.json")
        self.assertEqual((manifest["name"], manifest["version"]),
                         (EXPECTED_PLUGIN, EXPECTED_VERSION))
        self.assertEqual(manifest["commands"], "commands")
        self.assertNotIn("skills", manifest)
        self.assertNotIn("hooks", manifest)
        commands = {p.stem for p in (payload / "commands").glob("*.md")}
        self.assertEqual(len(commands), EXPECTED_COMMANDS)
        self.assertTrue(commands <= skills_for("zcode"))
        self.assertFalse((payload / "skills").exists())
        self.assertFalse((payload / "hooks").exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "repo-pedant"
SKILL = SKILL_DIR / "SKILL.md"
AZHOU_SKILL_NAMES = (
    "azhou-doctor",
    "azhou-info",
    "azhou-setup",
    "azhou-verify",
)
LAVISH_DIR = ROOT / "skills" / "lavish"
LLM_WIKI_DIR = ROOT / "skills" / "llm-wiki"
SUPER_CAVEMAN_DIR = ROOT / "skills" / "super-caveman"
SKILL_DIRS = (
    SKILL_DIR,
    ROOT / "skills" / "excalidraw-diagram",
    LAVISH_DIR,
    LLM_WIKI_DIR,
    SUPER_CAVEMAN_DIR,
    *(ROOT / "skills" / name for name in AZHOU_SKILL_NAMES),
)


class SkillPackageTest(unittest.TestCase):
    def test_frontmatter_and_folder_name_match(self) -> None:
        for package in SKILL_DIRS:
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", text, re.DOTALL)
            self.assertIsNotNone(match)
            frontmatter = match.group("frontmatter")
            name = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
            description = re.search(r"^description:\s*([^\n]+)$", frontmatter, re.MULTILINE)
            self.assertIsNotNone(name)
            self.assertIsNotNone(description)
            self.assertEqual(package.name, name.group(1).strip())
            self.assertLessEqual(len(description.group(1).strip()), 1024)
            self.assertRegex(name.group(1).strip(), r"^[a-z0-9-]+$")
            self.assertEqual({"name", "description"}, {line.split(":", 1)[0] for line in frontmatter.splitlines()})

    def test_skill_links_resolve(self) -> None:
        for package in SKILL_DIRS:
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            links = re.findall(r"\[[^]]+\]\(([^)]+)\)", text)
            relative_links = [value for value in links if "://" not in value and not value.startswith("#")]
            self.assertTrue(relative_links)
            for value in relative_links:
                self.assertTrue((package / value).exists(), f"{package.name}: {value}")

    def test_no_scaffold_placeholders(self) -> None:
        text_suffixes = {".md", ".py", ".mjs", ".json", ".toml", ".yaml", ".yml", ".html"}
        for package in SKILL_DIRS:
            for path in package.rglob("*"):
                if (
                    not path.is_file()
                    or path.suffix not in text_suffixes
                    or {"node_modules", ".venv", ".omc"} & set(path.parts)
                ):
                    continue
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("[TODO", text, str(path))
                self.assertNotIn("TODO:", text, str(path))

    def test_repo_pedant_is_the_only_current_package_name(self) -> None:
        legacy = ROOT / "skills" / "tidy"
        self.assertFalse(any(path.is_file() for path in legacy.rglob("*")) if legacy.exists() else False)
        self.assertTrue((SKILL_DIR / "scripts" / "collect_agent_history.py").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "validate_evidence_bundle.py").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "inventory_knowledge.py").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "closeout_hook.py").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "manage_evolution.py").exists())
        self.assertTrue((SKILL_DIR / "scripts" / "validate_execution_protocol.py").exists())

    def test_runtime_packages_are_harness_neutral(self) -> None:
        for package in SKILL_DIRS:
            self.assertFalse((package / "agents" / "openai.yaml").exists())
            self.assertFalse((package / "benchmarks").exists())

    def test_azhou_skills_are_independently_installable_packages(self) -> None:
        for name in AZHOU_SKILL_NAMES:
            package = ROOT / "skills" / name
            self.assertTrue((package / "SKILL.md").is_file(), name)
            self.assertTrue((package / "references" / "setup.md").is_file(), name)

    def test_lavish_import_is_locked_and_capability_mapped(self) -> None:
        skill = (LAVISH_DIR / "SKILL.md").read_text(encoding="utf-8")
        setup = (LAVISH_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        provenance = (LAVISH_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        compatibility = (LAVISH_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        brand = (LAVISH_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")

        self.assertIn("lavish-axi@0.1.47", skill)
        self.assertNotIn("npx -y lavish-axi ", skill)
        self.assertIn("Node 22+", setup)
        self.assertIn("232972beba9e0e4e75682c98f2aeb2cf01532122", provenance)
        self.assertIn("7c730b29baab6b29dd4c11f02783190f78e215604993a80228e3784423b5e857", provenance)
        self.assertIn("sha512-zB1kEUSgyvi6sC3I/nBPCGZwO8Z5pt8I2/ltFcovC8R+PuzRwJUb5V4BWMWnaPdXVBPH07B7XoBKKBf28733kg==", provenance)
        for capability in (
            "Foreground long-poll",
            "Mermaid-to-editable-Excalidraw",
            "Portable standalone export",
            "ht-ml.app",
            "design-source priority",
        ):
            self.assertIn(capability, compatibility)
        self.assertIn("lavish.receipt.v1", brand)
        self.assertIn("Do not run `share` without explicit publication authorization", skill)

    def test_lavish_license_and_notice_are_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "Lavish-AXI-MIT.txt").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Kun Chen", license_text)
        self.assertIn("Lavish Editor", notices)
        self.assertIn("Lavish-AXI-MIT.txt", notices)

    def test_llm_wiki_import_is_mapped_and_harness_neutral(self) -> None:
        skill = (LLM_WIKI_DIR / "SKILL.md").read_text(encoding="utf-8")
        compatibility = (LLM_WIKI_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        provenance = (LLM_WIKI_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        brand = (LLM_WIKI_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        script = (LLM_WIKI_DIR / "scripts" / "llm_wiki.py").read_text(encoding="utf-8")

        for operation in ("wiki_ingest", "wiki_query", "wiki_lint", "wiki_add", "wiki_list", "wiki_read", "wiki_delete"):
            self.assertIn(operation, compatibility)
        self.assertIn("deee3a446dadc9bfea31cdc8b19b00b16718082e", provenance)
        self.assertIn("llm-wiki.receipt.v1", brand)
        self.assertIn("autoCapture` defaults to false", skill)
        self.assertIn('DEFAULT_STORE = ".llm-wiki"', script)
        self.assertNotIn("@anthropic-ai", script)

    def test_llm_wiki_license_and_notice_are_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "oh-my-claudecode-MIT.txt").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2025 Yeachan Heo", license_text)
        self.assertIn("oh-my-claudecode", notices)
        self.assertIn("oh-my-claudecode-MIT.txt", notices)

    def test_super_caveman_extends_core_with_six_companions(self) -> None:
        skill = (SUPER_CAVEMAN_DIR / "SKILL.md").read_text(encoding="utf-8")
        modes = (SUPER_CAVEMAN_DIR / "references" / "modes.md").read_text(encoding="utf-8")
        provenance = (SUPER_CAVEMAN_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        capability_map = json.loads(
            (ROOT / "benchmarks" / "super-caveman" / "capability-map.json").read_text(encoding="utf-8")
        )
        source_names = {item["name"] for item in capability_map["sources"]}
        self.assertEqual("super-caveman", capability_map["canonical_skill"])
        self.assertEqual("original-caveman-enhanced", capability_map["positioning"])
        self.assertEqual("caveman", capability_map["core_source"])
        self.assertEqual(6, capability_map["absorbed_companions"])
        self.assertIn("# Super Caveman", skill)
        self.assertIn("/super-caveman", skill)
        self.assertEqual(
            {
                "cavecrew",
                "caveman",
                "caveman-commit",
                "caveman-compress",
                "caveman-help",
                "caveman-review",
                "caveman-stats",
            },
            source_names,
        )
        self.assertIn("one independently installable package", provenance)
        self.assertIn("b42a45a068e080294924bfba19a7a2e8944c48ff", provenance)
        self.assertIn("938d0e350a0c2b0e2e6c3a9032542e062846d108e0f89dd27c798ba5b436397e", provenance)
        for alias in source_names:
            self.assertFalse((ROOT / "skills" / alias / "SKILL.md").exists())
        for route in (
            "/cavecrew",
            "/caveman-commit",
            "/caveman-review",
            "/caveman-compress",
            "/caveman-help",
            "/caveman-stats",
        ):
            self.assertIn(route, skill)
        for rule in (
            "Lead with the next action",
            "Number multi-step tasks",
            "End with one concrete next action",
            "Restate state every turn",
            "Cap lists at five items",
            "A future-tense plan to edit, test, or inspect is not completion",
            "Casual acknowledgement",
            "one verb phrase",
            "approved deployment mechanism",
        ):
            self.assertIn(rule, modes)
        self.assertIn("not a diagnosis or medical claim", modes)

    def test_super_caveman_runtime_is_neutral_and_recoverable(self) -> None:
        guard = (SUPER_CAVEMAN_DIR / "scripts" / "compression_guard.py").read_text(encoding="utf-8")
        setup = (SUPER_CAVEMAN_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        stats = (SUPER_CAVEMAN_DIR / "references" / "statistics.md").read_text(encoding="utf-8")
        brand = (SUPER_CAVEMAN_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        self.assertNotIn("ANTHROPIC_API_KEY", guard)
        self.assertNotIn("claude --print", guard)
        self.assertNotIn("subprocess", guard)
        self.assertIn("Python standard library only", setup)
        self.assertIn("install_text_if_unchanged", guard)
        self.assertIn("finalize_state", guard)
        self.assertIn('"handoffs"', guard)
        self.assertIn("current source changed after compression; restore refused", guard)
        self.assertIn("unavailable: host exposes no audited current-session counters.", stats)
        self.assertIn("super-caveman.receipt.v1", brand)
        self.assertIn("learning_signal:", brand)
        self.assertIn("少说话，技术信号不丢。", brand)
        for event in (
            "🦊 阿舟 · Super Caveman 启动｜mode=<operation>｜scope=<target>",
            "🧭 范围锁定｜source=<target>｜holds=<n>",
            "🪨 候选完成｜artifact=<path-or-description>",
            "✅ 验证通过｜checks=<comma-separated ids>",
            "❌ 验证失败｜check=<id>｜impact=<fact>",
            "🔒 阿舟暂停这一项｜hold=<fact>",
        ):
            self.assertIn(event, brand)
        self.assertIn("at most one leading emoji per event", brand)
        self.assertIn("success appears once and is the final stage event", brand)
        self.assertIn("schema keys, enum values, digests, paths, commands, test names, and raw evidence emoji-free", brand)

    def test_super_caveman_licenses_and_notices_are_retained(self) -> None:
        caveman_license = (ROOT / "LICENSES" / "Caveman-MIT.txt").read_text(encoding="utf-8")
        adhd_license = (ROOT / "LICENSES" / "i-have-adhd-MIT.txt").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Julius Brussee", caveman_license)
        self.assertIn("Copyright (c) 2026 Ayoub Ghriss", adhd_license)
        self.assertIn("Caveman", notices)
        self.assertIn("Caveman-MIT.txt", notices)
        self.assertIn("i-have-adhd", notices)
        self.assertIn("i-have-adhd-MIT.txt", notices)

    def test_repo_pedant_brand_layer_covers_the_interactive_lifecycle(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        brand = (SKILL_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        hook = (SKILL_DIR / "scripts" / "closeout_hook.py").read_text(encoding="utf-8")
        anchors = (
            "🦊 阿舟 · Repo Pedant 启动",
            "🧭 范围锁定",
            "🗂️ 清单完成",
            "🕸️ 影响确认",
            "🧹 同步完成",
            "✅ 验证通过",
            "❌ 验证失败",
            "🔒 阿舟暂停这一项",
            "🟡 阿舟提醒",
            "🧠 阿舟记忆检查",
        )
        for anchor in anchors:
            self.assertIn(anchor, brand)
        self.assertIn("[brand-layer.md](references/brand-layer.md)", skill)
        self.assertIn('REMINDER = "🟡 阿舟提醒｜', hook)
        self.assertIn('PRECOMPACT_REMINDER = "🧠 阿舟记忆检查｜', hook)

    def test_project_skill_standard_is_the_shared_authority(self) -> None:
        standard = (ROOT / "docs" / "skill-standard.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/skill-standard.md", agents)
        self.assertIn("docs/skill-standard.md", readme)
        for phrase in (
            "skills/<canonical-name>/",
            "agents/openai.yaml",
            "references/brand-layer.md",
            "至少 3 个独立 paired judges",
            "repo-pedant",
        ):
            self.assertIn(phrase, standard)

    def test_excalidraw_brand_and_evolution_cover_the_shared_lifecycle(self) -> None:
        package = ROOT / "skills" / "excalidraw-diagram"
        skill = (package / "SKILL.md").read_text(encoding="utf-8")
        brand = (package / "references" / "brand-layer.md").read_text(encoding="utf-8")
        history = (package / "references" / "history-evolution.md").read_text(encoding="utf-8")
        evolution = (package / "references" / "evolution-contract.md").read_text(encoding="utf-8")
        for anchor in (
            "🦊 阿舟 · Excalidraw Diagram 启动",
            "🧭 需求锁定",
            "🔎 事实确认",
            "✏️ 场景生成",
            "🧪 审核第 n 轮",
            "📦 交付完成",
            "✅ 验证通过",
            "❌ 验证失败",
            "🔒 阿舟暂停这一项",
        ):
            self.assertIn(anchor, brand)
        self.assertIn("excalidraw-diagram.receipt.v1", brand)
        self.assertIn("(references/brand-layer.md)", skill)
        for runtime in ("Codex", "Claude", "zcode"):
            self.assertIn(runtime, history)
        self.assertIn("至少 3 个独立 paired judges", evolution)
        self.assertIn("exact diff", evolution)
        self.assertIn("不能写 live", evolution)

    def test_excalidraw_export_example_matches_locked_runtime_and_cli(self) -> None:
        package = ROOT / "skills" / "excalidraw-diagram"
        skill = (package / "SKILL.md").read_text(encoding="utf-8")
        exporter = (package / "scripts" / "export-official-svg.py").read_text(encoding="utf-8")
        self.assertIn('cd "$SKILL_DIR/references"', skill)
        self.assertIn('uv run python "$SKILL_DIR/scripts/export-official-svg.py"', skill)
        self.assertIn('uv run python "$SKILL_DIR/scripts/visual-check.py"', skill)
        self.assertNotRegex(skill, r"export-official-svg\.py[\s\\]+.*--output")
        self.assertIn('ap.add_argument("dst", type=Path', exporter)

    def test_public_markdown_links_resolve(self) -> None:
        for document in (
            ROOT / "AGENTS.md",
            ROOT / "CLAUDE.md",
            ROOT / "README.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "docs" / "skill-standard.md",
            ROOT / "docs" / "excalidraw-diagram.md",
            ROOT / "benchmarks" / "repo-pedant" / "README.md",
            ROOT / "benchmarks" / "excalidraw-diagram" / "README.md",
            ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "README.md",
            ROOT / "evidence" / "README.md",
        ):
            text = document.read_text(encoding="utf-8")
            for value in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in value or value.startswith("#"):
                    continue
                target = value.split("#", 1)[0]
                self.assertTrue((document.parent / target).exists(), f"{document}: {value}")

    def test_public_json_artifacts_parse(self) -> None:
        paths = [
            SKILL_DIR / "assets" / "history-report.schema.json",
            SKILL_DIR / "assets" / "inventory.schema.json",
            SKILL_DIR / "assets" / "closeout-state.schema.json",
            SKILL_DIR / "assets" / "evolution-evaluation.schema.json",
            SKILL_DIR / "assets" / "evolution-signal.schema.json",
            SKILL_DIR / "assets" / "evolution-candidate.schema.json",
            SKILL_DIR / "assets" / "execution-protocol.schema.json",
            SKILL_DIR / "assets" / "hooks" / "codex-hooks.fragment.json",
            SKILL_DIR / "assets" / "hooks" / "claude-hooks.fragment.json",
            ROOT / "benchmarks" / "repo-pedant" / "manifest.json",
            ROOT / "benchmarks" / "repo-pedant" / "neat-freak-parity.json",
            ROOT / "benchmarks" / "repo-pedant" / "regression-map.json",
            ROOT / "benchmarks" / "repo-pedant" / "trigger-cases.json",
            ROOT / "benchmarks" / "repo-pedant" / "history" / "baseline-2026-08-23.json",
            ROOT / "benchmarks" / "repo-pedant" / "protocol" / "valid.execution.json",
            ROOT / "benchmarks" / "repo-pedant" / "protocol" / "prior-drift.execution.json",
            ROOT / "benchmarks" / "super-caveman" / "manifest.json",
            ROOT / "benchmarks" / "super-caveman" / "capability-map.json",
            ROOT / "benchmarks" / "super-caveman" / "trigger-cases.json",
            ROOT / "benchmarks" / "super-caveman" / "response-cases.json",
            ROOT / "benchmarks" / "super-caveman" / "evaluation-contract.json",
            ROOT / "benchmarks" / "super-caveman" / "results" / "revision-a6cfc850-attempt-1-summary.json",
            ROOT / "benchmarks" / "super-caveman" / "results" / "revision-dfe45d69-attempt-1-summary.json",
            ROOT / "benchmarks" / "super-caveman" / "results" / "revision-de6b836a-attempt-1-summary.json",
            ROOT / "benchmarks" / "super-caveman" / "results" / "revision-e1eef218-attempt-1-summary.json",
            ROOT / "benchmarks" / "super-caveman" / "results" / "revision-f3ab4d37-attempt-1-summary.json",
            *(ROOT / "benchmarks" / "repo-pedant" / "cases").glob("*.case.json"),
            ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "manifest.json",
            *(ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "cases").glob("*.case.json"),
        ]
        for path in paths:
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), (list, dict))


if __name__ == "__main__":
    unittest.main()

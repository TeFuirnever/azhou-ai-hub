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
SUPER_CAVEMAN_DIR = ROOT / "skills" / "super-caveman"
LLM_WIKI_DIR = ROOT / "skills" / "llm-wiki"
SKILL_DIRS = (
    SKILL_DIR,
    ROOT / "skills" / "excalidraw-diagram",
    ROOT / "skills" / "spec-relay",
    SUPER_CAVEMAN_DIR,
    LLM_WIKI_DIR,
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
                    or {"node_modules", ".venv"} & set(path.parts)
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
    def test_public_readmes_expose_the_foundation_skill_contract(self) -> None:
        command_map = {
            "azhou-info": ("info", "version"),
            "azhou-doctor": ("doctor",),
            "azhou-setup": ("setup", "repair", "migrate", "uninstall"),
            "azhou-verify": ("verify",),
        }
        readmes = {
            "English": (ROOT / "README.md").read_text(encoding="utf-8"),
            "Chinese": (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"),
        }

        for language, text in readmes.items():
            lines = text.splitlines()
            for skill, commands in command_map.items():
                install = f"npx skills add TeFuirnever/azhou-ai-hub --skill {skill}"
                self.assertIn(install, text, f"{language}: {skill} install command")
                mapping = next((line for line in lines if line.startswith(f"| `{skill}` |")), "")
                self.assertTrue(mapping, f"{language}: {skill} CLI mapping")
                for command in commands:
                    self.assertIn(f"`{command}`", mapping, f"{language}: {skill} -> {command}")

        self.assertNotRegex(readmes["English"], r"\b\d+ deterministic tests\b")
        self.assertIn("complete deterministic test suite", readmes["English"])
        self.assertNotIn("Evidence today", readmes["English"])
        self.assertIn("Verification basis", readmes["English"])
        self.assertNotRegex(readmes["Chinese"], r"\b\d+ 项确定性测试\b")
        self.assertIn("完整确定性测试套件", readmes["Chinese"])
        self.assertNotIn("当前证据", readmes["Chinese"])
        self.assertIn("验证依据", readmes["Chinese"])

    def test_public_release_contract_stays_unpublished(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertNotIn("## Install in 30 seconds", english)
        self.assertNotIn("## 30 秒安装", chinese)
        self.assertNotIn("compare/v0.1.0...HEAD", changelog)
        self.assertNotIn("releases/tag/v0.1.0", changelog)
        self.assertRegex(changelog.lower(), r"draft|unpublished")

    def test_public_support_contract_separates_package_and_host_evidence(self) -> None:
        support = (ROOT / "docs" / "support-matrix.md").read_text(encoding="utf-8").lower()

        self.assertEqual(9, len(SKILL_DIRS))
        self.assertIn("nine canonical packages", support)
        self.assertIn("package availability", support)
        self.assertIn("host integration", support)
        self.assertIn("discovery/invocation", support)

    def test_public_provenance_contract_stays_reproducible(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        provenance = (
            ROOT / "skills" / "excalidraw-diagram" / "references" / "provenance.md"
        ).read_text(encoding="utf-8")
        diagram_types = (
            ROOT / "skills" / "excalidraw-diagram" / "references" / "diagram-types.md"
        ).read_text(encoding="utf-8")
        github_license_path = ROOT / "LICENSES" / "GitHub-Awesome-Copilot-MIT.txt"

        self.assertNotIn("\\`", notices)
        self.assertNotIn("\\`", provenance)
        self.assertIn("selected comparison baseline", provenance)
        self.assertIn("exact historical import commit was not recorded", provenance)
        self.assertIn("github/awesome-copilot", diagram_types)
        self.assertTrue(github_license_path.is_file())
        github_license = github_license_path.read_text(encoding="utf-8")
        self.assertIn("Copyright GitHub, Inc.", github_license)
        self.assertIn("GitHub-Awesome-Copilot-MIT.txt", notices)
        self.assertIn("GitHub-Awesome-Copilot-MIT.txt", provenance)

    def test_research_notes_use_portable_source_coordinates(self) -> None:
        for path in (
            ROOT / "docs" / "research" / "azhou-skill-portability.md",
            ROOT / "docs" / "research" / "oh-my-claudecode-foundation-capabilities.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text, str(path))

    def test_active_entry_docs_do_not_make_unverified_duration_claims(self) -> None:
        for path in (
            ROOT / "README.md",
            ROOT / "README.zh-CN.md",
            ROOT / "docs" / "README.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\b(?:30|60) seconds\b|(?:30|60) 秒", str(path))

    def test_azhou_setup_optional_support_is_link_only_and_bounded(self) -> None:
        skill = (ROOT / "skills" / "azhou-setup" / "SKILL.md").read_text(encoding="utf-8")
        cli = (ROOT / "scripts" / "azhou_hub.py").read_text(encoding="utf-8")

        self.assertIn("optional_support", skill)
        self.assertIn("https://github.com/TeFuirnever/azhou-ai-hub", skill)
        for boundary in (
            "mode is `setup`",
            "`--apply` succeeded",
            "at least one skill was newly installed",
            "dry-run",
            "repair",
            "migrate",
            "uninstall",
            "non-interactive",
        ):
            self.assertIn(boundary, skill)
        self.assertIn("must not replace `next_action`", skill)
        self.assertIn("Do not probe GitHub authentication", skill)
        self.assertNotIn("/user/starred/", skill)
        self.assertNotIn("github.com/TeFuirnever/azhou-ai-hub", cli)
        self.assertNotIn("/user/starred/", cli)
    def test_llm_wiki_import_is_mapped_and_harness_neutral(self) -> None:
        skill = (LLM_WIKI_DIR / "SKILL.md").read_text(encoding="utf-8")
        design = (LLM_WIKI_DIR / "references" / "design.md").read_text(encoding="utf-8")
        provenance = (LLM_WIKI_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        brand = (LLM_WIKI_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        script = (LLM_WIKI_DIR / "scripts" / "llm_wiki.py").read_text(encoding="utf-8")

        for operation in ("wiki_ingest", "wiki_query", "wiki_lint", "wiki_add", "wiki_list", "wiki_read", "wiki_delete"):
            self.assertIn(operation, skill)
        self.assertIn("Canonical store", design)
        self.assertIn("Production gates", design)
        self.assertIn("deee3a446dadc9bfea31cdc8b19b00b16718082e", provenance)
        self.assertIn("llm-wiki.receipt.v2", brand)
        self.assertIn("autoCapture` defaults to false", skill)
        self.assertIn('DEFAULT_STORE = ".azhou/llm-wiki"', script)

    def test_llm_wiki_license_and_notice_are_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "llm-wiki-source-MIT.txt").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2025 Yeachan Heo", license_text)
        self.assertIn("Yeachan Heo", notices)
        self.assertIn("llm-wiki-source-MIT.txt", notices)

    def test_llm_wiki_brand_layer_covers_the_interactive_lifecycle(self) -> None:
        skill = (LLM_WIKI_DIR / "SKILL.md").read_text(encoding="utf-8")
        brand = (LLM_WIKI_DIR / "references" / "brand-layer.md").read_text(encoding="utf-8")
        script = (LLM_WIKI_DIR / "scripts" / "llm_wiki.py").read_text(encoding="utf-8")
        anchors = (
            "🦊 阿舟 · LLM Wiki 启动｜operation=<operation>｜scope=<project-root>",
            "🧭 知识范围锁定｜topic=<topic>｜sources=<n|none>｜privacy=<checked|hold>",
            "🔎 Wiki 检索完成｜operation=<query|list|read>｜matches=<n>｜read_only=<true|false>",
            "📝 Wiki 更新完成｜action=<created|updated|deleted>｜page=<filename>｜confidence=<level|none>",
            "📦 Wiki 迁移完成｜status=<planned|migrated|already_current>｜files=<n>｜source_preserved=true",
            "🧪 Wiki 健康检查｜errors=<n>｜warnings=<n>｜info=<n>",
            "✅ 验证通过｜checks=<comma-separated ids>",
            "❌ 验证失败｜check=<id>｜impact=<fact>",
            "🔒 阿舟暂停这一项｜action=<action>｜missing=<authority|safe-input>",
        )
        for anchor in anchors:
            self.assertIn(anchor, brand)
        for section in (
            "### 🧭 Current truth",
            "### 📝 Changes",
            "### ✅ Verification",
            "### 🔒 Boundaries",
            "### ➡️ Next action",
            "### 🧠 Learning",
        ):
            self.assertIn(section, brand)
        self.assertIn("知识要留得住，也要经得起查证。", skill)
        self.assertIn("知识要留得住，也要经得起查证。", brand)
        self.assertIn("llm-wiki.receipt.v2", brand)
        self.assertIn('RECEIPT_SCHEMA = "llm-wiki.receipt.v2"', script)
        self.assertIn("[brand-layer.md](references/brand-layer.md)", skill)
        self.assertIn("Unicode", brand)

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
        self.assertIn("## 🦊 阿舟 · Repo Pedant receipt", skill)
        self.assertNotIn("## 🦊 阿舟 · Repo-pedant receipt", skill)
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

    def test_excalidraw_uses_one_canonical_public_motto(self) -> None:
        package = ROOT / "skills" / "excalidraw-diagram"
        skill = (package / "SKILL.md").read_text(encoding="utf-8")
        brand = (package / "references" / "brand-layer.md").read_text(encoding="utf-8")
        motto = "先让结构讲清关系，再让文字补充证据。"

        self.assertIn(f"> ✏️ {motto}", skill)
        self.assertIn(f"- 口号：`{motto}`", brand)
        self.assertIn(f"> ✏️ {motto}", brand)
        self.assertNotIn("图要可编辑，也要把关系说清楚。", brand)

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

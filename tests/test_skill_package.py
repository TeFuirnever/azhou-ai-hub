from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "repo-pedant"
SKILL = SKILL_DIR / "SKILL.md"
SKILL_DIRS = (SKILL_DIR, ROOT / "skills" / "excalidraw-diagram")


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
            *(ROOT / "benchmarks" / "repo-pedant" / "cases").glob("*.case.json"),
            ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "manifest.json",
            *(ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "cases").glob("*.case.json"),
        ]
        for path in paths:
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), (list, dict))


if __name__ == "__main__":
    unittest.main()

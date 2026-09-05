from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.check_repository import (
    SKILL_BRAND_CONTRACTS,
    check_action_pins,
    check_markdown_links,
    check_secret_patterns,
    check_skill_brand_contract,
    check_skill_discovery,
    check_treehouse_config,
    relative_markdown_targets,
)


ROOT = Path(__file__).parents[1]


def copy_skill_brand_surfaces(root: Path) -> None:
    for relative, contract in SKILL_BRAND_CONTRACTS.items():
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        brand_path = contract.get("brand_path")
        if brand_path:
            brand_source = ROOT / brand_path
            brand_target = root / brand_path
            brand_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(brand_source, brand_target)


def release_workflow_script() -> str:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    marker = "      - name: Validate tag and create draft\n        run: |\n"
    _, body = workflow.split(marker, 1)
    script: list[str] = []
    for line in body.splitlines():
        if line and not line.startswith("          "):
            break
        script.append(line[10:] if line else "")
    return "\n".join(script) + "\n"


class RepositoryPolicyTest(unittest.TestCase):
    def test_all_canonical_skills_follow_the_shared_brand_contract(self) -> None:
        self.assertEqual([], check_skill_brand_contract(ROOT))

    def test_skill_brand_contract_rejects_a_drifted_startup_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_skill_brand_surfaces(root)

            skill = root / "skills" / "azhou-info" / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "🦊 阿舟 · Azhou Info 启动｜mode=<info|version>｜scope=<checkout>",
                    "🦊 阿舟 · Azhou Info 启动: mode=<info|version>, scope=<checkout>",
                ),
                encoding="utf-8",
            )

            errors = check_skill_brand_contract(root)

            self.assertIn(
                "skill brand startup drift: skills/azhou-info/SKILL.md",
                errors,
            )

    def test_skill_brand_contract_rejects_missing_required_markers(self) -> None:
        relative = "skills/llm-wiki/SKILL.md"
        contract = SKILL_BRAND_CONTRACTS[relative]
        cases = (
            ("identity", ("🦊 阿舟 · LLM Wiki",), "identity missing"),
            ("motto", (contract["motto"],), "motto missing"),
            ("success", ("✅ 验证通过",), "success marker missing"),
            ("failure", ("❌ 验证失败",), "failure marker missing"),
            ("hold", ("🔒 阿舟暂停这一项",), "hold marker missing"),
            ("emoji boundary", ("Emoji",), "emoji boundary missing"),
            ("raw evidence", ("原始证据", "raw evidence"), "raw-evidence boundary missing"),
            (
                "Unicode fallback",
                ("host 不支持 Unicode", "Host 不支持 Unicode", "A host without Unicode"),
                "Unicode fallback missing",
            ),
        )

        for name, markers, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                copy_skill_brand_surfaces(root)
                surfaces = [root / relative, root / contract["brand_path"]]
                replacements = 0
                for surface in surfaces:
                    text = surface.read_text(encoding="utf-8")
                    for marker in markers:
                        replacements += text.count(marker)
                        text = text.replace(marker, "removed-marker")
                    surface.write_text(text, encoding="utf-8")

                self.assertGreater(replacements, 0)
                self.assertIn(
                    f"skill brand {expected}: {relative}",
                    check_skill_brand_contract(root),
                )

    def test_skill_brand_contract_rejects_a_missing_brand_layer(self) -> None:
        relative = "skills/llm-wiki/SKILL.md"
        contract = SKILL_BRAND_CONTRACTS[relative]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_skill_brand_surfaces(root)
            (root / contract["brand_path"]).unlink()

            self.assertIn(
                f"skill brand layer missing: {contract['brand_path']}",
                check_skill_brand_contract(root),
            )

    def test_skill_brand_contract_requires_identity_in_skill_md_itself(self) -> None:
        relative = "skills/super-caveman/SKILL.md"
        contract = SKILL_BRAND_CONTRACTS[relative]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_skill_brand_surfaces(root)
            skill = root / relative
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    f"🦊 阿舟 · {contract['display_name']}", "removed-marker"
                ),
                encoding="utf-8",
            )

            self.assertIn(
                f"skill brand identity missing: {relative}",
                check_skill_brand_contract(root),
            )

    def test_only_canonical_runtime_skills_are_discoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = [
                root / "skills" / "super-caveman" / "SKILL.md",
                root / "skills" / "excalidraw-diagram" / "SKILL.md",
                root / "skills" / "azhou-doctor" / "SKILL.md",
                root / "skills" / "azhou-info" / "SKILL.md",
                root / "skills" / "azhou-setup" / "SKILL.md",
                root / "skills" / "azhou-verify" / "SKILL.md",
                root / "skills" / "repo-pedant" / "SKILL.md",
                root / "skills" / "lavish" / "SKILL.md",
                root / "skills" / "eli5" / "SKILL.md",
                root / "skills" / "autoresearch" / "SKILL.md",
                root / "skills" / "arch-doc" / "SKILL.md",
            ]
            self.assertEqual([], check_skill_discovery(expected, root))
            legacy = root / "benchmarks" / "repo-pedant" / "upstream" / "neat-freak" / "SKILL.md"
            errors = check_skill_discovery([*expected, legacy], root)
            self.assertEqual(["unexpected installable skill: benchmarks/repo-pedant/upstream/neat-freak/SKILL.md"], errors)

    def test_relative_markdown_targets_skip_remote_and_anchor_links(self) -> None:
        text = "[local](docs/run.md) [remote](https://example.com/x) [anchor](#install)"
        self.assertEqual(["docs/run.md"], relative_markdown_targets(text))

    def test_broken_markdown_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text("[missing](docs/missing.md)\n", encoding="utf-8")
            errors = check_markdown_links([readme], root)
            self.assertEqual(1, len(errors))
            self.assertIn("broken local link", errors[0])

    def test_workflow_action_requires_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            workflow = workflows / "ci.yml"
            workflow.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            errors = check_action_pins([workflow], root)
            self.assertEqual(1, len(errors))
            workflow.write_text(
                "steps:\n  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n",
                encoding="utf-8",
            )
            self.assertEqual([], check_action_pins([workflow], root))

    def test_benchmark_workflow_fetches_full_history(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        _, benchmark_tail = workflow.split("  benchmarks:\n", 1)
        benchmark_job, _ = benchmark_tail.split("\n  policy:\n", 1)

        self.assertIn("fetch-depth: 0", benchmark_job)

    def test_release_workflow_enforces_ref_and_api_outcomes(self) -> None:
        cases = (
            ("outside-main", "refs/heads/feature", 2, False),
            ("exists", "refs/heads/main", 1, False),
            ("not-found", "refs/heads/main", 0, True),
            ("api-error", "refs/heads/main", 1, False),
        )
        for scenario, git_ref, expected_code, creates_release in cases:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                temp = Path(directory)
                calls = temp / "gh-calls.log"
                gh = temp / "gh"
                gh.write_text(
                    """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$MOCK_GH_CALLS"
if [ "$1" = "api" ]; then
  case "$MOCK_GH_SCENARIO" in
    exists) printf 'HTTP/2.0 200 OK\\n'; exit 0 ;;
    not-found) printf 'HTTP/2.0 404 Not Found\\n'; exit 1 ;;
    api-error) printf 'HTTP/2.0 403 Forbidden\\n'; printf 'denied\\n' >&2; exit 1 ;;
  esac
fi
exit 0
""",
                    encoding="utf-8",
                )
                gh.chmod(0o755)
                env = os.environ.copy()
                env.update(
                    {
                        "PATH": f"{temp}{os.pathsep}{env['PATH']}",
                        "MOCK_GH_CALLS": str(calls),
                        "MOCK_GH_SCENARIO": scenario,
                        "GITHUB_REF": git_ref,
                        "GITHUB_REPOSITORY": "TeFuirnever/azhou-ai-hub",
                        "GITHUB_SHA": "a" * 40,
                        "RELEASE_TAG": "v0.1.0",
                        "RUNNER_TEMP": str(temp),
                    }
                )

                result = subprocess.run(
                    ["bash", "-eu", "-c", release_workflow_script()],
                    cwd=ROOT,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(expected_code, result.returncode, result.stderr)
                observed_calls = calls.read_text(encoding="utf-8") if calls.exists() else ""
                self.assertEqual(creates_release, "release create" in observed_calls)
                if scenario == "api-error":
                    self.assertIn("unable to determine whether release exists", result.stderr)

    def test_secret_shapes_are_reported_without_echoing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.txt"
            marker = "AI" + "za" + ("A" * 35)
            fixture.write_text(f"credential={marker}\n", encoding="utf-8")

            errors = check_secret_patterns([fixture], root)

            self.assertEqual(1, len(errors))
            self.assertIn("google-api-key", errors[0])
            self.assertNotIn(marker, errors[0])
            fixture.write_text("credential=offline-renderer-disabled\n", encoding="utf-8")
            self.assertEqual([], check_secret_patterns([fixture], root))

    def test_aws_shape_requires_token_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.txt"
            marker = "AK" + "IA" + ("A" * 16)
            fixture.write_text(f"encoded=Q{marker}Z\n", encoding="utf-8")
            self.assertEqual([], check_secret_patterns([fixture], root))
            fixture.write_text(f'credential="{marker}"\n', encoding="utf-8")
            self.assertEqual(1, len(check_secret_patterns([fixture], root)))

    def test_treehouse_config_requires_a_small_git_pool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "treehouse.toml"
            config.write_text('max_trees = 4\nvcs = "git"\n', encoding="utf-8")
            self.assertEqual([], check_treehouse_config(root))

            config.write_text('max_trees = 16\nvcs = "jj"\n', encoding="utf-8")
            errors = check_treehouse_config(root)
            self.assertIn("treehouse max_trees must be an integer from 1 through 6", errors)
            self.assertIn("treehouse vcs must be git", errors)

    def test_treehouse_config_rejects_repo_hooks_and_invalid_toml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "treehouse.toml"
            config.write_text(
                'max_trees = 4\nvcs = "git"\nroot = "./"\n[hooks]\npost_create = ["unsafe"]\n',
                encoding="utf-8",
            )
            self.assertEqual(
                [
                    "treehouse repo config must not define hooks; use reviewed user-level hooks",
                    "treehouse repo config must not pin a machine-specific pool root",
                ],
                check_treehouse_config(root),
            )

            config.write_text("max_trees = [\n", encoding="utf-8")
            errors = check_treehouse_config(root)
            self.assertEqual(1, len(errors))
            self.assertTrue(errors[0].startswith("treehouse config is invalid TOML:"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.check_repository import (
    check_action_pins,
    check_markdown_links,
    check_secret_patterns,
    check_skill_discovery,
    check_treehouse_config,
    relative_markdown_targets,
)


ROOT = Path(__file__).parents[1]


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
            self.assertIn("treehouse max_trees must be an integer from 1 through 4", errors)
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

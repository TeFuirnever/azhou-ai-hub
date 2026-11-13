from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Direct execution (`python tests/test_check_retired_surfaces.py`) does not
# put the repository root on sys.path, so bootstrap it before importing the
# scripts package the way `unittest discover` from the root already does.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_retired_surfaces import (  # noqa: E402
    check_retired_surface_references,
    run_checks,
)


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class RetiredSurfaceReverseScanTest(unittest.TestCase):
    def test_repository_scans_clean_after_the_cut(self) -> None:
        self.assertEqual([], run_checks(ROOT))

    def test_kit_name_in_a_live_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = write(root, "docs/new-guide.md", "Install agent-orchestration-kit first.\n")
            self.assertEqual(
                ["retired-surface reference: docs/new-guide.md:1: agent-orchestration-kit"],
                check_retired_surface_references([guide], root),
            )

    def test_deleted_hub_adapter_surfaces_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = write(
                root,
                "scripts/new_router_seam.py",
                "from scripts.integration_model_router import install\n"
                "verdict = kit_installer.pstack_coexistence\n"
                "# compound identifiers like load_pstack_coexistence are not the seam\n",
            )
            errors = check_retired_surface_references([script], root)
            self.assertIn(
                "retired-surface reference: scripts/new_router_seam.py:1: integration_model_router",
                errors,
            )
            self.assertIn(
                "retired-surface reference: scripts/new_router_seam.py:2: pstack_coexistence",
                errors,
            )

    def test_legacy_root_name_fails_but_frozen_identities_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = write(
                root,
                "packages/agent-skin/tools/new-check.mjs",
                "const owner = 'azhou.codex-startup-animation';\n"
                "const pet = 'codex-startup-animation/native-pet-v1';\n"
                "const upstream = 'panding999/codex-startup-animation';\n"
                "const origin = 'TeFuirnever/codex-startup-animation';\n",
            )
            self.assertEqual([], check_retired_surface_references([frozen], root))
            live = write(
                root,
                "docs/new-guide.md",
                "Build from the codex-startup-animation checkout.\n",
            )
            self.assertEqual(
                ["retired-surface reference: docs/new-guide.md:1: codex-startup-animation"],
                check_retired_surface_references([live], root),
            )

    def test_kit_prose_names_fail_in_live_docs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = write(
                root,
                "docs/principles.md",
                "| Orchestrator Kit | token efficiency |\n"
                "Install the Agent Orchestration Kit first.\n"
                "Use the Codex model-routing integration.\n"
                "Register the Model-Router entry.\n"
                "pstack / Kit acceptance continues.\n"
                "Remove it with the Kit's own uninstaller.\n",
            )
            self.assertEqual(
                [
                    "retired-surface reference: docs/principles.md:1: Orchestration Kit",
                    "retired-surface reference: docs/principles.md:1: Kit",
                    "retired-surface reference: docs/principles.md:2: Orchestration Kit",
                    "retired-surface reference: docs/principles.md:2: Kit",
                    "retired-surface reference: docs/principles.md:3: model-router",
                    "retired-surface reference: docs/principles.md:4: model-router",
                    "retired-surface reference: docs/principles.md:5: Kit",
                    "retired-surface reference: docs/principles.md:6: Kit",
                ],
                check_retired_surface_references([guide], root),
            )

    def test_kit_tokens_avoid_living_and_generic_uses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prose = write(
                root,
                "docs/new-guide.md",
                "MIT with retained Cursor Team Kit and thermos notices.\n"
                "Kit-owned files and cursor-team-kit stay compounds.\n"
                "The same text a model router sees.\n"
                "WebKit and SDKs are unrelated.\n",
            )
            self.assertEqual([], check_retired_surface_references([prose], root))
            # The bare noun is Markdown-only: vendored code may spell it freely.
            bundle = write(root, "skills/demo/references/vendor/app.js", "const Kit = 1;\n")
            self.assertEqual([], check_retired_surface_references([bundle], root))
            # The product phrase still fails outside Markdown.
            script = write(root, "scripts/new_tool.py", "# wraps the Orchestration Kit\n")
            self.assertEqual(
                ["retired-surface reference: scripts/new_tool.py:1: Orchestration Kit"],
                check_retired_surface_references([script], root),
            )

    def test_kit_retirement_narrative_is_path_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            line = (
                "- **Agent Orchestration Kit (model router)** — never released; removed "
                "together with the model-router Hub entry: remove it with the Kit's own uninstaller.\n"
            )
            readme = write(root, "README.md", line)
            self.assertEqual([], check_retired_surface_references([readme], root))
            mirror = write(root, "docs/new-guide.md", line)
            self.assertTrue(check_retired_surface_references([mirror], root))

    def test_zcode_host_surface_tokens_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = write(
                root,
                "packages/agent-skin/tools/build-macos.sh",
                "swiftc Native/ZCodeSkinDriver.swift\n"
                "node tools/test-zcode-runtime.py\n"
                "open extension/hosts/zcode.mjs\n"
                "OWNER=azhou-zcode-startup\n"
                "cat docs/offline-acceptance-runbook.md\n",
            )
            errors = check_retired_surface_references([script], root)
            self.assertEqual(
                [
                    "retired-surface reference: packages/agent-skin/tools/build-macos.sh:1: ZCodeSkin",
                    "retired-surface reference: packages/agent-skin/tools/build-macos.sh:2: test-zcode-",
                    "retired-surface reference: packages/agent-skin/tools/build-macos.sh:3: hosts/zcode.mjs",
                    "retired-surface reference: packages/agent-skin/tools/build-macos.sh:4: azhou-zcode-startup",
                    "retired-surface reference: packages/agent-skin/tools/build-macos.sh:5: offline-acceptance-runbook",
                ],
                errors,
            )

    def test_retired_paths_fail_even_without_content_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kit = write(root, "packages/agent-orchestration-kit/UPSTREAM.md", "restored\n")
            legacy = write(root, "packages/codex-startup-animation/README.md", "restored\n")
            adapter = write(root, "packages/agent-skin/extension/hosts/zcode.mjs", "export {}\n")
            driver = write(root, "packages/agent-skin/Native/ZCodeSkinRuntime.swift", "// back\n")
            errors = check_retired_surface_references([kit, legacy, adapter, driver], root)
            self.assertEqual(
                [
                    "retired surface resurrected: packages/agent-orchestration-kit/UPSTREAM.md",
                    "retired surface resurrected: packages/codex-startup-animation/README.md",
                    "retired surface resurrected: packages/agent-skin/extension/hosts/zcode.mjs",
                    "retired surface resurrected: packages/agent-skin/Native/ZCodeSkinRuntime.swift",
                ],
                errors,
            )

    def test_historical_record_surfaces_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = [
                write(root, "evidence/old.md", "ZCodeSkinDriver and agent-orchestration-kit\n"),
                write(
                    root,
                    "packages/agent-skin/evidence/old.md",
                    "hosts/zcode.mjs and codex-startup-animation\n",
                ),
                write(root, "docs/decisions/old.md", "agent-orchestration-kit removed\n"),
                write(root, "docs/design/old/plan.md", "codex-startup-animation plan\n"),
                write(root, "docs/research/old.md", "zcode-adapter study\n"),
                write(root, "docs/specs/old.md", "test-zcode- spec\n"),
                write(root, "CHANGELOG.md", "- Removed agent-orchestration-kit.\n"),
            ]
            self.assertEqual([], check_retired_surface_references(receipts, root))

    def test_frozen_site_comment_is_path_scoped_and_hides_nothing_else(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = "packages/agent-skin/Native/InstallRegistryCore.swift"
            comment = '// Frozen installed-state owner identity inherited from codex-startup-animation;\n'
            core = write(root, site, comment + 'let owner = "azhou.codex-startup-animation"\n')
            self.assertEqual([], check_retired_surface_references([core], root))
            core.write_text(
                comment + "// See codex-startup-animation for the old installer.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [
                    "retired-surface reference: "
                    "packages/agent-skin/Native/InstallRegistryCore.swift:2: codex-startup-animation"
                ],
                check_retired_surface_references([core], root),
            )
            # The same comment is not a frozen site anywhere else.
            other = write(root, "docs/new-guide.md", comment)
            self.assertTrue(check_retired_surface_references([other], root))

    def test_frozen_narrative_fragment_is_path_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = write(
                root,
                "README.md",
                "- **Legacy `codex-startup-animation` package** — last version `0.7.1/build 8`.\n",
            )
            self.assertEqual([], check_retired_surface_references([readme], root))
            readme.write_text(
                readme.read_text(encoding="utf-8")
                + "Rebuild it from codex-startup-animation locally.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                ["retired-surface reference: README.md:2: codex-startup-animation"],
                check_retired_surface_references([readme], root),
            )
            # The frozen statement belongs to the README surface only.
            mirror = write(
                root,
                "docs/new-guide.md",
                "- **Legacy `codex-startup-animation` package** — copy below.\n",
            )
            self.assertTrue(check_retired_surface_references([mirror], root))

    def test_gate_definition_paths_only_excuse_themselves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition = (ROOT / "scripts/check_retired_surfaces.py").read_text(encoding="utf-8")
            self_path = write(root, "scripts/check_retired_surfaces.py", definition)
            self.assertEqual([], check_retired_surface_references([self_path], root))
            elsewhere = write(root, "docs/gate-dump.md", definition)
            errors = check_retired_surface_references([elsewhere], root)
            self.assertTrue(any("agent-orchestration-kit" in error for error in errors))

    def test_binary_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blob = root / "assets" / "snapshot.bin"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"agent-orchestration-kit\x00codex-startup-animation\x00")
            self.assertEqual([], check_retired_surface_references([blob], root))


if __name__ == "__main__":
    unittest.main()

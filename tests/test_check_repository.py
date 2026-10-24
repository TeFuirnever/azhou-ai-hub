from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.check_repository import (
    MEMORY_CREDIT_SURFACES,
    SKILL_BRAND_CONTRACTS,
    check_action_pins,
    check_chat_presentation_examples,
    check_command_surface,
    check_fidelity_axis, check_azhou_description_brand,
    check_invocation_axis,
    check_legacy_broadcast_delimiter,
    check_markdown_links,
    check_memory_credit_contract,
    peel_chat_presentation,
    check_public_boundaries,
    check_reference_script_paths,
    check_rename_residue,
    check_secret_patterns,
    check_skill_brand_contract,
    check_skill_discovery,
    check_router_coverage,
    check_skill_platform_view,
    check_treehouse_config,
    public_files,
    relative_markdown_targets,
)


ROOT = Path(__file__).parents[1]


class RouterCoverageTest(unittest.TestCase):
    def test_router_names_every_canonical_skill(self) -> None:
        self.assertEqual([], check_router_coverage(ROOT))

    def test_router_missing_a_name_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            router = root / "skills" / "super-ask-azhou"
            router.mkdir(parents=True)
            (router / "SKILL.md").write_text("Routes to super-eli5 and lavish only.\n", encoding="utf-8")
            errors = check_router_coverage(root)
            self.assertTrue(
                any("router coverage missing" in error for error in errors),
                errors,
            )
            self.assertIn("router coverage missing: super-arch-doc", errors)
            self.assertNotIn("router coverage missing: super-eli5", errors)


class SkillPlatformViewTest(unittest.TestCase):
    """The per-skill platform view is a derivation, never a second authority."""

    def test_view_is_derived_from_the_support_matrix(self) -> None:
        self.assertEqual([], check_skill_platform_view(ROOT))

    def write_fixture(self, root: Path, view_text: str) -> None:
        docs = root / "docs"
        docs.mkdir(parents=True)
        shutil.copy(ROOT / "docs" / "support-matrix.md", docs / "support-matrix.md")
        (docs / "skill-platform-view.md").write_text(view_text, encoding="utf-8")

    def real_view(self) -> str:
        return (ROOT / "docs" / "skill-platform-view.md").read_text(encoding="utf-8")

    def test_new_claim_in_the_view_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view = self.real_view()
            mutated = view.replace(
                "supported with filesystem tools<br>supported after package dependencies",
                "supported everywhere out of the box<br>supported after package dependencies",
                1,
            )
            self.assertNotEqual(view, mutated)
            self.write_fixture(root, mutated)
            errors = check_skill_platform_view(root)
            self.assertTrue(
                any(
                    "claim not derived from its governing rows" in error
                    and "supported everywhere out of the box" in error
                    for error in errors
                ),
                errors,
            )

    def test_skill_set_drift_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mutated = self.real_view().replace(
                "| super-ask-azhou | supported by a configured skill root |",
                "| retired-skill | supported by a configured skill root |",
                1,
            )
            self.assertNotIn("| retired-skill |", self.real_view())
            self.assertIn("| retired-skill |", mutated)
            self.write_fixture(root, mutated)
            errors = check_skill_platform_view(root)
            self.assertIn("skill platform view row missing: super-ask-azhou", errors)
            self.assertIn("skill platform view row unexpected: retired-skill", errors)

    def test_map_entry_without_a_matrix_row_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mutated = self.real_view().replace(
                "Eli5 zero-background picture explainer |",
                "Eli5 fictional capability row |",
                1,
            )
            self.assertNotIn("Eli5 fictional capability row", self.real_view())
            self.write_fixture(root, mutated)
            errors = check_skill_platform_view(root)
            self.assertTrue(
                any(
                    "map row not found in support matrix" in error and "super-eli5" in error
                    for error in errors
                ),
                errors,
            )

    def test_fragment_outside_governing_rows_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mutated = self.real_view().replace(
                "(evidence/eli5-load-explain-zcode-2026-09-03.md) | host-dependent",
                "(evidence/retired-skill-fragment-2026-01-01.md) | host-dependent",
                1,
            )
            self.assertNotIn(
                "retired-skill-fragment-2026-01-01.md) | host-dependent",
                self.real_view(),
            )
            self.write_fixture(root, mutated)
            errors = check_skill_platform_view(root)
            self.assertTrue(
                any(
                    "claim not derived from its governing rows" in error and "super-eli5:" in error
                    for error in errors
                ),
                errors,
            )


class InvocationAxisTest(unittest.TestCase):
    def test_declared_invocation_values_match_the_enum(self) -> None:
        self.assertEqual([], check_invocation_axis(ROOT))

    def test_unknown_invocation_value_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "super-lavish" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: super-lavish\ndescription: probe\ninvocation: sometimes\n---\n# Super Lavish\n",
                encoding="utf-8",
            )
            self.assertEqual(
                ["skill invocation enum invalid: skills/super-lavish/SKILL.md: sometimes"],
                check_invocation_axis(root),
            )

    def test_missing_invocation_declaration_fails_for_every_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for package in ("super-lavish", "super-eli5"):
                skill = root / "skills" / package / "SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(
                    f"---\nname: {package}\ndescription: probe\n---\n# Probe\n",
                    encoding="utf-8",
                )
            self.assertEqual(
                [
                    "skill invocation declaration missing: skills/super-eli5/SKILL.md",
                    "skill invocation declaration missing: skills/super-lavish/SKILL.md",
                ],
                check_invocation_axis(root),
            )


class FidelityAxisTest(unittest.TestCase):
    def test_every_canonical_skill_matches_the_prefix_rule(self) -> None:
        self.assertEqual([], check_fidelity_axis(ROOT))

    def write_skill(self, root: Path, relative: str, classification: str | None) -> None:
        skill = root / relative
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("---\nname: probe\ndescription: probe\ninvocation: both\n---\n# Probe\n", encoding="utf-8")
        if classification is not None:
            provenance = root / relative.replace("SKILL.md", "references/provenance.md")
            provenance.parent.mkdir(parents=True, exist_ok=True)
            provenance.write_text(f"# Provenance\n\nClassification: `{classification}` — probe.\n", encoding="utf-8")

    def test_new_skill_without_a_classification_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_skill(root, "skills/super-probe/SKILL.md", None)
            self.assertEqual(
                ["skill fidelity classification missing: skills/super-probe/SKILL.md"],
                check_fidelity_axis(root),
            )

    def test_unknown_classification_value_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_skill(root, "skills/super-probe/SKILL.md", "forked")
            self.assertEqual(
                ["skill fidelity classification enum invalid: skills/super-probe/SKILL.md: forked"],
                check_fidelity_axis(root),
            )

    def test_missing_brand_prefix_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_skill(root, "skills/probe/SKILL.md", "adapted")
            self.assertEqual(
                ["canonical package missing super- brand prefix: skills/probe/SKILL.md"],
                check_fidelity_axis(root),
            )

    def test_brand_prefix_accepts_any_fidelity_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_skill(root, "skills/super-lavish/SKILL.md", "original")
            self.assertEqual([], check_fidelity_axis(root))

    def test_probe_skill_requires_its_own_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_skill(root, "skills/super-probe/SKILL.md", None)
            self.assertEqual(
                ["skill fidelity classification missing: skills/super-probe/SKILL.md"],
                check_fidelity_axis(root),
            )


class AzhouDescriptionBrandTest(unittest.TestCase):
    def test_repository_descriptions_carry_the_brand_keyword(self) -> None:
        self.assertEqual([], check_azhou_description_brand(ROOT))

    def test_incidental_azhou_substring_is_not_enough(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "super-azhou-doctor" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: super-azhou-doctor\ndescription: Renamed from azhou-doctor. Diagnose a checkout.\ninvocation: both\n---\n# Probe\n",
                encoding="utf-8",
            )
            self.assertEqual(
                ["skill description missing Azhou brand keyword: skills/super-azhou-doctor/SKILL.md"],
                check_azhou_description_brand(root),
            )

    def test_uniform_marker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "super-eli5" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: super-eli5\ndescription: Azhou skill. Explain simply.\ninvocation: both\n---\n# Probe\n",
                encoding="utf-8",
            )
            self.assertEqual([], check_azhou_description_brand(root))


class RenameResidueTest(unittest.TestCase):
    def test_renamed_catalog_has_no_residue_outside_allowed_surfaces(self) -> None:
        self.assertEqual([], check_rename_residue(public_files(ROOT), ROOT))

    def test_old_name_outside_allowed_surfaces_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaked = root / "docs" / "new-guide.md"
            leaked.parent.mkdir(parents=True)
            leaked.write_text("Run repo-pedant reconcile at close.\n", encoding="utf-8")
            self.assertEqual(
                ["rename residue outside allowed surfaces: docs/new-guide.md: repo-pedant -> super-repo-pedant"],
                check_rename_residue([leaked], root),
            )

    def test_old_name_inside_allowed_surfaces_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "skills" / "super-repo-pedant" / "SKILL.md"
            allowed.parent.mkdir(parents=True)
            allowed.write_text(
                "description: Renamed from repo-pedant (the old name still triggers this skill).\n",
                encoding="utf-8",
            )
            history = root / "docs" / "research" / "note.md"
            history.parent.mkdir(parents=True)
            history.write_text("The repo-pedant package was renamed.\n", encoding="utf-8")
            self.assertEqual([], check_rename_residue([allowed, history], root))

    def test_compound_and_prefixed_forms_are_not_residue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "docs" / "new-guide.md"
            doc.parent.mkdir(parents=True)
            doc.write_text(
                "super-repo-pedant, .repo-pedant/, .azhou/repo-pedant, lavish-axi, .lavish/, super-lavish\n",
                encoding="utf-8",
            )
            self.assertEqual([], check_rename_residue([doc], root))


class ReferenceScriptPathsTest(unittest.TestCase):
    """Reference docs cite scripts mechanically: a `scripts/...` code span
    must resolve at the repository root or, on a skill's own reference page,
    inside the citing skill package (the super-arch-doc and super-excalidraw-diagram
    doc-script drift mechanism, now gated)."""

    def test_reference_docs_cite_existing_scripts(self) -> None:
        self.assertEqual([], check_reference_script_paths(public_files(ROOT), ROOT))

    def test_planted_broken_script_path_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "docs" / "workflow.md"
            doc.parent.mkdir(parents=True)
            doc.write_text("Render the hero with `scripts/does-not-exist.py`.\n", encoding="utf-8")
            self.assertEqual(
                ["reference script path missing: docs/workflow.md:1: scripts/does-not-exist.py"],
                check_reference_script_paths([doc], root),
            )

    def test_skill_reference_pages_resolve_their_own_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packaged = root / "skills" / "super-eli5" / "scripts" / "check_audience.py"
            packaged.parent.mkdir(parents=True)
            packaged.write_text("print('ok')\n", encoding="utf-8")
            reference = root / "skills" / "super-eli5" / "references" / "setup.md"
            reference.parent.mkdir(parents=True)
            reference.write_text("Assert with `scripts/check_audience.py`.\n", encoding="utf-8")
            self.assertEqual([], check_reference_script_paths([reference], root))

            docs_page = root / "docs" / "super-eli5.md"
            docs_page.parent.mkdir(parents=True)
            docs_page.write_text("Assert with `scripts/check_audience.py`.\n", encoding="utf-8")
            self.assertEqual(
                ["reference script path missing: docs/super-eli5.md:1: scripts/check_audience.py"],
                check_reference_script_paths([docs_page], root),
            )

    def test_placeholders_and_non_path_spans_stay_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "docs" / "conventions.md"
            doc.parent.mkdir(parents=True)
            doc.write_text(
                "Template `<skill-dir>/scripts/verify_doc.py` stays a placeholder. "
                "Upstream source `packages/utils/src/export.ts` is not a repo path. "
                "Command spans like `python scripts/unplanted.py --check` and the bare "
                "`scripts/` directory mention are not path citations.\n",
                encoding="utf-8",
            )
            self.assertEqual([], check_reference_script_paths([doc], root))

    def test_historical_and_vendored_surfaces_stay_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            research = root / "docs" / "research" / "2026-01-01-note.md"
            research.parent.mkdir(parents=True)
            research.write_text("The survey recorded `scripts/gone.py`.\n", encoding="utf-8")
            vendored = root / "skills" / "super-excalidraw-diagram" / "references" / ".venv" / "lib" / "note.md"
            vendored.parent.mkdir(parents=True)
            vendored.write_text("Upstream ships `scripts/gone.py`.\n", encoding="utf-8")
            self.assertEqual(
                [], check_reference_script_paths([research, vendored], root)
            )


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


class LocalSkillInstallationTest(unittest.TestCase):
    def test_local_install_is_excluded_but_forced_publication_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            skill = root / ".agents/skills/example/SKILL.md"
            metadata = root / ".agents/skills/example/agents/openai.yaml"
            metadata.parent.mkdir(parents=True)
            skill.write_text("# Local tool skill\n", encoding="utf-8")
            metadata.write_text("interface: {}\n", encoding="utf-8")
            self.assertNotIn(skill, public_files(root))
            self.assertNotIn(metadata, public_files(root))

            subprocess.run(
                ["git", "add", "-f", ".agents/skills/example"], cwd=root, check=True,
            )
            files = public_files(root)
            self.assertIn(skill, files)
            self.assertIn(metadata, files)
            self.assertIn(
                "unexpected installable skill: .agents/skills/example/SKILL.md",
                check_skill_discovery(files, root),
            )
            self.assertIn(
                "vendor-specific package metadata is forbidden: .agents/skills/example/agents/openai.yaml",
                check_public_boundaries(files, root),
            )


class RepositoryPolicyTest(unittest.TestCase):
    def test_all_canonical_skills_follow_the_shared_brand_contract(self) -> None:
        self.assertEqual([], check_skill_brand_contract(ROOT))

    def test_skill_brand_contract_rejects_a_drifted_startup_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_skill_brand_surfaces(root)

            skill = root / "skills" / "super-azhou-info" / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "🦊 阿舟 · Azhou Info 启动（mode=<info|version>, scope=<checkout>）",
                    "🦊 阿舟 · Azhou Info 启动: mode=<info|version>, scope=<checkout>",
                ),
                encoding="utf-8",
            )

            errors = check_skill_brand_contract(root)

            self.assertIn(
                "skill brand startup drift: skills/super-azhou-info/SKILL.md",
                errors,
            )

    def test_skill_brand_contract_rejects_missing_required_markers(self) -> None:
        relative = "skills/super-llm-wiki/SKILL.md"
        contract = SKILL_BRAND_CONTRACTS[relative]
        cases = (
            ("identity", ("🦊 阿舟 · Super LLM Wiki",), "identity missing"),
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
        relative = "skills/super-llm-wiki/SKILL.md"
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
        relative = "skills/super-excalidraw-diagram/SKILL.md"
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

    def test_memory_credit_contract_passes_on_the_live_repo(self) -> None:
        self.assertEqual([], check_memory_credit_contract(ROOT))

    def test_memory_credit_contract_rejects_a_dropped_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in MEMORY_CREDIT_SURFACES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# surface\n", encoding="utf-8")

            errors = check_memory_credit_contract(root)

            self.assertEqual(len(MEMORY_CREDIT_SURFACES), len(errors))
            for relative in MEMORY_CREDIT_SURFACES:
                self.assertIn(f"memory credit format missing: {relative}", errors)

    def test_legacy_broadcast_delimiter_passes_on_the_live_repo(self) -> None:
        self.assertEqual([], check_legacy_broadcast_delimiter(public_files(ROOT), ROOT))

    def test_legacy_broadcast_delimiter_rejects_the_pipe_grammar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            surface = root / "skills" / "probe" / "brand-layer.md"
            surface.parent.mkdir(parents=True)
            # Concatenated so this test file itself stays free of the legacy
            # literal the delimiter scan rejects.
            pipe = "｜"
            surface.write_text(
                f"🦊 阿舟 · Probe 启动{pipe}mode=route{pipe}scope=/repo\n", encoding="utf-8"
            )

            errors = check_legacy_broadcast_delimiter([surface], root)

            self.assertIn(
                "legacy broadcast delimiter: skills/probe/brand-layer.md:1", errors
            )

    def test_legacy_broadcast_delimiter_allows_new_grammar_and_held_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            surface = root / "skills" / "probe" / "SKILL.md"
            surface.parent.mkdir(parents=True)
            surface.write_text(
                "🦊 阿舟 · Probe 启动（mode=route, scope=/repo）\n", encoding="utf-8"
            )
            held = root / "scripts" / "check_repository.py"
            held.parent.mkdir(parents=True)
            pipe = "｜"
            held.write_text(
                f"🦊 阿舟 · Probe 启动{pipe}mode=x{pipe}scope=y\n", encoding="utf-8"
            )

            self.assertEqual(
                [], check_legacy_broadcast_delimiter([surface, held], root)
            )

    def test_only_canonical_runtime_skills_are_discoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = [
                root / "skills" / "super-excalidraw-diagram" / "SKILL.md",
                root / "skills" / "super-azhou-doctor" / "SKILL.md",
                root / "skills" / "super-azhou-info" / "SKILL.md",
                root / "skills" / "super-azhou-setup" / "SKILL.md",
                root / "skills" / "super-azhou-verify" / "SKILL.md",
                root / "skills" / "super-repo-pedant" / "SKILL.md",
                root / "skills" / "super-lavish" / "SKILL.md",
                root / "skills" / "super-eli5" / "SKILL.md",
                root / "skills" / "super-autoresearch" / "SKILL.md",
                root / "skills" / "super-ask-azhou" / "SKILL.md",
                root / "skills" / "super-arch-doc" / "SKILL.md",
                root / "skills" / "super-archify" / "SKILL.md",
                root / "skills" / "super-asd-ste100" / "SKILL.md",
                root / "skills" / "super-session-insights" / "SKILL.md",
            ]
            self.assertEqual([], check_skill_discovery(expected, root))
            legacy = root / "benchmarks" / "super-repo-pedant" / "upstream" / "neat-freak" / "SKILL.md"
            errors = check_skill_discovery([*expected, legacy], root)
            self.assertEqual(["unexpected installable skill: benchmarks/super-repo-pedant/upstream/neat-freak/SKILL.md"], errors)

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

    def test_command_surface_reports_posix_only_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "docs" / "installation.md"
            target.parent.mkdir(parents=True)
            target.write_text("```bash\npython3 scripts/x.py --json\n```\n", encoding="utf-8")
            errors = check_command_surface([target], root)
            self.assertEqual(1, len(errors))
            self.assertIn("POSIX-only interpreter 'python3' in docs/installation.md:2", errors[0])

    def test_command_surface_skips_historical_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            historical = root / "docs" / "research" / "2026-09-07-note.md"
            historical.parent.mkdir(parents=True)
            historical.write_text("the survey counted python3 occurrences\n", encoding="utf-8")
            self.assertEqual([], check_command_surface([historical], root))

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

    @unittest.skipIf(
        os.name == "nt",
        "the release-workflow mock drives a POSIX sh gh shim; the workflow itself runs on ubuntu",
    )
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
            self.assertIn("treehouse max_trees must be an integer from 1 through 8", errors)
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


class WorkflowExitCodePolicyTest(unittest.TestCase):
    """A receipt pipeline must propagate the original exit code (F09)."""

    def test_no_run_block_swallows_failures_with_an_echo_tail(self) -> None:
        offenders = [
            f"{path.name}:{line_number}"
            for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if '|| echo "exit=' in line
        ]
        self.assertEqual([], offenders, "run steps must propagate failures instead of echoing past them")


class ChatPresentationTest(unittest.TestCase):
    def test_peel_chat_presentation_restores_protocol_core(self) -> None:
        decorated = "> 🦊 **阿舟 · Azhou Info 启动**（mode=info, scope=checkout）"
        core = "🦊 阿舟 · Azhou Info 启动（mode=info, scope=checkout）"
        self.assertEqual(core, peel_chat_presentation(decorated))

    def test_peel_chat_presentation_rejects_unpaired_bold(self) -> None:
        line = "> 🧠 **From 阿舟 memory（page）— content"
        self.assertEqual(line, peel_chat_presentation(line))

    def test_chat_presentation_examples_pass_on_the_live_repo(self) -> None:
        self.assertEqual([], check_chat_presentation_examples(ROOT))

    def test_chat_presentation_examples_reject_a_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "docs" / "skill-standard.md"
            path.parent.mkdir(parents=True)
            path.write_text("# empty\n", encoding="utf-8")
            errors = check_chat_presentation_examples(root)
            self.assertIn("chat presentation marker missing: docs/skill-standard.md", errors)


if __name__ == "__main__":
    unittest.main()

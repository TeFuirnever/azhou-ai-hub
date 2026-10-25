#!/usr/bin/env python3
"""Synthetic tests for the bounded candidate import CLI; never use a real CODEX_HOME."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("import_codex_pet", HERE / "import-codex-pet.py")
IMPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORT)

# Reuse the existing synthetic atlas/run fixture helpers without inheriting its
# test class, so running this file does not execute the original 34 tests.
BASE_SPEC = importlib.util.spec_from_file_location("test_codex_pet_fixtures", HERE / "test-codex-pet.py")
BASE = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)
PET = IMPORT.PET


def tree_bytes(root):
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes())
        elif path.is_dir():
            result[relative] = ("directory",)
    return result


class CandidateImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BASE.PetSafetyTests.setUpClass()

    def setUp(self):
        self.fixture = BASE.PetSafetyTests("test_snapshot_is_frozen_and_deterministic")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.package()
        self.source = self.fixture.project
        self.target = self.fixture.root / "new-project"
        self.target.mkdir()
        for name in PET.INPUTS[2:]:
            source_path = self.source / name
            target_path = self.target / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(source_path.read_bytes())

    def cli(self, *args, code=0, env=None):
        command = [sys.executable, "-B", str(HERE / "import-codex-pet.py"),
                   "--from-project", str(self.source), "--project-root", str(self.target), *args]
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=45,
                                env=env or os.environ.copy())
        self.assertEqual(result.returncode, code, result.stderr + "\n" + result.stdout)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"CLI 没有返回 JSON：{result.stdout!r}; stderr={result.stderr!r}; {exc}")

    def assert_pet_error(self, function, code):
        with self.assertRaises(PET.PetError) as raised:
            function()
        self.assertEqual(raised.exception.code, code)
        return str(raised.exception)

    def test_default_plan_is_read_only(self):
        source_before = tree_bytes(self.source)
        target_before = tree_bytes(self.target)
        result = self.cli()
        self.assertEqual(result["status"], "candidate-import-plan")
        self.assertEqual(len(result["planId"]), 64)
        self.assertEqual(result["installed"], "unchanged")
        self.assertEqual(result["generation"], "not-performed")
        self.assertEqual(tree_bytes(self.source), source_before)
        self.assertEqual(tree_bytes(self.target), target_before)
        self.assertFalse((self.target / ".local").exists())
        self.assertEqual(IMPORT.PACKAGE_ROOT, HERE.parent)

    def test_success_preserves_source_qa_and_simulated_install(self):
        installed = self.fixture.install()
        self.assertEqual(installed["status"], "installed")
        source_package = PET.selected_package(self.source)
        source_before = tree_bytes(self.source)
        install_before = tree_bytes(self.fixture.codex)
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.fixture.codex)

        plan = self.cli(env=env)
        result = self.cli("--apply", "--plan-id", plan["planId"], env=env)
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["installed"], "unchanged")
        self.assertEqual(result["runtime"], PET.RUNTIME)
        self.assertEqual(result["generation"], "not-performed")
        self.assertEqual(tree_bytes(self.source), source_before)
        self.assertEqual(tree_bytes(self.fixture.codex), install_before)

        imported = PET.selected_package(self.target)
        facts, receipt = PET.check_package(imported, self.target, require_current=True)
        self.assertEqual(facts["atlasSHA256"], plan["source"]["atlasSHA256"])
        self.assertEqual(receipt["projectRoot"], str(self.target))
        self.assertEqual((imported / "spritesheet.webp").read_bytes(),
                         (source_package / "spritesheet.webp").read_bytes())
        for name in PET.QA_FILES:
            self.assertEqual((imported / name).read_bytes(), (source_package / name).read_bytes())
        for name in PET.INPUTS[:2]:
            self.assertEqual((self.target / name).read_bytes(), (self.source / name).read_bytes())

    def test_unreviewed_qa_is_rejected(self):
        package = PET.selected_package(self.source)
        qa_path = package / "qa/visual-qa.json"
        qa = json.loads(qa_path.read_bytes())
        qa["pass"] = False
        qa_path.write_text(json.dumps(qa))
        receipt_path = package / "package-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["qaSHA256"]["qa/visual-qa.json"] = PET.sha(qa_path.read_bytes())
        receipt_path.write_bytes(PET.json_bytes(receipt))

        target_before = tree_bytes(self.target)
        result = self.cli(code=2)
        self.assertEqual(result["status"], "invalid")
        self.assertIn("视觉审阅未通过", result["error"])
        self.assertEqual(tree_bytes(self.target), target_before)

    def test_captured_package_read_window_must_match_verified_receipt(self):
        package = PET.selected_package(self.source)
        visual_qa = package / "qa/visual-qa.json"
        original_read = PET.read
        reads = 0

        def inconsistent_capture(path):
            nonlocal reads
            data = original_read(path)
            if Path(path) == visual_qa:
                reads += 1
                if reads == 2:  # The captured package bytes, between two full checks.
                    return data + b" "
            return data

        with patch.object(PET, "read", side_effect=inconsistent_capture):
            self.assert_pet_error(lambda: IMPORT.source_evidence(self.source), "source-conflict")
        self.assertGreaterEqual(reads, 2)
        self.assertFalse((self.target / ".local").exists())

    def test_fixed_theme_mismatch_and_target_symlink_are_rejected(self):
        (self.target / "style.css").write_bytes(b"different theme")
        result = self.cli(code=2)
        self.assertEqual(result["status"], "target-conflict")
        self.assertFalse((self.target / ".local").exists())

        (self.target / "style.css").write_bytes((self.source / "style.css").read_bytes())
        private = self.target / "assets/private/working.png"
        private.parent.mkdir(parents=True)
        private.symlink_to(self.source / "assets/private/working.png")
        result = self.cli(code=2)
        self.assertEqual(result["status"], "unknown-target")
        self.assertTrue(private.is_symlink())
        self.assertFalse((self.target / ".local").exists())

        private.unlink()
        private.write_bytes(b"different private theme input")
        result = self.cli(code=2)
        self.assertEqual(result["status"], "unknown-target")
        self.assertIn("已有不同内容", result["error"])
        self.assertFalse((self.target / ".local").exists())

    def test_stale_source_and_target_plans_are_rejected(self):
        plan = self.cli()
        self.fixture.make_run(self.fixture.atlas_b)
        self.fixture.package()
        result = self.cli("--apply", "--plan-id", plan["planId"], code=3)
        self.assertEqual(result["status"], "stale-plan")
        self.assertFalse((self.target / ".local").exists())

        # A fresh plan is bound to target inputs and private-image pre-state.
        plan = self.cli()
        (self.target / "style.css").write_bytes(b"changed after plan")
        result = self.cli("--apply", "--plan-id", plan["planId"], code=3)
        self.assertEqual(result["status"], "stale-plan")
        self.assertFalse((self.target / ".local").exists())

        (self.target / "style.css").write_bytes((self.source / "style.css").read_bytes())
        plan = self.cli()
        private = self.target / PET.INPUTS[0]
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_bytes((self.source / PET.INPUTS[0]).read_bytes())
        result = self.cli("--apply", "--plan-id", plan["planId"], code=3)
        self.assertEqual(result["status"], "stale-plan")
        self.assertFalse((self.target / ".local").exists())

    def test_source_change_after_locked_plan_is_rejected_before_copy(self):
        plan = self.cli()
        package = PET.selected_package(self.source)
        real_source_evidence = IMPORT.source_evidence
        calls = 0

        def change_last_source_read(project):
            nonlocal calls
            calls += 1
            if calls == 4:
                qa_path = package / "qa/visual-qa.json"
                qa_path.write_bytes(qa_path.read_bytes() + b" ")
                receipt_path = package / "package-receipt.json"
                receipt = json.loads(receipt_path.read_bytes())
                receipt["qaSHA256"]["qa/visual-qa.json"] = PET.sha(qa_path.read_bytes())
                receipt_path.write_bytes(PET.json_bytes(receipt))
            return real_source_evidence(project)

        with patch.object(IMPORT, "source_evidence", side_effect=change_last_source_read):
            self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan["planId"]),
                                  "stale-plan")
        self.assertEqual(calls, 4)
        for name in PET.INPUTS[:2]:
            self.assertFalse((self.target / name).exists())

    def test_partial_private_write_uses_plan_bound_temp_and_resumes(self):
        _, plan_id, _, _ = IMPORT.build_plan(self.source, self.target)
        name = PET.INPUTS[0]
        final = self.target / name
        temporary = IMPORT.private_temp_path(self.target, name, plan_id)
        real_write = PET.write_new
        injected = False

        def partial_write(path, data):
            nonlocal injected
            if Path(path) == temporary and not injected:
                injected = True
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with Path(path).open("xb") as stream:
                    stream.write(data[:1])
                    stream.flush()
                raise OSError("injected short private-image write")
            return real_write(path, data)

        with patch.object(PET, "write_new", side_effect=partial_write):
            self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id),
                                  "import-incomplete")
        self.assertTrue(injected)
        self.assertFalse(final.exists())
        self.assertEqual(temporary.read_bytes(), (self.source / name).read_bytes()[:1])

        result = IMPORT.apply_import(self.source, self.target, plan_id)
        self.assertEqual(result["status"], "imported")
        self.assertEqual(final.read_bytes(), (self.source / name).read_bytes())
        self.assertFalse(temporary.exists())

    def test_private_publish_never_overwrites_a_raced_target(self):
        _, plan_id, _, _ = IMPORT.build_plan(self.source, self.target)
        name = PET.INPUTS[0]
        final = self.target / name
        raced_bytes = b"untrusted concurrent target"

        def race_at_publish(source, destination, *, follow_symlinks=True):
            Path(destination).write_bytes(raced_bytes)
            raise FileExistsError("target appeared before hard-link publish")

        with patch.object(IMPORT.os, "link", side_effect=race_at_publish):
            self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id),
                                  "unknown-target")
        self.assertEqual(final.read_bytes(), raced_bytes)

    def test_foreign_same_owner_journal_is_preserved(self):
        _, plan_id, _, _ = IMPORT.build_plan(self.source, self.target)
        with patch.object(PET, "package_run", side_effect=OSError("injected pack failure")):
            self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id),
                                  "import-incomplete")
        state = PET.state_dir(self.target)
        stage_name = ".stage-" + "a" * 32
        stage = state / stage_name
        stage.mkdir()
        sentinel = stage / "unrelated-manager-candidate"
        sentinel.write_text("preserve this foreign same-owner stage")
        journal = {"owner": PET.OWNER, "projectRoot": str(self.target), "petId": PET.PET_ID,
                   "stage": stage_name, "operationId": "f" * 64}
        PET.atomic_json(state / "package-journal.json", journal)

        self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id),
                              "recovery-required")
        self.assert_pet_error(lambda: PET.recover_package_stage(state, self.target, plan_id),
                              "recovery-required")
        self.assertEqual(sentinel.read_text(), "preserve this foreign same-owner stage")
        (state / "package-journal.json").unlink()
        PET.remove_tree(stage)

        matching_name = ".stage-" + "b" * 32
        matching_stage = state / matching_name
        matching_stage.mkdir()
        (matching_stage / "partial-package-file").write_text("owned by this plan")
        PET.atomic_json(state / "package-journal.json",
                        {"owner": PET.OWNER, "projectRoot": str(self.target), "petId": PET.PET_ID,
                         "stage": matching_name, "operationId": plan_id})

        resumed = IMPORT.apply_import(self.source, self.target, plan_id)
        self.assertEqual(resumed["status"], "imported")
        self.assertFalse(matching_stage.exists())

    def test_complete_import_requires_target_frozen_snapshot(self):
        _, plan_id, _, _ = IMPORT.build_plan(self.source, self.target)
        result = IMPORT.apply_import(self.source, self.target, plan_id)
        self.assertEqual(result["status"], "imported")
        state = PET.state_dir(self.target)
        receipt = json.loads((state / IMPORT.IMPORT_RECEIPT).read_bytes())
        snapshot = state / "snapshots" / receipt["plan"]["source"]["themeRevision"]
        shutil.rmtree(snapshot)
        self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id), "unknown-target")

    def test_unknown_same_name_target_state_and_overlapping_roots_fail_closed(self):
        state = PET.state_dir(self.target, create=True)
        (state / "selection.json").write_text("{}")
        result = self.cli(code=2)
        self.assertEqual(result["status"], "unknown-target")
        self.assertIn("未知同名状态", result["error"])

        nested = self.source / "nested-target"
        nested.mkdir()
        command = [sys.executable, "-B", str(HERE / "import-codex-pet.py"),
                   "--from-project", str(self.source), "--project-root", str(nested)]
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 2)
        self.assertIn("不能相同、包含或重叠", json.loads(result.stdout)["error"])
        self.assertFalse((nested / ".local").exists())

    def test_partial_failure_can_resume_with_same_plan_and_repeat_idempotently(self):
        plan, plan_id, _, _ = IMPORT.build_plan(self.source, self.target)
        with patch.object(PET, "package_run", side_effect=OSError("injected pack failure")):
            self.assert_pet_error(lambda: IMPORT.apply_import(self.source, self.target, plan_id),
                                  "import-incomplete")
        receipt_path = PET.state_dir(self.target) / IMPORT.IMPORT_RECEIPT
        receipt = json.loads(receipt_path.read_bytes())
        self.assertEqual(receipt["status"], "in-progress")
        self.assertEqual(receipt["planId"], plan_id)
        self.assertFalse((PET.state_dir(self.target) / "packages").exists())

        resumed = IMPORT.apply_import(self.source, self.target, plan_id)
        self.assertEqual(resumed["status"], "imported")
        target_after = tree_bytes(self.target)
        repeated = IMPORT.apply_import(self.source, self.target, plan_id)
        self.assertEqual(repeated["status"], "already-imported")
        self.assertEqual(tree_bytes(self.target), target_after)
        self.assertEqual(PET.selected_package(self.target).name, plan["target"]["packageName"])
        PET.check_package(PET.selected_package(self.target), self.target, require_current=True)


    def test_non_object_source_receipt_is_rejected_without_mutation(self):
        source_package = PET.selected_package(self.source)
        (source_package / "package-receipt.json").write_text("[]", encoding="utf-8")
        source_before = tree_bytes(self.source)
        target_before = tree_bytes(self.target)
        result = self.cli(code=2)
        self.assertEqual(result["status"], "unknown-target")
        self.assertEqual(tree_bytes(self.source), source_before)
        self.assertEqual(tree_bytes(self.target), target_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)

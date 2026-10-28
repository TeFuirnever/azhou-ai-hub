#!/usr/bin/env python3
"""Isolated safety/transaction tests; all images and QA are explicitly synthetic fixtures.

No real CODEX_HOME, host, project asset or installed pet is used.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("manage_codex_pet", HERE / "manage-codex-pet.py")
PET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PET)


def atlas_bytes(color=(200, 120, 70, 255), *, bad_unused=False, missing_used=False):
    image = Image.new("RGBA", (1536, 2288), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row, count in enumerate(PET.FRAME_COUNTS):
        for col in range(count):
            if missing_used and row == col == 0:
                continue
            x, y = col * 192 + 70, row * 208 + 70
            draw.rectangle((x, y, x + 35, y + 50), fill=color)
    image.paste(image.crop((0, 0, 192, 208)), (6 * 192, 0))
    if bad_unused:
        draw.point((7 * 192 + 10, 10), fill=color)
    stream = io.BytesIO()
    image.save(stream, "WEBP", lossless=True)
    return stream.getvalue()


class PetSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas_a = atlas_bytes()
        cls.atlas_b = atlas_bytes((70, 120, 200, 255))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="azhou-pet-test-")
        # macOS temp roots may use /var -> /private/var; mirror the CLI's
        # canonical project identity so receipt and rename assertions agree.
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.codex = self.root / "isolated-codex-home"
        for name in PET.INPUTS:
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "pet/theme.json":
                shutil.copyfile(HERE.parent / name, path)
            else:
                path.write_bytes(("synthetic-source:" + name).encode())
        self.run = self.root / "synthetic-run"
        self.snapshot = Path(PET.prepare(self.project)["snapshot"])
        self.rev = json.loads(self.snapshot.read_text())["themeRevision"]
        self.make_run(self.atlas_a)

    def tearDown(self):
        self.temp.cleanup()

    def make_run(self, image):
        (self.run / "final").mkdir(parents=True, exist_ok=True)
        (self.run / "qa").mkdir(exist_ok=True)
        (self.run / "final/spritesheet-extended.webp").write_bytes(image)
        data = {name: {"ok": True, "errors": []} for name in PET.QA_FILES}
        data["qa/direction-semantics.json"] = {"directions": [
            {"direction": str(n * 22.5), "pass": True, "expected": "synthetic", "observed": "synthetic",
             "reason": "fixture only, not a visual acceptance"} for n in range(16)]}
        data["qa/visual-qa.json"] = {"pass": True, "atlasSHA256": PET.sha(image),
                                     "themeRevision": self.rev, "reviewer": "synthetic test fixture"}
        for name, value in data.items():
            (self.run / name).write_text(json.dumps(value))

    def make_package_for(self, project, image, label):
        snapshot = Path(PET.prepare(project)["snapshot"])
        revision = json.loads(snapshot.read_text())["themeRevision"]
        run = self.root / label
        (run / "final").mkdir(parents=True)
        (run / "qa").mkdir()
        (run / "final/spritesheet-extended.webp").write_bytes(image)
        data = {name: {"ok": True, "errors": []} for name in PET.QA_FILES}
        data["qa/direction-semantics.json"] = {"directions": [
            {"direction": str(n * 22.5), "pass": True, "expected": "synthetic", "observed": "synthetic",
             "reason": "fixture only, not a visual acceptance"} for n in range(16)]}
        data["qa/visual-qa.json"] = {"pass": True, "atlasSHA256": PET.sha(image),
                                     "themeRevision": revision, "reviewer": "synthetic test fixture"}
        for name, value in data.items():
            (run / name).write_text(json.dumps(value))
        return PET.package_run(project, run, snapshot)

    def make_old_install(self, image=None):
        old_project = self.root / "previous-project"
        old_project.mkdir()
        for name in PET.INPUTS:
            destination = old_project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.project / name, destination)
        self.make_package_for(old_project, image or self.atlas_a, "previous-run")
        PET.install_package(old_project, self.codex)
        return old_project

    def change_qa(self, name, mutate):
        path = self.run / name
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))

    def package(self):
        return PET.package_run(self.project, self.run, self.snapshot)

    def install(self):
        self.package()
        return PET.install_package(self.project, self.codex)

    def expect_error(self, fn, code="invalid"):
        with self.assertRaises(PET.PetError) as raised:
            fn()
        self.assertEqual(raised.exception.code, code)
        return str(raised.exception)

    def test_snapshot_is_frozen_and_deterministic(self):
        again = PET.prepare(self.project)
        self.assertEqual(again["snapshot"], str(self.snapshot))
        frozen = self.snapshot.parent / "inputs/style.css"
        original = frozen.read_bytes()
        (self.project / "style.css").write_text("changed focus or theme")
        self.assertEqual(frozen.read_bytes(), original)
        self.expect_error(lambda: PET.validate_run(self.project, self.run, self.snapshot), "generation-required")

    def test_package_install_and_readback_do_not_claim_activation(self):
        before = {name: (self.project / name).read_bytes() for name in PET.INPUTS}
        result = self.install()
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["runtime"], "pending-refresh-selection")
        self.assertEqual({key: result["installed"][key] for key in
                          ("occupiedCells", "renderedCells", "animationCells", "lookDirectionCells",
                           "neutralCells", "unusedCells")},
                         {"occupiedCells": 74, "renderedCells": 73, "animationCells": 57,
                          "lookDirectionCells": 16, "neutralCells": 1, "unusedCells": 14})
        target = self.codex / "pets" / PET.PET_ID
        self.assertEqual(json.loads((target / "pet.json").read_text()),
                         PET.native_manifest(json.loads((self.project / "pet/theme.json").read_text())))
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)
        self.assertEqual(before, {name: (self.project / name).read_bytes() for name in PET.INPUTS})
        self.assertEqual(PET.install_package(self.project, self.codex)["status"], "already-installed")

    def test_png_valid_header_but_corrupt_body_is_rejected(self):
        stream = io.BytesIO()
        Image.new("RGBA", (1536, 2288)).save(stream, "PNG")
        broken = stream.getvalue()[:33]  # PNG signature + valid IHDR, no pixel stream.
        self.expect_error(lambda: PET.inspect_atlas(broken))

    def test_intermediate_nine_row_atlas_is_rejected(self):
        stream = io.BytesIO()
        Image.new("RGBA", (1536, 1872)).save(stream, "WEBP", lossless=True)
        self.expect_error(lambda: PET.inspect_atlas(stream.getvalue()))

    def test_nontransparent_unused_cell_is_rejected(self):
        self.expect_error(lambda: PET.inspect_atlas(atlas_bytes(bad_unused=True)))

    def test_blank_used_cell_is_rejected(self):
        self.expect_error(lambda: PET.inspect_atlas(atlas_bytes(missing_used=True)))

    def test_missing_toolchain_neutral_cell_is_rejected(self):
        image = Image.open(io.BytesIO(self.atlas_a)).convert("RGBA")
        image.paste((0, 0, 0, 0), (1152, 0, 1344, 208))
        stream = io.BytesIO()
        image.save(stream, "WEBP", lossless=True)
        self.expect_error(lambda: PET.inspect_atlas(stream.getvalue()))

    def test_refitted_neutral_cell_may_differ_from_idle00(self):
        image = Image.open(io.BytesIO(self.atlas_a)).convert("RGBA")
        image.putpixel((1152 + 70, 70), (201, 120, 70, 254))
        stream = io.BytesIO()
        image.save(stream, "WEBP", lossless=True)
        facts = PET.inspect_atlas(stream.getvalue())
        self.assertFalse(facts["neutralMatchesIdle00"])
        self.assertEqual(facts["occupiedCells"], 74)

    def test_neutral_mutation_after_visual_review_is_rejected(self):
        image = Image.open(io.BytesIO(self.atlas_a)).convert("RGBA")
        image.putpixel((1152 + 70, 70), (201, 120, 70, 254))
        stream = io.BytesIO()
        image.save(stream, "WEBP", lossless=True)
        changed = stream.getvalue()
        self.assertFalse(PET.inspect_atlas(changed)["neutralMatchesIdle00"])
        (self.run / "final/spritesheet-extended.webp").write_bytes(changed)
        error = self.expect_error(self.package)
        self.assertIn("atlasSHA256", error)

    def test_visual_qa_image_mismatch_is_rejected(self):
        self.change_qa("qa/visual-qa.json", lambda x: x.update(atlasSHA256="0" * 64))
        self.expect_error(self.package)

    def test_visual_qa_theme_mismatch_is_rejected(self):
        self.change_qa("qa/visual-qa.json", lambda x: x.update(themeRevision="0" * 64))
        self.expect_error(self.package)

    def test_positive_summary_cannot_hide_review_errors(self):
        self.change_qa("qa/review.json", lambda x: x.update(ok=True, errors=["wrong identity"]))
        self.expect_error(self.package)

    def test_direction_coverage_is_not_just_list_length(self):
        self.change_qa("qa/direction-semantics.json",
                       lambda x: x["directions"][1].update(direction=x["directions"][0]["direction"]))
        self.expect_error(self.package)

    def test_direction_unconfirmed_is_rejected(self):
        self.change_qa("qa/direction-blind-validation.json", lambda x: x.update(ok=True, unconfirmed=["left?"]))
        self.expect_error(self.package)

    def test_intermediate_warning_requires_explicit_review(self):
        def mark_warning(data):
            data["directions"][1].pop("pass")
            data["directions"][1]["verdict"] = "warning"
        self.change_qa("qa/direction-semantics.json", mark_warning)
        self.expect_error(self.package)
        self.change_qa("qa/visual-qa.json", lambda x: x.update(labeledLoopReviewed=True,
                       blindResolution={"decision": "accept", "severity": "minor"}))
        self.assertEqual(self.package()["status"], "packaged")

    def test_cardinal_warning_cannot_be_waived(self):
        def mark_warning(data):
            data["directions"][0].pop("pass")
            data["directions"][0]["verdict"] = "warning"
        self.change_qa("qa/direction-semantics.json", mark_warning)
        self.change_qa("qa/visual-qa.json", lambda x: x.update(labeledLoopReviewed=True,
                       blindResolution={"decision": "accept", "severity": "minor"}))
        self.expect_error(self.package)

    def test_fully_opaque_used_cell_is_rejected(self):
        image = Image.open(io.BytesIO(self.atlas_a)).convert("RGBA")
        ImageDraw.Draw(image).rectangle((0, 0, 191, 207), fill=(200, 120, 70, 255))
        stream = io.BytesIO()
        image.save(stream, "WEBP", lossless=True)
        self.expect_error(lambda: PET.inspect_atlas(stream.getvalue()))

    def test_unknown_same_name_target_is_untouched(self):
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        target.mkdir(parents=True)
        (target / "user-content.txt").write_text("keep me")
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "unknown-target")
        self.assertEqual((target / "user-content.txt").read_text(), "keep me")

    def test_handoff_rebinds_exact_old_install_and_retries_after_source_removal(self):
        previous_project = self.make_old_install()
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        old_facts = PET.installed_facts(target, previous_project)
        old_receipt = json.loads((target / ".azhou-pet-receipt.json").read_text())
        self.assertEqual(old_receipt["projectRoot"], str(previous_project))
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "unknown-target")
        self.assertEqual(json.loads((target / ".azhou-pet-receipt.json").read_text()), old_receipt)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = PET.main(["handoff", "--project-root", str(self.project),
                             "--previous-project-root", str(previous_project),
                             "--codex-home", str(self.codex)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "handed-off")
        new_receipt = json.loads((target / ".azhou-pet-receipt.json").read_text())
        self.assertEqual(new_receipt["projectRoot"], str(self.project))
        self.assertEqual(PET.installed_facts(target, self.project)["atlasSHA256"], old_facts["atlasSHA256"])
        self.assertFalse(PET.journal_path(target.parent).exists())
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.previous-*")))

        shutil.rmtree(previous_project)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = PET.main(["handoff", "--project-root", str(self.project),
                             "--previous-project-root", str(previous_project),
                             "--codex-home", str(self.codex)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "already-handed-off")
        self.assertEqual(PET.status(self.project, self.codex)["installed"]["status"], "verified")

    def test_handoff_rejects_different_hub_candidate_and_preserves_old_install(self):
        previous_project = self.make_old_install(self.atlas_a)
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        before = (target / "spritesheet.webp").read_bytes()
        self.expect_error(lambda: PET.handoff_package(self.project, previous_project, self.codex),
                          "source-conflict")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), before)
        self.assertEqual(PET.installed_facts(target, previous_project)["atlasSHA256"], PET.sha(self.atlas_a))
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_rechecks_hub_candidate_after_comparison_before_install(self):
        previous_project = self.make_old_install(self.atlas_a)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        receipt_before = (target / ".azhou-pet-receipt.json").read_bytes()
        atlas_before = (target / "spritesheet.webp").read_bytes()
        original_install = PET.install_package

        def replace_hub_selection_then_install(project, codex_home, **kwargs):
            self.make_run(self.atlas_b)
            self.package()
            return original_install(project, codex_home, **kwargs)

        with patch.object(PET, "install_package", side_effect=replace_hub_selection_then_install):
            self.expect_error(lambda: PET.handoff_package(self.project, previous_project, self.codex),
                              "source-conflict")
        self.assertEqual((target / ".azhou-pet-receipt.json").read_bytes(), receipt_before)
        self.assertEqual((target / "spritesheet.webp").read_bytes(), atlas_before)
        self.assertEqual(PET.installed_facts(target, previous_project)["atlasSHA256"], PET.sha(self.atlas_a))
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_rejects_modified_old_install_without_replacing_it(self):
        previous_project = self.make_old_install()
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        (target / "spritesheet.webp").write_bytes(self.atlas_b)
        self.expect_error(lambda: PET.handoff_package(self.project, previous_project, self.codex),
                          "unknown-target")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_b)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_requires_the_installed_receipt_to_name_the_exact_old_root(self):
        previous_project = self.make_old_install()
        other_project = self.root / "same-content-other-root"
        other_project.mkdir()
        for name in PET.INPUTS:
            destination = other_project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.project / name, destination)
        self.make_package_for(other_project, self.atlas_a, "other-root-run")
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        before = (target / ".azhou-pet-receipt.json").read_bytes()
        self.expect_error(lambda: PET.handoff_package(self.project, other_project, self.codex),
                          "unknown-target")
        self.assertEqual((target / ".azhou-pet-receipt.json").read_bytes(), before)
        self.assertEqual(PET.installed_facts(target, previous_project)["atlasSHA256"], PET.sha(self.atlas_a))
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_respects_old_project_lock_without_touching_target(self):
        previous_project = self.make_old_install()
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        receipt_before = (target / ".azhou-pet-receipt.json").read_bytes()
        with PET.lock(PET.state_dir(previous_project) / "project.lock"):
            self.expect_error(lambda: PET.handoff_package(self.project, previous_project, self.codex), "busy")
        self.assertEqual((target / ".azhou-pet-receipt.json").read_bytes(), receipt_before)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_rejects_symlink_alias_for_old_project(self):
        previous_project = self.make_old_install()
        self.package()
        alias = self.root / "previous-project-alias"
        alias.symlink_to(previous_project, target_is_directory=True)
        target = self.codex / "pets" / PET.PET_ID
        receipt_before = (target / ".azhou-pet-receipt.json").read_bytes()
        self.expect_error(lambda: PET.handoff_package(self.project, alias, self.codex), "unknown-target")
        self.assertEqual((target / ".azhou-pet-receipt.json").read_bytes(), receipt_before)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_handoff_recovery_restores_old_owner_after_swap_interruption(self):
        previous_project = self.make_old_install()
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        real = PET.os.rename

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated process exit during handoff")

        with patch.object(PET.os, "rename", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.handoff_package(self.project, previous_project, self.codex)
        self.assertTrue(PET.journal_path(target.parent).exists())
        self.assertEqual(PET.recover_install(target.parent, self.project), "restored-previous-installed-package")
        self.assertEqual(PET.installed_facts(target, previous_project)["atlasSHA256"], PET.sha(self.atlas_a))
        self.assertFalse(PET.journal_path(target.parent).exists())
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.stage-*")))
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.previous-*")))

    def test_handoff_commit_recovery_removes_old_owner_backup(self):
        previous_project = self.make_old_install()
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        real = PET.remove_tree

        def interrupted(path):
            if ".previous-" in str(path):
                raise SystemExit("simulated process exit during handoff cleanup")
            return real(path)

        with patch.object(PET, "remove_tree", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.handoff_package(self.project, previous_project, self.codex)
        self.assertEqual(json.loads((target / ".azhou-pet-receipt.json").read_text())["projectRoot"], str(self.project))
        self.assertTrue(PET.journal_path(target.parent).exists())
        self.assertEqual(PET.recover_install(target.parent, self.project), "completed-committed-install")
        self.assertEqual(PET.installed_facts(target, self.project)["atlasSHA256"], PET.sha(self.atlas_a))
        self.assertFalse(PET.journal_path(target.parent).exists())
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.previous-*")))

    def test_target_symlink_is_rejected(self):
        self.package()
        pets = self.codex / "pets"
        pets.mkdir(parents=True)
        outside = self.root / "unrelated"
        outside.mkdir()
        (pets / PET.PET_ID).symlink_to(outside, target_is_directory=True)
        self.expect_error(lambda: PET.install_package(self.project, self.codex))
        self.assertEqual(list(outside.iterdir()), [])

    def test_input_symlink_is_rejected(self):
        source = self.project / "style.css"
        source.unlink()
        source.symlink_to(self.snapshot.parent / "inputs/style.css")
        self.expect_error(lambda: PET.prepare(self.project))

    def test_package_manifest_path_escape_is_rejected(self):
        self.package()
        directory = PET.selected_package(self.project)
        path = directory / "pet.json"
        data = json.loads(path.read_text())
        data["spritesheetPath"] = "../escape.webp"
        path.write_text(json.dumps(data))
        receipt_path = directory / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["manifestSHA256"] = PET.sha(path.read_bytes())
        receipt_path.write_text(json.dumps(receipt))
        self.expect_error(lambda: PET.check_package(directory, self.project))

    def test_style_only_change_blocks_sync_and_preserves_old_install(self):
        self.install()
        target = self.codex / "pets" / PET.PET_ID / "spritesheet.webp"
        original = target.read_bytes()
        (self.project / "style.css").write_text("different theme, same artwork")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = PET.main(["sync", "--project-root", str(self.project), "--codex-home", str(self.codex)])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(stream.getvalue())["status"], "generation-required")
        self.assertEqual(target.read_bytes(), original)

    def fail_commit_once(self):
        real = PET.atomic_json
        failed = False

        def write(path, value):
            nonlocal failed
            if str(path).endswith(".transaction.json") and value.get("phase") == "committed" and not failed:
                failed = True
                raise OSError("injected disk failure at commit")
            return real(path, value)
        return patch.object(PET, "atomic_json", side_effect=write)

    def test_exception_after_swap_restores_previous_install(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        with self.fail_commit_once():
            message = self.expect_error(lambda: PET.install_package(self.project, self.codex), "install-failed")
        self.assertIn("restored-previous-installed-package", message)
        target = self.codex / "pets" / PET.PET_ID / "spritesheet.webp"
        self.assertEqual(target.read_bytes(), self.atlas_a)
        self.assertFalse(PET.journal_path(self.codex / "pets").exists())

    def test_exception_during_first_install_restores_absence(self):
        self.package()
        with self.fail_commit_once():
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "install-failed")
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())

    def test_interruption_after_swap_recovers_from_durable_journal(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        real = PET.os.rename
        target = self.codex / "pets" / PET.PET_ID

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated abrupt interruption")

        with patch.object(PET.os, "rename", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        self.assertTrue(PET.journal_path(self.codex / "pets").exists())
        self.assertEqual(PET.recover_install(self.codex / "pets", self.project),
                         "restored-previous-installed-package")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)

    def test_recover_does_not_require_the_old_theme_to_remain_current(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        real = PET.os.rename
        target = self.codex / "pets" / PET.PET_ID

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated process exit")

        with patch.object(PET.os, "rename", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        (self.project / "style.css").write_text("theme changed after interruption")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = PET.main(["recover", "--project-root", str(self.project), "--codex-home", str(self.codex)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["recovery"], "restored-previous-installed-package")
        self.assertEqual(result["states"]["installed"]["status"], "stale-theme")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)

    def test_committed_interruption_finishes_cleanup_without_false_rollback(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        real = PET.remove_tree

        def interrupted(path):
            if ".previous-" in str(path):
                raise SystemExit("simulated interruption during cleanup")
            return real(path)

        with patch.object(PET, "remove_tree", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        self.assertEqual(PET.recover_install(self.codex / "pets", self.project), "completed-committed-install")
        self.assertEqual((self.codex / "pets" / PET.PET_ID / "spritesheet.webp").read_bytes(), self.atlas_b)

    def test_same_theme_different_selected_atlas_is_reported_as_stale_package(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        result = PET.status(self.project, self.codex)
        self.assertEqual(result["installed"]["status"], "stale-package")
        self.assertTrue(result["installed"]["matchesCurrentTheme"])
        self.assertFalse(result["installed"]["matchesSelectedPackage"])

    def test_target_lock_blocks_concurrent_install_without_modification(self):
        self.package()
        pets = self.codex / "pets"
        pets.mkdir(parents=True)
        with PET.lock(pets / f".{PET.PET_ID}.lock"):
            result = subprocess.run([sys.executable, "-B", str(HERE / "manage-codex-pet.py"), "install",
                                     "--project-root", str(self.project), "--codex-home", str(self.codex)],
                                    text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(json.loads(result.stdout)["status"], "busy")
        self.assertFalse((pets / PET.PET_ID).exists())
        self.assertFalse(PET.journal_path(pets).exists())

    def test_transaction_copies_never_enter_the_native_pet_scan(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        real = PET.os.rename
        observations = []

        def inspect_scan():
            discovered = sorted(p.name for p in pets.iterdir()
                                if (p.is_dir() or p.is_symlink()) and (p / "pet.json").exists())
            self.assertTrue(set(discovered).issubset({PET.PET_ID}), discovered)
            observations.append(discovered)

        def intercepted(source, destination):
            source, destination = Path(source), Path(destination)
            if source == target or destination == target:
                inspect_scan()
                transient = destination if source == target else source
                self.assertEqual(transient.parent, self.codex)
            real(source, destination)
            if source == target or destination == target:
                inspect_scan()

        with patch.object(PET.os, "rename", side_effect=intercepted):
            result = PET.install_package(self.project, self.codex)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(observations, [[PET.PET_ID], [], [], [PET.PET_ID]])
        self.assertEqual([p.name for p in pets.iterdir() if p.is_dir()], [PET.PET_ID])
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.stage-*")))
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.previous-*")))

    def test_project_lock_blocks_concurrent_cli(self):
        state = PET.state_dir(self.project)
        with PET.lock(state / "project.lock"):
            result = subprocess.run([sys.executable, "-B", str(HERE / "manage-codex-pet.py"), "prepare",
                                     "--project-root", str(self.project), "--codex-home", str(self.codex)],
                                    text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(json.loads(result.stdout)["status"], "busy")

    def test_installed_bytes_changed_outside_receipt_are_not_overwritten(self):
        self.install()
        target = self.codex / "pets" / PET.PET_ID / "spritesheet.webp"
        target.write_bytes(self.atlas_b)
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "unknown-target")
        self.assertEqual(target.read_bytes(), self.atlas_b)

    def test_status_is_read_only(self):
        shutil.rmtree(self.project / ".local")
        result = PET.status(self.project, self.codex)
        self.assertEqual(result["installed"]["status"], "absent")
        self.assertEqual(result["runtime"], "pending-refresh-selection")
        self.assertFalse((self.project / ".local").exists())
        self.assertFalse(self.codex.exists())

    def test_python_cli_main_routes_prepare_validate_status_and_generation_error(self):
        def invoke(*args):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = PET.main(["--project-root", str(self.project), "--codex-home", str(self.codex), *args])
            return code, json.loads(output.getvalue())

        code, prepared = invoke("prepare")
        self.assertEqual(code, 0)
        self.assertEqual(prepared["status"], "generation-required")

        code, validated = invoke("validate", "--run", str(self.run), "--snapshot", str(self.snapshot))
        self.assertEqual(code, 0)
        self.assertEqual(validated["status"], "validated")

        code, current = invoke("status")
        self.assertEqual(code, 0)
        self.assertEqual(current["status"], "status")
        self.assertEqual(current["installed"]["status"], "absent")

        code, unavailable = invoke("sync")
        self.assertEqual(code, 3)
        self.assertEqual(unavailable["status"], "generation-required")
        self.assertIn("next", unavailable)

        code, invalid_args = invoke("status", "--run", str(self.run))
        self.assertEqual(code, 2)
        self.assertIn("--run 与 --snapshot 必须同时提供", invalid_args["error"])

        self.package()
        code, selected = invoke("validate")
        self.assertEqual(code, 0)
        self.assertEqual(selected["status"], "validated")
        code, packaged = invoke("package", "--run", str(self.run), "--snapshot", str(self.snapshot))
        self.assertEqual(code, 0)
        self.assertEqual(packaged["status"], "packaged")
        with patch.object(PET, "install_package", return_value={"status": "mock-installed"}):
            code, synced = invoke("sync", "--run", str(self.run), "--snapshot", str(self.snapshot))
        self.assertEqual(code, 0)
        self.assertEqual(synced["status"], "mock-installed")

        stdout = io.StringIO()
        with patch.object(sys, "argv", [str(HERE / "manage-codex-pet.py"), "status",
                                         "--project-root", str(self.project), "--codex-home", str(self.codex)]), \
                contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_code:
            runpy.run_path(str(HERE / "manage-codex-pet.py"), run_name="__main__")
        self.assertEqual(exit_code.exception.code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "status")

        real_codex = self.root / "real-codex-home"
        real_codex.mkdir()
        codex_link = self.root / "codex-home-link"
        codex_link.symlink_to(real_codex, target_is_directory=True)
        code, link_error = invoke("status", "--codex-home", str(codex_link))
        self.assertEqual(code, 2)
        self.assertEqual(link_error["states"]["status"], "unverified")

    def test_validation_qa_accepts_mapping_shape_and_rejects_unparseable_direction_or_warning(self):
        raw = {name: (self.run / name).read_bytes() for name in PET.QA_FILES}
        semantics = json.loads(raw[PET.QA_FILES[3]])
        semantics["directions"] = {
            item["direction"]: {"pass": item["pass"]} for item in semantics["directions"]
        }
        raw[PET.QA_FILES[3]] = PET.json_bytes(semantics)
        result = PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)
        self.assertEqual(set(result), set(PET.QA_FILES))

        first_angle = next(iter(semantics["directions"]))
        semantics["directions"]["north"] = semantics["directions"].pop(first_angle)
        bad_angle = dict(raw)
        bad_angle[PET.QA_FILES[3]] = PET.json_bytes(semantics)
        with self.assertRaisesRegex(PET.PetError, "方向必须"):
            PET.validate_qa(bad_angle, PET.sha(self.atlas_a), self.rev)

        blind = json.loads(raw[PET.QA_FILES[4]])
        blind["warnings"] = ["unreviewed blind warning"]
        raw[PET.QA_FILES[4]] = PET.json_bytes(blind)
        with self.assertRaisesRegex(PET.PetError, "盲测 warning"):
            PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)
        self.assertFalse(PET.passed({"status": "failed"}))

    def test_status_reports_invalid_source_transaction_and_installed_receipt(self):
        pets = self.codex / "pets"
        pets.mkdir(parents=True)
        transaction = PET.journal_path(pets)
        PET.atomic_json(transaction, {"fixture": "not an install claim"})
        result = PET.status(self.project, self.codex)
        self.assertEqual(result["transaction"]["status"], "recovery-required")

        target = pets / PET.PET_ID
        target.mkdir()
        result = PET.status(self.project, self.codex)
        self.assertIn(result["installed"]["status"], ("invalid", "unknown-target"))

        theme = self.project / "pet/theme.json"
        valid = theme.read_bytes()
        theme.write_text("{")
        try:
            result = PET.status(self.project, self.codex)
            self.assertEqual(result["source"]["status"], "invalid")
        finally:
            theme.write_bytes(valid)

    def test_recovery_without_backup_accepts_only_exact_previous_owner_and_keeps_missing_target_pending(self):
        old_project = self.make_old_install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        old = PET.installed_facts(target, old_project)
        tx = "c" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        journal = {
            "owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
            "previousProjectRoot": str(old_project), "transaction": tx,
            "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": True,
            "candidateAtlasSHA256": PET.sha(self.atlas_b), "candidateThemeRevision": self.rev,
            "previousAtlasSHA256": old["atlasSHA256"], "previousThemeRevision": old["themeRevision"],
            "previousManifestSHA256": old["manifestSHA256"],
        }
        journal_file = PET.journal_path(pets)
        PET.atomic_json(journal_file, journal)
        self.assertEqual(PET.recover_install(pets, self.project), "restored-pre-install-state")
        self.assertTrue(target.is_dir())
        self.assertFalse(stage.exists())
        self.assertFalse(journal_file.exists())

        PET.remove_tree(target)
        PET.atomic_json(journal_file, journal)
        with self.assertRaisesRegex(PET.PetError, "正式目标与旧包均缺失"):
            PET.recover_install(pets, self.project)
        self.assertTrue(journal_file.exists())

    def test_json_parser_cleanup_and_package_history_are_deterministic(self):
        with self.assertRaisesRegex(PET.PetError, "JSON 无效"):
            PET.parse(b"\xff")

        with tempfile.TemporaryDirectory(prefix="agent-skin-pet-atomic-json-") as temporary:
            path = Path(temporary) / "receipt.json"
            with patch.object(PET.os, "replace", side_effect=OSError("injected replace failure")):
                with self.assertRaisesRegex(OSError, "injected replace failure"):
                    PET.atomic_json(path, {"status": "fixture"})
            self.assertFalse(list(Path(temporary).glob("*.tmp")))
            self.assertFalse(path.exists())

        first = PET.selected_package(self.project) if (self.project / ".local/pets" / PET.PET_ID / "selection.json").exists() else None
        self.assertIsNone(first)
        self.package()
        state = PET.state_dir(self.project)
        first_package = PET.selected_package(self.project)
        self.make_run(self.atlas_b)
        self.package()
        self.make_run(atlas_bytes((90, 180, 50, 255)))
        self.package()
        self.assertFalse(first_package.exists())
        self.assertTrue(PET.selected_package(self.project).is_dir())

    def test_snapshot_staging_interruption_can_be_retried(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "a" * 32)
        stage.mkdir()
        (stage / "partial.txt").write_text("partial frozen input")
        PET.atomic_json(state / "package-journal.json", {"owner": PET.OWNER, "petId": PET.PET_ID,
                        "projectRoot": str(self.project), "stage": stage.name})
        self.assertEqual(PET.prepare(self.project)["themeRevision"], self.rev)
        self.assertFalse(stage.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

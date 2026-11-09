#!/usr/bin/env python3
"""Isolated safety/transaction tests; all images and QA are explicitly synthetic fixtures.

No real CODEX_HOME, host, project asset or installed pet is used.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
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

    def make_run(self, image, *, directory=None, revision=None):
        directory = directory or self.run
        revision = revision or self.rev
        (directory / "final").mkdir(parents=True, exist_ok=True)
        (directory / "qa").mkdir(exist_ok=True)
        (directory / "final/spritesheet-extended.webp").write_bytes(image)
        data = {name: {"ok": True, "errors": []} for name in PET.QA_FILES}
        data["qa/direction-semantics.json"] = {"directions": [
            {"direction": str(n * 22.5), "pass": True, "expected": "synthetic", "observed": "synthetic",
             "reason": "fixture only, not a visual acceptance"} for n in range(16)]}
        data["qa/visual-qa.json"] = {"pass": True, "atlasSHA256": PET.sha(image),
                                     "themeRevision": revision, "reviewer": "synthetic test fixture"}
        for name, value in data.items():
            (directory / name).write_text(json.dumps(value))

    def make_package_for(self, project, image, label):
        snapshot = Path(PET.prepare(project)["snapshot"])
        revision = json.loads(snapshot.read_text())["themeRevision"]
        run = self.root / label
        (run / "final").mkdir(parents=True)
        (run / "qa").mkdir()
        self.make_run(image, directory=run, revision=revision)
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

    def assert_changed_identity_after_publication_is_preserved(self, *, upgrade, field="manifest"):
        if upgrade:
            self.install()
            old_target = self.codex / "pets" / PET.PET_ID
            old_manifest = (old_target / "pet.json").read_bytes()
            old_atlas = (old_target / "spritesheet.webp").read_bytes()
            self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        rename = PET.rename_exclusive
        injected, original_published = [], {}
        def modify_after_publish(source, destination):
            result = rename(source, destination)
            if Path(destination) == target and ".stage-" in Path(source).name:
                manifest = target / "pet.json"
                original_published["manifest"] = manifest.read_bytes()
                original_published["receipt"] = (target / ".azhou-pet-receipt.json").read_bytes()
                receipt = target / ".azhou-pet-receipt.json"
                data = json.loads(original_published["receipt"])
                if field == "manifest":
                    metadata = json.loads(original_published["manifest"])
                    metadata["description"] = "foreign description after publication"
                    manifest.write_text(json.dumps(metadata))
                    data["manifestSHA256"] = PET.sha(manifest.read_bytes())
                else:
                    data["themeRevision"] = "a" * 64 if data["themeRevision"] != "a" * 64 else "b" * 64
                receipt.write_text(json.dumps(data))
                injected.append(True)
            return result
        with patch.object(PET, "rename_exclusive", side_effect=modify_after_publish):
            with self.assertRaises(PET.PetError) as raised:
                PET.install_package(self.project, self.codex)
        self.assertEqual(raised.exception.code, "recovery-required")
        self.assertEqual(injected, [True])
        if field == "manifest":
            self.assertEqual(json.loads((target / "pet.json").read_bytes())["description"],
                             "foreign description after publication")
        else:
            self.assertNotEqual(json.loads((target / ".azhou-pet-receipt.json").read_bytes())["themeRevision"],
                                json.loads(original_published["receipt"])["themeRevision"])
        journal = PET.journal_path(self.codex / "pets")
        self.assertTrue(journal.is_file())
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "prepared")
        backups = list(self.codex.glob(f".{PET.PET_ID}.previous-*"))
        self.assertEqual(len(backups), 1 if upgrade else 0)
        if upgrade:
            self.assertEqual((backups[0] / "pet.json").read_bytes(), old_manifest)
            self.assertEqual((backups[0] / "spritesheet.webp").read_bytes(), old_atlas)
        # Simulate a reviewer restoring the exact captured transaction bytes.
        (target / "pet.json").write_bytes(original_published["manifest"])
        (target / ".azhou-pet-receipt.json").write_bytes(original_published["receipt"])
        outcome = PET.recover_install(self.codex / "pets", self.project)
        self.assertEqual(outcome, "restored-previous-installed-package" if upgrade else "restored-pre-install-state")
        if upgrade:
            self.assertEqual((target / "pet.json").read_bytes(), old_manifest)
            self.assertEqual((target / "spritesheet.webp").read_bytes(), old_atlas)
        else:
            self.assertFalse(target.exists())
        self.assertFalse(journal.exists())

    def test_first_install_preserves_manifest_changed_after_publish(self):
        self.assert_changed_identity_after_publication_is_preserved(upgrade=False)

    def test_upgrade_preserves_manifest_changed_after_publish_and_old_backup(self):
        self.assert_changed_identity_after_publication_is_preserved(upgrade=True)

    def test_first_install_preserves_theme_receipt_changed_after_publish(self):
        self.assert_changed_identity_after_publication_is_preserved(upgrade=False, field="theme")

    def test_upgrade_preserves_theme_receipt_changed_after_publish_and_old_backup(self):
        self.assert_changed_identity_after_publication_is_preserved(upgrade=True, field="theme")

    def test_snapshot_metadata_requires_the_known_integer_schema(self):
        valid = json.loads(self.snapshot.read_bytes())
        self.assertEqual(PET.snapshot_metadata(valid), self.rev)
        for label, value in (("missing", None), ("boolean", True), ("text", "1"),
                             ("float", 1.0), ("zero", 0), ("future", 2)):
            with self.subTest(label=label):
                changed = dict(valid)
                if label == "missing": changed.pop("schemaVersion")
                else: changed["schemaVersion"] = value
                with self.assertRaises(PET.PetError): PET.snapshot_metadata(changed)

    def test_prepare_preserves_unknown_snapshot_schema(self):
        original = json.loads(self.snapshot.read_bytes())
        original["schemaVersion"] = 2
        data = PET.json_bytes(original)
        self.snapshot.write_bytes(data)
        self.expect_error(lambda: PET.prepare(self.project))
        self.assertEqual(self.snapshot.read_bytes(), data)
        self.assertFalse((PET.state_dir(self.project) / "selection.json").exists())

    def test_package_rejects_unknown_snapshot_schema_without_selection(self):
        original = json.loads(self.snapshot.read_bytes())
        original["schemaVersion"] = True
        data = PET.json_bytes(original)
        self.snapshot.write_bytes(data)
        self.expect_error(lambda: PET.package_run(self.project, self.run, self.snapshot))
        self.assertEqual(self.snapshot.read_bytes(), data)
        self.assertFalse((PET.state_dir(self.project) / "selection.json").exists())

    def test_selected_package_with_unknown_snapshot_schema_is_not_verified(self):
        self.package()
        directory = PET.selected_package(self.project)
        snapshot_path = directory / "theme-snapshot.json"
        snapshot = json.loads(snapshot_path.read_bytes())
        snapshot["schemaVersion"] = 2
        data = PET.json_bytes(snapshot)
        snapshot_path.write_bytes(data)
        receipt_path = directory / "package-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["snapshotSHA256"] = PET.sha(data)
        receipt_data = PET.json_bytes(receipt)
        receipt_path.write_bytes(receipt_data)
        self.assertEqual(PET.status(self.project, self.codex)["package"]["status"], "invalid")
        self.assertEqual(snapshot_path.read_bytes(), data)
        self.assertEqual(receipt_path.read_bytes(), receipt_data)
        self.assertTrue((directory / "spritesheet.webp").is_file())

    def test_package_refuses_reusing_a_different_visual_review(self):
        self.package()
        directory = PET.selected_package(self.project)
        selection = PET.state_dir(self.project) / "selection.json"
        before_selection = selection.read_bytes()
        old_qa = (directory / "qa/visual-qa.json").read_bytes()
        old_receipt = (directory / "package-receipt.json").read_bytes()
        current_qa = self.run / "qa/visual-qa.json"
        changed = json.loads(current_qa.read_bytes())
        changed["reviewer"] = "different synthetic review"
        current_qa.write_text(json.dumps(changed))
        new_qa = current_qa.read_bytes()
        self.expect_error(lambda: PET.package_run(self.project, self.run, self.snapshot), "source-conflict")
        self.assertEqual(selection.read_bytes(), before_selection)
        self.assertEqual((directory / "qa/visual-qa.json").read_bytes(), old_qa)
        self.assertEqual((directory / "package-receipt.json").read_bytes(), old_receipt)
        self.assertEqual(current_qa.read_bytes(), new_qa)

    def test_package_refuses_reusing_differently_serialized_snapshot(self):
        self.package()
        directory = PET.selected_package(self.project)
        selection = PET.state_dir(self.project) / "selection.json"
        before_selection = selection.read_bytes()
        old_snapshot = (directory / "theme-snapshot.json").read_bytes()
        old_receipt = (directory / "package-receipt.json").read_bytes()
        self.snapshot.write_text(json.dumps(json.loads(self.snapshot.read_bytes()), indent=2, ensure_ascii=False))
        changed_snapshot = self.snapshot.read_bytes()
        self.assertNotEqual(changed_snapshot, old_snapshot)
        self.expect_error(lambda: PET.package_run(self.project, self.run, self.snapshot), "source-conflict")
        self.assertEqual(selection.read_bytes(), before_selection)
        self.assertEqual((directory / "theme-snapshot.json").read_bytes(), old_snapshot)
        self.assertEqual((directory / "package-receipt.json").read_bytes(), old_receipt)
        self.assertEqual(self.snapshot.read_bytes(), changed_snapshot)

    def test_package_reuses_exactly_matching_review_evidence(self):
        first = self.package()
        directory = PET.selected_package(self.project)
        selection = PET.state_dir(self.project) / "selection.json"
        evidence = {name: (directory / name).read_bytes() for name in (*PET.QA_FILES, "theme-snapshot.json", "package-receipt.json")}
        selected = selection.read_bytes()
        second = self.package()
        self.assertEqual(first["package"]["path"], second["package"]["path"])
        self.assertEqual(selection.read_bytes(), selected)
        self.assertEqual({name: (directory / name).read_bytes() for name in evidence}, evidence)

    def replace_selected_with_identical_copy(self):
        self.package()
        selected = PET.selected_package(self.project)
        saved = self.root / "saved-original-selected"
        selected.rename(saved)
        shutil.copytree(saved, selected)
        self.assertNotEqual(saved.stat().st_ino, selected.stat().st_ino)
        return selected, saved

    def test_copied_selected_candidate_is_not_verified_or_installed(self):
        selected, saved = self.replace_selected_with_identical_copy()
        selection = PET.state_dir(self.project) / "selection.json"
        before = selection.read_bytes()
        copied_receipt = (selected / "package-receipt.json").read_bytes()
        original_receipt = (saved / "package-receipt.json").read_bytes()
        self.assertEqual(PET.status(self.project, self.codex)["package"]["status"], "source-conflict")
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "source-conflict")
        self.assertFalse(self.codex.exists())
        self.assertEqual(selection.read_bytes(), before)
        self.assertEqual((selected / "package-receipt.json").read_bytes(), copied_receipt)
        self.assertEqual((saved / "package-receipt.json").read_bytes(), original_receipt)

    def test_install_refuses_copied_selected_candidate_before_creating_home(self):
        selected, saved = self.replace_selected_with_identical_copy()
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "source-conflict")
        self.assertFalse(self.codex.exists())
        self.assertTrue(selected.is_dir())
        self.assertTrue(saved.is_dir())

    def test_copied_selected_candidate_is_not_adopted_by_package(self):
        selected, saved = self.replace_selected_with_identical_copy()
        selection = PET.state_dir(self.project) / "selection.json"
        before = selection.read_bytes()
        copied = (selected / "package-receipt.json").read_bytes()
        self.expect_error(self.package, "source-conflict")
        self.assertEqual(selection.read_bytes(), before)
        self.assertEqual((selected / "package-receipt.json").read_bytes(), copied)
        self.assertEqual((saved / "package-receipt.json").read_bytes(), copied)

    def test_selected_candidate_with_malformed_recorded_identity_is_not_reused(self):
        self.package()
        selected = PET.selected_package(self.project)
        receipt_path = selected / "package-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        selection = PET.state_dir(self.project) / "selection.json"
        before_selection = selection.read_bytes()
        for value in (None, {}, {"device": True, "inode": selected.stat().st_ino}):
            with self.subTest(identity=value):
                changed = dict(receipt, directoryIdentity=value)
                data = PET.json_bytes(changed)
                receipt_path.write_bytes(data)
                self.expect_error(lambda: PET.verified_selected_package(self.project), "source-conflict")
                self.expect_error(self.package, "source-conflict")
                self.assertEqual(receipt_path.read_bytes(), data)
                self.assertEqual(selection.read_bytes(), before_selection)

    def test_installed_manifest_non_object_is_reported_and_preserved(self):
        self.install()
        target = self.codex / 'pets' / PET.PET_ID
        path = target / 'pet.json'
        receipt_path = target / '.azhou-pet-receipt.json'
        original = json.loads(receipt_path.read_bytes())
        for value in (None, [], [{}], 'manifest', 7):
            with self.subTest(value=value):
                data = PET.json_bytes(value)
                path.write_bytes(data)
                receipt = dict(original, manifestSHA256=PET.sha(data))
                receipt_path.write_bytes(PET.json_bytes(receipt))
                before = {p.name: p.read_bytes() for p in target.iterdir()}
                self.assertEqual(PET.status(self.project, self.codex)['installed']['status'], 'unknown-target')
                self.expect_error(lambda: PET.install_package(self.project, self.codex), 'unknown-target')
                self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
                self.assertFalse(PET.journal_path(self.codex / 'pets').exists())

    def test_selected_manifest_non_object_is_reported_and_preserved(self):
        self.package()
        selected = PET.selected_package(self.project)
        path = selected / 'pet.json'
        receipt_path = selected / 'package-receipt.json'
        original = json.loads(receipt_path.read_bytes())
        selection = PET.state_dir(self.project) / 'selection.json'
        selection_before = selection.read_bytes()
        for value in (None, [], [{}], 'manifest', 7):
            with self.subTest(value=value):
                data = PET.json_bytes(value)
                path.write_bytes(data)
                receipt = dict(original, manifestSHA256=PET.sha(data))
                receipt_path.write_bytes(PET.json_bytes(receipt))
                self.assertEqual(PET.status(self.project, self.codex)['package']['status'], 'invalid')
                self.expect_error(lambda: PET.verified_selected_package(self.project))
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(selection.read_bytes(), selection_before)
                self.assertFalse(self.codex.exists())

    def test_installed_receipt_requires_a_valid_theme_digest(self):
        self.install()
        target = self.codex / "pets" / PET.PET_ID
        receipt_path = target / ".azhou-pet-receipt.json"
        original = json.loads(receipt_path.read_bytes())
        for label, value in (("missing", None), ("boolean", True), ("empty", ""),
                             ("nonhex", "z" * 64), ("uppercase", "A" * 64)):
            with self.subTest(label=label):
                receipt = dict(original)
                if label == "missing": receipt.pop("themeRevision")
                else: receipt["themeRevision"] = value
                data = PET.json_bytes(receipt)
                receipt_path.write_bytes(data)
                self.expect_error(lambda: PET.installed_facts(target, self.project), "unknown-target")
                self.assertEqual(PET.status(self.project, self.codex)["installed"]["status"], "unknown-target")
                self.assertEqual(receipt_path.read_bytes(), data)
        receipt_path.write_bytes(PET.json_bytes(original))
        self.assertEqual(PET.installed_facts(target, self.project)["themeRevision"], self.rev)

    def test_upgrade_preserves_target_with_invalid_receipt_before_transaction(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        receipt_path = target / ".azhou-pet-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["themeRevision"] = "not-a-digest"
        receipt_path.write_bytes(PET.json_bytes(receipt))
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        with self.assertRaises(PET.PetError) as raised:
            PET.install_package(self.project, self.codex)
        backups = list(self.codex.glob(f".{PET.PET_ID}.previous-*"))
        journal = PET.journal_path(self.codex / "pets")
        self.assertEqual(raised.exception.code, "unknown-target",
                         f"target={target.exists()}, backups={len(backups)}, journal={journal.exists()}")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)
        self.assertFalse(journal.exists())
        self.assertFalse(backups)
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.stage-*")))

    def test_read_rejects_in_place_mutation_with_restored_mtime(self):
        path = self.root / 'synthetic-changing-input'
        original = b'a' * (1024 * 1024 + 32)
        replacement = b'b' * len(original)
        path.write_bytes(original)
        before = path.stat()
        original_read = os.read
        changed = []
        def mutate_after_first_chunk(fd, count):
            data = original_read(fd, count)
            if data and not changed:
                path.write_bytes(replacement)
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                changed.append(path.stat())
            return data
        with patch.object(PET.os, 'read', side_effect=mutate_after_first_chunk):
            self.expect_error(lambda: PET.read(path), 'source-conflict')
        self.assertEqual(len(changed), 1)
        after = changed[0]
        self.assertEqual((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
                         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns))
        self.assertNotEqual(before.st_ctime_ns, after.st_ctime_ns)
        self.assertEqual(path.read_bytes(), replacement)

    def test_read_regular_files_and_size_limit(self):
        path = self.root / "bounded-input"
        with patch.object(PET, "MAX_FILE_BYTES", 32):
            for data in (b"", b"valid", b"x" * 32):
                path.write_bytes(data)
                self.assertEqual(PET.read(path), data)
            path.write_bytes(b"x" * 33)
            self.expect_error(lambda: PET.read(path))
            self.assertEqual(path.read_bytes(), b"x" * 33)

    def test_read_rejects_symlink_and_fifo_without_modification(self):
        source = self.root / "source"
        source.write_bytes(b"source")
        link = self.root / "source-link"
        link.symlink_to(source)
        fifo = self.root / "unrelated-fifo"
        os.mkfifo(fifo)
        self.expect_error(lambda: PET.read(link))
        self.expect_error(lambda: PET.read(fifo))
        self.assertTrue(link.is_symlink())
        self.assertTrue(fifo.exists())
        self.assertEqual(source.read_bytes(), b"source")

    def test_read_detects_replacement_before_open(self):
        path = self.root / "changing-input"
        original = self.root / "original-input"
        path.write_bytes(b"original")
        open_file = PET.os.open
        def replace_then_open(name, flags):
            path.rename(original)
            path.write_bytes(b"foreign")
            return open_file(name, flags)
        with patch.object(PET.os, "open", side_effect=replace_then_open):
            self.expect_error(lambda: PET.read(path), "source-conflict")
        self.assertEqual(original.read_bytes(), b"original")
        self.assertEqual(path.read_bytes(), b"foreign")

    def test_read_detects_replacement_after_open(self):
        path = self.root / "changing-input"
        original = self.root / "original-input"
        path.write_bytes(b"original")
        read_file = PET.os.read
        changed = False
        def replace_while_reading(fd, count):
            nonlocal changed
            if not changed:
                changed = True
                path.rename(original)
                path.write_bytes(b"foreign")
            return read_file(fd, count)
        with patch.object(PET.os, "read", side_effect=replace_while_reading):
            self.expect_error(lambda: PET.read(path), "source-conflict")
        self.assertEqual(original.read_bytes(), b"original")
        self.assertEqual(path.read_bytes(), b"foreign")

    def test_read_handles_interrupted_short_reads_and_reports_io_failure(self):
        path = self.root / "short-input"
        expected = b"abcdefghijklmno"
        path.write_bytes(expected)
        read_file = PET.os.read
        calls = 0
        def short_or_interrupted(fd, count):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise InterruptedError()
            return read_file(fd, min(count, 3))
        with patch.object(PET.os, "read", side_effect=short_or_interrupted):
            self.assertEqual(PET.read(path), expected)
        self.assertGreater(calls, 2)
        with patch.object(PET.os, "read", side_effect=OSError("injected read error")):
            self.expect_error(lambda: PET.read(path))
        self.assertEqual(path.read_bytes(), expected)

    def test_read_detects_in_place_change(self):
        path = self.root / "changing-input"
        path.write_bytes(b"original")
        read_file = PET.os.read
        changed = False
        def write_while_reading(fd, count):
            nonlocal changed
            data = read_file(fd, count)
            if not changed:
                changed = True
                path.write_bytes(b"modified and longer")
            return data
        with patch.object(PET.os, "read", side_effect=write_while_reading):
            self.expect_error(lambda: PET.read(path), "source-conflict")
        self.assertEqual(path.read_bytes(), b"modified and longer")

    def test_exclusive_rename_preserves_existing_directory_and_symlink(self):
        source = self.root / "exclusive-source"
        source.mkdir()
        (source / "owned").write_bytes(b"owned")
        target = self.root / "exclusive-target"
        target.mkdir()
        before = target.stat().st_ino
        with self.assertRaises(FileExistsError):
            PET.rename_exclusive(source, target)
        self.assertEqual(target.stat().st_ino, before)
        self.assertEqual((source / "owned").read_bytes(), b"owned")
        target.rmdir()
        outside = self.root / "outside-target"
        outside.mkdir()
        target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            PET.rename_exclusive(source, target)
        self.assertTrue(target.is_symlink())
        self.assertTrue(outside.is_dir())
        target.unlink()
        PET.rename_exclusive(source, target)
        self.assertEqual((target / "owned").read_bytes(), b"owned")

    def test_exclusive_rename_refuses_unsupported_platform(self):
        with patch.object(PET.sys, "platform", "unsupported-fixture"):
            self.expect_error(lambda: PET.rename_exclusive(self.root / "source", self.root / "target"))

    def test_first_install_preserves_target_created_during_publication(self):
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        publish = PET.rename_exclusive
        created = []
        def race(source, destination):
            if Path(destination) == target and ".stage-" in str(source):
                target.mkdir()
                created.append(target.stat().st_ino)
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=race):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertEqual(target.stat().st_ino, created[0])
        self.assertTrue(PET.journal_path(target.parent).is_file())
        self.assertEqual(len(list(self.codex.glob(f".{PET.PET_ID}.stage-*"))), 1)

    def test_first_install_preserves_symlink_created_during_publication(self):
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        outside = self.root / "unknown-pet"
        outside.mkdir()
        (outside / "foreign.txt").write_bytes(b"preserve")
        publish = PET.rename_exclusive
        def race(source, destination):
            if Path(destination) == target and ".stage-" in str(source):
                target.symlink_to(outside, target_is_directory=True)
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=race):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertTrue(target.is_symlink())
        self.assertEqual((outside / "foreign.txt").read_bytes(), b"preserve")
        self.assertTrue(PET.journal_path(target.parent).is_file())

    def test_backup_collision_preserves_old_pet_and_unknown_directory(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        publish = PET.rename_exclusive
        foreign = []
        def race(source, destination):
            if Path(source) == target and ".previous-" in str(destination):
                Path(destination).mkdir()
                foreign.append((Path(destination), Path(destination).stat().st_ino))
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=race):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)
        self.assertEqual(foreign[0][0].stat().st_ino, foreign[0][1])
        self.assertTrue(PET.journal_path(target.parent).is_file())

    def test_recovery_preserves_target_created_before_backup_restore(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        publish = PET.rename_exclusive
        def interrupt(source, destination):
            publish(source, destination)
            if Path(source) == target and ".previous-" in str(destination):
                raise SystemExit("synthetic interruption after backup")
        with patch.object(PET, "rename_exclusive", side_effect=interrupt), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        created = []
        def race(source, destination):
            if Path(destination) == target and ".previous-" in str(source):
                target.mkdir()
                created.append(target.stat().st_ino)
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=race), self.assertRaises(FileExistsError):
            PET.recover_install(target.parent, self.project)
        self.assertEqual(target.stat().st_ino, created[0])
        self.assertTrue(PET.journal_path(target.parent).is_file())
        self.assertEqual(len(list(self.codex.glob(f".{PET.PET_ID}.previous-*"))), 1)

    def test_snapshot_and_package_publication_preserve_raced_directories(self):
        (self.project / "style.css").write_bytes(b"changed synthetic theme")
        publish = PET.rename_exclusive
        captured = []
        def snapshot_race(source, destination):
            if "/snapshots/" in str(destination):
                Path(destination).mkdir()
                captured.append((Path(destination), Path(destination).stat().st_ino))
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=snapshot_race), self.assertRaises(FileExistsError):
            PET.prepare(self.project)
        self.assertEqual(captured[0][0].stat().st_ino, captured[0][1])
        self.assertTrue(self.snapshot.is_file())
        captured[0][0].rmdir()  # Only the synthetic directory created by this test.
        new_snapshot = Path(PET.prepare(self.project)["snapshot"])
        new_rev = json.loads(new_snapshot.read_text())["themeRevision"]
        self.make_run(self.atlas_a, revision=new_rev)
        def package_race(source, destination):
            if "/packages/" in str(destination):
                Path(destination).mkdir()
                captured.append((Path(destination), Path(destination).stat().st_ino))
            return publish(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=package_race), self.assertRaises(FileExistsError):
            PET.package_run(self.project, self.run, new_snapshot)
        self.assertEqual(captured[1][0].stat().st_ino, captured[1][1])
        self.assertFalse((PET.state_dir(self.project) / "selection.json").exists())

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

    def test_same_atlas_and_theme_with_different_installed_manifest_is_preserved(self):
        self.install()
        target = self.codex / "pets" / PET.PET_ID
        manifest_path = target / "pet.json"
        receipt_path = target / ".azhou-pet-receipt.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["description"] = "locally different description"
        manifest_path.write_bytes(PET.json_bytes(manifest))
        receipt = json.loads(receipt_path.read_text())
        receipt["manifestSHA256"] = PET.sha(manifest_path.read_bytes())
        receipt_path.write_bytes(PET.json_bytes(receipt))
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        selection_path = PET.state_dir(self.project) / "selection.json"
        selection = selection_path.read_bytes()
        candidate_manifest = (PET.selected_package(self.project) / "pet.json").read_bytes()
        installed = PET.status(self.project, self.codex)["installed"]
        self.assertEqual(installed["status"], "stale-package")
        self.assertFalse(installed["matchesSelectedPackage"])
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "source-conflict")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)
        self.assertEqual(selection_path.read_bytes(), selection)
        self.assertEqual((PET.selected_package(self.project) / "pet.json").read_bytes(), candidate_manifest)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_unknown_valid_looking_package_copy_is_preserved(self):
        self.package()
        selected = PET.selected_package(self.project)
        unknown = selected.parent / "unowned-copy"
        shutil.copytree(selected, unknown)
        marker = unknown / "pet.json"
        before = marker.read_bytes()
        self.make_run(self.atlas_b)
        result = self.package()
        self.assertEqual(marker.read_bytes(), before)
        self.assertIn(str(unknown), result["preservedUnverifiedPackages"])
        self.assertTrue(PET.selected_package(self.project).is_dir())

    def test_unbound_legacy_package_remains_readable_but_is_not_pruned(self):
        self.package()
        legacy = PET.selected_package(self.project)
        receipt_path = legacy / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        del receipt["directoryIdentity"]
        receipt_path.write_bytes(PET.json_bytes(receipt))
        PET.check_package(legacy, self.project)
        self.assertEqual(self.package()["status"], "packaged")
        self.assertEqual(PET.selected_package(self.project), legacy)
        self.make_run(self.atlas_b)
        self.package()
        self.make_run(atlas_bytes((90, 180, 50, 255)))
        result = self.package()
        self.assertTrue(legacy.is_dir())
        self.assertIn(str(legacy), result["preservedUnverifiedPackages"])
        PET.check_package(legacy, self.project, require_current=False)

    def test_same_name_candidate_with_different_content_is_not_selected(self):
        self.package()
        first = PET.selected_package(self.project)
        self.make_run(self.atlas_b)
        self.package()
        second = PET.selected_package(self.project)
        selection_path = PET.state_dir(self.project) / "selection.json"
        selection = selection_path.read_bytes()
        saved = self.root / "saved-original-candidate"
        first.rename(saved)
        shutil.copytree(second, first)
        receipt_path = first / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        identity = first.lstat()
        receipt["directoryIdentity"] = {"device": identity.st_dev, "inode": identity.st_ino}
        receipt_path.write_bytes(PET.json_bytes(receipt))
        before = (first / "spritesheet.webp").read_bytes()
        self.make_run(self.atlas_a)
        self.expect_error(self.package, "source-conflict")
        self.assertEqual(selection_path.read_bytes(), selection)
        self.assertEqual(PET.selected_package(self.project), second)
        self.assertEqual((first / "spritesheet.webp").read_bytes(), before)
        self.assertTrue(saved.is_dir())

    def test_unbound_unselected_legacy_candidate_is_not_adopted(self):
        self.package()
        legacy = PET.selected_package(self.project)
        receipt_path = legacy / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        del receipt["directoryIdentity"]
        receipt_path.write_bytes(PET.json_bytes(receipt))
        self.make_run(self.atlas_b)
        self.package()
        previous = PET.selected_package(self.project)
        selection = (PET.state_dir(self.project) / "selection.json").read_bytes()
        self.make_run(self.atlas_a)
        self.expect_error(self.package, "source-conflict")
        self.assertEqual(PET.selected_package(self.project), previous)
        self.assertEqual((PET.state_dir(self.project) / "selection.json").read_bytes(), selection)
        self.assertTrue(legacy.is_dir())

    def test_recreated_package_directory_is_preserved_despite_valid_copied_receipt(self):
        self.package()
        first = PET.selected_package(self.project)
        self.make_run(self.atlas_b)
        self.package()
        moved = self.root / "original-candidate"
        first.rename(moved)
        shutil.copytree(moved, first)
        self.assertNotEqual(first.stat().st_ino, moved.stat().st_ino)
        before = (first / "pet.json").read_bytes()
        self.make_run(atlas_bytes((90, 180, 50, 255)))
        result = self.package()
        self.assertEqual((first / "pet.json").read_bytes(), before)
        self.assertTrue(moved.is_dir())
        self.assertIn(str(first), result["preservedUnverifiedPackages"])

    def test_foreign_file_added_after_stage_validation_is_preserved(self):
        state = PET.state_dir(self.project, True)
        validate = PET.verify_stage_for_cleanup
        for index, kind in enumerate(("snapshot", "package")):
            with self.subTest(kind=kind):
                stage = state / (".stage-" + str(index) * 32)
                stage.mkdir()
                planned = {name: b"synthetic" for name in PET.stage_file_names(kind)}
                name = "generation-brief.md" if kind == "snapshot" else "pet.json"
                PET.write_new(stage / name, planned[name])
                record = PET.stage_journal(self.project, stage, kind, planned, None)
                journal = state / "package-journal.json"
                PET.atomic_json(journal, record)
                def inject(stage_path, *args):
                    validate(stage_path, *args)
                    (stage_path / "foreign.txt").write_bytes(b"do not delete")
                error = None
                with patch.object(PET, "verify_stage_for_cleanup", side_effect=inject):
                    try: PET.recover_package_stage(state, self.project)
                    except PET.PetError as exc: error = exc
                self.assertTrue((stage / "foreign.txt").is_file(), "foreign file must survive cleanup")
                self.assertEqual((stage / "foreign.txt").read_bytes(), b"do not delete")
                self.assertTrue(journal.is_file())
                self.assertIsNotNone(error)
                self.assertEqual(error.code, "recovery-required")
                (stage / "foreign.txt").unlink()
                PET.recover_package_stage(state, self.project)

    def test_foreign_file_added_after_install_stage_validation_is_preserved(self):
        self.install()
        pets = self.codex / "pets"
        facts = PET.installed_facts(pets / PET.PET_ID, self.project)
        tx = "a" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("install")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        journal = PET.journal_path(pets)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "committed", "hadPrevious": False,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"],
                  "stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                  "stageIdentity": binding["stageIdentity"]}
        PET.atomic_json(journal, record)
        validate = PET.verify_stage_for_cleanup
        def inject(stage_path, *args):
            validate(stage_path, *args)
            (stage_path / "foreign.txt").write_bytes(b"do not delete")
        error = None
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=inject):
            try: PET.recover_install(pets, self.project)
            except PET.PetError as exc: error = exc
        self.assertTrue((stage / "foreign.txt").is_file(), "foreign file must survive cleanup")
        self.assertEqual((stage / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue(journal.is_file())
        self.assertIsNotNone(error)
        self.assertEqual(error.code, "recovery-required")
        self.assertTrue((pets / PET.PET_ID).is_dir())

    def test_install_recovery_keeps_target_when_stage_gains_unknown_file(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        original = {path.name: path.read_bytes() for path in target.iterdir()}
        facts = PET.installed_facts(target, self.project)
        tx = "f" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("install")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        journal = PET.journal_path(pets)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": False,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"],
                  "stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                  "stageIdentity": binding["stageIdentity"]}
        PET.atomic_json(journal, record)
        validate = PET.verify_stage_for_cleanup
        calls = []
        def inject(stage_path, *args):
            validate(stage_path, *args)
            calls.append(True)
            if len(calls) == 1: (stage_path / "foreign.txt").write_bytes(b"do not delete")
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=inject):
            self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertTrue(target.is_dir(), "installed candidate must not be removed after stage conflict")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, original)
        self.assertEqual((stage / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue(journal.is_file())

    def test_foreign_file_added_during_stage_deletion_is_not_removed(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "b" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("snapshot")}
        PET.write_new(stage / "generation-brief.md", planned["generation-brief.md"])
        PET.write_new(stage / "inputs/style.css", planned["inputs/style.css"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "snapshot", planned, None))
        unlink = PET.os.unlink
        injected = []
        def inject(name, *args, **kwargs):
            if not injected:
                (stage / "foreign.txt").write_bytes(b"do not delete")
                injected.append(True)
            return unlink(name, *args, **kwargs)
        with patch.object(PET.os, "unlink", side_effect=inject):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual(injected, [True])
        self.assertEqual((stage / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue(journal.is_file())
        self.assertFalse((stage / "generation-brief.md").exists())

    def test_stage_file_changed_after_final_validation_is_not_removed(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "c" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("package")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        validate = PET.verify_stage_for_cleanup
        calls = []
        def replace_after_validation(stage_path, *args):
            validate(stage_path, *args)
            calls.append(True)
            if len(calls) == 2: (stage_path / "pet.json").write_bytes(b"changed by another actor")
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=replace_after_validation):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual((stage / "pet.json").read_bytes(), b"changed by another actor")
        self.assertTrue(journal.is_file())

    def test_stage_symlink_substitution_after_final_validation_is_preserved(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "d" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("package")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        outside = self.root / "outside"
        outside.write_bytes(b"do not delete")
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        validate = PET.verify_stage_for_cleanup
        calls = []
        def replace_after_validation(stage_path, *args):
            validate(stage_path, *args)
            calls.append(True)
            if len(calls) == 2:
                (stage_path / "pet.json").unlink()
                (stage_path / "pet.json").symlink_to(outside)
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=replace_after_validation):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual(outside.read_bytes(), b"do not delete")
        self.assertTrue((stage / "pet.json").is_symlink())
        self.assertTrue(journal.is_file())

    def test_stage_copy_after_final_validation_is_preserved(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "e" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("package")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        saved = self.root / "actual-stage"
        validate = PET.verify_stage_for_cleanup
        calls = []
        def replace_after_validation(stage_path, *args):
            validate(stage_path, *args)
            calls.append(True)
            if len(calls) == 2:
                stage_path.rename(saved)
                shutil.copytree(saved, stage_path)
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=replace_after_validation):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual((stage / "pet.json").read_bytes(), b"synthetic")
        self.assertEqual((saved / "pet.json").read_bytes(), b"synthetic")
        self.assertTrue(journal.is_file())

    def test_stage_unlink_failure_preserves_file_and_journal(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "1" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("package")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        with patch.object(PET.os, "unlink", side_effect=PermissionError("injected")):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual((stage / "pet.json").read_bytes(), b"synthetic")
        self.assertTrue(journal.is_file())
        PET.recover_package_stage(state, self.project)
        self.assertFalse(stage.exists())
        self.assertFalse(journal.exists())

    def test_stage_cleanup_retries_interrupted_file_read(self):
        state = PET.state_dir(self.project, True)
        stage = state / (".stage-" + "2" * 32)
        stage.mkdir()
        planned = {name: b"synthetic" for name in PET.stage_file_names("package")}
        PET.write_new(stage / "pet.json", planned["pet.json"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        validate, read = PET.verify_stage_for_cleanup, PET.os.read
        calls, interruptions = [], []
        def validated(stage_path, *args):
            validate(stage_path, *args)
            calls.append(True)
        def interrupt_once(fd, size):
            if len(calls) >= 2 and not interruptions:
                interruptions.append(True)
                raise InterruptedError()
            return read(fd, size)
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=validated), patch.object(PET.os, "read", side_effect=interrupt_once):
            PET.recover_package_stage(state, self.project)
        self.assertEqual(interruptions, [True])
        self.assertFalse(stage.exists())
        self.assertFalse(journal.exists())

    def test_history_cleanup_preserves_file_added_after_candidate_verification(self):
        self.package()
        first = PET.selected_package(self.project)
        self.make_run(self.atlas_b)
        self.package()
        self.make_run(atlas_bytes((90, 180, 50, 255)))
        verify = PET.check_package
        injected = []
        def inject(directory, *args, **kwargs):
            result = verify(directory, *args, **kwargs)
            if Path(directory) == first and not injected:
                (first / "foreign.txt").write_bytes(b"do not delete")
                injected.append(True)
            return result
        with patch.object(PET, "check_package", side_effect=inject):
            try: self.package()
            except PET.PetError: pass
        self.assertEqual(injected, [True])
        self.assertTrue((first / "foreign.txt").is_file(), "history cleanup deleted an unplanned file")
        self.assertEqual((first / "foreign.txt").read_bytes(), b"do not delete")

    def test_install_recovery_preserves_file_added_after_target_verification(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "3" * 32
        journal = PET.journal_path(pets)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": False,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"]}
        PET.atomic_json(journal, record)
        verify = PET.installed_facts
        injected = []
        def inject(directory, *args, **kwargs):
            result = verify(directory, *args, **kwargs)
            if Path(directory) == target and not injected:
                (target / "foreign.txt").write_bytes(b"do not delete")
                injected.append(True)
            return result
        with patch.object(PET, "installed_facts", side_effect=inject):
            try: PET.recover_install(pets, self.project)
            except PET.PetError: pass
        self.assertEqual(injected, [True])
        self.assertTrue((target / "foreign.txt").is_file(), "recovery deleted an unplanned file")
        self.assertEqual((target / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue(journal.is_file())

    def test_committed_recovery_preserves_file_added_after_backup_verification(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "4" * 32
        backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
        shutil.copytree(target, backup)
        journal = PET.journal_path(pets)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "committed", "hadPrevious": True,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"], "previousAtlasSHA256": facts["atlasSHA256"],
                  "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"]}
        PET.atomic_json(journal, record)
        verify = PET.installed_facts
        injected = []
        def inject(directory, *args, **kwargs):
            result = verify(directory, *args, **kwargs)
            if Path(directory) == backup and not injected:
                (backup / "foreign.txt").write_bytes(b"do not delete")
                injected.append(True)
            return result
        with patch.object(PET, "installed_facts", side_effect=inject):
            try: PET.recover_install(pets, self.project)
            except PET.PetError: pass
        self.assertEqual(injected, [True])
        self.assertTrue((backup / "foreign.txt").is_file(), "recovery deleted an unplanned backup file")
        self.assertEqual((backup / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue(target.is_dir())
        self.assertTrue(journal.is_file())

    def test_owned_cleanup_rejects_file_change_or_directory_copy_after_plan(self):
        for mode in ("content", "directory"):
            with self.subTest(mode=mode):
                target = self.root / ("planned-" + mode)
                target.mkdir()
                (target / "pet.json").write_bytes(b"synthetic")
                plan = PET.capture_removal_plan(target, {"pet.json"})
                if mode == "content":
                    (target / "pet.json").write_bytes(b"foreign content")
                    expected = b"foreign content"
                else:
                    saved = self.root / "saved-planned-target"
                    target.rename(saved)
                    shutil.copytree(saved, target)
                    expected = b"synthetic"
                self.expect_error(lambda: PET.remove_tree(target, plan), "recovery-required")
                self.assertEqual((target / "pet.json").read_bytes(), expected)
                if mode == "directory": self.assertEqual((saved / "pet.json").read_bytes(), b"synthetic")

    def test_owned_cleanup_preserves_unplanned_file_inserted_during_deletion(self):
        target = self.root / "planned-transaction"
        target.mkdir()
        for name in ("pet.json", "spritesheet.webp"):
            (target / name).write_bytes(b"synthetic")
        plan = PET.capture_removal_plan(target, {"pet.json", "spritesheet.webp"})
        unlink = PET.os.unlink
        injected = []
        def inject(name, *args, **kwargs):
            if not injected:
                (target / "foreign.txt").write_bytes(b"do not delete")
                injected.append(True)
            return unlink(name, *args, **kwargs)
        with patch.object(PET.os, "unlink", side_effect=inject):
            self.expect_error(lambda: PET.remove_tree(target, plan), "recovery-required")
        self.assertEqual(injected, [True])
        self.assertEqual((target / "foreign.txt").read_bytes(), b"do not delete")
        self.assertFalse((target / "pet.json").exists())

    def test_owned_cleanup_does_not_accept_file_disappearing_after_preflight(self):
        target = self.root / "planned-disappearing"
        target.mkdir()
        for name in ("pet.json", "spritesheet.webp"):
            (target / name).write_bytes(b"synthetic")
        plan = PET.capture_removal_plan(target, {"pet.json", "spritesheet.webp"})
        open_file = PET.os.open
        injected = []
        def disappear(name, *args, **kwargs):
            if name == "pet.json" and kwargs.get("dir_fd") is not None and not injected:
                (target / "pet.json").unlink()
                injected.append(True)
            return open_file(name, *args, **kwargs)
        error = None
        with patch.object(PET.os, "open", side_effect=disappear):
            try: PET.remove_tree(target, plan)
            except PET.PetError as exc: error = exc
        self.assertEqual(injected, [True])
        self.assertTrue(target.is_dir(), "missing planned file must not be accepted as cleanup")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), b"synthetic")
        self.assertIsNotNone(error)
        self.assertEqual(error.code, "recovery-required")

    def test_provisional_package_journal_preserves_even_empty_stage(self):
        state = PET.state_dir(self.project, True)
        journal = state / "package-journal.json"
        stage = state / (".stage-" + "a" * 32)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "stage": stage.name, "phase": "allocating"}
        stage.mkdir()
        PET.atomic_json(journal, record)
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertTrue(stage.is_dir())
        self.assertTrue(journal.exists())
        (stage / "foreign.txt").write_bytes(b"preserve")
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual((stage / "foreign.txt").read_bytes(), b"preserve")
        (stage / "foreign.txt").unlink()
        stage.rmdir()
        PET.recover_package_stage(state, self.project)
        self.assertFalse(journal.exists())

    def test_unknown_package_journal_phase_preserves_even_absent_stage(self):
        state = PET.state_dir(self.project, True)
        journal = state / "package-journal.json"
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "stage": ".stage-" + "a" * 32, "phase": "unexpected"}
        PET.atomic_json(journal, record)
        before = journal.read_bytes()
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual(journal.read_bytes(), before)

    def test_package_directory_binding_rejects_malformed_identity(self):
        directory = self.root / "identity"
        directory.mkdir()
        info = directory.lstat()
        valid = {"device": info.st_dev, "inode": info.st_ino}
        self.assertTrue(PET.package_directory_matches(directory, {"directoryIdentity": valid}))
        for identity in (None, {}, {"device": True, "inode": info.st_ino},
                         {"device": -1, "inode": info.st_ino},
                         {**valid, "unknown": 1}):
            with self.subTest(identity=identity):
                self.assertFalse(PET.package_directory_matches(directory, {"directoryIdentity": identity}))
        self.assertFalse(PET.package_directory_matches(self.root / "missing", {"directoryIdentity": valid}))

    def test_new_package_stage_collision_preserves_unknown_empty_directory(self):
        state = PET.state_dir(self.project, True)
        token = "a" * 32
        stage = state / (".stage-" + token)
        stage.mkdir()
        with patch.object(PET.uuid, "uuid4", return_value=type("Token", (), {"hex": token})()):
            self.expect_error(self.package, "recovery-required")
        self.assertTrue(stage.is_dir())
        self.assertEqual(list(stage.iterdir()), [])
        self.assertTrue((state / "package-journal.json").exists())
        self.assertFalse((state / "selection.json").exists())

    def test_empty_install_stage_preserves_target_and_journal(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "f" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        planned = {name: b"synthetic install evidence" for name in PET.stage_file_names("install")}
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": tx, "stagingLocation": "codex-home", "phase": "committed", "hadPrevious": True,
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"], "previousAtlasSHA256": facts["atlasSHA256"],
                   "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                   "stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                   "stageIdentity": binding["stageIdentity"]}
        PET.atomic_json(PET.journal_path(pets), journal)
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)
        self.assertTrue(stage.is_dir())
        self.assertTrue(PET.journal_path(pets).is_file())

    def test_package_stage_replaced_at_publish_is_not_selected(self):
        self.package()
        previous = PET.selected_package(self.project)
        selection = (PET.state_dir(self.project) / "selection.json").read_bytes()
        self.make_run(self.atlas_b)
        rename = PET.rename_exclusive
        moved = []
        def replace_stage(source, destination):
            source = Path(source)
            if source.name.startswith(".stage-") and Path(destination).parent.name == "packages":
                saved = self.root / "original-stage"
                source.rename(saved)
                shutil.copytree(saved, source)
                moved.append((saved, Path(destination)))
            return rename(source, destination)
        with patch.object(PET, "rename_exclusive", side_effect=replace_stage):
            self.expect_error(self.package, "source-conflict")
        self.assertTrue(moved[0][0].is_dir())
        self.assertTrue(moved[0][1].is_dir())
        self.assertEqual(PET.selected_package(self.project), previous)
        self.assertEqual((PET.state_dir(self.project) / "selection.json").read_bytes(), selection)

    def test_selection_metadata_mismatch_is_not_accepted(self):
        self.package()
        path = PET.state_dir(self.project) / "selection.json"
        value = json.loads(path.read_text())
        value["atlasSHA256"] = "0" * 64
        path.write_bytes(PET.json_bytes(value))
        before = path.read_bytes()
        self.expect_error(lambda: PET.selected_package(self.project), "source-conflict")
        self.assertEqual(path.read_bytes(), before)

    def test_selected_name_must_match_verified_package_for_status_and_install(self):
        self.package()
        first = PET.selected_package(self.project)
        first_selection = (PET.state_dir(self.project) / "selection.json").read_bytes()
        self.make_run(self.atlas_b)
        self.package()
        second = PET.selected_package(self.project)
        saved = self.root / "saved-first-package"
        first.rename(saved)
        shutil.copytree(second, first)
        receipt_path = first / "package-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        identity = first.lstat()
        receipt["directoryIdentity"] = {"device": identity.st_dev, "inode": identity.st_ino}
        receipt_path.write_bytes(PET.json_bytes(receipt))
        selection_path = PET.state_dir(self.project) / "selection.json"
        selection_path.write_bytes(first_selection)
        self.expect_error(lambda: PET.install_package(self.project, self.codex), "source-conflict")
        self.assertEqual(PET.status(self.project, self.codex)["package"]["status"], "source-conflict")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = PET.main(["validate", "--project-root", str(self.project), "--codex-home", str(self.codex)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "source-conflict")
        self.assertEqual(selection_path.read_bytes(), first_selection)
        self.assertTrue(saved.is_dir())
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())

    def test_handoff_rejects_mismatched_old_selection_without_changing_install(self):
        old_project = self.make_old_install()
        self.package()
        old_selection = PET.state_dir(old_project) / "selection.json"
        value = json.loads(old_selection.read_text())
        value["themeRevision"] = "0" * 64
        old_selection.write_bytes(PET.json_bytes(value))
        target = self.codex / "pets" / PET.PET_ID
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        self.expect_error(lambda: PET.handoff_package(self.project, old_project, self.codex), "source-conflict")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_selection_rejects_noncanonical_names_and_extra_fields(self):
        self.package()
        path = PET.state_dir(self.project) / "selection.json"
        original = json.loads(path.read_text())
        values = [[], {**original, "extra": 1}, {**original, "package": "-" + original["package"][1:]},
                  {**original, "package": original["package"].upper()},
                  {**original, "themeRevision": "0" * 64}]
        for value in values:
            with self.subTest(value=value):
                path.write_bytes(PET.json_bytes(value))
                before = path.read_bytes()
                self.expect_error(lambda: PET.selected_package(self.project), "source-conflict")
                self.assertEqual(path.read_bytes(), before)
        path.write_bytes(PET.json_bytes(original))
        self.assertTrue(PET.selected_package(self.project).is_dir())

    def test_malformed_theme_is_reported_without_modification(self):
        theme = self.project / "pet/theme.json"
        data = b"[]"
        theme.write_bytes(data)
        self.expect_error(lambda: PET.theme_facts(self.project))
        self.assertEqual(PET.status(self.project, self.codex)["source"]["status"], "invalid")
        self.assertEqual(theme.read_bytes(), data)

    def test_malformed_snapshot_records_are_reported_without_modification(self):
        original = json.loads(self.snapshot.read_bytes())
        for records in (None, {}, [None] * 4, [{"path": name} for name in PET.INPUTS],
                        [{"path": name, "sha256": "bad"} for name in PET.INPUTS]):
            with self.subTest(records=records):
                snapshot = {**original, "inputs": records, "themeRevision": PET.revision(records)}
                data = PET.json_bytes(snapshot)
                self.snapshot.write_bytes(data)
                self.expect_error(lambda: PET.load_snapshot(self.project, self.snapshot))
                self.assertEqual(self.snapshot.read_bytes(), data)

    def test_status_reports_malformed_selected_snapshot(self):
        self.package()
        directory = PET.selected_package(self.project)
        path = directory / "theme-snapshot.json"
        snapshot = json.loads(path.read_bytes())
        snapshot["inputs"] = [None] * 4
        data = PET.json_bytes(snapshot)
        path.write_bytes(data)
        self.assertEqual(PET.status(self.project, self.codex)["package"]["status"], "invalid")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = PET.main(["status", "--project-root", str(self.project), "--codex-home", str(self.codex)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["package"]["status"], "invalid")
        self.assertEqual(path.read_bytes(), data)

    def test_prepare_preserves_existing_invalid_or_missing_brief(self):
        brief = self.snapshot.parent / "generation-brief.md"
        original = brief.read_bytes()
        frozen = self.snapshot.read_bytes()
        outside = self.root / "outside-brief"
        outside.write_bytes(b"outside")
        for case in ("missing", "empty", "invalid-utf8", "wrong-revision", "symlink"):
            with self.subTest(case=case):
                brief.unlink()
                try:
                    if case == "empty": brief.write_bytes(b"")
                    if case == "invalid-utf8": brief.write_bytes(b"\xff")
                    if case == "wrong-revision": brief.write_bytes(b"revision not present")
                    if case == "symlink": brief.symlink_to(outside)
                    self.expect_error(lambda: PET.prepare(self.project), "source-conflict")
                    self.assertEqual(self.snapshot.read_bytes(), frozen)
                    self.assertEqual(outside.read_bytes(), b"outside")
                    if case == "missing": self.assertFalse(brief.exists())
                    elif case == "symlink": self.assertTrue(brief.is_symlink())
                    else: self.assertTrue(brief.is_file())
                finally:
                    if brief.is_symlink() or brief.exists(): brief.unlink()
                    brief.write_bytes(original)
        custom = ("custom brief " + self.rev + "\n").encode()
        brief.write_bytes(custom)
        self.assertEqual(PET.prepare(self.project)["snapshot"], str(self.snapshot))
        self.assertEqual(brief.read_bytes(), custom)

    def test_prepare_rechecks_theme_after_snapshot_publication(self):
        theme = self.project / "style.css"
        theme.write_bytes(b"new synthetic theme")
        expected_revision = PET.theme_facts(self.project)[0]["themeRevision"]
        rename = PET.rename_exclusive
        def change_after_publish(source, destination):
            rename(source, destination)
            if Path(destination).parent.name == "snapshots":
                theme.write_bytes(b"changed during publication")
        with patch.object(PET, "rename_exclusive", side_effect=change_after_publish):
            self.expect_error(lambda: PET.prepare(self.project), "generation-required")
        frozen = PET.state_dir(self.project) / "snapshots" / expected_revision / "theme-snapshot.json"
        self.assertTrue(frozen.is_file())
        self.assertTrue(self.snapshot.is_file())
        self.assertEqual(theme.read_bytes(), b"changed during publication")

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

    def test_hidden_rgb_is_rejected_only_for_fully_transparent_pixels(self):
        image = Image.open(io.BytesIO(self.atlas_a)).convert("RGBA")
        image.putpixel((1, 1), (9, 5, 1, 0))
        stream = io.BytesIO()
        image.save(stream, "PNG")
        self.expect_error(lambda: PET.inspect_atlas(stream.getvalue()))

        image.putpixel((1, 1), (9, 5, 1, 1))
        stream = io.BytesIO()
        image.save(stream, "PNG")
        self.assertTrue(PET.inspect_atlas(stream.getvalue())["fullDecode"])

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

    def test_direction_coverage_rejects_nonfinite_and_out_of_range_angles(self):
        raw = {name: (self.run / name).read_bytes() for name in PET.QA_FILES}
        report = json.loads(raw[PET.QA_FILES[3]])
        report["directions"][0]["direction"] = "-0"
        raw[PET.QA_FILES[3]] = PET.json_bytes(report)
        PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)
        for value in ("nan", "inf", "360"):
            with self.subTest(value=value):
                report["directions"][0]["direction"] = value
                raw[PET.QA_FILES[3]] = PET.json_bytes(report)
                with self.assertRaisesRegex(PET.PetError, "方向记录缺失"):
                    PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)

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

    def test_approved_warning_never_overrides_explicit_failure(self):
        raw = {name: (self.run / name).read_bytes() for name in PET.QA_FILES}
        visual = json.loads(raw[PET.QA_FILES[5]])
        visual.update(labeledLoopReviewed=True, blindResolution={"decision": "accept", "severity": "minor"})
        raw[PET.QA_FILES[5]] = PET.json_bytes(visual)
        original_semantics = raw[PET.QA_FILES[3]]
        for key, value in (("ok", False), ("pass", False), ("status", "fail"),
                           ("status", "failed"), ("result", "fail"), ("result", "failed")):
            with self.subTest(key=key, value=value):
                semantics = json.loads(original_semantics)
                direction = semantics["directions"][1]
                direction.pop("pass")
                direction.update(verdict="warning", **{key: value})
                raw[PET.QA_FILES[3]] = PET.json_bytes(semantics)
                with self.assertRaises(PET.PetError):
                    PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)

    def test_approved_warning_retains_existing_numeric_zero_semantics(self):
        raw = {name: (self.run / name).read_bytes() for name in PET.QA_FILES}
        visual = json.loads(raw[PET.QA_FILES[5]])
        visual.update(labeledLoopReviewed=True, blindResolution={"decision": "accept", "severity": "minor"})
        raw[PET.QA_FILES[5]] = PET.json_bytes(visual)
        semantics = json.loads(raw[PET.QA_FILES[3]])
        semantics["directions"][1].update(verdict="warning", ok=0)
        raw[PET.QA_FILES[3]] = PET.json_bytes(semantics)
        self.assertEqual(set(PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)), set(PET.QA_FILES))

    def test_direction_failure_list_cannot_be_waived(self):
        raw = {name: (self.run / name).read_bytes() for name in PET.QA_FILES}
        visual = json.loads(raw[PET.QA_FILES[5]])
        visual.update(labeledLoopReviewed=True, blindResolution={"decision": "accept", "severity": "minor"})
        raw[PET.QA_FILES[5]] = PET.json_bytes(visual)
        original = raw[PET.QA_FILES[3]]
        for verdict in ("pass", "warning"):
            with self.subTest(verdict=verdict):
                report = json.loads(original)
                report["directions"][1].update(verdict=verdict, failures=["unresolved"])
                raw[PET.QA_FILES[3]] = PET.json_bytes(report)
                with self.assertRaises(PET.PetError):
                    PET.validate_qa(raw, PET.sha(self.atlas_a), self.rev)

    def test_contradictory_warning_cannot_be_packaged(self):
        self.change_qa("qa/direction-semantics.json", lambda report: report["directions"][1].update(verdict="warning", ok=False))
        self.change_qa("qa/visual-qa.json", lambda review: review.update(labeledLoopReviewed=True,
                       blindResolution={"decision": "accept", "severity": "minor"}))
        qa_path = self.run / "qa/direction-semantics.json"
        before = qa_path.read_bytes()
        state = PET.state_dir(self.project)
        selection = state / "selection.json"
        self.assertFalse(selection.exists())
        state_before = sorted(str(path.relative_to(state)) for path in state.rglob("*"))
        self.expect_error(self.package)
        self.assertFalse(selection.exists())
        self.assertEqual(sorted(str(path.relative_to(state)) for path in state.rglob("*")), state_before)
        self.assertEqual(qa_path.read_bytes(), before)

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

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_recovery_refuses_to_delete_unknown_special_files(self):
        stage = self.root / "unknown-stage"
        stage.mkdir()
        (stage / "owned").write_bytes(b"synthetic")
        plan = PET.capture_removal_plan(stage, {"owned"})
        unknown = stage / "unexpected-fifo"
        os.mkfifo(unknown)
        self.expect_error(lambda: PET.remove_tree(stage, plan), code="recovery-required")
        self.assertTrue(unknown.exists())
        self.assertEqual((stage / "owned").read_bytes(), b"synthetic")

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
        real = PET.rename_exclusive

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated process exit during handoff")

        with patch.object(PET, "rename_exclusive", side_effect=interrupted), self.assertRaises(SystemExit):
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

        def interrupted(path, plan):
            if ".previous-" in str(path):
                raise SystemExit("simulated process exit during handoff cleanup")
            return real(path, plan)

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

    def mutate_after_stage_receipt(self, mutation):
        real = PET.write_new

        def write(path, data):
            result = real(path, data)
            if Path(path).name == ".azhou-pet-receipt.json" and ".stage-" in str(path):
                mutation()
            return result
        return patch.object(PET, "write_new", side_effect=write)

    def test_theme_change_during_install_preserves_previous_pet(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        with self.mutate_after_stage_receipt(lambda: (self.project / "style.css").write_text("changed during install")):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "install-failed")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_unexpected_target_change_during_install_is_preserved(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        foreign = target / "foreign.txt"
        with self.mutate_after_stage_receipt(lambda: foreign.write_text("preserve")):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertEqual(foreign.read_text(), "preserve")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)
        self.assertTrue(PET.journal_path(target.parent).exists())

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
        real = PET.rename_exclusive
        target = self.codex / "pets" / PET.PET_ID

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated abrupt interruption")

        with patch.object(PET, "rename_exclusive", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        self.assertTrue(PET.journal_path(self.codex / "pets").exists())
        self.assertEqual(PET.recover_install(self.codex / "pets", self.project),
                         "restored-previous-installed-package")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)

    def test_interruption_after_backing_up_target_restores_previous_pet(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        target = self.codex / "pets" / PET.PET_ID
        real = PET.rename_exclusive

        def interrupted(source, destination):
            real(source, destination)
            if Path(source) == target and ".previous-" in str(destination):
                raise SystemExit("simulated interruption after backup")

        with patch.object(PET, "rename_exclusive", side_effect=interrupted), self.assertRaises(SystemExit):
            PET.install_package(self.project, self.codex)
        self.assertFalse(target.exists())
        self.assertTrue(PET.journal_path(target.parent).exists())
        self.assertEqual(PET.recover_install(target.parent, self.project), "restored-previous-installed-package")
        self.assertEqual((target / "spritesheet.webp").read_bytes(), self.atlas_a)
        self.assertFalse(PET.journal_path(target.parent).exists())

    def test_recover_does_not_require_the_old_theme_to_remain_current(self):
        self.install()
        self.make_run(self.atlas_b)
        self.package()
        real = PET.rename_exclusive
        target = self.codex / "pets" / PET.PET_ID

        def interrupted(source, destination):
            real(source, destination)
            if Path(destination) == target and ".stage-" in str(source):
                raise SystemExit("simulated process exit")

        with patch.object(PET, "rename_exclusive", side_effect=interrupted), self.assertRaises(SystemExit):
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

        def interrupted(path, plan):
            if ".previous-" in str(path):
                raise SystemExit("simulated interruption during cleanup")
            return real(path, plan)

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
        real = PET.rename_exclusive
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

        with patch.object(PET, "rename_exclusive", side_effect=intercepted):
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
            "candidateManifestSHA256": old["manifestSHA256"],
            "previousAtlasSHA256": old["atlasSHA256"], "previousThemeRevision": old["themeRevision"],
            "previousManifestSHA256": old["manifestSHA256"],
        }
        planned = {name: b"synthetic install evidence" for name in PET.stage_file_names("install")}
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        journal.update({"stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                   "stageIdentity": binding["stageIdentity"]})
        (stage / "pet.json").write_bytes(planned["pet.json"])
        journal_file = PET.journal_path(pets)
        PET.atomic_json(journal_file, journal)
        self.assertEqual(PET.recover_install(pets, self.project), "restored-pre-install-state")
        self.assertTrue(target.is_dir())
        self.assertFalse(stage.exists())
        self.assertFalse(journal_file.exists())

        PET.remove_tree(target, PET.capture_removal_plan(target, PET.stage_file_names("install")))
        PET.atomic_json(journal_file, journal)
        with self.assertRaisesRegex(PET.PetError, "正式目标与旧包均缺失"):
            PET.recover_install(pets, self.project)
        self.assertTrue(journal_file.exists())

    def test_atomic_json_preserves_a_new_file_at_published_temporary_name(self):
        path = self.root / "receipt.json"
        replace = PET.os.replace
        foreign = []
        def publish_then_reuse(source, destination):
            replace(source, destination)
            Path(source).write_bytes(b"foreign after publication")
            foreign.append(Path(source))
        with patch.object(PET.os, "replace", side_effect=publish_then_reuse):
            PET.atomic_json(path, {"fixture": True})
        self.assertTrue(json.loads(path.read_text())["fixture"])
        self.assertEqual(foreign[0].read_bytes(), b"foreign after publication")

    def test_atomic_json_preserves_preexisting_and_replaced_temporary_files(self):
        path = self.root / "receipt.json"
        token = "1" * 32
        temp = path.with_name(f".{path.name}.{token}.tmp")
        temp.write_bytes(b"foreign collision")
        with patch.object(PET.uuid, "uuid4", return_value=type("Token", (), {"hex": token})()):
            with self.assertRaises(FileExistsError):
                PET.atomic_json(path, {"fixture": True})
        self.assertEqual(temp.read_bytes(), b"foreign collision")
        temp.unlink()
        foreign = []
        def replace_source_then_fail(source, destination):
            source = Path(source)
            source.rename(source.with_suffix(".saved"))
            source.write_bytes(b"foreign replacement")
            foreign.append(source)
            raise OSError("synthetic replace failure")
        with patch.object(PET.os, "replace", side_effect=replace_source_then_fail):
            with self.assertRaisesRegex(OSError, "synthetic replace failure"):
                PET.atomic_json(path, {"fixture": True})
        self.assertEqual(foreign[0].read_bytes(), b"foreign replacement")
        self.assertFalse(path.exists())

    def test_atomic_json_preserves_in_place_changed_temporary_file(self):
        path = self.root / "receipt.json"
        foreign = []
        def modify_then_fail(source, destination):
            source = Path(source)
            source.write_bytes(b"changed contents")
            foreign.append(source)
            raise OSError("synthetic replace failure")
        with patch.object(PET.os, "replace", side_effect=modify_then_fail):
            with self.assertRaisesRegex(OSError, "synthetic replace failure"):
                PET.atomic_json(path, {"fixture": True})
        self.assertEqual(foreign[0].read_bytes(), b"changed contents")
        self.assertFalse(path.exists())

    def test_atomic_json_preserves_incomplete_write_and_prepublication_replacement(self):
        path = self.root / "receipt.json"
        left = []
        def partial_write(temp, data):
            temp.write_bytes(b"incomplete")
            left.append(temp)
            raise OSError("synthetic write failure")
        with patch.object(PET, "write_new", side_effect=partial_write):
            with self.assertRaisesRegex(OSError, "synthetic write failure"):
                PET.atomic_json(path, {"fixture": True})
        self.assertEqual(left[0].read_bytes(), b"incomplete")
        write = PET.write_new
        def replace_after_write(temp, data):
            identity = write(temp, data)
            temp.rename(temp.with_suffix(".saved"))
            temp.write_bytes(b"foreign before publication")
            left.append(temp)
            return identity
        with patch.object(PET, "write_new", side_effect=replace_after_write):
            self.expect_error(lambda: PET.atomic_json(path, {"fixture": True}), "source-conflict")
        self.assertEqual(left[1].read_bytes(), b"foreign before publication")
        self.assertFalse(path.exists())

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

    def test_legacy_stage_with_matching_files_but_no_identity_is_preserved(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "d" * 32)
        stage.mkdir()
        planned = {name: b"synthetic frozen input" for name in PET.stage_file_names("snapshot")}
        (stage / "generation-brief.md").write_bytes(planned["generation-brief.md"])
        record = PET.stage_journal(self.project, stage, "snapshot", planned, None)
        del record["stageIdentity"]
        journal = state / "package-journal.json"
        PET.atomic_json(journal, record)
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual((stage / "generation-brief.md").read_bytes(), planned["generation-brief.md"])
        self.assertTrue(journal.is_file())

    def test_snapshot_and_package_bind_failure_preserves_allocating_stage(self):
        for kind in ("snapshot", "package"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(self.project, project, ignore=shutil.ignore_patterns('.local'))
                prepared = PET.prepare(project)
                snapshot = Path(prepared["snapshot"])
                if kind == "snapshot":
                    (project / "style.css").write_bytes(b"changed synthetic theme")
                revision = json.loads(snapshot.read_bytes())["themeRevision"]
                run = Path(tmp) / "run"
                self.make_run(self.atlas_a, directory=run, revision=revision)
                state = PET.state_dir(project)
                actual = PET.atomic_json
                def fail_binding(path, value):
                    if Path(path).name == "package-journal.json" and value.get("stageIdentity"):
                        raise OSError("injected binding failure")
                    return actual(path, value)
                with patch.object(PET, "atomic_json", side_effect=fail_binding):
                    operation = (lambda: PET.prepare(project)) if kind == "snapshot" else (lambda: PET.package_run(project, run, snapshot))
                    self.expect_error(operation, "recovery-required")
                record = json.loads((state / "package-journal.json").read_bytes())
                self.assertEqual(record["phase"], "allocating")
                stage = state / record["stage"]
                self.assertTrue(stage.is_dir())
                self.assertEqual(list(stage.iterdir()), [])
                self.assertTrue(snapshot.is_file())

    def test_install_bind_failure_preserves_stage_before_target_change(self):
        self.package()
        actual = PET.atomic_json
        def fail_binding(path, value):
            if value.get("stageKind") == "install" and value.get("stageIdentity"):
                raise OSError("injected install binding failure")
            return actual(path, value)
        with patch.object(PET, "atomic_json", side_effect=fail_binding):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        journal = PET.journal_path(self.codex / "pets")
        record = json.loads(journal.read_bytes())
        stage = self.codex / f".{PET.PET_ID}.stage-{record['transaction']}"
        self.assertNotIn("stageIdentity", record)
        self.assertTrue(stage.is_dir())
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())
        self.assertTrue(journal.is_file())

    def test_install_recovery_preserves_stage_that_appears_before_target_removal(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        tx = "e" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": False,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"], "previousAtlasSHA256": None,
                  "previousThemeRevision": None, "previousManifestSHA256": None}
        journal = PET.journal_path(pets)
        PET.atomic_json(journal, record)
        installed = PET.installed_facts
        def create_stage_during_observation(path, project):
            result = installed(path, project)
            if path == target:
                stage.mkdir()
                (stage / "unknown.txt").write_bytes(b"keep")
            return result
        with patch.object(PET, "installed_facts", side_effect=create_stage_during_observation):
            self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
        self.assertEqual((stage / "unknown.txt").read_bytes(), b"keep")
        self.assertTrue(journal.is_file())

    def test_snapshot_recovery_rechecks_stage_after_scan(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "d" * 32)
        stage.mkdir()
        planned = {name: b"synthetic frozen input" for name in PET.stage_file_names("snapshot")}
        (stage / "generation-brief.md").write_bytes(planned["generation-brief.md"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "snapshot", planned, None))
        verified = PET.verify_stage_for_cleanup
        saved = self.root / "saved-snapshot-stage"
        def replace_after_scan(path, data, kinds):
            verified(path, data, kinds)
            stage.rename(saved)
            shutil.copytree(saved, stage)
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=replace_after_scan):
            self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertTrue(stage.is_dir())
        self.assertTrue(saved.is_dir())
        self.assertTrue(journal.is_file())

    def test_install_recovery_rechecks_stage_before_target_removal(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        tx = "e" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        planned = {name: b"synthetic install evidence" for name in PET.stage_file_names("install")}
        (stage / "pet.json").write_bytes(planned["pet.json"])
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": False,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"], "previousAtlasSHA256": None,
                  "previousThemeRevision": None, "previousManifestSHA256": None,
                  "stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                  "stageIdentity": binding["stageIdentity"]}
        journal = PET.journal_path(pets)
        PET.atomic_json(journal, record)
        verified = PET.verify_stage_for_cleanup
        saved = self.root / "saved-stage-after-scan"
        def replace_after_scan(path, data, kinds):
            verified(path, data, kinds)
            stage.rename(saved)
            shutil.copytree(saved, stage)
        with patch.object(PET, "verify_stage_for_cleanup", side_effect=replace_after_scan):
            self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
        self.assertTrue(stage.is_dir())
        self.assertTrue(saved.is_dir())
        self.assertTrue(journal.is_file())

    def test_install_recovery_preserves_identical_stage_replacement_and_target(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        tx = "a" * 32
        stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
        stage.mkdir()
        planned = {name: b"synthetic install evidence" for name in PET.stage_file_names("install")}
        (stage / "pet.json").write_bytes(planned["pet.json"])
        binding = PET.stage_journal(self.project, stage, "install", planned, None)
        record = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                  "transaction": tx, "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": True,
                  "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                  "candidateManifestSHA256": facts["manifestSHA256"], "previousAtlasSHA256": facts["atlasSHA256"],
                  "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                  "stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                  "stageIdentity": binding["stageIdentity"]}
        journal = PET.journal_path(pets)
        PET.atomic_json(journal, record)
        saved = self.root / "saved-install-stage"
        stage.rename(saved)
        shutil.copytree(saved, stage)
        replacement_inode = stage.stat().st_ino
        self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual(stage.stat().st_ino, replacement_inode)
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
        self.assertTrue(saved.is_dir())
        self.assertTrue(journal.is_file())

    def test_snapshot_and_install_stage_collisions_preserve_unknown_objects(self):
        token = "f" * 32
        fixed_uuid = type("Token", (), {"hex": token})()
        (self.project / "style.css").write_bytes(b"changed synthetic theme")
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + token)
        stage.mkdir()
        (stage / "unknown.txt").write_bytes(b"keep snapshot")
        with patch.object(PET.uuid, "uuid4", return_value=fixed_uuid):
            self.expect_error(lambda: PET.prepare(self.project), "recovery-required")
        self.assertEqual((stage / "unknown.txt").read_bytes(), b"keep snapshot")
        self.assertEqual(json.loads((state / "package-journal.json").read_bytes())["phase"], "allocating")

        project = self.root / "other-project"
        shutil.copytree(self.project, project, ignore=shutil.ignore_patterns('.local'))
        self.make_package_for(project, self.atlas_a, "other-run")
        home = self.root / "other-home"
        home.mkdir()
        install_stage = home / f".{PET.PET_ID}.stage-{token}"
        install_stage.mkdir()
        (install_stage / "unknown.txt").write_bytes(b"keep install")
        with patch.object(PET.uuid, "uuid4", return_value=fixed_uuid):
            self.expect_error(lambda: PET.install_package(project, home), "recovery-required")
        self.assertEqual((install_stage / "unknown.txt").read_bytes(), b"keep install")
        self.assertTrue(PET.journal_path(home / "pets").is_file())
        self.assertFalse((home / "pets" / PET.PET_ID).exists())

    def test_package_recovery_preserves_identical_replacement_directory(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "b" * 32)
        stage.mkdir()
        planned = {name: b"synthetic package" for name in PET.stage_file_names("package")}
        (stage / "pet.json").write_bytes(planned["pet.json"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "package", planned, None))
        original = self.root / "original-package-stage"
        stage.rename(original)
        shutil.copytree(original, stage)
        replacement_inode = stage.stat().st_ino
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual(stage.stat().st_ino, replacement_inode)
        self.assertEqual((stage / "pet.json").read_bytes(), planned["pet.json"])
        self.assertTrue(original.is_dir())
        self.assertTrue(journal.is_file())

    def test_snapshot_publish_preserves_stage_replaced_after_fsync(self):
        (self.project / "style.css").write_bytes(b"new synthetic theme")
        state = PET.state_dir(self.project)
        sync = PET.fsync_tree
        saved = self.root / "snapshot-before-swap"
        seen = {}
        def replace_after_sync(stage):
            sync(stage)
            Path(stage).rename(saved)
            shutil.copytree(saved, stage)
            seen["stage"] = Path(stage)
            seen["inode"] = Path(stage).stat().st_ino
        with patch.object(PET, "fsync_tree", side_effect=replace_after_sync):
            self.expect_error(lambda: PET.prepare(self.project), "recovery-required")
        self.assertEqual(seen["stage"].stat().st_ino, seen["inode"])
        self.assertTrue(saved.is_dir())
        self.assertTrue(self.snapshot.is_file())
        self.assertTrue((state / "package-journal.json").is_file())

    def test_install_preserves_previous_target_when_stage_replaced_after_fsync(self):
        self.install()
        target = self.codex / "pets" / PET.PET_ID
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        self.make_run(self.atlas_b)
        self.package()
        sync = PET.fsync_dir
        saved = self.root / "install-before-swap"
        seen = {}
        def replace_after_sync(path):
            sync(path)
            path = Path(path)
            if path.name.startswith(f".{PET.PET_ID}.stage-") and not seen:
                path.rename(saved)
                shutil.copytree(saved, path)
                seen["stage"] = path
                seen["inode"] = path.stat().st_ino
        with patch.object(PET, "fsync_dir", side_effect=replace_after_sync):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertEqual(seen["stage"].stat().st_ino, seen["inode"])
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
        self.assertTrue(saved.is_dir())
        self.assertTrue(PET.journal_path(self.codex / "pets").is_file())

    def test_stage_recovery_preserves_identical_replacement_directory(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "a" * 32)
        stage.mkdir()
        planned = {name: b"synthetic frozen input" for name in PET.stage_file_names("snapshot")}
        (stage / "inputs").mkdir()
        (stage / "inputs/style.css").write_bytes(planned["inputs/style.css"])
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "snapshot", planned, None))
        original = self.root / "original-stage"
        stage.rename(original)
        shutil.copytree(original, stage)
        replacement_inode = stage.stat().st_ino
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertEqual(stage.stat().st_ino, replacement_inode)
        self.assertEqual((stage / "inputs/style.css").read_bytes(), planned["inputs/style.css"])
        self.assertTrue(journal.is_file())
        self.assertTrue(original.is_dir())

    def test_snapshot_staging_interruption_can_be_retried(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "a" * 32)
        stage.mkdir()
        planned = {name: b"synthetic frozen input" for name in PET.stage_file_names("snapshot")}
        (stage / "inputs").mkdir()
        (stage / "inputs/style.css").write_bytes(planned["inputs/style.css"])
        PET.atomic_json(state / "package-journal.json",
                        PET.stage_journal(self.project, stage, "snapshot", planned, None))
        self.assertEqual(PET.prepare(self.project)["themeRevision"], self.rev)
        self.assertFalse(stage.exists())

    def test_recovery_preserves_unknown_backup_entries_and_scan_failures(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "9" * 32
        backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
        shutil.copytree(target, backup)
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": tx, "stagingLocation": "codex-home", "phase": "committed",
                   "hadPrevious": True, "previousAtlasSHA256": facts["atlasSHA256"],
                   "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"]}
        real_scandir = PET.os.scandir
        for case in ("fifo", "empty-directory", "scan-error"):
            with self.subTest(case=case):
                extra = backup / "unknown"
                if case == "fifo":
                    os.mkfifo(extra)
                elif case == "empty-directory":
                    extra.mkdir()
                def fail_backup(path):
                    if Path(path) == backup:
                        raise OSError("injected scan failure")
                    return real_scandir(path)
                PET.atomic_json(PET.journal_path(pets), journal)
                injection = patch.object(PET.os, "scandir", side_effect=fail_backup) if case == "scan-error" else contextlib.nullcontext()
                with injection:
                    self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
                self.assertTrue(backup.is_dir())
                self.assertTrue(target.is_dir())
                self.assertTrue(PET.journal_path(pets).is_file())
                if case == "fifo":
                    self.assertTrue(extra.exists())
                    extra.unlink()
                elif case == "empty-directory":
                    self.assertTrue(extra.is_dir())
                    extra.rmdir()
                PET.journal_path(pets).unlink()

    def test_planned_empty_stage_directories_can_be_cleaned(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "8" * 32)
        (stage / "inputs/assets/private").mkdir(parents=True)
        planned = {name: b"planned synthetic bytes" for name in PET.stage_file_names("snapshot")}
        (stage / "inputs/style.css").write_bytes(planned["inputs/style.css"])
        PET.atomic_json(state / "package-journal.json", PET.stage_journal(self.project, stage, "snapshot", planned, None))
        PET.recover_package_stage(state, self.project)
        self.assertFalse(stage.exists())
        self.assertFalse((state / "package-journal.json").exists())

    def test_recovery_unproven_or_unknown_journals_preserve_target_and_backup(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "d" * 32
        backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
        shutil.copytree(target, backup)
        baseline = {p.name: p.read_bytes() for p in backup.iterdir()}
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": tx, "stagingLocation": "codex-home", "phase": "committed",
                   "hadPrevious": True, "previousAtlasSHA256": facts["atlasSHA256"],
                   "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"]}
        for case in ("legacy-candidate", "legacy-backup", "unknown-phase", "nonboolean", "first-with-backup", "bad-digest"):
            with self.subTest(case=case):
                value = dict(journal)
                if case == "legacy-candidate":
                    value.pop("candidateManifestSHA256")
                elif case == "legacy-backup":
                    value.pop("previousManifestSHA256")
                elif case == "unknown-phase":
                    value["phase"] = "unknown"
                elif case == "nonboolean":
                    value["hadPrevious"] = "yes"
                elif case == "first-with-backup":
                    value["hadPrevious"] = False
                    for key in ("previousAtlasSHA256", "previousThemeRevision", "previousManifestSHA256"):
                        value[key] = None
                else:
                    value["candidateManifestSHA256"] = "not-a-digest"
                PET.atomic_json(PET.journal_path(pets), value)
                self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
                self.assertEqual({p.name: p.read_bytes() for p in backup.iterdir()}, baseline)
                self.assertEqual(PET.installed_facts(target, self.project)["manifestSHA256"], facts["manifestSHA256"])
                self.assertTrue(PET.journal_path(pets).is_file())

    def test_recovery_preserves_same_atlas_backup_with_different_manifest(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "e" * 32
        backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
        shutil.copytree(target, backup)
        manifest = backup / "pet.json"
        altered = json.loads(manifest.read_text())
        altered["description"] = "unknown synthetic modification"
        manifest.write_bytes(PET.json_bytes(altered))
        receipt_path = backup / ".azhou-pet-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["manifestSHA256"] = PET.sha(manifest.read_bytes())
        receipt_path.write_bytes(PET.json_bytes(receipt))
        self.assertNotEqual(PET.installed_facts(backup, self.project)["manifestSHA256"], facts["manifestSHA256"])
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": tx, "stagingLocation": "codex-home", "phase": "committed",
                   "hadPrevious": True, "previousAtlasSHA256": facts["atlasSHA256"],
                   "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"]}
        PET.atomic_json(PET.journal_path(pets), journal)
        self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual(json.loads(manifest.read_text())["description"], "unknown synthetic modification")
        self.assertTrue(PET.journal_path(pets).is_file())
        self.assertTrue(target.is_dir())

    def test_recovery_preserves_same_atlas_backup_with_different_theme(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        tx = "e" * 32
        backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
        shutil.copytree(target, backup)
        receipt_path = backup / ".azhou-pet-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["themeRevision"] = "0" * 64
        receipt_path.write_bytes(PET.json_bytes(receipt))
        self.assertNotEqual(PET.installed_facts(backup, self.project)["themeRevision"], facts["themeRevision"])
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": tx, "stagingLocation": "codex-home", "phase": "committed",
                   "hadPrevious": True, "previousAtlasSHA256": facts["atlasSHA256"],
                   "previousThemeRevision": facts["themeRevision"], "previousManifestSHA256": facts["manifestSHA256"],
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"]}
        PET.atomic_json(PET.journal_path(pets), journal)
        self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual(json.loads(receipt_path.read_text())["themeRevision"], "0" * 64)
        self.assertTrue(PET.journal_path(pets).is_file())
        self.assertTrue(target.is_dir())

    def test_recovery_preserves_candidate_with_different_manifest(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                   "transaction": "f" * 32, "stagingLocation": "codex-home", "phase": "committed",
                   "hadPrevious": False, "previousAtlasSHA256": None, "previousThemeRevision": None,
                   "previousManifestSHA256": None, "candidateAtlasSHA256": facts["atlasSHA256"],
                   "candidateThemeRevision": facts["themeRevision"], "candidateManifestSHA256": "0" * 64}
        PET.atomic_json(PET.journal_path(pets), journal)
        self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
        self.assertEqual(PET.installed_facts(target, self.project)["manifestSHA256"], facts["manifestSHA256"])
        self.assertTrue(PET.journal_path(pets).is_file())

    def test_install_stage_unknown_is_checked_before_target_or_backup_changes(self):
        self.install()
        pets = self.codex / "pets"
        target = pets / PET.PET_ID
        facts = PET.installed_facts(target, self.project)
        for case in ("legacy-target", "bound-extra", "wrong-kind", "committed-backup"):
            with self.subTest(case=case):
                tx = {"legacy-target": "1", "bound-extra": "2", "wrong-kind": "3", "committed-backup": "4"}[case] * 32
                stage = self.codex / f".{PET.PET_ID}.stage-{tx}"
                backup = self.codex / f".{PET.PET_ID}.previous-{tx}"
                stage.mkdir()
                if case != "wrong-kind":
                    (stage / "foreign.txt").write_bytes(b"unknown synthetic bytes")
                if case == "committed-backup":
                    shutil.copytree(target, backup)
                journal = {"owner": PET.OWNER, "projectRoot": str(self.project), "petId": PET.PET_ID,
                           "transaction": tx, "stagingLocation": "codex-home",
                           "phase": "committed" if case == "committed-backup" else "prepared",
                           "hadPrevious": case == "committed-backup",
                           "previousAtlasSHA256": facts["atlasSHA256"] if case == "committed-backup" else None,
                           "previousThemeRevision": facts["themeRevision"] if case == "committed-backup" else None,
                           "previousManifestSHA256": facts["manifestSHA256"] if case == "committed-backup" else None,
                           "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                           "candidateManifestSHA256": facts["manifestSHA256"]}
                if case in ("bound-extra", "wrong-kind"):
                    kind = "snapshot" if case == "wrong-kind" else "install"
                    planned = {name: b"synthetic" for name in PET.stage_file_names(kind)}
                    binding = PET.stage_journal(self.project, stage, kind, planned, None)
                    journal.update({"stageKind": binding["stageKind"], "stageFiles": binding["stageFiles"],
                   "stageIdentity": binding["stageIdentity"]})
                PET.atomic_json(PET.journal_path(pets), journal)
                self.expect_error(lambda: PET.recover_install(pets, self.project), "recovery-required")
                self.assertEqual(PET.installed_facts(target, self.project)["atlasSHA256"], facts["atlasSHA256"])
                self.assertTrue(stage.is_dir())
                if case != "wrong-kind":
                    self.assertEqual((stage / "foreign.txt").read_bytes(), b"unknown synthetic bytes")
                self.assertTrue(PET.journal_path(pets).is_file())
                if case == "committed-backup":
                    self.assertEqual(PET.installed_facts(backup, self.project)["atlasSHA256"], facts["atlasSHA256"])
                    shutil.rmtree(backup)
                shutil.rmtree(stage)
                PET.journal_path(pets).unlink()

    def test_install_stage_partial_file_is_preserved_on_failure(self):
        self.package()
        write = PET.write_new

        def fail_during_file(path, data):
            if ".stage-" in str(path) and Path(path).name == "spritesheet.webp":
                Path(path).write_bytes(b"partial image")
                raise OSError("injected partial install write")
            return write(path, data)

        with patch.object(PET, "write_new", side_effect=fail_during_file):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "recovery-required")
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())
        self.assertTrue(PET.journal_path(self.codex / "pets").is_file())
        stages = list(self.codex.glob(f".{PET.PET_ID}.stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "spritesheet.webp").read_bytes(), b"partial image")

    def test_install_stage_boundary_failure_cleans_owned_subset(self):
        self.package()
        write = PET.write_new

        def fail_before_file(path, data):
            if ".stage-" in str(path) and Path(path).name == "spritesheet.webp":
                raise OSError("injected boundary interruption")
            return write(path, data)

        with patch.object(PET, "write_new", side_effect=fail_before_file):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "install-failed")
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())
        self.assertFalse(PET.journal_path(self.codex / "pets").exists())
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.stage-*")))
        self.assertEqual(PET.install_package(self.project, self.codex)["status"], "installed")

    def test_install_rechecks_package_bytes_before_journaling(self):
        self.package()
        manifest = PET.selected_package(self.project) / "pet.json"
        read = PET.read
        calls = 0

        def change_at_capture(path):
            nonlocal calls
            data = read(path)
            if Path(path) == manifest:
                calls += 1
                if calls == 2:
                    return b"changed synthetic manifest"
            return data

        with patch.object(PET, "read", side_effect=change_at_capture):
            self.expect_error(lambda: PET.install_package(self.project, self.codex), "source-conflict")
        self.assertEqual(calls, 2)
        self.assertFalse((self.codex / "pets" / PET.PET_ID).exists())
        self.assertFalse(PET.journal_path(self.codex / "pets").exists())
        self.assertFalse(list(self.codex.glob(f".{PET.PET_ID}.stage-*")))

    def test_stage_recovery_preserves_unbound_unknown_and_changed_contents(self):
        for case in ("legacy", "extra-file", "extra-directory", "symlink", "fifo", "changed", "bad-digest", "scan-error"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir=self.root) as temp:
                state = Path(temp)
                stage = state / (".stage-" + "b" * 32)
                stage.mkdir()
                planned = {name: b"expected synthetic bytes" for name in PET.stage_file_names("snapshot")}
                journal = PET.stage_journal(self.project, stage, "snapshot", planned, None)
                if case == "legacy":
                    journal.pop("stageKind")
                    journal.pop("stageFiles")
                    (stage / "foreign.txt").write_bytes(b"unknown")
                elif case == "extra-file":
                    (stage / "foreign.txt").write_bytes(b"unknown")
                elif case == "extra-directory":
                    (stage / "foreign").mkdir()
                elif case == "symlink":
                    (stage / "generation-brief.md").symlink_to(self.project / "style.css")
                elif case == "fifo":
                    os.mkfifo(stage / "foreign")
                elif case == "changed":
                    (stage / "generation-brief.md").write_bytes(b"not the recorded content")
                elif case == "bad-digest":
                    journal["stageFiles"]["generation-brief.md"] = "not-a-digest"
                PET.atomic_json(state / "package-journal.json", journal)
                failure = patch.object(PET.os, "scandir", side_effect=OSError("injected scan failure")) if case == "scan-error" else contextlib.nullcontext()
                with failure, self.assertRaises(PET.PetError) as raised:
                    PET.recover_package_stage(state, self.project)
                self.assertEqual(raised.exception.code, "recovery-required")
                self.assertTrue(stage.is_dir())
                self.assertTrue((state / "package-journal.json").is_file())
                if case == "legacy":
                    self.assertEqual((stage / "foreign.txt").read_bytes(), b"unknown")

    def test_snapshot_interrupted_at_file_boundary_cleans_and_retries(self):
        (self.project / "style.css").write_bytes(b"new synthetic theme")
        state = PET.state_dir(self.project)
        write = PET.write_new

        def fail_before_file(path, data):
            if ".stage-" in str(path) and Path(path).name == "style.css":
                raise OSError("injected boundary interruption")
            return write(path, data)

        with patch.object(PET, "write_new", side_effect=fail_before_file):
            with self.assertRaisesRegex(OSError, "injected boundary"):
                PET.prepare(self.project)
        self.assertTrue(self.snapshot.is_file())
        self.assertFalse((state / "package-journal.json").exists())
        self.assertFalse(list(state.glob(".stage-*")))
        self.assertNotEqual(PET.prepare(self.project)["themeRevision"], self.rev)

    def test_snapshot_partial_file_is_preserved_for_review(self):
        (self.project / "style.css").write_bytes(b"new synthetic theme")
        state = PET.state_dir(self.project)
        write = PET.write_new

        def fail_during_file(path, data):
            if ".stage-" in str(path) and Path(path).name == "style.css":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b"partial")
                raise OSError("injected partial write")
            return write(path, data)

        with patch.object(PET, "write_new", side_effect=fail_during_file):
            with self.assertRaises(PET.PetError) as raised:
                PET.prepare(self.project)
        self.assertEqual(raised.exception.code, "recovery-required")
        self.assertTrue(self.snapshot.is_file())
        self.assertTrue((state / "package-journal.json").is_file())
        stages = list(state.glob(".stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "inputs/style.css").read_bytes(), b"partial")

    def test_legacy_absent_stage_can_clear_but_empty_stage_is_preserved(self):
        for exists in (False, True):
            with self.subTest(exists=exists), tempfile.TemporaryDirectory(dir=self.root) as temp:
                state = Path(temp)
                stage = state / (".stage-" + "c" * 32)
                if exists:
                    stage.mkdir()
                journal = state / "package-journal.json"
                PET.atomic_json(journal, {"owner": PET.OWNER, "petId": PET.PET_ID,
                                "projectRoot": str(self.project), "stage": stage.name})
                if exists:
                    self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
                    self.assertTrue(stage.is_dir())
                    self.assertTrue(journal.is_file())
                else:
                    PET.recover_package_stage(state, self.project)
                    self.assertFalse(journal.exists())

    def test_bound_but_empty_stage_is_preserved(self):
        state = PET.state_dir(self.project)
        stage = state / (".stage-" + "e" * 32)
        stage.mkdir()
        planned = {name: b"synthetic bytes" for name in PET.stage_file_names("snapshot")}
        journal = state / "package-journal.json"
        PET.atomic_json(journal, PET.stage_journal(self.project, stage, "snapshot", planned, None))
        self.expect_error(lambda: PET.recover_package_stage(state, self.project), "recovery-required")
        self.assertTrue(stage.is_dir())
        self.assertTrue(journal.is_file())

    def test_snapshot_write_failure_preserves_previous_snapshot_and_can_retry(self):
        (self.project / "style.css").write_bytes(b"changed synthetic theme")
        state = PET.state_dir(self.project)
        with patch.object(PET, "fsync_tree", side_effect=OSError("injected sync failure")):
            with self.assertRaisesRegex(OSError, "injected sync failure"):
                PET.prepare(self.project)
        self.assertTrue(self.snapshot.is_file())
        self.assertFalse((state / "package-journal.json").exists())
        self.assertFalse(list(state.glob(".stage-*")))
        self.assertNotEqual(PET.prepare(self.project)["themeRevision"], self.rev)

    def test_package_write_failure_keeps_selected_package_and_can_retry(self):
        self.package()
        state = PET.state_dir(self.project)
        previous = PET.selected_package(self.project)
        self.make_run(self.atlas_b)
        with patch.object(PET, "fsync_tree", side_effect=OSError("injected sync failure")):
            with self.assertRaisesRegex(OSError, "injected sync failure"):
                self.package()
        self.assertEqual(PET.selected_package(self.project), previous)
        self.assertTrue(previous.is_dir())
        self.assertFalse((state / "package-journal.json").exists())
        self.assertFalse(list(state.glob(".stage-*")))
        self.package()
        self.assertNotEqual(PET.selected_package(self.project), previous)


if __name__ == "__main__":
    unittest.main(verbosity=2)

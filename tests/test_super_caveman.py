from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "super-caveman" / "scripts" / "compression_guard.py"
SPEC = importlib.util.spec_from_file_location("super_caveman_compression_guard", SCRIPT)
assert SPEC and SPEC.loader
GUARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GUARD
SPEC.loader.exec_module(GUARD)


ORIGINAL = """---
title: Notes
---
# Notes

You should always run `python3 -m unittest` before changing /srv/app/config.md.

- Parent item with unnecessary filler.
  - Child item stays nested.

| Item | Value |
|---|---|
| Docs | https://example.com/docs |

```python
print("keep exactly")
```
"""

CANDIDATE = """---
title: Notes
---
# Notes

Run `python3 -m unittest` before changing /srv/app/config.md.

- Parent item, no filler.
  - Child item stays nested.

| Item | Value |
|---|---|
| Docs | https://example.com/docs |

```python
print("keep exactly")
```
"""


class SuperCavemanCompressionGuardTest(unittest.TestCase):
    def test_preflight_accepts_prose_and_rejects_sensitive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / "notes.md"
            notes.write_text(ORIGINAL, encoding="utf-8")
            info = GUARD.preflight(notes)
            self.assertTrue(info["allowed"])
            self.assertEqual("natural_language", info["file_type"])

            secrets = root / "secrets.md"
            secrets.write_text("not actual credentials\n", encoding="utf-8")
            with self.assertRaisesRegex(GUARD.GuardError, "looks sensitive"):
                GUARD.preflight(secrets)

    def test_validation_preserves_structural_tokens(self) -> None:
        result = GUARD.validate_text(ORIGINAL, CANDIDATE)
        self.assertTrue(result.valid, result.as_dict())

        broken = CANDIDATE.replace('print("keep exactly")', 'print("changed")')
        result = GUARD.validate_text(ORIGINAL, broken)
        self.assertFalse(result.valid)
        self.assertIn("fenced code blocks mismatch", result.errors)

    def test_validation_preserves_semantic_tokens(self) -> None:
        original = (
            "# Release\n\n"
            "Run npm test for OAuth2 through parseToken on 2026-08-24. "
            "Keep v1.2.3, ENOENT, and 42 retries.\n"
        )
        replacements = {
            "npm test": "npm run build",
            "OAuth2": "OAuth3",
            "parseToken": "parseSession",
            "2026-08-24": "2026-08-25",
            "v1.2.3": "v2.0.0",
            "ENOENT": "EACCES",
            "42": "41",
        }
        for old, new in replacements.items():
            with self.subTest(token=old):
                result = GUARD.validate_text(original, original.replace(old, new))
                self.assertFalse(result.valid)
                self.assertIn("protected tokens mismatch", result.errors)

        path_result = GUARD.validate_text(
            "Read notes.md before editing.\n",
            "Read guide.md before editing.\n",
        )
        self.assertFalse(path_result.valid)
        self.assertIn("file paths mismatch", path_result.errors)

        filename_result = GUARD.validate_text(
            "Run Makefile before release.\n",
            "Run Dockerfile before release.\n",
        )
        self.assertFalse(filename_result.valid)
        self.assertIn("file paths mismatch", filename_result.errors)

        unclosed = "# Notes\n\n```text\nkeep this\n"
        result = GUARD.validate_text(unclosed, unclosed.replace("keep this", "changed"))
        self.assertFalse(result.valid)
        self.assertIn("fenced code blocks mismatch", result.errors)

    def test_validation_preserves_blockquoted_fenced_code(self) -> None:
        cases = (
            (
                "> ```text\n> keep this exact\n> ```\n\nLong prose.\n",
                "> ```text\n> changed code\n> ```\n\nShort prose.\n",
            ),
            (
                "> > ~~~python\n> > keep this exact\n> > ~~~\n\nLong prose.\n",
                "> > ~~~python\n> > changed code\n> > ~~~\n\nShort prose.\n",
            ),
        )
        for original, candidate in cases:
            with self.subTest(original=original):
                result = GUARD.validate_text(original, candidate)
                self.assertFalse(result.valid, result.as_dict())
                self.assertIn("fenced code blocks mismatch", result.errors)

    def test_validation_preserves_encoding_markers(self) -> None:
        crlf = "plain prose\r\nsecond line\r\n"
        result = GUARD.validate_text(crlf, "shorter prose\n")
        self.assertFalse(result.valid)
        self.assertIn("newline style mismatch", result.errors)

        bom = "\ufeffplain prose\n"
        result = GUARD.validate_text(bom, "shorter prose\n")
        self.assertFalse(result.valid)
        self.assertIn("UTF-8 BOM mismatch", result.errors)

    def test_validation_preserves_frontmatter_after_utf8_bom(self) -> None:
        original = "\ufeff---\ntitle: Alpha\n---\n# Notes\n\nLong prose here.\n"
        candidate = "\ufeff---\ntitle: Beta\n---\n# Notes\n\nShort prose.\n"

        result = GUARD.validate_text(original, candidate)

        self.assertFalse(result.valid)
        self.assertIn("YAML frontmatter mismatch", result.errors)

    def test_validation_preserves_indented_code_blocks(self) -> None:
        cases = (
            (
                "# Notes\n\n    keep this exact\n    and this line\n\nLong prose.\n",
                "# Notes\n\n    changed code\n    and this line\n\nShort prose.\n",
            ),
            (
                "# Notes\n\n\tkeep this exact\n\tand this line\n\nLong prose.\n",
                "# Notes\n\n\tkeep this exact\n\tchanged code\n\nShort prose.\n",
            ),
            (
                "- Item\n\n      keep this exact\n      and this line\n\nLong prose.\n",
                "- Item\n\n      changed code\n      and this line\n\nShort prose.\n",
            ),
            (
                ">     keep this exact\n>     and this line\n\nLong prose.\n",
                ">     changed code\n>     and this line\n\nShort prose.\n",
            ),
            (
                "> - Item\n>       keep this exact\n>       and this line\n\nLong prose.\n",
                "> - Item\n>       changed code\n>       and this line\n\nShort prose.\n",
            ),
            (
                "> > - Nested\n> >       keep this exact\n> >       and this line\n\nLong prose.\n",
                "> > - Nested\n> >       changed code\n> >       and this line\n\nShort prose.\n",
            ),
        )
        for original, candidate in cases:
            with self.subTest(indentation=repr(original.splitlines()[2][:4])):
                result = GUARD.validate_text(original, candidate)
                self.assertFalse(result.valid)
                self.assertIn("indented code blocks mismatch", result.errors)

    def test_validation_allows_compressing_ordinary_list_continuation(self) -> None:
        original = "- Item\n\n    Long continuation prose with filler.\n"
        candidate = "- Item\n\n    Short continuation.\n"

        result = GUARD.validate_text(original, candidate)

        self.assertTrue(result.valid, result.as_dict())

    def test_validation_allows_compressing_ordinary_quoted_continuations(self) -> None:
        cases = (
            ("> Long quoted prose with filler.\n", "> Short quote.\n"),
            ("> - Item\n>   Long continuation prose with filler.\n", "> - Item\n>   Short continuation.\n"),
        )

        for original, candidate in cases:
            with self.subTest(original=original):
                result = GUARD.validate_text(original, candidate)
                self.assertTrue(result.valid, result.as_dict())

    def test_validation_preserves_each_list_level(self) -> None:
        original = "- A\n- B\n  - C\n"
        candidate = "- A\n  - B\n  - C\n"
        result = GUARD.validate_text(original, candidate)
        self.assertFalse(result.valid)
        self.assertIn("list hierarchy mismatch", result.errors)

    def test_apply_and_restore_are_hash_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}):
                applied = GUARD.apply_candidate(source, candidate)
                self.assertEqual("applied", applied["status"])
                self.assertEqual("super-caveman.compression.v1", applied["schema"])
                self.assertEqual(CANDIDATE, source.read_text(encoding="utf-8"))
                self.assertTrue(Path(applied["backup"]).is_file())
                self.assertTrue(Path(applied["receipt"]).is_file())

                restored = GUARD.restore_source(source)
                self.assertEqual("restored", restored["status"])
                self.assertEqual("super-caveman.compression.v1", restored["schema"])
                self.assertEqual(ORIGINAL, source.read_text(encoding="utf-8"))
                self.assertTrue(Path(applied["backup"]).is_file())
                self.assertTrue(Path(applied["receipt"]).is_file())
                self.assertEqual(2, len(restored["handoffs"]))

                with self.assertRaisesRegex(GUARD.GuardError, "explicit finalize"):
                    GUARD.apply_candidate(source, candidate)
                finalized = GUARD.finalize_state(source)
                self.assertEqual("finalized", finalized["status"])
                self.assertEqual(2, finalized["removed_handoffs"])
                reapplied = GUARD.apply_candidate(source, candidate)
                self.assertEqual("applied", reapplied["status"])
                self.assertTrue(reapplied["retired_previous_state"])
                self.assertEqual(CANDIDATE, source.read_text(encoding="utf-8"))

    def test_apply_and_restore_preserve_crlf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            original_bytes = ORIGINAL.replace("\n", "\r\n").encode("utf-8")
            candidate_bytes = CANDIDATE.replace("\n", "\r\n").encode("utf-8")
            source.write_bytes(original_bytes)
            candidate.write_bytes(candidate_bytes)

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                self.assertEqual(candidate_bytes, source.read_bytes())
                self.assertEqual(original_bytes, Path(applied["backup"]).read_bytes())

                restored = GUARD.restore_source(source)
                self.assertEqual("restored", restored["status"])
                self.assertEqual(original_bytes, source.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not portable to Windows")
    def test_backup_state_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                self.assertEqual(0o700, Path(applied["backup"]).parent.stat().st_mode & 0o777)
                self.assertEqual(0o600, Path(applied["backup"]).stat().st_mode & 0o777)
                self.assertEqual(0o600, Path(applied["receipt"]).stat().st_mode & 0o777)

    def test_candidate_size_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text("# Notes\n\n" + "x" * GUARD.MAX_FILE_SIZE, encoding="utf-8")
            with self.assertRaisesRegex(GUARD.GuardError, "candidate exceeds"):
                GUARD.validate_files(source, candidate)

    def test_overlapping_operation_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with GUARD.operation_lock(source):
                    with self.assertRaisesRegex(GUARD.GuardError, "operation already in progress"):
                        GUARD.apply_candidate(source, candidate)

    def test_apply_refuses_source_change_after_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            real_write_receipt = GUARD.write_json_exclusive

            def write_receipt_then_change(path: Path, payload: dict[str, object]) -> None:
                real_write_receipt(path, payload)
                source.write_text("external newer work\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with mock.patch.object(GUARD, "write_json_exclusive", side_effect=write_receipt_then_change):
                    with self.assertRaisesRegex(GUARD.GuardError, "changed before apply"):
                        GUARD.apply_candidate(source, candidate)
                backup, receipt = GUARD.backup_paths(source.resolve())
                self.assertEqual("external newer work\n", source.read_text(encoding="utf-8"))
                self.assertTrue(backup.is_file())
                self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_apply_does_not_overwrite_change_at_install_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            real_replace = os.replace
            resolved_source = source.resolve()

            def change_before_handoff(old: object, new: object) -> None:
                if Path(old).resolve() == resolved_source:
                    source.write_text("external newer work\n", encoding="utf-8")
                real_replace(old, new)

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with mock.patch.object(GUARD.os, "replace", side_effect=change_before_handoff):
                    with self.assertRaisesRegex(GUARD.GuardError, "changed at apply checkpoint"):
                        GUARD.apply_candidate(source, candidate)
                backup, receipt = GUARD.backup_paths(source.resolve())
                self.assertEqual("external newer work\n", source.read_text(encoding="utf-8"))
                self.assertTrue(backup.is_file())
                self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_apply_does_not_overwrite_recreated_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            real_link = os.link
            resolved_source = source.resolve()

            def recreate_before_link(old: object, new: object) -> None:
                if Path(new).resolve() == resolved_source:
                    source.write_text("external recreated work\n", encoding="utf-8")
                real_link(old, new)

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with mock.patch.object(GUARD.os, "link", side_effect=recreate_before_link):
                    with self.assertRaisesRegex(GUARD.GuardError, "path recreated during apply"):
                        GUARD.apply_candidate(source, candidate)
                backup, receipt = GUARD.backup_paths(source.resolve())
                self.assertEqual("external recreated work\n", source.read_text(encoding="utf-8"))
                self.assertTrue(backup.is_file())
                self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_apply_preserves_second_writer_during_checkpoint_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            real_replace = os.replace
            real_link = os.link
            resolved_source = source.resolve()
            inserted_second_write = False

            def first_change_before_handoff(old: object, new: object) -> None:
                if Path(old).resolve() == resolved_source:
                    source.write_text("external first work\n", encoding="utf-8")
                real_replace(old, new)

            def second_change_before_rollback(old: object, new: object) -> None:
                nonlocal inserted_second_write
                if Path(new).resolve() == resolved_source and not inserted_second_write:
                    inserted_second_write = True
                    source.write_text("external second work\n", encoding="utf-8")
                real_link(old, new)

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with mock.patch.object(GUARD.os, "replace", side_effect=first_change_before_handoff):
                    with mock.patch.object(GUARD.os, "link", side_effect=second_change_before_rollback):
                        with self.assertRaisesRegex(GUARD.GuardError, "displaced content preserved"):
                            GUARD.apply_candidate(source, candidate)
                self.assertEqual("external second work\n", source.read_text(encoding="utf-8"))
                handoffs = list(root.glob(".notes.md.super-caveman-handoff-*"))
                self.assertEqual(1, len(handoffs))
                self.assertEqual("external first work\n", handoffs[0].read_text(encoding="utf-8"))
                backup, receipt = GUARD.backup_paths(source.resolve())
                self.assertEqual(ORIGINAL, backup.read_text(encoding="utf-8"))
                self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_apply_retains_recovery_after_post_install_failure(self) -> None:
        for failure_call in (2,):
            with self.subTest(fsync_call=failure_call), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "notes.md"
                candidate = root / "candidate.md"
                source.write_text(ORIGINAL, encoding="utf-8")
                candidate.write_text(CANDIDATE, encoding="utf-8")
                real_fsync_directory = GUARD.fsync_directory
                calls = 0

                def fail_selected_fsync(path: Path) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == failure_call:
                        raise OSError("injected directory fsync failure")
                    real_fsync_directory(path)

                with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                    with mock.patch.object(GUARD, "fsync_directory", side_effect=fail_selected_fsync):
                        with self.assertRaisesRegex(Exception, "injected directory fsync failure"):
                            GUARD.apply_candidate(source, candidate)
                    backup, receipt = GUARD.backup_paths(source.resolve())
                    self.assertEqual(CANDIDATE, source.read_text(encoding="utf-8"))
                    self.assertEqual(ORIGINAL, backup.read_text(encoding="utf-8"))
                    self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_hard_link_probe_fails_before_source_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                with mock.patch.object(GUARD.os, "link", side_effect=OSError("hard links unsupported")):
                    with self.assertRaisesRegex(OSError, "hard links unsupported"):
                        GUARD.apply_candidate(source, candidate)
                backup, receipt = GUARD.backup_paths(source.resolve())
                self.assertEqual(ORIGINAL, source.read_text(encoding="utf-8"))
                self.assertFalse(backup.exists())
                self.assertFalse(receipt.exists())
                self.assertEqual([], list(root.glob(".notes.md.super-caveman-handoff-*")))

    def test_late_open_descriptor_write_is_retained_and_blocks_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            real_link = os.link
            resolved_source = source.resolve()

            with source.open("r+", encoding="utf-8", newline="") as stale_writer:
                def write_old_inode_after_install(old: object, new: object) -> None:
                    real_link(old, new)
                    if Path(new).resolve() == resolved_source:
                        stale_writer.seek(0)
                        stale_writer.write("external late inode work\n")
                        stale_writer.truncate()
                        stale_writer.flush()
                        os.fsync(stale_writer.fileno())

                with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                    with mock.patch.object(GUARD.os, "link", side_effect=write_old_inode_after_install):
                        applied = GUARD.apply_candidate(source, candidate)
                    self.assertEqual(CANDIDATE, source.read_text(encoding="utf-8"))
                    handoff = Path(applied["handoffs"][0]["path"])
                    self.assertEqual("external late inode work\n", handoff.read_text(encoding="utf-8"))
                    with self.assertRaisesRegex(GUARD.GuardError, "handoff changed after checkpoint"):
                        GUARD.restore_source(source)

    def test_restore_recovers_completed_source_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                source.write_text(ORIGINAL, encoding="utf-8")
                restored = GUARD.restore_source(source)
                self.assertEqual("restored", restored["status"])
                self.assertTrue(restored["recovered"])
                self.assertTrue(Path(applied["backup"]).is_file())
                self.assertTrue(Path(applied["receipt"]).is_file())

    def test_restore_refuses_newer_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                GUARD.apply_candidate(source, candidate)
                source.write_text(CANDIDATE + "newer work\n", encoding="utf-8")
                with self.assertRaisesRegex(GUARD.GuardError, "changed after compression"):
                    GUARD.restore_source(source)

    def test_restore_retains_external_change_at_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                real_replace = os.replace
                resolved_source = source.resolve()

                def change_before_handoff(old: object, new: object) -> None:
                    if Path(old).resolve() == resolved_source:
                        source.write_text("external restore-race work\n", encoding="utf-8")
                    real_replace(old, new)

                with mock.patch.object(GUARD.os, "replace", side_effect=change_before_handoff):
                    with self.assertRaisesRegex(GUARD.GuardError, "changed at apply checkpoint"):
                        GUARD.restore_source(source)
                self.assertEqual("external restore-race work\n", source.read_text(encoding="utf-8"))
                receipt = Path(applied["receipt"])
                self.assertEqual("conflict", json.loads(receipt.read_text(encoding="utf-8"))["status"])

    def test_restore_probe_failure_keeps_receipt_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                with mock.patch.object(GUARD.os, "link", side_effect=OSError("hard links unsupported")):
                    with self.assertRaisesRegex(OSError, "hard links unsupported"):
                        GUARD.restore_source(source)
                receipt = Path(applied["receipt"])
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual("applied", payload["status"])
                self.assertEqual(1, len(payload["handoffs"]))
                self.assertTrue(Path(payload["handoffs"][0]["path"]).is_file())
                self.assertEqual(CANDIDATE, source.read_text(encoding="utf-8"))
                self.assertEqual("restored", GUARD.restore_source(source)["status"])

    def test_late_restore_inode_write_marks_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                real_link = os.link
                resolved_source = source.resolve()
                with source.open("r+", encoding="utf-8", newline="") as stale_writer:
                    def write_old_inode_after_restore(old: object, new: object) -> None:
                        real_link(old, new)
                        if Path(new).resolve() == resolved_source:
                            stale_writer.seek(0)
                            stale_writer.write("external late restore work\n")
                            stale_writer.truncate()
                            stale_writer.flush()
                            os.fsync(stale_writer.fileno())

                    with mock.patch.object(GUARD.os, "link", side_effect=write_old_inode_after_restore):
                        with self.assertRaisesRegex(GUARD.GuardError, "handoff changed after checkpoint"):
                            GUARD.restore_source(source)
                receipt = Path(applied["receipt"])
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual("conflict", payload["status"])
                self.assertEqual(ORIGINAL, source.read_text(encoding="utf-8"))
                self.assertEqual("external late restore work\n", Path(payload["handoffs"][-1]["path"]).read_text(encoding="utf-8"))

    def test_finalize_resumes_after_cleanup_fsync_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")

            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                applied = GUARD.apply_candidate(source, candidate)
                GUARD.restore_source(source)
                with mock.patch.object(GUARD, "fsync_directory", side_effect=OSError("injected finalize fsync failure")):
                    with self.assertRaisesRegex(OSError, "injected finalize fsync failure"):
                        GUARD.finalize_state(source)
                receipt = Path(applied["receipt"])
                self.assertEqual("finalizing", json.loads(receipt.read_text(encoding="utf-8"))["status"])
                finalized = GUARD.finalize_state(source)
                self.assertEqual("finalized", finalized["status"])
                self.assertEqual("finalized", GUARD.finalize_state(source)["status"])
                source.write_text(
                    ORIGINAL.replace("unnecessary filler", "new unnecessary filler"),
                    encoding="utf-8",
                )
                candidate.write_text(
                    CANDIDATE.replace("no filler", "new, no filler"),
                    encoding="utf-8",
                )
                self.assertEqual("finalized", GUARD.finalize_state(source)["status"])
                reapplied = GUARD.apply_candidate(source, candidate)
                self.assertTrue(reapplied["retired_previous_state"])

    def test_cli_json_validation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            candidate = root / "candidate.md"
            source.write_text(ORIGINAL, encoding="utf-8")
            candidate.write_text(CANDIDATE, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", str(source), str(candidate), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertEqual(
                {"valid": True, "errors": [], "warnings": []},
                json.loads(completed.stdout),
            )


if __name__ == "__main__":
    unittest.main()

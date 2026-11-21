import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import approved_startup_video as subject

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

class ApprovedStartupVideoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "package"
        self.private = self.root / "assets" / "private"
        self.private.mkdir(parents=True)
        self.clip = b"fixture bytes, not a decoded clip"
        self.manifest = self.private / subject.MANIFEST_NAME
        self.video = self.private / subject.CLIP_NAME
        self.video.write_bytes(self.clip)
        self.fields = {"schema": 1, "clipSHA256": digest(self.clip), "byteLength": len(self.clip),
                       "holdMs": 700, "fadeStartMs": 900, "fadeEndMs": 1100}
        self.raw = self.save(self.fields)

    def save(self, fields):
        raw = (json.dumps(fields, ensure_ascii=False, indent=2) + "\n").encode()
        self.manifest.write_bytes(raw)
        return raw

    def read(self, raw=None):
        return subject.read_approved_startup_video(self.root, digest(self.raw if raw is None else raw))

    def test_unset_never_opens_any_file(self):
        with patch.object(subject.os, "open", side_effect=AssertionError("unexpected filesystem probe")):
            self.assertIsNone(subject.read_approved_startup_video(self.root / "missing", None))

    def test_validated_snapshot_keeps_exact_manifest_and_clip_after_source_change(self):
        sealed = self.read()
        self.manifest.write_bytes(b"replaced manifest")
        self.video.write_bytes(b"replaced video")
        self.assertEqual(sealed.manifest_bytes, self.raw)
        self.assertEqual(sealed.clip_bytes, self.clip)
        self.assertEqual(sealed.manifest_sha256, digest(sealed.manifest_bytes))
        self.assertEqual(sealed.clip_sha256, digest(sealed.clip_bytes))

    def test_original_manifest_pin_rejects_modified_manifest(self):
        self.manifest.write_bytes(self.raw + b" ")
        with self.assertRaisesRegex(subject.StartupVideoInputError, "manifest digest"):
            self.read()

    def test_clip_with_same_size_but_different_digest_rejected(self):
        self.video.write_bytes(b"x" * len(self.clip))
        with self.assertRaisesRegex(subject.StartupVideoInputError, "clip digest"):
            self.read()

    def test_clip_symlink_and_fifo_are_rejected(self):
        other = self.private / "other.mp4"
        other.write_bytes(self.clip)
        self.video.unlink()
        self.video.symlink_to(other.name)
        with self.assertRaises(subject.StartupVideoInputError):
            self.read()
        self.video.unlink()
        os.mkfifo(self.video)
        with self.assertRaisesRegex(subject.StartupVideoInputError, "bounded regular file"):
            self.read()

    def test_private_directory_symlink_rejected(self):
        alternate = self.private.with_name("alt")
        self.private.rename(alternate)
        self.private.symlink_to(alternate.name, target_is_directory=True)
        with self.assertRaises(subject.StartupVideoInputError):
            self.read()

    def test_real_same_bytes_rename_during_read_is_rejected(self):
        original_open = os.open
        swap = self.private / "swap.mp4"
        swap.write_bytes(self.clip)
        # Keep capability checks bound to genuine platform primitives, but inject
        # a deterministic replacement after the production open and before fstat.
        def open_and_swap(path, flags, *, dir_fd=None):
            fd = original_open(path, flags, dir_fd=dir_fd)
            if path == subject.CLIP_NAME:
                swap.replace(self.video)
            return fd
        valid_capabilities = os.supports_dir_fd | {open_and_swap}
        with patch.object(subject.os, "open", open_and_swap), patch.object(subject.os, "supports_dir_fd", valid_capabilities):
            with self.assertRaisesRegex(subject.StartupVideoInputError, "changed during verification"):
                self.read()

    def test_private_directory_replacement_after_read_rejected(self):
        original_reader = subject._read_at
        changed = self.private.with_name("parked")
        def read_and_replace(directory, name, limit):
            data = original_reader(directory, name, limit)
            if name == subject.CLIP_NAME:
                self.private.rename(changed)
                self.private.mkdir()
            return data
        with patch.object(subject, "_read_at", read_and_replace):
            with self.assertRaisesRegex(subject.StartupVideoInputError, "directory changed"):
                self.read()

    def test_duplicate_extra_boolean_and_bad_timeline_are_rejected(self):
        cases = [self.raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1'),
                 json.dumps({**self.fields, "url": "http://example.invalid/test"}).encode(),
                 json.dumps({**self.fields, "schema": True}).encode(),
                 json.dumps({**self.fields, "holdMs": 1100}).encode()]
        for raw in cases:
            with self.subTest(raw=raw):
                self.manifest.write_bytes(raw)
                with self.assertRaises(subject.StartupVideoInputError):
                    self.read(raw)

if __name__ == "__main__":
    unittest.main()

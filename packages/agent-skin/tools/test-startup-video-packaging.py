import hashlib
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
TOOLS = HERE
M = runpy.run_path(str(TOOLS / "verify-artifacts.py"))
G = M["write_marker"].__globals__
ARTIFACTS = "Contents/Resources"
PINS = M["NATIVE_STARTUP_VIDEO_INPUTS"]

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

class NativeVideoPackaging(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.bundle = self.root / ".build" / "azhou-stage.x" / "azhou-payload"
        self.resources = self.bundle / ARTIFACTS
        self.resources.mkdir(parents=True)
        self.directory = self.resources / M["NATIVE_STARTUP_VIDEO_DIR"]
        self.private = self.root / "assets/private"
        self.private.mkdir(parents=True)
        (self.root / "tools").mkdir()
        shutil.copyfile(TOOLS / "approved_startup_video.py", self.root / "tools/approved_startup_video.py")
        self.clip = b"test pinned private bytes"
        self.raw = json.dumps(dict(schema=1, clipSHA256=sha(self.clip), byteLength=len(self.clip),
                                   holdMs=300, fadeStartMs=600, fadeEndMs=900), indent=2).encode()
        (self.root / PINS["manifest.json"]).write_bytes(self.raw)
        (self.root / PINS["clip.mp4"]).write_bytes(self.clip)
        self.pin = sha(self.raw)
        root = patch.dict(G, ROOT=self.root)
        root.start()
        self.addCleanup(root.stop)

    def stage(self):
        return M["stage_native_startup_video"](self.bundle, self.pin)

    def verify(self, inputs):
        return M["verify_native_startup_video_outputs"](self.resources, inputs)

    def test_default_no_probe_even_with_private_files(self):
        with patch.dict(G, _startup_video_verifier=lambda: self.fail("opened capsule")):
            self.assertEqual(M["stage_native_startup_video"](self.bundle, None), {})
            self.assertEqual(self.verify({}), {})
        self.assertFalse(self.directory.exists())

    def test_bundle_pair_remains_self_contained_when_private_inputs_are_removed(self):
        pins = self.stage()
        shutil.rmtree(self.private)
        self.assertEqual({x.name for x in self.directory.iterdir()}, set(PINS))
        self.assertEqual((self.directory / "manifest.json").read_bytes(), self.raw)
        self.assertEqual((self.directory / "clip.mp4").read_bytes(), self.clip)
        self.assertEqual(self.verify(pins),
                         {"startup/native-video/manifest.json": self.pin,
                          "startup/native-video/clip.mp4": sha(self.clip)})

    def test_wrong_pair_extra_and_unmarked_outputs_rejected(self):
        pins = self.stage()
        with self.assertRaisesRegex(RuntimeError, "unapproved"):
            self.verify({})
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self.verify({PINS["manifest.json"]: self.pin})
        with self.assertRaisesRegex(RuntimeError, "build marker"):
            self.verify({**pins, PINS["clip.mp4"]: "a" * 64})
        extra = self.directory / "third"
        extra.touch()
        with self.assertRaisesRegex(RuntimeError, "output set"):
            self.verify(pins)
        extra.unlink()
        (self.directory / "clip.mp4").write_bytes(b"x" * len(self.clip))
        with self.assertRaisesRegex(ValueError, "clip digest"):
            self.verify(pins)

    def test_stage_does_not_overwrite_existing_reserved_entry(self):
        pins = self.stage()
        with self.assertRaises(FileExistsError):
            self.stage()
        self.assertIsNotNone(self.verify(pins))

    def test_publish_forwards_explicit_video_approval_to_input_check(self):
        class StopBeforePublish(Exception):
            pass
        calls = []
        def check(candidate, *, approved_video_manifest_sha256=None):
            calls.append((candidate, approved_video_manifest_sha256))
            raise StopBeforePublish
        with patch.dict(G, verify_product=lambda path: True, check_inputs=check):
            with self.assertRaises(StopBeforePublish):
                M["publish"](self.bundle, approved_video_manifest_sha256=self.pin)
        self.assertEqual(calls, [(self.bundle, self.pin)])

if __name__ == "__main__":
    unittest.main()

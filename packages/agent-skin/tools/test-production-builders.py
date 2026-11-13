#!/usr/bin/env python3
"""Boundary tests for the private asset preparation and wallpaper packager."""
from __future__ import annotations

import contextlib
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import signal
import stat
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
TOOLS = PACKAGE / "tools"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_header(width: int, height: int, *, depth: int = 8, color: int = 6, padding: int = 0) -> bytes:
    data = (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
            + struct.pack(">IIBB", width, height, depth, color))
    return data + b"x" * padding


def png_chunk(kind: bytes, body: bytes) -> bytes:
    payload = kind + body
    return (len(body).to_bytes(4, "big") + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF))


def png_bytes(width=1, height=1, *, depth=8, color=6, compression=0, filtering=0,
              interlace=0, raw=b"\x00\x10\x20\x30\xff", idat=None, ending=True) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, depth, color, compression, filtering, interlace)
    compressed = zlib.compress(raw) if idat is None else idat
    result = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", compressed)
    return result + (png_chunk(b"IEND", b"") if ending else b"")


class WallpaperPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module(TOOLS / "build-wallpaper.py", "agent_skin_canonical_wallpaper")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-wallpaper-api-")
        self.addCleanup(self.temporary.cleanup)
        self.root = (Path(self.temporary.name) / "source").resolve()
        self.stage = self.root / ".build/azhou-stage.test/azhou-payload"
        self.stage.mkdir(parents=True)
        for name in ("hub-package.json", "theme-config.json"):
            shutil.copy2(PACKAGE / name, self.root / name)
        (self.root / "tools").mkdir()
        canonical_verifier = TOOLS / "verify-artifacts.py"
        copied_verifier = self.root / "tools/verify-artifacts.py"
        shutil.copy2(canonical_verifier, copied_verifier)
        self.assertEqual(copied_verifier.read_bytes(), canonical_verifier.read_bytes())
        renderer = self.root / "wallpaper/renderer.js"
        renderer.parent.mkdir(parents=True)
        renderer.write_text("export async function installRenderer(value) { return value; }\n", encoding="utf-8")
        (self.root / "wallpaper/wallpaper.css").write_text("body { color: black; }\n", encoding="utf-8")
        self.image = self.root / "assets/private/wallpaper-scene-q-v3.png"
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(png_header(1400, 1000))

    def package(self):
        with mock.patch.object(self.module, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            self.module.package(self.stage)

    def test_package_binds_private_image_renderer_css_and_theme(self):
        self.package()
        output = self.stage / "Contents/Resources/wallpaper"
        script = (output / "install.js").read_text(encoding="utf-8")
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.assertEqual(manifest["imageSHA256"], digest)
        self.assertEqual(manifest["width"], 1400)
        self.assertEqual(manifest["height"], 1000)
        self.assertEqual(manifest["alpha"], True)
        self.assertEqual(manifest["displayMode"], "cover")
        self.assertEqual(manifest["scriptSHA256"], hashlib.sha256(script.encode()).hexdigest())
        payload = json.loads(script.rsplit("return await installRenderer(", 1)[1].removesuffix(");\n})()\n"))
        theme = json.loads((self.root / "theme-config.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["strength"], theme["wallpaper"]["strength"])
        self.assertEqual(payload["imageSHA256"], digest)
        self.assertIn("async function installRenderer", script)

    def test_package_rejects_invalid_stage_and_missing_or_symlinked_artwork(self):
        with mock.patch.object(self.module, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "azhou-stage"):
                self.module.package(self.root / "ordinary/azhou-payload")
            self.image.unlink()
            with self.assertRaisesRegex(RuntimeError, "缺少阿舟素材 wallpaper-scene-q-v3.png"):
                self.module.package(self.stage)
            outside = Path(self.temporary.name) / "outside.png"
            outside.write_bytes(png_header(1400, 1000))
            self.image.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, "cannot pass through a symlink"):
                self.module.package(self.stage)
            self.image.unlink()
            library = self.root / "assets/azhou/wallpaper-scene-q-v3.png"
            library.parent.mkdir(parents=True, exist_ok=True)
            library.write_bytes(png_header(1400, 1000))
            self.module.package(self.stage)
            manifest = json.loads((self.stage / "Contents/Resources/wallpaper/manifest.json").read_text())
            self.assertEqual(manifest["asset"], "assets/azhou/wallpaper-scene-q-v3.png")

    def test_package_preserves_artwork_across_encoding_boundaries(self):
        header = png_header(1400, 1000)
        for length in (49151, 49152, 49153, 98305):
            with self.subTest(length=length):
                image = header + b"x" * (length - len(header))
                self.image.write_bytes(image)
                self.package()
                output = self.stage / "Contents/Resources/wallpaper"
                script = (output / "install.js").read_text(encoding="utf-8")
                payload = json.loads(script.rsplit("return await installRenderer(", 1)[1].removesuffix(");\n})()\n"))
                prefix = "data:image/png;base64,"
                self.assertTrue(payload["image"].startswith(prefix))
                self.assertEqual(base64.b64decode(payload["image"][len(prefix):], validate=True), image)
                self.assertEqual(payload["imageSHA256"], hashlib.sha256(image).hexdigest())

    def test_package_rejects_bad_png_depth_color_and_dimensions(self):
        with mock.patch.object(self.module, "ROOT", self.root):
            cases = (
                (b"not png", "8-bit RGB/RGBA"),
                (png_header(1400, 1000, depth=16), "8-bit RGB/RGBA"),
                (png_header(1400, 1000, color=0), "8-bit RGB/RGBA"),
                (png_header(1000, 1000), "landscape PNG"),
                (png_header(9000, 5000), "landscape PNG"),
            )
            for data, message in cases:
                with self.subTest(message=message, data=data[:26]):
                    self.image.write_bytes(data)
                    with self.assertRaisesRegex(RuntimeError, message):
                        self.module.package(self.stage)

    def test_package_rejects_oversize_artwork_and_non_self_contained_renderer(self):
        with mock.patch.object(self.module, "ROOT", self.root):
            self.image.write_bytes(png_header(1400, 1000, padding=13 * 1024 * 1024))
            with self.assertRaisesRegex(RuntimeError, "renderer local-image limit"):
                self.module.package(self.stage)
            self.image.write_bytes(png_header(1400, 1000))
            renderer = self.root / "wallpaper/renderer.js"
            renderer.write_text("import './dep.js';\nexport async function installRenderer() {}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "one self-contained"):
                self.module.package(self.stage)
            renderer.write_text(
                "export async function installRenderer() {}\nexport async function installRenderer() {}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "one self-contained"):
                self.module.package(self.stage)

    def test_oversized_artwork_is_rejected_with_bounded_temporary_storage(self):
        self.image.write_bytes(png_header(1400, 1000, padding=13 * 1024 * 1024))
        limit = ((16 * 1024 * 1024 - len("data:image/png;base64,")) // 4) * 3
        original_temporary = tempfile.TemporaryFile

        class LimitedTemporary:
            def __init__(self, stream):
                self.stream = stream
                self.total = 0

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def write(self, data):
                self.total += len(data)
                if self.total > limit:
                    raise OSError("synthetic temporary storage exhausted")
                return self.stream.write(data)

            def __getattr__(self, name):
                return getattr(self.stream, name)

        def limited(*args, **kwargs):
            return LimitedTemporary(original_temporary(*args, **kwargs))

        with mock.patch.object(tempfile, "TemporaryFile", side_effect=limited):
            with mock.patch.object(self.module, "ROOT", self.root):
                with self.assertRaisesRegex(RuntimeError, "renderer local-image limit"):
                    self.module.package(self.stage)

    def test_capture_rejects_in_place_source_changes(self):
        self.image.write_bytes(png_header(1400, 1000) + b'a' * 100000)
        original_sha = hashlib.sha256
        image = self.image
        class MutatingDigest:
            def __init__(self):
                self.digest = original_sha()
                self.changed = False
            def update(self, data):
                self.digest.update(data)
                if not self.changed:
                    self.changed = True
                    image.write_bytes(png_header(1400, 1000) + b'b' * 100000)
            def hexdigest(self):
                return self.digest.hexdigest()
        output = io.BytesIO()
        with mock.patch.object(self.module.hashlib, 'sha256', side_effect=MutatingDigest):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                self.module.snapshot_image(image, output)
        self.assertEqual(image.read_bytes()[-1:], b'b')

    def test_capture_rejects_file_replaced_by_fifo_before_open(self):
        saved = self.image.with_name('saved.png')
        original = os.open
        def substitute(path, flags, *args, **kwargs):
            if Path(path) == self.image:
                self.image.rename(saved)
                os.mkfifo(self.image)
            return original(path, flags, *args, **kwargs)
        with mock.patch.object(self.module.os, 'open', side_effect=substitute):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                self.package()
        self.assertTrue(saved.is_file())
        self.assertTrue(stat.S_ISFIFO(self.image.lstat().st_mode))
        self.assertFalse((self.stage / 'Contents/Resources/wallpaper').exists())

    def test_capture_handles_short_reads_and_interruptions(self):
        data = png_header(1400, 1000) + b'x' * 400
        self.image.write_bytes(data)
        original = os.read
        calls = 0
        def short_read(fd, count):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise InterruptedError()
            return original(fd, min(count, 19))
        output = io.BytesIO()
        with mock.patch.object(self.module.os, 'read', side_effect=short_read):
            result = self.module.snapshot_image(self.image, output)
        self.assertGreater(calls, 2)
        self.assertEqual(output.getvalue(), data)
        self.assertEqual(result[0], hashlib.sha256(data).hexdigest())

    def test_capture_rejects_read_error_and_retains_source(self):
        original = self.image.read_bytes()
        with mock.patch.object(self.module.os, 'read', side_effect=OSError('synthetic read error')):
            with self.assertRaisesRegex(RuntimeError, 'could not be read'):
                self.package()
        self.assertEqual(self.image.read_bytes(), original)
        self.assertFalse((self.stage / 'Contents/Resources/wallpaper').exists())

    def test_capture_bounds_a_source_that_grows_during_read(self):
        self.image.write_bytes(png_header(1400, 1000))
        original = os.read
        grown = False
        def grow_after_read(fd, count):
            nonlocal grown
            result = original(fd, count)
            if result and not grown:
                grown = True
                with self.image.open('ab') as stream:
                    stream.write(b'x' * 100)
            return result
        output = io.BytesIO()
        with mock.patch.object(self.module, 'MAX_IMAGE_BYTES', 64), mock.patch.object(self.module.os, 'read', side_effect=grow_after_read):
            with self.assertRaisesRegex(RuntimeError, 'renderer local-image limit'):
                self.module.snapshot_image(self.image, output)
        self.assertLessEqual(len(output.getvalue()), 64)
        self.assertGreater(self.image.stat().st_size, 64)

    def test_capture_rejects_path_replaced_after_read(self):
        saved = self.image.with_name('saved.png')
        original = os.read
        changed = False
        def replace_after_read(fd, count):
            nonlocal changed
            result = original(fd, count)
            if result and not changed:
                changed = True
                self.image.rename(saved)
                self.image.write_bytes(b'foreign synthetic data')
            return result
        with mock.patch.object(self.module.os, 'read', side_effect=replace_after_read):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                self.package()
        self.assertEqual(self.image.read_bytes(), b'foreign synthetic data')
        self.assertTrue(saved.is_file())
        self.assertFalse((self.stage / 'Contents/Resources/wallpaper').exists())

    def test_cli_packages_the_requested_stage(self):
        script = self.root / "tools/build-wallpaper.py"
        shutil.copy2(TOOLS / script.name, script)
        self.assertEqual(script.read_bytes(), (TOOLS / script.name).read_bytes())
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(script), "--bundle", str(self.stage)]), \
                contextlib.redirect_stdout(stdout):
            runpy.run_path(str(script), run_name="__main__")
        self.assertIn("Packaged Azhou wallpaper: assets/private/wallpaper-scene-q-v3.png", stdout.getvalue())
        self.assertTrue((self.stage / "Contents/Resources/wallpaper/manifest.json").is_file())


class PrepareAzhouAssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-prepare-assets-")
        self.addCleanup(self.temporary.cleanup)
        self.root = (Path(self.temporary.name) / "source").resolve()
        tools = self.root / "tools"
        tools.mkdir(parents=True)
        self.script = tools / "prepare-azhou-assets.py"
        shutil.copy2(TOOLS / self.script.name, self.script)
        shutil.copy2(TOOLS / "build-lock.py", tools / "build-lock.py")
        self.state = self.root / ".local/agent-skin-asset-preparation"
        self.assertEqual(self.script.read_bytes(), (TOOLS / self.script.name).read_bytes())
        self.source = Path(self.temporary.name) / "approved-working.png"
        self.source.write_bytes(png_header(1254, 1254))
        self.run_result = subprocess.CompletedProcess(["git", "check-ignore"], 0)
        self.tracked = b""

    def invoke(self, source=None, *, adopt=False):
        source = source or self.source
        stdout = io.StringIO()
        self.stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--source", str(source), *(["--adopt-existing"] if adopt else [])]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result) as run, \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked) as check_output, \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(self.stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        return stdout.getvalue(), run.call_args, check_output.call_args

    def real_git_prepare(self, ignore_rules, *, tracked_private=False):
        environment = os.environ.copy()
        environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env=environment)
        (self.root / ".gitignore").write_text(ignore_rules)
        if tracked_private:
            foreign = self.root / "assets/private/already-tracked.txt"
            foreign.parent.mkdir(parents=True)
            foreign.write_bytes(b"preserve tracked fixture")
            subprocess.run(["git", "add", "-f", "--", "assets/private/already-tracked.txt"],
                           cwd=self.root, env=environment, check=True)
        command = [sys.executable, "-B", str(self.script), "--source", str(self.source)]
        result = subprocess.run(command, cwd=self.root, env=environment, capture_output=True, text=True, timeout=10)
        return result, command, environment

    def test_real_git_rejects_private_directory_with_only_image_ignored(self):
        result, _, env = self.real_git_prepare("/.build/\n/assets/private/working.png\n/.local/\n")
        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all", "--", "assets/private"],
                                         cwd=self.root, env=env, text=True)
        self.assertNotEqual(result.returncode, 0, f"incomplete ignore wrote files: {status}")
        self.assertFalse((self.root / "assets/private").exists())
        self.assertFalse(self.state.exists())

    def test_real_git_rejects_state_directory_with_only_receipt_ignored(self):
        rules = "/.build/\n/assets/private/\n/.local/agent-skin-asset-preparation/.azhou-assets-receipt.json\n"
        result, _, _ = self.real_git_prepare(rules)
        self.assertNotEqual(result.returncode, 0, "receipt-only ignore must not authorize transaction state")
        self.assertFalse((self.root / "assets/private").exists())
        self.assertFalse(self.state.exists())

    def test_real_git_directory_ignores_allow_repeat_and_recovery(self):
        result, command, env = self.real_git_prepare("/.build/\n/assets/private/\n/.local/\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        image = self.root / "assets/private/working.png"
        before = (image.stat().st_ino, image.read_bytes())
        repeated = subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual((image.stat().st_ino, image.read_bytes()), before)
        recovery = subprocess.run([sys.executable, "-B", str(self.script), "--recover"], cwd=self.root,
                                  env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(recovery.returncode, 0, recovery.stderr)
        self.assertIn("no transaction", recovery.stdout)
        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all", "--", "assets/private", ".local"],
                                         cwd=self.root, env=env, text=True)
        self.assertEqual(status, "")

    def test_real_git_tracked_private_file_remains_untouched(self):
        result, _, _ = self.real_git_prepare("/.build/\n/assets/private/\n/.local/\n", tracked_private=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "assets/private/already-tracked.txt").read_bytes(), b"preserve tracked fixture")
        self.assertFalse((self.root / "assets/private/working.png").exists())

    def test_prepares_exact_bytes_and_provenance_under_the_local_project(self):
        output, run_call, check_call = self.invoke()
        destination = self.root / "assets/private"
        self.assertEqual((destination / "working.png").read_bytes(), self.source.read_bytes())
        scene = (destination / "scene.js").read_text(encoding="utf-8")
        self.assertIn(base64.b64encode(self.source.read_bytes()).decode("ascii"), scene)
        provenance = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertTrue(provenance["copiedByteForByte"])
        self.assertIn("Prepared private working pose", output)
        self.assertEqual(run_call.kwargs["cwd"], self.root)
        self.assertEqual(check_call.kwargs["cwd"], self.root)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO")
    def test_fifo_source_is_rejected_without_waiting_for_writer(self):
        fifo = Path(self.temporary.name) / "source-fifo"
        os.mkfifo(fifo)
        try:
            completed = subprocess.run([sys.executable, "-B", str(self.script), "--source", str(fifo)],
                                       capture_output=True, text=True, timeout=2)
        except subprocess.TimeoutExpired:
            self.fail("FIFO source blocked while waiting for a writer")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("regular file", completed.stderr)
        self.assertFalse((self.root / "assets/private").exists())

    def test_short_png_header_is_a_controlled_input_error(self):
        self.source.write_bytes(b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + b"xx")
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertIn("must be a PNG", self.stderr.getvalue())
        self.assertFalse((self.root / "assets/private").exists())

    def test_source_path_replaced_during_capture_is_rejected(self):
        self.source.write_bytes(png_header(1254, 1254, padding=200))
        original = self.source.read_bytes()
        replacement = png_header(1254, 1254, padding=201)
        original_info = self.source.stat()
        saved = Path(self.temporary.name) / "original-saved.png"
        opened = Path.open
        os_read = os.read
        changed = []
        def replace_source():
            if not changed:
                self.source.rename(saved)
                self.source.write_bytes(replacement)
                changed.append(True)
        class SourceReader:
            def __init__(self, wrapped): self.wrapped = wrapped
            def __enter__(self): self.wrapped.__enter__(); return self
            def __exit__(self, *args): return self.wrapped.__exit__(*args)
            def read(self, size=-1):
                data = self.wrapped.read(size)
                if data: replace_source()
                return data
        def instrumented_open(path, *args, **kwargs):
            stream = opened(path, *args, **kwargs)
            return SourceReader(stream) if path == self.source.resolve() and args and args[0] == "rb" else stream
        def instrumented_read(fd, size):
            info = os.fstat(fd)
            data = os_read(fd, size)
            if (info.st_dev, info.st_ino) == (original_info.st_dev, original_info.st_ino) and data: replace_source()
            return data
        with mock.patch.object(Path, "open", new=instrumented_open), mock.patch.object(os, "read", side_effect=instrumented_read):
            with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual(changed, [True])
        self.assertEqual(saved.read_bytes(), original)
        self.assertEqual(self.source.read_bytes(), replacement)
        self.assertFalse((self.root / "assets/private").exists())

    def test_empty_and_oversize_sources_leave_no_private_output(self):
        for mode in ("empty", "oversize"):
            with self.subTest(mode=mode):
                self.source.write_bytes(b"" if mode == "empty" else png_header(1254, 1254))
                if mode == "oversize":
                    with self.source.open("r+b") as stream: stream.truncate(64 * 1024 * 1024 + 1)
                with self.assertRaises(SystemExit): self.invoke()
                self.assertIn("must be a PNG" if mode == "empty" else "64 MiB", self.stderr.getvalue())
                self.assertFalse((self.root / "assets/private").exists())

    def test_source_symlink_to_regular_approved_file_is_supported(self):
        alias = Path(self.temporary.name) / "approved-alias.png"
        alias.symlink_to(self.source)
        self.invoke(alias)
        destination = self.root / "assets/private"
        self.assertEqual((destination / "working.png").read_bytes(), self.source.read_bytes())
        self.assertEqual(json.loads((destination / "provenance.json").read_text())["source"], str(self.source.resolve()))

    def test_source_capture_retries_interrupted_read(self):
        original_read = os.read
        info = self.source.stat()
        interrupted = []
        def read_once(fd, size):
            now = os.fstat(fd)
            if (now.st_dev, now.st_ino) == (info.st_dev, info.st_ino) and not interrupted:
                interrupted.append(True)
                raise InterruptedError()
            return original_read(fd, size)
        with mock.patch.object(os, "read", side_effect=read_once): self.invoke()
        self.assertEqual(interrupted, [True])
        self.assertEqual((self.root / "assets/private/working.png").read_bytes(), self.source.read_bytes())

    def test_source_changed_in_place_during_capture_is_rejected(self):
        original_read = os.read
        info = self.source.stat()
        changed = []
        def mutate(fd, size):
            now = os.fstat(fd)
            data = original_read(fd, size)
            if (now.st_dev, now.st_ino) == (info.st_dev, info.st_ino) and data and not changed:
                with self.source.open("ab") as stream: stream.write(b"changed")
                changed.append(True)
            return data
        with mock.patch.object(os, "read", side_effect=mutate):
            with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual(changed, [True])
        self.assertTrue(self.source.read_bytes().endswith(b"changed"))
        self.assertFalse((self.root / "assets/private").exists())

    def test_source_replaced_by_symlink_before_open_is_rejected(self):
        original_open = os.open
        saved = Path(self.temporary.name) / "saved.png"
        outside = Path(self.temporary.name) / "outside.png"
        outside.write_bytes(b"do not touch")
        changed = []
        def replace_before_open(path, *args, **kwargs):
            if Path(path) == self.source.resolve() and not changed:
                self.source.rename(saved)
                self.source.symlink_to(outside)
                changed.append(True)
            return original_open(path, *args, **kwargs)
        with mock.patch.object(os, "open", side_effect=replace_before_open):
            with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual(changed, [True])
        self.assertEqual(outside.read_bytes(), b"do not touch")
        self.assertTrue(self.source.is_symlink())
        self.assertFalse((self.root / "assets/private").exists())

    def test_invalid_source_preserves_all_existing_outputs(self):
        self.invoke()
        destination = self.root / "assets/private"
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        self.source.write_bytes(b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + b"xx")
        with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, before)

    def test_capture_accepts_limit_and_refuses_one_byte_more(self):
        module = load_module(self.script, "synthetic_bounded_asset_capture")
        module.MAX_SOURCE_BYTES = 32
        self.source.write_bytes(png_header(1254, 1254) + b"x" * 6)
        with tempfile.TemporaryFile(mode="w+b") as snapshot:
            header, digest = module.capture(self.source.resolve(), snapshot)
            snapshot.seek(0)
            self.assertEqual(snapshot.read(), self.source.read_bytes())
            self.assertEqual(digest, hashlib.sha256(self.source.read_bytes()).hexdigest())
            self.assertEqual(len(header), 26)
        with self.source.open("ab") as stream: stream.write(b"x")
        with tempfile.TemporaryFile(mode="w+b") as snapshot:
            with self.assertRaisesRegex(ValueError, "64 MiB"):
                module.capture(self.source.resolve(), snapshot)
            self.assertEqual(snapshot.tell(), 0)

    def test_foreign_output_symlink_does_not_change_its_target(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        foreign = Path(self.temporary.name) / "foreign-user-data"
        foreign.write_bytes(b"do not modify")
        (destination / "working.png").symlink_to(foreign)
        try: self.invoke()
        except SystemExit: pass
        self.assertEqual(foreign.read_bytes(), b"do not modify")
        self.assertTrue((destination / "working.png").is_symlink())
        self.assertFalse((destination / "scene.js").exists())

    def test_unknown_partial_output_is_not_replaced(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        (destination / "scene.js").write_bytes(b"foreign content")
        try: self.invoke()
        except SystemExit: pass
        self.assertEqual((destination / "scene.js").read_bytes(), b"foreign content")
        self.assertFalse((destination / "working.png").exists())
        self.assertFalse((destination / "provenance.json").exists())

    def test_output_failure_does_not_silently_mix_old_and_new_assets(self):
        self.invoke()
        destination = self.root / "assets/private"
        names = ("working.png", "scene.js", "provenance.json", ".azhou-assets-receipt.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=15))
        module = load_module(self.script, "synthetic_asset_transaction_fault")
        swap = module.swap_files
        calls = []
        def fail_second(*args):
            calls.append(args)
            if len(calls) == 2: raise OSError("injected second publication failure")
            return swap(*args)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=fail_second), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertGreaterEqual(len(calls), 3)
        self.assertIn("prior outputs restored", stderr.getvalue())
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_unbound_legacy_output_requires_explicit_adoption(self):
        self.invoke()
        destination = self.root / "assets/private"
        receipt = self.state / ".azhou-assets-receipt.json"
        receipt.unlink()
        names = ("working.png", "scene.js", "provenance.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=11))
        with self.assertRaises(SystemExit): self.invoke()
        self.assertIn("--adopt-existing", self.stderr.getvalue())
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        self.assertFalse(receipt.exists())
        self.invoke(adopt=True)
        self.assertTrue(receipt.is_file())
        self.assertEqual((destination / "working.png").read_bytes(), self.source.read_bytes())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())

    def test_adoption_refuses_legacy_scene_with_changed_bytes(self):
        self.invoke()
        destination = self.root / "assets/private"
        (self.state / ".azhou-assets-receipt.json").unlink()
        (destination / "scene.js").write_bytes(b"foreign scene")
        before = {name: (destination / name).read_bytes() for name in ("working.png", "scene.js", "provenance.json")}
        with self.assertRaises(SystemExit): self.invoke(adopt=True)
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in before}, before)
        self.assertFalse((self.state / ".azhou-assets-receipt.json").exists())

    def test_copied_private_directory_does_not_inherit_binding(self):
        self.invoke()
        destination = self.root / "assets/private"
        saved = self.root / "assets/saved-private"
        destination.rename(saved)
        shutil.copytree(saved, destination)
        before = (destination / "working.png").read_bytes()
        with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual((destination / "working.png").read_bytes(), before)
        self.assertEqual((saved / "working.png").read_bytes(), before)
        self.assertIn("receipt does not match", self.stderr.getvalue())

    def test_unknown_transaction_record_is_preserved_without_publishing(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        self.state.mkdir(parents=True)
        journal = self.state / ".azhou-assets-transaction.json"
        journal.write_bytes(b"unknown journal")
        with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual(journal.read_bytes(), b"unknown journal")
        self.assertFalse((destination / "working.png").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def interrupted_update_for_recovery(self):
        self.invoke()
        destination = self.root / "assets/private"
        before = (destination / "working.png").read_bytes()
        self.source.write_bytes(png_header(1254, 1254, padding=81))
        module = load_module(self.script, "synthetic_interrupted_record")
        swap = module.swap_files
        def interrupt(*args):
            swap(*args)
            raise SystemExit("synthetic interruption")
        with mock.patch.object(module, "swap_files", side_effect=interrupt), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): module.main()
        return destination, before

    def assert_recovery_rejected(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
        return stderr.getvalue()

    def test_recovery_preserves_moved_transaction_directory_and_journal(self):
        destination, old_image = self.interrupted_update_for_recovery()
        journal = self.state / ".azhou-assets-transaction.json"
        journal_bytes = journal.read_bytes()
        stage = next(self.state.glob(".azhou-assets-stage-*"))
        moved = self.state / "foreign-moved-stage"
        stage.rename(moved)
        self.source.unlink()
        self.assertIn("directory is missing", self.assert_recovery_rejected())
        self.assertEqual(journal.read_bytes(), journal_bytes)
        self.assertEqual((moved / "working.png").read_bytes(), old_image)
        self.assertTrue((destination / "working.png").exists())

    def test_recovery_preserves_unrecognized_transaction_plan(self):
        destination, _ = self.interrupted_update_for_recovery()
        journal = self.state / ".azhou-assets-transaction.json"
        record = json.loads(journal.read_bytes())
        record["items"]["working.png"]["new"]["sha256"] = "not-a-digest"
        journal.write_text(json.dumps(record))
        corrupt = journal.read_bytes()
        stage = next(self.state.glob(".azhou-assets-stage-*"))
        before = {p.name: p.read_bytes() for p in stage.iterdir()}
        self.source.unlink()
        self.assertIn("plan is not recognized", self.assert_recovery_rejected())
        self.assertEqual(journal.read_bytes(), corrupt)
        self.assertEqual({p.name: p.read_bytes() for p in stage.iterdir()}, before)
        self.assertTrue((destination / "working.png").exists())

    def test_adoption_retries_interrupted_legacy_image_read(self):
        self.invoke()
        (self.state / ".azhou-assets-receipt.json").unlink()
        destination = self.root / "assets/private"
        info = (destination / "working.png").stat()
        original_read = os.read
        interrupted, completed_reads = [], []
        def read_once(fd, size):
            current = os.fstat(fd)
            matching = (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)
            if matching and completed_reads and not interrupted:
                interrupted.append(True)
                raise InterruptedError()
            result = original_read(fd, size)
            if matching and not result: completed_reads.append(True)
            return result
        with mock.patch.object(os, "read", side_effect=read_once): self.invoke(adopt=True)
        self.assertTrue(completed_reads)
        self.assertEqual(interrupted, [True])
        self.assertTrue((self.state / ".azhou-assets-receipt.json").is_file())
        self.assertEqual((destination / "working.png").read_bytes(), self.source.read_bytes())

    def test_adoption_refuses_legacy_image_replaced_during_capture(self):
        self.invoke()
        (self.state / ".azhou-assets-receipt.json").unlink()
        destination = self.root / "assets/private"
        image = destination / "working.png"
        info = image.stat()
        old_data = image.read_bytes()
        replacement = b"foreign replacement"
        original_read = os.read
        changed, completed_reads = [], []
        def replace(fd, size):
            current = os.fstat(fd)
            data = original_read(fd, size)
            matching = (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)
            if matching and not data: completed_reads.append(True)
            if data and matching and completed_reads and not changed:
                image.rename(destination / "saved-original.png")
                image.write_bytes(replacement)
                changed.append(True)
            return data
        with mock.patch.object(os, "read", side_effect=replace):
            with self.assertRaises(SystemExit): self.invoke(adopt=True)
        self.assertEqual(changed, [True])
        self.assertEqual((destination / "saved-original.png").read_bytes(), old_data)
        self.assertEqual(image.read_bytes(), replacement)
        self.assertFalse((self.state / ".azhou-assets-receipt.json").exists())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())

    def test_native_atomic_exchange_failure_preserves_other_file(self):
        module = load_module(self.script, "synthetic_exchange_failure")
        directory = Path(self.temporary.name)
        (directory / "existing").write_bytes(b"preserve")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        with self.assertRaises(OSError):
            module.swap_files(fd, "missing", fd, "existing")
        self.assertEqual((directory / "existing").read_bytes(), b"preserve")

    def test_recover_argument_conflicts_do_not_create_private_state(self):
        for extra in (["--source", str(self.source)], ["--adopt-existing"]):
            with self.subTest(extra=extra):
                stderr = io.StringIO()
                with mock.patch.object(sys, "argv", [str(self.script), "--recover", *extra]), \
                        contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
                self.assertIn("cannot be combined", stderr.getvalue())
                self.assertFalse((self.root / "assets/private").exists())
                self.assertFalse(self.state.exists())

    def test_recover_without_local_state_reports_no_transaction(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), contextlib.redirect_stdout(stdout):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("No private asset transaction found", stdout.getvalue())
        self.assertFalse(self.state.exists())
        self.assertFalse((self.root / "assets/private").exists())

    def test_journal_array_is_rejected_without_claiming_it(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        self.state.mkdir(parents=True)
        journal = self.state / ".azhou-assets-transaction.json"
        journal.write_bytes(b'[]')
        with self.assertRaises(SystemExit): self.invoke()
        self.assertIn("Invalid JSON record", self.stderr.getvalue())
        self.assertEqual(journal.read_bytes(), b'[]')
        self.assertEqual(list(destination.iterdir()), [])

    def test_staged_scene_changed_after_write_is_preserved_without_publishing(self):
        module = load_module(self.script, "synthetic_stage_content_change")
        write_stage = module.stage_file
        tampered = []
        def alter(path, writer, stage_fd):
            result = write_stage(path, writer, stage_fd)
            if path.name == "scene.js":
                path.write_bytes(b"foreign scene change")
                tampered.append(True)
            return result
        stderr = io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=alter), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(tampered, [True])
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "scene.js").read_bytes(), b"foreign scene change")
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertEqual(list((self.root / "assets/private").iterdir()), [])
        self.assertIn("preserve", stderr.getvalue())

    def test_transaction_record_changed_before_publication_is_preserved(self):
        module = load_module(self.script, "synthetic_record_change")
        create = module.write_journal
        modified = []
        def alter(state, *args):
            record, info = create(state, *args)
            path = state / ".azhou-assets-transaction.json"
            changed = json.loads(path.read_bytes())
            changed["owner"] = "foreign-owner"
            path.write_text(json.dumps(changed))
            modified.append(path.read_bytes())
            return record, info
        stderr = io.StringIO()
        with mock.patch.object(module, "write_journal", side_effect=alter), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(len(modified), 1)
        self.assertEqual((self.state / ".azhou-assets-transaction.json").read_bytes(), modified[0])
        self.assertEqual(len(list(self.state.glob(".azhou-assets-stage-*"))), 1)
        self.assertEqual(list((self.root / "assets/private").iterdir()), [])
        self.assertIn("requires recovery", stderr.getvalue())

    def test_readers_refuse_file_replaced_between_stat_and_open(self):
        module = load_module(self.script, "synthetic_preopen_replacement")
        directory = Path(self.temporary.name)
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        original_open = os.open
        for mode in ("metadata", "legacy-image"):
            with self.subTest(mode=mode):
                path = directory / mode
                saved = directory / (mode + "-original")
                path.write_bytes(b"original")
                changed = []
                def replace(name, flags, *args, **kwargs):
                    if name == mode and kwargs.get("dir_fd") == fd and not changed:
                        path.rename(saved)
                        path.write_bytes(b"foreign")
                        changed.append(True)
                    return original_open(name, flags, *args, **kwargs)
                with mock.patch.object(module.os, "open", side_effect=replace):
                    with self.assertRaises(module.AssetConflict):
                        if mode == "metadata": module.file_info_at(fd, mode)
                        else:
                            with tempfile.TemporaryFile() as snapshot: module.capture_at(fd, mode, snapshot)
                self.assertEqual(changed, [True])
                self.assertEqual(saved.read_bytes(), b"original")
                self.assertEqual(path.read_bytes(), b"foreign")

    def test_final_swap_success_then_error_finishes_verified_transaction(self):
        self.invoke()
        self.source.write_bytes(png_header(1254, 1254, padding=87))
        module = load_module(self.script, "synthetic_final_swap_uncertain")
        swap = module.swap_files
        calls = []
        def success_then_error(*args):
            result = swap(*args)
            calls.append(True)
            if len(calls) == 4: raise OSError("injected error after final successful swap")
            return result
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=success_then_error), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            module.main()
        self.assertEqual(len(calls), 4)
        self.assertEqual((self.root / "assets/private/working.png").read_bytes(), self.source.read_bytes())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_output_changed_between_publication_steps_is_preserved(self):
        self.invoke()
        self.source.write_bytes(png_header(1254, 1254, padding=89))
        module = load_module(self.script, "synthetic_between_publications")
        swap = module.swap_files
        target = self.root / "assets/private/working.png"
        changed = []
        def change_after_first(*args):
            result = swap(*args)
            if not changed:
                target.write_bytes(b"foreign output")
                changed.append(True)
            return result
        stderr = io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=change_after_first), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(changed, [True])
        self.assertEqual(target.read_bytes(), b"foreign output")
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.assertEqual(len(list(self.state.glob(".azhou-assets-stage-*"))), 1)
        self.assertIn("requires recovery", stderr.getvalue())

    def test_recover_with_local_directory_but_no_state_reports_none(self):
        (self.root / ".local").mkdir()
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), contextlib.redirect_stdout(stdout):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("No private asset transaction found", stdout.getvalue())
        self.assertFalse(self.state.exists())

    def test_recover_rejects_valid_json_with_unknown_owner(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        self.state.mkdir(parents=True)
        journal = self.state / ".azhou-assets-transaction.json"
        original = b'{"owner":"unknown"}'
        journal.write_bytes(original)
        self.assertIn("record is not recognized", self.assert_recovery_rejected())
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(list(destination.iterdir()), [])

    def test_git_tracked_transaction_state_blocks_preparation(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", side_effect=[b"", b"tracked-state\n"]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("transaction state is tracked", stderr.getvalue())
        self.assertFalse(self.state.exists())
        self.assertFalse((self.root / "assets/private").exists())

    def assert_late_foreign_journal_is_preserved(self, *, inject_after):
        module = load_module(self.script, "synthetic_late_foreign_journal")
        stage_file, checked_unlink = module.stage_file, module.checked_unlink
        removed = []
        def stop_before_receipt(path, writer, fd):
            if path.name == ".azhou-assets-receipt.json": raise OSError("injected stage failure")
            return stage_file(path, writer, fd)
        def insert_after_unlink(directory_fd, name, expected):
            checked_unlink(directory_fd, name, expected)
            removed.append(name)
            if len(removed) == inject_after:
                (self.state / ".azhou-assets-transaction.json").write_bytes(b"foreign record")
        stderr = io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=stop_before_receipt), \
                mock.patch.object(module, "checked_unlink", side_effect=insert_after_unlink), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(len(removed), inject_after)
        self.assertEqual((self.state / ".azhou-assets-transaction.json").read_bytes(), b"foreign record")
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual(len(list(stages[0].iterdir())), 3 - inject_after)
        self.assertIn("preserve", stderr.getvalue())

    def test_cleanup_stops_when_foreign_journal_appears_between_unlinks(self):
        self.assert_late_foreign_journal_is_preserved(inject_after=1)

    def test_cleanup_stops_when_foreign_journal_appears_after_last_unlink(self):
        self.assert_late_foreign_journal_is_preserved(inject_after=3)

    def test_capture_refuses_source_replaced_between_stat_and_open(self):
        module = load_module(self.script, "synthetic_source_preopen_replacement")
        source = self.source
        saved = Path(self.temporary.name) / "saved-source.png"
        original = source.read_bytes()
        original_open = os.open
        changed = []
        def replace(path, flags, *args, **kwargs):
            if path == source and not changed:
                source.rename(saved)
                source.write_bytes(b"foreign")
                changed.append(True)
            return original_open(path, flags, *args, **kwargs)
        with tempfile.TemporaryFile() as snapshot, mock.patch.object(module.os, "open", side_effect=replace):
            with self.assertRaisesRegex(ValueError, "changed before"):
                module.capture(source, snapshot)
            self.assertEqual(snapshot.tell(), 0)
        self.assertEqual(changed, [True])
        self.assertEqual(saved.read_bytes(), original)
        self.assertEqual(source.read_bytes(), b"foreign")

    def test_readers_refuse_growth_past_bounded_capture(self):
        module = load_module(self.script, "synthetic_growing_files")
        directory = Path(self.temporary.name)
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, directory_fd)
        original_read = os.read
        for mode in ("source", "metadata", "legacy-image"):
            with self.subTest(mode=mode):
                path = directory / (mode + "-growing")
                path.write_bytes(b"original")
                info = path.stat()
                changed = []
                def grow(fd, size):
                    current = os.fstat(fd)
                    data = original_read(fd, size)
                    if data and (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino) and not changed:
                        with path.open("ab") as stream: stream.write(b"-foreign-growth")
                        changed.append(True)
                    return data
                with mock.patch.object(module.os, "read", side_effect=grow), \
                        mock.patch.object(module, "MAX_SOURCE_BYTES", 12):
                    with self.assertRaises((module.AssetConflict, ValueError)):
                        if mode == "metadata": module.file_info_at(directory_fd, path.name, max_bytes=12)
                        else:
                            with tempfile.TemporaryFile() as snapshot:
                                if mode == "source": module.capture(path, snapshot)
                                else: module.capture_at(directory_fd, path.name, snapshot)
                self.assertEqual(changed, [True])
                self.assertEqual(path.read_bytes(), b"original-foreign-growth")

    def assert_foreign_bytes_during_stage_are_preserved(self, target):
        module = load_module(self.script, "synthetic_stage_corruption")
        stage_file = module.stage_file
        injected = []
        def write_with_foreign(path, writer, fd):
            def corrupt(stream):
                writer(stream)
                if path.name == target:
                    stream.write(b"foreign bytes")
                    injected.append(True)
            return stage_file(path, corrupt, fd)
        stderr = io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=write_with_foreign), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(injected, [True])
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1, "unrecognized staged bytes must remain available for review")
        self.assertTrue((stages[0] / target).read_bytes().endswith(b"foreign bytes"))
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertEqual(list((self.root / "assets/private").iterdir()), [])
        self.assertIn("preserve", stderr.getvalue())

    def test_foreign_bytes_in_staged_working_image_are_preserved(self):
        self.assert_foreign_bytes_during_stage_are_preserved("working.png")

    def test_foreign_bytes_in_staged_scene_are_preserved(self):
        self.assert_foreign_bytes_during_stage_are_preserved("scene.js")

    def test_foreign_bytes_in_staged_provenance_are_preserved(self):
        self.assert_foreign_bytes_during_stage_are_preserved("provenance.json")

    def test_foreign_bytes_in_staged_receipt_are_preserved(self):
        self.assert_foreign_bytes_during_stage_are_preserved(".azhou-assets-receipt.json")

    def test_unjournaled_empty_staging_is_cleaned_after_prepare_error(self):
        module = load_module(self.script, "synthetic_asset_stage_fault")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=OSError("injected before stage write")), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        self.assertIn("before publication", stderr.getvalue())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))
        self.assertFalse((destination / "working.png").exists())

    def test_unknown_journal_appearing_during_creation_is_not_claimed(self):
        module = load_module(self.script, "synthetic_asset_journal_collision")
        write_journal = module.write_journal
        unknown = b"foreign transaction record"
        def collide(state, *args):
            (state / ".azhou-assets-transaction.json").write_bytes(unknown)
            return write_journal(state, *args)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "write_journal", side_effect=collide), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        self.assertEqual((self.state / ".azhou-assets-transaction.json").read_bytes(), unknown)
        self.assertEqual(len(list(self.state.glob(".azhou-assets-stage-*"))), 1)
        self.assertFalse((destination / "working.png").exists())

    def test_recover_option_restores_interrupted_update_without_source(self):
        self.invoke()
        destination = self.root / "assets/private"
        names = ("working.png", "scene.js", "provenance.json", ".azhou-assets-receipt.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=17))
        module = load_module(self.script, "synthetic_asset_interrupted")
        swap = module.swap_files
        def crash_after_swap(*args):
            swap(*args)
            raise SystemExit("simulated process exit after first swap")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=crash_after_swap), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.source.unlink()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("rolled-back", stdout.getvalue())
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_output_lock_excludes_an_independent_process(self):
        module = load_module(self.script, "synthetic_asset_lock")
        self.state.mkdir(parents=True)
        code = ("import importlib.util,sys\n"
                "spec=importlib.util.spec_from_file_location('asset_lock_child',sys.argv[1])\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "try:\n with m.preparation_lock(m.Path(sys.argv[2]),m.Path(sys.argv[3])): pass\n"
                "except m.AssetConflict: sys.exit(3)\n")
        command = [sys.executable, "-B", "-c", code, str(self.script), str(self.root), str(self.state)]
        with module.preparation_lock(self.root, self.state):
            blocked = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(blocked.returncode, 3, blocked.stderr)
        admitted = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(admitted.returncode, 0, admitted.stderr)

    def test_new_target_race_preserves_foreign_file_and_transaction(self):
        module = load_module(self.script, "synthetic_asset_new_race")
        link = module.os.link
        unknown = b"foreign target"
        injected = []
        def race(source, destination, *args, **kwargs):
            if destination == "working.png" and not injected:
                (self.root / "assets/private/working.png").write_bytes(unknown)
                injected.append(True)
            return link(source, destination, *args, **kwargs)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module.os, "link", side_effect=race), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        self.assertEqual(injected, [True])
        self.assertEqual((destination / "working.png").read_bytes(), unknown)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.assertEqual(len(list(self.state.glob(".azhou-assets-stage-*"))), 1)
        self.assertIn("requires recovery", stderr.getvalue())

    def test_swap_race_preserves_displaced_foreign_file_and_original(self):
        self.invoke()
        destination = self.root / "assets/private"
        original = (destination / "working.png").read_bytes()
        saved = Path(self.temporary.name) / "saved-prior-working.png"
        self.source.write_bytes(png_header(1254, 1254, padding=21))
        module = load_module(self.script, "synthetic_asset_swap_race")
        swap = module.swap_files
        unknown = b"foreign replacement"
        injected = []
        def race(left_fd, left_name, right_fd, right_name):
            if right_name == "working.png" and not injected:
                (destination / right_name).rename(saved)
                (destination / right_name).write_bytes(unknown)
                injected.append(True)
            return swap(left_fd, left_name, right_fd, right_name)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=race), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(injected, [True])
        self.assertEqual(saved.read_bytes(), original)
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "working.png").read_bytes(), unknown)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.assertIn("requires recovery", stderr.getvalue())

    def test_partial_unjournaled_stage_is_preserved(self):
        module = load_module(self.script, "synthetic_asset_partial_stage")
        partial = b"partial stage bytes"
        def fail_after_creation(path, writer, stage_fd):
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=stage_fd)
            with os.fdopen(fd, "wb") as stream: stream.write(partial)
            raise OSError("injected partial write")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=fail_after_creation), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "working.png").read_bytes(), partial)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse((destination / "working.png").exists())

    def test_unknown_stage_file_after_journal_stops_before_publication(self):
        self.invoke()
        destination = self.root / "assets/private"
        names = ("working.png", "scene.js", "provenance.json", ".azhou-assets-receipt.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=24))
        module = load_module(self.script, "synthetic_asset_stage_foreign")
        write_journal = module.write_journal
        def insert_unknown(state, state_fd, stage, *args):
            result = write_journal(state, state_fd, stage, *args)
            (stage / "foreign.txt").write_bytes(b"do not delete")
            return result
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "write_journal", side_effect=insert_unknown), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "foreign.txt").read_bytes(), b"do not delete")
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())

    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires owned child SIGKILL")
    def test_killed_child_update_can_be_recovered_without_source(self):
        self.invoke()
        destination = self.root / "assets/private"
        names = ("working.png", "scene.js", "provenance.json", ".azhou-assets-receipt.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=31))
        code = ("import importlib.util,os,signal,subprocess,sys\n"
                "spec=importlib.util.spec_from_file_location('asset_killed',sys.argv[1])\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "real=m.swap_files\n"
                "def crash(*args):\n real(*args);os.kill(os.getpid(),signal.SIGKILL)\n"
                "m.swap_files=crash\n"
                "m.subprocess.run=lambda *a,**k:subprocess.CompletedProcess([],0)\n"
                "m.subprocess.check_output=lambda *a,**k:b''\n"
                "sys.argv=[sys.argv[1],'--source',sys.argv[2]];m.main()\n")
        child = subprocess.run([sys.executable, "-B", "-c", code, str(self.script), str(self.source)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, -signal.SIGKILL, child.stderr)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.source.unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("rolled-back", stdout.getvalue())
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires owned child SIGKILL")
    def test_killed_first_publication_retracts_only_created_files(self):
        code = ("import importlib.util,os,signal,subprocess,sys\n"
                "spec=importlib.util.spec_from_file_location('asset_first_killed',sys.argv[1])\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "real=m.os.link\n"
                "def crash(*args,**kwargs):\n real(*args,**kwargs);os.kill(os.getpid(),signal.SIGKILL)\n"
                "m.os.link=crash\n"
                "m.subprocess.run=lambda *a,**k:subprocess.CompletedProcess([],0)\n"
                "m.subprocess.check_output=lambda *a,**k:b''\n"
                "sys.argv=[sys.argv[1],'--source',sys.argv[2]];m.main()\n")
        child = subprocess.run([sys.executable, "-B", "-c", code, str(self.script), str(self.source)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, -signal.SIGKILL, child.stderr)
        destination = self.root / "assets/private"
        self.assertTrue((destination / "working.png").is_file())
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.source.unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("rolled-back", stdout.getvalue())
        self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires owned child SIGKILL")
    def test_killed_child_after_publish_finishes_commit_without_source(self):
        self.invoke()
        destination = self.root / "assets/private"
        image = png_header(1254, 1254, padding=33)
        self.source.write_bytes(image)
        code = ("import importlib.util,os,signal,subprocess,sys\n"
                "spec=importlib.util.spec_from_file_location('asset_killed_done',sys.argv[1])\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "real=m.recover_transaction;calls=[]\n"
                "def crash_after_publish(*args):\n calls.append(1)\n if len(calls)==2: os.kill(os.getpid(),signal.SIGKILL)\n return real(*args)\n"
                "m.recover_transaction=crash_after_publish\n"
                "m.subprocess.run=lambda *a,**k:subprocess.CompletedProcess([],0)\n"
                "m.subprocess.check_output=lambda *a,**k:b''\n"
                "sys.argv=[sys.argv[1],'--source',sys.argv[2]];m.main()\n")
        child = subprocess.run([sys.executable, "-B", "-c", code, str(self.script), str(self.source)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, -signal.SIGKILL, child.stderr)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.source.unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("committed", stdout.getvalue())
        self.assertEqual((destination / "working.png").read_bytes(), image)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_private_directory_symlink_is_rejected_without_touching_target(self):
        assets = self.root / "assets"
        assets.mkdir()
        outside = Path(self.temporary.name) / "foreign-directory"
        outside.mkdir()
        (outside / "user.txt").write_bytes(b"do not touch")
        (assets / "private").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual((outside / "user.txt").read_bytes(), b"do not touch")
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ["user.txt"])
        self.assertTrue((assets / "private").is_symlink())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO")
    def test_fifo_output_is_rejected_without_waiting(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        fifo = destination / "scene.js"
        os.mkfifo(fifo)
        with self.assertRaises(SystemExit): self.invoke()
        self.assertTrue(fifo.exists())
        self.assertFalse((destination / "working.png").exists())

    def test_receipt_symlink_is_preserved_without_following_it(self):
        self.invoke()
        destination = self.root / "assets/private"
        receipt = self.state / ".azhou-assets-receipt.json"
        saved = Path(self.temporary.name) / "saved-receipt.json"
        receipt.rename(saved)
        outside = Path(self.temporary.name) / "foreign-receipt"
        outside.write_bytes(b"do not touch")
        receipt.symlink_to(outside)
        before = (destination / "working.png").read_bytes()
        with self.assertRaises(SystemExit): self.invoke()
        self.assertEqual(outside.read_bytes(), b"do not touch")
        self.assertEqual((destination / "working.png").read_bytes(), before)
        self.assertTrue(receipt.is_symlink())
        self.assertTrue(saved.is_file())

    def test_swap_that_succeeds_then_raises_is_proven_and_rolled_back(self):
        self.invoke()
        destination = self.root / "assets/private"
        names = ("working.png", "scene.js", "provenance.json", ".azhou-assets-receipt.json")
        before = {name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}
        self.source.write_bytes(png_header(1254, 1254, padding=41))
        module = load_module(self.script, "synthetic_asset_swap_uncertain")
        swap = module.swap_files
        calls = []
        def success_then_error(*args):
            swap(*args)
            calls.append(True)
            if len(calls) == 1: raise OSError("injected error after successful exchange")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=success_then_error), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertGreaterEqual(len(calls), 2)
        self.assertIn("prior outputs restored", stderr.getvalue())
        self.assertEqual({name: ((self.state if name == ".azhou-assets-receipt.json" else destination) / name).read_bytes() for name in names}, before)
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_partial_cleanup_preserves_remaining_stage_and_journal(self):
        self.invoke()
        destination = self.root / "assets/private"
        image = png_header(1254, 1254, padding=45)
        self.source.write_bytes(image)
        module = load_module(self.script, "synthetic_asset_cleanup_partial")
        unlink = module.checked_unlink
        calls = []
        def fail_after_unlink(directory_fd, name, expected):
            unlink(directory_fd, name, expected)
            if name == "working.png" and not calls:
                calls.append(True)
                raise OSError("injected partial cleanup")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "checked_unlink", side_effect=fail_after_unlink), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(calls, [True])
        self.assertEqual((destination / "working.png").read_bytes(), image)
        journal = self.state / ".azhou-assets-transaction.json"
        journal_before = journal.read_bytes()
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertIn("requires recovery", stderr.getvalue())
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
        self.assertEqual(journal.read_bytes(), journal_before)
        self.assertTrue(stages[0].is_dir())
        self.assertEqual((destination / "working.png").read_bytes(), image)

    def test_staged_image_corruption_never_publishes(self):
        module = load_module(self.script, "synthetic_asset_short_stage")
        stdout, stderr = io.StringIO(), io.StringIO()
        def short_copy(source, destination, length): destination.write(source.read(8))
        with mock.patch.object(module.shutil, "copyfileobj", side_effect=short_copy), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        self.assertFalse((destination / "working.png").exists())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())

    def test_staged_scene_corruption_never_publishes(self):
        module = load_module(self.script, "synthetic_asset_bad_scene")
        stage_file = module.stage_file
        def corrupt(path, writer, stage_fd):
            result = stage_file(path, writer, stage_fd)
            if path.name == "scene.js": path.write_bytes(b"incorrect scene")
            return result
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=corrupt), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        destination = self.root / "assets/private"
        self.assertFalse((destination / "working.png").exists())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())

    def test_identical_repeat_keeps_private_fingerprint_and_identities_stable(self):
        self.invoke()
        destination = self.root / "assets/private"
        receipt = self.state / ".azhou-assets-receipt.json"
        paths = [destination / name for name in ("working.png", "scene.js", "provenance.json")] + [receipt]
        before = {str(path): (path.stat().st_dev, path.stat().st_ino, path.read_bytes()) for path in paths}
        def fingerprint():
            return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(destination.iterdir())}
        inputs = fingerprint()
        self.invoke()
        self.assertEqual({str(path): (path.stat().st_dev, path.stat().st_ino, path.read_bytes()) for path in paths}, before)
        self.assertEqual(fingerprint(), inputs)
        self.assertEqual(sorted(path.name for path in destination.iterdir()), ["provenance.json", "scene.js", "working.png"])
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_unignored_local_transaction_state_prevents_preparation(self):
        module = load_module(self.script, "synthetic_asset_git_guard")
        success = subprocess.CompletedProcess(["git", "check-ignore"], 0)
        fail = subprocess.CompletedProcess(["git", "check-ignore"], 1)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", side_effect=[success, fail]), \
                mock.patch.object(subprocess, "check_output", return_value=b""), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertIn("transaction state must be ignored", stderr.getvalue())
        self.assertFalse((self.root / "assets/private").exists())
        self.assertFalse(self.state.exists())

    def test_preparation_refuses_when_project_build_lock_is_held(self):
        lock = load_module(self.root / "tools/build-lock.py", "synthetic_existing_build_lock")
        with lock.acquired():
            with self.assertRaises(SystemExit): self.invoke()
        self.assertIn("build lock", self.stderr.getvalue())
        destination = self.root / "assets/private"
        self.assertFalse((destination / "working.png").exists())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))

    def test_direct_startup_build_contends_and_accepts_verified_inherited_lock(self):
        builder_path = self.root / "tools/build-startup.py"
        shutil.copy2(TOOLS / "build-startup.py", builder_path)
        lock = load_module(self.root / "tools/build-lock.py", "synthetic_startup_build_lock")
        code = ("import importlib.util,sys\n"
                "from pathlib import Path\n"
                "spec=importlib.util.spec_from_file_location('synthetic_child_builder',sys.argv[1])\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "try: m.build_startup(Path(sys.argv[2])/'.build/stage',root=Path(sys.argv[2]))\n"
                "except Exception as e:\n"
                " print(str(e))\n"
                " sys.exit(3 if '另一个构建' in str(e) else 4 if 'verify-artifacts.py' in str(e) else 5)\n")
        command = [sys.executable, "-B", "-c", code, str(builder_path), str(self.root)]
        environment = os.environ.copy()
        environment.pop("_AZHOU_BUILD_LOCK_FD", None)
        with lock.acquired() as fd:
            blocked = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(blocked.returncode, 3, blocked.stdout + blocked.stderr)
            inherited = dict(environment, _AZHOU_BUILD_LOCK_FD=str(fd))
            passed = subprocess.run(command, env=inherited, pass_fds=(fd,), capture_output=True, text=True, timeout=5)
            self.assertEqual(passed.returncode, 4, passed.stdout + passed.stderr)
        self.assertFalse((self.root / ".build/stage").exists())

    def test_build_lock_replacement_during_publication_preserves_transaction(self):
        self.invoke()
        destination = self.root / "assets/private"
        original = (destination / "working.png").read_bytes()
        self.source.write_bytes(png_header(1254, 1254, padding=49))
        module = load_module(self.script, "synthetic_asset_lock_replacement")
        swap = module.swap_files
        lock_path = self.root / ".build/.agent-skin-build.lock"
        saved_lock = self.root / ".build/saved-lock"
        changed = []
        def replace_lock_after_swap(*args):
            swap(*args)
            if not changed:
                lock_path.rename(saved_lock)
                lock_path.write_bytes(b"foreign lock")
                changed.append(True)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=replace_lock_after_swap), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(changed, [True])
        self.assertEqual(lock_path.read_bytes(), b"foreign lock")
        self.assertTrue(saved_lock.is_file())
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "working.png").read_bytes(), original)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.assertIn("requires recovery", stderr.getvalue())

    def test_recover_refuses_missing_output_when_journal_exists(self):
        self.state.mkdir(parents=True)
        journal = self.state / ".azhou-assets-transaction.json"
        journal.write_bytes(b"preserve pending transaction")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
        self.assertNotIn("No private asset transaction found", stdout.getvalue())
        self.assertEqual(journal.read_bytes(), b"preserve pending transaction")
        self.assertFalse((self.root / "assets/private").exists())

    def test_recover_refuses_local_directory_symlink(self):
        outside = Path(self.temporary.name) / "foreign-local"
        outside.mkdir()
        (outside / "user.txt").write_bytes(b"do not touch")
        (self.root / ".local").symlink_to(outside, target_is_directory=True)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): runpy.run_path(str(self.script), run_name="__main__")
        self.assertEqual((outside / "user.txt").read_bytes(), b"do not touch")
        self.assertTrue((self.root / ".local").is_symlink())
        self.assertNotIn("No private asset transaction found", stdout.getvalue())

    def test_staging_directory_replaced_before_write_does_not_touch_foreign_directory(self):
        module = load_module(self.script, "synthetic_asset_stage_dir_race")
        stage_file = module.stage_file
        saved = self.state / "moved-original-stage"
        replaced = []
        def swap_stage(path, writer, stage_fd):
            if not replaced:
                path.parent.rename(saved)
                path.parent.mkdir()
                (path.parent / "foreign.txt").write_bytes(b"do not modify")
                replaced.append(path.parent)
            return stage_file(path, writer, stage_fd)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "stage_file", side_effect=swap_stage), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(len(replaced), 1)
        self.assertEqual((replaced[0] / "foreign.txt").read_bytes(), b"do not modify")
        self.assertFalse((replaced[0] / "working.png").exists())
        self.assertEqual((saved / "working.png").read_bytes(), self.source.read_bytes())
        self.assertFalse((self.root / "assets/private/working.png").exists())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())

    def test_private_directory_replaced_at_swap_does_not_touch_foreign_directory(self):
        self.invoke()
        destination = self.root / "assets/private"
        original = (destination / "working.png").read_bytes()
        saved = self.root / "assets/saved-private"
        self.source.write_bytes(png_header(1254, 1254, padding=51))
        module = load_module(self.script, "synthetic_asset_output_root_race")
        swap = module.swap_files
        changed = []
        def replace_before_swap(*args):
            if not changed:
                destination.rename(saved)
                destination.mkdir()
                (destination / "working.png").write_bytes(b"foreign file")
                changed.append(True)
            return swap(*args)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=replace_before_swap), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(changed, [True])
        self.assertEqual((destination / "working.png").read_bytes(), b"foreign file")
        self.assertEqual(sorted(path.name for path in destination.iterdir()), ["working.png"])
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "working.png").read_bytes(), original)
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        self.assertTrue(saved.is_dir())

    def test_state_directory_replaced_during_rollback_preserves_foreign_directory(self):
        self.invoke()
        destination = self.root / "assets/private"
        original = (destination / "working.png").read_bytes()
        self.source.write_bytes(png_header(1254, 1254, padding=53))
        module = load_module(self.script, "synthetic_asset_recovery_root_race")
        swap = module.swap_files
        def crash_after_swap(*args):
            swap(*args)
            raise SystemExit("simulated process exit")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "swap_files", side_effect=crash_after_swap), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        saved = self.state.parent / "saved-asset-state"
        changed = []
        def move_state_before_rollback(*args):
            if not changed:
                self.state.rename(saved)
                self.state.mkdir()
                (self.state / "foreign.txt").write_bytes(b"do not modify")
                changed.append(True)
            return swap(*args)
        with mock.patch.object(module, "swap_files", side_effect=move_state_before_rollback), \
                mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit): module.main()
        self.assertEqual(changed, [True])
        self.assertEqual((self.state / "foreign.txt").read_bytes(), b"do not modify")
        self.assertEqual(sorted(path.name for path in self.state.iterdir()), ["foreign.txt"])
        self.assertEqual((destination / "working.png").read_bytes(), original)
        self.assertTrue((saved / ".azhou-assets-transaction.json").is_file())
        self.assertEqual(len(list(saved.glob(".azhou-assets-stage-*"))), 1)

    def test_output_fsync_failure_after_final_swap_preserves_old_backups(self):
        self.invoke()
        destination = self.root / "assets/private"
        old_working = (destination / "working.png").read_bytes()
        output_identity = destination.stat()
        self.source.write_bytes(png_header(1254, 1254, padding=57))
        module = load_module(self.script, "synthetic_asset_fsync_failure")
        swap, fsync = module.swap_files, module.os.fsync
        swaps, failures = [], []
        def tracked_swap(*args):
            result = swap(*args)
            swaps.append(True)
            return result
        def fail_output(fd):
            info = os.fstat(fd)
            if len(swaps) >= 4 and (info.st_dev, info.st_ino) == (output_identity.st_dev, output_identity.st_ino):
                failures.append(True)
                raise OSError("injected output fsync failure")
            return fsync(fd)
        stdout, stderr = io.StringIO(), io.StringIO()
        error = None
        with mock.patch.object(module, "swap_files", side_effect=tracked_swap), \
                mock.patch.object(module.os, "fsync", side_effect=fail_output), \
                mock.patch.object(sys, "argv", [str(self.script), "--source", str(self.source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try: module.main()
            except SystemExit as exc: error = exc
        self.assertEqual(len(swaps), 4)
        self.assertTrue(failures)
        self.assertIsNotNone(error, "unsynced output must not be reported as committed")
        self.assertTrue((self.state / ".azhou-assets-transaction.json").is_file())
        stages = list(self.state.glob(".azhou-assets-stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / "working.png").read_bytes(), old_working)
        self.source.unlink()
        with mock.patch.object(sys, "argv", [str(self.script), "--recover"]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result), \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        self.assertIn("committed", stdout.getvalue())
        self.assertFalse((self.state / ".azhou-assets-transaction.json").exists())
        self.assertFalse(list(self.state.glob(".azhou-assets-stage-*")))
        self.assertEqual((destination / "working.png").read_bytes(), png_header(1254, 1254, padding=57))

    def test_legacy_adoption_refuses_unrecognized_contents(self):
        self.invoke()
        destination = self.root / "assets/private"
        (self.state / ".azhou-assets-receipt.json").unlink()
        files = {name: (destination / name).read_bytes() for name in ("working.png", "scene.js", "provenance.json")}
        cases = (
            ("provenance.json", b'{}', "provenance"),
            ("working.png", b'not a PNG', "recognized PNG"),
            ("working.png", png_header(1, 1), "dimensions"),
            ("working.png", png_header(1254, 1254, padding=1), "provenance differ"),
        )
        for name, contents, message in cases:
            with self.subTest(name=name, message=message):
                for filename, data in files.items():
                    (destination / filename).write_bytes(data)
                (destination / name).write_bytes(contents)
                before = {filename: (destination / filename).read_bytes() for filename in files}
                with self.assertRaises(SystemExit):
                    self.invoke(adopt=True)
                self.assertIn(message, self.stderr.getvalue())
                self.assertEqual({filename: (destination / filename).read_bytes() for filename in files}, before)
                self.assertFalse((self.state / ".azhou-assets-receipt.json").exists())

    def test_existing_file_read_handles_interrupt_and_rejects_midread_replacement(self):
        self.invoke()
        module = load_module(self.script, "synthetic_existing_asset_read")
        destination = self.root / "assets/private"
        fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        original_read = os.read
        calls = []
        def interrupted_once(file_fd, size):
            if not calls:
                calls.append(True)
                raise InterruptedError()
            return original_read(file_fd, size)
        with mock.patch.object(module.os, "read", side_effect=interrupted_once):
            info = module.file_info_at(fd, "working.png")
        self.assertEqual(info["sha256"], hashlib.sha256((destination / "working.png").read_bytes()).hexdigest())
        replacement = b"foreign replacement"
        calls.clear()
        def replace_after_read(file_fd, size):
            result = original_read(file_fd, size)
            if result and not calls:
                calls.append(True)
                (destination / "working.png").unlink()
                (destination / "working.png").write_bytes(replacement)
            return result
        with mock.patch.object(module.os, "read", side_effect=replace_after_read):
            with self.assertRaises(module.AssetConflict):
                module.file_info_at(fd, "working.png")
        self.assertEqual((destination / "working.png").read_bytes(), replacement)

    def test_unsupported_atomic_exchange_leaves_original_files_unchanged(self):
        module = load_module(self.script, "synthetic_unsupported_exchange")
        directory = Path(self.temporary.name)
        (directory / "old").write_bytes(b"old")
        (directory / "new").write_bytes(b"new")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        with mock.patch.object(module.sys, "platform", "unsupported"):
            with self.assertRaisesRegex(module.AssetConflict, "unavailable"):
                module.swap_files(fd, "old", fd, "new")
        self.assertEqual((directory / "old").read_bytes(), b"old")
        self.assertEqual((directory / "new").read_bytes(), b"new")

    def test_deeply_nested_transaction_record_is_preserved(self):
        destination = self.root / "assets/private"
        destination.mkdir(parents=True)
        self.state.mkdir(parents=True)
        journal = self.state / ".azhou-assets-transaction.json"
        contents = b'{"nested":' + b'[' * 100000 + b'0' + b']' * 100000 + b'}'
        journal.write_bytes(contents)
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertTrue("Invalid JSON record" in self.stderr.getvalue() or "not recognized" in self.stderr.getvalue())
        self.assertEqual(journal.read_bytes(), contents)
        self.assertFalse((destination / "working.png").exists())

    def test_rejects_using_the_output_copy_as_source(self):
        destination = self.root / "assets/private/working.png"
        destination.parent.mkdir(parents=True)
        shutil.copyfile(self.source, destination)
        with self.assertRaises(SystemExit):
            self.invoke(destination)
        self.assertIn("original approved source", self.stderr.getvalue())
        self.assertFalse((destination.parent / "provenance.json").exists())

    def test_prepares_large_images_without_corrupting_the_data_url(self):
        header = png_header(1254, 1254)
        for length in (49151, 49152, 49153, 98305):
            with self.subTest(length=length):
                image = header + b"x" * (length - len(header))
                self.source.write_bytes(image)
                self.invoke()
                destination = self.root / "assets/private"
                self.assertEqual((destination / "working.png").read_bytes(), image)
                expected = 'window.AZHOU_WORKING_IMAGE = "data:image/png;base64,' + base64.b64encode(image).decode("ascii") + '";\n'
                self.assertEqual((destination / "scene.js").read_text(encoding="utf-8"), expected)
                provenance = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(provenance["sha256"], hashlib.sha256(image).hexdigest())

    def test_prepares_complete_image_when_source_reads_are_fragmented(self):
        image = png_header(1254, 1254, padding=1000)
        self.source.write_bytes(image)
        original_read = os.read
        source_info = self.source.stat()
        fragmented = []
        def read_fragment(fd, size):
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) == (source_info.st_dev, source_info.st_ino):
                fragmented.append(True)
                return original_read(fd, min(size, 7))
            return original_read(fd, size)
        with mock.patch.object(os, "read", side_effect=read_fragment):
            self.invoke()
        self.assertGreater(len(fragmented), 1)
        destination = self.root / "assets/private"
        self.assertEqual((destination / "working.png").read_bytes(), image)
        expected = 'window.AZHOU_WORKING_IMAGE = "data:image/png;base64,' + base64.b64encode(image).decode("ascii") + '";\n'
        self.assertEqual((destination / "scene.js").read_text(encoding="utf-8"), expected)

    def test_rejects_non_png_and_unreviewed_dimensions_or_color(self):
        cases = (
            (b"not a PNG", "must be a PNG"),
            (png_header(1253, 1254), "new visual review"),
            (png_header(1254, 1254, color=2), "new visual review"),
        )
        for data, message in cases:
            with self.subTest(message=message):
                self.source.write_bytes(data)
                with self.assertRaises(SystemExit):
                    self.invoke()
                self.assertIn(message, self.stderr.getvalue())
        self.assertFalse((self.root / "assets/private/working.png").exists())

    def test_requires_ignored_untracked_private_output(self):
        self.run_result = subprocess.CompletedProcess(["git", "check-ignore"], 1)
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertIn("must be ignored", self.stderr.getvalue())
        self.assertFalse((self.root / "assets/private/working.png").exists())

        self.run_result = subprocess.CompletedProcess(["git", "check-ignore"], 0)
        self.tracked = b"assets/private/working.png\n"
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertIn("Private assets are tracked", self.stderr.getvalue())
        self.assertFalse((self.root / "assets/private/working.png").exists())

    def test_missing_source_fails_before_any_private_output_is_written(self):
        with self.assertRaises(FileNotFoundError):
            self.invoke(Path(self.temporary.name) / "missing.png")
        self.assertFalse((self.root / "assets/private").exists())


class StartupBuilderBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module(TOOLS / "build-startup.py", "agent_skin_canonical_startup_builder")

    def startup_fixture(self):
        helpers = load_module(TOOLS / "test-startup-build.py", "agent_skin_startup_edge_fixtures")
        temporary = tempfile.TemporaryDirectory(prefix="agent-skin-startup-edge-")
        root = (Path(temporary.name) / "source").resolve()
        helpers.clone_source_tree(root)
        bundle = root / ".build/azhou-stage.edge/azhou-payload"
        bundle.mkdir(parents=True)
        self.addCleanup(temporary.cleanup)
        return helpers, root, bundle

    def test_png_parser_rejects_truncation_crc_header_encoding_and_decoded_pixels(self):
        module = self.module
        good = png_bytes()
        bad_crc = bytearray(good)
        bad_crc[29] ^= 1
        invalid_header_size = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", b"x" * 12)
        oversized_chunk = b"\x89PNG\r\n\x1a\n" + (50).to_bytes(4, "big") + b"IHDR" + b"x" * 4
        invalid_first_chunk = b"\x89PNG\r\n\x1a\n" + png_chunk(b"tEXt", b"x")
        invalid_pngs = (
            (b"not png", "is not a PNG"),
            (b"\x89PNG\r\n\x1a\nX", "truncated"),
            (oversized_chunk, "chunk length is invalid"),
            (bytes(bad_crc), "CRC is invalid"),
            (invalid_header_size, "no valid IHDR"),
            (invalid_first_chunk, "no valid IHDR"),
            (png_bytes(width=0), "dimensions/encoding are invalid"),
            (png_bytes(width=8000, height=7000), "dimensions/encoding are invalid"),
            (png_bytes(depth=16), "dimensions/encoding are invalid"),
            (png_bytes(color=0), "dimensions/encoding are invalid"),
            (png_bytes(compression=1), "dimensions/encoding are invalid"),
            (png_bytes(filtering=1), "dimensions/encoding are invalid"),
            (png_bytes(interlace=1), "dimensions/encoding are invalid"),
            (good[:-12], "did not finish"),
            (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
             + png_chunk(b"IEND", b""), "incomplete"),
            (good + b"tail", "incomplete"),
            (png_bytes(idat=b"broken zlib"), "cannot be decoded"),
            (png_bytes(raw=b"\x00"), "decoded pixels are invalid"),
            (png_bytes(raw=b"\x05\x10\x20\x30\xff"), "decoded pixels are invalid"),
        )
        for data, message in invalid_pngs:
            with self.subTest(message=message, size=len(data)):
                with self.assertRaisesRegex(RuntimeError, message):
                    module._png_data(data, "case.png")
        self.assertEqual(module._png_data(good, "good.png"), (1, 1))

    def test_contour_validation_rejects_unbounded_invalid_and_undrawable_paths(self):
        module = self.module
        for value in (None, []):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "bounded contour paths"):
                module._validate_contours(value)
        for value in (["bad"], [[[0, 0]]], [[0, 0]], [[[0, 0], [float("inf"), 1]]],
                      [[[0, 0], [-1, 1]]], [[[0, 0], [1536, 1025]]],
                      [[[0, 0], [0, 0]]]):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                module._validate_contours(value)
        self.assertEqual(module._validate_contours([[[0, 0], [1, 1]]]), (1, 2))

    def test_source_extractors_enforce_single_self_contained_entry_points(self):
        module = self.module
        valid_animation = "function installAnimation() { return true; }\n/* Local preview adapter. Ticket 05 extracts only installAnimation above. */\n"
        self.assertEqual(module._extract_animation(valid_animation), "function installAnimation() { return true; }")
        for value in ("function installAnimation() {}", valid_animation + valid_animation,
                      "function installAnimation() {\n/* Local preview adapter. Ticket 05 extracts only installAnimation above. */\n"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                module._extract_animation(value)
        self.assertEqual(module._module_function("export function run() {}", "export function run(",
                                                 "function run(", "fixture"), "function run() {}")
        for value in ("export function run() {}\nimport './x.js';", "export function run() {}\nexport function run() {}"):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "one self-contained module"):
                module._module_function(value, "export function run(", "function run(", "fixture")

    def test_private_inputs_and_metadata_reject_missing_build_material(self):
        module = self.module
        with tempfile.TemporaryDirectory(prefix="agent-skin-startup-inputs-") as temporary:
            root = Path(temporary)
            for name in ("hub-package.json", "theme-config.json"):
                shutil.copy2(PACKAGE / name, root / name)
            artifacts = load_module(TOOLS / "verify-artifacts.py", "agent_skin_require_assets_fixture")
            names = ("working.png", "wallpaper-scene-q-v3.png", "entry-avatar.png", "app-icon/source.png")
            for name in names:
                path = root / "assets/azhou" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            self.assertEqual({name: root / "assets/azhou" / name for name in names},
                             module._require_assets(root, artifacts))
            overlay = root / "assets/private/working.png"
            overlay.parent.mkdir(parents=True)
            overlay.write_bytes(b"overlay")
            self.assertEqual(overlay, module._require_assets(root, artifacts)["working.png"])
            (root / "assets/azhou/entry-avatar.png").unlink()
            with self.assertRaisesRegex(RuntimeError, "缺少阿舟素材 entry-avatar.png"):
                module._require_assets(root, artifacts)
            (root / "assets/azhou/entry-avatar.png").write_bytes(b"fixture")
            private = root / "assets/private"
            private.rename(root / "private-dir")
            private.symlink_to(root / "private-dir", target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "assets/private"):
                module._require_assets(root, artifacts)

        class Artifacts:
            STARTUP_REQUIRED_INPUTS = ("source.py", "hub-package.json")
            INPUT_FILES = ("hub-package.json",)
            def load_package_metadata(self, _root):
                return {"runtime_version": "1", "runtime_build": "2",
                        "build_inputs": list(self.STARTUP_REQUIRED_INPUTS),
                        "runtime_paths": list(self.STARTUP_REQUIRED_INPUTS)}

        with self.assertRaisesRegex(RuntimeError, "source.py"):
            module._check_metadata(Path("."), Artifacts(), {})
        artifacts = Artifacts()
        artifacts.INPUT_FILES = artifacts.STARTUP_REQUIRED_INPUTS
        with self.assertRaisesRegex(RuntimeError, "build inputs/runtime paths"):
            module._check_metadata(Path("."), artifacts, {"identity": {"version": "other", "build": "2"}})

    def test_dsh_host_builds_the_codex_style_dsh_adapter_payload(self):
        module = self.module
        verifier = load_module(TOOLS / "verify-artifacts.py", "agent_skin_dsh_boundary_verifier")
        payload = module._build_script(PACKAGE, {}, "body{}", verifier, host="dsh")
        self.assertTrue(payload.startswith("(() => {\n"))
        self.assertTrue(payload.endswith("})()\n"))
        self.assertEqual(payload.count("function createDSHPageAdapter("), 1)
        self.assertNotIn("createCodexPageAdapter(", payload)
        self.assertFalse(payload.startswith("((controllerMetadata) => {"))
        self.assertIn('const pageAdapter = createDSHPageAdapter(globalThis, { build: { version: APP_VERSION, '
                      'buildNumber: "' + verifier.BUILD + '" }, sidebarEntry: false }, {', payload)
        self.assertIn("    installRenderer,\n    createWallpaperApplicator,\n  });", payload)
        self.assertIn("return bootstrapStartup({", payload)
        adapter = (PACKAGE / "extension/hosts/dsh.mjs").read_text(encoding="utf-8")
        self.assertIn(adapter.replace("export function createDSHPageAdapter(",
                                      "function createDSHPageAdapter(", 1).strip(), payload)
        with self.assertRaisesRegex(RuntimeError, "Unsupported startup host"):
            module._build_script(PACKAGE, {}, "body{}", verifier, host="web")

    def test_dsh_adapter_module_rejects_imports_and_unbound_entries(self):
        module = self.module
        verifier = load_module(TOOLS / "verify-artifacts.py", "agent_skin_dsh_adapter_verifier")
        with tempfile.TemporaryDirectory(prefix="agent-skin-dsh-adapter-negative-") as temporary:
            root = Path(temporary) / "source"
            for relative in ("animation.js", "image-settings.js", "extension/renderer.mjs",
                             "extension/codex-page-adapter.mjs", "extension/bootstrap.mjs",
                             "extension/hosts/dsh.mjs", "wallpaper/renderer.js", "wallpaper/apply.js",
                             "localization.js", "vendor/dream-image-metadata.mjs"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(PACKAGE / relative, target)
            adapter_path = root / "extension/hosts/dsh.mjs"
            original = adapter_path.read_text(encoding="utf-8")
            adapter_path.write_text(original + "\nimport x from 'y';\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "DSH page adapter"):
                module._build_script(root, {}, "body{}", verifier, host="dsh")
            adapter_path.write_text(original + "\nexport function createDSHPageAdapter() {}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "DSH page adapter"):
                module._build_script(root, {}, "body{}", verifier, host="dsh")
            adapter_path.write_text(original, encoding="utf-8")
            self.assertIn("function createDSHPageAdapter(",
                          module._build_script(root, {}, "body{}", verifier, host="dsh"))

    def test_dsh_required_inputs_and_historical_sets_stay_composed_and_frozen(self):
        verifier = load_module(TOOLS / "verify-artifacts.py", "agent_skin_dsh_inputs_verifier")
        self.assertEqual(verifier.DSH_PLUGIN_REQUIRED_INPUTS,
                         (*verifier.STARTUP_REQUIRED_INPUTS,
                          "extension/hosts/dsh.mjs", "tools/build-dsh-plugin.py"))
        self.assertIn("extension/hosts/dsh.mjs", verifier.INPUT_FILES)
        self.assertIn("tools/build-dsh-plugin.py", verifier.INPUT_FILES)
        for name in ("PRE_PAGE_ADAPTER_STARTUP_REQUIRED_INPUTS",
                     "PRE_IMAGE_METADATA_STARTUP_REQUIRED_INPUTS",
                     "PREVIOUS_THEME_STARTUP_REQUIRED_INPUTS",
                     "LEGACY_STARTUP_REQUIRED_INPUTS",
                     "STARTUP_REQUIRED_INPUTS"):
            frozen = getattr(verifier, name)
            with self.subTest(input_set=name):
                self.assertNotIn("extension/hosts/dsh.mjs", frozen)
                self.assertNotIn("tools/build-dsh-plugin.py", frozen)

    def test_script_builder_reports_missing_or_non_self_contained_sources_and_size_limit(self):
        module = self.module
        artifacts = mock.Mock(VERSION="0.5.1")
        self.assertTrue(module._build_script(PACKAGE, {}, "body { color: black; }", artifacts))
        with tempfile.TemporaryDirectory(prefix="agent-skin-startup-source-") as temporary:
            root = Path(temporary)
            for relative in ("animation.js", "image-settings.js", "extension/renderer.mjs",
                             "extension/codex-page-adapter.mjs", "extension/bootstrap.mjs",
                             "wallpaper/renderer.js", "wallpaper/apply.js", "localization.js",
                             "vendor/dream-image-metadata.mjs"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(PACKAGE / relative, target)

            vendor_source = root / "vendor/dream-image-metadata.mjs"
            vendor_source.unlink()
            with self.assertRaisesRegex(RuntimeError, r"Missing startup source module: .*vendor/dream-image-metadata\.mjs"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "vendor/dream-image-metadata.mjs", vendor_source)

            (root / "animation.js").unlink()
            with self.assertRaisesRegex(RuntimeError, "Missing startup source module"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "animation.js", root / "animation.js")
            (root / "extension/codex-page-adapter.mjs").write_text(
                "export function createCodexPageAdapter() {}\nimport './x.js';\n")
            with self.assertRaisesRegex(RuntimeError, "Codex page adapter"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "extension/codex-page-adapter.mjs", root / "extension/codex-page-adapter.mjs")
            (root / "localization.js").unlink()
            with self.assertRaisesRegex(RuntimeError, "Missing startup localization source"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "localization.js", root / "localization.js")
            (root / "localization.js").write_text("function createLocalization() {}\nimport './x.js';\n")
            with self.assertRaisesRegex(RuntimeError, "Localization source"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "localization.js", root / "localization.js")
            (root / "image-settings.js").write_text("function createImageSettings() {}\nexport {};\n")
            with self.assertRaisesRegex(RuntimeError, "Image Settings source"):
                module._build_script(root, {}, "", artifacts)
            shutil.copyfile(PACKAGE / "image-settings.js", root / "image-settings.js")
            (root / "extension/renderer.mjs").write_text(
                "export function installStartup() {}\nfunction installStartup() {}\n")
            (root / "wallpaper/renderer.js").write_text("export async function installRenderer() {}\n")
            with self.assertRaisesRegex(RuntimeError, "unexpected entry count"):
                module._build_script(root, {}, "", artifacts)
        with self.assertRaisesRegex(RuntimeError, "strict 24 MiB"):
            module._build_script(PACKAGE, {}, "x" * module.MAX_STARTUP_BYTES, artifacts)

    def test_startup_cli_reports_success_and_build_errors(self):
        helpers = load_module(TOOLS / "test-startup-build.py", "agent_skin_startup_cli_fixtures")
        with tempfile.TemporaryDirectory(prefix="agent-skin-startup-cli-") as temporary:
            root = (Path(temporary) / "source").resolve()
            helpers.clone_source_tree(root)
            self.assertEqual((root / "tools/build-startup.py").read_bytes(), (TOOLS / "build-startup.py").read_bytes())
            bundle = root / ".build/azhou-stage.cli/azhou-payload"
            bundle.mkdir(parents=True)

            def vision(command, **kwargs):
                if command[0] != "xcrun":
                    helpers.synthetic_png(Path(command[3]), 512, 512, lambda _x, _y: (50, 60, 70, 255))
                    helpers.synthetic_png(Path(command[4]), 1536, 1024, lambda _x, _y: (30, 40, 50, 255))
                    Path(command[5]).write_text(json.dumps([[[1, 1], [2, 2]]]), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)

            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", [str(root / "tools/build-startup.py"), "--bundle", str(bundle)]), \
                    mock.patch.object(subprocess, "check_output", return_value="arm64\n"), \
                    mock.patch.object(subprocess, "run", side_effect=vision), contextlib.redirect_stdout(stdout), \
                    self.assertRaises(SystemExit) as success:
                runpy.run_path(str(root / "tools/build-startup.py"), run_name="__main__")
            self.assertEqual(success.exception.code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["kind"], "startupPayload")
            self.assertEqual(result["scope"], "hidden local build payload and preview defaults; no install or host writes")

            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", [str(root / "tools/build-startup.py"), "--bundle",
                                                  str(root / ".build/not-a-stage/azhou-payload")]), \
                    contextlib.redirect_stderr(stdout), self.assertRaises(SystemExit) as error:
                runpy.run_path(str(root / "tools/build-startup.py"), run_name="__main__")
            self.assertEqual(error.exception.code, 1)
            self.assertIn("启动载荷构建失败", stdout.getvalue())

    def test_startup_cli_updates_image_metadata_reader_and_rejects_missing_source(self):
        helpers = load_module(TOOLS / "test-startup-build.py", "agent_skin_reader_cli_fixtures")
        builder = load_module(TOOLS / "build-startup.py", "agent_skin_reader_cli_builder")
        with tempfile.TemporaryDirectory(prefix="agent-skin-reader-cli-") as temporary:
            root = (Path(temporary) / "source").resolve()
            helpers.clone_source_tree(root)
            script = root / "tools/build-startup.py"
            reader = root / "image-metadata-reader.js"
            reader.write_text("stale reader\n", encoding="utf-8")

            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", [str(script), "--update-image-metadata-reader"]), \
                    contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as success:
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(success.exception.code, 0)
            self.assertIn("Updated image-metadata-reader.js", stdout.getvalue())
            self.assertEqual(reader.read_text(encoding="utf-8"), builder.image_metadata_reader_source(root))

            stderr = io.StringIO()
            with mock.patch.object(sys, "argv", [str(script)]), contextlib.redirect_stderr(stderr), \
                    self.assertRaises(SystemExit) as missing_bundle:
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(missing_bundle.exception.code, 2)
            self.assertIn("--bundle is required unless --update-image-metadata-reader is used", stderr.getvalue())

            (root / "vendor/dream-image-metadata.mjs").unlink()
            stderr = io.StringIO()
            with mock.patch.object(sys, "argv", [str(script), "--update-image-metadata-reader"]), \
                    contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as missing_source:
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(missing_source.exception.code, 1)
            self.assertIn("尺寸解析器适配生成失败", stderr.getvalue())

    def test_startup_build_fails_closed_for_missing_sources_generation_and_output_bounds(self):
        module = self.module
        helpers, root, bundle = self.startup_fixture()
        artifacts = load_module(root / "tools/verify-artifacts.py", "agent_skin_startup_missing_inputs")
        artifacts.ROOT = root
        source_inputs = artifacts.source_inputs()
        with mock.patch.object(module.importlib.util, "spec_from_file_location", return_value=None), \
                self.assertRaisesRegex(RuntimeError, "Missing build verifier"):
            module.load_artifacts(root)

        class MissingInputArtifacts:
            STARTUP_REQUIRED_INPUTS = artifacts.STARTUP_REQUIRED_INPUTS
            INPUT_FILES = artifacts.STARTUP_REQUIRED_INPUTS
            def configure_build_host(self, host): artifacts.configure_build_host(host)
            def staged_path(self, path): return Path(path)
            def load_theme_config(self, _root, require_inputs=False):
                theme = json.loads((root / "theme-config.json").read_text(encoding="utf-8"))
                package = json.loads((root / "hub-package.json").read_text(encoding="utf-8"))
                theme["identity"].update(version=package["runtime_version"], build=str(package["runtime_build"]))
                return theme
            def load_package_metadata(self, _root):
                return json.loads((root / "hub-package.json").read_text(encoding="utf-8"))
            def resolved_assets(self, _root): return artifacts.resolved_assets(root)
            def source_inputs(self): return {}

        with mock.patch.object(module, "load_artifacts", return_value=MissingInputArtifacts()), \
                self.assertRaisesRegex(RuntimeError, "cannot bind every required source input"):
            module.build_startup(bundle, root=root)

        (root / "index.html").unlink()
        with mock.patch.object(module, "load_artifacts", return_value=artifacts), \
                mock.patch.object(artifacts, "source_inputs", return_value=source_inputs), \
                self.assertRaisesRegex(RuntimeError, "Missing preview source: index.html"):
            module.build_startup(bundle, root=root)
        (root / "index.html").write_text("<!doctype html>")
        (root / "tools/build-startup-assets.swift").unlink()
        with mock.patch.object(module, "load_artifacts", return_value=artifacts), \
                mock.patch.object(artifacts, "source_inputs", return_value=source_inputs), \
                mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                self.assertRaisesRegex(RuntimeError, "Missing build-only Swift Vision helper"):
            module.build_startup(bundle, root=root)

        (root / "tools/build-startup-assets.swift").write_text("// fixture")
        command = ["xcrun", "--sdk", "macosx", "swiftc"]
        with mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(module.subprocess, "run", side_effect=subprocess.CalledProcessError(
                    1, command, stderr="compiler fixture detail")), \
                self.assertRaisesRegex(RuntimeError, "compiler fixture detail"):
            module.build_startup(bundle, root=root)

        calls = 0
        def invalid_contour_data(command, **kwargs):
            nonlocal calls
            calls += 1
            if command[0] != "xcrun":
                helpers.synthetic_png(Path(command[3]), 512, 512, lambda _x, _y: (40, 50, 60, 255))
                helpers.synthetic_png(Path(command[4]), 1536, 1024, lambda _x, _y: (10, 20, 30, 255))
                Path(command[5]).write_text("{", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(module.subprocess, "run", side_effect=invalid_contour_data), \
                self.assertRaisesRegex(RuntimeError, "Vision helper did not return valid startup contour data"):
            module.build_startup(bundle, root=root)

        def bad_dimensions(command, **kwargs):
            if command[0] != "xcrun":
                helpers.synthetic_png(Path(command[3]), 511, 512, lambda _x, _y: (40, 50, 60, 255))
                helpers.synthetic_png(Path(command[4]), 1536, 1024, lambda _x, _y: (10, 20, 30, 255))
                Path(command[5]).write_text("[[[1,1],[2,2]]]")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(module.subprocess, "run", side_effect=bad_dimensions), \
                self.assertRaisesRegex(RuntimeError, "512×512 / 1536×1024"):
            module.build_startup(bundle, root=root)

        def good_artwork(command, **kwargs):
            if command[0] != "xcrun":
                helpers.synthetic_png(Path(command[3]), 512, 512, lambda _x, _y: (40, 50, 60, 255))
                helpers.synthetic_png(Path(command[4]), 1536, 1024, lambda _x, _y: (10, 20, 30, 255))
                Path(command[5]).write_text("[[[1,1],[2,2]]]")
            return subprocess.CompletedProcess(command, 0)
        theme = json.loads((root / "theme-config.json").read_text(encoding="utf-8"))
        entry_input = artifacts.resolve_asset(root, artifacts.asset_name(theme["identity"]["entryAvatarInput"]))[0]
        helpers.synthetic_png(entry_input, 1253, 1254, lambda _x, _y: (1, 2, 3, 255))
        with mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(module.subprocess, "run", side_effect=good_artwork), \
                self.assertRaisesRegex(RuntimeError, "1254×1254"):
            module.build_startup(bundle, root=root)

        helpers.synthetic_png(entry_input, 1254, 1254, lambda _x, _y: (1, 2, 3, 255))
        with mock.patch.object(module, "MAX_ENTRY_AVATAR_DATA_URL_BYTES", 1), \
                mock.patch.object(module.subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(module.subprocess, "run", side_effect=good_artwork), \
                self.assertRaisesRegex(RuntimeError, "data URL limit"):
            module.build_startup(bundle, root=root)


if __name__ == "__main__":
    unittest.main()

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
            with self.assertRaisesRegex(RuntimeError, "Missing private wallpaper artwork"):
                self.module.package(self.stage)
            outside = Path(self.temporary.name) / "outside.png"
            outside.write_bytes(png_header(1400, 1000))
            self.image.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, "Missing private wallpaper artwork"):
                self.module.package(self.stage)

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

    def test_cli_packages_the_requested_stage(self):
        script = self.root / "tools/build-wallpaper.py"
        shutil.copy2(TOOLS / script.name, script)
        self.assertEqual(script.read_bytes(), (TOOLS / script.name).read_bytes())
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(script), "--bundle", str(self.stage)]), \
                contextlib.redirect_stdout(stdout):
            runpy.run_path(str(script), run_name="__main__")
        self.assertIn("Packaged private Azhou wallpaper", stdout.getvalue())
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
        self.assertEqual(self.script.read_bytes(), (TOOLS / self.script.name).read_bytes())
        self.source = Path(self.temporary.name) / "approved-working.png"
        self.source.write_bytes(png_header(1254, 1254))
        self.run_result = subprocess.CompletedProcess(["git", "check-ignore"], 0)
        self.tracked = b""

    def invoke(self, source=None):
        source = source or self.source
        stdout = io.StringIO()
        self.stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.script), "--source", str(source)]), \
                mock.patch.object(subprocess, "run", return_value=self.run_result) as run, \
                mock.patch.object(subprocess, "check_output", return_value=self.tracked) as check_output, \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(self.stderr):
            runpy.run_path(str(self.script), run_name="__main__")
        return stdout.getvalue(), run.call_args, check_output.call_args

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

    def test_rejects_using_the_output_copy_as_source(self):
        destination = self.root / "assets/private/working.png"
        destination.parent.mkdir(parents=True)
        shutil.copyfile(self.source, destination)
        with self.assertRaises(SystemExit):
            self.invoke(destination)
        self.assertIn("original approved source", self.stderr.getvalue())
        self.assertFalse((destination.parent / "provenance.json").exists())

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
            theme = {"identity": {"entryAvatarInput": "assets/private/entry.png",
                                  "iconInput": "assets/private/icon.png"}}
            private = root / "assets/private"
            private.mkdir(parents=True)
            for relative in (*module.PRIVATE_STARTUP_INPUTS, "assets/private/entry.png", "assets/private/icon.png"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            module._require_private_inputs(root, theme)
            (root / module.PRIVATE_STARTUP_INPUTS[0]).unlink()
            with self.assertRaisesRegex(RuntimeError, "缺少本地启动默认素材"):
                module._require_private_inputs(root, theme)
            (root / module.PRIVATE_STARTUP_INPUTS[0]).write_bytes(b"fixture")
            private.rename(root / "private-dir")
            private.symlink_to(root / "private-dir", target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "缺少实体私有素材目录"):
                module._require_private_inputs(root, theme)

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

    def test_script_builder_reports_missing_or_non_self_contained_sources_and_size_limit(self):
        module = self.module
        artifacts = mock.Mock(VERSION="0.5.1")
        self.assertTrue(module._build_script(PACKAGE, {}, "body { color: black; }", artifacts))
        with tempfile.TemporaryDirectory(prefix="agent-skin-startup-source-") as temporary:
            root = Path(temporary)
            for relative in ("animation.js", "image-settings.js", "extension/renderer.mjs", "extension/bootstrap.mjs",
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
            def staged_path(self, path): return Path(path)
            def load_theme_config(self, _root, require_inputs=False):
                theme = json.loads((root / "theme-config.json").read_text(encoding="utf-8"))
                package = json.loads((root / "hub-package.json").read_text(encoding="utf-8"))
                theme["identity"].update(version=package["runtime_version"], build=str(package["runtime_build"]))
                return theme
            def load_package_metadata(self, _root):
                return json.loads((root / "hub-package.json").read_text(encoding="utf-8"))
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
        entry_input = root / theme["identity"]["entryAvatarInput"]
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

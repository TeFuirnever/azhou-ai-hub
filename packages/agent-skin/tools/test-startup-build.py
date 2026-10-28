#!/usr/bin/env python3
"""Isolated synthetic-image tests for the Agent Skin startup builder."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib


PACKAGE = Path(__file__).resolve().parents[1]
BUILDER_PATH = PACKAGE / "tools/build-startup.py"
APP_VERSION = "0.9.0"
APP_BUILD = "10"
BUILD_FILES = (
    "Native/App.swift",
    "Native/InstallRegistry.swift",
    "Native/Wallpaper.swift",
    "Native/StartupNativeTests.swift",
    "extension/renderer.mjs",
    "image-settings.js",
    "localization.js",
    "index.html",
    "style.css",
    "animation.js",
    "wallpaper/renderer.js",
    "wallpaper/wallpaper.css",
    "wallpaper/preview.html",
    "tools/build-macos.sh",
    "tools/build-wallpaper.py",
    "tools/test-startup-browser.mjs",
    "tools/test-startup-native.py",
    "tools/build-startup.py",
    "tools/build-startup-assets.swift",
    "tools/verify-artifacts.py",
    "hub-package.json",
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_png(path: Path, width: int, height: int, pixel) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(pixel(x, y))

    def chunk(kind: bytes, value: bytes) -> bytes:
        body = kind + value
        return struct.pack(">I", len(value)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    encoded = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
               + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def decode_png(path: Path):
    data = path.read_bytes()
    position = 8
    compressed = bytearray()
    width = height = color_type = None
    while position < len(data):
        size = int.from_bytes(data[position:position + 4], "big")
        kind = data[position + 4:position + 8]
        chunk = data[position + 8:position + 8 + size]
        if kind == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or color_type not in (2, 6) or interlace != 0:
                raise AssertionError("unexpected generated PNG layout")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
        position += size + 12
    channels = 3 if color_type == 2 else 4
    row_bytes = width * channels
    raw = zlib.decompress(bytes(compressed))
    pixels = bytearray(row_bytes * height)

    def paeth(left, above, upper_left):
        estimate = left + above - upper_left
        distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
        return (left, above, upper_left)[distances.index(min(distances))]

    for y in range(height):
        source_offset = y * (row_bytes + 1)
        filter_type = raw[source_offset]
        source = raw[source_offset + 1:source_offset + row_bytes + 1]
        target_offset = y * row_bytes
        for x, value in enumerate(source):
            left = pixels[target_offset + x - channels] if x >= channels else 0
            above = pixels[target_offset - row_bytes + x] if y else 0
            upper_left = pixels[target_offset - row_bytes + x - channels] if y and x >= channels else 0
            if filter_type == 1:
                value = (value + left) & 255
            elif filter_type == 2:
                value = (value + above) & 255
            elif filter_type == 3:
                value = (value + ((left + above) // 2)) & 255
            elif filter_type == 4:
                value = (value + paeth(left, above, upper_left)) & 255
            elif filter_type != 0:
                raise AssertionError("unsupported PNG filter")
            pixels[target_offset + x] = value

    def sample(x, y):
        offset = (y * width + x) * channels
        return tuple(pixels[offset:offset + channels])

    return width, height, sample


def clone_source_tree(destination: Path, *, private: bool = True) -> None:
    for relative in BUILD_FILES:
        source = PACKAGE / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
    if private:
        private_dir = destination / "assets/private"
        private_dir.mkdir(parents=True, exist_ok=True)
        synthetic_png(private_dir / "working.png", 640, 480,
                      lambda x, y: (230, 40, 60, 255) if x < 100 else (25, 50, 220, 255))
        synthetic_png(private_dir / "entry-avatar.png", 1254, 1254,
                      lambda x, y: (35, 185, 95, 255) if x < 600 else (35, 45, 220, 255))
        synthetic_png(private_dir / "wallpaper-scene-q-v3.png", 2000, 1000,
                      lambda x, y: ((245, 245, 245, 255) if 520 <= x < 720 and 180 <= y < 360
                                    else (40, 45, 55, 255)))
        (private_dir / "scene.js").write_text("window.AZHOU_WORKING_IMAGE = 'synthetic';\n")
        synthetic_png(private_dir / "app-icon/source.png", 1024, 1024,
                      lambda x, y: (x % 256, y % 256, 90, 255))


class StartupBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin" or shutil.which("xcrun") is None:
            raise unittest.SkipTest("startup image generation requires macOS Vision")
        cls.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-startup-test-")
        cls.root = (Path(cls.temporary.name) / "source").resolve()
        clone_source_tree(cls.root)
        cls.bundle = cls.root / ".build/azhou-stage.test/azhou-payload"
        cls.bundle.mkdir(parents=True)
        cls.builder = load_module(BUILDER_PATH, "agent_skin_startup_builder")
        cls.builder.build_startup(cls.bundle, root=cls.root)
        cls.verifier = load_module(cls.root / "tools/verify-artifacts.py", "agent_skin_fixture_artifacts")
        cls.info = {"CFBundleShortVersionString": APP_VERSION, "CFBundleVersion": APP_BUILD}
        cls.inputs = cls.verifier.source_inputs()
        cls.marker = {"version": APP_VERSION, "build": APP_BUILD,
                      "inputSHA256": cls.verifier.aggregate_inputs(cls.inputs), "inputs": cls.inputs}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_build_binds_one_complete_payload_and_the_same_defaults_to_preview(self):
        startup = self.bundle / "Contents/Resources/startup"
        web = self.bundle / "Contents/Resources/web"
        avatar = web / "assets/defaults/avatar.png"
        entry_avatar = web / "assets/defaults/entry-avatar.png"
        artwork = web / "assets/defaults/artwork.png"
        contours_js = web / "assets/defaults/contours.js"
        manifest_path = startup / "manifest.json"
        install_js = startup / "install.js"
        self.assertTrue(install_js.is_file())
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(avatar.is_file())
        self.assertTrue(entry_avatar.is_file())
        self.assertTrue(artwork.is_file())
        self.assertTrue(contours_js.is_file())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["protocolVersion"], 1)
        self.assertEqual((manifest["appVersion"], manifest["appBuild"]), (APP_VERSION, APP_BUILD))
        self.assertEqual(manifest["inputSHA256"], self.marker["inputSHA256"])
        self.assertEqual((manifest["assets"]["avatar"]["width"], manifest["assets"]["avatar"]["height"]), (512, 512))
        self.assertEqual((manifest["assets"]["entryAvatar"]["width"], manifest["assets"]["entryAvatar"]["height"]), (1254, 1254))
        self.assertEqual((manifest["assets"]["artwork"]["width"], manifest["assets"]["artwork"]["height"]), (1536, 1024))
        avatar_width, avatar_height, avatar_sample = decode_png(avatar)
        self.assertEqual((avatar_width, avatar_height), (512, 512))
        self.assertGreater(avatar_sample(10, 250)[0], avatar_sample(10, 250)[2])
        self.assertGreater(avatar_sample(50, 250)[2], avatar_sample(50, 250)[0])
        entry_width, entry_height, entry_sample = decode_png(entry_avatar)
        self.assertEqual((entry_width, entry_height), (1254, 1254))
        self.assertGreater(entry_sample(100, 200)[1], entry_sample(1000, 200)[1])
        art_width, art_height, art_sample = decode_png(artwork)
        self.assertEqual((art_width, art_height), (1536, 1024))
        self.assertGreater(min(art_sample(380, 280)[:3]), 220,
                           "center-cover crop should retain the asymmetric high-left rectangle")
        self.assertLess(max(art_sample(100, 500)[:3]), 90,
                        "pixels outside the known crop marker must stay dark")

        defaults_source = contours_js.read_text(encoding="utf-8")
        prefix = "window.AGENT_SKIN_ASSETS = Object.freeze("
        self.assertTrue(defaults_source.startswith(prefix))
        self.assertTrue(defaults_source.endswith(");\n"))
        preview_assets = json.loads(defaults_source[len(prefix):-3])
        self.assertEqual(base64.b64decode(preview_assets["avatar"].split(",", 1)[1]), avatar.read_bytes())
        self.assertEqual(base64.b64decode(preview_assets["entryAvatar"].split(",", 1)[1]), entry_avatar.read_bytes())
        self.assertEqual(preview_assets["entryAvatar"],
                         "data:image/png;base64," + base64.b64encode(entry_avatar.read_bytes()).decode("ascii"))
        self.assertEqual(base64.b64decode(preview_assets["artwork"].split(",", 1)[1]), artwork.read_bytes())
        self.assertEqual(preview_assets["artworkSHA256"], hashlib.sha256(artwork.read_bytes()).hexdigest())
        self.assertEqual(preview_assets["contours"], manifest["assets"]["contours"])
        self.assertNotIn("introTitle", preview_assets)
        self.assertNotIn("introCaption", preview_assets)
        self.assertNotIn("artworkSubtitle", preview_assets)
        contour_boxes = []
        for path in preview_assets["contours"]:
            xs = [point[0] for point in path]
            ys = [point[1] for point in path]
            contour_boxes.append((min(xs), max(xs), min(ys), max(ys)))
        self.assertTrue(any(230 <= left <= 330 and 430 <= right <= 530
                            and 140 <= top <= 240 and 320 <= bottom <= 420
                            for left, right, top, bottom in contour_boxes),
                        "Vision paths must use top-left 1536×1024 coordinates from the exact cropped artwork")

        payload = install_js.read_text(encoding="utf-8")
        source_animation = (self.root / "animation.js").read_text(encoding="utf-8")
        animation_start = source_animation.index("function installAnimation(")
        animation_end = source_animation.index("/* Local preview adapter.", animation_start)
        self.assertIn(source_animation[animation_start:animation_end].rstrip(), payload)
        self.assertIn((self.root / "image-settings.js").read_text(encoding="utf-8").strip(), payload)
        renderer = (self.root / "extension/renderer.mjs").read_text(encoding="utf-8")
        self.assertIn(renderer.replace("export function installStartup", "function installStartup", 1).strip(), payload)
        self.assertIn("class PageController", payload)
        self.assertIn("function dataProperty", payload)
        self.assertIn("function createLocalization(", payload)
        self.assertIn("createLocalization: { value: createLocalization }", payload)
        self.assertNotIn("const settings = environment.AGENT_SKIN_ASSETS || null", payload)
        self.assertNotRegex(payload, r"\bfixture\s*:\s*true\b")
        self.assertLess(len(install_js.read_bytes()), 24 * 1024 * 1024)
        subprocess.run(["node", "--check", str(install_js)], check=True, capture_output=True, text=True)

        for relative, digest in manifest["outputs"].items():
            output = self.bundle / "Contents/Resources" / relative
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), digest)
        self.verifier.verify_startup(self.bundle, self.info, self.marker)

    def test_manifest_and_actual_resources_reject_tampering(self):
        resources = self.bundle / "Contents/Resources"
        for relative in ("startup/install.js", "web/assets/defaults/artwork.png",
                         "web/assets/defaults/contours.js"):
            with self.subTest(relative=relative):
                clone = Path(self.temporary.name) / ("tamper-" + relative.replace("/", "-"))
                shutil.copytree(self.bundle, clone)
                target = clone / "Contents/Resources" / relative
                target.write_bytes(target.read_bytes() + b"tampered")
                with self.assertRaisesRegex(RuntimeError, "startup|摘要|轮廓|PNG"):
                    self.verifier.verify_startup(clone, self.info, self.marker)

        clone = Path(self.temporary.name) / "manifest-version"
        shutil.copytree(self.bundle, clone)
        manifest_path = clone / "Contents/Resources/startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["appVersion"] = "99.0.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "version|版本"):
            self.verifier.verify_startup(clone, self.info, self.marker)

        clone = Path(self.temporary.name) / "fixture-payload"
        shutil.copytree(self.bundle, clone)
        install_path = clone / "Contents/Resources/startup/install.js"
        install_path.write_text(install_path.read_text(encoding="utf-8") + "\nfixture: true\n", encoding="utf-8")
        manifest_path = clone / "Contents/Resources/startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"]["startup/install.js"] = hashlib.sha256(install_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "fixture|preview|生产"):
            self.verifier.verify_startup(clone, self.info, self.marker)

    def test_missing_private_default_input_fails_before_writing_outputs(self):
        root = (Path(self.temporary.name) / "missing-private-source").resolve()
        clone_source_tree(root, private=False)
        bundle = root / ".build/azhou-stage.test/azhou-payload"
        bundle.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "assets/private|私有素材"):
            self.builder.build_startup(bundle, root=root)
        self.assertFalse((bundle / "Contents/Resources/startup/install.js").exists())

    def test_hub_build_entry_requires_each_private_input_before_creating_a_stage(self):
        private = self.root / "assets/private"
        build_root = self.root / ".build"
        original_children = {path.name for path in build_root.iterdir()}
        for name in ("working.png", "scene.js", "wallpaper-scene-q-v3.png", "entry-avatar.png", "app-icon/source.png"):
            path = private / name
            original = path.read_bytes()
            path.unlink()
            with self.subTest(missing=name):
                result = subprocess.run(["bash", "tools/build-macos.sh"], cwd=self.root,
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("working.png", result.stderr)
                self.assertIn("scene.js", result.stderr)
                self.assertIn("wallpaper-scene-q-v3.png", result.stderr)
                self.assertIn("entry-avatar.png", result.stderr)
                self.assertIn("app-icon/source.png", result.stderr)
                self.assertEqual({item.name for item in build_root.iterdir()}, original_children)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)

    def test_builder_sources_are_hashed_and_listed_as_build_inputs(self):
        required = {"tools/build-startup.py", "tools/build-startup-assets.swift", "localization.js"}
        verifier_inputs = set(self.verifier.INPUT_FILES)
        package = json.loads((self.root / "hub-package.json").read_text(encoding="utf-8"))
        self.assertTrue(required <= verifier_inputs)
        self.assertTrue(required <= set(package["build_inputs"]))
        self.assertTrue(required <= set(package["runtime_paths"]))
        for source in required:
            self.assertIn(source, self.marker["inputs"])

    def test_native_display_names_are_localized_with_the_canonical_install_basename(self):
        build_script = (PACKAGE / "tools/build-macos.sh").read_text(encoding="utf-8")
        self.assertIn('"CFBundleDisplayName" = "Azhou AI Lab";', build_script)
        self.assertIn('"CFBundleDisplayName" = "阿舟 AI 实验室";', build_script)
        self.assertIn('install-macos.sh 安装到 ~/Applications/阿舟 AI 实验室.app', build_script)
        self.assertIn("NAME = '阿舟 AI 实验室.app'", (PACKAGE / "tools/verify-artifacts.py").read_text(encoding="utf-8"))
        bundle = Path(self.temporary.name) / "localized-display.app"
        resources = bundle / "Contents/Resources"
        for language, label in (("en", "Azhou AI Lab"), ("zh-Hans", "阿舟 AI 实验室")):
            strings = resources / f"{language}.lproj/InfoPlist.strings"
            strings.parent.mkdir(parents=True, exist_ok=True)
            strings.write_text(f'"CFBundleDisplayName" = "{label}";\n"CFBundleName" = "{label}";\n',
                               encoding="utf-8")
        self.verifier.verify_localized_names(bundle, {
            "CFBundleName": "Azhou AI Lab", "CFBundleDisplayName": "Azhou AI Lab",
        })
        (resources / "zh-Hans.lproj/InfoPlist.strings").write_text("invalid\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "localized display-name"):
            self.verifier.verify_localized_names(bundle, {
                "CFBundleName": "Azhou AI Lab", "CFBundleDisplayName": "Azhou AI Lab",
            })

    def test_verifier_rejects_a_builder_source_omitted_from_input_manifest(self):
        original = self.verifier.INPUT_FILES
        self.verifier.INPUT_FILES = tuple(path for path in original if path != "tools/build-startup-assets.swift")
        try:
            with self.assertRaisesRegex(RuntimeError, "build-startup-assets.swift|构建输入"):
                self.verifier.verify_startup(self.bundle, self.info, self.marker)
        finally:
            self.verifier.INPUT_FILES = original

    def test_startup_payload_limit_is_enforced_even_when_manifest_matches(self):
        clone = Path(self.temporary.name) / "oversized-payload"
        shutil.copytree(self.bundle, clone)
        resources = clone / "Contents/Resources"
        install_path = resources / "startup/install.js"
        install_path.write_bytes(b"x" * (24 * 1024 * 1024))
        manifest_path = resources / "startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"]["startup/install.js"] = hashlib.sha256(install_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "24 MiB|24MiB|24 MB"):
            self.verifier.verify_startup(clone, self.info, self.marker)


if __name__ == "__main__":
    unittest.main(verbosity=2)

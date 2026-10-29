#!/usr/bin/env python3
"""Isolated synthetic-image tests for the Agent Skin startup builder."""
from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
BUILDER_PATH = PACKAGE / "tools/build-startup.py"
APP_PACKAGE = json.loads((PACKAGE / "hub-package.json").read_text(encoding="utf-8"))
APP_VERSION = APP_PACKAGE["runtime_version"]
APP_BUILD = str(APP_PACKAGE["runtime_build"])
BUILD_FILES = (
    "Native/App.swift",
    "Native/InstallRegistry.swift",
    "Native/InstallRegistryCore.swift",
    "Native/Wallpaper.swift",
    "Native/StartupNativeTests.swift",
    "extension/renderer.mjs",
    "extension/bootstrap.mjs",
    "image-settings.js",
    "localization.js",
    "image-metadata-reader.js",
    "vendor/dream-image-metadata.mjs",
    "vendor/dream-image-metadata.LICENSE",
    "index.html",
    "style.css",
    "animation.js",
    "wallpaper/renderer.js",
    "wallpaper/wallpaper.css",
    "wallpaper/apply.js",
    "wallpaper/preview.html",
    "tools/build-macos.sh",
    "tools/build-preflight.py",
    "tools/build-wallpaper.py",
    "tools/test-startup-browser.mjs",
    "tools/test-startup-native.py",
    "tools/build-startup.py",
    "tools/build-startup-assets.swift",
    "tools/verify-artifacts.py",
    "hub-package.json",
    "theme-config.json",
)
IMAGE_METADATA_SOURCE_INPUTS = (
    "image-metadata-reader.js",
    "vendor/dream-image-metadata.mjs",
    "vendor/dream-image-metadata.LICENSE",
)
IMAGE_METADATA_OUTPUTS = tuple("web/" + name for name in IMAGE_METADATA_SOURCE_INPUTS)
PRE_IMAGE_METADATA_STARTUP_OUTPUTS = frozenset({
    "startup/install.js",
    "web/index.html", "web/style.css", "web/animation.js", "web/image-settings.js", "web/localization.js",
    "web/assets/defaults/avatar.png", "web/assets/defaults/entry-avatar.png", "web/assets/defaults/artwork.png",
    "web/assets/defaults/contours.js",
})
BUILD10_LEGACY_SOURCE_INPUTS = frozenset({
    "tools/build-startup.py", "tools/build-startup-assets.swift", "tools/verify-artifacts.py",
    "extension/renderer.mjs", "image-settings.js", "localization.js", "wallpaper/renderer.js",
    "wallpaper/wallpaper.css", "index.html", "style.css", "animation.js", "hub-package.json",
})
PRE_IMAGE_METADATA_THEME_SOURCE_INPUTS = frozenset({
    "tools/build-startup.py", "tools/build-startup-assets.swift", "tools/verify-artifacts.py",
    "extension/renderer.mjs", "extension/bootstrap.mjs", "image-settings.js", "localization.js",
    "wallpaper/renderer.js", "wallpaper/apply.js", "wallpaper/wallpaper.css",
    "index.html", "style.css", "animation.js", "hub-package.json", "theme-config.json",
})
PREVIOUS_THEME_SOURCE_INPUTS = frozenset({
    "tools/build-startup.py", "tools/build-startup-assets.swift", "tools/verify-artifacts.py",
    "extension/renderer.mjs", "image-settings.js", "localization.js", "wallpaper/renderer.js",
    "wallpaper/wallpaper.css", "index.html", "style.css", "animation.js", "hub-package.json", "theme-config.json",
})


def load_module(path: Path, name: str):
    path = Path(path)
    if path.name in {"verify-artifacts.py", "build-wallpaper.py", "build-preflight.py"}:
        canonical = PACKAGE / "tools" / path.name
        if path.resolve() != canonical.resolve() and path.read_bytes() != canonical.read_bytes():
            raise AssertionError(f"coverage-mapped source differs from canonical source: {path}")
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


def build_staged_product(root: Path, label: str):
    bundle = root / ".build" / f"azhou-stage.{label}" / "azhou-payload"
    bundle.mkdir(parents=True)
    builder = load_module(BUILDER_PATH, f"agent_skin_publish_builder_{label}")

    def build_vision_outputs(command, **kwargs):
        if command[0] == "xcrun":
            return subprocess.CompletedProcess(command, 0)
        synthetic_png(Path(command[3]), 512, 512, lambda x, y: (240, 80, 30, 255))
        synthetic_png(Path(command[4]), 1536, 1024, lambda x, y: (30, 70, 110, 255))
        Path(command[5]).write_text(json.dumps([[[10, 20], [30, 40]]]), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    with mock.patch.object(builder.subprocess, "check_output", return_value="arm64\n"), \
            mock.patch.object(builder.subprocess, "run", side_effect=build_vision_outputs):
        builder.build_startup(bundle, root=root)

    artifacts = load_module(root / "tools/verify-artifacts.py", f"agent_skin_publish_artifacts_{label}")
    wallpaper = load_module(root / "tools/build-wallpaper.py", f"agent_skin_publish_wallpaper_{label}")
    wallpaper.package(bundle)
    artifacts.write_bundle_info(bundle)
    executable = bundle / "Contents/MacOS/AzhouCodexStartup"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"synthetic executable")
    executable.chmod(0o755)
    icon = bundle / "Contents/Resources/AzhouAppIcon.icns"
    icon.write_bytes(b"icns" + (12).to_bytes(4, "big") + b"test")
    artifacts.write_marker(bundle)
    return bundle, artifacts


def convert_bundle_to_pre_image_metadata(bundle: Path, artifacts, *, omit_source_inputs=(),
                                         omit_marker_inputs=()) -> dict:
    """Make a current synthetic bundle match the exact pre-image-metadata manifest/output contract."""
    resources = Path(bundle) / "Contents/Resources"
    marker_path = Path(bundle) / artifacts.MARKER
    manifest_path = resources / "startup/manifest.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name in IMAGE_METADATA_SOURCE_INPUTS:
        marker["inputs"].pop(name)
        manifest["sourceInputs"].pop(name)
    for name in omit_marker_inputs:
        marker["inputs"].pop(name)
    for name in omit_source_inputs:
        manifest["sourceInputs"].pop(name)

    marker["inputSHA256"] = artifacts.aggregate_inputs(marker["inputs"])
    manifest["inputSHA256"] = marker["inputSHA256"]
    for relative in IMAGE_METADATA_OUTPUTS:
        manifest["outputs"].pop(relative)
        (resources / relative).unlink()
    for relative in manifest["outputs"]:
        manifest["outputs"][relative] = hashlib.sha256((resources / relative).read_bytes()).hexdigest()

    try:
        (resources / "web/vendor").rmdir()
    except OSError:
        pass
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
    return manifest


def simulated_swap(left: Path, right: Path) -> None:
    backup = Path(left).parent / ".publish-test-backup"
    os.replace(right, backup)
    os.replace(left, right)
    os.replace(backup, left)


def publish_with_test_native_tools(artifacts, staged: Path) -> None:
    signed = subprocess.CompletedProcess(["codesign"], 0)
    with mock.patch.object(artifacts.subprocess, "run", return_value=signed), \
            mock.patch.object(artifacts, "swap", side_effect=simulated_swap), \
            contextlib.redirect_stdout(io.StringIO()):
        artifacts.publish(staged)


class BuildOwnedThemeTests(unittest.TestCase):
    def test_publish_rebuilds_existing_payload_after_theme_edit(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-theme-rebuild-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            first, artifacts = build_staged_product(root, "theme-first")
            publish_with_test_native_tools(artifacts, first)

            config_path = root / "theme-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["identity"]["appName"] = {"zh-CN": "阿舟新实验室", "en": "Azhou Next Lab"}
            config["identity"]["botName"] = {"zh-CN": "小舟", "en": "Zhou"}
            config["identity"]["installationName"] = "阿舟新实验室.app"
            config["startup"]["text"]["introCaption"] = {
                "zh-CN": "阿舟正在出发", "en": "Azhou is ready",
            }
            config["wallpaper"]["strength"] = 21
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            rebuilt, _ = build_staged_product(root, "theme-rebuilt")
            publish_with_test_native_tools(artifacts, rebuilt)

            actual_identity, info = artifacts.identity(artifacts.PAYLOAD)
            self.assertEqual(actual_identity, artifacts.IDENTITY)
            self.assertEqual(info["CFBundleIdentifier"], "local.azhou.codex-startup")
            self.assertEqual(info["CFBundleExecutable"], "AzhouCodexStartup")
            self.assertEqual((info["CFBundleName"], info["CFBundleDisplayName"]), ("阿舟新实验室", "阿舟新实验室"))
            artifacts.verify_localized_names(artifacts.PAYLOAD, info)
            defaults = (artifacts.PAYLOAD / "Contents/Resources/web/assets/defaults/contours.js").read_text(
                encoding="utf-8")
            prefix = "window.AGENT_SKIN_ASSETS = Object.freeze("
            assets = json.loads(defaults[len(prefix):-3])
            self.assertEqual(assets["themeConfig"]["identity"]["installationName"], "阿舟新实验室.app")
            self.assertEqual(assets["wallpaperStrength"], 21)
            self.assertEqual(assets["themeConfig"]["startup"]["text"], config["startup"]["text"])
            marker = artifacts.read_marker(artifacts.PAYLOAD, required=True)
            self.assertEqual(marker["inputs"]["theme-config.json"], hashlib.sha256(config_path.read_bytes()).hexdigest())

    def test_publish_upgrades_build10_payload_without_theme_config(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-legacy-publish-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            metadata_path = root / "hub-package.json"
            current_metadata = metadata_path.read_bytes()
            old_metadata = json.loads(current_metadata)
            old_metadata['runtime_build'] = '10'
            metadata_path.write_text(json.dumps(old_metadata), encoding='utf-8')
            legacy, artifacts = build_staged_product(root, "legacy")
            info_path = legacy / 'Contents/Info.plist'
            info = plistlib.loads(info_path.read_bytes())
            info['CFBundleName'] = info['CFBundleDisplayName'] = 'Azhou AI Lab'
            info_path.write_bytes(plistlib.dumps(info))
            resources = legacy / "Contents/Resources"
            defaults_path = resources / "web/assets/defaults/contours.js"
            defaults_prefix = "window.AGENT_SKIN_ASSETS = Object.freeze("
            defaults_suffix = ");\n"
            defaults = defaults_path.read_text(encoding="utf-8")
            preview_assets = json.loads(defaults[len(defaults_prefix):-len(defaults_suffix)])
            preview_assets.pop("themeConfig")
            legacy_defaults = defaults_prefix + json.dumps(preview_assets, ensure_ascii=False, separators=(",", ":")) + defaults_suffix
            defaults_path.write_text(legacy_defaults, encoding="utf-8")

            install_path = resources / "startup/install.js"
            script = install_path.read_text(encoding="utf-8")
            assets_prefix = "const DEFAULT_ASSETS = Object.freeze("
            assets_start = script.index(assets_prefix) + len(assets_prefix)
            assets_end = script.index(");\n", assets_start)
            script_assets = json.loads(script[assets_start:assets_end])
            script_assets.pop("themeConfig")
            script = (script[:assets_start]
                      + json.dumps(script_assets, ensure_ascii=False, separators=(",", ":"))
                      + script[assets_end:])
            install_path.write_text(script, encoding="utf-8")

            manifest = convert_bundle_to_pre_image_metadata(
                legacy,
                artifacts,
                omit_source_inputs=("theme-config.json", "wallpaper/apply.js", "extension/bootstrap.mjs"),
                omit_marker_inputs=("theme-config.json", "wallpaper/apply.js", "extension/bootstrap.mjs"),
            )
            self.assertEqual(set(manifest["sourceInputs"]), BUILD10_LEGACY_SOURCE_INPUTS)
            self.assertEqual(set(manifest["outputs"]), PRE_IMAGE_METADATA_STARTUP_OUTPUTS)

            artifacts.PAYLOAD.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, artifacts.PAYLOAD)
            metadata_path.write_bytes(current_metadata)
            current, artifacts = build_staged_product(root, "legacy-upgrade")
            publish_with_test_native_tools(artifacts, current)

            installed_marker = artifacts.read_marker(artifacts.PAYLOAD, required=True)
            self.assertIn("theme-config.json", installed_marker["inputs"])
            installed_assets = json.loads(
                (artifacts.PAYLOAD / "Contents/Resources/web/assets/defaults/contours.js").read_text(
                    encoding="utf-8")[len(defaults_prefix):-len(defaults_suffix)])
            self.assertIn("themeConfig", installed_assets)

    def test_publish_upgrades_theme_build10_with_previous_english_fallback_name(self):
        with tempfile.TemporaryDirectory(prefix='agent-skin-theme-build10-upgrade-') as temporary:
            root = (Path(temporary) / 'source').resolve()
            clone_source_tree(root)
            metadata_path = root / 'hub-package.json'
            current_metadata = metadata_path.read_bytes()
            old_metadata = json.loads(current_metadata)
            old_metadata['runtime_build'] = '10'
            metadata_path.write_text(json.dumps(old_metadata), encoding='utf-8')
            previous, artifacts = build_staged_product(root, 'previous-theme')
            info_path = previous / 'Contents/Info.plist'
            info = plistlib.loads(info_path.read_bytes())
            info['CFBundleName'] = info['CFBundleDisplayName'] = 'Azhou AI Lab'
            info_path.write_bytes(plistlib.dumps(info))
            manifest = convert_bundle_to_pre_image_metadata(previous, artifacts)
            self.assertEqual(set(manifest["sourceInputs"]), PRE_IMAGE_METADATA_THEME_SOURCE_INPUTS)
            self.assertEqual(set(manifest["outputs"]), PRE_IMAGE_METADATA_STARTUP_OUTPUTS)
            artifacts.PAYLOAD.parent.mkdir(parents=True, exist_ok=True)
            os.replace(previous, artifacts.PAYLOAD)
            metadata_path.write_bytes(current_metadata)
            current, artifacts = build_staged_product(root, 'current-theme')
            publish_with_test_native_tools(artifacts, current)
            self.assertEqual(artifacts.read_marker(artifacts.PAYLOAD)['build'], APP_BUILD)

    def test_publish_upgrades_build11_and_build12_previous_theme_payloads(self):
        for build in ("11", "12"):
            with self.subTest(build=build), tempfile.TemporaryDirectory(
                    prefix=f"agent-skin-build{build}-upgrade-") as temporary:
                root = (Path(temporary) / "source").resolve()
                clone_source_tree(root)
                metadata_path = root / "hub-package.json"
                current_metadata = metadata_path.read_bytes()
                previous_metadata = json.loads(current_metadata)
                previous_metadata["runtime_build"] = build
                metadata_path.write_text(json.dumps(previous_metadata), encoding="utf-8")

                previous, artifacts = build_staged_product(root, f"previous-build-{build}")
                manifest = convert_bundle_to_pre_image_metadata(
                    previous,
                    artifacts,
                    omit_source_inputs=("wallpaper/apply.js", "extension/bootstrap.mjs"),
                )
                self.assertEqual(set(manifest["sourceInputs"]), PREVIOUS_THEME_SOURCE_INPUTS)
                self.assertEqual(set(manifest["outputs"]), PRE_IMAGE_METADATA_STARTUP_OUTPUTS)

                artifacts.PAYLOAD.parent.mkdir(parents=True, exist_ok=True)
                os.replace(previous, artifacts.PAYLOAD)
                metadata_path.write_bytes(current_metadata)
                current, artifacts = build_staged_product(root, f"current-build-{build}")
                publish_with_test_native_tools(artifacts, current)
                self.assertEqual(artifacts.read_marker(artifacts.PAYLOAD)["build"], APP_BUILD)

    def test_previous_theme_payload_rejects_added_sources_outputs_and_tampering(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-historical-contract-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            metadata_path = root / "hub-package.json"
            previous_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            previous_metadata["runtime_build"] = "12"
            metadata_path.write_text(json.dumps(previous_metadata), encoding="utf-8")
            bundle, artifacts = build_staged_product(root, "previous-build-12-contract")
            manifest = convert_bundle_to_pre_image_metadata(
                bundle,
                artifacts,
                omit_source_inputs=("wallpaper/apply.js", "extension/bootstrap.mjs"),
            )
            self.assertEqual(set(manifest["sourceInputs"]), PREVIOUS_THEME_SOURCE_INPUTS)
            self.assertEqual(set(manifest["outputs"]), PRE_IMAGE_METADATA_STARTUP_OUTPUTS)

            info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
            marker_path = bundle / artifacts.MARKER
            manifest_path = bundle / "Contents/Resources/startup/manifest.json"
            marker_bytes = marker_path.read_bytes()
            manifest_bytes = manifest_path.read_bytes()
            marker = json.loads(marker_bytes)
            artifacts.verify_startup(bundle, info, marker, current_source=False)

            added_name = IMAGE_METADATA_SOURCE_INPUTS[0]
            added_digest = hashlib.sha256((root / added_name).read_bytes()).hexdigest()
            forged_marker = dict(marker)
            forged_marker["inputs"] = dict(marker["inputs"])
            forged_marker["inputs"][added_name] = added_digest
            forged_marker["inputSHA256"] = artifacts.aggregate_inputs(forged_marker["inputs"])
            forged_manifest = json.loads(manifest_bytes)
            forged_manifest["sourceInputs"][added_name] = added_digest
            forged_manifest["inputSHA256"] = forged_marker["inputSHA256"]
            marker_path.write_text(json.dumps(forged_marker, ensure_ascii=False), encoding="utf-8")
            manifest_path.write_text(json.dumps(forged_manifest, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "sourceInputs.*不完整"):
                artifacts.verify_startup(bundle, info, forged_marker, current_source=False)

            marker_path.write_bytes(marker_bytes)
            forged_manifest = json.loads(manifest_bytes)
            forged_manifest["outputs"][IMAGE_METADATA_OUTPUTS[0]] = "0" * 64
            manifest_path.write_text(json.dumps(forged_manifest, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "output 路径清单不完整"):
                artifacts.verify_startup(bundle, info, marker, current_source=False)

            manifest_path.write_bytes(manifest_bytes)
            tampered_output = bundle / "Contents/Resources/web/index.html"
            tampered_output.write_bytes(tampered_output.read_bytes() + b"tampered")
            with self.assertRaisesRegex(RuntimeError, "启动产物摘要不匹配"):
                artifacts.verify_startup(bundle, info, marker, current_source=False)

    def test_same_version_old_build_is_not_skipped_by_strict_product_verification(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-old-build-check-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            bundle, artifacts = build_staged_product(root, "old-build")
            info_path = bundle / "Contents/Info.plist"
            with info_path.open("rb") as stream:
                info = plistlib.load(stream)
            info["CFBundleVersion"] = "9"
            with info_path.open("wb") as stream:
                plistlib.dump(info, stream)
            marker_path = bundle / artifacts.MARKER
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["build"] = "9"
            marker_path.write_text(json.dumps(marker, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                   encoding="utf-8")

            signed = subprocess.CompletedProcess(["codesign"], 0)
            with mock.patch.object(artifacts.subprocess, "run", return_value=signed):
                with self.assertRaisesRegex(RuntimeError, "version/build"):
                    artifacts.verify_product(bundle)

    def test_build_startup_embeds_theme_config_and_verifies_it(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-theme-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            package_path = root / "hub-package.json"
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["runtime_version"] = "9.8.7"
            package["runtime_build"] = "123"
            package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
            app_version, app_build = package["runtime_version"], package["runtime_build"]
            bundle = root / ".build/azhou-stage.test/azhou-payload"
            bundle.mkdir(parents=True)
            builder = load_module(BUILDER_PATH, "agent_skin_theme_builder")

            def build_vision_outputs(command, **kwargs):
                if command[0] == "xcrun":
                    return subprocess.CompletedProcess(command, 0)
                synthetic_png(Path(command[3]), 512, 512, lambda x, y: (240, 80, 30, 255))
                synthetic_png(Path(command[4]), 1536, 1024, lambda x, y: (30, 70, 110, 255))
                Path(command[5]).write_text(json.dumps([[[10, 20], [30, 40]]]), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(builder.subprocess, "check_output", return_value="arm64\n"), \
                    mock.patch.object(builder.subprocess, "run", side_effect=build_vision_outputs):
                builder.build_startup(bundle, root=root)

            artifacts = builder.load_artifacts(root)
            manifest_path = bundle / "Contents/Resources/startup/manifest.json"
            defaults_path = bundle / "Contents/Resources/web/assets/defaults/contours.js"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            defaults = defaults_path.read_text(encoding="utf-8")
            prefix = "window.AGENT_SKIN_ASSETS = Object.freeze("
            preview_assets = json.loads(defaults[len(prefix):-3])
            self.assertEqual(set(preview_assets), {
                "avatar", "entryAvatar", "artwork", "artworkSHA256", "contours", "wallpaperStrength", "themeConfig",
            })
            expected_theme = json.loads((root / "theme-config.json").read_text(encoding="utf-8"))
            expected_theme["identity"].update({"version": app_version, "build": app_build})

            self.assertEqual(preview_assets["themeConfig"], expected_theme)
            self.assertEqual(preview_assets["wallpaperStrength"], expected_theme["wallpaper"]["strength"])
            self.assertIn("theme-config.json", manifest["sourceInputs"])
            self.assertEqual((manifest["appVersion"], manifest["appBuild"]), (app_version, app_build))
            self.assertIn(f'const APP_VERSION = "{app_version}";',
                          (bundle / "Contents/Resources/startup/install.js").read_text(encoding="utf-8"))
            marker_inputs = artifacts.source_inputs()
            marker = {"version": app_version, "build": app_build,
                      "inputSHA256": artifacts.aggregate_inputs(marker_inputs), "inputs": marker_inputs}
            verifier = load_module(root / "tools/verify-artifacts.py", "agent_skin_theme_artifacts")
            verifier.verify_startup(bundle, {
                "CFBundleShortVersionString": app_version,
                "CFBundleVersion": app_build,
            }, marker)

    def test_custom_theme_names_reach_payload_and_localized_bundle_without_changing_install_identity(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-custom-theme-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            config_path = root / "theme-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["identity"]["appName"] = {"zh-CN": "阿舟演示实验室", "en": "Azhou Demo Lab"}
            config["identity"]["botName"] = {"zh-CN": "小舟", "en": "Zhou"}
            config["identity"]["installationName"] = "阿舟演示实验室.app"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            bundle = root / ".build/azhou-stage.test/azhou-payload"
            bundle.mkdir(parents=True)
            builder = load_module(BUILDER_PATH, "agent_skin_custom_theme_builder")

            def build_vision_outputs(command, **kwargs):
                if command[0] == "xcrun":
                    return subprocess.CompletedProcess(command, 0)
                synthetic_png(Path(command[3]), 512, 512, lambda x, y: (240, 80, 30, 255))
                synthetic_png(Path(command[4]), 1536, 1024, lambda x, y: (30, 70, 110, 255))
                Path(command[5]).write_text(json.dumps([[[10, 20], [30, 40]]]), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(builder.subprocess, "check_output", return_value="arm64\n"), \
                    mock.patch.object(builder.subprocess, "run", side_effect=build_vision_outputs):
                builder.build_startup(bundle, root=root)

            artifacts = builder.load_artifacts(root)
            defaults_path = bundle / "Contents/Resources/web/assets/defaults/contours.js"
            defaults = defaults_path.read_text(encoding="utf-8")
            prefix = "window.AGENT_SKIN_ASSETS = Object.freeze("
            assets = json.loads(defaults[len(prefix):-3])
            self.assertEqual(assets["themeConfig"]["identity"]["appName"], config["identity"]["appName"])
            self.assertEqual(assets["themeConfig"]["identity"]["installationName"], "阿舟演示实验室.app")

            info = artifacts.write_bundle_info(bundle)
            actual_identity, parsed_info = artifacts.identity(bundle)
            self.assertEqual(actual_identity, artifacts.IDENTITY)
            self.assertEqual(parsed_info["CFBundleIdentifier"], "local.azhou.codex-startup")
            self.assertEqual(parsed_info["CFBundleExecutable"], "AzhouCodexStartup")
            self.assertEqual((parsed_info["CFBundleName"], parsed_info["CFBundleDisplayName"]),
                             ("阿舟演示实验室", "阿舟演示实验室"))
            self.assertEqual(info["CFBundleIdentifier"], artifacts.IDENTITY[0])
            artifacts.verify_localized_names(bundle, parsed_info)

    def test_theme_config_rejects_private_asset_path_escape_before_writing(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-unsafe-theme-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            config_path = root / "theme-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["identity"]["iconInput"] = "assets/private/../../outside.png"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            bundle = root / ".build/azhou-stage.test/azhou-payload"
            bundle.mkdir(parents=True)
            builder = load_module(BUILDER_PATH, "agent_skin_unsafe_theme_builder")

            with self.assertRaisesRegex(RuntimeError, "assets/private"):
                builder.build_startup(bundle, root=root)
            self.assertFalse((bundle / "Contents/Resources/startup/install.js").exists())

    def test_theme_config_matches_fixed_runtime_ranges_and_editable_text_limits(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-theme-limits-test-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root)
            config_path = root / "theme-config.json"
            base = json.loads(config_path.read_text(encoding="utf-8"))
            builder = load_module(BUILDER_PATH, "agent_skin_theme_limits_builder")
            artifacts = builder.load_artifacts(root)

            cleared_text = json.loads(json.dumps(base))
            for values in cleared_text["startup"]["text"].values():
                values.update({"zh-CN": "", "en": ""})
            config_path.write_text(json.dumps(cleared_text, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(artifacts.load_theme_config(root)["startup"]["text"], cleared_text["startup"]["text"])

            invalid_cases = (
                ("duration", lambda value: value["startup"].update(durationMs=12001), "exactly 12000"),
                ("name control", lambda value: value["identity"]["appName"].update(en="Azhou\nLab"),
                 "control or invalid Unicode"),
                ("name length", lambda value: value["identity"]["appName"].update(en="x" * 65),
                 "64-UTF-16-code-unit"),
                ("wallpaper minimum", lambda value: value["wallpaper"].update(min=1), "min/max must be 0/75"),
                ("wallpaper maximum", lambda value: value["wallpaper"].update(max=76), "min/max must be 0/75"),
                ("title limit", lambda value: value["startup"]["text"]["introTitle"].update(en="x" * 17),
                 "16-UTF-16-code-unit"),
                ("caption UTF-16 limit",
                 lambda value: value["startup"]["text"]["introCaption"].update({"zh-CN": "🙂" * 25}),
                 "48-UTF-16-code-unit"),
                ("subtitle limit", lambda value: value["startup"]["text"]["artworkSubtitle"].update(en="x" * 61),
                 "60-UTF-16-code-unit"),
            )
            for label, update, message in invalid_cases:
                with self.subTest(label=label):
                    invalid = json.loads(json.dumps(base))
                    update(invalid)
                    config_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError, message):
                        artifacts.load_theme_config(root)


class WallpaperThemeBuildTests(unittest.TestCase):
    def test_helper_payload_uses_the_shared_zero_and_custom_default_strength(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-wallpaper-strength-") as temporary:
            root = (Path(temporary) / "source").resolve()
            clone_source_tree(root, private=False)
            synthetic_png(root / "assets/private/wallpaper-scene-q-v3.png", 1024, 512,
                          lambda x, y: (30, 70, 110, 255))
            wallpaper = load_module(root / "tools/build-wallpaper.py", "agent_skin_strength_wallpaper")
            config_path = root / "theme-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            for strength in (0, 17):
                with self.subTest(strength=strength):
                    config["wallpaper"]["strength"] = strength
                    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
                    bundle = root / f".build/azhou-stage.strength-{strength}/azhou-payload"
                    bundle.mkdir(parents=True)
                    with contextlib.redirect_stdout(io.StringIO()):
                        wallpaper.package(bundle)
                    script = (bundle / "Contents/Resources/wallpaper/install.js").read_text(encoding="utf-8")
                    argument = script.rsplit("return await installRenderer(", 1)[1].removesuffix(");\n})()\n")
                    payload = json.loads(argument)
                    self.assertEqual(payload.get("strength"), strength,
                                     "the helper must use the same configured default as startup, including zero")


class ImageMetadataAssemblyTests(unittest.TestCase):
    def test_metadata_sources_are_bound_to_runtime_build_and_preview_outputs(self):
        builder = load_module(BUILDER_PATH, "agent_skin_image_metadata_manifest_builder")
        artifacts = load_module(PACKAGE / "tools/verify-artifacts.py", "agent_skin_image_metadata_manifest_artifacts")
        package = json.loads((PACKAGE / "hub-package.json").read_text(encoding="utf-8"))
        required = {
            "image-metadata-reader.js",
            "vendor/dream-image-metadata.mjs",
            "vendor/dream-image-metadata.LICENSE",
        }
        self.assertTrue(required <= set(package["build_inputs"]))
        self.assertTrue(required <= set(package["runtime_paths"]))
        self.assertTrue(required <= set(artifacts.INPUT_FILES))
        self.assertTrue(required <= set(artifacts.STARTUP_REQUIRED_INPUTS))
        self.assertTrue(required <= set(builder.PREVIEW_SOURCES))
        self.assertTrue({
            "tools/dream-image-metadata.test.mjs",
            "tools/image-import-preflight.test.mjs",
        } <= set(package["runtime_paths"]))

    def test_original_esm_is_adapted_into_and_executed_from_the_generated_payload(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("generated image-metadata assembly probe requires Node.js")
        builder = load_module(BUILDER_PATH, "agent_skin_image_metadata_builder")
        artifacts = load_module(PACKAGE / "tools/verify-artifacts.py", "agent_skin_image_metadata_artifacts")
        original = (PACKAGE / "vendor/dream-image-metadata.mjs").read_text(encoding="utf-8")
        adapted = builder._classic_image_metadata(original)
        generated_reader = builder.image_metadata_reader_source(PACKAGE)
        self.assertIn("function readRawDimensions(", adapted)
        self.assertNotIn("export ", adapted)
        self.assertNotIn("MAX_IMAGE_PIXELS", adapted)
        expected_reader = (builder.IMAGE_METADATA_READER_HEADER + adapted + "\n\n"
                           "globalThis.AGENT_SKIN_READ_RAW_DIMENSIONS = readRawDimensions;\n")
        self.assertEqual(generated_reader, expected_reader)

        css = (PACKAGE / "wallpaper/wallpaper.css").read_text(encoding="utf-8")
        payload = builder._build_script(PACKAGE, {}, css, artifacts)
        self.assertIn(adapted, payload)
        self.assertEqual(payload.count("function readRawDimensions("), 1)
        self.assertNotIn("MAX_IMAGE_PIXELS", payload)

        start = "  return bootstrapStartup({"
        end = "    host: globalThis,\n  });\n\n})()"
        self.assertEqual(payload.count(start), 1)
        self.assertEqual(payload.count(end), 1)
        probe_payload = payload.replace(start, "  const startupResult = bootstrapStartup({", 1).replace(
            end,
            "    host: globalThis,\n  });\n"
            "  return { startupResult, dimensions: readRawDimensions(globalThis.__agentSkinProbeHeader, '.png') };\n})()",
            1,
        )
        with tempfile.TemporaryDirectory(prefix="agent-skin-image-metadata-build-") as temporary:
            payload_path = Path(temporary) / "install.js"
            probe_path = Path(temporary) / "probe.cjs"
            payload_path.write_text(probe_payload, encoding="utf-8")
            probe_path.write_text(
                "const fs = require('node:fs');\n"
                "const vm = require('node:vm');\n"
                "const source = fs.readFileSync(process.argv[2], 'utf8');\n"
                "const sandbox = { URL, location: { href: 'https://example.invalid/' } };\n"
                "sandbox.__agentSkinProbeHeader = new Uint8Array(24);\n"
                "sandbox.__agentSkinProbeHeader.set([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82]);\n"
                "new DataView(sandbox.__agentSkinProbeHeader.buffer).setUint32(16, 24000, false);\n"
                "new DataView(sandbox.__agentSkinProbeHeader.buffer).setUint32(20, 2001, false);\n"
                "const result = vm.runInNewContext(source, sandbox);\n"
                "if (JSON.stringify(result.dimensions) !== JSON.stringify({ width: 24000, height: 2001 })) {\n"
                "  throw new Error('generated payload did not execute the bundled raw-dimensions parser');\n"
                "}\n",
                encoding="utf-8",
            )
            syntax = subprocess.run([node, "--check", str(payload_path)], check=False, capture_output=True, text=True)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            result = subprocess.run([node, str(probe_path), str(payload_path)], check=True,
                                    capture_output=True, text=True)
            self.assertEqual(result.stderr, "")

    def test_classic_reader_rejects_changed_source_and_generated_reader_drift(self):
        builder = load_module(BUILDER_PATH, "agent_skin_image_metadata_contract_builder")
        source = (PACKAGE / "vendor/dream-image-metadata.mjs").read_text(encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unexpected ESM boundary"):
            builder._classic_image_metadata(source + "\nimport './unexpected.js';\n")
        missing_boundary = source.replace(
            "// Raw pixel dimensions straight from the container header",
            "// Raw dimension boundary changed",
            1,
        )
        with self.assertRaisesRegex(RuntimeError, "missing a required raw-parser boundary"):
            builder._classic_image_metadata(missing_boundary)
        unsafe_policy = source.replace(
            "const SOF_MARKERS = new Set([",
            "const SOF_MARKERS = new Set([\n// MAX_IMAGE_PIXELS is not part of the adapter",
            1,
        )
        with self.assertRaisesRegex(RuntimeError, "retained an ESM export or safety policy"):
            builder._classic_image_metadata(unsafe_policy)

        with tempfile.TemporaryDirectory(prefix="agent-skin-image-metadata-reader-") as temporary:
            root = Path(temporary)
            vendor_source = root / "vendor/dream-image-metadata.mjs"
            vendor_source.parent.mkdir(parents=True)
            vendor_source.write_text(source, encoding="utf-8")
            destination = root / "image-metadata-reader.js"
            with self.assertRaisesRegex(RuntimeError, "Missing generated image-metadata-reader.js"):
                builder.verify_image_metadata_reader(root)

            self.assertEqual(builder.update_image_metadata_reader(root), destination)
            self.assertEqual(destination.read_text(encoding="utf-8"),
                             builder.image_metadata_reader_source(root))
            builder.verify_image_metadata_reader(root)

            destination.write_text("stale adapter\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "image-metadata-reader.js is stale"):
                builder.verify_image_metadata_reader(root)

            target = root / "reader-target.js"
            target.write_text("target\n", encoding="utf-8")
            destination.unlink()
            destination.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "Missing generated image-metadata-reader.js"):
                builder.verify_image_metadata_reader(root)
            with self.assertRaisesRegex(RuntimeError, "must not be a symlink"):
                builder.update_image_metadata_reader(root)


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
                self.assertIn(name, result.stderr)
                self.assertEqual({item.name for item in build_root.iterdir()}, original_children)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)

    def test_builder_sources_are_hashed_and_listed_as_build_inputs(self):
        required = {"tools/build-startup.py", "tools/build-startup-assets.swift", "localization.js", "theme-config.json",
                    "image-metadata-reader.js", "vendor/dream-image-metadata.mjs",
                    "vendor/dream-image-metadata.LICENSE"}
        verifier_inputs = set(self.verifier.INPUT_FILES)
        package = json.loads((self.root / "hub-package.json").read_text(encoding="utf-8"))
        self.assertTrue(required <= verifier_inputs)
        self.assertTrue(required <= set(package["build_inputs"]))
        self.assertTrue(required <= set(package["runtime_paths"]))
        for source in required:
            self.assertIn(source, self.marker["inputs"])

    def test_native_display_names_are_localized_with_the_canonical_install_basename(self):
        build_script = (PACKAGE / "tools/build-macos.sh").read_text(encoding="utf-8")
        self.assertIn('python3 tools/verify-artifacts.py --write-bundle-info "$bundle"', build_script)
        self.assertIn("NAME = load_theme_config(ROOT)['identity']['installationName']",
                      (PACKAGE / "tools/verify-artifacts.py").read_text(encoding="utf-8"))
        info = self.verifier.write_bundle_info(self.bundle)
        self.verifier.verify_localized_names(self.bundle, info)
        resources = self.bundle / "Contents/Resources"
        (resources / "zh-Hans.lproj/InfoPlist.strings").write_text("invalid\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "localized display-name"):
            self.verifier.verify_localized_names(self.bundle, info)

    def test_finder_display_name_uses_the_generated_localized_resources(self):
        info = self.verifier.write_bundle_info(self.bundle)
        theme = self.verifier.load_theme_config(self.root)
        app = Path(self.temporary.name) / 'finder-probe' / theme['identity']['installationName']
        resources = app / 'Contents/Resources'
        resources.mkdir(parents=True)
        shutil.copy2(self.bundle / 'Contents/Info.plist', app / 'Contents/Info.plist')
        for language in ('en', 'zh-Hans'):
            shutil.copytree(self.bundle / f'Contents/Resources/{language}.lproj', resources / f'{language}.lproj')
        probe = '''import Foundation
let path = CommandLine.arguments[1]
// Finder follows the system language, not a helper process AppleLanguages override.
let systemLanguages = UserDefaults.standard.persistentDomain(forName: UserDefaults.globalDomain)?["AppleLanguages"] as? [String] ?? Locale.preferredLanguages
let expected = systemLanguages.first?.lowercased().hasPrefix("zh") == true ? "阿舟 AI 实验室" : "Azhou AI Lab"
let actual = FileManager.default.displayName(atPath: path)
guard actual == expected else { fputs("Finder display mismatch: \\(actual) != \\(expected)\\n", stderr); exit(1) }
for (language, name) in [("en", "Azhou AI Lab"), ("zh-Hans", "阿舟 AI 实验室")] {
 let localized = Bundle(path: path + "/Contents/Resources/" + language + ".lproj")!
 guard localized.localizedString(forKey: "CFBundleDisplayName", value: nil, table: "InfoPlist") == name else { exit(2) }
}
'''
        result = subprocess.run(['xcrun', 'swift', '-e', probe, str(app)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

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

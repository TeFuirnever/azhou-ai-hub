#!/usr/bin/env python3
"""Public artifact-verifier API tests with synthetic staged application bundles."""
from __future__ import annotations

import contextlib
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


def png_chunk(kind: bytes, body: bytes) -> bytes:
    payload = kind + body
    return (len(body).to_bytes(4, "big") + payload
            + (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "big"))


def valid_png(width=1, height=1, *, color=6, filter_type=0, data=b"\x10\x20\x30\xff") -> bytes:
    channels = 4 if color == 6 else 3
    raw = bytes([filter_type]) + data[:width * channels]
    header = struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
            + png_chunk(b"IDAT", zlib.compress(raw)) + png_chunk(b"IEND", b""))


class VerifierApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-verifier-api-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = (Path(cls.temporary.name) / "source").resolve()
        cls.helpers = load_module(TOOLS / "test-startup-build.py", "agent_skin_verifier_fixtures")
        cls.helpers.clone_source_tree(cls.root)
        cls.staged, cls.build_artifacts = cls.helpers.build_staged_product(cls.root, "verifier-api")
        cls.verifier = load_module(TOOLS / "verify-artifacts.py", "agent_skin_canonical_verifier")
        cls.verifier.ROOT = cls.root
        cls.marker = cls.verifier.read_marker(cls.staged, required=True)
        _, cls.info = cls.verifier.identity(cls.staged)

    def setUp(self):
        self.case_dir = Path(self.temporary.name) / "cases"
        self.case_dir.mkdir(exist_ok=True)
        self.bundle = self.case_dir / f"bundle-{self.id().rsplit('.', 1)[-1]}"
        if self.bundle.exists():
            shutil.rmtree(self.bundle)
        shutil.copytree(self.staged, self.bundle)

    def copy_bundle(self, label):
        path = self.case_dir / label
        if path.exists():
            shutil.rmtree(path)
        shutil.copytree(self.staged, path)
        return path

    def read_marker(self, path=None):
        return self.verifier.read_marker(path or self.bundle, required=True)

    def update_output_digest(self, bundle: Path, relative: str) -> None:
        manifest_path = bundle / "Contents/Resources/startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = bundle / "Contents/Resources" / relative
        manifest["outputs"][relative] = hashlib.sha256(output.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def rewrite_defaults(self, bundle: Path, assets: dict) -> None:
        path = bundle / "Contents/Resources/web/assets/defaults/contours.js"
        path.write_text("window.AGENT_SKIN_ASSETS = Object.freeze(" + json.dumps(assets) + ");\n",
                        encoding="utf-8")
        self.update_output_digest(bundle, "web/assets/defaults/contours.js")

    def assert_startup_rejected(self, mutate, message):
        path = self.copy_bundle("invalid-" + hashlib.sha1(message.encode()).hexdigest()[:8])
        mutate(path)
        with self.assertRaisesRegex(RuntimeError, message):
            self.verifier.verify_startup(path, self.info, self.marker)

    def test_current_bundle_passes_verifier_api_boundaries(self):
        self.assertEqual(self.verifier.identity(self.bundle)[0], self.verifier.IDENTITY)
        info = self.verifier.require(self.bundle, self.verifier.IDENTITY)
        self.assertEqual(info["CFBundleExecutable"], self.verifier.IDENTITY[1])
        self.assertEqual(self.verifier.read_marker(self.bundle, required=True), self.marker)
        self.verifier.check_inputs(self.bundle)
        self.verifier.verify_icon(self.bundle, info)
        self.verifier.verify_wallpaper(self.bundle, info, self.marker)
        self.verifier.verify_startup(self.bundle, info, self.marker)
        self.verifier.verify_localized_names(self.bundle, info)
        with mock.patch.object(self.verifier.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.verifier.verify_product(self.bundle)
        self.assertEqual(run.call_args.args[0][:3], ["/usr/bin/codesign", "--verify", "--strict"])
        self.assertEqual(self.verifier.fingerprint(self.bundle), self.verifier.fingerprint(self.bundle))

    def test_old_090_theme_names_remain_valid_after_host_label_change(self):
        base = self.verifier.load_theme_config(self.root)['identity']
        old_app_names = {'zh-CN': '阿舟 AI 实验室', 'en': 'Azhou AI Lab'}
        for build, fallback in (('10', 'Azhou AI Lab'), ('22', '阿舟 AI 实验室')):
            with self.subTest(build=build):
                identity = {**base, 'appName': old_app_names, 'build': build}
                theme = {'identity': identity}
                old_info = dict(self.info)
                old_info['CFBundleName'] = old_info['CFBundleDisplayName'] = fallback
                resources = self.bundle / 'Contents/Resources'
                for locale, name in (('en', old_app_names['en']), ('zh-Hans', old_app_names['zh-CN'])):
                    quoted = json.dumps(name, ensure_ascii=False)
                    (resources / f'{locale}.lproj/InfoPlist.strings').write_text(
                        f'"CFBundleDisplayName" = {quoted};\n"CFBundleName" = {quoted};\n',
                        encoding='utf-8',
                    )
                self.verifier.verify_localized_names(self.bundle, old_info, theme_config=theme)

    def test_source_metadata_and_theme_validation_reject_unsafe_inputs(self):
        source_json = self.verifier._read_source_json(self.root, "theme-config.json", "theme config")
        package = self.verifier.load_package_metadata(self.root)
        valid = self.verifier._validate_theme_config_data(
            source_json, package["runtime_version"], package["runtime_build"],
        )
        self.assertEqual(valid["identity"]["version"], package["runtime_version"])

        path = self.root / "theme-config.json"
        original = path.read_bytes()
        invalid_configs = (
            ({**source_json, "extra": True}, "top-level shape"),
            ({**source_json, "identity": {**source_json["identity"], "appName": {"zh-CN": "A"}}}, "exactly zh-CN and en"),
            ({**source_json, "identity": {**source_json["identity"], "installationName": "../bad.app"}}, "safe .app basename"),
            ({**source_json, "identity": {**source_json["identity"], "entryAvatarInput": source_json["identity"]["iconInput"]}}, "must be distinct"),
            ({**source_json, "startup": {**source_json["startup"], "durationMs": True}}, "exactly 12000"),
            ({**source_json, "wallpaper": {**source_json["wallpaper"], "strength": 76}}, "within that runtime range"),
        )
        for config, message in invalid_configs:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RuntimeError, message):
                    self.verifier._validate_theme_config_data(config, package["runtime_version"], package["runtime_build"])

        try:
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "JSON object"):
                self.verifier._read_source_json(self.root, "theme-config.json", "theme config")
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "valid JSON"):
                self.verifier._read_source_json(self.root, "theme-config.json", "theme config")
            path.unlink()
            with self.assertRaisesRegex(RuntimeError, "Missing theme config"):
                self.verifier._read_source_json(self.root, "theme-config.json", "theme config")
        finally:
            path.write_bytes(original)

    def test_small_public_validator_boundaries_reject_invalid_records(self):
        package_path = self.root / "hub-package.json"
        original_package = package_path.read_bytes()
        try:
            package = json.loads(original_package)
            package["runtime_build"] = True
            package_path.write_text(json.dumps(package), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "runtime_version/runtime_build are invalid"):
                self.verifier.load_package_metadata(self.root)
        finally:
            package_path.write_bytes(original_package)

        with self.assertRaisesRegex(RuntimeError, "is not safe display text"):
            self.verifier._locale_map({"zh-CN": None, "en": "valid"}, "fixture", max_length=12)

        non_file = self.root / "assets/private/non-file.png"
        non_file.mkdir()
        with self.assertRaisesRegex(RuntimeError, "not a regular file"):
            self.verifier._private_input(
                self.root, "assets/private/non-file.png", "fixture", required=True,
            )

        with self.assertRaisesRegex(RuntimeError, "JSON object with identity metadata"):
            self.verifier.validate_embedded_theme_config(None, self.verifier.VERSION, self.verifier.BUILD)
        with self.assertRaisesRegex(RuntimeError, "identity fields are invalid"):
            self.verifier.validate_embedded_theme_config(
                {"identity": {}}, self.verifier.VERSION, self.verifier.BUILD,
            )
        valid_keys = {
            "appName", "botName", "installationName", "iconInput", "entryAvatarInput", "version", "build",
        }
        wrong_release = {"identity": {key: "wrong" for key in valid_keys}}
        with self.assertRaisesRegex(RuntimeError, "release does not match"):
            self.verifier.validate_embedded_theme_config(
                wrong_release, self.verifier.VERSION, self.verifier.BUILD,
            )

    def test_private_input_paths_and_source_snapshot_reject_links_and_missing_files(self):
        with self.assertRaisesRegex(RuntimeError, "must stay inside"):
            self.verifier._private_input_path("assets/private/../outside.png", "asset")
        with self.assertRaisesRegex(RuntimeError, "relative assets/private"):
            self.verifier._private_input_path("assets\\private\\working.png", "asset")
        with self.assertRaisesRegex(RuntimeError, "does not exist|inside assets/private"):
            self.verifier._private_input(self.root, "assets/private/missing.png", "asset", required=True)

        private = self.root / "assets/private"
        link = private / "linked.png"
        link.symlink_to(private / "working.png")
        try:
            with self.assertRaisesRegex(RuntimeError, "符号链接|symlink"):
                self.verifier.source_inputs()
            with self.assertRaisesRegex(RuntimeError, "符号链接|symlink"):
                self.verifier._private_input(self.root, "assets/private/linked.png", "asset", required=False)
        finally:
            link.unlink()
        self.assertIn("assets/private/working.png", self.verifier.source_inputs())

    def test_marker_reader_validates_schema_digest_paths_identity_and_version(self):
        marker_path = self.bundle / self.verifier.MARKER
        original = marker_path.read_bytes()
        valid = json.loads(original)
        mutations = (
            (lambda m: m.update(schema=2), "schema 无效"),
            (lambda m: m.pop("projectID"), "projectID"),
            (lambda m: m.update(projectRoot="relative/root"), "不是绝对路径"),
            (lambda m: m.update(inputs=[]), "输入列表无效"),
            (lambda m: m.update(inputs={"../escape": "0" * 64}), "输入记录无效"),
            (lambda m: m.update(inputs={"safe": "bad"}), "输入记录无效"),
            (lambda m: m.update(inputSHA256="0" * 64), "摘要不匹配"),
            (lambda m: m.update(bundleID="wrong.bundle"), "包身份不一致"),
            (lambda m: m.update(version="99.0"), "包版本不一致"),
        )
        for index, (mutate, message) in enumerate(mutations):
            path = self.copy_bundle(f"marker-{index}")
            current = json.loads((path / self.verifier.MARKER).read_text(encoding="utf-8"))
            mutate(current)
            (path / self.verifier.MARKER).write_text(json.dumps(current), encoding="utf-8")
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                self.verifier.read_marker(path, required=True)

        path = self.copy_bundle("marker-invalid-json")
        (path / self.verifier.MARKER).write_text("{", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.verifier.read_marker(path, required=True)
        path = self.copy_bundle("marker-missing")
        (path / self.verifier.MARKER).unlink()
        self.assertIsNone(self.verifier.read_marker(path))
        with self.assertRaisesRegex(RuntimeError, "缺少构建来源标记"):
            self.verifier.read_marker(path, required=True)

        path = self.copy_bundle("marker-symlink")
        (path / self.verifier.MARKER).unlink()
        (path / self.verifier.MARKER).symlink_to(marker_path)
        with self.assertRaisesRegex(RuntimeError, "符号链接"):
            self.verifier.read_marker(path)
        marker_path.write_bytes(original)

    def test_package_identity_fingerprint_and_icon_boundaries(self):
        with self.assertRaisesRegex(RuntimeError, "非实体应用目录"):
            self.verifier.identity(self.case_dir / "absent")
        with self.assertRaisesRegex(RuntimeError, "非实体目录"):
            self.verifier.fingerprint(self.case_dir / "absent")
        self.assertEqual(self.verifier.fingerprint(self.bundle), self.verifier.fingerprint(self.bundle))

        wrong = dict(self.info, CFBundleIdentifier="other.bundle")
        with self.assertRaisesRegex(RuntimeError, "身份不符"):
            self.verifier.require(self.bundle, ("expected.bundle", "AzhouCodexStartup"))
        with self.assertRaisesRegex(RuntimeError, "当前构建缺少"):
            self.verifier.verify_icon(self.bundle, {**wrong, "CFBundleShortVersionString": self.verifier.VERSION,
                                                     "CFBundleIconFile": None})
        self.verifier.verify_icon(self.bundle, {"CFBundleShortVersionString": "0.5.0"})

        icon = self.bundle / "Contents/Resources/AzhouAppIcon.icns"
        good = icon.read_bytes()
        icon.write_bytes(b"bad")
        with self.assertRaisesRegex(RuntimeError, "ICNS 容器无效"):
            self.verifier.verify_icon(self.bundle, self.info)
        icon.write_bytes(good)
        with self.assertRaisesRegex(RuntimeError, "资源名称无效"):
            self.verifier.verify_icon(self.bundle, {**self.info, "CFBundleIconFile": "../bad.icns"})

        backup = icon.with_suffix(".backup")
        icon.rename(backup)
        icon.symlink_to(self.case_dir / "outside.icns")
        try:
            with self.assertRaisesRegex(RuntimeError, "资源缺失"):
                self.verifier.verify_icon(self.bundle, self.info)
        finally:
            icon.unlink()
            backup.rename(icon)

    def test_staged_paths_atomic_swap_and_bundle_info_are_confined_to_fixture(self):
        self.assertEqual(self.verifier.staged_path(self.staged), self.staged)
        with self.assertRaisesRegex(RuntimeError, "新构建实体载荷"):
            self.verifier.staged_path(self.case_dir / "ordinary/azhou-payload")

        left = self.case_dir / "left"
        right = self.case_dir / "right"
        left.write_text("left")
        right.write_text("right")
        operation = mock.Mock(return_value=0)
        library = mock.Mock(renamex_np=operation)
        with mock.patch.object(self.verifier.ctypes, "CDLL", return_value=library):
            self.verifier.swap(left, right)
        self.assertEqual(operation.call_args.args[-1], 2)
        operation.return_value = 1
        with mock.patch.object(self.verifier.ctypes, "CDLL", return_value=library), \
                mock.patch.object(self.verifier.ctypes, "get_errno", return_value=17):
            with self.assertRaisesRegex(OSError, "原子替换失败"):
                self.verifier.swap(left, right)

        info = self.verifier.write_bundle_info(self.staged)
        self.verifier.verify_localized_names(self.staged, info)
        info_path = self.staged / "Contents/Info.plist"
        original = info_path.read_bytes()
        info_path.unlink()
        info_path.symlink_to(self.case_dir / "outside.plist")
        try:
            with self.assertRaisesRegex(RuntimeError, "符号链接 Info.plist"):
                self.verifier.write_bundle_info(self.staged)
        finally:
            info_path.unlink()
            info_path.write_bytes(original)

    def test_png_and_contour_parsers_reject_malformed_or_unbounded_data(self):
        parsed = self.verifier.png_details(valid_png(), "fixture.png")
        self.assertEqual((parsed["width"], parsed["height"], parsed["colorType"]), (1, 1, 6))
        bad_pngs = (
            ("text", "不是有效 PNG"),
            (b"\x89PNG\r\n\x1a\n\x00", "区块被截断"),
            (b"\x89PNG\r\n\x1a\n" + (100).to_bytes(4, "big") + b"IHDR" + b"\\x00" * 4, "区块长度无效"),
            (b"\x89PNG\r\n\x1a\n" + png_chunk(b"tEXt", b"x"), "缺少有效 IHDR"),
            (valid_png()[:-1] + b"X", "校验失败"),
        )
        for data, message in bad_pngs:
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                self.verifier.png_details(data, "broken.png")

        contours = [[[0, 0], [10, 10]]]
        self.assertEqual(self.verifier.validate_contours(contours), 2)
        invalid_contours = (
            (None, "数量无效"),
            ([], "数量无效"),
            ([[[0, 0]]], "路径无效"),
            ([[[0, 0], [float("nan"), 1]]], "坐标无效"),
            ([[[0, 0], [1537, 1]]], "坐标无效"),
            ([[[1, 1], [1, 1]]], "没有可绘制路径"),
        )
        for value, message in invalid_contours:
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                self.verifier.validate_contours(value)

    def test_startup_verifier_rejects_manifest_script_and_output_tampering(self):
        def bad_script(path, value):
            script = path / "Contents/Resources/startup/install.js"
            script.write_bytes(value)

        script_cases = (
            (b"", "必须小于 24 MiB"),
            (b"\xff", "必须是 UTF-8"),
            (b"import x from 'https://example.test/x.js';", "模块导入"),
            (b"fixture: true", "模块导入"),
            (b"fetch('https://example.test');", "模块导入"),
        )
        for index, (value, message) in enumerate(script_cases):
            with self.subTest(message=message):
                self.assert_startup_rejected(lambda path, data=value: bad_script(path, data), message)

        def manifest_case(key, value):
            def mutate(path):
                manifest_path = path / "Contents/Resources/startup/manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return mutate

        for key, value in (("schema", True), ("protocolVersion", 2), ("appVersion", "99.0"),
                           ("appBuild", "999"), ("inputSHA256", "0" * 64)):
            self.assert_startup_rejected(manifest_case(key, value), "manifest schema、protocol、version/build")

        self.assert_startup_rejected(
            manifest_case("outputs", {}), "output 路径清单不完整",
        )

        def tamper_output(path):
            output = path / "Contents/Resources/web/index.html"
            output.write_bytes(output.read_bytes() + b"changed")
        self.assert_startup_rejected(tamper_output, "启动产物摘要不匹配")

        def preview_mismatch(path):
            output = path / "Contents/Resources/web/index.html"
            output.write_bytes(output.read_bytes() + b"changed")
            self.update_output_digest(path, "web/index.html")
        self.assert_startup_rejected(preview_mismatch, "预览源码与标记来源不一致")

        def missing_bootstrap_result(path):
            output = path / "Contents/Resources/startup/install.js"
            output.write_text(output.read_text(encoding="utf-8").replace(
                "return installStartup(installAnimation, host);",
                "installStartup(installAnimation, host);"), encoding="utf-8")
            self.update_output_digest(path, "startup/install.js")
        self.assert_startup_rejected(missing_bootstrap_result, "未从完整 Page Controller")

    def test_startup_verifier_binds_metadata_source_and_requires_regular_outputs(self):
        path = self.copy_bundle("invalid-metadata-source-digest")
        marker_path = path / self.verifier.MARKER
        marker = self.read_marker(path)
        source_name = "vendor/dream-image-metadata.mjs"
        marker["inputs"][source_name] = hashlib.sha256(b"different metadata source").hexdigest()
        marker["inputSHA256"] = self.verifier.aggregate_inputs(marker["inputs"])
        marker_path.write_text(json.dumps(marker, ensure_ascii=False), encoding="utf-8")
        manifest_path = path / "Contents/Resources/startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["inputSHA256"] = marker["inputSHA256"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "启动构建源码未被来源标记覆盖：vendor/dream-image-metadata.mjs"):
            self.verifier.verify_startup(path, self.info, marker)

        output_relative = "web/image-metadata-reader.js"
        for label, use_symlink in (("missing-metadata-reader", False), ("symlink-metadata-reader", True)):
            with self.subTest(output=label):
                bundle = self.copy_bundle(label)
                output = bundle / "Contents/Resources" / output_relative
                output.unlink()
                if use_symlink:
                    output.symlink_to(bundle / "Contents/Resources/web/index.html")
                with self.assertRaisesRegex(RuntimeError, "启动产物缺失或不是实体文件"):
                    self.verifier.verify_startup(bundle, self.info, self.marker)

    def test_previous_theme_build_11_12_source_set_is_read_only_and_exact(self):
        path = self.copy_bundle("previous-theme-build-11")
        historical_manifest = self.helpers.convert_bundle_to_pre_image_metadata(
            path,
            self.build_artifacts,
            omit_source_inputs=("wallpaper/apply.js", "extension/bootstrap.mjs"),
        )
        self.assertEqual(set(historical_manifest["outputs"]), self.helpers.PRE_IMAGE_METADATA_STARTUP_OUTPUTS)
        info = dict(self.info, CFBundleShortVersionString="0.9.0", CFBundleVersion="11")
        marker_path = path / self.verifier.MARKER
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["version"], marker["build"] = "0.9.0", "11"
        marker_path.write_text(json.dumps(marker, ensure_ascii=False), encoding="utf-8")

        manifest_path = path / "Contents/Resources/startup/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["appVersion"], manifest["appBuild"] = "0.9.0", "11"
        manifest["sourceInputs"] = {
            name: marker["inputs"][name]
            for name in self.verifier.PREVIOUS_THEME_STARTUP_REQUIRED_INPUTS
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        defaults_path = path / "Contents/Resources/web/assets/defaults/contours.js"
        defaults = json.loads(defaults_path.read_text(encoding="utf-8").removeprefix(
            "window.AGENT_SKIN_ASSETS = Object.freeze(").removesuffix(");\n"))
        defaults["themeConfig"]["identity"].update(version="0.9.0", build="11")
        self.rewrite_defaults(path, defaults)

        script_path = path / "Contents/Resources/startup/install.js"
        script = script_path.read_text(encoding="utf-8")
        prefix = "const DEFAULT_ASSETS = Object.freeze("
        start = script.index(prefix) + len(prefix)
        end = script.index(");\n", start)
        embedded = json.loads(script[start:end])
        embedded["themeConfig"]["identity"].update(version="0.9.0", build="11")
        script_path.write_text(script[:start] + json.dumps(embedded, ensure_ascii=False, separators=(",", ":"))
                               + script[end:], encoding="utf-8")
        self.update_output_digest(path, "startup/install.js")

        self.verifier.verify_startup(path, info, marker, current_source=False)
        with self.assertRaisesRegex(RuntimeError, "App version/build"):
            self.verifier.verify_startup(path, info, marker, current_source=True)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"]["web/image-metadata-reader.js"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "output 路径清单不完整"):
            self.verifier.verify_startup(path, info, marker, current_source=False)

        forged_marker = dict(self.marker)
        forged_marker["version"], forged_marker["build"] = "0.9.0", "11"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"].pop("web/image-metadata-reader.js")
        manifest["inputSHA256"] = forged_marker["inputSHA256"]
        manifest["sourceInputs"] = {
            name: forged_marker["inputs"][name] for name in self.verifier.STARTUP_REQUIRED_INPUTS
        }
        manifest["sourceInputs"]["Native/App.swift"] = forged_marker["inputs"]["Native/App.swift"]
        marker_path.write_text(json.dumps(forged_marker, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "sourceInputs 清单不完整"):
            self.verifier.verify_startup(path, info, forged_marker, current_source=False)

    def test_startup_verifier_rejects_default_assets_and_theme_mismatches(self):
        defaults_path = "Contents/Resources/web/assets/defaults/contours.js"

        def defaults_case(value):
            def mutate(path):
                (path / defaults_path).write_text(value, encoding="utf-8")
                self.update_output_digest(path, "web/assets/defaults/contours.js")
            return mutate

        self.assert_startup_rejected(defaults_case("not controlled data"), "固定格式")
        self.assert_startup_rejected(defaults_case("window.AGENT_SKIN_ASSETS = Object.freeze([]);\n"),
                                      "受控 JSON 对象")

        def invalid_theme(path):
            defaults = json.loads((path / defaults_path).read_text(encoding="utf-8").removeprefix(
                "window.AGENT_SKIN_ASSETS = Object.freeze(").removesuffix(");\n"))
            defaults["themeConfig"]["wallpaper"]["strength"] = 100
            self.rewrite_defaults(path, defaults)
        path = self.copy_bundle("invalid-embedded-theme")
        invalid_theme(path)
        with self.assertRaisesRegex(RuntimeError, "strength must be within"):
            self.verifier.verify_startup(path, self.info, self.marker, current_source=False)

        def invalid_image(path, *, key="avatar", value="not-a-data-url"):
            defaults = json.loads((path / defaults_path).read_text(encoding="utf-8").removeprefix(
                "window.AGENT_SKIN_ASSETS = Object.freeze(").removesuffix(");\n"))
            defaults[key] = value
            self.rewrite_defaults(path, defaults)
        self.assert_startup_rejected(invalid_image, "规范 PNG data URL")
        self.assert_startup_rejected(lambda path: invalid_image(path, value="data:image/png;base64,%%%"),
                                      "PNG data URL 无效")

        def bad_contours(path):
            defaults = json.loads((path / defaults_path).read_text(encoding="utf-8").removeprefix(
                "window.AGENT_SKIN_ASSETS = Object.freeze(").removesuffix(");\n"))
            defaults["contours"] = []
            self.rewrite_defaults(path, defaults)
        self.assert_startup_rejected(bad_contours, "轮廓数量无效")

        def bad_manifest_assets(path):
            manifest_path = path / "Contents/Resources/startup/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["assets"] = {}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_startup_rejected(bad_manifest_assets, "startup manifest 默认图像")


if __name__ == "__main__":
    unittest.main()

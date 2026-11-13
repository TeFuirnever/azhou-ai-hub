#!/usr/bin/env python3
"""Tests the build preflight API and CLI with isolated private assets and fake Git boundaries."""
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


def png_header(width: int, height: int, *, kind: bytes = b"IHDR") -> bytes:
    return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + kind
            + struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))


class BuildPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module(TOOLS / "build-preflight.py", "agent_skin_canonical_preflight")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-preflight-")
        self.addCleanup(self.temporary.cleanup)
        self.root = (Path(self.temporary.name) / "source").resolve()
        (self.root / "tools").mkdir(parents=True)
        for name in ("hub-package.json", "theme-config.json"):
            shutil.copy2(PACKAGE / name, self.root / name)
        for name in ("verify-artifacts.py", "build-preflight.py"):
            shutil.copy2(TOOLS / name, self.root / "tools" / name)
            self.assertEqual((self.root / "tools" / name).read_bytes(), (TOOLS / name).read_bytes())
        private = self.root / "assets/private"
        private.mkdir(parents=True)
        (private / "working.png").write_bytes(b"working")
        (private / "scene.js").write_text("fixture", encoding="utf-8")
        (private / "wallpaper-scene-q-v3.png").write_bytes(b"wallpaper")
        theme = json.loads((self.root / "theme-config.json").read_text(encoding="utf-8"))
        self.entry_avatar = self.root / theme["identity"]["entryAvatarInput"]
        self.icon_source = self.root / theme["identity"]["iconInput"]
        self.entry_avatar.parent.mkdir(parents=True, exist_ok=True)
        self.entry_avatar.write_bytes(b"entry-avatar")
        self.icon_source.parent.mkdir(parents=True, exist_ok=True)
        self.icon_source.write_bytes(png_header(1024, 1024))
        (self.root / ".build").mkdir()
        (self.root / "dist").mkdir()
        self.run_returncode = 0
        self.tracked = b""
        self.run_calls = []
        self.output = None

    def run_git(self, command, *, cwd):
        self.run_calls.append((command, cwd))
        return subprocess.CompletedProcess(command, self.run_returncode)

    def fake_git(self):
        return (
            mock.patch.object(self.module.subprocess, "run", side_effect=self.run_git),
            mock.patch.object(self.module.subprocess, "check_output", return_value=self.tracked),
        )

    def test_preflight_returns_theme_after_all_git_ignore_checks(self):
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch as check_output:
            theme = self.module.preflight(self.root)
        self.assertEqual(theme["identity"]["installationName"], "阿舟 AI 实验室.app")
        self.assertEqual(len(self.run_calls), 7)
        self.assertTrue(all(cwd == self.root for _, cwd in self.run_calls))
        self.assertTrue(all(command[:4] == ["git", "check-ignore", "-q", "--"]
                            for command, _ in self.run_calls))
        self.assertEqual(check_output.call_args.args[0], ["git", "ls-files", "--", "assets/private", "dist", ".build", ".local"])

    def test_main_emits_the_same_compact_theme_json(self):
        expected = self.module.load_theme(self.root)
        stdout = io.StringIO()
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main(self.root, argv=[]), 0)
        self.assertEqual(stdout.getvalue(), json.dumps(expected, ensure_ascii=False, separators=(",", ":")) + "\n")

    def test_cli_executes_the_copied_source_and_returns_success(self):
        script = self.root / "tools/build-preflight.py"
        stdout = io.StringIO()
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout), \
                mock.patch.object(sys, "argv", [str(script)]):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(script), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), self.module.load_theme(self.root))

    def test_preflight_theme_matches_the_embedded_theme_contract(self):
        run_patch, output_patch = self.fake_git()
        stdout = io.StringIO()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main(self.root, argv=[]), 0)
        theme = json.loads(stdout.getvalue())
        self.assertEqual(theme["identity"]["iconInput"], self.icon_source.relative_to(self.root).as_posix())
        self.assertEqual(set(theme), {"identity", "startup", "wallpaper"})
        self.assertEqual(theme["identity"]["installationName"], "阿舟 AI 实验室.app")
        artifacts = load_module(self.root / "tools/verify-artifacts.py", "icon_theme_validation")
        self.assertEqual(artifacts.validate_embedded_theme_config(
            theme, theme["identity"]["version"], theme["identity"]["build"]), theme)

    def test_approved_digest_is_checked_against_the_icon_source(self):
        digest = hashlib.sha256(self.icon_source.read_bytes()).hexdigest()
        run_patch, output_patch = self.fake_git()
        stdout = io.StringIO()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout), \
                mock.patch.dict(os.environ, {"AZHOU_APPROVED_ICON_SHA256": digest.upper()}):
            self.assertEqual(self.module.main(self.root, argv=[]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["identity"]["iconInput"],
                         self.icon_source.relative_to(self.root).as_posix())
        self.assertNotIn(digest, stdout.getvalue().lower())

    def test_rejects_invalid_approved_digest(self):
        for digest in ("", "not-a-digest"):
            with self.subTest(digest=digest):
                run_patch, output_patch = self.fake_git()
                with run_patch, output_patch, mock.patch.dict(
                    os.environ, {"AZHOU_APPROVED_ICON_SHA256": digest},
                ):
                    with self.assertRaisesRegex(SystemExit, "AZHOU_APPROVED_ICON_SHA256"):
                        self.module.main(self.root, argv=[])

    def prepare_build(self):
        shutil.copy2(TOOLS / "build-macos.sh", self.root / "tools/build-macos.sh")
        shutil.copy2(TOOLS / "build-lock.py", self.root / "tools/build-lock.py")
        shutil.copy2(PACKAGE / ".gitignore", self.root / ".gitignore")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def test_build_rejects_a_swapped_icon_before_staging(self):
        self.prepare_build()
        approved_digest = hashlib.sha256(self.icon_source.read_bytes()).hexdigest()
        self.icon_source.write_bytes(png_header(1024, 1024) + b"unapproved fixture")
        payload = self.root / ".build" / "azhou-payload"
        payload.mkdir()
        receipt = payload / "fixture-receipt"
        receipt.write_bytes(b"existing payload")
        result = subprocess.run(
            ["bash", "tools/build-macos.sh"], cwd=self.root, capture_output=True, text=True,
            env={**os.environ, "AZHOU_APPROVED_ICON_SHA256": approved_digest}, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("图标源图与已批准的 SHA-256 不符", result.stderr)
        self.assertEqual(receipt.read_bytes(), b"existing payload")
        self.assertCountEqual((self.root / ".build").iterdir(), [payload])

    def test_build_binds_the_staged_icon_to_the_approval_after_preflight(self):
        self.prepare_build()
        artifacts = load_module(self.root / "tools/verify-artifacts.py", "icon_snapshot_fixture")
        for name in artifacts.INPUT_FILES:
            path = self.root / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        payload = self.root / ".build/azhou-payload"
        payload.mkdir()
        receipt = payload / "fixture-receipt"
        receipt.write_bytes(b"existing payload")
        original_icon = self.icon_source.read_bytes()
        system_bin = self.root / "system-bin"
        system_bin.mkdir()
        compiler = system_bin / "xcrun"
        compiler.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        compiler.chmod(0o755)
        converter = system_bin / "sips"
        converter.write_text(
            '#!/bin/bash\nset -eu\n'
            'test "${4##*/}" = approved-icon.png\n'
            'cmp "$APPROVED_FIXTURE_ICON" "$4"\n'
            'printf "%s\\n" "approved snapshot reached converter" >&2\nexit 73\n',
            encoding="utf-8",
        )
        converter.chmod(0o755)
        env = {**os.environ, "AZHOU_APPROVED_ICON_SHA256": hashlib.sha256(original_icon).hexdigest().upper(),
               "AZHOU_BUILD_SYSTEM_BIN": str(system_bin), "APPROVED_FIXTURE_ICON": str(self.icon_source)}
        command = ["bash", "tools/build-macos.sh"]
        success = subprocess.run(command, cwd=self.root, capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(success.returncode, 73, success.stderr)
        self.assertIn("approved snapshot reached converter", success.stderr)
        retained_stages = set((self.root / ".build").glob("azhou-stage.*"))
        self.assertEqual(len(retained_stages), 1)
        self.assertTrue(next(iter(retained_stages)).joinpath("approved-icon.png").is_file())

        preflight = self.root / "tools/build-preflight.py"
        source = preflight.read_text(encoding="utf-8")
        preflight.write_text(source.replace(
            "    raise SystemExit(main())",
            '    main()\n'
            f'    (ROOT / {self.icon_source.relative_to(self.root).as_posix()!r})'
            '.write_bytes(bytes.fromhex('
            f'{(original_icon + b"replacement after preflight").hex()!r}))',
        ), encoding="utf-8")
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, env=env, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("图标源图与已批准的 SHA-256 不符", result.stderr)
        self.assertEqual(receipt.read_bytes(), b"existing payload")
        self.assertEqual(set((self.root / ".build").glob("azhou-stage.*")), retained_stages)

    def test_legacy_codex_config_is_valid_and_retired_host_icons_are_rejected(self):
        path = self.root / "theme-config.json"
        original = path.read_text()
        theme = json.loads(original)
        theme.pop("hostIcons", None)
        path.write_text(json.dumps(theme))
        self.assertEqual(self.module.load_theme(self.root)["identity"]["iconInput"],
                         self.icon_source.relative_to(self.root).as_posix())
        with open(self.root / "theme-config.json", "w", encoding="utf-8") as stream:
            json.dump({**json.loads(original), "hostIcons": {}}, stream)
        with self.assertRaisesRegex(RuntimeError, "unsupported top-level shape"):
            self.module.load_theme(self.root)
        path.write_text(original)
        self.module.load_theme(self.root)

    def test_build_payload_directory_rejects_symlinks(self):
        payload = self.root / ".build/azhou-payload"
        payload.symlink_to(Path(self.temporary.name), target_is_directory=True)
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "azhou-payload"):
            self.module.preflight(self.root)

    def test_symlinked_build_roots_and_tracked_outputs_stop_before_ignore_checks(self):
        target = Path(self.temporary.name) / "outside"
        target.mkdir()
        build = self.root / ".build"
        build.rmdir()
        build.symlink_to(target, target_is_directory=True)
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "拒绝通过符号链接构建：.build"):
            self.module.preflight(self.root)
        self.assertEqual(self.run_calls, [])
        build.unlink()
        build.mkdir()

        linked_cache = build / "module-cache"
        linked_cache.symlink_to(target, target_is_directory=True)
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "module-cache"):
            self.module.preflight(self.root)
        linked_cache.unlink()

        self.tracked = b"assets/private/working.png\n"
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "进入 Git 跟踪范围"):
            self.module.preflight(self.root)
        self.assertEqual(self.run_calls, [])

    def test_missing_ignore_rule_and_invalid_theme_or_icon_stop_the_build(self):
        self.run_returncode = 1
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "working.png"):
            self.module.preflight(self.root)
        self.assertEqual(len(self.run_calls), 1)

        self.run_returncode = 0
        self.icon_source.write_bytes(b"not an image")
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "必须是有效 PNG"):
            self.module.preflight(self.root)

        self.icon_source.write_bytes(png_header(1024, 1023))
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "方形 PNG"):
            self.module.preflight(self.root)

        self.icon_source.write_bytes(png_header(512, 512))
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "至少 1024"):
            self.module.preflight(self.root)

        self.icon_source.write_bytes(png_header(1024, 1024, kind=b"tEXt"))
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(SystemExit, "必须是有效 PNG"):
            self.module.preflight(self.root)

        theme_path = self.root / "theme-config.json"
        original = theme_path.read_bytes()
        theme = json.loads(original)
        theme["wallpaper"]["strength"] = 100
        theme_path.write_text(json.dumps(theme), encoding="utf-8")
        self.run_calls.clear()
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, self.assertRaisesRegex(RuntimeError, "within that runtime range"):
            self.module.preflight(self.root)
        self.assertEqual(self.run_calls, [])
        theme_path.write_bytes(original)

    def test_preflight_reports_unloadable_verifier_and_missing_icon_source(self):
        with mock.patch.object(self.module.importlib.util, "spec_from_file_location", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "cannot load artifact verifier"):
                self.module.load_theme(self.root)

        theme = self.module.load_theme(self.root)
        self.icon_source.unlink()
        run_patch, output_patch = self.fake_git()
        with mock.patch.object(self.module, "load_theme", return_value=theme), run_patch, output_patch:
            with self.assertRaisesRegex(SystemExit, "缺少阿舟素材 app-icon/source.png"):
                self.module.preflight(self.root)

    def test_icon_path_prefers_the_local_overlay_over_the_library(self):
        run_patch, output_patch = self.fake_git()
        stdout = io.StringIO()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main(self.root, argv=["--icon-path"]), 0)
        self.assertEqual(stdout.getvalue().strip(), str(self.icon_source))
        overlay = self.root / "assets/private/app-icon/source.png"
        overlay.parent.mkdir(parents=True, exist_ok=True)
        overlay.write_bytes(png_header(2048, 2048))
        run_patch, output_patch = self.fake_git()
        stdout = io.StringIO()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main(self.root, argv=["--icon-path"]), 0)
        self.assertEqual(stdout.getvalue().strip(), str(overlay))


if __name__ == "__main__":
    unittest.main()

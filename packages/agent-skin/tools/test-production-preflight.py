#!/usr/bin/env python3
"""Tests the build preflight API and CLI with isolated private assets and fake Git boundaries."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
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
        self.assertEqual(len(self.run_calls), 9)
        self.assertTrue(all(cwd == self.root for _, cwd in self.run_calls))
        self.assertTrue(all(command[:4] == ["git", "check-ignore", "-q", "--"]
                            for command, _ in self.run_calls))
        self.assertEqual(check_output.call_args.args[0], ["git", "ls-files", "--", "assets/private", "dist", ".build", ".local"])

    def test_main_emits_the_same_compact_theme_json(self):
        expected = self.module.load_theme(self.root)
        stdout = io.StringIO()
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main(self.root), 0)
        self.assertEqual(stdout.getvalue(), json.dumps(expected, ensure_ascii=False, separators=(",", ":")) + "\n")

    def test_cli_executes_the_copied_source_and_returns_success(self):
        script = self.root / "tools/build-preflight.py"
        stdout = io.StringIO()
        run_patch, output_patch = self.fake_git()
        with run_patch, output_patch, contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(script), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), self.module.load_theme(self.root))

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
            with self.assertRaisesRegex(SystemExit, "实体私有图标源图"):
                self.module.preflight(self.root)


if __name__ == "__main__":
    unittest.main()

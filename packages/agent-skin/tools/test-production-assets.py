#!/usr/bin/env python3
"""Tests the Azhou asset library check and the overlay-first build resolver."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import zlib


PACKAGE = Path(__file__).resolve().parents[1]
TOOLS = PACKAGE / "tools"
NAMES = ("working.png", "wallpaper-scene-q-v3.png", "entry-avatar.png", "app-icon/source.png")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load_module(TOOLS / "check-assets.py", "agent_skin_check_assets_test")
ARTIFACTS = load_module(TOOLS / "verify-artifacts.py", "agent_skin_asset_resolver_test")


def chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def png(width: int, height: int, color: int = 6, depth: int = 8) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0)
    return (CHECK.PNG_SIGNATURE + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\0")) + chunk(b"IEND", b""))


VALID = {
    "working.png": png(1254, 1254, 6),
    "wallpaper-scene-q-v3.png": png(1672, 941, 2),
    "entry-avatar.png": png(1254, 1254, 2),
    "app-icon/source.png": png(1024, 1024, 2),
}


class AssetFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "package"
        self.root.mkdir()
        for name in ("hub-package.json", "theme-config.json"):
            shutil.copy2(PACKAGE / name, self.root / name)
        self.library = self.root / "assets/azhou"
        self.overlay = self.root / "assets/private"
        for name, data in VALID.items():
            self.write(self.library / name, data)
        self.write(self.library / "LICENSE", b"Attribution-NonCommercial-NoDerivatives 4.0 International\n")
        self.write(self.library / "NOTICE.md", b"# Azhou artwork notice\n")

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def errors(self, **options) -> list[str]:
        return CHECK.check(self.root, **options)["errors"]


class CheckAssetsTests(AssetFixture):
    def test_published_library_in_this_checkout_is_complete(self):
        report = CHECK.check(PACKAGE)
        self.assertEqual([], report["errors"])
        self.assertEqual(set(NAMES), set(report["library"]))

    def test_library_without_overlay_passes_and_fresh_clone_mode_accepts_it(self):
        self.assertEqual([], self.errors())
        self.assertEqual([], self.errors(require_no_overlay=True))

    def test_fresh_clone_mode_rejects_an_overlay(self):
        self.overlay.mkdir(parents=True)
        self.assertIn("assets/private: a fresh checkout must not contain the local overlay",
                      self.errors(require_no_overlay=True))

    def test_partial_overlay_is_validated_and_other_files_are_listed(self):
        self.write(self.overlay / "app-icon/source.png", png(2048, 2048, 6))
        self.write(self.overlay / "provenance.json", b"{}")
        report = CHECK.check(self.root)
        self.assertEqual([], report["errors"])
        self.assertEqual(["app-icon/source.png"], list(report["overlay"]))
        self.assertEqual(["assets/private/provenance.json"], report["ignored"])

    def test_overlay_with_the_wrong_shape_fails(self):
        self.write(self.overlay / "working.png", png(512, 512, 6))
        self.write(self.overlay / "entry-avatar.png", png(1254, 1254, 0))
        errors = self.errors()
        self.assertTrue(any("working.png: 512×512 does not match 1254×1254" in e for e in errors), errors)
        self.assertTrue(any("entry-avatar.png: must be an 8-bit RGB/RGBA PNG" in e for e in errors), errors)

    def test_library_rejects_missing_extra_symlinked_and_oversized_files(self):
        (self.library / "working.png").unlink()
        self.write(self.library / "provenance.json", b"{}")
        (self.library / "LICENSE").write_text(" \n")
        (self.library / "entry-avatar.png").write_bytes(b"\0" * (CHECK.MAX_ENTRY_AVATAR_BYTES + 1))
        errors = self.errors()
        self.assertIn("assets/azhou/provenance.json: not part of the published asset set", errors)
        self.assertIn("assets/azhou/LICENSE: required license text is missing", errors)
        self.assertTrue(any(e.endswith("working.png: must be a regular file") for e in errors), errors)
        self.assertTrue(any("exceeds the" in e for e in errors), errors)

    def test_missing_library_and_symlinked_overlay_fail(self):
        shutil.rmtree(self.library)
        self.overlay.parent.mkdir(parents=True, exist_ok=True)
        self.overlay.symlink_to(self.root, target_is_directory=True)
        errors = self.errors()
        self.assertIn("assets/azhou: the published asset library is missing", errors)
        self.assertIn("assets/private: the local overlay must be a real directory", errors)

    def test_png_walk_rejects_corrupt_files(self):
        good = png(1254, 1254)
        cases = {
            "not a PNG file": b"GIF89a",
            "truncated PNG chunk": good[:10],
            "fails its CRC": good[:-5] + b"X" + good[-4:],
            "does not start with IHDR": CHECK.PNG_SIGNATURE + chunk(b"IDAT", b"") + chunk(b"IEND", b""),
            "does not end with IEND": good[:-12],
            "PNG does not end": good + b"trailing",
        }
        for message, data in cases.items():
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                CHECK.png_facts(data)
        with self.assertRaisesRegex(ValueError, "truncated PNG chunk"):
            CHECK.png_facts(good[:8] + struct.pack(">I", 999) + b"IHDR" + b"\0" * 4)

    def test_cli_reports_text_and_json(self):
        self.write(self.overlay / "working.png", VALID["working.png"])
        self.write(self.overlay / "notes.txt", b"x")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(0, CHECK.main(["--root", str(self.root)]))
        text = stdout.getvalue()
        self.assertIn("ok: assets/azhou/working.png 1254×1254 RGBA", text)
        self.assertIn("(build uses overlay)", text)
        self.assertIn("ignored by the build: assets/private/notes.txt", text)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(0, CHECK.main(["--root", str(self.root), "--json"]))
        self.assertEqual(["working.png"], list(json.loads(stdout.getvalue())["overlay"]))
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, CHECK.main(["--root", str(self.root), "--require-no-overlay"]))
        self.assertIn("FAILED: assets/private", stderr.getvalue())


class ResolverTests(AssetFixture):
    def test_no_overlay_resolves_every_asset_from_the_library(self):
        self.assertEqual({name: "azhou" for name in NAMES}, ARTIFACTS.asset_sources(self.root))
        self.assertEqual("assets/azhou/app-icon/source.png", ARTIFACTS.asset_key(self.root, "app-icon/source.png"))

    def test_partial_overlay_wins_only_for_its_own_files(self):
        self.write(self.overlay / "wallpaper-scene-q-v3.png", VALID["wallpaper-scene-q-v3.png"])
        sources = ARTIFACTS.asset_sources(self.root)
        self.assertEqual("private", sources["wallpaper-scene-q-v3.png"])
        self.assertEqual({"azhou"}, {sources[name] for name in NAMES if name != "wallpaper-scene-q-v3.png"})

    def test_full_overlay_replaces_every_asset_and_works_without_the_library(self):
        for name, data in VALID.items():
            self.write(self.overlay / name, data)
        shutil.rmtree(self.library)
        self.assertEqual({name: "private" for name in NAMES}, ARTIFACTS.asset_sources(self.root))
        path, source = ARTIFACTS.resolve_asset(self.root, "entry-avatar.png")
        self.assertEqual((self.overlay / "entry-avatar.png", "private"), (path, source))

    def test_missing_unsafe_and_linked_assets_fail_closed(self):
        (self.library / "working.png").unlink()
        with self.assertRaisesRegex(RuntimeError, "缺少阿舟素材 working.png"):
            ARTIFACTS.resolved_assets(self.root)
        for name in ("../outside.png", "/abs.png", "a\\b.png", ""):
            with self.subTest(name), self.assertRaisesRegex(RuntimeError, "not a safe logical asset name"):
                ARTIFACTS.resolve_asset(self.root, name)
        (self.overlay / "app-icon").mkdir(parents=True)
        (self.overlay / "app-icon/source.png").mkdir()
        with self.assertRaisesRegex(RuntimeError, "not a regular file"):
            ARTIFACTS.resolve_asset(self.root, "app-icon/source.png")
        os.symlink(self.library / "entry-avatar.png", self.overlay / "entry-avatar.png")
        with self.assertRaisesRegex(RuntimeError, "cannot pass through a symlink"):
            ARTIFACTS.resolve_asset(self.root, "entry-avatar.png")

    def test_overlay_must_be_a_directory(self):
        self.overlay.parent.mkdir(parents=True, exist_ok=True)
        self.overlay.write_bytes(b"not a directory")
        with self.assertRaisesRegex(RuntimeError, "assets/private"):
            ARTIFACTS.resolved_assets(self.root)

    def test_theme_paths_use_the_library_and_accept_legacy_embedded_overlay_paths(self):
        self.assertEqual("app-icon/source.png", ARTIFACTS.asset_name("assets/azhou/app-icon/source.png"))
        self.assertEqual("entry-avatar.png", ARTIFACTS.asset_name("assets/private/entry-avatar.png"))
        for value in ("assets/other/x.png", "assets/azhou/../x.png", "assets\\azhou\\x.png", None):
            with self.subTest(value), self.assertRaisesRegex(RuntimeError, "assets/azhou"):
                ARTIFACTS.asset_name(value)


if __name__ == "__main__":
    unittest.main()

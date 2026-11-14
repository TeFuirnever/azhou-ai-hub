#!/usr/bin/env python3
"""Resolve Azhou build assets and validate Git boundaries before staging a bundle."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD_PATHS = (
    ".build", ".build/module-cache", ".build/azhou-payload",
    ".build/azhou-install-registry",
    "dist", "assets/private",
)


def load_artifacts(root: Path):
    path = root / "tools/verify-artifacts.py"
    spec = importlib.util.spec_from_file_location("agent_skin_preflight_artifacts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load artifact verifier: {path}")
    artifacts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(artifacts)
    return artifacts


def load_theme(root: Path) -> dict:
    return load_artifacts(root).load_theme_config(root, require_inputs=True)


def resolve_icon(root: Path, theme: dict) -> Path:
    """Path of the icon source after the local overlay/library resolution."""
    artifacts = load_artifacts(root)
    return artifacts.resolve_asset(root, artifacts.asset_name(theme["identity"]["iconInput"]))[0]


def preflight(root: Path = ROOT, *, approved_icon_sha256: str | None = None) -> dict:
    """Return the validated theme after checking private paths and Git state."""
    root = Path(root).resolve()
    artifacts = load_artifacts(root)
    try:
        artifacts.resolved_assets(root)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    theme = load_theme(root)
    for name in BUILD_PATHS:
        if (root / name).is_symlink():
            raise SystemExit("拒绝通过符号链接构建：" + name)
    tracked = subprocess.check_output(
        ["git", "ls-files", "--", "assets/private", "dist", ".build", ".local"], cwd=root,
    ).decode().strip()
    if tracked:
        raise SystemExit("私有素材、构建或验收产物进入 Git 跟踪范围，停止构建：\n" + tracked)
    paths = (
        "assets/private/working.png", "assets/private/wallpaper-scene-q-v3.png",
        "assets/private/entry-avatar.png", "assets/private/app-icon/source.png",
        "dist/check.app", ".build/check.app", ".local/check",
    )
    for name in paths:
        result = subprocess.run(["git", "check-ignore", "-q", "--", name], cwd=root)
        if result.returncode:
            raise SystemExit("缺少私有产物 ignore 规则：" + name)
    icon_source = resolve_icon(root, theme)
    with icon_source.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SystemExit("图标源图必须是有效 PNG。")
    icon_width, icon_height = struct.unpack(">II", header[16:24])
    if icon_width != icon_height or icon_width < 1024:
        raise SystemExit(f"图标源图须为至少 1024×1024 的方形 PNG，实际 {icon_width}×{icon_height}。")
    if approved_icon_sha256 is not None:
        if re.fullmatch(r"[0-9a-fA-F]{64}", approved_icon_sha256) is None:
            raise SystemExit("AZHOU_APPROVED_ICON_SHA256 必须是 64 位十六进制 SHA-256。")
        with icon_source.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != approved_icon_sha256.lower():
            raise SystemExit("图标源图与已批准的 SHA-256 不符，未开始构建。")
    return theme


def main(root: Path = ROOT, *, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon-path", action="store_true",
                        help="print the resolved icon source path instead of the theme")
    args = parser.parse_args(argv)
    theme = preflight(root, approved_icon_sha256=os.environ.get("AZHOU_APPROVED_ICON_SHA256"))
    if args.icon_path:
        print(resolve_icon(Path(root).resolve(), theme))
        return 0
    print(json.dumps(theme, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

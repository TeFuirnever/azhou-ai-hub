#!/usr/bin/env python3
"""Validate private build inputs and Git boundaries before staging a bundle."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD_PATHS = (
    ".build", ".build/module-cache", ".build/azhou-payload", ".build/azhou-install-registry",
    "dist", "assets/private",
)


def load_theme(root: Path) -> dict:
    path = root / "tools/verify-artifacts.py"
    spec = importlib.util.spec_from_file_location("agent_skin_preflight_artifacts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load artifact verifier: {path}")
    artifacts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(artifacts)
    return artifacts.load_theme_config(root, require_inputs=True)


def preflight(root: Path = ROOT) -> dict:
    """Return the validated theme after checking private paths and Git state."""
    root = Path(root).resolve()
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
        "assets/private/working.png", "assets/private/working-v2.png", "assets/private/wallpaper-scene-q-v3.png",
        theme["identity"]["entryAvatarInput"], theme["identity"]["iconInput"], "assets/private/scene.js",
        "dist/check.app", ".build/check.app", ".local/check",
    )
    for name in paths:
        result = subprocess.run(["git", "check-ignore", "-q", "--", name], cwd=root)
        if result.returncode:
            raise SystemExit("缺少私有产物 ignore 规则：" + name)
    icon_source = root / theme["identity"]["iconInput"]
    if icon_source.is_symlink() or not icon_source.is_file():
        raise SystemExit("缺少 theme-config.json 指定的实体私有图标源图。")
    with icon_source.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SystemExit("图标源图必须是有效 PNG。")
    icon_width, icon_height = struct.unpack(">II", header[16:24])
    if icon_width != icon_height or icon_width < 1024:
        raise SystemExit(f"图标源图须为至少 1024×1024 的方形 PNG，实际 {icon_width}×{icon_height}。")
    return theme


def main(root: Path = ROOT) -> int:
    theme = preflight(root)
    print(json.dumps(theme, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

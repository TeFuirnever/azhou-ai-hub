#!/usr/bin/env python3
"""Check the published Azhou asset library and the optional local overlay.

assets/azhou/ must hold every build asset in the expected PNG shape plus its
LICENSE and NOTICE.md. assets/private/ is an optional, Git-ignored custom-skin
overlay: any build asset placed there must have the same shape; other files
are ignored by the build and only listed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = "assets/azhou"
OVERLAY = "assets/private"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_ASSET_BYTES = 8 * 1024 * 1024
# The entry avatar is embedded as a data URL capped at 2 MiB by build-startup.py.
MAX_ENTRY_AVATAR_BYTES = (2 * 1024 * 1024 - len("data:image/png;base64,")) // 4 * 3
LEGAL_FILES = ("LICENSE", "NOTICE.md")


def _exact(width: int, height: int):
    return lambda w, h: (w, h) == (width, height), f"{width}×{height}"


ASSETS = {
    "working.png": {"size": _exact(1254, 1254), "colors": (6,), "max": MAX_ASSET_BYTES},
    "wallpaper-scene-q-v3.png": {
        "size": (lambda w, h: 1024 <= w <= 8192 and 512 <= h <= 8192 and 1.4 <= w / h <= 2.5,
                 "landscape 1024–8192 × 512–8192, aspect 1.4–2.5"),
        "colors": (2, 6), "max": MAX_ASSET_BYTES,
    },
    "entry-avatar.png": {"size": _exact(1254, 1254), "colors": (2, 6), "max": MAX_ENTRY_AVATAR_BYTES},
    "app-icon/source.png": {"size": (lambda w, h: w == h and w >= 1024, "square, at least 1024"),
                            "colors": (2, 6), "max": MAX_ASSET_BYTES},
}
COLOR_NAMES = {2: "RGB", 6: "RGBA"}


def png_facts(data: bytes) -> tuple[int, int, int, int]:
    """Return (width, height, bit depth, color type) after walking every chunk CRC."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    offset, header, seen_end = len(PNG_SIGNATURE), None, False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        body_end = offset + 8 + length
        if body_end + 4 > len(data):
            raise ValueError("truncated PNG chunk")
        body = data[offset + 8:body_end]
        (crc,) = struct.unpack(">I", data[body_end:body_end + 4])
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise ValueError(f"PNG chunk {kind!r} fails its CRC")
        if header is None:
            if kind != b"IHDR" or length != 13:
                raise ValueError("PNG does not start with IHDR")
            header = struct.unpack(">IIBB", body[:10])
        offset = body_end + 4
        if kind == b"IEND":
            seen_end = True
            break
    if not seen_end or offset != len(data):
        raise ValueError("PNG does not end with IEND")
    return header


def check_file(path: Path, name: str) -> tuple[list[str], str | None]:
    """Validate one build asset; return (errors, summary)."""
    label = path.as_posix()
    if path.is_symlink() or not path.is_file():
        return [f"{label}: must be a regular file"], None
    spec = ASSETS[name]
    data = path.read_bytes()
    if len(data) > spec["max"]:
        return [f"{label}: {len(data)} bytes exceeds the {spec['max']}-byte limit"], None
    try:
        width, height, depth, color = png_facts(data)
    except ValueError as exc:
        return [f"{label}: {exc}"], None
    errors = []
    accepts, expected = spec["size"]
    if not accepts(width, height):
        errors.append(f"{label}: {width}×{height} does not match {expected}")
    if depth != 8 or color not in spec["colors"]:
        allowed = "/".join(COLOR_NAMES[value] for value in spec["colors"])
        errors.append(f"{label}: must be an 8-bit {allowed} PNG (bit depth {depth}, color type {color})")
    summary = f"{width}×{height} {COLOR_NAMES.get(color, color)} {len(data)} bytes"
    return errors, summary


def _walk(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file() or path.is_symlink())


def check(root: Path = ROOT, *, require_no_overlay: bool = False) -> dict:
    root = Path(root)
    report = {"library": {}, "overlay": {}, "ignored": [], "errors": []}
    errors = report["errors"]
    library = root / LIBRARY
    if library.is_symlink() or not library.is_dir():
        errors.append(f"{LIBRARY}: the published asset library is missing")
    else:
        expected = {*ASSETS, *LEGAL_FILES}
        for path in _walk(library):
            relative = path.relative_to(library).as_posix()
            if relative not in expected:
                errors.append(f"{LIBRARY}/{relative}: not part of the published asset set")
        for name in LEGAL_FILES:
            path = library / name
            if path.is_symlink() or not path.is_file() or not path.read_text(encoding="utf-8").strip():
                errors.append(f"{LIBRARY}/{name}: required license text is missing")
        for name in ASSETS:
            problems, summary = check_file(library / name, name)
            errors.extend(problems)
            if summary:
                report["library"][name] = summary
    overlay = root / OVERLAY
    if overlay.is_symlink() or (overlay.exists() and not overlay.is_dir()):
        errors.append(f"{OVERLAY}: the local overlay must be a real directory")
    elif overlay.is_dir():
        if require_no_overlay:
            errors.append(f"{OVERLAY}: a fresh checkout must not contain the local overlay")
        for path in _walk(overlay):
            relative = path.relative_to(overlay).as_posix()
            if relative not in ASSETS:
                report["ignored"].append(f"{OVERLAY}/{relative}")
                continue
            problems, summary = check_file(path, relative)
            errors.extend(problems)
            if summary:
                report["overlay"][relative] = summary
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="Agent Skin package root")
    parser.add_argument("--require-no-overlay", action="store_true",
                        help="fail when assets/private exists (fresh-clone check)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    report = check(args.root, require_no_overlay=args.require_no_overlay)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, summary in report["library"].items():
            source = "overlay" if name in report["overlay"] else "azhou"
            print(f"ok: {LIBRARY}/{name} {summary} (build uses {source})")
        for name, summary in report["overlay"].items():
            print(f"ok: {OVERLAY}/{name} {summary}")
        for name in report["ignored"]:
            print(f"ignored by the build: {name}")
        for error in report["errors"]:
            print(f"FAILED: {error}", file=sys.stderr)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

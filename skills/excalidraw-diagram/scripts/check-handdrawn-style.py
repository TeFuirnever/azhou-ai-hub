#!/usr/bin/env python3
"""Style gate: assert hand-drawn style properties on .excalidraw sources and exported SVGs.

Red on the exact symptom "hand-drawn feel too weak / inconsistent across viewers":
  1. Every geometric element (rectangle/ellipse/diamond/arrow/line) has roughness == 1.
  2. Every text element has fontFamily == 1 (Virgil hand-drawn latin).
  3. Every exported SVG embeds its required hand-drawn fonts in @font-face —
     always Virgil, plus Xiaolai when any source scene contains CJK — so glyphs
     never fall back to viewer-dependent system fonts.

Usage: python3 check-handdrawn-style.py [dir-or-file ...]   (default: current dir)
Exit 0 = green, 1 = red with a report.
"""

import json
import re
import sys
from pathlib import Path

GEOM = {"rectangle", "ellipse", "diamond", "arrow", "line"}


def check_scene(p: Path) -> tuple[list[str], bool, bool]:
    """Style-check one scene. Returns (issues, has_cjk, has_text)."""
    data = json.loads(p.read_text(encoding="utf-8"))
    bad_rough, bad_font = [], []
    has_cjk = has_text = False
    for el in data.get("elements", []):
        if el.get("isDeleted"):
            continue
        t = el.get("type")
        if t in GEOM and el.get("roughness") != 1:
            bad_rough.append(f"{el.get('id')}(roughness={el.get('roughness')})")
        if t == "text":
            has_text = True
            if any(ord(ch) > 0x2E00 for ch in el.get("text", "")):
                has_cjk = True
            if el.get("fontFamily") != 1:
                bad_font.append(f"{el.get('id')}(fontFamily={el.get('fontFamily')})")
    issues = []
    if bad_rough:
        issues.append(f"non-handdrawn roughness x{len(bad_rough)}: {bad_rough[:5]}")
    if bad_font:
        issues.append(f"non-handdrawn fontFamily x{len(bad_font)}: {bad_font[:5]}")
    return issues, has_cjk, has_text


def check_svg(p: Path, need_cjk: bool, need_virgil: bool) -> list[str]:
    content = p.read_text(encoding="utf-8")
    faces = set(re.findall(r"@font-face\s*\{[^}]*font-family:\s*['\"]?([^;'\"\s]+)", content))
    issues = []
    if need_virgil and not any("virgil" in f.lower() for f in faces):
        issues.append(f"no Virgil @font-face embedded (found: {sorted(faces)})")
    if need_cjk and not any("xiaolai" in f.lower() for f in faces):
        issues.append(f"no Xiaolai @font-face embedded (found: {sorted(faces)})")
    return issues


def main() -> int:
    targets = sys.argv[1:] or ["."]
    paths: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.excalidraw")))
        elif p.exists() and p.suffix == ".excalidraw":
            paths.append(p)
        else:
            print(f"RED {t}: not an .excalidraw file or directory")
            return 1
    if not paths:
        print("RED: no .excalidraw files found under targets — nothing to gate")
        return 1
    red = False
    for src in paths:
        issues, has_cjk, has_text = check_scene(src)
        for msg in issues:
            print(f"RED {src.name}: {msg}")
            red = True
        svg = src.with_suffix(".svg")
        if svg.exists():
            # the official engine only embeds faces for families the scene's
            # text actually uses — a textless scene ships no Virgil face
            for msg in check_svg(svg, has_cjk, need_virgil=has_text):
                print(f"RED {svg.name}: {msg}")
                red = True
        else:
            print(f"RED {svg.name}: missing export (deliverable SVG must share the scene's filename stem)")
            red = True
    if not red:
        print("GREEN: all sources roughness=1 fontFamily=1; SVGs embed required hand-drawn fonts")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())

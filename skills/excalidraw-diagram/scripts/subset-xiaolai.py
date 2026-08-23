#!/usr/bin/env python3
"""Build a char-level Xiaolai (CJK hand-drawn) subset covering given .excalidraw scenes.

The official Xiaolai font ships as ~211 unicode-range subset files (12 MB total).
For SVG delivery you only need the glyphs actually used. This tool collects the
union of characters from one or more scenes (plus optional extra text), merges the
covering subset files with fontTools, and emits one small woff2 (typically tens of
KB). Feed the result to export-official-svg.py via --subset (or drop it as
xiaolai-subset.woff2 next to the scenes — that path is the default there).

Needs fontTools + brotli (no install into the skill env required):

    cd "$SKILL_DIR/references"
    uv run --with fonttools --with brotli python ../scripts/subset-xiaolai.py \\
        <scene.excalidraw | dir> [...] [-o xiaolai-subset.woff2] [--extra "，·→"]

Exit 0 with a coverage report on success; exit 1 if any CJK char is missing.
"""

import argparse
import json
import string
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FONTDIR = SKILL / "references" / "fonts" / "Xiaolai"


def collect_chars(inputs: list[Path], extra: str) -> set[str]:
    chars = set(string.printable) | set(extra)
    for p in inputs:
        files = sorted(p.glob("*.excalidraw")) if p.is_dir() else [p]
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            for el in data.get("elements", []):
                if el.get("type") == "text" and not el.get("isDeleted"):
                    chars |= set(el.get("text", ""))
    return {c for c in chars if ord(c) >= 32}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help=".excalidraw files or directories")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="output woff2 (default: xiaolai-subset.woff2 in the first input's directory — "
                         "where export-official-svg.py auto-discovers it)")
    ap.add_argument("--extra", default="", help="additional characters to include")
    args = ap.parse_args()
    if args.output is None:
        first = args.inputs[0] if args.inputs[0].is_dir() else args.inputs[0].parent
        args.output = first / "xiaolai-subset.woff2"

    chars = collect_chars(args.inputs, args.extra)
    cjk = {c for c in chars if ord(c) > 0x2E00}
    print(f"unique chars: {len(chars)} (CJK-ish: {len(cjk)})")
    if not cjk:
        print("no CJK characters found — scenes render with Virgil alone; subset not needed")
        return 0

    try:
        from fontTools import subset
        from fontTools.merge import Merger
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.exit("fontTools missing. Run via: uv run --with fonttools --with brotli python subset-xiaolai.py ...")

    covering = set()
    for f in sorted(FONTDIR.glob("*.woff2")):
        try:
            cmap = TTFont(f).getBestCmap() or {}
        except Exception as e:  # broken subset file — skip, others cover the ranges
            print(f"  skip {f.name}: {e}", file=sys.stderr)
            continue
        if any(ord(c) in cmap for c in chars):
            covering.add(f)
    if not covering:
        sys.exit(f"no Xiaolai subset file covers any needed char — is {FONTDIR} present?")
    print(f"covering subset files: {len(covering)}")

    import tempfile

    # single covering file: Merger is built for >=2 fonts; load it directly
    merged = TTFont(next(iter(covering))) if len(covering) == 1 else Merger().merge([str(f) for f in covering])
    tmp = Path(tempfile.mkdtemp(prefix="xiaolai-")) / "merged.ttf"
    try:
        merged.save(tmp)

        opts = subset.Options()
        opts.flavor = "woff2"
        ss = subset.Subsetter(options=opts)
        ss.populate(unicodes=sorted(ord(c) for c in chars))
        font = subset.load_font(str(tmp), opts)
        ss.subset(font)
        subset.save_font(font, args.output, opts)
    finally:
        import shutil

        shutil.rmtree(tmp.parent, ignore_errors=True)

    final_cmap = TTFont(args.output).getBestCmap() or {}
    # Xiaolai exists to cover CJK; latin/digits render via Virgil, which sits
    # first in the injected font-family chain — so only CJK coverage is required.
    missing = sorted(c for c in chars if ord(c) > 0x2E00 and ord(c) not in final_cmap)
    print(f"subset: {args.output} ({args.output.stat().st_size / 1024:.1f} KB)")
    if missing:
        print(f"MISSING {len(missing)} CJK chars: {''.join(missing[:40])}")
        return 1
    print(f"coverage: 100% of used CJK characters ({len(cjk)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

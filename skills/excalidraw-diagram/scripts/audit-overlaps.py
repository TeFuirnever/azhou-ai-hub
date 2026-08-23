#!/usr/bin/env python3
"""Geometric overlap audit for a .excalidraw scene — precise complement to vision-model audits.

Vision models over-report overlaps on hand-drawn diagrams (legitimate nesting and
rough.js border wobble get flagged as defects). This script computes exact
bounding-box geometry and reports only real defects:

  1. STRADDLE  — a non-rectangle element (text/icon part) sits half-in/half-out of a
                 rectangle's border (a label riding a box edge, an icon crossing a line).
  2. TEXT-TEXT — two text elements' bounding boxes intersect.
  3. NESTING   — a child rectangle partially (not fully) inside a parent rectangle,
                 i.e. it pokes out through the parent's border.

Arrows, lines, and freedraw strokes are exempt from STRADDLE — they connect boxes
and must cross borders.

Exit code 0 = clean, 1 = defects found. Output lines are `kind: detail` so a fix
loop can parse them. After each fix, re-run until clean, then do one vision audit
to confirm aesthetics (geometry can't judge wobble-induced visual crowding).

Usage: audit-overlaps.py scene.excalidraw [--margin N]   # margin: border clearance px, default 3
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from excalidraw_lib import _elem_bounds as bb  # points- and rotation-aware bounds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--margin", type=float, default=3.0)
    a = ap.parse_args()
    els = json.load(open(a.scene))["elements"]
    rects = [e for e in els if e["type"] == "rectangle"]
    texts = [e for e in els if e["type"] == "text"]
    m = a.margin
    issues = 0

    def label(r):
        for be in r.get("boundElements") or []:
            if be.get("type") == "text":
                t = [q for q in els if q["id"] == be["id"]]
                if t:
                    return t[0]["text"].split("\n")[0][:30]
        return r["id"][:12]

    # 1) elements straddling a rectangle border
    def icon_prefix(i):
        return i.split("_")[0] + "_" + i.split("_")[1] if i.count("_") >= 1 else i

    for r in rects:
        x0, y0, x1, y1 = bb(r)
        for e in els:
            if e is r or e["type"] in ("rectangle", "arrow", "line", "freedraw"):
                continue
            # skip intra-icon composition: elements of the same merged library icon
            # (same groupIds tag, or the legacy same-id-prefix heuristic)
            if set(e.get("groupIds") or []) & set(r.get("groupIds") or []) \
                    or icon_prefix(e["id"]) == icon_prefix(r["id"]):
                continue
            ex0, ey0, ex1, ey1 = bb(e)
            corners = [(ex0, ey0), (ex1, ey0), (ex1, ey1), (ex0, ey1)]
            ins = [x0 + m < p[0] < x1 - m and y0 + m < p[1] < y1 - m for p in corners]
            if any(ins) and not all(ins):
                issues += 1
                what = e.get("text", e["id"][:14]).replace("\n", "/")[:30]
                print(f"STRADDLE: [{label(r)}] <- {e['type']} '{what}'"
                      " — fixes: move element fully inside/outside | shrink an inflated declared width to the rendered text")

    # 2) text-text overlaps
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            t, u = texts[i], texts[j]
            ox = min(t["x"] + t["width"], u["x"] + u["width"]) - max(t["x"], u["x"])
            oy = min(t["y"] + t["height"], u["y"] + u["height"]) - max(t["y"], u["y"])
            if ox > 2 and oy > 2:
                issues += 1
                print(f"TEXT-TEXT: {t['text'][:20]!r} <-> {u['text'][:20]!r} ({ox:.0f}x{oy:.0f}px)"
                      " — fixes: move one label | shorten wording | wrap with \\n")

    # 3) child rects poking out of parents
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i == j:
                continue
            c, p = bb(rects[i]), bb(rects[j])
            ix, iy = min(c[2], p[2]) - max(c[0], p[0]), min(c[3], p[3]) - max(c[1], p[1])
            if ix > 2 and iy > 2:
                inside_x = c[0] >= p[0] - 1 and c[2] <= p[2] + 1
                inside_y = c[1] >= p[1] - 1 and c[3] <= p[3] + 1
                if not (inside_x and inside_y) and rects[i]["width"] * rects[i]["height"] < rects[j]["width"] * rects[j]["height"]:
                    issues += 1
                    print(f"NESTING: [{label(rects[i])}] pokes out of [{label(rects[j])}]"
                          " — fixes: resize child to fit | move child fully outside | grow parent with 50-60px padding")

    print(f"GEOMETRY ISSUES: {issues}")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()

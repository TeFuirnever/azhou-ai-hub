#!/usr/bin/env python3
"""Scene hygiene gate — the anti-pattern checklist, mechanized (two phases).

Phase 1 (per-element shape):
  H-SEED      seed is a positive int and unique across the scene
  H-ID        ids are non-empty and unique
  H-POINTS    line/arrow `points` start at [0, 0]
  H-TEXT-COLOR every text element carries an explicit strokeColor
  H-BOUND-EMPTY boundElements is null or a non-empty list — [] is the smell
  H-ARROWHEAD arrowheads are in the valid enum

Phase 2 (cross-collection + preset consistency):
  H-REF-CONTAINER  text.containerId resolves; the container lists the text back
  H-REF-BOUND      every boundElements id resolves
  H-REF-BINDING    arrow startBinding/endBinding elementIds resolve
  H-PRESET-FONT    all text fontFamily values are one single value — never mix
  H-PRESET-ROUGH   all geometry roughness values are one single value (0 or 1)

Diagnostics are `CODE: subject — evidence — fixes: ...` (stable codes, parseable
by fix loops and the benchmark verifier). Exit 0 = clean, 1 = violations.

Usage: python3 check-scene-hygiene.py <scene.excalidraw> [...] [--json]
"""

import argparse
import json
import sys
from pathlib import Path

GEOM = {"rectangle", "ellipse", "diamond", "arrow", "line"}
ARROWHEADS = {None, "arrow", "bar", "dot", "triangle"}


def check_scene(data: dict) -> list[dict]:
    els = [e for e in data.get("elements", []) if not e.get("isDeleted")]
    by_id = {e.get("id"): e for e in els if e.get("id")}
    diags: list[dict] = []

    def add(code, subject, evidence, fixes):
        fixes = [fixes] if isinstance(fixes, str) else fixes
        diags.append({"code": code, "subject": subject, "evidence": evidence, "fixes": fixes})

    # ---- phase 1: per-element shape
    seeds: dict[int, str] = {}
    seen_ids: dict[str, str] = {}
    for e in els:
        eid = e.get("id") or "<no-id>"
        seed = e.get("seed")
        if not isinstance(seed, int) or seed <= 0:
            add("H-SEED", eid, f"seed={seed!r}", "assign a unique positive int (namespace by section: 100xxx, 200xxx)")
        elif seed in seeds:
            add("H-SEED", eid, f"seed={seed} already used by {seeds[seed]}", "assign a unique positive int")
        else:
            seeds[seed] = eid
        if not e.get("id"):
            add("H-ID", eid, "empty id", "assign a descriptive unique id")
        elif eid in seen_ids:
            add("H-ID", eid, f"id already used by {seen_ids[eid]}", "assign unique ids — merge via excalidraw_lib.py deduplicates automatically")
        else:
            seen_ids[eid] = eid
        if e["type"] in ("line", "arrow"):
            pts = e.get("points") or []
            bad = not pts or pts[0][0] != 0 or pts[0][1] != 0
            if bad:
                add("H-POINTS", eid, f"points[0]={pts[0] if pts else None}", "shift x/y to the first point and start points at [0,0]")
        if e["type"] == "text" and not e.get("strokeColor"):
            add("H-TEXT-COLOR", eid, "text without strokeColor", "set an explicit palette strokeColor (text stroke IS the render color)")
        be = e.get("boundElements")
        if be == []:
            add("H-BOUND-EMPTY", eid, "boundElements is []", "use null (never []) — or list the real bound ids")
        if e["type"] == "arrow":
            for k in ("startArrowhead", "endArrowhead"):
                if e.get(k) not in ARROWHEADS:
                    add("H-ARROWHEAD", eid, f"{k}={e.get(k)!r}", f"pick from {sorted(str(a) for a in ARROWHEADS)}")

    # ---- phase 2: cross-collection
    for e in els:
        eid = e.get("id") or "<no-id>"
        if e["type"] == "text" and e.get("containerId"):
            target = by_id.get(e["containerId"])
            if target is None:
                add("H-REF-CONTAINER", eid, f"containerId={e['containerId']} not found", "point at an existing container or clear containerId")
            elif not any(isinstance(b, dict) and b.get("id") == eid for b in (target.get("boundElements") or [])):
                add("H-REF-CONTAINER", eid, f"container {e['containerId']} does not list this text in boundElements",
                    "add {\"id\": ..., \"type\": \"text\"} to the container's boundElements")
        for b in (e.get("boundElements") or []):
            if isinstance(b, dict) and b.get("id") not in by_id:
                add("H-REF-BOUND", eid, f"boundElements id={b.get('id')!r} not found", "drop the stale binding or restore the element")
        for k in ("startBinding", "endBinding"):
            b = e.get(k)
            if isinstance(b, dict) and b.get("elementId") not in by_id:
                add("H-REF-BINDING", eid, f"{k}.elementId={b.get('elementId')!r} not found", "drop the binding or restore the element")

    fonts = {e.get("fontFamily") for e in els if e["type"] == "text"}
    if len(fonts) > 1:
        add("H-PRESET-FONT", "<scene>", f"mixed fontFamily values {sorted(map(str, fonts))}",
            "pick one preset per deliverable — 1 Virgil hand-drawn or 3 Cascadia clean — never mix")
    roughs = {e.get("roughness") for e in els if e["type"] in GEOM}
    if len(roughs) > 1:
        add("H-PRESET-ROUGH", "<scene>", f"mixed roughness values {sorted(map(str, roughs))}",
            "pick one preset per deliverable — 0 clean or 1 hand-drawn — never mix")
    return diags


def main() -> int:
    ap = argparse.ArgumentParser(description="Mechanized anti-pattern checklist for .excalidraw scenes.")
    ap.add_argument("scenes", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="print diagnostics as JSON")
    args = ap.parse_args()

    total = 0
    for p in args.scenes:
        data = json.loads(p.read_text(encoding="utf-8"))
        diags = check_scene(data)
        total += len(diags)
        if args.json:
            print(json.dumps({"scene": p.name, "diagnostics": diags}, ensure_ascii=False))
        else:
            for d in diags:
                print(f"{d['code']}: {d['subject']} — {d['evidence']} — fixes: {' | '.join(d['fixes'])}")
            if not diags:
                print(f"{p.name}: HYGIENE CLEAN")
    print(f"HYGIENE ISSUES: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

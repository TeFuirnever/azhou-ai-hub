#!/usr/bin/env python3
"""Fetch and embed Excalidraw community-library items into a .excalidraw scene.

Community libraries (https://libraries.excalidraw.com, repo excalidraw/excalidraw-libraries)
are almost all built from the same vector primitives this skill already exports
(rectangle/ellipse/line/arrow/diamond/text/freedraw), so their items render correctly
through Kroki and the local brute-export CLI. This helper discovers libraries, lists
their items, and merges an item into a scene with namespaced IDs and translated
coordinates so it drops in without collisions.

The FULL official library set (all 231 libraries) is vendored gzipped at
references/libraries/<author>/<name>.excalidrawlib.gz (~10 MB) — search/items/merge/
catalog resolve from it offline; the network is only touched for sources that are
neither a local path nor in the vendored set.

Usage:
  excalidraw_lib.py search <keyword>
      Match vendored libraries by filename or item name (offline).
  excalidraw_lib.py items  <source>
      List the items in a library (index, name, element count, image flag).
  excalidraw_lib.py merge  <scene.excalidraw> <source> <item> <x> <y> [--prefix P] [--scale S]
                           [--strip-text] [--roughness N]
      Add <item> (index or name substring) to the scene at (x, y), in place.
      --strip-text   drop the item's own text elements (use when the scene
                     already labels the node — also shrinks the icon's bbox
                     to art-only, which usually fits a tighter niche)
      --roughness N  force merged elements to roughness N (e.g. 1 to match a
                     hand-drawn scene; library items ship mixed values)
  excalidraw_lib.py catalog [filter]
      List the vendored libraries with item counts and image flags (offline).

<source> is "author/name.excalidrawlib" (vendored or fetched from the official repo)
or a path to a local .excalidrawlib file.
"""
import argparse, copy, gzip, json, math, os, re, sys, urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/excalidraw/excalidraw-libraries/main"
CACHE = "/tmp/excalidraw-libs"
VENDORED = Path(__file__).resolve().parent.parent / "references" / "libraries"
SOURCE_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.excalidrawlib$")


def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        with urllib.request.urlopen(url, timeout=30) as r, open(dest, "wb") as w:
            w.write(r.read())
    return dest


def load_index():
    return json.load(open(fetch(f"{BASE}/libraries.json", f"{CACHE}/libraries.json")))


def vendored_path(source):
    """Path to the vendored .gz for 'author/name.excalidrawlib', or None."""
    gz = VENDORED / f"{source}.gz"
    return gz if gz.exists() else None


def load_lib(source):
    if os.path.exists(source):
        return json.load(open(source, encoding="utf-8"))
    if not SOURCE_RE.match(source):
        sys.exit(f"Invalid library source '{source}' — expected author/name.excalidrawlib or a local path")
    gz = vendored_path(source)
    if gz:
        return json.load(gzip.open(gz, "rt", encoding="utf-8"))
    path = fetch(f"{BASE}/libraries/{source}", f"{CACHE}/{source}")
    return json.load(open(path, encoding="utf-8"))


def items_of(lib):
    """Return list of (name, elements) regardless of library format version."""
    raw = lib.get("libraryItems") or lib.get("library") or []
    out = []
    for i, it in enumerate(raw):
        if isinstance(it, list):
            out.append((f"item{i}", it))
        else:
            out.append((it.get("name") or f"item{i}", it.get("elements", [])))
    return out


def _elem_bounds(e):
    """True visual bounds of one element — accounts for `points` (lines/arrows)
    and `angle` (rotation), both of which a naive x/y/w/h box misses and which
    otherwise mis-place rotated or arrow-based library icons."""
    x, y, w, h = e.get("x", 0), e.get("y", 0), e.get("width", 0), e.get("height", 0)
    pts = e.get("points")
    if pts:
        xs = [x + p[0] for p in pts]; ys = [y + p[1] for p in pts]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    else:
        x0, y0, x1, y1 = x, y, x + w, y + h
    a = e.get("angle", 0) or 0
    if a:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ca, sa = math.cos(a), math.sin(a)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        rx = [cx + (px - cx) * ca - (py - cy) * sa for px, py in corners]
        ry = [cy + (px - cx) * sa + (py - cy) * ca for px, py in corners]
        x0, x1, y0, y1 = min(rx), max(rx), min(ry), max(ry)
    return x0, y0, x1, y1


def bbox(els):
    b = [_elem_bounds(e) for e in els]
    return min(p[0] for p in b), min(p[1] for p in b), max(p[2] for p in b), max(p[3] for p in b)


def place(els, tx, ty, prefix, scale):
    x0, y0, _, _ = bbox(els)
    els = copy.deepcopy(els)
    # normalize corrupt library data natively present in some items:
    # duplicate ids inside one item, and colliding/invalid seeds
    counts: dict = {}
    for e in els:
        eid = e.get("id")
        if eid is None:
            continue
        counts[eid] = counts.get(eid, 0) + 1
        if counts[eid] > 1:
            e["id"] = f"{eid}__{counts[eid]}"
    used_seeds: set = set()
    for e in els:
        sd = e.get("seed")
        sd = sd if isinstance(sd, int) and sd > 0 else 1
        while sd in used_seeds:
            sd += 1
        e["seed"] = sd
        used_seeds.add(sd)
    idmap = {e["id"]: f"{prefix}_{e['id']}" for e in els if "id" in e}
    out = []
    for e in els:
        e = copy.deepcopy(e)
        if e.get("boundElements") == []:
            e["boundElements"] = None  # library items ship []; null is the hygiene contract
        if "id" in e:
            e["id"] = idmap[e["id"]]
        e["groupIds"] = [prefix]  # one group per merged item — audits exempt intra-icon art
        e["x"] = (e.get("x", 0) - x0) * scale + tx
        e["y"] = (e.get("y", 0) - y0) * scale + ty
        for k in ("width", "height"):
            if k in e:
                e[k] *= scale
        if "points" in e and e["points"]:
            # points may carry extra dims (freedraw pressure) — scale x/y only
            pts = [list(p) for p in e["points"]]
            for q in pts:
                q[0] *= scale
                q[1] *= scale
            # re-base to origin (hygiene contract: points[0][:2] == [0,0]) while
            # preserving absolute geometry; snap float noise first
            p0x = 0.0 if abs(pts[0][0]) < 1e-9 else pts[0][0]
            p0y = 0.0 if abs(pts[0][1]) < 1e-9 else pts[0][1]
            if p0x or p0y:
                e["x"] += p0x
                e["y"] += p0y
                for q in pts:
                    q[0] -= p0x
                    q[1] -= p0y
                pts[0][0] = 0.0
                pts[0][1] = 0.0
            e["points"] = pts
        if "fontSize" in e:
            e["fontSize"] *= scale
        if e.get("containerId") in idmap:
            e["containerId"] = idmap[e["containerId"]]
        elif e.get("containerId"):
            e["containerId"] = None  # library items reference elements outside the item
        be = e.get("boundElements")
        if isinstance(be, list):
            kept = []
            for b in be:
                if isinstance(b, dict) and b.get("id") in idmap:
                    b["id"] = idmap[b["id"]]
                    kept.append(b)
                # entries pointing outside the merged item (e.g. sibling arrows the
                # library kept in a different item) are dropped — they are dangling
                # refs by the time the item lands in a scene
            e["boundElements"] = kept or None
        for b in ("startBinding", "endBinding"):
            if e.get(b) and e[b].get("elementId") in idmap:
                e[b]["elementId"] = idmap[e[b]["elementId"]]
            elif e.get(b):
                e[b] = None  # binding to an element outside the merged item
        out.append(e)
    return out


def resolve_item(items, sel):
    if sel.isdigit():
        i = int(sel)
        if i >= len(items):
            sys.exit(f"Index {i} out of range (0–{len(items)-1}). Run: excalidraw_lib.py items <source>")
        return items[i]
    for name, els in items:
        if sel.lower() in name.lower():
            return name, els
    sys.exit(f"No item matching '{sel}'. Run: excalidraw_lib.py items <source>")


def vendored_libs():
    """Yield 'author/name.excalidrawlib' for every vendored library."""
    for gz in sorted(VENDORED.rglob("*.excalidrawlib.gz")):
        yield str(gz.relative_to(VENDORED))[: -len(".gz")]


def cmd_search(args):
    needle = args.keyword.lower()
    hits = 0
    for src in vendored_libs():
        entries = items_of(load_lib(src))
        matched = [n for n, _ in entries if needle in n.lower()]
        if needle in src.lower() or matched:
            hits += 1
            print(f"{src}\n    {len(entries)} items" + (f"; matched: {', '.join(matched[:10])}" if matched else ""))
    if not hits:
        print(f"No vendored libraries match '{args.keyword}'.")
        if not VENDORED.exists():
            print("Vendored set missing — searching the online index instead:")
            for lib in load_index():
                names = " ".join(lib.get("itemNames", []))
                if args.keyword.lower() in f"{lib['name']} {lib.get('description','')} {names}".lower():
                    print(f"{lib['source']}\n    {lib['name']} — {len(lib.get('itemNames', []))} items")


def cmd_catalog(args):
    total_items = 0
    libs = 0
    for src in vendored_libs():
        if args.filter and args.filter.lower() not in src.lower():
            continue
        lib = load_lib(src)
        entries = items_of(lib)
        total_items += len(entries)
        libs += 1
        img = [n for n, els in entries if any(e.get("type") == "image" for e in els)]
        flag = f"  [image items: {len(img)}]" if img else ""
        print(f"{src:70} {len(entries):4} items{flag}")
    print(f"\n{libs} libraries, {total_items} items vendored at {VENDORED}")


def cmd_items(args):
    for i, (name, els) in enumerate(items_of(load_lib(args.source))):
        img = "  [HAS IMAGE — won't render via export]" if any(e.get("type") == "image" for e in els) else ""
        print(f"{i:3}  {name}  ({len(els)} els){img}")


def cmd_merge(args):
    name, els = resolve_item(items_of(load_lib(args.source)), args.item)
    if any(e.get("type") == "image" for e in els):
        sys.exit(f"Item '{name}' contains an image element — skip it (won't render via Kroki/CLI).")
    if not els:
        sys.exit(f"Item '{name}' has no elements.")
    stripped = set()
    if args.strip_text:
        stripped = {e["id"] for e in els if e.get("type") == "text"}
        els = [e for e in els if e.get("type") != "text"]
        for e in els:  # keep no dangling refs to the stripped labels
            be = e.get("boundElements")
            if isinstance(be, list):
                e["boundElements"] = [b for b in be if not (isinstance(b, dict) and b.get("id") in stripped)] or None
    if args.roughness is not None:
        for e in els:
            e["roughness"] = args.roughness
    scene = json.load(open(args.scene, encoding="utf-8"))
    prefix = args.prefix or f"lib{len(scene['elements'])}"
    placed = place(els, args.x, args.y, prefix, args.scale)
    scene["elements"].extend(placed)
    tmp = args.scene + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(scene, f, ensure_ascii=False)
    os.replace(tmp, args.scene)
    x0, y0, x1, y1 = bbox(placed)
    print(f"Merged '{name}' ({len(placed)} els) at ({args.x},{args.y}) into {args.scene}"
          f" — art bbox ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("keyword"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("items"); s.add_argument("source"); s.set_defaults(fn=cmd_items)
    s = sub.add_parser("catalog"); s.add_argument("filter", nargs="?", default=""); s.set_defaults(fn=cmd_catalog)
    s = sub.add_parser("merge")
    s.add_argument("scene"); s.add_argument("source"); s.add_argument("item")
    s.add_argument("x", type=float); s.add_argument("y", type=float)
    s.add_argument("--prefix"); s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--strip-text", action="store_true")
    s.add_argument("--roughness", type=int, default=None)
    s.set_defaults(fn=cmd_merge)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

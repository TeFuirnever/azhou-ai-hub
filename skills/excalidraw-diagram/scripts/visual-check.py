#!/usr/bin/env python3
"""Post-delivery visual evidence collector — honest by construction.

Renders the EXACT delivered SVG (never re-renders or modifies it) at standard
widths and writes PNG sidecars plus a JSON receipt bound to the artifact's
SHA-256. The receipt always reports visual_review: "pending" — screenshots are
evidence for inspection, never an automatic polish claim. Exit 0 = all captures
passed, 1 = capture failure, 2 = Chromium unavailable (receipt status skipped,
stale sidecars removed rather than passed off as current).

Usage (needs the skill's uv env with Playwright chromium):

    cd "$SKILL_DIR/references"
    uv run python ../scripts/visual-check.py <artifact.svg> [--widths 880,1300]

Default widths: 880 (Markdown report column) and 1300 (full audit view).
Sidecars land next to the artifact as <stem>.evidence-<width>.png plus
<artifact>.visual-check.json. Review the sidecars yourself (or with a vision
model), then record passed / failed / skipped separately — this script never
decides perceptual quality for you.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect honest visual evidence for a delivered SVG.")
    ap.add_argument("artifact", type=Path)
    ap.add_argument("--widths", default="880,1300", help="comma-separated CSS pixel widths (default 880,1300)")
    args = ap.parse_args()

    svg = args.artifact
    if not svg.exists():
        print(f"RED artifact not found: {svg}", file=sys.stderr)
        return 1
    widths = [int(w) for w in args.widths.split(",")]
    art_stat = {"sha256": hashlib.sha256(svg.read_bytes()).hexdigest(), "bytes": svg.stat().st_size}
    receipt_path = svg.with_name(svg.name + ".visual-check.json")
    sidecar_for = lambda w: svg.with_name(f"{svg.stem}.evidence-{w}.png")

    def stale_cleanup():
        for w in (880, 1300):
            sidecar_for(w).unlink(missing_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        stale_cleanup()
        receipt_path.write_text(json.dumps(
            {"schema": 1, "artifact": art_stat, "status": "skipped",
             "reason": "playwright unavailable", "visual_review": "pending"},
            sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("SKIPPED — playwright not installed (receipt: skipped)", file=sys.stderr)
        return 2

    captures = []
    ok = True
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            stale_cleanup()
            receipt_path.write_text(json.dumps(
                {"schema": 1, "artifact": art_stat, "status": "skipped",
                 "reason": f"chromium launch failed: {e}", "visual_review": "pending"},
                sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print("SKIPPED — chromium unavailable (receipt: skipped)", file=sys.stderr)
            return 2
        try:
            page = browser.new_page(viewport={"width": max(widths) + 40, "height": 1000})
            page.goto(f"file://{svg.resolve()}")
            page.wait_for_timeout(600)  # embedded fonts settle
            el = page.query_selector("svg")
            if el is None:
                raise RuntimeError("no <svg> element in artifact")
            for w in widths:
                page.evaluate(
                    "(w) => { const s = document.querySelector('svg');"
                    " s.style.width = w + 'px'; s.style.height = 'auto'; }", w)
                page.wait_for_timeout(200)
                sidecar = sidecar_for(w)
                el.screenshot(path=str(sidecar))
                captures.append({"width": w, "file": sidecar.name, "bytes": sidecar.stat().st_size})
                if sidecar.stat().st_size < 500:
                    ok = False
        except Exception as e:
            stale_cleanup()
            receipt_path.write_text(json.dumps(
                {"schema": 1, "artifact": art_stat, "status": "failed",
                 "reason": str(e), "visual_review": "pending"},
                sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print(f"FAILED — {e}", file=sys.stderr)
            return 1
        finally:
            browser.close()

    receipt_path.write_text(json.dumps(
        {"schema": 1, "artifact": art_stat, "status": "captured",
         "widths": widths, "captures": captures, "visual_review": "pending"},
        sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"CAPTURED {len(captures)} sidecar(s) next to {svg.name}; receipt {receipt_path.name}")
    print('visual_review: pending — inspect the sidecars, then record passed/failed/skipped yourself')
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Export .excalidraw to SVG via the OFFICIAL Excalidraw engine (deliverable path).

Why this exists: the skill's render-svg.mjs uses rough.js directly and emits
font-family fallback chains like "Virgil, 'Comic Sans MS', 'Segoe Print', cursive"
— CJK (and any missing glyph) then falls back to whatever the viewing machine
has, so the same file looks different per viewer. This script renders through
the vendored official bundle (same code path as excalidraw.com) and injects a
char-level Xiaolai subset for CJK when one is available, so the SVG is
self-contained and viewer-independent. Validation path == delivery path: pass
--png to screenshot the exact mutated DOM used for the SVG.

Pipeline:
  1. Playwright loads references/render_template.html (official exportToSvg,
     fonts resolved offline from references/fonts/).
  2. In-page DOM mutation (when a Xiaolai subset is supplied — autodiscovery
     picks up <scene dir>/xiaolai-subset.woff2; an explicit --subset overrides,
     --no-cjk skips):
       - @font-face for the subset appended to the SVG's font style block
       - text font-family chains gain Xiaolai after Virgil
  3. Writes the mutated outerHTML as the .svg deliverable; optionally
     screenshots the same DOM to a .png for the audit loop.

Usage (needs the skill's uv env with playwright + chromium):

    cd "$SKILL_DIR/references"
    uv run python ../scripts/export-official-svg.py <in.excalidraw> <out.svg> \
        [--subset xiaolai-subset.woff2] [--no-cjk] [--png audit.png] [--deliver]

Build the subset with subset-xiaolai.py first when scenes contain CJK. With
--deliver, the target is replaced atomically only after the scene-style and
artifact-font checks pass, and <out.svg>.receipt.json records SHA-256 + bytes
for scene and artifact (visual_review stays "pending" — receipts never claim
visual review).
"""

from __future__ import annotations

import base64
import functools
import http.server
import json
import os
import sys
import threading
from pathlib import Path

REFERENCES = Path(__file__).resolve().parent.parent / "references"

MUTATE_JS = """
(fontB64) => {
    const svg = document.querySelector('#root svg');
    let styleEl = svg.querySelector('style.style-fonts');
    if (!styleEl) {
        styleEl = document.createElementNS('http://www.w3.org/2000/svg', 'style');
        styleEl.setAttribute('class', 'style-fonts');
        svg.insertBefore(styleEl, svg.firstChild);
    }
    styleEl.textContent += `\\n@font-face { font-family: Xiaolai; src: url(data:font/woff2;base64,${fontB64}) format('woff2'); }`;
    svg.querySelectorAll('text').forEach(t => {
        const ff = t.getAttribute('font-family');
        if (ff && ff.includes('Virgil') && !ff.includes('Xiaolai')) {
            t.setAttribute('font-family', ff.replace('Virgil', 'Virgil, Xiaolai'));
        }
    });
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return clone.outerHTML;
}
"""

PLAIN_JS = """
() => {
    const svg = document.querySelector('#root svg');
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return clone.outerHTML;
}
"""


def export(src: Path, dst: Path, png_dst: Path | None, subset: Path | None) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    font_b64 = base64.b64encode(subset.read_bytes()).decode("ascii") if subset else None

    class _Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Quiet, directory=str(REFERENCES))
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/render_template.html"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(url)
            page.wait_for_function("window.__moduleReady === true", timeout=30000)
            result = page.evaluate(f"window.renderDiagram({json.dumps(data)})")
            if not result or not result.get("success"):
                print(f"ERROR: {result}", file=sys.stderr)
                sys.exit(1)
            page.wait_for_function("window.__renderComplete === true", timeout=15000)
            page.wait_for_timeout(300)  # let injected fonts settle
            svg_html = page.evaluate(MUTATE_JS, font_b64) if font_b64 else page.evaluate(PLAIN_JS)
            dst.write_text(svg_html, encoding="utf-8")
            if png_dst:
                page.query_selector("#root svg").screenshot(path=str(png_dst))
        finally:
            browser.close()
            httpd.shutdown()

    note = " + Xiaolai injected" if font_b64 else " (no CJK subset)"
    print(f"wrote {dst} ({len(svg_html)} bytes){note}" + (f" + {png_dst}" if png_dst else ""))


def _sha256(p: Path) -> str:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest()


def deliver(src: Path, dst: Path, subset: Path | None) -> None:
    """Atomic verified delivery: render a private candidate, run the artifact
    checks, replace the target only if every check passes, and write a
    deterministic SHA-256 receipt. Failure preserves the previous artifact
    byte-for-byte. The receipt proves bytes + automated checks only — it never
    includes visual review (visual_review stays "pending" until a human/agent
    inspects; use visual-check.py to collect that evidence)."""
    import importlib.util

    sys.path.insert(0, str(Path(__file__).parent))
    spec = importlib.util.spec_from_file_location(
        "handdrawn_gate", Path(__file__).parent / "check-handdrawn-style.py"
    )
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    candidate = dst.with_name(dst.stem + ".candidate" + dst.suffix)
    export(src, candidate, None, subset)

    scene_issues, has_cjk, has_text = gate.check_scene(src)
    checks = [{"name": "scene-style", "pass": not scene_issues, "detail": scene_issues[:5]}]
    svg_issues = gate.check_svg(candidate, has_cjk, need_virgil=has_text)
    checks.append({"name": "artifact-fonts", "pass": not svg_issues, "detail": svg_issues})

    scene_stat = {"sha256": _sha256(src), "bytes": src.stat().st_size}
    receipt_path = dst.with_name(dst.name + ".receipt.json")

    if any(not c["pass"] for c in checks):
        candidate.unlink(missing_ok=True)
        receipt = {
            "schema": 1, "status": "failed", "scene": scene_stat,
            "checks": checks, "visual_review": "not_run",
        }
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"DELIVER FAILED — previous artifact preserved: {dst}", file=sys.stderr)
        for c in checks:
            if not c["pass"]:
                print(f"  {c['name']}: {c['detail']}", file=sys.stderr)
        print(f"  receipt: {receipt_path}", file=sys.stderr)
        sys.exit(1)

    artifact_stat = {"sha256": _sha256(candidate), "bytes": candidate.stat().st_size}
    os.replace(candidate, dst)
    receipt = {
        "schema": 1, "status": "delivered",
        "scene": scene_stat, "artifact": artifact_stat,
        "checks": checks, "visual_review": "pending",
    }
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"DELIVERED {dst}")
    print(f"  scene    sha256={scene_stat['sha256']} bytes={scene_stat['bytes']}")
    print(f"  artifact sha256={artifact_stat['sha256']} bytes={artifact_stat['bytes']}")
    print(f"  receipt  {receipt_path}")
    print("  visual_review: pending — the deterministic receipt never includes visual review")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Export .excalidraw to a self-contained SVG via the official engine.")
    ap.add_argument("src", type=Path, help="input .excalidraw")
    ap.add_argument("dst", type=Path, help="output .svg")
    ap.add_argument("--subset", type=Path, default=None, help="Xiaolai subset woff2 to inject (overrides autodiscovery)")
    ap.add_argument("--no-cjk", action="store_true", help="skip Xiaolai injection even if a subset is discovered")
    ap.add_argument("--png", type=Path, default=None, help="also screenshot the mutated DOM to this PNG (audit loop)")
    ap.add_argument("--deliver", action="store_true",
                    help="atomic verified delivery: checks must pass, target replaced only on success, "
                         "SHA-256 receipt written next to the artifact")
    args = ap.parse_args()

    subset = args.subset
    if subset is None and not args.no_cjk:
        default = args.src.parent / "xiaolai-subset.woff2"
        subset = default if default.exists() else None
    if subset is not None and not subset.exists():
        sys.exit(f"subset not found: {subset} — build one with subset-xiaolai.py or drop it as xiaolai-subset.woff2 next to the scene")
    if args.deliver:
        deliver(args.src, args.dst, subset)
    else:
        export(args.src, args.dst, args.png, subset)


if __name__ == "__main__":
    main()

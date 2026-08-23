"""Convert an SVG file to a native .excalidraw scene — fully offline.

Runs the official excalidraw/svg-to-excalidraw converter inside the same
headless-Chromium setup as the render loop (the converter needs a DOM).

Usage (playwright lives in the references venv):
    cd "$SKILL_DIR/references"
    uv run python ../scripts/svg-to-excalidraw.py input.svg out.excalidraw
"""
from __future__ import annotations

import functools
import http.server
import json
import sys
import threading
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "references"


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: uv run python ../scripts/svg-to-excalidraw.py <input.svg> <out.excalidraw>", file=sys.stderr)
        sys.exit(1)
    in_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    svg_text = in_path.read_text(encoding="utf-8")

    from playwright.sync_api import sync_playwright

    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(REFS))
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/vendor/svg-template.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("window.__ready === true", timeout=30000)
        result = page.evaluate("window.convertSvgText(%s)" % json.dumps(svg_text))
        browser.close()
    httpd.shutdown()

    if not result or not result.get("ok"):
        print(f"ERROR: svg conversion failed: {(result or {}).get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    content = result.get("content") or {}
    elements = content.get("elements")
    if not isinstance(elements, list) or not elements:
        print("ERROR: converter returned no elements (SVG may contain unsupported nodes)", file=sys.stderr)
        sys.exit(1)

    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
        "files": {},
    }
    out_path.write_text(json.dumps(scene, indent=1), encoding="utf-8")
    print(f"wrote {out_path} ({len(elements)} elements)")


if __name__ == "__main__":
    main()

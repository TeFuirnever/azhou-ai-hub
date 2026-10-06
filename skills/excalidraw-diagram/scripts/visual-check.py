#!/usr/bin/env python3
"""Post-delivery visual evidence collector — honest by construction.

Renders the EXACT delivered SVG (never re-renders or modifies it) at standard
widths and writes PNG sidecars plus a JSON receipt bound to the artifact's
SHA-256. The receipt always reports visual_review: "pending" — screenshots are
evidence for inspection, never an automatic polish claim.

Receipt schema 2:

  captured  — status "captured"; each capture carries the SHA-256 of the exact
              PNG sidecar bytes (pixel-hash binding), and visual_review stays
              "pending".
  skipped   — the browser path is unavailable (Playwright import failed or
              Chromium launch was denied). The receipt carries the explicit
              hold "sandbox blocked preview" plus a GUI-free "fallback" block:
              artifact and scene SHA-256 digests, the renderer's own
              scene-envelope validation, and the deterministic geometry audit
              result. That is geometry- and hash-level verification only — it
              never counts as a visual review, and the hold must be copied
              into the delivery receipt instead of a silent skip.
  failed    — capture started but broke; hold "preview capture failed" plus
              the same fallback block.

Exit 0 = all captures written, 1 = capture failure (or artifact missing),
2 = browser path unavailable or invalid invocation.

Usage (needs the skill's uv env with Playwright chromium):

    cd "$SKILL_DIR/references"
    uv run python ../scripts/visual-check.py <artifact.svg> \
        [--scene scene.excalidraw] [--widths 880,1300]

`--artifact` is a spelled-out alias of the positional. Default widths: 880
(Markdown report column) and 1300 (full audit view). Sidecars land next to the
artifact as <stem>.evidence-<width>.png plus <artifact>.visual-check.json.
Review the sidecars yourself (or with a vision model), then record passed /
failed / skipped separately — this script never decides perceptual quality for
you. See references/setup.md, "When the sandbox blocks the browser".
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

SANDBOX_BLOCKED_HOLD = "sandbox blocked preview"
CAPTURE_FAILED_HOLD = "preview capture failed"
RECEIPT_SCHEMA = 2

_SCRIPTS = Path(__file__).resolve().parent
_RENDERER = _SCRIPTS.parent / "references" / "render_excalidraw.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_renderer():
    spec = importlib.util.spec_from_file_location("_azhou_render_excalidraw", _RENDERER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fallback_block(scene: Path | None, artifact_stat: dict) -> dict:
    """GUI-free deterministic verification: byte digests + geometry facts."""
    block: dict = {"artifact": dict(artifact_stat)}
    if scene is None:
        return block
    entry: dict = {}
    if not scene.exists():
        entry["error"] = f"scene not found: {scene}"
        block["scene"] = entry
        return block
    entry["sha256"] = _sha256(scene)
    entry["bytes"] = scene.stat().st_size
    block["scene"] = entry
    if _RENDERER.exists():
        try:
            renderer = _load_renderer()
            data = renderer.load_scene(scene)
            min_x, min_y, max_x, max_y = renderer.scene_extent(
                [e for e in data.get("elements", []) if isinstance(e, dict)]
            )
            entry["elements"] = len(data.get("elements", []))
            entry["extent"] = [min_x, min_y, max_x, max_y]
        except Exception as exc:  # noqa: BLE001 — any validation failure is evidence
            entry["error"] = f"{type(exc).__name__}: {exc}"
    else:
        entry["error"] = f"renderer not found: {_RENDERER}"

    audit = subprocess.run(
        [sys.executable, str(_SCRIPTS / "audit-overlaps.py"), str(scene)],
        capture_output=True, text=True)
    audit_entry: dict = {"exit": audit.returncode}
    match = re.search(r"GEOMETRY ISSUES: (\d+)", audit.stdout)
    audit_entry["issues"] = int(match.group(1)) if match else None
    if audit.returncode != 0 and match is None:
        audit_entry["detail"] = (audit.stderr or audit.stdout).strip().splitlines()[-1:]
    block["geometry_audit"] = audit_entry
    return block


def _write_receipt(path: Path, receipt: dict) -> None:
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect honest visual evidence for a delivered SVG.")
    ap.add_argument("artifact", type=Path, nargs="?", default=None)
    ap.add_argument("--artifact", type=Path, dest="artifact_opt", default=None,
                    help="spelled-out alias of the positional artifact")
    ap.add_argument("--scene", type=Path, default=None,
                    help="source .excalidraw scene; binds digests and geometry facts to the receipt")
    ap.add_argument("--widths", default="880,1300", help="comma-separated CSS pixel widths (default 880,1300)")
    args = ap.parse_args()

    svg = args.artifact or args.artifact_opt
    if svg is None:
        ap.error("an artifact SVG is required (positional or --artifact)")
    try:
        widths = [int(w) for w in args.widths.split(",")]
    except ValueError:
        ap.error(f"--widths must be comma-separated integers: {args.widths!r}")
    if not svg.exists():
        print(f"RED artifact not found: {svg}", file=sys.stderr)
        return 1
    art_stat = {"sha256": _sha256(svg), "bytes": svg.stat().st_size}
    receipt_path = svg.with_name(svg.name + ".visual-check.json")
    sidecar_for = lambda w: svg.with_name(f"{svg.stem}.evidence-{w}.png")

    def stale_cleanup():
        for w in widths:
            sidecar_for(w).unlink(missing_ok=True)

    def unavailable(reason: str, status: str, hold: str) -> int:
        stale_cleanup()
        _write_receipt(receipt_path, {
            "schema": RECEIPT_SCHEMA, "artifact": art_stat, "status": status,
            "reason": reason, "holds": [hold],
            "fallback": _fallback_block(args.scene, art_stat),
            "visual_review": "pending",
        })
        print(f"{status.upper()} — {reason} (receipt: {status}; holds: {hold})", file=sys.stderr)
        return 2 if status == "skipped" else 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return unavailable(f"playwright unavailable: {exc}", "skipped", SANDBOX_BLOCKED_HOLD)

    captures = []
    ok = True
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            return unavailable(f"chromium launch failed: {e}", "skipped", SANDBOX_BLOCKED_HOLD)
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
                captures.append({"width": w, "file": sidecar.name,
                                 "bytes": sidecar.stat().st_size,
                                 "sha256": _sha256(sidecar)})
                if sidecar.stat().st_size < 500:
                    ok = False
        except Exception as e:
            return unavailable(str(e), "failed", CAPTURE_FAILED_HOLD)
        finally:
            browser.close()

    receipt = {
        "schema": RECEIPT_SCHEMA, "artifact": art_stat, "status": "captured",
        "widths": widths, "captures": captures, "visual_review": "pending",
    }
    if args.scene is not None and args.scene.exists():
        receipt["scene_sha256"] = _sha256(args.scene)
    _write_receipt(receipt_path, receipt)
    print(f"CAPTURED {len(captures)} sidecar(s) next to {svg.name}; receipt {receipt_path.name}")
    print('visual_review: pending — inspect the sidecars, then record passed/failed/skipped yourself')
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

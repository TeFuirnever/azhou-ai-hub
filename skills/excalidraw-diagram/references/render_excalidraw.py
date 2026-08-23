#!/usr/bin/env python3
"""Render a local Excalidraw scene through the vendored official exporter."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import math
from pathlib import Path
import sys
import threading
from typing import Iterator


class RenderError(RuntimeError):
    """A scene or local rendering dependency cannot produce a trustworthy image."""


def load_scene(scene_path: Path) -> dict:
    """Read a scene and reject envelope errors before a browser starts."""
    try:
        value = json.loads(scene_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RenderError(f"cannot read scene: {scene_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RenderError(f"scene is not valid JSON: {scene_path}: {exc}") from exc

    if not isinstance(value, dict):
        raise RenderError("scene root must be a JSON object")
    if value.get("type") != "excalidraw":
        raise RenderError("scene type must be 'excalidraw'")

    elements = value.get("elements")
    if not isinstance(elements, list):
        raise RenderError("scene elements must be an array")
    if not any(isinstance(item, dict) and not item.get("isDeleted") for item in elements):
        raise RenderError("scene has no visible elements")
    return value


def _finite_number(value: object, fallback: float = 0.0) -> float:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return fallback


def scene_extent(elements: list[dict]) -> tuple[float, float, float, float]:
    """Return the visible coordinate envelope, including line and arrow points."""
    positions: list[tuple[float, float]] = []
    for element in elements:
        if not isinstance(element, dict) or element.get("isDeleted"):
            continue
        origin_x = _finite_number(element.get("x"))
        origin_y = _finite_number(element.get("y"))
        points = element.get("points")
        if element.get("type") in {"arrow", "line", "draw"} and isinstance(points, list):
            for point in points:
                if isinstance(point, list) and len(point) >= 2:
                    positions.append(
                        (origin_x + _finite_number(point[0]), origin_y + _finite_number(point[1]))
                    )
            continue

        width = abs(_finite_number(element.get("width")))
        height = abs(_finite_number(element.get("height")))
        positions.extend(((origin_x, origin_y), (origin_x + width, origin_y + height)))

    if not positions:
        return (0.0, 0.0, 800.0, 600.0)
    xs, ys = zip(*positions)
    return (min(xs), min(ys), max(xs), max(ys))


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


@contextlib.contextmanager
def local_asset_server(directory: Path) -> Iterator[str]:
    """Expose ES modules on loopback for the lifetime of one render."""
    handler = functools.partial(_SilentHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/render_template.html"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def viewport_for(scene: dict, width_limit: int) -> tuple[int, int]:
    left, top, right, bottom = scene_extent(scene["elements"])
    padding = 160
    natural_width = max(320, math.ceil(right - left) + padding)
    natural_height = max(320, math.ceil(bottom - top) + padding)
    return (min(natural_width, width_limit), natural_height)


def render_scene(
    scene_path: Path,
    output_path: Path | None = None,
    *,
    scale: int = 2,
    width_limit: int = 1920,
) -> Path:
    """Create a PNG from one scene and return its absolute output path."""
    if scale < 1 or scale > 4:
        raise RenderError("scale must be between 1 and 4")
    if width_limit < 320:
        raise RenderError("width limit must be at least 320 pixels")

    scene_path = scene_path.resolve()
    scene = load_scene(scene_path)
    destination = (output_path or scene_path.with_suffix(".png")).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    reference_dir = Path(__file__).resolve().parent
    html_path = reference_dir / "render_template.html"
    engine_path = reference_dir / "vendor" / "excalidraw-all.esm.js"
    if not html_path.is_file() or not engine_path.is_file():
        raise RenderError("renderer template or vendored Excalidraw engine is missing")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError(
            "Playwright is not installed; run 'uv sync --frozen' in the references directory"
        ) from exc

    viewport_width, viewport_height = viewport_for(scene, width_limit)
    try:
        with local_asset_server(reference_dir) as renderer_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": viewport_width, "height": viewport_height},
                    device_scale_factor=scale,
                )
                page.goto(renderer_url, wait_until="domcontentloaded")
                page.wait_for_function("window.rendererReady === true", timeout=30_000)
                result = page.evaluate("scene => window.drawScene(scene)", scene)
                if not isinstance(result, dict) or result.get("ok") is not True:
                    detail = result.get("message", "renderer returned no detail") if isinstance(result, dict) else "renderer returned an invalid result"
                    raise RenderError(f"official exporter failed: {detail}")
                page.locator("#canvas svg").screenshot(path=str(destination))
            finally:
                browser.close()
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" in message:
            raise RenderError(
                "Playwright Chromium is missing; run 'uv run playwright install chromium'"
            ) from exc
        raise RenderError(f"browser render failed: {message}") from exc

    return destination


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render editable Excalidraw JSON to PNG")
    parser.add_argument("scene", type=Path, help="input .excalidraw file")
    parser.add_argument("-o", "--output", type=Path, help="destination PNG")
    parser.add_argument("--scale", type=int, default=2, help="device pixel ratio: 1-4")
    parser.add_argument("--width", type=int, default=1920, help="maximum viewport width")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.scene.is_file():
        print(f"render error: scene not found: {args.scene}", file=sys.stderr)
        return 2
    try:
        result = render_scene(
            args.scene,
            args.output,
            scale=args.scale,
            width_limit=args.width,
        )
    except RenderError as exc:
        print(f"render error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

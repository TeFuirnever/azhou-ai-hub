from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "skills" / "excalidraw-diagram" / "references" / "render_excalidraw.py"
SPEC = importlib.util.spec_from_file_location("azhou_render_excalidraw", RENDERER)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExcalidrawRendererTest(unittest.TestCase):
    def test_scene_extent_includes_relative_arrow_points(self) -> None:
        extent = MODULE.scene_extent(
            [
                {"type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50},
                {"type": "arrow", "x": 110, "y": 45, "points": [[0, 0], [90, 30]]},
            ]
        )
        self.assertEqual((10.0, 20.0, 200.0, 75.0), extent)

    def test_load_scene_requires_visible_elements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.excalidraw"
            path.write_text(
                json.dumps({"type": "excalidraw", "elements": [{"isDeleted": True}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MODULE.RenderError, "no visible elements"):
                MODULE.load_scene(path)

    def test_viewport_caps_width_but_keeps_content_height(self) -> None:
        scene = {
            "elements": [
                {"type": "rectangle", "x": 0, "y": 0, "width": 4000, "height": 1200}
            ]
        }
        self.assertEqual((1000, 1360), MODULE.viewport_for(scene, 1000))


if __name__ == "__main__":
    unittest.main()

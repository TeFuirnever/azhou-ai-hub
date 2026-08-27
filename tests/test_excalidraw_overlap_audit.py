"""CLI tests for audit-overlaps.py."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/excalidraw-diagram/scripts/audit-overlaps.py"


def put(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def overlapping_scene():
    return {"elements": [
        {"id": "a", "type": "text", "x": 0, "y": 0, "width": 12, "height": 7, "text": "Alpha"},
        {"id": "b", "type": "text", "x": 0, "y": 0, "width": 12, "height": 7, "text": "Beta"},
    ]}


class AuditCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def test_detect_clean_writes_record_sidecar_and_empty_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; output = root / "detector.json"
            put(scene, {"elements": []})
            result = self.run_cli("detect", "--scene", scene, "--output", output)
            self.assertEqual(result.returncode, 0); self.assertEqual(result.stdout, ""); self.assertEqual(result.stderr, "")
            record = json.loads(output.read_text())
            self.assertEqual(record["state"], "clean")
            self.assertEqual(record["scene_digest"], hashlib.sha256(b'{"elements":[]}').hexdigest())
            self.assertEqual(output.with_name(output.name + ".sha256").read_text(), hashlib.sha256(output.read_bytes()).hexdigest() + "\n")

    def test_detect_issues_returns_one_and_has_sorted_subject_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; output = root / "detector.json"
            put(scene, overlapping_scene())
            result = self.run_cli("detect", "--scene", scene, "--output", output)
            self.assertEqual(result.returncode, 1); self.assertEqual(result.stdout, ""); self.assertEqual(result.stderr, "")
            record = json.loads(output.read_text())
            self.assertEqual(record["state"], "issues"); self.assertEqual(record["issues"][0]["subject_ids"], ["a", "b"])

    def test_invalid_json_is_contract_error_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; output = root / "detector.json"
            scene.write_text("{not json")
            result = self.run_cli("detect", "--scene", scene, "--output", output)
            self.assertEqual(result.returncode, 2); self.assertTrue(result.stderr.startswith("E_SCHEMA:")); self.assertFalse(output.exists())

    def test_existing_output_is_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; output = root / "detector.json"
            put(scene, {"elements": []}); output.write_text("sentinel")
            self.assertEqual(self.run_cli("detect", "--scene", scene, "--output", output).returncode, 2)
            self.assertEqual(output.read_text(), "sentinel")

    def test_legacy_clean_has_stable_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scene.json"; put(scene, {"elements": []})
            result = self.run_cli(scene)
            self.assertEqual(result.returncode, 0); self.assertEqual(result.stdout, "GEOMETRY ISSUES: 0\n"); self.assertEqual(result.stderr, "")

    def test_legacy_issue_has_fix_hint_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scene.json"; put(scene, overlapping_scene())
            result = self.run_cli(scene)
            self.assertEqual(result.returncode, 1); self.assertIn("TEXT-TEXT:", result.stdout); self.assertIn("GEOMETRY ISSUES: 1", result.stdout)

    def test_legacy_label_uses_actual_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scene.json"
            put(scene, {"elements": [
                {"id": "rect", "type": "rectangle", "x": 0, "y": 0, "width": 20, "height": 20,
                 "boundElements": [{"id": "label", "type": "text"}]},
                {"id": "label", "type": "text", "x": 1, "y": 1, "width": 2, "height": 2,
                 "text": "First\nSecond"},
                {"id": "other", "type": "text", "x": -1, "y": 5, "width": 10, "height": 2,
                 "text": "outside"},
            ]})
            result = self.run_cli(scene)
            self.assertEqual(result.returncode, 1)
            self.assertIn("STRADDLE: [First]", result.stdout)

    def test_legacy_straddle_exempts_shared_group_and_icon_prefix(self):
        cases = [
            (
                "shared-group",
                {"id": "rect", "groupIds": ["icon"]},
                {"id": "text", "groupIds": ["icon"]},
            ),
            (
                "shared-icon-prefix",
                {"id": "icon_1_rect"},
                {"id": "icon_1_text"},
            ),
        ]
        for name, rectangle_identity, text_identity in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                scene = Path(tmp) / "scene.json"
                rectangle = {
                    "type": "rectangle", "x": 0, "y": 0, "width": 20, "height": 20,
                    **rectangle_identity,
                }
                text = {
                    "type": "text", "x": -1, "y": 5, "width": 10, "height": 2,
                    "text": "label", **text_identity,
                }
                put(scene, {"elements": [rectangle, text]})
                result = self.run_cli(scene)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "GEOMETRY ISSUES: 0\n")

    def test_margin_changes_issue_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; first = root / "first.json"; second = root / "second.json"
            put(scene, {"elements": [{"id": "r", "type": "rectangle", "x": 0, "y": 0, "width": 20, "height": 20}, {"id": "e", "type": "text", "x": -1, "y": 5, "width": 10, "height": 2}]})
            self.assertEqual(self.run_cli("detect", "--scene", scene, "--margin", 1, "--output", first).returncode, 1)
            self.assertEqual(self.run_cli("detect", "--scene", scene, "--margin", 3, "--output", second).returncode, 1)
            self.assertNotEqual(json.loads(first.read_text())["issues"][0]["evidence"], json.loads(second.read_text())["issues"][0]["evidence"])

    def test_nan_scene_returns_contract_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"
            put(scene, {"elements": [{"id": "a", "type": "text", "x": float("nan"), "y": 0, "width": 1, "height": 1}]})
            result = self.run_cli("detect", "--scene", scene, "--output", root / "out.json")
            self.assertEqual(result.returncode, 2); self.assertTrue(result.stderr.startswith("E_NONFINITE")); self.assertNotIn("Traceback", result.stderr)

    def test_output_without_json_suffix_is_sidecar_name_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); scene = root / "scene.json"; put(scene, {"elements": []})
            result = self.run_cli("detect", "--scene", scene, "--output", root / "out")
            self.assertEqual(result.returncode, 2); self.assertTrue(result.stderr.startswith("E_SIDECAR_NAME"))


if __name__ == "__main__":
    unittest.main()

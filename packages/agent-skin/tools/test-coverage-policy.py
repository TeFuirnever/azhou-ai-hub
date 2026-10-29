#!/usr/bin/env python3
"""Behavior checks for full-scope coverage accounting and the 95% gate."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("unit_coverage_gate", Path(__file__).with_name("test-unit-coverage.py"))
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class CoveragePolicyTests(unittest.TestCase):
    def test_scope_discovers_unlisted_production_and_excludes_only_test_material(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["animation.js", "Native/Player.swift", "Native/PlayerTests.swift",
                         "tools/new-production.py", "tools/test-production-new.py", "tools/build.sh",
                         "tools/a.test.mjs", ".build/old.js", "预览.command"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source\n", encoding="utf-8")
            self.assertEqual(gate.production_sources(root), {
                "javascript": ["animation.js"], "python": ["tools/new-production.py"],
                "swift": ["Native/Player.swift"], "shell": ["tools/build.sh", "预览.command"],
            })

    def test_exactly_95_passes_and_rounded_95_does_not_pass(self):
        scope = {"python": ["a.py"]}
        self.assertTrue(gate.evaluate(scope, {"python": {"a.py": {"count": 100, "covered": 95}}})["passed"])
        result = gate.evaluate(scope, {"python": {"a.py": {"count": 10001, "covered": 9500}}})
        self.assertFalse(result["passed"])

    def test_generated_production_scripts_are_required_even_if_no_unit_executes_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Native").mkdir()
            (root / "Native/Wallpaper.swift").write_text("production script producer\n")
            scope = gate.production_sources(root)
            self.assertEqual(set(scope["javascript"]), set(gate.GENERATED_JAVASCRIPT))
            result = gate.evaluate({"javascript": scope["javascript"]}, {"javascript": {}})
            self.assertFalse(result["passed"])
        source = ".build/unit-generated-sources/Native-Wallpaper.statusSource.js"
        self.assertEqual(gate.canonical_source(source), "generated/Native-Wallpaper.statusSource.js")
        self.assertIsNone(gate.canonical_source(".build/unit-generated-sources/arbitrary-test.js"))

    def test_missing_production_file_fails_instead_of_disappearing_from_denominator(self):
        result = gate.evaluate({"swift": ["App.swift", "Registry.swift"]}, {
            "swift": {"App.swift": {"count": 100, "covered": 100}},
        })
        self.assertFalse(result["passed"])
        self.assertIsNone(result["percent"])
        self.assertEqual(result["languages"]["swift"]["files"]["Registry.swift"]["status"], "missing")

    def test_high_js_coverage_cannot_mask_low_native_coverage(self):
        result = gate.evaluate({"javascript": ["a.js"], "swift": ["App.swift"]}, {
            "javascript": {"a.js": {"count": 10000, "covered": 10000}},
            "swift": {"App.swift": {"count": 100, "covered": 90}},
        })
        self.assertGreater(result["percent"], 95)
        self.assertFalse(result["passed"])

    def test_non_integer_negative_and_impossible_counters_are_rejected(self):
        for count, covered in [(0, 0), (10, 11), (10, -1), (True, 1), (10, True), (1.5, 1)]:
            with self.subTest(count=count, covered=covered), self.assertRaises(ValueError):
                gate.evaluate({"python": ["a.py"]}, {"python": {"a.py": {"count": count, "covered": covered}}})

    def test_lcov_counts_each_source_line_once_and_ignores_test_file_totals(self):
        data = gate.parse_lcov("SF:animation.js\nDA:1,2\nDA:2,0\nDA:1,7\nend_of_record\n")
        self.assertEqual(data["animation.js"], {"count": 2, "covered": 1})
        result = gate.evaluate({"javascript": ["animation.js"]}, {"javascript": {
            **data, "tools/test.js": {"count": 100000, "covered": 100000},
        }})
        self.assertEqual(result["percent"], 50)

    def test_lcov_rejects_duplicate_records_and_outside_sources_never_match_scope(self):
        with self.assertRaises(ValueError):
            gate.parse_lcov("SF:animation.js\nDA:1,1\nend_of_record\n" * 2)
        self.assertEqual(gate.parse_lcov("SF:/outside/animation.js\nDA:1,1\nend_of_record\n"), {})

    def test_normalizers_preserve_engine_executable_line_counts(self):
        self.assertEqual(gate.canonical_source("packages/agent-skin/tools/install-macos.py"), "tools/install-macos.py")
        self.assertEqual(gate.parse_python({"files": {"tools/install-macos.py": {
            "summary": {"num_statements": 20, "covered_lines": 19}}}}), {
                "tools/install-macos.py": {"count": 20, "covered": 19}})
        native = {"data": [{"files": [{"filename": str(gate.ROOT / "Native/App.swift"),
                   "summary": {"lines": {"count": 100, "covered": 95}}}]}]}
        self.assertEqual(gate.parse_native(native), {"Native/App.swift": {"count": 100, "covered": 95}})
        with self.assertRaises(ValueError):
            gate.parse_native({"data": native["data"] * 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)

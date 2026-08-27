"""Strict tests for overlap canonicalization, detector records, and transitions."""
import hashlib
import importlib.util
import math
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/excalidraw-diagram/scripts/overlap_contract.py"
spec = importlib.util.spec_from_file_location("overlap_contract", SCRIPT)
oc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(oc)


def scene(*elements):
    return {"elements": list(elements)}


def box(element_id, kind, x, y, width, height, **extra):
    return {"id": element_id, "type": kind, "x": x, "y": y,
            "width": width, "height": height, **extra}


def issue_scene():
    return scene(box("a", "text", 0, 0, 12, 7), box("b", "text", 0, 0, 12, 7))


def detector(state="clean", scene_digest=None, issues=None):
    return {"record_type": "detector", "schema_version": oc.AUDIT_VERSION,
            "state": state, "scene_digest": "a" * 64 if scene_digest is None else scene_digest,
            "issues": [] if issues is None else issues}


class CanonicalEncodingTests(unittest.TestCase):
    def test_canonical_json_is_sorted_compact_utf8_without_newline(self):
        raw = oc.canonical_bytes({"z": ["中", 1], "a": {"b": 2, "a": 1}})
        self.assertEqual(raw, '{"a":{"a":1,"b":2},"z":["中",1]}'.encode())
        self.assertFalse(raw.endswith(b"\n"))
        self.assertEqual(oc.digest({"b": 1, "a": 2}), hashlib.sha256(b'{"a":2,"b":1}').hexdigest())

    def test_canonical_json_rejects_nan_and_infinity_at_every_depth(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            for payload in (value, [value], {"v": value}, {"n": [{"v": value}]}):
                with self.subTest(payload=repr(payload)):
                    with self.assertRaisesRegex(oc.ContractError, "E_NONFINITE"):
                        oc.canonical_bytes(payload)

    def test_half_even_quantization_handles_ties(self):
        self.assertEqual(oc._q("1.2345"), 1234)
        self.assertEqual(oc._q("1.2355"), 1236)
        self.assertEqual(oc._q(Decimal("-1.2345")), -1234)

    def test_quantization_stores_integer_millipixels_and_normalizes_negative_zero(self):
        self.assertEqual(oc._q("12"), 12000)
        self.assertEqual(oc._q("0.001"), 1)
        for value in ("-0", "-0.0004", "-0.0005"):
            with self.subTest(value=value):
                self.assertEqual(oc._q(value), 0)


class SidecarTests(unittest.TestCase):
    def test_sidecar_name_rejects_non_json_and_sidecar_suffix(self):
        for path in (Path("record.txt"), Path("record.json.sha256")):
            with self.subTest(path=path):
                with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_NAME"):
                    oc.sidecar_for(path)

    def test_sidecar_missing_format_and_mismatch_have_exact_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "record.json"
            record.write_bytes(b"{}")
            with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_MISSING"):
                oc.read_sidecar(record)
            sidecar = Path(str(record) + ".sha256")
            sidecar.write_text("bad")
            with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_FORMAT"):
                oc.read_sidecar(record)
            sidecar.write_text("0" * 64 + "\n")
            with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_MISMATCH"):
                oc.verify_sidecar(record)

    def test_sidecar_duplicate_and_name_errors_do_not_change_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = root / "record.json"
            record.write_text("original")
            with self.assertRaisesRegex(oc.ContractError, "E_OUTPUT_EXISTS"):
                oc.write_atomic(record, {"new": True})
            self.assertEqual(record.read_text(), "original")
            sidecar = Path(str(record) + ".sha256")
            sidecar.write_text("0" * 64 + "\n")
            with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_DUPLICATE"):
                oc.write_atomic(record, {"new": True})
            with self.assertRaisesRegex(oc.ContractError, "E_SIDECAR_NAME"):
                oc.write_atomic(root / "record", {})

    def test_second_install_failure_leaves_no_half_pair_or_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = root / "record.json"
            real_link = oc.os.link
            calls = 0

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("second install")
                return real_link(source, target)

            with mock.patch.object(oc.os, "link", side_effect=fail_second):
                with self.assertRaisesRegex(oc.ContractError, "E_IO"):
                    oc.write_atomic(record, {"value": 1})
            self.assertFalse(record.exists())
            self.assertFalse(Path(str(record) + ".sha256").exists())
            self.assertEqual(list(root.iterdir()), [])


class DetectorFormulaTests(unittest.TestCase):
    def test_text_text_formula_returns_exact_12_by_7_severity(self):
        result = oc.detect_scene(issue_scene())
        self.assertEqual(result["state"], "issues")
        self.assertEqual(result["issues"][0]["code"], "TEXT_TEXT")
        self.assertEqual(result["issues"][0]["evidence"], {"overlap_x": 12000, "overlap_y": 7000})
        self.assertEqual(result["issues"][0]["severity"], 5000)

    def test_text_text_two_pixel_boundary_is_clean_and_three_pixel_is_one_pixel(self):
        self.assertEqual(oc.detect_scene(scene(box("a", "text", 0, 0, 2, 4), box("b", "text", 0, 0, 2, 4)))["state"], "clean")
        result = oc.detect_scene(scene(box("a", "text", 0, 0, 3, 4), box("b", "text", 0, 0, 3, 4)))
        self.assertEqual(result["issues"][0]["severity"], 1000)

    def test_nesting_roles_and_four_overflow_costs_are_exact(self):
        result = oc.detect_scene(scene(box("child", "rectangle", -2, -3, 15, 16), box("parent", "rectangle", 0, 0, 10, 10)))
        issue = next(i for i in result["issues"] if i["code"] == "NESTING")
        self.assertEqual(issue["subject_ids"], ["child", "parent"])
        self.assertEqual(issue["evidence"], {"left": 1000, "top": 2000, "right": 3000, "bottom": 3000, "inside": 9000, "outside": 7000})
        self.assertEqual(issue["severity"], 7000)

    def test_nesting_tolerance_and_equal_bounds_are_clean(self):
        parent = box("parent", "rectangle", 0, 0, 10, 10)
        child = box("child", "rectangle", 1, 1, 8, 8)
        equal = box("child", "rectangle", 0, 0, 10, 10)
        tolerance_issue = [i for i in oc.detect_scene(scene(child, parent))["issues"] if i["code"] == "NESTING"]
        self.assertEqual(len(tolerance_issue), 1)
        self.assertEqual(tolerance_issue[0]["severity"], 0)
        self.assertEqual([i for i in oc.detect_scene(scene(equal, parent))["issues"] if i["code"] == "NESTING"], [])

    def test_bounds_use_rotated_visual_bounds_and_half_even_quantization(self):
        bounds = oc._bounds(box("rotated", "rectangle", 0, 0, 2, 4, angle=math.pi / 2))
        self.assertEqual(bounds, (-1000, 1000, 3000, 3000))

    def test_bounds_use_points_visual_bounds(self):
        element = box("arrow", "arrow", 10, 20, 1, 1, points=[[0, 0], [5, 7], [-2, 3]])
        self.assertEqual(oc._bounds(element), (8000, 20000, 15000, 27000))

    def test_straddle_inside_margin_and_outside_cost_are_exact(self):
        result = oc.detect_scene(scene(box("r", "rectangle", 0, 0, 20, 20), box("e", "text", -1, 5, 10, 2)), margin=3)
        issue = next(i for i in result["issues"] if i["code"] == "STRADDLE")
        self.assertEqual(issue["subject_ids"], ["r", "e"])
        self.assertEqual(issue["evidence"]["dx_inside"], [4000, 8000])
        self.assertEqual(issue["evidence"]["dy_inside"], [-2000, 10000])
        self.assertEqual(issue["evidence"]["inside"], 4000)
        self.assertEqual(issue["evidence"]["outside"], 7000)
        self.assertEqual(issue["severity"], 4000)

    def test_straddle_four_outside_directions_have_finite_evidence(self):
        cases = {"left": box("e", "text", -1, 4, 4, 2), "right": box("e", "text", 7, 4, 4, 2), "top": box("e", "text", 4, -1, 2, 4), "bottom": box("e", "text", 4, 7, 2, 4)}
        for direction, element in cases.items():
            with self.subTest(direction=direction):
                result = oc.detect_scene(scene(box("r", "rectangle", 0, 0, 10, 10), element), margin=1)
                self.assertEqual(result["state"], "issues")
                evidence = result["issues"][0]["evidence"]
                self.assertTrue(all(math.isfinite(value / 1000) for value in evidence["dx_inside"] + evidence["dy_inside"]))

    def test_roles_identity_evidence_digests_and_sorted_issue_order_are_exact(self):
        result = oc.detect_scene(scene(box("z", "text", 0, 0, 12, 7), box("a", "text", 0, 0, 12, 7)))
        issue = result["issues"][0]
        self.assertEqual(issue["subject_ids"], ["a", "z"])
        self.assertEqual(issue["issue_key"], "TEXT_TEXT:a:z")
        self.assertEqual(issue["identity_digest"], oc.digest({"code": "TEXT_TEXT", "subject_ids": ["a", "z"]}))
        self.assertEqual(issue["evidence_digest"], oc.digest(issue["evidence"]))

    def test_detector_clean_and_error_branches_are_closed(self):
        for state in ("clean", "error"):
            record = detector(state)
            self.assertTrue(oc.validate_record(record))
            record["issues"] = [{"invalid": True}]
            with self.assertRaisesRegex(oc.ContractError, "E_SCHEMA"):
                oc.validate_record(record)

    def test_duplicate_identity_and_unsorted_text_role_are_rejected(self):
        issue = oc.detect_scene(issue_scene())["issues"][0]
        with self.assertRaisesRegex(oc.ContractError, "E_INVALID_ROLE"):
            oc.validate_record(detector("issues", issues=[issue, dict(issue)]))
        invalid = dict(issue, subject_ids=["z", "a"], issue_key="TEXT_TEXT:z:a", identity_digest=oc.digest({"code": "TEXT_TEXT", "subject_ids": ["z", "a"]}))
        with self.assertRaisesRegex(oc.ContractError, "E_INVALID_ROLE"):
            oc.validate_record(detector("issues", issues=[invalid]))


class ParetoAndDecisionTests(unittest.TestCase):
    def test_pareto_removal_addition_and_improvement_are_distinct(self):
        old = {"issues": [{"issue_key": "A", "severity": 4}]}
        self.assertEqual(oc.pareto(old, {"issues": []}), "improved")
        self.assertEqual(oc.pareto({"issues": []}, old), "regressed")
        self.assertEqual(oc.pareto(old, {"issues": [{"issue_key": "A", "severity": 4}, {"issue_key": "B", "severity": 0}]}), "regressed")
        self.assertEqual(oc.pareto(old, {"issues": [{"issue_key": "A", "severity": 3}]}), "improved")

    def test_pareto_improvement_plus_worsening_is_incomparable(self):
        old = {"issues": [{"issue_key": "A", "severity": 4}, {"issue_key": "B", "severity": 1}]}
        new = {"issues": [{"issue_key": "A", "severity": 3}, {"issue_key": "B", "severity": 2}]}
        self.assertEqual(oc.pareto(old, new), "incomparable")

    def test_pareto_digest_only_change_is_unchanged(self):
        old = {"issues": [{"issue_key": "A", "severity": 1}]}
        self.assertEqual(oc.pareto(old, {"issues": [{"issue_key": "A", "severity": 1}]}), "unchanged")

    def test_decision_clean_error_initial_and_attempt_three_have_exact_triples(self):
        clean = oc.decision(detector("clean"))
        error = oc.decision(detector("error"))
        initial = oc.decision(oc.detect_scene(issue_scene()))
        first = oc.detect_scene(issue_scene())
        previous = oc.decision(first)
        previous = dict(previous, attempt=2)
        exhausted_scene = scene(box("a", "text", 0, 1, 12, 7), box("b", "text", 0, 0, 12, 7))
        exhausted = oc.decision(oc.detect_scene(exhausted_scene), 2, 3, True, oc.detect_scene(exhausted_scene)["scene_digest"], first, previous)
        self.assertEqual((clean["decision"], clean["repair_allowed"], clean["progress_relation"]), ("clean", False, "not_compared"))
        self.assertEqual((error["decision"], error["repair_allowed"], error["progress_relation"]), ("error", False, "not_compared"))
        self.assertEqual((initial["decision"], initial["repair_allowed"], initial["progress_relation"]), ("continue", True, "not_compared"))
        self.assertEqual((exhausted["decision"], exhausted["repair_allowed"], exhausted["progress_relation"]), ("exhausted", False, "not_compared"))

    def test_initial_requires_round_one_attempt_zero_no_edit_and_no_refs(self):
        issue = oc.detect_scene(issue_scene())
        cases = (({"round_no": 0}, "E_INVALID_ROUND"), ({"round_no": 5}, "E_INVALID_ROUND"), ({"attempt": 1}, "E_INVALID_ATTEMPT"), ({"edit_applied": True}, "E_INVALID_ROUND"))
        for kwargs, code in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(oc.ContractError, code):
                    oc.decision(issue, **kwargs)

    def test_subsequent_requires_prior_continue_exact_refs_and_edit_scene_change(self):
        first = oc.detect_scene(issue_scene())
        previous = oc.decision(first)
        edited = oc.detect_scene(scene(box("a", "text", 0, 1, 12, 7), box("b", "text", 0, 0, 12, 7)))
        second = oc.decision(edited, 2, 1, True, edited["scene_digest"], first, previous)
        self.assertEqual((second["decision"], second["repair_allowed"], second["progress_relation"]), ("continue", True, "improved"))
        with self.assertRaisesRegex(oc.ContractError, "E_INVALID_TRANSITION"):
            oc.decision(edited, 2, 1, True, edited["scene_digest"], first, dict(previous, decision="stalled", repair_allowed=False, progress_relation="unchanged"))

    def test_subsequent_no_edit_keeps_attempt_and_scene_digest(self):
        first = oc.detect_scene(issue_scene())
        previous = oc.decision(first)
        with self.assertRaisesRegex(oc.ContractError, "E_INVALID_ATTEMPT"):
            oc.decision(first, 2, 1, False, first["scene_digest"], first, previous)


if __name__ == "__main__":
    unittest.main()

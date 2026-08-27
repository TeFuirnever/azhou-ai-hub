"""Receipt build/replay, sealing, and Markdown compatibility tests."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "skills/excalidraw-diagram/scripts"
AUDIT_SCHEMA = ROOT / "skills/excalidraw-diagram/assets/overlap-audit.schema.json"
RECEIPT_SCHEMA = ROOT / "skills/excalidraw-diagram/assets/overlap-receipt.schema.json"
sys.path.insert(0, str(SCRIPTS))
import overlap_contract as c


def assert_schema(value, schema, base):
    """Small dependency-free checker for the draft keywords shipped here."""
    def check(v, s, origin):
        if "$ref" in s:
            ref = s["$ref"]
            if ref.startswith("#/"):
                target = origin
                for part in ref[1:].lstrip("/").split("/"):
                    target = target[part]
                return check(v, target, origin)
            filename, pointer = ref.split("#", 1)
            external = json.loads((AUDIT_SCHEMA.parent / filename).read_text())
            target = external
            for part in pointer[1:].lstrip("/").split("/"):
                target = target[part]
            return check(v, target, external)
        if "allOf" in s and any(not check(v, part, origin) for part in s["allOf"]):
            return False
        if "oneOf" in s and sum(check(v, part, origin) for part in s["oneOf"]) != 1:
            return False
        if "anyOf" in s and not any(check(v, part, origin) for part in s["anyOf"]):
            return False
        typ = s.get("type")
        types = typ if isinstance(typ, list) else [typ] if typ else []
        if types and not any({"object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str), "integer": isinstance(v, int) and not isinstance(v, bool), "boolean": isinstance(v, bool), "null": v is None}.get(t, True) for t in types):
            return False
        if "const" in s and v != s["const"]: return False
        if "enum" in s and v not in s["enum"]: return False
        if "pattern" in s and (not isinstance(v, str) or re.fullmatch(s["pattern"], v) is None): return False
        if "minLength" in s and len(v) < s["minLength"]: return False
        if "minimum" in s and v < s["minimum"]: return False
        if "maximum" in s and v > s["maximum"]: return False
        if isinstance(v, dict):
            if any(k not in s.get("properties", {}) and s.get("additionalProperties") is False for k in v): return False
            if any(k not in v for k in s.get("required", [])): return False
            for k, subschema in s.get("properties", {}).items():
                if k in v and not check(v[k], subschema, origin): return False
        if isinstance(v, list):
            if len(v) < s.get("minItems", 0) or len(v) > s.get("maxItems", 10**9): return False
            if s.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in v}) != len(v): return False
            if "items" in s and any(not check(x, s["items"], origin) for x in v): return False
        return True
    assert check(value, schema, schema), value


class ReceiptFixtureMixin:
    def make_fixture(self, root, issue=False):
        scene = root / "scene.json"
        elements = [] if not issue else [{"id": "a", "type": "text", "x": 0, "y": 0, "width": 12, "height": 7}, {"id": "b", "type": "text", "x": 0, "y": 0, "width": 12, "height": 7}]
        scene.write_text(json.dumps({"elements": elements}))
        detector = root / "detector-1.json"
        decision = root / "decision-1.json"
        self.assertEqual(self.cli("audit-overlaps.py", "detect", "--scene", scene, "--output", detector).returncode, 1 if issue else 0)
        self.assertEqual(self.cli("overlap_repair_decision.py", "decide", "--detector", detector, "--round", 1, "--attempt", 0, "--edit-applied", "false", "--output", decision).returncode, 0)
        gates = root / "gates.json"; visual = root / "visual.json"; dispositions = root / "dispositions.json"
        c.write_atomic(gates, {"record_type": "gates", "schema_version": c.GATES_VERSION, "gates": [], "holds": []})
        c.write_atomic(visual, {"record_type": "visual_review", "schema_version": c.VISUAL_VERSION, "status": "pass", "reviewer": "named"})
        c.write_atomic(dispositions, {"record_type": "dispositions", "schema_version": c.DISPOSITIONS_VERSION, "dispositions": []})
        manifest = root / "manifest.json"
        c.write_atomic(manifest, {"record_type": "chain_manifest", "schema_version": c.CHAIN_VERSION, "rounds": [{"round": 1, "detector_path": str(detector), "decision_path": str(decision), "detector_sidecar": str(detector) + ".sha256", "decision_sidecar": str(decision) + ".sha256"}], "holds": []})
        return manifest, gates, visual, dispositions, detector, decision

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)

    def build(self, root, output=None):
        manifest, gates, visual, dispositions, *_ = self.fixture
        output = root / "receipt.json" if output is None else output
        return self.cli("overlap_receipt.py", "build", "--chain-manifest", manifest, "--gates", gates, "--visual-review", visual, "--dispositions", dispositions, "--output", output)


class SealTests(unittest.TestCase, ReceiptFixtureMixin):
    def test_four_seal_kinds_accept_valid_closed_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, gates, visual, dispositions, *_ = self.make_fixture(root)
            for kind, path in (("chain_manifest", manifest), ("gates", gates), ("visual_review", visual), ("dispositions", dispositions)):
                output = root / (kind + "-sealed.json")
                result = self.cli("overlap_contract.py", "seal", "--kind", kind, "--record", path, "--output", output)
                self.assertEqual(result.returncode, 0, (kind, result.stderr))

    def test_seal_rejects_wrong_version_and_wrong_shape_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, gates, *_ = self.make_fixture(root)
            value = json.loads(gates.read_text()); value["schema_version"] = "wrong"
            bad = root / "bad.json"; c.write_atomic(bad, value)
            output = root / "out.json"
            result = self.cli("overlap_contract.py", "seal", "--kind", "gates", "--record", bad, "--output", output)
            self.assertEqual(result.returncode, 2); self.assertFalse(output.exists())

    def test_seal_rejects_wrong_sidecar_reference_and_wrong_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, *_ = self.make_fixture(root)
            value = json.loads(manifest.read_text()); value["rounds"][0]["detector_sidecar"] = "wrong.sha256"
            bad = root / "bad.json"; c.write_atomic(bad, value)
            result = self.cli("overlap_contract.py", "seal", "--kind", "chain_manifest", "--record", bad, "--output", root / "out.json")
            self.assertEqual(result.returncode, 2)

    def test_seal_rejects_non_string_holds_at_shared_contract_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, gates, *_ = self.make_fixture(root)
            for kind, path in (("chain_manifest", manifest), ("gates", gates)):
                value = json.loads(path.read_text()); value["holds"] = [1]
                bad = root / f"bad-{kind}.json"; c.write_atomic(bad, value)
                result = self.cli("overlap_contract.py", "seal", "--kind", kind, "--record", bad, "--output", root / f"out-{kind}.json")
                self.assertEqual(result.returncode, 2, (kind, result.stderr))


class BuildAndReplayTests(unittest.TestCase, ReceiptFixtureMixin):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, issue=False):
        self.fixture = self.make_fixture(self.root, issue=issue)

    def test_build_complete_receipt_has_exact_embedded_chain_and_final_refs(self):
        self.prepare(False)
        result = self.build(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.root / "receipt.json").read_text())
        self.assertEqual(receipt["schema_version"], c.RECEIPT_VERSION)
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(len(receipt["audit_chain"]), 1)
        tail = receipt["audit_chain"][-1]
        self.assertEqual(receipt["final_detector_digest"], tail["detector"]["digest"])
        self.assertEqual(receipt["final_decision_digest"], tail["decision"]["digest"])
        self.assertNotIn("final_detector", receipt)
        self.assertNotIn("final_decision", receipt)

    def test_validate_receipt_passes_after_all_build_inputs_and_sidecars_are_deleted(self):
        self.prepare(False); self.assertEqual(self.build(self.root).returncode, 0)
        for path in self.root.glob("*.json"):
            if path.name == "receipt.json":
                continue
            path.unlink(); Path(str(path) + ".sha256").unlink(missing_ok=True)
        result = self.cli("overlap_receipt.py", "validate", "--receipt", self.root / "receipt.json")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_output_and_sidecar_are_no_clobber(self):
        self.prepare(False); output = self.root / "receipt.json"; output.write_text("sentinel")
        result = self.build(self.root, output)
        self.assertEqual(result.returncode, 2); self.assertEqual(output.read_text(), "sentinel")

    def test_build_rejects_zero_round_manifest(self):
        self.prepare(False); manifest, *_ = self.fixture
        value = json.loads(manifest.read_text()); value["rounds"] = []
        bad = self.root / "zero.json"; c.write_atomic(bad, value); self.fixture = (bad, *self.fixture[1:])
        self.assertEqual(self.build(self.root).returncode, 2)

    def test_build_rejects_duplicate_round_paths_and_nonconsecutive_rounds(self):
        self.prepare(False); manifest, *_ = self.fixture; value = json.loads(manifest.read_text())
        row = value["rounds"][0]; value["rounds"] = [row, dict(row, round=3)]
        bad = self.root / "bad.json"; c.write_atomic(bad, value); self.fixture = (bad, *self.fixture[1:])
        self.assertEqual(self.build(self.root).returncode, 2)

    def test_failed_terminal_mapping_is_not_reported_as_complete(self):
        self.prepare(True)
        manifest, gates, visual, dispositions, detector, decision = self.fixture
        value = json.loads(visual.read_text()); value["status"] = "fail"; visual.unlink(); Path(str(visual) + ".sha256").unlink(); c.write_atomic(visual, value)
        result = self.build(self.root)
        self.assertEqual(result.returncode, 0)
        receipt = json.loads((self.root / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "failed")

    def test_receipt_validation_rejects_digest_correct_semantic_decision_tamper(self):
        self.prepare(False); self.assertEqual(self.build(self.root).returncode, 0)
        receipt = json.loads((self.root / "receipt.json").read_text())
        projection = receipt["audit_chain"][0]["decision"]["projection"]
        projection["decision"] = "continue"; projection["repair_allowed"] = True
        receipt["audit_chain"][0]["decision"]["digest"] = c.digest(projection)
        tampered = self.root / "tampered.json"; c.write_atomic(tampered, receipt)
        result = self.cli("overlap_receipt.py", "validate", "--receipt", tampered)
        self.assertEqual(result.returncode, 2)

    def test_receipt_validation_rejects_reordered_or_skipped_rounds(self):
        self.prepare(False); self.assertEqual(self.build(self.root).returncode, 0)
        receipt = json.loads((self.root / "receipt.json").read_text())
        receipt["audit_chain"][0]["round"] = 2
        tampered = self.root / "tampered.json"; c.write_atomic(tampered, receipt)
        self.assertEqual(self.cli("overlap_receipt.py", "validate", "--receipt", tampered).returncode, 2)

    def test_build_and_validate_reject_non_string_holds(self):
        self.prepare(False)
        manifest, *_ = self.fixture
        value = json.loads(manifest.read_text()); value["holds"] = [1]
        bad_manifest = self.root / "bad-manifest.json"; c.write_atomic(bad_manifest, value)
        self.fixture = (bad_manifest, *self.fixture[1:])
        self.assertEqual(self.build(self.root).returncode, 2)

        self.tmp.cleanup(); self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.prepare(False)
        self.assertEqual(self.build(self.root).returncode, 0)
        receipt = json.loads((self.root / "receipt.json").read_text()); receipt["holds"] = [1]
        bad_receipt = self.root / "bad-receipt.json"; c.write_atomic(bad_receipt, receipt)
        self.assertEqual(self.cli("overlap_receipt.py", "validate", "--receipt", bad_receipt).returncode, 2)

    def test_generated_detector_decision_and_receipt_validate_against_shipped_schemas(self):
        self.prepare(True)
        self.assertEqual(self.build(self.root).returncode, 0)
        audit = json.loads(AUDIT_SCHEMA.read_text())
        receipt_schema = json.loads(RECEIPT_SCHEMA.read_text())
        assert_schema(json.loads(self.fixture[4].read_text()), audit, AUDIT_SCHEMA)
        assert_schema(json.loads(self.fixture[5].read_text()), audit, AUDIT_SCHEMA)
        assert_schema(json.loads((self.root / "receipt.json").read_text()), receipt_schema, RECEIPT_SCHEMA)

    def test_shipped_receipt_schema_rejects_nested_extra_projection_property(self):
        self.prepare(False)
        self.assertEqual(self.build(self.root).returncode, 0)
        receipt = json.loads((self.root / "receipt.json").read_text())
        receipt["gates"]["projection"]["unexpected"] = True
        with self.assertRaises(AssertionError):
            assert_schema(receipt, json.loads(RECEIPT_SCHEMA.read_text()), RECEIPT_SCHEMA)

    def test_shipped_audit_schema_rejects_wrong_and_extra_evidence(self):
        self.prepare(True)
        detector = json.loads(self.fixture[4].read_text())
        detector["issues"][0]["evidence"]["unexpected"] = 1
        with self.assertRaises(AssertionError):
            assert_schema(detector, json.loads(AUDIT_SCHEMA.read_text()), AUDIT_SCHEMA)
        detector["issues"][0]["evidence"].pop("unexpected")
        detector["issues"][0]["evidence"]["overlap_x"] = -1
        with self.assertRaises(AssertionError):
            assert_schema(detector, json.loads(AUDIT_SCHEMA.read_text()), AUDIT_SCHEMA)


class MarkdownAndIsolationTests(unittest.TestCase, ReceiptFixtureMixin):
    def test_markdown_validates_marker_path_sidecar_sha_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture = self.make_fixture(root); self.assertEqual(self.build(root).returncode, 0)
            receipt = root / "receipt.json"; sha = c.verify_sidecar(receipt); markdown = root / "review.md"
            markdown.write_text(f"Schema: excalidraw-diagram.receipt.v1\nMachine receipt: receipt.json\nMachine sidecar SHA: {sha}\nMachine status: complete\n")
            self.assertEqual(self.cli("overlap_receipt.py", "validate-markdown", "--markdown", markdown, "--receipt", receipt).returncode, 0)
            markdown.write_text(markdown.read_text().replace("complete", "failed"))
            self.assertEqual(self.cli("overlap_receipt.py", "validate-markdown", "--markdown", markdown, "--receipt", receipt).returncode, 2)

    def test_markdown_missing_duplicate_marker_or_receipt_fields_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture = self.make_fixture(root); self.assertEqual(self.build(root).returncode, 0)
            receipt = root / "receipt.json"; markdown = root / "review.md"
            markdown.write_text("Schema: excalidraw-diagram.receipt.v1\n")
            self.assertEqual(self.cli("overlap_receipt.py", "validate-markdown", "--markdown", markdown, "--receipt", receipt).returncode, 2)
            markdown.write_text(("Schema: excalidraw-diagram.receipt.v1\n" * 2) + "Machine receipt: receipt.json\nMachine sidecar SHA: x\nMachine status: complete\n")
            self.assertEqual(self.cli("overlap_receipt.py", "validate-markdown", "--markdown", markdown, "--receipt", receipt).returncode, 2)

    def test_isolated_package_runs_complete_chain_without_root_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root / "excalidraw-diagram"
            shutil.copytree(ROOT / "skills/excalidraw-diagram", package)
            self.assertFalse((package.parent / "scripts").exists())
            scene = root / "scene.json"; scene.write_text(json.dumps({"elements": []}))
            detector = root / "detector.json"; decision = root / "decision.json"
            detect_script = package / "scripts/audit-overlaps.py"
            decide_script = package / "scripts/overlap_repair_decision.py"
            contract_script = package / "scripts/overlap_contract.py"
            receipt_script = package / "scripts/overlap_receipt.py"
            detect = subprocess.run([sys.executable, str(detect_script), "detect", "--scene", scene, "--output", detector], capture_output=True, text=True)
            self.assertEqual(detect.returncode, 0, detect.stderr)
            decide = subprocess.run([sys.executable, str(decide_script), "decide", "--detector", detector, "--round", "1", "--attempt", "0", "--edit-applied", "false", "--output", decision], capture_output=True, text=True)
            self.assertEqual(decide.returncode, 0, decide.stderr)
            gates = root / "gates.raw.json"; visual = root / "visual.raw.json"; dispositions = root / "dispositions.raw.json"
            c.write_atomic(gates, {"record_type": "gates", "schema_version": c.GATES_VERSION, "gates": [], "holds": []})
            c.write_atomic(visual, {"record_type": "visual_review", "schema_version": c.VISUAL_VERSION, "status": "pass", "reviewer": "isolated"})
            c.write_atomic(dispositions, {"record_type": "dispositions", "schema_version": c.DISPOSITIONS_VERSION, "dispositions": []})
            sealed = {}
            for kind, raw in (("gates", gates), ("visual_review", visual), ("dispositions", dispositions)):
                out = root / f"{kind}.json"
                result = subprocess.run([sys.executable, str(contract_script), "seal", "--kind", kind, "--record", raw, "--output", out], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr); sealed[kind] = out
            manifest_raw = root / "manifest.raw.json"
            c.write_atomic(manifest_raw, {"record_type": "chain_manifest", "schema_version": c.CHAIN_VERSION, "rounds": [{"round": 1, "detector_path": str(detector), "decision_path": str(decision), "detector_sidecar": str(detector) + ".sha256", "decision_sidecar": str(decision) + ".sha256"}], "holds": []})
            manifest = root / "chain_manifest.json"
            result = subprocess.run([sys.executable, str(contract_script), "seal", "--kind", "chain_manifest", "--record", manifest_raw, "--output", manifest], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = root / "receipt.json"
            result = subprocess.run([sys.executable, str(receipt_script), "build", "--chain-manifest", manifest, "--gates", sealed["gates"], "--visual-review", sealed["visual_review"], "--dispositions", sealed["dispositions"], "--output", receipt], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(receipt.read_text())["status"], "complete")
            for path in (detector, decision, manifest, sealed["gates"], sealed["visual_review"], sealed["dispositions"]):
                path.unlink(); Path(str(path) + ".sha256").unlink()
            result = subprocess.run([sys.executable, str(receipt_script), "validate", "--receipt", receipt], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            sha = c.verify_sidecar(receipt); markdown = root / "review.md"
            markdown.write_text(f"Schema: excalidraw-diagram.receipt.v1\nMachine receipt: receipt.json\nMachine sidecar SHA: {sha}\nMachine status: complete\n")
            result = subprocess.run([sys.executable, str(receipt_script), "validate-markdown", "--markdown", markdown, "--receipt", receipt], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

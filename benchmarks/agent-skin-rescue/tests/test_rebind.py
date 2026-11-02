"""Portable source-copy seams; no host or private material needed."""
from pathlib import Path
import os
import importlib.util
import sys
import unittest
import tempfile
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "packages/agent-skin"
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "rebind"))
from source_patch import patch_sources

class SourcePatchTests(unittest.TestCase):
    def inputs(self):
        names = ["tools/build-startup.py", "extension/bootstrap.mjs", "extension/renderer.mjs", "tools/verify-artifacts.py", "hub-package.json"]
        return {name: (SOURCE/name).read_text() for name in names}

    def test_default_keeps_formal_adapter_and_explicit_diagnostic_default(self):
        original = self.inputs()
        patched = patch_sources(original, (HERE/"rebind/r10-diagnostics.mjs").read_text())
        self.assertIn("pageAdapter, diagnostics = null", patched["extension/renderer.mjs"])
        self.assertIn("return installStartup(installAnimation, host, pageAdapter);", patched["extension/bootstrap.mjs"])
        self.assertIn("r10_diagnostics: bool = False", patched["tools/build-startup.py"])
        self.assertEqual(original, self.inputs())

    def test_missing_boundary_fails_closed(self):
        original=self.inputs()
        original["extension/renderer.mjs"]="// incompatible source"
        with self.assertRaisesRegex(ValueError,"boundary drift"):
            patch_sources(original,"export function createR10Diagnostics() {}")

class BindingTests(unittest.TestCase):
    def fixture(self, root):
        def item(name, data):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
            return {"path":name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
        payload=item("build/payload.js","synthetic fixture only")
        manifest=item("build/manifest.json","{}")
        wrapper=item("build/mount.js","synthetic wrapper")
        source=item("build/source/input.js","fixed input")
        binding={"kind":"A","scope":"synthetic unit fixture", "source_commit":"8eec664611c2f679be6714bd888a07d764459c8a", "inputs":[source],"source_stage":"build/source","source_inputs":{"input.js":source["sha256"]},"base_payload":payload,"startup_manifest":manifest,"wrappers":{"mount":dict(wrapper,config={"owner":"fixture"}),"clean":wrapper},"command_count":0,"commands":[]}
        bp=root/"build/binding.json";bp.write_text(json.dumps(binding))
        producer={"argv":["synthetic-fixture"],"observed_at":"2026-11-01T00:00:00Z","signal":None,"kind":"C","execution_state":"exited","exit_code":0,"error":None,"inputs_unchanged":True,"argument_inputs_unchanged":True,"evidence_errors":[],"evidence_complete":True,"inputs":[],"argument_inputs":[],"outputs":{"raw_files":[]},"artifacts":[{"source_path":"build/binding.json","relation":"produced","source_sha256":hashlib.sha256(bp.read_bytes()).hexdigest()}]}
        pp=root/"producer.json";pp.write_text(json.dumps(producer));return bp,pp

    def test_binding_requires_immutable_successful_producer_and_exact_resources(self):
        from check_binding import verify_binding
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();bp,pp=self.fixture(root)
            result=verify_binding(bp,pp,root=root)
            self.assertEqual(result["status"],"verified-resources-only")
            self.assertEqual(result["host_validation"],"not_run")
            (root/"build/payload.js").write_text("changed")
            with self.assertRaisesRegex(ValueError,"digest mismatch"):
                verify_binding(bp,pp,root=root)

    def test_unlinked_producer_fails_without_resource_proof(self):
        from check_binding import verify_binding
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();bp,pp=self.fixture(root)
            producer=json.loads(pp.read_text());producer["artifacts"]=[];pp.write_text(json.dumps(producer))
            with self.assertRaisesRegex(ValueError,"linked"):
                verify_binding(bp,pp,root=root)

    def test_checked_relation_does_not_establish_producer(self):
        from check_binding import verify_binding
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();bp,pp=self.fixture(root)
            producer=json.loads(pp.read_text());producer["artifacts"][0]["relation"]="checked";pp.write_text(json.dumps(producer))
            with self.assertRaisesRegex(ValueError,"linked"):
                verify_binding(bp,pp,root=root)

    def test_forged_completion_fields_are_rejected(self):
        from check_binding import verify_binding
        for field,value in [("argv",[]),("observed_at","not UTC"),("signal",15)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();bp,pp=self.fixture(root)
                producer=json.loads(pp.read_text());producer[field]=value;pp.write_text(json.dumps(producer))
                with self.assertRaises(ValueError):
                    verify_binding(bp,pp,root=root)

    def test_incomplete_producer_evidence_is_not_verified_resources(self):
        from check_binding import verify_binding
        failures = [
            ("incomplete evidence", {"evidence_complete": False, "evidence_errors": []}, None),
            ("artifact postcheck error", {"evidence_complete": True,
                                           "evidence_errors": [{"phase": "artifact_postcheck",
                                                                "message": "synthetic postcheck failure"}]}, None),
            ("missing completeness flag", {}, "evidence_complete"),
            ("missing error list", {}, "evidence_errors"),
        ]
        for label, evidence, remove in failures:
            with self.subTest(evidence=label), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();bp,pp=self.fixture(root)
                producer=json.loads(pp.read_text())
                producer.update(evidence)
                if remove is not None:
                    producer.pop(remove)
                pp.write_text(json.dumps(producer))
                with self.assertRaisesRegex(ValueError,"successfully completed"):
                    verify_binding(bp,pp,root=root)

    def test_fifo_producer_receipt_is_rejected_without_blocking(self):
        from check_binding import verify_binding
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();bp,pp=self.fixture(root)
            pp.unlink();os.mkfifo(pp,0o600)
            code=("import sys\nfrom pathlib import Path\n"
                  "sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[1]+'/rebind')\n"
                  "from check_binding import verify_binding\n"
                  "try:\n    verify_binding(Path(sys.argv[2]),Path(sys.argv[3]),root=Path(sys.argv[4]))\n"
                  "except ValueError as error:\n    raise SystemExit(0 if str(error)=='candidate input is not a regular file' else 2)\n"
                  "raise SystemExit(1)\n")
            result=subprocess.run([sys.executable,"-B","-c",code,str(HERE),str(bp),str(pp),str(root)],
                                  capture_output=True,text=True,encoding="utf-8",timeout=3)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__ == "__main__": unittest.main(verbosity=2)

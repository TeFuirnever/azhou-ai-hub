import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('payload_output_guard',ROOT/'packages/agent-skin/tools/test-startup-payload-browser.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class OutputGuardTests(unittest.TestCase):
    def test_measurement_leaves_collector_output_unclaimed_and_native_separate(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'collection'
            native=m.prepare_evidence_paths(out,True,True)
            self.assertFalse(out.exists())
            self.assertNotIn(out,native.parents)
    def test_ordinary_output_is_owned_and_nested_native_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'ordinary'
            self.assertEqual(m.prepare_evidence_paths(out,False,True),out/'native-window-ordering')
            self.assertTrue(out.is_dir())
    def test_existing_measurement_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'collection';out.mkdir();(out/'sentinel').write_text('old')
            with self.assertRaises(FileExistsError):m.prepare_evidence_paths(out,True,False)
            self.assertEqual((out/'sentinel').read_text(),'old')
    def test_preflight_requires_its_sealed_receipt_not_browser_report(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            checkpoint={'head':'a'*40,'indexSHA256':'b'*64,'inputCount':5131,'execution':{'payloadSHA256':'c'*64}}
            receipt={'status':'preflight-only','browserStarted':False,'before':checkpoint,'after':checkpoint}
            path=out/'measurement-preflight.json';path.write_text(json.dumps(receipt))
            manifest={'schema':1,'files':{path.name:hashlib.sha256(path.read_bytes()).hexdigest()}}
            (out/'collection-manifest.json').write_text(json.dumps(manifest))
            m.validate_wrapper_report(out,[],True)
            receipt['browserStarted']=True;path.write_text(json.dumps(receipt))
            with self.assertRaises((ValueError,AssertionError)):m.validate_wrapper_report(out,[],True)
    def test_missing_normal_report_still_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):m.validate_wrapper_report(Path(d),['real check'],False)

if __name__=='__main__':unittest.main()

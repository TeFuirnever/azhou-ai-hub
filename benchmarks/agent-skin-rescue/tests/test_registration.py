import hashlib,json,os,plistlib,subprocess,sys,unittest,uuid
from pathlib import Path
L=Path(__file__).resolve().parents[1];sys.path.insert(0,str(L));WORK=L.parents[1];EVIDENCE=WORK/'.scratch/rescue-b'
EVIDENCE.mkdir(parents=True,exist_ok=True,mode=0o700)
from registration import observe_installation
class RegistrationTests(unittest.TestCase):
 def make_bundle(self):
  root=EVIDENCE/('registration-'+uuid.uuid4().hex)/'Fixture.app';(root/'Contents/MacOS').mkdir(parents=True);(root/'Contents/Resources').mkdir()
  (root/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'fixture.app','CFBundleShortVersionString':'1.0','CFBundleVersion':'1','CFBundleExecutable':'Fixture'}))
  (root/'Contents/MacOS/Fixture').write_bytes(b'not-an-app');(root/'Contents/Resources/app.asar').write_bytes(b'synthetic-asar');return root
 def test_current_bytes_and_metadata_do_not_claim_signature_or_window(self):
  x=observe_installation(self.make_bundle(),synthetic=True,root=WORK)
  self.assertEqual(x['metadata']['bundle_id'],'fixture.app');self.assertEqual(x['scope'],'synthetic-bundle');self.assertFalse(x['hostLaunchAllowed'])
  self.assertEqual(x['strictSignature']['status'],'not-run');self.assertEqual(len(x['files']),3)
 def test_fixture_symlink_is_rejected_without_following_outside_bundle(self):
  p=self.make_bundle();(p/'Contents/Resources/app.asar').unlink();(p/'Contents/Resources/app.asar').symlink_to('/dev/null')
  with self.assertRaises(ValueError):observe_installation(p,synthetic=True,root=WORK)
 def test_fifo_installation_input_is_rejected_without_blocking(self):
  p=self.make_bundle();fifo=p/'Contents/Resources/app.asar';fifo.unlink();os.mkfifo(fifo,0o600)
  code=("import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0,sys.argv[1])\n"
        "from registration import observe_installation\n"
        "try:\n    observe_installation(Path(sys.argv[2]),synthetic=True,root=Path(sys.argv[3]))\n"
        "except ValueError as error:\n    raise SystemExit(0 if str(error)=='installation input is not regular' else 2)\n"
        "raise SystemExit(1)\n")
  result=subprocess.run([sys.executable,'-B','-c',code,str(L),str(p),str(WORK)],capture_output=True,text=True,encoding='utf-8',timeout=3)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_actual_mode_does_not_accept_fixture_as_current_installation(self):
  with self.assertRaises(ValueError):observe_installation(self.make_bundle())
 def test_parent_symlink_is_rejected_even_when_target_stays_in_bundle(self):
  p=self.make_bundle();(p/'Contents/Resources').rename(p/'Contents/RealResources')
  (p/'Contents/Resources').symlink_to('RealResources',target_is_directory=True)
  with self.assertRaises(ValueError):observe_installation(p,synthetic=True,root=WORK)
 def test_streamed_three_file_hashes_match_explicit_synthetic_baseline(self):
  p=self.make_bundle();exe=b'fixture-executable\x00'*131073;asar=b'fixture-asar\xff'*262145
  (p/'Contents/MacOS/Fixture').write_bytes(exe);(p/'Contents/Resources/app.asar').write_bytes(asar)
  expected={'bundle_id':'fixture.app','version':'1.0','build':'1','info_sha256':hashlib.sha256((p/'Contents/Info.plist').read_bytes()).hexdigest(),'executable_sha256':hashlib.sha256(exe).hexdigest(),'app_asar_sha256':hashlib.sha256(asar).hexdigest()}
  x=observe_installation(p,synthetic=True,root=WORK,expected=expected)
  self.assertTrue(x['matchesHistoricalFilesAndMetadata']);self.assertEqual([f['bytes'] for f in x['files']][1:],[len(exe),len(asar)])
  self.assertEqual(x['strictSignature']['status'],'not-run');self.assertFalse(x['hostLaunchAllowed'])
 def test_metadata_observation_has_a_fixed_size_bound(self):
  p=self.make_bundle();(p/'Contents/Info.plist').write_bytes(b'x'*(1024*1024+1))
  with self.assertRaisesRegex(ValueError,'bound'):observe_installation(p,synthetic=True,root=WORK)
 def test_executable_path_escape_is_rejected(self):
  p=self.make_bundle();info=plistlib.loads((p/'Contents/Info.plist').read_bytes());info['CFBundleExecutable']='../Fixture'
  (p/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
  with self.assertRaisesRegex(ValueError,'executable'):observe_installation(p,synthetic=True,root=WORK)
 def test_caller_cannot_expand_worktree_scope(self):
  with self.assertRaisesRegex(ValueError,'scope'):observe_installation(self.make_bundle(),synthetic=True,root=WORK.parent)
if __name__=='__main__':unittest.main(verbosity=2)

import hashlib,json,os,sys,tempfile,unittest,uuid
from pathlib import Path
L=Path(__file__).resolve().parents[1];sys.path.insert(0,str(L));WORK=L.parents[1];EVIDENCE=WORK/'.scratch/rescue-b'
EVIDENCE.mkdir(parents=True,exist_ok=True,mode=0o700)
from launcher import Supervisor,host_launch,SignalLatch
class LauncherTests(unittest.TestCase):
 def setUp(self):
  self.root=EVIDENCE/('launcher-case-'+uuid.uuid4().hex);self.root.mkdir(mode=0o700)
 def test_binary_capture_and_real_exit(self):
  result,case=Supervisor(self.root).fixture('binary','bytes')
  self.assertEqual(result['exit_code'],0);self.assertEqual(result['execution_state'],'exited')
  self.assertEqual((case/'stdout.raw').read_bytes(),b'controlled stdout\x00\xff\r\n')
  self.assertEqual((case/'stderr.raw').read_bytes(),b'controlled stderr\xfe\r\n')
 def test_nonzero_exit_is_not_success(self):
  result,case=Supervisor(self.root).fixture('failed','failure')
  self.assertEqual(result['exit_code'],37);self.assertFalse(result['successful'])
 def test_handoff_stays_owned_and_ack_mutation_is_rejected(self):
  def mutate(offer):offer['nonce']='foreign';return offer
  result,case=Supervisor(self.root).fixture('handoff','hold',handoff=mutate)
  self.assertFalse(result['successful']);self.assertEqual(result['error']['type'],'ValueError')
  self.assertFalse((case/'handoff-accepted.json').exists())
  self.assertIsNotNone(result['exit_code'])
 def test_host_and_arbitrary_app_are_refused(self):
  with self.assertRaises(RuntimeError):host_launch()
  with self.assertRaises(ValueError):Supervisor(self.root).run('forbidden',['/Applications/ZCode.app/Contents/MacOS/ZCode'])
 def test_timeout_with_natural_zero_exit_stays_failed(self):
  result,case=Supervisor(self.root).fixture('timeout','ignore-term',timeout=.03)
  self.assertEqual(result['exit_code'],0);self.assertEqual(result['execution_state'],'timed_out');self.assertFalse(result['successful'])
 def test_unknown_identity_never_signals_or_claims_success(self):
  class Unknown:
   def verify(self,child):return False
  result,case=Supervisor(self.root,identity_factory=Unknown).fixture('unknown','hold')
  self.assertEqual(result['cleanup'],'identity-unverified-no-signal');self.assertFalse(result['successful'])
  events=(case/'events.jsonl').read_text();self.assertNotIn('terminate_sent',events)
 def test_callback_error_retains_real_wait(self):
  def fail(offer):raise RuntimeError('controlled handoff failure')
  result,case=Supervisor(self.root).fixture('callback','hold',handoff=fail)
  self.assertEqual(result['error']['type'],'RuntimeError');self.assertIsNotNone(result['exit_code']);self.assertFalse(result['successful'])
 def test_first_signal_is_latched_during_handoff_and_owned_cleanup(self):
  import signal
  def interrupt(offer):
   os.kill(os.getpid(),signal.SIGTERM);os.kill(os.getpid(),signal.SIGHUP);return offer
  from offline_runtime import SupervisorSignal
  with self.assertRaises(SupervisorSignal):
   with SignalLatch() as stop:
    result,case=Supervisor(self.root,interruption=stop).fixture('signal','hold',handoff=interrupt)
    self.assertFalse(result['successful']);self.assertEqual(result['error']['signal'],signal.SIGTERM);self.assertIsNotNone(result['exit_code'])
 def test_missing_argument_input_still_records_completed_failure(self):
  request=self.root/'input.json';request.write_text('{}')
  def remove_input(offer):request.unlink();return offer
  result,case=Supervisor(self.root).run('missing-input',[sys.executable,'-B',str(L/'fixtures/controlled_host.py'),'--request',str(request)],fixture_mode='hold',handoff=remove_input)
  self.assertEqual(result['kind'],'C');self.assertEqual(result['exit_code'],0)
  self.assertFalse(result['argument_inputs_unchanged']);self.assertFalse(result['successful'])
  self.assertEqual(json.loads((case/'command-result.json').read_text())['command_id'],result['command_id'])
 def test_unregistered_cli_flag_is_refused_before_spawn(self):
  with self.assertRaises(ValueError):Supervisor(self.root).run('bad-flag',[sys.executable,'-B',str(L/'fixtures/controlled_host.py'),'--application','unused'],fixture_mode='bytes')
  self.assertFalse((self.root/'bad-flag').exists())
 def test_child_output_is_linked_to_the_completed_producer(self):
  out=self.root/'products'
  result,case=Supervisor(self.root).run('produce',[sys.executable,'-B',str(L/'fixtures/controlled_host.py'),'--out',str(out)],fixture_mode='artifacts')
  self.assertEqual(result['exit_code'],0);self.assertTrue(result['successful'])
  produced=next(x for x in result['artifacts'] if x['source_path'].endswith('/products/payload.bin'))
  self.assertEqual((WORK/produced['source_path']).read_bytes(),b'produced\x00\xff\r\n')
  self.assertEqual(produced['source_sha256'],hashlib.sha256(b'produced\x00\xff\r\n').hexdigest())
  self.assertEqual(produced['relation'],'produced');self.assertEqual(produced['file_state'],'present')
 def test_missing_declared_output_cannot_be_success(self):
  out=self.root/'missing-products'
  result,case=Supervisor(self.root).run('no-products',[sys.executable,'-B',str(L/'fixtures/controlled_host.py'),'--out',str(out)],fixture_mode='bytes')
  self.assertEqual(result['kind'],'C');self.assertEqual(result['exit_code'],0);self.assertFalse(result['successful'])
  self.assertFalse(out.exists());self.assertTrue(result['evidence_errors'])
 def test_empty_archive_request_is_refused(self):
  from archive import archive
  request=self.root/'archive-request.json';request.write_text(json.dumps({'scope':'offline-archive-only','producers':[]}))
  with self.assertRaises(ValueError):archive(request,self.root/'archive-empty',root=WORK)
 def test_later_archive_preserves_producer_and_binary_outputs(self):
  from archive import archive
  result,case=Supervisor(self.root).fixture('archive-producer','bytes')
  producer=case/'command-result.json';before=producer.read_bytes();digest=hashlib.sha256(before).hexdigest()
  request=self.root/'archive-request.json';request.write_text(json.dumps({'scope':'offline-archive-only','producers':[{'path':str(producer),'sha256':digest}]}))
  archived=archive(request,self.root/'archive-later',root=WORK)
  self.assertEqual(archived['kind'],'A');self.assertEqual(archived['status'],'complete');self.assertNotIn('exit_code',archived)
  self.assertEqual(producer.read_bytes(),before);self.assertTrue(archived['originalProducersUnchanged'])
  self.assertEqual(len(archived['records']),2)
  for original,copied in zip(result['outputs']['raw_files'],archived['records']):
   self.assertEqual(copied['producer_receipt_sha256'],digest)
   self.assertEqual((WORK/copied['archive_path']).read_bytes(),(WORK/original['path']).read_bytes())
 def test_symlink_argument_is_rejected_without_opening_external_target(self):
  foreign=Path(tempfile.mkdtemp(prefix='agent-skin-rescue-b-foreign-',dir='/tmp')).resolve()
  target=foreign/'controlled-input.json';target.write_bytes(b'{"synthetic":true}')
  link=self.root/'linked-request.json';link.symlink_to(target)
  attempts=[];armed=[True]
  def audit(event,args):
   if armed[0] and event=='open' and isinstance(args[0],str) and args[0] in {str(link),str(target)}:
    attempts.append(args[0]);raise PermissionError('synthetic external read blocked by test audit')
  sys.addaudithook(audit)
  try:
   with self.assertRaises(ValueError):Supervisor(self.root).run('foreign-input',[sys.executable,'-B',str(L/'fixtures/controlled_host.py'),'--request',str(link)],fixture_mode='bytes')
   self.assertEqual(attempts,[]);self.assertFalse((self.root/'foreign-input').exists())
  finally:armed[0]=False
 def test_pinned_script_loss_or_replacement_keeps_completed_receipt(self):
  script=L/'fixtures/controlled_host.py';original=script.read_bytes();original_mode=script.stat().st_mode & 0o777
  for index,replacement in enumerate([None,b'replaced after child loaded its source']):
   with self.subTest(replacement=replacement is not None):
    def change_source(offer):
     script.unlink()
     if replacement is not None:script.write_bytes(replacement)
     return offer
    try:
     result,case=Supervisor(self.root).fixture('changed-script-'+str(index),'hold',handoff=change_source)
     self.assertEqual(result['kind'],'C');self.assertEqual(result['exit_code'],0)
     self.assertFalse(result['script_input']['unchanged']);self.assertFalse(result['successful']);self.assertTrue(result['evidence_errors'])
     self.assertTrue((case/'stdout.raw').is_file());self.assertEqual(json.loads((case/'command-result.json').read_bytes())['command_id'],result['command_id'])
    finally:script.write_bytes(original);os.chmod(script,original_mode)
if __name__=='__main__':unittest.main(verbosity=2)

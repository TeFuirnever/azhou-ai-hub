"""Checks at the binary recording, wait, event, and ownership boundaries.

Only bounded synthetic children and a Node mock socket are executed. Test case
files are retained in a new private .scratch directory on each invocation.
"""
from pathlib import Path
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import offline_runtime as runtime
from command_log import CommandLog, SignalLatch, wait_for_check

RUN = Path.cwd() / '.scratch' / ('records-cases-' + uuid.uuid4().hex)
RUN.mkdir(mode=0o700, parents=True)

CHILD = '"""Synthetic child with bounded lifetime. No app, profile or network access."""\nimport json\nimport os\nfrom pathlib import Path\nimport signal\nimport sys\nimport time\nmode = sys.argv[1]\ncase = Path(os.environ["RECOVERY_CASE"])\nif mode == "bytes":\n    os.write(1, b"stdout\\x00\\xff\\r\\n")\n    os.write(2, b"stderr\\xfe\\x00\\r\\n")\nelif mode == "exit37":\n    os.write(2, b"intentional failure\\xff\\n")\n    os._exit(37)\nelif mode in {"hold", "ignore-term"}:\n    if mode == "ignore-term":\n        signal.signal(signal.SIGTERM, signal.SIG_IGN)\n    data = json.dumps({"pid": os.getpid(), "nonce": os.environ["RECOVERY_NONCE"]}).encode()\n    fd = os.open(case / "ready.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)\n    os.write(fd, data)\n    os.fsync(fd)\n    os.close(fd)\n    os.write(1, b"synthetic child ready\\n")\n    time.sleep(1.2)\nelif mode == "artifact":\n    fd = os.open(case / "artifact.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)\n    os.write(fd, b\'{"scope":"synthetic-artifact"}\\n\')\n    os.close(fd)\nelif mode == "partial":\n    fd = os.open(case / "partial.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)\n    os.write(fd, b\'{"unfinished":\')\n    os.close(fd)\n    os._exit(23)\nelse:\n    raise SystemExit("unregistered synthetic mode")\n'
NODE_TESTS = "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { withOwnedSocket } from '../candidate/owned-connection.mjs';\nfor (const phase of ['connect', 'frame', 'context', 'observation-write']) {\n  test(`early ${phase} failure still closes its socket`, async () => {\n    let closed = 0;\n    const error = new Error(`synthetic-${phase}`);\n    await assert.rejects(withOwnedSocket(() => ({ close() { closed++; } }), async () => { throw error; }), value => value === error);\n    assert.equal(closed, 1);\n  });\n}\ntest('open failure creates no fake cleanup', async () => {\n  let worked = false;\n  await assert.rejects(withOwnedSocket(() => { throw Error('open-failed'); }, async () => { worked = true; }), /open-failed/);\n  assert.equal(worked, false);\n});\ntest('success closes once and returns the actual work result', async () => {\n  let closed = 0;\n  assert.equal(await withOwnedSocket(() => ({ close() { closed++; } }), async () => 37), 37);\n  assert.equal(closed, 1);\n});\ntest('work and cleanup failures both remain visible', async () => {\n  await assert.rejects(withOwnedSocket(() => ({ close() { throw Error('close-failed'); } }), async () => { throw Error('work-failed'); }), error => {\n    assert.ok(error instanceof AggregateError);\n    assert.deepEqual(error.errors.map(x => x.message), ['work-failed', 'close-failed']);\n    return true;\n  });\n});\ntest('cleanup failure never returns a successful work value', async () => {\n  await assert.rejects(withOwnedSocket(() => ({ close() { throw Error('close-failed'); } }), async () => 0), /cleanup-unknown/);\n});\n\nfor (const value of [null, undefined, 0, '', false]) {\n  test(`falsy thrown work value ${String(value)} is preserved`, async () => {\n    let caught = false;\n    try { await withOwnedSocket(() => ({ close() {} }), async () => { throw value; }); }\n    catch (error) { caught = true; assert.equal(error, value); }\n    assert.equal(caught, true);\n  });\n  test(`falsy close failure ${String(value)} is never success`, async () => {\n    await assert.rejects(withOwnedSocket(() => ({ close() { throw value; } }), async () => 37), error => {\n      assert.ok(error instanceof AggregateError);\n      assert.equal(error.errors[0], value);\n      return true;\n    });\n  });\n}\n"


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.root = RUN / self._testMethodName
        self.root.mkdir(mode=0o700)

    def recorder(self, identity=None):
        (self.root / 'tests').mkdir(mode=0o700)
        fixture = self.root / 'tests/child_fixture.py'
        runtime.write_new(fixture, CHILD.encode(), root=self.root)
        runtime.json_new(self.root / 'OWNERSHIP.json', {'thread_id': 'synthetic-rescue-owner'}, root=self.root)
        directory = self.root / 'cases'
        directory.mkdir(mode=0o700)
        return runtime.Recorder(directory, fixture, identity, root=self.root,
                                owner_thread='synthetic-rescue-owner')

    def logger(self, inputs=()):
        directory = self.root / 'commands'
        directory.mkdir(mode=0o700)
        return CommandLog(directory, inputs, root=self.root)

    def test_binary_write_is_exclusive(self):
        path = self.root / 'raw.bin'
        runtime.write_new(path, b'a\x00\xff\r\n', root=self.root)
        self.assertEqual(path.read_bytes(), b'a\x00\xff\r\n')
        with self.assertRaises(FileExistsError):
            runtime.write_new(path, b'replacement', root=self.root)
        self.assertEqual(path.read_bytes(), b'a\x00\xff\r\n')

    def test_binary_short_writes_retain_every_byte(self):
        real = os.write
        def short(fd, data):
            return real(fd, data[:1])
        with patch.object(runtime.os, 'write', short):
            runtime.write_new(self.root / 'raw.bin', b'a\x00\xff\r\n', root=self.root)
        self.assertEqual((self.root / 'raw.bin').read_bytes(), b'a\x00\xff\r\n')

    def test_scope_rejects_parent_escape_symlink_and_implicit_root(self):
        outside = self.root.parent / (self.root.name + '-outside')
        outside.mkdir(mode=0o700)
        link = self.root / 'linked'
        link.symlink_to(outside, target_is_directory=True)
        for value in [outside / 'new', link / 'new', self.root / '../escape']:
            with self.assertRaises(ValueError):
                runtime.write_new(value, b'forbidden', root=self.root)
        with self.assertRaises(ValueError):
            runtime.write_new(self.root / 'implicit', b'forbidden')
        self.assertFalse((outside / 'new').exists())

    def test_journal_preserves_event_unknown_and_blocks_completion_override(self):
        path = self.root / 'events.jsonl'
        journal = runtime.Journal(path, ['synthetic-command'], 'case-id', root=self.root)
        try:
            journal.emit('spawn-intent', pid=None)
            with self.assertRaises(ValueError):
                journal.emit('forged-completion', exit_code=0)
        finally:
            journal.close()
        events = [json.loads(line) for line in path.read_bytes().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'E')
        self.assertIsNone(events[0]['exit_code'])
        self.assertEqual(events[0]['command_id'], 'case-id')

    def test_schema_refuses_fabricated_wait_and_signal(self):
        fixture = {'kind': 'C', 'argv': ['synthetic-command'],
                   'observed_at': '2026-11-01T00:00:00+00:00',
                   'execution_state': 'exited', 'exit_code': 0, 'signal': None}
        runtime.validate_result(fixture)
        for change in [{'exit_code': None}, {'kind': 'E'}, {'signal': 9},
                       {'exit_code': True}, {'execution_state': 'not_started'}]:
            with self.assertRaises(ValueError):
                runtime.validate_result({**fixture, **change})
        runtime.validate_result({**fixture, 'kind': 'E', 'execution_state': 'exit_unknown',
                                 'exit_code': None})

    def test_recorder_binary_stream_and_immutable_completion(self):
        receipt, case = self.recorder().run('binary', 'bytes')
        self.assertEqual(receipt['kind'], 'C')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertEqual((case / 'stdout.raw').read_bytes(), b'stdout\x00\xff\r\n')
        self.assertEqual((case / 'stderr.raw').read_bytes(), b'stderr\xfe\x00\r\n')
        before = (case / 'command-result.json').read_bytes()
        with self.assertRaises(FileExistsError):
            runtime.json_new(case / 'command-result.json', {}, root=self.root)
        self.assertEqual((case / 'command-result.json').read_bytes(), before)

    def test_recorder_partial_artifact_retains_nonzero_wait(self):
        receipt, case = self.recorder().run('partial', 'partial')
        self.assertEqual(receipt['exit_code'], 23)
        self.assertEqual((case / 'partial.json').read_bytes(), b'{"unfinished":')
        self.assertEqual(receipt['artifacts'][0]['file_state'], 'partial')

    def test_unknown_identity_never_signals_or_invents_exit(self):
        class Unknown:
            def verify(self, child):
                return False
        receipt, case = self.recorder(Unknown()).run('unknown', 'hold', timeout=0.01)
        self.assertEqual(receipt['cleanup'], 'identity_unverified_no_signal')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertNotIn(b'terminate_sent', (case / 'events.jsonl').read_bytes())
        self.assertIsNotNone(receipt['error'])

    def test_command_capture_uses_actual_binary_wait_and_source_binding(self):
        script = self.root / 'child.py'
        script.write_text("import os;os.write(1,b'raw\\x00\\xff\\r\\n');os.write(2,b'err\\xfe');raise SystemExit(37)\n")
        script.chmod(0o600)
        registered = [{'path': 'child.py', 'sha256': runtime.sha(script)}]
        logger = self.logger(registered)
        result = logger.record([sys.executable, '-B', str(script)])
        self.assertEqual(result.returncode, 37)
        self.assertEqual(result.stdout, b'raw\x00\xff\r\n')
        self.assertEqual(result.stderr, b'err\xfe')
        receipt = json.loads((logger.directory / '0/command.json').read_bytes())
        self.assertEqual(receipt['kind'], 'C')
        self.assertEqual(receipt['execution_state'], 'exited')
        self.assertEqual(receipt['argument_inputs'][0]['sha256'], registered[0]['sha256'])
        self.assertTrue(receipt['inputs_unchanged'])

    def test_stability_check_rejects_fifo_without_blocking(self):
        fifo = self.root / 'input.fifo'
        os.mkfifo(fifo, 0o600)
        self.logger()  # Create the scoped command directory used by the child check.
        code = ("import sys; from pathlib import Path; "
                "sys.path.insert(0, sys.argv[1]); "
                "from command_log import CommandLog; "
                "root = Path(sys.argv[2]); "
                "log = CommandLog(root / 'commands', "
                "[{'path': 'input.fifo', 'sha256': '0' * 64}], root=root); "
                "raise SystemExit(0 if not log.stable() else 1)")
        result = subprocess.run([sys.executable, '-B', '-c', code, str(SOURCE), str(self.root)],
                                capture_output=True, text=True, encoding='utf-8', timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)

    def _check_completed_child_input_mutation(self, mutation):
        script = self.root / 'mutating-child.py'
        replacement = self.root / 'replacement.py'
        replacement.write_text('pass\n')
        operation = "path.unlink()" if mutation == 'unlink' else "path.unlink();path.symlink_to('replacement.py')"
        script.write_text("from pathlib import Path;import os;path=Path(__file__);" + operation
                          + ";os.write(1,b'completed\\x00\\xff');os.write(2,b'actual-stderr')\n")
        logger = self.logger([{'path': script.name, 'sha256': runtime.sha(script)}])
        with self.assertRaises((ValueError, OSError)):
            logger.record([sys.executable, '-B', str(script)], check=True)
        path = logger.directory / '0/command.json'
        self.assertTrue(path.is_file(), 'a completed child must retain its actual wait receipt')
        receipt = json.loads(path.read_bytes())
        self.assertEqual(receipt['kind'], 'C')
        self.assertEqual(receipt['execution_state'], 'exited')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertIsNone(receipt['signal'])
        self.assertFalse(receipt['inputs_unchanged'])
        self.assertFalse(receipt['argument_inputs_unchanged'])
        self.assertTrue(receipt['evidence_errors'])
        self.assertFalse(receipt['evidence_complete'])
        self.assertEqual((logger.directory / '0/stdout.raw').read_bytes(), b'completed\x00\xff')
        self.assertEqual((logger.directory / '0/stderr.raw').read_bytes(), b'actual-stderr')

    def test_command_retains_wait_after_registered_input_unlinked(self):
        self._check_completed_child_input_mutation('unlink')

    def test_command_retains_wait_after_registered_input_replaced_by_symlink(self):
        self._check_completed_child_input_mutation('symlink')

    def _check_completed_child_illegal_artifact(self, mutation):
        script = self.root / 'artifact-child.py'
        artifact = self.root / 'artifact.bin'
        outside = self.root.parent / 'external-target-must-not-open'
        if mutation == 'symlink':
            operation = "artifact.symlink_to(" + repr(str(outside)) + ")"
        else:
            operation = "artifact.write_bytes(b'produced-bytes');artifact.chmod(0)"
        script.write_text("from pathlib import Path;import os;artifact=Path("
                          + repr(str(artifact)) + ");" + operation
                          + ";os.write(1,b'completed-artifact\\x00\\xff');os.write(2,b'actual-artifact-stderr')\n")
        logger = self.logger([{'path': script.name, 'sha256': runtime.sha(script)}])
        try:
            with self.assertRaises((ValueError, OSError)):
                logger.record([sys.executable, '-B', str(script)], check=True,
                              artifact_paths=[artifact])
            path = logger.directory / '0/command.json'
            self.assertTrue(path.is_file(), 'artifact observation errors must not lose actual wait')
            receipt = json.loads(path.read_bytes())
            self.assertEqual(receipt['kind'], 'C')
            self.assertEqual(receipt['execution_state'], 'exited')
            self.assertEqual(receipt['exit_code'], 0)
            self.assertIsNone(receipt['signal'])
            self.assertTrue(receipt['inputs_unchanged'])
            self.assertTrue(receipt['argument_inputs_unchanged'])
            self.assertFalse(receipt['evidence_complete'])
            self.assertTrue(any(error['phase'] == 'artifact_postcheck'
                                for error in receipt['evidence_errors']))
            self.assertEqual(receipt['artifacts'], [])
            self.assertEqual((logger.directory / '0/stdout.raw').read_bytes(),
                             b'completed-artifact\x00\xff')
            self.assertEqual((logger.directory / '0/stderr.raw').read_bytes(),
                             b'actual-artifact-stderr')
            self.assertFalse(outside.exists())
        finally:
            # The deliberately unreadable private fixture stays available for recovery.
            if mutation == 'unreadable' and artifact.exists():
                artifact.chmod(0o600)

    def test_command_retains_wait_after_artifact_points_outside_scope(self):
        self._check_completed_child_illegal_artifact('symlink')

    def test_command_retains_wait_after_artifact_read_is_refused(self):
        self._check_completed_child_illegal_artifact('unreadable')

    def test_command_start_failure_is_event_with_null_exit(self):
        logger = self.logger()
        with self.assertRaises(FileNotFoundError):
            logger.record([str(self.root / 'does-not-exist')])
        receipt = json.loads((logger.directory / '0/command.json').read_bytes())
        self.assertEqual(receipt['kind'], 'E')
        self.assertEqual(receipt['execution_state'], 'not_started')
        self.assertIsNone(receipt['exit_code'])
        self.assertIsNone(receipt['signal'])

    def test_command_signal_preserves_native_return_code(self):
        logger = self.logger()
        result = logger.record([sys.executable, '-B', '-c', 'import os,signal;os.kill(os.getpid(),signal.SIGTERM)'])
        receipt = json.loads((logger.directory / '0/command.json').read_bytes())
        self.assertEqual(result.returncode, -signal.SIGTERM)
        self.assertEqual(receipt['execution_state'], 'signaled')
        self.assertEqual(receipt['signal'], signal.SIGTERM)

    def test_timeout_with_zero_wait_remains_timeout(self):
        class Unknown:
            def verify(self, child):
                return False
        process = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(.08)'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        waited = wait_for_check(process, .001, Unknown())
        self.assertEqual(waited['exit_code'], 0)
        self.assertEqual(waited['execution_state'], 'timed_out')
        self.assertEqual(waited['cleanup'], 'identity_unverified_no_signal')

    def test_signal_latch_preserves_first_and_restores_handlers(self):
        before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        with self.assertRaises(runtime.SupervisorSignal) as caught:
            with SignalLatch() as interrupted:
                os.kill(os.getpid(), signal.SIGTERM)
                os.kill(os.getpid(), signal.SIGHUP)
                self.assertEqual(interrupted(), signal.SIGTERM)
        self.assertEqual(caught.exception.signum, signal.SIGTERM)
        self.assertEqual(before, {sig: signal.getsignal(sig) for sig in before})

    def test_daily_environment_and_host_commands_are_refused(self):
        logger = self.logger()
        with self.assertRaises(ValueError):
            logger.record(['/Applications/Synthetic.app/Contents/MacOS/Synthetic'])
        with self.assertRaises(ValueError):
            logger.record([sys.executable, '-c', 'pass'], env={'UNAPPROVED_SECRET': 'synthetic'})
        self.assertFalse((logger.directory / '0/command.json').exists())

    def test_input_drift_refuses_spawn(self):
        script = self.root / 'input.py'
        script.write_text('pass\n')
        logger = self.logger([{'path': 'input.py', 'sha256': runtime.sha(script)}])
        script.write_text('raise SystemExit(1)\n')
        with self.assertRaises(ValueError):
            logger.record([sys.executable, '-B', str(script)])
        self.assertFalse((logger.directory / '0').exists())

    def test_owned_node_socket_all_eighteen_cases(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is a required local tool')
        script = self.root / 'socket-tests.mjs'
        script.write_text(NODE_TESTS.replace('../candidate/owned-connection.mjs',
                                            (SOURCE / 'owned-connection.mjs').as_uri()))
        logger = self.logger([{'path': 'socket-tests.mjs', 'sha256': runtime.sha(script)}])
        result = logger.record([node, '--test', '--test-reporter=tap', str(script)], check=True, timeout=20)
        self.assertIn(b'# tests 18', result.stdout)
        self.assertIn(b'# fail 0', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)

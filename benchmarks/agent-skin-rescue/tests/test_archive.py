"""Synthetic copy_raw boundary tests; no host launcher or process identity calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import unittest
from unittest.mock import patch
SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import uuid
ROOT = Path.cwd() / '.scratch' / ('archive-cases-' + uuid.uuid4().hex)
ROOT.mkdir(mode=0o700, parents=True)
import archive_raw
from offline_runtime import utc, write_new as _write_new, json_new as _json_new
RUN = ROOT

def write_new(path, data):
    return _write_new(path, data, root=ROOT)

def json_new(path, value):
    return _json_new(path, value, root=ROOT)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.case = RUN / self._testMethodName
        self.case.mkdir(mode=0o700)
        self.source = self.case / 'stdout.raw'
        self.receipt = self.case / 'producer.json'
        self.destdir = self.case / 'archive'
        self.destdir.mkdir(mode=0o700)
        self.dest = self.destdir / 'copy.raw'
        argv = [sys.executable, '-B', '-c', 'import os; os.write(1, b"stdout\\x00\\xff\\r\\n")']
        started = utc()
        with self.source.open('xb') as out, (self.case / 'stderr.raw').open('xb') as err:
            process = subprocess.Popen(argv, stdout=out, stderr=err, cwd=self.case)
            code = process.wait()
        self.source.chmod(0o600)
        (self.case / 'stderr.raw').chmod(0o600)
        self.assertEqual(code, 0)
        self.producer = {'kind':'C', 'started_at':started, 'observed_at':utc(), 'argv':argv,
                         'execution_state':'exited', 'exit_code':code,
                         'outputs':{'raw_files':[{'path':str(self.source.relative_to(ROOT)),
                         'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}]}}
        json_new(self.receipt, self.producer)
        self.original_receipt = self.receipt.read_bytes()

    def archive(self, **kwargs):
        result = archive_raw.copy_raw(self.source, self.dest, self.receipt, root=ROOT, **kwargs)
        json_new(self.case / 'archive-result.json', result)
        self.assertEqual(result['kind'], 'A')
        self.assertNotIn('exit_code', result)
        return result

    def replace_receipt(self):
        self.receipt.rename(self.case / 'preserved-producer.json')
        json_new(self.receipt, {**self.producer, 'command_id':'replacement-must-not-bind'})

    def test_producer_replaced_after_parse_cannot_bind_new_sha(self):
        original = json.loads
        def replace_after_parse(data, *args, **kwargs):
            parsed = original(data, *args, **kwargs)
            self.replace_receipt()
            return parsed
        with patch.object(archive_raw.json, 'loads', replace_after_parse):
            result = self.archive()
        self.assertNotEqual(result['status'], 'complete')
        self.assertEqual(result['producer_receipt_sha256'], hashlib.sha256(self.original_receipt).hexdigest())
        self.assertEqual((self.case / 'preserved-producer.json').read_bytes(), self.original_receipt)

    def _check_metadata_change(self, selected):
        # Exercise independent public copy attempts; preserve every partial target.
        mutations = {
            'destination-mode': lambda source, target: target.chmod(0o644),
            'destination-hardlink': lambda source, target: os.link(target, target.with_name('alias.raw')),
            'source-mode': lambda source, target: source.chmod(0o644),
            'source-hardlink': lambda source, target: os.link(source, source.with_name('alias.raw')),
            'receipt-mode': lambda source, target: self.receipt.chmod(0o644),
            'receipt-hardlink': lambda source, target: os.link(self.receipt, self.case / 'receipt-alias.json'),
            'source-directory-mode': lambda source, target: source.parent.chmod(0o755),
            'destination-directory-mode': lambda source, target: target.parent.chmod(0o755),
        }
        result = self.archive(after_open=mutations[selected])
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(self.dest.exists())
        self.assertEqual(self.dest.read_bytes(), b'stdout\x00\xff\r\n')

    def test_destination_mode_remains_partial(self):
        self._check_metadata_change('destination-mode')

    def test_destination_hardlink_remains_partial(self):
        self._check_metadata_change('destination-hardlink')

    def test_source_mode_remains_partial(self):
        self._check_metadata_change('source-mode')

    def test_source_hardlink_remains_partial(self):
        self._check_metadata_change('source-hardlink')

    def test_receipt_mode_remains_partial(self):
        self._check_metadata_change('receipt-mode')

    def test_receipt_hardlink_remains_partial(self):
        self._check_metadata_change('receipt-hardlink')

    def test_source_directory_mode_remains_partial(self):
        self._check_metadata_change('source-directory-mode')

    def test_destination_directory_mode_remains_partial(self):
        self._check_metadata_change('destination-directory-mode')

    def _bounded_fifo_attempt(self, path):
        path.rename(path.with_name('original-' + path.name))
        os.mkfifo(path, 0o600)
        previous = signal.getsignal(signal.SIGALRM)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        def blocked(signum, frame):
            raise TimeoutError('archive blocked opening or reading a FIFO')
        signal.signal(signal.SIGALRM, blocked)
        signal.setitimer(signal.ITIMER_REAL, 0.25)
        try:
            started = time.monotonic()
            if path == self.receipt:
                with self.assertRaises(ValueError):
                    archive_raw.copy_raw(self.source, self.dest, self.receipt, root=ROOT)
            else:
                result = archive_raw.copy_raw(self.source, self.dest, self.receipt, root=ROOT)
                self.assertEqual(result['status'], 'not_started')
                self.assertEqual(result['error']['type'], 'ValueError')
            self.assertLess(time.monotonic() - started, 0.2)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        self.assertFalse(self.dest.exists())

    def test_source_fifo_is_rejected_without_blocking(self):
        self._bounded_fifo_attempt(self.source)

    def test_producer_fifo_is_rejected_without_blocking(self):
        self._bounded_fifo_attempt(self.receipt)

    def test_malformed_completion_is_refused_before_copy(self):
        self.receipt.rename(self.case / 'original-producer.json')
        json_new(self.receipt, {**self.producer, 'exit_code': True})
        with self.assertRaises(ValueError):
            archive_raw.copy_raw(self.source, self.dest, self.receipt, root=ROOT)
        self.assertFalse(self.dest.exists())

    def test_nonzero_producer_raw_output_can_be_archived(self):
        self.source = self.case / 'failed.raw'
        argv = [sys.executable, '-B', '-c', 'import os;os.write(1,b"failed-output");raise SystemExit(37)']
        started = utc()
        with self.source.open('xb') as out:
            child = subprocess.Popen(argv, cwd=self.case, stdout=out, stderr=subprocess.DEVNULL)
            code = child.wait(timeout=5)
        self.source.chmod(0o600)
        self.assertEqual(code, 37)
        self.receipt.rename(self.case / 'original-producer.json')
        json_new(self.receipt, {'kind':'C', 'started_at':started, 'observed_at':utc(),
                               'argv':argv, 'execution_state':'exited', 'exit_code':code,
                               'signal':None, 'outputs':{'raw_files':[{
                                   'path':str(self.source.relative_to(ROOT)),
                                   'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}]}})
        result = self.archive()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.dest.read_bytes(), b'failed-output')

    def test_normal_copy_binds_original_receipt_and_preserves_bytes(self):
        result = self.archive()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.dest.read_bytes(), b'stdout\x00\xff\r\n')
        self.assertEqual(self.receipt.read_bytes(), self.original_receipt)
        self.assertEqual(result['producer_receipt_sha256'], hashlib.sha256(self.original_receipt).hexdigest())
        self.assertEqual(result['source_sha256'], result['archive_sha256'])

    def test_real_short_writes_finish_copy(self):
        result = self.archive(writer=lambda fd, data: os.write(fd, data[:2]))
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.dest.read_bytes(), b'stdout\x00\xff\r\n')

    def test_partial_is_preserved_and_retry_cannot_overwrite(self):
        result = self.archive(writer=lambda fd, data: 0)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(self.dest.read_bytes(), b'')
        again = archive_raw.copy_raw(self.source, self.dest, self.receipt, root=ROOT)
        json_new(self.case / 'retry-result.json', again)
        self.assertEqual(again['status'], 'not_started')
        self.assertEqual(self.dest.read_bytes(), b'')

    def test_receipt_replacement_during_copy_is_partial(self):
        result = self.archive(after_open=lambda *_: self.replace_receipt())
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(self.dest.read_bytes(), b'stdout\x00\xff\r\n')

    def test_receipt_rewritten_during_copy_is_partial(self):
        def change(*_):
            self.receipt.write_bytes(self.original_receipt + b' ')
        result = self.archive(after_open=change)
        self.assertEqual(result['status'], 'partial')


if __name__ == '__main__':
    unittest.main(verbosity=2)

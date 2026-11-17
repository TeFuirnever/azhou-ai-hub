from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RECORDER = Path(__file__).resolve().parents[1] / 'benchmarks/super-session-insights/recorder'


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'mkfifo'), 'requires a POSIX FIFO')
class CallRecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.target = self.root / 'reflection.py'
        self.target.write_text('print("synthetic target executed")\n', encoding='utf-8')
        fifo = self.root / 'events.fifo'
        os.mkfifo(fifo, 0o600)
        self.reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        self.addCleanup(os.close, self.reader)
        self.env = os.environ.copy()
        self.env.update({'PYTHONPATH': str(RECORDER), 'SSI_RECORDER_FIFO': str(fifo),
                         'SSI_RECORDER_TARGET': str(self.target), 'PYTHONDONTWRITEBYTECODE': '1'})

    def run_python(self, *args):
        result = subprocess.run([sys.executable, *args], env=self.env, text=True, capture_output=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        try:
            data = os.read(self.reader, 65536)
        except BlockingIOError:
            data = b''
        return result.stdout, [json.loads(line) for line in data.splitlines()]

    def test_observes_actual_direct_and_nested_python_invocations(self):
        _, direct = self.run_python(str(self.target), 'render')
        self.assertEqual(['render'], [e['operation'] for e in direct if e['event'] == 'target_start'])
        source = (
            'import subprocess,sys\n'
            f'target={str(self.target)!r}\n'
            'subprocess.run([sys.executable,target,"review-citations"],check=True)\n'
            'child=subprocess.Popen([sys.executable,target,"validate-reflection"])\n'
            'assert child.wait()==0\n'
        )
        _, events = self.run_python('-c', source)
        self.assertEqual(['review-citations', 'validate-reflection'],
                         [e['operation'] for e in events if e['event'] == 'target_start'])
        self.assertEqual(2, sum(e['event'] == 'subprocess_attempt' for e in events))
        self.assertNotIn(str(self.target), json.dumps(events))

    def test_string_literals_and_isolated_python_do_not_claim_observed_execution(self):
        _, events = self.run_python('-c', 's="subprocess.Popen(pretend)"\n# subprocess.run(pretend)\n')
        self.assertEqual([], [e for e in events if e['event'] != 'python_start'])
        source = ('import subprocess,sys\n'
                  f'subprocess.run([sys.executable,"-I",{str(self.target)!r},"render"],check=True)\n')
        output, events = self.run_python('-c', source)
        self.assertIn('synthetic target executed', output)
        self.assertEqual([], [e for e in events if e['event'] == 'target_start'])
        self.assertEqual(1, sum(e['event'] == 'subprocess_attempt' for e in events))

    def test_recorder_does_not_write_to_a_regular_file(self):
        regular = self.root / 'not-a-fifo'
        regular.write_text('keep', encoding='utf-8')
        self.env['SSI_RECORDER_FIFO'] = str(regular)
        self.run_python(str(self.target), 'render')
        self.assertEqual('keep', regular.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

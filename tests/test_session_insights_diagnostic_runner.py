"""Tests for the development diagnostic runner: freeze binding, opt-in recorder session, honest coverage.

The runner is benchmark tooling only. It is not a security monitor, does not
enforce isolation, and must never infer success from static command text.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RECORDER = REPO / 'benchmarks' / 'super-session-insights' / 'recorder'
RUNNER = RECORDER / 'run_diagnostic.py'


def load_runner():
    spec = importlib.util.spec_from_file_location('ssi_run_diagnostic', RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


RESULT_V1_FIELDS = {'schema', 'label', 'argv', 'cwd', 'target', 'recorder_dir', 'fifo_path',
                    'env_overrides', 'returncode', 'stop_reason', 'elapsed_seconds', 'timeout_seconds',
                    'recorder_events_sha256', 'recorder_event_count', 'recorder_parse_errors',
                    'stdout_sha256', 'stderr_sha256', 'command_records', 'stdout_event_parse_errors',
                    'classification', 'repo_binding', 'file_binding_before', 'file_binding_after',
                    'file_binding_unchanged', 'isolation'}


class ClassifyTest(unittest.TestCase):
    """Pure classification: instrumented events are the count basis; text is never one."""

    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def test_counts_instrumented_starts_attempts_and_keeps_zero_call_verdict_false(self):
        events = [
            {'event': 'python_start', 'pid': 10},
            {'event': 'target_start', 'pid': 10, 'operation': 'render'},
            {'event': 'subprocess_attempt', 'pid': 9},
            {'event': 'python_start', 'pid': 11},
            {'event': 'target_start', 'pid': 11, 'operation': 'review-citations'},
        ]
        summary = self.runner.classify(events, [], 'reflection.py')
        self.assertEqual(2, summary['python_starts'])
        self.assertEqual(1, summary['subprocess_attempts'])
        self.assertEqual(1, summary['operations']['render']['instrumented_starts'])
        self.assertEqual(1, summary['operations']['review-citations']['instrumented_starts'])
        self.assertEqual(0, summary['operations']['validate-reflection']['instrumented_starts'])
        self.assertEqual('observed', summary['operations']['render']['start_outcome'])
        self.assertEqual('unobserved', summary['operations']['validate-reflection']['start_outcome'])
        self.assertFalse(summary['zero_call_verdict'])
        self.assertIn('python -I/-S/-E', summary['coverage_statement'])
        self.assertIn('FIFO loss and forged messages', summary['coverage_statement'])
        self.assertIn('not a security monitor', summary['coverage_statement'])
        self.assertIn('not a complete call budget', summary['coverage_statement'])

    def test_exit_candidates_stay_textual_and_exclude_quoted_and_heredoc_forms(self):
        records = [
            {'command': 'python3 reflection.py render', 'exit_code': 0},
            {'command': 'subprocess.run([sys.executable, "/tmp/x/reflection.py", "review-citations"])', 'exit_code': 0},
            {'command': 'quoted = "reflection.py validate-evidence"', 'exit_code': 0},
            {'command': "cat <<'EOF'\nreflection.py validate-evidence\nEOF", 'exit_code': 0},
            {'command': 'python3 reflection.py render && python3 -c \'import subprocess,sys;'
                        'subprocess.run([sys.executable, "reflection.py", "review-citations"])\'', 'exit_code': 5},
        ]
        summary = self.runner.classify([], records, 'reflection.py')
        self.assertEqual([{'exit_code': 0, 'linkage': 'textual-candidate'},
                          {'exit_code': 5, 'linkage': 'textual-candidate'}],
                         summary['operations']['render']['exit_candidates'])
        self.assertEqual([{'exit_code': 0, 'linkage': 'python-list-candidate'},
                          {'exit_code': 5, 'linkage': 'python-list-candidate'}],
                         summary['operations']['review-citations']['exit_candidates'])
        self.assertEqual([], summary['operations']['validate-evidence']['exit_candidates'])
        self.assertEqual('unknown', summary['operations']['render']['exit_outcome'])
        self.assertEqual([], summary['unlinked_target_records'])
        self.assertEqual(0, summary['python_starts'])
        self.assertFalse(summary['zero_call_verdict'])

    def test_missing_recorder_records_keep_unknown_coverage(self):
        summary = self.runner.classify([], [{'command': 'python3 -I reflection.py render', 'exit_code': 0}],
                                       'reflection.py')
        self.assertEqual(0, summary['python_starts'])
        self.assertEqual(0, summary['operations']['render']['instrumented_starts'])
        self.assertEqual([{'exit_code': 0, 'linkage': 'textual-candidate'}],
                         summary['operations']['render']['exit_candidates'])
        self.assertEqual('unobserved', summary['operations']['render']['start_outcome'])
        self.assertFalse(summary['zero_call_verdict'])
        self.assertIn('python -I/-S/-E', summary['coverage_statement'])
        self.assertIn('FIFO loss and forged messages', summary['coverage_statement'])
        self.assertIn('not a security monitor', summary['coverage_statement'])
        self.assertIn('not a complete call budget', summary['coverage_statement'])

    def test_shell_heredoc_stripping_matches_pinned_behavior(self):
        stripped = self.runner.strip_heredocs(
            "cat <<'EOF'\nreflection.py validate-reflection\nEOF\npython reflection.py review-citations")
        self.assertEqual("cat <<'EOF'\npython reflection.py review-citations", stripped)

    def test_shell_heredoc_stripping_only_drops_true_heredoc_bodies(self):
        self.assertEqual('cat <<< "note"\npython3 reflection.py render',
                         self.runner.strip_heredocs('cat <<< "note"\npython3 reflection.py render'))
        self.assertEqual("python3 -c 'print(1 << bits)'\npython3 reflection.py render",
                         self.runner.strip_heredocs("python3 -c 'print(1 << bits)'\npython3 reflection.py render"))
        self.assertEqual('cat <<EOF',
                         self.runner.strip_heredocs('cat <<EOF\nusage: python3 reflection.py render\nEOF'))
        self.assertEqual("cat<<'EOF'",
                         self.runner.strip_heredocs("cat<<'EOF'\nreflection.py validate-evidence\nEOF"))

    def test_here_string_and_shift_operators_keep_trailing_invocations_scannable(self):
        records = [
            {'command': 'cat <<< "note"\npython3 reflection.py render', 'exit_code': 0},
            {'command': "python3 -c 'print(1 << bits)'\npython3 reflection.py review-citations",
             'exit_code': 3},
        ]
        summary = self.runner.classify([], records, 'reflection.py')
        self.assertEqual([{'exit_code': 0, 'linkage': 'textual-candidate'}],
                         summary['operations']['render']['exit_candidates'])
        self.assertEqual([{'exit_code': 3, 'linkage': 'textual-candidate'}],
                         summary['operations']['review-citations']['exit_candidates'])
        self.assertEqual([], summary['unlinked_target_records'])

    def test_unquoted_and_attached_heredoc_bodies_stay_out_of_candidate_scans(self):
        records = [
            {'command': 'cat <<EOF\nusage: python3 reflection.py render\nEOF', 'exit_code': 0},
            {'command': "cat<<'EOF'\nreflection.py validate-evidence\nEOF", 'exit_code': 0},
        ]
        summary = self.runner.classify([], records, 'reflection.py')
        self.assertEqual([], summary['operations']['render']['exit_candidates'])
        self.assertEqual([], summary['operations']['validate-evidence']['exit_candidates'])
        self.assertEqual([], summary['unlinked_target_records'])


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'mkfifo'), 'requires a POSIX FIFO')
class RecordCommandTest(unittest.TestCase):
    """End-to-end recorder session over a synthetic authorized command."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.target = self.work / 'reflection.py'
        self.target.write_text('print("synthetic target executed")\n', encoding='utf-8')
        self.counter = 0

    def record(self, script, extra=(), stdin_path=None, out_name=None):
        self.counter += 1
        out = self.root / (out_name or f'out-{self.counter}')
        command = [sys.executable, str(RUNNER), 'record',
                   '--argv-json', json.dumps(['/bin/sh', '-c', script]),
                   '--work', str(self.work), '--out', str(out),
                   '--target', str(self.target), '--recorder-dir', str(RECORDER), *extra]
        if stdin_path:
            command += ['--stdin-path', str(stdin_path)]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120, encoding="utf-8")
        return proc, out

    def result(self, out):
        return json.loads((out / 'result.json').read_text(encoding='utf-8'))

    def test_record_collects_starts_attempts_bypass_and_raw_output(self):
        script = (
            f'python3 {self.target} render\n'
            'python3 -c \'import subprocess,sys; '
            f'subprocess.run([sys.executable, "{self.target}", "review-citations"], check=True)\'\n'
            f'python3 -I {self.target} validate-evidence\n'
            'python3 -c \'literal = "reflection.py validate-evidence"\'\n'
        )
        proc, out = self.record(script)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertEqual(RESULT_V1_FIELDS, set(result))
        classification = result['classification']
        self.assertEqual(4, classification['python_starts'])
        self.assertEqual(1, classification['subprocess_attempts'])
        self.assertEqual(1, classification['operations']['render']['instrumented_starts'])
        self.assertEqual(1, classification['operations']['review-citations']['instrumented_starts'])
        self.assertEqual(0, classification['operations']['validate-evidence']['instrumented_starts'])
        self.assertEqual('unobserved', classification['operations']['validate-evidence']['start_outcome'])
        self.assertFalse(classification['zero_call_verdict'])
        self.assertEqual([], result['command_records'])
        self.assertEqual(3, (out / 'stdout.log').read_text(encoding='utf-8').count('synthetic target executed'))
        raw = (out / 'recorder-events.jsonl').read_bytes()
        self.assertEqual(sha256_bytes(raw), result['recorder_events_sha256'])
        events = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual({'render', 'review-citations'},
                         {e['operation'] for e in events if e['event'] == 'target_start'})
        self.assertEqual(0, result['recorder_parse_errors'])

    def test_record_parses_command_records_and_links_candidates_verbatim(self):
        records_path = self.root / 'records.jsonl'
        entries = [
            {'type': 'item.completed',
             'item': {'type': 'command_execution', 'command': f'python3 {self.target} render', 'exit_code': 0}},
            {'type': 'item.completed',
             'item': {'type': 'command_execution',
                      'command': f'subprocess.run([sys.executable, {str(self.target)!r}, "review-citations"])',
                      'exit_code': 0}},
            {'type': 'item.completed',
             'item': {'type': 'command_execution',
                      'command': "cat <<'EOF'\nreflection.py validate-evidence\nEOF", 'exit_code': 0}},
            {'type': 'item.completed',
             'item': {'type': 'command_execution', 'exit_code': 5,
                      'command': f'python3 {self.target} render && python3 -c \'import subprocess,sys; '
                                 f'subprocess.run([sys.executable, "{self.target}", "review-citations"])\''}},
        ]
        records_path.write_text('\n'.join(json.dumps(entry) for entry in entries) + '\n', encoding='utf-8')
        script = f'cat {records_path}; python3 {self.target} render'
        proc, out = self.record(script)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertEqual([{'command': entry['item']['command'], 'exit_code': entry['item']['exit_code']}
                          for entry in entries],
                         result['command_records'])
        classification = result['classification']
        self.assertEqual(1, classification['operations']['render']['instrumented_starts'])
        self.assertEqual([{'exit_code': 0, 'linkage': 'textual-candidate'},
                          {'exit_code': 5, 'linkage': 'textual-candidate'}],
                         classification['operations']['render']['exit_candidates'])
        self.assertEqual([{'exit_code': 0, 'linkage': 'python-list-candidate'},
                          {'exit_code': 5, 'linkage': 'python-list-candidate'}],
                         classification['operations']['review-citations']['exit_candidates'])
        self.assertEqual([], classification['operations']['validate-evidence']['exit_candidates'])
        self.assertEqual([], classification['unlinked_target_records'])

    def test_record_refuses_existing_output(self):
        proc, out = self.record('true')
        self.assertEqual(0, proc.returncode, proc.stderr)
        repeat, _ = self.record('true', out_name=out.name)
        self.assertNotEqual(0, repeat.returncode)
        self.assertIn('already exists', repeat.stderr)

    def test_record_enforces_timeout_and_records_stop_reason(self):
        proc, out = self.record('sleep 30', extra=('--timeout-seconds', '2'))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertEqual('timeout', result['stop_reason'])
        self.assertNotEqual(0, result['returncode'])
        self.assertLess(result['elapsed_seconds'], 15)
        self.assertFalse((out / 'recorder-events.fifo').exists())

    def test_record_times_out_when_stdin_feed_would_block(self):
        prompt = self.root / 'big-prompt.txt'
        prompt.write_bytes(b'x' * 70000)
        proc, out = self.record('sleep 30', extra=('--timeout-seconds', '2'), stdin_path=prompt)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertEqual('timeout', result['stop_reason'])
        self.assertLess(result['elapsed_seconds'], 15)

    def test_record_places_fifo_at_requested_path_and_keeps_output_private(self):
        fifo = self.root / 'shared' / 'events.fifo'
        fifo.parent.mkdir()
        script = f'python3 {self.target} render'
        proc, out = self.record(script, extra=('--fifo-path', str(fifo)))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertFalse((out / 'recorder-events.fifo').exists())
        result = self.result(out)
        self.assertEqual(str(fifo), result['fifo_path'])
        self.assertEqual(1, result['classification']['operations']['render']['instrumented_starts'])
        self.assertNotIn(str(fifo), json.dumps(json.loads(json.dumps(result['classification']))))
        self.assertFalse(fifo.exists())

    def test_record_feeds_stdin_file_bytes(self):
        prompt = self.root / 'prompt.txt'
        prompt.write_bytes(b'authorized synthetic prompt bytes\n')
        capture = self.root / 'stdin-capture.txt'
        script = f'cat > {capture}; python3 {self.target} render'
        proc, out = self.record(script, stdin_path=prompt)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(b'authorized synthetic prompt bytes\n', capture.read_bytes())

    def test_record_rejects_recorder_env_overrides_and_merges_pythonpath(self):
        proc, out = self.record('true', extra=('--env', 'SSI_RECORDER_FIFO=/tmp/elsewhere'))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn('SSI_RECORDER_FIFO', proc.stderr)
        proc, out = self.record(f'python3 {self.target} render',
                                extra=('--env', 'PYTHONPATH=/w/vendor', '--env', 'EXTRA=1'))
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertEqual(1, result['classification']['operations']['render']['instrumented_starts'])
        self.assertEqual({'PYTHONPATH': '/w/vendor', 'EXTRA': '1'}, result['env_overrides'])

    def test_record_binds_repo_and_file_revisions(self):
        repo = self.root / 'repo'
        repo.mkdir()
        (repo / 'tracked.txt').write_text('one\n', encoding='utf-8')

        def git(*args):
            subprocess.run(['git', *args], cwd=str(repo), check=True, capture_output=True)

        git('init', '-q', '-b', 'main')
        git('-c', 'user.email=bench@example', '-c', 'user.name=bench', 'add', '.')
        git('-c', 'user.email=bench@example', '-c', 'user.name=bench', 'commit', '-q', '-m', 'init')
        binding = ('--bind-repo', str(repo), '--bind-file', str(self.target))
        proc, out = self.record('true', extra=binding)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertTrue(result['repo_binding']['unchanged'])
        self.assertTrue(result['file_binding_unchanged'])
        self.assertIn('covers', result['repo_binding'])
        proc, out = self.record(f'printf more >> {repo}/tracked.txt; printf changed > {self.target}', extra=binding)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = self.result(out)
        self.assertFalse(result['repo_binding']['unchanged'])
        self.assertFalse(result['file_binding_unchanged'])

    def test_record_reports_deleted_bound_file_without_losing_run(self):
        victim = self.root / 'victim.txt'
        victim.write_bytes(b'bound bytes\n')
        proc, out = self.record(f'rm {victim}; rm "$(dirname "$SSI_RECORDER_FIFO")/stdout.log"',
                                extra=('--bind-file', str(victim)))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((out / 'result.json').is_file())
        result = self.result(out)
        self.assertIsNone(result['stop_reason'])
        self.assertEqual(0, result['returncode'])
        self.assertFalse(result['file_binding_unchanged'])
        self.assertEqual('missing-or-unreadable', result['file_binding_after'][str(victim)])
        self.assertIn('classification', result)
        self.assertTrue((out / 'recorder-events.jsonl').is_file())
        self.assertEqual('missing-or-unreadable', result['stdout_sha256'])
        self.assertEqual([], result['command_records'])

    def test_record_reports_removed_repo_git_without_losing_run(self):
        repo = self.root / 'repo'
        repo.mkdir()
        (repo / 'tracked.txt').write_text('one\n', encoding='utf-8')

        def git(*args):
            subprocess.run(['git', *args], cwd=str(repo), check=True, capture_output=True)

        git('init', '-q', '-b', 'main')
        git('-c', 'user.email=bench@example', '-c', 'user.name=bench', 'add', '.')
        git('-c', 'user.email=bench@example', '-c', 'user.name=bench', 'commit', '-q', '-m', 'init')
        proc, out = self.record(f'rm -rf {repo}/.git', extra=('--bind-repo', str(repo)))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((out / 'result.json').is_file())
        result = self.result(out)
        self.assertIsNone(result['stop_reason'])
        self.assertFalse(result['repo_binding']['unchanged'])
        self.assertEqual('missing-or-unreadable', result['repo_binding']['after'])
        self.assertIn('classification', result)

    def test_record_rejects_fifo_paths_before_creating_out(self):
        taken = self.root / 'taken.fifo'
        taken.write_bytes(b'')
        proc, out = self.record('true', extra=('--fifo-path', str(taken)))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn('already exists', proc.stderr)
        self.assertFalse(out.exists())
        proc, out = self.record('true', extra=('--fifo-path', str(self.root / 'missing' / 'x.fifo')))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn('does not exist', proc.stderr)
        self.assertFalse(out.exists())

    def test_record_writes_result_json_when_command_fails_to_start(self):
        self.counter += 1
        out = self.root / f'out-{self.counter}'
        command = [sys.executable, str(RUNNER), 'record',
                   '--argv-json', json.dumps(['/nonexistent-binary-xyz']),
                   '--work', str(self.work), '--out', str(out),
                   '--target', str(self.target), '--recorder-dir', str(RECORDER)]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertNotEqual(0, proc.returncode)
        self.assertIn('failed to start', proc.stderr)
        result = self.result(out)
        self.assertIsNone(result['returncode'])
        self.assertEqual('spawn-failed', result['stop_reason'])
        self.assertIn('nonexistent-binary-xyz', result['spawn_error'])
        self.assertTrue(RESULT_V1_FIELDS.issubset(result))
        self.assertEqual(600, result['timeout_seconds'])
        self.assertEqual([], result['command_records'])
        self.assertEqual(0, result['recorder_event_count'])

    def test_record_writes_full_result_json_when_setup_fails(self):
        self.counter += 1
        out = self.root / f'out-{self.counter}'
        not_a_repo = self.root / 'not-a-repo'
        not_a_repo.mkdir()
        command = [sys.executable, str(RUNNER), 'record',
                   '--argv-json', json.dumps(['true']),
                   '--work', str(self.work), '--out', str(out),
                   '--target', str(self.target), '--recorder-dir', str(RECORDER),
                   '--bind-repo', str(not_a_repo)]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertNotEqual(0, proc.returncode)
        self.assertIn('record setup failed', proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)
        result = self.result(out)
        self.assertEqual('setup-failed', result['stop_reason'])
        self.assertIsNone(result['returncode'])
        self.assertEqual(600, result['timeout_seconds'])
        self.assertEqual([], result['command_records'])
        self.assertTrue(RESULT_V1_FIELDS.issubset(result))
        self.assertFalse((out / 'recorder-events.fifo').exists())

    def test_record_keeps_result_json_when_command_deletes_output_dir(self):
        proc, out = self.record('rm -rf "$(dirname "$SSI_RECORDER_FIFO")"')
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((out / 'result.json').is_file())
        result = self.result(out)
        self.assertTrue(RESULT_V1_FIELDS.issubset(result))
        self.assertEqual('missing-or-unreadable', result['stdout_sha256'])
        self.assertEqual('missing-or-unreadable', result['stderr_sha256'])
        self.assertEqual([], result['command_records'])
        self.assertIsNone(result['stop_reason'])
        self.assertNotEqual('missing-or-unreadable', result['recorder_events_sha256'])

    def test_record_writes_result_json_when_run_is_interrupted(self):
        runner = load_runner()
        self.counter += 1
        out = self.root / f'out-{self.counter}'
        args = runner.build_parser().parse_args([
            'record', '--argv-json', json.dumps(['true']),
            '--work', str(self.work), '--out', str(out),
            '--target', str(self.target), '--recorder-dir', str(RECORDER)])
        fake_proc = mock.Mock(returncode=None)
        fake_proc.poll.side_effect = KeyboardInterrupt()
        with mock.patch.object(runner.subprocess, 'Popen', return_value=fake_proc):
            with self.assertRaises(KeyboardInterrupt):
                runner.record_command(args)
        result = self.result(out)
        self.assertEqual('interrupted', result['stop_reason'])
        self.assertIsNone(result['returncode'])
        self.assertTrue(RESULT_V1_FIELDS.issubset(result))

    def test_record_writes_result_json_when_setup_is_interrupted(self):
        runner = load_runner()
        self.counter += 1
        out = self.root / f'out-{self.counter}'
        args = runner.build_parser().parse_args([
            'record', '--argv-json', json.dumps(['true']),
            '--work', str(self.work), '--out', str(out),
            '--target', str(self.target), '--recorder-dir', str(RECORDER),
            '--bind-repo', str(self.root / 'repo')])
        with mock.patch.object(runner, 'snapshot_repo', side_effect=KeyboardInterrupt()):
            with self.assertRaises(SystemExit):
                runner.record_command(args)
        result = self.result(out)
        self.assertEqual('setup-failed', result['stop_reason'])
        self.assertEqual('KeyboardInterrupt', result['setup_error'])
        self.assertTrue(RESULT_V1_FIELDS.issubset(result))


class BindFreezeTest(unittest.TestCase):
    """Frozen material must verify first, copy read-only, and bind source and copy hashes."""

    def make_freeze(self, root: Path) -> Path:
        freeze = root / 'freeze'
        (freeze / 'cases').mkdir(parents=True)
        (freeze / 'MODEL-PROMPT.md').write_bytes(b'prompt bytes\n')
        (freeze / 'cases' / 'case-1.md').write_bytes(b'case bytes\n')
        members = [('MODEL-PROMPT.md', sha256_bytes((freeze / 'MODEL-PROMPT.md').read_bytes())),
                   ('cases/case-1.md', sha256_bytes((freeze / 'cases' / 'case-1.md').read_bytes()))]
        manifest = {'schema': 'diag.freeze.v1',
                    'frozen_files': [{'path': path, 'sha256': digest} for path, digest in members]}
        (freeze / 'FREEZE.manifest.json').write_bytes((json.dumps(manifest) + '\n').encode('utf-8'))
        return freeze

    def run_bind(self, freeze: Path, copy: Path):
        return subprocess.run([sys.executable, str(RUNNER), 'bind-freeze',
                               '--freeze', str(freeze), '--copy', str(copy)],
                              capture_output=True, text=True, timeout=60, encoding="utf-8")

    def test_bind_freeze_verifies_copies_and_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            copy = root / 'copy'
            proc = self.run_bind(freeze, copy)
            self.assertEqual(0, proc.returncode, proc.stderr)
            binding = json.loads((copy / 'freeze-binding.json').read_text(encoding='utf-8'))
            self.assertTrue(binding['verified'])
            self.assertEqual(sha256_bytes((freeze / 'FREEZE.manifest.json').read_bytes()),
                             binding['manifest_sha256'])
            for entry in binding['files']:
                self.assertTrue(entry['match'])
                member = copy / entry['path']
                self.assertEqual(entry['source_sha256'], sha256_bytes(member.read_bytes()))
                self.assertEqual(0, stat.S_IMODE(member.stat().st_mode) & 0o222)
            self.assertEqual(0, stat.S_IMODE(copy.stat().st_mode) & 0o222)
            self.assertEqual(0, stat.S_IMODE((copy / 'cases').stat().st_mode) & 0o222)
            repeat = self.run_bind(freeze, copy)
            self.assertNotEqual(0, repeat.returncode)
            self.assertIn('already exists', repeat.stderr)

    def test_bind_freeze_rejects_tampered_material_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            (freeze / 'MODEL-PROMPT.md').write_bytes(b'tampered\n')
            copy = root / 'copy'
            proc = self.run_bind(freeze, copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn('verification failed', proc.stderr)
            self.assertFalse(copy.exists())

    def test_bind_freeze_fails_when_source_changes_after_verification(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            copy = root / 'copy'
            target = freeze / 'MODEL-PROMPT.md'
            real_hash = runner.hash_file
            mutated = []

            def hash_and_mutate(path):
                result = real_hash(path)
                if Path(path) == target and not mutated:
                    mutated.append(True)
                    target.write_bytes(b'changed after verification\n')
                return result

            with mock.patch.object(runner, 'hash_file', side_effect=hash_and_mutate):
                with self.assertRaises(SystemExit):
                    runner.bind_freeze(freeze, copy)
            self.assertFalse((copy / 'MODEL-PROMPT.md').exists())
            self.assertFalse((copy / 'freeze-binding.json').exists())
            self.assertFalse(copy.exists())

    def test_bind_freeze_rejects_escaping_manifest_paths_without_writing_outside_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            absolute_target = root / 'absolute-target.txt'
            absolute_target.write_bytes(b'escape bytes\n')
            cases = [('traversal', '../leak.txt', root / 'traversal' / 'leak.txt',
                      root / 'traversal' / 'deep' / 'leak.txt'),
                     ('absolute', str(absolute_target), absolute_target, absolute_target)]
            for name, entry_path, source, outside in cases:
                with self.subTest(name):
                    source.parent.mkdir(parents=True, exist_ok=True)
                    outside.parent.mkdir(parents=True, exist_ok=True)
                    source.write_bytes(b'escape bytes\n')
                    if outside != source:
                        outside.write_bytes(b'sentinel bytes\n')
                    before = outside.read_bytes()
                    freeze = self.make_freeze(source.parent)
                    manifest = {'schema': 'diag.freeze.v1',
                                'frozen_files': [{'path': entry_path, 'sha256': sha256_bytes(source.read_bytes())}]}
                    (freeze / 'FREEZE.manifest.json').write_bytes((json.dumps(manifest) + '\n').encode('utf-8'))
                    copy = outside.parent / 'copy'
                    proc = self.run_bind(freeze, copy)
                    self.assertNotEqual(0, proc.returncode)
                    self.assertIn('verification failed', proc.stderr)
                    self.assertFalse(copy.exists())
                    self.assertEqual(before, outside.read_bytes())
                    self.assertNotEqual(0, stat.S_IMODE(outside.stat().st_mode) & 0o222)
            for name, entry_path in (('windows-absolute', 'C:\\Users\\bob\\leak.txt'),
                                     ('windows-traversal', '..\\leak.txt')):
                with self.subTest(name):
                    freeze = self.make_freeze(root / name)
                    manifest = {'schema': 'diag.freeze.v1',
                                'frozen_files': [{'path': entry_path, 'sha256': '0' * 64}]}
                    (freeze / 'FREEZE.manifest.json').write_bytes((json.dumps(manifest) + '\n').encode('utf-8'))
                    copy = root / name / 'copy'
                    proc = self.run_bind(freeze, copy)
                    self.assertNotEqual(0, proc.returncode)
                    self.assertIn('unsafe path', proc.stderr)
                    self.assertFalse(copy.exists())

    def test_bind_freeze_rejects_malformed_manifest_without_copy_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (('missing-key', {'schema': 'diag.freeze.v1'}),
                     ('non-list', {'schema': 'diag.freeze.v1', 'frozen_files': 'oops'}),
                     ('non-dict-entry', {'schema': 'diag.freeze.v1', 'frozen_files': ['oops']}),
                     ('missing-sha', {'schema': 'diag.freeze.v1', 'frozen_files': [{'path': 'a.txt'}]}))
            for name, manifest in cases:
                with self.subTest(name):
                    freeze = root / name / 'freeze'
                    freeze.mkdir(parents=True)
                    (freeze / 'FREEZE.manifest.json').write_bytes((json.dumps(manifest) + '\n').encode('utf-8'))
                    copy = root / name / 'copy'
                    proc = self.run_bind(freeze, copy)
                    self.assertNotEqual(0, proc.returncode)
                    self.assertIn('verification failed', proc.stderr)
                    self.assertNotIn('Traceback', proc.stderr)
                    self.assertFalse(copy.exists())

    def test_bind_freeze_rejects_missing_and_unparseable_manifest_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('missing', 'unparseable'):
                with self.subTest(name):
                    freeze = root / name / 'freeze'
                    freeze.mkdir(parents=True)
                    if name == 'unparseable':
                        (freeze / 'FREEZE.manifest.json').write_bytes(b'{not json\n')
                    copy = root / name / 'copy'
                    proc = self.run_bind(freeze, copy)
                    self.assertNotEqual(0, proc.returncode)
                    self.assertIn('verification failed', proc.stderr)
                    self.assertNotIn('Traceback', proc.stderr)
                    self.assertFalse(copy.exists())

    def test_bind_freeze_reports_unreadable_member_without_traceback(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            copy = root / 'copy'
            with mock.patch.object(runner, 'hash_file', side_effect=OSError('unreadable')):
                with self.assertRaises(SystemExit) as caught:
                    runner.bind_freeze(freeze, copy)
            self.assertIn('verification failed', str(caught.exception))
            self.assertFalse(copy.exists())

    def test_bind_freeze_cleans_residue_when_lock_down_is_interrupted(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            copy = root / 'copy'
            real_chmod = Path.chmod

            def chmod_with_interrupted_lock_down(path, mode):
                if mode == 0o555 and Path(path) == copy:
                    raise OSError('lock-down interrupted')
                return real_chmod(path, mode)

            with mock.patch.object(Path, 'chmod', new=chmod_with_interrupted_lock_down):
                with self.assertRaises(OSError):
                    runner.bind_freeze(freeze, copy)
            self.assertFalse(copy.exists())

    def test_bind_freeze_surfaces_cleanup_failure(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = self.make_freeze(root)
            copy = root / 'copy'
            target = freeze / 'MODEL-PROMPT.md'
            real_hash = runner.hash_file
            mutated = []

            def hash_and_mutate(path):
                result = real_hash(path)
                if Path(path) == target and not mutated:
                    mutated.append(True)
                    target.write_bytes(b'changed after verification\n')
                return result

            def stubborn_rmtree(path, ignore_errors=False):
                if ignore_errors:
                    return None
                raise OSError('copy removal denied')

            with mock.patch.object(runner, 'hash_file', side_effect=hash_and_mutate):
                with mock.patch.object(runner.shutil, 'rmtree', new=stubborn_rmtree):
                    with self.assertRaises(SystemExit) as caught:
                        runner.bind_freeze(freeze, copy)
            self.assertIn('copy cleanup failed', str(caught.exception))
            self.assertIn('copy removal denied', str(caught.exception))
            self.assertIn('verification failed', str(caught.exception))


if __name__ == '__main__':
    unittest.main()

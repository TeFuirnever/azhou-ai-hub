"""Isolation regressions use temporary synthetic evaluators, never old evidence."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'repo_pedant_replay_isolated',
    ROOT / 'benchmarks' / 'super-repo-pedant' / 'replay_isolated.py',
)
assert SPEC is not None and SPEC.loader is not None
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


class IsolatedReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.runtime = self.root / 'runtime'
        self.source.mkdir()
        self.runtime.mkdir()
        self.output = self.root / 'output'

    def frozen_fixture(self, *, passed=16, action=''):
        # The reviewed production evaluator pin is patched only for this isolated
        # verifier-wiring fixture. These are not model or natural-task results.
        evaluator = (
            "import argparse, json\n"
            "from pathlib import Path\n"
            "parser = argparse.ArgumentParser()\n"
            "for key in ('variant', 'runtime', 'run-id'): parser.add_argument('--' + key)\n"
            "args = parser.parse_args()\n"
            "root = Path(__file__).resolve().parent\n"
            "runtime = Path(args.runtime)\n"
            "ids = [case['id'] for case in json.loads((root / 'cases.json').read_text())]\n"
            + action + "\n"
            + f"print(json.dumps({{'cases': len(ids), 'passed': {passed}, 'failed': ids[{passed}:]}}))\n"
        ).encode('utf-8')
        cases = [{'id': f'case-{i:02}', 'expected': {'code': 0}} for i in range(16)]
        prepared = []
        for case in cases:
            cid = case['id']
            frozen = self.source / 'inputs' / cid / 'frozen'
            frozen.mkdir(parents=True)
            fields = {
                'case.json': json.dumps(case).encode('utf-8'),
                'ownership.json': json.dumps({'own': {
                    'remote': f'https://example.invalid/project-scope/{cid}/own.git',
                    'common_dir': str(self.source / 'inputs' / cid / 'projects' / 'own' / '.git'),
                }}).encode('utf-8'),
                'live.jsonl': b'',
                'include.jsonl': b'',
                'rows.json': b'[]',
            }
            for name, data in fields.items():
                (frozen / name).write_bytes(data)
            prepared.append({'id': cid, 'frozen_inputs': {
                name: {'sha256': replay.sha(data), 'bytes': len(data)}
                for name, data in fields.items()
            }})
        originals = {
            'frozen_evaluator.py': evaluator,
            'cases.json': json.dumps(cases).encode('utf-8'),
            'prepared-inputs.json': json.dumps(prepared).encode('utf-8'),
            'baseline-manifest.json': b'{}',
        }
        for name, data in originals.items():
            (self.source / name).write_bytes(data)
        registration = json.dumps({'frozen_files': {
            name: replay.sha(data) for name, data in originals.items()
        }}).encode('utf-8')
        (self.source / 'preregistration.json').write_bytes(registration)
        for name in ('manage_evolution.py', 'azhou_runtime_state.py'):
            (self.runtime / name).write_text('# synthetic runtime\n', encoding='utf-8')
        return replay.sha(registration), replay.sha(evaluator)

    def run_fixture(self, registration_sha, evaluator_sha):
        with mock.patch.object(replay, 'EVALUATOR_SHA256', evaluator_sha):
            return replay.replay(self.source, self.runtime, self.output, registration_sha)

    def test_success_preserves_all_sources_and_rejects_reused_output(self):
        registration_sha, evaluator_sha = self.frozen_fixture()
        before_source, before_runtime = replay.inventory(self.source), replay.inventory(self.runtime)
        report = self.run_fixture(registration_sha, evaluator_sha)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['isolation_status'], 'passed')
        self.assertEqual(report['effect_status'], 'passed')
        self.assertEqual(report['passed'], 16)
        self.assertEqual(report['wrapper_model_calls'], 0)
        for field in ('evaluator_model_calls', 'evaluator_model_tokens', 'evaluator_api_cost'):
            self.assertIsNone(report[field], 'uninstrumented child cost must remain unknown')
        self.assertNotIn('runner_api_cost', report)
        self.assertIn('descendant', report['timeout_scope'])
        self.assertEqual(replay.inventory(self.source), before_source)
        self.assertEqual(replay.inventory(self.runtime), before_runtime)
        for name in ('protocol', 'inputs', 'runtime'):
            self.assertTrue(report['copied_' + name + '_unchanged'])
        output_before = replay.inventory(self.output)
        with self.assertRaisesRegex(ValueError, 'must not exist'):
            self.run_fixture(registration_sha, evaluator_sha)
        self.assertEqual(replay.inventory(self.output), output_before)

    def test_completed_isolation_does_not_claim_failed_cases_passed(self):
        registration_sha, evaluator_sha = self.frozen_fixture(passed=10)
        report = self.run_fixture(registration_sha, evaluator_sha)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['isolation_status'], 'passed')
        self.assertEqual(report['effect_status'], 'failed')
        self.assertEqual(report['passed'], 10)
        self.assertEqual(len(report['failed']), 6)

    def test_pollution_is_detected_and_failed_artifacts_are_retained(self):
        marker = self.source / 'unexpected-empty-directory'
        action = (
            "(root / 'cases.json').write_text('[]')\n"
            "(root / 'preregistration.json').write_text('{}')\n"
            "(root / 'inputs' / ids[0] / 'frozen' / 'new-empty-directory').mkdir()\n"
            "(runtime / 'azhou_runtime_state.py').write_text('# replaced')\n"
            + f"Path({str(marker)!r}).mkdir()\n"
        )
        registration_sha, evaluator_sha = self.frozen_fixture(action=action)
        report = self.run_fixture(registration_sha, evaluator_sha)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['isolation_status'], 'failed')
        self.assertEqual(report['effect_status'], 'invalidated')
        for field in ('original_corpus_unchanged', 'copied_protocol_unchanged',
                      'copied_inputs_unchanged', 'copied_runtime_unchanged'):
            self.assertFalse(report[field], field)
        self.assertTrue(report['runtime_source_unchanged'])
        self.assertTrue(marker.is_dir())
        self.assertTrue((self.output / 'stdout.json').is_file())
        self.assertTrue((self.output / 'report.json').is_file())
        self.assertTrue((self.output / 'copies-before.json').is_file())
        self.assertTrue((self.output / 'copies-after.json').is_file())

    def test_timeout_retains_partial_logs_and_integrity_observations(self):
        registration_sha, evaluator_sha = self.frozen_fixture()
        real_run = subprocess.run

        def bounded_run(command, **kwargs):
            if command[0] == sys.executable:
                raise subprocess.TimeoutExpired(command, 120, output=b'partial stdout',
                                                stderr=b'partial stderr')
            return real_run(command, **kwargs)

        with mock.patch.object(replay.subprocess, 'run', side_effect=bounded_run):
            report = self.run_fixture(registration_sha, evaluator_sha)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['isolation_status'], 'passed')
        self.assertEqual(report['effect_status'], 'not_evaluated')
        self.assertTrue(report['timed_out'])
        self.assertEqual((self.output / 'stdout.json').read_bytes(), b'partial stdout')
        self.assertEqual((self.output / 'stderr.log').read_bytes(), b'partial stderr')

    def test_wrong_registration_or_modified_input_fails_before_output(self):
        registration_sha, evaluator_sha = self.frozen_fixture()
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.run_fixture('0' * 64, evaluator_sha)
        self.assertFalse(self.output.exists())
        (self.source / 'cases.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.run_fixture(registration_sha, evaluator_sha)
        self.assertFalse(self.output.exists())

    @unittest.skipIf(os.name == 'nt', 'directory symlink fixture requires POSIX')
    def test_symlinked_input_ancestors_are_rejected_before_output(self):
        ancestors = ('inputs', 'inputs/case-00', 'inputs/case-00/frozen')
        for index, relative in enumerate(ancestors):
            with self.subTest(ancestor=relative):
                self.source = self.root / f'source-{index}'
                self.runtime = self.root / f'runtime-{index}'
                self.output = self.root / f'output-{index}'
                self.source.mkdir()
                self.runtime.mkdir()
                registration_sha, evaluator_sha = self.frozen_fixture()
                original = self.source / relative
                outside = self.root / f'outside-source-{index}'
                original.rename(outside)
                original.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    self.run_fixture(registration_sha, evaluator_sha)
                self.assertFalse(self.output.exists())

    def test_overlap_and_symlink_output_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            replay.validate_output(self.source, self.runtime, self.source / 'new')
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            replay.validate_output(self.source, self.runtime, self.runtime / 'new')
        if os.name != 'nt':
            alias = self.root / 'alias'
            alias.symlink_to(self.root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                replay.validate_output(self.source, self.runtime, alias / 'new')

    def test_inventory_observes_empty_directories_and_permission_changes(self):
        initial = replay.inventory(self.source)
        child = self.source / 'empty'
        child.mkdir()
        with_empty = replay.inventory(self.source)
        self.assertNotEqual(initial, with_empty)
        self.assertEqual(with_empty['empty']['kind'], 'directory')
        if os.name != 'nt':
            child.chmod(0o500)
            self.assertNotEqual(with_empty, replay.inventory(self.source))
            child.chmod(0o700)

    def test_inconsistent_or_fabricated_summary_cannot_be_accepted(self):
        cases = [{'id': 'known'}]
        for summary in (
                {'cases': 1, 'passed': 1, 'failed': ['known']},
                {'cases': 1, 'passed': 0, 'failed': ['unknown']},
                {'cases': True, 'passed': 1, 'failed': []},
                {'cases': 1, 'passed': True, 'failed': []}):
            with self.subTest(summary=summary):
                with self.assertRaises(ValueError):
                    replay.validate_summary(summary, cases)


if __name__ == '__main__':
    unittest.main()

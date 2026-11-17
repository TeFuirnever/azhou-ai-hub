from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'skills/super-session-insights/scripts/reflection.py'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def evidence():
    text = '交付前确认样例。'
    result = {'schema': 'super-session-insights.evidence.v1',
              'scope': {'question': '如何交接', 'selection': 'selected', 'omissions': 'unknown'},
              'sources': [{'id': 's1', 'type': 'conversation', 'imported_at': '2026-11-15', 'origin_id': 'unknown', 'completeness': 'partial'}],
              'segments': [{'id': 'e1', 'container_source_id': 's1', 'content_source_id': 's1', 'order': 1, 'container_role': 'user', 'speaker': 'user', 'attribution': 'self', 'kind': 'direct_statement', 'occurred_at': 'unknown', 'time_basis': 'unknown', 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'locator': 'turn-1'}],
              'relations': [], 'coverage': {'selected': 1, 'processed': 1, 'omissions': 'unknown'},
              'authorization': {'analysis': 'selected redacted text', 'disclosure': 'local report', 'tool_boundary': 'instruction_only', 'policy_reference': 'unknown'}}
    result['digest'] = digest(result)
    return result


def reflection(ev):
    ref = {'segment_id': 'e1', 'start': 0, 'end': 3, 'type': 'quote', 'text': '交付前'}
    return {'schema': 'super-session-insights.reflection.v1', 'evidence_digest': ev['digest'], 'status': 'limited',
            'observations': [{'claim': '要求交付前确认样例', 'refs': [ref], 'scope': 'selected conversation'}],
            'insights': [{'id': 'i1', 'claim': '样例可能有助于交接', 'epistemic_status': 'hypothesis', 'supporting_refs': [ref], 'counter_refs': [], 'alternatives': ['任务不同'], 'scope': 'selected conversation', 'revisit_condition': '出现反例'}],
            'changes': [], 'experiment': None, 'limitations': ['仅一段对话'], 'host': 'test', 'model': 'unknown'}


@unittest.skipUnless(os.name == 'posix' and os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'), 'secure reflection publication requires POSIX directory descriptors')
class ReflectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.ev = evidence()
        self.result = reflection(self.ev)
        self.write()

    def write(self):
        # Synthetic fixture bytes, not real credentials. codeql[py/clear-text-storage-sensitive-data]
        (self.root / 'evidence.json').write_text(json.dumps(self.ev, ensure_ascii=False), encoding='utf-8')
        # codeql[py/clear-text-storage-sensitive-data]
        (self.root / 'reflection.json').write_text(json.dumps(self.result, ensure_ascii=False), encoding='utf-8')

    def run_cli(self, command, *args):
        return subprocess.run([sys.executable, str(CLI), command, *args], cwd=self.root, text=True, encoding='utf-8', capture_output=True)

    def render(self, target='run'):
        return self.run_cli('render', '--evidence', 'evidence.json', '--input', 'reflection.json', '--out-dir', target)

    def test_complete_selected_input_to_readable_private_report(self):
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('样例可能有助于交接', report)
        receipt = json.loads((self.root / 'run/receipt.json').read_text())
        self.assertEqual('pass', receipt['verification']['structural_validation'])
        self.assertEqual('not_reviewed', receipt['verification']['semantic_review'])
        self.assertEqual('not_observed', receipt['verification']['outcome_evidence'])
        self.assertEqual(0o700, (self.root / 'run').stat().st_mode & 0o777)
        self.assertEqual(0o600, (self.root / 'run/report.md').stat().st_mode & 0o777)
        self.assertNotEqual(0, self.render().returncode)

    def test_bad_quote_or_changed_evidence_refuses_report_without_echo(self):
        self.result['insights'][0]['supporting_refs'][0]['text'] = 'private-seed'
        self.write()
        p = self.render()
        self.assertEqual(1, p.returncode)
        self.assertNotIn('private-seed', p.stdout + p.stderr)
        receipt = json.loads(p.stdout)
        self.assertEqual('fail', receipt['status'])
        self.assertEqual('fail', receipt['verification']['structural_validation'])
        self.assertFalse((self.root / 'run').exists())

    def test_cycle_and_dangling_sources_are_rejected(self):
        self.ev['relations'] = [{'from': 's1', 'to': 's1', 'type': 'derived_from'}]
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        p = self.run_cli('validate-evidence', '--input', 'evidence.json')
        self.assertEqual(1, p.returncode)

    def test_oversize_and_unknown_tool_boundary_fail_closed(self):
        self.ev['authorization']['tool_boundary'] = 'unknown'
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        self.assertEqual(1, self.render().returncode)
        self.ev['authorization']['tool_boundary'] = 'instruction_only'
        self.ev['segments'][0]['text'] = 'x' * 40001
        self.ev['segments'][0]['text_sha256'] = hashlib.sha256(self.ev['segments'][0]['text'].encode()).hexdigest()
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        self.assertEqual(1, self.render().returncode)

    def test_duplicate_json_key_and_unbound_evidence_are_rejected(self):
        payload = json.dumps(self.ev, ensure_ascii=False)
        marker = '"question":'
        payload = payload.replace(marker, marker + json.dumps(self.ev['scope']['question'], ensure_ascii=False) + ', ' + marker, 1)
        (self.root / 'evidence.json').write_text(payload, encoding='utf-8')
        self.assertEqual(1, self.run_cli('validate-evidence', '--input', 'evidence.json').returncode)
        self.ev['segments'][0]['text'] += 'changed'
        self.write()
        self.assertEqual(1, self.render().returncode)

    def test_prior_report_alone_cannot_upgrade_an_insight(self):
        self.ev['segments'][0]['kind'] = 'prior_report'
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.result['insights'][0]['epistemic_status'] = 'supported'
        self.write()
        self.assertEqual(1, self.render().returncode)

    def test_empty_evidence_requires_insufficient_status(self):
        self.ev['sources'] = []
        self.ev['segments'] = []
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result.update(evidence_digest=self.ev['digest'], status='insufficient_evidence', observations=[], insights=[])
        self.write()
        self.assertEqual(0, self.render().returncode)

    def test_exact_duplicate_segments_are_flagged_in_receipt(self):
        duplicate = dict(self.ev['segments'][0], id='e2', order=2)
        self.ev['segments'].append(duplicate)
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.write()
        self.assertEqual(0, self.render().returncode)
        receipt = json.loads((self.root / 'run/receipt.json').read_text())
        self.assertEqual([['e1', 'e2']], receipt['exact_duplicate_segments'])

    def test_secret_pattern_is_not_echoed_or_published(self):
        secret = 'ghp_' + 'X' * 30
        self.ev['segments'][0]['text'] = secret
        self.ev['segments'][0]['text_sha256'] = hashlib.sha256(secret.encode()).hexdigest()
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        p = self.render()
        self.assertEqual(1, p.returncode)
        self.assertNotIn(secret, p.stderr + p.stdout)
        self.assertFalse((self.root / 'run').exists())

    def test_sensitive_seed_in_model_result_cannot_reach_report(self):
        secret = 'sk-' + 'Z' * 32
        self.result['insights'][0]['claim'] = secret
        self.write()
        p = self.render()
        self.assertEqual(1, p.returncode)
        self.assertNotIn(secret, p.stdout + p.stderr)
        self.assertFalse((self.root / 'run').exists())

    def test_windows_home_path_is_rejected_and_not_echoed(self):
        text = 'C:\\Users\\bob\\secret-note'
        self.ev['segments'][0]['text'] = text
        self.ev['segments'][0]['text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        p = self.run_cli('validate-evidence', '--input', 'evidence.json')
        self.assertEqual(1, p.returncode)
        self.assertNotIn(text, p.stdout + p.stderr)

    def test_bare_home_paths_in_evidence_are_rejected_and_not_echoed(self):
        for text in ('/Users/bob', '/home/bob', 'C:\\Users\\bob'):
            with self.subTest(text=text):
                self.ev = evidence()
                self.result = reflection(self.ev)
                self.ev['segments'][0]['text'] = text
                self.ev['segments'][0]['text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
                self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
                self.write()
                p = self.run_cli('validate-evidence', '--input', 'evidence.json')
                self.assertEqual(1, p.returncode)
                self.assertNotIn(text, p.stdout + p.stderr)

    def test_bare_home_paths_in_reflection_are_rejected_and_not_echoed(self):
        for text in ('/Users/bob', '/home/bob', 'C:\\Users\\bob'):
            with self.subTest(text=text):
                self.ev = evidence()
                self.result = reflection(self.ev)
                self.result['insights'][0]['claim'] = text
                self.write()
                p = self.render()
                self.assertEqual(1, p.returncode)
                self.assertNotIn(text, p.stdout + p.stderr)
                self.assertFalse((self.root / 'run').exists())

    def test_windows_absolute_and_backslash_traversal_identifiers_are_rejected(self):
        for field, value in (('origin_id', 'C:\\Users\\bob\\proj'), ('origin_id', '..\\..\\proj'),
                             ('locator', 'C:\\Users\\bob\\rollout.jsonl'), ('locator', '..\\..\\rollout.jsonl')):
            with self.subTest(field=field, value=value):
                self.ev = evidence()
                (self.ev['sources'][0] if field == 'origin_id' else self.ev['segments'][0])[field] = value
                self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
                self.write()
                self.assertEqual(1, self.run_cli('validate-evidence', '--input', 'evidence.json').returncode)

    def test_unsafe_identifier_ids_are_rejected(self):
        for container, value in (('sources', '/var/folders/xy/T/sess-42'), ('sources', '..\\..\\proj'),
                                 ('segments', 'C:\\Temp\\sess.jsonl'), ('segments', '../../x')):
            with self.subTest(container=container, value=value):
                self.ev = evidence()
                self.ev[container][0]['id'] = value
                if container == 'sources':
                    for segment in self.ev['segments']:
                        segment['container_source_id'] = value
                        segment['content_source_id'] = value
                self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
                self.write()
                self.assertEqual(1, self.run_cli('validate-evidence', '--input', 'evidence.json').returncode)

    def test_unsafe_insight_and_change_ids_are_rejected(self):
        self.result['insights'][0]['id'] = '/var/folders/xy/T/ins'
        self.write()
        self.assertEqual(1, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)
        self.result = reflection(self.ev)
        prior = json.dumps({'schema': 'super-session-insights.reflection.v1', 'insights': [{'id': '/var/folders/xy/T/old', 'epistemic_status': 'hypothesis'}]}, ensure_ascii=False)
        self.ev['segments'].append(dict(self.ev['segments'][0], id='old', order=0, kind='prior_report', speaker='assistant', text=prior, text_sha256=hashlib.sha256(prior.encode()).hexdigest()))
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.result['changes'] = [{'prior_segment_id': 'old', 'previous_report_digest': hashlib.sha256(prior.encode()).hexdigest(),
                                   'previous_insight_id': '/var/folders/xy/T/old', 'current_insight_id': 'i1', 'type': 'revised',
                                   'old_status': 'hypothesis', 'new_status': 'hypothesis', 'reason': '范围缩小',
                                   'new_refs': self.result['insights'][0]['supporting_refs']}]
        self.write()
        self.assertEqual(1, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)

    def test_explicit_prior_report_and_insight_are_bound(self):
        prior = json.dumps({'schema': 'super-session-insights.reflection.v1', 'insights': [{'id': 'old1', 'epistemic_status': 'hypothesis'}]}, ensure_ascii=False)
        self.ev['segments'].append(dict(self.ev['segments'][0], id='old', order=0, kind='prior_report', speaker='assistant', text=prior, text_sha256=hashlib.sha256(prior.encode()).hexdigest()))
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.result['changes'] = [{'prior_segment_id': 'old', 'previous_report_digest': hashlib.sha256(prior.encode()).hexdigest(), 'previous_insight_id': 'old1', 'current_insight_id': 'i1', 'type': 'revised', 'old_status': 'hypothesis', 'new_status': 'hypothesis', 'reason': '范围缩小', 'new_refs': self.result['insights'][0]['supporting_refs']}]
        self.write()
        self.assertEqual(0, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)
        self.result['changes'][0]['previous_insight_id'] = 'missing'
        self.write()
        self.assertEqual(1, self.render().returncode)

    def test_coverage_cannot_claim_more_processed_than_selected(self):
        self.ev['coverage']['processed'] = 2
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.write()
        self.assertEqual(1, self.run_cli('validate-evidence', '--input', 'evidence.json').returncode)

    @unittest.skipUnless(os.name == 'posix' and os.open in os.supports_dir_fd, 'requires directory descriptors')
    def test_parent_replacement_cannot_redirect_private_artifacts(self):
        spec = importlib.util.spec_from_file_location('reflection_runtime', CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        approved = self.root / 'approved'
        moved = self.root / 'moved'
        outside = self.root / 'outside'
        approved.mkdir()
        outside.mkdir()
        real_open = module.open_parent
        def swap(*args):
            result = real_open(*args)
            approved.rename(moved)
            approved.symlink_to(outside, target_is_directory=True)
            return result
        with mock.patch.object(module, 'open_parent', side_effect=swap):
            with self.assertRaises(module.Invalid):
                module.render(self.ev, self.result, str(approved / 'run'))
        self.assertEqual([], list(outside.iterdir()))
        self.assertFalse((moved / 'run').exists())

    def test_parent_replacement_during_write_is_rejected_and_cleaned(self):
        spec = importlib.util.spec_from_file_location('reflection_runtime_write', CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        approved, moved, outside = (self.root / name for name in ('approved', 'moved', 'outside'))
        approved.mkdir()
        outside.mkdir()
        real_check = module.parent_matches
        calls = 0
        def swap_on_publish(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                approved.rename(moved)
                approved.symlink_to(outside, target_is_directory=True)
            return real_check(*args)
        with mock.patch.object(module, 'parent_matches', side_effect=swap_on_publish):
            with self.assertRaises(module.Invalid):
                module.render(self.ev, self.result, str(approved / 'run'))
        self.assertEqual([], list(outside.iterdir()))
        self.assertEqual([], list(moved.iterdir()))

    def test_parent_replacement_after_publish_leaves_no_success_receipt(self):
        spec = importlib.util.spec_from_file_location('reflection_runtime_after', CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        approved, moved, outside = (self.root / name for name in ('approved', 'moved', 'outside'))
        approved.mkdir()
        outside.mkdir()
        real_check = module.parent_matches
        calls = 0
        def swap_after_publish(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                approved.rename(moved)
                approved.symlink_to(outside, target_is_directory=True)
            return real_check(*args)
        with mock.patch.object(module, 'parent_matches', side_effect=swap_after_publish):
            with self.assertRaises(module.Invalid):
                module.render(self.ev, self.result, str(approved / 'run'))
        self.assertEqual([], list(outside.iterdir()))
        self.assertEqual([], list(moved.iterdir()))

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX mode bits')
    def test_shared_writable_parent_is_rejected(self):
        shared = self.root / 'shared'
        shared.mkdir(mode=0o777)
        shared.chmod(0o777)
        self.assertEqual(1, self.render('shared/run').returncode)
        self.assertEqual([], list(shared.iterdir()))

    def test_citation_review_exposes_only_cited_unicode_spans_and_attribution(self):
        self.ev['scope']['subject'] = 'selected participant'
        self.ev['segments'][0]['container_role'] = 'user'
        self.ev['segments'][0]['speaker'] = 'assistant'
        self.ev['segments'][0]['attribution'] = 'third_party'
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.write()
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, p.returncode, p.stderr)
        review = json.loads(p.stdout)
        self.assertEqual('not_reviewed', review['semantic_review'])
        self.assertEqual('selected participant', review['subject'])
        entry = next(x for x in review['claims'] if x['kind'] == 'insight')
        self.assertEqual(self.result['insights'][0]['claim'], entry['claim'])
        ref = entry['supporting_refs'][0]
        self.assertEqual('交付前', ref['cited_text'])
        self.assertEqual(('user', 'assistant', 'third_party'), (ref['container_role'], ref['speaker'], ref['attribution']))
        self.assertNotIn('确认样例', json.dumps(ref, ensure_ascii=False))

    def test_citation_review_rejects_unbound_or_secret_evidence(self):
        self.result['evidence_digest'] = 'wrong'
        self.write()
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(1, p.returncode)
        self.assertEqual('', p.stdout)
        self.result['evidence_digest'] = self.ev['digest']
        self.ev['segments'][0]['text'] = 'ghp_' + 'X' * 30
        self.ev['segments'][0]['text_sha256'] = hashlib.sha256(self.ev['segments'][0]['text'].encode()).hexdigest()
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.write()
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(1, p.returncode)
        self.assertNotIn(self.ev['segments'][0]['text'], p.stdout + p.stderr)

    def test_citation_review_includes_the_complete_reported_insight(self):
        self.result['insights'][0]['alternatives'] = ['另一人可能负责确认']
        self.result['insights'][0]['revisit_condition'] = '核对交接记录后再判断'
        self.write()
        review_result = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, review_result.returncode, review_result.stderr)
        review = json.loads(review_result.stdout)
        insight = next(x for x in review['claims'] if x['kind'] == 'insight')
        expected = self.result['insights'][0]
        self.assertEqual(expected['epistemic_status'], insight['epistemic_status'])
        self.assertEqual(expected['alternatives'], insight['alternatives'])
        self.assertEqual(expected['revisit_condition'], insight['revisit_condition'])
        self.assertEqual('交付前', insight['supporting_refs'][0]['cited_text'])
        self.assertEqual('not_reviewed', review['semantic_review'])
        rendered = self.render()
        self.assertEqual(0, rendered.returncode, rendered.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn(expected['alternatives'][0], report)
        self.assertIn(expected['revisit_condition'], report)

    def test_citation_review_exposes_report_limits_and_experiment_without_extra_metadata(self):
        self.result['limitations'] = ['交接记录未确认']
        self.result['experiment'] = {
            'change': '核对样例', 'context': '交接', 'expected_observation': '确认是否完成',
            'effort': '一次', 'success_condition': '样例可用', 'stop_condition': '无权访问时停止',
            'followup_evidence': '交接记录', 'unverified_extra': 'do not echo extra metadata',
        }
        self.write()
        reviewed = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, reviewed.returncode, reviewed.stderr)
        review = json.loads(reviewed.stdout)
        self.assertEqual(self.result['limitations'], review['limitations'])
        self.assertIsNone(review['limitation_refs'])
        self.assertIsNone(review['experiment_refs'])
        self.assertEqual('核对样例', review['experiment']['change'])
        self.assertEqual('交接记录', review['experiment']['followup_evidence'])
        self.assertNotIn('unverified_extra', review['experiment'])
        self.assertEqual('not_reviewed', review['semantic_review'])
        rendered = self.render()
        self.assertEqual(0, rendered.returncode, rendered.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('交接记录未确认', report)
        self.assertIn('核对样例', report)
        self.result['experiment'] = None
        self.write()
        without_experiment = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, without_experiment.returncode, without_experiment.stderr)
        self.assertIsNone(json.loads(without_experiment.stdout)['experiment'])

    def test_omitted_experiment_key_fails_validation(self):
        del self.result['experiment']
        self.write()
        validated = self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(1, validated.returncode)
        reviewed = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(1, reviewed.returncode)
        rendered = self.render()
        self.assertEqual(1, rendered.returncode)
        self.assertEqual('fail', json.loads(rendered.stdout)['status'])

    def test_limitations_and_experiment_can_bind_individual_citations(self):
        ref = {'segment_id': 'e1', 'start': 0, 'end': 3, 'type': 'quote', 'text': '交付前'}
        self.result['limitations'] = ['交付前的要求仅来自所选片段', '没有额外记录']
        self.result['limitation_refs'] = [[ref], []]
        self.result['experiment'] = {
            'change': '确认样例', 'context': '交付前', 'expected_observation': '是否有纠正',
            'effort': '一次', 'success_condition': '样例可用', 'stop_condition': '产生额外负担时停止',
            'followup_evidence': '交接结果', 'unverified_extra': 'do not publish extra metadata',
        }
        self.result['experiment_refs'] = {'context': [ref]}
        self.write()
        result = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, result.returncode, result.stderr)
        review = json.loads(result.stdout)
        self.assertEqual('交付前', review['limitation_refs'][0][0]['cited_text'])
        self.assertEqual([], review['limitation_refs'][1])
        self.assertEqual('self', review['experiment_refs']['context'][0]['attribution'])
        self.assertEqual('not_reviewed', review['semantic_review'])
        self.assertNotIn('确认样例', json.dumps(review['limitation_refs'], ensure_ascii=False))
        self.assertEqual(0, self.render().returncode)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('交付前的要求仅来自所选片段 [e1[0:3]]', report)
        self.assertIn('适用情境：交付前 [e1[0:3]]', report)
        self.assertNotIn('do not publish extra metadata', report)

    def test_optional_item_citations_reject_mismatch_without_echo(self):
        self.result['limitation_refs'] = []
        self.write()
        self.assertEqual(1, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)
        self.result['limitation_refs'] = [[{'segment_id': 'e1', 'start': 0, 'end': 3, 'type': 'quote', 'text': 'private-seed'}]]
        self.write()
        result = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(1, result.returncode)
        self.assertNotIn('private-seed', result.stdout + result.stderr)
        del self.result['limitation_refs']
        self.result['experiment_refs'] = {'context': []}
        self.write()
        self.assertEqual(1, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)
        self.result['experiment'] = {'change': 'a', 'context': 'b', 'expected_observation': 'c', 'effort': 'd',
                                     'success_condition': 'e', 'stop_condition': 'f', 'followup_evidence': 'g'}
        self.result['experiment_refs'] = {'unrecognized': []}
        self.write()
        self.assertEqual(1, self.run_cli('validate-reflection', '--evidence', 'evidence.json', '--input', 'reflection.json').returncode)

    def test_report_keeps_limitations_and_provenance_without_empty_sections(self):
        self.ev['scope']['subject'] = 'selected participant'
        self.ev['segments'][0]['attribution'] = 'third_party'
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.write()
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('样例可能有助于交接', report)
        self.assertIn('仅一段对话', report)
        self.assertIn('third_party', report)
        self.assertIn('selected participant', report)
        self.assertIn('e1[0:3]', report)
        self.assertNotIn('## 与旧理解的关系', report)
        self.assertNotIn('## 可选实验', report)

    def test_report_preserves_nonempty_experiment_and_status(self):
        self.result['experiment'] = {'change': '核对样例', 'context': '交接', 'expected_observation': '是否有纠正', 'effort': '一次', 'success_condition': '样例可用', 'stop_condition': '产生额外负担时停止', 'followup_evidence': '交接结果'}
        self.write()
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('状态：limited', report)
        self.assertIn('核对样例', report)
        self.assertIn('产生额外负担时停止', report)
        self.assertIn('交接结果', report)

    def test_citation_review_keeps_unsupplied_subject_unknown(self):
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, p.returncode, p.stderr)
        review = json.loads(p.stdout)
        self.assertEqual('unknown', review['subject'])
        self.assertEqual('not_reviewed', review['semantic_review'])

    def test_short_report_retains_observations_and_limits(self):
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertIn('要求交付前确认样例', report)
        self.assertIn('查看观察与来源', report)
        self.assertLess(report.index('仅一段对话'), report.index('<details>'))
        self.assertIn('容器角色=user', report)
        self.assertIn('发言者=user', report)
        self.assertIn('归属=self', report)

    def test_report_omits_exact_duplicate_observations_but_keeps_distinct_scopes(self):
        first = self.result['observations'][0]
        self.result['insights'] = []
        self.result['observations'] += [dict(first), {**first, 'scope': 'another selection'}]
        self.write()
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertEqual(2, report.count(first['claim']))
        self.assertIn('another selection', report)
        saved = json.loads((self.root / 'run/reflection.json').read_text(encoding='utf-8'))
        self.assertEqual(3, len(saved['observations']))

    def test_report_keeps_observations_with_distinct_citations(self):
        first = self.result['observations'][0]
        other = {**first, 'refs': [{'segment_id': 'e1', 'start': 0, 'end': 2, 'type': 'quote', 'text': '交付'}]}
        self.result['observations'] += [dict(first), other]
        self.write()
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        report = (self.root / 'run/report.md').read_text(encoding='utf-8')
        self.assertEqual(2, report.count(first['claim']))
        self.assertIn('e1[0:3]', report)
        self.assertIn('e1[0:2]', report)

    def test_citation_review_preserves_counter_reference_ranges(self):
        self.result['insights'][0]['counter_refs'] = [{'segment_id': 'e1', 'start': 3, 'end': 5, 'type': 'paraphrase'}]
        self.write()
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, p.returncode, p.stderr)
        insight = next(x for x in json.loads(p.stdout)['claims'] if x['kind'] == 'insight')
        self.assertEqual('确认', insight['counter_refs'][0]['cited_text'])
        self.assertEqual((3, 5), (insight['counter_refs'][0]['start'], insight['counter_refs'][0]['end']))

    def test_citation_review_does_not_echo_unverified_paraphrase_metadata(self):
        ref = self.result['insights'][0]['supporting_refs'][0]
        ref['type'] = 'paraphrase'
        ref['text'] = 'unverified paraphrase text'
        ref['source_claim'] = 'unverified source claim'
        self.write()
        p = self.run_cli('review-citations', '--evidence', 'evidence.json', '--input', 'reflection.json')
        self.assertEqual(0, p.returncode, p.stderr)
        insight = next(x for x in json.loads(p.stdout)['claims'] if x['kind'] == 'insight')
        result_ref = insight['supporting_refs'][0]
        self.assertEqual('交付前', result_ref['cited_text'])
        self.assertNotIn('text', result_ref)
        self.assertNotIn('source_claim', result_ref)

    def test_receipt_does_not_claim_to_verify_host_tool_isolation(self):
        self.ev['authorization']['tool_boundary'] = 'host_enforced'
        self.ev['digest'] = digest({k: v for k, v in self.ev.items() if k != 'digest'})
        self.result['evidence_digest'] = self.ev['digest']
        self.write()
        p = self.render()
        self.assertEqual(0, p.returncode, p.stderr)
        receipt = json.loads((self.root / 'run/receipt.json').read_text(encoding='utf-8'))
        self.assertEqual('host_enforced', receipt['authorization']['tool_boundary'])
        self.assertEqual('not_verified', receipt['verification']['tool_boundary_verification'])

    def test_symlink_and_traversal_rejected(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(1, self.render('link/run').returncode)
        self.assertEqual(1, self.render('../outside').returncode)

if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Validate explicitly selected evidence and render a local reflection report."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys

EVIDENCE = 'super-session-insights.evidence.v1'
REFLECTION = 'super-session-insights.reflection.v1'
RECEIPT = 'super-session-insights.reflection-receipt.v1'
UNKNOWN = 'unknown'
EXPERIMENT_FIELDS = ('change', 'context', 'expected_observation', 'effort', 'success_condition', 'stop_condition', 'followup_evidence')
SENSITIVE = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})|https?://[^\s"<>]+|(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}|/(?:Users|home)/[^/\s]+/|[A-Za-z]:\\Users\\[^\\\s]+\\',
    re.IGNORECASE,
)


class Invalid(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise Invalid(reason)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid('invalid JSON number')))
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise Invalid('cannot read valid UTF-8 JSON') from None


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def fields(obj, names):
    require(isinstance(obj, dict) and all(nonempty(obj.get(k)) for k in names), 'missing required text field')


def ids(items):
    require(isinstance(items, list), 'expected list')
    result = {}
    for item in items:
        fields(item, ['id'])
        require(item['id'] not in result, 'duplicate id')
        result[item['id']] = item
    return result


def validate_evidence(e):
    require(isinstance(e, dict) and e.get('schema') == EVIDENCE, 'invalid evidence schema')
    require(not SENSITIVE.search(canonical(e).decode('utf-8')), 'sensitive pattern detected')
    require(e.get('digest') == sha(canonical({k: v for k, v in e.items() if k != 'digest'})), 'evidence digest mismatch')
    fields(e.get('scope'), ['question', 'selection', 'omissions'])
    if 'subject' in e['scope']:
        fields(e['scope'], ['subject'])
    fields(e.get('authorization'), ['analysis', 'disclosure', 'tool_boundary', 'policy_reference'])
    auth = e['authorization']
    require(auth['tool_boundary'] in ('host_enforced', 'instruction_only', 'unknown'), 'invalid tool boundary')
    fields(e.get('coverage'), ['omissions'])
    coverage = e['coverage']
    for key in ('selected', 'processed'):
        require(coverage.get(key) == UNKNOWN or (type(coverage.get(key)) is int and coverage[key] >= 0), 'invalid coverage')
    if type(coverage['selected']) is int and type(coverage['processed']) is int:
        require(coverage['processed'] <= coverage['selected'], 'invalid coverage')
    sources = ids(e.get('sources'))
    segments = ids(e.get('segments'))
    require(len(sources) <= 8, 'oversize: reduce sources')
    require(sum(len(s.get('text', '')) for s in segments.values() if isinstance(s.get('text'), str)) <= 40000, 'oversize: reduce text')
    for s in sources.values():
        fields(s, ['type', 'imported_at', 'origin_id', 'completeness'])
        require(not s['origin_id'].startswith('/') and '..' not in Path(s['origin_id']).parts, 'unsafe source identifier')
    for s in segments.values():
        fields(s, ['container_source_id', 'content_source_id', 'container_role', 'speaker', 'attribution', 'kind', 'occurred_at', 'time_basis', 'text', 'text_sha256', 'locator'])
        require(s['container_source_id'] in sources and (s['content_source_id'] in sources or s['content_source_id'] == UNKNOWN), 'unknown source')
        require(type(s.get('order')) is int and s['order'] >= 0, 'invalid segment order')
        require(s['container_role'] in ('user', 'assistant', 'tool', UNKNOWN) and s['speaker'] in ('user', 'assistant', 'tool', UNKNOWN), 'invalid role')
        require(s['attribution'] in ('self', 'third_party', UNKNOWN), 'invalid attribution')
        require(s['kind'] in ('direct_statement', 'artifact_observation', 'quoted_material', 'interpretation', 'retrospective_summary', 'prior_report'), 'invalid kind')
        require(s['time_basis'] in ('source_metadata', 'user_declared', 'quoted_claim', UNKNOWN), 'invalid time basis')
        require(s['time_basis'] != UNKNOWN or s['occurred_at'] == UNKNOWN, 'unknown time basis')
        require(s['text_sha256'] == sha(s['text'].encode('utf-8')), 'segment digest mismatch')
        require(not s['locator'].startswith('/') and '..' not in Path(s['locator']).parts, 'unsafe locator')
    relations = e.get('relations')
    require(isinstance(relations, list), 'invalid relations')
    nodes = set(sources) | set(segments)
    require(not (set(sources) & set(segments)), 'ambiguous id')
    graph = {n: [] for n in nodes}
    for relation in relations:
        fields(relation, ['from', 'to', 'type'])
        require(relation['from'] in nodes and relation['to'] in nodes, 'dangling relation')
        require(relation['type'] in ('quotes', 'summarizes', 'duplicates', 'derived_from'), 'invalid relation')
        graph[relation['from']].append(relation['to'])
    visited, active = set(), set()
    def visit(node):
        require(node not in active, 'cyclic relation')
        if node in visited:
            return
        active.add(node)
        for child in graph[node]:
            visit(child)
        active.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    return sources, segments


def check_refs(refs, segments, required=False):
    require(isinstance(refs, list) and (refs or not required), 'missing evidence references')
    for ref in refs:
        fields(ref, ['segment_id', 'type'])
        segment = segments.get(ref['segment_id'])
        require(segment is not None, 'unknown evidence reference')
        start, end = ref.get('start'), ref.get('end')
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(segment['text']), 'invalid reference range')
        require(ref['type'] in ('quote', 'paraphrase'), 'invalid reference type')
        if ref['type'] == 'quote':
            require(ref.get('text') == segment['text'][start:end], 'quote mismatch')


def validate_reflection(e, result):
    sources, segments = validate_evidence(e)
    require(isinstance(result, dict) and result.get('schema') == REFLECTION, 'invalid reflection schema')
    require(not SENSITIVE.search(canonical(result).decode('utf-8')), 'sensitive pattern detected')
    require(result.get('evidence_digest') == e['digest'], 'reflection evidence mismatch')
    require(result.get('status') in ('complete', 'limited', 'insufficient_evidence', 'hold'), 'invalid status')
    require(e['authorization']['tool_boundary'] != UNKNOWN, 'hold: tool boundary unknown')
    fields(result, ['host', 'model'])
    observations = result.get('observations')
    require(isinstance(observations, list), 'invalid observations')
    for observation in observations:
        fields(observation, ['claim', 'scope'])
        check_refs(observation.get('refs'), segments, True)
    insights = ids(result.get('insights'))
    require(len(insights) <= 3, 'too many insights')
    for insight in insights.values():
        fields(insight, ['claim', 'epistemic_status', 'scope', 'revisit_condition'])
        require(insight['epistemic_status'] in ('hypothesis', 'supported', 'disputed', 'withdrawn'), 'invalid insight status')
        check_refs(insight.get('supporting_refs'), segments, True)
        check_refs(insight.get('counter_refs'), segments)
        require(isinstance(insight.get('alternatives'), list) and all(nonempty(x) for x in insight['alternatives']), 'invalid alternatives')
        if insight['epistemic_status'] == 'supported':
            require(any(segments[r['segment_id']]['kind'] not in ('prior_report', 'interpretation', 'retrospective_summary') for r in insight['supporting_refs']), 'prior interpretation alone cannot support status')
    require(isinstance(result.get('limitations'), list) and all(nonempty(x) for x in result['limitations']), 'invalid limitations')
    if 'limitation_refs' in result:
        groups = result['limitation_refs']
        require(isinstance(groups, list) and len(groups) == len(result['limitations']), 'invalid limitation references')
        for group in groups:
            check_refs(group, segments)
    if not segments:
        require(result['status'] in ('insufficient_evidence', 'hold') and not observations and not insights, 'empty evidence requires insufficient status')
    experiment = result.get('experiment')
    if experiment is not None:
        fields(experiment, EXPERIMENT_FIELDS)
    if 'experiment_refs' in result:
        groups = result['experiment_refs']
        require(experiment is not None and isinstance(groups, dict) and all(k in EXPERIMENT_FIELDS for k in groups), 'invalid experiment references')
        for group in groups.values():
            check_refs(group, segments)
    changes = result.get('changes')
    require(isinstance(changes, list), 'invalid changes')
    # Previous reports must be supplied as evidence; never load a path from a result.
    for change in changes:
        fields(change, ['previous_report_digest', 'previous_insight_id', 'current_insight_id', 'type', 'old_status', 'new_status', 'reason', 'prior_segment_id'])
        prior = segments.get(change['prior_segment_id'])
        require(prior is not None and prior['kind'] == 'prior_report' and prior['text_sha256'] == change['previous_report_digest'], 'prior report not supplied')
        try:
            old = json.loads(prior['text'], object_pairs_hook=unique_pairs)
        except (ValueError, TypeError):
            raise Invalid('invalid prior report') from None
        require(isinstance(old, dict) and old.get('schema') == REFLECTION and isinstance(old.get('insights'), list), 'invalid prior report')
        require(any(i.get('id') == change['previous_insight_id'] and i.get('epistemic_status') == change['old_status'] for i in old.get('insights', []) if isinstance(i, dict)), 'prior insight not found')
        require(change['current_insight_id'] in insights and insights[change['current_insight_id']]['epistemic_status'] == change['new_status'], 'current insight not found')
        check_refs(change.get('new_refs'), segments, True)
    return sources, segments


def package_digest():
    root = Path(__file__).resolve().parent.parent
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and not path.is_symlink():
            entries.append([path.relative_to(root).as_posix(), sha(path.read_bytes())])
    return sha(canonical(entries))


def exact_duplicates(e):
    groups = {}
    for segment in e['segments']:
        groups.setdefault(segment['text_sha256'], []).append(segment['id'])
    return sorted(sorted(group) for group in groups.values() if len(group) > 1)


def citation_review(e, result, segments):
    def excerpts(refs):
        output = []
        for ref in refs:
            segment = segments[ref['segment_id']]
            entry = {key: ref[key] for key in ('segment_id', 'start', 'end', 'type')}
            entry.update({key: segment[key] for key in (
                'container_source_id', 'content_source_id', 'container_role', 'speaker',
                'attribution', 'kind', 'occurred_at', 'time_basis', 'locator')})
            entry['cited_text'] = segment['text'][ref['start']:ref['end']]
            output.append(entry)
        return output

    claims = []
    for observation in result['observations']:
        claims.append({'kind': 'observation', 'claim': observation['claim'],
                       'scope': observation['scope'], 'refs': excerpts(observation['refs'])})
    for insight in result['insights']:
        claims.append({'kind': 'insight', 'id': insight['id'], 'claim': insight['claim'],
                       'scope': insight['scope'], 'epistemic_status': insight['epistemic_status'],
                       'alternatives': insight['alternatives'], 'revisit_condition': insight['revisit_condition'],
                       'supporting_refs': excerpts(insight['supporting_refs']),
                       'counter_refs': excerpts(insight['counter_refs'])})
    for change in result['changes']:
        claims.append({'kind': 'change', 'claim': change['reason'], 'refs': excerpts(change['new_refs'])})
    experiment = result.get('experiment')
    if experiment is not None:
        experiment = {key: experiment[key] for key in EXPERIMENT_FIELDS}
    limitation_refs = result.get('limitation_refs')
    experiment_refs = result.get('experiment_refs')
    return {'schema': 'super-session-insights.citation-review.v1', 'evidence_digest': e['digest'],
            'subject': e['scope'].get('subject', UNKNOWN), 'semantic_review': 'not_reviewed', 'claims': claims,
            'limitations': result['limitations'], 'experiment': experiment,
            'limitation_refs': None if limitation_refs is None else [excerpts(group) for group in limitation_refs],
            'experiment_refs': None if experiment_refs is None else {key: excerpts(group) for key, group in experiment_refs.items()}}


def report_text(e, r):
    def refs(items):
        return ', '.join(f"{x['segment_id']}[{x['start']}:{x['end']}]" for x in items)

    observations = list({canonical(obs): obs for obs in r['observations']}.values())
    scopes = {}
    for obs in observations:
        scopes.setdefault((obs['claim'], canonical(obs['refs'])), set()).add(obs['scope'])

    def observation_line(obs):
        line = '- ' + obs['claim'] + ' [' + refs(obs['refs']) + ']'
        if len(scopes[(obs['claim'], canonical(obs['refs']))]) > 1:
            line += ' / 范围：' + obs['scope']
        return line

    lines = ['# 跨会话反思', '', '状态：' + r['status'], '', e['scope']['question'], '', '范围：' + e['scope']['selection']]
    if 'subject' in e['scope']:
        lines += ['分析对象：' + e['scope']['subject']]
    lines += ['遗漏：' + e['scope']['omissions']]
    if r['insights']:
        lines += ['', '## 值得核对的理解']
        for i in r['insights']:
            lines += ['', '### ' + i['claim'], '状态：' + i['epistemic_status'],
                      '范围：' + i['scope'], '依据：' + refs(i['supporting_refs'])]
            if i['counter_refs']:
                lines += ['反例：' + refs(i['counter_refs'])]
            if i['alternatives']:
                lines += ['其他解释：' + '；'.join(i['alternatives'])]
            lines += ['何时重看：' + i['revisit_condition']]
    elif observations:
        lines += ['', '## 观察']
        lines += [observation_line(obs) for obs in observations]
    else:
        lines += ['', '目前没有可报告的观察。']
    if r['changes']:
        lines += ['', '## 与旧理解的关系'] + ['- ' + x['reason'] for x in r['changes']]
    if r['experiment']:
        labels = {'change': '尝试', 'context': '适用情境', 'expected_observation': '观察',
                  'effort': '投入', 'success_condition': '成功条件', 'stop_condition': '停止条件',
                  'followup_evidence': '后续证据'}
        groups = r.get('experiment_refs', {})
        lines += ['', '## 可选实验'] + [f'- {labels[k]}：{r["experiment"][k]}' + (f' [{refs(groups[k])}]' if groups.get(k) else '') for k in EXPERIMENT_FIELDS]
    if r['limitations']:
        groups = r.get('limitation_refs', [[] for _ in r['limitations']])
        lines += ['', '## 限制'] + ['- ' + text + (f' [{refs(group)}]' if group else '') for text, group in zip(r['limitations'], groups)]
    if exact_duplicates(e):
        lines += ['', '存在精确重复片段；不能仅凭不同 ID 视为独立支持。']
    lines += ['', '<details>', '<summary>查看观察与来源</summary>', '']
    if r['insights'] and observations:
        lines += ['### 观察'] + [observation_line(obs) for obs in observations] + ['']
    lines += ['### 来源索引']
    lines += ['- ' + s['id'] + '：容器=' + s['container_source_id'] + ' / 内容来源=' + s['content_source_id']
              + ' / 容器角色=' + s['container_role'] + ' / 发言者=' + s['speaker']
              + ' / 归属=' + s['attribution'] + ' / 时间依据=' + s['time_basis'] + ' / ' + s['locator']
              for s in e['segments']]
    lines += ['', '</details>', '', '结构检查不等于语义审阅或工作流效果验证。分享前请人工检查敏感信息。', '']
    return '\n'.join(lines).encode('utf-8')


def open_directory(path):
    require(os.name == 'posix' and os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'),
            'secure directory publication unavailable')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_parent(raw):
    path = Path(raw)
    require('..' not in path.parts and path.name not in ('', '.', '..'), 'unsafe output path')
    path = Path(os.path.abspath(path))
    return open_directory(path.parent), path.name, path.parent


def parent_matches(fd, path):
    try:
        check = open_directory(path)
    except OSError:
        raise Invalid('output parent changed') from None
    try:
        actual, current = os.fstat(fd), os.fstat(check)
        require((actual.st_dev, actual.st_ino) == (current.st_dev, current.st_ino), 'output parent changed')
    finally:
        os.close(check)


def publish_exclusive(parent_fd, source, dest):
    # Both supported calls publish relative to the pinned directory, without replacement.
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin' and hasattr(libc, 'renameatx_np'):
        call = libc.renameatx_np
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = call(parent_fd, os.fsencode(source), parent_fd, os.fsencode(dest), 0x00000004)
    elif sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        call = libc.renameat2
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = call(parent_fd, os.fsencode(source), parent_fd, os.fsencode(dest), 1)
    else:
        raise Invalid('exclusive directory publication unavailable')
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def render(e, r, target):
    validate_reflection(e, r)
    parent_fd, dest, parent = open_parent(target)
    temp_name = None
    temp_fd = None
    published = False
    complete = False
    temp_stat = None
    try:
        parent_stat = os.fstat(parent_fd)
        require(parent_stat.st_uid == os.geteuid() and not (parent_stat.st_mode & 0o022), 'output parent is not private to owner')
        parent_matches(parent_fd, parent)
        for _ in range(10):
            candidate = '.reflection-' + secrets.token_hex(12)
            try:
                os.mkdir(candidate, 0o700, dir_fd=parent_fd)
                temp_name = candidate
                break
            except FileExistsError:
                continue
        require(temp_name is not None, 'cannot create private temporary directory')
        temp_fd = os.open(temp_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        os.fchmod(temp_fd, 0o700)
        temp_stat = os.fstat(temp_fd)
        files = {'evidence.json': canonical(e) + b'\n', 'reflection.json': canonical(r) + b'\n', 'report.md': report_text(e, r)}
        receipt = {'schema': RECEIPT, 'status': r['status'], 'evidence_digest': e['digest'], 'package_digest': package_digest(), 'host': r['host'], 'model': r['model'], 'authorization': e['authorization'], 'coverage': e['coverage'], 'artifacts': {name: sha(data) for name, data in files.items()}, 'exact_duplicate_segments': exact_duplicates(e), 'verification': {'structural_validation': 'pass', 'semantic_review': 'not_reviewed', 'outcome_evidence': 'not_observed', 'tool_boundary_verification': 'not_verified'}, 'holds': [] if r['status'] != 'hold' else ['reflection held'], 'next_action': 'Review the report and its privacy before sharing.', 'learning_signal': 'none', 'retention': 'Files remain in this run directory until the user removes them.'}
        files['receipt.json'] = canonical(receipt) + b'\n'
        for name, data in files.items():
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=temp_fd)
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=temp_fd)
            with os.fdopen(fd, 'rb') as f:
                require(f.read() == data, 'artifact readback failed')
        parent_matches(parent_fd, parent)
        publish_exclusive(parent_fd, temp_name, dest)
        published = True
        parent_matches(parent_fd, parent)
        complete = True
    finally:
        if temp_fd is not None:
            if not complete:
                for name in ('evidence.json', 'reflection.json', 'report.md', 'receipt.json'):
                    try:
                        os.unlink(name, dir_fd=temp_fd)
                    except FileNotFoundError:
                        pass
            os.close(temp_fd)
        if temp_name is not None and not complete:
            name = dest if published else temp_name
            try:
                entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if temp_stat is not None and (entry.st_dev, entry.st_ino) == (temp_stat.st_dev, temp_stat.st_ino):
                    os.rmdir(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('validate-evidence')
    p.add_argument('--input', required=True)
    for command in ('validate-reflection', 'review-citations', 'render'):
        p = sub.add_parser(command)
        p.add_argument('--evidence', required=True)
        p.add_argument('--input', required=True)
        if command == 'render':
            p.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    e = result = None
    try:
        if args.command == 'validate-evidence':
            validate_evidence(read_json(args.input))
        else:
            e, result = read_json(args.evidence), read_json(args.input)
            if args.command == 'render':
                render(e, result, args.out_dir)
            else:
                _, segments = validate_reflection(e, result)
                if args.command == 'review-citations':
                    print(json.dumps(citation_review(e, result, segments), ensure_ascii=True, sort_keys=True))
                    return 0
        print('structural_validation=pass')
        return 0
    except (Invalid, OSError, ValueError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, Invalid) else 'invalid input or output'
        print('structural_validation=fail: ' + reason, file=sys.stderr)
        if args.command == 'render':
            try:
                evidence_hash = sha(canonical(e)) if e is not None else UNKNOWN
                result_hash = sha(canonical(result)) if result is not None else UNKNOWN
            except (ValueError, TypeError, UnicodeError, RecursionError):
                evidence_hash = result_hash = UNKNOWN
            receipt = {'schema': RECEIPT, 'status': 'fail', 'input_evidence_sha256': evidence_hash,
                       'input_reflection_sha256': result_hash, 'artifacts': {},
                       'verification': {'structural_validation': 'fail', 'semantic_review': 'not_reviewed', 'outcome_evidence': 'not_observed', 'tool_boundary_verification': 'not_verified'},
                       'holds': [reason], 'next_action': 'Review the failed input or output boundary.', 'learning_signal': 'none'}
            print(json.dumps(receipt, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

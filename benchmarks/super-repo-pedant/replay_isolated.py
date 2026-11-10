#!/usr/bin/env python3
"""Replay the reviewed 2026-11-10 synthetic evaluator without editing its corpus.

Development-only adapter: path remapping is a new declared experiment, not a
retroactive change to the frozen registration or an OS sandbox. Exit zero means
the isolated replay completed; effect_status separately records case outcomes.
The timeout bounds the direct evaluator process, not descendant cleanup.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

EVALUATOR_SHA256 = '9da187226fb46479591963b55aa3316469ac8936ff810b04f2f483e89a233469'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entry(path: Path) -> dict:
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        return {'kind': 'symlink', 'target': os.readlink(path), 'mode': mode}
    if stat.S_ISREG(info.st_mode):
        return {'kind': 'file', 'sha256': sha(path.read_bytes()),
                'bytes': info.st_size, 'mode': mode}
    if stat.S_ISDIR(info.st_mode):
        return {'kind': 'directory', 'mode': mode}
    raise ValueError('unsupported filesystem entry: ' + str(path))


def inventory(root: Path) -> dict:
    """Include empty directories, root permissions, symlinks and file bytes."""
    result = {'.': entry(root)}
    if result['.']['kind'] != 'directory':
        return result

    def inaccessible(error: OSError) -> None:
        raise error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=inaccessible):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = entry(path)
    return result


def inventory_digest(value: dict) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8'))


def publish(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    path.chmod(0o600)


def validate_output(source: Path, runtime: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError('output must not exist; never reuse or delete previous runs')
    resolved = output.resolve()
    if any(resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in (source, runtime)):
        raise ValueError('output overlaps frozen corpus or runtime')
    for parent in output.parents:
        if parent.is_symlink():
            raise ValueError('output ancestor must not be a symlink')


def checked_input(root: Path, name: str, expected: str) -> bytes:
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('unsafe frozen input path')
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('frozen input cannot traverse a symlink')
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError('frozen input digest mismatch: ' + name)
    return data


def immutable_copies(workspace: Path, runtime: Path, cases: list[dict]) -> dict:
    protocol = {name: entry(workspace / name) for name in (
        'frozen_evaluator.py', 'cases.json', 'prepared-inputs.json',
        'baseline-manifest.json', 'preregistration.json')}
    inputs = {case['id']: inventory(workspace / 'inputs' / case['id'] / 'frozen')
              for case in cases}
    return {'protocol': protocol, 'inputs': inputs, 'runtime': inventory(runtime)}


def validate_summary(summary: object, cases: list[dict]) -> None:
    if not isinstance(summary, dict):
        raise ValueError('evaluator summary must be an object')
    count, passed, failed = (summary.get(key) for key in ('cases', 'passed', 'failed'))
    ids = {case['id'] for case in cases}
    if (type(count) is not int or count != len(cases) or type(passed) is not int
            or not 0 <= passed <= count or not isinstance(failed, list)
            or any(not isinstance(item, str) or item not in ids for item in failed)
            or len(set(failed)) != len(failed) or len(failed) != count - passed):
        raise ValueError('evaluator case counts or failed identities are inconsistent')


def replay(source: Path, runtime: Path, output: Path, registration_sha: str) -> dict:
    source, runtime = source.resolve(strict=True), runtime.resolve(strict=True)
    if not source.is_dir() or not runtime.is_dir():
        raise ValueError('source and runtime must be directories')
    output = output.expanduser().absolute()
    validate_output(source, runtime, output)
    original_before, runtime_before = inventory(source), inventory(runtime)
    original_registration = checked_input(source, 'preregistration.json', registration_sha)
    registration = json.loads(original_registration)
    if registration['frozen_files'].get('frozen_evaluator.py') != EVALUATOR_SHA256:
        raise ValueError('unsupported evaluator; independent source review is required')
    originals = {name: checked_input(source, name, digest)
                 for name, digest in registration['frozen_files'].items()}
    if set(originals) != {'frozen_evaluator.py', 'cases.json', 'prepared-inputs.json', 'baseline-manifest.json'}:
        raise ValueError('unsupported corpus shape')
    cases = json.loads(originals['cases.json'])
    prepared = json.loads(originals['prepared-inputs.json'])
    if len(cases) != 16 or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('unsupported or duplicate case set')
    by_id = {r['id']: r for r in prepared}
    if len(by_id) != len(prepared) or set(by_id) != {c['id'] for c in cases}:
        raise ValueError('prepared case set mismatch')
    frozen = {}
    for case in cases:
        cid = case['id']
        if not re.fullmatch(r'[a-z0-9-]+', cid):
            raise ValueError('unsafe case identity')
        relative_root = Path('inputs') / cid / 'frozen'
        frozen[cid] = {name: checked_input(source, (relative_root / name).as_posix(), value['sha256'])
                       for name, value in by_id[cid]['frozen_inputs'].items()}
        if set(frozen[cid]) != {'case.json', 'ownership.json', 'live.jsonl', 'include.jsonl', 'rows.json'}:
            raise ValueError('unsupported frozen fields')
        if json.loads(frozen[cid]['case.json']) != case:
            raise ValueError('case expectations disagree')
    runtime_files = {}
    for path in runtime.glob('*.py'):
        if path.is_symlink():
            raise ValueError('runtime modules cannot be symlinks')
        data = path.read_bytes()
        if sha(data) != runtime_before[path.name]['sha256']:
            raise ValueError('runtime changed while capturing its bytes')
        runtime_files[path.name] = data
    if not {'manage_evolution.py', 'azhou_runtime_state.py'}.issubset(runtime_files):
        raise ValueError('incomplete runtime')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    publish(output / 'source-before.json', original_before)
    publish(output / 'runtime-before.json', runtime_before)
    workspace = output / 'workspace'; workspace.mkdir(mode=0o700)
    runtime_copy = output / 'runtime'; runtime_copy.mkdir(mode=0o700)
    for name, data in runtime_files.items():
        (runtime_copy / name).write_bytes(data)
    for name, data in originals.items():
        (workspace / name).write_bytes(data)
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(('GIT_', 'PYTHON'))}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1',
               PYTHONNOUSERSITE='1')
    commands = []
    started = time.monotonic()
    protected_before = None
    report = {'schema': 'super-repo-pedant.isolated-replay.v1', 'status': 'failed',
              'isolation_status': 'not_completed', 'effect_status': 'not_evaluated',
              'original_registration_sha256': registration_sha, 'synthetic': True,
              'wrapper_model_calls': 0, 'wrapper_model_tokens': 0, 'wrapper_api_cost': 0,
              'evaluator_model_calls': None, 'evaluator_model_tokens': None, 'evaluator_api_cost': None,
              'cost_scope': 'Wrapper makes no model/API calls. Child runtime usage and cost are not instrumented; self-reported evaluator counts are not verified metering.',
              'timeout_scope': 'Direct evaluator process only; descendant termination is not monitored or guaranteed.',
              'scope': 'Derived path-mapped replay; no original answers/evaluator edits and no OS sandbox claim.'}

    def git(project: Path, *args: str) -> str:
        command = ['git', '-c', 'core.hooksPath=' + str(output / 'empty-hooks'), '-C', str(project), *args]
        process = subprocess.run(command, env=env, capture_output=True, timeout=15)
        commands.append({'argv': command, 'exit': process.returncode,
                         'stdout': process.stdout.decode('utf-8'),
                         'stderr': process.stderr.decode('utf-8'),
                         'stdout_sha256': sha(process.stdout), 'stderr_sha256': sha(process.stderr)})
        if process.returncode:
            raise ValueError('synthetic project setup failed')
        return process.stdout.decode('utf-8').strip()

    try:
        mappings = []
        derived_prepared = copy.deepcopy(prepared)
        for row in derived_prepared:
            cid = row['id']; destination = workspace / 'inputs' / cid
            target_frozen = destination / 'frozen'; target_frozen.mkdir(parents=True, mode=0o700)
            for name, data in frozen[cid].items():
                (target_frozen / name).write_bytes(data)
            facts = json.loads(frozen[cid]['ownership.json']); common_groups = {}; derived_facts = {}
            for owner in sorted(facts, key=lambda name: (name != 'own', name)):
                if owner not in {'own', 'foreign1', 'foreign2', 'linked'}:
                    raise ValueError('unsupported owner')
                fact = facts[owner]
                remote = fact['remote']
                if not re.fullmatch(r'https://example\.invalid/project-scope/[a-z0-9-]+/(own|foreign1|foreign2)\.git', remote):
                    raise ValueError('only recorded synthetic origins may be re-created')
                project = destination / 'projects' / owner
                if fact['common_dir'] in common_groups:
                    first = common_groups[fact['common_dir']]
                    git(first, '-c', 'user.name=Isolated Replay', '-c', 'user.email=replay@example.invalid',
                        '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-m', 'synthetic ownership')
                    git(first, 'worktree', 'add', '--detach', str(project), 'HEAD')
                else:
                    project.mkdir(parents=True, mode=0o700)
                    git(project, 'init', '--quiet', '--template=')
                    git(project, 'config', 'remote.origin.url', remote)
                    common_groups[fact['common_dir']] = project
                new_common = str((project / git(project, 'rev-parse', '--git-common-dir')).resolve())
                if git(project, 'config', '--get', 'remote.origin.url') != remote:
                    raise ValueError('identity config changed')
                derived_facts[owner] = {'remote': remote, 'common_dir': new_common}
                mappings.append({'case': cid, 'owner': owner, 'old_common_dir': fact['common_dir'],
                                 'new_common_dir': new_common, 'remote_unchanged': True})
            publish(target_frozen / 'ownership.json', derived_facts)
            changed = (target_frozen / 'ownership.json').read_bytes()
            row['frozen_inputs']['ownership.json'] = {'sha256': sha(changed), 'bytes': len(changed)}
        publish(workspace / 'prepared-inputs.json', derived_prepared)
        derived = copy.deepcopy(registration)
        derived['frozen_files']['prepared-inputs.json'] = sha((workspace / 'prepared-inputs.json').read_bytes())
        derived['derivation'] = {'original_registration_sha256': registration_sha,
                                'reason': 'Only ownership common-directory paths remapped to new synthetic repositories.',
                                'not_original_exact_protocol': True}
        publish(workspace / 'preregistration.json', derived)
        publish(output / 'path-mapping.json', mappings)
        protected_before = immutable_copies(workspace, runtime_copy, cases)
        publish(output / 'copies-before.json', protected_before)
        if inventory(source) != original_before or inventory(runtime) != runtime_before:
            raise ValueError('source changed during isolated preparation')
        command = [sys.executable, '-B', str(workspace / 'frozen_evaluator.py'), '--variant', 'isolated-replay',
                   '--runtime', str(runtime_copy), '--run-id', 'run']
        report['command'] = command
        t = time.monotonic()
        try:
            process = subprocess.run(command, capture_output=True, env=env, cwd=workspace, timeout=120)
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = exc.stdout or b'', exc.stderr or b''
            (output / 'stdout.json').write_bytes(stdout); (output / 'stderr.log').write_bytes(stderr)
            report.update(exit=None, timed_out=True, replay_seconds=time.monotonic() - t,
                          stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
            raise
        (output / 'stdout.json').write_bytes(process.stdout); (output / 'stderr.log').write_bytes(process.stderr)
        report.update(exit=process.returncode, replay_seconds=time.monotonic() - t,
                      stdout_sha256=sha(process.stdout), stderr_sha256=sha(process.stderr))
        if process.returncode:
            raise ValueError('isolated evaluator failed')
        summary = json.loads(process.stdout)
        validate_summary(summary, cases)
        report.update(status='complete', cases=summary['cases'], passed=summary['passed'],
                      failed=summary['failed'],
                      effect_status='passed' if summary['passed'] == summary['cases'] else 'failed',
                      runtime_sha256={name: sha(data) for name, data in runtime_files.items()},
                      evaluator_sha256=EVALUATOR_SHA256,
                      derived_registration_sha256=sha((workspace / 'preregistration.json').read_bytes()))
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        for label, root, before in (
                ('original_corpus', source, original_before), ('runtime_source', runtime, runtime_before)):
            try:
                after = inventory(root)
                publish(output / (label + '-after.json'), after)
                report[label + '_unchanged'] = after == before
                report[label + '_before_sha256'] = inventory_digest(before)
                report[label + '_after_sha256'] = inventory_digest(after)
            except (ValueError, OSError) as exc:
                report[label + '_unchanged'] = False
                report[label + '_inspection_error'] = str(exc)
        if protected_before is not None:
            try:
                protected_after = immutable_copies(workspace, runtime_copy, cases)
                publish(output / 'copies-after.json', protected_after)
                for label in ('protocol', 'inputs', 'runtime'):
                    report['copied_' + label + '_unchanged'] = protected_after[label] == protected_before[label]
            except (ValueError, OSError) as exc:
                report['copies_inspection_error'] = str(exc)
        guards = ('original_corpus_unchanged', 'runtime_source_unchanged',
                  'copied_protocol_unchanged', 'copied_inputs_unchanged', 'copied_runtime_unchanged')
        if all(report.get(key) is True for key in guards):
            report['isolation_status'] = 'passed'
        elif protected_before is not None:
            report['isolation_status'] = 'failed'
        if report['isolation_status'] != 'passed':
            report['status'] = 'failed'
            if report['effect_status'] != 'not_evaluated':
                report['effect_status'] = 'invalidated'
        report['total_seconds'] = time.monotonic() - started
        publish(output / 'setup-commands.json', commands)
        publish(output / 'report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-registration-sha256', required=True)
    args = parser.parse_args()
    try:
        result = replay(args.source, args.runtime, args.output, args.expected_registration_sha256)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {'status': 'failed', 'isolation_status': 'not_completed',
                  'effect_status': 'not_evaluated', 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'complete' and result['isolation_status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

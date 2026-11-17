#!/usr/bin/env python3
"""Development diagnostic runner for frozen evaluation material.

Benchmark tooling only. Two subcommands:

- ``bind-freeze`` verifies a frozen diagnostic set against its manifest and
  copies it into a fresh read-only directory with source and copy hash binding.
- ``record`` runs one authorized diagnostic command under the opt-in call
  recorder (``sitecustomize.py`` in this directory): it creates a private FIFO,
  injects ``PYTHONPATH``/``SSI_RECORDER_FIFO``/``SSI_RECORDER_TARGET``, drains
  events while the command runs, and preserves raw events, command output and
  exit records in a fresh output directory.

This is not a security monitor. It does not enforce filesystem, network or
process isolation; the caller must arrange that separately. ``python -I/-S/-E``,
changed environments, native launchers, inline imports, FIFO loss and forged
messages bypass or corrupt observation. Instrumented interpreter starts are the
only call-count basis; static command text is carried verbatim as uninterpreted
evidence and never counts as a call or proves success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


OPERATIONS = ('validate-evidence', 'validate-reflection', 'review-citations', 'render')
COVERAGE_STATEMENT = (
    'Instrumented Python interpreter starts and subprocess attempts only; '
    'python -I/-S/-E, changed environments, native launchers, inline imports, '
    'FIFO loss and forged messages bypass or corrupt observation; unmatched '
    'attempts, unobserved paths and textual exit candidates remain unknown; '
    'this is not a complete call budget and not a security monitor.'
)
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z_0-9]*)['\"]?")


def hash_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unsafe_path(value) -> bool:
    if not isinstance(value, str) or not value:
        return True
    normalized = value.replace('\\', '/')
    return (normalized.startswith('/') or bool(re.match(r'[A-Za-z]:', normalized))
            or '..' in normalized.split('/'))


def strip_heredocs(command: str) -> str:
    """Drop shell here-document bodies so literal examples stay out of text scans."""
    kept = []
    delimiter = None
    for line in command.splitlines():
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        kept.append(line)
        match = HEREDOC.search(line)
        if match:
            delimiter = match.group(1)
    return '\n'.join(kept)


def classify(events, records, target_path):
    """Bind recorder events and raw command records into one honest coverage summary.

    ``events`` are recorder observations (python_start, subprocess_attempt,
    target_start). ``records`` are executed-command exit records carried
    verbatim, for example codex ``command_execution`` items. Instrumented
    starts are the only count basis; every exit linkage stays a labeled
    textual candidate and every outcome stays unknown.
    """
    basename = Path(target_path).name
    ops_pattern = '|'.join(OPERATIONS)
    # Direct shell-form candidates only: a quoted or assigned basename is a
    # literal, not an invocation token.
    candidate = re.compile(r"(?<!['\"=\w])" + re.escape(basename) + r'\s+(' + ops_pattern + r')\b')
    # Python list form, e.g. subprocess.run([sys.executable, target_path, "render"]):
    # exactly the invocation shape a bare shell-token scan historically missed.
    list_form = re.compile(
        re.escape(basename) + r"""['\"]?\s*,\s*['\"](""" + ops_pattern + r""")['\"]""")
    bare_name = re.compile(r"(?<!['\"=\w])" + re.escape(basename))
    python_starts = 0
    subprocess_attempts = 0
    starts = {op: [] for op in OPERATIONS}
    parse_failures = 0
    for event in events:
        if not isinstance(event, dict):
            parse_failures += 1
            continue
        kind = event.get('event')
        if kind == 'python_start':
            python_starts += 1
        elif kind == 'subprocess_attempt':
            subprocess_attempts += 1
        elif kind == 'target_start' and event.get('operation') in starts:
            starts[event['operation']].append(event.get('pid'))
    candidates = {op: [] for op in OPERATIONS}
    unlinked = []
    for record in records:
        command_text = str(record.get('command', ''))
        stripped = strip_heredocs(command_text)
        found = sorted({match.group(1) for match in candidate.finditer(stripped)})
        list_found = sorted({match.group(1) for match in list_form.finditer(stripped)})
        for op in found:
            candidates[op].append({'exit_code': record.get('exit_code'), 'linkage': 'textual-candidate'})
        for op in list_found:
            candidates[op].append({'exit_code': record.get('exit_code'), 'linkage': 'python-list-candidate'})
        if not found and not list_found and bare_name.search(stripped):
            unlinked.append({'exit_code': record.get('exit_code'),
                             'reason': 'target named without a recognized invocation form'})
    operations = {}
    for op in OPERATIONS:
        operations[op] = {
            'instrumented_starts': len(starts[op]),
            'start_pids': starts[op],
            'exit_candidates': candidates[op],
            'start_outcome': 'observed' if starts[op] else 'unobserved',
            'exit_outcome': 'unknown',
        }
    return {
        'python_starts': python_starts,
        'subprocess_attempts': subprocess_attempts,
        'operations': operations,
        'unlinked_target_records': unlinked,
        'event_parse_failures': parse_failures,
        'zero_call_verdict': False,
        'coverage_statement': COVERAGE_STATEMENT,
    }


def bind_freeze(freeze_dir, copy_dir):
    """Verify frozen material against its manifest, then copy it read-only."""
    freeze_dir = Path(freeze_dir)
    copy_dir = Path(copy_dir)
    if copy_dir.exists():
        raise SystemExit(f'copy directory already exists: {copy_dir}')
    manifest_bytes = (freeze_dir / 'FREEZE.manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    unsafe = [entry.get('path') for entry in manifest.get('frozen_files', []) if unsafe_path(entry.get('path'))]
    if unsafe:
        raise SystemExit(f'frozen material verification failed: unsafe path {unsafe}')
    problems = [entry['path'] for entry in manifest.get('frozen_files', [])
                if not (freeze_dir / entry['path']).is_file()
                or hash_file(freeze_dir / entry['path']) != entry.get('sha256')]
    if problems:
        raise SystemExit(f'frozen material verification failed: {problems}')
    copy_dir.mkdir(mode=0o700)
    entries = []
    for entry in manifest['frozen_files']:
        source_bytes = (freeze_dir / entry['path']).read_bytes()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if source_sha256 != entry.get('sha256'):
            raise SystemExit(f'frozen material verification failed: {entry["path"]}')
        member = copy_dir / entry['path']
        member.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        member.write_bytes(source_bytes)
        member.chmod(0o444)
        entries.append({'path': entry['path'], 'source_sha256': source_sha256,
                        'copy_sha256': hash_file(member), 'match': hash_file(member) == source_sha256})
    manifest_copy = copy_dir / 'FREEZE.manifest.json'
    manifest_copy.write_bytes(manifest_bytes)
    manifest_copy.chmod(0o444)
    binding = {
        'schema': 'super-session-insights.freeze-binding.v1',
        'freeze_dir': str(freeze_dir),
        'copy_dir': str(copy_dir),
        'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'manifest_copy_sha256': hash_file(copy_dir / 'FREEZE.manifest.json'),
        'verified': all(entry['match'] for entry in entries),
        'files': entries,
    }
    binding_path = copy_dir / 'freeze-binding.json'
    binding_path.write_text(json.dumps(binding, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    binding_path.chmod(0o444)
    for directory in sorted((item for item in copy_dir.rglob('*') if item.is_dir()), reverse=True):
        directory.chmod(0o555)
    copy_dir.chmod(0o555)
    print(json.dumps({'binding': str(binding_path), 'verified': binding['verified'],
                      'files': len(entries)}, ensure_ascii=False))


REPO_BINDING_COVER_NOTE = 'HEAD, index, tracked diff and status; untracked file bytes need --bind-file'


def snapshot_repo(repo):
    """Bind one git revision surface; untracked bytes need --bind-file instead."""
    repo = Path(repo)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(repo), capture_output=True, text=True, check=True, encoding='utf-8')
    index = subprocess.check_output(['git', 'ls-files', '--stage'], cwd=str(repo))
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=str(repo), capture_output=True, text=True, check=True, encoding='utf-8')
    diff = subprocess.check_output(['git', 'diff', '--binary'], cwd=str(repo))
    return {
        'head': head.stdout.strip(),
        'index_sha256': hashlib.sha256(index).hexdigest(),
        'status': status.stdout,
        'diff_binary_sha256': hashlib.sha256(diff).hexdigest(),
    }


def record_command(args):
    """Run one diagnostic command under the opt-in recorder and bind everything."""
    out = Path(args.out).resolve()
    if out.exists():
        raise SystemExit(f'output directory already exists: {out}')
    work = Path(args.work).resolve()
    if not work.is_dir():
        raise SystemExit(f'working directory does not exist: {work}')
    # The recorder must be importable from the child's own cwd, and the target
    # comparison uses realpaths, so both are pinned absolute here.
    recorder_dir = Path(args.recorder_dir).resolve()
    target = Path(args.target).resolve()
    if not (recorder_dir / 'sitecustomize.py').is_file():
        raise SystemExit(f'recorder directory lacks sitecustomize.py: {recorder_dir}')
    try:
        argv = json.loads(args.argv_json)
    except ValueError as error:
        raise SystemExit(f'invalid argv-json: {error}')
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise SystemExit('argv-json must be a JSON array of strings')
    if args.timeout_seconds <= 0:
        raise SystemExit('--timeout-seconds must be positive')
    env_overrides = {}
    for item in args.env:
        name, separator, value = item.partition('=')
        if not separator or not name:
            raise SystemExit(f'--env must be NAME=VALUE, got: {item}')
        if name.startswith('SSI_RECORDER_'):
            raise SystemExit(f'--env must not override recorder wiring: {name}')
        env_overrides[name] = value
    if args.stdin_path and not Path(args.stdin_path).is_file():
        raise SystemExit(f'stdin file does not exist: {args.stdin_path}')
    for bound in args.bind_file:
        if not Path(bound).is_file():
            raise SystemExit(f'bound file does not exist: {bound}')

    out.mkdir(mode=0o700)
    # The recorder emitter opens the FIFO from inside the observed process, so
    # when the output directory is not writable by that process (for example a
    # private evidence tree behind a sandbox deny rule) the caller moves the
    # FIFO into the observed workspace with --fifo-path.
    fifo = Path(args.fifo_path).resolve() if args.fifo_path else out / 'recorder-events.fifo'
    if fifo.exists():
        raise SystemExit(f'FIFO path already exists: {fifo}')
    if not fifo.parent.is_dir():
        raise SystemExit(f'FIFO parent directory does not exist: {fifo.parent}')
    os.mkfifo(fifo, 0o600)
    try:
        reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        raw = bytearray()

        def drain():
            while True:
                try:
                    chunk = os.read(reader, 65536)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                raw.extend(chunk)

        env = os.environ.copy()
        env.update(env_overrides)
        existing = env.get('PYTHONPATH')
        env['PYTHONPATH'] = str(recorder_dir) + (os.pathsep + existing if existing else '')
        env['SSI_RECORDER_FIFO'] = str(fifo)
        env['SSI_RECORDER_TARGET'] = str(target)

        repo_binding = None
        if args.bind_repo:
            repo_binding = {'covers': REPO_BINDING_COVER_NOTE,
                            'before': snapshot_repo(args.bind_repo), 'after': None, 'unchanged': None}
        file_before = {str(Path(item)): hash_file(item) for item in args.bind_file}
        stdin_bytes = Path(args.stdin_path).read_bytes() if args.stdin_path else None

        stdout_path = out / 'stdout.log'
        stderr_path = out / 'stderr.log'
        began = time.monotonic()
        stop_reason = None
        with stdout_path.open('wb') as stdout_stream, stderr_path.open('wb') as stderr_stream:
            os.chmod(stdout_path, 0o600)
            os.chmod(stderr_path, 0o600)
            proc = subprocess.Popen(argv, cwd=str(work), stdin=subprocess.PIPE, stdout=stdout_stream,
                                    stderr=stderr_stream, env=env, start_new_session=True)
            deadline = began + args.timeout_seconds

            def feed_stdin():
                try:
                    if stdin_bytes is not None:
                        proc.stdin.write(stdin_bytes)
                    proc.stdin.close()
                except OSError:
                    pass

            threading.Thread(target=feed_stdin, daemon=True).start()
            while proc.poll() is None:
                drain()
                if time.monotonic() > deadline:
                    stop_reason = 'timeout'
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
                    break
                time.sleep(0.2)
        drain()
        os.close(reader)
    finally:
        try:
            os.unlink(fifo)
        except OSError:
            pass

    events_path = out / 'recorder-events.jsonl'
    events_path.write_bytes(bytes(raw))
    events_path.chmod(0o600)
    events = []
    raw_parse_failures = 0
    for line in bytes(raw).splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            raw_parse_failures += 1

    records = []
    stdout_parse_failures = 0
    for line in stdout_path.read_bytes().decode(errors='replace').splitlines():
        stripped_line = line.strip()
        if not stripped_line.startswith('{'):
            continue
        try:
            event = json.loads(stripped_line)
        except ValueError:
            stdout_parse_failures += 1
            continue
        item = event.get('item') if isinstance(event, dict) else None
        if isinstance(event, dict) and event.get('type') == 'item.completed' and \
                isinstance(item, dict) and item.get('type') == 'command_execution':
            records.append({'command': item.get('command'), 'exit_code': item.get('exit_code')})

    if args.bind_repo:
        repo_binding['after'] = snapshot_repo(args.bind_repo)
        repo_binding['unchanged'] = repo_binding['before'] == repo_binding['after']
    file_after = {str(Path(item)): hash_file(item) for item in args.bind_file}

    result = {
        'schema': 'super-session-insights.diagnostic-run.v1',
        'label': args.label,
        'argv': argv,
        'cwd': str(work),
        'target': str(target),
        'recorder_dir': str(recorder_dir),
        'fifo_path': str(fifo),
        'env_overrides': env_overrides,
        'returncode': proc.returncode,
        'stop_reason': stop_reason,
        'elapsed_seconds': round(time.monotonic() - began, 3),
        'timeout_seconds': args.timeout_seconds,
        'recorder_events_sha256': hashlib.sha256(bytes(raw)).hexdigest(),
        'recorder_event_count': len(events),
        'recorder_parse_errors': raw_parse_failures,
        'stdout_sha256': hash_file(stdout_path),
        'stderr_sha256': hash_file(stderr_path),
        'command_records': records,
        'stdout_event_parse_errors': stdout_parse_failures,
        'classification': classify(events, records, args.target),
        'repo_binding': repo_binding,
        'file_binding_before': file_before,
        'file_binding_after': file_after,
        'file_binding_unchanged': file_before == file_after,
        'isolation': 'not enforced by this runner; caller-arranged and independently verified',
    }
    result_path = out / 'result.json'
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result_path.chmod(0o600)
    print(json.dumps({'result': str(result_path), 'returncode': proc.returncode, 'stop_reason': stop_reason},
                     ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser(description='Development diagnostic runner for frozen evaluation material.')
    sub = parser.add_subparsers(dest='command', required=True)
    freeze = sub.add_parser('bind-freeze', help='verify frozen material and copy it read-only with hash binding')
    freeze.add_argument('--freeze', required=True, help='frozen diagnostic set containing FREEZE.manifest.json')
    freeze.add_argument('--copy', required=True, help='fresh read-only copy directory that must not exist')
    record = sub.add_parser('record', help='run one authorized diagnostic command under the opt-in call recorder')
    record.add_argument('--argv-json', required=True, help='JSON array of argv strings for the diagnostic command')
    record.add_argument('--work', required=True, help='existing working directory for the diagnostic command')
    record.add_argument('--out', required=True, help='fresh output directory that must not exist')
    record.add_argument('--target', required=True, help='authorized target script recorded as SSI_RECORDER_TARGET')
    record.add_argument('--recorder-dir', required=True, help='directory holding the opt-in sitecustomize.py')
    record.add_argument('--stdin-path', help='optional file whose bytes are written to the command stdin')
    record.add_argument('--fifo-path', help='place the recorder FIFO at this path instead of inside --out')
    record.add_argument('--timeout-seconds', type=int, default=600)
    record.add_argument('--label', default='')
    record.add_argument('--env', action='append', default=[], metavar='NAME=VALUE')
    record.add_argument('--bind-repo', help='git repository whose revision surface is bound before and after')
    record.add_argument('--bind-file', action='append', default=[], help='extra file hashed before and after')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == 'bind-freeze':
        bind_freeze(args.freeze, args.copy)
    else:
        record_command(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())

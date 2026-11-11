"""Read-only source/patch binding for the existing promotion CLI.

Only a private temporary Git index/object directory is written. This is a content
check, not an OS sandbox, human identity proof, deployment writer or lock.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = 'super-repo-pedant.source-binding.v1'
MAX_RECORD_BYTES = 8 * 1024 * 1024
OID = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')


class BindingError(ValueError):
    pass


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular(path: Path) -> bytes:
    """Read a bounded regular file once; detect replacement during that read."""
    path = path.expanduser().absolute()
    try:
        if path.is_symlink():
            raise BindingError('evidence/patch must not be a symlink')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_RECORD_BYTES:
                raise BindingError('evidence/patch must be a bounded regular file')
            data = handle.read(MAX_RECORD_BYTES + 1)
            after = os.fstat(handle.fileno())
        current = path.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode)
        if len(data) > MAX_RECORD_BYTES or identity(before) != identity(after) or identity(after) != identity(current):
            raise BindingError('evidence/patch changed during read')
        return data
    except (OSError, UnicodeError) as exc:
        raise BindingError('evidence/patch unavailable') from exc


def parse_record(data: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise BindingError('duplicate JSON key')
            value[key] = item
        return value

    def finite(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise BindingError('non-finite JSON number')
        return result

    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                          parse_float=finite, parse_constant=finite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BindingError('invalid or ambiguous JSON evidence') from exc


def git_environment() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1',
               GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    return env


def git(project: Path, *args: str, data: bytes | None = None,
        private: dict[str, str] | None = None) -> bytes:
    env = git_environment()
    env.update(private or {})
    # read-tree/apply can invoke post-index-change even with a private index.
    # Disable repository hooks for every observational Git operation.
    command = ['git', '--no-pager', '-c', 'core.hooksPath=' + os.devnull,
               '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
               '-c', 'core.splitIndex=false', '-c', 'index.sparse=false',
               '-c', 'core.attributesFile=' + os.devnull, '-C', str(project), *args]
    try:
        result = subprocess.run(command, input=data, capture_output=True, env=env, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BindingError('Git source verification unavailable') from exc
    if result.returncode:
        raise BindingError('Git verification failed: ' + args[0])
    return result.stdout


def commit(project: Path, value: str) -> tuple[str, list[str]]:
    if not isinstance(value, str) or OID.fullmatch(value) is None:
        raise BindingError('full immutable commit object id required')
    if git(project, 'cat-file', '-t', value).strip() != b'commit':
        raise BindingError('expected commit object')
    if int(git(project, 'cat-file', '-s', value)) > MAX_RECORD_BYTES:
        raise BindingError('commit metadata exceeds bound')
    header = git(project, 'cat-file', '-p', value).split(b'\n\n', 1)[0].splitlines()
    tree = next(row[5:].decode('ascii') for row in header if row.startswith(b'tree '))
    parents = [row[7:].decode('ascii') for row in header if row.startswith(b'parent ')]
    return tree, parents


def tree_entries(project: Path, revision: str) -> dict[str, tuple[str, str]]:
    entries = {}
    for row in git(project, 'ls-tree', '-r', '-z', '--full-tree', revision).split(b'\0'):
        if not row:
            continue
        metadata, raw_path = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        path = raw_path.decode('utf-8')
        parts = path.split('/')
        if (path in entries or '\\' in path or any(x in ('', '.', '..') or x.lower() == '.git' for x in parts)
                or kind != 'blob' or mode not in ('100644', '100755', '120000')):
            raise BindingError('unsupported tree path/type; submodules require separate review')
        entries[path] = (mode, oid)
    return entries


def snapshot(project: Path) -> dict[str, Any]:
    """Compare raw bytes to Git objects, never invoke clean/smudge filters."""
    if Path(git(project, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve() != project:
        raise BindingError('project must name the exact worktree root')
    head = git(project, 'rev-parse', 'HEAD').decode('ascii').strip()
    tree, _ = commit(project, head)
    entries = tree_entries(project, head)
    index = {}
    for row in git(project, 'ls-files', '--stage', '-z').split(b'\0'):
        if row:
            metadata, path = row.split(b'\t', 1)
            mode, oid, stage = metadata.decode('ascii').split()
            name = path.decode('utf-8')
            if stage != '0' or name in index:
                raise BindingError('unmerged/duplicate index entries')
            index[name] = (mode, oid)
    if index != entries:
        raise BindingError('staged source differs from committed version')
    flags = git(project, 'ls-files', '-v', '-z')
    if any(row[:2] != b'H ' for row in flags.split(b'\0') if row):
        raise BindingError('hidden index flags are unsupported')
    if git(project, 'ls-files', '--others', '--exclude-standard', '-z'):
        raise BindingError('untracked non-ignored source exists')
    object_format = git(project, 'rev-parse', '--show-object-format').decode('ascii').strip()
    if object_format not in ('sha1', 'sha256'):
        raise BindingError('unsupported Git object format')
    for relative, (mode, oid) in entries.items():
        path = project / relative
        for parent in path.parents:
            if parent == project:
                break
            if parent.is_symlink():
                raise BindingError('tracked source has a symlink ancestor')
        info = path.lstat()
        if mode == '120000':
            if not path.is_symlink():
                raise BindingError('source type drift')
            raw = os.fsencode(os.readlink(path))
        else:
            if not stat.S_ISREG(info.st_mode):
                raise BindingError('source type drift')
            if os.name != 'nt' and bool(info.st_mode & 0o111) != (mode == '100755'):
                raise BindingError('source executable mode drift')
            raw = path.read_bytes()
        actual = hashlib.new(object_format, b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
        if actual != oid:
            raise BindingError('working source bytes differ from committed version')
    common = Path(git(project, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode('utf-8').strip()).resolve()
    index_path = Path(git(project, 'rev-parse', '--path-format=absolute', '--git-path', 'index').decode('utf-8').strip())
    return {'head': head, 'tree': tree, 'repository_id': sha256(os.fsencode(str(common))),
            'index_sha256': sha256(index_path.read_bytes()), 'tracked_files': len(entries)}


def describe(project: Path, candidate_bytes: bytes, patch_bytes: bytes,
             base: str, target: str, phase: str) -> dict[str, Any]:
    project = project.expanduser().resolve(strict=True)
    before = snapshot(project)
    base_tree, _ = commit(project, base)
    target_tree, parents = commit(project, target)
    if parents != [base] or base_tree == target_tree or not patch_bytes:
        raise BindingError('candidate must be one nonempty commit directly on the exact base')
    if phase == 'gate' and before['head'] != base:
        raise BindingError('stale base: pre-application HEAD must equal approved base')
    if phase == 'bind' and before['head'] not in (base, target):
        raise BindingError('binding requires the clean base or candidate checkout')
    if phase == 'verify-applied':
        actual_tree, actual_parents = commit(project, before['head'])
        if actual_parents != [base] or actual_tree != target_tree:
            raise BindingError('actual applied commit/tree differs from approved result')
    old, new = tree_entries(project, base), tree_entries(project, target)
    paths = sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))
    if len(paths) > 1000 or any(x and x[0] not in ('100644', '100755') for p in paths for x in (old.get(p), new.get(p))):
        raise BindingError('candidate scope or changed path modes require separate review')
    common = Path(git(project, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode('utf-8').strip()).resolve()
    # gettempdir() creates a probe file before returning a directory. Select
    # without probing so rejected source/worktree roots receive no writes.
    temp_setting = tempfile.tempdir
    if temp_setting is None:
        temp_setting = next((os.environ[name] for name in ('TMPDIR', 'TEMP', 'TMP')
                             if os.environ.get(name)), None)
    if temp_setting is None:
        if os.name == 'nt':
            raise BindingError('set TMPDIR, TEMP or TMP to an existing dedicated temporary directory')
        temp_setting = '/tmp'
    temp_root = Path(os.fsdecode(temp_setting)).expanduser().resolve(strict=True)
    if not temp_root.is_dir():
        raise BindingError('temporary storage must name an existing directory')
    worktree_records = git(project, 'worktree', 'list', '--porcelain', '-z').split(b'\0')
    worktree_roots = [Path(os.fsdecode(row[len(b'worktree '):])).resolve()
                      for row in worktree_records if row.startswith(b'worktree ')]
    if (temp_root.is_relative_to(common)
            or any(temp_root.is_relative_to(root) for root in [project, *worktree_roots])
            or any((ancestor / '.git').exists()
                   or ((ancestor / 'HEAD').is_file() and (ancestor / 'objects').is_dir())
                   for ancestor in (temp_root, *temp_root.parents))):
        raise BindingError('temporary index/object storage must be outside all worktrees and Git directories')
    objects = git(project, 'rev-parse', '--path-format=absolute', '--git-path', 'objects').decode('utf-8').strip()
    if os.pathsep in objects or '\n' in objects:
        raise BindingError('unsupported object directory representation')
    with tempfile.TemporaryDirectory(prefix='azhou-promotion-', dir=temp_root) as directory:
        temporary = Path(directory)
        (temporary / 'objects').mkdir(mode=0o700)
        private = {'GIT_INDEX_FILE': str(temporary / 'index'), 'GIT_OBJECT_DIRECTORY': str(temporary / 'objects'),
                   'GIT_ALTERNATE_OBJECT_DIRECTORIES': objects}
        git(project, 'read-tree', base, private=private)
        git(project, 'apply', '--cached', '--whitespace=nowarn', '-p1', data=patch_bytes, private=private)
        if git(project, 'write-tree', private=private).decode('ascii').strip() != target_tree:
            raise BindingError('actual patch does not produce the approved candidate tree')
        git(project, 'apply', '--cached', '--reverse', '--whitespace=nowarn', '-p1', data=patch_bytes, private=private)
        if git(project, 'write-tree', private=private).decode('ascii').strip() != base_tree:
            raise BindingError('patch reverse does not restore the known base tree')
    if snapshot(project) != before:
        raise BindingError('source/index changed during verification')
    binding = {'schema_version': SCHEMA, 'repository_id': before['repository_id'],
               'candidate_sha256': sha256(candidate_bytes), 'diff_sha256': sha256(patch_bytes),
               'base_commit': base, 'base_tree': base_tree, 'target_commit': target, 'target_tree': target_tree}
    encoded = json.dumps(binding, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {'binding': binding, 'binding_sha256': sha256(encoded), 'changed_paths': paths,
            'source_observation': before, 'reverse_verified': True, 'live_source_modified': False,
            'applied_commit': before['head'] if phase == 'verify-applied' else None}

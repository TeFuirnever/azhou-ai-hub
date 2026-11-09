#!/usr/bin/env python3
"""Prepare the local startup image from an isolated source snapshot."""

import argparse
import base64
import contextlib
import ctypes
import fcntl
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import sys
import uuid


MAX_SOURCE_BYTES = 64 * 1024 * 1024


def capture(source, snapshot):
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('The source must be a regular file.')
    if before.st_size > MAX_SOURCE_BYTES:
        raise ValueError('The source must not exceed 64 MiB.')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open(source, flags)
    try:
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise ValueError('The source changed before it could be captured.')
        header, digest, total = bytearray(), hashlib.sha256(), 0
        while True:
            try:
                data = os.read(fd, min(48 * 1024, MAX_SOURCE_BYTES + 1 - total))
            except InterruptedError:
                continue
            if not data:
                break
            total += len(data)
            if total > MAX_SOURCE_BYTES:
                raise ValueError('The source must not exceed 64 MiB.')
            if len(header) < 26:
                header.extend(data[:26 - len(header)])
            digest.update(data)
            snapshot.write(data)
        after = os.fstat(fd)
        current = source.lstat()
        if (not stat.S_ISREG(current.st_mode) or identity(before) != identity(after)
                or identity(after) != identity(current) or total != after.st_size):
            raise ValueError('The source changed while it was being captured.')
        return bytes(header), digest.hexdigest()
    finally:
        os.close(fd)


def write_scene(snapshot, output):
    snapshot.seek(0)
    remainder = b''
    output.write(b'window.AZHOU_WORKING_IMAGE = "data:image/png;base64,')
    while chunk := snapshot.read(48 * 1024):
        payload = remainder + chunk
        whole = len(payload) - len(payload) % 3
        output.write(base64.b64encode(payload[:whole]))
        remainder = payload[whole:]
    output.write(base64.b64encode(remainder))
    output.write(b'";\n')



def scene_fingerprint(snapshot):
    class Sink:
        def __init__(self):
            self.digest, self.size = hashlib.sha256(), 0
        def write(self, data):
            self.digest.update(data)
            self.size += len(data)
    output = Sink()
    write_scene(snapshot, output)
    return {'sha256': output.digest.hexdigest(), 'size': output.size}


ASSET_NAMES = ('working.png', 'scene.js', 'provenance.json')
RECEIPT = '.azhou-assets-receipt.json'
JOURNAL = '.azhou-assets-transaction.json'
LOCK = '.azhou-assets.lock'
OWNER = 'agent-skin/local-startup-assets-v1'
MAX_SCENE_BYTES = ((MAX_SOURCE_BYTES + 2) // 3) * 4 + 128


class AssetConflict(Exception):
    pass


def directory_identity(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise AssetConflict(f'Not a regular directory: {path}')
    return {'device': info.st_dev, 'inode': info.st_ino}


def file_info_at(directory_fd, name, *, max_bytes=MAX_SCENE_BYTES, content=False):
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
        raise AssetConflict(f'Not a bounded regular file: {name}')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory_fd)
    try:
        def identity(value):
            return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise AssetConflict(f'File changed before reading: {name}')
        digest, total, chunks = hashlib.sha256(), 0, []
        while True:
            try:
                chunk = os.read(fd, min(48 * 1024, max_bytes + 1 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise AssetConflict(f'File exceeds the allowed size: {name}')
            digest.update(chunk)
            if content:
                chunks.append(chunk)
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (not stat.S_ISREG(current.st_mode) or identity(before) != identity(after)
                or identity(after) != identity(current) or total != after.st_size):
            raise AssetConflict(f'File changed while reading: {name}')
        info = {'device': after.st_dev, 'inode': after.st_ino, 'size': total, 'sha256': digest.hexdigest()}
        return (info, b''.join(chunks)) if content else info
    finally:
        os.close(fd)


def capture_at(directory_fd, name, snapshot):
    before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SOURCE_BYTES:
        raise AssetConflict(f'Existing image is not a bounded regular file: {name}')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory_fd)
    try:
        def identity(value):
            return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise AssetConflict('Existing image changed before reading.')
        header, digest, total = bytearray(), hashlib.sha256(), 0
        while True:
            try:
                chunk = os.read(fd, min(48 * 1024, MAX_SOURCE_BYTES + 1 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SOURCE_BYTES:
                raise AssetConflict('Existing image exceeds 64 MiB.')
            if len(header) < 26:
                header.extend(chunk[:26 - len(header)])
            digest.update(chunk)
            snapshot.write(chunk)
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (not stat.S_ISREG(current.st_mode) or identity(before) != identity(after)
                or identity(after) != identity(current) or total != after.st_size):
            raise AssetConflict('Existing image changed while reading.')
        return bytes(header), digest.hexdigest()
    finally:
        os.close(fd)


def read_json_at(directory_fd, name):
    result = file_info_at(directory_fd, name, max_bytes=1024 * 1024, content=True)
    if result is None:
        return None, None
    info, raw = result
    try:
        value = json.loads(raw, parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AssetConflict(f'Invalid JSON record: {name}') from exc
    if not isinstance(value, dict):
        raise AssetConflict(f'Invalid JSON record: {name}')
    return info, value


def opened_identity(fd):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise AssetConflict('An opened transaction root is not a directory.')
    return {'device': info.st_dev, 'inode': info.st_ino}


def open_bound_directory(path, expected, handles):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    handles.callback(os.close, fd)
    if opened_identity(fd) != expected or directory_identity(path) != expected:
        raise AssetConflict('A transaction root changed identity; preserve it for review.')
    return fd


def target_fd(fds, name):
    return fds['state'] if name == RECEIPT else fds['output']


def data_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'


def valid_identity(value):
    return (isinstance(value, dict) and set(value) == {'device', 'inode'}
            and all(type(value[key]) is int and value[key] >= 0 for key in value))


def valid_file_info(value):
    return (isinstance(value, dict) and set(value) == {'device', 'inode', 'size', 'sha256'}
            and all(type(value[key]) is int and value[key] >= 0 for key in ('device', 'inode', 'size'))
            and isinstance(value['sha256'], str) and len(value['sha256']) == 64
            and all(char in '0123456789abcdef' for char in value['sha256']))


def verify_legacy_triple(output_fd):
    info, provenance = read_json_at(output_fd, 'provenance.json')
    if (not info or set(provenance) != {'source', 'sha256', 'width', 'height', 'alpha', 'copiedByteForByte', 'purpose'}
            or not isinstance(provenance['source'], str) or provenance['width'] != 1254 or provenance['height'] != 1254
            or provenance['alpha'] is not True or provenance['copiedByteForByte'] is not True
            or provenance['purpose'] != 'Local-only startup scene. Do not commit or publish.'):
        raise AssetConflict('Existing provenance is incomplete or unrecognized; preserve it for review.')
    with tempfile.TemporaryFile(mode='w+b') as original:
        header, digest = capture_at(output_fd, 'working.png', original)
        if len(header) < 26 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
            raise AssetConflict('Existing working image is not a recognized PNG.')
        if struct.unpack('>IIBB', header[16:26])[0:2] != (1254, 1254) or header[25] != 6:
            raise AssetConflict('Existing working image dimensions or color are not recognized.')
        if provenance['sha256'] != digest:
            raise AssetConflict('Existing working image and provenance differ.')
        expected_info = scene_fingerprint(original)
    actual_scene = file_info_at(output_fd, 'scene.js')
    if actual_scene is None or actual_scene['sha256'] != expected_info['sha256'] or actual_scene['size'] != expected_info['size']:
        raise AssetConflict('Existing scene does not match the working image.')


def existing_outputs(root_identity, state_identity, adopt, fds):
    names = (*ASSET_NAMES, RECEIPT)
    observed = {name: file_info_at(target_fd(fds, name), name) for name in names}
    if not any(observed.values()):
        return observed
    if not all(observed[name] for name in ASSET_NAMES):
        raise AssetConflict('Existing output is incomplete; preserve it for review.')
    receipt_info, receipt = read_json_at(fds['state'], RECEIPT)
    if receipt_info is None:
        if not adopt:
            raise AssetConflict('Existing output has no bound receipt; inspect it and use --adopt-existing to update.')
        verify_legacy_triple(fds['output'])
        return observed
    if (set(receipt) != {'owner', 'version', 'rootIdentity', 'stateIdentity', 'files'} or receipt.get('owner') != OWNER
            or type(receipt.get('version')) is not int or receipt['version'] != 1
            or receipt.get('rootIdentity') != root_identity or receipt.get('stateIdentity') != state_identity
            or not isinstance(receipt.get('files'), dict)
            or set(receipt['files']) != set(ASSET_NAMES)
            or any(not valid_file_info(receipt['files'][name]) or receipt['files'][name] != observed[name]
                   for name in ASSET_NAMES)):
        raise AssetConflict('Existing output receipt does not match; preserve it for review.')
    return observed


def swap_files(left_fd, left_name, right_fd, right_name):
    if sys.platform == 'darwin':
        library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
        operation = library.renameatx_np
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(left_fd, os.fsencode(left_name), right_fd, os.fsencode(right_name), 2)
    elif sys.platform.startswith('linux'):
        library = ctypes.CDLL(None, use_errno=True)
        operation = library.renameat2
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(left_fd, os.fsencode(left_name), right_fd, os.fsencode(right_name), 2)
    else:
        raise AssetConflict('Atomic file exchange is unavailable on this platform.')
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def check_roots(destination, state, stage, record, guard, fds):
    guard()
    if directory_identity(destination) != record['rootIdentity'] or opened_identity(fds['output']) != record['rootIdentity']:
        raise AssetConflict('Private output directory changed; preserve transaction for review.')
    if directory_identity(state) != record['stateIdentity'] or opened_identity(fds['state']) != record['stateIdentity']:
        raise AssetConflict('Private state directory changed; preserve transaction for review.')
    if directory_identity(stage) != record['stageIdentity'] or opened_identity(fds['stage']) != record['stageIdentity']:
        raise AssetConflict('Private transaction directory changed; preserve it for review.')


def check_journal(state_fd, expected_info):
    if file_info_at(state_fd, JOURNAL, max_bytes=1024 * 1024) != expected_info:
        raise AssetConflict('Private transaction record changed; preserve it for review.')


def checked_unlink(directory_fd, name, expected):
    if file_info_at(directory_fd, name) != expected:
        raise AssetConflict(f'Private transaction file changed; preserve it: {name}')
    os.unlink(name, dir_fd=directory_fd)


def remove_transaction(destination, state, stage, record, journal_info, staged_states, guard, fds):
    check_roots(destination, state, stage, record, guard, fds)
    check_journal(fds['state'], journal_info)
    if set(os.listdir(fds['stage'])) != {name for name, info in staged_states.items() if info is not None}:
        raise AssetConflict('Private transaction contains unknown entries; preserve it for review.')
    for name, expected in staged_states.items():
        if expected is not None:
            check_roots(destination, state, stage, record, guard, fds)
            check_journal(fds['state'], journal_info)
            checked_unlink(fds['stage'], name, expected)
    check_roots(destination, state, stage, record, guard, fds)
    check_journal(fds['state'], journal_info)
    os.rmdir(stage.name, dir_fd=fds['state'])
    os.fsync(fds['state'])
    guard()
    if (directory_identity(destination) != record['rootIdentity'] or opened_identity(fds['output']) != record['rootIdentity']
            or directory_identity(state) != record['stateIdentity'] or opened_identity(fds['state']) != record['stateIdentity']):
        raise AssetConflict('Private transaction root changed; preserve journal for review.')
    check_journal(fds['state'], journal_info)
    checked_unlink(fds['state'], JOURNAL, journal_info)
    os.fsync(fds['state'])


def recover_transaction(destination, state, guard):
    guard()
    with contextlib.ExitStack() as handles:
        fds = {
            'output': open_bound_directory(destination, directory_identity(destination), handles),
            'state': open_bound_directory(state, directory_identity(state), handles),
        }
        journal_info, record = read_json_at(fds['state'], JOURNAL)
        if journal_info is None:
            return None
        required = {'owner', 'version', 'rootIdentity', 'stateIdentity', 'stageIdentity', 'stageName', 'journalIdentity', 'items'}
        names = (*ASSET_NAMES, RECEIPT)
        if (set(record) != required or record.get('owner') != OWNER or type(record.get('version')) is not int
                or record['version'] != 1 or not valid_identity(record.get('rootIdentity'))
                or not valid_identity(record.get('stateIdentity')) or not valid_identity(record.get('stageIdentity'))
                or not valid_identity(record.get('journalIdentity'))
                or record['journalIdentity'] != {'device': journal_info['device'], 'inode': journal_info['inode']}
                or not isinstance(record.get('stageName'), str)
                or not re.fullmatch(r'\.azhou-assets-stage-[0-9a-f]{32}', record['stageName'])
                or not isinstance(record.get('items'), dict) or set(record['items']) != set(names)):
            raise AssetConflict('Private transaction record is not recognized; preserve it for review.')
        for item in record['items'].values():
            if (not isinstance(item, dict) or set(item) != {'old', 'new'} or not valid_file_info(item['new'])
                    or (item['old'] is not None and not valid_file_info(item['old']))):
                raise AssetConflict('Private transaction plan is not recognized; preserve it for review.')
        if (directory_identity(destination) != record['rootIdentity']
                or opened_identity(fds['output']) != record['rootIdentity']
                or directory_identity(state) != record['stateIdentity']
                or opened_identity(fds['state']) != record['stateIdentity']):
            raise AssetConflict('Private transaction roots changed; preserve them for review.')
        stage = state / record['stageName']
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            fds['stage'] = os.open(record['stageName'], flags, dir_fd=fds['state'])
        except FileNotFoundError as exc:
            raise AssetConflict('Private transaction directory is missing; preserve targets and journal for review.') from exc
        handles.callback(os.close, fds['stage'])
        check_roots(destination, state, stage, record, guard, fds)
        targets = {name: file_info_at(target_fd(fds, name), name) for name in names}
        all_new = all(targets[name] == record['items'][name]['new'] for name in names)
        if not set(os.listdir(fds['stage'])).issubset(set(names)):
            raise AssetConflict('Private transaction contains unknown entries; preserve it for review.')
        staged = {name: file_info_at(fds['stage'], name) for name in names}
        states = {}
        for name in names:
            old, new = record['items'][name]['old'], record['items'][name]['new']
            current, saved = targets[name], staged[name]
            if current == old and saved == new:
                states[name] = 'pending'
            elif old is None and current == new and saved == new:
                states[name] = 'created'
            elif old is not None and current == new and saved == old:
                states[name] = 'swapped'
            else:
                raise AssetConflict('Private transaction contents changed; preserve them for review.')
        if all_new:
            check_roots(destination, state, stage, record, guard, fds)
            check_journal(fds['state'], journal_info)
            for fd in fds.values():
                os.fsync(fd)
            remove_transaction(destination, state, stage, record, journal_info, staged, guard, fds)
            return 'committed'
        for name in reversed(names):
            phase = states[name]
            if phase not in ('created', 'swapped'):
                continue
            check_roots(destination, state, stage, record, guard, fds)
            check_journal(fds['state'], journal_info)
            item = record['items'][name]
            if (file_info_at(target_fd(fds, name), name) != item['new']
                    or file_info_at(fds['stage'], name) != (item['new'] if phase == 'created' else item['old'])):
                raise AssetConflict('Private transaction changed during recovery; preserve it for review.')
            if phase == 'created':
                checked_unlink(target_fd(fds, name), name, item['new'])
            else:
                swap_files(target_fd(fds, name), name, fds['stage'], name)
                if (file_info_at(target_fd(fds, name), name) != item['old']
                        or file_info_at(fds['stage'], name) != item['new']):
                    raise AssetConflict('Private transaction recovery is uncertain; preserve it for review.')
            for fd in fds.values():
                os.fsync(fd)
        for name in names:
            if (file_info_at(target_fd(fds, name), name) != record['items'][name]['old']
                    or file_info_at(fds['stage'], name) != record['items'][name]['new']):
                raise AssetConflict('Private transaction recovery changed; preserve it for review.')
        remove_transaction(destination, state, stage, record, journal_info,
                           {name: record['items'][name]['new'] for name in names}, guard, fds)
        return 'rolled-back'

def prepare_destination(package):
    assets, local = package / 'assets', package / '.local'
    destination, state = assets / 'private', local / 'agent-skin-asset-preparation'
    for directory in (assets, destination, local, state):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        directory_identity(directory)
    if destination.lstat().st_dev != state.lstat().st_dev:
        raise AssetConflict('Private output and transaction state must share a filesystem.')
    return destination, state



def stage_file(path, writer, stage_fd):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path.name, flags, 0o600, dir_fd=stage_fd)
    with os.fdopen(fd, 'wb') as stream:
        writer(stream)
        stream.flush()
        os.fsync(stream.fileno())
        written = os.fstat(stream.fileno())
    result = file_info_at(stage_fd, path.name)
    if result is None or (result['device'], result['inode']) != (written.st_dev, written.st_ino):
        raise AssetConflict('New staged file changed identity; preserve transaction for review.')
    return result


@contextlib.contextmanager
def preparation_lock(package, state):
    spec = importlib.util.spec_from_file_location('agent_skin_asset_build_lock', package / 'tools/build-lock.py')
    if spec is None or spec.loader is None:
        raise AssetConflict('Missing project build lock.')
    lock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lock)
    acquired = False
    try:
        with lock.acquired() as fd:
            acquired = True
            def guard():
                try:
                    lock.checked_lock_file(fd)
                except (OSError, RuntimeError) as exc:
                    raise AssetConflict(f'Project build lock changed: {exc}') from exc
            guard()
            yield directory_identity(state), guard
    except (OSError, RuntimeError) as exc:
        if acquired:
            raise
        raise AssetConflict(f'Project build lock is unavailable: {exc}') from exc


def write_journal(state, state_fd, stage, root_identity, state_identity, stage_identity, items):
    fd = os.open(JOURNAL, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=state_fd)
    try:
        info = os.fstat(fd)
        record = {'owner': OWNER, 'version': 1, 'rootIdentity': root_identity, 'stageIdentity': stage_identity,
                  'stateIdentity': state_identity, 'stageName': stage.name, 'journalIdentity': {'device': info.st_dev, 'inode': info.st_ino},
                  'items': items}
        data = data_bytes(record)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    os.fsync(state_fd)
    result = file_info_at(state_fd, JOURNAL, max_bytes=1024 * 1024, content=True)
    if result is None:
        raise AssetConflict('Private transaction record disappeared during creation.')
    info, observed = result
    if ({'device': info['device'], 'inode': info['inode']} != record['journalIdentity'] or observed != data):
        raise AssetConflict('Private transaction record changed during creation; preserve it.')
    return record, info


def journal_present(state_fd):
    try:
        os.stat(JOURNAL, dir_fd=state_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def cleanup_unjournaled(destination, state, stage, record, staged, guard, fds):
    check_roots(destination, state, stage, record, guard, fds)
    if journal_present(fds['state']):
        return False
    if (set(os.listdir(fds['stage'])) != set(staged)
            or any(file_info_at(fds['stage'], name) != info for name, info in staged.items())):
        return False
    for name, info in staged.items():
        check_roots(destination, state, stage, record, guard, fds)
        if journal_present(fds['state']):
            return False
        checked_unlink(fds['stage'], name, info)
    check_roots(destination, state, stage, record, guard, fds)
    if journal_present(fds['state']):
        return False
    os.rmdir(stage.name, dir_fd=fds['state'])
    os.fsync(fds['state'])
    return True


def check_publication_progress(destination, state, stage, record, journal_info, completed, guard, fds):
    check_roots(destination, state, stage, record, guard, fds)
    check_journal(fds['state'], journal_info)
    names = (*ASSET_NAMES, RECEIPT)
    if set(os.listdir(fds['stage'])) != set(names):
        raise AssetConflict('Private transaction contains unknown or missing entries; preserve it for review.')
    for name in names:
        item = record['items'][name]
        if name in completed:
            expected_target = item['new']
            expected_stage = item['old'] if item['old'] is not None else item['new']
        else:
            expected_target, expected_stage = item['old'], item['new']
        if (file_info_at(target_fd(fds, name), name) != expected_target
                or file_info_at(fds['stage'], name) != expected_stage):
            raise AssetConflict('Private transaction changed during publication; preserve it for review.')


def publish_assets(package, snapshot, source, digest, adopt):
    destination, state = prepare_destination(package)
    with preparation_lock(package, state) as (state_identity, guard):
        root_identity = directory_identity(destination)
        recover_transaction(destination, state, guard)
        if directory_identity(destination) != root_identity:
            raise AssetConflict('Private output directory changed before preparation.')
        with contextlib.ExitStack() as handles:
            fds = {
                'output': open_bound_directory(destination, root_identity, handles),
                'state': open_bound_directory(state, state_identity, handles),
            }
            old = existing_outputs(root_identity, state_identity, adopt, fds)
            provenance = {'source': str(source), 'sha256': digest, 'width': 1254, 'height': 1254,
                          'alpha': True, 'copiedByteForByte': True,
                          'purpose': 'Local-only startup scene. Do not commit or publish.'}
            expected_scene = scene_fingerprint(snapshot)
            provenance_raw = data_bytes(provenance)
            expected = {
                'working.png': {'sha256': digest, 'size': snapshot.seek(0, os.SEEK_END)},
                'scene.js': expected_scene,
                'provenance.json': {'sha256': hashlib.sha256(provenance_raw).hexdigest(), 'size': len(provenance_raw)},
            }
            guard()
            if (directory_identity(destination) != root_identity or opened_identity(fds['output']) != root_identity
                    or directory_identity(state) != state_identity or opened_identity(fds['state']) != state_identity):
                raise AssetConflict('Private transaction roots changed before staging.')
            if old[RECEIPT] is not None and all(
                    old[name]['sha256'] == expected[name]['sha256'] and old[name]['size'] == expected[name]['size']
                    for name in ASSET_NAMES):
                return destination
            token = uuid.uuid4().hex
            stage = state / ('.azhou-assets-stage-' + token)
            os.mkdir(stage.name, mode=0o700, dir_fd=fds['state'])
            fds['stage'] = os.open(stage.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                   dir_fd=fds['state'])
            handles.callback(os.close, fds['stage'])
            stage_identity = opened_identity(fds['stage'])
            base_record = {'rootIdentity': root_identity, 'stateIdentity': state_identity, 'stageIdentity': stage_identity}
            journal_created = False
            staged = {}
            try:
                check_roots(destination, state, stage, base_record, guard, fds)
                if os.listdir(fds['stage']):
                    raise AssetConflict('New staging is not empty; preserve it for review.')
                snapshot.seek(0)
                image_info = stage_file(stage / 'working.png', lambda stream: shutil.copyfileobj(snapshot, stream, 48 * 1024), fds['stage'])
                if image_info['sha256'] != digest or image_info['size'] != expected['working.png']['size']:
                    raise AssetConflict('Staged image does not match the source snapshot.')
                staged['working.png'] = image_info
                check_roots(destination, state, stage, base_record, guard, fds)
                snapshot.seek(0)
                scene_info = stage_file(stage / 'scene.js', lambda stream: write_scene(snapshot, stream), fds['stage'])
                if (scene_info['sha256'] != expected_scene['sha256']
                        or scene_info['size'] != expected_scene['size']):
                    raise AssetConflict('Staged scene does not match the source snapshot.')
                staged['scene.js'] = scene_info
                check_roots(destination, state, stage, base_record, guard, fds)
                provenance_info = stage_file(stage / 'provenance.json', lambda stream: stream.write(provenance_raw), fds['stage'])
                if (provenance_info['sha256'] != expected['provenance.json']['sha256']
                        or provenance_info['size'] != expected['provenance.json']['size']):
                    raise AssetConflict('Staged provenance does not match the source snapshot.')
                staged['provenance.json'] = provenance_info
                receipt = {'owner': OWNER, 'version': 1, 'rootIdentity': root_identity, 'stateIdentity': state_identity,
                           'files': {name: staged[name] for name in ASSET_NAMES}}
                receipt_raw = data_bytes(receipt)
                check_roots(destination, state, stage, base_record, guard, fds)
                receipt_info = stage_file(stage / RECEIPT, lambda stream: stream.write(receipt_raw), fds['stage'])
                if (receipt_info['sha256'] != hashlib.sha256(receipt_raw).hexdigest()
                        or receipt_info['size'] != len(receipt_raw)):
                    raise AssetConflict('Staged asset receipt does not match the transaction.')
                staged[RECEIPT] = receipt_info
                check_roots(destination, state, stage, base_record, guard, fds)
                if (set(os.listdir(fds['stage'])) != set(staged)
                        or any(file_info_at(fds['stage'], name) != info for name, info in staged.items())):
                    raise AssetConflict('New private staging changed; preserve it for review.')
                os.fsync(fds['stage'])
                items = {name: {'old': old[name], 'new': staged[name]} for name in (*ASSET_NAMES, RECEIPT)}
                guard()
                record, journal_info = write_journal(state, fds['state'], stage, root_identity, state_identity, stage_identity, items)
                journal_created = True
                completed = set()
                for name in (*ASSET_NAMES, RECEIPT):
                    check_publication_progress(destination, state, stage, record, journal_info, completed, guard, fds)
                    destination_fd = target_fd(fds, name)
                    if file_info_at(destination_fd, name) != old[name] or file_info_at(fds['stage'], name) != staged[name]:
                        raise AssetConflict('Private output changed before publication; preserve it for review.')
                    if old[name] is None:
                        os.link(name, name, src_dir_fd=fds['stage'], dst_dir_fd=destination_fd, follow_symlinks=False)
                    else:
                        swap_files(fds['stage'], name, destination_fd, name)
                    after_stage = staged[name] if old[name] is None else old[name]
                    if file_info_at(destination_fd, name) != staged[name] or file_info_at(fds['stage'], name) != after_stage:
                        raise AssetConflict('Private publication result is uncertain; preserve it for review.')
                    completed.add(name)
                    for directory_fd in fds.values():
                        os.fsync(directory_fd)
                if recover_transaction(destination, state, guard) != 'committed':
                    raise AssetConflict('Private transaction did not commit; preserve it for review.')
            except Exception as exc:
                if journal_created:
                    try:
                        outcome = recover_transaction(destination, state, guard)
                    except Exception as recovery_exc:
                        raise AssetConflict(f'Private preparation requires recovery; preserve {stage}: {recovery_exc}') from exc
                    if outcome == 'committed':
                        return destination
                    if outcome == 'rolled-back':
                        raise AssetConflict(f'Private preparation failed; prior outputs restored: {exc}') from exc
                    raise AssetConflict(f'Private transaction record disappeared; preserve {stage} for review.') from exc
                try:
                    cleaned = cleanup_unjournaled(destination, state, stage, base_record, staged, guard, fds)
                except Exception:
                    cleaned = False
                if cleaned:
                    raise AssetConflict(f'Private preparation stopped before publication: {exc}') from exc
                raise AssetConflict(f'Private preparation stopped; preserve {stage}: {exc}') from exc
    return destination

def require_private_git_guard(package, parser):
    ignored = subprocess.run(['git', 'check-ignore', '-q', '--', 'assets/private/'], cwd=package)
    if ignored.returncode:
        parser.error('assets/private/ must be ignored by Git before preparing private artwork.')
    if subprocess.check_output(['git', 'ls-files', '--', 'assets/private'], cwd=package).strip():
        parser.error('Private assets are tracked. Remove them from the index before continuing.')
    state_path = '.local/agent-skin-asset-preparation/'
    if subprocess.run(['git', 'check-ignore', '-q', '--', state_path], cwd=package).returncode:
        parser.error('The local asset transaction state must be ignored by Git.')
    if subprocess.check_output(['git', 'ls-files', '--', '.local/agent-skin-asset-preparation'], cwd=package).strip():
        parser.error('Local asset transaction state is tracked. Remove it from the index before continuing.')


def main():
    package = Path(__file__).resolve().parent.parent
    library = Path(os.environ.get('AZHOU_ASSET_ROOT', str(Path.home() / 'Desktop/oh-my-ai/IP/azhou')))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopt-existing', action='store_true', help='Adopt a reviewed, complete legacy output set before updating.')
    parser.add_argument('--recover', action='store_true', help='Recover a verifiable interrupted preparation without reading a source image.')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    destination = package / 'assets/private'
    if args.recover:
        if args.adopt_existing or args.source is not None:
            parser.error('--recover cannot be combined with --source or --adopt-existing.')
        try:
            local = package / '.local'
            if not local.exists() and not local.is_symlink():
                print('No private asset transaction found.')
                return
            directory_identity(local)
            state = local / 'agent-skin-asset-preparation'
            if not state.exists() and not state.is_symlink():
                print('No private asset transaction found.')
                return
            directory_identity(state)
            require_private_git_guard(package, parser)
            with preparation_lock(package, state) as (_, guard):
                journal = state / JOURNAL
                if not journal.exists() and not journal.is_symlink():
                    outcome = None
                else:
                    directory_identity(package / 'assets')
                    directory_identity(destination)
                    outcome = recover_transaction(destination, state, guard)
        except (OSError, ValueError, AssetConflict) as exc:
            parser.error(str(exc))
        print('Private asset recovery:', outcome or 'no transaction')
        return
    source_path = args.source or library / 'assets/characters/azhou-chibi-pet/v1.0.0/images/04-working.png'
    source = source_path.expanduser().resolve(strict=True)
    if source == destination / 'working.png':
        parser.error('Use the original approved source file, not the output copy.')

    with tempfile.TemporaryFile(mode='w+b') as snapshot:
        try:
            header, digest = capture(source, snapshot)
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot capture source: {exc}')
        if len(header) < 26 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
            parser.error('The approved working pose must be a PNG.')
        width, height, _, color = struct.unpack('>IIBB', header[16:26])
        if (width, height, color) != (1254, 1254, 6):
            parser.error('This scene is registered to the 1254 × 1254 RGBA working pose; another image requires a new visual review.')
        require_private_git_guard(package, parser)

        try:
            destination = publish_assets(package, snapshot, source, digest, args.adopt_existing)
        except (OSError, ValueError, AssetConflict) as exc:
            parser.error(str(exc))
    print('Prepared private working pose:', destination)
    print('Source SHA-256:', digest)


if __name__ == '__main__':
    main()

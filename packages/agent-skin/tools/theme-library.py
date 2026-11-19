#!/usr/bin/env python3
"""Store validated Dream source ZIPs in an explicit isolated library. Never applies them."""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, contextmanager
import ctypes
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid
import zipfile
import zlib

spec = importlib.util.spec_from_file_location('dream_source_preflight', Path(__file__).with_name('theme-package-preflight.py'))
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
Blocked = preflight.Blocked
require = preflight.require
MARKER = 'library-owner'
OWNER_SCHEMA = 'azhou-agent-skin.dream-source-library.v2'
LOCK_NAME = 'library-lock'
LOCK_CONTENT = b'azhou-agent-skin.dream-source-library.lock.v1\n'
LOCK_WAIT_SECONDS = 2.0
CATALOG_LIMIT = 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
THEME_ADAPTER = Path(__file__).with_name('reference-official-theme.mjs')


def identity(info):
    return info.st_dev, info.st_ino


@contextmanager
def descriptor(fd):
    try:
        yield fd
    finally:
        os.close(fd)


def directory(path):
    path = Path(path)
    require('..' not in path.parts, 'library_path')
    parts = Path(os.path.abspath(path)).parts
    fd = os.open(parts[0], DIRECTORY_FLAGS)
    try:
        for part in parts[1:]:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def names(fd, limit, reason):
    result = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            require(len(result) < limit, reason)
            result.add(entry.name)
    return result


def read_regular(parent, name, limit):
    with os.fdopen(os.open(name, FILE_FLAGS, dir_fd=parent), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'stored_object_invalid')
        require(0 < before.st_size <= limit, 'stored_object_invalid')
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and len(data) == before.st_size, 'stored_object_changed')
        return data


def owner_bytes(lock_identity):
    return (json.dumps({'schema': OWNER_SCHEMA, 'lockIdentity': list(lock_identity)},
                       sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def read_owner(root):
    data = read_regular(root, MARKER, 512)
    try:
        value = json.loads(data.decode('ascii'), object_pairs_hook=preflight.unique_object)
    except (UnicodeError, ValueError):
        raise Blocked('library_unknown') from None
    require(isinstance(value, dict) and set(value) == {'schema', 'lockIdentity'}
            and value['schema'] == OWNER_SCHEMA and isinstance(value['lockIdentity'], list)
            and len(value['lockIdentity']) == 2
            and all(type(part) is int and part >= 0 for part in value['lockIdentity']), 'library_unknown')
    expected = tuple(value['lockIdentity'])
    require(data == owner_bytes(expected), 'library_unknown')
    return data, expected


def read_source(path):
    path = Path(path)
    require(path.suffix.lower() == '.zip', 'input_type')
    with descriptor(directory(path.parent)) as parent:
        fd = os.open(path.name, FILE_FLAGS, dir_fd=parent)
        return preflight.read_open_archive(fd)


def publish_directory(source_fd, source, destination_fd, destination):
    try:
        if sys.platform == 'darwin':
            library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
            operation, flag = library.renameatx_np, 4
        elif sys.platform.startswith('linux'):
            library = ctypes.CDLL(None, use_errno=True)
            operation, flag = library.renameat2, 1
        else:
            raise Blocked('atomic_publish_unavailable')
    except AttributeError:
        raise Blocked('atomic_publish_unavailable') from None
    operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), flag) != 0:
        code = ctypes.get_errno()
        raise OSError(code, 'exclusive publication failed')


class Stage:
    def __init__(self, parent, prefix):
        self.parent = parent
        self.name = prefix + uuid.uuid4().hex
        os.mkdir(self.name, 0o700, dir_fd=parent)
        self.fd = os.open(self.name, DIRECTORY_FLAGS, dir_fd=parent)
        self.identity = identity(os.fstat(self.fd))
        self.children = {}

    def __enter__(self):
        return self

    def write(self, name, data):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        with descriptor(os.open(name, flags, 0o600, dir_fd=self.fd)) as fd:
            self.children[name] = (identity(os.fstat(fd)), False)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                require(written > 0, 'storage_io')
                view = view[written:]
            os.fsync(fd)

    def mkdir(self, name):
        os.mkdir(name, 0o700, dir_fd=self.fd)
        self.children[name] = (identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False)), True)
        with descriptor(os.open(name, DIRECTORY_FLAGS, dir_fd=self.fd)) as fd:
            os.fsync(fd)

    def check(self):
        require(identity(os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)) == self.identity,
                'staging_changed')
        require(names(self.fd, len(self.children) + 1, 'staging_changed') == set(self.children), 'staging_changed')
        for name, (expected, _) in self.children.items():
            require(identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == expected, 'staging_changed')

    def __exit__(self, *_):
        try:
            self.check()
            for name, (_, is_directory) in self.children.items():
                if is_directory:
                    os.rmdir(name, dir_fd=self.fd)
                else:
                    os.unlink(name, dir_fd=self.fd)
            os.rmdir(self.name, dir_fd=self.parent)
        except (OSError, Blocked):
            pass
        finally:
            os.close(self.fd)


def initialize(path):
    path = Path(path)
    require(path.name and path.name not in ('.', '..'), 'library_path')
    with descriptor(directory(path.parent)) as parent:
        with Stage(parent, '.azhou-dream-init-') as stage:
            stage.write(LOCK_NAME, LOCK_CONTENT)
            stage.write(MARKER, owner_bytes(stage.children[LOCK_NAME][0]))
            stage.mkdir('objects')
            stage.mkdir('incoming')
            os.fsync(stage.fd)
            stage.check()
            try:
                publish_directory(parent, stage.name, parent, path.name)
                os.fsync(parent)
            except OSError as error:
                if error.errno != errno.EEXIST:
                    raise


@dataclass(frozen=True)
class Package:
    archive: bytes
    digest: str
    theme: dict
    files: dict

    def record(self):
        return {'schema': 'azhou-agent-skin.dream-source-package.v1', 'format': 'dream-simple-v1',
                'storageStatus': 'imported', 'archiveSha256': self.digest,
                'applyStatus': 'blocked', 'reason': 'hub_mapping_unimplemented', 'theme': self.theme,
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                          for name, data in sorted(self.files.items())}}


def validate_package(data):
    try:
        require(type(data) is bytes and 0 < len(data) <= preflight.ARCHIVE_LIMIT, 'archive_size')
        files = preflight.package_files(data)
        theme = json.loads(files['theme.json'].decode('utf-8'), object_pairs_hook=preflight.unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        response = preflight.reference_adapter(files['theme.json'], THEME_ADAPTER)
        require(response == {'schema': 'azhou-agent-skin.reference-official-theme.v1',
                             'contract': 'codex-dream-official-theme/6fc42df4', 'status': 'passed', 'reasons': []},
                'official_theme_validation_blocked')
        require(set(files) == {'theme.json', 'theme.css', theme['image']}, 'required_files')
        preflight.inspect_image(theme['image'], files[theme['image']])
        require(preflight.reference_css(files['theme.css'])['status'] == 'passed', 'safe_css_validation_blocked')
        return Package(data, hashlib.sha256(data).hexdigest(), theme, files)
    except Blocked:
        raise
    except (OSError, ValueError, KeyError, TypeError, RecursionError, zipfile.BadZipFile,
            NotImplementedError, RuntimeError, EOFError, preflight.struct.error, zlib.error):
        raise Blocked('package_invalid') from None


class Library:
    def __init__(self, path, create=False):
        self.path = Path(path)
        self.create = create
        self.stack = ExitStack()

    def __enter__(self):
        try:
            try:
                root = directory(self.path)
            except FileNotFoundError:
                require(self.create, 'library_missing')
                initialize(self.path)
                root = directory(self.path)
            self.root = self.stack.enter_context(descriptor(root))
            self.root_identity = identity(os.fstat(root))
            require(names(root, 5, 'library_unknown') == {MARKER, LOCK_NAME, 'objects', 'incoming'}, 'library_unknown')
            self.owner, self.lock_identity = read_owner(root)
            self.lock = self.stack.enter_context(descriptor(os.open(LOCK_NAME, FILE_FLAGS, dir_fd=root)))
            self.check_lock()
            self.objects = self.stack.enter_context(descriptor(os.open('objects', DIRECTORY_FLAGS, dir_fd=root)))
            self.incoming = self.stack.enter_context(descriptor(os.open('incoming', DIRECTORY_FLAGS, dir_fd=root)))
            self.objects_identity = identity(os.fstat(self.objects))
            self.incoming_identity = identity(os.fstat(self.incoming))
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *_):
        self.stack.close()

    def check(self):
        with descriptor(directory(self.path)) as current:
            require(identity(os.fstat(current)) == self.root_identity, 'library_changed')
        require(names(self.root, 5, 'library_unknown') == {MARKER, LOCK_NAME, 'objects', 'incoming'}, 'library_unknown')
        require(read_regular(self.root, MARKER, 512) == self.owner, 'library_changed')
        self.check_lock()
        for name, expected in [('objects', self.objects_identity), ('incoming', self.incoming_identity)]:
            require(identity(os.stat(name, dir_fd=self.root, follow_symlinks=False)) == expected, 'library_changed')

    def check_lock(self):
        before = os.fstat(self.lock)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and identity(before) == self.lock_identity and before.st_size == len(LOCK_CONTENT), 'library_lock_changed')
        require(os.pread(self.lock, len(LOCK_CONTENT) + 1, 0) == LOCK_CONTENT, 'library_lock_changed')
        after = os.fstat(self.lock)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and identity(os.stat(LOCK_NAME, dir_fd=self.root, follow_symlinks=False)) == self.lock_identity,
                'library_lock_changed')

    @contextmanager
    def exclusive(self):
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        locked = False
        try:
            while not locked:
                self.check()
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except BlockingIOError:
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, 'library_busy')
                    time.sleep(min(0.02, remaining))
            self.check()
            yield
            self.check()
        finally:
            if locked:
                fcntl.flock(self.lock, fcntl.LOCK_UN)

    def digests(self):
        values = names(self.objects, CATALOG_LIMIT, 'library_size')
        require(all(re.fullmatch('[0-9a-f]{64}', value) for value in values), 'library_unknown')
        return sorted(values)

    def read(self, digest):
        require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'archive_digest')
        with descriptor(os.open(digest, DIRECTORY_FLAGS, dir_fd=self.objects)) as object_fd:
            require(names(object_fd, 2, 'stored_object_invalid') == {'archive.zip'}, 'stored_object_invalid')
            data = read_regular(object_fd, 'archive.zip', preflight.ARCHIVE_LIMIT)
            require(hashlib.sha256(data).hexdigest() == digest, 'stored_archive_hash_mismatch')
            package = validate_package(data)
            require(identity(os.stat(digest, dir_fd=self.objects, follow_symlinks=False)) == identity(os.fstat(object_fd)),
                    'stored_object_changed')
            self.check()
            return package

    def store(self, package):
        if package.digest in self.digests():
            require(self.read(package.digest).archive == package.archive, 'stored_object_invalid')
            return True
        with Stage(self.incoming, '.package-') as stage:
            stage.write('archive.zip', package.archive)
            require(read_regular(stage.fd, 'archive.zip', preflight.ARCHIVE_LIMIT) == package.archive, 'staging_changed')
            os.fsync(stage.fd)
            with self.exclusive():
                values = self.digests()
                idempotent = package.digest in values
                if not idempotent:
                    require(len(values) < CATALOG_LIMIT, 'library_size')
                    stage.check()
                    try:
                        publish_directory(self.incoming, stage.name, self.objects, package.digest)
                        require(identity(os.stat(package.digest, dir_fd=self.objects, follow_symlinks=False)) == stage.identity,
                                'staging_changed')
                        require(names(stage.fd, 2, 'staging_changed') == {'archive.zip'}, 'staging_changed')
                        require(read_regular(stage.fd, 'archive.zip', preflight.ARCHIVE_LIMIT) == package.archive, 'staging_changed')
                        os.fsync(self.objects)
                        os.fsync(self.incoming)
                    except OSError as error:
                        if error.errno != errno.EEXIST:
                            raise
                        idempotent = True
            if idempotent:
                require(self.read(package.digest).archive == package.archive, 'stored_object_invalid')
            return idempotent


def import_package(source, library):
    package = validate_package(read_source(source))
    with Library(library, create=True) as store:
        idempotent = store.store(package)
    return {**package.record(), 'idempotent': idempotent}


def read_package(library, digest):
    require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'archive_digest')
    with Library(library) as store:
        return store.read(digest)


def list_packages(library):
    entries = []
    with Library(library) as store:
        for digest in store.digests():
            try:
                entries.append(store.read(digest).record())
            except (Blocked, OSError) as error:
                entries.append({'archiveSha256': digest, 'storageStatus': 'blocked', 'applyStatus': 'blocked',
                                'reason': str(error) if isinstance(error, Blocked) else 'stored_object_unavailable'})
        store.check()
    partial = any(entry['storageStatus'] != 'imported' for entry in entries)
    return {'schema': 'azhou-agent-skin.dream-source-library.v1', 'entries': entries,
            'storageStatus': 'partial' if partial else 'imported', 'applyStatus': 'blocked',
            'reason': 'library_contains_blocked_objects' if partial else 'hub_mapping_unimplemented'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('import').add_argument('archive', type=Path)
    commands.add_parser('list')
    commands.add_parser('read').add_argument('digest')
    commands.add_parser('export-capsule').add_argument('digest')
    args = parser.parse_args()
    try:
        if args.command == 'import':
            result = import_package(args.archive, args.library)
        elif args.command == 'export-capsule':
            package = read_package(args.library, args.digest)
            capsule = {'schema': 'azhou-agent-skin.dream-capsule.v1', 'archiveSha256': package.digest,
                       'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                                        'base64': base64.b64encode(data).decode('ascii')}
                                 for name, data in sorted(package.files.items())}}
            print(json.dumps(capsule, sort_keys=True, separators=(',', ':')))
            return 0
        elif args.command == 'read':
            result = read_package(args.library, args.digest).record()
        else:
            result = list_packages(args.library)
        code = 2 if result['storageStatus'] == 'partial' else 0
    except (Blocked, OSError) as error:
        result = {'storageStatus': 'blocked', 'applyStatus': 'blocked',
                  'reason': str(error) if isinstance(error, Blocked) else 'storage_io'}
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

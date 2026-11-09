#!/usr/bin/env python3
"""Install one Azhou app from an unregistered payload; retire proven project copies."""
import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / 'tools/verify-artifacts.py'))
EXPECTED = HELPERS['IDENTITY']
KNOWN = tuple(HELPERS['KNOWN_IDENTITIES'])
SOURCE = HELPERS['PAYLOAD']
REGISTRY_TOOL = HELPERS['REGISTRY_TOOL']
DESTINATION = Path.home() / 'Applications' / HELPERS['NAME']
DIST = ROOT / 'dist'
PROJECT_ID = 'azhou.codex-startup-animation'
OFFICIAL_ID = 'com.openai.codex'
LEGACY_SHA256 = '7a39526e155c2b1fd06d1f60dc74f3d6cf3e85a7bdf3d5e86b0e1381828fc680'
LSREGISTER = '/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
fingerprint = HELPERS['fingerprint']
swap = HELPERS['swap']


def publish_exclusive(source, destination):
    rename_excl = 0x00000004
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    rename = libc.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(os.fsencode(source), os.fsencode(destination), rename_excl) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise RuntimeError('规范入口被其他操作创建，未覆盖。')
        raise OSError(error, os.strerror(error), str(destination))


def version_key(info):
    def number(value):
        value = str(value)
        if not re.fullmatch(r'\d+(?:\.\d+){0,3}', value):
            raise RuntimeError(f'版本格式未知，保留应用：{value!r}')
        parts = tuple(int(part) for part in value.split('.'))
        return parts + (0,) * (4 - len(parts))
    return (number(info.get('CFBundleShortVersionString', '')),
            number(info.get('CFBundleVersion', '')))


def verify(path):
    HELPERS['verify_product'](path)
    return HELPERS['require'](path, EXPECTED)


def receipt_path():
    local = ROOT / '.local'
    record = local / 'installation.json'
    if local.is_symlink() or record.is_symlink():
        raise RuntimeError('拒绝通过符号链接读取或写入安装记录。')
    return record


def read_receipt():
    record = receipt_path()
    if not record.exists():
        return {}
    result = json.loads(record.read_text())
    if not isinstance(result, dict):
        raise RuntimeError('安装记录格式未知，未修改应用。')
    return result


def save_receipt(record):
    destination = receipt_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.installation-', suffix='.json', dir=destination.parent)
    expected = None
    published = False

    def matches_owned():
        if expected is None:
            return False
        try:
            HELPERS['require_file'](name, expected)
            return True
        except (OSError, RuntimeError):
            return False

    try:
        with os.fdopen(descriptor, 'w') as stream:
            data = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            identity = os.fstat(stream.fileno())
            expected = [identity.st_dev, identity.st_ino, identity.st_mode & 0o777,
                        hashlib.sha256(data.encode(stream.encoding)).hexdigest()]
        if not matches_owned():
            raise RuntimeError(f'安装回执暂存内容发生变化，保留待核对：{name}')
        os.replace(name, destination)
        published = True
    finally:
        if not published and matches_owned():
            Path(name).unlink()


@contextlib.contextmanager
def file_lock(path):
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RuntimeError(f'安装锁目录不是实体目录：{path.parent}')
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('另一个项目安装正在进行，请待其结束后重试。') from error
        yield
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def install_lock(check_only, old_root=None):
    if check_only:
        yield
        return
    local = receipt_path().parent
    local.mkdir(parents=True, exist_ok=True)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        stack.enter_context(file_lock(DESTINATION.parent / '.azhou-startup-install.lock'))
        stack.enter_context(file_lock(local / 'install.lock'))
        if old_root is not None:
            old_local = old_root / '.local'
            if old_local.is_symlink() or not old_local.is_dir():
                raise RuntimeError('旧安装记录目录不是实体目录。')
            stack.enter_context(file_lock(old_local / 'install.lock'))
        yield


def migration_root(value):
    old_root = Path(value)
    if (not old_root.is_absolute() or old_root.is_symlink() or not old_root.is_dir()
            or old_root != old_root.resolve(strict=True) or old_root == ROOT):
        raise RuntimeError('旧项目路径必须是不同于当前项目的绝对实体目录。')
    return old_root


def managed_install_path(value):
    """Limit receipt paths to one direct app entry; ownership still requires full proof."""
    if not isinstance(value, str):
        return None
    path = Path(value)
    if (not path.is_absolute() or str(path) != value
            or path.parent != DESTINATION.parent or path.suffix != '.app'):
        return None
    return path


def old_install_proof(old_root):
    """Authorize exactly the currently installed old-root package, never a root wildcard."""
    record_path = old_root / '.local/installation.json'
    old_source = old_root / '.build/azhou-payload'
    if (record_path.is_symlink() or not record_path.is_file()
            or old_source.parent.is_symlink() or old_source.is_symlink()
            or not old_source.is_dir()):
        raise RuntimeError('旧安装记录或构建载荷缺失，不能接管。')
    record = json.loads(record_path.read_text())
    if not isinstance(record, dict):
        raise RuntimeError('旧安装记录格式无效，不能接管。')
    installed_path = record.get('installedPath')
    if managed_install_path(installed_path) is None:
        raise RuntimeError('旧安装记录没有证明当前入口归属，不能接管。')
    required = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(old_root),
                'installedPath': installed_path, 'sourcePath': str(old_source),
                'bundleID': EXPECTED[0], 'executable': EXPECTED[1]}
    if (any(record.get(key) != value for key, value in required.items())
            or record.get('status') not in ('installed', 'current', 'consolidated')
            or not re.fullmatch(r'[0-9a-f]{64}', str(record.get('sha256Tree', '')))):
        raise RuntimeError('旧安装记录没有证明当前入口归属，不能接管。')
    old_hash = record['sha256Tree']
    for path in (old_source, Path(installed_path)):
        info = HELPERS['require'](path, EXPECTED)
        marker = HELPERS['read_marker'](path, required=True)
        if (marker['projectID'] != PROJECT_ID or marker['projectRoot'] != str(old_root)
                or marker['bundleID'] != EXPECTED[0] or marker['executable'] != EXPECTED[1]
                or info.get('CFBundleShortVersionString') != record.get('version')
                or str(info.get('CFBundleVersion')) != str(record.get('build'))
                or fingerprint(path) != old_hash):
            raise RuntimeError(f'旧包与安装记录不一致，不能接管：{path}')
        HELPERS['verify_icon'](path, info)
        HELPERS['verify_wallpaper'](path, info, marker)
        subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)], check=True)
    old_dist = old_root / 'dist'
    if old_dist.is_symlink() or (old_dist.exists() and not old_dist.is_dir()):
        raise RuntimeError('旧输出目录不是实体目录，不能接管。')
    if old_dist.exists() and any(path.suffix.lower() == '.app' for path in old_dist.iterdir()):
        raise RuntimeError('旧输出目录仍有应用，不能接管。')
    return {'oldRoot': str(old_root), 'installedPath': installed_path, 'oldSHA256': old_hash}


def recheck_handoff(old_root, expected):
    if old_install_proof(old_root) != expected:
        raise RuntimeError('旧安装归属在交换前发生变化，未替换。')


def trusted_receipt(record):
    return record.get('projectID') == PROJECT_ID and record.get('projectRoot') == str(ROOT)


def retired_records(record):
    if not trusted_receipt(record):
        return []
    accepted = []
    for item in record.get('retiredArtifacts', []):
        path = Path(item.get('path', ''))
        identity = (item.get('bundleID'), item.get('executable'))
        if (path.is_absolute() and path.parent in (DESTINATION.parent, DIST)
                and path != DESTINATION and identity in KNOWN
                and re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256Tree', '')))):
            accepted.append(item)
    return accepted


import hashlib
import stat


def _same_inode(first, second):
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _require_retirement_fd_support():
    required = {os.open, os.stat, os.unlink, os.rmdir, os.access}
    if (not required.issubset(os.supports_dir_fd) or not {os.scandir, os.listdir}.issubset(os.supports_fd)
            or not {os.stat, os.access}.issubset(os.supports_follow_symlinks)):
        raise RuntimeError('系统缺少安全清理所需的目录描述符支持。')
    if any(not hasattr(os, name) for name in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_CLOEXEC', 'O_NONBLOCK')):
        raise RuntimeError('系统缺少安全清理所需的目录打开标志。')


def _require_retirement_identity(directory_fd, expected):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    identity, info = HELPERS['identity_at_fd'](directory_fd)
    if identity != expected:
        raise RuntimeError('隔离包身份不匹配。')
    contents = os.open('Contents', flags | os.O_DIRECTORY, dir_fd=directory_fd)
    try:
        executable_dir = os.open('MacOS', flags | os.O_DIRECTORY, dir_fd=contents)
        try:
            executable = os.open(expected[1], flags | os.O_NONBLOCK, dir_fd=executable_dir)
            try:
                metadata = os.fstat(executable)
                if (not stat.S_ISREG(metadata.st_mode)
                        or not _same_inode(metadata, os.stat(expected[1], dir_fd=executable_dir, follow_symlinks=False))
                        or not os.access(expected[1], os.X_OK, dir_fd=executable_dir, follow_symlinks=False)):
                    raise RuntimeError('隔离包缺少有效的可执行文件。')
            finally:
                os.close(executable)
        finally:
            os.close(executable_dir)
        if not _same_inode(os.fstat(contents), os.stat('Contents', dir_fd=directory_fd, follow_symlinks=False)):
            raise RuntimeError('隔离包目录在核验期间发生变化。')
        return info
    finally:
        os.close(contents)


def _fingerprint_retirement_directory(directory_fd, with_evidence=False):
    files = []
    evidence = {}
    root_device = os.fstat(directory_fd).st_dev

    def collect(parent_fd, parts):
        with os.scandir(parent_fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if observed.st_dev != root_device:
                raise RuntimeError('隔离副本跨越文件系统边界，已停止核验。')
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if stat.S_ISDIR(observed.st_mode):
                child = os.open(name, flags | os.O_DIRECTORY, dir_fd=parent_fd)
                try:
                    if not _same_inode(observed, os.fstat(child)):
                        raise RuntimeError('隔离目录在核验期间发生变化。')
                    evidence[(*parts, name)] = ('directory', observed.st_dev, observed.st_ino, observed.st_mode)
                    collect(child, (*parts, name))
                    if not _same_inode(os.fstat(child), os.stat(name, dir_fd=parent_fd, follow_symlinks=False)):
                        raise RuntimeError('隔离目录在核验期间发生变化。')
                finally:
                    os.close(child)
            elif stat.S_ISREG(observed.st_mode):
                child = os.open(name, flags | os.O_NONBLOCK, dir_fd=parent_fd)
                try:
                    before = os.fstat(child)
                    if not _same_inode(observed, before):
                        raise RuntimeError('隔离文件在核验期间发生变化。')
                    digest = hashlib.sha256()
                    while chunk := os.read(child, 64 * 1024):
                        digest.update(chunk)
                    after = os.fstat(child)
                    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')
                    if (any(getattr(before, key) != getattr(after, key) for key in fields)
                            or not _same_inode(after, os.stat(name, dir_fd=parent_fd, follow_symlinks=False))):
                        raise RuntimeError('隔离文件在核验期间发生变化。')
                    evidence[(*parts, name)] = ('file', *(getattr(after, key) for key in fields))
                    files.append(((*parts, name), before.st_mode & 0o777, digest.digest()))
                finally:
                    os.close(child)
            else:
                raise RuntimeError('隔离副本包含非普通文件，已停止核验。')

    collect(directory_fd, ())
    result = hashlib.sha256()
    for parts, mode, digest in sorted(files):
        result.update('/'.join(parts).encode())
        result.update(b'\0')
        result.update(str(mode).encode())
        result.update(b'\0')
        result.update(digest)
    return (result.hexdigest(), evidence) if with_evidence else result.hexdigest()


def _verify_displaced_entry(entry, path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = _require_retirement_identity(descriptor, entry['identity'])
        if (version_key(info) != entry['versionKey']
                or _fingerprint_retirement_directory(descriptor) != entry['sha256Tree']
                or not _same_inode(os.fstat(descriptor), os.stat(path, follow_symlinks=False))):
            raise RuntimeError('隔离副本与原候选不一致。')
    except Exception as error:
        raise RuntimeError(f'候选在核查后发生变化，未替换或删除：{path}') from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _remove_retirement_contents(directory_fd, evidence, parts=(), guard=None):
    if guard is not None:
        guard()
    with os.scandir(directory_fd) as entries:
        names = sorted(entry.name for entry in entries)
    expected_names = {path[-1] for path in evidence if len(path) == len(parts) + 1 and path[:-1] == parts}
    if set(names) != expected_names:
        raise RuntimeError('隔离目录内容在清理期间发生变化。')
    for name in names:
        if guard is not None:
            guard()
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        expected = evidence[(*parts, name)]
        if stat.S_ISDIR(observed.st_mode):
            if expected != ('directory', observed.st_dev, observed.st_ino, observed.st_mode):
                raise RuntimeError('隔离目录在清理期间发生变化。')
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
            try:
                if not _same_inode(observed, os.fstat(child)):
                    raise RuntimeError('隔离目录在清理期间发生变化。')
                _remove_retirement_contents(child, evidence, (*parts, name), guard)
                if not _same_inode(os.fstat(child), os.stat(name, dir_fd=directory_fd, follow_symlinks=False)):
                    raise RuntimeError('隔离目录在清理期间发生变化。')
                if guard is not None:
                    guard()
                os.rmdir(name, dir_fd=directory_fd)
            finally:
                os.close(child)
        elif stat.S_ISREG(observed.st_mode):
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')
            if expected != ('file', *(getattr(observed, key) for key in fields)):
                raise RuntimeError('隔离文件在清理期间发生变化。')
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory_fd)
            try:
                current = os.fstat(child)
                final = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if (expected != ('file', *(getattr(current, key) for key in fields))
                        or expected != ('file', *(getattr(final, key) for key in fields))):
                    raise RuntimeError('隔离文件在清理期间发生变化。')
                if guard is not None:
                    guard()
                os.unlink(name, dir_fd=directory_fd)
            finally:
                os.close(child)
        else:
            raise RuntimeError('隔离副本包含非普通文件，已停止清理。')


def _clean_install_work(directory, expected_hash, expected_root, expected_payload):
    _require_retirement_fd_support()
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    descriptor = None
    try:
        if (not _same_inode(os.fstat(directory_fd), expected_root)
                or not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))):
            raise RuntimeError('安装临时目录发生变化。')
        names = set(os.listdir(directory_fd))
        if names - {'payload'}:
            raise RuntimeError('安装临时目录包含未识别内容。')
        if 'payload' in names:
            _require_retirement_fd_support()
            descriptor = os.open('payload', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
            if os.fstat(descriptor).st_dev != os.fstat(directory_fd).st_dev:
                raise RuntimeError('隔离副本跨越文件系统边界，已停止清理。')
            if expected_payload is None or not _same_inode(os.fstat(descriptor), expected_payload):
                raise RuntimeError('安装临时载荷身份发生变化。')
            digest, evidence = _fingerprint_retirement_directory(descriptor, with_evidence=True)
            if digest != expected_hash:
                raise RuntimeError('安装临时副本与已验证内容不一致。')

            def guard():
                if (not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))
                        or not _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False))):
                    raise RuntimeError('安装临时位置发生变化。')

            guard()
            _remove_retirement_contents(descriptor, evidence, guard=guard)
            guard()
            os.rmdir('payload', dir_fd=directory_fd)
        if os.listdir(directory_fd) or not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False)):
            raise RuntimeError('安装临时目录发生变化。')
        os.rmdir(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)


def recover_retirement(record, read_only=False):
    pending = record.get('retirementPending')
    if pending is None:
        return record
    if read_only:
        raise RuntimeError('旧入口清理尚未恢复，请先完成安装恢复。')
    if not trusted_receipt(record) or not isinstance(pending, dict):
        raise RuntimeError('待恢复的旧入口记录无效，未进行任何清理。')
    original, stage = pending.get('path'), pending.get('stage')
    retired = {item['path']: item for item in retired_records(record)}
    if not isinstance(original, str) or original not in retired or not isinstance(stage, str):
        raise RuntimeError('待恢复的旧入口记录无效，未进行任何清理。')
    target, payload = Path(original), Path(stage)
    directory = payload.parent
    if (str(target) != original or str(payload) != stage or payload.name != 'payload'
            or directory.parent != target.parent or not directory.name.startswith('.azhou-retire-')
            or target.parent.is_symlink() or not target.parent.is_dir() or directory.is_symlink()):
        raise RuntimeError('待恢复的旧入口路径无效，未进行任何清理。')
    item = retired[original]
    _require_retirement_fd_support()
    if payload.exists() or payload.is_symlink():
        if target.exists() or target.is_symlink():
            raise RuntimeError(f'旧入口恢复受阻，临时副本保留在 {payload}。')
        descriptor = None
        try:
            try:
                descriptor = os.open(payload, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                _require_retirement_identity(descriptor, (item['bundleID'], item['executable']))
                if (not _same_inode(os.fstat(descriptor), os.stat(payload, follow_symlinks=False))
                        or _fingerprint_retirement_directory(descriptor) != item['sha256Tree']):
                    raise RuntimeError('隔离副本内容发生变化')
            except Exception as error:
                raise RuntimeError(f'隔离副本无法验证，已保留：{payload}。') from error
            publish_exclusive(payload, target)
            try:
                if (not _same_inode(os.fstat(descriptor), os.stat(target, follow_symlinks=False))
                        or _fingerprint_retirement_directory(descriptor) != item['sha256Tree']):
                    raise RuntimeError('恢复时隔离副本发生变化')
            except Exception as error:
                raise RuntimeError(f'旧入口恢复期间发生变化，临时目录已保留：{directory}。') from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
    elif target.exists() or target.is_symlink():
        descriptor = None
        try:
            descriptor = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            _require_retirement_identity(descriptor, (item['bundleID'], item['executable']))
            if (_fingerprint_retirement_directory(descriptor) != item['sha256Tree']
                    or not _same_inode(os.fstat(descriptor), os.stat(target, follow_symlinks=False))):
                raise RuntimeError('原路径内容发生变化')
        except Exception as error:
            raise RuntimeError(f'旧入口恢复受阻，原位置已变化并保留：{target}。') from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
    if directory.exists():
        try:
            directory.rmdir()
        except OSError as error:
            raise RuntimeError(f'旧入口临时目录未清空，已保留：{directory}。') from error
    record = {key: value for key, value in record.items() if key != 'retirementPending'}
    save_receipt(record)
    return record


def retire_entry(entry, record):
    _require_retirement_fd_support()
    target = entry['path']
    directory = Path(tempfile.mkdtemp(prefix='.azhou-retire-', dir=target.parent))
    payload = directory / 'payload'
    record['retirementPending'] = {'path': str(target), 'stage': str(payload)}
    descriptor = None
    directory_fd = None
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        if not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False)):
            raise RuntimeError(f'隔离目录发生变化，已保留：{directory}。')
        save_receipt(record)
        publish_exclusive(target, payload)
        try:
            if not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False)):
                raise RuntimeError('隔离目录在移动期间发生变化。')
            descriptor = os.open('payload', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
            if os.fstat(descriptor).st_dev != os.fstat(directory_fd).st_dev:
                raise RuntimeError('隔离副本跨越文件系统边界，已停止清理。')
            info = _require_retirement_identity(descriptor, entry['identity'])
            if version_key(info) != entry['versionKey']:
                raise RuntimeError('隔离包版本发生变化。')
            if not _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False)):
                raise RuntimeError('隔离目录在核验期间发生变化。')
            digest, evidence = _fingerprint_retirement_directory(descriptor, with_evidence=True)
            if digest != entry['sha256Tree']:
                raise RuntimeError('隔离副本内容在核验期间发生变化。')
            if (not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))
                    or not _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False))):
                raise RuntimeError('隔离目录在核验期间发生变化。')
        except BaseException as error:
            try:
                unchanged_directory = _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))
            except OSError:
                unchanged_directory = False
            if not unchanged_directory:
                raise RuntimeError(f'隔离位置发生变化，临时目录已保留：{directory}。') from error
            if descriptor is not None:
                try:
                    unchanged_path = _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False))
                except OSError:
                    unchanged_path = False
                if not unchanged_path:
                    raise RuntimeError(f'隔离位置发生变化，临时目录已保留：{directory}。') from error
            if isinstance(error, Exception):
                raise RuntimeError(f'隔离副本无法验证，已保留：{payload}。') from error
            raise
        try:
            def guard():
                if (not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))
                        or not _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False))):
                    raise RuntimeError('隔离目录在清理期间发生变化。')
            _remove_retirement_contents(descriptor, evidence, guard=guard)
            guard()
            os.rmdir('payload', dir_fd=directory_fd)
        except BaseException as removal_error:
            try:
                if (not _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False))
                        or not _same_inode(os.fstat(descriptor), os.stat('payload', dir_fd=directory_fd, follow_symlinks=False))):
                    raise RuntimeError('隔离位置发生变化')
                info = _require_retirement_identity(descriptor, entry['identity'])
                if (version_key(info) != entry['versionKey']
                        or _fingerprint_retirement_directory(descriptor) != entry['sha256Tree']):
                    raise RuntimeError('隔离副本内容发生变化。')
                publish_exclusive(payload, target)
            except BaseException as recovery_error:
                raise RuntimeError(f'旧入口清理未完成，临时副本保留在 {payload}。') from recovery_error
            record.pop('retirementPending')
            save_receipt(record)
            raise removal_error
        record.pop('retirementPending')
        save_receipt(record)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if directory_fd is not None and _same_inode(os.fstat(directory_fd), os.stat(directory, follow_symlinks=False)):
                directory.rmdir()
        except OSError:
            pass
        finally:
            if directory_fd is not None:
                os.close(directory_fd)


def pending_legacy_handoff(old_root, source_hash, record):
    if not trusted_receipt(record) or record.get('status') not in ('source-handoff-pending', 'cleanup-pending'):
        return None
    previous = record.get('sourceHandoff')
    if (not isinstance(previous, dict) or previous.get('oldRoot') != str(old_root)
            or previous.get('newRoot') != str(ROOT) or previous.get('newSHA256') != source_hash
            or not re.fullmatch(r'[0-9a-f]{64}', str(previous.get('oldSHA256', '')))):
        return None
    legacy_path = managed_install_path(previous.get('oldInstalledPath',
                                                   str(DESTINATION.with_name(HELPERS['LEGACY_NAME']))))
    if legacy_path is None or legacy_path == DESTINATION:
        return None
    retired = any(item.get('path') == str(legacy_path)
                  and item.get('bundleID') == EXPECTED[0]
                  and item.get('executable') == EXPECTED[1]
                  and item.get('sha256Tree') == previous['oldSHA256']
                  and item.get('proof') == 'verified-source-handoff'
                  for item in retired_records(record))
    if ((record.get('status') == 'cleanup-pending' and not retired)
            or not (legacy_path.exists() or legacy_path.is_symlink())):
        return None
    proof = old_install_proof(old_root)
    if (proof['installedPath'] != str(legacy_path)
            or proof['oldSHA256'] != previous['oldSHA256']):
        raise RuntimeError('旧安装与待完成的来源接管记录不一致，不能继续清理。')
    return proof


def scan_apps(source_info, source_hash, record, handoff=None):
    """Only immediate real .app directories in the two managed locations."""
    raw, dist_entities, conflicts = {}, [], []
    known_ids = {identity[0] for identity in KNOWN}
    for directory in (DESTINATION.parent, DIST):
        if directory.is_symlink():
            raise RuntimeError(f'拒绝扫描符号链接目录：{directory}')
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise RuntimeError(f'应用目录不是目录：{directory}')
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() != '.app':
                continue
            if path.is_symlink():
                if path == DESTINATION or directory == DIST:
                    conflicts.append(f'符号链接入口已保留：{path}')
                continue
            if not path.is_dir():
                if path == DESTINATION:
                    conflicts.append(f'规范入口不是实体应用：{path}')
                continue
            if directory == DIST:
                dist_entities.append(path)
            try:
                actual, info = HELPERS['identity'](path)
            except (OSError, ValueError, RuntimeError) as error:
                if path == DESTINATION or directory == DIST:
                    conflicts.append(f'无法核实的应用已保留：{path}；{error}')
                continue
            if actual[0] == OFFICIAL_ID or actual[0] not in known_ids:
                if path == DESTINATION or directory == DIST:
                    conflicts.append(f'非项目应用已保留，不能占用项目入口或输出目录：{path}；{actual!r}')
                continue
            try:
                if actual not in KNOWN:
                    raise RuntimeError(f'项目 ID 与主可执行文件不匹配：{actual!r}')
                HELPERS['require'](path, actual)
                if not (path / 'Contents/Resources/web/index.html').is_file():
                    raise RuntimeError('缺少项目 web 资源')
                raw[path] = {'path': path, 'identity': actual, 'info': info,
                             'sha256Tree': fingerprint(path), 'versionKey': version_key(info)}
            except (OSError, ValueError, RuntimeError) as error:
                conflicts.append(f'无法核实的项目候选已保留：{path}；{error}')
    legacy_install_paths = (DESTINATION, DESTINATION.with_name(HELPERS['LEGACY_NAME']))
    legacy_dist_paths = (DIST / HELPERS['NAME'], DIST / HELPERS['LEGACY_NAME'])
    old_receipt = (record.get('sha256Tree') == LEGACY_SHA256
                   and record.get('installedPath') in tuple(str(path) for path in legacy_install_paths)
                   and record.get('sourcePath') in tuple(str(path) for path in legacy_dist_paths)
                   and record.get('bundleID') == EXPECTED[0] and record.get('version') == '0.5.0')
    history = trusted_receipt(record) and LEGACY_SHA256 in record.get('managedFingerprints', [])
    matching = [entry for entry in raw.values() if entry['sha256Tree'] == LEGACY_SHA256]
    paired = (any(entry['path'] in legacy_install_paths for entry in matching)
              and any(entry['path'] in legacy_dist_paths for entry in matching))
    legacy_proven = old_receipt or history or paired
    confirmed = []
    for entry in raw.values():
        path = entry['path']
        try:
            if entry['versionKey'] > version_key(source_info):
                raise RuntimeError('候选版本高于待安装构建，拒绝降级或删除')
            marker = HELPERS['read_marker'](path, required=False)
            if entry['sha256Tree'] == source_hash:
                proof = 'current-payload-fingerprint'
            elif marker:
                old_entry = (handoff is not None and str(path) == handoff['installedPath']
                             and entry['sha256Tree'] == handoff['oldSHA256']
                             and marker.get('projectID') == PROJECT_ID
                             and marker.get('projectRoot') == handoff['oldRoot'])
                if not old_entry and (marker.get('projectID') != PROJECT_ID or marker.get('projectRoot') != str(ROOT)):
                    raise RuntimeError('来源标记属于其他项目或路径')
                proof = 'verified-source-handoff' if old_entry else 'project-build-marker'
            elif (legacy_proven and entry['path'] in (*legacy_install_paths, *legacy_dist_paths)
                  and entry['sha256Tree'] == LEGACY_SHA256 and entry['identity'] == EXPECTED
                  and entry['info'].get('CFBundleShortVersionString') == '0.5.0'
                  and str(entry['info'].get('CFBundleVersion')) == '2'):
                proof = 'verified-0.5.0-fingerprint'
            else:
                raise RuntimeError('仅有相同名称或身份不足以证明安装来源')
            subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)], check=True)
            entry['proof'] = proof
            confirmed.append(entry)
        except (OSError, ValueError, RuntimeError) as error:
            conflicts.append(f'候选已保留：{path}；{error}')
    if conflicts:
        raise RuntimeError('应用归属或版本存在冲突，未清理：\n' + '\n'.join(conflicts))
    return confirmed, dist_entities


def registry_inventory():
    raw = subprocess.check_output([str(REGISTRY_TOOL), 'inventory'], text=True)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    try:
        result = json.loads(raw, object_pairs_hook=unique_object)
    except (TypeError, ValueError) as error:
        raise RuntimeError('应用登记检查器返回未知格式。') from error
    if (not isinstance(result, dict) or type(result.get('schema')) is not int
            or result['schema'] != 1 or not isinstance(result.get('applications'), list)):
        raise RuntimeError('应用登记检查器返回未知格式。')
    known_ids = {identity[0] for identity in KNOWN}
    inventory = {}
    for group in result['applications']:
        if not isinstance(group, dict) or not isinstance(group.get('bundleID'), str):
            raise RuntimeError('应用登记检查器返回未知格式。')
        bundle_id = group['bundleID']
        if bundle_id not in known_ids or bundle_id in inventory:
            raise RuntimeError('应用登记检查没有覆盖全部已知项目 ID 或存在重复。')
        if not isinstance(group.get('urls'), list):
            raise RuntimeError('应用登记检查器返回未知格式。')
        urls = set()
        for item in group['urls']:
            if not isinstance(item, dict) or not isinstance(item.get('path'), str) or '\0' in item['path']:
                raise RuntimeError('应用登记检查器返回未知格式。')
            path = Path(item['path'])
            if not path.is_absolute():
                raise RuntimeError('应用登记检查返回非绝对路径。')
            urls.add(path)
        inventory[bundle_id] = urls
    if set(inventory) != known_ids:
        raise RuntimeError('应用登记检查没有覆盖全部已知项目 ID。')
    return inventory


def validate_registry_scope(inventory, candidates, record):
    actual = {entry['path'] for entry in candidates}
    historical = {Path(item['path']) for item in retired_records(record)}
    conflicts = []
    for bundle_id, paths in inventory.items():
        for path in paths:
            if path == DESTINATION or path in actual:
                continue
            if path in historical and not path.exists() and not path.is_symlink():
                continue
            conflicts.append(f'{bundle_id}: {path}')
    if conflicts:
        raise RuntimeError('发现未获来源确认或超出清理范围的项目登记，已保留：\n' + '\n'.join(conflicts))


def require_stopped(paths):
    prefixes = tuple(str(path) + '/Contents/MacOS/' for path in paths)
    if not prefixes:
        return
    for line in subprocess.check_output(['/bin/ps', '-axo', 'pid=,comm='], text=True).splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and fields[1].startswith(prefixes):
            raise RuntimeError(f'项目启动动画仍在运行，未替换或移除：{fields[1]}')


def unchanged(entry):
    info = HELPERS['require'](entry['path'], entry['identity'])
    if version_key(info) != entry['versionKey'] or fingerprint(entry['path']) != entry['sha256Tree']:
        raise RuntimeError(f'候选在核查后发生变化，未替换或删除：{entry["path"]}')


def install_payload(source_hash, original, before_swap=None):
    if original:
        _require_retirement_fd_support()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.azhou-install-', dir=DESTINATION.parent))
    temporary_identity = os.stat(temporary, follow_symlinks=False)
    staged = temporary / 'payload'  # Never create a second discoverable .app.
    cleanup = True
    cleanup_hash = source_hash
    cleanup_payload_identity = None
    try:
        subprocess.run(['/usr/bin/ditto', str(SOURCE), str(staged)], check=True)
        staged_identity = os.stat(staged, follow_symlinks=False)
        cleanup_payload_identity = staged_identity
        verify(staged)
        if fingerprint(staged) != source_hash or fingerprint(SOURCE) != source_hash:
            raise RuntimeError('构建载荷在复制期间发生变化，原入口未修改。')
        require_stopped([DESTINATION])
        if original:
            original_identity = os.stat(DESTINATION, follow_symlinks=False)
            unchanged(original)

            def require_positions(stage_identity, target_identity):
                for path, expected in ((temporary, temporary_identity), (staged, stage_identity),
                                       (DESTINATION, target_identity)):
                    actual = os.stat(path, follow_symlinks=False)
                    if not stat.S_ISDIR(actual.st_mode) or not _same_inode(actual, expected):
                        raise RuntimeError(f'安装交换位置发生变化：{path}')

            cleanup = False
            if before_swap is not None:
                try:
                    before_swap()
                except Exception as error:
                    raise RuntimeError(f'预发布核验失败，临时目录已保留：{temporary}；{error}') from error
            try:
                require_positions(staged_identity, original_identity)
                unchanged(original)
                require_positions(staged_identity, original_identity)
            except (OSError, ValueError, RuntimeError) as error:
                raise RuntimeError(f'候选在核查后发生变化，已保留入口和临时目录：{temporary}') from error
            try:
                swap(staged, DESTINATION)
                cleanup_hash = original['sha256Tree']
                cleanup_payload_identity = original_identity
            except BaseException as swap_error:
                try:
                    require_positions(staged_identity, original_identity)
                    unchanged(original)
                    if fingerprint(staged) == source_hash:
                        cleanup = True
                except (OSError, ValueError, RuntimeError):
                    pass
                if not cleanup:
                    raise RuntimeError(f'安装交换结果未确认，已保留入口和临时目录：{temporary}') from swap_error
                raise
            try:
                require_positions(original_identity, staged_identity)
                _verify_displaced_entry(original, staged)
                verify(DESTINATION)
                if fingerprint(DESTINATION) != source_hash:
                    raise RuntimeError('安装后内容校验失败。')
                require_positions(original_identity, staged_identity)
            except BaseException as verification_error:
                try:
                    require_positions(original_identity, staged_identity)
                    _verify_displaced_entry(original, staged)
                    if fingerprint(DESTINATION) != source_hash:
                        raise RuntimeError('新入口内容发生变化')
                    require_positions(original_identity, staged_identity)
                    swap(staged, DESTINATION)
                    require_positions(staged_identity, original_identity)
                    cleanup_hash = source_hash
                    cleanup_payload_identity = staged_identity
                except BaseException as rollback_error:
                    raise RuntimeError(f'安装校验失败且回滚未完成；请保留入口及临时目录待核对：{temporary}') from rollback_error
                cleanup = True
                raise verification_error
            cleanup = True
        else:
            if DESTINATION.exists() or DESTINATION.is_symlink():
                raise RuntimeError('规范入口被其他操作创建，未覆盖。')
            cleanup = False
            if before_swap is not None:
                try:
                    before_swap()
                except Exception as error:
                    raise RuntimeError(f'预发布核验失败，临时目录已保留：{temporary}；{error}') from error
            try:
                current_root = os.stat(temporary, follow_symlinks=False)
                current_stage = os.stat(staged, follow_symlinks=False)
                if (not stat.S_ISDIR(current_root.st_mode) or not _same_inode(current_root, temporary_identity)
                        or not stat.S_ISDIR(current_stage.st_mode) or not _same_inode(current_stage, staged_identity)):
                    raise RuntimeError('入口暂存身份发生变化')
            except (OSError, RuntimeError) as error:
                cleanup = False
                raise RuntimeError(f'安装暂存发生变化，已保留：{temporary}') from error
            cleanup = True
            publish_exclusive(staged, DESTINATION)
            try:
                verify(DESTINATION)
                if fingerprint(DESTINATION) != source_hash:
                    raise RuntimeError('安装后内容校验失败。')
            except BaseException:
                cleanup = False
                try:
                    current_root = os.stat(temporary, follow_symlinks=False)
                    current_target = os.stat(DESTINATION, follow_symlinks=False)
                    if (not stat.S_ISDIR(current_root.st_mode) or not _same_inode(current_root, temporary_identity)
                            or not stat.S_ISDIR(current_target.st_mode) or not _same_inode(current_target, staged_identity)):
                        raise RuntimeError('入口或临时目录身份发生变化')
                    publish_exclusive(DESTINATION, staged)
                except (OSError, RuntimeError) as error:
                    raise RuntimeError(f'新入口校验失败且撤回未完成；旧副本未清理，临时目录已保留：{temporary}') from error
                cleanup = True
                raise
    finally:
        if cleanup:
            try:
                _clean_install_work(temporary, cleanup_hash, temporary_identity, cleanup_payload_identity)
            except BaseException as cleanup_error:
                raise RuntimeError(f'安装临时内容未清理，已保留：{temporary}。') from cleanup_error


def unique_state(source_info, source_hash, record):
    candidates, dist_entities = scan_apps(source_info, source_hash, record)
    if len(candidates) != 1 or candidates[0]['path'] != DESTINATION or dist_entities:
        raise RuntimeError('实体入口尚未唯一：' + json.dumps([str(entry['path']) for entry in candidates], ensure_ascii=False))
    verify(DESTINATION)
    if fingerprint(DESTINATION) != source_hash or fingerprint(SOURCE) != source_hash:
        raise RuntimeError('规范安装与当前构建载荷不一致。')
    inventory = registry_inventory()
    expected = {identity[0]: ({DESTINATION} if identity == EXPECTED else set()) for identity in KNOWN}
    if inventory != expected:
        actual = {key: sorted(str(path) for path in paths) for key, paths in inventory.items()}
        raise RuntimeError('应用登记尚未唯一，未标记升级完成：' + json.dumps(actual, ensure_ascii=False))
    return {'installedProjectAppCount': 1, 'distAppCount': 0, 'registeredProjectPathCount': 1}


def install(check_only=False, migrate_from=None):
    if check_only and migrate_from is not None:
        raise RuntimeError('只读检查与来源接管不能同时执行。')
    old_root = migration_root(migrate_from) if migrate_from is not None else None
    with install_lock(check_only, old_root):
        if (ROOT / '.build').is_symlink() or SOURCE.suffix.lower() == '.app':
            raise RuntimeError('构建源必须为项目 .build 内无 .app 后缀的实体载荷。')
        source_hash = fingerprint(SOURCE)
        source_info = verify(SOURCE)
        HELPERS['check_inputs'](SOURCE)
        if fingerprint(SOURCE) != source_hash:
            raise RuntimeError('构建载荷在核查期间发生变化，请待构建结束后重试。')
        record = recover_retirement(read_receipt(), check_only)
        already_current = False
        if old_root is not None and DESTINATION.is_dir() and not DESTINATION.is_symlink():
            try:
                verify(DESTINATION)
                already_current = fingerprint(DESTINATION) == source_hash
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
                pass
        handoff = None
        if old_root is not None:
            handoff = (pending_legacy_handoff(old_root, source_hash, record)
                       if already_current else old_install_proof(old_root))
        candidates, _ = scan_apps(source_info, source_hash, record, handoff)
        inventory = registry_inventory()
        validate_registry_scope(inventory, candidates, record)
        if handoff is not None:
            handoff_path = Path(handoff['installedPath'])
            expected_registry = {identity[0]: ({handoff_path} if identity == EXPECTED else set()) for identity in KNOWN}
            retry_paths_valid = False
            if already_current and handoff_path != DESTINATION:
                allowed_paths = {handoff_path, DESTINATION}
                retry_paths_valid = (inventory[EXPECTED[0]] <= allowed_paths
                                     and all(not paths for bundle_id, paths in inventory.items()
                                             if bundle_id != EXPECTED[0]))
            if inventory != expected_registry and not retry_paths_valid:
                raise RuntimeError('旧应用登记不唯一，不能接管。')
        original = next((entry for entry in candidates if entry['path'] == DESTINATION), None)
        current = original is not None and original['sha256Tree'] == source_hash
        if check_only:
            counts = unique_state(source_info, source_hash, record)
            result = {'status': 'current', 'installedPath': str(DESTINATION), 'sourcePath': str(SOURCE),
                      'sha256Tree': source_hash, 'version': source_info['CFBundleShortVersionString'], **counts}
            print(json.dumps(result, ensure_ascii=False))
            return result
        retire = [entry for entry in candidates if entry['path'] != DESTINATION]
        if retire:
            _require_retirement_fd_support()
        if not current or retire:
            require_stopped([entry['path'] for entry in candidates])
        if not current:
            if handoff is not None:
                pending = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
                           'status': 'source-handoff-pending', 'installedPath': str(DESTINATION),
                           'sourcePath': str(SOURCE), 'sha256Tree': source_hash,
                           'bundleID': EXPECTED[0], 'executable': EXPECTED[1],
                           'sourceHandoff': {'oldRoot': handoff['oldRoot'],
                                             'oldInstalledPath': handoff['installedPath'],
                                             'oldSHA256': handoff['oldSHA256'],
                                             'newRoot': str(ROOT), 'newSHA256': source_hash}}
                save_receipt(pending)
            install_payload(source_hash, original,
                            (lambda: recheck_handoff(old_root, handoff)) if handoff is not None else None)
        verify(DESTINATION)
        if fingerprint(DESTINATION) != source_hash or fingerprint(SOURCE) != source_hash:
            raise RuntimeError('构建或安装内容已变化，旧副本未清理。')

        # This metadata is a receipt, not a binary backup. Save before deletion so
        # an interrupted registration update can retry the exact proven paths.
        historical = {item['path']: item for item in retired_records(record)}
        for entry in retire:
            historical[str(entry['path'])] = {
                'path': str(entry['path']), 'bundleID': entry['identity'][0],
                'executable': entry['identity'][1], 'sha256Tree': entry['sha256Tree'],
                'version': entry['info']['CFBundleShortVersionString'], 'proof': entry['proof']}
        managed_hashes = {entry['sha256Tree'] for entry in candidates}
        if trusted_receipt(record):
            managed_hashes.update(record.get('managedFingerprints', []))
        result = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
                  'status': 'cleanup-pending', 'installedPath': str(DESTINATION), 'sourcePath': str(SOURCE),
                  'sha256Tree': source_hash, 'bundleID': EXPECTED[0], 'executable': EXPECTED[1],
                  'displayName': source_info['CFBundleDisplayName'],
                  'version': source_info['CFBundleShortVersionString'], 'build': str(source_info['CFBundleVersion']),
                  'managedFingerprints': sorted(managed_hashes), 'retiredArtifacts': list(historical.values())}
        if handoff is not None:
            result['sourceHandoff'] = {'oldRoot': handoff['oldRoot'], 'oldSHA256': handoff['oldSHA256'],
                                       'oldInstalledPath': handoff['installedPath'],
                                       'newRoot': str(ROOT), 'newSHA256': source_hash}
        elif trusted_receipt(record) and isinstance(record.get('sourceHandoff'), dict):
            result['sourceHandoff'] = record['sourceHandoff']
        save_receipt(result)
        unregistered = set()
        for entry in retire:
            unchanged(entry)
            require_stopped([entry['path']])
            subprocess.run([LSREGISTER, '-u', str(entry['path'])], check=True)
            unregistered.add(entry['path'])
            unchanged(entry)
            retire_entry(entry, result)
            print(json.dumps({'retiredPath': str(entry['path']), 'bundleID': entry['identity'][0],
                              'sha256Tree': entry['sha256Tree'], 'proof': entry['proof']}, ensure_ascii=False))
        # A prior attempt may have deleted the package but left a stale record.
        for paths in inventory.values():
            for path in paths:
                if path != DESTINATION and path not in unregistered:
                    if str(path) not in historical or path.exists() or path.is_symlink():
                        raise RuntimeError(f'登记目标已变化或没有退役凭据，未注销：{path}')
                    subprocess.run([LSREGISTER, '-u', str(path)], check=True)
                    unregistered.add(path)
        # Always refresh the verified canonical package's metadata, including a
        # pending upgrade whose URL is already registered. --check returned above.
        # Unregistration is reserved for proven retired paths, never this one.
        subprocess.run([str(REGISTRY_TOOL), 'register', str(DESTINATION)], check=True)
        counts = unique_state(source_info, source_hash, result)
        result.update(status='installed' if not current else ('consolidated' if retire or unregistered else 'current'), **counts)
        save_receipt(result)
        print(json.dumps(result, ensure_ascii=False))
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true', help='只读复查实体入口、载荷与全部项目登记是否唯一')
    group.add_argument('--open', action='store_true', help='完成升级与旧副本清理后打开唯一阿舟入口')
    group.add_argument('--migrate-from', metavar='OLD_ROOT', help='核对旧项目记录、构建载荷及唯一入口后接管安装')
    args = parser.parse_args()
    try:
        install(args.check, args.migrate_from)
        if args.open:
            subprocess.run(['/usr/bin/open', str(DESTINATION)], check=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')

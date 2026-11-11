#!/usr/bin/env python3
"""把一份通过完整核验的构建载荷安装成唯一规范入口，并退役所有可证明归属本项目的旧副本。

整个安装器建立在三条不变量之上：

1. 位置不变量：参与复制、交换、隔离与清理的每个目录都以 (st_dev, st_ino) 锚定
   （见 Spot）。任何阶段发现锚点漂移就立即停止并保留现场，绝不猜测磁盘状态。
2. 归属不变量：替换或删除一个 .app 必须持有四类凭据之一——当前载荷指纹、本
   项目构建标记、旧项目接管证明、0.5.0 配对指纹。名称与身份本身不构成授权。
3. 日志先行不变量：破坏性步骤（隔离、交换、注销）之前先把可恢复回执落盘，
   每次中断都落在已知恢复点上，由恢复阶段续走。

安全基线（不可回退）：排他重命名发布、fd 身份核验、隔离目录内逐项证据清理、
接管逐字段证明、事务各阶段的位置与内容复检。
"""
import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import stat
import subprocess
import tempfile

# ---------------------------------------------------------------------------
# 环境合同：项目布局与来自 verify-artifacts.py 的共享原语
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / 'tools/verify-artifacts.py'))
EXPECTED = HELPERS['IDENTITY']                # (bundleID, executable)
KNOWN = tuple(HELPERS['KNOWN_IDENTITIES'])    # 历代项目身份，全部视为"我们的"
SOURCE = HELPERS['PAYLOAD']                   # .build/azhou-payload
REGISTRY_TOOL = HELPERS['REGISTRY_TOOL']
DESTINATION = Path.home() / 'Applications' / HELPERS['NAME']
DIST = ROOT / 'dist'
PROJECT_ID = 'azhou.codex-startup-animation'
OFFICIAL_ID = 'com.openai.codex'
LEGACY_SHA256 = '7a39526e155c2b1fd06d1f60dc74f3d6cf3e85a7bdf3d5e86b0e1381828fc680'
LEGACY_VERSION = '0.5.0'
LEGACY_BUILD = '2'
LSREGISTER = '/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
fingerprint = HELPERS['fingerprint']  # 经模块名引用，测试可整体替换
swap = HELPERS['swap']                # renamex_np 原子交换


def verify(path):
    """完整产品核验（来源标记、图标、壁纸、签名），再确认身份与主执行位。"""
    HELPERS['verify_product'](path)
    return HELPERS['require'](path, EXPECTED)


# ---------------------------------------------------------------------------
# 锚定位置：所有"必须是同一个目录"的判断都收敛到这一种表达
# ---------------------------------------------------------------------------


class Spot:
    """以一次 stat 快照锚定的目录位置，之后每个阶段都对照 (st_dev, st_ino) 复核。"""

    __slots__ = ('path', 'st_dev', 'st_ino')

    def __init__(self, path):
        info = os.stat(path, follow_symlinks=False)
        self.path = Path(path)
        self.st_dev = info.st_dev
        self.st_ino = info.st_ino

    def same_as(self, other):
        return (self.st_dev, self.st_ino) == (other.st_dev, other.st_ino)

    def assert_holds(self):
        """锚定路径当前仍必须是同一个实体目录。"""
        info = os.stat(self.path, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or not self.same_as(info):
            raise RuntimeError(f'锚定路径上的内容已变化：{self.path}')

    def assert_moved_to(self, path):
        """锚定的内容此刻必须以实体目录形态出现在 path。"""
        info = os.stat(path, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or not self.same_as(info):
            raise RuntimeError(f'锚定内容并未出现在预期位置：{path}')


def _same_origin(left, right):
    """两个 stat/Spot 是否指向同一 (设备, inode)；这是本文件唯一的身份判据。"""
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _close_quietly(handle):
    if handle is not None:
        try:
            os.close(handle)
        except OSError:
            pass


def _open_pinned_level(parent_fd, name, directory=False):
    """以不跟随链接的方式打开锚定层级；目录带 O_DIRECTORY，文件带 O_NONBLOCK。

    文件侧的 O_NONBLOCK 是防 FIFO 阻塞的关键：打开 FIFO 绝不能挂起安装器。
    """
    open_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    if directory:
        return os.open(name, open_flags | os.O_DIRECTORY, dir_fd=parent_fd)
    return os.open(name, open_flags | os.O_NONBLOCK, dir_fd=parent_fd)


def publish_exclusive(source, destination):
    """排他发布：目标已被任何操作创建时绝不覆盖（renamex_np + RENAME_EXCL）。"""
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    operation = libc.renamex_np
    operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(os.fsencode(source), os.fsencode(destination), 0x00000004) != 0:
        failure = ctypes.get_errno()
        if failure == errno.EEXIST:
            raise RuntimeError('规范入口被其他操作创建，拒绝覆盖。')
        raise OSError(failure, os.strerror(failure), str(destination))


# ---------------------------------------------------------------------------
# 安装回执：唯一的持久状态，先写可恢复点再做破坏性动作
# ---------------------------------------------------------------------------


def receipt_path():
    """回执文件位置；.local 目录与记录文件本身都不允许是符号链接。"""
    journal_dir = ROOT / '.local'
    journal_file = journal_dir / 'installation.json'
    if journal_dir.is_symlink() or journal_file.is_symlink():
        raise RuntimeError('检测到符号链接读取或写入安装记录，已拒绝。')
    return journal_file


def read_receipt():
    journal_file = receipt_path()
    if not journal_file.exists():
        return {}
    stored = json.loads(journal_file.read_text())
    if not isinstance(stored, dict):
        raise RuntimeError('安装记录格式未知，应用保持原样。')
    return stored


def _write_journal_staging(journal_dir, record):
    """把回执写进暂存文件并 fsync，返回 (暂存名, 内容身份凭据)。

    身份凭据 = [dev, inode, 权限位, 内容摘要]；发布前将按名复核，任何一项
    漂移都说明暂存位已被并发操作占用。
    """
    handle, staging_name = tempfile.mkstemp(prefix='.installation-', suffix='.json',
                                            dir=journal_dir)
    with os.fdopen(handle, 'w') as stream:
        payload = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
        flushed = os.fstat(stream.fileno())
        ownership = [flushed.st_dev, flushed.st_ino, flushed.st_mode & 0o777,
                     hashlib.sha256(payload.encode(stream.encoding)).hexdigest()]
    return staging_name, ownership


def save_receipt(record):
    """回执落盘：暂存写入并 fsync → 按 fd 身份复核 → 原子替换正式记录。

    复核或替换失败时只回收"仍归本次写入所有且内容未变"的暂存文件；
    其余任何情形都保留现场待人工核对。
    """
    journal_file = receipt_path()
    journal_file.parent.mkdir(parents=True, exist_ok=True)
    staging_name, ownership = _write_journal_staging(journal_file.parent, record)
    in_place = False

    def staging_is_ours():
        try:
            HELPERS['require_file'](staging_name, ownership)
            return True
        except (OSError, RuntimeError):
            return False

    try:
        if not staging_is_ours():
            raise RuntimeError(f'安装回执暂存内容有变，保留待核对：{staging_name}')
        os.replace(staging_name, journal_file)
        in_place = True
    finally:
        if not in_place and staging_is_ours():
            Path(staging_name).unlink()


def journal_owned(record):
    """回执是否由当前项目写入——决定它在本次安装里被授权的范围。"""
    return record.get('projectID') == PROJECT_ID and record.get('projectRoot') == str(ROOT)


def _retirement_claim_is_scoped(claim):
    """一条退役凭据是否落在可再次引用的范围内。

    范围 = 应用目录或 dist 内的绝对路径（规范入口本身除外）+ 已知身份 +
    64 位十六进制指纹；各键名属于回执 schema，不可增删。
    """
    claimed_path = Path(claim.get('path', ''))
    claimed_identity = (claim.get('bundleID'), claim.get('executable'))
    if not claimed_path.is_absolute() or claimed_path.parent not in (DESTINATION.parent, DIST):
        return False
    if claimed_path == DESTINATION or claimed_identity not in KNOWN:
        return False
    return re.fullmatch(r'[0-9a-f]{64}', str(claim.get('sha256Tree', ''))) is not None


def proven_retirements(record):
    """回执中可复用的退役凭据：只信任当前项目写入的受控记录。"""
    if not journal_owned(record):
        return []
    return [claim for claim in record.get('retiredArtifacts', [])
            if _retirement_claim_is_scoped(claim)]


# ---------------------------------------------------------------------------
# 互斥：全局应用目录、本项目、（接管时）旧项目的三级文件锁
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def file_lock(path):
    """以非阻塞排他 flock 保护一段安装临界区；锁所在目录被调包则拒绝加锁。"""
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise RuntimeError(f'安装锁目录不是实体目录，拒绝加锁：{parent}')
    lock_fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('另一个项目安装正在进行，请稍后重试。') from error
        yield
    finally:
        os.close(lock_fd)


@contextlib.contextmanager
def install_lock(check_only, old_root=None):
    """安装临界区：应用目录全局锁 + 本项目锁，接管时再补旧项目锁。

    加锁次序固定为先全局后本地；只读检查不加锁、不创建任何目录。
    """
    if check_only:
        yield
        return
    journal_dir = receipt_path().parent
    journal_dir.mkdir(parents=True, exist_ok=True)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        stack.enter_context(file_lock(DESTINATION.parent / '.azhou-startup-install.lock'))
        stack.enter_context(file_lock(journal_dir / 'install.lock'))
        if old_root is not None:
            previous_journal = old_root / '.local'
            if previous_journal.is_symlink() or not previous_journal.is_dir():
                raise RuntimeError('旧安装记录目录不是实体目录，无法接管加锁。')
            stack.enter_context(file_lock(previous_journal / 'install.lock'))
        yield


def migration_root(value):
    """接管来源必须是不同于当前项目、解析到自身的绝对实体目录。"""
    previous_root = Path(value)
    if (not previous_root.is_absolute() or previous_root.is_symlink()
            or not previous_root.is_dir()
            or previous_root != previous_root.resolve(strict=True) or previous_root == ROOT):
        raise RuntimeError('旧项目路径必须是不同于当前项目的实体绝对路径。')
    return previous_root


def managed_install_path(value):
    """受管安装路径只允许应用目录下的直接 .app 条目；归属仍需完整凭据。"""
    if not isinstance(value, str):
        return None
    parsed = Path(value)
    if (not parsed.is_absolute() or str(parsed) != value
            or parsed.parent != DESTINATION.parent or parsed.suffix != '.app'):
        return None
    return parsed


# ---------------------------------------------------------------------------
# fd 锚定的目录树：审计（指纹 + 证据）与逐项证据清理
# ---------------------------------------------------------------------------

_CONTENT_FIELDS = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')


def _require_fd_capabilities():
    """清理依赖 dir_fd 一类系统支持；缺失时在任何破坏性动作前拒绝。"""
    required = {os.open, os.stat, os.unlink, os.rmdir, os.access}
    if (not required.issubset(os.supports_dir_fd)
            or not {os.scandir, os.listdir}.issubset(os.supports_fd)
            or not {os.stat, os.access}.issubset(os.supports_follow_symlinks)):
        raise RuntimeError('当前系统缺少目录描述符支持，无法安全清理。')
    if any(not hasattr(os, name) for name in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_CLOEXEC', 'O_NONBLOCK')):
        raise RuntimeError('当前系统缺少目录打开标志，无法安全清理。')


def _content_fields_of(metadata):
    """内容身份六元组：设备、inode、大小、mtime、ctime、模式。"""
    return tuple(getattr(metadata, field) for field in _CONTENT_FIELDS)


def _confirm_bundle_binary(macos_fd, binary_name):
    """主可执行文件必须始终是同一个可执行的普通文件。"""
    binary_fd = _open_pinned_level(macos_fd, binary_name)
    try:
        binary_stat = os.fstat(binary_fd)
        if (not stat.S_ISREG(binary_stat.st_mode)
                or not _same_origin(binary_stat,
                                    os.stat(binary_name, dir_fd=macos_fd, follow_symlinks=False))
                or not os.access(binary_name, os.X_OK, dir_fd=macos_fd, follow_symlinks=False)):
            raise RuntimeError('隔离副本中没有可执行的主程序。')
    finally:
        os.close(binary_fd)


def _audit_bundle_layout(directory_fd, expected_identity):
    """在不开 FIFO、不跟随链接的前提下确认目录树仍是预期的应用包结构。"""
    actual_identity, info = HELPERS['identity_at_fd'](directory_fd)
    if actual_identity != expected_identity:
        raise RuntimeError('隔离副本身份与预期不符。')
    contents_fd = _open_pinned_level(directory_fd, 'Contents', directory=True)
    try:
        macos_fd = _open_pinned_level(contents_fd, 'MacOS', directory=True)
        try:
            _confirm_bundle_binary(macos_fd, expected_identity[1])
        finally:
            os.close(macos_fd)
        if not _same_origin(os.fstat(contents_fd),
                            os.stat('Contents', dir_fd=directory_fd, follow_symlinks=False)):
            raise RuntimeError('核验期间隔离包目录发生了变化。')
        return info
    finally:
        os.close(contents_fd)


def _read_pinned_file_digest(handle, child_name, parent_fd, entry_stat):
    """读取已打开文件的内容摘要；打开前后或路径位置的任何漂移都视为调包。

    错误文案是既有回归的断言锚点，措辞不可改动。
    """
    opened = os.fstat(handle)
    if not stat.S_ISREG(opened.st_mode) or not _same_origin(entry_stat, opened):
        raise RuntimeError('隔离文件在核验期间发生变化。')
    hasher = hashlib.sha256()
    while chunk := os.read(handle, 64 * 1024):
        hasher.update(chunk)
    settled = os.fstat(handle)
    if (any(getattr(opened, field) != getattr(settled, field) for field in _CONTENT_FIELDS)
            or not _same_origin(settled,
                                os.stat(child_name, dir_fd=parent_fd, follow_symlinks=False))):
        raise RuntimeError('隔离文件在核验期间发生变化。')
    return hasher.digest(), settled


def _fingerprint_retirement_directory(directory_fd, with_evidence=False):
    """基于目录描述符计算与共享原语 fingerprint() 逐字节一致的树摘要。

    排序基准显式复刻 fingerprint()：它按 sorted(Path) 的顺序拼接摘要，而 Path
    的序是组件序。这里以 PurePosixPath(*place) 作排序键——同一比较实现、共享
    根前缀下相对序与绝对序等价，因此在所有支持的 Python 版本上都与
    fingerprint() 同序。禁止改用 '/'.join(...) 字符串序：当目录名恰是同级文
    件名的前缀且下一字符小于 '/' 时（如 web/ 与 web.config 并存），两种序会
    分歧，内容一致的树将被误判为已变化，升级与退役随之确定性失败。

    with_evidence=True 时同时返回逐项证据账本，供定向清理逐项复核；读取期间
    的任何替换、改写、跨设备条目或非常规文件都会立即中止。
    """
    file_records = []   # (相对组件, 权限位, 内容摘要)
    ledger = {}         # 相对组件 -> ('directory'|'file', 身份字段...)
    origin_device = os.fstat(directory_fd).st_dev

    def sweep(parent_fd, where):
        with os.scandir(parent_fd) as entries:
            children = sorted(entry.name for entry in entries)
        for child_name in children:
            entry_stat = os.stat(child_name, dir_fd=parent_fd, follow_symlinks=False)
            if entry_stat.st_dev != origin_device:
                raise RuntimeError('隔离副本跨越文件系统边界，中止核验。')
            place = (*where, child_name)
            if stat.S_ISDIR(entry_stat.st_mode):
                handle = _open_pinned_level(parent_fd, child_name, directory=True)
                try:
                    if not _same_origin(entry_stat, os.fstat(handle)):
                        raise RuntimeError('核验期间隔离目录发生了变化。')
                    ledger[place] = ('directory', entry_stat.st_dev, entry_stat.st_ino,
                                     entry_stat.st_mode)
                    sweep(handle, place)
                    if not _same_origin(os.fstat(handle),
                                        os.stat(child_name, dir_fd=parent_fd,
                                                follow_symlinks=False)):
                        raise RuntimeError('核验期间隔离目录发生了变化。')
                finally:
                    os.close(handle)
            elif stat.S_ISREG(entry_stat.st_mode):
                handle = _open_pinned_level(parent_fd, child_name)
                try:
                    content_digest, settled = _read_pinned_file_digest(handle, child_name,
                                                                       parent_fd, entry_stat)
                    ledger[place] = ('file', *_content_fields_of(settled))
                    file_records.append((place, settled.st_mode & 0o777, content_digest))
                finally:
                    os.close(handle)
            else:
                raise RuntimeError('隔离副本中存在非普通文件，中止核验。')

    sweep(directory_fd, ())
    tree = hashlib.sha256()
    for place, mode_bits, content_digest in sorted(file_records,
                                                   key=lambda item: PurePosixPath(*item[0])):
        tree.update('/'.join(place).encode())
        tree.update(b'\0')
        tree.update(str(mode_bits).encode())
        tree.update(b'\0')
        tree.update(content_digest)
    return (tree.hexdigest(), ledger) if with_evidence else tree.hexdigest()


def _remove_retirement_contents(directory_fd, ledger, parts=(), guard=None):
    """对照证据账本逐项删除目录树：每次删除前复核该项与所在位置未被调包。"""
    if guard is not None:
        guard()
    with os.scandir(directory_fd) as entries:
        children = sorted(entry.name for entry in entries)
    expected_children = {place[-1] for place in ledger
                         if len(place) == len(parts) + 1 and place[:-1] == parts}
    if set(children) != expected_children:
        raise RuntimeError('清理期间隔离目录内容发生了变化。')
    for child_name in children:
        if guard is not None:
            guard()
        entry_stat = os.stat(child_name, dir_fd=directory_fd, follow_symlinks=False)
        claim = ledger[(*parts, child_name)]
        if stat.S_ISDIR(entry_stat.st_mode):
            _purge_verified_directory(directory_fd, child_name, entry_stat, claim, ledger,
                                      parts, guard)
        elif stat.S_ISREG(entry_stat.st_mode):
            _purge_verified_file(directory_fd, child_name, entry_stat, claim, guard)
        else:
            raise RuntimeError('隔离副本中存在非普通文件，中止清理。')


def _purge_verified_directory(directory_fd, child_name, entry_stat, claim, ledger, parts, guard):
    """删除一个子目录：先核对证据，递归清空，再确认位置未变后才 rmdir。"""
    if claim != ('directory', entry_stat.st_dev, entry_stat.st_ino, entry_stat.st_mode):
        raise RuntimeError('清理期间隔离目录发生了变化。')
    handle = _open_pinned_level(directory_fd, child_name, directory=True)
    try:
        if not _same_origin(entry_stat, os.fstat(handle)):
            raise RuntimeError('清理期间隔离目录发生了变化。')
        _remove_retirement_contents(handle, ledger, (*parts, child_name), guard)
        if not _same_origin(os.fstat(handle),
                            os.stat(child_name, dir_fd=directory_fd, follow_symlinks=False)):
            raise RuntimeError('清理期间隔离目录发生了变化。')
        if guard is not None:
            guard()
        os.rmdir(child_name, dir_fd=directory_fd)
    finally:
        os.close(handle)


def _purge_verified_file(directory_fd, child_name, entry_stat, claim, guard):
    """删除一个文件：打开前后各核对一次证据，全部一致才 unlink。"""
    if claim != ('file', *_content_fields_of(entry_stat)):
        raise RuntimeError('清理期间隔离文件发生了变化。')
    handle = _open_pinned_level(directory_fd, child_name)
    try:
        from_fd = os.fstat(handle)
        by_name = os.stat(child_name, dir_fd=directory_fd, follow_symlinks=False)
        if (claim != ('file', *_content_fields_of(from_fd))
                or claim != ('file', *_content_fields_of(by_name))):
            raise RuntimeError('清理期间隔离文件发生了变化。')
        if guard is not None:
            guard()
        os.unlink(child_name, dir_fd=directory_fd)
    finally:
        os.close(handle)


def _reverify_displaced(entry, path):
    """交换后被换到暂存位的候选：身份、版本、指纹与 fd 位置必须原样。"""
    handle = None
    try:
        handle = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = _audit_bundle_layout(handle, entry['identity'])
        if (version_key(info) != entry['versionKey']
                or _fingerprint_retirement_directory(handle) != entry['sha256Tree']
                or not _same_origin(os.fstat(handle), os.stat(path, follow_symlinks=False))):
            raise RuntimeError('隔离副本与清点时的候选不一致。')
    except Exception as error:
        raise RuntimeError(f'候选在核查后发生变化，既不替换也不删除：{path}') from error
    finally:
        if handle is not None:
            os.close(handle)


def _clean_install_work(directory, expected_tree, expected_root, expected_payload):
    """清理安装暂存目录：锚定目录身份、核对载荷指纹，最后按证据清空。

    只有 (expected_tree, expected_payload) 双双匹配的内容才允许删除；
    未核验或被调包的内容一律保留并报错。
    """
    _require_fd_capabilities()
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    payload_fd = None
    try:
        if (not _same_origin(os.fstat(directory_fd), expected_root)
                or not _same_origin(os.fstat(directory_fd),
                                    os.stat(directory, follow_symlinks=False))):
            raise RuntimeError('安装暂存目录发生了变化。')
        children = set(os.listdir(directory_fd))
        if children - {'payload'}:
            raise RuntimeError('安装暂存目录中有无法识别的内容。')
        if 'payload' in children:
            payload_fd = _open_pinned_level(directory_fd, 'payload', directory=True)
            if os.fstat(payload_fd).st_dev != os.fstat(directory_fd).st_dev:
                raise RuntimeError('隔离副本跨越文件系统边界，中止清理。')
            if expected_payload is None or not _same_origin(os.fstat(payload_fd), expected_payload):
                raise RuntimeError('暂存载荷身份有变。')
            tree, ledger = _fingerprint_retirement_directory(payload_fd, with_evidence=True)
            if tree != expected_tree:
                raise RuntimeError('暂存副本与已核验内容不符。')

            def positions_hold():
                if (not _same_origin(os.fstat(directory_fd),
                                     os.stat(directory, follow_symlinks=False))
                        or not _same_origin(os.fstat(payload_fd),
                                            os.stat('payload', dir_fd=directory_fd,
                                                    follow_symlinks=False))):
                    raise RuntimeError('暂存位置发生了变化。')

            positions_hold()
            _remove_retirement_contents(payload_fd, ledger, guard=positions_hold)
            positions_hold()
            os.rmdir('payload', dir_fd=directory_fd)
        if (os.listdir(directory_fd)
                or not _same_origin(os.fstat(directory_fd),
                                    os.stat(directory, follow_symlinks=False))):
            raise RuntimeError('安装暂存目录发生了变化。')
        os.rmdir(directory)
    finally:
        _close_quietly(payload_fd)
        os.close(directory_fd)


# ---------------------------------------------------------------------------
# 归属凭据：旧项目接管与待完成的接管续走
# ---------------------------------------------------------------------------


def version_key(info):
    """把 (短版本, 构建号) 规范化为可比较的四段数字元组。"""

    def component(value):
        value = str(value)
        if not re.fullmatch(r'\d+(?:\.\d+){0,3}', value):
            raise RuntimeError(f'版本格式未知，应用原样保留：{value!r}')
        parts = tuple(int(part) for part in value.split('.'))
        return parts + (0,) * (4 - len(parts))

    return (component(info.get('CFBundleShortVersionString', '')),
            component(info.get('CFBundleVersion', '')))


def old_install_proof(old_root):
    """逐字段重放旧项目留下的安装证明：回执、构建载荷与入口三方一致才可接管。"""
    record_path = old_root / '.local/installation.json'
    old_payload_root = old_root / '.build/azhou-payload'
    missing = (record_path.is_symlink() or not record_path.is_file()
               or old_payload_root.parent.is_symlink() or old_payload_root.is_symlink()
               or not old_payload_root.is_dir())
    if missing:
        raise RuntimeError('旧安装记录或构建载荷缺失，拒绝接管。')
    record = json.loads(record_path.read_text())
    if not isinstance(record, dict):
        raise RuntimeError('旧安装记录格式无效，拒绝接管。')
    installed_path = record.get('installedPath')
    if managed_install_path(installed_path) is None:
        raise RuntimeError('旧安装记录没有证明当前入口归属，拒绝接管。')
    required = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(old_root),
                'installedPath': installed_path, 'sourcePath': str(old_payload_root),
                'bundleID': EXPECTED[0], 'executable': EXPECTED[1]}
    trusted_states = ('installed', 'current', 'consolidated')
    if (any(record.get(key) != value for key, value in required.items())
            or record.get('status') not in trusted_states
            or re.fullmatch(r'[0-9a-f]{64}', str(record.get('sha256Tree', ''))) is None):
        raise RuntimeError('旧安装记录没有证明当前入口归属，拒绝接管。')
    claimed_hash = record['sha256Tree']
    for witness in (old_payload_root, Path(installed_path)):
        _replay_old_witness(witness, old_root, record, claimed_hash)
    _reject_leftover_dist_apps(old_root)
    return {'oldRoot': str(old_root), 'installedPath': installed_path, 'oldSHA256': claimed_hash}


def _replay_old_witness(path, old_root, record, claimed_hash):
    """单个旧包（构建载荷或已装入口）与回执逐字段互证，再验视觉资源与签名。"""
    info = HELPERS['require'](path, EXPECTED)
    marker = HELPERS['read_marker'](path, required=True)
    consistent = (marker['projectID'] == PROJECT_ID
                  and marker['projectRoot'] == str(old_root)
                  and marker['bundleID'] == EXPECTED[0]
                  and marker['executable'] == EXPECTED[1]
                  and info.get('CFBundleShortVersionString') == record.get('version')
                  and str(info.get('CFBundleVersion')) == str(record.get('build'))
                  and fingerprint(path) == claimed_hash)
    if not consistent:
        raise RuntimeError(f'旧包与安装记录不一致，接管中止：{path}')
    HELPERS['verify_icon'](path, info)
    HELPERS['verify_wallpaper'](path, info, marker)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)], check=True)


def _reject_leftover_dist_apps(old_root):
    """旧项目 dist 若仍留有 .app，说明其输出尚未清点，不允许接管。"""
    old_dist = old_root / 'dist'
    if old_dist.is_symlink() or (old_dist.exists() and not old_dist.is_dir()):
        raise RuntimeError('旧输出目录不是实体目录，拒绝接管。')
    if old_dist.exists() and any(item.suffix.lower() == '.app' for item in old_dist.iterdir()):
        raise RuntimeError('旧输出目录仍有应用，拒绝接管。')


def recheck_handoff(old_root, expected):
    """交换前最后一道接管复核：旧安装归属不得在证明之后发生变化。"""
    if old_install_proof(old_root) != expected:
        raise RuntimeError('旧安装归属在交换前发生变化，中止替换。')


def _resumable_handoff_plan(record, old_root, source_hash):
    """从回执提取与本次安装匹配的待续走接管计划；不匹配返回 None。"""
    if not journal_owned(record):
        return None
    if record.get('status') not in ('source-handoff-pending', 'cleanup-pending'):
        return None
    plan = record.get('sourceHandoff')
    if (not isinstance(plan, dict) or plan.get('oldRoot') != str(old_root)
            or plan.get('newRoot') != str(ROOT) or plan.get('newSHA256') != source_hash
            or not re.fullmatch(r'[0-9a-f]{64}', str(plan.get('oldSHA256', '')))):
        return None
    return plan


def _handoff_retirement_is_registered(record, path_text, tree):
    """旧入口是否已作为 verified-source-handoff 记入退役凭据（cleanup 阶段必需）。"""
    return any(claim.get('path') == path_text
               and claim.get('bundleID') == EXPECTED[0]
               and claim.get('executable') == EXPECTED[1]
               and claim.get('sha256Tree') == tree
               and claim.get('proof') == 'verified-source-handoff'
               for claim in proven_retirements(record))


def pending_legacy_handoff(old_root, source_hash, record):
    """识别中断在"发布后、清理前"的来源接管，返回仍待完成的旧入口证明。

    续走前提按序确认：回执属于本项目且处于可续走状态 → sourceHandoff 与本次
    安装完全匹配 → 旧入口路径受管且不是规范入口 → cleanup 阶段已有退役凭据
    且旧入口仍在磁盘上 → 旧项目的安装证明仍与计划一致。
    """
    plan = _resumable_handoff_plan(record, old_root, source_hash)
    if plan is None:
        return None
    resumable_path = managed_install_path(plan.get(
        'oldInstalledPath', str(DESTINATION.with_name(HELPERS['LEGACY_NAME']))))
    if resumable_path is None or resumable_path == DESTINATION:
        return None
    if record.get('status') == 'cleanup-pending' and not _handoff_retirement_is_registered(
            record, str(resumable_path), plan['oldSHA256']):
        return None
    if not (resumable_path.exists() or resumable_path.is_symlink()):
        return None
    verified = old_install_proof(old_root)
    if (verified['installedPath'] != str(resumable_path)
            or verified['oldSHA256'] != plan['oldSHA256']):
        raise RuntimeError('旧安装与待完成的来源接管记录不一致，清理中止。')
    return verified


# ---------------------------------------------------------------------------
# 清点：两个受控位置下的实体入口与系统登记
# ---------------------------------------------------------------------------


def _legacy_era_locations():
    """0.5.0 时代的四个受管位置（运行时求值，DESTINATION 可被测试整体替换）。"""
    return (DESTINATION, DESTINATION.with_name(HELPERS['LEGACY_NAME']),
            DIST / HELPERS['NAME'], DIST / HELPERS['LEGACY_NAME'])


def _legacy_era_is_provable(findings, record):
    """0.5.0 双件套的三条授权途径：旧版回执、本项目历史指纹、成对实体。"""
    install_side, legacy_side, current_dist_side, legacy_dist_side = _legacy_era_locations()

    def witnessed_by_v050_receipt():
        return (record.get('sha256Tree') == LEGACY_SHA256
                and record.get('installedPath') in (str(install_side), str(legacy_side))
                and record.get('sourcePath') in (str(current_dist_side), str(legacy_dist_side))
                and record.get('bundleID') == EXPECTED[0]
                and record.get('version') == LEGACY_VERSION)

    def witnessed_by_managed_history():
        return journal_owned(record) and LEGACY_SHA256 in record.get('managedFingerprints', [])

    def witnessed_by_paired_copies():
        era_copies = [entry for entry in findings.values()
                      if entry['sha256Tree'] == LEGACY_SHA256]
        install_present = any(entry['path'] in (install_side, legacy_side)
                              for entry in era_copies)
        dist_present = any(entry['path'] in (current_dist_side, legacy_dist_side)
                           for entry in era_copies)
        return install_present and dist_present

    return (witnessed_by_v050_receipt() or witnessed_by_managed_history()
            or witnessed_by_paired_copies())


def scan_apps(source_info, source_hash, record, handoff=None):
    """只承认应用目录与 dist 下直接的实体 .app，并为每个候选找到一项归属凭据。"""
    findings, dist_entries, conflicts = {}, [], []
    known_bundle_ids = {identity[0] for identity in KNOWN}
    for directory in (DESTINATION.parent, DIST):
        if directory.is_symlink():
            raise RuntimeError(f'遇到符号链接目录，拒绝扫描：{directory}')
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise RuntimeError(f'应用目录不是目录，拒绝清点：{directory}')
        for candidate in sorted(directory.iterdir()):
            if candidate.suffix.lower() != '.app':
                continue
            guards_canonical = candidate == DESTINATION or directory == DIST
            if candidate.is_symlink():
                if guards_canonical:
                    conflicts.append(f'入口是符号链接，已原样保留：{candidate}')
                continue
            if not candidate.is_dir():
                if candidate == DESTINATION:
                    conflicts.append(f'规范入口不是实体应用，拒绝处理：{candidate}')
                continue
            if directory == DIST:
                dist_entries.append(candidate)
            try:
                actual, info = HELPERS['identity'](candidate)
            except (OSError, ValueError, RuntimeError) as error:
                if guards_canonical:
                    conflicts.append(f'无法核实的应用已保留，等待核对：{candidate}；{error}')
                continue
            if actual[0] == OFFICIAL_ID or actual[0] not in known_bundle_ids:
                if guards_canonical:
                    conflicts.append(f'非项目应用已保留；项目入口与输出目录不容占用：'
                                     f'{candidate}；{actual!r}')
                continue
            try:
                if actual not in KNOWN:
                    raise RuntimeError(f'项目 bundleID 与主可执行文件不匹配：{actual!r}')
                HELPERS['require'](candidate, actual)
                if not (candidate / 'Contents/Resources/web/index.html').is_file():
                    raise RuntimeError('缺少项目自带的 web 资源')
                findings[candidate] = {'path': candidate, 'identity': actual, 'info': info,
                                       'sha256Tree': fingerprint(candidate),
                                       'versionKey': version_key(info)}
            except (OSError, ValueError, RuntimeError) as error:
                conflicts.append(f'无法核实的项目候选已保留，等待核对：{candidate}；{error}')
    authorized = _authorize_candidates(findings, source_info, source_hash, record, handoff,
                                       conflicts)
    if conflicts:
        raise RuntimeError('应用归属或版本存在冲突，停止清理：\n' + '\n'.join(conflicts))
    return authorized, dist_entries


def _authorize_candidates(findings, source_info, source_hash, record, handoff, conflicts):
    """给每个候选配一项凭据；无凭据者进入冲突清单并原样保留。"""
    era_proven = _legacy_era_is_provable(findings, record)
    confirmed = []
    for entry in findings.values():
        candidate_path = entry['path']
        try:
            if entry['versionKey'] > version_key(source_info):
                raise RuntimeError('候选的版本高于本次构建，拒绝降级或删除')
            marker = HELPERS['read_marker'](candidate_path, required=False)
            if entry['sha256Tree'] == source_hash:
                proof = 'current-payload-fingerprint'
            elif marker:
                from_old_root = (handoff is not None
                                 and str(candidate_path) == handoff['installedPath']
                                 and entry['sha256Tree'] == handoff['oldSHA256']
                                 and marker.get('projectID') == PROJECT_ID
                                 and marker.get('projectRoot') == handoff['oldRoot'])
                if not from_old_root and (marker.get('projectID') != PROJECT_ID
                                          or marker.get('projectRoot') != str(ROOT)):
                    raise RuntimeError('来源标记属于其他项目或路径，拒绝认领')
                proof = 'verified-source-handoff' if from_old_root else 'project-build-marker'
            elif (era_proven and candidate_path in _legacy_era_locations()
                  and entry['sha256Tree'] == LEGACY_SHA256 and entry['identity'] == EXPECTED
                  and entry['info'].get('CFBundleShortVersionString') == LEGACY_VERSION
                  and str(entry['info'].get('CFBundleVersion')) == LEGACY_BUILD):
                proof = 'verified-0.5.0-fingerprint'
            else:
                raise RuntimeError('仅凭名称或身份相同不足以证明安装来源')
            subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(candidate_path)],
                           check=True)
            entry['proof'] = proof
            confirmed.append(entry)
        except (OSError, ValueError, RuntimeError) as error:
            conflicts.append(f'候选已保留，等待核对：{candidate_path}；{error}')
    return confirmed


def _decode_registry_document(raw):
    """解析登记清单文档；重复 JSON 键直接判为未知格式。"""

    def first_occurrence(pairs):
        unique = {}
        for key, value in pairs:
            if key in unique:
                raise ValueError('duplicate JSON key')
            unique[key] = value
        return unique

    try:
        return json.loads(raw, object_pairs_hook=first_occurrence)
    except (TypeError, ValueError) as error:
        raise RuntimeError('登记检查器返回未知格式。') from error


def _collect_group_urls(group):
    """把一组的 urls 收敛为绝对路径集合；任何畸形条目都判为未知格式。"""
    if not isinstance(group.get('urls'), list):
        raise RuntimeError('登记检查器返回未知格式。')
    urls = set()
    for item in group['urls']:
        if (not isinstance(item, dict) or not isinstance(item.get('path'), str)
                or '\0' in item['path']):
            raise RuntimeError('登记检查器返回未知格式。')
        if not Path(item['path']).is_absolute():
            raise RuntimeError('登记检查返回了非绝对路径。')
        urls.add(Path(item['path']))
    return urls


def registry_inventory():
    """读取并严格校验系统登记：每个已知 bundleID 恰好一组，路径为绝对路径集合。"""
    raw = subprocess.check_output([str(REGISTRY_TOOL), 'inventory'], text=True)
    document = _decode_registry_document(raw)
    if (not isinstance(document, dict) or type(document.get('schema')) is not int
            or document['schema'] != 1 or not isinstance(document.get('applications'), list)):
        raise RuntimeError('登记检查器返回未知格式。')
    known_bundle_ids = {identity[0] for identity in KNOWN}
    inventory = {}
    for group in document['applications']:
        if not isinstance(group, dict) or not isinstance(group.get('bundleID'), str):
            raise RuntimeError('登记检查器返回未知格式。')
        bundle_id = group['bundleID']
        if bundle_id not in known_bundle_ids or bundle_id in inventory:
            raise RuntimeError('登记检查没有覆盖全部已知项目 ID，或存在重复分组。')
        inventory[bundle_id] = _collect_group_urls(group)
    if set(inventory) != known_bundle_ids:
        raise RuntimeError('登记检查没有覆盖全部已知项目 ID。')
    return inventory


def ensure_registry_within_proven_scope(inventory, candidates, record):
    """系统登记必须落在：规范入口、本轮已证实候选、或持有退役凭据且已消失的路径。"""
    present = {entry['path'] for entry in candidates}
    retired = {Path(claim['path']) for claim in proven_retirements(record)}
    violations = []
    for bundle_id, paths in inventory.items():
        for path in paths:
            if path == DESTINATION or path in present:
                continue
            if path in retired and not path.exists() and not path.is_symlink():
                continue
            violations.append(f'{bundle_id}: {path}')
    if violations:
        raise RuntimeError('存在未获来源确认或超出清理范围的项目登记，全部保留：\n'
                           + '\n'.join(violations))


def require_stopped(paths):
    """候选包的主程序还在运行时，任何替换或删除都拒绝执行。"""
    exec_prefixes = tuple(f'{path}/Contents/MacOS/' for path in paths)
    if not exec_prefixes:
        return
    listing = subprocess.check_output(['/bin/ps', '-axo', 'pid=,comm='], text=True)
    for row in listing.splitlines():
        command = row.strip().split(None, 1)
        if len(command) == 2 and command[1].startswith(exec_prefixes):
            raise RuntimeError(f'检测到项目启动动画仍在运行，停止替换与移除：{command[1]}')


def unchanged(entry):
    """最后一道复查：候选的身份、版本与指纹必须与清点时完全一致。"""
    info = HELPERS['require'](entry['path'], entry['identity'])
    if version_key(info) != entry['versionKey'] or fingerprint(entry['path']) != entry['sha256Tree']:
        raise RuntimeError(f'候选在核查后发生变化，既不替换也不删除：{entry["path"]}')


# ---------------------------------------------------------------------------
# 发布事务：暂存复制 → 位置锚定 → 提交（交换或排他发布）→ 凭据回收
# ---------------------------------------------------------------------------


class _Disposal:
    """安装事务的回收凭据：只有 (指纹, 锚点) 双双匹配的内容才允许清理暂存目录。"""

    __slots__ = ('digest', 'payload_spot')

    def __init__(self, digest, payload_spot):
        self.digest = digest
        self.payload_spot = payload_spot

    def adopt(self, digest, payload_spot):
        self.digest = digest
        self.payload_spot = payload_spot

    def release(self):
        """放弃回收权：临时目录必须原样保留待人工核对。"""
        self.digest = None
        self.payload_spot = None


def _copy_into_stage(stage):
    """ditto 复制载荷并立刻锚定暂存身份；此后的核验失败也持有回收凭据。"""
    subprocess.run(['/usr/bin/ditto', str(SOURCE), str(stage)], check=True)
    return Spot(stage)


def _confirm_staged_content(stage, source_hash):
    """暂存副本与构建源双侧复核：复制期间任何一侧变化都终止安装。"""
    verify(stage)
    if fingerprint(stage) != source_hash or fingerprint(SOURCE) != source_hash:
        raise RuntimeError('构建载荷在复制期间发生变化，规范入口原样不动。')


def install_payload(source_hash, original, before_swap=None):
    """把已核验载荷送入规范入口；original 指向既有入口记录，None 表示首次发布。

    替换走"原子交换 + 失败回滚"，首次发布走"排他重命名 + 失败撤回"。
    disposal 未持凭据时，临时目录一律保留。
    """
    if original is not None:
        _require_fd_capabilities()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix='.azhou-install-', dir=DESTINATION.parent))
    workdir_spot = Spot(workdir)
    stage = workdir / 'payload'  # 永不制造第二个可被系统发现的 .app
    disposal = _Disposal(source_hash, None)
    try:
        staged_spot = _copy_into_stage(stage)
        disposal.payload_spot = staged_spot
        _confirm_staged_content(stage, source_hash)
        require_stopped([DESTINATION])
        if original is not None:
            _replace_canonical(workdir_spot, stage, staged_spot, source_hash,
                               original, before_swap, disposal)
        else:
            _publish_canonical(workdir_spot, stage, staged_spot, source_hash,
                               before_swap, disposal)
    finally:
        if disposal.digest is not None:
            try:
                _clean_install_work(workdir, disposal.digest, workdir_spot, disposal.payload_spot)
            except BaseException as cleanup_error:
                raise RuntimeError(f'安装临时内容未清理，保留待查：{workdir}。') from cleanup_error


def _replace_canonical(workdir_spot, stage, staged_spot, source_hash,
                       original, before_swap, disposal):
    """替换既有规范入口：三处锚定下的原子交换，交换后逐项核验，失败即回滚。"""
    incumbent_spot = Spot(DESTINATION)
    unchanged(original)

    def layout(swapped):
        workdir_spot.assert_holds()
        (incumbent_spot if swapped else staged_spot).assert_moved_to(stage)
        (staged_spot if swapped else incumbent_spot).assert_moved_to(DESTINATION)

    disposal.release()
    if before_swap is not None:
        try:
            before_swap()
        except Exception as error:
            raise RuntimeError(f'预发布核验失败，临时目录保留待查：{workdir_spot.path}；{error}') from error
    try:
        layout(False)
        unchanged(original)
        layout(False)
    except (OSError, ValueError, RuntimeError) as error:
        raise RuntimeError(f'候选在核查后发生变化，入口与临时目录均已保留：{workdir_spot.path}') from error
    try:
        swap(stage, DESTINATION)
        disposal.adopt(original['sha256Tree'], incumbent_spot)  # 原件退到暂存位待核验后回收
    except BaseException as swap_error:
        try:
            layout(False)
            unchanged(original)
            if fingerprint(stage) == source_hash:
                disposal.adopt(source_hash, staged_spot)
        except (OSError, ValueError, RuntimeError):
            pass
        if disposal.digest is None:
            raise RuntimeError(f'安装交换结果未确认，入口与临时目录均已保留：'
                               f'{workdir_spot.path}') from swap_error
        raise
    try:
        layout(True)
        _reverify_displaced(original, stage)
        verify(DESTINATION)
        if fingerprint(DESTINATION) != source_hash:
            raise RuntimeError('发布后的内容校验未通过。')
        layout(True)
    except BaseException as verification_error:
        try:
            layout(True)
            _reverify_displaced(original, stage)
            if fingerprint(DESTINATION) != source_hash:
                raise RuntimeError('新入口内容有变')
            layout(True)
            swap(stage, DESTINATION)
            layout(False)
            disposal.adopt(source_hash, staged_spot)
        except BaseException as rollback_error:
            disposal.release()
            raise RuntimeError(f'安装校验失败且回滚未完成；请将入口与临时目录一并保留待核对：'
                               f'{workdir_spot.path}') from rollback_error
        raise verification_error


def _publish_canonical(workdir_spot, stage, staged_spot, source_hash, before_swap, disposal):
    """首次发布：排他重命名进入规范入口，发布后核验失败则原路撤回。"""
    if DESTINATION.exists() or DESTINATION.is_symlink():
        raise RuntimeError('规范入口被其他操作创建，拒绝覆盖。')
    disposal.release()
    if before_swap is not None:
        try:
            before_swap()
        except Exception as error:
            raise RuntimeError(f'预发布核验失败，临时目录保留待查：{workdir_spot.path}；{error}') from error
    try:
        workdir_spot.assert_holds()
        staged_spot.assert_holds()
    except (OSError, RuntimeError) as error:
        raise RuntimeError(f'安装暂存发生变化，保留待查：{workdir_spot.path}') from error
    disposal.adopt(source_hash, staged_spot)
    publish_exclusive(stage, DESTINATION)
    try:
        verify(DESTINATION)
        if fingerprint(DESTINATION) != source_hash:
            raise RuntimeError('发布后的内容校验未通过。')
    except BaseException:
        disposal.release()
        try:
            workdir_spot.assert_holds()
            staged_spot.assert_moved_to(DESTINATION)  # 撤回前提：新入口仍是我们的载荷
            publish_exclusive(DESTINATION, stage)
        except (OSError, RuntimeError) as error:
            raise RuntimeError(f'新入口校验失败且撤回未完成；旧副本未动，'
                               f'临时目录保留待查：{workdir_spot.path}') from error
        disposal.adopt(source_hash, staged_spot)
        raise


# ---------------------------------------------------------------------------
# 退役事务：日志先行 → 排他隔离 → fd 审计 → 证据清理；中断可恢复
# ---------------------------------------------------------------------------


def retire_proven_entry(entry, journal):
    """退役一个已证实候选：先写恢复日志，再隔离进排他目录，核验后按证据删除。"""
    _require_fd_capabilities()
    entry_path = entry['path']
    quarantine_root = Path(tempfile.mkdtemp(prefix='.azhou-retire-', dir=entry_path.parent))
    quarantine = quarantine_root / 'payload'
    journal['retirementPending'] = {'path': str(entry_path), 'stage': str(quarantine)}
    root_fd = payload_fd = None
    try:
        root_fd = os.open(quarantine_root,
                          os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        if not _same_origin(os.fstat(root_fd),
                            os.stat(quarantine_root, follow_symlinks=False)):
            raise RuntimeError(f'隔离目录发生变化，保留待查：{quarantine_root}。')
        save_receipt(journal)  # 恢复点：此后任何中断都从回执续走
        publish_exclusive(entry_path, quarantine)
        payload_fd, ledger = _audit_isolated_stage(quarantine_root, root_fd, entry)
        try:
            def positions_hold():
                if (not _same_origin(os.fstat(root_fd),
                                     os.stat(quarantine_root, follow_symlinks=False))
                        or not _same_origin(os.fstat(payload_fd),
                                            os.stat('payload', dir_fd=root_fd,
                                                    follow_symlinks=False))):
                    raise RuntimeError('清理期间隔离目录发生了变化。')

            _remove_retirement_contents(payload_fd, ledger, guard=positions_hold)
            positions_hold()
            os.rmdir('payload', dir_fd=root_fd)
        except BaseException as removal_error:
            # 清理未完成：若隔离副本完好则原路放回入口，清掉 pending 后重抛原错误。
            try:
                positions_hold()
                info = _audit_bundle_layout(payload_fd, entry['identity'])
                if (version_key(info) != entry['versionKey']
                        or _fingerprint_retirement_directory(payload_fd) != entry['sha256Tree']):
                    raise RuntimeError('隔离副本内容有变。')
                publish_exclusive(quarantine, entry_path)
            except BaseException as recovery_error:
                raise RuntimeError(f'旧入口清理未完成，临时副本保留于 {quarantine}。') from recovery_error
            journal.pop('retirementPending')
            save_receipt(journal)
            raise removal_error
        journal.pop('retirementPending')
        save_receipt(journal)
    finally:
        _close_quietly(payload_fd)
        try:
            if root_fd is not None and _same_origin(os.fstat(root_fd),
                                                    os.stat(quarantine_root,
                                                            follow_symlinks=False)):
                quarantine_root.rmdir()
        except OSError:
            pass
        finally:
            if root_fd is not None:
                os.close(root_fd)


def _audit_isolated_stage(quarantine_root, root_fd, entry):
    """对刚隔离的副本做 fd 级审计；期间被调包则保留现场，只报"无法验证"。"""
    quarantine = quarantine_root / 'payload'
    payload_fd = None
    try:
        if not _same_origin(os.fstat(root_fd),
                            os.stat(quarantine_root, follow_symlinks=False)):
            raise RuntimeError('移动期间隔离目录发生了变化。')
        payload_fd = _open_pinned_level(root_fd, 'payload', directory=True)
        if os.fstat(payload_fd).st_dev != os.fstat(root_fd).st_dev:
            raise RuntimeError('隔离副本跨越文件系统边界，已停止清理。')
        info = _audit_bundle_layout(payload_fd, entry['identity'])
        if version_key(info) != entry['versionKey']:
            raise RuntimeError('隔离副本版本有变。')
        if not _same_origin(os.fstat(payload_fd),
                            os.stat('payload', dir_fd=root_fd, follow_symlinks=False)):
            raise RuntimeError('核验期间隔离目录发生了变化。')
        tree, ledger = _fingerprint_retirement_directory(payload_fd, with_evidence=True)
        if tree != entry['sha256Tree']:
            raise RuntimeError('核验期间隔离副本内容发生了变化。')
        if (not _same_origin(os.fstat(root_fd), os.stat(quarantine_root, follow_symlinks=False))
                or not _same_origin(os.fstat(payload_fd),
                                    os.stat('payload', dir_fd=root_fd,
                                            follow_symlinks=False))):
            raise RuntimeError('核验期间隔离目录发生了变化。')
        return payload_fd, ledger
    except BaseException as error:
        # 先确认隔离位置未被调包，再决定报"位置变化"还是"无法验证"。
        try:
            root_intact = _same_origin(os.fstat(root_fd),
                                       os.stat(quarantine_root, follow_symlinks=False))
        except OSError:
            root_intact = False
        if not root_intact:
            _close_quietly(payload_fd)
            raise RuntimeError(f'隔离位置发生变化，临时目录保留待查：{quarantine_root}。') from error
        if payload_fd is not None:
            try:
                payload_intact = _same_origin(os.fstat(payload_fd),
                                              os.stat('payload', dir_fd=root_fd,
                                                      follow_symlinks=False))
            except OSError:
                payload_intact = False
            if not payload_intact:
                _close_quietly(payload_fd)
                raise RuntimeError(f'隔离位置发生变化，临时目录保留待查：{quarantine_root}。') from error
        _close_quietly(payload_fd)
        if isinstance(error, Exception):
            raise RuntimeError(f'隔离副本无法验证，保留待查：{quarantine}。') from error
        raise


def resume_pending_retirement(record, read_only=False):
    """把中断在"已隔离、未删除"状态的旧入口恢复到一致状态，再继续本次安装。"""
    pending = record.get('retirementPending')
    if pending is None:
        return record
    if read_only:
        raise RuntimeError('检测到旧入口清理尚未恢复，请先完成恢复流程。')
    if not journal_owned(record) or not isinstance(pending, dict):
        raise RuntimeError('待恢复的旧入口记录无效，未执行任何清理。')
    entry_text, stage_text = pending.get('path'), pending.get('stage')
    retired = {claim['path']: claim for claim in proven_retirements(record)}
    if (not isinstance(entry_text, str) or entry_text not in retired
            or not isinstance(stage_text, str)):
        raise RuntimeError('待恢复的旧入口记录无效，未执行任何清理。')
    entry_path, quarantine = Path(entry_text), Path(stage_text)
    quarantine_root = quarantine.parent
    if (str(entry_path) != entry_text or str(quarantine) != stage_text
            or quarantine.name != 'payload'
            or quarantine_root.parent != entry_path.parent
            or not quarantine_root.name.startswith('.azhou-retire-')
            or entry_path.parent.is_symlink() or not entry_path.parent.is_dir()
            or quarantine_root.is_symlink()):
        raise RuntimeError('旧入口路径无效，未执行任何清理。')
    credential = retired[entry_text]
    identity = (credential['bundleID'], credential['executable'])
    _require_fd_capabilities()
    if quarantine.exists() or quarantine.is_symlink():
        _restore_isolated_entry(entry_path, quarantine, quarantine_root, identity,
                                credential['sha256Tree'])
    elif entry_path.exists() or entry_path.is_symlink():
        _accept_completed_removal(entry_path, identity, credential['sha256Tree'])
    if quarantine_root.exists():
        try:
            quarantine_root.rmdir()
        except OSError as error:
            raise RuntimeError(f'旧入口临时目录未清空，保留待查：{quarantine_root}。') from error
    record = {key: value for key, value in record.items() if key != 'retirementPending'}
    save_receipt(record)
    return record


def _restore_isolated_entry(entry_path, quarantine, quarantine_root, identity, expected_tree):
    """隔离副本仍在：核验后原路排他发布回入口位置，并复核发布结果。"""
    if entry_path.exists() or entry_path.is_symlink():
        raise RuntimeError(f'旧入口恢复受阻，临时副本留在 {quarantine}。')
    payload_fd = None
    try:
        try:
            payload_fd = os.open(quarantine,
                                 os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            _audit_bundle_layout(payload_fd, identity)
            if (not _same_origin(os.fstat(payload_fd),
                                 os.stat(quarantine, follow_symlinks=False))
                    or _fingerprint_retirement_directory(payload_fd) != expected_tree):
                raise RuntimeError('隔离副本内容已变化')
        except Exception as error:
            raise RuntimeError(f'隔离副本无法验证，保留待查：{quarantine}。') from error
        publish_exclusive(quarantine, entry_path)
        try:
            if (not _same_origin(os.fstat(payload_fd),
                                 os.stat(entry_path, follow_symlinks=False))
                    or _fingerprint_retirement_directory(payload_fd) != expected_tree):
                raise RuntimeError('恢复时隔离副本有变化')
        except Exception as error:
            raise RuntimeError(f'恢复期间旧入口有变化，临时目录保留待查：'
                               f'{quarantine_root}。') from error
    finally:
        _close_quietly(payload_fd)


def _accept_completed_removal(entry_path, identity, expected_tree):
    """隔离副本已消失而入口路径仍有实体：只有完全一致者才视为已完成的清理。"""
    payload_fd = None
    try:
        payload_fd = os.open(entry_path,
                             os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        _audit_bundle_layout(payload_fd, identity)
        if (_fingerprint_retirement_directory(payload_fd) != expected_tree
                or not _same_origin(os.fstat(payload_fd),
                                    os.stat(entry_path, follow_symlinks=False))):
            raise RuntimeError('原路径内容有变')
    except Exception as error:
        raise RuntimeError(f'旧入口恢复受阻，原位置内容有变并保留：{entry_path}。') from error
    finally:
        _close_quietly(payload_fd)


# ---------------------------------------------------------------------------
# 收敛审计与总编排
# ---------------------------------------------------------------------------


def unique_state(source_info, source_hash, record):
    """只读收敛审计：实体入口、构建载荷与系统登记三者必须同时唯一。"""
    candidates, dist_entries = scan_apps(source_info, source_hash, record)
    if len(candidates) != 1 or candidates[0]['path'] != DESTINATION or dist_entries:
        raise RuntimeError('实体入口尚未唯一，停止收敛：'
                           + json.dumps([str(entry['path']) for entry in candidates],
                                        ensure_ascii=False))
    verify(DESTINATION)
    if fingerprint(DESTINATION) != source_hash or fingerprint(SOURCE) != source_hash:
        raise RuntimeError('规范安装与当前构建载荷不一致，停止收敛。')
    inventory = registry_inventory()
    expected = {identity[0]: ({DESTINATION} if identity == EXPECTED else set())
                for identity in KNOWN}
    if inventory != expected:
        actual = {key: sorted(str(path) for path in paths) for key, paths in inventory.items()}
        raise RuntimeError('应用登记尚未唯一，暂不标记升级完成：'
                           + json.dumps(actual, ensure_ascii=False))
    return {'installedProjectAppCount': 1, 'distAppCount': 0, 'registeredProjectPathCount': 1}


def _require_handoff_registration(inventory, handoff, already_current):
    """接管前系统登记必须只指向旧入口；重试时最多再容纳新规范入口。"""
    handoff_path = Path(handoff['installedPath'])
    expected = {identity[0]: ({handoff_path} if identity == EXPECTED else set())
                for identity in KNOWN}
    if inventory == expected:
        return
    retry_tolerant = False
    if already_current and handoff_path != DESTINATION:
        allowed = {handoff_path, DESTINATION}
        retry_tolerant = (inventory[EXPECTED[0]] <= allowed
                          and all(not paths for bundle_id, paths in inventory.items()
                                  if bundle_id != EXPECTED[0]))
    if not retry_tolerant:
        raise RuntimeError('旧应用登记不唯一，拒绝接管。')


def install(check_only=False, migrate_from=None):
    """一次完整安装：核验构建 → 恢复中断事务 → 清点 → 发布 → 退役 → 收敛审计。"""
    if check_only and migrate_from is not None:
        raise RuntimeError('只读检查与来源接管不能同时执行。')
    old_root = migration_root(migrate_from) if migrate_from is not None else None
    with install_lock(check_only, old_root):
        return _install_locked(check_only, old_root)


def _install_locked(check_only, old_root):
    if (ROOT / '.build').is_symlink() or SOURCE.suffix.lower() == '.app':
        raise RuntimeError('构建源要求位于项目 .build 内且无 .app 后缀，并须为实体载荷。')
    source_hash = fingerprint(SOURCE)
    source_info = verify(SOURCE)
    HELPERS['check_inputs'](SOURCE)
    if fingerprint(SOURCE) != source_hash:
        raise RuntimeError('构建载荷在核查期间发生变化，请等构建结束后再试。')
    journal = resume_pending_retirement(read_receipt(), check_only)
    already_current = False
    if old_root is not None and DESTINATION.is_dir() and not DESTINATION.is_symlink():
        try:
            verify(DESTINATION)
            already_current = fingerprint(DESTINATION) == source_hash
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
            pass
    handoff = None
    if old_root is not None:
        handoff = (pending_legacy_handoff(old_root, source_hash, journal)
                   if already_current else old_install_proof(old_root))
    candidates, _ = scan_apps(source_info, source_hash, journal, handoff)
    inventory = registry_inventory()
    ensure_registry_within_proven_scope(inventory, candidates, journal)
    if handoff is not None:
        _require_handoff_registration(inventory, handoff, already_current)
    original = next((entry for entry in candidates if entry['path'] == DESTINATION), None)
    current = original is not None and original['sha256Tree'] == source_hash
    if check_only:
        counts = unique_state(source_info, source_hash, journal)
        outcome = {'status': 'current', 'installedPath': str(DESTINATION),
                   'sourcePath': str(SOURCE), 'sha256Tree': source_hash,
                   'version': source_info['CFBundleShortVersionString'], **counts}
        print(json.dumps(outcome, ensure_ascii=False))
        return outcome
    retire = [entry for entry in candidates if entry['path'] != DESTINATION]
    if retire:
        _require_fd_capabilities()
    if not current or retire:
        require_stopped([entry['path'] for entry in candidates])
    if not current:
        if handoff is not None:
            save_receipt({  # 日志先行：接管中断后的恢复点
                'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
                'status': 'source-handoff-pending', 'installedPath': str(DESTINATION),
                'sourcePath': str(SOURCE), 'sha256Tree': source_hash,
                'bundleID': EXPECTED[0], 'executable': EXPECTED[1],
                'sourceHandoff': {'oldRoot': handoff['oldRoot'],
                                  'oldInstalledPath': handoff['installedPath'],
                                  'oldSHA256': handoff['oldSHA256'],
                                  'newRoot': str(ROOT), 'newSHA256': source_hash}})
        install_payload(source_hash, original,
                        (lambda: recheck_handoff(old_root, handoff)) if handoff is not None else None)
    verify(DESTINATION)
    if fingerprint(DESTINATION) != source_hash or fingerprint(SOURCE) != source_hash:
        raise RuntimeError('构建或安装内容已有变化，旧副本暂不清理。')

    # 回执先于删除落盘：登记刷新若中断，可凭精确路径重试。这是凭据清单，不是备份。
    retired_ledger = {claim['path']: claim for claim in proven_retirements(journal)}
    for entry in retire:
        retired_ledger[str(entry['path'])] = {
            'path': str(entry['path']), 'bundleID': entry['identity'][0],
            'executable': entry['identity'][1], 'sha256Tree': entry['sha256Tree'],
            'version': entry['info']['CFBundleShortVersionString'], 'proof': entry['proof']}
    managed_digests = {entry['sha256Tree'] for entry in candidates}
    if journal_owned(journal):
        managed_digests.update(journal.get('managedFingerprints', []))
    outcome = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
               'status': 'cleanup-pending', 'installedPath': str(DESTINATION),
               'sourcePath': str(SOURCE), 'sha256Tree': source_hash,
               'bundleID': EXPECTED[0], 'executable': EXPECTED[1],
               'displayName': source_info['CFBundleDisplayName'],
               'version': source_info['CFBundleShortVersionString'],
               'build': str(source_info['CFBundleVersion']),
               'managedFingerprints': sorted(managed_digests),
               'retiredArtifacts': list(retired_ledger.values())}
    if handoff is not None:
        outcome['sourceHandoff'] = {'oldRoot': handoff['oldRoot'], 'oldSHA256': handoff['oldSHA256'],
                                    'oldInstalledPath': handoff['installedPath'],
                                    'newRoot': str(ROOT), 'newSHA256': source_hash}
    elif journal_owned(journal) and isinstance(journal.get('sourceHandoff'), dict):
        outcome['sourceHandoff'] = journal['sourceHandoff']
    save_receipt(outcome)
    unregistered = set()
    for entry in retire:
        unchanged(entry)
        require_stopped([entry['path']])
        subprocess.run([LSREGISTER, '-u', str(entry['path'])], check=True)
        unregistered.add(entry['path'])
        unchanged(entry)
        retire_proven_entry(entry, outcome)
        print(json.dumps({'retiredPath': str(entry['path']), 'bundleID': entry['identity'][0],
                          'sha256Tree': entry['sha256Tree'], 'proof': entry['proof']},
                         ensure_ascii=False))
    # 上一次尝试可能已删除包却留下过期登记；只有持有退役凭据且路径已消失者允许补注销。
    for paths in inventory.values():
        for path in paths:
            if path != DESTINATION and path not in unregistered:
                if str(path) not in retired_ledger or path.exists() or path.is_symlink():
                    raise RuntimeError(f'登记目标已变化或没有退役凭据，拒绝注销：{path}')
                subprocess.run([LSREGISTER, '-u', str(path)], check=True)
                unregistered.add(path)
    # 规范入口永远只刷新登记、从不注销（含登记已就位的未完成升级）。
    subprocess.run([str(REGISTRY_TOOL), 'register', str(DESTINATION)], check=True)
    counts = unique_state(source_info, source_hash, outcome)
    outcome.update(status='installed' if not current
                   else ('consolidated' if retire or unregistered else 'current'), **counts)
    save_receipt(outcome)
    print(json.dumps(outcome, ensure_ascii=False))
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true', help='只读核对唯一性：实体入口、构建载荷与系统登记')
    group.add_argument('--open', action='store_true', help='升级与旧副本清理完成后启动唯一入口')
    group.add_argument('--migrate-from', metavar='OLD_ROOT', help='核实旧项目回执与构建载荷后接管其安装')
    args = parser.parse_args()
    try:
        install(args.check, args.migrate_from)
        if args.open:
            subprocess.run(['/usr/bin/open', str(DESTINATION)], check=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')

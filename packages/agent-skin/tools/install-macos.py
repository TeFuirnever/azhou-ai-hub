#!/usr/bin/env python3
"""Install one Azhou app from an unregistered payload; retire proven project copies."""
import argparse
import contextlib
import fcntl
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
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)


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
    allowed_installed_paths = (str(DESTINATION), str(DESTINATION.with_name(HELPERS['LEGACY_NAME'])))
    if not isinstance(installed_path, str) or installed_path not in allowed_installed_paths:
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


def pending_legacy_handoff(old_root, source_hash, record):
    if not trusted_receipt(record) or record.get('status') not in ('source-handoff-pending', 'cleanup-pending'):
        return None
    previous = record.get('sourceHandoff')
    if (not isinstance(previous, dict) or previous.get('oldRoot') != str(old_root)
            or previous.get('newRoot') != str(ROOT) or previous.get('newSHA256') != source_hash
            or not re.fullmatch(r'[0-9a-f]{64}', str(previous.get('oldSHA256', '')))):
        return None
    legacy_path = DESTINATION.with_name(HELPERS['LEGACY_NAME'])
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
    result = json.loads(subprocess.check_output([str(REGISTRY_TOOL), 'inventory'], text=True))
    if result.get('schema') != 1:
        raise RuntimeError('应用登记检查器返回未知格式。')
    groups = result.get('applications', [])
    if {item.get('bundleID') for item in groups} != {identity[0] for identity in KNOWN}:
        raise RuntimeError('应用登记检查没有覆盖全部已知项目 ID。')
    inventory = {}
    for group in groups:
        urls = set()
        for item in group.get('urls', []):
            path = Path(item.get('path', ''))
            if not path.is_absolute():
                raise RuntimeError('应用登记检查返回非绝对路径。')
            urls.add(path)
        inventory[group['bundleID']] = urls
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
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.azhou-install-', dir=DESTINATION.parent))
    staged = temporary / 'payload'  # Never create a second discoverable .app.
    cleanup = True
    try:
        subprocess.run(['/usr/bin/ditto', str(SOURCE), str(staged)], check=True)
        verify(staged)
        if fingerprint(staged) != source_hash or fingerprint(SOURCE) != source_hash:
            raise RuntimeError('构建载荷在复制期间发生变化，原入口未修改。')
        require_stopped([DESTINATION])
        if original:
            unchanged(original)
            if before_swap is not None:
                before_swap()
            cleanup = False
            try:
                swap(staged, DESTINATION)
            except BaseException:
                cleanup = True
                raise
            try:
                verify(DESTINATION)
                if fingerprint(DESTINATION) != source_hash:
                    raise RuntimeError('安装后内容校验失败。')
            except BaseException as verification_error:
                try:
                    swap(staged, DESTINATION)
                except BaseException as rollback_error:
                    raise RuntimeError(f'安装校验失败且回滚未完成；原包保留在 {staged}，请保留该临时目录。') from rollback_error
                cleanup = True
                raise verification_error
            cleanup = True
        else:
            if DESTINATION.exists() or DESTINATION.is_symlink():
                raise RuntimeError('规范入口被其他操作创建，未覆盖。')
            if before_swap is not None:
                before_swap()
            os.rename(staged, DESTINATION)
            try:
                verify(DESTINATION)
                if fingerprint(DESTINATION) != source_hash:
                    raise RuntimeError('安装后内容校验失败。')
            except BaseException:
                try:
                    os.rename(DESTINATION, staged)
                except OSError as error:
                    cleanup = False
                    raise RuntimeError(f'新入口校验失败且撤回未完成；旧副本未清理，临时目录已保留：{temporary}') from error
                raise
    finally:
        if cleanup:
            shutil.rmtree(temporary)


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
        record = read_receipt()
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
        if not current or retire:
            require_stopped([entry['path'] for entry in candidates])
        if not current:
            if handoff is not None:
                pending = {'schema': 2, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
                           'status': 'source-handoff-pending', 'installedPath': str(DESTINATION),
                           'sourcePath': str(SOURCE), 'sha256Tree': source_hash,
                           'bundleID': EXPECTED[0], 'executable': EXPECTED[1],
                           'sourceHandoff': {'oldRoot': handoff['oldRoot'],
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
            shutil.rmtree(entry['path'])
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

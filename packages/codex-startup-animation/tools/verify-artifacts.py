#!/usr/bin/env python3
"""Validate/publish the hidden build payload; installed-app cleanup is separate."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'  # Legacy location; only the installer may retire its apps.
NAME = '阿舟启动 Codex.app'
IDENTITY = ('local.azhou.codex-startup', 'AzhouCodexStartup')
LEGACY = {
    'Aemeath Startup.app': ('local.aemeath.startup', 'AemeathStartup'),
    'Codex.app': ('local.aemeath.extension', 'CodexStartup'),
}
KNOWN_IDENTITIES = (IDENTITY, *LEGACY.values())
PAYLOAD = ROOT / '.build/azhou-payload'
REGISTRY_TOOL = ROOT / '.build/azhou-install-registry'
MARKER = Path('Contents/Resources/azhou-build.json')
PROJECT_ID = 'azhou.codex-startup-animation'
VERSION = '0.7.1'
BUILD = '8'
ICON_NAME = 'AzhouAppIcon.icns'
INPUT_FILES = (
    'Native/App.swift', 'Native/Wallpaper.swift', 'Native/InstallRegistry.swift',
    'tools/build-macos.sh', 'tools/build-wallpaper.py', 'tools/verify-artifacts.py',
    'wallpaper/renderer.js', 'wallpaper/wallpaper.css',
    'index.html', 'style.css', 'animation.js',
)


def identity(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f'拒绝处理非实体应用目录：{path}')
    with (path / 'Contents/Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    return (info.get('CFBundleIdentifier'), info.get('CFBundleExecutable')), info


def require(path, expected):
    path = Path(path)
    actual, info = identity(path)
    if actual != expected:
        raise RuntimeError(f'身份不符，保留未处理：{path}；实际 {actual!r}，预期 {expected!r}')
    if any(item.is_symlink() for item in path.rglob('*')):
        raise RuntimeError(f'拒绝处理含符号链接的启动器：{path}')
    executable = path / 'Contents/MacOS' / expected[1]
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f'缺少主可执行文件：{executable}')
    return info


def fingerprint(path):
    """Exact package-tree digest, compatible with the 0.5.0 installer."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f'拒绝计算非实体目录的指纹：{path}')
    digest = hashlib.sha256()
    for item in sorted(path.rglob('*')):
        if item.is_symlink():
            raise RuntimeError(f'拒绝含符号链接的启动器：{item}')
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(b'\0')
            digest.update(str(item.stat().st_mode & 0o777).encode())
            digest.update(b'\0')
            digest.update(hashlib.sha256(item.read_bytes()).digest())
        elif not item.is_dir():
            raise RuntimeError(f'拒绝非普通包内容：{item}')
    return digest.hexdigest()


def aggregate_inputs(inputs):
    digest = hashlib.sha256()
    for name, value in sorted(inputs.items()):
        digest.update(name.encode('utf-8'))
        digest.update(b'\0')
        digest.update(bytes.fromhex(value))
    return digest.hexdigest()


def source_inputs():
    files = [ROOT / name for name in INPUT_FILES]
    private = ROOT / 'assets/private'
    if private.is_symlink() or not private.is_dir():
        raise RuntimeError('缺少实体私有素材目录 assets/private。')
    for item in private.rglob('*'):
        if item.is_symlink():
            raise RuntimeError(f'拒绝通过符号链接构建素材：{item}')
        if item.is_file():
            files.append(item)
        elif not item.is_dir():
            raise RuntimeError(f'拒绝非普通素材文件：{item}')
    inputs = {}
    for path in sorted(files):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'缺少实体构建输入：{path}')
        inputs[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inputs


def read_marker(path, required=False):
    """Read a self-consistent marker; callers decide which project/root to trust."""
    path = Path(path)
    marker_path = path / MARKER
    if marker_path.is_symlink():
        raise RuntimeError(f'拒绝符号链接来源标记：{marker_path}')
    if not marker_path.exists():
        if required:
            raise RuntimeError(f'缺少构建来源标记：{marker_path}')
        return None
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if not isinstance(marker, dict) or type(marker.get('schema')) is not int or marker['schema'] != 1:
        raise RuntimeError(f'构建来源标记 schema 无效：{marker_path}')
    for key in ('projectID', 'projectRoot', 'bundleID', 'executable', 'version', 'build', 'inputSHA256'):
        if not isinstance(marker.get(key), str) or not marker[key]:
            raise RuntimeError(f'构建来源标记缺少有效字段 {key}：{marker_path}')
    if not Path(marker['projectRoot']).is_absolute():
        raise RuntimeError(f'来源根目录不是绝对路径：{marker_path}')
    inputs = marker.get('inputs')
    if not isinstance(inputs, dict) or not inputs:
        raise RuntimeError(f'构建输入列表无效：{marker_path}')
    for name, value in inputs.items():
        if (not isinstance(name, str) or not name or Path(name).is_absolute()
                or '..' in Path(name).parts or not isinstance(value, str)
                or re.fullmatch(r'[0-9a-f]{64}', value) is None):
            raise RuntimeError(f'构建输入记录无效：{marker_path}')
    if marker['inputSHA256'] != aggregate_inputs(inputs):
        raise RuntimeError(f'构建输入摘要不匹配：{marker_path}')
    actual, info = identity(path)
    if actual != (marker['bundleID'], marker['executable']):
        raise RuntimeError(f'来源标记与包身份不一致：{path}')
    if (info.get('CFBundleShortVersionString'), info.get('CFBundleVersion')) != (marker['version'], marker['build']):
        raise RuntimeError(f'来源标记与包版本不一致：{path}')
    return marker


def write_marker(path):
    path = staged_path(path)
    actual, info = identity(path)
    if actual != IDENTITY or (info.get('CFBundleShortVersionString'), info.get('CFBundleVersion')) != (VERSION, BUILD):
        raise RuntimeError('只能为当前版本、本项目身份的构建载荷写入来源标记。')
    inputs = source_inputs()
    marker = {
        'schema': 1, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
        'bundleID': IDENTITY[0], 'executable': IDENTITY[1],
        'version': VERSION, 'build': BUILD,
        'inputSHA256': aggregate_inputs(inputs), 'inputs': inputs,
    }
    marker_path = path / MARKER
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    if marker_path.is_symlink():
        raise RuntimeError(f'拒绝覆写符号链接来源标记：{marker_path}')
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def check_inputs(path):
    marker = read_marker(path, required=True)
    if marker['inputs'] != source_inputs():
        raise RuntimeError('编译期间源码或私有素材发生变化，未发布；请在修改完成后重新构建。')


def staged_path(path):
    staged = Path(path).absolute()
    build = ROOT / '.build'
    if (build.is_symlink() or staged.is_symlink() or staged.name != PAYLOAD.name
            or staged.parent.is_symlink() or staged.parent.parent != build
            or not staged.parent.name.startswith('azhou-stage.')):
        raise RuntimeError('仅接受项目 .build/azhou-stage.*/azhou-payload 内的新构建实体载荷。')
    return staged


def swap(left, right):
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    operation = libc.renamex_np
    operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(os.fsencode(left), os.fsencode(right), 2) != 0:
        raise OSError(ctypes.get_errno(), '原子替换失败，旧产物保持原位')


def verify_icon(path, info):
    icon_name = info.get('CFBundleIconFile')
    current_version = info.get('CFBundleShortVersionString') == VERSION
    if not icon_name:
        if current_version:
            raise RuntimeError(f'当前构建缺少 CFBundleIconFile：{path}')
        return  # Older verified packages, including 0.5.1, can still be upgraded.
    if (not isinstance(icon_name, str) or Path(icon_name).name != icon_name
            or not icon_name.endswith('.icns') or (current_version and icon_name != ICON_NAME)):
        raise RuntimeError(f'应用图标资源名称无效：{path}')
    icon = Path(path) / 'Contents/Resources' / icon_name
    if icon.is_symlink() or not icon.is_file():
        raise RuntimeError(f'应用图标资源缺失或不是实体文件：{icon}')
    with icon.open('rb') as stream:
        header = stream.read(8)
    if (len(header) != 8 or header[:4] != b'icns'
            or int.from_bytes(header[4:8], 'big') != icon.stat().st_size or icon.stat().st_size <= 8):
        raise RuntimeError(f'应用图标 ICNS 容器无效：{icon}')


def verify_wallpaper(path, info, marker):
    if info.get('CFBundleShortVersionString') != VERSION:
        return  # Verified earlier launchers remain valid upgrade sources.
    folder = Path(path) / 'Contents/Resources/wallpaper'
    script, metadata = folder / 'install.js', folder / 'manifest.json'
    if any(f.is_symlink() or not f.is_file() for f in (script, metadata)):
        raise RuntimeError(f'当前构建缺少实体壁纸脚本或素材清单：{path}')
    manifest = json.loads(metadata.read_text())
    width, height, color_type = manifest.get('width'), manifest.get('height'), manifest.get('colorType')
    if (manifest.get('version') != VERSION or type(width) is not int or not 1024 <= width <= 8192
            or type(height) is not int or not 512 <= height <= 8192 or not 1.4 <= width / height <= 2.5
            or type(color_type) is not int or color_type not in (2, 6) or manifest.get('bitDepth') != 8
            or manifest.get('alpha') is not (color_type == 6) or manifest.get('displayMode') != 'cover'
            or manifest.get('asset') != 'assets/private/wallpaper-scene-q-v3.png'
            or manifest.get('imageSHA256') != marker['inputs'].get('assets/private/wallpaper-scene-q-v3.png')
            or manifest.get('rendererSHA256') != marker['inputs'].get('wallpaper/renderer.js')
            or manifest.get('cssSHA256') != marker['inputs'].get('wallpaper/wallpaper.css')
            or manifest.get('scriptSHA256') != hashlib.sha256(script.read_bytes()).hexdigest()):
        raise RuntimeError(f'壁纸资源与版本或构建输入不一致：{path}')


def verify_product(path):
    info = require(path, IDENTITY)
    marker = read_marker(path, required=True)
    if marker['projectID'] != PROJECT_ID or marker['projectRoot'] != str(ROOT):
        raise RuntimeError(f'来源不属于当前项目，保留未处理：{path}')
    verify_icon(path, info)
    verify_wallpaper(path, info, marker)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)], check=True)
    return info


def check():
    if (ROOT / '.build').is_symlink():
        raise RuntimeError('拒绝通过符号链接检查 .build。')
    info = verify_product(PAYLOAD)
    marker = read_marker(PAYLOAD, required=True)
    print(json.dumps({
        'kind': 'buildPayload', 'payload': str(PAYLOAD),
        'bundleID': info['CFBundleIdentifier'], 'executable': info['CFBundleExecutable'],
        'name': info['CFBundleDisplayName'], 'version': marker['version'], 'build': marker['build'],
        'LSUIElement': info.get('LSUIElement'), 'inputSHA256': marker['inputSHA256'],
        'iconFile': info.get('CFBundleIconFile'),
        'wallpaper': 'Contents/Resources/wallpaper/install.js',
        'fingerprint': fingerprint(PAYLOAD), 'hasAppSuffix': PAYLOAD.suffix == '.app',
        'installation': str(Path.home() / 'Applications' / NAME),
        'scope': 'build payload only; run tools/install-macos.py --check for installed-entry audit',
    }, ensure_ascii=False))


def publish(staged):
    staged = staged_path(staged)
    verify_product(staged)
    check_inputs(staged)
    if PAYLOAD.is_symlink():
        raise RuntimeError('拒绝替换符号链接构建载荷。')
    if PAYLOAD.exists():
        # Every affected existing object must be this project's verified payload.
        verify_product(PAYLOAD)
        marker = staged.parent / '.preserve-original'
        marker.write_text(str(staged) + '\n', encoding='utf-8')
        try:
            swap(staged, PAYLOAD)
        except BaseException:
            marker.unlink()
            raise
        try:
            verify_product(PAYLOAD)
        except BaseException as verification_error:
            try:
                swap(staged, PAYLOAD)
            except BaseException as rollback_error:
                raise RuntimeError(f'发布校验失败且回滚未完成；原载荷保留在 {staged}，请保留该临时目录。') from rollback_error
            marker.unlink()
            raise verification_error
        marker.unlink()
    else:
        os.replace(staged, PAYLOAD)
        try:
            verify_product(PAYLOAD)
        except Exception:
            os.rename(PAYLOAD, staged)
            raise
    # Never touch dist or installed .app paths here. The installer verifies the
    # new installed app before retiring its proven old entrances.
    check()
    if staged.exists():
        shutil.rmtree(staged)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--publish', metavar='STAGED_PAYLOAD')
    actions.add_argument('--write-marker', metavar='STAGED_PAYLOAD')
    actions.add_argument('--check-inputs', metavar='STAGED_PAYLOAD')
    options = parser.parse_args()
    try:
        if options.publish:
            publish(options.publish)
        elif options.write_marker:
            write_marker(options.write_marker)
        elif options.check_inputs:
            check_inputs(options.check_inputs)
        else:
            check()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, plistlib.InvalidFileException) as error:
        parser.exit(1, f'{error}\n')

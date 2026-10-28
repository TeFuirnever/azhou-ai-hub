#!/usr/bin/env python3
"""Validate/publish the hidden build payload; installed-app cleanup is separate."""
import argparse
import base64
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'  # Legacy location; only the installer may retire its apps.
NAME = '阿舟 AI 实验室.app'
LEGACY_NAME = '阿舟启动 Codex.app'
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
VERSION = '0.9.0'
BUILD = '10'
ICON_NAME = 'AzhouAppIcon.icns'
INPUT_FILES = (
    'Native/App.swift', 'Native/Wallpaper.swift', 'Native/InstallRegistry.swift',
    'tools/build-macos.sh', 'tools/build-wallpaper.py', 'tools/build-startup.py',
    'tools/build-startup-assets.swift', 'tools/verify-artifacts.py', 'hub-package.json',
    'extension/renderer.mjs', 'image-settings.js', 'localization.js', 'wallpaper/renderer.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js',
)
STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'image-settings.js', 'localization.js', 'wallpaper/renderer.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js', 'hub-package.json',
)
STARTUP_OUTPUTS = (
    'startup/install.js',
    'web/index.html', 'web/style.css', 'web/animation.js', 'web/image-settings.js', 'web/localization.js',
    'web/assets/defaults/avatar.png', 'web/assets/defaults/entry-avatar.png', 'web/assets/defaults/artwork.png',
    'web/assets/defaults/contours.js',
)
MAX_STARTUP_BYTES = 24 * 1024 * 1024
MAX_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ENTRY_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ARTWORK_DATA_URL_BYTES = 12 * 1024 * 1024


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


def png_details(data, label):
    """Validate a complete, non-interlaced 8-bit RGB/RGBA PNG without Pillow."""
    if not isinstance(data, bytes) or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError(f'启动默认图不是有效 PNG：{label}')
    position = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    seen_end = False
    seen_data = False
    while position < len(data):
        if position + 12 > len(data):
            raise RuntimeError(f'启动默认 PNG 区块被截断：{label}')
        size = int.from_bytes(data[position:position + 4], 'big')
        kind = data[position + 4:position + 8]
        end = position + 12 + size
        if end > len(data):
            raise RuntimeError(f'启动默认 PNG 区块长度无效：{label}')
        body = data[position + 4:position + 8 + size]
        expected_crc = int.from_bytes(data[position + 8 + size:end], 'big')
        if (zlib.crc32(body) & 0xffffffff) != expected_crc:
            raise RuntimeError(f'启动默认 PNG 校验失败：{label}')
        chunk = data[position + 8:position + 8 + size]
        if position == 8:
            if kind != b'IHDR' or size != 13:
                raise RuntimeError(f'启动默认 PNG 缺少有效 IHDR：{label}')
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            if (not width or not height or width * height > 48_000_000
                    or bit_depth != 8 or color_type not in (2, 6)
                    or compression != 0 or filtering != 0 or interlace != 0):
                raise RuntimeError(f'启动默认 PNG 尺寸或像素格式无效：{label}')
        elif kind == b'IDAT':
            if seen_end:
                raise RuntimeError(f'启动默认 PNG 数据位于 IEND 之后：{label}')
            seen_data = True
            compressed.extend(chunk)
        elif kind == b'IEND':
            if size != 0 or seen_end or not seen_data:
                raise RuntimeError(f'启动默认 PNG 缺少有效图像数据：{label}')
            seen_end = True
            if end != len(data):
                raise RuntimeError(f'启动默认 PNG 含有尾随数据：{label}')
        elif not seen_data and kind[0] & 0x20 == 0 and kind not in (b'PLTE',):
            raise RuntimeError(f'启动默认 PNG 含有不支持的关键区块：{label}')
        position = end
    if not seen_end or width is None or height is None:
        raise RuntimeError(f'启动默认 PNG 未完整结束：{label}')
    channels = 3 if color_type == 2 else 4
    row_bytes = width * channels
    expected_size = (row_bytes + 1) * height
    try:
        decoded = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise RuntimeError(f'启动默认 PNG 无法解码：{label}') from exc
    if len(decoded) != expected_size or any(decoded[row * (row_bytes + 1)] > 4 for row in range(height)):
        raise RuntimeError(f'启动默认 PNG 解码长度或滤镜无效：{label}')
    return {'width': width, 'height': height, 'bitDepth': bit_depth, 'colorType': color_type}


def validate_contours(value, label='startup defaults'):
    if not isinstance(value, list) or not 1 <= len(value) <= 1200:
        raise RuntimeError(f'启动轮廓数量无效：{label}')
    total = 0
    length = 0.0
    for path in value:
        if not isinstance(path, list) or len(path) < 2:
            raise RuntimeError(f'启动轮廓路径无效：{label}')
        previous = None
        for point in path:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(axis) not in (int, float) or not math.isfinite(axis) for axis in point)
                    or not 0 <= point[0] <= 1536 or not 0 <= point[1] <= 1024):
                raise RuntimeError(f'启动轮廓坐标无效：{label}')
            if previous is not None:
                length += math.hypot(point[0] - previous[0], point[1] - previous[1])
            previous = point
            total += 1
            if total > 300_000:
                raise RuntimeError(f'启动轮廓点数超出上限：{label}')
    if length <= 0:
        raise RuntimeError(f'启动轮廓没有可绘制路径：{label}')
    return total


def _read_json(path, label):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'启动资源缺失或不是实体文件：{path}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'启动资源 JSON 无效：{label}') from exc
    return value


def verify_startup(path, info, marker):
    """Validate the current startup bundle against its source marker and resources."""
    if not set(STARTUP_REQUIRED_INPUTS).issubset(INPUT_FILES):
        missing = sorted(set(STARTUP_REQUIRED_INPUTS) - set(INPUT_FILES))
        raise RuntimeError('启动构建源码未纳入 INPUT_FILES：' + ', '.join(missing))
    if (info.get('CFBundleShortVersionString'), str(info.get('CFBundleVersion'))) != (VERSION, BUILD):
        raise RuntimeError('启动载荷 App version/build 与当前 verifier 不一致。')
    if (marker.get('version'), marker.get('build')) != (VERSION, BUILD):
        raise RuntimeError('启动载荷来源标记的版本与当前 verifier 不一致。')
    if not isinstance(marker.get('inputs'), dict) or marker.get('inputSHA256') != aggregate_inputs(marker['inputs']):
        raise RuntimeError('启动载荷来源输入摘要无效。')
    if not Path(path).is_dir() or Path(path).is_symlink():
        raise RuntimeError(f'启动载荷目录无效：{path}')

    resources = Path(path) / 'Contents/Resources'
    startup = resources / 'startup'
    install_script = startup / 'install.js'
    manifest_path = startup / 'manifest.json'
    if (startup.is_symlink() or install_script.is_symlink() or manifest_path.is_symlink()
            or not install_script.is_file() or not manifest_path.is_file()):
        raise RuntimeError(f'当前构建缺少 startup/install.js 或 manifest.json：{path}')
    script_data = install_script.read_bytes()
    if not script_data or len(script_data) >= MAX_STARTUP_BYTES:
        raise RuntimeError('startup/install.js 必须小于 24 MiB。')
    try:
        script = script_data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise RuntimeError('startup/install.js 必须是 UTF-8。') from exc
    if (re.search(r'^\s*(?:import|export)\s', script, re.M)
            or re.search(r'\b(?:fixture|preview)\s*:\s*true\b', script)
            or re.search(r'''["'`](?:https?:)?//[^\s"'`]+''', script)
            or re.search(r'\b(?:fetch|XMLHttpRequest)\s*\(', script)):
        raise RuntimeError('startup/install.js 含有模块导入、fixture/preview 开关或外部资源访问。')

    manifest = _read_json(manifest_path, 'startup manifest')
    if (not isinstance(manifest, dict) or type(manifest.get('schema')) is not int or manifest.get('schema') != 1
            or type(manifest.get('protocolVersion')) is not int or manifest.get('protocolVersion') != 1
            or manifest.get('appVersion') != VERSION or str(manifest.get('appBuild')) != BUILD
            or manifest.get('inputSHA256') != marker['inputSHA256']):
        raise RuntimeError('startup manifest schema、protocol、version/build 或输入摘要无效。')

    source_inputs = manifest.get('sourceInputs')
    if not isinstance(source_inputs, dict) or set(source_inputs) != set(STARTUP_REQUIRED_INPUTS):
        raise RuntimeError('startup manifest 的 sourceInputs 清单不完整。')
    for name in STARTUP_REQUIRED_INPUTS:
        digest = source_inputs.get(name)
        if (not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None
                or marker['inputs'].get(name) != digest):
            raise RuntimeError(f'启动构建源码未被来源标记覆盖：{name}')

    metadata_path = ROOT / 'hub-package.json'
    package = _read_json(metadata_path, 'hub package manifest')
    if (package.get('runtime_version') != VERSION or str(package.get('runtime_build')) != BUILD
            or not set(STARTUP_REQUIRED_INPUTS).issubset(package.get('build_inputs', []))
            or not set(STARTUP_REQUIRED_INPUTS).issubset(package.get('runtime_paths', []))):
        raise RuntimeError('Hub package runtime version/build 或 startup build inputs/runtime_paths 未同步。')

    outputs = manifest.get('outputs')
    if not isinstance(outputs, dict) or set(outputs) != set(STARTUP_OUTPUTS):
        raise RuntimeError('startup manifest 的 output 路径清单不完整。')
    output_bytes = {}
    for relative in STARTUP_OUTPUTS:
        candidate = resources / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError(f'启动产物缺失或不是实体文件：{candidate}')
        data = candidate.read_bytes()
        digest = outputs.get(relative)
        if not isinstance(digest, str) or digest != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f'启动产物摘要不匹配：{candidate}')
        output_bytes[relative] = data

    for source_name in ('index.html', 'style.css', 'animation.js', 'image-settings.js', 'localization.js'):
        copied = output_bytes['web/' + source_name]
        source_digest = marker['inputs'].get(source_name)
        if source_digest != hashlib.sha256(copied).hexdigest():
            raise RuntimeError(f'预览源码与标记来源不一致：web/{source_name}')

    defaults = output_bytes['web/assets/defaults/contours.js']
    prefix = b'window.AGENT_SKIN_ASSETS = Object.freeze('
    suffix = b');\n'
    if not defaults.startswith(prefix) or not defaults.endswith(suffix):
        raise RuntimeError('web/assets/defaults/contours.js 不符合 AGENT_SKIN_ASSETS 固定格式。')
    try:
        preview_assets = json.loads(defaults[len(prefix):-len(suffix)].decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError('默认素材 JavaScript 不是受控 JSON 数据。') from exc
    required_asset_keys = {'avatar', 'entryAvatar', 'artwork', 'artworkSHA256', 'contours', 'wallpaperStrength'}
    if not isinstance(preview_assets, dict) or set(preview_assets) != required_asset_keys:
        raise RuntimeError('默认素材对象字段与 Agent Skin 资源契约不符。')
    image_details = {}
    for key, relative, size_limit in (
        ('avatar', 'web/assets/defaults/avatar.png', MAX_AVATAR_DATA_URL_BYTES),
        ('entryAvatar', 'web/assets/defaults/entry-avatar.png', MAX_ENTRY_AVATAR_DATA_URL_BYTES),
        ('artwork', 'web/assets/defaults/artwork.png', MAX_ARTWORK_DATA_URL_BYTES),
    ):
        encoded = preview_assets.get(key)
        if not isinstance(encoded, str) or not encoded.startswith('data:image/png;base64,'):
            raise RuntimeError(f'默认 {key} 必须使用规范 PNG data URL。')
        try:
            image_bytes = base64.b64decode(encoded.split(',', 1)[1], validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError(f'默认 {key} PNG data URL 无效。') from exc
        if len(encoded.encode('ascii')) > size_limit:
            raise RuntimeError(f'默认 {key} data URL 超出允许大小。')
        if image_bytes != output_bytes[relative]:
            raise RuntimeError(f'预览默认 {key} 与打包 PNG 字节不一致。')
        details = png_details(image_bytes, relative)
        image_details[key] = details
        if key == 'avatar':
            expected = (512, 512)
            if (details['width'], details['height']) != expected:
                raise RuntimeError(f'默认 {key} 必须为 {expected[0]}×{expected[1]} PNG。')
        elif key == 'entryAvatar' and (details['width'], details['height']) != (1254, 1254):
            raise RuntimeError('默认 entryAvatar 必须为 1254×1254 PNG。')
        elif key == 'artwork' and (details['width'], details['height']) != (1536, 1024):
            raise RuntimeError('默认 artwork 必须为 1536×1024 PNG。')

    artwork_sha = hashlib.sha256(output_bytes['web/assets/defaults/artwork.png']).hexdigest()
    if preview_assets.get('artworkSHA256') != artwork_sha:
        raise RuntimeError('默认背景摘要与默认线稿来源不一致。')
    point_count = validate_contours(preview_assets.get('contours'))
    if (manifest.get('assets') != {
            'avatar': {'width': 512, 'height': 512,
                       'sha256': hashlib.sha256(output_bytes['web/assets/defaults/avatar.png']).hexdigest()},
            'entryAvatar': {'width': image_details['entryAvatar']['width'],
                            'height': image_details['entryAvatar']['height'],
                            'sha256': hashlib.sha256(output_bytes['web/assets/defaults/entry-avatar.png']).hexdigest()},
            'artwork': {'width': 1536, 'height': 1024, 'sha256': artwork_sha},
            'contours': preview_assets['contours'],
            'contourPathCount': len(preview_assets['contours']),
            'contourPointCount': point_count,
            'contourArtworkSHA256': artwork_sha,
        }
            or preview_assets.get('wallpaperStrength') != 42):
        raise RuntimeError('startup manifest 默认图像、线稿配准或文字默认值无效。')

    assets_prefix = 'const DEFAULT_ASSETS = Object.freeze('
    if assets_prefix not in script:
        raise RuntimeError('startup/install.js 未嵌入受控默认素材对象。')
    literal = script.split(assets_prefix, 1)[1].split(');\n', 1)[0]
    try:
        bundled_assets = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise RuntimeError('startup/install.js 默认素材对象无效。') from exc
    if bundled_assets != preview_assets:
        raise RuntimeError('启动载荷与预览没有使用同一组默认图像和线稿。')
    if 'return installStartup(installAnimation, globalThis);' not in script:
        raise RuntimeError('startup/install.js 未从完整 Page Controller 安装入口返回结果。')
    return manifest


def verify_localized_names(path, info):
    if (info.get('CFBundleName'), info.get('CFBundleDisplayName')) != ('Azhou AI Lab', 'Azhou AI Lab'):
        raise RuntimeError('Native bundle fallback display name must be Azhou AI Lab.')
    resources = Path(path) / 'Contents/Resources'
    expected = {
        'en.lproj/InfoPlist.strings': (
            '"CFBundleDisplayName" = "Azhou AI Lab";\n'
            '"CFBundleName" = "Azhou AI Lab";\n'
        ),
        'zh-Hans.lproj/InfoPlist.strings': (
            '"CFBundleDisplayName" = "阿舟 AI 实验室";\n'
            '"CFBundleName" = "阿舟 AI 实验室";\n'
        ),
    }
    for relative, text in expected.items():
        candidate = resources / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError(f'Native localized display-name resource is missing: {relative}')
        try:
            actual = candidate.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f'Native localized display-name resource is unreadable: {relative}') from exc
        if actual != text:
            raise RuntimeError(f'Native localized display-name resource is incorrect: {relative}')


def verify_product(path):
    info = require(path, IDENTITY)
    marker = read_marker(path, required=True)
    if marker['projectID'] != PROJECT_ID or marker['projectRoot'] != str(ROOT):
        raise RuntimeError(f'来源不属于当前项目，保留未处理：{path}')
    if (info.get('CFBundleShortVersionString'), str(info.get('CFBundleVersion'))) == (VERSION, BUILD):
        verify_localized_names(path, info)
    verify_icon(path, info)
    verify_wallpaper(path, info, marker)
    if info.get('CFBundleShortVersionString') == VERSION:
        verify_startup(path, info, marker)
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
        'startup': 'Contents/Resources/startup/install.js',
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

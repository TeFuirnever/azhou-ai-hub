#!/usr/bin/env python3
"""Validate/publish the hidden build payload; installed-app cleanup is separate."""
import argparse
import base64
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'  # Legacy location; only the installer may retire its apps.
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
# Frozen installed-state owner identity; installed receipts and registry records
# depend on this exact historical string (inherited from codex-startup-animation).
PROJECT_ID = 'azhou.codex-startup-animation'
ICON_NAME = 'AzhouAppIcon.icns'


def _read_source_json(root: Path, relative: str, label: str) -> dict:
    path = Path(root) / relative
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'Missing {label}: {path}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'{label} is not valid JSON: {path}') from exc
    if not isinstance(value, dict):
        raise RuntimeError(f'{label} must be a JSON object: {path}')
    return value


def load_package_metadata(root: Path = ROOT) -> dict:
    package = _read_source_json(root, 'hub-package.json', 'hub package manifest')
    version = package.get('runtime_version')
    raw_build = package.get('runtime_build')
    if (not isinstance(version, str) or re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?', version) is None
            or isinstance(raw_build, bool) or not isinstance(raw_build, (str, int))
            or re.fullmatch(r'[0-9]+', str(raw_build)) is None):
        raise RuntimeError('hub-package.json runtime_version/runtime_build are invalid.')
    package['runtime_version'] = version
    package['runtime_build'] = str(raw_build)
    return package


def _locale_map(value, label: str, *, max_length: int, allow_empty: bool = False) -> dict:
    if not isinstance(value, dict) or set(value) != {'zh-CN', 'en'}:
        raise RuntimeError(f'{label} must define exactly zh-CN and en values.')
    for locale, text in value.items():
        if not isinstance(text, str) or (not allow_empty and not text.strip()):
            raise RuntimeError(f'{label}.{locale} is not safe display text.')
        if any(ord(character) < 32 or 0x7f <= ord(character) <= 0x9f
               or 0xd800 <= ord(character) <= 0xdfff for character in text):
            raise RuntimeError(f'{label}.{locale} contains a control or invalid Unicode character.')
        if len(text.encode('utf-16-le')) // 2 > max_length:
            raise RuntimeError(f'{label}.{locale} exceeds the {max_length}-UTF-16-code-unit runtime limit.')
    return value


# Published Azhou artwork (CC BY-NC-ND 4.0) and the optional, Git-ignored local
# overlay. A logical asset resolves from the overlay first, then the library.
ASSET_LIBRARY = 'assets/azhou'
ASSET_OVERLAY = 'assets/private'
ASSET_SOURCES = (('private', ASSET_OVERLAY), ('azhou', ASSET_LIBRARY))
STARTUP_ASSET_NAMES = ('working.png', 'wallpaper-scene-q-v3.png')
# Themes embedded in earlier bundles name their inputs under the overlay.
_ASSET_PREFIXES = (('assets', 'azhou'), ('assets', 'private'))


def _asset_input_path(value, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or '\\' in value:
        raise RuntimeError(f'{label} must be a relative assets/azhou path.')
    relative = PurePosixPath(value)
    if (relative.is_absolute() or relative.as_posix() != value
            or len(relative.parts) < 3 or relative.parts[:2] not in _ASSET_PREFIXES
            or any(part in ('', '.', '..') for part in relative.parts)):
        raise RuntimeError(f'{label} must stay inside assets/azhou.')
    return relative


def asset_name(value, label: str = 'asset') -> str:
    """Logical asset name of a theme input, independent of where it resolves."""
    return PurePosixPath(*_asset_input_path(value, label).parts[2:]).as_posix()


def resolve_asset(root: Path, name: str, label: str | None = None) -> tuple[Path, str]:
    """Return (path, source) for one logical asset: overlay first, then library."""
    label = label or name
    relative = PurePosixPath(name)
    if (not name or '\\' in name or relative.is_absolute() or relative.as_posix() != name
            or any(part in ('', '.', '..') for part in relative.parts)):
        raise RuntimeError(f'{label} is not a safe logical asset name: {name!r}')
    root = Path(root)
    for source, base in ASSET_SOURCES:
        parts = (*PurePosixPath(base).parts, *relative.parts)
        current = root
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise RuntimeError(f'{label} cannot pass through a symlink: {current}')
        target = root.joinpath(*parts)
        if not target.exists():
            continue
        if not target.is_file():
            raise RuntimeError(f'{label} is not a regular file: {target}')
        target.resolve(strict=True).relative_to(root.resolve())
        return target, source
    raise RuntimeError(f'缺少阿舟素材 {name}：assets/private/ 与 assets/azhou/ 中都没有。')


def _asset_input(root: Path, value, label: str) -> Path:
    return resolve_asset(root, asset_name(value, label), label)[0]


def asset_names(theme: dict) -> tuple[str, ...]:
    identity = theme['identity']
    return (*STARTUP_ASSET_NAMES, asset_name(identity['iconInput'], 'identity.iconInput'),
            asset_name(identity['entryAvatarInput'], 'identity.entryAvatarInput'))


def resolved_assets(root: Path = ROOT) -> dict:
    """Map each required logical asset to its (path, source) for this checkout."""
    root = Path(root)
    overlay = root / ASSET_OVERLAY
    if overlay.is_symlink() or (overlay.exists() and not overlay.is_dir()):
        raise RuntimeError('assets/private 只能是实体目录（可选的本地覆盖层）。')
    return {name: resolve_asset(root, name) for name in asset_names(load_theme_config(root))}


def asset_sources(root: Path = ROOT) -> dict:
    return {name: source for name, (_, source) in resolved_assets(root).items()}


def asset_key(root: Path, name: str) -> str:
    """Repository-relative path a build input records for one logical asset."""
    path, _ = resolve_asset(root, name)
    return path.relative_to(Path(root)).as_posix()


def _validate_theme_config_data(config: dict, version: str, build: str) -> dict:
    if set(config) != {'identity', 'startup', 'wallpaper'}:
        raise RuntimeError('theme-config.json has an unsupported top-level shape.')
    identity = config.get('identity')
    if not isinstance(identity, dict) or set(identity) != {
            'appName', 'botName', 'installationName', 'iconInput', 'entryAvatarInput'}:
        raise RuntimeError('theme-config.json identity fields are invalid.')
    app_name = _locale_map(identity.get('appName'), 'identity.appName', max_length=64)
    bot_name = _locale_map(identity.get('botName'), 'identity.botName', max_length=32)
    installation_name = identity.get('installationName')
    if (not isinstance(installation_name, str) or len(installation_name) > 255
            or '/' in installation_name or '\\' in installation_name
            or not installation_name.endswith('.app') or installation_name == '.app'
            or any(ord(character) < 32 or ord(character) == 127 for character in installation_name)):
        raise RuntimeError('theme-config.json installationName must be a safe .app basename.')
    icon_input = _asset_input_path(identity.get('iconInput'), 'identity.iconInput')
    entry_avatar_input = _asset_input_path(identity.get('entryAvatarInput'), 'identity.entryAvatarInput')
    if icon_input.parts[2:] == entry_avatar_input.parts[2:]:
        raise RuntimeError('theme-config.json iconInput and entryAvatarInput must be distinct assets.')

    startup = config.get('startup')
    if not isinstance(startup, dict) or set(startup) != {'durationMs', 'text'}:
        raise RuntimeError('theme-config.json startup fields are invalid.')
    duration_ms = startup.get('durationMs')
    if type(duration_ms) is not int or duration_ms != 12000:
        raise RuntimeError('theme-config.json startup.durationMs must be exactly 12000; the runtime animation duration is fixed.')
    text = startup.get('text')
    if not isinstance(text, dict) or set(text) != {'introTitle', 'introCaption', 'artworkSubtitle'}:
        raise RuntimeError('theme-config.json startup.text fields are invalid.')
    text_limits = {'introTitle': 16, 'introCaption': 48, 'artworkSubtitle': 60}
    for key, value in text.items():
        _locale_map(value, f'startup.text.{key}', max_length=text_limits[key], allow_empty=True)

    wallpaper = config.get('wallpaper')
    if not isinstance(wallpaper, dict) or set(wallpaper) != {'strength', 'min', 'max'}:
        raise RuntimeError('theme-config.json wallpaper fields are invalid.')
    strength, minimum, maximum = wallpaper.get('strength'), wallpaper.get('min'), wallpaper.get('max')
    if (any(type(value) is not int for value in (strength, minimum, maximum))
            or minimum != 0 or maximum != 75 or not minimum <= strength <= maximum):
        raise RuntimeError('theme-config.json wallpaper min/max must be 0/75 and strength must be within that runtime range.')

    output = {
        'identity': {
            'appName': app_name,
            'botName': bot_name,
            'installationName': installation_name,
            'iconInput': identity['iconInput'],
            'entryAvatarInput': identity['entryAvatarInput'],
            'version': version,
            'build': build,
        },
        'startup': {'durationMs': duration_ms, 'text': text},
        'wallpaper': {'strength': strength, 'min': minimum, 'max': maximum},
    }
    return output


def validate_embedded_theme_config(value, version: str, build: str) -> dict:
    """Validate a theme stored in a bundle without consulting current source files."""
    if not isinstance(value, dict) or not isinstance(value.get('identity'), dict):
        raise RuntimeError('Embedded themeConfig must be a JSON object with identity metadata.')
    identity = value['identity']
    if set(identity) != {'appName', 'botName', 'installationName', 'iconInput', 'entryAvatarInput', 'version', 'build'}:
        raise RuntimeError('Embedded themeConfig identity fields are invalid.')
    if identity.get('version') != version or str(identity.get('build')) != str(build):
        raise RuntimeError('Embedded themeConfig release does not match its startup manifest.')
    source_config = {
        'identity': {key: identity[key] for key in (
            'appName', 'botName', 'installationName', 'iconInput', 'entryAvatarInput',
        )},
        'startup': value.get('startup'),
        'wallpaper': value.get('wallpaper'),
    }
    validated = _validate_theme_config_data(source_config, version, str(build))
    if validated != value:
        raise RuntimeError('Embedded themeConfig is not in the normalized build-owned shape.')
    return validated


def load_theme_config(root: Path = ROOT, *, require_inputs: bool = False) -> dict:
    """Load and validate the single build-owned theme contract."""
    root = Path(root)
    config = _read_source_json(root, 'theme-config.json', 'theme config')
    package = load_package_metadata(root)
    theme = _validate_theme_config_data(config, package['runtime_version'], package['runtime_build'])
    if require_inputs:
        _asset_input(root, theme['identity']['iconInput'], 'identity.iconInput')
        _asset_input(root, theme['identity']['entryAvatarInput'], 'identity.entryAvatarInput')
    return theme


VERSION, BUILD = (load_package_metadata(ROOT)[key] for key in ('runtime_version', 'runtime_build'))
NAME = load_theme_config(ROOT)['identity']['installationName']


INPUT_FILES = (
    'Native/App.swift', 'Native/Wallpaper.swift', 'Native/InstallRegistry.swift', 'Native/InstallRegistryCore.swift',
    'Native/SkinHostContract.swift', 'Native/CodexSkinDriver.swift',
    'tools/build-macos.sh', 'tools/build-lock.py', 'tools/build-preflight.py', 'tools/build-wallpaper.py', 'tools/build-startup.py',
    'tools/build-dsh-plugin.py',
    'tools/build-startup-assets.swift', 'tools/verify-artifacts.py', 'hub-package.json', 'theme-config.json',
    'extension/renderer.mjs', 'extension/codex-page-adapter.mjs',
    'extension/hosts/dsh.mjs', 'extension/bootstrap.mjs',
    'image-settings.js', 'localization.js',
    'image-metadata-reader.js', 'vendor/dream-image-metadata.mjs', 'vendor/dream-image-metadata.LICENSE',
    'wallpaper/renderer.js', 'wallpaper/apply.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js',
)
STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'extension/codex-page-adapter.mjs', 'extension/bootstrap.mjs',
    'image-settings.js', 'localization.js',
    'image-metadata-reader.js', 'vendor/dream-image-metadata.mjs', 'vendor/dream-image-metadata.LICENSE',
    'wallpaper/renderer.js', 'wallpaper/apply.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js', 'hub-package.json', 'theme-config.json',
)
# A web plugin package, never a macOS bundle.
DSH_PLUGIN_REQUIRED_INPUTS = (*STARTUP_REQUIRED_INPUTS, 'extension/hosts/dsh.mjs', 'tools/build-dsh-plugin.py')
DSH_PLUGIN_PACKAGE_NAME = 'azhou-agent-skin'
DSH_PLUGIN_OUTPUTS = (
    'client.js', 'cordis.patch.yml', 'icon.png', 'index.js',
    'locale/en.json', 'locale/zh.json', 'package.json',
)
DSH_PLUGIN_PACKAGE_ENTRIES = (*DSH_PLUGIN_OUTPUTS, 'manifest.json')
MAX_PLUGIN_ICON_BYTES = 256 * 1024
DSH_PLUGIN_LOCALE_TITLES = {
    'zh': '阿舟 AI 实验室 for DeepSeek Harness',
    'en': 'Azhou AI Lab for DeepSeek Harness',
}
DSH_PLUGIN_PATCH_YAML = "- insert:\n    - id: azhou-agent-skin\n      name: 'azhou-agent-skin'\n"

# Exact pre-adapter startup source set, retained for installed local builds through 30.
# C0 and the parallel Codex line used overlapping build numbers with distinct inputs.
PRE_PAGE_ADAPTER_STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'extension/bootstrap.mjs', 'image-settings.js', 'localization.js',
    'image-metadata-reader.js', 'vendor/dream-image-metadata.mjs', 'vendor/dream-image-metadata.LICENSE',
    'wallpaper/renderer.js', 'wallpaper/apply.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js', 'hub-package.json', 'theme-config.json',
)
PRE_PAGE_ADAPTER_STARTUP_LAST_BUILD = 30
# Exact 0.9.0 startup source set used before image metadata was added to the payload.
PRE_IMAGE_METADATA_STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'extension/bootstrap.mjs', 'image-settings.js', 'localization.js',
    'wallpaper/renderer.js', 'wallpaper/apply.js', 'wallpaper/wallpaper.css',
    'index.html', 'style.css', 'animation.js', 'hub-package.json', 'theme-config.json',
)
# Builds 11/12 are installed locally and used this exact pre-extraction input set.
PREVIOUS_THEME_STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'image-settings.js', 'localization.js', 'wallpaper/renderer.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js', 'hub-package.json', 'theme-config.json',
)
# Exact 0.9.0/build 10 source contract from before theme-config.json was added.
LEGACY_STARTUP_REQUIRED_INPUTS = (
    'tools/build-startup.py', 'tools/build-startup-assets.swift', 'tools/verify-artifacts.py',
    'extension/renderer.mjs', 'image-settings.js', 'localization.js', 'wallpaper/renderer.js',
    'wallpaper/wallpaper.css', 'index.html', 'style.css', 'animation.js', 'hub-package.json',
)
LEGACY_STARTUP_ASSET_KEYS = frozenset({
    'avatar', 'entryAvatar', 'artwork', 'artworkSHA256', 'contours', 'wallpaperStrength',
})
# Pre-theme-config 0.9.0/build 10 bundles embedded these native names.
LEGACY_DEFAULT_APP_NAME = {'zh-CN': '阿舟 AI 实验室', 'en': 'Azhou AI Lab'}
IMAGE_METADATA_STARTUP_FIRST_BUILD = 17
STARTUP_OUTPUTS = (
    'startup/install.js',
    'web/index.html', 'web/style.css', 'web/animation.js', 'web/image-settings.js', 'web/localization.js',
    'web/image-metadata-reader.js', 'web/vendor/dream-image-metadata.mjs',
    'web/vendor/dream-image-metadata.LICENSE',
    'web/assets/defaults/avatar.png', 'web/assets/defaults/entry-avatar.png', 'web/assets/defaults/artwork.png',
    'web/assets/defaults/contours.js',
)
# Exact output set from the pre-image-metadata 0.9.0 payloads, including builds 10/11/12.
PRE_IMAGE_METADATA_STARTUP_OUTPUTS = (
    'startup/install.js',
    'web/index.html', 'web/style.css', 'web/animation.js', 'web/image-settings.js', 'web/localization.js',
    'web/assets/defaults/avatar.png', 'web/assets/defaults/entry-avatar.png', 'web/assets/defaults/artwork.png',
    'web/assets/defaults/contours.js',
)
PRE_IMAGE_METADATA_PREVIEW_SOURCES = (
    'index.html', 'style.css', 'animation.js', 'image-settings.js', 'localization.js',
)
MAX_STARTUP_BYTES = 24 * 1024 * 1024
MAX_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ENTRY_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ARTWORK_DATA_URL_BYTES = 12 * 1024 * 1024


import stat


def _require_identity_fd_support():
    if (not {os.open, os.stat}.issubset(os.supports_dir_fd) or os.stat not in os.supports_follow_symlinks
            or any(not hasattr(os, name) for name in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_CLOEXEC', 'O_NONBLOCK'))):
        raise RuntimeError('系统缺少安全读取应用身份所需的目录描述符支持。')


def identity_at_fd(root_fd):
    _require_identity_fd_support()
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    contents = os.open('Contents', flags | os.O_DIRECTORY, dir_fd=root_fd)
    try:
        info_fd = os.open('Info.plist', flags | os.O_NONBLOCK, dir_fd=contents)
        try:
            before = os.fstat(info_fd)
            if not stat.S_ISREG(before.st_mode):
                raise RuntimeError('应用 Info.plist 不是普通文件。')
            data = bytearray()
            remaining = before.st_size + 1
            while remaining:
                chunk = os.read(info_fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                data.extend(chunk)
                remaining -= len(chunk)
            after = os.fstat(info_fd)
            current = os.stat('Info.plist', dir_fd=contents, follow_symlinks=False)
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')
            if (any(getattr(before, key) != getattr(after, key) for key in fields)
                    or any(getattr(after, key) != getattr(current, key) for key in fields)):
                raise RuntimeError('应用 Info.plist 在核验期间发生变化。')
            info = plistlib.loads(data)
        finally:
            os.close(info_fd)
        current = os.stat('Contents', dir_fd=root_fd, follow_symlinks=False)
        actual = os.fstat(contents)
        if (current.st_dev, current.st_ino) != (actual.st_dev, actual.st_ino):
            raise RuntimeError('应用 Contents 目录在核验期间发生变化。')
        return (info.get('CFBundleIdentifier'), info.get('CFBundleExecutable')), info
    finally:
        os.close(contents)


def identity(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f'拒绝处理非实体应用目录：{path}')
    _require_identity_fd_support()
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        result = identity_at_fd(descriptor)
        actual, current = os.fstat(descriptor), os.stat(path, follow_symlinks=False)
        if (actual.st_dev, actual.st_ino) != (current.st_dev, current.st_ino):
            raise RuntimeError(f'应用目录在核验期间发生变化：{path}')
        return result
    finally:
        os.close(descriptor)


def checked_descendants(path):
    def fail_scan(error):
        raise error
    for directory, subdirectories, files in os.walk(path, followlinks=False, onerror=fail_scan):
        yield from (Path(directory) / name for name in (*subdirectories, *files))


def require(path, expected):
    path = Path(path)
    actual, info = identity(path)
    if actual != expected:
        raise RuntimeError(f'身份不符，保留未处理：{path}；实际 {actual!r}，预期 {expected!r}')
    if any(item.is_symlink() for item in checked_descendants(path)):
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
    for item in sorted(checked_descendants(path)):
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


def require_no_asset_transaction(root):
    local = root / '.local'
    state = local / 'agent-skin-asset-preparation'
    if local.is_symlink() or (local.exists() and not local.is_dir()):
        raise RuntimeError('Asset transaction state has an unsafe .local path; preserve it for review.')
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise RuntimeError('Asset transaction state is not a regular directory; preserve it for review.')
    journal = state / '.azhou-assets-transaction.json'
    if journal.exists() or journal.is_symlink():
        raise RuntimeError('Private asset preparation is incomplete; run prepare-azhou-assets.py --recover.')


def source_inputs():
    require_no_asset_transaction(ROOT)
    files = [ROOT / name for name in INPUT_FILES]
    files.extend(path for path, _ in resolved_assets(ROOT).values())
    inputs = {}
    for path in sorted(files):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'缺少实体构建输入：{path}')
        inputs[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    require_no_asset_transaction(ROOT)
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


def write_marker(path, *, approved_icon_sha256=None):
    path = staged_path(path)
    actual, info = identity(path)
    if actual != IDENTITY or (info.get('CFBundleShortVersionString'), info.get('CFBundleVersion')) != (VERSION, BUILD):
        raise RuntimeError('只能为当前版本、本项目身份的构建载荷写入来源标记。')
    inputs = source_inputs()
    if approved_icon_sha256 is not None:
        approved = approved_icon_sha256.lower()
        icon_input = asset_key(ROOT, asset_name(load_theme_config(ROOT)['identity']['iconInput']))
        if inputs.get(icon_input) != approved:
            raise RuntimeError('图标源图与已批准的 SHA-256 不符，未发布。')
        # Render from the verified copy even if the original changes after recording inputs.
        icon_snapshot = path.parent / 'approved-icon.png'
        shutil.copyfile(ROOT / icon_input, icon_snapshot)
        with icon_snapshot.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != approved:
                raise RuntimeError('图标源图与已批准的 SHA-256 不符，未发布。')
    marker = {
        'schema': 1, 'projectID': PROJECT_ID, 'projectRoot': str(ROOT),
        'bundleID': IDENTITY[0], 'executable': IDENTITY[1],
        'version': VERSION, 'build': BUILD,
        'inputSHA256': aggregate_inputs(inputs), 'inputs': inputs,
        'assetSources': asset_sources(ROOT),
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


def tree_receipt(path):
    """Capture directories and regular file identity/content without following links."""
    root = Path(path)
    root_stat = root.lstat()
    if not stat.S_ISDIR(root_stat.st_mode):
        raise RuntimeError(f'拒绝核验非实体目录：{root}')
    entries = []
    for item in sorted(checked_descendants(root)):
        info = item.lstat()
        relative = item.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            entries.append((relative, 'directory', info.st_dev, info.st_ino, info.st_mode & 0o777))
        elif stat.S_ISREG(info.st_mode):
            fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            try:
                opened = os.fstat(fd)
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise RuntimeError(f'文件在核验时发生替换：{item}')
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                after = os.fstat(fd)
                if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError(f'文件在核验时发生变化：{item}')
            finally:
                os.close(fd)
            entries.append((relative, 'file', info.st_dev, info.st_ino, info.st_mode & 0o777, digest))
        else:
            raise RuntimeError(f'拒绝清理含链接或非常规条目的目录：{item}')
    current = root.lstat()
    if (root_stat.st_dev, root_stat.st_ino) != (current.st_dev, current.st_ino):
        raise RuntimeError(f'目录在核验时发生替换：{root}')
    return (root_stat.st_dev, root_stat.st_ino, root_stat.st_mode & 0o777, entries)


def require_tree(path, expected):
    if tree_receipt(path) != expected:
        raise RuntimeError(f'目录身份或内容发生变化，保留未处理：{path}')


def rename_exclusive(source, destination):
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    operation = libc.renamex_np
    operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(os.fsencode(source), os.fsencode(destination), 4) != 0:
        raise OSError(ctypes.get_errno(), '排他发布失败，保留现有对象')


def stage_root_identity(path):
    root = Path(path).absolute()
    build = ROOT / '.build'
    if root.parent != build or not root.name.startswith('azhou-stage.') or build.is_symlink():
        raise RuntimeError(f'拒绝不属于本项目的构建暂存目录：{root}')
    parent, info = build.lstat(), root.lstat()
    if not stat.S_ISDIR(parent.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f'暂存根或构建目录不是实体目录：{root}')
    return {'root': str(root), 'build': [parent.st_dev, parent.st_ino], 'stage': [info.st_dev, info.st_ino]}


def seal_stage(path, identity, approved_icon):
    if stage_root_identity(path) != identity:
        raise RuntimeError(f'构建暂存目录已替换，保留：{path}')
    root = Path(path)
    receipt = tree_receipt(root)
    names = {entry[0] for entry in receipt[3] if '/' not in entry[0]}
    expected = {PAYLOAD.name, 'azhou-install-registry', 'AzhouAppIcon.iconset'}
    if approved_icon:
        expected.add('approved-icon.png')
    if names != expected:
        raise RuntimeError(f'构建暂存含未知或缺失对象，保留：{root}')
    types = {entry[0]: entry[1] for entry in receipt[3] if '/' not in entry[0]}
    if (types.get(PAYLOAD.name) != 'directory' or types.get('AzhouAppIcon.iconset') != 'directory'
            or types.get('azhou-install-registry') != 'file'
            or (approved_icon and types.get('approved-icon.png') != 'file')):
        raise RuntimeError(f'构建暂存对象类型无效，保留：{root}')
    icon_files = {f'AzhouAppIcon.iconset/icon_{size}x{size}{suffix}.png'
                  for size in (16, 32, 128, 256, 512) for suffix in ('', '@2x')}
    actual_icons = {entry[0] for entry in receipt[3] if entry[0].startswith('AzhouAppIcon.iconset/')}
    if actual_icons != icon_files or any(entry[1] != 'file' for entry in receipt[3] if entry[0] in icon_files):
        raise RuntimeError(f'构建图标目录含未知或缺失对象，保留：{root}')
    if stage_root_identity(root) != identity:
        raise RuntimeError(f'封存期间暂存根发生变化，保留：{root}')
    leftovers = [entry for entry in receipt[3]
                 if entry[0] != PAYLOAD.name and not entry[0].startswith(PAYLOAD.name + '/')
                 and entry[0] != 'azhou-install-registry']
    registry = next(entry for entry in receipt[3] if entry[0] == 'azhou-install-registry')
    return {'identity': identity, 'remaining': leftovers, 'registry': list(registry[2:])}


def cleanup_stage(path, sealed):
    if not isinstance(sealed, dict) or stage_root_identity(path) != sealed.get('identity'):
        raise RuntimeError(f'暂存根身份不符，保留：{path}')
    current = tree_receipt(path)
    if json.dumps(current[3], ensure_ascii=False) != json.dumps(sealed.get('remaining'), ensure_ascii=False):
        raise RuntimeError(f'暂存剩余内容发生变化，保留：{path}')
    if stage_root_identity(path) != sealed['identity']:
        raise RuntimeError(f'暂存根在清理前变化，保留：{path}')
    shutil.rmtree(path)


def file_receipt(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'拒绝处理非普通文件，保留：{path}')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns')
        def same(left, right):
            return all(getattr(left, field) == getattr(right, field) for field in fields)
        if not stat.S_ISREG(opened.st_mode) or not same(info, opened):
            raise RuntimeError(f'文件身份发生变化，保留：{path}')
        hasher = hashlib.sha256()
        while chunk := os.read(fd, 64 * 1024):
            hasher.update(chunk)
        digest = hasher.hexdigest()
        after = os.fstat(fd)
        current = Path(path).lstat()
        if not same(opened, after) or not same(after, current):
            raise RuntimeError(f'文件内容或身份发生变化，保留：{path}')
    finally:
        os.close(fd)
    return [info.st_dev, info.st_ino, info.st_mode & 0o777, digest]


def require_file(path, receipt):
    if file_receipt(path) != receipt:
        raise RuntimeError(f'文件身份或内容发生变化，保留：{path}')


def registry_receipt_path(receipt):
    device, inode, _, digest = receipt
    return ROOT / '.build' / f'.azhou-registry-{device}-{inode}-{digest}.json'


def registry_receipt_data(receipt):
    return {'projectRoot': str(ROOT), 'file': receipt, 'kind': 'azhou-install-registry'}


def verify_registry_receipt(receipt):
    path = registry_receipt_path(receipt)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'已有注册工具缺少来源回执，保留未替换：{REGISTRY_TOOL}')
    with path.open('r', encoding='utf-8') as stream:
        if json.load(stream) != registry_receipt_data(receipt):
            raise RuntimeError(f'注册工具来源回执不匹配，保留：{path}')


def create_registry_receipt(receipt):
    path = registry_receipt_path(receipt)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(registry_receipt_data(receipt), stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        verify_registry_receipt(receipt)


def publish_build(staged, sealed):
    staged = staged_path(staged)
    root = staged.parent
    identity = sealed.get('identity') if isinstance(sealed, dict) else None
    if stage_root_identity(root) != identity:
        raise RuntimeError(f'暂存根身份不符，保留：{root}')
    source = root / 'azhou-install-registry'
    if PAYLOAD.is_symlink():
        raise RuntimeError(f'载荷是符号链接，保留：{PAYLOAD}')
    previous_payload = tree_receipt(PAYLOAD) if PAYLOAD.exists() else None
    new = sealed.get('registry')
    require_file(source, new)
    if REGISTRY_TOOL.is_symlink():
        raise RuntimeError(f'注册工具是符号链接，保留：{REGISTRY_TOOL}')
    old = file_receipt(REGISTRY_TOOL) if REGISTRY_TOOL.exists() else None
    reused = False
    if old is not None:
        try:
            verify_registry_receipt(old)
        except RuntimeError:
            if old[2:] != new[2:]:
                raise
            reused = True  # Identical executable stays untouched; ownership is not asserted.
    create_registry_receipt(new)
    marker = root / '.registry-transaction.json'
    with marker.open('x', encoding='utf-8') as stream:
        json.dump({'projectRoot': str(ROOT), 'stage': str(root), 'new': new, 'old': old, 'reused': reused}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    marker_info = marker.lstat()

    def remove_marker():
        current = marker.lstat()
        if (current.st_dev, current.st_ino) != (marker_info.st_dev, marker_info.st_ino):
            raise RuntimeError(f'注册事务标记发生变化，保留：{marker}')
        marker.unlink()

    require_file(source, new)
    if old is None:
        rename_exclusive(source, REGISTRY_TOOL)
    elif not reused:
        require_file(REGISTRY_TOOL, old)
        swap(source, REGISTRY_TOOL)
    try:
        require_file(REGISTRY_TOOL, old if reused else new)
        if old is not None:
            require_file(source, new if reused else old)
        publish(staged)
    except BaseException as error:
        try:
            if stage_root_identity(root) != identity:
                raise RuntimeError('暂存根已变化')
            if previous_payload is None:
                if PAYLOAD.exists() or PAYLOAD.is_symlink():
                    raise RuntimeError('载荷状态未恢复')
            else:
                require_tree(PAYLOAD, previous_payload)
            require_file(REGISTRY_TOOL, old if reused else new)
            if old is None:
                rename_exclusive(REGISTRY_TOOL, source)
            elif not reused:
                require_file(source, old)
                swap(source, REGISTRY_TOOL)
                require_file(REGISTRY_TOOL, old)
            require_file(source, new)
            remove_marker()
        except BaseException as rollback_error:
            raise RuntimeError(f'注册工具回滚未确认；保留事务与暂存，请核对：{root}') from rollback_error
        raise error
    require_file(REGISTRY_TOOL, old if reused else new)
    if old is not None:
        require_file(source, new if reused else old)
        source.unlink()
    remove_marker()


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


def write_bundle_info(path):
    """Write localized bundle names from the validated theme; retain fixed app identity."""
    path = staged_path(path)
    theme = load_theme_config(ROOT, require_inputs=True)
    identity = theme['identity']
    contents = path / 'Contents'
    if contents.is_symlink() or not contents.is_dir():
        raise RuntimeError(f'缺少实体应用 Contents 目录：{contents}')
    info_path = contents / 'Info.plist'
    if info_path.is_symlink():
        raise RuntimeError(f'拒绝覆写符号链接 Info.plist：{info_path}')
    info = {
        'CFBundleExecutable': IDENTITY[1],
        'CFBundleIdentifier': IDENTITY[0],
        'CFBundleName': bundle_fallback_display_name(identity),
        'CFBundleDisplayName': bundle_fallback_display_name(identity),
        'CFBundleDevelopmentRegion': 'en',
        'CFBundleLocalizations': ['en', 'zh-Hans'],
        'CFBundleIconFile': ICON_NAME,
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': BUILD,
        'LSMinimumSystemVersion': '13.0',
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
    }
    with info_path.open('wb') as stream:
        plistlib.dump(info, stream, fmt=plistlib.FMT_XML, sort_keys=False)
    resources = contents / 'Resources'
    resources.mkdir(parents=True, exist_ok=True)
    for locale, name in (('en', identity['appName']['en']), ('zh-Hans', identity['appName']['zh-CN'])):
        localized = resources / f'{locale}.lproj/InfoPlist.strings'
        if localized.is_symlink():
            raise RuntimeError(f'拒绝覆写符号链接本地化名称：{localized}')
        localized.parent.mkdir(parents=True, exist_ok=True)
        quoted = json.dumps(name, ensure_ascii=False)
        localized.write_text(
            f'"CFBundleDisplayName" = {quoted};\n"CFBundleName" = {quoted};\n', encoding='utf-8',
        )
    return info


WALLPAPER_ASSET_KEYS = tuple(f'{base}/wallpaper-scene-q-v3.png' for _, base in ASSET_SOURCES)


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
            or manifest.get('asset') not in WALLPAPER_ASSET_KEYS
            or manifest.get('imageSHA256') != marker['inputs'].get(manifest['asset'])
            or manifest.get('rendererSHA256') != marker['inputs'].get('wallpaper/renderer.js')
            or manifest.get('cssSHA256') != marker['inputs'].get('wallpaper/wallpaper.css')
            or manifest.get('scriptSHA256') != hashlib.sha256(script.read_bytes()).hexdigest()):
        raise RuntimeError(f'壁纸资源与版本或构建输入不一致：{path}')


    wallpaper_host = manifest.get('targetHost', 'codex')
    if wallpaper_host != 'codex':
        raise RuntimeError('Wallpaper host label does not match its adapter entry.')


def verify_dsh_plugin(path):
    """Validate an assembled local DSH plugin package against the current sources.

    Mirrors verify_wallpaper's manifest binding: the plugin manifest pins the
    current build identity, the exact DSH source-input set, and the digest of
    every shipped file, so any drift from this tree refuses verification.
    """
    package = Path(path)
    if package.is_symlink():
        raise RuntimeError(f'DSH 插件包含符号链接：{package}')
    if not package.is_dir():
        raise RuntimeError(f'DSH 插件包缺失或不是实体目录：{package}')
    for item in checked_descendants(package):
        if item.is_symlink():
            raise RuntimeError(f'DSH 插件包含符号链接：{item}')
    present = sorted(item.relative_to(package).as_posix() for item in checked_descendants(package) if item.is_file())
    if present != sorted(DSH_PLUGIN_PACKAGE_ENTRIES):
        raise RuntimeError(f'DSH 插件包文件清单与固定集合不符：{package}')

    def package_bytes(relative):
        target = package / relative
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f'DSH 插件文件缺失或不是实体文件：{relative}')
        return target.read_bytes()

    def package_json_of(relative):
        try:
            value = json.loads(package_bytes(relative).decode('utf-8'))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'DSH 插件文件不是有效 JSON：{relative}') from exc
        if not isinstance(value, dict):
            raise RuntimeError(f'DSH 插件文件必须是 JSON 对象：{relative}')
        return value

    manifest_json = package_json_of('package.json')
    if (manifest_json.get('name') != DSH_PLUGIN_PACKAGE_NAME
            or manifest_json.get('private') is not True
            or manifest_json.get('type') != 'module'
            or manifest_json.get('version') != VERSION
            or manifest_json.get('icon') != 'icon.png'
            or manifest_json.get('exports') != {
                '.': './index.js', './client': './client.js',
                './locale/*.json': './locale/*.json', './package.json': './package.json'}
            or manifest_json.get('files') != ['client.js', 'cordis.patch.yml', 'icon.png', 'index.js',
                                              'locale/*.json', 'manifest.json']
            or manifest_json.get('dsh') != {
                'bundle': {'patch': './cordis.patch.yml'},
                'client': {'inject': [], 'immediately': True, 'platform': 'web'}}
            or any(key in manifest_json for key in (
                'dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'))):
        raise RuntimeError('DSH 插件 package.json 不符合固定的本地 bundle 清单。')

    if package_bytes('cordis.patch.yml').decode('utf-8') != DSH_PLUGIN_PATCH_YAML:
        raise RuntimeError('DSH 插件 patch 必须是唯一的 azhou-agent-skin insert 行。')

    try:
        index_js = package_bytes('index.js').decode('utf-8')
    except UnicodeError as exc:
        raise RuntimeError('DSH 插件 index.js 必须是 UTF-8。') from exc
    if index_js != '/** Host half of the Agent Skin bundle; the Client module owns the rendering. */\nexport function apply() {}\n':
        raise RuntimeError('DSH 插件 index.js 必须保持官方模板的宿主侧 no-op 形态。')

    client_data = package_bytes('client.js')
    if not client_data or len(client_data) >= MAX_STARTUP_BYTES:
        raise RuntimeError('DSH 插件 client.js 必须是小于 24 MiB 的非空文件。')
    try:
        client = client_data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise RuntimeError('DSH 插件 client.js 必须是 UTF-8。') from exc
    binding = ('const pageAdapter = createDSHPageAdapter(globalThis, { build: { version: APP_VERSION, buildNumber: '
               + json.dumps(BUILD) + ' }, sidebarEntry: false }, {')
    bound_once = (
        'window.__ModuleLoader__.load({', "id: 'azhou-agent-skin',", 'factory(require) {',
        'const runStartup = (registerCleanup) => {', 'function createDSHPageAdapter(', binding,
        '    installRenderer,\n    createWallpaperApplicator,\n    registerCleanup,\n  });',
        'return bootstrapStartup({', "const inject = ['slots'];", 'function apply(ctx) {',
        "slots.inject('settings.section', function* () {",
        "name: 'settings.section', id: 'azhou-appearance', order: 40,",
        'module.exports = { apply, inject };', 'return module.exports;',
        "controllerOwner: 'azhou-dsh-startup'", "owner: 'azhou.dsh-startup-animation'",
        'const DEFAULT_ASSETS = Object.freeze(',
    )
    for needle in bound_once:
        if client.count(needle) != 1:
            raise RuntimeError(f'DSH 插件 client.js 必须恰好绑定一次：{needle!r}')
    if ('createCodexPageAdapter(' in client
            or '((controllerMetadata) => {' in client
            or re.search(r'^\s*(?:import|export)\s', client, re.M)
            or re.search(r'\b(?:fixture|preview)\s*:\s*true\b', client)
            or re.search(r'''["'`](?:https?:)?//[^\s"'`]+''', client)
            or re.search(r'\b(?:fetch|XMLHttpRequest)\s*\(', client)):
        raise RuntimeError('DSH 插件 client.js 含有外来适配器、模块导入或外部资源访问。')

    for locale, title in DSH_PLUGIN_LOCALE_TITLES.items():
        meta = package_json_of(f'locale/{locale}.json')
        description = (meta.get('meta') or {}).get('description')
        if (set(meta) != {'meta'} or set(meta['meta']) != {'title', 'description'}
                or meta['meta'].get('title') != title
                or not isinstance(description, str) or not description.strip()):
            raise RuntimeError(f'DSH 插件 locale/{locale}.json 缺少固定的 meta 标题与描述。')

    icon = package_bytes('icon.png')
    if len(icon) > MAX_PLUGIN_ICON_BYTES:
        raise RuntimeError('DSH 插件 icon.png 超出宿主 256 KiB 限制。')
    png_details(icon, 'icon.png')

    inputs = source_inputs()
    manifest = package_json_of('manifest.json')
    outputs = {relative: hashlib.sha256(package_bytes(relative)).hexdigest()
               for relative in DSH_PLUGIN_OUTPUTS}
    if (manifest.get('schema') != 1 or manifest.get('protocolVersion') != 1
            or manifest.get('appVersion') != VERSION or str(manifest.get('appBuild')) != BUILD
            or manifest.get('targetHost') != 'dsh'
            or manifest.get('inputSHA256') != aggregate_inputs(inputs)
            or manifest.get('sourceInputs') != {name: inputs[name] for name in DSH_PLUGIN_REQUIRED_INPUTS}
            or manifest.get('outputs') != outputs
            or not isinstance(manifest.get('scope'), str)
            or 'no install or host writes' not in manifest['scope']):
        raise RuntimeError('DSH 插件 manifest 未绑定当前构建输入与包内文件摘要。')
    return manifest

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


def _parse_default_assets(data: bytes) -> dict:
    prefix = b'window.AGENT_SKIN_ASSETS = Object.freeze('
    suffix = b');\n'
    if not data.startswith(prefix) or not data.endswith(suffix):
        raise RuntimeError('web/assets/defaults/contours.js 不符合 AGENT_SKIN_ASSETS 固定格式。')
    try:
        value = json.loads(data[len(prefix):-len(suffix)].decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError('默认素材 JavaScript 不是受控 JSON 数据。') from exc
    if not isinstance(value, dict):
        raise RuntimeError('默认素材对象必须是受控 JSON 对象。')
    return value


def _payload_theme_config(path, version: str, build: str):
    defaults = Path(path) / 'Contents/Resources/web/assets/defaults/contours.js'
    if defaults.is_symlink() or not defaults.is_file():
        raise RuntimeError(f'启动载荷缺少实体默认素材文件：{defaults}')
    assets = _parse_default_assets(defaults.read_bytes())
    if 'themeConfig' not in assets:
        return None
    return validate_embedded_theme_config(assets['themeConfig'], version, build)


def verify_startup(path, info, marker, *, current_source=True):
    """Validate startup files against their source marker; staged builds can require current inputs."""
    if current_source and not set(STARTUP_REQUIRED_INPUTS).issubset(INPUT_FILES):
        missing = sorted(set(STARTUP_REQUIRED_INPUTS) - set(INPUT_FILES))
        raise RuntimeError('启动构建源码未纳入 INPUT_FILES：' + ', '.join(missing))
    expected_version = VERSION if current_source else marker.get('version')
    expected_build = BUILD if current_source else str(marker.get('build'))
    if (info.get('CFBundleShortVersionString'), str(info.get('CFBundleVersion'))) != (expected_version, expected_build):
        raise RuntimeError('启动载荷 App version/build 与当前 verifier 不一致。')
    if (marker.get('version'), marker.get('build')) != (expected_version, expected_build):
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
            or manifest.get('appVersion') != expected_version or str(manifest.get('appBuild')) != expected_build
            or manifest.get('inputSHA256') != marker['inputSHA256']):
        raise RuntimeError('startup manifest schema、protocol、version/build 或输入摘要无效。')

    source_inputs = manifest.get('sourceInputs')
    target_host = manifest.get('targetHost', 'codex')
    if target_host != 'codex':
        raise RuntimeError('Startup manifest targetHost is invalid.')
    current_startup_inputs = frozenset(STARTUP_REQUIRED_INPUTS)
    if current_source:
        allowed_theme_inputs = {current_startup_inputs}
    else:
        allowed_theme_inputs = {frozenset(PRE_IMAGE_METADATA_STARTUP_REQUIRED_INPUTS)}
        # 0.9.0 builds from 17 through this verifier's build share the image-metadata contract.
        is_known_image_metadata_build = (
            expected_version == '0.9.0'
            and re.fullmatch(r'(?:0|[1-9][0-9]*)', expected_build) is not None
            and len(expected_build) <= len(BUILD)
            and IMAGE_METADATA_STARTUP_FIRST_BUILD <= int(expected_build) <= int(BUILD)
        )
        if ((expected_version, expected_build) == (VERSION, BUILD)
                or is_known_image_metadata_build):
            allowed_theme_inputs.add(current_startup_inputs)
        # The local 17–30 line predates the adapter; C0 build 26 also exists.
        if (expected_version == '0.9.0' and is_known_image_metadata_build
                and int(expected_build) <= PRE_PAGE_ADAPTER_STARTUP_LAST_BUILD):
            allowed_theme_inputs.add(frozenset(PRE_PAGE_ADAPTER_STARTUP_REQUIRED_INPUTS))
        if expected_version == '0.9.0' and expected_build in {'11', '12'}:
            allowed_theme_inputs.add(frozenset(PREVIOUS_THEME_STARTUP_REQUIRED_INPUTS))
    allowed_source_inputs = set(allowed_theme_inputs)
    if not current_source and (expected_version, expected_build) == ('0.9.0', '10'):
        allowed_source_inputs.add(frozenset(LEGACY_STARTUP_REQUIRED_INPUTS))
    if (not isinstance(source_inputs, dict)
            or frozenset(source_inputs) not in allowed_source_inputs):
        raise RuntimeError('startup manifest 的 sourceInputs 清单不完整。')
    for name in source_inputs:
        digest = source_inputs.get(name)
        if (not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None
                or marker['inputs'].get(name) != digest):
            raise RuntimeError(f'启动构建源码未被来源标记覆盖：{name}')

    if current_source:
        metadata_path = ROOT / 'hub-package.json'
        package = _read_json(metadata_path, 'hub package manifest')
        if (package.get('runtime_version') != VERSION or str(package.get('runtime_build')) != BUILD
                or not set(STARTUP_REQUIRED_INPUTS).issubset(package.get('build_inputs', []))
                or not set(STARTUP_REQUIRED_INPUTS).issubset(package.get('runtime_paths', []))):
            raise RuntimeError('Hub package runtime version/build 或 startup build inputs/runtime_paths 未同步。')

    uses_current_startup_inputs = frozenset(source_inputs) == current_startup_inputs
    uses_pre_page_adapter_startup_inputs = (
        frozenset(source_inputs) == frozenset(PRE_PAGE_ADAPTER_STARTUP_REQUIRED_INPUTS))
    uses_image_metadata_outputs = uses_current_startup_inputs or uses_pre_page_adapter_startup_inputs
    expected_outputs = STARTUP_OUTPUTS if uses_image_metadata_outputs else PRE_IMAGE_METADATA_STARTUP_OUTPUTS
    outputs = manifest.get('outputs')
    if not isinstance(outputs, dict) or set(outputs) != set(expected_outputs):
        raise RuntimeError('startup manifest 的 output 路径清单不完整。')
    output_bytes = {}
    for relative in expected_outputs:
        candidate = resources / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError(f'启动产物缺失或不是实体文件：{candidate}')
        data = candidate.read_bytes()
        digest = outputs.get(relative)
        if not isinstance(digest, str) or digest != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f'启动产物摘要不匹配：{candidate}')
        output_bytes[relative] = data

    preview_sources = (
        ('index.html', 'style.css', 'animation.js', 'image-settings.js', 'localization.js',
         'image-metadata-reader.js', 'vendor/dream-image-metadata.mjs', 'vendor/dream-image-metadata.LICENSE')
        if uses_image_metadata_outputs else PRE_IMAGE_METADATA_PREVIEW_SOURCES
    )
    for source_name in preview_sources:
        copied = output_bytes['web/' + source_name]
        source_digest = marker['inputs'].get(source_name)
        if source_digest != hashlib.sha256(copied).hexdigest():
            raise RuntimeError(f'预览源码与标记来源不一致：web/{source_name}')

    preview_assets = _parse_default_assets(output_bytes['web/assets/defaults/contours.js'])
    current_asset_keys = {
        'avatar', 'entryAvatar', 'artwork', 'artworkSHA256', 'contours', 'wallpaperStrength', 'themeConfig',
    }
    legacy_asset_keys = LEGACY_STARTUP_ASSET_KEYS
    if not isinstance(preview_assets, dict):
        raise RuntimeError('默认素材对象字段与 Agent Skin 资源契约不符。')
    has_theme_config = 'themeConfig' in preview_assets
    if not has_theme_config and (expected_version, expected_build) != ('0.9.0', '10'):
        raise RuntimeError('Only verified 0.9.0/build 10 payloads may omit themeConfig.')
    expected_asset_keys = current_asset_keys if has_theme_config else legacy_asset_keys
    if (set(preview_assets) != expected_asset_keys
            or (current_source and not has_theme_config)
            or (has_theme_config and frozenset(source_inputs) not in allowed_theme_inputs)
            or (not has_theme_config and frozenset(source_inputs) != frozenset(LEGACY_STARTUP_REQUIRED_INPUTS))):
        raise RuntimeError('默认素材对象字段与 Agent Skin 资源契约不符。')
    if has_theme_config:
        if current_source:
            theme_config = load_theme_config(ROOT)
            if preview_assets.get('themeConfig') != theme_config:
                raise RuntimeError('startup themeConfig does not match the build-owned theme config and package version.')
        else:
            theme_config = validate_embedded_theme_config(
                preview_assets.get('themeConfig'), expected_version, expected_build,
            )
    else:
        theme_config = None
    expected_wallpaper_strength = theme_config['wallpaper']['strength'] if theme_config else 42
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
            or preview_assets.get('wallpaperStrength') != expected_wallpaper_strength):
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
    legacy_entry = 'return installStartup(installAnimation, globalThis);' in script
    bootstrap_entry = ('return bootstrapStartup({' in script
                       and 'return installStartup(installAnimation, host);' in script)
    page_adapter_entry = ('return bootstrapStartup({' in script
                          and 'return installStartup(installAnimation, host, pageAdapter);' in script)
    if script.startswith('((controllerMetadata) => {'):
        raise RuntimeError('Codex startup cannot carry a controller-metadata factory entry.')
    if target_host == 'codex' and not (legacy_entry or bootstrap_entry or page_adapter_entry):
        raise RuntimeError('startup/install.js 未从完整 Page Controller 安装入口返回结果。')
    return manifest


def verify_localized_names(path, info, theme_config=None, *, legacy=False):
    if legacy:
        app_name = LEGACY_DEFAULT_APP_NAME
        fallback_name = app_name['en']
    else:
        theme = theme_config or load_theme_config(ROOT)
        identity = theme['identity']
        app_name = identity['appName']
        fallback_name = bundle_fallback_display_name(identity)
    if (info.get('CFBundleName'), info.get('CFBundleDisplayName')) != (fallback_name, fallback_name):
        raise RuntimeError('Native bundle fallback display name does not match its verified theme.')
    resources = Path(path) / 'Contents/Resources'
    def localized_strings(name):
        quoted = json.dumps(name, ensure_ascii=False)
        return f'"CFBundleDisplayName" = {quoted};\n"CFBundleName" = {quoted};\n'
    expected = {
        'en.lproj/InfoPlist.strings': localized_strings(app_name['en']),
        'zh-Hans.lproj/InfoPlist.strings': localized_strings(app_name['zh-CN']),
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


def bundle_fallback_display_name(identity):
    """Keep CFBundleName aligned with the installation basename for registration."""
    version = identity['version']
    build = int(identity['build'])
    # Build 10 used an English fallback; build 11 onward aligns the native bundle
    # name with the canonical path. Localized InfoPlist.strings carry the display label.
    if version == '0.9.0' and build == 10:
        return identity['appName']['en']
    return Path(identity['installationName']).stem


def verify_product(path, *, current_source=True):
    info = require(path, IDENTITY)
    marker = read_marker(path, required=True)
    if marker['projectID'] != PROJECT_ID or marker['projectRoot'] != str(ROOT):
        raise RuntimeError(f'来源不属于当前项目，保留未处理：{path}')
    is_current_release = (
        info.get('CFBundleShortVersionString'), str(info.get('CFBundleVersion'))
    ) == (VERSION, BUILD)
    is_current_version = info.get('CFBundleShortVersionString') == VERSION
    if is_current_release and current_source:
        verify_localized_names(path, info)
    verify_icon(path, info)
    verify_wallpaper(path, info, marker)
    if is_current_version:
        verify_startup(path, info, marker, current_source=current_source)
        if not current_source:
            theme = _payload_theme_config(path, marker['version'], marker['build'])
            verify_localized_names(path, info, theme_config=theme, legacy=theme is None)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)], check=True)
    return info


def check():
    if (ROOT / '.build').is_symlink():
        raise RuntimeError('拒绝通过符号链接检查 .build。')
    info = verify_product(PAYLOAD)
    marker = read_marker(PAYLOAD, required=True)
    dsh_plugin = ROOT / '.build/azhou-dsh-plugin' / DSH_PLUGIN_PACKAGE_NAME
    dsh_plugin_path = None
    if dsh_plugin.is_symlink():
        raise RuntimeError('拒绝通过符号链接检查 DSH 插件包。')
    if dsh_plugin.is_dir():
        verify_dsh_plugin(dsh_plugin)
        dsh_plugin_path = str(dsh_plugin)
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
        'dshPlugin': dsh_plugin_path,
        'scope': 'build payload only; run tools/install-macos.py --check for installed-entry audit',
    }, ensure_ascii=False))


def publish(staged):
    staged = staged_path(staged)
    verify_product(staged)
    check_inputs(staged)
    new_tree = tree_receipt(staged)
    if PAYLOAD.is_symlink():
        raise RuntimeError('拒绝替换符号链接构建载荷。')
    if PAYLOAD.exists():
        verify_product(PAYLOAD, current_source=False)
        old_tree = tree_receipt(PAYLOAD)
        marker = staged.parent / '.preserve-original'
        with marker.open('x', encoding='utf-8') as stream:
            stream.write(str(staged) + '\n')
        marker_identity = marker.lstat()
        require_tree(staged, new_tree)
        require_tree(PAYLOAD, old_tree)
        swap(staged, PAYLOAD)
        try:
            require_tree(staged, old_tree)
            require_tree(PAYLOAD, new_tree)
            verify_product(PAYLOAD)
            check()
            require_tree(staged, old_tree)
            require_tree(PAYLOAD, new_tree)
        except BaseException as error:
            try:
                require_tree(staged, old_tree)
                require_tree(PAYLOAD, new_tree)
                swap(staged, PAYLOAD)
                require_tree(staged, new_tree)
                require_tree(PAYLOAD, old_tree)
            except BaseException as rollback_error:
                raise RuntimeError(f'发布或回滚未确认，保留两处载荷和标记，请核对：{staged}、{PAYLOAD}') from rollback_error
            current_marker = marker.lstat()
            if (current_marker.st_dev, current_marker.st_ino) != (marker_identity.st_dev, marker_identity.st_ino):
                raise RuntimeError(f'恢复标记发生变化，保留待核对：{marker}') from error
            marker.unlink()
            raise error
        current_marker = marker.lstat()
        if (current_marker.st_dev, current_marker.st_ino) != (marker_identity.st_dev, marker_identity.st_ino):
            raise RuntimeError(f'恢复标记发生变化，保留待核对：{marker}')
        shutil.rmtree(staged)
        marker.unlink()
    else:
        rename_exclusive(staged, PAYLOAD)
        try:
            require_tree(PAYLOAD, new_tree)
            verify_product(PAYLOAD)
            check()
            require_tree(PAYLOAD, new_tree)
        except BaseException as error:
            try:
                require_tree(PAYLOAD, new_tree)
                rename_exclusive(PAYLOAD, staged)
                require_tree(staged, new_tree)
            except BaseException as rollback_error:
                raise RuntimeError(f'首次发布恢复未确认，保留待核对：{staged}、{PAYLOAD}') from rollback_error
            raise error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--publish', metavar='STAGED_PAYLOAD')
    actions.add_argument('--publish-build', metavar='STAGED_PAYLOAD')
    actions.add_argument('--write-marker', metavar='STAGED_PAYLOAD')
    actions.add_argument('--write-bundle-info', metavar='STAGED_PAYLOAD')
    actions.add_argument('--check-inputs', metavar='STAGED_PAYLOAD')
    actions.add_argument('--verify-dsh-plugin', metavar='DSH_PLUGIN_DIR')
    actions.add_argument('--stage-identity', metavar='STAGE_ROOT')
    actions.add_argument('--seal-stage', metavar='STAGE_ROOT')
    actions.add_argument('--cleanup-stage', metavar='STAGE_ROOT')
    options = parser.parse_args()
    try:
        if options.publish:
            publish(options.publish)
        elif options.publish_build:
            publish_build(options.publish_build, json.load(sys.stdin))
        elif options.write_marker:
            write_marker(options.write_marker, approved_icon_sha256=os.environ.get('AZHOU_APPROVED_ICON_SHA256'))
        elif options.write_bundle_info:
            write_bundle_info(options.write_bundle_info)
        elif options.check_inputs:
            check_inputs(options.check_inputs)
        elif options.verify_dsh_plugin:
            verify_dsh_plugin(options.verify_dsh_plugin)
        elif options.stage_identity:
            print(json.dumps(stage_root_identity(options.stage_identity)))
        elif options.seal_stage:
            print(json.dumps(seal_stage(options.seal_stage, json.load(sys.stdin),
                                        bool(os.environ.get('AZHOU_APPROVED_ICON_SHA256')))))
        elif options.cleanup_stage:
            cleanup_stage(options.cleanup_stage, json.load(sys.stdin))
        else:
            check()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, plistlib.InvalidFileException) as error:
        parser.exit(1, f'{error}\n')

#!/usr/bin/env python3
"""Build the self-contained startup expression and identical preview defaults."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_STARTUP_INPUTS = (
    'assets/private/working.png',
    'assets/private/wallpaper-scene-q-v3.png',
)
PREVIEW_SOURCES = ('index.html', 'style.css', 'animation.js', 'image-settings.js', 'localization.js')
ASSET_JS_PREFIX = 'window.AGENT_SKIN_ASSETS = Object.freeze('
ASSET_JS_SUFFIX = ');\n'
MAX_STARTUP_BYTES = 24 * 1024 * 1024
MAX_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ENTRY_AVATAR_DATA_URL_BYTES = 2 * 1024 * 1024
MAX_ARTWORK_DATA_URL_BYTES = 12 * 1024 * 1024


def load_artifacts(root: Path):
    path = root / 'tools/verify-artifacts.py'
    spec = importlib.util.spec_from_file_location('agent_skin_build_artifacts', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Missing build verifier tools/verify-artifacts.py.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_private_inputs(root: Path, theme_config: dict) -> None:
    private = root / 'assets/private'
    if private.is_symlink() or not private.is_dir():
        raise RuntimeError('缺少实体私有素材目录 assets/private；source-only 构建不能生成启动默认图。')
    configured = theme_config['identity']
    for name in (*PRIVATE_STARTUP_INPUTS, configured['entryAvatarInput'], configured['iconInput']):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'缺少本地启动默认素材 {name}；source-only 构建失败。')


def _check_metadata(root: Path, artifacts, theme_config: dict) -> dict:
    missing = set(artifacts.STARTUP_REQUIRED_INPUTS) - set(artifacts.INPUT_FILES)
    if missing:
        raise RuntimeError('startup builder source missing from verify-artifacts INPUT_FILES: '
                           + ', '.join(sorted(missing)))
    package = artifacts.load_package_metadata(root)
    if (package.get('runtime_version') != theme_config['identity']['version']
            or package.get('runtime_build') != theme_config['identity']['build']
            or not set(artifacts.STARTUP_REQUIRED_INPUTS).issubset(package.get('build_inputs', []))
            or not set(artifacts.STARTUP_REQUIRED_INPUTS).issubset(package.get('runtime_paths', []))):
        raise RuntimeError('Hub package build inputs/runtime paths do not match the startup builder sources and version.')
    return package


def _extract_animation(source: str) -> str:
    declaration = 'function installAnimation('
    adapter = '/* Local preview adapter. Ticket 05 extracts only installAnimation above. */'
    if source.count(declaration) != 1 or source.count(adapter) != 1:
        raise RuntimeError('Animation source must define one installAnimation and its one local preview adapter boundary.')
    start = source.index(declaration)
    end = source.index(adapter, start)
    function = source[start:end].rstrip()
    if not function.endswith('}'):
        raise RuntimeError('installAnimation source is incomplete before the preview adapter.')
    return function


def _module_function(source: str, export_prefix: str, local_prefix: str, label: str) -> str:
    if source.count(export_prefix) != 1 or source.count('\nimport ') or source.startswith('import '):
        raise RuntimeError(f'{label} must be one self-contained module entry with no imports.')
    return source.replace(export_prefix, local_prefix, 1)


def _json_literal(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _png_data(data: bytes, label: str) -> tuple[int, int]:
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError(f'Generated startup image is not a PNG: {label}')
    position = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    ended = False
    saw_data = False
    while position < len(data):
        if position + 12 > len(data):
            raise RuntimeError(f'Generated startup PNG is truncated: {label}')
        size = int.from_bytes(data[position:position + 4], 'big')
        kind = data[position + 4:position + 8]
        end = position + 12 + size
        if end > len(data):
            raise RuntimeError(f'Generated startup PNG chunk length is invalid: {label}')
        body = data[position + 4:position + 8 + size]
        crc = int.from_bytes(data[position + 8 + size:end], 'big')
        if zlib.crc32(body) & 0xffffffff != crc:
            raise RuntimeError(f'Generated startup PNG CRC is invalid: {label}')
        chunk = data[position + 8:position + 8 + size]
        if position == 8:
            if kind != b'IHDR' or size != 13:
                raise RuntimeError(f'Generated startup PNG has no valid IHDR: {label}')
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            if (not width or not height or width * height > 48_000_000
                    or bit_depth != 8 or color_type not in (2, 6)
                    or compression != 0 or filtering != 0 or interlace != 0):
                raise RuntimeError(f'Generated startup PNG dimensions/encoding are invalid: {label}')
        elif kind == b'IDAT':
            saw_data = True
            compressed.extend(chunk)
        elif kind == b'IEND':
            if size != 0 or not saw_data or end != len(data):
                raise RuntimeError(f'Generated startup PNG is incomplete: {label}')
            ended = True
        position = end
    if not ended or width is None or height is None:
        raise RuntimeError(f'Generated startup PNG did not finish: {label}')
    channels = 3 if color_type == 2 else 4
    row_bytes = width * channels
    try:
        decoded = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise RuntimeError(f'Generated startup PNG cannot be decoded: {label}') from exc
    if (len(decoded) != (row_bytes + 1) * height
            or any(decoded[row * (row_bytes + 1)] > 4 for row in range(height))):
        raise RuntimeError(f'Generated startup PNG decoded pixels are invalid: {label}')
    return width, height


def _validate_contours(contours) -> tuple[int, int]:
    if not isinstance(contours, list) or not 1 <= len(contours) <= 1200:
        raise RuntimeError('Default artwork produced no bounded contour paths.')
    point_count = 0
    path_length = 0.0
    for path in contours:
        if not isinstance(path, list) or len(path) < 2:
            raise RuntimeError('Default contour path must contain at least two points.')
        previous = None
        for point in path:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(axis) not in (int, float) or not math.isfinite(axis) for axis in point)
                    or not 0 <= point[0] <= 1536 or not 0 <= point[1] <= 1024):
                raise RuntimeError('Default contour contains an invalid coordinate.')
            if previous is not None:
                path_length += math.hypot(point[0] - previous[0], point[1] - previous[1])
            previous = point
            point_count += 1
            if point_count > 300_000:
                raise RuntimeError('Default artwork contours exceed the 300,000-point limit.')
    if path_length <= 0:
        raise RuntimeError('Default artwork contours contain no drawable path.')
    return len(contours), point_count


def _build_script(root: Path, assets: dict, wallpaper_css: str, artifacts) -> str:
    try:
        animation = _extract_animation((root / 'animation.js').read_text(encoding='utf-8'))
        settings = (root / 'image-settings.js').read_text(encoding='utf-8').strip()
        controller = _module_function(
            (root / 'extension/renderer.mjs').read_text(encoding='utf-8'),
            'export function installStartup(', 'function installStartup(', 'Page Controller',
        ).strip()
        wallpaper = _module_function(
            (root / 'wallpaper/renderer.js').read_text(encoding='utf-8'),
            'export async function installRenderer(', 'async function installRenderer(', 'Wallpaper renderer',
        ).strip()
    except OSError as exc:
        raise RuntimeError(f'Missing startup source module: {exc.filename}') from exc
    try:
        localization = (root / 'localization.js').read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise RuntimeError(f'Missing startup localization source: {exc.filename}') from exc
    if (localization.count('function createLocalization(') != 1
            or '\nimport ' in localization or localization.startswith('import ')
            or '\nexport ' in localization or localization.startswith('export ')):
        raise RuntimeError('Localization source must contain its complete self-contained factory.')
    if (settings.count('function createImageSettings(') != 1
            or '\nimport ' in settings or settings.startswith('import ')
            or '\nexport ' in settings or settings.startswith('export ')):
        raise RuntimeError('Image Settings source must contain its complete self-contained factory.')
    if (controller.count('function installStartup(') != 1
            or wallpaper.count('async function installRenderer(') != 1):
        raise RuntimeError('Startup/controller or wallpaper module has an unexpected entry count.')
    css_literal = json.dumps(wallpaper_css, ensure_ascii=True, separators=(',', ':'))
    version_literal = json.dumps(artifacts.VERSION)
    payload = '\n'.join((
        '(() => {',
        "  'use strict';",
        f'  const APP_VERSION = {version_literal};',
        '  const DEFAULT_ASSETS = Object.freeze(' + _json_literal(assets) + ');',
        '  const WALLPAPER_CSS = ' + css_literal + ';',
        controller,
        localization,
        settings,
        wallpaper,
        animation,
        '''
  function wallpaperShellState(isCurrent) {
    if (typeof isCurrent === 'function' && !isCurrent()) return 'cancelled';
    const applicationRoot = document.getElementById('root');
    return document.body && applicationRoot
      && applicationRoot.querySelector('[data-app-shell-frame]')
      && applicationRoot.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]')
      ? 'ready' : null;
  }
  function waitForWallpaperShell(isCurrent) {
    const initial = wallpaperShellState(isCurrent);
    if (initial) return Promise.resolve(initial);
    const Observer = globalThis.MutationObserver;
    if (typeof Observer !== 'function' || !document.documentElement) return Promise.resolve('unsupported');
    return new Promise(resolve => {
      let observer;
      let timer;
      let settled = false;
      const finish = state => {
        if (settled) return;
        settled = true;
        observer?.disconnect();
        globalThis.clearTimeout(timer);
        resolve(state);
      };
      const check = () => {
        const state = wallpaperShellState(isCurrent);
        if (state) finish(state);
      };
      try {
        observer = new Observer(check);
        observer.observe(document.documentElement, {
          childList: true, subtree: true, attributes: true,
          attributeFilter: ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface'],
        });
      } catch {
        finish('unsupported');
        return;
      }
      timer = globalThis.setTimeout(() => finish(wallpaperShellState(isCurrent) || 'timeout'), 5000);
      check();
    });
  }
  async function applyWallpaper(value, isCurrent) {
    if (!value || typeof value.image !== 'string' || typeof globalThis.crypto?.subtle?.digest !== 'function') {
      throw new TypeError('wallpaper-unsupported');
    }
    const encoded = value.image.slice(value.image.indexOf(',') + 1);
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
    const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
    const imageSHA256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (typeof isCurrent === 'function' && !isCurrent()) return { applied: false, reason: 'operation-cancelled' };
    const shellState = await waitForWallpaperShell(isCurrent);
    if (shellState === 'cancelled' || (typeof isCurrent === 'function' && !isCurrent())) {
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    if (shellState !== 'ready') return { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
    return installRenderer({
      version: APP_VERSION, image: value.image, imageSHA256, css: WALLPAPER_CSS,
      strength: value.strength, isCurrent,
    });
  }
  Object.defineProperties(installAnimation, {
    assets: { value: DEFAULT_ASSETS },
    createLocalization: { value: createLocalization },
    createImageSettings: { value: createImageSettings },
    applyWallpaper: { value: applyWallpaper },
  });
  return installStartup(installAnimation, globalThis);''',
        '})()',
        '',
    ))
    if len(payload.encode('utf-8')) >= MAX_STARTUP_BYTES:
        raise RuntimeError('startup/install.js exceeds the strict 24 MiB payload limit.')
    return payload


def build_startup(bundle: Path, *, root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    bundle = Path(bundle)
    artifacts = load_artifacts(root)
    bundle = artifacts.staged_path(bundle)
    theme_config = artifacts.load_theme_config(root, require_inputs=True)
    _require_private_inputs(root, theme_config)
    _check_metadata(root, artifacts, theme_config)
    inputs = artifacts.source_inputs()
    if not set(artifacts.STARTUP_REQUIRED_INPUTS).issubset(inputs):
        raise RuntimeError('Startup manifest cannot bind every required source input.')

    resources = bundle / 'Contents/Resources'
    startup_dir = resources / 'startup'
    defaults_dir = resources / 'web/assets/defaults'
    startup_dir.mkdir(parents=True, exist_ok=True)
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for name in PREVIEW_SOURCES:
        source = root / name
        target = resources / 'web' / name
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f'Missing preview source: {name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    with tempfile.TemporaryDirectory(prefix='agent-skin-startup-assets-', dir=bundle.parent) as temporary:
        work = Path(temporary)
        executable = work / 'build-startup-assets'
        contours_path = work / 'contours.json'
        avatar_path = defaults_dir / 'avatar.png'
        entry_avatar_path = defaults_dir / 'entry-avatar.png'
        artwork_path = defaults_dir / 'artwork.png'
        architecture = subprocess.check_output(['uname', '-m'], text=True).strip()
        swift = root / 'tools/build-startup-assets.swift'
        if swift.is_symlink() or not swift.is_file():
            raise RuntimeError('Missing build-only Swift Vision helper tools/build-startup-assets.swift.')
        compile_command = [
            'xcrun', '--sdk', 'macosx', 'swiftc', '-O', '-target', f'{architecture}-apple-macos13.0',
            str(swift), '-o', str(executable), '-framework', 'Vision', '-framework', 'CoreGraphics',
            '-framework', 'ImageIO', '-framework', 'UniformTypeIdentifiers',
        ]
        try:
            subprocess.run(compile_command, cwd=root, check=True, capture_output=True, text=True)
            subprocess.run([
                str(executable), str(root / PRIVATE_STARTUP_INPUTS[0]), str(root / PRIVATE_STARTUP_INPUTS[1]),
                str(avatar_path), str(artwork_path), str(contours_path),
            ], cwd=root, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or '').strip()
            raise RuntimeError('Startup default image generation failed: ' + (detail[-1200:] or str(exc))) from exc
        try:
            contours = json.loads(contours_path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError('Vision helper did not return valid startup contour data.') from exc

    avatar = avatar_path.read_bytes()
    entry_avatar_input = root / theme_config['identity']['entryAvatarInput']
    entry_avatar = entry_avatar_input.read_bytes()
    artwork = artwork_path.read_bytes()
    avatar_dimensions = _png_data(avatar, 'avatar.png')
    entry_avatar_dimensions = _png_data(entry_avatar, 'entry-avatar.png')
    artwork_dimensions = _png_data(artwork, 'artwork.png')
    if avatar_dimensions != (512, 512) or artwork_dimensions != (1536, 1024):
        raise RuntimeError('Startup default image dimensions do not match the 512×512 / 1536×1024 contract.')
    if entry_avatar_dimensions != (1254, 1254):
        raise RuntimeError('The native entry avatar must be the provided 1254×1254 PNG.')
    avatar_data_url = 'data:image/png;base64,' + base64.b64encode(avatar).decode('ascii')
    entry_avatar_data_url = 'data:image/png;base64,' + base64.b64encode(entry_avatar).decode('ascii')
    artwork_data_url = 'data:image/png;base64,' + base64.b64encode(artwork).decode('ascii')
    if (len(avatar_data_url.encode('ascii')) > MAX_AVATAR_DATA_URL_BYTES
            or len(entry_avatar_data_url.encode('ascii')) > MAX_ENTRY_AVATAR_DATA_URL_BYTES
            or len(artwork_data_url.encode('ascii')) > MAX_ARTWORK_DATA_URL_BYTES):
        raise RuntimeError('Generated startup default image exceeds the Avatar/Entry Avatar/Artwork data URL limit.')
    contour_paths, contour_points = _validate_contours(contours)
    artwork_sha = hashlib.sha256(artwork).hexdigest()
    assets = {
        'avatar': avatar_data_url,
        'entryAvatar': entry_avatar_data_url,
        'artwork': artwork_data_url,
        'artworkSHA256': artwork_sha,
        'contours': contours,
        'wallpaperStrength': theme_config['wallpaper']['strength'],
        'themeConfig': theme_config,
    }
    (defaults_dir / 'contours.js').write_text(
        ASSET_JS_PREFIX + _json_literal(assets) + ASSET_JS_SUFFIX, encoding='utf-8',
    )
    shutil.copyfile(entry_avatar_input, entry_avatar_path)
    wallpaper_css = (root / 'wallpaper/wallpaper.css').read_text(encoding='utf-8')
    install_script = _build_script(root, assets, wallpaper_css, artifacts)
    install_path = startup_dir / 'install.js'
    install_path.write_text(install_script, encoding='utf-8')

    output_paths = ('startup/install.js', *(f'web/{name}' for name in PREVIEW_SOURCES),
                    'web/assets/defaults/avatar.png', 'web/assets/defaults/entry-avatar.png',
                    'web/assets/defaults/artwork.png',
                    'web/assets/defaults/contours.js')
    outputs = {}
    for relative in output_paths:
        outputs[relative] = hashlib.sha256((resources / relative).read_bytes()).hexdigest()
    source_inputs = {name: inputs[name] for name in artifacts.STARTUP_REQUIRED_INPUTS}
    manifest = {
        'schema': 1,
        'protocolVersion': 1,
        'appVersion': artifacts.VERSION,
        'appBuild': artifacts.BUILD,
        'inputSHA256': artifacts.aggregate_inputs(inputs),
        'sourceInputs': source_inputs,
        'outputs': outputs,
        'assets': {
            'avatar': {'width': 512, 'height': 512, 'sha256': hashlib.sha256(avatar).hexdigest()},
            'entryAvatar': {'width': entry_avatar_dimensions[0], 'height': entry_avatar_dimensions[1],
                            'sha256': hashlib.sha256(entry_avatar).hexdigest()},
            'artwork': {'width': 1536, 'height': 1024, 'sha256': artwork_sha},
            'contours': contours,
            'contourPathCount': contour_paths,
            'contourPointCount': contour_points,
            'contourArtworkSHA256': artwork_sha,
        },
    }
    manifest_path = startup_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path,
                        help='staged .build/azhou-stage.*/azhou-payload bundle')
    args = parser.parse_args()
    try:
        manifest = build_startup(args.bundle)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        parser.exit(1, f'启动载荷构建失败：{exc}\n')
    print(json.dumps({
        'kind': 'startupPayload', 'appVersion': manifest['appVersion'], 'appBuild': manifest['appBuild'],
        'protocolVersion': manifest['protocolVersion'], 'outputs': len(manifest['outputs']),
        'contours': manifest['assets']['contourPathCount'], 'points': manifest['assets']['contourPointCount'],
        'scope': 'hidden local build payload and preview defaults; no install or host writes',
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

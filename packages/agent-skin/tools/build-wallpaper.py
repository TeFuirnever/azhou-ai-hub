#!/usr/bin/env python3
"""Package local private wallpaper into a staged payload; never commit generated artwork."""

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import runpy
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSET = 'assets/private/wallpaper-scene-q-v3.png'
DATA_PREFIX = 'data:image/png;base64,'
MAX_IMAGE_BYTES = ((16 * 1024 * 1024 - len(DATA_PREFIX)) // 4) * 3


def snapshot_image(path, output):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Missing private wallpaper artwork assets/private/wallpaper-scene-q-v3.png; retain the local project asset when updating.')
    digest = hashlib.sha256()
    header = b''
    size = 0
    with path.open('rb') as source:
        while chunk := source.read(48 * 1024):
            size += len(chunk)
            header += chunk[:max(0, 26 - len(header))]
            digest.update(chunk)
            if size <= MAX_IMAGE_BYTES:
                output.write(chunk)
    if (len(header) < 26 or header[:8] != b'\x89PNG\r\n\x1a\n'
            or header[12:16] != b'IHDR' or header[24] != 8 or header[25] not in (2, 6)):
        raise RuntimeError('Wallpaper requires the private 8-bit RGB/RGBA PNG Q-style Azhou panorama.')
    width, height = struct.unpack('>II', header[16:24])
    if not (1024 <= width <= 8192 and 512 <= height <= 8192 and 1.4 <= width / height <= 2.5):
        raise RuntimeError('Wallpaper artwork must be a landscape PNG, 1024–8192px wide, 512–8192px high, aspect 1.4–2.5.')
    if len(DATA_PREFIX) + 4 * ((size + 2) // 3) > 16 * 1024 * 1024:
        raise RuntimeError('Wallpaper image exceeds the renderer local-image limit.')
    return digest.hexdigest(), width, height, header[24], header[25]


def as_classic_module(source, exported, local, error_message):
    if source.count(exported) != 1:
        raise RuntimeError(error_message)
    text = source.replace(exported, local, 1)
    if re.search(r'^\s*import\s', text, re.MULTILINE):
        raise RuntimeError(error_message)
    return text


def write_script(path, renderer, adapter, image, payload):
    marker = '__AZHOU_IMAGE_STREAM__'
    data = dict(payload)
    data['image'] = marker
    encoded = json.dumps(data, ensure_ascii=False)
    before, after = encoded.split(json.dumps(marker), 1)
    digest = hashlib.sha256()
    with path.open('wb') as stream:
        def emit(text):
            chunk = text.encode('utf-8') if isinstance(text, str) else text
            stream.write(chunk)
            digest.update(chunk)

        emit('(async () => {\n' + renderer + '\n')
        if adapter is not None:
            emit(adapter + '\nconst pageAdapter = createZCodePageAdapter(globalThis);\nconst wallpaperPayload = ')
        else:
            emit('return await installRenderer(')
        emit(before + '"' + DATA_PREFIX)
        image.seek(0)
        carry = b''
        while chunk := image.read(48 * 1024):
            data_chunk = carry + chunk
            full = len(data_chunk) - len(data_chunk) % 3
            emit(base64.b64encode(data_chunk[:full]))
            carry = data_chunk[full:]
        emit(base64.b64encode(carry))
        emit('"' + after)
        if adapter is None:
            emit(');\n})()\n')
        else:
            emit(';\nwallpaperPayload.pageAdapter = pageAdapter;\nreturn await installRenderer(wallpaperPayload);\n})()\n')
    return digest.hexdigest()


def package(bundle, *, host='codex'):
    if host not in ('codex', 'zcode'):
        raise RuntimeError('Unsupported wallpaper host.')
    helper = runpy.run_path(str(ROOT / 'tools/verify-artifacts.py'))
    helper['configure_build_host'](host)
    bundle = helper['staged_path'](bundle)
    theme = helper['load_theme_config'](ROOT)
    version = helper['VERSION']
    with tempfile.TemporaryFile(mode='w+b') as image:
        image_hash, width, height, depth, color = snapshot_image(ROOT / ASSET, image)
        renderer_text = (ROOT / 'wallpaper/renderer.js').read_text(encoding='utf-8')
        css = (ROOT / 'wallpaper/wallpaper.css').read_text(encoding='utf-8')
        renderer = as_classic_module(renderer_text, 'export async function installRenderer(',
                                     'async function installRenderer(', 'Wallpaper renderer must export one self-contained installRenderer function.')
        adapter = None
        adapter_hash = None
        if host == 'zcode':
            raw = (ROOT / 'extension/hosts/zcode.mjs').read_bytes()
            adapter_hash = hashlib.sha256(raw).hexdigest()
            spec = importlib.util.spec_from_file_location('wallpaper_startup_builder', ROOT / 'tools/build-startup.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            adapter = builder._module_function(raw.decode('utf-8'), 'export function createZCodePageAdapter(',
                                               'function createZCodePageAdapter(', 'ZCode page adapter')
        payload = {'version': version, 'image': '', 'imageSHA256': image_hash,
                   'css': css, 'strength': theme['wallpaper']['strength']}
        output = bundle / 'Contents/Resources/wallpaper'
        output.mkdir(parents=True, exist_ok=True)
        script_hash = write_script(output / 'install.js', renderer, adapter, image, payload)
    manifest = {
        'version': version, 'imageSHA256': image_hash, 'asset': ASSET,
        'width': width, 'height': height, 'alpha': color == 6,
        'bitDepth': depth, 'colorType': color, 'displayMode': 'cover',
        'rendererSHA256': hashlib.sha256(renderer_text.encode('utf-8')).hexdigest(),
        'cssSHA256': hashlib.sha256(css.encode('utf-8')).hexdigest(),
        'scriptSHA256': script_hash,
        'scope': ('ZCode' if host == 'zcode' else 'Codex') + ' renderer only; no desktop image or official bundle writes',
    }
    if host == 'zcode':
        manifest.update({'targetHost': 'zcode', 'adapterSHA256': adapter_hash})
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Packaged private Azhou wallpaper:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--host', choices=('codex', 'zcode'), default='codex')
    args = parser.parse_args()
    package(args.bundle, host=args.host)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Package the project-private Azhou derivative for a one-shot renderer wallpaper.

The generated script contains private artwork and belongs only in an ignored
build payload or local preview directory, never in the tracked source tree.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def package(bundle):
    spec = importlib.util.spec_from_file_location('azhou_artifacts', ROOT / 'tools/verify-artifacts.py')
    artifacts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(artifacts)
    bundle = artifacts.staged_path(bundle)
    theme = artifacts.load_theme_config(ROOT)
    source = ROOT / 'assets/private/wallpaper-scene-q-v3.png'
    if source.is_symlink() or not source.is_file():
        raise RuntimeError('Missing private wallpaper artwork assets/private/wallpaper-scene-q-v3.png; retain the local project asset when updating.')
    data = source.read_bytes()
    if (len(data) < 26 or data[:8] != b'\x89PNG\r\n\x1a\n'
            or data[12:16] != b'IHDR'
            or data[24] != 8 or data[25] not in (2, 6)):
        raise RuntimeError('Wallpaper requires the private 8-bit RGB/RGBA PNG Q-style Azhou panorama.')
    width, height = struct.unpack('>II', data[16:24])
    if not (1024 <= width <= 8192 and 512 <= height <= 8192 and 1.4 <= width / height <= 2.5):
        raise RuntimeError('Wallpaper artwork must be a landscape PNG, 1024–8192px wide, 512–8192px high, aspect 1.4–2.5.')
    if ((len(data) + 2) // 3) * 4 + 22 > 16 * 1024 * 1024:
        raise RuntimeError('Wallpaper image exceeds the renderer local-image limit.')
    renderer = (ROOT / 'wallpaper/renderer.js').read_text()
    prefix = 'export async function installRenderer('
    if renderer.count(prefix) != 1 or re.search(r'^\s*import\s', renderer, re.M):
        raise RuntimeError('Wallpaper renderer must export one self-contained installRenderer function.')
    css = (ROOT / 'wallpaper/wallpaper.css').read_text()
    payload = {'version': artifacts.VERSION,
               'image': 'data:image/png;base64,' + base64.b64encode(data).decode('ascii'),
               'imageSHA256': hashlib.sha256(data).hexdigest(), 'css': css,
               'strength': theme['wallpaper']['strength']}
    expression = '(async () => {\n' + renderer.replace(prefix, 'async function installRenderer(', 1)
    expression += '\nreturn await installRenderer(' + json.dumps(payload, ensure_ascii=False) + ');\n})()\n'
    target = bundle / 'Contents/Resources/wallpaper'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'install.js').write_text(expression, encoding='utf-8')
    manifest = {'version': artifacts.VERSION, 'imageSHA256': payload['imageSHA256'],
                'asset': 'assets/private/wallpaper-scene-q-v3.png',
                'width': width, 'height': height, 'alpha': data[25] == 6,
                'bitDepth': data[24], 'colorType': data[25], 'displayMode': 'cover',
                'rendererSHA256': hashlib.sha256(renderer.encode()).hexdigest(),
                'cssSHA256': hashlib.sha256(css.encode()).hexdigest(),
                'scriptSHA256': hashlib.sha256(expression.encode()).hexdigest(),
                'scope': 'Codex renderer only; no desktop image or official bundle writes'}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Packaged private Azhou wallpaper:', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    package(parser.parse_args().bundle)

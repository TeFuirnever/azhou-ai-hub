#!/usr/bin/env python3
"""Package the resolved Azhou wallpaper (local overlay first) into a staged payload."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import stat
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSET_NAME = 'wallpaper-scene-q-v3.png'
DATA_PREFIX = 'data:image/png;base64,'
MAX_IMAGE_BYTES = ((16 * 1024 * 1024 - len(DATA_PREFIX)) // 4) * 3


def snapshot_image(path, output):
    missing = 'Missing Azhou wallpaper artwork wallpaper-scene-q-v3.png in assets/private/ or assets/azhou/.'
    limit = 'Wallpaper image exceeds the renderer local-image limit.'
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    try:
        before = path.lstat()
    except OSError as error:
        raise RuntimeError(missing) from error
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(missing)
    if before.st_size > MAX_IMAGE_BYTES:
        raise RuntimeError(limit)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise RuntimeError('Wallpaper source could not be safely opened.') from error
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise RuntimeError('Wallpaper source changed before capture.')
        digest, header, size = hashlib.sha256(), bytearray(), 0
        while True:
            try:
                chunk = os.read(fd, min(48 * 1024, MAX_IMAGE_BYTES + 1 - size))
            except InterruptedError:
                continue
            except OSError as error:
                raise RuntimeError('Wallpaper source could not be read.') from error
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_IMAGE_BYTES:
                raise RuntimeError(limit)
            header.extend(chunk[:max(0, 26 - len(header))])
            digest.update(chunk)
            output.write(chunk)
        after = os.fstat(fd)
        try:
            current = path.lstat()
        except OSError as error:
            raise RuntimeError('Wallpaper source changed during capture.') from error
        if (not stat.S_ISREG(current.st_mode) or identity(before) != identity(after)
                or identity(after) != identity(current) or size != after.st_size):
            raise RuntimeError('Wallpaper source changed during capture.')
    finally:
        os.close(fd)
    if (len(header) < 26 or header[:8] != b'\x89PNG\r\n\x1a\n'
            or header[12:16] != b'IHDR' or header[24] != 8 or header[25] not in (2, 6)):
        raise RuntimeError('Wallpaper requires an 8-bit RGB/RGBA PNG Q-style Azhou panorama.')
    width, height = struct.unpack('>II', header[16:24])
    if not (1024 <= width <= 8192 and 512 <= height <= 8192 and 1.4 <= width / height <= 2.5):
        raise RuntimeError('Wallpaper artwork must be a landscape PNG, 1024–8192px wide, 512–8192px high, aspect 1.4–2.5.')
    return digest.hexdigest(), width, height, header[24], header[25]


def as_classic_module(source, exported, local, error_message):
    if source.count(exported) != 1:
        raise RuntimeError(error_message)
    text = source.replace(exported, local, 1)
    if re.search(r'^\s*import\s', text, re.MULTILINE):
        raise RuntimeError(error_message)
    return text


def write_script(path, renderer, image, payload):
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
        emit(');\n})()\n')
    return digest.hexdigest()


def package(bundle):
    helper = runpy.run_path(str(ROOT / 'tools/verify-artifacts.py'))
    bundle = helper['staged_path'](bundle)
    theme = helper['load_theme_config'](ROOT)
    version = helper['VERSION']
    asset = helper['asset_key'](ROOT, ASSET_NAME)
    with tempfile.TemporaryFile(mode='w+b') as image:
        image_hash, width, height, depth, color = snapshot_image(ROOT / asset, image)
        renderer_text = (ROOT / 'wallpaper/renderer.js').read_text(encoding='utf-8')
        css = (ROOT / 'wallpaper/wallpaper.css').read_text(encoding='utf-8')
        renderer = as_classic_module(renderer_text, 'export async function installRenderer(',
                                     'async function installRenderer(', 'Wallpaper renderer must export one self-contained installRenderer function.')
        payload = {'version': version, 'image': '', 'imageSHA256': image_hash,
                   'css': css, 'strength': theme['wallpaper']['strength']}
        output = bundle / 'Contents/Resources/wallpaper'
        output.mkdir(parents=True, exist_ok=True)
        script_hash = write_script(output / 'install.js', renderer, image, payload)
    manifest = {
        'version': version, 'imageSHA256': image_hash, 'asset': asset,
        'width': width, 'height': height, 'alpha': color == 6,
        'bitDepth': depth, 'colorType': color, 'displayMode': 'cover',
        'rendererSHA256': hashlib.sha256(renderer_text.encode('utf-8')).hexdigest(),
        'cssSHA256': hashlib.sha256(css.encode('utf-8')).hexdigest(),
        'scriptSHA256': script_hash,
        'scope': 'Codex renderer only; no desktop image or official bundle writes',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Packaged Azhou wallpaper:', asset, '->', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args()
    package(args.bundle)


if __name__ == '__main__':
    main()

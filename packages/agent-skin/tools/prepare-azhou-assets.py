#!/usr/bin/env python3
"""Prepare the local startup image from an isolated source snapshot."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile


MAX_SOURCE_BYTES = 64 * 1024 * 1024


def capture(source, snapshot):
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('The source must be a regular file.')
    if before.st_size > MAX_SOURCE_BYTES:
        raise ValueError('The source must not exceed 64 MiB.')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open(source, flags)
    try:
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise ValueError('The source changed before it could be captured.')
        header, digest, total = bytearray(), hashlib.sha256(), 0
        while True:
            try:
                data = os.read(fd, min(48 * 1024, MAX_SOURCE_BYTES + 1 - total))
            except InterruptedError:
                continue
            if not data:
                break
            total += len(data)
            if total > MAX_SOURCE_BYTES:
                raise ValueError('The source must not exceed 64 MiB.')
            if len(header) < 26:
                header.extend(data[:26 - len(header)])
            digest.update(data)
            snapshot.write(data)
        after = os.fstat(fd)
        current = source.lstat()
        if (not stat.S_ISREG(current.st_mode) or identity(before) != identity(after)
                or identity(after) != identity(current) or total != after.st_size):
            raise ValueError('The source changed while it was being captured.')
        return bytes(header), digest.hexdigest()
    finally:
        os.close(fd)


def emit_scene(snapshot, destination):
    snapshot.seek(0)
    remainder = b''
    with destination.open('wb') as output:
        output.write(b'window.AZHOU_WORKING_IMAGE = "data:image/png;base64,')
        while chunk := snapshot.read(48 * 1024):
            payload = remainder + chunk
            whole = len(payload) - len(payload) % 3
            output.write(base64.b64encode(payload[:whole]))
            remainder = payload[whole:]
        output.write(base64.b64encode(remainder))
        output.write(b'";\n')


def main():
    package = Path(__file__).resolve().parent.parent
    library = Path(os.environ.get('AZHOU_ASSET_ROOT', str(Path.home() / 'Desktop/oh-my-ai/IP/azhou')))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=library / 'assets/characters/azhou-chibi-pet/v1.0.0/images/04-working.png')
    source = parser.parse_args().source.expanduser().resolve(strict=True)
    destination = package / 'assets/private'
    if source == destination / 'working.png':
        parser.error('Use the original approved source file, not the output copy.')

    with tempfile.TemporaryFile(mode='w+b') as snapshot:
        try:
            header, digest = capture(source, snapshot)
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot capture source: {exc}')
        if len(header) < 26 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
            parser.error('The approved working pose must be a PNG.')
        width, height, _, color = struct.unpack('>IIBB', header[16:26])
        if (width, height, color) != (1254, 1254, 6):
            parser.error('This scene is registered to the 1254 × 1254 RGBA working pose; another image requires a new visual review.')
        ignored = subprocess.run(['git', 'check-ignore', '-q', '--', 'assets/private/working.png'], cwd=package)
        if ignored.returncode:
            parser.error('assets/private/ must be ignored by Git before preparing private artwork.')
        if subprocess.check_output(['git', 'ls-files', '--', 'assets/private'], cwd=package).strip():
            parser.error('Private assets are tracked. Remove them from the index before continuing.')

        destination.mkdir(parents=True, exist_ok=True)
        snapshot.seek(0)
        with (destination / 'working.png').open('wb') as image:
            shutil.copyfileobj(snapshot, image, length=48 * 1024)
        emit_scene(snapshot, destination / 'scene.js')
    provenance = {
        'source': str(source), 'sha256': digest, 'width': width, 'height': height,
        'alpha': True, 'copiedByteForByte': True,
        'purpose': 'Local-only startup scene. Do not commit or publish.',
    }
    (destination / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    print('Prepared private working pose:', destination)
    print('Source SHA-256:', digest)


if __name__ == '__main__':
    main()

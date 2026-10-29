#!/usr/bin/env python3
"""Copy the approved working pose locally, without changing the source library.
The output is private and must stay outside Git. No image resampling is performed.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

project = Path(__file__).resolve().parent.parent
root = Path(os.environ.get('AZHOU_ASSET_ROOT', str(Path.home() / 'Desktop/oh-my-ai/IP/azhou')))
default = root / 'assets/characters/azhou-chibi-pet/v1.0.0/images/04-working.png'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=default)
args = parser.parse_args()
source = args.source.expanduser().resolve(strict=True)
output = project / 'assets/private'
if source == output / 'working.png':
    parser.error('Use the original approved source file, not the output copy.')
data = source.read_bytes()
if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
    parser.error('The approved working pose must be a PNG.')
width, height, depth, color = struct.unpack('>IIBB', data[16:26])
if width != 1254 or height != 1254 or color != 6:
    parser.error('This scene is registered to the 1254 × 1254 RGBA working pose; another image requires a new visual review.')
ignored = subprocess.run(['git', 'check-ignore', '-q', '--', 'assets/private/working.png'], cwd=project)
if ignored.returncode != 0:
    parser.error('assets/private/ must be ignored by Git before preparing private artwork.')
tracked = subprocess.check_output(['git', 'ls-files', '--', 'assets/private'], cwd=project).strip()
if tracked:
    parser.error('Private assets are tracked. Remove them from the index before continuing.')
output.mkdir(parents=True, exist_ok=True)
(output / 'working.png').write_bytes(data)
(output / 'scene.js').write_text('window.AZHOU_WORKING_IMAGE = "data:image/png;base64,' + base64.b64encode(data).decode('ascii') + '";\n')
manifest = {'source': str(source), 'sha256': hashlib.sha256(data).hexdigest(), 'width': width, 'height': height, 'alpha': True, 'copiedByteForByte': True, 'purpose': 'Local-only startup scene. Do not commit or publish.'}
(output / 'provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print('Prepared private working pose:', output)
print('Source SHA-256:', manifest['sha256'])

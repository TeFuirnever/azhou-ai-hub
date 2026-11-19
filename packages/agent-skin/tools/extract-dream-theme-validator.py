#!/usr/bin/env python3
"""Rebuild the pure official-theme contract from its pinned MIT source."""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = '8f249d726367c383d8c5894890e2b6d1c3b56a7282d7441a80cfb6470955b5f8'
LICENSE_SHA256 = '18f8478d0f9efd45307e5f17790194593b116658145c758ced3166398eb05b21'
SPANS = [
    ('const BACKGROUND_MEDIA =', 'const PAYLOAD_MEDIA ='),
    ('const THEME_REQUIRED =', 'const SEMVER_PATTERN ='),
    ('const THEME_ID_PATTERN =', 'const PUBLISHER_ID_PATTERN ='),
    ('const CONTROL_PATTERN =', 'const PROVENANCE_CONTROL_PATTERN ='),
    ('const COLOR_PATTERN =', 'const RFC3339_PATTERN ='),
    ('function fail(', 'function parseArguments('),
    ('function isObject(', 'export function codePointLength('),
    ('export function codePointLength(', 'export function normalizeThemeText('),
    ('function assertString(', 'function parseSemver('),
    ('function validateOfficialTheme(', 'function validateManifest('),
]
HEADER = '// Derived from Codex-Dream-Skin 6fc42df48a6a5365011f55cc349e20c038e56d1d.\n// Copyright (c) 2026 Codex Dream Skin Studio contributors. MIT, see dream-theme-validator.LICENSE.\n'


def extract(source, license_bytes):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256 or hashlib.sha256(license_bytes).hexdigest() != LICENSE_SHA256:
        raise ValueError('Pinned source or MIT notice does not match')
    text = source.decode('utf-8')
    pieces = [text[text.index(start):text.index(end, text.index(start))].rstrip() for start, end in SPANS]
    return (HEADER + '\n\n'.join(pieces) + '\n\nexport { validateOfficialTheme };\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--license', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.write_bytes(extract(args.source.read_bytes(), args.license.read_bytes()))


if __name__ == '__main__':
    main()

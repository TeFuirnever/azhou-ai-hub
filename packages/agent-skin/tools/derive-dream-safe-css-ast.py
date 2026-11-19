#!/usr/bin/env python3
"""Expose the pinned pristine SafeCSS AST with one reproducible export-only patch."""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = '98a626655a4167ba0bbbff5eab96e78de7a5a74371e4a4ff6d8ac15211e5b24e'
OUTPUT_SHA256 = 'ed0657f061e7f500233b8723683b3e28b236721b8f6fe13af24f8ac796d8cc37'
LICENSE_SHA256 = '18f8478d0f9efd45307e5f17790194593b116658145c758ced3166398eb05b21'
PATCH = b'\nexport { parseSafeCss as parseSafeCssAst };\n'
VENDOR = Path(__file__).resolve().parents[1] / 'vendor'


def derive(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Pinned pristine SafeCSS source does not match')
    return source + PATCH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = VENDOR / 'dream-safe-css-ast.mjs'
    if hashlib.sha256((VENDOR / 'dream-safe-css.LICENSE').read_bytes()).hexdigest() != LICENSE_SHA256:
        raise ValueError('Pinned MIT notice does not match')
    expected = derive((VENDOR / 'dream-safe-css-validator.mjs').read_bytes())
    if hashlib.sha256(expected).hexdigest() != OUTPUT_SHA256:
        raise ValueError('Fixed AST derivation hash does not match')
    if args.check:
        if output.read_bytes() != expected:
            raise ValueError('Derived SafeCSS AST is stale; run derive-dream-safe-css-ast.py')
    else:
        output.write_bytes(expected)


if __name__ == '__main__':
    main()

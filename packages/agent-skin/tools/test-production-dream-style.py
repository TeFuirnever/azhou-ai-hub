#!/usr/bin/env python3
"""Registered source-capsule, AST derivation and total-mapping contract tests."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DreamStyleTests(unittest.TestCase):
    def test_source_bound_generator_rejects_drift(self):
        spec = importlib.util.spec_from_file_location('dream_ast_generator', ROOT / 'tools/derive-dream-safe-css-ast.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = (ROOT / 'vendor/dream-safe-css-validator.mjs').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), module.SOURCE_SHA256)
        self.assertEqual(module.derive(source), (ROOT / 'vendor/dream-safe-css-ast.mjs').read_bytes())
        with self.assertRaises(ValueError):
            module.derive(source + b'\n')

    def test_javascript_source_contracts_and_pristine_corpus(self):
        for arguments in [
            ['tools/dream-theme-style.test.mjs'],
            ['tools/dream-capsule.test.mjs'],
            ['tools/dream-safe-css.test.mjs', (ROOT / 'vendor/dream-safe-css-ast.mjs').as_uri()],
        ]:
            with self.subTest(arguments=arguments):
                result = subprocess.run(['node', *arguments], cwd=ROOT, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode())


if __name__ == '__main__':
    unittest.main()

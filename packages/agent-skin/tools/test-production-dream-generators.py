#!/usr/bin/env python3
"""Exercise reproducible Dream generator boundaries without touching canonical files."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DreamGeneratorTests(unittest.TestCase):
    def test_ast_cli_write_check_and_integrity_failures(self):
        module = load('derive-dream-safe-css-ast')
        with tempfile.TemporaryDirectory() as temporary:
            vendor = Path(temporary)
            for name in ('dream-safe-css-validator.mjs', 'dream-safe-css.LICENSE'):
                shutil.copyfile(ROOT / 'vendor' / name, vendor / name)
            with mock.patch.object(module, 'VENDOR', vendor), mock.patch('sys.argv', ['derive']):
                module.main()
                output = vendor / 'dream-safe-css-ast.mjs'
                self.assertEqual(output.read_bytes(), (ROOT / 'vendor' / output.name).read_bytes())
                with mock.patch('sys.argv', ['derive', '--check']):
                    module.main()
                    output.write_bytes(b'stale')
                    with self.assertRaisesRegex(ValueError, 'stale'):
                        module.main()
                with mock.patch.object(module, 'OUTPUT_SHA256', '0' * 64):
                    with self.assertRaisesRegex(ValueError, 'derivation hash'):
                        module.main()
                (vendor / 'dream-safe-css.LICENSE').write_bytes(b'changed notice')
                with self.assertRaisesRegex(ValueError, 'MIT notice'):
                    module.main()

    def test_classic_write_verify_symlink_and_module_boundaries(self):
        module = load('build-startup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            domain = root / 'azhou-theme-snapshot.mjs'
            shutil.copyfile(ROOT / domain.name, domain)
            output = module.update_dream_theme_style(root)
            self.assertEqual(output.read_bytes(), (ROOT / 'dream-theme-style.js').read_bytes())
            module.verify_dream_theme_style(root)
            output.write_bytes(b'stale')
            with self.assertRaisesRegex(RuntimeError, 'stale'):
                module.verify_dream_theme_style(root)
            output.unlink()
            target = root / 'protected'; target.write_bytes(b'keep')
            output.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, 'symlink'):
                module.update_dream_theme_style(root)
            self.assertEqual(target.read_bytes(), b'keep')
            output.unlink()
            original = domain.read_text()
            domain.write_text(original.replace('export function validateThemeSnapshot(', 'export function changed(', 1))
            with self.assertRaisesRegex(RuntimeError, 'export changed'):
                module.dream_theme_style_source(root)
            domain.write_text(original + "\nimport extra from './elsewhere.mjs';\n")
            with self.assertRaisesRegex(RuntimeError, 'module linkage'):
                module.dream_theme_style_source(root)
            domain.write_text(original)
            self.assertEqual(module.dream_theme_style_source(root), (ROOT / 'dream-theme-style.js').read_text(encoding='utf-8'))
            with mock.patch('sys.argv', ['build', '--update-dream-theme-style']), mock.patch.object(
                    module, 'update_dream_theme_style', return_value=ROOT / 'dream-theme-style.js') as update:
                self.assertEqual(module.main(), 0)
                update.assert_called_once_with()

    def test_extract_cli_passes_exact_bytes_and_writes_only_requested_output(self):
        module = load('extract-dream-theme-validator')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; notice = root / 'notice'; output = root / 'output'
            source.write_bytes(b'source fixture'); notice.write_bytes(b'notice fixture')
            args = ['extract', '--source', str(source), '--license', str(notice), '--output', str(output)]
            # The pinned-byte extractor itself is tested separately; this tests CLI transport.
            with mock.patch('sys.argv', args), mock.patch.object(module, 'extract', return_value=b'derived') as extract:
                module.main()
                extract.assert_called_once_with(b'source fixture', b'notice fixture')
            self.assertEqual(output.read_bytes(), b'derived')
            self.assertEqual(source.read_bytes(), b'source fixture')
            self.assertEqual(notice.read_bytes(), b'notice fixture')

    def test_startup_rejects_unsupported_owner_and_excess_contour_points(self):
        module = load('build-startup')
        with self.assertRaisesRegex(RuntimeError, 'playback owner'):
            module._build_script(ROOT, {}, '', None, host='dsh', playback_owner='native')
        with self.assertRaisesRegex(RuntimeError, '300,000'):
            module._validate_contours([[[0, 0], [1, 1]] * 150001])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Behavioral contract for the P08 read-only ZIP subset."""
import importlib.util
import json
from pathlib import Path
import stat
import struct
import zlib
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

TOOL = Path(__file__).with_name('theme-package-preflight.py')


class ThemePackagePreflightTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('theme_preflight', TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'theme.zip'
        self.files = {
            'theme.json': json.dumps({'schemaVersion': 1, 'id': 'demo', 'name': 'Demo', 'image': 'background.png'}).encode(),
            'theme.css': b'[data-dream-part="workspace"] { color: red; }',
            'background.png': b'\x89PNG\r\n\x1a\nnot-a-decoded-image',
        }

    def archive(self, files=None, compression=zipfile.ZIP_STORED):
        with zipfile.ZipFile(self.path, 'w', compression=compression) as archive:
            for name, data in (self.files if files is None else files).items():
                archive.writestr(name, data)
        return self.tool.preflight(self.path)

    def assert_blocked_structure(self, result, reason):
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['structure']['status'], 'blocked')
        self.assertIn(reason, result['structure']['reasons'])

    def test_structure_pass_never_implies_importable(self):
        result = self.archive()
        self.assertEqual(result['structure']['status'], 'passed')
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('image_decode_unverified', result['resources']['reasons'])
        self.assertEqual(result['reference_css']['status'], 'blocked')
        self.assertEqual(result['hub_mapping']['status'], 'blocked')
        self.assertEqual(len(result['archive_sha256']), 64)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['theme.zip'])

    def test_deflated_subset(self):
        self.assertEqual(self.archive(compression=zipfile.ZIP_DEFLATED)['structure']['status'], 'passed')

    def test_missing_empty_and_unknown_entries(self):
        for name in self.files:
            with self.subTest(name=name):
                files = dict(self.files)
                del files[name]
                self.assert_blocked_structure(self.archive(files), 'required_files')
                files[name] = b''
                self.assert_blocked_structure(self.archive(files), 'entry_size')
        self.assert_blocked_structure(self.archive({**self.files, 'extra.txt': b'x'}), 'unknown_entry')

    def test_unsafe_paths(self):
        for name in ['../escape', '/escape', 'C:escape', 'a\\b', 'a/b', './theme.json']:
            with self.subTest(name=name):
                self.assert_blocked_structure(self.archive({**self.files, name: b'x'}), 'unsafe_path')

    def test_duplicate_paths(self):
        self.archive()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(self.path, 'a') as archive:
                archive.writestr('theme.json', self.files['theme.json'])
        self.assert_blocked_structure(self.tool.preflight(self.path), 'duplicate_path')
        self.assert_blocked_structure(self.archive({**self.files, 'THEME.JSON': b'x'}), 'duplicate_path')

    def test_symlink(self):
        self.archive()
        with zipfile.ZipFile(self.path, 'a') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b'theme.json')
        self.assert_blocked_structure(self.tool.preflight(self.path), 'entry_type')

    def test_manifest_is_explicitly_unsupported(self):
        self.assert_blocked_structure(self.archive({**self.files, 'manifest.json': b'{}'}), 'studio_format_unsupported')

    def test_theme_schema_and_duplicate_keys(self):
        for data in [b'{"image":"a","image":"background.png"}', b'[]', b'{"schemaVersion":NaN}', b'\xff', b'{}']:
            with self.subTest(data=data):
                self.assert_blocked_structure(self.archive({**self.files, 'theme.json': data}), 'theme_schema')
        theme = json.loads(self.files['theme.json'])
        for key, value in [('schemaVersion', True), ('id', '../bad'), ('image', 'missing.png'), ('optional', 1)]:
            with self.subTest(key=key):
                self.assert_blocked_structure(self.archive({**self.files, 'theme.json': json.dumps({**theme, key: value}).encode()}), 'theme_schema')

    def test_size_budget_and_compressed_bomb(self):
        for name, limit in [('theme.json', 1048576), ('theme.css', 262144), ('background.png', 10485760)]:
            with self.subTest(name=name):
                self.assert_blocked_structure(self.archive({**self.files, name: b'x' * (limit + 1)}, zipfile.ZIP_DEFLATED), 'entry_size')

    def test_magic_mismatch_and_nested_archive(self):
        result = self.archive({**self.files, 'background.png': b'not PNG'})
        self.assertIn('image_magic_mismatch', result['resources']['reasons'])
        self.assert_blocked_structure(self.archive({**self.files, 'background.png': b'PK\x03\x04nested'}), 'nested_archive')

    def test_nul_name_on_wire(self):
        self.archive()
        self.path.write_bytes(self.path.read_bytes().replace(b'theme.css', b'theme\x00css'))
        self.assert_blocked_structure(self.tool.preflight(self.path), 'unsafe_path')

    def test_hidden_expanded_bytes_are_rejected(self):
        self.archive(compression=zipfile.ZIP_DEFLATED)
        data = bytearray(self.path.read_bytes())
        with zipfile.ZipFile(self.path) as archive:
            info = archive.getinfo('theme.css')
        truncated = self.files['theme.css'][:-1]
        for offset, signature in [(info.header_offset, b'PK\x03\x04')]:
            self.assertEqual(data[offset:offset + 4], signature)
            struct.pack_into('<I', data, offset + 14, zlib.crc32(truncated))
            struct.pack_into('<I', data, offset + 22, len(truncated))
        cursor = data.find(b'PK\x01\x02')
        while cursor >= 0:
            length = struct.unpack_from('<H', data, cursor + 28)[0]
            if data[cursor + 46:cursor + 46 + length] == b'theme.css':
                struct.pack_into('<I', data, cursor + 16, zlib.crc32(truncated))
                struct.pack_into('<I', data, cursor + 24, len(truncated))
                break
            cursor = data.find(b'PK\x01\x02', cursor + 4)
        self.path.write_bytes(data)
        self.assert_blocked_structure(self.tool.preflight(self.path), 'zip_integrity')

    def test_nonzero_entry_disk_is_rejected(self):
        self.archive()
        data = bytearray(self.path.read_bytes())
        central = data.find(b'PK\x01\x02')
        self.assertGreaterEqual(central, 0)
        struct.pack_into('<H', data, central + 34, 1)
        self.path.write_bytes(data)
        self.assert_blocked_structure(self.tool.preflight(self.path), 'zip_metadata_unsupported')

    def test_crc_corruption(self):
        self.archive()
        data = self.path.read_bytes().replace(self.files['theme.css'], b'x' * len(self.files['theme.css']))
        self.path.write_bytes(data)
        self.assert_blocked_structure(self.tool.preflight(self.path), 'zip_integrity')

    def test_non_zip_extension_and_input_symlink(self):
        self.path.write_bytes(b'not zip')
        self.assert_blocked_structure(self.tool.preflight(self.path), 'zip_integrity')
        alternate = self.root / 'theme.dreamskin'
        alternate.write_bytes(b'PK\x03\x04')
        self.assert_blocked_structure(self.tool.preflight(alternate), 'input_type')
        self.path.unlink()
        self.path.symlink_to(alternate)
        self.assert_blocked_structure(self.tool.preflight(self.path), 'input_type')

    def test_exact_file_limits_are_not_exceeded(self):
        result = self.archive({**self.files, 'theme.css': b' ' * 262144,
                               'background.png': b'\x89PNG\r\n\x1a\n' + b'x' * (10485760 - 8)},
                              zipfile.ZIP_DEFLATED)
        self.assertEqual(result['structure']['status'], 'passed')
        self.assertIn('css_utf8_or_content_invalid', result['resources']['reasons'])

    def test_metadata_and_entry_count_are_blocked(self):
        self.archive()
        with zipfile.ZipFile(self.path, 'a') as archive:
            archive.comment = b'comment'
        self.assert_blocked_structure(self.tool.preflight(self.path), 'zip_integrity')
        self.assert_blocked_structure(self.archive({f'x{i}': b'x' for i in range(33)}), 'entry_count')
        self.assert_blocked_structure(self.archive(compression=zipfile.ZIP_BZIP2), 'zip_metadata_unsupported')

    def test_archive_ceiling_before_parsing(self):
        with self.path.open('wb') as stream:
            stream.truncate(32 * 1024 * 1024 + 1)
        self.assert_blocked_structure(self.tool.preflight(self.path), 'archive_size')

    def test_input_digest_changes_and_invalid_css_stays_blocked(self):
        first = self.archive()
        second = self.archive({**self.files, 'theme.css': b'\xff'})
        self.assertNotEqual(first['archive_sha256'], second['archive_sha256'])
        self.assertIn('css_utf8_or_content_invalid', second['resources']['reasons'])
        self.assertEqual(second['reference_css']['status'], 'blocked')

    def test_cli_reports_block_without_private_paths(self):
        self.archive()
        result = subprocess.run([sys.executable, '-B', str(TOOL), str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'blocked')
        self.assertNotIn(str(self.root), result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

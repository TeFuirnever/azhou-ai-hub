#!/usr/bin/env python3
"""Behavioral contract for the P08 read-only ZIP subset."""
import base64
import builtins
import io
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
from unittest import mock
import warnings
import zipfile

FIXTURES = {'PNG': 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGMUt4xmYGBgYgADKAUADMEAsTl1AMYAAAAASUVORK5CYII=', 'JPEG': '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDzKiiivUPNP//Z', 'WEBP': 'UklGRjQAAABXRUJQVlA4ICgAAACQAQCdASoCAAMAAUAmJYgCdLoAA5gA/vjqf+j8y5OgP+K31AzSAAAA', 'APNG': 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAACGFjVEwAAAACAAAAAPONk3AAAAAaZmNUTAAAAAAAAAACAAAAAwAAAAAAAAAAAAAAAQAAYJrBuQAAABFJREFUeJxj/M8AAkxgEkYBABRAAQVQ1S44AAAAGmZjVEwAAAABAAAAAgAAAAMAAAAAAAAAAAAAAAEAAPvpK20AAAAYZmRBVAAAAAJ4nGNkYPjPwMDAxAAGUAoAEkIBBVsNz4sAAAAASUVORK5CYII=', 'ANIM_WEBP': 'UklGRsQAAABXRUJQVlA4WAoAAAACAAAAAQAAAgAAQU5JTQYAAAAAAAAAAABBTk1GSgAAAAAAAAAAAAEAAAIAAGQAAAJWUDggMgAAADABAJ0BKgIAAwABQCYloAADcAD+8ut///mwP/bz/wR6Af//0uD//pcH//S4P/SkAAAAQU5NRkYAAAAAAAAAAAABAAACAABkAAAAVlA4IC4AAAA0AQCdASoCAAMAAAAmJaAAA3AA/vtV4///S4P/+lwf/9Lg/9Lg//rV5Vesq6AA'}

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
        self.assertEqual(result['resources']['status'], 'blocked')
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


    def image_archive(self, fmt, payload=None, extension=None):
        extension = extension or {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[fmt]
        name = 'background' + extension
        theme = json.loads(self.files['theme.json'])
        theme['image'] = name
        return self.archive({'theme.json': json.dumps(theme).encode(),
                             'theme.css': self.files['theme.css'],
                             name: payload if payload is not None else base64.b64decode(FIXTURES[fmt])})

    def test_static_images_really_decode_but_aggregate_stays_blocked(self):
        from PIL import Image
        for fmt in ['PNG', 'JPEG', 'WEBP']:
            with self.subTest(format=fmt):
                original_open = Image.open
                loaded = []
                def observed_open(*args, **kwargs):
                    image = original_open(*args, **kwargs)
                    original_load = image.load
                    def load(*args, **kwargs):
                        loaded.append(image.format)
                        return original_load(*args, **kwargs)
                    image.load = load
                    return image
                with mock.patch.object(Image, 'open', side_effect=observed_open):
                    result = self.image_archive(fmt)
                self.assertIn(fmt, loaded)
                self.assertEqual(result['resources'], {'status': 'passed', 'reasons': []})
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['reference_css']['status'], 'blocked')
                self.assertEqual(result['hub_mapping']['status'], 'blocked')
        self.assertEqual(self.image_archive('JPEG', extension='.jpeg')['resources']['status'], 'passed')

    def test_corrupt_and_truncated_images_are_blocked(self):
        for fmt in ['PNG', 'JPEG', 'WEBP']:
            payload = base64.b64decode(FIXTURES[fmt])
            for bad in [payload[:len(payload)//2], payload[:-8]]:
                with self.subTest(format=fmt, length=len(bad)):
                    self.assertEqual(self.image_archive(fmt, bad)['resources']['status'], 'blocked')
        self.assertEqual(self.archive()['resources']['reasons'], ['image_decode_invalid'])

    def test_animation_is_outside_static_subset(self):
        for fmt, fixture in [('PNG', 'APNG'), ('WEBP', 'ANIM_WEBP')]:
            self.assertIn('image_animation_unsupported',
                          self.image_archive(fmt, base64.b64decode(FIXTURES[fixture]))['resources']['reasons'])

    def test_header_budget_rejects_before_decoder_open(self):
        from PIL import Image
        for fmt in ['PNG', 'JPEG', 'WEBP']:
            for width, height in [(0, 1), (1, 0), (16385, 1), (1, 16385), (10000, 5001)]:
                if fmt == 'WEBP' and (not width or not height or width > 16384 or height > 16384):
                    continue
                with self.subTest(format=fmt, width=width, height=height):
                    payload = self.dimension_fixture(fmt, width, height)
                    with mock.patch.object(Image, 'open', side_effect=AssertionError('decoder must not open')) as decoder:
                        result = self.image_archive(fmt, payload)
                    decoder.assert_not_called()
                    self.assertIn('image_dimensions_or_pixels', result['resources']['reasons'])

    def dimension_fixture(self, fmt, width, height):
        payload = bytearray(base64.b64decode(FIXTURES[fmt]))
        if fmt == 'PNG':
            struct.pack_into('>II', payload, 16, width, height)
            struct.pack_into('>I', payload, 29, zlib.crc32(payload[12:29]))
        elif fmt == 'JPEG':
            offset = payload.index(b'\xff\xc0')
            struct.pack_into('>HH', payload, offset + 5, height, width)
        else:
            bits = (width - 1) | ((height - 1) << 14)
            chunk = b'VP8L' + struct.pack('<I', 5) + b'\x2f' + struct.pack('<I', bits) + b'\x00'
            payload = b'RIFF' + struct.pack('<I', 4 + len(chunk)) + b'WEBP' + chunk
        return bytes(payload)

    def test_exact_dimension_and_pixel_boundaries_reach_decoder(self):
        from PIL import Image
        for width, height in [(1, 1), (16384, 1), (1, 16384), (10000, 5000)]:
            for fmt in ['PNG', 'JPEG', 'WEBP']:
                with self.subTest(format=fmt, width=width, height=height):
                    with mock.patch.object(Image, 'open', side_effect=OSError('sentinel')) as decoder:
                        result = self.image_archive(fmt, self.dimension_fixture(fmt, width, height))
                    decoder.assert_called_once()
                    self.assertEqual(result['resources']['reasons'], ['image_decode_invalid'])

    def test_webp_canvas_raster_disagreement_never_opens_decoder(self):
        from PIL import Image
        base = base64.b64decode(FIXTURES['WEBP'])
        canvas = b'VP8X' + struct.pack('<I', 10) + b'\x00' * 4 + b'\x00' * 6
        payload = b'RIFF' + struct.pack('<I', len(base) - 8 + len(canvas)) + b'WEBP' + canvas + base[12:]
        with mock.patch.object(Image, 'open') as decoder:
            result = self.image_archive('WEBP', payload)
        decoder.assert_not_called()
        self.assertIn('image_dimensions_mismatch', result['resources']['reasons'])

    def test_missing_decoder_and_webp_support_fail_closed_without_paths(self):
        original_import = builtins.__import__
        def missing(name, *args, **kwargs):
            if name == 'PIL' or name.startswith('PIL.'):
                raise ImportError('/private/decoder/install')
            return original_import(name, *args, **kwargs)
        with mock.patch('builtins.__import__', side_effect=missing):
            result = self.image_archive('PNG')
        self.assertEqual(result['resources']['reasons'], ['image_decoder_unavailable'])
        self.assertNotIn('/private/', json.dumps(result))
        from PIL import features
        with mock.patch.object(features, 'check', return_value=False):
            result = self.image_archive('WEBP')
        self.assertEqual(result['resources']['reasons'], ['image_decoder_unavailable'])

    def test_decoder_size_mismatch_and_extension_magic_disagreement(self):
        from PIL import Image
        with mock.patch.object(Image, 'open') as decoder:
            image = decoder.return_value.__enter__.return_value
            image.format = 'PNG'
            image.size = (3, 2)
            result = self.image_archive('PNG')
            image.load.assert_not_called()
        self.assertEqual(result['resources']['reasons'], ['image_dimensions_mismatch'])
        for fmt, extension in [('PNG', '.jpg'), ('JPEG', '.webp'), ('WEBP', '.png')]:
            self.assertEqual(self.image_archive(fmt, extension=extension)['resources']['reasons'], ['image_magic_mismatch'])

    def test_cli_missing_pillow_is_stably_blocked(self):
        self.image_archive('PNG')
        result = subprocess.run([sys.executable, '-S', '-B', str(TOOL), str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report['structure']['status'], 'passed')
        self.assertEqual(report['resources']['reasons'], ['image_decoder_unavailable'])
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    def test_decoder_warning_is_blocked_without_exposing_private_paths(self):
        from PIL import Image
        original = Image.open
        def warning_decoder(*args, **kwargs):
            warnings.warn('/private/decoder/image/path', UserWarning)
            return original(*args, **kwargs)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            with mock.patch.object(Image, 'open', side_effect=warning_decoder):
                result = self.image_archive('PNG')
        self.assertEqual(result['resources']['reasons'], ['image_decode_invalid'])
        self.assertEqual(captured, [])
        self.assertNotIn('/private/', json.dumps(result))

    def test_actual_decoder_format_must_match(self):
        from PIL import Image
        with mock.patch.object(Image, 'open') as decoder:
            decoder.return_value.__enter__.return_value.format = 'JPEG'
            result = self.image_archive('PNG')
        self.assertIn('image_format_mismatch', result['resources']['reasons'])

    def test_cli_reports_block_without_private_paths(self):
        self.archive()
        result = subprocess.run([sys.executable, '-B', str(TOOL), str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'blocked')
        self.assertNotIn(str(self.root), result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

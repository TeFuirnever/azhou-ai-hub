#!/usr/bin/env python3
"""Read-only, intentionally incomplete theme ZIP preflight. Never imports a theme."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import zipfile
import zlib

ARCHIVE_LIMIT = 32 * 1024 * 1024
EXPANDED_LIMIT = 64 * 1024 * 1024
ENTRY_LIMIT = 32
FILE_LIMITS = {'theme.json': 1048576, 'theme.css': 262144}
IMAGE_LIMIT = 10485760
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
NESTED_MAGIC = (b'PK\x03\x04', b'PK\x05\x06', b'7z\xbc\xaf\x27\x1c', b'Rar!', b'\x1f\x8b')


class Blocked(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Blocked(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'theme_schema')
        result[key] = value
    return result


def theme_definition(data, names):
    try:
        theme = json.loads(data.decode('utf-8'), object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError):
        raise Blocked('theme_schema') from None
    require(isinstance(theme, dict) and set(theme) == {'schemaVersion', 'id', 'name', 'image'}, 'theme_schema')
    require(type(theme['schemaVersion']) is int and theme['schemaVersion'] == 1, 'theme_schema')
    require(isinstance(theme['id'], str) and 3 <= len(theme['id']) <= 64
            and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', theme['id']), 'theme_schema')
    require(isinstance(theme['name'], str) and 1 <= len(theme['name']) <= 80
            and theme['name'].strip() and not re.search(r'[\x00-\x1f\x7f]', theme['name']), 'theme_schema')
    image = theme['image']
    require(isinstance(image, str) and image in names and Path(image).suffix in IMAGE_EXTENSIONS, 'theme_schema')
    require(set(names) == {'theme.json', 'theme.css', image}, 'required_files')
    return image


def read_archive(path):
    require(path.suffix.lower() == '.zip', 'input_type')
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise Blocked('input_type') from None
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'input_type')
        require(0 < before.st_size <= ARCHIVE_LIMIT, 'archive_size')
        data = stream.read(ARCHIVE_LIMIT + 1)
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and len(data) == before.st_size, 'input_changed')
        return data


def package_files(data):
    require(data.startswith(b'PK\x03\x04') and data[-22:-18] == b'PK\x05\x06', 'zip_integrity')
    disk, central_disk, count_disk, count, central_size, central_offset, comment_size = struct.unpack('<4H2IH', data[-18:])
    require(disk == central_disk == 0 and count_disk == count and comment_size == 0
            and central_offset + central_size == len(data) - 22, 'zip_integrity')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= ENTRY_LIMIT, 'entry_count')
        require(len(entries) == count and archive.start_dir == central_offset, 'zip_integrity')
        require(not archive.comment, 'zip_metadata_unsupported')
        names = set()
        for entry in entries:
            mode = entry.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not entry.is_dir()
                    and not (entry.external_attr & 0x410), 'entry_type')
            name = entry.orig_filename
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) is not None, 'unsafe_path')
            require(name.casefold() not in names, 'duplicate_path')
            names.add(name.casefold())
        require('manifest.json' not in names and 'manifest.sig' not in names, 'studio_format_unsupported')
        total = 0
        for entry in entries:
            name = entry.filename
            limit = FILE_LIMITS.get(name, IMAGE_LIMIT if Path(name).suffix in IMAGE_EXTENSIONS else 0)
            require(limit > 0, 'unknown_entry')
            require(0 < entry.file_size <= limit, 'entry_size')
            require(entry.volume == 0 and not entry.extra and not entry.comment and entry.extract_version <= 20
                    and entry.flag_bits & ~0x800 == 0
                    and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'zip_metadata_unsupported')
            total += entry.file_size
        require(total <= EXPANDED_LIMIT, 'expanded_size')
        require({'theme.json', 'theme.css'} <= {entry.filename for entry in entries}
                and len(entries) == 3, 'required_files')
        cursor = 0
        files = {}
        for entry in entries:
            require(entry.header_offset == cursor, 'zip_integrity')
            header = data[cursor:cursor + 30]
            require(len(header) == 30, 'zip_integrity')
            signature, version, flags, method, _, _, crc, compressed, expanded, name_len, extra_len = struct.unpack('<4s5H3I2H', header)
            require(signature == b'PK\x03\x04' and version == entry.extract_version
                    and flags == entry.flag_bits and method == entry.compress_type
                    and crc == entry.CRC and compressed == entry.compress_size
                    and expanded == entry.file_size and extra_len == 0, 'zip_integrity')
            start = cursor + 30 + name_len
            cursor = start + compressed
            require(cursor <= archive.start_dir, 'zip_integrity')
            require(data[start - name_len:start] == entry.filename.encode('ascii'), 'zip_integrity')
            compressed_data = data[start:cursor]
            if method == zipfile.ZIP_STORED:
                payload = compressed_data
            else:
                decoder = zlib.decompressobj(-15)
                payload = decoder.decompress(compressed_data, entry.file_size + 1)
                require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, 'zip_integrity')
            require(len(payload) == entry.file_size and zlib.crc32(payload) == entry.CRC, 'zip_integrity')
            require(not payload.startswith(NESTED_MAGIC), 'nested_archive')
            files[entry.filename] = payload
        require(cursor == archive.start_dir, 'zip_integrity')
        return files


def image_magic_matches(name, data):
    extension = Path(name).suffix
    if extension == '.png':
        return data.startswith(b'\x89PNG\r\n\x1a\n')
    if extension in {'.jpg', '.jpeg'}:
        return data.startswith(b'\xff\xd8\xff')
    return len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'


def preflight(path):
    report = {
        'schema': 'azhou-agent-skin.theme-package-preflight.v1',
        'status': 'blocked',
        'structure': {'status': 'blocked', 'reasons': []},
        'resources': {'status': 'blocked', 'reasons': ['not_inspected']},
        'reference_css': {'status': 'blocked', 'reasons': ['reference_policy_unverified']},
        'hub_mapping': {'status': 'blocked', 'reasons': ['hub_mapping_unverified']},
    }
    try:
        data = read_archive(Path(path))
        report['archive_sha256'] = hashlib.sha256(data).hexdigest()
        files = package_files(data)
        image = theme_definition(files['theme.json'], files)
        report['structure'] = {'status': 'passed', 'reasons': []}
        reasons = ['image_decode_unverified', 'image_dimensions_unverified', 'image_pixel_budget_unverified']
        if not image_magic_matches(image, files[image]):
            reasons.append('image_magic_mismatch')
        try:
            require(bool(files['theme.css'].decode('utf-8').strip()), 'css_empty')
        except (UnicodeError, Blocked):
            reasons.append('css_utf8_or_content_invalid')
        report['resources']['reasons'] = reasons
    except Blocked as error:
        report['structure']['reasons'] = [str(error)]
    except (OSError, ValueError, zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, struct.error, zlib.error):
        report['structure']['reasons'] = ['zip_integrity']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(preflight(arguments.archive), sort_keys=True))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())

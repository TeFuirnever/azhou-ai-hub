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
import selectors
import shutil
import subprocess
import time
import stat
import struct
import warnings
import zipfile
import zlib

ARCHIVE_LIMIT = 32 * 1024 * 1024
EXPANDED_LIMIT = 64 * 1024 * 1024
ENTRY_LIMIT = 32
CENTRAL_DIRECTORY_LIMIT = ENTRY_LIMIT * (46 + 65535)
FILE_LIMITS = {'theme.json': 1048576, 'theme.css': 262144}
IMAGE_LIMIT = 10485760
IMAGE_DIMENSION_LIMIT = 16384
IMAGE_PIXEL_LIMIT = 50_000_000
IMAGE_FORMATS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
CSS_ADAPTER = Path(__file__).with_name('reference-safe-css.mjs')
CSS_TIMEOUT = 3
CSS_OUTPUT_LIMIT = 4096
CSS_CONTRACT = 'dreamskin-safe-css/1'
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


def check_central_directory(data, offset, size, count):
    require(0 < count <= ENTRY_LIMIT, 'entry_count')
    require(0 < size <= CENTRAL_DIRECTORY_LIMIT, 'central_directory_size')
    end = offset + size
    cursor = offset
    scanned = 0
    while cursor < end:
        require(scanned < ENTRY_LIMIT, 'entry_count')
        require(cursor + 46 <= end and data[cursor:cursor + 4] == b'PK\x01\x02', 'zip_integrity')
        name_size, extra_size, comment_size = struct.unpack_from('<3H', data, cursor + 28)
        cursor += 46 + name_size + extra_size + comment_size
        require(cursor <= end, 'zip_integrity')
        scanned += 1
    require(cursor == end and scanned == count, 'zip_integrity')


def package_files(data):
    require(data.startswith(b'PK\x03\x04') and data[-22:-18] == b'PK\x05\x06', 'zip_integrity')
    disk, central_disk, count_disk, count, central_size, central_offset, comment_size = struct.unpack('<4H2IH', data[-18:])
    require(disk == central_disk == 0 and count_disk == count and comment_size == 0
            and central_offset + central_size == len(data) - 22, 'zip_integrity')
    check_central_directory(data, central_offset, central_size, count)
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


def image_header_dimensions(format, data):
    if format == 'PNG':
        require(len(data) >= 33 and data[8:16] == b'\x00\x00\x00\rIHDR', 'image_decode_invalid')
        return struct.unpack('>II', data[16:24])
    if format == 'JPEG':
        offset = 2
        while offset < len(data):
            require(data[offset] == 255, 'image_decode_invalid')
            while offset < len(data) and data[offset] == 255:
                offset += 1
            require(offset < len(data), 'image_decode_invalid')
            marker = data[offset]
            offset += 1
            require(marker not in (0, 0xd9, 0xda), 'image_decode_invalid')
            if marker == 1 or 0xd0 <= marker <= 0xd8:
                continue
            require(offset + 2 <= len(data), 'image_decode_invalid')
            length = int.from_bytes(data[offset:offset + 2], 'big')
            require(length >= 2 and offset + length <= len(data), 'image_decode_invalid')
            if marker in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                          0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}:
                require(length >= 8, 'image_decode_invalid')
                height, width = struct.unpack('>HH', data[offset + 3:offset + 7])
                return width, height
            offset += length
    else:
        require(len(data) >= 20 and int.from_bytes(data[4:8], 'little') + 8 == len(data), 'image_decode_invalid')
        offset = 12
        canvas = None
        raster = None
        while offset + 8 <= len(data):
            kind = data[offset:offset + 4]
            size = int.from_bytes(data[offset + 4:offset + 8], 'little')
            offset += 8
            require(offset + size + size % 2 <= len(data), 'image_decode_invalid')
            chunk = data[offset:offset + size]
            require(kind not in (b'ANIM', b'ANMF'), 'image_animation_unsupported')
            if kind == b'VP8X':
                require(size == 10 and canvas is None, 'image_decode_invalid')
                require(not chunk[0] & 2, 'image_animation_unsupported')
                canvas = (int.from_bytes(chunk[4:7], 'little') + 1,
                          int.from_bytes(chunk[7:10], 'little') + 1)
            if kind in (b'VP8L', b'VP8 '):
                require(raster is None, 'image_decode_invalid')
                if kind == b'VP8L':
                    require(size >= 5 and chunk[0] == 47, 'image_decode_invalid')
                    bits = int.from_bytes(chunk[1:5], 'little')
                    raster = (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
                else:
                    require(size >= 10 and chunk[3:6] == b'\x9d\x01\x2a', 'image_decode_invalid')
                    width, height = struct.unpack('<HH', chunk[6:10])
                    raster = width & 0x3fff, height & 0x3fff
            offset += size + size % 2
        require(offset == len(data) and raster is not None, 'image_decode_invalid')
        require(canvas is None or canvas == raster, 'image_dimensions_mismatch')
        return raster
    raise Blocked('image_decode_invalid')


def inspect_image(name, data):
    require(len(data) <= IMAGE_LIMIT, 'image_size')
    require(image_magic_matches(name, data), 'image_magic_mismatch')
    format = IMAGE_FORMATS[Path(name).suffix]
    dimensions = image_header_dimensions(format, data)
    width, height = dimensions
    require(1 <= width <= IMAGE_DIMENSION_LIMIT and 1 <= height <= IMAGE_DIMENSION_LIMIT
            and width * height <= IMAGE_PIXEL_LIMIT, 'image_dimensions_or_pixels')
    try:
        from PIL import Image, ImageFile, features
    except (ImportError, OSError):
        raise Blocked('image_decoder_unavailable') from None
    require(not ImageFile.LOAD_TRUNCATED_IMAGES
            and (format != 'WEBP' or features.check('webp')), 'image_decoder_unavailable')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            for verify in (True, False):
                with Image.open(io.BytesIO(data)) as image:
                    require(image.format == format, 'image_format_mismatch')
                    require(image.size == dimensions, 'image_dimensions_mismatch')
                    require(getattr(image, 'n_frames', 1) == 1 and not getattr(image, 'is_animated', False)
                            and not (format == 'PNG' and 'loop' in image.info), 'image_animation_unsupported')
                    if verify:
                        image.verify()
                    else:
                        image.load()
    except (OSError, ValueError, SyntaxError, EOFError, struct.error, Warning, Image.DecompressionBombError) as error:
        if isinstance(error, Blocked):
            raise
        raise Blocked('image_decode_invalid') from None


def reference_css(data):
    blocked = {'status': 'blocked', 'reasons': ['validator_unavailable'], 'contract': CSS_CONTRACT}
    node = shutil.which('node')
    if node is None or not 0 < len(data) <= FILE_LIMITS['theme.css']:
        return blocked
    process = None
    try:
        process = subprocess.Popen([node, str(CSS_ADAPTER)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env={'PATH': os.defpath})
        deadline = time.monotonic() + CSS_TIMEOUT
        output = {'stdout': bytearray(), 'stderr': bytearray()}
        offset = 0
        with selectors.DefaultSelector() as selector:
            for stream, event, name in [(process.stdin, selectors.EVENT_WRITE, 'stdin'),
                                        (process.stdout, selectors.EVENT_READ, 'stdout'),
                                        (process.stderr, selectors.EVENT_READ, 'stderr')]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return blocked
                for key, _ in selector.select(remaining):
                    stream, name = key.fileobj, key.data
                    if name == 'stdin':
                        offset += os.write(stream.fileno(), data[offset:offset + 65536])
                        if offset == len(data):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        budget = CSS_OUTPUT_LIMIT - sum(map(len, output.values()))
                        chunk = os.read(stream.fileno(), budget + 1)
                        if len(chunk) > budget:
                            return blocked
                        if chunk:
                            output[name].extend(chunk)
                        else:
                            selector.unregister(stream)
                            stream.close()
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0 or output['stderr']:
            return blocked
        response = json.loads(output['stdout'].decode('utf-8'), object_pairs_hook=unique_object)
        if (not isinstance(response, dict)
                or set(response) != {'schema', 'contract', 'status', 'reasons'}
                or response['schema'] != 'azhou-agent-skin.reference-safe-css.v1'
                or response['contract'] != CSS_CONTRACT
                or not ((response['status'] == 'passed' and response['reasons'] == [])
                        or (response['status'] == 'blocked' and response['reasons'] in
                            [['safe_css_invalid'], ['css_utf8_invalid'], ['validator_unavailable']]))):
            return blocked
        return {key: response[key] for key in ('status', 'reasons', 'contract')}
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError):
        return blocked
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


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
        reasons = []
        try:
            inspect_image(image, files[image])
        except Blocked as error:
            reasons.append(str(error))
        try:
            require(bool(files['theme.css'].decode('utf-8').strip()), 'css_empty')
        except (UnicodeError, Blocked):
            reasons.append('css_utf8_or_content_invalid')
        report['resources'] = {'status': 'blocked' if reasons else 'passed', 'reasons': reasons}
        report['reference_css'] = reference_css(files['theme.css'])
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

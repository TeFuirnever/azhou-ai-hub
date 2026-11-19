#!/usr/bin/env python3
"""Isolated Dream source-package storage and CLI contract tests."""
import base64
import builtins
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zipfile

TOOL = Path(__file__).with_name('theme-library.py')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGMUt4xmYGBgYgADKAUADMEAsTl1AMYAAAAASUVORK5CYII=')
COLORS = ['background', 'panel', 'panelAlt', 'accent', 'accentAlt', 'secondary', 'highlight', 'text', 'muted', 'line']
COPY = ['brandSubtitle', 'tagline', 'projectPrefix', 'projectLabel', 'statusText', 'quote', 'promoTitle', 'promoSub']


def load_tool():
    spec = importlib.util.spec_from_file_location('dream_library', TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ThemeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.library = self.root / 'library'
        self.path = self.root / 'source.zip'
        self.theme = {'schemaVersion': 1, 'id': 'dream.demo', 'name': '<b>Dream</b>', 'image': 'background.png',
                      **{key: key + ' 🦊' for key in COPY}, 'promoUrl': 'https://example.invalid/no-navigation',
                      'appearance': 'auto', 'art': {'focusX': 0, 'focusY': 1, 'safeArea': 'right', 'taskMode': 'ambient'},
                      'colors': {key: '#123456' for key in COLORS}}
        self.css = b'[data-ds-part="main"]{background-color:#123456;}'
        self.package()

    def package(self, theme=None, css=None, image=None):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('theme.json', json.dumps(self.theme if theme is None else theme, ensure_ascii=True).encode())
            archive.writestr('theme.css', self.css if css is None else css)
            archive.writestr('background.png', PNG if image is None else image)
        data = out.getvalue()
        self.path.write_bytes(data)
        return data

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(TOOL), '--library', str(self.library), *args],
                              capture_output=True, timeout=20)

    def test_actual_original_zip_import_list_read_and_idempotency(self):
        data = self.path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        result = self.tool.import_package(self.path, self.library)
        self.assertEqual(result['storageStatus'], 'imported')
        self.assertEqual(result['format'], 'dream-simple-v1')
        self.assertEqual(result['applyStatus'], 'blocked')
        self.assertEqual(result['reason'], 'hub_mapping_unimplemented')
        self.assertEqual(result['archiveSha256'], digest)
        self.assertEqual(result['theme'], self.theme)
        stored = self.library / 'objects' / digest / 'archive.zip'
        self.assertEqual(stored.read_bytes(), data)
        before = stored.stat().st_mtime_ns
        self.assertTrue(self.tool.import_package(self.path, self.library)['idempotent'])
        self.assertEqual(stored.stat().st_mtime_ns, before)
        loaded = self.tool.read_package(self.library, digest)
        self.assertEqual(loaded.archive, data)
        self.assertEqual(loaded.record()['theme'], self.theme)
        self.assertEqual(self.tool.list_packages(self.library)['entries'][0]['archiveSha256'], digest)

    def test_cli_restarts_read_real_store_and_never_change_settings_or_lkg(self):
        protected = {name: self.root / name for name in ['images', 'themeState', 'last-known-good', 'host-config']}
        for name, path in protected.items():
            path.write_bytes(name.encode())
        imported = self.cli('import', str(self.path))
        self.assertEqual(imported.returncode, 0, imported.stderr)
        record = json.loads(imported.stdout)
        for args in [('list',), ('read', record['archiveSha256'])]:
            completed = self.cli(*args)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(str(self.root), completed.stdout.decode())
        for name, path in protected.items():
            self.assertEqual(path.read_bytes(), name.encode())

    def test_same_id_different_bytes_get_independent_objects(self):
        first = self.tool.import_package(self.path, self.library)
        original = self.path.read_bytes()
        self.package(css=b'[data-ds-part="main"]{background-color:#654321;}')
        second = self.tool.import_package(self.path, self.library)
        self.assertNotEqual(first['archiveSha256'], second['archiveSha256'])
        self.assertEqual(self.tool.read_package(self.library, first['archiveSha256']).archive, original)
        self.assertEqual(len(self.tool.list_packages(self.library)['entries']), 2)

    def test_all_validation_and_storage_use_the_one_original_read(self):
        original = self.path.read_bytes()
        reader = self.tool.read_source
        def changed_after_read(path):
            data = reader(path)
            self.path.write_bytes(b'changed after read')
            return data
        with mock.patch.object(self.tool, 'read_source', side_effect=changed_after_read) as observed:
            result = self.tool.import_package(self.path, self.library)
        observed.assert_called_once()
        self.assertEqual(self.tool.read_package(self.library, result['archiveSha256']).archive, original)

    def test_strict_official_optional_contract_rejects_invalid_values_and_background_aliases(self):
        changes = [lambda x: x.update(extra=True), lambda x: x.update(schemaVersion=True),
                   lambda x: x.update(image='portal-hero.png'), lambda x: x.update(image='background.jpeg'),
                   lambda x: x.update(appearance='system'), lambda x: x.update(tagline='x' * 121),
                   lambda x: x.update(promoUrl='x' * 513), lambda x: x.update(name='x' * 81),
                   lambda x: x.update(art={'focusX': True}), lambda x: x.update(art={'focusY': 1.01}),
                   lambda x: x.update(art={'safeArea': 'center'}), lambda x: x.update(art={'taskMode': 'on'}),
                   lambda x: x.update(art={'extra': 0}), lambda x: x.update(colors={'background': '#123456'}),
                   lambda x: x['colors'].update(extra='#fff'), lambda x: x['colors'].update(text='var(--text)'),
                   lambda x: x.update(quote='bad\x00value')]
        for change in changes:
            with self.subTest(change=change):
                theme = json.loads(json.dumps(self.theme))
                change(theme)
                self.package(theme=theme)
                with self.assertRaises(self.tool.Blocked):
                    self.tool.import_package(self.path, self.library)
                self.assertFalse(self.library.exists())

    def test_reference_lengths_and_colors_are_not_silently_tightened(self):
        self.theme['tagline'] = '🦊' * 120
        self.theme['name'] = ' '
        self.theme['colors']['text'] = 'rgb(999, 0, 0)'
        self.theme['promoUrl'] = 'stored data, not a URL navigation request'
        self.package()
        self.assertEqual(self.tool.import_package(self.path, self.library)['theme'], self.theme)

    def test_bad_css_image_and_missing_validators_never_initialize_a_library(self):
        for kwargs in [{'css': b'body{color:red;}'}, {'image': b'not png'}]:
            with self.subTest(kwargs=kwargs):
                self.package(**kwargs)
                with self.assertRaises(self.tool.Blocked):
                    self.tool.import_package(self.path, self.library)
                self.assertFalse(self.library.exists())
        self.package()
        with mock.patch.object(self.tool.preflight.shutil, 'which', return_value=None):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        self.assertFalse(self.library.exists())

    def test_unknown_roots_objects_and_links_are_never_overwritten_or_deleted(self):
        self.library.mkdir()
        unknown = self.library / 'unowned'
        unknown.write_bytes(b'keep')
        with self.assertRaises((self.tool.Blocked, OSError)):
            self.tool.import_package(self.path, self.library)
        self.assertEqual(unknown.read_bytes(), b'keep')
        unknown.unlink(); self.library.rmdir()
        result = self.tool.import_package(self.path, self.library)
        object_dir = self.library / 'objects' / result['archiveSha256']
        extra = object_dir / 'unowned'
        extra.write_bytes(b'keep')
        with self.assertRaises((self.tool.Blocked, OSError)):
            self.tool.import_package(self.path, self.library)
        self.assertEqual(extra.read_bytes(), b'keep')
        extra.unlink()
        archive = object_dir / 'archive.zip'
        archive.unlink(); archive.symlink_to(self.path)
        with self.assertRaises((self.tool.Blocked, OSError)):
            self.tool.import_package(self.path, self.library)
        self.assertTrue(archive.is_symlink())

    def test_library_root_and_parent_symlinks_are_rejected(self):
        real = self.root / 'real'; real.mkdir()
        alias = self.root / 'alias'; alias.symlink_to(real, target_is_directory=True)
        for library in [alias, alias / 'library']:
            with self.assertRaises((self.tool.Blocked, OSError)):
                self.tool.import_package(self.path, library)
        self.assertEqual(list(real.iterdir()), [])

    def test_tampering_is_blocked_on_read_and_reported_per_item_on_list(self):
        first = self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        second = self.tool.import_package(self.path, self.library)
        (self.library / 'objects' / first['archiveSha256'] / 'archive.zip').write_bytes(b'tampered')
        with self.assertRaises(self.tool.Blocked):
            self.tool.read_package(self.library, first['archiveSha256'])
        listed = self.tool.list_packages(self.library)
        self.assertEqual(listed['storageStatus'], 'partial')
        entries = {item['archiveSha256']: item for item in listed['entries']}
        self.assertEqual(entries[first['archiveSha256']]['storageStatus'], 'blocked')
        self.assertEqual(entries[second['archiveSha256']]['storageStatus'], 'imported')

    def test_write_failure_keeps_existing_objects_and_initialization_can_retry(self):
        with mock.patch.object(self.tool.os, 'write', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises((self.tool.Blocked, OSError)):
                self.tool.import_package(self.path, self.library)
        self.assertFalse(self.library.exists())
        first = self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        with mock.patch.object(self.tool.os, 'write', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises((self.tool.Blocked, OSError)):
                self.tool.import_package(self.path, self.library)
        self.assertEqual([item['archiveSha256'] for item in self.tool.list_packages(self.library)['entries']], [first['archiveSha256']])

    def test_concurrent_same_package_is_idempotent(self):
        command = [sys.executable, '-B', str(TOOL), '--library', str(self.library), 'import', str(self.path)]
        workers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for worker in workers:
            stdout, stderr = worker.communicate(timeout=20)
            self.assertEqual(worker.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)['storageStatus'], 'imported')
        self.assertEqual(len(self.tool.list_packages(self.library)['entries']), 1)

    def test_racing_unknown_empty_destination_is_not_replaced(self):
        self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        original = self.tool.publish_directory
        def race(source_fd, source, destination_fd, destination):
            if destination == digest:
                os.mkdir(destination, dir_fd=destination_fd)
            return original(source_fd, source, destination_fd, destination)
        with mock.patch.object(self.tool, 'publish_directory', side_effect=race):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        self.assertEqual(list((self.library / 'objects' / digest).iterdir()), [])

    def test_changed_staged_bytes_cannot_report_a_successful_import(self):
        self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        original = self.tool.publish_directory
        def change_stage(source_fd, source, destination_fd, destination):
            stage = self.library / 'incoming' / source
            (stage / 'archive.zip').write_bytes(b'changed staging bytes')
            return original(source_fd, source, destination_fd, destination)
        with mock.patch.object(self.tool, 'publish_directory', side_effect=change_stage):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)

    def test_unknown_postpublication_object_entry_is_blocked_and_preserved(self):
        self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        original = self.tool.publish_directory
        def extra_entry(source_fd, source, destination_fd, destination):
            (self.library / 'incoming' / source / 'unowned').write_bytes(b'keep')
            return original(source_fd, source, destination_fd, destination)
        with mock.patch.object(self.tool, 'publish_directory', side_effect=extra_entry):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        self.assertEqual((self.library / 'objects' / digest / 'unowned').read_bytes(), b'keep')

    def test_directory_fd_pins_prevent_writes_into_replaced_root(self):
        self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        original = self.tool.publish_directory
        moved = self.root / 'moved'
        def replace_root(source_fd, source, destination_fd, destination):
            self.library.rename(moved)
            self.library.mkdir()
            (self.library / 'unowned').write_bytes(b'keep')
            return original(source_fd, source, destination_fd, destination)
        with mock.patch.object(self.tool, 'publish_directory', side_effect=replace_root):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        self.assertEqual([(path.name, path.read_bytes()) for path in self.library.iterdir()], [('unowned', b'keep')])
        self.assertTrue((moved / 'objects').is_dir())

    def test_process_exit_before_root_or_object_publication_leaves_retryable_store(self):
        for phase in ['root', 'object']:
            with self.subTest(phase=phase):
                target = self.root / ('crash-' + phase)
                if phase == 'object':
                    self.tool.import_package(self.path, target)
                    self.package(css=b'[data-ds-part="main"]{color:#fff;}')
                program = """import importlib.util,sys,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('dream_library',sys.argv[1]);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
original=m.publish_directory
def stop(a,b,c,d):
    if (sys.argv[4]=='root' and d==Path(sys.argv[3]).name) or (sys.argv[4]=='object' and len(d)==64): os._exit(72)
    return original(a,b,c,d)
m.publish_directory=stop
m.import_package(Path(sys.argv[2]),Path(sys.argv[3]))
"""
                worker = subprocess.run([sys.executable, '-B', '-c', program, str(TOOL), str(self.path), str(target), phase],
                                        capture_output=True, timeout=20)
                self.assertEqual(worker.returncode, 72, worker.stderr)
                if phase == 'root':
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(len(self.tool.list_packages(target)['entries']), 1)
                self.assertEqual(self.tool.import_package(self.path, target)['storageStatus'], 'imported')

    def test_missing_pillow_and_untrusted_validator_responses_cannot_publish(self):
        original_import = builtins.__import__
        def no_pillow(name, *args, **kwargs):
            if name == 'PIL' or name.startswith('PIL.'):
                raise ImportError('unavailable')
            return original_import(name, *args, **kwargs)
        with mock.patch('builtins.__import__', side_effect=no_pillow):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        for response in [None, [], {'status': 'passed'},
                         {'schema': 'azhou-agent-skin.reference-official-theme.v1', 'contract': 'codex-dream-official-theme/6fc42df4',
                          'status': 'passed', 'reasons': [], 'trusted': True}]:
            with self.subTest(response=response), mock.patch.object(self.tool.preflight, 'reference_adapter', return_value=response):
                with self.assertRaises(self.tool.Blocked):
                    self.tool.import_package(self.path, self.library)
        self.assertFalse(self.library.exists())

    def test_catalog_bound_and_unknown_names_fail_without_deleting_objects(self):
        first = self.tool.import_package(self.path, self.library)
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        with mock.patch.object(self.tool, 'CATALOG_LIMIT', 1):
            with self.assertRaises(self.tool.Blocked):
                self.tool.import_package(self.path, self.library)
        unowned = self.library / 'objects' / 'unowned'
        unowned.write_bytes(b'keep')
        with self.assertRaises(self.tool.Blocked):
            self.tool.list_packages(self.library)
        self.assertEqual(unowned.read_bytes(), b'keep')
        self.assertTrue((self.library / 'objects' / first['archiveSha256']).is_dir())

    def test_reference_derivative_has_fixed_hash_and_no_filesystem_or_host_compiler(self):
        vendor = TOOL.parent.parent / 'vendor'
        module = (vendor / 'dream-theme-validator.mjs').read_bytes()
        self.assertEqual(hashlib.sha256(module).hexdigest(), '63363d5830cd76c57483ce7bdad28b66bce5dfae596134a6c46350c3169ad3ff')
        self.assertEqual(hashlib.sha256((vendor / 'dream-theme-validator.LICENSE').read_bytes()).hexdigest(),
                         '18f8478d0f9efd45307e5f17790194593b116658145c758ced3166398eb05b21')
        self.assertNotIn(b'node:fs', module)
        self.assertNotIn(b'decodeAndValidateSafeCss', module)
        spec = importlib.util.spec_from_file_location('extract_dream', TOOL.with_name('extract-dream-theme-validator.py'))
        extractor = importlib.util.module_from_spec(spec); spec.loader.exec_module(extractor)
        with self.assertRaises(ValueError):
            extractor.extract(b'unknown source', (vendor / 'dream-theme-validator.LICENSE').read_bytes())
        synthetic = '\n'.join(start + '\n' + end for start, end in extractor.SPANS).encode()
        with mock.patch.object(extractor, 'SOURCE_SHA256', hashlib.sha256(synthetic).hexdigest()):
            result = extractor.extract(synthetic, (vendor / 'dream-theme-validator.LICENSE').read_bytes())
        self.assertTrue(result.startswith(extractor.HEADER.encode()))
        self.assertTrue(result.endswith(b'export { validateOfficialTheme };\n'))


    def test_two_real_processes_compete_for_the_last_catalog_slot(self):
        program = """import importlib.util,json,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('dream_library',sys.argv[1]);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.CATALOG_LIMIT=int(sys.argv[4]);gate=Path(sys.argv[5]);worker=sys.argv[6]
original=m.Stage.write
def barrier(stage,name,data):
    original(stage,name,data)
    if name=='archive.zip':
        (gate/(worker+'.ready')).write_text('ready')
        end=time.monotonic()+5
        while not all((gate/(str(n)+'.ready')).exists() for n in range(2)):
            if time.monotonic()>end: raise RuntimeError('fixture barrier timed out')
            time.sleep(0.005)
m.Stage.write=barrier
try:
    print(json.dumps(m.import_package(Path(sys.argv[2]),Path(sys.argv[3]))));code=0
except m.Blocked as error:
    print(json.dumps({'storageStatus':'blocked','reason':str(error)}));code=2
raise SystemExit(code)
"""
        for limit in [1, 2]:
            with self.subTest(limit=limit):
                library = self.root / ('capacity-' + str(limit))
                gate = self.root / ('gate-' + str(limit)); gate.mkdir()
                if limit == 2:
                    self.package()
                    self.tool.import_package(self.path, library)
                sources = []
                for index, color in enumerate(['#654321', '#abcdef']):
                    data = self.package(css=('[data-ds-part="main"]{color:' + color + ';}').encode())
                    source = self.root / ('capacity-' + str(limit) + '-' + str(index) + '.zip')
                    source.write_bytes(data); sources.append(source)
                workers = [subprocess.Popen([sys.executable, '-B', '-c', program, str(TOOL), str(source), str(library),
                                             str(limit), str(gate), str(index)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                           for index, source in enumerate(sources)]
                results = []
                for worker in workers:
                    stdout, stderr = worker.communicate(timeout=15)
                    results.append((worker.returncode, json.loads(stdout), stderr))
                self.assertEqual(sorted(item[0] for item in results), [0, 2], results)
                self.assertEqual([item[1]['reason'] for item in results if item[0] == 2], ['library_size'])
                with mock.patch.object(self.tool, 'CATALOG_LIMIT', limit):
                    listed = self.tool.list_packages(library)
                self.assertEqual(len(listed['entries']), limit)
                self.assertEqual(listed['storageStatus'], 'imported')

    def test_lock_identity_content_and_symlinks_are_not_adopted(self):
        self.tool.import_package(self.path, self.library)
        owner = (self.library / self.tool.MARKER).read_bytes()
        lock = self.library / self.tool.LOCK_NAME
        info = lock.stat()
        self.assertEqual(json.loads(owner)['lockIdentity'], [info.st_dev, info.st_ino])
        self.package(css=b'[data-ds-part="main"]{color:#fff;}')
        lock.write_bytes(b'unowned lock')
        with self.assertRaises(self.tool.Blocked):
            self.tool.import_package(self.path, self.library)
        self.assertEqual(lock.read_bytes(), b'unowned lock')
        lock.write_bytes(self.tool.LOCK_CONTENT)
        saved = self.root / 'original-lock'
        lock.rename(saved)
        lock.write_bytes(self.tool.LOCK_CONTENT)
        with self.assertRaises(self.tool.Blocked):
            self.tool.import_package(self.path, self.library)
        self.assertEqual((self.library / self.tool.MARKER).read_bytes(), owner)
        lock.unlink(); lock.symlink_to(saved)
        with self.assertRaises((self.tool.Blocked, OSError)):
            self.tool.import_package(self.path, self.library)
        self.assertTrue(lock.is_symlink())
        self.assertEqual(saved.read_bytes(), self.tool.LOCK_CONTENT)

    def test_legacy_unlocked_layout_is_not_silently_migrated(self):
        self.library.mkdir()
        (self.library / self.tool.MARKER).write_bytes(b'azhou-agent-skin.dream-source-library.v1\n')
        (self.library / 'objects').mkdir(); (self.library / 'incoming').mkdir()
        with self.assertRaises(self.tool.Blocked):
            self.tool.import_package(self.path, self.library)
        self.assertEqual({path.name for path in self.library.iterdir()}, {self.tool.MARKER, 'objects', 'incoming'})

    def test_lock_wait_is_bounded_and_process_exit_releases_it(self):
        self.tool.import_package(self.path, self.library)
        ready = self.root / 'lock-ready'; release = self.root / 'lock-release'
        program = """import importlib.util,os,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('dream_library',sys.argv[1]);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
with m.Library(Path(sys.argv[2])) as store:
    with store.exclusive():
        Path(sys.argv[3]).write_text('locked');end=time.monotonic()+5
        while not Path(sys.argv[4]).exists() and time.monotonic()<end: time.sleep(0.005)
        os._exit(72)
"""
        worker = subprocess.Popen([sys.executable, '-B', '-c', program, str(TOOL), str(self.library), str(ready), str(release)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < end:
                time.sleep(0.005)
            self.assertTrue(ready.exists())
            self.assertTrue(self.tool.import_package(self.path, self.library)['idempotent'])
            with self.tool.Library(self.library) as store, mock.patch.object(self.tool, 'LOCK_WAIT_SECONDS', 0.05):
                started = time.monotonic()
                with self.assertRaisesRegex(self.tool.Blocked, '^library_busy$'):
                    with store.exclusive():
                        self.fail('another process holds the lock')
                self.assertLess(time.monotonic() - started, 2)
            release.write_text('exit without unlock')
            _, stderr = worker.communicate(timeout=3)
            self.assertEqual(worker.returncode, 72, stderr)
            self.package(css=b'[data-ds-part="main"]{color:#fff;}')
            self.assertEqual(self.tool.import_package(self.path, self.library)['storageStatus'], 'imported')
        finally:
            if worker.poll() is None:
                worker.terminate(); worker.communicate(timeout=3)

    def test_replaced_lock_is_detected_by_a_waiting_process(self):
        self.tool.import_package(self.path, self.library)
        ready = self.root / 'waiter-ready'
        program = """import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('dream_library',sys.argv[1]);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
try:
    with m.Library(Path(sys.argv[2])) as store:
        Path(sys.argv[3]).write_text('opened original lock')
        with store.exclusive(): pass
    code=0
except m.Blocked as error:
    print(json.dumps({'reason':str(error)}));code=2
raise SystemExit(code)
"""
        lock = self.library / self.tool.LOCK_NAME
        replacement = self.root / 'replacement-lock'
        replacement.write_bytes(self.tool.LOCK_CONTENT)
        with self.tool.descriptor(os.open(lock, self.tool.FILE_FLAGS)) as fd:
            self.tool.fcntl.flock(fd, self.tool.fcntl.LOCK_EX)
            worker = subprocess.Popen([sys.executable, '-B', '-c', program, str(TOOL), str(self.library), str(ready)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                end = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < end:
                    time.sleep(0.005)
                self.assertTrue(ready.exists())
                # Keep the lock name present while changing its identity.
                replacement.replace(lock)
                stdout, stderr = worker.communicate(timeout=3)
                self.assertEqual(worker.returncode, 2, stderr)
                self.assertEqual(json.loads(stdout)['reason'], 'library_lock_changed')
                self.assertEqual(lock.read_bytes(), self.tool.LOCK_CONTENT)
            finally:
                if worker.poll() is None:
                    worker.terminate(); worker.communicate(timeout=3)
                self.tool.fcntl.flock(fd, self.tool.fcntl.LOCK_UN)

    def test_developer_library_only_reads_and_never_exports_an_appearance_capsule(self):
        data = self.path.read_bytes()
        result = self.tool.import_package(self.path, self.library)
        digest = result["archiveSha256"]
        readback = self.cli("read", digest)
        self.assertEqual(readback.returncode, 0, readback.stderr)
        self.assertEqual(json.loads(readback.stdout)["applyStatus"], "blocked")
        self.assertEqual(self.tool.read_package(self.library, digest).archive, data)
        refused = self.cli("export-capsule", digest)
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(refused.stdout, b"")
        self.assertIn(b"invalid choice", refused.stderr)
        self.assertEqual(self.path.read_bytes(), data)

    def test_read_requires_digest_and_never_creates_missing_library(self):
        result = self.cli('read', '../private')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(self.root), result.stdout.decode())
        self.assertFalse(self.library.exists())


if __name__ == '__main__':
    unittest.main()

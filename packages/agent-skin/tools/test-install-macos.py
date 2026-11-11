#!/usr/bin/env python3
"""Isolated installer regressions; native exclusive rename is exercised on macOS."""
import contextlib
from functools import partial
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import signal
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
INSTALLER = Path(__file__).with_name('install-macos.py')


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='azhou-installer-test-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        spec = importlib.util.spec_from_file_location('azhou_installer_tested', INSTALLER)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        m = self.module
        m.ROOT = self.base / 'project'
        m.ROOT.mkdir()
        m.SOURCE = m.ROOT / '.build/azhou-payload'
        m.DIST = m.ROOT / 'dist'
        m.DESTINATION = self.base / 'Applications' / m.HELPERS['NAME']
        m.REGISTRY_TOOL = m.ROOT / '.build/azhou-install-registry'
        helpers = m.HELPERS['verify_product'].__globals__
        helpers['ROOT'] = m.ROOT
        for name in helpers['INPUT_FILES']:
            path = m.ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test source: ' + name)
        private = m.ROOT / 'assets/private'
        private.mkdir(parents=True)
        (private / 'scene.js').write_text('test fixture')
        self.bundle(m.SOURCE)
        self.registry = {identity[0]: set() for identity in m.KNOWN}
        self.commands = []
        self.running = ''
        self.failure = None
        self.swap_calls = 0
        self.sticky_unregister = set()
        self.fail_unregister_once = set()
        self.mutate_source_during_copy = False
        self.mutate_old_during_copy = None
        self.capture = io.StringIO()
        self.addCleanup(patch.stopall)
        patch.object(subprocess, 'run', self.run_command).start()
        patch.object(subprocess, 'check_output', self.check_output).start()
        patch.object(m, 'swap', self.exchange).start()
        self.native_publish_exclusive = m.publish_exclusive
        patch.object(m, 'publish_exclusive', self.publish_exclusive).start()
        self.output = contextlib.redirect_stdout(self.capture)
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_receipt_preserves_file_created_at_published_temporary_name(self):
        m = self.module
        replace = os.replace
        foreign = []
        def publish_then_reuse(source, destination):
            replace(source, destination)
            Path(source).write_bytes(b'foreign after publication')
            foreign.append(Path(source))
        with patch.object(m.os, 'replace', side_effect=publish_then_reuse):
            m.save_receipt({'fixture': True})
        self.assertEqual(json.loads(m.receipt_path().read_text()), {'fixture': True})
        self.assertEqual(foreign[0].read_bytes(), b'foreign after publication')

    def test_receipt_failure_removes_only_unmodified_temporary_file(self):
        m = self.module
        with patch.object(m.os, 'replace', side_effect=OSError('synthetic replace failure')):
            with self.assertRaisesRegex(OSError, 'synthetic replace failure'):
                m.save_receipt({'fixture': True})
        self.assertEqual(list((m.ROOT / '.local').glob('.installation-*.json')), [])
        foreign = []
        def replace_source_then_fail(source, destination):
            source = Path(source)
            source.rename(source.with_suffix('.saved'))
            source.write_bytes(b'foreign replacement')
            foreign.append(source)
            raise OSError('synthetic replace failure')
        with patch.object(m.os, 'replace', side_effect=replace_source_then_fail):
            with self.assertRaisesRegex(OSError, 'synthetic replace failure'):
                m.save_receipt({'fixture': True})
        self.assertEqual(foreign[0].read_bytes(), b'foreign replacement')
        self.assertFalse(m.receipt_path().exists())

    def test_receipt_preserves_in_place_modified_and_incomplete_files(self):
        m = self.module
        changed = []
        def modify_then_fail(source, destination):
            source = Path(source)
            source.write_bytes(b'changed contents')
            changed.append(source)
            raise OSError('synthetic replace failure')
        with patch.object(m.os, 'replace', side_effect=modify_then_fail):
            with self.assertRaisesRegex(OSError, 'synthetic replace failure'):
                m.save_receipt({'fixture': True})
        self.assertEqual(changed[0].read_bytes(), b'changed contents')
        with patch.object(m.os, 'fsync', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaisesRegex(OSError, 'synthetic fsync failure'):
                m.save_receipt({'incomplete': True})
        leftovers = list((m.ROOT / '.local').glob('.installation-*.json'))
        self.assertEqual(len(leftovers), 2)
        self.assertFalse(m.receipt_path().exists())

    def test_receipt_rejects_replacement_before_publication(self):
        m = self.module
        fsync = os.fsync
        changed = []
        def replace_after_sync(fd):
            fsync(fd)
            source = next((m.ROOT / '.local').glob('.installation-*.json'))
            source.rename(source.with_suffix('.saved'))
            source.write_bytes(b'foreign before publication')
            changed.append(source)
        with patch.object(m.os, 'fsync', side_effect=replace_after_sync):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                m.save_receipt({'fixture': True})
        self.assertEqual(changed[0].read_bytes(), b'foreign before publication')
        self.assertFalse(m.receipt_path().exists())

    def bundle(self, path, identity=None, version='0.5.1', build='3', marker=True, body='new'):
        m = self.module
        identity = identity or m.EXPECTED
        executable = path / 'Contents/MacOS' / identity[1]
        executable.parent.mkdir(parents=True)
        executable.write_text(body)
        executable.chmod(0o755)
        web = path / 'Contents/Resources/web'
        web.mkdir(parents=True)
        (web / 'index.html').write_text(body)
        info = {'CFBundleIdentifier': identity[0], 'CFBundleExecutable': identity[1],
                'CFBundleDisplayName': '阿舟启动 Codex', 'CFBundleShortVersionString': version,
                'CFBundleVersion': build, 'CFBundlePackageType': 'APPL', 'LSUIElement': True}
        (path / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        if marker:
            inputs = m.HELPERS['source_inputs']()
            data = {'schema': 1, 'projectID': m.PROJECT_ID, 'projectRoot': str(m.ROOT),
                    'bundleID': identity[0], 'executable': identity[1], 'version': version,
                    'build': build, 'inputs': inputs, 'inputSHA256': m.HELPERS['aggregate_inputs'](inputs)}
            (path / m.HELPERS['MARKER']).write_text(json.dumps(data))

    def clone(self, destination, source=None):
        source = source or self.module.SOURCE
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        self.registry[self.module.EXPECTED[0]].add(destination)
        return destination

    def old_pair(self, installed_path=None):
        m = self.module
        installed_path = (Path(installed_path) if installed_path is not None
                          else m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME']))
        self.bundle(installed_path, version='0.5.0', build='2', marker=False, body='known old')
        old = self.clone(m.DIST / m.HELPERS['LEGACY_NAME'], installed_path)
        self.registry[m.EXPECTED[0]].add(installed_path)
        # Test packages contain no private assets; pin their own known digest.
        m.LEGACY_SHA256 = m.fingerprint(installed_path)
        record = m.receipt_path()
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({'sha256Tree': m.LEGACY_SHA256, 'installedPath': str(installed_path),
                                      'sourcePath': str(old), 'bundleID': m.EXPECTED[0], 'version': '0.5.0'}))
        return old

    def old_owned_install(self, installed_path=None):
        m = self.module
        installed_path = Path(installed_path) if installed_path is not None else m.DESTINATION
        old_root = self.base / 'old-project'
        old_root.mkdir()
        old_root = old_root.resolve()
        self.bundle(installed_path, version='0.5.0', build='2', body='old owner')
        marker_path = installed_path / m.HELPERS['MARKER']
        marker = json.loads(marker_path.read_text())
        marker['projectRoot'] = str(old_root)
        marker_path.write_text(json.dumps(marker))
        old_source = old_root / '.build/azhou-payload'
        old_source.parent.mkdir(parents=True)
        shutil.copytree(installed_path, old_source)
        old_hash = m.fingerprint(installed_path)
        record = {'schema': 2, 'projectID': m.PROJECT_ID, 'projectRoot': str(old_root),
                  'status': 'installed', 'installedPath': str(installed_path),
                  'sourcePath': str(old_source), 'sha256Tree': old_hash,
                  'bundleID': m.EXPECTED[0], 'executable': m.EXPECTED[1],
                  'version': '0.5.0', 'build': '2'}
        (old_root / '.local').mkdir()
        (old_root / '.local/installation.json').write_text(json.dumps(record))
        self.registry[m.EXPECTED[0]].add(installed_path)
        return old_root, record

    def leave_pending_handoff_after_removal_failure(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_root, _ = self.old_owned_install(installed_path=legacy)
        real_rmtree = shutil.rmtree
        fail_once = {'pending': True}

        def fail_old_entry_once(path, *args, **kwargs):
            pending = m.read_receipt().get('retirementPending', {})
            isolated_old_entry = (pending.get('path') == str(legacy) and pending.get('stage') == str(path))
            if (Path(path) == legacy or isolated_old_entry) and fail_once['pending']:
                fail_once['pending'] = False
                raise OSError('injected old entry removal failure')
            return real_rmtree(path, *args, **kwargs)

        def fail_isolated_entry_once(descriptor, *args, **kwargs):
            pending = m.read_receipt().get('retirementPending', {})
            if pending.get('path') == str(legacy) and fail_once['pending']:
                fail_once['pending'] = False
                raise OSError('injected old entry removal failure')
            return remove_contents(descriptor, *args, **kwargs)

        remove_contents = getattr(m, '_remove_retirement_contents', None)
        fault = (patch.object(m, '_remove_retirement_contents', side_effect=fail_isolated_entry_once)
                 if remove_contents else patch.object(m.shutil, 'rmtree', side_effect=fail_old_entry_once))
        with fault:
            with self.assertRaisesRegex(OSError, 'injected old entry removal failure'):
                m.install(migrate_from=str(old_root))
        self.assertTrue(legacy.is_dir())
        self.assertEqual(self.registry[m.EXPECTED[0]], set())
        return legacy, old_root

    def interrupted_retirement(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        digest = m.fingerprint(legacy)
        directory = legacy.parent / '.azhou-retire-interrupted'
        directory.mkdir()
        payload = directory / 'payload'
        legacy.rename(payload)
        record = {'schema': 2, 'projectID': m.PROJECT_ID, 'projectRoot': str(m.ROOT),
                  'status': 'cleanup-pending', 'managedFingerprints': [digest],
                  'retiredArtifacts': [{'path': str(legacy), 'bundleID': m.EXPECTED[0],
                                        'executable': m.EXPECTED[1], 'sha256Tree': digest}],
                  'retirementPending': {'path': str(legacy), 'stage': str(payload)}}
        m.save_receipt(record)
        return legacy, payload

    def run_command(self, command, **options):
        m = self.module
        self.commands.append(tuple(str(value) for value in command))
        if command[0] == '/usr/bin/codesign':
            if Path(command[-1]) == m.DESTINATION and self.swap_calls == 1 and self.failure in ('verify', 'rollback'):
                raise subprocess.CalledProcessError(1, command)
        elif command[0] == '/usr/bin/ditto':
            shutil.copytree(command[1], command[2])
            if self.mutate_source_during_copy:
                (m.SOURCE / 'Contents/Resources/web/index.html').write_text('concurrent build')
            if self.mutate_old_during_copy is not None:
                (self.mutate_old_during_copy / 'Contents/Resources/web/index.html').write_text('concurrent old build')
        elif command[0] == m.LSREGISTER:
            self.assertEqual(command[1], '-u')
            path = Path(command[2])
            if path in self.fail_unregister_once:
                self.fail_unregister_once.remove(path)
                raise subprocess.CalledProcessError(1, command)
            if path not in self.sticky_unregister:
                for paths in self.registry.values():
                    paths.discard(path)
        elif command[0] == str(m.REGISTRY_TOOL) and command[1] == 'register':
            self.assertEqual(Path(command[2]), m.DESTINATION)
            self.registry[m.EXPECTED[0]].add(m.DESTINATION)
        else:
            self.fail('Unexpected external operation: ' + repr(command))
        return subprocess.CompletedProcess(command, 0)

    def check_output(self, command, **options):
        m = self.module
        if command[0] == '/bin/ps':
            return self.running
        self.assertEqual(command, [str(m.REGISTRY_TOOL), 'inventory'])
        return json.dumps({'schema': 1, 'applications': [
            {'bundleID': identity, 'urls': [{'path': str(path), 'exists': path.exists()} for path in sorted(paths)]}
            for identity, paths in self.registry.items()]})

    def exchange(self, left, right):
        self.swap_calls += 1
        if (self.failure == 'swap' and self.swap_calls == 1) or (self.failure == 'rollback' and self.swap_calls == 2):
            raise OSError('injected atomic exchange failure')
        temporary = left.parent / 'exchange'
        os.rename(left, temporary)
        os.rename(right, left)
        os.rename(temporary, right)

    def publish_exclusive(self, source, destination):
        if destination.exists() or destination.is_symlink():
            raise RuntimeError('规范入口被其他操作创建，未覆盖。')
        os.rename(source, destination)

    def assert_clean(self):
        m = self.module
        self.assertEqual(m.fingerprint(m.DESTINATION), m.fingerprint(m.SOURCE))
        self.assertFalse(list(m.DIST.glob('*.app')))
        self.assertFalse(list(self.base.rglob('*.zip')))
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assertTrue(all(not paths for identity, paths in self.registry.items() if identity != m.EXPECTED[0]))

    def test_verified_050_pair_migrates_to_one_app(self):
        old = self.old_pair()
        result = self.module.install()
        self.assertEqual(result['status'], 'installed')
        self.assertFalse(old.exists())
        self.assert_clean()
        self.assertEqual(self.module.install()['status'], 'current')
        self.assert_clean()

    def test_legacy_050_receipt_and_pair_prove_only_the_legacy_canonical_path(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_source = m.DIST / '阿舟启动 Codex.app'
        self.bundle(legacy, version='0.5.0', build='2', marker=False, body='known old')
        old_source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy, old_source)
        self.registry[m.EXPECTED[0]].add(legacy)
        m.LEGACY_SHA256 = m.fingerprint(legacy)
        record = m.receipt_path()
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({
            'sha256Tree': m.LEGACY_SHA256, 'installedPath': str(legacy),
            'sourcePath': str(old_source), 'bundleID': m.EXPECTED[0], 'version': '0.5.0',
        }))

        result = m.install()

        self.assertEqual(result['status'], 'installed')
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertFalse(legacy.exists())
        self.assertFalse(old_source.exists())
        self.assertIn((m.LSREGISTER, '-u', str(legacy)), self.commands)
        self.assert_clean()

    def test_legacy_050_fingerprint_does_not_authorize_a_renamed_alias(self):
        m = self.module
        alias = m.DESTINATION.with_name('Renamed copy.app')
        old_source = m.DIST / '阿舟启动 Codex.app'
        self.bundle(alias, version='0.5.0', build='2', marker=False, body='known old')
        old_source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(alias, old_source)
        self.registry[m.EXPECTED[0]].add(alias)
        m.LEGACY_SHA256 = m.fingerprint(alias)
        record = m.receipt_path()
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({
            'sha256Tree': m.LEGACY_SHA256, 'installedPath': str(alias),
            'sourcePath': str(old_source), 'bundleID': m.EXPECTED[0], 'version': '0.5.0',
        }))
        before = m.fingerprint(alias)

        with self.assertRaisesRegex(RuntimeError, '不足以证明'):
            m.install()

        self.assertEqual(m.fingerprint(alias), before)
        self.assertTrue(old_source.exists())
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_legacy_pair_accepts_current_name_in_old_dist_receipt(self):
        m = self.module
        old_dist = self.old_pair()
        renamed = m.DIST / m.HELPERS['NAME']
        old_dist.rename(renamed)
        self.registry[m.EXPECTED[0]].discard(old_dist)
        self.registry[m.EXPECTED[0]].add(renamed)
        receipt = m.receipt_path()
        record = json.loads(receipt.read_text())
        record['sourcePath'] = str(renamed)
        receipt.write_text(json.dumps(record))
        self.assertEqual(m.install()['status'], 'installed')
        self.assertFalse(renamed.exists())
        self.assert_clean()

    def test_legacy_pair_accepts_current_name_in_old_dist_without_receipt(self):
        m = self.module
        old_dist = self.old_pair()
        renamed = m.DIST / m.HELPERS['NAME']
        old_dist.rename(renamed)
        self.registry[m.EXPECTED[0]].discard(old_dist)
        self.registry[m.EXPECTED[0]].add(renamed)
        m.receipt_path().unlink()
        self.assertEqual(m.install()['status'], 'installed')
        self.assertFalse(renamed.exists())
        self.assert_clean()

    def test_untrusted_history_does_not_authorize_a_legacy_fingerprint(self):
        m = self.module
        old = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        self.bundle(old, version='0.5.0', build='2', marker=False, body='known old')
        m.LEGACY_SHA256 = m.fingerprint(old)
        forged = {'projectID': 'foreign', 'projectRoot': '/foreign',
                  'managedFingerprints': [m.LEGACY_SHA256]}
        with self.assertRaisesRegex(RuntimeError, '不足以证明'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), forged)
        self.assertTrue(old.is_dir())

    def test_handoff_without_matching_source_marker_cannot_authorize_an_alias(self):
        m = self.module
        alias = m.DESTINATION.with_name('Unowned.app')
        self.bundle(alias, version='0.5.0', build='2', marker=False, body='unowned old')
        digest = m.fingerprint(alias)
        forged = {'oldRoot': '/foreign', 'installedPath': str(alias), 'oldSHA256': digest}
        with self.assertRaisesRegex(RuntimeError, '不足以证明'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), {}, forged)
        self.assertTrue(alias.is_dir())

    def test_upgrade_registers_canonical_without_unregistering_it(self):
        m = self.module
        old = self.old_pair()
        m.install()
        self.assertIn((m.LSREGISTER, '-u', str(old)), self.commands)
        self.assertNotIn((m.LSREGISTER, '-u', str(m.DESTINATION)), self.commands)
        self.assertIn((str(m.REGISTRY_TOOL), 'register', str(m.DESTINATION)), self.commands)
        self.assert_clean()

    def test_pending_upgrade_repairs_canonical_registration_without_unregister(self):
        m = self.module
        old = self.old_pair()
        m.install()
        self.assertFalse(old.exists())
        record = m.read_receipt()
        record['status'] = 'cleanup-pending'
        m.save_receipt(record)
        self.registry[m.EXPECTED[0]].clear()
        self.commands.clear()
        m.install()
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))
        self.assertIn((str(m.REGISTRY_TOOL), 'register', str(m.DESTINATION)), self.commands)
        self.assert_clean()

    def test_pending_upgrade_refreshes_metadata_when_registry_url_is_already_correct(self):
        m = self.module
        self.old_pair()
        m.install()
        record = m.read_receipt()
        record['status'] = 'cleanup-pending'
        m.save_receipt(record)
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.commands.clear()
        m.install()
        self.assertIn((str(m.REGISTRY_TOOL), 'register', str(m.DESTINATION)), self.commands)
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))
        self.assertNotEqual(m.read_receipt()['status'], 'cleanup-pending')
        self.assert_clean()

    def test_current_target_still_retires_dist_and_renamed_copy(self):
        m = self.module
        self.clone(m.DESTINATION)
        self.clone(m.DIST / 'Renamed copy.app')
        alias = self.clone(m.DESTINATION.parent / 'Another name.app')
        self.assertEqual(m.install()['status'], 'consolidated')
        self.assertFalse(alias.exists())
        self.assert_clean()

    def test_canonical_name_retires_same_root_legacy_entry_and_preserves_other_apps(self):
        m = self.module
        legacy = m.DESTINATION.parent / '阿舟启动 Codex.app'
        self.bundle(legacy, version='0.5.0', build='2', body='old canonical name')
        self.registry[m.EXPECTED[0]].add(legacy)
        official = m.DESTINATION.parent / 'Codex.app'
        self.bundle(official, identity=('com.openai.codex', 'Codex'), marker=False)
        unrelated = m.DESTINATION.parent / 'Unrelated.app'
        self.bundle(unrelated, identity=('org.example.unrelated', 'Unrelated'), marker=False)
        preserved = (m.fingerprint(official), m.fingerprint(unrelated))

        result = m.install()

        self.assertEqual(m.HELPERS['NAME'], '阿舟 AI 实验室.app')
        self.assertEqual(m.DESTINATION.name, '阿舟 AI 实验室.app')
        self.assertEqual(result['installedPath'], str(m.DESTINATION))
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertFalse(legacy.exists())
        self.assertNotIn(legacy, self.registry[m.EXPECTED[0]])
        self.assertIn((m.LSREGISTER, '-u', str(legacy)), self.commands)
        self.assertEqual((m.fingerprint(official), m.fingerprint(unrelated)), preserved)
        self.assert_clean()

    def test_higher_version_is_preserved(self):
        m = self.module
        path = m.DESTINATION.parent / 'Future.app'
        self.bundle(path, version='0.6.0', build='1')
        before = m.fingerprint(path)
        with self.assertRaisesRegex(RuntimeError, '版本高于'):
            m.install()
        self.assertEqual(m.fingerprint(path), before)
        self.assertFalse(m.DESTINATION.exists())

    def test_unknown_source_same_id_is_preserved(self):
        m = self.module
        path = m.DESTINATION.parent / 'Unproven.app'
        self.bundle(path, marker=False)
        with self.assertRaisesRegex(RuntimeError, '不足以证明'):
            m.install()
        self.assertTrue(path.exists())
        self.assertFalse(m.DESTINATION.exists())

    def test_other_project_root_is_preserved(self):
        m = self.module
        path = self.clone(m.DESTINATION.parent / 'Other checkout.app')
        marker = path / m.HELPERS['MARKER']
        data = json.loads(marker.read_text())
        data['projectRoot'] = str(self.base / 'another-project')
        marker.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, '其他项目或路径'):
            m.install()
        self.assertTrue(path.exists())

    def test_explicit_source_handoff_replaces_exact_old_owner(self):
        m = self.module
        old_root, old_record = self.old_owned_install()
        with self.assertRaisesRegex(RuntimeError, '其他项目或路径'):
            m.install()
        result = m.install(migrate_from=str(old_root))
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['sourceHandoff']['oldSHA256'], old_record['sha256Tree'])
        self.assertEqual(result['sourceHandoff']['newRoot'], str(m.ROOT))
        self.assertEqual(m.HELPERS['read_marker'](m.DESTINATION)['projectRoot'], str(m.ROOT))
        self.assertEqual(m.install(True)['status'], 'current')
        self.assert_clean()

    def test_source_handoff_moves_verified_legacy_basename_to_new_canonical_path(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_root, old_record = self.old_owned_install(installed_path=legacy)
        self.assertFalse(m.DESTINATION.exists())

        result = m.install(migrate_from=str(old_root))

        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['sourceHandoff']['oldSHA256'], old_record['sha256Tree'])
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertFalse(legacy.exists())
        self.assertIn((m.LSREGISTER, '-u', str(legacy)), self.commands)
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assert_clean()

    def test_theme_rename_and_source_handoff_retire_the_verified_previous_name(self):
        m = self.module
        previous_name = m.DESTINATION.with_name('阿舟之前的主题.app')
        old_root, old_record = self.old_owned_install(installed_path=previous_name)
        result = m.install(migrate_from=str(old_root))
        self.assertEqual(result['sourceHandoff']['oldSHA256'], old_record['sha256Tree'])
        self.assertFalse(previous_name.exists())
        self.assertTrue(m.DESTINATION.is_dir())
        self.assert_clean()

    def test_theme_rename_handoff_retry_keeps_the_exact_old_entry_after_cleanup_failure(self):
        m = self.module
        previous_name = m.DESTINATION.with_name('阿舟之前的主题.app')
        old_root, _ = self.old_owned_install(installed_path=previous_name)
        self.fail_unregister_once.add(previous_name)
        with self.assertRaises(subprocess.CalledProcessError):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.read_receipt()['sourceHandoff']['oldInstalledPath'], str(previous_name))
        result = m.install(migrate_from=str(old_root))
        self.assertEqual(result['status'], 'consolidated')
        self.assertFalse(previous_name.exists())
        self.assert_clean()

    def test_theme_rename_handoff_cannot_adopt_an_entry_outside_managed_applications(self):
        m = self.module
        outside = self.base / 'unmanaged/阿舟.app'
        old_root, _ = self.old_owned_install(installed_path=outside)
        before = m.fingerprint(outside)
        with self.assertRaisesRegex(RuntimeError, '没有证明当前入口归属'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(outside), before)
        self.assertFalse(m.DESTINATION.exists())
        self.assertEqual(self.swap_calls, 0)

    def test_legacy_handoff_rechecks_old_owner_before_first_publication(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_root, _ = self.old_owned_install(installed_path=legacy)
        self.mutate_old_during_copy = old_root / '.build/azhou-payload'

        with self.assertRaisesRegex(RuntimeError, '不一致'):
            m.install(migrate_from=str(old_root))

        self.assertFalse(m.DESTINATION.exists())
        self.assertTrue(legacy.is_dir())
        self.assertEqual(self.registry[m.EXPECTED[0]], {legacy})
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))
        self.assertEqual(self.swap_calls, 0)

    def test_legacy_handoff_retry_finishes_after_publication_before_cleanup_receipt(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_root, _ = self.old_owned_install(installed_path=legacy)
        publish = m.install_payload

        def interrupt_after_publication(*args, **kwargs):
            publish(*args, **kwargs)
            raise RuntimeError('injected interruption after publication')

        with patch.object(m, 'install_payload', side_effect=interrupt_after_publication):
            with self.assertRaisesRegex(RuntimeError, 'injected interruption after publication'):
                m.install(migrate_from=str(old_root))
        self.assertEqual(m.read_receipt()['status'], 'source-handoff-pending')
        self.assertTrue(legacy.is_dir())

        result = m.install(migrate_from=str(old_root))
        self.assertEqual(result['registeredProjectPathCount'], 1)
        self.assertFalse(legacy.exists())
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assert_clean()

    def test_legacy_handoff_retry_finishes_after_old_entry_unregistration_fails(self):
        m = self.module
        legacy = m.DESTINATION.with_name('阿舟启动 Codex.app')
        old_root, old_record = self.old_owned_install(installed_path=legacy)
        self.fail_unregister_once.add(legacy)

        with self.assertRaises(subprocess.CalledProcessError):
            m.install(migrate_from=str(old_root))

        self.assertEqual(m.fingerprint(m.DESTINATION), m.fingerprint(m.SOURCE))
        self.assertTrue(legacy.is_dir())
        self.assertEqual(self.registry[m.EXPECTED[0]], {legacy})
        pending = m.read_receipt()
        self.assertEqual(pending['status'], 'cleanup-pending')
        self.assertEqual(pending['sourceHandoff']['oldRoot'], str(old_root))
        self.assertEqual(pending['sourceHandoff']['oldSHA256'], old_record['sha256Tree'])

        self.commands.clear()
        result = m.install(migrate_from=str(old_root))

        self.assertEqual(result['status'], 'consolidated')
        self.assertFalse(legacy.exists())
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assertIn((m.LSREGISTER, '-u', str(legacy)), self.commands)
        self.assert_clean()

    def test_legacy_handoff_retry_finishes_after_old_entry_removal_fails(self):
        m = self.module
        legacy, old_root = self.leave_pending_handoff_after_removal_failure()
        self.commands.clear()
        result = m.install(migrate_from=str(old_root))

        self.assertFalse(legacy.exists())
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assertEqual(result['registeredProjectPathCount'], 1)
        self.assert_clean()

    def test_handoff_can_retry_after_old_entry_is_removed_and_registration_fails(self):
        m = self.module
        previous = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        old_root, _ = self.old_owned_install(installed_path=previous)

        def fail_registration(command, **options):
            if command[0] == str(m.REGISTRY_TOOL) and command[1] == 'register':
                raise OSError('injected registration failure')
            return self.run_command(command, **options)

        with patch.object(m.subprocess, 'run', side_effect=fail_registration):
            with self.assertRaisesRegex(OSError, 'injected registration failure'):
                m.install(migrate_from=str(old_root))
        self.assertFalse(previous.exists())
        result = m.install(migrate_from=str(old_root))
        self.assertEqual(result['registeredProjectPathCount'], 1)
        self.assert_clean()

    def test_completed_handoff_can_be_repeated_after_old_entry_is_removed(self):
        m = self.module
        previous = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        old_root, _ = self.old_owned_install(installed_path=previous)
        m.install(migrate_from=str(old_root))
        self.assertFalse(previous.exists())
        self.assertEqual(m.install(migrate_from=str(old_root))['status'], 'current')
        self.assert_clean()

    def test_legacy_handoff_retry_accepts_only_new_entry_after_removal_fails(self):
        m = self.module
        legacy, old_root = self.leave_pending_handoff_after_removal_failure()
        self.registry[m.EXPECTED[0]].add(m.DESTINATION)
        self.commands.clear()

        result = m.install(migrate_from=str(old_root))

        self.assertFalse(legacy.exists())
        self.assertEqual(self.registry[m.EXPECTED[0]], {m.DESTINATION})
        self.assertEqual(result['registeredProjectPathCount'], 1)
        self.assert_clean()

    def test_handoff_retry_refuses_dangling_symlink_at_old_entry(self):
        m = self.module
        legacy, old_root = self.leave_pending_handoff_after_removal_failure()
        shutil.rmtree(legacy)
        legacy.symlink_to(self.base / 'missing-target', target_is_directory=True)
        with self.assertRaises(RuntimeError):
            m.install(migrate_from=str(old_root))
        self.assertTrue(legacy.is_symlink())

    def test_handoff_rejects_receipt_or_payload_mismatch(self):
        m = self.module
        old_root, record = self.old_owned_install()
        record['sha256Tree'] = '0' * 64
        (old_root / '.local/installation.json').write_text(json.dumps(record))
        before = m.fingerprint(m.DESTINATION)
        with self.assertRaisesRegex(RuntimeError, '不一致'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertEqual(self.swap_calls, 0)

    def test_handoff_rejects_invalid_old_icon_or_wallpaper(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        def fail(*args):
            raise RuntimeError('synthetic visual resource failure')
        for name in ('verify_icon', 'verify_wallpaper'):
            with self.subTest(validator=name):
                with patch.dict(m.HELPERS, {name: fail}):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic visual resource failure'):
                        m.old_install_proof(old_root)
        self.assertTrue(m.DESTINATION.is_dir())

    def test_handoff_rejects_other_registered_app(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        self.registry[m.EXPECTED[0]].add(self.base / 'elsewhere/Another.app')
        with self.assertRaisesRegex(RuntimeError, '超出清理范围'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(self.swap_calls, 0)

    def test_handoff_rejects_additional_verified_project_registration(self):
        m = self.module
        previous = m.DESTINATION.with_name('Previous.app')
        old_root, _ = self.old_owned_install(installed_path=previous)
        other = self.clone(m.DESTINATION.with_name('Another current app.app'))
        previous_hash, other_hash = m.fingerprint(previous), m.fingerprint(other)
        with self.assertRaisesRegex(RuntimeError, '旧应用登记不唯一'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(previous), previous_hash)
        self.assertEqual(m.fingerprint(other), other_hash)
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_handoff_rejects_missing_old_registration(self):
        m = self.module
        previous = m.DESTINATION.with_name('Previous.app')
        old_root, _ = self.old_owned_install(installed_path=previous)
        self.registry[m.EXPECTED[0]].discard(previous)
        before = m.fingerprint(previous)
        with self.assertRaisesRegex(RuntimeError, '旧应用登记不唯一'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(previous), before)
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_handoff_swap_failure_preserves_old_install(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'swap'
        with self.assertRaises(OSError):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertEqual(m.HELPERS['read_marker'](m.DESTINATION)['projectRoot'], str(old_root))

    def test_handoff_rechecks_old_payload_before_swap(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        before = m.fingerprint(m.DESTINATION)
        self.mutate_old_during_copy = old_root / '.build/azhou-payload'
        with self.assertRaisesRegex(RuntimeError, '不一致'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertEqual(self.swap_calls, 0)

    def test_official_and_unrelated_apps_are_excluded(self):
        m = self.module
        official = m.DESTINATION.parent / 'Codex.app'
        self.bundle(official, identity=('com.openai.codex', 'Codex'), marker=False)
        unrelated = m.DESTINATION.parent / 'Other.app'
        self.bundle(unrelated, identity=('org.example.other', 'Other'), marker=False)
        before = (m.fingerprint(official), m.fingerprint(unrelated))
        m.install()
        self.assertEqual(before, (m.fingerprint(official), m.fingerprint(unrelated)))
        self.assertFalse(any(str(official) in command or str(unrelated) in command for command in self.commands))
        self.assert_clean()

    def test_official_at_canonical_path_is_never_replaced(self):
        m = self.module
        self.bundle(m.DESTINATION, identity=('com.openai.codex', 'Codex'), marker=False)
        before = m.fingerprint(m.DESTINATION)
        with self.assertRaisesRegex(RuntimeError, '非项目应用'):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)

    def test_unknown_app_in_dist_blocks_cleanup(self):
        m = self.module
        other = m.DIST / 'Other.app'
        self.bundle(other, identity=('org.example.other', 'Other'), marker=False)
        with self.assertRaisesRegex(RuntimeError, '非项目应用'):
            m.install()
        self.assertTrue(other.exists())

    def test_symbolic_entry_is_preserved(self):
        m = self.module
        m.DESTINATION.parent.mkdir(parents=True)
        m.DESTINATION.symlink_to(m.SOURCE, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '符号链接'):
            m.install()
        self.assertTrue(m.DESTINATION.is_symlink())

    def test_running_renamed_copy_blocks_retirement(self):
        m = self.module
        alias = self.clone(m.DIST / 'Running copy.app')
        self.running = f'22 {alias}/Contents/MacOS/{m.EXPECTED[1]}\n'
        with self.assertRaisesRegex(RuntimeError, '仍在运行'):
            m.install()
        self.assertTrue(alias.exists())
        self.assertFalse(m.DESTINATION.exists())

    def test_running_canonical_entry_blocks_retirement_of_a_duplicate(self):
        m = self.module
        self.clone(m.DESTINATION)
        duplicate = self.clone(m.DIST / 'Duplicate.app')
        self.running = f'22 {m.DESTINATION}/Contents/MacOS/{m.EXPECTED[1]}\n'
        with self.assertRaisesRegex(RuntimeError, '仍在运行'):
            m.install()
        self.assertTrue(duplicate.is_dir())
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_empty_running_check_does_not_enumerate_processes(self):
        m = self.module
        with patch.object(m.subprocess, 'check_output', side_effect=OSError('should not inspect processes')) as inspect_processes:
            m.require_stopped([])
        inspect_processes.assert_not_called()

    def test_missing_directory_descriptor_support_stops_before_retirement(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        with patch.object(m.os, 'supports_dir_fd', set()):
            with self.assertRaisesRegex(RuntimeError, '目录描述符支持'):
                m.install()
        self.assertTrue(legacy.is_dir())
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_descriptor_fingerprint_matches_package_tree_fingerprint(self):
        m = self.module
        sample = self.base / 'descriptor-fingerprint'
        (sample / 'a/sub').mkdir(parents=True)
        (sample / 'a/sub/中文.txt').write_text('synthetic')
        (sample / 'a/file.txt').write_bytes(b'\x00\x01fixture')
        (sample / 'z.txt').write_text('other')
        (sample / 'z.txt').chmod(0o640)
        descriptor = os.open(sample, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.assertEqual(m._fingerprint_retirement_directory(descriptor), m.fingerprint(sample))
        finally:
            os.close(descriptor)

    def test_descriptor_fingerprint_orders_boundary_tree_like_package_fingerprint(self):
        m = self.module
        sample = self.base / 'boundary-fingerprint'
        (sample / 'web').mkdir(parents=True)
        (sample / 'web/index.html').write_text('page')
        # 目录名恰是同级文件名的前缀，且下一字符 '.' 排在 '/' 之前：
        # 组件序与 join 字符串序在此类树上分歧，fd 摘要必须与 fingerprint() 同序。
        (sample / 'web.config').write_text('config')
        (sample / 'zz last.txt').write_text('tail')
        descriptor = os.open(sample, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.assertEqual(m._fingerprint_retirement_directory(descriptor), m.fingerprint(sample))
        finally:
            os.close(descriptor)

    def test_descriptor_fingerprint_rejects_changes_during_read(self):
        m = self.module
        sample = self.base / 'changing-fingerprint'
        sample.mkdir()
        content = sample / 'file.txt'
        content.write_text('synthetic')
        descriptor = os.open(sample, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        actual_read = os.read
        changed = False

        def mutate_after_read(file_descriptor, size):
            nonlocal changed
            data = actual_read(file_descriptor, size)
            if not changed:
                changed = True
                with content.open('a') as stream:
                    stream.write(' changed')
            return data

        try:
            with patch.object(m.os, 'read', side_effect=mutate_after_read):
                with self.assertRaisesRegex(RuntimeError, '隔离文件在核验期间发生变化'):
                    m._fingerprint_retirement_directory(descriptor)
        finally:
            os.close(descriptor)

    def test_descriptor_fingerprint_does_not_block_on_fifo_replacement(self):
        m = self.module
        sample = self.base / 'fifo-fingerprint'
        sample.mkdir()
        content = sample / 'file.txt'
        content.write_text('synthetic')
        descriptor = os.open(sample, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        actual_open = os.open
        replaced = False

        def replace_before_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if path == 'file.txt' and not replaced:
                replaced = True
                content.unlink()
                os.mkfifo(content)
            return actual_open(path, flags, *args, **kwargs)

        try:
            with patch.object(m.os, 'open', side_effect=replace_before_open):
                with self.assertRaisesRegex(RuntimeError, '隔离文件在核验期间发生变化'):
                    m._fingerprint_retirement_directory(descriptor)
            self.assertTrue(replaced)
        finally:
            os.close(descriptor)

    def test_descriptor_fingerprint_refuses_cross_device_descendant(self):
        m = self.module
        sample = self.base / 'cross-device-fingerprint'
        sample.mkdir()
        (sample / 'file.txt').write_text('synthetic')
        descriptor = os.open(sample, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        actual_stat = os.stat

        class OtherDevice:
            def __init__(self, original):
                self.original = original
                self.st_dev = original.st_dev + 1

            def __getattr__(self, name):
                return getattr(self.original, name)

        def report_other_device(path, *args, **kwargs):
            value = actual_stat(path, *args, **kwargs)
            return OtherDevice(value) if path == 'file.txt' and kwargs.get('dir_fd') is not None else value

        try:
            with patch.object(m.os, 'stat', side_effect=report_other_device):
                with self.assertRaisesRegex(RuntimeError, '跨越文件系统边界'):
                    m._fingerprint_retirement_directory(descriptor)
        finally:
            os.close(descriptor)

    def test_install_cleanup_preserves_cross_device_payload(self):
        m = self.module
        directory = self.base / 'synthetic-install-stage'
        payload = directory / 'payload'
        payload.mkdir(parents=True)
        content = payload / 'kept.txt'
        content.write_text('synthetic')
        expected = m.fingerprint(payload)
        payload_inode = os.stat(payload).st_ino
        actual_fstat = os.fstat

        class OtherDevice:
            def __init__(self, original):
                self.original = original
                self.st_dev = original.st_dev + 1

            def __getattr__(self, name):
                return getattr(self.original, name)

        def report_other_device(fd):
            value = actual_fstat(fd)
            return OtherDevice(value) if value.st_ino == payload_inode else value

        with patch.object(m.os, 'fstat', side_effect=report_other_device):
            with patch.object(m, '_fingerprint_retirement_directory', side_effect=AssertionError('unexpected scan')):
                with self.assertRaisesRegex(RuntimeError, '跨越文件系统边界'):
                    m._clean_install_work(directory, expected, directory.stat(), payload.stat())
        self.assertEqual(content.read_text(), 'synthetic')

    def test_retirement_preserves_cross_device_payload(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        expected = m.fingerprint(legacy)
        payload_inode = os.stat(legacy).st_ino
        actual_fstat = os.fstat
        reported = False

        class OtherDevice:
            def __init__(self, original):
                self.original = original
                self.st_dev = original.st_dev + 1

            def __getattr__(self, name):
                return getattr(self.original, name)

        def report_other_device(fd):
            nonlocal reported
            value = actual_fstat(fd)
            if value.st_ino == payload_inode and not legacy.exists() and not reported:
                reported = True
                return OtherDevice(value)
            return value

        with patch.object(m.os, 'fstat', side_effect=report_other_device):
            with self.assertRaisesRegex(RuntimeError, '隔离副本无法验证') as raised:
                m.install()
        self.assertIn('跨越文件系统边界', str(raised.exception.__cause__))
        retained = list(legacy.parent.glob('.azhou-retire-*/payload'))
        self.assertEqual(len(retained), 1)
        self.assertEqual(m.fingerprint(retained[0]), expected)

    def test_unknown_registry_path_is_not_unregistered(self):
        m = self.module
        outside = self.base / 'outside/Old.app'
        self.registry[m.EXPECTED[0]].add(outside)
        with self.assertRaisesRegex(RuntimeError, '超出清理范围'):
            m.install()
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_check_is_read_only_and_rejects_duplicate(self):
        m = self.module
        self.clone(m.DESTINATION)
        duplicate = self.clone(m.DIST / 'Duplicate.app')
        with self.assertRaisesRegex(RuntimeError, '实体入口尚未唯一'):
            m.install(True)
        self.assertTrue(duplicate.exists())
        self.assertFalse((m.ROOT / '.local').exists())
        self.assertTrue(all(command[0] == '/usr/bin/codesign' for command in self.commands))

    def test_check_of_unique_install_does_not_write_receipt_or_register(self):
        m = self.module
        m.install()
        receipt = m.receipt_path().read_bytes()
        before = m.receipt_path().stat().st_mtime_ns
        self.commands.clear()
        self.assertEqual(m.install(True)['registeredProjectPathCount'], 1)
        self.assertEqual(m.receipt_path().read_bytes(), receipt)
        self.assertEqual(m.receipt_path().stat().st_mtime_ns, before)
        self.assertTrue(all(command[0] == '/usr/bin/codesign' for command in self.commands))

    def test_unique_state_revalidates_entry_and_detects_changed_source(self):
        m = self.module
        self.clone(m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        actual_fingerprint = m.fingerprint

        def changed_source(path):
            return '0' * 64 if path == m.SOURCE else actual_fingerprint(path)

        with patch.object(m, 'verify', wraps=m.verify) as verify, \
                patch.object(m, 'fingerprint', side_effect=changed_source):
            with self.assertRaisesRegex(RuntimeError, '规范安装与当前构建载荷不一致'):
                m.unique_state(info, digest, {})
        verify.assert_called_with(m.DESTINATION)

    def test_install_refuses_an_active_global_install_lock(self):
        m = self.module
        m.DESTINATION.parent.mkdir(parents=True)
        lock = m.DESTINATION.parent / '.azhou-startup-install.lock'
        with m.file_lock(lock):
            with self.assertRaisesRegex(RuntimeError, '另一个项目安装正在进行'):
                m.install()
        self.assertFalse(m.DESTINATION.exists())

    def test_install_reports_retirements_and_final_result_as_json_lines(self):
        m = self.module
        retired = self.old_pair()
        result = m.install()
        messages = [json.loads(line) for line in self.capture.getvalue().splitlines()]
        self.assertEqual(messages[-1], result)
        self.assertIn(str(retired), [entry['retiredPath'] for entry in messages[:-1]])
        self.assertTrue(all({'retiredPath', 'bundleID', 'sha256Tree', 'proof'} == set(entry)
                            for entry in messages[:-1]))

    def test_deleted_package_stale_registration_is_retryable(self):
        m = self.module
        old = self.old_pair()
        self.sticky_unregister.add(old)
        with self.assertRaisesRegex(RuntimeError, '登记尚未唯一'):
            m.install()
        self.assertFalse(old.exists())
        record = m.read_receipt()
        self.assertEqual(record['status'], 'cleanup-pending')
        self.assertIn(m.LEGACY_SHA256, record['managedFingerprints'])
        self.assertIn(str(old), [item['path'] for item in record['retiredArtifacts']])
        self.sticky_unregister.clear()
        self.assertEqual(m.install()['status'], 'consolidated')
        self.assert_clean()

    def test_stale_registration_is_not_cleaned_when_path_reappears(self):
        m = self.module
        retired = self.old_pair()
        self.sticky_unregister.add(retired)
        with self.assertRaisesRegex(RuntimeError, '登记尚未唯一'):
            m.install()
        self.sticky_unregister.clear()
        self.commands.clear()
        save = m.save_receipt

        def restore_path_after_receipt(record):
            save(record)
            if record.get('status') == 'cleanup-pending':
                retired.mkdir(parents=True)

        with patch.object(m, 'save_receipt', side_effect=restore_path_after_receipt):
            with self.assertRaisesRegex(RuntimeError, '登记目标已变化或没有退役凭据'):
                m.install()
        self.assertTrue(retired.is_dir())
        self.assertFalse(any(command[:2] == (str(m.REGISTRY_TOOL), 'register')
                             for command in self.commands))

    def test_source_change_during_copy_does_not_replace_old_install(self):
        m = self.module
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        old = self.old_pair()
        before = m.fingerprint(legacy)
        self.mutate_source_during_copy = True
        with self.assertRaisesRegex(RuntimeError, '复制期间发生变化'):
            m.install()
        self.assertEqual(m.fingerprint(legacy), before)
        self.assertTrue(old.exists())

    def test_atomic_swap_failure_preserves_original(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'swap'
        with self.assertRaises(OSError):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_upgrade_failure_preserves_foreign_target_without_exchange(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        actual_verify = m.verify
        saved = m.DESTINATION.with_name('saved-new')
        def replace_during_verification(path):
            if Path(path) == m.DESTINATION:
                m.DESTINATION.rename(saved)
                m.DESTINATION.mkdir()
                (m.DESTINATION / 'unknown.txt').write_text('keep')
                raise RuntimeError('injected verify failure')
            return actual_verify(path)
        with patch.object(m, 'verify', side_effect=replace_during_verification):
            with self.assertRaisesRegex(RuntimeError, '回滚未完成'):
                m.install_payload(digest, original)
        self.assertEqual((m.DESTINATION / 'unknown.txt').read_text(), 'keep')
        self.assertTrue(saved.is_dir())
        self.assertTrue(next(m.DESTINATION.parent.glob('.azhou-install-*/payload')).is_dir())
        self.assertEqual(self.swap_calls, 1)

    def test_upgrade_failure_preserves_foreign_stage_without_exchange(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        actual_verify = m.verify
        saved = {}
        def replace_during_verification(path):
            if Path(path) == m.DESTINATION:
                stage = next(m.DESTINATION.parent.glob('.azhou-install-*/payload'))
                saved['old'] = stage.with_name('saved-old')
                stage.rename(saved['old'])
                stage.mkdir()
                (stage / 'unknown.txt').write_text('keep')
                saved['foreign'] = stage
                raise RuntimeError('injected verify failure')
            return actual_verify(path)
        with patch.object(m, 'verify', side_effect=replace_during_verification):
            with self.assertRaisesRegex(RuntimeError, '回滚未完成'):
                m.install_payload(digest, original)
        self.assertEqual((saved['foreign'] / 'unknown.txt').read_text(), 'keep')
        self.assertTrue(saved['old'].is_dir())
        self.assertEqual(m.fingerprint(m.DESTINATION), digest)
        self.assertEqual(self.swap_calls, 1)

    def test_swap_error_after_exchange_preserves_both_positions(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        old_hash = m.fingerprint(m.DESTINATION)
        exchange = m.swap
        def exchange_then_fail(left, right):
            exchange(left, right)
            raise OSError('injected uncertain swap')
        with patch.object(m, 'swap', side_effect=exchange_then_fail):
            with self.assertRaisesRegex(RuntimeError, '交换结果未确认'):
                m.install_payload(digest, original)
        stage = next(m.DESTINATION.parent.glob('.azhou-install-*/payload'))
        self.assertEqual(m.fingerprint(stage), old_hash)
        self.assertEqual(m.fingerprint(m.DESTINATION), digest)
        self.assertEqual(self.swap_calls, 1)

    def test_upgrade_failure_preserves_replaced_transaction_root(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        actual_verify = m.verify
        saved = {}
        def replace_during_verification(path):
            if Path(path) == m.DESTINATION:
                root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
                saved['old'] = root.with_name('saved-transaction')
                root.rename(saved['old'])
                root.mkdir()
                (root / 'unknown.txt').write_text('keep')
                saved['foreign'] = root
                raise RuntimeError('injected verify failure')
            return actual_verify(path)
        with patch.object(m, 'verify', side_effect=replace_during_verification):
            with self.assertRaisesRegex(RuntimeError, '回滚未完成'):
                m.install_payload(digest, original)
        self.assertEqual((saved['foreign'] / 'unknown.txt').read_text(), 'keep')
        self.assertTrue((saved['old'] / 'payload').is_dir())
        self.assertEqual(m.fingerprint(m.DESTINATION), digest)
        self.assertEqual(self.swap_calls, 1)

    def test_failed_prepublication_callback_preserves_replaced_stage(self):
        m = self.module
        def replace_then_fail():
            root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
            stage = root / 'payload'
            stage.rename(root / 'saved-payload')
            stage.mkdir()
            (stage / 'unknown.txt').write_text('keep')
            raise RuntimeError('injected callback failure')
        with self.assertRaisesRegex(RuntimeError, 'injected callback failure'):
            m.install_payload(m.fingerprint(m.SOURCE), None, before_swap=replace_then_fail)
        stage = next(m.DESTINATION.parent.glob('.azhou-install-*/payload'))
        self.assertEqual((stage / 'unknown.txt').read_text(), 'keep')
        self.assertTrue((stage.parent / 'saved-payload').is_dir())
        self.assertFalse(m.DESTINATION.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'native exchange is a macOS API')
    def test_native_exchange_installs_verified_synthetic_payload(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        with patch.object(m, 'swap', m.HELPERS['swap']):
            m.install_payload(digest, original)
        self.assertEqual(m.fingerprint(m.DESTINATION), digest)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    @unittest.skipUnless(sys.platform == 'darwin', 'native exchange is a macOS API')
    def test_native_exchange_rolls_back_verified_synthetic_payload(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        old_hash = m.fingerprint(m.DESTINATION)
        actual_verify = m.verify
        def fail_after_exchange(path):
            if Path(path) == m.DESTINATION:
                raise RuntimeError('injected verify failure')
            return actual_verify(path)
        with patch.object(m, 'swap', m.HELPERS['swap']), patch.object(m, 'verify', side_effect=fail_after_exchange):
            with self.assertRaisesRegex(RuntimeError, 'injected verify failure'):
                m.install_payload(digest, original)
        self.assertEqual(m.fingerprint(m.DESTINATION), old_hash)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_post_swap_failure_rolls_back(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'verify'
        with self.assertRaises(subprocess.CalledProcessError):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_swap_rejects_entry_changed_after_final_check(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info = m.verify(m.SOURCE)
        source_hash = m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, source_hash, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        preserved = m.DESTINATION.with_name('saved-original')
        old_hash = m.fingerprint(m.DESTINATION)

        def replace_target():
            m.DESTINATION.rename(preserved)
            self.bundle(m.DESTINATION, version='0.5.0', build='2', body='different owner')

        with self.assertRaisesRegex(RuntimeError, '候选在核查后发生变化'):
            m.install_payload(source_hash, original, before_swap=replace_target)
        self.assertEqual(m.fingerprint(preserved), old_hash)
        self.assertEqual((m.DESTINATION / 'Contents/Resources/web/index.html').read_text(), 'different owner')
        self.assertEqual(self.swap_calls, 0)

    def test_swap_verification_does_not_block_on_fifo_info_plist(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        exchange = m.swap
        raced = False

        def replace_info_after_exchange(left, right):
            nonlocal raced
            exchange(left, right)
            if not raced:
                raced = True
                info_path = Path(left) / 'Contents/Info.plist'
                info_path.unlink()
                os.mkfifo(info_path)

        def timed_out(_signal, _frame):
            raise TimeoutError('displaced package validation blocked')

        previous = signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(3)
        try:
            with patch.object(m, 'swap', side_effect=replace_info_after_exchange):
                with self.assertRaisesRegex(RuntimeError, '回滚未完成'):
                    m.install_payload(digest, original)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        self.assertTrue(raced)
        staged = next(m.DESTINATION.parent.glob('.azhou-install-*/payload'))
        self.assertTrue((staged / 'Contents/Info.plist').is_fifo())
        self.assertEqual(m.fingerprint(m.DESTINATION), digest)

    def test_swap_cleanup_preserves_replaced_staging_entry(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        clean = m._clean_install_work
        observed = {}

        def replace_before_cleanup(directory, expected_hash, expected_root, expected_payload):
            payload = Path(directory) / 'payload'
            saved = payload.with_name('saved-original')
            payload.rename(saved)
            payload.mkdir()
            (payload / 'valuable-user-data.txt').write_text('keep')
            observed.update(payload=payload, saved=saved)
            return clean(directory, expected_hash, expected_root, expected_payload)

        with patch.object(m, '_clean_install_work', side_effect=replace_before_cleanup):
            with self.assertRaisesRegex(RuntimeError, '临时'):
                m.install_payload(digest, original)
        self.assertEqual((observed['payload'] / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertEqual((observed['saved'] / 'Contents/Resources/web/index.html').read_text(), 'known old')

    def test_swap_cleanup_preserves_identical_foreign_payload(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        clean = m._clean_install_work
        observed = {}
        def replace_before_cleanup(directory, expected_hash, expected_root, expected_payload):
            payload = Path(directory) / 'payload'
            saved = m.DESTINATION.parent / 'saved-original'
            payload.rename(saved)
            shutil.copytree(saved, payload)
            observed.update(payload=payload, saved=saved, inode=payload.stat().st_ino)
            return clean(directory, expected_hash, expected_root, expected_payload)
        with patch.object(m, '_clean_install_work', side_effect=replace_before_cleanup):
            with self.assertRaisesRegex(RuntimeError, '临时'):
                m.install_payload(digest, original)
        self.assertEqual(observed['payload'].stat().st_ino, observed['inode'])
        self.assertTrue(observed['saved'].is_dir())

    def test_swap_cleanup_preserves_stage_replaced_after_verification(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        candidates, _ = m.scan_apps(info, digest, m.read_receipt())
        original = next(entry for entry in candidates if entry['path'] == m.DESTINATION)
        clean_contents = m._remove_retirement_contents
        observed = {}

        def replace_after_verification(descriptor, *args, **kwargs):
            if not observed:
                directory = next(m.DESTINATION.parent.glob('.azhou-install-*'))
                payload = directory / 'payload'
                saved = directory / 'saved-original'
                payload.rename(saved)
                payload.mkdir()
                (payload / 'valuable-user-data.txt').write_text('keep')
                observed.update(payload=payload, saved=saved)
            return clean_contents(descriptor, *args, **kwargs)

        with patch.object(m, '_remove_retirement_contents', side_effect=replace_after_verification):
            with self.assertRaisesRegex(RuntimeError, '安装临时内容未清理'):
                m.install_payload(digest, original)
        self.assertEqual((observed['payload'] / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertEqual((observed['saved'] / 'Contents/Resources/web/index.html').read_text(), 'known old')

    def test_retirement_preserves_entry_changed_after_last_check(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        preserved = legacy.with_name('saved-original')
        old_hash = m.fingerprint(legacy)
        original_check = m.unchanged
        checks = 0

        def replace_after_check(entry):
            nonlocal checks
            original_check(entry)
            if entry['path'] == legacy:
                checks += 1
                if checks == 2:
                    legacy.rename(preserved)
                    legacy.mkdir()
                    (legacy / 'valuable-user-data.txt').write_text('keep')

        with patch.object(m, 'unchanged', side_effect=replace_after_check):
            with self.assertRaises(RuntimeError):
                m.install()
        self.assertEqual(m.fingerprint(preserved), old_hash)
        payload = Path(m.read_receipt()['retirementPending']['stage'])
        self.assertEqual((payload / 'valuable-user-data.txt').read_text(), 'keep')

    def test_retirement_and_recovery_do_not_block_on_fifo_info_plist(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        move = m.publish_exclusive
        raced = False

        def replace_info_after_isolation(source, destination):
            nonlocal raced
            move(source, destination)
            if Path(source) == legacy and Path(destination).name == 'payload' and not raced:
                raced = True
                info = Path(destination) / 'Contents/Info.plist'
                info.unlink()
                os.mkfifo(info)

        def timed_out(_signal, _frame):
            raise TimeoutError('FIFO validation blocked')

        previous = signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(3)
        try:
            with patch.object(m, 'publish_exclusive', side_effect=replace_info_after_isolation):
                with self.assertRaisesRegex(RuntimeError, '隔离副本无法验证'):
                    m.install()
            self.assertTrue(raced)
            payload = Path(m.read_receipt()['retirementPending']['stage'])
            self.assertTrue(payload.is_dir())
            with self.assertRaisesRegex(RuntimeError, '隔离副本无法验证'):
                m.install()
            self.assertTrue(payload.is_dir())
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_retirement_does_not_delete_replacement_of_isolated_directory(self):
        m = self.module
        self.old_pair()
        original_remove = m._remove_retirement_contents
        injected = {'path': None}

        def replace_isolation_after_open(descriptor, *args, **kwargs):
            if injected['path'] is None:
                pending = m.read_receipt()['retirementPending']
                payload = Path(pending['stage'])
                held = payload.with_name('saved-original')
                payload.rename(held)
                payload.mkdir()
                (payload / 'valuable-user-data.txt').write_text('keep')
                injected['path'] = payload
            return original_remove(descriptor, *args, **kwargs)

        with patch.object(m, '_remove_retirement_contents', side_effect=replace_isolation_after_open):
            with self.assertRaisesRegex(RuntimeError, '临时副本保留'):
                m.install()
        self.assertIsNotNone(injected['path'])
        self.assertEqual((injected['path'] / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertEqual((injected['path'].with_name('saved-original') / 'Contents/Resources/web/index.html').read_text(), 'known old')

    def test_retirement_preserves_file_replaced_after_fingerprint(self):
        m = self.module
        self.old_pair()
        original_remove = m._remove_retirement_contents
        injected = {'path': None}
        preserved = self.base / 'saved-original-index'

        def replace_file_after_verification(descriptor, *args, **kwargs):
            if injected['path'] is None:
                payload = Path(m.read_receipt()['retirementPending']['stage'])
                path = payload / 'Contents/Resources/web/index.html'
                path.rename(preserved)
                path.write_text('valuable replacement data')
                injected['path'] = path
            return original_remove(descriptor, *args, **kwargs)

        with patch.object(m, '_remove_retirement_contents', side_effect=replace_file_after_verification):
            with self.assertRaisesRegex(RuntimeError, '临时副本保留'):
                m.install()
        self.assertIsNotNone(injected['path'])
        self.assertEqual(injected['path'].read_text(), 'valuable replacement data')
        self.assertEqual(preserved.read_text(), 'known old')

    def test_retirement_preserves_payload_if_isolation_parent_is_replaced(self):
        m = self.module
        self.old_pair()
        original_remove = m._remove_retirement_contents
        injected = {'directory': None}

        def replace_parent(descriptor, *args, **kwargs):
            if injected['directory'] is None:
                payload = Path(m.read_receipt()['retirementPending']['stage'])
                directory = payload.parent
                held = directory.with_name(directory.name + '-saved')
                directory.rename(held)
                directory.mkdir()
                (held / 'payload').rename(payload)
                injected['directory'] = directory
            return original_remove(descriptor, *args, **kwargs)

        with patch.object(m, '_remove_retirement_contents', side_effect=replace_parent):
            with self.assertRaisesRegex(RuntimeError, '临时副本保留'):
                m.install()
        self.assertIsNotNone(injected['directory'])
        self.assertEqual((injected['directory'] / 'payload/Contents/Resources/web/index.html').read_text(), 'known old')

    def test_retirement_preserves_file_modified_before_unlink(self):
        m = self.module
        self.old_pair()
        original_remove, original_stat = m._remove_retirement_contents, os.stat
        state = {'started': False, 'checks': 0, 'path': None}

        def stat_with_change(path, *args, **kwargs):
            if path == 'index.html' and kwargs.get('dir_fd') is not None:
                state['checks'] += 1
                if state['checks'] == 2:
                    payload = Path(m.read_receipt()['retirementPending']['stage'])
                    state['path'] = payload / 'Contents/Resources/web/index.html'
                    with state['path'].open('a') as stream:
                        stream.write(' valuable new data')
            return original_stat(path, *args, **kwargs)

        def inspect_before_deletion(descriptor, *args, **kwargs):
            if state['started']:
                return original_remove(descriptor, *args, **kwargs)
            state['started'] = True
            with patch.object(m.os, 'stat', side_effect=stat_with_change):
                return original_remove(descriptor, *args, **kwargs)

        with patch.object(m, '_remove_retirement_contents', side_effect=inspect_before_deletion):
            with self.assertRaisesRegex(RuntimeError, '临时副本保留'):
                m.install()
        self.assertIsNotNone(state['path'])
        self.assertIn('valuable new data', state['path'].read_text())

    def test_interrupted_retirement_is_recovered_without_writing_during_check(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        receipt = m.receipt_path().read_bytes()
        with self.assertRaisesRegex(RuntimeError, '清理尚未恢复'):
            m.install(True)
        self.assertTrue(payload.is_dir())
        self.assertFalse(legacy.exists())
        self.assertEqual(m.receipt_path().read_bytes(), receipt)
        m.install()
        self.assertFalse(payload.parent.exists())
        self.assert_clean()

    def test_interrupted_retirement_preserves_modified_staged_copy(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        (payload / 'Contents/Resources/web/index.html').write_text('changed while isolated')
        self.commands.clear()
        with self.assertRaisesRegex(RuntimeError, '隔离副本无法验证'):
            m.install()
        self.assertFalse(legacy.exists())
        self.assertEqual((payload / 'Contents/Resources/web/index.html').read_text(), 'changed while isolated')
        self.assertFalse(any(command[0] == m.LSREGISTER for command in self.commands))

    def test_interrupted_retirement_preserves_conflicting_entry_and_staged_copy(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        legacy.mkdir()
        (legacy / 'valuable-user-data.txt').write_text('keep')
        with self.assertRaisesRegex(RuntimeError, '旧入口恢复受阻'):
            m.install()
        self.assertEqual((legacy / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertTrue(payload.is_dir())

    def test_retirement_recovery_preserves_stage_replaced_before_restore(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        held = payload.with_name('saved-original')
        original_move = m.publish_exclusive
        raced = False

        def replace_stage_before_move(source, destination):
            nonlocal raced
            if Path(source) == payload and Path(destination) == legacy and not raced:
                raced = True
                payload.rename(held)
                payload.mkdir()
                (payload / 'valuable-user-data.txt').write_text('keep')
            return original_move(source, destination)

        with patch.object(m, 'publish_exclusive', side_effect=replace_stage_before_move):
            with self.assertRaisesRegex(RuntimeError, '恢复|变化'):
                m.install()
        self.assertTrue(raced)
        self.assertTrue(held.is_dir())
        self.assertEqual((legacy / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertIn('retirementPending', m.read_receipt())

    def test_interrupted_retirement_rejects_stage_outside_its_parent(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        unrelated = self.base / 'unrelated/payload'
        unrelated.parent.mkdir()
        unrelated.mkdir()
        (unrelated / 'valuable-user-data.txt').write_text('keep')
        record = m.read_receipt()
        record['retirementPending']['stage'] = str(unrelated)
        m.save_receipt(record)
        with self.assertRaisesRegex(RuntimeError, '旧入口路径无效'):
            m.install()
        self.assertFalse(legacy.exists())
        self.assertTrue(payload.is_dir())
        self.assertEqual((unrelated / 'valuable-user-data.txt').read_text(), 'keep')

    def test_interrupted_retirement_rejects_symlinked_isolation_directory(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        directory = payload.parent
        preserved = self.base / 'preserved-isolation'
        directory.rename(preserved)
        directory.symlink_to(preserved, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '旧入口路径无效'):
            m.install()
        self.assertFalse(legacy.exists())
        self.assertTrue((preserved / 'payload').is_dir())
        self.assertTrue(directory.is_symlink())

    def test_interrupted_retirement_after_completed_deletion_can_retry(self):
        m = self.module
        _, payload = self.interrupted_retirement()
        shutil.rmtree(payload)
        m.install()
        self.assertFalse(payload.parent.exists())
        self.assert_clean()

    def test_interrupted_retirement_preserves_reappeared_path_after_deletion(self):
        m = self.module
        legacy, payload = self.interrupted_retirement()
        shutil.rmtree(payload)
        legacy.mkdir()
        (legacy / 'valuable-user-data.txt').write_text('keep')
        receipt = m.receipt_path().read_bytes()
        with self.assertRaisesRegex(RuntimeError, '旧入口恢复受阻'):
            m.install()
        self.assertEqual((legacy / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertEqual(m.receipt_path().read_bytes(), receipt)
        self.assertTrue(payload.parent.is_dir())

    def test_partial_retirement_failure_keeps_remaining_staged_content(self):
        m = self.module
        self.old_pair()
        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        def fail_after_partial_removal(_descriptor, *_args, **_kwargs):
            path = Path(m.read_receipt()['retirementPending']['stage'])
            (path / 'Contents/Resources/web/index.html').unlink()
            raise OSError('injected partial removal')

        with patch.object(m, '_remove_retirement_contents', side_effect=fail_after_partial_removal):
            with self.assertRaisesRegex(RuntimeError, '临时副本保留'):
                m.install()
        record = m.read_receipt()
        payload = Path(record['retirementPending']['stage'])
        self.assertTrue(payload.is_dir())
        self.assertFalse(legacy.exists())
        with self.assertRaisesRegex(RuntimeError, '隔离副本无法验证'):
            m.install()
        self.assertTrue(payload.is_dir())

    def test_retract_preserves_foreign_destination_in_place(self):
        m = self.module
        saved = m.DESTINATION.with_name('own-payload-saved')
        real_verify = m.verify
        def verify(path):
            if Path(path) == m.DESTINATION:
                m.DESTINATION.rename(saved)
                m.DESTINATION.mkdir()
                (m.DESTINATION / 'unknown.txt').write_text('keep')
                raise RuntimeError('injected verification failure')
            return real_verify(path)
        with patch.object(m, 'verify', side_effect=verify):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install_payload(m.fingerprint(m.SOURCE), None)
        self.assertEqual((m.DESTINATION / 'unknown.txt').read_text(), 'keep')
        self.assertTrue(saved.is_dir())
        self.assertEqual(len(list(m.DESTINATION.parent.glob('.azhou-install-*'))), 1)

    @unittest.skipUnless(sys.platform == 'darwin', 'renamex_np is a macOS API')
    def test_retract_does_not_replace_foreign_empty_stage(self):
        m = self.module
        real_verify = m.verify
        created = {}
        def verify(path):
            if Path(path) == m.DESTINATION:
                stage = next(m.DESTINATION.parent.glob('.azhou-install-*')) / 'payload'
                stage.mkdir()
                created['path'] = stage
                created['inode'] = stage.stat().st_ino
                raise RuntimeError('injected verification failure')
            return real_verify(path)
        with patch.object(m, 'verify', side_effect=verify), patch.object(m, 'publish_exclusive', self.native_publish_exclusive):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install_payload(m.fingerprint(m.SOURCE), None)
        self.assertEqual(created['path'].stat().st_ino, created['inode'])
        self.assertTrue(m.DESTINATION.is_dir())

    def test_retract_preserves_replaced_temporary_root(self):
        m = self.module
        real_verify = m.verify
        saved = {}
        def verify(path):
            if Path(path) == m.DESTINATION:
                root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
                saved['old'] = root.with_name('original-transaction')
                root.rename(saved['old'])
                root.mkdir()
                (root / 'unknown.txt').write_text('keep')
                saved['new'] = root
                raise RuntimeError('injected verification failure')
            return real_verify(path)
        with patch.object(m, 'verify', side_effect=verify):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install_payload(m.fingerprint(m.SOURCE), None)
        self.assertEqual((saved['new'] / 'unknown.txt').read_text(), 'keep')
        self.assertTrue(saved['old'].is_dir())
        self.assertTrue(m.DESTINATION.is_dir())

    def test_first_publication_preserves_replaced_stage_with_identical_contents(self):
        m = self.module
        saved = {}
        def replace_stage():
            root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
            stage = root / 'payload'
            saved['original'] = root / 'saved-payload'
            stage.rename(saved['original'])
            shutil.copytree(saved['original'], stage)
            saved['foreign'] = stage
            saved['inode'] = stage.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, '暂存发生变化'):
            m.install_payload(m.fingerprint(m.SOURCE), None, before_swap=replace_stage)
        self.assertFalse(m.DESTINATION.exists())
        self.assertTrue(saved['original'].is_dir())
        self.assertEqual(saved['foreign'].stat().st_ino, saved['inode'])

    def test_cleanup_preserves_replaced_temporary_root(self):
        m = self.module
        saved = {}
        def replace_root():
            root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
            saved['original'] = root.with_name('original-transaction')
            root.rename(saved['original'])
            root.mkdir()
            saved['foreign'] = root
            saved['inode'] = root.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, '暂存发生变化'):
            m.install_payload(m.fingerprint(m.SOURCE), None, before_swap=replace_root)
        self.assertFalse(m.DESTINATION.exists())
        self.assertTrue(saved['original'].is_dir())
        self.assertEqual(saved['foreign'].stat().st_ino, saved['inode'])

    def test_cleanup_preserves_empty_root_replaced_after_publication(self):
        m = self.module
        real_verify = m.verify
        saved = {}
        def verify(path):
            result = real_verify(path)
            if Path(path) == m.DESTINATION:
                root = next(m.DESTINATION.parent.glob('.azhou-install-*'))
                saved['original'] = root.with_name('original-transaction')
                root.rename(saved['original'])
                root.mkdir()
                saved['foreign'] = root
                saved['inode'] = root.stat().st_ino
            return result
        with patch.object(m, 'verify', side_effect=verify):
            with self.assertRaisesRegex(RuntimeError, '安装临时内容未清理'):
                m.install_payload(m.fingerprint(m.SOURCE), None)
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertTrue(saved['original'].is_dir())
        self.assertEqual(saved['foreign'].stat().st_ino, saved['inode'])

    def test_first_install_verification_failure_retracts_new_entry(self):
        m = self.module
        real_verify = m.verify

        def verify(path):
            if Path(path) == m.DESTINATION:
                raise RuntimeError('injected installed verification failure')
            return real_verify(path)

        with patch.object(m, 'verify', side_effect=verify):
            with self.assertRaisesRegex(RuntimeError, 'injected installed verification failure'):
                m.install()
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_failed_first_install_preserves_replacement_during_retraction(self):
        m = self.module
        saved = m.DESTINATION.with_name('saved-new-payload')
        actual_verify = m.verify

        def replace_during_verification(path):
            if Path(path) == m.DESTINATION:
                m.DESTINATION.rename(saved)
                m.DESTINATION.mkdir()
                (m.DESTINATION / 'valuable-user-data.txt').write_text('keep')
                raise RuntimeError('injected installed verification failure')
            return actual_verify(path)

        with patch.object(m, 'verify', side_effect=replace_during_verification):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install_payload(m.fingerprint(m.SOURCE), None)
        self.assertEqual((m.DESTINATION / 'valuable-user-data.txt').read_text(), 'keep')
        self.assertTrue(saved.is_dir())
        self.assertEqual(len(list(m.DESTINATION.parent.glob('.azhou-install-*'))), 1)

    def test_first_install_retraction_failure_preserves_recovery_directory(self):
        m = self.module
        real_verify, real_publish = m.verify, m.publish_exclusive

        def verify(path):
            if Path(path) == m.DESTINATION:
                raise RuntimeError('injected installed verification failure')
            return real_verify(path)

        def publish(source, destination):
            if Path(source) == m.DESTINATION and Path(destination).name == 'payload':
                raise OSError('injected retract failure')
            return real_publish(source, destination)

        with patch.object(m, 'verify', side_effect=verify), patch.object(m, 'publish_exclusive', side_effect=publish):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install()
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertEqual(len(list(m.DESTINATION.parent.glob('.azhou-install-*'))), 1)

    def test_rollback_failure_keeps_original_without_app_suffix(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'rollback'
        with self.assertRaisesRegex(RuntimeError, '回滚未完成'):
            m.install()
        temporary = list(m.DESTINATION.parent.glob('.azhou-install-*'))
        self.assertEqual(len(temporary), 1)
        self.assertEqual(m.fingerprint(temporary[0] / 'payload'), before)
        self.assertFalse(list(temporary[0].rglob('*.app')))

    def test_install_helper_boundaries_reject_bad_receipts_roots_and_locks(self):
        m = self.module
        with self.assertRaisesRegex(RuntimeError, '版本格式未知'):
            m.version_key({'CFBundleShortVersionString': 'future', 'CFBundleVersion': '3'})
        self.assertIsNone(m.managed_install_path(None))
        self.assertIsNone(m.managed_install_path('relative.app'))
        self.assertIsNone(m.managed_install_path(str(self.base / 'outside.app')))
        self.assertEqual(m.managed_install_path(str(m.DESTINATION)), m.DESTINATION)

        local = m.ROOT / '.local'
        link_target = self.base / 'receipt-dir'
        link_target.mkdir()
        local.symlink_to(link_target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '符号链接读取或写入安装记录'):
            m.receipt_path()
        local.unlink()
        local.mkdir()
        m.receipt_path().write_text('[]')
        with self.assertRaisesRegex(RuntimeError, '安装记录格式未知'):
            m.read_receipt()

        with self.assertRaisesRegex(RuntimeError, '安装锁目录不是实体目录'):
            with m.file_lock(self.base / 'missing-lock-dir/install.lock'):
                pass
        lock_link = self.base / 'lock-link'
        lock_link.symlink_to(link_target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '安装锁目录不是实体目录'):
            with m.file_lock(lock_link / 'install.lock'):
                pass
        lock_path = self.base / 'busy.lock'
        with m.file_lock(lock_path):
            with self.assertRaisesRegex(RuntimeError, '另一个项目安装正在进行'):
                with m.file_lock(lock_path):
                    pass

        with self.assertRaisesRegex(RuntimeError, '必须是不同于当前项目'):
            m.migration_root('relative-root')
        with self.assertRaisesRegex(RuntimeError, '必须是不同于当前项目'):
            m.migration_root(str(m.ROOT))
        old_root = self.base / 'old-project-root'
        old_root.mkdir()
        old_link = self.base / 'old-project-link'
        old_link.symlink_to(old_root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '必须是不同于当前项目'):
            m.migration_root(str(old_link))

        with self.assertRaisesRegex(RuntimeError, '旧安装记录目录不是实体目录'):
            with m.install_lock(False, old_root):
                pass

        trusted = {'projectID': m.PROJECT_ID, 'projectRoot': str(m.ROOT),
                   'status': 'source-handoff-pending'}
        source_hash = m.fingerprint(m.SOURCE)
        canonical_previous = {'oldRoot': str(old_root), 'newRoot': str(m.ROOT),
                              'newSHA256': source_hash, 'oldSHA256': 'a' * 64,
                              'oldInstalledPath': str(m.DESTINATION)}
        self.assertIsNone(m.pending_legacy_handoff(old_root, source_hash,
                                                   {**trusted, 'sourceHandoff': canonical_previous}))
        legacy_previous = {**canonical_previous,
                           'oldInstalledPath': str(m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME']))}
        self.assertIsNone(m.pending_legacy_handoff(
            old_root, source_hash,
            {**trusted, 'status': 'cleanup-pending', 'sourceHandoff': legacy_previous},
        ))

    def test_old_install_proof_and_pending_handoff_reject_untrusted_record_states(self):
        m = self.module
        old_root = self.base / 'empty-old-project'
        old_root.mkdir()
        with self.assertRaisesRegex(RuntimeError, '记录或构建载荷缺失'):
            m.old_install_proof(old_root)

        old_root, _ = self.old_owned_install()
        record_path = old_root / '.local/installation.json'
        valid = record_path.read_bytes()
        record_path.write_text('[]')
        with self.assertRaisesRegex(RuntimeError, '安装记录格式无效'):
            m.old_install_proof(old_root)
        record = json.loads(valid)
        record['status'] = 'unknown'
        record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError, '没有证明当前入口归属'):
            m.old_install_proof(old_root)

        record_path.write_bytes(valid)
        old_dist = old_root / 'dist'
        old_dist.write_text('not a directory')
        with self.assertRaisesRegex(RuntimeError, '旧输出目录不是实体目录'):
            m.old_install_proof(old_root)
        old_dist.unlink()
        old_dist.mkdir()
        (old_dist / 'remaining.app').mkdir()
        with self.assertRaisesRegex(RuntimeError, '旧输出目录仍有应用'):
            m.old_install_proof(old_root)

        shutil.rmtree(old_root)
        source_hash = m.fingerprint(m.SOURCE)
        self.assertIsNone(m.pending_legacy_handoff(old_root, source_hash, {}))
        trusted = {'projectID': m.PROJECT_ID, 'projectRoot': str(m.ROOT), 'status': 'cleanup-pending'}
        self.assertIsNone(m.pending_legacy_handoff(old_root, source_hash, trusted))

        legacy = m.DESTINATION.with_name(m.HELPERS['LEGACY_NAME'])
        old_root, old_record = self.old_owned_install(installed_path=legacy)
        source_hash = m.fingerprint(m.SOURCE)
        bad_previous = {'oldRoot': str(old_root), 'newRoot': str(m.ROOT), 'newSHA256': source_hash,
                        'oldSHA256': '0' * 64, 'oldInstalledPath': str(legacy)}
        bad_receipt = {**trusted, 'status': 'source-handoff-pending', 'sourceHandoff': bad_previous,
                       'retiredArtifacts': [{'path': str(legacy), 'bundleID': m.EXPECTED[0],
                                             'executable': m.EXPECTED[1], 'sha256Tree': '0' * 64,
                                             'proof': 'verified-source-handoff'}]}
        with self.assertRaisesRegex(RuntimeError, '待完成的来源接管记录不一致'):
            m.pending_legacy_handoff(old_root, source_hash, bad_receipt)

    def test_registry_inventory_rejects_ambiguous_or_malformed_results(self):
        m = self.module
        groups = [{'bundleID': identity[0], 'urls': []} for identity in m.KNOWN]
        hidden = {'bundleID': groups[0]['bundleID'], 'urls': [{'path': '/other/unknown.app'}]}
        cases = [
            {'schema': 1, 'applications': [hidden, *groups]},
            {'schema': 1, 'applications': [*groups, hidden]},
            {'schema': True, 'applications': groups},
            {'schema': 1, 'applications': {}},
            {'schema': 1, 'applications': [*groups, None]},
            {'schema': 1, 'applications': [dict(groups[0], urls={}), *groups[1:]]},
            {'schema': 1, 'applications': [dict(groups[0], urls=[None]), *groups[1:]]},
            {'schema': 1, 'applications': [dict(groups[0], urls=[{'path': None}]), *groups[1:]]},
            {'schema': 1, 'applications': [dict(groups[0], urls=[{'path': '/bad\x00name'}]), *groups[1:]]},
            {'schema': 1, 'applications': [dict(groups[0], bundleID=123), *groups[1:]]},
            None,
        ]
        for value in cases:
            with self.subTest(value=value), patch.object(m.subprocess, 'check_output', return_value=json.dumps(value)):
                with self.assertRaises(RuntimeError):
                    m.registry_inventory()
        with patch.object(m.subprocess, 'check_output', return_value='{'):
            with self.assertRaises(RuntimeError):
                m.registry_inventory()

    def test_registry_inventory_rejects_duplicate_json_keys(self):
        m = self.module
        groups = [{'bundleID': identity[0], 'urls': []} for identity in m.KNOWN]
        normal = json.dumps({'schema': 1, 'applications': groups})
        duplicated_schema = normal.replace('"schema": 1', '"schema": 1, "schema": 1', 1)
        duplicated_urls = normal.replace('"urls": []', '"urls": [{"path": "/other/unknown.app"}], "urls": []', 1)
        groups[0]['urls'] = [{'path': '/fixture/known.app'}]
        duplicated_path = json.dumps({'schema': 1, 'applications': groups}).replace(
            '"path": "/fixture/known.app"', '"path": "/other/unknown.app", "path": "/fixture/known.app"', 1)
        for raw in (duplicated_schema, duplicated_urls, duplicated_path):
            with self.subTest(raw=raw), patch.object(m.subprocess, 'check_output', return_value=raw):
                with self.assertRaises(RuntimeError):
                    m.registry_inventory()

    def test_installer_stops_before_publication_on_duplicate_inventory_group(self):
        m = self.module
        unknown = self.base / 'foreign.app'
        unknown.mkdir()
        (unknown / 'sentinel').write_text('keep')
        groups = [{'bundleID': identity[0], 'urls': []} for identity in m.KNOWN]
        hidden = {'bundleID': groups[0]['bundleID'], 'urls': [{'path': str(unknown)}]}
        result = json.dumps({'schema': 1, 'applications': [hidden, *groups]})
        with patch.object(m.subprocess, 'check_output', return_value=result), patch.object(m, 'install_payload') as publish:
            with self.assertRaisesRegex(RuntimeError, '重复'):
                m.install()
            publish.assert_not_called()
        self.assertEqual((unknown / 'sentinel').read_text(), 'keep')
        self.assertFalse(m.DESTINATION.exists())

    def test_registry_inventory_accepts_complete_groups_and_deduplicates_paths(self):
        m = self.module
        groups = [{'bundleID': identity[0], 'urls': []} for identity in m.KNOWN]
        groups[0]['urls'] = [{'path': '/fixture/one.app', 'other': 4}, {'path': '/fixture/one.app'}]
        with patch.object(m.subprocess, 'check_output', return_value=json.dumps({'schema': 1, 'applications': groups, 'other': 2})):
            inventory = m.registry_inventory()
        self.assertEqual(inventory[groups[0]['bundleID']], {Path('/fixture/one.app')})
        self.assertEqual(set(inventory), {item['bundleID'] for item in groups})

    def test_scan_and_registry_inventory_reject_unsafe_managed_entries(self):
        m = self.module
        app_parent = m.DESTINATION.parent
        outside = self.base / 'outside-applications'
        outside.mkdir()
        app_parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, '符号链接目录'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), {})
        app_parent.unlink()

        m.DIST.write_text('not a directory')
        with self.assertRaisesRegex(RuntimeError, '应用目录不是目录'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), {})
        m.DIST.unlink()
        m.DIST.mkdir()
        (m.DIST / 'linked.app').symlink_to(m.SOURCE, target_is_directory=True)
        (m.DIST / 'unreadable.app').mkdir()

        mismatched = m.DIST / 'mismatched.app'
        info = {'CFBundleIdentifier': m.EXPECTED[0], 'CFBundleExecutable': 'UnexpectedExecutable',
                'CFBundlePackageType': 'APPL'}
        executable = mismatched / 'Contents/Info.plist'
        executable.parent.mkdir(parents=True)
        executable.write_bytes(plistlib.dumps(info))

        missing_web = m.DIST / 'missing-web.app'
        self.bundle(missing_web)
        (missing_web / 'Contents/Resources/web/index.html').unlink()

        with self.assertRaisesRegex(RuntimeError, '应用归属或版本存在冲突'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), {})

        valid_groups = [{'bundleID': identity[0], 'urls': []} for identity in m.KNOWN]
        with patch.object(m.subprocess, 'check_output', return_value=json.dumps({'schema': 2,
                                                                                 'applications': valid_groups})):
            with self.assertRaisesRegex(RuntimeError, '返回未知格式'):
                m.registry_inventory()
        with patch.object(m.subprocess, 'check_output', return_value=json.dumps({'schema': 1,
                                                                                 'applications': valid_groups[:-1]})):
            with self.assertRaisesRegex(RuntimeError, '没有覆盖全部已知项目 ID'):
                m.registry_inventory()
        relative_groups = [dict(item) for item in valid_groups]
        relative_groups[0] = {'bundleID': m.KNOWN[0][0], 'urls': [{'path': 'relative.app'}]}
        with patch.object(m.subprocess, 'check_output', return_value=json.dumps({'schema': 1,
                                                                                 'applications': relative_groups})):
            with self.assertRaisesRegex(RuntimeError, '非绝对路径'):
                m.registry_inventory()

    def test_scan_refuses_fifo_info_plist_without_blocking(self):
        m = self.module
        info, digest = m.verify(m.SOURCE), m.fingerprint(m.SOURCE)
        contents = m.DIST / 'fifo.app/Contents'
        contents.mkdir(parents=True)
        os.mkfifo(contents / 'Info.plist')

        def timed_out(_signal, _frame):
            raise TimeoutError('candidate scan blocked on FIFO')

        previous = signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(3)
        try:
            with self.assertRaisesRegex(RuntimeError, '无法核实的应用已保留'):
                m.scan_apps(info, digest, {})
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        self.assertTrue((contents / 'Info.plist').is_fifo())

    def test_scan_preserves_non_directory_at_canonical_entry_and_unchanged_checks_fingerprint(self):
        m = self.module
        m.DESTINATION.parent.mkdir(parents=True)
        m.DESTINATION.write_text('not an app bundle')
        with self.assertRaisesRegex(RuntimeError, '规范入口不是实体应用'):
            m.scan_apps(m.verify(m.SOURCE), m.fingerprint(m.SOURCE), {})

        info = m.verify(m.SOURCE)
        entry = {'path': m.SOURCE, 'identity': m.EXPECTED,
                 'versionKey': m.version_key(info), 'sha256Tree': '0' * 64}
        with self.assertRaisesRegex(RuntimeError, '候选在核查后发生变化'):
            m.unchanged(entry)

    def test_install_rejects_conflicting_modes_invalid_payload_and_mutating_source(self):
        m = self.module
        old_root = self.base / 'old-for-mode-check'
        old_root.mkdir()
        with self.assertRaisesRegex(RuntimeError, '只读检查与来源接管不能同时执行'):
            m.install(True, str(old_root))

        app_source = self.base / 'not-a-payload.app'
        app_source.mkdir()
        with patch.object(m, 'SOURCE', app_source), self.assertRaisesRegex(RuntimeError, '无 .app 后缀'):
            m.install()

        actual = m.fingerprint(m.SOURCE)
        calls = 0
        def change_between_checks(_path):
            nonlocal calls
            calls += 1
            return actual if calls == 1 else 'f' * 64
        with patch.object(m, 'fingerprint', side_effect=change_between_checks), \
                self.assertRaisesRegex(RuntimeError, '核查期间发生变化'):
            m.install()
        self.assertEqual(calls, 2)

    def test_install_rejects_symlinked_build_directory_before_publication(self):
        m = self.module
        build = m.SOURCE.parent
        elsewhere = self.base / 'external-build'
        build.rename(elsewhere)
        build.symlink_to(elsewhere, target_is_directory=True)
        with patch.object(m, 'install_payload') as publish:
            with self.assertRaisesRegex(RuntimeError, '实体载荷'):
                m.install()
        publish.assert_not_called()
        self.assertFalse(m.DESTINATION.exists())

    def test_recheck_handoff_rejects_entry_path_change_after_proof(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        expected = m.old_install_proof(old_root)
        alternate = m.DESTINATION.with_name('Verified alternate.app')
        shutil.copytree(m.DESTINATION, alternate)
        record_path = old_root / '.local/installation.json'
        record = json.loads(record_path.read_text())
        record['installedPath'] = str(alternate)
        record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError, '归属在交换前发生变化'):
            m.recheck_handoff(old_root, expected)

    def test_new_entry_arriving_before_publication_is_preserved(self):
        m = self.module
        source_hash = m.fingerprint(m.SOURCE)
        created = {}

        def create_competing_entry():
            m.DESTINATION.mkdir()
            created['inode'] = m.DESTINATION.stat().st_ino

        with self.assertRaisesRegex(RuntimeError, '规范入口被其他操作创建'):
            m.install_payload(source_hash, None, before_swap=create_competing_entry)
        self.assertEqual(m.DESTINATION.stat().st_ino, created['inode'])
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    @unittest.skipUnless(sys.platform == 'darwin', 'renamex_np is a macOS API')
    def test_native_publication_preserves_entry_created_before_rename(self):
        m = self.module
        source_hash = m.fingerprint(m.SOURCE)
        created = {}

        def create_competing_entry():
            m.DESTINATION.mkdir()
            created['inode'] = m.DESTINATION.stat().st_ino

        with patch.object(m, 'publish_exclusive', self.native_publish_exclusive):
            with self.assertRaisesRegex(RuntimeError, '规范入口被其他操作创建'):
                m.install_payload(source_hash, None, before_swap=create_competing_entry)
        self.assertEqual(m.DESTINATION.stat().st_ino, created['inode'])
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    @unittest.skipUnless(sys.platform == 'darwin', 'renamex_np is a macOS API')
    def test_native_publication_refuses_existing_directory_and_symlink(self):
        source, destination = self.base / 'source', self.base / 'destination'
        source.mkdir()
        destination.mkdir()
        with self.assertRaisesRegex(RuntimeError, '规范入口被其他操作创建'):
            self.native_publish_exclusive(source, destination)
        self.assertTrue(source.is_dir())
        self.assertTrue(destination.is_dir())
        destination.rmdir()
        destination.symlink_to(self.base / 'missing')
        with self.assertRaisesRegex(RuntimeError, '规范入口被其他操作创建'):
            self.native_publish_exclusive(source, destination)
        self.assertTrue(source.is_dir())
        self.assertTrue(destination.is_symlink())
        destination.unlink()
        self.native_publish_exclusive(source, destination)
        self.assertFalse(source.exists())
        self.assertTrue(destination.is_dir())

    @unittest.skipUnless(sys.platform == 'darwin', 'renamex_np is a macOS API')
    def test_native_exclusive_rename_installs_and_retires_verified_pair(self):
        m = self.module
        self.old_pair()
        with patch.object(m, 'publish_exclusive', self.native_publish_exclusive):
            self.assertEqual(m.install()['status'], 'installed')
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-retire-*')))
        self.assertFalse(list(m.DIST.glob('.azhou-retire-*')))
        self.assert_clean()

    def test_new_install_payload_rolls_back_or_preserves_temporary_after_failed_retraction(self):
        m = self.module
        source_hash = m.fingerprint(m.SOURCE)
        real_verify = m.verify

        def fail_published_app(path):
            if Path(path) == m.DESTINATION:
                raise RuntimeError('injected installed-entry verification failure')
            return real_verify(path)

        with patch.object(m, 'verify', side_effect=fail_published_app):
            with self.assertRaisesRegex(RuntimeError, 'installed-entry verification failure'):
                m.install_payload(source_hash, None)
        self.assertFalse(m.DESTINATION.exists())
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

        real_rename = os.rename
        def fail_retraction(source, destination):
            if Path(source) == m.DESTINATION and Path(destination).name == 'payload':
                raise OSError('injected retraction failure')
            return real_rename(source, destination)

        with patch.object(m, 'verify', side_effect=fail_published_app), \
                patch.object(m.os, 'rename', side_effect=fail_retraction):
            with self.assertRaisesRegex(RuntimeError, '撤回未完成'):
                m.install_payload(source_hash, None)
        retained = list(m.DESTINATION.parent.glob('.azhou-install-*'))
        self.assertEqual(len(retained), 1)
        self.assertTrue(m.DESTINATION.is_dir())
        self.assertTrue(retained[0].is_dir())
        shutil.rmtree(m.DESTINATION)
        shutil.rmtree(retained[0])

    def test_failed_copy_preserves_unverified_temporary_content(self):
        m = self.module
        digest = m.fingerprint(m.SOURCE)

        def fail_ditto(command, **options):
            if command[0] == '/usr/bin/ditto':
                payload = Path(command[2])
                payload.mkdir(parents=True)
                (payload / 'unverified-data.txt').write_text('keep')
                raise OSError('injected partial copy')
            return self.run_command(command, **options)

        with patch.object(m.subprocess, 'run', side_effect=fail_ditto):
            with self.assertRaisesRegex(RuntimeError, '安装临时内容未清理'):
                m.install_payload(digest, None)
        preserved = list(m.DESTINATION.parent.glob('.azhou-install-*/payload/unverified-data.txt'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_text(), 'keep')
        self.assertFalse(m.DESTINATION.exists())

    def test_source_change_during_copy_preserves_canonical_path(self):
        m = self.module
        old = self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.mutate_source_during_copy = True
        with self.assertRaisesRegex(RuntimeError, '复制期间发生变化'):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertTrue(old.exists())

    def test_verified_050_pair_migrates_to_one_app_at_canonical_path(self):
        self.old_pair = partial(self.old_pair, installed_path=self.module.DESTINATION)
        self.test_verified_050_pair_migrates_to_one_app()

    def test_upgrade_registers_canonical_without_unregistering_it_at_canonical_path(self):
        self.old_pair = partial(self.old_pair, installed_path=self.module.DESTINATION)
        self.test_upgrade_registers_canonical_without_unregistering_it()

    def test_pending_upgrade_repairs_canonical_registration_without_unregister_at_canonical_path(self):
        self.old_pair = partial(self.old_pair, installed_path=self.module.DESTINATION)
        self.test_pending_upgrade_repairs_canonical_registration_without_unregister()

    def test_pending_upgrade_refreshes_metadata_when_registry_url_is_already_correct_at_canonical_path(self):
        self.old_pair = partial(self.old_pair, installed_path=self.module.DESTINATION)
        self.test_pending_upgrade_refreshes_metadata_when_registry_url_is_already_correct()

    def test_deleted_package_stale_registration_is_retryable_at_canonical_path(self):
        self.old_pair = partial(self.old_pair, installed_path=self.module.DESTINATION)
        self.test_deleted_package_stale_registration_is_retryable()


if __name__ == '__main__':
    print('Scope: isolated filesystem tests; exclusive rename is native on macOS; codesign, ditto, registry and atomic swap are mocked.')
    unittest.main(verbosity=2)

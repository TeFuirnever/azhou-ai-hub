#!/usr/bin/env python3
"""Isolated installer regression tests; macOS commands are mocked, not validated."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
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
        self.output = contextlib.redirect_stdout(self.capture)
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

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
            if Path(path) == legacy and fail_once['pending']:
                fail_once['pending'] = False
                raise OSError('injected old entry removal failure')
            return real_rmtree(path, *args, **kwargs)

        with patch.object(m.shutil, 'rmtree', side_effect=fail_old_entry_once):
            with self.assertRaisesRegex(OSError, 'injected old entry removal failure'):
                m.install(migrate_from=str(old_root))
        self.assertTrue(legacy.is_dir())
        self.assertEqual(self.registry[m.EXPECTED[0]], set())
        return legacy, old_root

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

    def test_handoff_rejects_other_registered_app(self):
        m = self.module
        old_root, _ = self.old_owned_install()
        self.registry[m.EXPECTED[0]].add(self.base / 'elsewhere/Another.app')
        with self.assertRaisesRegex(RuntimeError, '超出清理范围'):
            m.install(migrate_from=str(old_root))
        self.assertEqual(self.swap_calls, 0)

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

    def test_post_swap_failure_rolls_back(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'verify'
        with self.assertRaises(subprocess.CalledProcessError):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_rollback_failure_keeps_original_without_app_suffix(self):
        m = self.module
        self.old_pair(installed_path=m.DESTINATION)
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'rollback'
        with self.assertRaisesRegex(RuntimeError, '原包保留'):
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


if __name__ == '__main__':
    print('Scope: isolated filesystem tests; codesign, ditto, NSWorkspace registry and atomic syscall are mocked.')
    unittest.main(verbosity=2)

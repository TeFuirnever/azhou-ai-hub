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

    def old_pair(self):
        m = self.module
        self.bundle(m.DESTINATION, version='0.5.0', build='2', marker=False, body='known old')
        old = self.clone(m.DIST / m.HELPERS['NAME'], m.DESTINATION)
        self.registry[m.EXPECTED[0]].add(m.DESTINATION)
        # Test packages contain no private assets; pin their own known digest.
        m.LEGACY_SHA256 = m.fingerprint(m.DESTINATION)
        record = m.receipt_path()
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({'sha256Tree': m.LEGACY_SHA256, 'installedPath': str(m.DESTINATION),
                                      'sourcePath': str(old), 'bundleID': m.EXPECTED[0], 'version': '0.5.0'}))
        return old

    def old_owned_install(self):
        m = self.module
        old_root = self.base / 'old-project'
        old_root.mkdir()
        old_root = old_root.resolve()
        self.bundle(m.DESTINATION, version='0.5.0', build='2', body='old owner')
        marker_path = m.DESTINATION / m.HELPERS['MARKER']
        marker = json.loads(marker_path.read_text())
        marker['projectRoot'] = str(old_root)
        marker_path.write_text(json.dumps(marker))
        old_source = old_root / '.build/azhou-payload'
        old_source.parent.mkdir(parents=True)
        shutil.copytree(m.DESTINATION, old_source)
        old_hash = m.fingerprint(m.DESTINATION)
        record = {'schema': 2, 'projectID': m.PROJECT_ID, 'projectRoot': str(old_root),
                  'status': 'installed', 'installedPath': str(m.DESTINATION),
                  'sourcePath': str(old_source), 'sha256Tree': old_hash,
                  'bundleID': m.EXPECTED[0], 'executable': m.EXPECTED[1],
                  'version': '0.5.0', 'build': '2'}
        (old_root / '.local').mkdir()
        (old_root / '.local/installation.json').write_text(json.dumps(record))
        self.registry[m.EXPECTED[0]].add(m.DESTINATION)
        return old_root, record

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
        old = self.old_pair()
        before = m.fingerprint(m.DESTINATION)
        self.mutate_source_during_copy = True
        with self.assertRaisesRegex(RuntimeError, '复制期间发生变化'):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertTrue(old.exists())

    def test_atomic_swap_failure_preserves_original(self):
        m = self.module
        self.old_pair()
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'swap'
        with self.assertRaises(OSError):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_post_swap_failure_rolls_back(self):
        m = self.module
        self.old_pair()
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'verify'
        with self.assertRaises(subprocess.CalledProcessError):
            m.install()
        self.assertEqual(m.fingerprint(m.DESTINATION), before)
        self.assertFalse(list(m.DESTINATION.parent.glob('.azhou-install-*')))

    def test_rollback_failure_keeps_original_without_app_suffix(self):
        m = self.module
        self.old_pair()
        before = m.fingerprint(m.DESTINATION)
        self.failure = 'rollback'
        with self.assertRaisesRegex(RuntimeError, '原包保留'):
            m.install()
        temporary = list(m.DESTINATION.parent.glob('.azhou-install-*'))
        self.assertEqual(len(temporary), 1)
        self.assertEqual(m.fingerprint(temporary[0] / 'payload'), before)
        self.assertFalse(list(temporary[0].rglob('*.app')))


if __name__ == '__main__':
    print('Scope: isolated filesystem tests; codesign, ditto, NSWorkspace registry and atomic syscall are mocked.')
    unittest.main(verbosity=2)

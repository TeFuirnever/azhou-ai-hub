#!/usr/bin/env python3
"""Isolated build publication and cleanup safety checks; no installed app or private assets."""
from __future__ import annotations

import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent / 'verify-artifacts.py'
spec = importlib.util.spec_from_file_location('build_safety_verifier', SOURCE)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
lock_spec = importlib.util.spec_from_file_location('build_lock', SOURCE.parent / 'build-lock.py')
build_lock = importlib.util.module_from_spec(lock_spec)
lock_spec.loader.exec_module(build_lock)
startup_spec = importlib.util.spec_from_file_location('startup_builder', SOURCE.parent / 'build-startup.py')
startup_builder = importlib.util.module_from_spec(startup_spec)
startup_spec.loader.exec_module(startup_builder)


def fake_swap(left, right):
    middle = left.parent / '.synthetic-swap'
    os.rename(left, middle)
    os.rename(right, left)
    os.rename(middle, right)


class BuildSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent-skin-build-safety-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / '.build'
        self.build.mkdir()
        self.stage_root = self.build / 'azhou-stage.synthetic'
        self.stage_root.mkdir()
        self.stage = self.stage_root / 'azhou-payload'
        self.stage.mkdir()
        (self.stage / 'new.txt').write_bytes(b'new synthetic payload')
        self.target = self.build / 'azhou-payload'
        self.root_patch = mock.patch.object(verifier, 'ROOT', self.root)
        self.target_patch = mock.patch.object(verifier, 'PAYLOAD', self.target)
        self.root_patch.start(); self.addCleanup(self.root_patch.stop)
        self.target_patch.start(); self.addCleanup(self.target_patch.stop)
        self.registry = self.build / 'azhou-install-registry'
        self.registry_patch = mock.patch.object(verifier, 'REGISTRY_TOOL', self.registry)
        self.registry_patch.start(); self.addCleanup(self.registry_patch.stop)

    def existing_payload(self):
        self.target.mkdir()
        (self.target / 'old.txt').write_bytes(b'old synthetic payload')

    def publish(self, check):
        with mock.patch.object(verifier, 'verify_product'), mock.patch.object(verifier, 'check_inputs'), \
             mock.patch.object(verifier, 'check', side_effect=check), mock.patch.object(verifier, 'swap', side_effect=fake_swap):
            verifier.publish(self.stage)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'requires POSIX FIFO')
    def test_file_receipt_rejects_fifo_inserted_before_open_without_blocking(self):
        path = self.root / 'raced-file'
        program = r"""
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('fixture', sys.argv[1])
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
p = Path(sys.argv[2]); p.write_bytes(b'original')
original = os.open
def race(path, flags, *args, **kwargs):
    if Path(path) == p:
        p.rename(p.with_name('saved')); os.mkfifo(p)
    return original(path, flags, *args, **kwargs)
os.open = race
try:
    try: v.file_receipt(p)
    except RuntimeError: pass
    else: raise AssertionError('replacement accepted')
finally: os.open = original
assert p.is_fifo() and p.with_name('saved').read_bytes() == b'original'
"""
        result = subprocess.run([sys.executable, '-c', program, str(SOURCE), str(path)],
                                capture_output=True, text=True, timeout=4)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_file_receipt_preserves_replacement_after_read(self):
        path = self.root / 'raced-file'
        path.write_bytes(b'original')
        fstat = verifier.os.fstat
        calls = 0
        def replace_after_read(fd):
            nonlocal calls
            result = fstat(fd)
            calls += 1
            if calls == 2:
                path.rename(path.with_name('saved'))
                path.write_bytes(b'foreign')
            return result
        with mock.patch.object(verifier.os, 'fstat', side_effect=replace_after_read):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                verifier.file_receipt(path)
        self.assertEqual(path.read_bytes(), b'foreign')
        self.assertEqual(path.with_name('saved').read_bytes(), b'original')

    def test_native_exchange_on_synthetic_directories(self):
        self.existing_payload()
        verifier.swap(self.stage, self.target)
        self.assertEqual((self.stage / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')

    def test_unknown_file_added_to_old_payload_is_not_removed(self):
        self.existing_payload()
        def add_unknown():
            (self.stage / 'foreign.txt').write_bytes(b'unknown')
        with self.assertRaisesRegex(RuntimeError, '保留'):
            self.publish(add_unknown)
        self.assertEqual((self.stage / 'foreign.txt').read_bytes(), b'unknown')
        self.assertEqual((self.stage / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')

    def test_upgrade_success_cleans_only_verified_previous_payload(self):
        self.existing_payload()
        self.publish(lambda: None)
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertFalse(self.stage.exists())
        self.assertFalse((self.stage_root / '.preserve-original').exists())

    def test_replaced_stage_after_swap_preserves_unknown_and_old(self):
        self.existing_payload()
        moved = self.stage_root / 'old-payload-moved'
        def replace_after_check():
            self.stage.rename(moved)
            self.stage.mkdir()
            (self.stage / 'foreign.txt').write_bytes(b'unknown synthetic data')
        with self.assertRaisesRegex(RuntimeError, '保留'):
            self.publish(replace_after_check)
        self.assertEqual((self.stage / 'foreign.txt').read_bytes(), b'unknown synthetic data')
        self.assertEqual((moved / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertTrue((self.stage_root / '.preserve-original').exists())

    def test_target_replaced_during_swap_is_preserved(self):
        self.existing_payload()
        moved = self.build / 'old-target-moved'
        def raced_swap(left, right):
            right.rename(moved)
            right.mkdir()
            (right / 'foreign.txt').write_bytes(b'unknown target')
            fake_swap(left, right)
        with mock.patch.object(verifier, 'verify_product'), mock.patch.object(verifier, 'check_inputs'),              mock.patch.object(verifier, 'swap', side_effect=raced_swap):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                verifier.publish(self.stage)
        self.assertEqual((moved / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.stage / 'foreign.txt').read_bytes(), b'unknown target')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertTrue((self.stage_root / '.preserve-original').exists())

    def test_failed_rollback_preserves_both_verified_payloads(self):
        self.existing_payload()
        calls = 0
        def failing_swap(left, right):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('synthetic rollback failure')
            fake_swap(left, right)
        with mock.patch.object(verifier, 'verify_product'), mock.patch.object(verifier, 'check_inputs'),              mock.patch.object(verifier, 'check', side_effect=RuntimeError('check failed')),              mock.patch.object(verifier, 'swap', side_effect=failing_swap):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                verifier.publish(self.stage)
        self.assertEqual((self.stage / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertTrue((self.stage_root / '.preserve-original').exists())

    def test_check_failure_rolls_back_only_matching_payloads(self):
        self.existing_payload()
        def fail():
            raise RuntimeError('synthetic verification failure')
        with self.assertRaisesRegex(RuntimeError, 'synthetic verification failure'):
            self.publish(fail)
        self.assertEqual((self.target / 'old.txt').read_bytes(), b'old synthetic payload')
        self.assertEqual((self.stage / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertFalse((self.stage_root / '.preserve-original').exists())

    def test_first_publish_failure_restores_staged_payload(self):
        def fail():
            raise RuntimeError('synthetic verification failure')
        with mock.patch.object(verifier, 'verify_product'), mock.patch.object(verifier, 'check_inputs'),              mock.patch.object(verifier, 'check', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'synthetic verification failure'):
                verifier.publish(self.stage)
        self.assertFalse(self.target.exists())
        self.assertEqual((self.stage / 'new.txt').read_bytes(), b'new synthetic payload')

    def test_first_publish_refuses_target_created_at_rename(self):
        real = verifier.rename_exclusive
        def raced(source, destination):
            self.target.mkdir()
            (self.target / 'foreign.txt').write_bytes(b'unknown')
            real(source, destination)
        with mock.patch.object(verifier, 'verify_product'), mock.patch.object(verifier, 'check_inputs'), \
             mock.patch.object(verifier, 'rename_exclusive', side_effect=raced):
            with self.assertRaises(OSError):
                verifier.publish(self.stage)
        self.assertEqual((self.target / 'foreign.txt').read_bytes(), b'unknown')
        self.assertEqual((self.stage / 'new.txt').read_bytes(), b'new synthetic payload')

    def create_seal(self):
        (self.stage_root / 'azhou-install-registry').write_bytes(b'synthetic registry')
        icons = self.stage_root / 'AzhouAppIcon.iconset'
        icons.mkdir()
        for size in (16, 32, 128, 256, 512):
            for suffix in ('', '@2x'):
                (icons / f'icon_{size}x{size}{suffix}.png').write_bytes(b'synthetic icon')
        identity = verifier.stage_root_identity(self.stage_root)
        return verifier.seal_stage(self.stage_root, identity, False)

    def seal_fixture(self):
        sealed = self.create_seal()
        shutil.rmtree(self.stage)
        (self.stage_root / 'azhou-install-registry').unlink()
        return sealed

    def test_build_publishes_registry_before_payload_and_cleans_success(self):
        sealed = self.create_seal()
        with mock.patch.object(verifier, 'publish', side_effect=lambda path: os.rename(path, self.target)):
            verifier.publish_build(self.stage, sealed)
        self.assertEqual(self.registry.read_bytes(), b'synthetic registry')
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        verifier.verify_registry_receipt(verifier.file_receipt(self.registry))
        verifier.cleanup_stage(self.stage_root, sealed)
        self.assertFalse(self.stage_root.exists())

    def test_unknown_existing_registry_is_never_overwritten(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'unknown registry')
        with self.assertRaisesRegex(RuntimeError, '回执'):
            verifier.publish_build(self.stage, sealed)
        self.assertEqual(self.registry.read_bytes(), b'unknown registry')
        self.assertTrue(self.stage.exists())
        self.assertTrue((self.stage_root / 'azhou-install-registry').exists())

    def test_identical_unproven_registry_is_reused_without_claiming_or_deleting(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'synthetic registry')
        original = verifier.file_receipt(self.registry)
        with mock.patch.object(verifier, 'publish', side_effect=lambda path: os.rename(path, self.target)):
            verifier.publish_build(self.stage, sealed)
        self.assertEqual(verifier.file_receipt(self.registry), original)
        self.assertFalse(verifier.registry_receipt_path(original).exists())
        verifier.cleanup_stage(self.stage_root, sealed)

    def test_proven_registry_upgrades_and_cleans_owned_backup(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'previous registry')
        verifier.create_registry_receipt(verifier.file_receipt(self.registry))
        with mock.patch.object(verifier, 'swap', side_effect=fake_swap),              mock.patch.object(verifier, 'publish', side_effect=lambda path: os.rename(path, self.target)):
            verifier.publish_build(self.stage, sealed)
        self.assertEqual(self.registry.read_bytes(), b'synthetic registry')
        verifier.verify_registry_receipt(verifier.file_receipt(self.registry))
        verifier.cleanup_stage(self.stage_root, sealed)

    def test_payload_failure_retracts_new_registry_without_deleting_it(self):
        sealed = self.create_seal()
        with mock.patch.object(verifier, 'publish', side_effect=RuntimeError('synthetic payload failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic payload failure'):
                verifier.publish_build(self.stage, sealed)
        self.assertFalse(self.registry.exists())
        self.assertEqual((self.stage_root / 'azhou-install-registry').read_bytes(), b'synthetic registry')
        self.assertTrue(self.stage.is_dir())
        self.assertFalse((self.stage_root / '.registry-transaction.json').exists())

    def test_payload_failure_restores_proven_previous_registry(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'previous registry')
        verifier.create_registry_receipt(verifier.file_receipt(self.registry))
        with mock.patch.object(verifier, 'swap', side_effect=fake_swap),              mock.patch.object(verifier, 'publish', side_effect=RuntimeError('synthetic payload failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic payload failure'):
                verifier.publish_build(self.stage, sealed)
        self.assertEqual(self.registry.read_bytes(), b'previous registry')
        self.assertEqual((self.stage_root / 'azhou-install-registry').read_bytes(), b'synthetic registry')
        self.assertFalse((self.stage_root / '.registry-transaction.json').exists())

    def test_unrestored_payload_keeps_new_registry_and_old_backup(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'previous registry')
        verifier.create_registry_receipt(verifier.file_receipt(self.registry))
        def publish_then_fail(path):
            os.rename(path, self.target)
            raise RuntimeError('synthetic rollback failure')
        with mock.patch.object(verifier, 'swap', side_effect=fake_swap),              mock.patch.object(verifier, 'publish', side_effect=publish_then_fail):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                verifier.publish_build(self.stage, sealed)
        self.assertEqual((self.target / 'new.txt').read_bytes(), b'new synthetic payload')
        self.assertEqual(self.registry.read_bytes(), b'synthetic registry')
        self.assertEqual((self.stage_root / 'azhou-install-registry').read_bytes(), b'previous registry')
        self.assertTrue((self.stage_root / '.registry-transaction.json').exists())

    def test_changed_registry_backup_is_preserved_when_rollback_cannot_be_proven(self):
        sealed = self.create_seal()
        self.registry.write_bytes(b'previous registry')
        verifier.create_registry_receipt(verifier.file_receipt(self.registry))
        saved = self.stage_root / 'known-previous-moved'
        def change_then_fail(_):
            backup = self.stage_root / 'azhou-install-registry'
            backup.rename(saved)
            backup.write_bytes(b'unknown foreign data')
            raise RuntimeError('synthetic failure')
        with mock.patch.object(verifier, 'swap', side_effect=fake_swap),              mock.patch.object(verifier, 'publish', side_effect=change_then_fail):
            with self.assertRaisesRegex(RuntimeError, '保留'):
                verifier.publish_build(self.stage, sealed)
        self.assertEqual(self.registry.read_bytes(), b'synthetic registry')
        self.assertEqual((self.stage_root / 'azhou-install-registry').read_bytes(), b'unknown foreign data')
        self.assertEqual(saved.read_bytes(), b'previous registry')
        self.assertTrue((self.stage_root / '.registry-transaction.json').exists())

    def test_seal_rejects_unknown_entry_and_missing_icon_without_deleting(self):
        sealed = self.create_seal()
        foreign = self.stage_root / 'foreign.txt'
        foreign.write_bytes(b'unknown')
        with self.assertRaisesRegex(RuntimeError, '保留'):
            verifier.seal_stage(self.stage_root, sealed['identity'], False)
        self.assertEqual(foreign.read_bytes(), b'unknown')
        foreign.unlink()
        missing = self.stage_root / 'AzhouAppIcon.iconset/icon_16x16.png'
        missing.unlink()
        with self.assertRaisesRegex(RuntimeError, '保留'):
            verifier.seal_stage(self.stage_root, sealed['identity'], False)
        self.assertTrue(self.stage.is_dir())

    def test_seal_rejects_symlink_and_wrong_stage_root(self):
        sealed = self.create_seal()
        link = self.stage_root / 'foreign-link'
        link.symlink_to(self.target)
        with self.assertRaisesRegex(RuntimeError, '链接'):
            verifier.seal_stage(self.stage_root, sealed['identity'], False)
        self.assertTrue(link.is_symlink())
        with self.assertRaisesRegex(RuntimeError, '拒绝'):
            verifier.stage_root_identity(self.root / 'not-an-owned-stage')

    def test_registry_symlink_is_preserved(self):
        sealed = self.create_seal()
        outside = self.root / 'unknown-registry'
        outside.write_bytes(b'unknown')
        self.registry.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, '符号链接'):
            verifier.publish_build(self.stage, sealed)
        self.assertTrue(self.registry.is_symlink())
        self.assertEqual(outside.read_bytes(), b'unknown')

    def test_verified_successful_stage_cleanup(self):
        sealed = self.seal_fixture()
        verifier.cleanup_stage(self.stage_root, sealed)
        self.assertFalse(self.stage_root.exists())

    def test_unknown_file_after_seal_preserves_stage(self):
        sealed = self.seal_fixture()
        foreign = self.stage_root / 'foreign.txt'
        foreign.write_bytes(b'unknown')
        with self.assertRaisesRegex(RuntimeError, '保留'):
            verifier.cleanup_stage(self.stage_root, sealed)
        self.assertEqual(foreign.read_bytes(), b'unknown')

    def test_partial_cleanup_failure_reports_without_claiming_intact_tree(self):
        sealed = self.seal_fixture()
        icon = self.stage_root / 'AzhouAppIcon.iconset/icon_16x16.png'
        def partial(path):
            icon.unlink()
            raise OSError('injected partial removal')
        with mock.patch.object(verifier.shutil, 'rmtree', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'partial removal'):
                verifier.cleanup_stage(self.stage_root, sealed)
        self.assertTrue(self.stage_root.is_dir())
        self.assertFalse(icon.exists())
        self.assertTrue((self.stage_root / 'AzhouAppIcon.iconset/icon_32x32.png').exists())

    def test_replaced_root_after_seal_preserves_both_directories(self):
        sealed = self.seal_fixture()
        moved = self.build / 'owned-stage-moved'
        self.stage_root.rename(moved)
        self.stage_root.mkdir()
        (self.stage_root / 'foreign.txt').write_bytes(b'unknown')
        with self.assertRaisesRegex(RuntimeError, '保留'):
            verifier.cleanup_stage(self.stage_root, sealed)
        self.assertEqual((self.stage_root / 'foreign.txt').read_bytes(), b'unknown')
        self.assertTrue(moved.is_dir())


class StartupAssetsWorkTests(unittest.TestCase):
    def test_verified_generated_work_is_cleaned(self):
        with tempfile.TemporaryDirectory(prefix='agent-skin-assets-work-') as temp:
            with startup_builder.asset_work_directory(Path(temp), verifier) as work:
                (work / 'contours.json').write_bytes(b'[]')
                (work / 'build-startup-assets').write_bytes(b'synthetic executable')
            self.assertFalse(work.exists())

    def test_unknown_or_failed_work_is_preserved(self):
        for case in ('unknown', 'failure', 'replacement'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='agent-skin-assets-work-') as temp:
                moved = Path(temp) / 'moved-work'
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises((RuntimeError, OSError)):
                    with startup_builder.asset_work_directory(Path(temp), verifier) as work:
                        (work / 'contours.json').write_bytes(b'[]')
                        if case == 'unknown':
                            (work / 'unknown').write_bytes(b'preserve')
                        elif case == 'failure':
                            raise OSError('synthetic generation failure')
                        else:
                            work.rename(moved)
                            work.mkdir()
                            (work / 'unknown').write_bytes(b'preserve')
                self.assertTrue(work.is_dir())
                if case != 'failure':
                    self.assertEqual((work / 'unknown').read_bytes(), b'preserve')
                if case == 'replacement':
                    self.assertTrue(moved.is_dir())


class BuildLockTests(unittest.TestCase):
    def test_lock_cli_routes_run_verify_and_reports_failure(self):
        with mock.patch.object(sys, 'argv', ['build-lock.py', '--run']),              mock.patch.object(build_lock, 'run', return_value=17) as run:
            self.assertEqual(build_lock.main(), 17)
            run.assert_called_once_with()
        with mock.patch.object(sys, 'argv', ['build-lock.py', '--verify', '42']),              mock.patch.object(build_lock, 'checked_lock_file') as checked:
            self.assertEqual(build_lock.main(), 0)
            checked.assert_called_once_with(42)
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['build-lock.py', '--run']),              mock.patch.object(build_lock, 'run', side_effect=RuntimeError('lock failed')),              contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as failure:
            build_lock.main()
        self.assertEqual(failure.exception.code, 1)
        self.assertIn('lock failed', output.getvalue())

    def test_inherited_lock_serializes_build_and_preserves_lock_file(self):
        with tempfile.TemporaryDirectory(prefix='agent-skin-lock-') as temp:
            root = Path(temp).resolve()
            (root / 'tools').mkdir()
            shutil.copyfile(SOURCE.parent / 'build-lock.py', root / 'tools/build-lock.py')
            script = root / 'tools/build-macos.sh'
            script.write_text('#!/bin/bash\npython3 "$(dirname "$0")/build-lock.py" --verify "$_AZHOU_BUILD_LOCK_FD"\n', encoding='utf-8')
            build = root / '.build'
            lock = build / '.agent-skin-build.lock'
            with mock.patch.object(build_lock, 'ROOT', root), mock.patch.object(build_lock, 'BUILD', build),                  mock.patch.object(build_lock, 'LOCK', lock):
                self.assertEqual(build_lock.run(), 0)
                self.assertTrue(lock.is_file())
                first = os.open(lock, os.O_RDWR)
                second = os.open(lock, os.O_RDWR)
                try:
                    build_lock.checked_lock_file(first)
                    with self.assertRaisesRegex(RuntimeError, '另一个构建'):
                        build_lock.checked_lock_file(second)
                    moved = build / 'original-lock'
                    lock.rename(moved)
                    lock.write_bytes(b'unknown')
                    with self.assertRaisesRegex(RuntimeError, '身份'):
                        build_lock.checked_lock_file(first)
                    self.assertEqual(lock.read_bytes(), b'unknown')
                    self.assertTrue(moved.is_file())
                finally:
                    os.close(second)
                    os.close(first)

class ShellCleanupIntegrationTests(unittest.TestCase):
    def test_real_cli_and_shell_trap_for_both_hosts_and_failures(self):
        original = SOURCE.parent.parent
        build_script = (SOURCE.parent / 'build-macos.sh').read_text(encoding='utf-8')
        start = build_script.index('cleanup_stage() {')
        end = build_script.index('trap cleanup_stage EXIT', start) + len('trap cleanup_stage EXIT')
        trap = build_script[start:end]
        for mode in ('success', 'unknown', 'failed-build'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='agent-skin-shell-stage-') as temp:
                root = Path(temp).resolve()
                (root / 'tools').mkdir()
                shutil.copyfile(SOURCE, root / 'tools/verify-artifacts.py')
                shutil.copyfile(SOURCE.parent / 'build-lock.py', root / 'tools/build-lock.py')
                for name in ('hub-package.json', 'theme-config.json'):
                    shutil.copyfile(original / name, root / name)
                build = root / '.build'
                stage = build / 'azhou-stage.synthetic'
                stage.mkdir(parents=True)
                payload = stage / 'azhou-payload'
                payload.mkdir()
                (payload / 'synthetic').write_bytes(b'payload')
                (stage / 'azhou-install-registry').write_bytes(b'registry')
                icons = stage / 'AzhouAppIcon.iconset'
                icons.mkdir()
                for size in (16, 32, 128, 256, 512):
                    for suffix in ('', '@2x'):
                        (icons / f'icon_{size}x{size}{suffix}.png').write_bytes(b'icon')
                env = os.environ.copy()
                env.pop('AZHOU_APPROVED_ICON_SHA256', None)
                cli = [sys.executable, 'tools/verify-artifacts.py']
                identity = subprocess.run([*cli, '--stage-identity', str(stage)], cwd=root, env=env,
                                          capture_output=True, text=True, check=True).stdout
                sealed = subprocess.run([*cli, '--seal-stage', str(stage)], cwd=root, env=env,
                                        input=identity, capture_output=True, text=True, check=True).stdout
                shutil.rmtree(payload)
                (stage / 'azhou-install-registry').unlink()
                if mode == 'unknown':
                    (stage / 'unknown.txt').write_bytes(b'preserve')
                env.update({'STAGE_ROOT': str(stage), 'STAGE_RECEIPT': sealed})
                shell = ('stage_root="$STAGE_ROOT"\nstage_receipt="$STAGE_RECEIPT"\n'
                         'build_succeeded=' + ('0' if mode == 'failed-build' else '1')
                         + '\n' + trap + ('\nexit 18\n' if mode == 'failed-build' else '\nexit 0\n'))
                lock_fd = os.open(build / '.agent-skin-build.lock', os.O_RDWR | os.O_CREAT, 0o600)
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                env['_AZHOU_BUILD_LOCK_FD'] = str(lock_fd)
                try:
                    result = subprocess.run(['/bin/bash', '-c', shell], cwd=root, env=env,
                                            pass_fds=(lock_fd,), capture_output=True, text=True)
                finally:
                    os.close(lock_fd)
                if mode == 'success':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(stage.exists())
                else:
                    self.assertEqual(result.returncode, 1 if mode == 'unknown' else 18)
                    self.assertTrue(stage.is_dir())
                    if mode == 'unknown':
                        self.assertEqual((stage / 'unknown.txt').read_bytes(), b'preserve')
                    self.assertIn('保留', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)

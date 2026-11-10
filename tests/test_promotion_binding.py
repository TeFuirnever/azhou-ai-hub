"""Actual Git/patch promotion regressions; every repository and approval is synthetic."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import test_manage_evolution as evolution_tests

ROOT = Path(__file__).parents[1]
CLI = ROOT / 'skills/super-repo-pedant/scripts/manage_evolution.py'


class PromotionBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'commit.gpgsign', 'false')
        (self.project / '.gitignore').write_text('.azhou/\n', encoding='utf-8')
        (self.project / 'policy.txt').write_text('before\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()
        (self.project / 'policy.txt').write_text('after\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'candidate')
        self.target = self.git('rev-parse', 'HEAD').strip()
        self.target_tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        self.patch = self.root / 'candidate.diff'
        self.patch.write_bytes(self.git_bytes('diff', '--binary', '--full-index', self.base, self.target))
        self.git('checkout', '--quiet', '--detach', self.base)
        self.candidate = self.root / 'candidate.json'
        self.candidate.write_text(json.dumps(evolution_tests.ManageEvolutionTest().candidate_fixture()), encoding='utf-8')
        self.evaluation = self.root / 'evaluation.json'
        self.fixture = evolution_tests.ManageEvolutionTest().evaluation('a' * 24, hashlib.sha256(self.patch.read_bytes()).hexdigest())
        self.anchor = '0' * 64

    def git_bytes(self, *args: str) -> bytes:
        r = subprocess.run(['git', *args], cwd=self.project, env=self.env, capture_output=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr.decode('utf-8', errors='replace'))
        return r.stdout

    def git(self, *args: str) -> str:
        return self.git_bytes(*args).decode('utf-8')

    def cli(self, action: str, *, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        args = [sys.executable, '-B', str(CLI), action, '--project', str(self.project),
                '--candidate', str(self.candidate), '--patch', str(self.patch),
                '--base-commit', self.base, '--target-commit', self.target]
        if action != 'bind':
            args += ['--evaluation', str(self.evaluation), '--expected-binding-sha256', self.anchor]
        return subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                              env=env or self.env, timeout=20)

    def prepare(self) -> dict:
        r = self.cli('bind')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(r.stdout)
        self.anchor = data['binding_sha256']
        self.assertEqual(data['binding']['diff_sha256'], hashlib.sha256(self.patch.read_bytes()).hexdigest())
        self.assertEqual(data['binding']['candidate_sha256'], hashlib.sha256(self.candidate.read_bytes()).hexdigest())
        self.assertEqual(data['binding']['target_tree'], self.target_tree)
        self.fixture['source_binding_sha256'] = self.anchor
        self.fixture['human_approval']['source_binding_sha256'] = self.anchor
        self.save_evaluation()
        return data

    def save_evaluation(self) -> None:
        self.evaluation.write_text(json.dumps(self.fixture), encoding='utf-8')

    def denied(self, action: str = 'gate') -> None:
        r = self.cli(action)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            self.assertFalse(data.get('promotable', False))
            self.assertFalse(data.get('applied_verified', False))

    def test_legacy_metadata_only_gate_no_longer_promotes(self) -> None:
        self.save_evaluation()
        r = subprocess.run([sys.executable, '-B', str(CLI), 'gate', '--candidate', str(self.candidate),
                            '--evaluation', str(self.evaluation)], capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertNotEqual(r.returncode, 0, r.stdout)

    def test_valid_gate_is_not_an_application_receipt(self) -> None:
        self.prepare()
        before = self.git_bytes('ls-files', '--stage', '-z')
        r = self.cli('gate')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout)['promotable'])
        self.assertFalse(json.loads(r.stdout)['applied_verified'])
        self.assertEqual(self.base, self.git('rev-parse', 'HEAD').strip())
        self.assertEqual(before, self.git_bytes('ls-files', '--stage', '-z'))
        self.assertEqual('before\n', (self.project / 'policy.txt').read_text())


    def test_plain_python_cli_does_not_write_installed_package_bytecode(self) -> None:
        installed = self.root / 'installed-skill'
        shutil.copytree(CLI.parent.parent, installed, ignore=shutil.ignore_patterns('__pycache__'))
        environment = dict(self.env)
        environment.pop('PYTHONDONTWRITEBYTECODE', None)
        command = [sys.executable, str(installed / 'scripts' / 'manage_evolution.py'),
                   'bind', '--project', str(self.project), '--candidate', str(self.candidate),
                   '--patch', str(self.patch), '--base-commit', self.base,
                   '--target-commit', self.target]
        result = subprocess.run(command, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(list(installed.rglob('*.pyc')), 'read-only CLI wrote package bytecode')
        self.assertFalse(list(installed.rglob('__pycache__')), 'read-only CLI created a cache directory')

    def test_missing_patch_is_rejected(self) -> None:
        self.prepare(); self.patch.unlink(); self.denied()

    def test_replacement_after_approval_is_rejected(self) -> None:
        self.prepare(); self.patch.write_bytes(self.patch.read_bytes().replace(b'+after', b'+unapproved')); self.denied()

    def test_exact_bytes_not_only_equivalent_tree_are_bound(self) -> None:
        self.prepare(); self.patch.write_bytes(self.patch.read_bytes() + b'\n'); self.denied()

    def test_candidate_metadata_drift_is_rejected(self) -> None:
        self.prepare(); self.candidate.write_bytes(self.candidate.read_bytes() + b' '); self.denied()

    def test_wrong_external_binding_is_rejected(self) -> None:
        self.prepare(); self.anchor = 'f' * 64; self.denied()

    def test_approval_binding_cannot_be_replaced_by_evaluation(self) -> None:
        self.prepare(); self.fixture['human_approval']['source_binding_sha256'] = 'f' * 64
        self.save_evaluation(); self.denied()

    def test_evaluation_binding_mismatch_is_rejected(self) -> None:
        self.prepare(); self.fixture['source_binding_sha256'] = 'f' * 64
        self.save_evaluation(); self.denied()

    def test_stale_base_rejected_even_with_identical_source_tree(self) -> None:
        self.prepare(); self.git('commit', '--quiet', '--allow-empty', '-m', 'new base'); self.denied()

    def test_changed_target_commit_is_rejected(self) -> None:
        self.prepare(); self.target = self.base; self.denied()

    def test_dirty_worktree_is_rejected(self) -> None:
        self.prepare(); (self.project / 'policy.txt').write_text('dirty\n'); self.denied()

    def test_dirty_index_is_rejected_even_when_worktree_matches(self) -> None:
        self.prepare(); (self.project / 'policy.txt').write_text('dirty\n'); self.git('add', '.')
        (self.project / 'policy.txt').write_text('before\n'); self.denied()

    def test_untracked_source_is_rejected(self) -> None:
        self.prepare(); (self.project / 'surprise.py').write_text('pass\n'); self.denied()

    def test_ignored_evidence_remains_untouched(self) -> None:
        self.prepare(); state = self.project / '.azhou'; state.mkdir(); f = state / 'sentinel'; f.write_bytes(b'private')
        r = self.cli('gate'); self.assertEqual(0, r.returncode, r.stdout + r.stderr); self.assertEqual(f.read_bytes(), b'private')

    def test_inherited_git_redirect_cannot_change_checked_repository(self) -> None:
        self.prepare(); env = dict(self.env, GIT_DIR=str(self.root / 'missing'), GIT_INDEX_FILE=str(self.root / 'bad-index'))
        r = self.cli('gate', env=env); self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse((self.root / 'bad-index').exists())

    @unittest.skipIf(os.name == 'nt', 'symlink fixture requires POSIX')
    def test_symlink_patch_is_rejected(self) -> None:
        self.prepare(); real = self.patch.with_suffix('.real'); self.patch.rename(real); self.patch.symlink_to(real); self.denied()

    def test_duplicate_json_keys_fail_closed(self) -> None:
        self.prepare(); self.evaluation.write_text('{"candidate_id":"a","candidate_id":"b"}'); self.denied()

    def test_malformed_votes_fail_closed_without_traceback(self) -> None:
        self.prepare(); self.fixture['paired_votes'] = [None, None, None]; self.save_evaluation()
        r = self.cli('gate'); self.assertNotEqual(r.returncode, 0); self.assertNotIn('Traceback', r.stderr)

    def test_applied_squash_tree_and_parent_are_verified(self) -> None:
        self.prepare(); self.git('apply', '--index', str(self.patch)); self.git('commit', '--quiet', '-m', 'explicit application')
        r = self.cli('verify-applied'); self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        result = json.loads(r.stdout); self.assertTrue(result['applied_verified']); self.assertFalse(result['promotable'])
        self.assertEqual(result['applied_commit'], self.git('rev-parse', 'HEAD').strip())
        self.assertEqual(result['binding']['target_tree'], self.git('rev-parse', 'HEAD^{tree}').strip())

    def test_incorrect_application_never_verifies(self) -> None:
        self.prepare(); (self.project / 'policy.txt').write_text('wrong\n'); self.git('add', '.'); self.git('commit', '--quiet', '-m', 'wrong')
        self.denied('verify-applied')

    def test_post_application_requires_actual_application(self) -> None:
        self.prepare(); self.denied('verify-applied')

    def test_explicit_reverse_restores_base_after_failed_application_check(self) -> None:
        self.prepare(); self.git('apply', '--index', str(self.patch)); self.denied('verify-applied')
        self.git('apply', '--index', '--reverse', str(self.patch))
        self.assertEqual(self.git('write-tree').strip(), self.git('rev-parse', self.base + '^{tree}').strip())
        self.assertEqual('before\n', (self.project / 'policy.txt').read_text())
        self.assertEqual(0, self.cli('gate').returncode)

    def test_hidden_index_flag_is_rejected(self) -> None:
        self.prepare(); self.git('update-index', '--assume-unchanged', 'policy.txt'); self.denied()


    def test_verification_does_not_change_git_metadata_with_split_index_config(self) -> None:
        self.git('config', 'core.splitIndex', 'true')
        gitdir = self.project / '.git'
        def inventory() -> dict:
            return {str(p.relative_to(gitdir)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(gitdir.rglob('*')) if p.is_file()}
        before = inventory()
        self.prepare()
        r = self.cli('gate')
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual(before, inventory())

    def test_binary_and_non_ascii_added_files_replay_and_reverse(self) -> None:
        self.git('checkout', '--quiet', '--detach', self.base)
        (self.project / '数据.bin').write_bytes(bytes(range(256)) * 4)
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'binary candidate')
        self.target = self.git('rev-parse', 'HEAD').strip()
        self.target_tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        self.patch.write_bytes(self.git_bytes('diff', '--binary', '--full-index', self.base, self.target))
        self.fixture['diff_sha256'] = hashlib.sha256(self.patch.read_bytes()).hexdigest()
        self.fixture['human_approval']['diff_sha256'] = self.fixture['diff_sha256']
        self.git('checkout', '--quiet', '--detach', self.base)
        self.prepare()
        self.assertEqual(0, self.cli('gate').returncode)

    def test_repository_copy_requires_new_external_approval_binding(self) -> None:
        import shutil
        self.prepare()
        original = self.project
        self.project = self.root / 'copy'
        shutil.copytree(original, self.project)
        self.denied()

    @unittest.skipIf(os.name == 'nt', 'executable shell hook fixture requires POSIX')
    def test_repository_index_hook_cannot_run_during_any_binding_phase(self) -> None:
        import shlex
        hooks = self.root / 'configured-hooks'
        hooks.mkdir()
        marker = self.root / 'post-index-change-ran'
        hook = hooks / 'post-index-change'
        hook.write_text('#!/bin/sh\nprintf called >> ' + shlex.quote(str(marker)) + '\n', encoding='utf-8')
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', str(hooks))
        self.prepare()
        self.assertFalse(marker.exists(), 'bind executed repository post-index-change hook')
        result = self.cli('gate')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), 'gate executed repository post-index-change hook')
        self.git('apply', '--index', str(self.patch))
        self.git('commit', '--quiet', '-m', 'explicit application with host hooks')
        self.assertTrue(marker.exists(), 'fixture hook must run for ordinary application owner')
        marker.unlink()
        result = self.cli('verify-applied')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), 'verify-applied executed repository post-index-change hook')

    def test_source_filter_command_is_not_executed(self) -> None:
        marker = self.root / 'filter-ran'
        self.git('config', 'filter.untrusted.clean', 'echo unsafe > ' + str(marker))
        (self.project / '.git/info/attributes').write_text('policy.txt filter=untrusted\n', encoding='utf-8')
        self.prepare()
        self.assertEqual(0, self.cli('gate').returncode)
        self.assertFalse(marker.exists())

    def test_applied_tree_on_unapproved_parent_is_rejected(self) -> None:
        self.prepare()
        self.git('commit', '--quiet', '--allow-empty', '-m', 'different parent')
        self.git('apply', '--index', str(self.patch))
        self.git('commit', '--quiet', '-m', 'same tree wrong parent')
        self.denied('verify-applied')


    def replace_candidate_from_current_head(self) -> None:
        self.target = self.git('rev-parse', 'HEAD').strip()
        self.target_tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        self.patch.write_bytes(self.git_bytes('diff', '--binary', '--full-index', self.base, self.target))
        self.fixture['diff_sha256'] = hashlib.sha256(self.patch.read_bytes()).hexdigest()
        self.fixture['human_approval']['diff_sha256'] = self.fixture['diff_sha256']
        self.git('checkout', '--quiet', '--detach', self.base)

    def test_replaced_target_commit_with_same_tree_requires_new_approval(self) -> None:
        self.prepare()
        self.git('checkout', '--quiet', '--detach', self.target)
        self.git('commit', '--quiet', '--amend', '-m', 'another candidate identity')
        self.target = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '--quiet', '--detach', self.base)
        self.denied()

    def test_deletion_and_executable_file_change_reconstruct_and_reverse(self) -> None:
        (self.project / 'policy.txt').unlink()
        script = self.project / 'policy.sh'
        script.write_bytes(b'#!/bin/sh\necho approved\n')
        script.chmod(0o755)
        self.git('add', '.')
        self.git('update-index', '--chmod=+x', 'policy.sh')
        self.git('commit', '--quiet', '-m', 'mode and deletion')
        self.replace_candidate_from_current_head()
        self.prepare()
        self.assertEqual(0, self.cli('gate').returncode)
        self.assertTrue((self.project / 'policy.txt').exists())
        self.assertFalse(script.exists())

    @unittest.skipIf(os.name == 'nt', 'symlink fixture requires POSIX')
    def test_candidate_changing_symlink_is_rejected_before_private_application(self) -> None:
        (self.project / 'outside-link').symlink_to(self.root / 'outside')
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'unsupported link')
        self.replace_candidate_from_current_head()
        self.denied('bind')
        self.assertFalse((self.root / 'outside').exists())

    @unittest.skipIf(os.name == 'nt', 'FIFO fixture requires POSIX')
    def test_fifo_patch_rejects_without_blocking(self) -> None:
        self.prepare()
        self.patch.unlink()
        os.mkfifo(self.patch)
        self.denied()

    def test_oversize_patch_is_rejected(self) -> None:
        self.prepare()
        self.patch.write_bytes(b'x' * (8 * 1024 * 1024 + 1))
        self.denied()

    def test_private_index_storage_inside_project_is_rejected(self) -> None:
        self.prepare()
        directory = self.project / '.azhou' / 'tmp'
        directory.mkdir(parents=True)
        env = dict(self.env, TMPDIR=str(directory), TEMP=str(directory), TMP=str(directory))
        r = self.cli('gate', env=env)
        self.assertNotEqual(0, r.returncode, r.stdout)
        self.assertEqual([], list(directory.iterdir()))

    def test_rejected_temporary_root_has_no_probe_file_creation(self) -> None:
        self.prepare()
        directory = self.project / '.azhou' / 'rejected-temp'
        directory.mkdir(parents=True)
        env = dict(self.env, TMPDIR=str(directory), TEMP=str(directory), TMP=str(directory))
        probe = """import json, os, sys
from pathlib import Path
watched = Path(sys.argv[1]).resolve()
def observe(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        flags = args[2]
        path = Path(os.fsdecode(args[0])).resolve()
        if isinstance(flags, int) and flags & os.O_CREAT and path.is_relative_to(watched):
            print('AUDITED_TEMP_CREATE ' + json.dumps(str(path)), file=sys.stderr)
sys.addaudithook(observe)
sys.argv = sys.argv[2:]
import runpy
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        command = [sys.executable, '-B', '-c', probe, str(directory), str(CLI), 'gate',
                   '--project', str(self.project), '--candidate', str(self.candidate),
                   '--patch', str(self.patch), '--evaluation', str(self.evaluation),
                   '--base-commit', self.base, '--target-commit', self.target,
                   '--expected-binding-sha256', self.anchor]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                env=env, timeout=20)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertFalse(json.loads(result.stdout)['promotable'])
        self.assertNotIn('AUDITED_TEMP_CREATE', result.stderr,
                         'rejected temporary roots must never be probed with a created file')
        self.assertEqual([], list(directory.iterdir()))

    def test_private_index_storage_inside_sibling_worktree_is_rejected(self) -> None:
        self.prepare()
        sibling = self.root / 'sibling-worktree'
        self.git('worktree', 'add', '--quiet', '--detach', str(sibling), self.base)
        directory = sibling / '.azhou' / 'tmp'
        directory.mkdir(parents=True)
        env = dict(self.env, TMPDIR=str(directory), TEMP=str(directory), TMP=str(directory))
        result = self.cli('gate', env=env)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['promotable'])
        self.assertEqual([], list(directory.iterdir()))
        self.assertEqual('before\n', (sibling / 'policy.txt').read_text())

    def test_bind_from_candidate_checkout_is_not_preapplication_permission(self) -> None:
        self.git('checkout', '--quiet', '--detach', self.target)
        data = self.prepare()
        self.assertFalse(data['promotable'])
        self.assertFalse(data['applied_verified'])
        self.denied('gate')

    def test_post_application_still_requires_approved_binding(self) -> None:
        self.prepare()
        self.git('apply', '--index', str(self.patch))
        self.git('commit', '--quiet', '-m', 'explicit application')
        self.fixture['human_approval']['status'] = 'pending'
        self.save_evaluation()
        self.denied('verify-applied')


if __name__ == '__main__':
    unittest.main()

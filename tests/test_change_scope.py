from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "azhou_hub.py"


class ChangeScopeCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "scope-fixture@example.invalid")
        self.git("config", "user.name", "Scope Fixture")
        (self.root / "base.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, encoding="utf-8")

    def call(self, *args, env_overrides=None):
        return subprocess.run(
            [sys.executable, "-B", str(CLI), "scope", "--project", str(self.root), *args],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, **(env_overrides or {})},
        )

    def test_four_layers_are_distinct_and_worktree_is_not_mutated(self):
        (self.root / "committed.txt").write_text("commit\n")
        self.git("add", ".")
        self.git("commit", "-qm", "change")
        (self.root / "staged.txt").write_text("staged\n")
        (self.root / "mixed.txt").write_text("stage\n")
        self.git("add", "staged.txt", "mixed.txt")
        (self.root / "mixed.txt").write_bytes(b"stage\nplus\n")
        (self.root / "base.txt").write_text("changed\n")
        (self.root / "name with space.txt").write_bytes(b"untracked\n")
        special_name = "line\nbreak.txt" if os.name != "nt" else "unicode-测试.txt"
        (self.root / special_name).write_text("untracked\n")
        status = ["git", "status", "--porcelain=v1", "-z"]
        before = subprocess.check_output(status, cwd=self.root)
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["paths"], {
            "committed": ["committed.txt"],
            "staged": ["mixed.txt", "staged.txt"],
            "unstaged": ["base.txt", "mixed.txt"],
            "untracked": sorted([special_name, "name with space.txt"]),
        })
        self.assertEqual(payload["resolved"]["worktree_head"], self.git("rev-parse", "HEAD").strip())
        self.assertEqual(before, subprocess.check_output(status, cwd=self.root))
        identity = {row["path"]: row for row in payload["identity"]["worktree"]}
        self.assertEqual(identity["mixed.txt"]["sha256"], hashlib.sha256(b"stage\nplus\n").hexdigest())
        self.assertEqual(identity["name with space.txt"]["sha256"], hashlib.sha256(b"untracked\n").hexdigest())
        (self.root / "mixed.txt").write_text("different content\n")
        again = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(again.returncode, 0, again.stderr)
        changed = {row["path"]: row for row in json.loads(again.stdout)["identity"]["worktree"]}
        self.assertNotEqual(identity["mixed.txt"]["sha256"], changed["mixed.txt"]["sha256"])

    def test_identity_changes_with_git_attributes(self):
        (self.root / "base.txt").write_text("changed\n")
        info = self.root / ".git" / "info" / "attributes"
        info.write_text("base.txt text\n")
        first = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(first.returncode, 0, first.stderr)
        info.write_text("base.txt -text\n")
        second = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(second.returncode, 0, second.stderr)
        first_identity = json.loads(first.stdout)["identity"]
        second_identity = json.loads(second.stdout)["identity"]
        self.assertNotEqual(first_identity["info_attributes_sha256"], second_identity["info_attributes_sha256"])
        self.assertNotEqual(first_identity["effective_attributes_sha256"], second_identity["effective_attributes_sha256"])
        self.assertEqual(first_identity["index_file_sha256"], hashlib.sha256((self.root / ".git" / "index").read_bytes()).hexdigest())

    def test_tmpdir_inside_an_unrelated_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory) / "other"
            other.mkdir()
            subprocess.run(["git", "init", "-q", str(other)], check=True)
            result = self.call("--base", self.base, "--head", "HEAD", env_overrides={"TMPDIR": str(other)})
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("temporary directory", result.stderr)
            self.assertEqual(list(other.glob("azhou-scope-*")), [])

    def test_tmpdir_inside_an_unrelated_bare_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory) / "other.git"
            subprocess.run(["git", "init", "--bare", "-q", str(other)], check=True)
            (other / "config").unlink()  # Git accepts bare repositories without a config file.
            result = self.call("--base", self.base, "--head", "HEAD", env_overrides={"TMPDIR": str(other)})
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("temporary directory", result.stderr)
            self.assertEqual(list(other.glob("azhou-scope-*")), [])

    def test_unsafe_tmpdir_is_rejected_before_python_creates_probe_files(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            other = fixture / "other"
            other.mkdir()
            subprocess.run(["git", "init", "-q", str(other)], check=True)
            marker = fixture / "creation-observed"
            (fixture / "sitecustomize.py").write_text(
                "import os, sys\n"
                f"target = {str(other)!r} + os.sep\n"
                f"marker = {str(marker)!r}\n"
                "def audit(event, args):\n"
                "    if event == 'open' and isinstance(args[0], str) and args[0].startswith(target) "
                "and isinstance(args[2], int) and args[2] & os.O_CREAT:\n"
                "        fd = os.open(marker, os.O_CREAT | os.O_WRONLY, 0o600)\n"
                "        os.close(fd)\n"
                "sys.addaudithook(audit)\n",
                encoding="utf-8",
            )
            result = self.call("--base", self.base, "--head", "HEAD",
                               env_overrides={"TMPDIR": str(other), "PYTHONPATH": str(fixture)})
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("temporary directory", result.stderr)
            self.assertFalse(marker.exists(), "Python created a temporary probe in another worktree")

    def test_invalid_and_ambiguous_refs_fail_without_success_json(self):
        self.git("branch", "collision")
        self.git("tag", "collision")
        for ref in ("absent-ref", "collision"):
            with self.subTest(ref=ref):
                result = self.call("--base", ref, "--head", "HEAD")
                self.assertEqual(result.returncode, 1)
                self.assertFalse(result.stdout.strip())
                self.assertIn("scope:", result.stderr)
        valid = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads(valid.stdout)["paths"], {
            "committed": [], "staged": [], "unstaged": [], "untracked": [],
        })

    def test_non_commit_ref_and_missing_project_are_rejected(self):
        blob = subprocess.check_output(["git", "hash-object", "-w", "--stdin"],
                                       cwd=self.root, input=b"blob").decode().strip()
        self.git("tag", "blob-ref", blob)
        result = self.call("--base", "blob-ref", "--head", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(result.stdout.strip())
        self.assertIn("scope:", result.stderr)
        missing = subprocess.run(
            [sys.executable, "-B", str(CLI), "scope", "--project", str(self.root / "absent"),
             "--base", self.base, "--head", "HEAD"], capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(missing.returncode, 1)
        self.assertFalse(missing.stdout.strip())

    def test_intent_to_add_is_rejected_instead_of_misclassifying_layers(self):
        (self.root / "new.txt").write_text("new\n")
        self.git("add", "-N", "new.txt")
        self.assertEqual(self.git("diff", "--cached", "--name-only").strip(), "")
        self.assertEqual(self.git("diff", "--name-only").strip(), "new.txt")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("intent-to-add", result.stderr)

    def test_unmerged_index_is_not_reported_as_a_successful_scope(self):
        blob = subprocess.check_output(["git", "hash-object", "-w", "--stdin"],
                                       cwd=self.root, input=b"conflict").strip()
        self.git("update-index", "--force-remove", "base.txt")
        entry = b"100644 " + blob + b" 1\tbase.txt\0"
        subprocess.run(["git", "update-index", "-z", "--index-info"],
                       cwd=self.root, input=entry, check=True)
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("unmerged", result.stderr)

    def test_submodule_and_split_index_are_reported_unsupported(self):
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.base + ",nested")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("submodule", result.stderr)
        self.git("update-index", "--force-remove", "nested")
        self.git("update-index", "--split-index")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("split Git index", result.stderr)

    def test_linked_worktree_uses_its_own_index_and_common_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            linked = Path(directory) / "linked"
            self.git("worktree", "add", "-qb", "fixture-linked", str(linked), "HEAD")
            (linked / "base.txt").write_text("linked edit\n")
            result = subprocess.run(
                [sys.executable, "-B", str(CLI), "scope", "--project", str(linked),
                 "--base", self.base, "--head", "HEAD"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["paths"]["unstaged"], ["base.txt"])
            self.assertEqual(payload["resolved"]["worktree_head"], self.base)

    def test_no_or_multiple_merge_bases_are_rejected(self):
        tree = self.git("rev-parse", "HEAD^{tree}").strip()

        def create_commit(parents, message):
            command = ["git", "commit-tree", tree]
            for parent in parents:
                command.extend(["-p", parent])
            return subprocess.check_output(command, cwd=self.root, input=message, text=True, encoding="utf-8").strip()

        unrelated = create_commit([], "unrelated")
        left = create_commit([self.base], "left")
        right = create_commit([self.base], "right")
        merge_one = create_commit([left, right], "merge one")
        merge_two = create_commit([right, left], "merge two")
        for base, head in ((self.base, unrelated), (merge_one, merge_two)):
            with self.subTest(base=base, head=head):
                result = self.call("--base", base, "--head", head)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(result.stdout.strip())
                self.assertIn("scope:", result.stderr)

    @unittest.skipIf(os.name == "nt", "raw non-UTF-8 paths are POSIX-only")
    def test_invalid_utf8_paths_fail_closed(self):
        blob = subprocess.check_output(["git", "hash-object", "-w", "--stdin"],
                                       cwd=self.root, input=b"blob").strip()
        entry = b"100644 " + blob + b"\tinvalid-" + bytes([255]) + bytes([0])
        subprocess.run(["git", "update-index", "-z", "--index-info"],
                       cwd=self.root, input=entry, check=True)
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(result.stdout.strip())
        self.assertIn("not valid UTF-8", result.stderr)

    def test_equal_size_edit_with_restored_mtime_is_not_hidden(self):
        target = self.root / "base.txt"
        original = target.stat()
        self.git("config", "core.trustctime", "false")
        target.write_bytes(b"other")
        os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["paths"]["unstaged"], ["base.txt"])

    def test_head_is_separate_from_current_worktree(self):
        (self.root / "later.txt").write_text("later")
        self.git("add", ".")
        self.git("commit", "-qm", "later")
        (self.root / "base.txt").write_text("dirty")
        result = self.call("--base", self.base, "--head", self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["paths"]["committed"], [])
        self.assertEqual(payload["paths"]["unstaged"], ["base.txt"])
        self.assertEqual(payload["resolved"]["head"], self.base)
        self.assertNotEqual(payload["resolved"]["head"], payload["resolved"]["worktree_head"])

    @unittest.skipIf(os.name == "nt", "shell shim fixture")
    def test_concurrent_new_untracked_file_fails_closed(self):
        shim_dir = self.root / ".git" / "scope-shim"
        shim_dir.mkdir()
        executable = shim_dir / "git"
        marker = self.root / ".git" / "shim-ran"
        late = self.root / "late-untracked.txt"
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        executable.write_text(
            "#!/bin/sh\n"
            + shlex.quote(real_git) + ' "$@"\n'
            + "code=$?\n"
            + 'case "$*" in\n'
            + '  *"ls-files --others --exclude-standard -z --"*)\n'
            + "    if [ ! -e " + shlex.quote(str(marker)) + " ]; then\n"
            + "      touch " + shlex.quote(str(marker)) + " " + shlex.quote(str(late)) + "\n"
            + "    fi ;;\n"
            + "esac\n"
            + 'exit "$code"\n'
        )
        executable.chmod(0o755)
        result = self.call("--base", self.base, "--head", "HEAD",
                           env_overrides={"PATH": str(shim_dir) + os.pathsep + os.environ["PATH"]})
        self.assertTrue(late.exists(), "fixture must mutate during inspection")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("changed during", result.stderr)

    @unittest.skipIf(os.name == "nt", "shell shim fixture")
    def test_filter_added_during_inspection_never_executes_helper(self):
        hook = self.root / ".git" / "clean.sh"
        marker = self.root / ".git" / "filter-ran"
        hook.write_text("#!/bin/sh\ntouch " + shlex.quote(str(marker)) + "\ncat\n")
        hook.chmod(0o755)
        self.git("config", "filter.probe.clean", str(hook))
        (self.root / "base.txt").write_text("changed\n")
        shim_dir = self.root / ".git" / "scope-shim"
        shim_dir.mkdir()
        shim = shim_dir / "git"
        fired = self.root / ".git" / "shim-ran"
        attributes = self.root / ".git" / "info" / "attributes"
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        shim.write_text(
            "#!/bin/sh\n"
            + 'if [ "$5" = diff ] && [ ! -e ' + shlex.quote(str(fired)) + " ]; then\n"
            + "  touch " + shlex.quote(str(fired)) + "\n"
            + "  printf 'base.txt filter=probe\\n' > " + shlex.quote(str(attributes)) + "\n"
            + "fi\n"
            + "exec " + shlex.quote(real_git) + ' "$@"\n'
        )
        shim.chmod(0o755)
        result = self.call("--base", self.base, "--head", "HEAD",
                           env_overrides={"PATH": str(shim_dir) + os.pathsep + os.environ["PATH"]})
        self.assertTrue(fired.exists(), "fixture must alter attributes before diff")
        self.assertFalse(marker.exists(), "read-only scope must never execute clean filters")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())

    def test_hidden_index_flags_never_report_clean(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", flag, "base.txt")
                (self.root / "base.txt").write_text("changed\n")
                result = self.call("--base", self.base, "--head", "HEAD")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(result.stdout.strip())
                self.assertIn("index flags", result.stderr)
                self.git("update-index", "--no-assume-unchanged", "base.txt")
                self.git("update-index", "--no-skip-worktree", "base.txt")
                (self.root / "base.txt").write_text("base\n")
        normal = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(normal.returncode, 0, normal.stderr)

    def test_ignored_files_are_not_untracked(self):
        (self.root / ".gitignore").write_text("ignored.bin\n")
        (self.root / "ignored.bin").write_text("ignored\n")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["paths"]["untracked"], [".gitignore"])

    def test_line_endings_follow_original_safe_git_configuration(self):
        self.git("config", "core.autocrlf", "true")
        (self.root / "base.txt").write_bytes(b"base\r\n")
        self.assertEqual(self.git("diff", "--name-only"), "")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["paths"]["unstaged"], [])

        info_attributes = self.root / ".git" / "info" / "attributes"
        info_attributes.write_text("base.txt -text\n")
        self.assertEqual(self.git("diff", "--name-only").strip(), "base.txt")
        changed = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertEqual(json.loads(changed.stdout)["paths"]["unstaged"], ["base.txt"])

    def test_temporary_root_inside_worktree_is_rejected_before_writing(self):
        before = subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=self.root)
        result = self.call("--base", self.base, "--head", "HEAD",
                           env_overrides={"TMPDIR": str(self.root), "TEMP": str(self.root), "TMP": str(self.root)})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertIn("outside all worktrees", result.stderr)
        self.assertEqual(before, subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=self.root))
        self.assertEqual(list(self.root.glob("azhou-scope-*")), [])

    def test_inherited_git_trace_cannot_create_file(self):
        marker = self.root / "trace.log"
        result = self.call("--base", self.base, "--head", "HEAD",
                           env_overrides={"GIT_TRACE": str(marker), "GIT_TRACE2_EVENT": str(marker)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == "nt", "shell hook fixture")
    def test_filtered_file_is_rejected_without_running_filter(self):
        attributes = self.root / ".gitattributes"
        attributes.write_text("*.txt filter=probe\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "attributes")
        marker = self.root / "filter-ran"
        hook = self.root / "filter.sh"
        hook.write_text("#!/bin/sh\ntouch \"" + str(marker) + "\"\ncat\n")
        hook.chmod(0o755)
        self.git("config", "filter.probe.clean", str(hook))
        (self.root / "base.txt").write_text("changed\n")
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean filters", result.stderr)
        self.assertFalse(result.stdout.strip())
        self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == "nt", "shell hook fixture")
    def test_does_not_run_configured_fsmonitor(self):
        marker = self.root / "monitor-ran"
        hook = self.root / "monitor.sh"
        hook.write_text("#!/bin/sh\ntouch \"" + str(marker) + "\"\n")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        result = self.call("--base", self.base, "--head", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()

"""Failure controls for fixed source identity, snapshot isolation and receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import integration_common as common


class IntegrationSourceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.hub = self.root / "hub"
        self.lock_path = self.hub / "integrations/pstack/source-lock.json"
        self.lock_path.parent.mkdir(parents=True)
        self.workspace = self.root / "workspace"
        self.file = self.source / "runtime.txt"
        self.file.write_text("fixed runtime input\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "runtime.txt")
        self.git("-c", "user.name=Integration test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Fixture")
        self.lock = {
            "schema": common.LOCK_SCHEMA, "component": "pstack",
            "repository": "https://example.invalid/fixture",
            "commit": self.git("rev-parse", "HEAD").strip(),
            "source_kind": "commit",
            "files": {"runtime.txt": self.file_record()},
            "license": "test fixture",
        }
        self.save_lock()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.source), *args], text=True, encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )

    def file_record(self):
        return {
            "sha256": hashlib.sha256(self.file.read_bytes()).hexdigest(),
            "executable": bool(self.file.stat().st_mode & 0o111),
        }

    def save_lock(self):
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")

    def inspect(self):
        return common.inspect_source("pstack", self.source, hub_root=self.hub)

    def snapshot(self):
        return common.snapshot_source("pstack", self.source, self.workspace, hub_root=self.hub)

    def test_exact_subset_snapshot_is_repeatable_and_does_not_copy_unselected_files(self):
        (self.source / "private-input.txt").write_text("excluded fixture", encoding="utf-8")
        result = self.inspect()
        self.assertTrue(result["working_tree_dirty"])
        snapshot = self.snapshot()
        self.assertEqual(snapshot, self.snapshot())
        self.assertEqual(self.file.read_bytes(), (snapshot / "runtime.txt").read_bytes())
        self.assertFalse((snapshot / "private-input.txt").exists())
        self.assertEqual(self.lock["commit"], common.verify_snapshot("pstack", snapshot, hub_root=self.hub)["commit"])

    def test_missing_input_rejects_before_creating_workspace(self):
        self.file.unlink()
        with self.assertRaisesRegex(common.IntegrationError, "file missing"):
            self.snapshot()
        self.assertFalse(self.workspace.exists())

    def test_wrong_content_rejects_before_creating_workspace(self):
        self.file.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "content drift"):
            self.snapshot()
        self.assertFalse(self.workspace.exists())

    @unittest.skipIf(os.name == "nt", "POSIX executable-bit control")
    def test_executable_drift_is_rejected(self):
        self.file.chmod(0o755)
        with self.assertRaisesRegex(common.IntegrationError, "executable drift"):
            self.inspect()

    def test_dirty_bytes_cannot_be_mislabeled_as_committed_source(self):
        self.file.write_text("explicit local overlay", encoding="utf-8")
        self.lock["files"]["runtime.txt"] = self.file_record()
        self.save_lock()
        with self.assertRaisesRegex(common.IntegrationError, "declared committed source"):
            self.inspect()
        self.lock["source_kind"] = "worktree"
        self.save_lock()
        self.assertEqual("worktree", self.inspect()["source_kind"])
        self.assertEqual(self.file.read_bytes(), (self.snapshot() / "runtime.txt").read_bytes())

    def test_wrong_git_commit_is_rejected(self):
        self.lock["commit"] = "0" * 40
        self.save_lock()
        with self.assertRaisesRegex(common.IntegrationError, "commit mismatch"):
            self.inspect()

    def test_snapshot_drift_is_not_silently_repaired(self):
        snapshot = self.snapshot()
        (snapshot / "runtime.txt").write_text("foreign change", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "content drift"):
            self.snapshot()
        self.assertEqual("foreign change", (snapshot / "runtime.txt").read_text(encoding="utf-8"))

    def test_snapshot_inside_read_only_source_is_rejected(self):
        with self.assertRaisesRegex(common.IntegrationError, "outside the read-only source"):
            common.snapshot_source("pstack", self.source, self.source / "build", hub_root=self.hub)
        self.assertFalse((self.source / "build").exists())

    def test_manifest_path_traversal_is_rejected(self):
        self.lock["files"]["../escape"] = self.file_record()
        self.save_lock()
        with self.assertRaisesRegex(common.IntegrationError, "unsafe source-lock path"):
            self.inspect()

    @unittest.skipIf(os.name == "nt", "symlink creation may require privileges")
    def test_source_symlink_is_rejected(self):
        target = self.root / "elsewhere.txt"
        target.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(target)
        with self.assertRaisesRegex(common.IntegrationError, "symlink"):
            self.inspect()

    @unittest.skipIf(os.name == "nt", "symlink creation may require privileges")
    def test_state_symlink_is_rejected_without_writing_outside_workspace(self):
        self.workspace.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.workspace / ".azhou").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(common.IntegrationError, "symlink"):
            self.snapshot()
        self.assertEqual([], list(outside.iterdir()))

    def test_receipt_corruption_is_rejected(self):
        path = self.root / "receipt.json"
        common.write_receipt(path, {"status": "installed", "owner": "fixture"})
        self.assertEqual("installed", common.read_receipt(path)["status"])
        value = json.loads(path.read_text(encoding="utf-8"))
        value["status"] = "forged"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "integrity mismatch"):
            common.read_receipt(path)


if __name__ == "__main__":
    unittest.main()

"""Failure controls for canonical package inputs, snapshots, and receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from package_fixture import configure_package, package_root
from scripts import integration_common as common


class IntegrationSourceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.hub = self.root / "hub"
        self.source = configure_package(self.hub, "pstack", ["runtime.txt"], license="test fixture")
        self.workspace = self.root / "workspace"
        self.file = self.source / "runtime.txt"
        self.file.write_text("runtime package input\n", encoding="utf-8")

    def manifest(self):
        return common.load_lock("pstack", hub_root=self.hub)

    def inspect(self, source=None):
        return common.inspect_source("pstack", source, hub_root=self.hub)

    def snapshot(self, source=None, workspace=None):
        return common.snapshot_source("pstack", source, workspace or self.workspace, hub_root=self.hub)

    def test_default_package_and_exact_canonical_path_are_selected(self):
        self.assertEqual(package_root(self.hub, "pstack"), common.package_root("pstack", hub_root=self.hub))
        self.assertEqual(str(self.source), self.inspect()["source"])
        self.assertEqual(str(self.source), self.inspect(self.source)["source"])

    def test_external_source_checkout_is_rejected(self):
        external = self.root / "old-external-source"
        external.mkdir()
        with self.assertRaisesRegex(common.IntegrationError, "in-repository package|external source"):
            self.inspect(external)

    def test_each_temporary_hub_resolves_its_own_package_without_external_access(self):
        other_hub = self.root / "fresh-clone"
        other_source = configure_package(other_hub, "pstack", ["runtime.txt"])
        (other_source / "runtime.txt").write_text("fresh clone package\n", encoding="utf-8")

        result = common.inspect_source("pstack", hub_root=other_hub)

        self.assertEqual(str(other_source), result["source"])
        self.assertNotEqual(str(self.source), result["source"])
        fresh = common.snapshot_source("pstack", None, self.root / "fresh-workspace", hub_root=other_hub)
        self.assertEqual("fresh clone package\n", (fresh / "runtime.txt").read_text(encoding="utf-8"))

    def test_live_manifest_computes_package_hash_and_executable_mode(self):
        manifest_path = self.source / "hub-package.json"
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("hub-package.json", metadata["runtime_paths"])

        self.file.write_text("edited package input\n", encoding="utf-8")
        if os.name != "nt":
            self.file.chmod(0o755)
        manifest = self.manifest()

        self.assertEqual(common.LOCK_SCHEMA, manifest["schema"])
        self.assertEqual("package", manifest["source_kind"])
        self.assertEqual(hashlib.sha256(self.file.read_bytes()).hexdigest(), manifest["files"]["runtime.txt"]["sha256"])
        self.assertEqual(os.name != "nt", manifest["files"]["runtime.txt"]["executable"])
        self.assertIn("hub-package.json", manifest["files"])
        self.assertEqual("package", self.inspect()["source_kind"])

    def test_package_edit_is_valid_and_new_snapshot_contains_current_bytes(self):
        original = self.manifest()
        self.file.write_text("valid updated package input\n", encoding="utf-8")
        (self.source / "private-input.txt").write_text("not selected", encoding="utf-8")

        current = self.manifest()
        snapshot = self.snapshot()

        self.assertNotEqual(original["files"]["runtime.txt"]["sha256"], current["files"]["runtime.txt"]["sha256"])
        self.assertEqual(self.file.read_bytes(), (snapshot / "runtime.txt").read_bytes())
        self.assertFalse((snapshot / "private-input.txt").exists())

    def test_snapshot_embeds_manifest_and_remains_verifiable_after_source_removal(self):
        snapshot = self.snapshot()
        recorded = common.snapshot_lock("pstack", snapshot)
        self.assertEqual(self.manifest(), recorded)

        shutil.rmtree(self.source)

        self.assertEqual(recorded, common.snapshot_lock("pstack", snapshot))
        result = common.verify_snapshot("pstack", snapshot)
        self.assertEqual(recorded["commit"], result["commit"])
        self.assertEqual(recorded["files"]["runtime.txt"]["sha256"], hashlib.sha256((snapshot / "runtime.txt").read_bytes()).hexdigest())

    def test_missing_input_rejects_before_creating_workspace(self):
        self.file.unlink()
        with self.assertRaisesRegex(common.IntegrationError, "missing|unsupported"):
            self.snapshot()
        self.assertFalse(self.workspace.exists())

    def test_runtime_path_traversal_is_rejected(self):
        path = self.source / "hub-package.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["runtime_paths"].append("../escape")
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "unsafe .*path"):
            self.manifest()

    def test_private_and_generated_runtime_paths_are_rejected(self):
        path = self.source / "hub-package.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["runtime_paths"].append(".build")
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "private or generated runtime input"):
            self.manifest()

    @unittest.skipIf(os.name == "nt", "symlink creation may require privileges")
    def test_source_symlink_is_rejected(self):
        target = self.root / "elsewhere.txt"
        target.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(target)
        with self.assertRaisesRegex(common.IntegrationError, "symlink"):
            self.inspect()

    def test_snapshot_tampering_is_not_silently_repaired(self):
        snapshot = self.snapshot()
        (snapshot / "runtime.txt").write_text("foreign change", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "content drift"):
            common.verify_snapshot("pstack", snapshot, hub_root=self.hub)
        self.assertEqual("foreign change", (snapshot / "runtime.txt").read_text(encoding="utf-8"))

    def test_snapshot_inside_read_only_source_is_rejected(self):
        with self.assertRaisesRegex(common.IntegrationError, "outside the read-only source"):
            self.snapshot(workspace=self.source / "build")
        self.assertFalse((self.source / "build").exists())

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

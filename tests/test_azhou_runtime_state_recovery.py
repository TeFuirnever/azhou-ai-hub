"""Reject damaged migration state without overwriting source or destination."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import azhou_runtime_state as state


class MigrationRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / ".repo-pedant"
        self.source.mkdir()
        (self.source / "state.json").write_bytes(b'{"owner":"original"}\n')
        self.arguments = {
            "namespace": "super-repo-pedant",
            "source": ".repo-pedant",
            "allowed_sources": (".repo-pedant",),
        }
        self.plan = state.plan_directory_migration(self.root, **self.arguments)
        state.apply_directory_migration(self.plan)
        self.target = Path(self.plan["target"])
        self.receipt = self.target / state.MIGRATION_RECEIPT

    def inventory(self):
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }

    def assert_conflict_preserves_files(self, detail):
        before = self.inventory()
        plan = state.plan_directory_migration(self.root, **self.arguments)
        self.assertEqual("conflict", plan["status"])
        self.assertFalse(plan["applied"])
        self.assertIn(detail, plan["conflicts"])
        with self.assertRaisesRegex(state.StateError, "conflicts"):
            state.apply_directory_migration(plan)
        with self.assertRaisesRegex(state.StateError, "verification failed"):
            state.verify_directory_migration(self.plan)
        self.assertEqual(before, self.inventory())
        self.assertEqual([], list(self.target.parent.glob(".super-repo-pedant-migration-*")))

    def test_valid_json_nonobject_receipts_are_conflicts(self) -> None:
        for value in [[], None, "not a receipt", 17, False]:
            with self.subTest(value=value):
                self.receipt.write_text(json.dumps(value), encoding="utf-8")
                self.assert_conflict_preserves_files("target migration receipt is invalid")

    def test_malformed_json_receipt_is_a_conflict(self) -> None:
        self.receipt.write_text("{interrupted", encoding="utf-8")
        self.assert_conflict_preserves_files("target migration receipt is invalid")

    def test_missing_receipt_does_not_adopt_an_unowned_matching_directory(self) -> None:
        self.receipt.unlink()
        self.assert_conflict_preserves_files("target migration receipt is missing or unsafe")

    def test_mismatched_receipt_does_not_reauthorize_existing_contents(self) -> None:
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        receipt["planId"] = "0" * 64
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")
        self.assert_conflict_preserves_files("target migration receipt does not match the source plan")

    def test_target_drift_is_reported_without_repair_or_overwrite(self) -> None:
        (self.target / "state.json").write_bytes(b'{"owner":"new work"}\n')
        self.assert_conflict_preserves_files("target content differs from the compatibility source")


if __name__ == "__main__":
    unittest.main()

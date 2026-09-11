from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import azhou_runtime_state


class AzhouRuntimeStateTest(unittest.TestCase):
    def test_namespace_resolution_and_private_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = azhou_runtime_state.state_path(root, "super-llm-wiki")

            self.assertEqual(root.resolve() / ".azhou" / "super-llm-wiki", state)
            azhou_runtime_state.ensure_private_directory(state, root=root)

            self.assertTrue(state.is_dir())
            if os.name != "nt":  # os.chmod on Windows implements only the read-only bit
                self.assertEqual(0o700, state.stat().st_mode & 0o777)
            self.assertFalse((root / ".gitignore").exists())

    def test_namespace_resolution_rejects_traversal_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (root / ".azhou").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(azhou_runtime_state.StateError):
                azhou_runtime_state.state_path(root, "../escape")
            with self.assertRaises(azhou_runtime_state.StateError):
                azhou_runtime_state.state_path(root, "repo-pedant", "../escape")
            with self.assertRaises(azhou_runtime_state.StateError):
                azhou_runtime_state.state_path(root, "repo-pedant")

    def test_chained_migration_skips_the_prior_receipt_as_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".repo-pedant"
            legacy.mkdir()
            (legacy / "execution.json").write_text('{"status":"pass"}\n', encoding="utf-8")

            first = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )
            azhou_runtime_state.apply_directory_migration(first)
            prior_receipt = (root / ".azhou" / "repo-pedant" / azhou_runtime_state.MIGRATION_RECEIPT).read_bytes()

            second = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".azhou/repo-pedant",
                allowed_sources=(".repo-pedant", ".azhou/repo-pedant"),
            )
            self.assertEqual("planned", second["status"])
            self.assertNotIn(
                azhou_runtime_state.MIGRATION_RECEIPT,
                {row["path"] for row in second["contents"]},
            )
            applied = azhou_runtime_state.apply_directory_migration(second)
            self.assertEqual("verified", azhou_runtime_state.verify_directory_migration(applied)["status"])

            target = root / ".azhou" / "super-repo-pedant"
            self.assertEqual((legacy / "execution.json").read_bytes(), (target / "execution.json").read_bytes())
            receipt = json.loads((target / azhou_runtime_state.MIGRATION_RECEIPT).read_text(encoding="utf-8"))
            self.assertEqual(second["planId"], receipt["planId"])
            self.assertEqual(prior_receipt, (root / ".azhou" / "repo-pedant" / azhou_runtime_state.MIGRATION_RECEIPT).read_bytes())

    def test_migration_is_stable_atomic_idempotent_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".repo-pedant"
            source.mkdir()
            (source / "execution.json").write_text('{"status":"pass"}\n', encoding="utf-8")

            first = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )
            second = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )

            self.assertEqual(first, second)
            self.assertEqual("planned", first["status"])
            self.assertTrue(first["sourcePreserved"])
            self.assertFalse((root / ".azhou").exists())

            applied = azhou_runtime_state.apply_directory_migration(first)
            target = root / ".azhou" / "super-repo-pedant"
            self.assertEqual("migrated", applied["status"])
            self.assertTrue((source / "execution.json").is_file())
            self.assertEqual((source / "execution.json").read_bytes(), (target / "execution.json").read_bytes())
            receipt = json.loads((target / ".migration-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(first["planId"], receipt["planId"])
            self.assertTrue(receipt["sourcePreserved"])
            self.assertEqual("verified", azhou_runtime_state.verify_directory_migration(applied)["status"])

            repeated = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )
            self.assertEqual("already-current", repeated["status"])
            self.assertEqual("already-current", azhou_runtime_state.apply_directory_migration(repeated)["status"])

    def test_apply_rejects_changed_plan_and_cleans_interrupted_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".repo-pedant"
            source.mkdir()
            payload = source / "inventory.json"
            payload.write_text("one\n", encoding="utf-8")
            plan = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )

            payload.write_text("two\n", encoding="utf-8")
            with self.assertRaises(azhou_runtime_state.StateError):
                azhou_runtime_state.apply_directory_migration(plan)
            self.assertFalse((root / ".azhou").exists())

            current = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )
            real_replace = os.replace
            target = Path(current["target"])

            def fail_publish(source_path: str | Path, target_path: str | Path) -> None:
                if Path(target_path) == target:
                    raise OSError("simulated interruption")
                real_replace(source_path, target_path)

            with mock.patch.object(azhou_runtime_state.os, "replace", side_effect=fail_publish):
                with self.assertRaises(OSError):
                    azhou_runtime_state.apply_directory_migration(current)

            self.assertFalse((root / ".azhou" / "super-repo-pedant").exists())
            self.assertEqual([], list((root / ".azhou").glob(".super-repo-pedant-migration-*")))

    def test_apply_rejects_source_change_during_copy_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".repo-pedant"
            source.mkdir()
            payload = source / "inventory.json"
            payload.write_text("one\n", encoding="utf-8")
            plan = azhou_runtime_state.plan_directory_migration(
                root,
                namespace="super-repo-pedant",
                source=".repo-pedant",
                allowed_sources=(".repo-pedant",),
            )
            real_copytree = azhou_runtime_state.shutil.copytree

            def mutate_after_copy(source_path: Path, target_path: Path, **kwargs: object) -> Path:
                result = real_copytree(source_path, target_path, **kwargs)
                payload.write_text("two\n", encoding="utf-8")
                return result

            with mock.patch.object(azhou_runtime_state.shutil, "copytree", side_effect=mutate_after_copy):
                with self.assertRaisesRegex(
                    azhou_runtime_state.StateError,
                    "source changed while copying",
                ):
                    azhou_runtime_state.apply_directory_migration(plan)

            self.assertFalse((root / ".azhou" / "super-repo-pedant").exists())
            self.assertEqual([], list((root / ".azhou").glob(".super-repo-pedant-migration-*")))


if __name__ == "__main__":
    unittest.main()

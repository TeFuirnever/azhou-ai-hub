from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = "super-azhou-info"


class ManagedLifecycleCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project" / ".agents" / "skills"
        self.target.mkdir(parents=True)
        self.receipt = self.target / ".azhou" / "hub" / "receipts" / f"{SKILL}.json"
        self.installed = self.target / SKILL
        self.setup_args = (
            "setup", "--managed", "--receipt", self.receipt, "--skill", SKILL,
            "--target", self.target, "--mode", "copy",
        )

    def cli(self, *args: object, expected: int = 0) -> dict:
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "azhou_hub.py"), *map(str, args), "--json"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(expected, process.returncode, process.stderr + process.stdout)
        return json.loads(process.stdout)

    def install(self) -> None:
        preview = self.cli(*self.setup_args)
        self.assertEqual("dry_run", preview["status"])
        self.assertFalse(self.installed.exists())
        applied = self.cli(*self.setup_args, "--apply", "--plan-id", preview["planId"])
        self.assertEqual("pass", applied["status"])
        self.assertTrue(self.receipt.is_file())
        self.assertTrue((self.installed / "SKILL.md").is_file())

    def test_setup_rejects_changed_state_after_review(self) -> None:
        preview = self.cli(*self.setup_args)
        self.assertEqual("dry_run", preview["status"])
        self.assertFalse(self.installed.exists())
        self.installed.mkdir()
        foreign = self.installed / "user-data.txt"
        foreign.write_text("user data\n", encoding="utf-8")

        result = self.cli(*self.setup_args, "--apply", "--plan-id", preview["planId"], expected=1)
        self.assertEqual("fail", result["status"])
        self.assertIn("plan changed", result.get("error", ""))
        self.assertNotEqual(preview["planId"], result["planId"])
        self.assertEqual("user data\n", foreign.read_text(encoding="utf-8"))
        self.assertFalse(self.receipt.exists())

    def test_repair_rechecks_after_install_disappears(self) -> None:
        self.install()
        args = ("repair", "--receipt", self.receipt, "--target", self.target)
        preview = self.cli(*args)
        self.assertEqual("current", preview["skills"][0]["status"])
        self.assertNotIn("planId", preview)
        shutil.rmtree(self.installed)

        result = self.cli(*args, "--apply")
        self.assertEqual("pass", result["status"])
        self.assertEqual("repaired", result["skills"][0]["status"])
        self.assertTrue((self.installed / "SKILL.md").is_file())

    def test_migrate_rechecks_edited_install(self) -> None:
        self.install()
        args = ("migrate", "--receipt", self.receipt, "--target", self.target, "--mode", "link")
        preview = self.cli(*args)
        self.assertEqual("dry_run", preview["status"])
        self.assertNotIn("planId", preview)
        content = self.installed / "SKILL.md"
        original = content.read_bytes()
        changed = original + b"\nuser change\n"
        content.write_bytes(changed)

        result = self.cli(*args, "--apply", expected=1)
        self.assertEqual("fail", result["status"])
        self.assertEqual("conflict", result["skills"][0]["status"])
        self.assertEqual(changed, content.read_bytes())
        self.assertFalse(self.installed.is_symlink())
        content.write_bytes(original)
        self.assertEqual("pass", self.cli(*args, "--apply")["status"])
        self.assertTrue(self.installed.is_symlink())
        self.assertEqual("link", json.loads(self.receipt.read_text(encoding="utf-8"))["mode"])

    def test_uninstall_rechecks_edited_install(self) -> None:
        self.install()
        args = ("uninstall", "--receipt", self.receipt, "--target", self.target)
        preview = self.cli(*args)
        self.assertEqual("current", preview["skills"][0]["status"])
        self.assertNotIn("planId", preview)
        content = self.installed / "SKILL.md"
        original = content.read_bytes()
        changed = original + b"\nuser change\n"
        content.write_bytes(changed)
        receipt_bytes = self.receipt.read_bytes()

        result = self.cli(*args, "--apply", expected=1)
        self.assertEqual("fail", result["status"])
        self.assertEqual("conflict", result["skills"][0]["status"])
        self.assertEqual(changed, content.read_bytes())
        self.assertEqual(receipt_bytes, self.receipt.read_bytes())
        content.write_bytes(original)
        self.assertEqual("pass", self.cli(*args, "--apply")["status"])
        self.assertFalse(self.installed.exists())
        self.assertEqual(receipt_bytes, self.receipt.read_bytes())
        records = list((self.target / ".azhou" / "hub" / "uninstalled").iterdir())
        self.assertEqual(1, len(records))
        self.assertTrue(os.path.samefile(records[0], self.receipt))
        doctor = self.cli("doctor", "--target", self.target, "--skill", SKILL)
        self.assertEqual("pass", next(c for c in doctor["checks"] if c["name"] == "target:hub-receipts")["status"])


if __name__ == "__main__":
    unittest.main()

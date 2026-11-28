"""Exercise migration rejection and recovery through both real CLI entry points."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "scripts" / "azhou_hub.py"
PEDANT = ROOT / "skills" / "super-repo-pedant" / "scripts" / "migrate_state.py"


class RuntimeStateCliRecoveryTest(unittest.TestCase):
    def cli(self, script: Path, *args: object, expected: int = 0, status: str) -> dict:
        process = subprocess.run(
            [sys.executable, "-B", str(script), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        output = process.stdout + process.stderr
        self.assertNotIn("Traceback", process.stderr, output)
        self.assertEqual(expected, process.returncode, output)
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            self.fail(f"CLI did not emit one JSON document: {output}")
        self.assertIsInstance(payload, dict, output)
        self.assertEqual(status, payload.get("status"), output)
        return payload

    @staticmethod
    def snapshot(root: Path) -> dict[str, bytes | None]:
        # Include empty directories so leaked staging directories or Hub mutation
        # locks cannot disappear from the preservation assertion.
        return {
            path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
            for path in root.rglob("*")
        }

    def assert_recovery(
        self, script: Path, args: tuple, project: Path, source: Path, target: Path,
        *, conflict_exit: int, apply_exit: int,
    ) -> None:
        source_before = self.snapshot(source)
        before = self.snapshot(project)
        planned = self.cli(script, *args, status="planned")
        self.assertFalse(planned["applied"])
        self.assertEqual(before, self.snapshot(project), "Planning must be read-only")
        self.assertFalse(target.exists())
        applied = self.cli(script, *args, "--apply", "--plan-id", planned["planId"], status="migrated")
        self.assertTrue(applied["applied"])
        self.assertEqual(source_before, self.snapshot(source))
        receipt = target / ".migration-receipt.json"
        valid_receipt = receipt.read_bytes()
        migrated = self.snapshot(project)

        for name, contents in (
            ("array", "[]"), ("null", "null"), ("string", '"not a receipt"'),
            ("number", "17"), ("boolean", "false"), ("malformed", "{interrupted"),
        ):
            with self.subTest(receipt=name):
                receipt.write_text(contents, encoding="utf-8")
                damaged = self.snapshot(project)
                conflict = self.cli(script, *args, expected=conflict_exit, status="conflict")
                self.assertFalse(conflict["applied"])
                self.assertEqual(["target migration receipt is invalid"], conflict["conflicts"])
                self.assertEqual(damaged, self.snapshot(project))
                refused = self.cli(
                    script, *args, "--apply", "--plan-id", conflict["planId"],
                    expected=apply_exit, status="fail",
                )
                self.assertEqual("runtime-state migration plan has conflicts", refused["error"])
                self.assertEqual(damaged, self.snapshot(project), "Refusal must preserve all files and directories")

        receipt.write_bytes(valid_receipt)
        self.assertEqual(migrated, self.snapshot(project))
        restored = self.cli(script, *args, status="already-current")
        self.assertEqual(planned["planId"], restored["planId"])
        repeated = self.cli(
            script, *args, "--apply", "--plan-id", restored["planId"], status="already-current",
        )
        self.assertFalse(repeated["applied"])
        self.assertEqual(migrated, self.snapshot(project), "Recovery must be an idempotent retry")
        self.assertEqual(source_before, self.snapshot(source))

    def test_pedant_cli_rejects_damaged_receipts_and_recovers_without_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            source = project / ".repo-pedant"
            source.mkdir()
            (source / "execution.json").write_bytes(b'{"status":"pass"}\n')
            self.assert_recovery(
                PEDANT, ("--project", project), project, source, project / ".azhou/super-repo-pedant",
                conflict_exit=0, apply_exit=2,
            )

    def test_hub_cli_rejects_damaged_receipts_and_recovers_without_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            target = project / "skills"
            current = target / ".azhou/hub/receipts/super-eli5.json"
            setup = (
                "setup", "--skill", "super-eli5", "--target", target,
                "--mode", "copy", "--managed", "--receipt", current, "--json",
            )
            planned = self.cli(HUB, *setup, status="dry_run")
            self.assertFalse(target.exists())
            self.cli(HUB, *setup, "--apply", "--plan-id", planned["planId"], status="pass")
            source = target / ".azhou-ai-hub/receipts"
            source.mkdir(parents=True)
            shutil.copy2(current, source / current.name)
            # Recreate a legacy namespace using only this test's generated state.
            shutil.rmtree(target / ".azhou")
            self.assert_recovery(
                HUB, ("migrate-receipts", "--target", target, "--json"), project, source, current.parent,
                conflict_exit=1, apply_exit=1,
            )


if __name__ == "__main__":
    unittest.main()

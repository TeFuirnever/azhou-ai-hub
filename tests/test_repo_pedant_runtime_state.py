from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "repo-pedant" / "scripts"
INVENTORY = SCRIPTS / "inventory_knowledge.py"
MIGRATE = SCRIPTS / "migrate_state.py"


class RepoPedantRuntimeStateTest(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text("# Project\n", encoding="utf-8")
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        return project

    def test_inventory_defaults_to_repo_pedant_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(Path(directory))
            result = self.run_script(
                INVENTORY,
                "snapshot",
                "--project",
                str(project),
                "--memory-decision",
                "none_discovered::checked project and harness memory surfaces",
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            output = project / ".azhou" / "repo-pedant" / "inventory.json"
            self.assertTrue(output.is_file())
            self.assertFalse((project / ".repo-pedant").exists())
            self.assertEqual(str(output.resolve()), json.loads(result.stdout)["output"])

    def test_explicit_repo_pedant_state_migration_is_idempotent_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(Path(directory))
            source = project / ".repo-pedant"
            source.mkdir()
            (source / "execution.json").write_text('{"status":"pass"}\n', encoding="utf-8")

            planned = self.run_script(MIGRATE, "--project", str(project))
            self.assertEqual(0, planned.returncode, planned.stdout + planned.stderr)
            plan = json.loads(planned.stdout)
            self.assertEqual("planned", plan["status"])
            self.assertFalse((project / ".azhou").exists())

            applied = self.run_script(
                MIGRATE,
                "--project",
                str(project),
                "--apply",
                "--plan-id",
                plan["planId"],
            )
            self.assertEqual(0, applied.returncode, applied.stdout + applied.stderr)
            self.assertEqual("migrated", json.loads(applied.stdout)["status"])
            target = project / ".azhou" / "repo-pedant"
            self.assertTrue((source / "execution.json").is_file())
            self.assertTrue((target / "execution.json").is_file())

            repeated = self.run_script(
                MIGRATE,
                "--project",
                str(project),
                "--apply",
                "--plan-id",
                plan["planId"],
            )
            self.assertEqual(0, repeated.returncode, repeated.stdout + repeated.stderr)
            self.assertEqual("already-current", json.loads(repeated.stdout)["status"])


if __name__ == "__main__":
    unittest.main()

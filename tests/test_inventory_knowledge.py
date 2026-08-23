from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "repo-pedant" / "scripts" / "inventory_knowledge.py"
SPEC = importlib.util.spec_from_file_location("inventory_knowledge", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InventoryKnowledgeTest(unittest.TestCase):
    def make_project(self, parent: Path, name: str = "project") -> Path:
        root = parent / name
        (root / "docs" / "deep").mkdir(parents=True)
        (root / "README.md").write_text("# Project\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (root / "docs" / "deep" / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
        (root / "notes").mkdir()
        (root / "notes" / "status.md").write_text("# Status\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "ignored.md").write_text("ignored\n", encoding="utf-8")
        return root

    def complete(self, inventory: dict) -> dict:
        for project in inventory["projects"]:
            project["runnable_stage"] = True
            if project.get("memory_inventory", {}).get("status") == "unresolved":
                project["memory_inventory"] = {
                    "status": "none_discovered",
                    "paths": [],
                    "evidence": "Checked the synthetic project and harness memory candidates; none exist.",
                }
        for record in inventory["files"]:
            record["classification"] = "verified"
        inventory["history_sources"] = [{"type": "task_state", "coverage": "complete"}]
        inventory["checks"] = {name: True for name in MODULE.REQUIRED_CHECKS}
        return inventory

    def test_snapshot_enumerates_all_affected_project_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = self.make_project(base, "first")
            second = self.make_project(base, "second")
            memory = base / "memory"
            memory.mkdir()
            (memory / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
            global_rule = base / "GLOBAL.md"
            global_rule.write_text("# Global\n", encoding="utf-8")

            inventory = MODULE.build_inventory([first, second], [memory], [global_rule])
            paths = {Path(record["path"]) for record in inventory["files"]}

            self.assertIn(first / "docs" / "deep" / "runbook.md", paths)
            self.assertIn(second / "notes" / "status.md", paths)
            self.assertIn(memory / "MEMORY.md", paths)
            self.assertIn(global_rule, paths)
            self.assertNotIn(first / "node_modules" / "ignored.md", paths)
            self.assertEqual(2, len(inventory["projects"]))

    def test_complete_inventory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            self.assertEqual([], MODULE.validate_inventory(inventory))

    def test_unclassified_file_and_incomplete_history_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = MODULE.build_inventory([project], [], [])
            inventory["projects"][0]["runnable_stage"] = True
            errors = MODULE.validate_inventory(inventory)
            self.assertTrue(any("every enumerated file" in error for error in errors))
            self.assertTrue(any("history_sources" in error for error in errors))

    def test_bloat_and_agent_rule_growth_are_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            rules = next(record for record in inventory["files"] if record["path"] == str(project / "AGENTS.md"))
            (project / "AGENTS.md").write_text("\n".join(f"rule {index}" for index in range(340)) + "\n", encoding="utf-8")
            errors = MODULE.validate_inventory(inventory)
            self.assertTrue(any("size_resolution" in error for error in errors))
            self.assertTrue(any("growth_explanation" in error for error in errors))
            rules["size_resolution"] = "Reviewed and held for a dedicated split."
            rules["growth_explanation"] = "Synthetic threshold regression."
            self.assertEqual([], MODULE.validate_inventory(inventory))

    def test_global_instruction_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = self.make_project(base)
            global_rule = base / "GLOBAL.md"
            global_rule.write_text("# Global\n", encoding="utf-8")
            inventory = self.complete(MODULE.build_inventory([project], [], [global_rule]))
            record = next(item for item in inventory["files"] if item["path"] == str(global_rule))
            record["classification"] = "update"
            self.assertTrue(any("read-only" in error for error in MODULE.validate_inventory(inventory)))

    def test_explicit_external_memory_binds_to_single_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = self.make_project(base)
            memory = base / "runtime-memory" / "MEMORY.md"
            memory.parent.mkdir()
            memory.write_text("# Memory\n", encoding="utf-8")
            inventory = self.complete(MODULE.build_inventory([project], [memory], []))
            record = next(item for item in inventory["files"] if item["path"] == str(memory))
            self.assertEqual(str(project), record["project_root"])
            self.assertTrue(record["write_allowed"])
            self.assertEqual(
                {
                    "status": "bound",
                    "paths": [str(memory)],
                    "evidence": "Explicit --memory candidate bound to this project.",
                },
                inventory["projects"][0]["memory_inventory"],
            )

    def test_unresolved_memory_inventory_blocks_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = MODULE.build_inventory([project], [], [])
            for record in inventory["files"]:
                record["classification"] = "verified"
            inventory["projects"][0]["runnable_stage"] = True
            inventory["history_sources"] = [{"type": "task_state", "coverage": "complete"}]
            inventory["checks"] = {name: True for name in MODULE.REQUIRED_CHECKS}
            errors = MODULE.validate_inventory(inventory)
            self.assertTrue(any("memory_inventory.status" in error and "unresolved" in error for error in errors))

    def test_explicit_none_discovered_decision_is_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            decisions = {
                project.resolve(): {
                    "status": "none_discovered",
                    "evidence": "Checked repository MEMORY.md and the active harness project-memory path; neither exists.",
                }
            }
            inventory = self.complete(MODULE.build_inventory([project], [], [], decisions))
            proof = inventory["projects"][0]["memory_inventory"]
            self.assertEqual("none_discovered", proof["status"])
            self.assertEqual([], proof["paths"])
            self.assertIn("active harness", proof["evidence"])
            self.assertEqual([], MODULE.validate_inventory(inventory))

    def test_snapshot_cli_records_memory_decision_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = self.make_project(base)
            output = base / "inventory.json"
            result = MODULE.main(
                [
                    "snapshot",
                    "--project",
                    str(project),
                    "--memory-decision",
                    "none_discovered::checked repository and active harness memory surfaces",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(0, result)
            proof = json.loads(output.read_text(encoding="utf-8"))["projects"][0]["memory_inventory"]
            self.assertEqual("none_discovered", proof["status"])
            self.assertIn("active harness", proof["evidence"])

    def test_fixture_memory_name_does_not_prove_active_project_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            fixture_memory = project / "fixtures" / "agent-memory" / "MEMORY.md"
            fixture_memory.parent.mkdir(parents=True)
            fixture_memory.write_text("# Synthetic fixture\n", encoding="utf-8")
            inventory = MODULE.build_inventory([project], [], [])
            self.assertEqual("unresolved", inventory["projects"][0]["memory_inventory"]["status"])
            self.assertIn(str(fixture_memory), {record["path"] for record in inventory["files"]})

    def test_bound_memory_proof_must_reference_an_enumerated_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            inventory["projects"][0]["memory_inventory"] = {
                "status": "bound",
                "paths": [str(Path(directory) / "missing-memory.md")],
                "evidence": "Claimed binding without enumeration.",
            }
            errors = MODULE.validate_inventory(inventory)
            self.assertTrue(any("memory_inventory.paths" in error and "enumerated" in error for error in errors))

    def test_runnable_project_requires_minimum_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "bare"
            project.mkdir()
            (project / "notes.md").write_text("# Notes\n", encoding="utf-8")
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            errors = MODULE.validate_inventory(inventory)
            self.assertTrue(any("requires README.md" in error for error in errors))
            self.assertTrue(any("requires AGENTS.md" in error for error in errors))

    def test_new_surface_requires_inventory_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            (project / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
            self.assertTrue(any("absent from inventory" in error for error in MODULE.validate_inventory(inventory)))

    def test_whole_file_deletion_requires_exact_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            inventory = self.complete(MODULE.build_inventory([project], [], []))
            record = next(item for item in inventory["files"] if item["path"] == str(project / "notes" / "status.md"))
            (project / "notes" / "status.md").unlink()
            record["classification"] = "remove_proposal"
            record["reason"] = "Superseded status surface."
            self.assertTrue(any("deletion_authorized" in error for error in MODULE.validate_inventory(inventory)))
            record["deletion_authorized"] = True
            self.assertEqual([], MODULE.validate_inventory(inventory))


if __name__ == "__main__":
    unittest.main()

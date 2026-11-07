"""Exercise native ownership boundaries without spending model requests."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from package_fixture import configure_package
from native_codex_fixture import install_fake_codex
from scripts import integration_common as common
from scripts import integration_pstack as pstack


class PstackSessionStartTest(unittest.TestCase):
    def test_setup_guidance_retains_routing_setting_and_uses_host_sheet(self):
        package = pstack.ROOT / "packages/pstack-agent-harness"
        adapters = package / "harness/pstack"
        for host in ("codex", "claude-code", "zcode", "skills-root"):
            with self.subTest(host=host):
                guidance = (adapters / host / "docs/harness" / (host + ".md")).read_text(encoding="utf-8")
                write = next(line for line in guidance.splitlines() if line.startswith("- Write."))
                self.assertIn("`session hook`", write)
                self.assertRegex(write, r"(?i)preserve")
                self.assertIn("unless the user", write)
                self.assertIn("ambiguous", write)
        zcode = (adapters / "zcode/docs/harness/zcode.md").read_text(encoding="utf-8")
        self.assertIn("`~/.zcode/pstack-models.md`", zcode)

    def test_canonical_codex_hook_routes_to_registered_skills(self):
        package = pstack.ROOT / "packages/pstack-agent-harness"
        marketplace = json.loads((package / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        plugin, marketplace_name = pstack.PLUGIN.split("@")
        self.assertEqual(marketplace["name"], marketplace_name)
        entry = next(item for item in marketplace["plugins"] if item["name"] == plugin)
        plugin_root = package / entry["source"]["path"]
        manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], plugin)

        with tempfile.TemporaryDirectory() as codex_home:
            command = ["sh", str(plugin_root / "hooks/session-start.sh"), "codex"]
            env = {**os.environ, "CODEX_HOME": codex_home, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
            output = subprocess.check_output(command, env=env, encoding="utf-8", timeout=10)
            routes = re.findall(r"`([\w-]+):([\w-]+)`", output)
            self.assertIn((plugin, "poteto-mode"), routes)
            for namespace, skill in routes:
                with self.subTest(route=f"{namespace}:{skill}"):
                    self.assertEqual(namespace, plugin)
                    self.assertTrue((plugin_root / manifest["skills"] / skill / "SKILL.md").is_file())

            (Path(codex_home) / pstack.SHEET_NAME).write_text(pstack.HOOK_OFF + "\n", encoding="utf-8")
            self.assertEqual("", subprocess.check_output(command, env=env, encoding="utf-8", timeout=10))


class PstackIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.hub = self.base / "hub"
        self.workspace = self.base / "workspace"
        self.home = self.workspace / ".azhou/hub/targets/pstack"
        self.binary = install_fake_codex(self.base / "codex")
        files = {
            ".agents/plugins/marketplace.json": json.dumps({"name":"pstack-claude", "plugins":[]}),
            "harness/pstack/codex/.codex-plugin/plugin.json": json.dumps({"name":"pstack-azhouzhou", "version":"0.9.102"}),
            "harness/pstack/codex/skills/poteto-mode/SKILL.md": "---\nname: poteto-mode\ndescription: fixture\n---\n# fixture\n",
            "harness/pstack/codex/skills/poteto-mode/scripts/bootstrap.ts": "// fixture dependency bootstrap\n",
            "harness/pstack/codex/hooks/session-start.sh": "#!/bin/sh\nprintf 'fixture hook'\n",
            "LICENSE": "fixture license\n",
        }
        self.source = configure_package(self.hub, "pstack", [
            ".agents/plugins/marketplace.json", "harness/pstack/codex", "LICENSE",
        ])
        for name, content in files.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            target.chmod(0o755 if name.endswith(".sh") else 0o644)

    def plan(self, operation="install"):
        return pstack.make_plan(source=None,
                                workspace=self.workspace, codex_home=self.home, codex_bin=self.binary,
                                operation=operation, hub_root=self.hub)

    def apply(self, operation="install"):
        plan = self.plan(operation)
        return pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)

    def doctor(self):
        return pstack.doctor(workspace=self.workspace, codex_home=self.home, codex_bin=self.binary, hub_root=self.hub)

    def calls(self):
        return [json.loads(line) for line in (self.home / "native-operations.jsonl").read_text(encoding="utf-8").splitlines()]

    def _install_owned_legacy_fixture(self):
        """Build an actual old-layout frozen snapshot and native install.

        The historical receipt and snapshot remain the only ownership basis:
        there is no access to a real user Codex home.
        """
        current = self.source / "harness/pstack/codex"
        legacy = self.source / "plugins/pstack"
        shutil.copytree(current, legacy)
        (legacy / ".codex-plugin/plugin.json").write_text(
            json.dumps({"name": "pstack", "version": "0.9.102"}), encoding="utf-8"
        )
        metadata_path = self.source / "hub-package.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["runtime_paths"] = [
            "hub-package.json", ".agents/plugins/marketplace.json", "plugins/pstack", "LICENSE"
        ]
        metadata_path.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        snapshot = common.snapshot_source("pstack", self.source, self.workspace, hub_root=self.hub)
        lock = common.snapshot_lock("pstack", snapshot)
        self.assertEqual(pstack._snapshot_plugin_identity(lock),
                         ("pstack@pstack-claude", "plugins/pstack/"))
        pstack._native(self.binary, self.home, ["marketplace", "add", str(snapshot)])
        pstack._native(self.binary, self.home, ["add", "pstack@pstack-claude"])
        receipt = {
            "schema": pstack.RECEIPT_SCHEMA, "codex_home": str(self.home),
            "snapshot": str(snapshot), "source_lock_sha256": common.plan_digest(lock),
            "commit": lock["commit"], "codex_bin": str(self.binary),
            "codex_bin_sha256": pstack._digest(self.binary), "state": "installed",
            "operation": "install", "commands": [], "completed_steps": [0, 1],
            "coexistence": None,
        }
        common.write_receipt(pstack._receipt_path(self.workspace, self.home), receipt)
        return snapshot, self.home / "plugins/cache/pstack-claude/pstack/0.9.102"

    def test_owned_legacy_receipt_preserves_old_identity_and_removes_only_old_plugin(self):
        snapshot, installed = self._install_owned_legacy_fixture()
        self.assertTrue(installed.is_dir())
        report = self.doctor()
        self.assertEqual(report["status"], "installation-verified")
        plan = self.plan("remove")
        self.assertEqual(plan["commands"][0][3], "pstack@pstack-claude")
        self.assertEqual(plan["commands"][1][4], "pstack-claude")
        result = self.apply("remove")
        self.assertEqual(result["status"], "removed")
        self.assertTrue(snapshot.is_dir())
        self.assertFalse(installed.exists())
        calls = self.calls()
        self.assertIn(["remove", "pstack@pstack-claude"], calls)
        self.assertIn(["marketplace", "remove", "pstack-claude"], calls)
        self.assertLess(calls.index(["remove", "pstack@pstack-claude"]),
                        calls.index(["marketplace", "remove", "pstack-claude"]))
        self.assertNotIn(["remove", pstack.PLUGIN], calls)

    def test_other_plugin_on_same_marketplace_blocks_owned_legacy_removal(self):
        _snapshot, installed = self._install_owned_legacy_fixture()
        with mock.patch.dict(os.environ, {"PSTACK_TEST_FOREIGN_PLUGIN": "1"}):
            with self.assertRaisesRegex(common.IntegrationError, "contains another plugin"):
                self.apply("remove")
        self.assertTrue(installed.is_dir())
        self.assertNotIn(["remove", "pstack@pstack-claude"], self.calls())
        self.assertNotIn(["marketplace", "remove", "pstack-claude"], self.calls())
        # The owned state can be recovered once an external plugin is gone.
        self.assertEqual(self.apply("remove")["status"], "removed")
        self.assertFalse(installed.exists())

    def test_failed_legacy_removal_retry_rechecks_installed_byte_hashes(self):
        _snapshot, installed = self._install_owned_legacy_fixture()
        with mock.patch.dict(os.environ, {"PSTACK_TEST_FOREIGN_PLUGIN": "1"}):
            with self.assertRaisesRegex(common.IntegrationError, "contains another plugin"):
                self.apply("remove")
        manifest = installed / "skills/poteto-mode/SKILL.md"
        manifest.write_text("user changed this file after failed remove", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "content missing or changed"):
            self.apply("remove")
        self.assertTrue(installed.is_dir())
        self.assertEqual(manifest.read_text(encoding="utf-8"),
                         "user changed this file after failed remove")
        self.assertNotIn(["remove", "pstack@pstack-claude"], self.calls())
        self.assertNotIn(["marketplace", "remove", "pstack-claude"], self.calls())

    def test_malformed_native_registry_never_authorizes_marketplace_removal(self):
        result = self.apply()
        installed = Path(result["installed_path"])
        with mock.patch.dict(os.environ, {"PSTACK_TEST_MALFORMED_REGISTRY": "1"}):
            with self.assertRaisesRegex(common.IntegrationError, "missing installed"):
                self.apply("remove")
        self.assertTrue(installed.is_dir())
        self.assertNotIn(["remove", pstack.PLUGIN], self.calls())
        self.assertNotIn(["marketplace", "remove", "pstack-claude"], self.calls())
        self.assertEqual(self.apply("remove")["status"], "removed")

    def test_owned_legacy_modified_install_is_preserved_and_removal_refused(self):
        _snapshot, installed = self._install_owned_legacy_fixture()
        skill = installed / "skills/poteto-mode/SKILL.md"
        skill.write_text("local edit - preserve", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "content missing or changed"):
            self.plan("remove")
        self.assertTrue(installed.is_dir())
        self.assertEqual(skill.read_text(encoding="utf-8"), "local edit - preserve")
        self.assertNotIn(["remove", "pstack@pstack-claude"], self.calls())

    def test_mixed_new_and_legacy_snapshot_identity_is_never_adopted(self):
        lock = {"files": {
            "plugins/pstack/.codex-plugin/plugin.json": {},
            "harness/pstack/codex/.codex-plugin/plugin.json": {},
        }}
        with self.assertRaisesRegex(common.IntegrationError, "ambiguous native plugin identity"):
            pstack._snapshot_plugin_identity(lock)

    def test_plan_defaults_to_canonical_package_and_cli_needs_no_source_flag(self):
        plan = self.plan()
        self.assertFalse(self.workspace.exists())
        self.assertEqual(plan["commands"][0][1:4], ["plugin", "marketplace", "add"])
        self.assertTrue(plan["commands"][0][4].startswith(str(self.workspace)))
        self.assertEqual(plan["source"]["source"], str(self.source))
        self.assertNotIn("michael-denyer", json.dumps(plan["commands"]))

        output = io.StringIO()
        with redirect_stdout(output):
            result = pstack.main(["plan", "--workspace", str(self.workspace), "--codex-home", str(self.home),
                                  "--codex-bin", str(self.binary)], hub_root=self.hub)
        self.assertEqual(0, result)
        self.assertEqual(str(self.source), json.loads(output.getvalue())["source"]["source"])
        self.assertFalse(self.workspace.exists())

    def test_stale_plan_and_wrong_plan_id_do_not_install(self):
        plan = self.plan()
        with self.assertRaisesRegex(common.IntegrationError, "plan-id mismatch"):
            pstack.apply_plan(plan, plan_id="wrong", hub_root=self.hub)
        self.home.mkdir(parents=True)
        (self.home / "config.toml").write_text("unrelated = 42\n", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "changed after the plan"):
            pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)
        self.assertFalse((self.home / "plugins").exists())

    def test_native_install_reinstall_and_removal_preserve_existing_config(self):
        self.home.mkdir(parents=True)
        config = self.home / "config.toml"
        config.write_text("unrelated = 42\n", encoding="utf-8")
        first = self.apply()
        self.assertTrue(first["changed"])
        self.assertEqual(first["evidence_levels"]["invoked"], "requires a real session")
        second = self.apply()
        self.assertFalse(second["changed"])
        self.assertEqual(sum(call[:2] == ["marketplace", "add"] for call in self.calls()), 1)
        self.assertEqual(sum(call[:1] == ["add"] for call in self.calls()), 1)
        removed = self.apply("remove")
        self.assertEqual(removed["status"], "removed")
        self.assertEqual(config.read_text(encoding="utf-8"), "unrelated = 42\n")
        self.assertTrue(Path(removed["snapshot_retained"]).is_dir())
        self.assertTrue(self.apply()["changed"])

    def test_partial_native_failure_resumes_without_reregistering_marketplace(self):
        with mock.patch.dict(os.environ, {"PSTACK_TEST_FAIL_PLUGIN":"1"}):
            with self.assertRaisesRegex(common.IntegrationError, "fixture plugin installation failure"):
                self.apply()
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["state"], "failed-install")
        self.assertEqual(receipt["completed_steps"], [0])
        self.assertTrue(self.apply()["changed"])
        self.assertEqual(sum(call[:2] == ["marketplace", "add"] for call in self.calls()), 1)

    def test_partial_native_failure_can_be_removed_by_its_owner(self):
        with mock.patch.dict(os.environ, {"PSTACK_TEST_FAIL_PLUGIN":"1"}):
            with self.assertRaises(common.IntegrationError):
                self.apply()
        self.assertEqual(self.apply("remove")["status"], "removed")
        self.assertNotIn(["remove", pstack.PLUGIN], self.calls())

    def test_missing_installed_runtime_fails_doctor_and_refuses_destructive_removal(self):
        result = self.apply()
        (Path(result["installed_path"]) / "hooks/session-start.sh").unlink()
        with self.assertRaisesRegex(common.IntegrationError, "content missing or changed"):
            self.doctor()
        with self.assertRaisesRegex(common.IntegrationError, "content missing or changed"):
            self.plan("remove")

    def test_registry_source_swap_fails_even_when_runtime_hashes_match(self):
        self.apply()
        state = self.home / "native-marketplace.json"
        state.write_text(json.dumps({"source":"/different-pstack"}), encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "selected pinned local"):
            self.doctor()

    def test_package_edit_is_valid_but_invalidates_an_old_reviewed_plan(self):
        old_plan = self.plan()
        (self.source / "harness/pstack/codex/hooks/session-start.sh").write_text("changed\n", encoding="utf-8")

        fresh_plan = self.plan()
        self.assertNotEqual(old_plan["source_lock_sha256"], fresh_plan["source_lock_sha256"])
        with self.assertRaisesRegex(common.IntegrationError, "changed after the plan|stale"):
            pstack.apply_plan(old_plan, plan_id=old_plan["plan_id"], hub_root=self.hub)
        self.assertFalse(self.home.exists())
        self.assertFalse((self.home / "native-operations.jsonl").exists())

    def test_package_change_after_plan_check_is_rejected_before_codex_install(self):
        plan = self.plan()
        snapshot_source = common.snapshot_source
        mutated = []

        def mutate_then_snapshot(component, source, workspace, *, hub_root, expected_digest=None):
            (self.source / "harness/pstack/codex/hooks/session-start.sh").write_text("unreviewed hook\n", encoding="utf-8")
            mutated.append(True)
            return snapshot_source(component, source, workspace, hub_root=hub_root, expected_digest=expected_digest)

        with mock.patch.object(common, "snapshot_source", side_effect=mutate_then_snapshot):
            with self.assertRaisesRegex(common.IntegrationError, "changed after the reviewed plan"):
                pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)

        self.assertEqual([True], mutated)
        self.assertFalse(self.home.exists())
        self.assertFalse((self.home / "native-operations.jsonl").exists())
        self.assertFalse(Path(plan["snapshot"]).exists())

    def test_foreign_installation_and_router_are_not_adopted(self):
        self.home.mkdir(parents=True)
        (self.home / "foreign-plugin.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "unowned Codex target"):
            self.plan()
        (self.home / "foreign-plugin.json").unlink()
        marker = self.home / "agent-orchestration-kit/state.json"
        marker.parent.mkdir()
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "unrecognized agent-orchestration-kit ownership record"):
            self.plan()

    def test_existing_config_symlink_is_not_written_through(self):
        self.home.mkdir(parents=True)
        external = self.base / "external.toml"
        external.write_text("keep = true\n", encoding="utf-8")
        (self.home / "config.toml").symlink_to(external)
        with self.assertRaisesRegex(common.IntegrationError, "must not be symlinks"):
            self.plan()
        self.assertEqual(external.read_text(encoding="utf-8"), "keep = true\n")

    def test_negative_router_mention_is_allowed_but_managed_block_is_rejected(self):
        self.home.mkdir(parents=True)
        instructions = self.home / "AGENTS.md"
        instructions.write_text("Do not invoke astra-orchestrator.\n", encoding="utf-8")
        self.assertEqual(self.plan()["operation"], "install")
        instructions.write_text("<!-- ASTRA-LUNA-ORCHESTRATOR:BEGIN -->\nUse the installed astra-orchestrator skill.\n<!-- ASTRA-LUNA-ORCHESTRATOR:END -->\n", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "without its Kit ownership record"):
            self.plan()

    def test_source_cannot_be_used_as_workspace_before_any_write(self):
        with self.assertRaisesRegex(common.IntegrationError, "workspace must be outside"):
            pstack.make_plan(source=self.source, workspace=self.source, codex_home=self.home,
                             codex_bin=self.binary, hub_root=self.hub)
        self.assertFalse((self.source / ".azhou").exists())

    def test_unlocked_skill_in_cached_snapshot_is_not_installed(self):
        plan = self.plan()
        snapshot = common.snapshot_source("pstack", self.source, self.workspace, hub_root=self.hub)
        extra = snapshot / "harness/pstack/codex/skills/unlocked/SKILL.md"
        extra.parent.mkdir()
        extra.write_text("unreviewed instructions", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "unlocked pstack runtime"):
            pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)
        self.assertFalse((self.home / "plugins").exists())
        self.assertTrue(extra.exists())

    def test_unlocked_installed_skill_fails_doctor_and_is_preserved(self):
        result = self.apply()
        extra = Path(result["installed_path"]) / "skills/unlocked/SKILL.md"
        extra.parent.mkdir()
        extra.write_text("user addition", encoding="utf-8")
        with self.assertRaisesRegex(common.IntegrationError, "unlocked pstack runtime"):
            self.doctor()
        with self.assertRaisesRegex(common.IntegrationError, "unlocked pstack runtime"):
            self.plan("remove")
        self.assertEqual(extra.read_text(encoding="utf-8"), "user addition")

    def test_runtime_dependencies_are_reported_but_not_deleted_without_ownership(self):
        result = self.apply()
        dependency = Path(result["installed_path"]) / "skills/poteto-mode/scripts/node_modules/commander/package.json"
        dependency.parent.mkdir(parents=True)
        dependency.write_text('{"name":"commander","version":"14.0.0"}', encoding="utf-8")
        status = self.doctor()["dependency_runtime"]
        self.assertEqual(status["status"], "not-independently-verified")
        with self.assertRaisesRegex(common.IntegrationError, "unlocked pstack runtime"):
            self.plan("remove")
        self.assertTrue(dependency.exists())


if __name__ == "__main__":
    unittest.main()

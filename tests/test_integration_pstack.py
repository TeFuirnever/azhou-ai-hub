"""Exercise native ownership boundaries without spending model requests."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import integration_pstack as pstack


FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
h = pathlib.Path(os.environ['CODEX_HOME'])
a = sys.argv[2:-1]
state = h / 'native-marketplace.json'
log = h / 'native-operations.jsonl'
h.mkdir(parents=True, exist_ok=True)
with log.open('a') as out:
    out.write(json.dumps(a)+'\n')
def source():
    return json.loads(state.read_text())['source']
def installed():
    return h / 'plugins/cache/pstack-claude/pstack/0.9.102'
if a[:2] == ['marketplace', 'add']:
    assert pathlib.Path(a[2]).is_absolute()
    assert not a[2].startswith('https:')
    state.write_text(json.dumps({'source': a[2]}))
    print(json.dumps({'marketplaceName': 'pstack-claude', 'installedRoot': a[2], 'alreadyAdded': False}))
elif a == ['add', 'pstack@pstack-claude']:
    if os.environ.get('PSTACK_TEST_FAIL_PLUGIN'):
        sys.exit('fixture plugin installation failure')
    shutil.copytree(pathlib.Path(source())/'plugins/pstack', installed(), dirs_exist_ok=True)
    print(json.dumps({'pluginId': 'pstack@pstack-claude', 'version': '0.9.102', 'installedPath': str(installed())}))
elif a == ['marketplace', 'list']:
    entries = [{'name':'pstack-claude', 'root':source(), 'marketplaceSource':{'sourceType':'local','source':source()}}] if state.exists() else []
    print(json.dumps({'marketplaces':entries}))
elif a == ['list', '--marketplace', 'pstack-claude'] or a == ['list']:
    entries = [{'pluginId':'pstack@pstack-claude','name':'pstack','marketplaceName':'pstack-claude','installed':True,'enabled':True,'source':{'source':'local','path':str(pathlib.Path(source())/'plugins/pstack')},'marketplaceSource':{'sourceType':'local','source':source()}}] if installed().exists() else []
    print(json.dumps({'installed':entries,'available':[]}))
elif a == ['remove', 'pstack@pstack-claude']:
    shutil.rmtree(installed())
    print(json.dumps({'removed':True}))
elif a == ['marketplace', 'remove', 'pstack-claude']:
    state.unlink()
    print(json.dumps({'removed':True}))
else:
    sys.exit('unexpected command: '+repr(a))
'''


class PstackIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.hub = self.base / "hub"
        self.workspace = self.base / "workspace"
        self.home = self.workspace / ".azhou/hub/targets/pstack"
        self.binary = self.base / "codex"
        self.binary.write_text(FAKE_CODEX, encoding="utf-8")
        self.binary.chmod(0o700)
        files = {
            ".agents/plugins/marketplace.json": json.dumps({"name":"pstack-claude", "plugins":[]}),
            "plugins/pstack/.codex-plugin/plugin.json": json.dumps({"name":"pstack", "version":"0.9.102"}),
            "plugins/pstack/skills/poteto-mode/SKILL.md": "---\nname: poteto-mode\ndescription: fixture\n---\n# fixture\n",
            "plugins/pstack/skills/poteto-mode/scripts/bootstrap.ts": "// fixture dependency bootstrap\n",
            "plugins/pstack/hooks/session-start.sh": "#!/bin/sh\nprintf 'fixture hook'\n",
            "LICENSE": "fixture license\n",
        }
        self.source = configure_package(self.hub, "pstack", [
            ".agents/plugins/marketplace.json", "plugins/pstack", "LICENSE",
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
        (self.source / "plugins/pstack/hooks/session-start.sh").write_text("changed\n", encoding="utf-8")

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
            (self.source / "plugins/pstack/hooks/session-start.sh").write_text("unreviewed hook\n", encoding="utf-8")
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
        extra = snapshot / "plugins/pstack/skills/unlocked/SKILL.md"
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

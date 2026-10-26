"""Controlled transition review for existing installations (#342).

Ticket #340 shipped the coexistence install contract and #341 the owned update
and exit paths. This suite drives the read-only ``transition-plan`` entry over
the four reachable existing-install states — a Kit beside shared pstack Skills,
a compatible native pstack, an armed one, and locally modified shared Skills —
and checks the ticket's acceptance directly: each state gets a differentiated
plan or block reason naming the actual source, the content differences against
the pinned package, the owner and the recovery basis; unknown installations are
never adopted by name or byte-identical content; planning preserves everything;
an applicable conversion is applied through the same entry's reviewed plan,
stops on drift, recovers from interruption, and leaves the #341 update and exit
paths working. Every apply runs on isolated rebuilt sources and targets with
the fake native runtime; nothing here claims a real host session, and nothing
touches a real user installation.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import integration_pstack as pstack
from scripts import integration_model_router as adapter
from test_integration_model_router import FakeInstaller, FakeNative
from test_integration_pstack import FAKE_CODEX

ROOT = Path(__file__).resolve().parents[1]
OFF_SHEET = "# pstack model configuration\nsession hook: off\n"
ARMED_SHEET = "# pstack model configuration\nfeature: opus\nsession hook: on\n"
FOREIGN_INSTALLED = "plugins/cache/pstack-claude/pstack/0.9.102"


class TransitionTestCase(unittest.TestCase):
    """One isolated hub, workspace, shared Codex home, shared Skills root and fake Codex."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.hub = self.base / "hub"
        self.source = configure_package(self.hub, "model-router", [
            "scripts/install_codex.py", "scripts/codex_native.py", "profiles/azhou-balanced",
        ])
        for name in ("install_codex.py", "codex_native.py"):
            path = self.source / "scripts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# source fixture\n", encoding="utf-8")
        profile = self.source / "profiles/azhou-balanced/AGENTS.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text("# fixture profile\n", encoding="utf-8")
        self.workspace = self.base / "workspace"
        self.home = self.workspace / ".azhou/hub/targets/codex"
        self.skills = self.home / "skills"
        self.shared = self.base / "shared-skills"
        self.binary = self.base / "codex"
        self.binary.write_text(FAKE_CODEX, encoding="utf-8")
        self.binary.chmod(0o700)
        self.pstack_source = configure_package(self.hub, "pstack", [
            ".agents/plugins/marketplace.json", "plugins/pstack", "LICENSE",
        ])
        files = {
            ".agents/plugins/marketplace.json": json.dumps({"name": "pstack-claude", "plugins": []}),
            "plugins/pstack/.codex-plugin/plugin.json": json.dumps({"name": "pstack", "version": "0.9.102"}),
            "plugins/pstack/skills/poteto-mode/SKILL.md": "---\nname: poteto-mode\ndescription: fixture\n---\n# fixture\n",
            "plugins/pstack/skills/poteto-mode/scripts/bootstrap.ts": "// fixture dependency bootstrap\n",
            "plugins/pstack/hooks/session-start.sh": "#!/bin/sh\nprintf 'fixture hook'\n",
            "LICENSE": "fixture license\n",
        }
        for name, content in files.items():
            target = self.pstack_source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            target.chmod(0o755 if name.endswith(".sh") else 0o644)
        FakeNative.fail = False
        FakeNative.discovery_cwds = []
        FakeInstaller.verified_roots = []
        patcher = patch.object(adapter, "_module",
                               side_effect=lambda _, f, **kw: FakeInstaller if f == "install_codex.py" else FakeNative)
        patcher.start()
        self.addCleanup(patcher.stop)

    # -- public entries ----------------------------------------------------
    def kit_apply(self):
        plan = adapter.make_plan(None, self.workspace, self.home, self.skills, self.binary,
                                 hub_root=self.hub)[0]
        return adapter.apply(None, self.workspace, self.home, self.skills, self.binary,
                             plan["plan_id"], hub_root=self.hub)

    def pstack_apply(self, operation="install", coexistence=None):
        plan = pstack.make_plan(source=None, workspace=self.workspace, codex_home=self.home,
                                codex_bin=self.binary, operation=operation,
                                coexistence=coexistence, hub_root=self.hub)
        return pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)

    def transition(self, skills_dir="default"):
        return pstack.transition(workspace=self.workspace, codex_home=self.home, codex_bin=self.binary,
                                 skills_dir=self.shared if skills_dir == "default" else skills_dir,
                                 hub_root=self.hub)

    # -- helpers -----------------------------------------------------------
    def put(self, relative, raw):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw.encode() if isinstance(raw, str) else raw)
        return path

    def sheet(self):
        path = self.home / pstack.SHEET_NAME
        return path.read_bytes() if path.exists() else None

    def native_log(self):
        path = self.home / "native-operations.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def tree_digests(self, root: Path) -> dict:
        result = {}
        if not root.exists():
            return result
        for path in sorted(root.rglob("*")):
            name = path.relative_to(root).as_posix()
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
        return result

    def install_shared_skill(self, *, modify=False, drop=None, extra=None):
        """Rebuild the shared Skills entry from the pinned package bytes, then optionally drift it."""
        self.shared.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.pstack_source / "plugins/pstack/skills/poteto-mode",
                        self.shared / "poteto-mode")
        skill = self.shared / "poteto-mode"
        if modify:
            (skill / "SKILL.md").write_text("---\nname: poteto-mode\ndescription: local edit\n---\n", encoding="utf-8")
        for name in drop or []:
            (skill / name).unlink()
        for name, content in (extra or {}).items():
            target = skill / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return skill

    def install_foreign_plugin(self, *, marketplace_source="/foreign-upstream-clone"):
        """A native pstack install this Hub never wrote, registered from a foreign source."""
        installed = self.home / FOREIGN_INSTALLED
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.pstack_source / "plugins/pstack", installed)
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "native-marketplace.json").write_text(
            json.dumps({"source": marketplace_source}), encoding="utf-8")
        return installed


class ReachableStateTests(TransitionTestCase):
    """Each of the four states gets a differentiated plan or block reason."""

    def routing(self, report):
        return report["transitions"][0]

    def test_kit_with_shared_pstack_skills_is_already_compatible_and_preserved(self):
        self.kit_apply()
        self.install_shared_skill()
        kit_before = self.tree_digests(self.home)
        shared_before = self.tree_digests(self.shared)
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["kit-with-shared-pstack-skills"])
        self.assertTrue(report["compatibility"]["compatible"])
        self.assertEqual(report["compatibility"]["auto_routing"], "not-armed")
        routing = self.routing(report)
        self.assertEqual(routing["status"], "not-required")
        self.assertIn("never routes tasks", routing["reason"])
        self.assertIn("never required for compatibility", routing["shared_skills_note"])
        shared = [t for t in report["transitions"] if t["goal"].startswith("keep using shared")][0]
        self.assertEqual(shared["status"], "preserved")
        self.assertEqual(shared["differences"]["poteto-mode"]["modified_count"], 0)
        self.assertIn("never requires turning shared Skills into a native plugin", shared["forced_conversion"])
        # No native registration means no ownership transition was offered.
        self.assertEqual(len(report["transitions"]), 2)
        # Read-only: every install and user file kept its bytes; no receipt appeared.
        # (native-operations.jsonl is the fixture runtime's own listing log.)
        self.assertEqual(kit_before, {name: digest for name, digest in self.tree_digests(self.home).items()
                                      if name != "native-operations.jsonl"})
        self.assertEqual(shared_before, self.tree_digests(self.shared))
        self.assertFalse(pstack._receipt_path(self.workspace, self.home).exists())

    def test_compatible_native_pstack_without_receipt_is_reported_not_adopted(self):
        self.install_foreign_plugin()
        self.put("pstack-models.md", OFF_SHEET)
        plugin_before = self.tree_digests(self.home / "plugins")
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["compatible-native-pstack"])
        self.assertTrue(report["compatibility"]["compatible"])
        self.assertEqual(self.routing(report)["status"], "not-required")
        ownership = report["transitions"][1]
        self.assertEqual(ownership["status"], "not-adopted")
        self.assertIn("not a takeover basis", ownership["reason"])
        self.assertIn("/foreign-upstream-clone", ownership["actual_source"])
        content = ownership["content_vs_pinned"]
        self.assertEqual(content["identical"], 4)
        self.assertEqual((content["modified_count"], content["missing_count"], content["unexpected_count"]), (0, 0, 0))
        self.assertIn("identical content is a comparison result, never a takeover basis", content["basis"])
        self.assertIn("no byte-exact Hub restore is claimed", ownership["recovery"])
        # Byte-identical content did not create Hub ownership: nothing changed.
        self.assertEqual(plugin_before, self.tree_digests(self.home / "plugins"))
        self.assertFalse(pstack._receipt_path(self.workspace, self.home).exists())

    def test_armed_native_pstack_without_receipt_is_blocked_with_reviewed_steps(self):
        self.install_foreign_plugin()
        self.put("pstack-models.md", ARMED_SHEET)
        sheet_before = self.sheet()
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["armed-pstack"])
        self.assertFalse(report["compatibility"]["compatible"])
        self.assertEqual(report["compatibility"]["auto_routing"], "on")
        routing = self.routing(report)
        self.assertEqual(routing["status"], "blocked")
        self.assertIn("no Hub ownership receipt", routing["reason"])
        self.assertIn("byte-identical content", routing["reason"])
        self.assertIn("/setup-pstack", " ".join(routing["steps"]))
        self.assertIn("codex plugin remove " + pstack.PLUGIN, " ".join(routing["steps"]))
        self.assertIn("no byte-exact Hub restore is claimed", routing["recovery"])
        # The blocked transition left the armed sheet exactly as it was.
        self.assertEqual(self.sheet(), sheet_before)

    def test_locally_modified_shared_skills_list_differences_and_stay_preserved(self):
        self.kit_apply()
        self.install_shared_skill(modify=True, drop=["scripts/bootstrap.ts"],
                                  extra={"references/local-host-mapping.md": "my host mapping\n"})
        shared_before = self.tree_digests(self.shared)
        report = self.transition()
        self.assertEqual(report["recognized_states"],
                         ["kit-with-shared-pstack-skills", "locally-modified-shared-skills"])
        shared = [t for t in report["transitions"] if t["goal"].startswith("keep using shared")][0]
        self.assertEqual(shared["status"], "preserved-with-differences")
        differences = shared["differences"]["poteto-mode"]
        self.assertEqual(differences["modified_count"], 1)
        self.assertEqual(differences["missing_count"], 1)
        self.assertEqual(differences["extra_count"], 1)
        facet = report["facets"]["shared_skills"]["skills"]["poteto-mode"]
        self.assertEqual(facet["modified"], ["SKILL.md"])
        self.assertEqual(facet["missing"], ["scripts/bootstrap.ts"])
        self.assertIn("references/local-host-mapping.md", facet["extra"])
        self.assertIn("nothing rewrites this directory", " ".join(shared["steps"]))
        self.assertEqual(shared_before, self.tree_digests(self.shared))

    def test_shared_skill_symlinks_report_their_actual_source(self):
        clone = self.base / "pstack-clone/plugins/pstack/skills/poteto-mode"
        clone.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.pstack_source / "plugins/pstack/skills/poteto-mode", clone)
        self.shared.mkdir(parents=True, exist_ok=True)
        (self.shared / "poteto-mode").symlink_to(clone)
        report = self.transition()
        row = report["facets"]["shared_skills"]["skills"]["poteto-mode"]
        self.assertEqual(row["kind"], "symlink")
        self.assertEqual(row["target"], str(clone))
        self.assertEqual(row["modified_count"], 0)
        self.assertEqual(report["recognized_states"], ["shared-pstack-skills-only"])

    def test_duplicate_plugin_copies_block_with_the_shared_verdict_reason(self):
        for relative in ("plugins/cache/one/.codex-plugin/plugin.json",
                         "plugins/cache/two/.codex-plugin/plugin.json"):
            self.put(relative, '{"name": "pstack"}')
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["registration-conflict"])
        self.assertEqual(report["compatibility"]["compatible"], None)
        self.assertIn("Duplicate pstack plugin copies", report["compatibility"]["error"])
        routing = report["transitions"][0]
        self.assertEqual(routing["status"], "blocked")
        self.assertIn("Duplicate pstack plugin copies", routing["reason"])

    def test_empty_target_reports_nothing_to_transition(self):
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["no-pstack-installation"])
        self.assertEqual(report["transitions"][0]["status"], "not-required")
        self.assertTrue(report["compatibility"]["compatible"])
        self.assertFalse(pstack._receipt_path(self.workspace, self.home).exists())


class ApplicableConversionTests(TransitionTestCase):
    """An armed Hub-owned install converts through this entry's reviewed plan."""

    def armed_hub_owned(self):
        self.put("pstack-models.md", ARMED_SHEET)
        self.pstack_apply()  # standalone: the armed sheet keeps its mode
        return self.transition()

    def applicable_plan(self, report):
        routing = report["transitions"][0]
        self.assertEqual(routing["status"], "applicable")
        plan = pstack.make_plan(source=None, workspace=self.workspace, codex_home=self.home,
                                codex_bin=self.binary, operation="install",
                                coexistence=True, hub_root=self.hub)
        self.assertEqual(plan["plan_id"], routing["plan_id"])
        return plan

    def test_armed_hub_owned_install_gets_an_applicable_plan_with_owner_and_recovery(self):
        self.put("pstack-models.md", ARMED_SHEET)
        self.pstack_apply()  # standalone: the armed sheet keeps its mode
        operations_before = self.native_log()
        report = self.transition()
        self.assertEqual(report["recognized_states"], ["armed-pstack"])
        ownership = report["transitions"][1]
        self.assertEqual(ownership["status"], "owned")
        routing = report["transitions"][0]
        self.assertEqual(routing["owner"], "hub-pstack-adapter")
        self.assertEqual(routing["sheet_change"]["action"], "set-line")
        self.assertEqual(routing["sheet_change"]["before_sha256"],
                         hashlib.sha256(ARMED_SHEET.encode()).hexdigest())
        self.assertIn("model rows", routing["preserved"])
        self.assertIn("'plan --operation remove' restores them", routing["recovery"])
        self.assertIn("stops on any drift", routing["apply"]["recheck"])
        # The report queried only the read-only native listings.
        self.assertEqual([call[:2] for call in self.native_log()[len(operations_before):]],
                         [["marketplace", "list"], ["list"]])
        self.assertEqual(self.sheet(), ARMED_SHEET.encode())

    def test_user_model_rows_are_reported_and_survive_the_conversion(self):
        report = self.armed_hub_owned()
        self.assertEqual(report["facets"]["sheet"]["preserved_user_rows"],
                         ["feature: opus"])
        self.assertTrue(self.applicable_plan(report)["coexistence"]["sheet_change"])
        self.pstack_apply(coexistence=True)
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature: opus\nsession hook: off\n".encode())

    def test_applied_conversion_opens_the_kit_and_exit_paths(self):
        report = self.armed_hub_owned()
        plan = self.applicable_plan(report)
        result = pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)
        self.assertTrue(result["changed"])
        self.assertEqual(result["coexistence"]["auto_routing"], "off")
        # The #341 update path: replans report the sheet as already satisfied.
        again = self.transition()
        self.assertEqual(again["recognized_states"], ["compatible-native-pstack"])
        self.assertEqual(again["transitions"][0]["status"], "not-required")
        # The Kit entry the armed state used to block now installs beside pstack.
        self.assertEqual(self.kit_apply()["status"], "installed")
        # The #341 exit path restores the user's exact original sheet bytes.
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), ARMED_SHEET.encode())

    def test_drift_between_the_transition_plan_and_apply_stops(self):
        report = self.armed_hub_owned()
        plan = self.applicable_plan(report)
        edited = ARMED_SHEET + "bug-fix: haiku\n"
        self.put("pstack-models.md", edited)
        with self.assertRaisesRegex(common.IntegrationError, "changed after the plan"):
            pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)
        self.assertEqual(self.sheet(), edited.encode())

    def test_interrupted_conversion_resumes_and_the_exit_still_restores(self):
        report = self.armed_hub_owned()
        plan = self.applicable_plan(report)
        real_write = common.write_receipt
        interruptions = []

        def interrupt_after_basis(path, payload):
            record = (payload.get("coexistence") or {}).get("sheet")
            if record and payload.get("commands") == []:
                real_write(path, payload)
                interruptions.append(self.sheet() == ARMED_SHEET.encode())
                raise RuntimeError("simulated interruption right after the recovery basis")
            return real_write(path, payload)

        with patch.object(common, "write_receipt", side_effect=interrupt_after_basis):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)
        # The persisted basis saw the sheet still untouched, so nothing is orphaned.
        self.assertEqual(interruptions, [True])
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["coexistence"]["sheet"]["before_sha256"],
                         hashlib.sha256(ARMED_SHEET.encode()).hexdigest())
        # A fresh reviewed plan — the same one transition-plan hands out — resumes.
        self.assertTrue(self.pstack_apply(coexistence=True)["changed"])
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature: opus\nsession hook: off\n".encode())
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), ARMED_SHEET.encode())

    def test_undecodable_sheet_blocks_the_conversion_with_its_reason(self):
        self.put("pstack-models.md", b"\xff\xfe\x01")
        self.pstack_apply()  # a standalone install never decodes the sheet
        report = self.transition()
        routing = report["transitions"][0]
        self.assertEqual(routing["status"], "blocked")
        self.assertIn("cannot be decoded", routing["reason"])
        self.assertEqual(self.sheet(), b"\xff\xfe\x01")

    def test_repeated_transition_reports_are_deterministic(self):
        self.kit_apply()
        self.install_shared_skill(modify=True)
        self.assertEqual(self.transition(), self.transition())


class RegistryAndCliTests(TransitionTestCase):
    def test_registry_failure_is_reported_without_hiding_file_evidence(self):
        broken = self.base / "broken-codex"
        broken.write_text("#!/usr/bin/env python3\nimport sys; sys.exit('registry down')\n", encoding="utf-8")
        broken.chmod(0o700)
        self.install_foreign_plugin()
        report = pstack.transition(workspace=self.workspace, codex_home=self.home, codex_bin=broken,
                                   skills_dir=self.shared, hub_root=self.hub)
        self.assertIn("registry down", report["facets"]["native_registry"]["error"])
        self.assertEqual(report["facets"]["native_registration"]["classification"], "single")
        self.assertEqual(report["recognized_states"], ["armed-pstack"])

    def test_cli_transition_plan_is_read_only(self):
        self.kit_apply()
        self.install_shared_skill()
        before = self.tree_digests(self.home)
        output = io.StringIO()
        with redirect_stdout(output):
            result = pstack.main(["transition-plan", "--workspace", str(self.workspace),
                                  "--codex-home", str(self.home), "--codex-bin", str(self.binary),
                                  "--skills-dir", str(self.shared)], hub_root=self.hub)
        self.assertEqual(0, result)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["schema"], "azhou-hub.pstack-transition.v1")
        self.assertEqual(payload["recognized_states"], ["kit-with-shared-pstack-skills"])
        self.assertIn("does not authorize applying any transition to the main environment",
                      payload["review_before_main_environment"]["boundary"])
        # Planning modified nothing: the Kit files keep their bytes and no pstack receipt appeared.
        self.assertEqual(before, {name: digest for name, digest in self.tree_digests(self.home).items()
                                  if name != "native-operations.jsonl"})
        self.assertFalse(pstack._receipt_path(self.workspace, self.home).exists())


if __name__ == "__main__":
    unittest.main()

"""Same-home coexistence installation through both public entries (#340).

Ticket #339 shipped the task-ownership rules; this suite drives the install
contract: the Hub's model-router entry and the Kit's direct installer must
reach the same compatibility verdict for the same target, both install orders
must converge on one coexistence configuration (Kit rules plus a pstack plugin
whose SessionStart auto-routing is switched off by the model sheet), repeat
installs must change nothing further, an armed target must be converted by a
reviewed plan instead of silently accepted, and adapter-owned sheet changes
must be restored on removal without touching Kit-owned files. All of it runs
through the public plan/apply/doctor/remove entries with the established
fake native runtime; nothing here claims a real host session.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import integration_pstack as pstack
from scripts import integration_model_router as adapter
from test_integration_model_router import FakeInstaller, FakeNative, REAL_INSTALLER
from test_integration_pstack import FAKE_CODEX

ROOT = Path(__file__).resolve().parents[1]
KIT_PACKAGE = ROOT / "packages" / "agent-orchestration-kit"
OFF_SHEET = "# pstack model configuration\nsession hook: off\n"


class CoexistenceInstallTestCase(unittest.TestCase):
    """One isolated hub, workspace, shared Codex home and fake Codex binary."""

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
    def kit_plan(self):
        return adapter.make_plan(None, self.workspace, self.home, self.skills, self.binary,
                                 hub_root=self.hub)[0]

    def kit_apply(self):
        plan = self.kit_plan()
        return adapter.apply(None, self.workspace, self.home, self.skills, self.binary,
                             plan["plan_id"], hub_root=self.hub)

    def pstack_plan(self, operation="install", coexistence=None):
        return pstack.make_plan(source=None, workspace=self.workspace, codex_home=self.home,
                                codex_bin=self.binary, operation=operation,
                                coexistence=coexistence, hub_root=self.hub)

    def pstack_apply(self, operation="install", coexistence=None):
        plan = self.pstack_plan(operation, coexistence)
        return pstack.apply_plan(plan, plan_id=plan["plan_id"], hub_root=self.hub)

    def doctor(self):
        return pstack.doctor(workspace=self.workspace, codex_home=self.home,
                             codex_bin=self.binary, hub_root=self.hub)

    # -- helpers -----------------------------------------------------------
    def put(self, relative, raw):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw.encode() if isinstance(raw, str) else raw)
        return path

    def sheet(self):
        path = self.home / pstack.SHEET_NAME
        return path.read_bytes() if path.exists() else None

    def kit_files_snapshot(self):
        home = self.home
        names = ["config.toml", "AGENTS.md", "agent-orchestration-kit/state.json", "agents/worker.toml"]
        return {name: (home / name).read_bytes() for name in names if (home / name).exists()}

    def native_log(self):
        path = self.home / "native-operations.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def plugin_installed(self):
        return (self.home / "plugins/cache/pstack-claude/pstack/0.9.102/.codex-plugin/plugin.json").is_file()


class BothEntriesAgreeTests(CoexistenceInstallTestCase):
    """The Hub entry and the Kit's direct entry judge the same target alike."""

    def hub_entry(self):
        try:
            self.kit_plan()
            return "allow"
        except common.IntegrationError as exc:
            return f"block: {exc}"

    def direct_entry(self):
        try:
            REAL_INSTALLER.build_plan(KIT_PACKAGE, self.home, self.skills)
            return "allow"
        except Exception as exc:
            return f"block: {exc}"

    def assert_agree(self, expected):
        hub, direct = self.hub_entry(), self.direct_entry()
        self.assertEqual(hub.startswith("allow"), expected == "allow",
                         f"Hub entry verdict {hub!r}, expected {expected}")
        self.assertEqual(hub.startswith("allow"), direct.startswith("allow"),
                         f"Hub entry {hub!r} disagrees with direct entry {direct!r}")

    def test_empty_target_allows_both_entries(self):
        self.assert_agree("allow")
        self.assertFalse(self.workspace.exists())

    def test_sheet_or_shared_skills_alone_are_not_routing_evidence(self):
        self.put("pstack-models.md", "# sheet\nsession hook: on\n")
        self.assert_agree("allow")
        plan = self.kit_plan()
        self.assertEqual(plan["coexistence"]["auto_routing"], "not-armed")
        self.assertEqual(plan["coexistence"]["session_hook"], "on")
        self.put("skills/poteto-mode/SKILL.md", "fixture\n")
        self.assert_agree("allow")
        plan = self.kit_plan()
        self.assertTrue(plan["coexistence"]["shared_skills_visible"])
        self.assertEqual(plan["coexistence"]["auto_routing"], "not-armed")

    def test_armed_registration_blocks_both_entries_until_the_off_line_exists(self):
        self.put("plugins/cache/pstack/.codex-plugin/plugin.json", '{"name": "pstack"}')
        self.assert_agree("block")
        self.put("pstack-models.md", OFF_SHEET)
        self.assert_agree("allow")
        plan = self.kit_plan()
        self.assertEqual(plan["coexistence"]["auto_routing"], "off")
        self.assertIn("unknown", plan["coexistence"]["hook_trust"])

    def test_config_registration_blocks_and_off_sheet_disarms_both_entries(self):
        self.put("config.toml", '[plugins."pstack@pstack-claude"]\nenabled = true\n')
        self.assert_agree("block")
        self.put("pstack-models.md", OFF_SHEET)
        self.assert_agree("allow")

    def test_duplicate_plugin_copies_block_both_entries(self):
        for relative in ("plugins/cache/one/.codex-plugin/plugin.json",
                         "plugins/cache/two/.codex-plugin/plugin.json"):
            self.put(relative, '{"name": "pstack"}')
        with self.assertRaisesRegex(common.IntegrationError, "[Dd]uplicate pstack plugin copies"):
            self.kit_plan()
        with self.assertRaisesRegex(Exception, "[Dd]uplicate pstack plugin copies"):
            REAL_INSTALLER.build_plan(KIT_PACKAGE, self.home, self.skills)


class InstallOrderTests(CoexistenceInstallTestCase):
    """Kit first then compatible pstack, and compatible pstack first then Kit."""

    def test_kit_first_then_compatible_pstack(self):
        self.kit_apply()
        kit_before = self.kit_files_snapshot()
        result = self.pstack_apply()
        self.assertTrue(result["changed"])
        self.assertEqual(self.sheet(), OFF_SHEET.encode())
        self.assertTrue(self.plugin_installed())
        self.assertEqual(kit_before, self.kit_files_snapshot())
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        record = receipt["coexistence"]["sheet"]
        self.assertIsNone(record["before_sha256"])
        self.assertTrue(receipt["coexistence"]["sheet"]["after_sha256"])
        diagnosis = result["coexistence"]
        self.assertTrue(diagnosis["kit_rules_present"])
        self.assertEqual(diagnosis["auto_routing"], "off")
        self.assertIn("unknown", diagnosis["hook_trust"])
        # Repeats on both entries change nothing further.
        self.assertEqual(self.kit_apply()["changed_files_count"], 0)
        self.assertFalse(self.pstack_apply()["changed"])
        self.assertEqual(self.sheet(), OFF_SHEET.encode())

    def test_compatible_pstack_first_then_kit(self):
        result = self.pstack_apply(coexistence=True)
        self.assertTrue(result["changed"])
        self.assertEqual(self.sheet(), OFF_SHEET.encode())
        self.assertTrue(self.plugin_installed())
        installed = self.kit_apply()
        self.assertEqual(installed["status"], "installed")
        # The Kit never touches pstack state and never installs pstack itself.
        self.assertEqual(self.sheet(), OFF_SHEET.encode())
        self.assertTrue(self.plugin_installed())
        self.assertEqual(self.kit_apply()["changed_files_count"], 0)
        self.assertFalse(self.pstack_apply(coexistence=True)["changed"])

    def test_standalone_install_keeps_its_mode_and_kit_needs_conversion_later(self):
        plan = self.pstack_plan()
        self.assertFalse(plan["coexistence"]["requested"])
        self.assertFalse(plan["coexistence"]["sheet_change"])
        self.assertIn("standalone", plan["coexistence"]["compatibility"])
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertIsNone(self.sheet())
        # Both entries now refuse to add the Kit beside armed auto-routing.
        with self.assertRaisesRegex(common.IntegrationError, "auto-routing is armed"):
            self.kit_plan()
        with self.assertRaisesRegex(Exception, "auto-routing is armed"):
            REAL_INSTALLER.build_plan(KIT_PACKAGE, self.home, self.skills)
        # Declaring coexistence up front leaves nothing armed.
        self.assertEqual(self.pstack_plan(coexistence=True)["coexistence"]["requested"], True)


class AutoRoutingConflictTests(CoexistenceInstallTestCase):
    """An armed target is converted by a reviewed plan, never silently accepted."""

    def test_conversion_plan_is_read_only_until_applied(self):
        self.kit_apply()
        original = "# pstack model configuration\nfeature, refactoring: sonnet\nsession hook: on\n"
        self.put("pstack-models.md", original)
        plan = self.pstack_plan()
        change = plan["coexistence"]["sheet_change"]
        self.assertIsNotNone(change)
        self.assertEqual(change["action"], "set-line")
        self.assertEqual(change["owner"], "hub-pstack-adapter")
        self.assertIn("restore", change)
        self.assertIn("pending", plan["coexistence"]["compatibility"])
        # Planning alone modifies nothing.
        self.assertEqual(self.sheet(), original.encode())

    def test_apply_converts_only_the_hook_line(self):
        self.kit_apply()
        original = "# pstack model configuration\nfeature, refactoring: sonnet\nsession hook: on\n"
        self.put("pstack-models.md", original)
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature, refactoring: sonnet\nsession hook: off\n".encode())
        self.assertEqual(self.doctor()["coexistence"]["auto_routing"], "off")

    def test_cli_supports_declared_coexistence(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = pstack.main(["plan", "--workspace", str(self.workspace), "--codex-home", str(self.home),
                                  "--codex-bin", str(self.binary), "--coexistence"], hub_root=self.hub)
        self.assertEqual(0, result)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["coexistence"]["requested"])
        self.assertIsNotNone(payload["coexistence"]["sheet_change"])
        self.assertIsNone(self.sheet())

    def test_undecodable_sheet_cannot_be_converted(self):
        self.kit_apply()
        self.put("pstack-models.md", b"\xff\xfe\x01")
        with self.assertRaisesRegex(common.IntegrationError, "cannot be decoded"):
            self.pstack_plan()


class FailureAndRemovalTests(CoexistenceInstallTestCase):
    """Partial failure resumes; removal restores only adapter-owned changes."""

    def test_partial_failure_resumes_and_remove_restores_the_user_sheet(self):
        self.kit_apply()
        original = "# pstack model configuration\nfeature: opus\nsession hook: on\n"
        self.put("pstack-models.md", original)
        with patch.dict(os.environ, {"PSTACK_TEST_FAIL_PLUGIN": "1"}):
            with self.assertRaisesRegex(common.IntegrationError, "fixture plugin installation failure"):
                self.pstack_apply()
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["state"], "failed-install")
        self.assertEqual(receipt["completed_steps"], [0])
        self.assertEqual(receipt["coexistence"]["sheet"]["before_sha256"],
                         hashlib.sha256(original.encode()).hexdigest())
        # A fresh reviewed plan resumes without redoing the marketplace step.
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(sum(call[:2] == ["marketplace", "add"] for call in self.native_log()), 1)
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature: opus\nsession hook: off\n".encode())
        # Removal restores the user's exact sheet bytes and keeps the Kit intact.
        kit_before = self.kit_files_snapshot()
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), original.encode())
        self.assertFalse(self.plugin_installed())
        self.assertEqual(kit_before, self.kit_files_snapshot())

    def test_remove_after_writing_a_fresh_sheet_deletes_it(self):
        self.kit_apply()
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertIsNone(self.sheet())
        self.assertTrue((self.home / "agent-orchestration-kit/state.json").is_file())

    def test_user_edited_sheet_blocks_automatic_restore_and_is_preserved(self):
        self.kit_apply()
        self.assertTrue(self.pstack_apply()["changed"])
        edited = OFF_SHEET + "feature: opus\n"
        self.put("pstack-models.md", edited)
        with self.assertRaisesRegex(common.IntegrationError,
                                    "modified after the coexistence install.*recorded sha256 [0-9a-f]{64}, "
                                    "found sha256 [0-9a-f]{64}"):
            self.pstack_apply("remove")
        self.assertEqual(self.sheet(), edited.encode())

    def test_standalone_remove_never_touches_a_user_sheet(self):
        self.put("pstack-models.md", "# user sheet\nsession hook: on\n")
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), b"# user sheet\nsession hook: on\n")


class UpdateAndRemovalTests(CoexistenceInstallTestCase):
    """Ticket #341: owned updates and exits keep the other module and user edits.

    Either module can be removed first; an existing installation is recognized
    when compatibility rules are updated to it; manual edits stop an exit with
    the recorded-versus-observed difference; interrupted exits recover; repeats
    converge. All of it runs through the public entries.
    """

    def test_kit_removed_first_leaves_pstack_usable_and_unrelated_files(self):
        self.kit_apply()
        self.assertTrue(self.pstack_apply()["changed"])
        notes = self.put("notes.txt", "unrelated user file\n")
        plan = adapter.uninstall_plan(self.workspace, self.home, self.skills, hub_root=self.hub)
        result = adapter.uninstall(self.workspace, self.home, self.skills, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(result["status"], "restored")
        # The Kit's owned scope is gone; nothing else moved.
        self.assertFalse((self.home / "agents/worker.toml").exists())
        self.assertFalse((self.home / "agent-orchestration-kit/state.json").exists())
        self.assertEqual(notes.read_bytes(), b"unrelated user file\n")
        # pstack remains usable in its retained mode: the sheet keeps routing
        # off exactly as the adapter wrote it, and the plugin stays registered.
        self.assertEqual(self.sheet(), OFF_SHEET.encode())
        self.assertTrue(self.plugin_installed())
        diagnosis = self.doctor()["coexistence"]
        self.assertFalse(diagnosis["kit_rules_present"])
        self.assertEqual(diagnosis["auto_routing"], "off")
        self.assertEqual(diagnosis["compatibility"],
                         "coexistence target: SessionStart auto-routing is off, so Kit rules may share this home")
        # Repeating the Kit exit is an explainable stop, not a silent pass.
        with self.assertRaisesRegex(common.IntegrationError, "no active installation receipt"):
            adapter.uninstall_plan(self.workspace, self.home, self.skills, hub_root=self.hub)

    def test_pstack_removed_first_then_kit_exit_restores_kit_scope(self):
        self.kit_apply()
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertIsNone(self.sheet())
        plan = adapter.uninstall_plan(self.workspace, self.home, self.skills, hub_root=self.hub)
        result = adapter.uninstall(self.workspace, self.home, self.skills, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(result["status"], "restored")
        self.assertFalse((self.home / "agents/worker.toml").exists())
        self.assertFalse((self.home / "agent-orchestration-kit/state.json").exists())
        self.assertFalse(self.plugin_installed())

    def test_old_standalone_record_is_recognized_updated_then_removed(self):
        original = "# pstack model configuration\nfeature: opus\nsession hook: on\n"
        self.put("pstack-models.md", original)
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.sheet(), original.encode())  # standalone keeps its mode
        # Updating the same receipt to coexistence rules produces a reviewed,
        # applicable change instead of a false no-op on the installed receipt.
        plan = self.pstack_plan(coexistence=True)
        self.assertIsNotNone(plan["coexistence"]["sheet_change"])
        self.assertIn("pending", plan["coexistence"]["compatibility"])
        result = self.pstack_apply(coexistence=True)
        self.assertTrue(result["changed"])
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature: opus\nsession hook: off\n".encode())
        self.assertEqual(self.doctor()["coexistence"]["auto_routing"], "off")
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["coexistence"]["sheet"]["before_sha256"],
                         hashlib.sha256(original.encode()).hexdigest())
        # Removing after the update restores the user's exact original sheet.
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), original.encode())
        self.assertFalse(self.plugin_installed())

    def test_sheet_recovery_basis_precedes_the_sheet_write_and_survives_interruption(self):
        """An interruption between the basis and the sheet write never orphans it.

        The recovery record must reach the receipt before the sheet changes
        (the Kit installer's journal-first order). The crash lands right after
        the basis is persisted; the retry must converge to installed while
        keeping the basis, and a later remove must restore the user's bytes.
        """
        self.kit_apply()
        original = "# pstack model configuration\nfeature: opus\nsession hook: on\n"
        self.put("pstack-models.md", original)
        real_write = common.write_receipt
        interruptions = []

        def interrupt_after_basis(path, payload):
            record = (payload.get("coexistence") or {}).get("sheet")
            if record and payload.get("commands") == []:
                real_write(path, payload)
                interruptions.append(self.sheet() == original.encode())
                raise RuntimeError("simulated interruption right after the recovery basis")
            return real_write(path, payload)

        with patch.object(common, "write_receipt", side_effect=interrupt_after_basis):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                self.pstack_apply()
        # Journal-first: the persisted basis saw the sheet still untouched.
        self.assertEqual(interruptions, [True])
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["coexistence"]["sheet"]["before_sha256"],
                         hashlib.sha256(original.encode()).hexdigest())
        # The retry converges to installed and keeps the recorded basis.
        self.assertTrue(self.pstack_apply()["changed"])
        self.assertEqual(self.sheet(),
                         "# pstack model configuration\nfeature: opus\nsession hook: off\n".encode())
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertEqual(receipt["coexistence"]["sheet"]["before_sha256"],
                         hashlib.sha256(original.encode()).hexdigest())
        # Removing after the interrupted-and-retried install restores the user's bytes.
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), original.encode())

    def test_preexisting_off_sheet_is_reported_satisfied_and_never_touched(self):
        user_sheet = "# my own sheet\nsession hook: off\n"
        self.put("pstack-models.md", user_sheet)
        plan = self.pstack_plan(coexistence=True)
        self.assertIsNone(plan["coexistence"]["sheet_change"])
        self.assertIn("already satisfied", plan["coexistence"]["compatibility"])
        self.assertTrue(self.pstack_apply(coexistence=True)["changed"])
        self.assertEqual(self.sheet(), user_sheet.encode())
        receipt = common.read_receipt(pstack._receipt_path(self.workspace, self.home))
        self.assertFalse((receipt.get("coexistence") or {}).get("sheet"))
        # The user's own sheet is not adapter-owned, so remove leaves it alone.
        self.assertEqual(self.pstack_apply("remove")["status"], "removed")
        self.assertEqual(self.sheet(), user_sheet.encode())

    def test_hub_uninstall_refusal_reports_the_recorded_and_observed_digest(self):
        self.kit_apply()
        worker = self.home / "agents/worker.toml"
        worker.write_bytes(worker.read_bytes() + b"\n# user amendment\n")
        before = self.kit_files_snapshot()
        with self.assertRaisesRegex(common.IntegrationError,
                                    "refusing automatic restore or overwrite.*recorded sha256 [0-9a-f]{64}, "
                                    "found sha256 [0-9a-f]{64}") as caught:
            adapter.uninstall_plan(self.workspace, self.home, self.skills, hub_root=self.hub)
        self.assertIn(str(worker), str(caught.exception))
        self.assertEqual(before, self.kit_files_snapshot())


class SheetSemanticsTests(unittest.TestCase):
    """Both shipped parsers read the sheet exactly as the hook does."""

    def test_hook_line_parsers_agree(self):
        corpus = [
            (None, None),
            (b"# c\nsession hook: off\n", "off"),
            (b"# c\nsession hook: on\n", "on"),
            (b"# c\n", "on"),
            (b"# c\nsession hook: off  \n", "on"),
            (b"\xef\xbb\xbf# c\r\nsession hook: off\r\n", "off"),
            ("# c\r\nsession hook: on\r\n".encode("utf-16"), "on"),
            ("# c\nsession hook: off\n".encode("utf-16"), "off"),
            (b"\xff\xfe\x01", "on"),
            (b"\x81\x82\x83", "on"),
            (b"# c\nsession hook: off\nsession hook: on\n", "off"),
        ]
        for raw, expected in corpus:
            with self.subTest(raw=raw):
                self.assertEqual(REAL_INSTALLER.pstack_sheet_hook(raw), expected)
                self.assertEqual(pstack._sheet_hook(raw), expected)

    def test_set_line_conversion_preserves_every_other_byte(self):
        raw = "\ufeff# pstack model configuration\r\nfeature: opus\r\nsession hook: on\r\n".encode("utf-8")
        action, desired = pstack._sheet_conversion(raw, Path("/unused"))
        self.assertEqual(action, "set-line")
        text = desired.decode("utf-8")
        self.assertTrue(text.startswith("\ufeff"))
        self.assertIn("session hook: off\r\n", text)
        self.assertEqual(text.count("session hook:"), 1)
        self.assertIn("feature: opus\r\n", text)

    def test_append_conversion_adds_one_line_and_write_creates_a_minimal_sheet(self):
        action, desired = pstack._sheet_conversion(b"feature: opus\n", Path("/unused"))
        self.assertEqual(action, "set-line")
        self.assertEqual(desired, b"feature: opus\nsession hook: off\n")
        action, desired = pstack._sheet_conversion(None, Path("/unused"))
        self.assertEqual(action, "write")
        self.assertEqual(desired, OFF_SHEET.encode())

    def test_conversion_preserves_utf16_sheets(self):
        raw = "# c\nsession hook: on\n".encode("utf-16")
        action, desired = pstack._sheet_conversion(raw, Path("/unused"))
        self.assertEqual(action, "set-line")
        self.assertEqual(pstack._sheet_hook(desired), "off")
        self.assertIn("session hook: off\n", desired.decode("utf-16"))


if __name__ == "__main__":
    unittest.main()

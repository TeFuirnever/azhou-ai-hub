"""Independent filesystem/semantic tests; never invokes a Codex runtime."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_under_test", ROOT / "scripts/install_codex.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def snapshot(root, timestamps=False):
    """Record independent on-disk evidence, including unexpected new paths."""
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        value = (stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode))
        if path.is_symlink():
            value += (os.readlink(path),)
        elif path.is_file():
            value += (path.read_bytes(),)
            if timestamps:
                value += (info.st_mtime_ns,)
        result[str(path.relative_to(root))] = value
    return result


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is a system symlink, rather than a user path conflict.
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "personal/.codex"
        self.skills = self.base / "personal/.agents/skills"

    def plan(self, source=ROOT):
        return installer.build_plan(source, self.home, self.skills)

    def put(self, relative, data, mode=0o640):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(mode)
        return path

    def install(self):
        plan = self.plan()
        installer.apply_plan(plan)
        return plan

    def source_copy(self):
        path = self.base / "source"
        shutil.copytree(ROOT / "profiles/azhou-balanced", path / "profiles/azhou-balanced")
        return path

    def test_first_install_preserves_personal_configuration_and_instructions(self):
        original = '# Personal preferences\napproval_policy = "never"\nmodel = "old" # keep model comment\n[projects."/tmp/me"]\ntrust_level = "trusted"\n[mcp_servers.notes]\ncommand = "notes"\n'
        self.put("config.toml", original)
        self.put("AGENTS.md", "Personal instructions.\n", 0o600)
        custom = self.put("agents/my-helper.toml", 'name = "my-helper"\nmodel = "custom"\n')
        custom_before = custom.read_bytes()
        before = snapshot(self.base)
        plan = self.plan()
        self.assertEqual(snapshot(self.base), before, "preflight must be read-only")
        installer.apply_plan(plan)
        config = tomllib.loads((self.home / "config.toml").read_text())
        self.assertEqual(config["approval_policy"], "never")
        self.assertEqual(config["projects"]["/tmp/me"]["trust_level"], "trusted")
        self.assertEqual(config["mcp_servers"]["notes"]["command"], "notes")
        self.assertEqual(config["model"], "gpt-6.1-sol")
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 4)
        self.assertIn("# keep model comment", (self.home / "config.toml").read_text())
        instructions = (self.home / "AGENTS.md").read_text()
        self.assertTrue(instructions.startswith("Personal instructions.\n"))
        self.assertEqual(instructions.count(installer.BEGIN), 1)
        self.assertEqual(custom.read_bytes(), custom_before)
        for name, (model, effort) in installer.ROLE_MODELS.items():
            role = tomllib.loads((self.home / f"agents/{name}.toml").read_text())
            self.assertEqual((role["name"], role["model"], role["model_reasoning_effort"]), (name, model, effort))
        self.assertTrue((self.skills / "astra-orchestrator/SKILL.md").is_file())
        state = json.loads((self.home / "agent-orchestration-kit/state.json").read_text())
        self.assertEqual(state["original_config"]["model"], {"present": True, "value": "old"})

    def test_fresh_install_then_second_install_is_exact_noop(self):
        self.install()
        before = snapshot(self.base, timestamps=True)
        plan = self.plan()
        self.assertEqual(plan["changes"], {})
        calls = []
        self.assertEqual(installer.apply_plan(plan, verify=lambda: calls.append(True)), 0)
        self.assertEqual(calls, [True])
        self.assertEqual(snapshot(self.base, timestamps=True), before)

    def test_personal_owned_config_change_is_refused_without_writes(self):
        self.install()
        path = self.home / "config.toml"
        path.write_text(path.read_text().replace('model = "gpt-6.1-sol"', 'model = "personal"', 1))
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_personal_role_change_is_refused_without_writes(self):
        self.install()
        path = self.home / "agents/worker.toml"
        path.write_bytes(path.read_bytes() + b"\n# user amendment\n")
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_unrelated_changes_after_install_are_preserved(self):
        self.install()
        config = self.home / "config.toml"
        config.write_bytes(b'personality = "friendly"\n' + config.read_bytes())
        instructions = self.home / "AGENTS.md"
        instructions.write_bytes(b"New personal preamble.\n" + instructions.read_bytes())
        before = snapshot(self.base, True)
        self.assertEqual(installer.apply_plan(self.plan()), 0)
        self.assertEqual(snapshot(self.base, True), before)

    def test_same_role_name_in_different_filename_is_collision(self):
        self.put("agents/nested/alternative.toml", 'name = "worker"\nmodel = "personal"\n')
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "collision"):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_existing_unowned_role_is_preserved(self):
        self.put("agents/worker.toml", 'name = "worker"\nmodel = "personal"\n')
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_managed_role_directory_and_symlink_are_refused(self):
        path = self.home / "agents/worker.toml"
        path.mkdir(parents=True)
        before = snapshot(self.base)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base), before)
        path.rmdir()
        victim = self.base / "victim"
        victim.write_text('name = "worker"\n')
        path.symlink_to(victim)
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_symlink_parent_is_refused_without_touching_target(self):
        external = self.base / "external"
        external.mkdir()
        self.home.mkdir(parents=True)
        (self.home / "agents").symlink_to(external, target_is_directory=True)
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_bad_target_toml_is_preflight_only(self):
        self.put("config.toml", 'model = "unterminated\n')
        before = snapshot(self.base, True)
        with self.assertRaises(tomllib.TOMLDecodeError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_malformed_source_role_is_preflight_only(self):
        source = self.source_copy()
        (source / "profiles/azhou-balanced/codex/agents/tester.toml").write_text('model = "bad\n')
        before = snapshot(self.base, True)
        with self.assertRaises(tomllib.TOMLDecodeError):
            self.plan(source)
        self.assertEqual(snapshot(self.base, True), before)

    def test_source_contract_mismatch_is_preflight_only(self):
        source = self.source_copy()
        path = source / "profiles/azhou-balanced/codex/config.toml"
        path.write_text(path.read_text().replace('"gpt-6.1-sol"', '"other"'))
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan(source)
        self.assertEqual(snapshot(self.base, True), before)

    def test_source_config_and_instructions_symlinks_are_refused(self):
        source = self.source_copy()
        for relative in ["codex/config.toml", "AGENTS.md"]:
            with self.subTest(relative=relative):
                path = source / "profiles/azhou-balanced" / relative
                original = path.read_bytes()
                outside = self.base / "external-source"
                outside.write_bytes(original)
                path.unlink()
                path.symlink_to(outside)
                before = snapshot(self.base, True)
                try:
                    with self.assertRaises(installer.InstallError):
                        self.plan(source)
                    self.assertEqual(snapshot(self.base, True), before)
                finally:
                    path.unlink()
                    path.write_bytes(original)

    def test_personal_managed_instruction_change_is_refused(self):
        self.install()
        path = self.home / "AGENTS.md"
        path.write_bytes(path.read_bytes().replace(installer.BEGIN.encode(), installer.BEGIN.encode() + b"\nPersonal amendment"))
        before = snapshot(self.base, True)
        with self.assertRaises(installer.InstallError):
            self.plan()
        self.assertEqual(snapshot(self.base, True), before)

    def test_multiline_and_comment_content_survives_all_key_styles(self):
        preamble = '# Personal header\nnotes = """\nmodel = \'inside multiline\'\n[agents]\n# not a TOML comment\n"""\nitems = [\n "a", # item comment\n "b",\n]\n'
        styles = [
            '"model" = "old" # model annotation\n["agents"] # agents annotation\n"enabled" = false # enabled annotation\n',
            'model = "old" # model annotation\nagents.enabled = false # enabled annotation\n',
            'model = "old" # model annotation\n[agents]\nenabled = false # enabled annotation\n',
        ]
        suffix = '[mcp_servers."literal.with.dots"]\ncommand = "keep"\n'
        for style in styles:
            with self.subTest(style=style):
                original = preamble + style + suffix
                merged = installer.merge_config(original)
                parsed = tomllib.loads(merged)
                self.assertEqual(parsed["notes"], tomllib.loads(original)["notes"])
                self.assertEqual(parsed["items"], ["a", "b"])
                self.assertEqual(parsed["mcp_servers"], tomllib.loads(original)["mcp_servers"])
                self.assertIn(preamble, merged)
                self.assertIn(suffix, merged)
                self.assertIn("# model annotation", merged)
                self.assertIn("# enabled annotation", merged)
                self.assertEqual(parsed["model"], "gpt-6.1-sol")
                self.assertTrue(parsed["agents"]["enabled"])
                self.assertEqual(installer.merge_config(merged), merged)

    def test_crlf_and_obsolete_setting_comment_survive_merge(self):
        original = '# header\r\nmodel = "old" # model\r\n[agents]\r\nmax_threads = 10 # legacy annotation\r\nenabled = false\r\n'
        merged = installer.merge_config(original)
        self.assertNotIn("max_threads", tomllib.loads(merged)["agents"])
        self.assertIn("# legacy annotation\r\n", merged)
        self.assertNotIn("\n", merged.replace("\r\n", ""))

    def test_aggregate_owned_settings_fail_without_silent_reinterpretation(self):
        for original in ['agents = {enabled = false}\n', 'agents = {enabled = false, custom = 123}\n']:
            with self.subTest(original=original), self.assertRaises(installer.InstallError):
                installer.merge_config(original)

    def assert_write_failure_restores(self, existing):
        if existing:
            self.put("config.toml", '# private\nmodel = "previous"\n', 0o640)
            self.put("AGENTS.md", "Personal instructions\n", 0o644)
        before = snapshot(self.base)
        plan = self.plan()
        calls = []
        def fail_after_actual_write(path, data, mode):
            calls.append(path)
            installer.atomic_write(path, data, mode)
            if len(calls) == 8:
                raise OSError("independent fault after rename")
        with self.assertRaisesRegex(installer.InstallError, "restored"):
            installer.apply_plan(plan, write=fail_after_actual_write)
        self.assertEqual(len(calls), 8)
        self.assertEqual(snapshot(self.base), before)

    def test_mid_write_failure_restores_fresh_install_and_removes_new_dirs(self):
        self.assert_write_failure_restores(existing=False)

    def test_mid_write_failure_restores_existing_bytes_and_modes(self):
        self.assert_write_failure_restores(existing=True)

    def test_verification_failure_restores_existing_bytes_and_new_files(self):
        self.put("config.toml", 'model = "previous"\n', 0o640)
        self.put("AGENTS.md", "Keep me.\n", 0o644)
        before = snapshot(self.base)
        def reject():
            self.assertTrue((self.home / "agents/worker.toml").exists())
            raise RuntimeError("native discovery rejected")
        with self.assertRaisesRegex(installer.InstallError, "native discovery rejected"):
            installer.apply_plan(self.plan(), verify=reject)
        self.assertEqual(snapshot(self.base), before)

    def test_changed_after_preflight_refuses_before_any_install_writes(self):
        self.put("config.toml", 'model = "original"\n')
        plan = self.plan()
        self.put("config.toml", 'model = "external edit"\n')
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "changed after preflight"):
            installer.apply_plan(plan)
        self.assertEqual(snapshot(self.base, True), before)

    def test_unchanged_plan_still_detects_changed_after_preflight(self):
        self.install()
        plan = self.plan()
        self.assertEqual(plan["changes"], {})
        path = self.home / "agents/worker.toml"
        path.write_bytes(path.read_bytes() + b"\n# concurrent personal edit\n")
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "changed after preflight"):
            installer.apply_plan(plan)
        self.assertEqual(snapshot(self.base, True), before)

    def test_retained_interruption_journal_recovers_exact_original_tree(self):
        self.put("config.toml", 'model = "original"\n', 0o640)
        before = snapshot(self.base)
        plan = self.plan()
        count = 0
        def interrupt(path, data, mode):
            nonlocal count
            installer.atomic_write(path, data, mode)
            count += 1
            if count == 8:
                raise RuntimeError("interruption")
        # A killed process cannot run rollback. Keep its real journal to model that.
        with patch.object(installer, "restore", side_effect=OSError("process stopped")):
            with self.assertRaisesRegex(installer.InstallError, "rollback needs attention"):
                installer.apply_plan(plan, write=interrupt)
        self.assertTrue((plan["transaction"] / "journal.json").is_file())
        with self.assertRaisesRegex(installer.InstallError, "Unfinished transaction"):
            self.plan()
        installer.recover(self.home, self.skills)
        self.assertEqual(snapshot(self.base), before)

    def test_recovery_refuses_external_target_in_journal(self):
        tx = self.home / ".agent-orchestration-kit-transaction"
        tx.mkdir(parents=True)
        victim = self.base / "unrelated"
        victim.write_bytes(b"private")
        journal = {"schema": 1, "created_directories": [], "files": [{"path": str(victim), "before": None, "after_sha256": installer.sha(b"private"), "mode": 0o600}]}
        (tx / "journal.json").write_text(json.dumps(journal))
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "unexpected target"):
            installer.recover(self.home, self.skills)
        self.assertEqual(snapshot(self.base, True), before)

    def test_shell_missing_python_stops_without_target_changes(self):
        empty_path = self.base / "empty-bin"
        empty_path.mkdir()
        # dirname is used by setup itself, before dependency checking.
        dirname = shutil.which("dirname")
        self.assertIsNotNone(dirname)
        (empty_path / "dirname").symlink_to(dirname)
        before = snapshot(self.base, True)
        env = dict(os.environ, PATH=str(empty_path), HOME=str(self.base / "personal"), CODEX_HOME=str(self.home))
        result = subprocess.run(["/bin/sh", str(ROOT / "setup.sh"), "--dry-run"], env=env, text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.11", result.stderr)
        self.assertEqual(snapshot(self.base, True), before)


class PstackCoexistenceTests(unittest.TestCase):
    """The shipped compatibility verdict: registration plus the sheet's routing
    switch decide; a sheet, visible Skills, or a cached copy alone proves nothing."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.skills = self.base / "skills"

    def put(self, relative, data, mode=0o640):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(mode)
        return path

    def put_plugin_copy(self, relative="plugins/cache/pstack-claude/pstack/0.9.103"):
        return self.put(f"{relative}/.codex-plugin/plugin.json", '{"name": "pstack"}')

    def put_sheet(self, body):
        return self.put("pstack-models.md", body)

    def test_sheet_hook_reading_mirrors_the_session_hook(self):
        self.assertIsNone(installer.pstack_sheet_hook(None))
        self.assertEqual(installer.pstack_sheet_hook(b"# c\nsession hook: off\n"), "off")
        self.assertEqual(installer.pstack_sheet_hook(b"# c\nsession hook: on\n"), "on")
        self.assertEqual(installer.pstack_sheet_hook(b"# c\n"), "on")
        self.assertEqual(installer.pstack_sheet_hook(b"# c\nsession hook: off  \n"), "on")
        self.assertEqual(installer.pstack_sheet_hook(b"\xef\xbb\xbf# c\r\nsession hook: off\r\n"), "off")
        self.assertEqual(installer.pstack_sheet_hook("# c\nsession hook: off\n".encode("utf-16")), "off")
        self.assertEqual(installer.pstack_sheet_hook(b"\xff\xfe\x01"), "on")
        self.assertEqual(installer.pstack_sheet_hook(b"\x81\x82\x83"), "on")

    def test_verdict_separates_every_evidence_stream(self):
        self.assertIsNone(installer.pstack_coexistence(self.home)["shared_skills_visible"])
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertEqual(verdict["auto_routing"], "not-armed")
        self.assertTrue(verdict["compatible"])
        self.assertFalse(verdict["model_sheet_present"])
        self.assertIsNone(verdict["session_hook"])
        self.assertFalse(verdict["native_plugin_present"])
        self.assertFalse(verdict["config_registration_present"])
        self.assertFalse(verdict["shared_skills_visible"])
        self.assertIn("unknown", verdict["hook_trust"])
        # A sheet alone, even one saying on, is not routing evidence.
        self.put_sheet("# sheet\nsession hook: on\n")
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertEqual(verdict["auto_routing"], "not-armed")
        self.assertEqual(verdict["session_hook"], "on")
        # Visible shared pstack Skills are reported, never treated as routing.
        (self.skills / "poteto-mode").mkdir(parents=True)
        (self.skills / "poteto-mode/SKILL.md").write_text("fixture", encoding="utf-8")
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertTrue(verdict["shared_skills_visible"])
        self.assertEqual(verdict["auto_routing"], "not-armed")
        # Registration arms routing until the sheet switches it off.
        self.put_plugin_copy()
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertEqual(verdict["auto_routing"], "on")
        self.assertFalse(verdict["compatible"])
        self.assertIn("session hook: off", verdict["reason"])
        self.put_sheet("# sheet\nsession hook: off\n")
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertEqual(verdict["auto_routing"], "off")
        self.assertTrue(verdict["compatible"])

    def test_config_registration_arms_and_off_sheet_disarms(self):
        self.put("config.toml", '[plugins."pstack@pstack-claude"]\nenabled = true\n')
        verdict = installer.pstack_coexistence(self.home)
        self.assertTrue(verdict["config_registration_present"])
        self.assertEqual(verdict["auto_routing"], "on")
        self.assertFalse(verdict["compatible"])
        self.put_sheet("session hook: off\n")
        verdict = installer.pstack_coexistence(self.home)
        self.assertEqual(verdict["auto_routing"], "off")

    def test_duplicate_copies_and_symlinked_state_are_errors(self):
        self.put_plugin_copy("plugins/cache/one")
        self.put_plugin_copy("plugins/cache/two")
        with self.assertRaisesRegex(installer.InstallError, "Duplicate pstack plugin copies"):
            installer.pstack_coexistence(self.home)
        shutil.rmtree(self.home / "plugins")
        outside = self.base / "outside-plugins"
        outside.mkdir()
        (outside / "marker").write_text("x", encoding="utf-8")
        (self.home / "plugins").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError, "[Ss]ymbolic link"):
            installer.pstack_coexistence(self.home)

    def test_armed_target_blocks_the_install_before_any_write(self):
        self.put_plugin_copy()
        before = snapshot(self.base)
        with self.assertRaisesRegex(installer.InstallError, "session hook: off"):
            installer.build_plan(ROOT, self.home, self.skills)
        self.assertEqual(snapshot(self.base), before)

    def test_installed_kit_replans_as_exact_noop_beside_compatible_pstack(self):
        plan = installer.build_plan(ROOT, self.home, self.skills)
        installer.apply_plan(plan)
        self.put_plugin_copy()
        self.put_sheet("session hook: off\n")
        before = snapshot(self.base, timestamps=True)
        plan = installer.build_plan(ROOT, self.home, self.skills)
        self.assertEqual(plan["changes"], {})
        self.assertEqual(plan["pstack_coexistence"]["auto_routing"], "off")
        self.assertEqual(installer.apply_plan(plan), 0)
        self.assertEqual(snapshot(self.base, timestamps=True), before)
        self.assertEqual((self.home / "pstack-models.md").read_text(), "session hook: off\n")


class UninstallTests(unittest.TestCase):
    """Exiting a completed installation through the Kit's own public entry.

    Uninstall restores the recorded pre-install managed content by owned scope
    and leaves unrelated files, later additions and other modules alone; it is
    a different operation from ``--recover`` (interrupted-transaction restore).
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "personal/.codex"
        self.skills = self.base / "personal/.agents/skills"
        self.skill_source = (ROOT / "profiles/azhou-balanced/agents/skills/astra-orchestrator/SKILL.md").read_bytes()

    def put(self, relative, data, mode=0o640):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(mode)
        return path

    def install(self):
        plan = installer.build_plan(ROOT, self.home, self.skills)
        installer.apply_plan(plan)
        return plan

    def uninstall(self):
        plan = installer.build_uninstall_plan(self.home, self.skills)
        return installer.apply_uninstall(plan)

    def test_uninstall_restores_owned_scopes_and_keeps_pstack_and_unrelated_content(self):
        original_config = '# Personal preferences\napproval_policy = "never"\nmodel = "old"\n[mcp_servers.notes]\ncommand = "notes"\n'
        self.put("config.toml", original_config)
        instructions = self.put("AGENTS.md", "Personal instructions.\n", 0o600)
        custom = self.put("agents/my-helper.toml", 'name = "my-helper"\nmodel = "custom"\n')
        self.install()
        # Another module and later user content arrive after the Kit install.
        sheet = self.put("pstack-models.md", "# pstack model configuration\nsession hook: off\n")
        self.put("plugins/cache/pstack-claude/pstack/0.9.103/.codex-plugin/plugin.json", '{"name": "pstack"}')
        config = self.home / "config.toml"
        config.write_bytes(config.read_bytes() + b'[plugins."pstack@pstack-claude"]\nenabled = true\n')
        before = snapshot(self.base)

        result = self.uninstall()
        self.assertEqual(result["status"], "uninstalled")
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed["model"], "old")
        self.assertEqual(parsed["approval_policy"], "never")
        self.assertEqual(parsed["mcp_servers"]["notes"]["command"], "notes")
        self.assertEqual(parsed["plugins"]["pstack@pstack-claude"]["enabled"], True)
        self.assertNotIn("enabled", parsed.get("agents", {}))
        self.assertNotIn("service_tier", parsed)
        self.assertEqual(instructions.read_bytes(), b"Personal instructions.\n")
        self.assertEqual(stat.S_IMODE(instructions.stat().st_mode), 0o600)
        self.assertFalse((self.home / "agent-orchestration-kit/state.json").exists())
        for name in installer.ROLE_MODELS:
            self.assertFalse((self.home / f"agents/{name}.toml").exists())
        self.assertFalse((self.skills / "astra-orchestrator/SKILL.md").exists())
        self.assertEqual(custom.read_bytes(), b'name = "my-helper"\nmodel = "custom"\n')
        self.assertEqual(sheet.read_bytes(), b"# pstack model configuration\nsession hook: off\n")
        # pstack stays usable in its retained mode after the Kit exit.
        verdict = installer.pstack_coexistence(self.home, self.skills)
        self.assertEqual(verdict["auto_routing"], "off")
        self.assertTrue(verdict["compatible"])
        self.assertTrue(verdict["model_sheet_present"])

    def test_uninstall_retains_adopted_pre_existing_files_and_recorded_block(self):
        managed_block = installer.owned_block((ROOT / "profiles/azhou-balanced/AGENTS.md").read_text())
        instructions = self.put("AGENTS.md", "Pre-existing setup.\n\n" + managed_block + "\n")
        adopted_skill = self.skills / "astra-orchestrator/SKILL.md"
        adopted_skill.parent.mkdir(parents=True)
        adopted_skill.write_bytes(self.skill_source)
        self.install()
        plan = installer.build_uninstall_plan(self.home, self.skills)
        self.assertIn("restore the recorded pre-install instruction block", plan["instruction_block"])
        self.assertIn(str(adopted_skill), plan["retained_pre_existing"])

        def observed(path):
            return (path.read_bytes(), path.stat().st_mtime_ns, stat.S_IMODE(path.stat().st_mode))

        before_skill, before_instructions = observed(adopted_skill), observed(instructions)
        result = installer.apply_uninstall(plan)
        self.assertEqual(result["status"], "uninstalled")
        # Pre-existing adopted content is untouched, not deleted or rewritten.
        self.assertEqual(observed(adopted_skill), before_skill)
        self.assertEqual(observed(instructions), before_instructions)
        self.assertFalse((self.home / "agent-orchestration-kit/state.json").exists())
        # Retained pre-existing content is no longer kit-owned: a repeat reports
        # it for manual review instead of a clean no-op or a deletion.
        with self.assertRaisesRegex(installer.InstallError, "source is unknown"):
            installer.build_uninstall_plan(self.home, self.skills)
        self.assertEqual(observed(adopted_skill), before_skill)
        self.assertEqual(observed(instructions), before_instructions)

    def test_user_modified_owned_content_stops_uninstall_with_differences(self):
        self.install()
        config = self.home / "config.toml"
        role = self.home / "agents/worker.toml"
        instructions = self.home / "AGENTS.md"
        cases = [
            ("owned key", config, config.read_bytes(),
             config.read_bytes().replace(b'model = "gpt-6.1-sol"', b'model = "personal"', 1),
             'model (installed {"present": true, "value": "gpt-6.1-sol"}'),
            ("owned file", role, role.read_bytes(), role.read_bytes() + b"\n# user amendment\n",
             f"{role} (recorded sha256 "),
            ("managed block", instructions, instructions.read_bytes(),
             instructions.read_bytes().replace(installer.BEGIN.encode(), installer.BEGIN.encode() + b"\nPersonal amendment", 1),
             f"{instructions} managed block (recorded sha256 "),
        ]
        for label, path, original, edited, fragment in cases:
            with self.subTest(case=label):
                path.write_bytes(edited)
                before = snapshot(self.base, True)
                with self.assertRaisesRegex(installer.InstallError,
                                            "User-modified owned content stops uninstall.*" + re.escape(fragment)):
                    installer.build_uninstall_plan(self.home, self.skills)
                # The refusal writes nothing and keeps the user's edit in place.
                self.assertEqual(snapshot(self.base, True), before)
                path.write_bytes(original)
        # With the owned scope intact again, the exit proceeds.
        self.assertEqual(self.uninstall()["status"], "uninstalled")

    def test_uninstall_reports_the_difference_it_refuses_to_overwrite(self):
        self.install()
        role = self.home / "agents/worker.toml"
        role.write_bytes(role.read_bytes() + b"\n# user amendment\n")
        try:
            installer.build_uninstall_plan(self.home, self.skills)
            self.fail("expected a refusal")
        except installer.InstallError as exc:
            message = str(exc)
            self.assertIn(f"recorded sha256 {installer.sha((ROOT / 'profiles/azhou-balanced/codex/agents/worker.toml').read_bytes())}", message)
            self.assertIn("found sha256 ", message)

    def test_unknown_source_without_a_record_is_never_adopted_or_removed(self):
        instructions = self.put("AGENTS.md", installer.BEGIN + "\nstray block without a record\n" + installer.END + "\n")
        role = self.put("agents/worker.toml", 'name = "worker"\n')
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "source is unknown"):
            installer.build_uninstall_plan(self.home, self.skills)
        self.assertEqual(snapshot(self.base, True), before)
        instructions.write_bytes(b"No marker left.\n")
        before = snapshot(self.base, True)
        with self.assertRaisesRegex(installer.InstallError, "source is unknown"):
            installer.build_uninstall_plan(self.home, self.skills)
        self.assertEqual(snapshot(self.base, True), before)
        role.unlink()
        # A target with no owned footprint converges to a clean no-op.
        plan = installer.build_uninstall_plan(self.home, self.skills)
        self.assertEqual(plan["operation"], "noop")
        self.assertEqual(installer.apply_uninstall(plan)["changed_files_count"], 0)

    def test_unrecognized_or_incomplete_record_is_refused(self):
        for content in ['{"schema": 2, "project": "agent-orchestration-kit"}',
                        '{"schema": 1, "project": "other"}',
                        '{"schema": 1, "project": "agent-orchestration-kit", "targets": {}, "files": {}}']:
            with self.subTest(record=content):
                self.put("agent-orchestration-kit/state.json", content)
                before = snapshot(self.base, True)
                with self.assertRaisesRegex(installer.InstallError, "nrecognized|changed"):
                    installer.build_uninstall_plan(self.home, self.skills)
                self.assertEqual(snapshot(self.base, True), before)

    def test_unfinished_transaction_directs_to_recover_not_uninstall(self):
        self.install()
        tx = self.home / ".agent-orchestration-kit-transaction"
        tx.mkdir(parents=True)
        (tx / "journal.json").write_text('{"schema": 1, "created_directories": [], "files": []}')
        with self.assertRaisesRegex(installer.InstallError, "run --recover"):
            installer.build_uninstall_plan(self.home, self.skills)

    def test_mid_uninstall_failure_restores_the_installed_state(self):
        self.install()
        before = snapshot(self.base)
        plan = installer.build_uninstall_plan(self.home, self.skills)
        calls = []

        def fail_after_actual_write(path, data, mode):
            calls.append(path)
            installer.atomic_write(path, data, mode)
            if len(calls) == 1:
                raise OSError("independent fault after rename")

        with self.assertRaisesRegex(installer.InstallError, "restored"):
            installer.apply_uninstall(plan, write=fail_after_actual_write)
        self.assertEqual(snapshot(self.base), before)
        self.assertFalse((self.home / ".agent-orchestration-kit-transaction").exists())

    def test_interrupted_uninstall_recovers_to_installed_and_retries(self):
        self.install()
        before = snapshot(self.base)
        plan = installer.build_uninstall_plan(self.home, self.skills)
        calls = []

        def interrupt(path, data, mode):
            calls.append(path)
            installer.atomic_write(path, data, mode)
            if len(calls) == 1:
                raise RuntimeError("interruption")

        # A killed process cannot run rollback. Keep its real journal to model that.
        with patch.object(installer, "restore", side_effect=OSError("process stopped")):
            with self.assertRaisesRegex(installer.InstallError, "rollback needs attention"):
                installer.apply_uninstall(plan, write=interrupt)
        self.assertTrue((plan["transaction"] / "journal.json").is_file())
        with self.assertRaisesRegex(installer.InstallError, "Unfinished transaction"):
            installer.build_uninstall_plan(self.home, self.skills)
        installer.recover(self.home, self.skills)
        self.assertEqual(snapshot(self.base), before)
        self.assertEqual(self.uninstall()["status"], "uninstalled")

    def test_cli_uninstall_entry_exits_and_repeats_converge(self):
        self.install()
        self.assertTrue((self.home / "agent-orchestration-kit/state.json").is_file())
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        script = str(ROOT / "scripts/install_codex.py")
        common_args = [sys.executable, script, "--codex-home", str(self.home), "--skills-dir", str(self.skills)]

        dry = subprocess.run([*common_args, "--uninstall", "--dry-run"], env=env, text=True, capture_output=True, timeout=60)
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertIn("no target files written", dry.stdout)
        self.assertTrue((self.home / "agent-orchestration-kit/state.json").is_file())

        first = subprocess.run([*common_args, "--uninstall"], env=env, text=True, capture_output=True, timeout=60)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertIn("Uninstalled", first.stdout)
        self.assertFalse((self.home / "agent-orchestration-kit/state.json").exists())
        for name in installer.ROLE_MODELS:
            self.assertFalse((self.home / f"agents/{name}.toml").exists())

        repeat = subprocess.run([*common_args, "--uninstall"], env=env, text=True, capture_output=True, timeout=60)
        self.assertEqual(0, repeat.returncode, repeat.stderr)
        self.assertIn("Nothing owned by this installation remains", repeat.stdout)

        conflict = subprocess.run([*common_args, "--uninstall", "--recover"], env=env, text=True, capture_output=True, timeout=60)
        self.assertNotEqual(0, conflict.returncode)
        self.assertIn("choose one", conflict.stderr)

        # An interrupted operation is recovered by --recover, a separate path.
        tx = self.home / ".agent-orchestration-kit-transaction"
        tx.mkdir(parents=True)
        (tx / "journal.json").write_text('{"schema": 1, "created_directories": [], "files": []}')
        recover = subprocess.run([*common_args, "--recover"], env=env, text=True, capture_output=True, timeout=60)
        self.assertEqual(0, recover.returncode, recover.stderr)
        self.assertIn("Interrupted operation restored", recover.stdout)
        self.assertIn("--uninstall", recover.stdout)
        self.assertFalse(tx.exists())


if __name__ == "__main__":
    unittest.main()

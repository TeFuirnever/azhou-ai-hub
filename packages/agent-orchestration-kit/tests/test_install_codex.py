"""Independent filesystem/semantic tests; never invokes a Codex runtime."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
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


if __name__ == "__main__":
    unittest.main()

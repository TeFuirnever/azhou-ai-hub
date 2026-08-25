from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import azhou_hub


class AzhouHubCliTest(unittest.TestCase):
    def test_info_json_exposes_stable_commands_and_installable_skills(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = azhou_hub.main(["info", "--json"])

        self.assertEqual(0, result)
        payload = json.loads(stream.getvalue())
        self.assertEqual("azhou-ai-hub.info.v1", payload["schema_version"])
        self.assertEqual(["doctor", "info", "setup", "verify", "version"], payload["commands"])
        self.assertIn("repo-pedant", payload["installable_skills"])
        self.assertEqual(sorted(payload["installable_skills"]), payload["installable_skills"])

    def test_version_json_never_manufactures_a_release_version(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = azhou_hub.main(["version", "--json"])

        self.assertEqual(0, result)
        payload = json.loads(stream.getvalue())
        self.assertEqual("azhou-ai-hub.version.v1", payload["schema_version"])
        self.assertIn("commit", payload)
        self.assertIn("dirty", payload)
        self.assertNotIn("installed_version", payload)

    def test_setup_link_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"

            first = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=False,
            )
            second = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=False,
            )

            installed = target / "repo-pedant"
            self.assertTrue(installed.is_symlink())
            self.assertEqual((azhou_hub.ROOT / "skills/repo-pedant").resolve(), installed.resolve())
            self.assertEqual("pass", first["status"])
            self.assertEqual("installed", first["skills"][0]["status"])
            self.assertEqual("pass", second["status"])
            self.assertEqual("current", second["skills"][0]["status"])

    def test_setup_copy_is_idempotent_and_detects_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            source = root / "skills" / "sample"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("version one\n", encoding="utf-8")
            target = Path(directory) / "installed"

            first = azhou_hub.setup_skills(
                root=root,
                target=target,
                skills=["sample"],
                mode="copy",
                dry_run=False,
            )
            current = azhou_hub.setup_skills(
                root=root,
                target=target,
                skills=["sample"],
                mode="copy",
                dry_run=False,
            )
            (source / "SKILL.md").write_text("version two\n", encoding="utf-8")
            stale = azhou_hub.setup_skills(
                root=root,
                target=target,
                skills=["sample"],
                mode="copy",
                dry_run=False,
            )

            self.assertEqual("installed", first["skills"][0]["status"])
            self.assertEqual("current", current["skills"][0]["status"])
            self.assertEqual("fail", stale["status"])
            self.assertEqual("conflict", stale["skills"][0]["status"])
            self.assertEqual("version one\n", (target / "sample" / "SKILL.md").read_text(encoding="utf-8"))

    def test_setup_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"

            receipt = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=True,
            )

            self.assertEqual("dry_run", receipt["status"])
            self.assertEqual("planned", receipt["skills"][0]["status"])
            self.assertFalse(target.exists())

    def test_setup_collision_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            collision = target / "repo-pedant"
            collision.mkdir(parents=True)
            marker = collision / "keep.txt"
            marker.write_text("user owned\n", encoding="utf-8")

            receipt = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=False,
            )

            self.assertEqual("fail", receipt["status"])
            self.assertEqual("conflict", receipt["skills"][0]["status"])
            self.assertEqual("user owned\n", marker.read_text(encoding="utf-8"))

    def test_setup_conflict_blocks_other_planned_installs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            for name in ("conflict", "planned"):
                source = root / "skills" / name
                source.mkdir(parents=True)
                (source / "SKILL.md").write_text(f"{name}\n", encoding="utf-8")
            target = Path(directory) / "skills"
            collision = target / "conflict"
            collision.mkdir(parents=True)
            (collision / "SKILL.md").write_text("user owned\n", encoding="utf-8")

            receipt = azhou_hub.setup_skills(
                root=root,
                target=target,
                skills=["conflict", "planned"],
                mode="link",
                dry_run=False,
            )

            self.assertEqual("fail", receipt["status"])
            self.assertFalse((target / "planned").exists())

    def test_setup_rejects_a_target_root_that_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            target.write_text("not a directory\n", encoding="utf-8")

            receipt = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=False,
            )

            self.assertEqual("fail", receipt["status"])
            self.assertEqual("target root exists and is not a directory", receipt["error"])

    def test_setup_cli_returns_json_when_a_target_parent_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            source = root / "skills" / "sample"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("sample\n", encoding="utf-8")
            blocked_parent = Path(directory) / "blocked"
            blocked_parent.write_text("not a directory\n", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                result = azhou_hub.main(
                    [
                        "setup",
                        "--skill",
                        "sample",
                        "--target",
                        str(blocked_parent / "skills"),
                        "--apply",
                        "--json",
                    ],
                    root=root,
                )

            self.assertEqual(1, result)
            payload = json.loads(stream.getvalue())
            self.assertEqual("azhou-ai-hub.setup.v1", payload["schema_version"])
            self.assertEqual("fail", payload["status"])
            self.assertIn("not a directory", payload["error"])

    def test_setup_rejects_skill_names_that_escape_the_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"

            receipt = azhou_hub.setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["../outside"],
                mode="link",
                dry_run=False,
            )

            self.assertEqual("fail", receipt["status"])
            self.assertEqual("conflict", receipt["skills"][0]["status"])
            self.assertFalse(target.exists())

    def test_setup_cli_defaults_to_dry_run_and_requires_apply_for_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            source = root / "skills" / "sample"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("sample\n", encoding="utf-8")
            target = Path(directory) / "installed"

            with redirect_stdout(io.StringIO()):
                preview_result = azhou_hub.main(
                    ["setup", "--skill", "sample", "--target", str(target), "--json"],
                    root=root,
                )
            self.assertEqual(0, preview_result)
            self.assertFalse(target.exists())

            with redirect_stdout(io.StringIO()):
                apply_result = azhou_hub.main(
                    ["setup", "--skill", "sample", "--target", str(target), "--apply", "--json"],
                    root=root,
                )
            self.assertEqual(0, apply_result)
            self.assertTrue((target / "sample").is_symlink())

    def test_doctor_reports_wrong_link_target_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            wrong = Path(directory) / "wrong"
            wrong.mkdir()
            target.mkdir()
            (target / "repo-pedant").symlink_to(wrong, target_is_directory=True)

            report = azhou_hub.run_doctor(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                run_verification=False,
            )

            self.assertFalse(report["valid"])
            self.assertEqual("unhealthy", report["status"])
            target_check = next(check for check in report["checks"] if check["name"] == "target:repo-pedant")
            self.assertEqual("fail", target_check["status"])

    def test_doctor_rejects_a_target_with_a_file_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            blocked_parent = Path(directory) / "blocked"
            blocked_parent.write_text("not a directory\n", encoding="utf-8")

            report = azhou_hub.run_doctor(
                root=azhou_hub.ROOT,
                target=blocked_parent / "skills",
                skills=["repo-pedant"],
                run_verification=False,
            )

            self.assertFalse(report["valid"])
            self.assertEqual("unhealthy", report["status"])
            target_check = next(check for check in report["checks"] if check["name"] == "installation_target")
            self.assertEqual("fail", target_check["status"])
            self.assertIn("target ancestor is not a directory", target_check["details"])

    def test_doctor_verification_status_controls_exit_health(self) -> None:
        completed = mock.Mock(returncode=7, stdout="", stderr="broken gate\n")
        with mock.patch("scripts.azhou_hub.subprocess.run", return_value=completed):
            report = azhou_hub.run_doctor(
                root=azhou_hub.ROOT,
                target=None,
                skills=["repo-pedant"],
                run_verification=True,
            )

        self.assertFalse(report["valid"])
        verification = next(check for check in report["checks"] if check["name"] == "repository_verification")
        self.assertEqual("fail", verification["status"])
        self.assertIn("exit 7", verification["details"])

    def test_verify_command_preserves_the_authoritative_exit_code(self) -> None:
        completed = mock.Mock(returncode=9)
        with mock.patch("scripts.azhou_hub.subprocess.run", return_value=completed) as run:
            result = azhou_hub.main(["verify", "--python", "/custom/python"])

        self.assertEqual(9, result)
        run.assert_called_once_with(
            ["/custom/python", str(azhou_hub.ROOT / "scripts/verify.py"), "--python", "/custom/python"],
            cwd=azhou_hub.ROOT,
            check=False,
        )

    def test_documented_direct_script_verify_invocation_does_not_require_package_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            scripts = root / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(azhou_hub.ROOT / "scripts/azhou_hub.py", scripts / "azhou_hub.py")
            (scripts / "verify.py").write_text("raise SystemExit(6)\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(scripts / "azhou_hub.py"), "verify"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(6, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()

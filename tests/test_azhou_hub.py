from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
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
from scripts import verify as verify_script


AZHOU_SKILL_NAMES = (
    "azhou-doctor",
    "azhou-info",
    "azhou-setup",
    "azhou-verify",
)


class AzhouHubCliTest(unittest.TestCase):
    def _json_main(self, argv: list[str], *, root: Path | None = None, auto_plan: bool = True) -> tuple[int, dict]:
        if auto_plan and "setup" in argv and "--apply" in argv and "--plan-id" not in argv:
            dry_argv = [item for item in argv if item not in {"--apply"}]
            dry_result, dry_payload = self._json_main(dry_argv, root=root, auto_plan=False)
            if dry_payload.get("planId"):
                argv = [*argv, "--plan-id", dry_payload["planId"]]
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = azhou_hub.main(argv, root=root or azhou_hub.ROOT)
        return result, json.loads(stream.getvalue())

    def _fixture_repo(self, directory: str) -> tuple[Path, Path, Path]:
        root = Path(directory) / "repo"
        source = root / "skills" / "sample"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("sample\n", encoding="utf-8")
        (root / "README.md").write_text("fixture\n", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "skill-standard.md").write_text("fixture\n", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "verify.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        return root, source, Path(directory) / "installed"

    def _managed_fixture(self, directory: str, mode: str = "link") -> tuple[Path, Path, Path]:
        root, source, target = self._fixture_repo(directory)
        receipt = target / ".azhou/hub" / "receipts" / "sample.json"
        result, payload = self._json_main(
            [
                "setup", "--managed", "--receipt", str(receipt), "--skill", "sample",
                "--target", str(target), "--mode", mode, "--apply", "--json",
            ],
            root=root,
        )
        self.assertEqual(0, result, payload)
        self.assertEqual("pass", payload["status"])
        return root, target, receipt

    def _setup_skills(self, **kwargs):
        if kwargs.get("dry_run"):
            return azhou_hub.setup_skills(**kwargs)
        preview = azhou_hub.setup_skills(**{**kwargs, "dry_run": True})
        if "planId" not in preview:
            return azhou_hub.setup_skills(**kwargs)
        return azhou_hub.setup_skills(**kwargs, plan_id=preview["planId"])

    def _legacy_package_digest(self, package: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(
            (candidate for candidate in package.rglob("*") if candidate.is_file()),
            key=lambda candidate: candidate.relative_to(package).as_posix(),
        ):
            digest.update(path.relative_to(package).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def _write_legacy_receipt(
        self, receipt: Path, *, mode: str, source: Path, destination: Path
    ) -> None:
        legacy = json.loads(receipt.read_text(encoding="utf-8"))
        source_digest = self._legacy_package_digest(source)
        legacy["schema"] = "azhou-ai-hub.install-receipt.v1"
        legacy["skills"][0].update(
            {
                "installed_identity": mode,
                "source_digest": source_digest,
                "installed_digest": (
                    source_digest
                    if mode == "link"
                    else self._legacy_package_digest(destination)
                ),
            }
        )
        legacy.pop("integrity_digest")
        canonical = json.dumps(
            legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        legacy["integrity_digest"] = hashlib.sha256(canonical).hexdigest()
        receipt.write_text(json.dumps(legacy), encoding="utf-8")

    def test_info_json_exposes_stable_commands_and_installable_skills(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = azhou_hub.main(["info", "--json"])

        self.assertEqual(0, result)
        payload = json.loads(stream.getvalue())
        self.assertEqual("azhou-ai-hub.info.v1", payload["schema_version"])
        self.assertEqual(["doctor", "info", "setup", "verify", "version"], payload["primary_commands"])
        self.assertEqual(payload["primary_commands"], payload["commands"])
        self.assertEqual(
            ["hub", "llm-wiki", "repo-pedant"],
            payload["runtime_state"]["namespaces"],
        )
        self.assertEqual(
            [".azhou-ai-hub/receipts", ".llm-wiki", ".omc/wiki", ".repo-pedant"],
            payload["runtime_state"]["compatibility_sources"],
        )
        self.assertEqual(
            [
                "arch-doc",
                "autoresearch",
                *AZHOU_SKILL_NAMES,
                "eli5",
                "excalidraw-diagram",
                "lavish",
                "llm-wiki",
                "repo-pedant",
                "super-caveman",
            ],
            payload["installable_skills"],
        )

    def test_azhou_skill_packages_install_and_doctor_cleanly(self) -> None:
        for name in AZHOU_SKILL_NAMES:
            with self.subTest(skill=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "skills"
                args = [
                    "setup", "--skill", name, "--target", str(target),
                    "--mode", "copy", "--json",
                ]

                result, dry_run = self._json_main(args)

                self.assertEqual(0, result, dry_run)
                self.assertEqual("dry_run", dry_run["status"])
                self.assertFalse(target.exists())

                result, applied = self._json_main([*args[:-1], "--apply", "--json"])

                self.assertEqual(0, result, applied)
                self.assertEqual("pass", applied["status"])
                self.assertEqual("installed", applied["skills"][0]["status"])

                result, doctor = self._json_main(
                    ["doctor", "--skill", name, "--target", str(target), "--json"]
                )

                self.assertEqual(0, result, doctor)
                self.assertEqual("healthy", doctor["status"])
                checks = {check["name"]: check for check in doctor["checks"]}
                self.assertEqual("pass", checks["target:hub-receipts"]["status"])
                checks = {check["name"]: check for check in doctor["checks"]}
                self.assertEqual("pass", checks[f"target:{name}"]["status"])

    def test_task_skill_real_packages_complete_managed_lifecycle(self) -> None:
        for name in ("repo-pedant", "super-caveman", "excalidraw-diagram"):
            with self.subTest(skill=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "skills"
                receipt = target / ".azhou/hub" / "receipts" / f"{name}.json"
                destination = target / name

                result, setup = self._json_main(
                    [
                        "setup", "--managed", "--receipt", str(receipt),
                        "--skill", name, "--target", str(target),
                        "--mode", "copy", "--apply", "--json",
                    ]
                )
                self.assertEqual(0, result, setup)
                self.assertEqual("pass", setup["status"])
                self.assertTrue(destination.is_dir())
                self.assertFalse(destination.is_symlink())

                result, migrated = self._json_main(
                    [
                        "migrate", "--receipt", str(receipt), "--target", str(target),
                        "--mode", "link", "--apply", "--json",
                    ]
                )
                self.assertEqual(0, result, migrated)
                self.assertEqual("pass", migrated["status"])
                self.assertTrue(destination.is_symlink())

                destination.unlink()
                result, repaired = self._json_main(
                    [
                        "repair", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ]
                )
                self.assertEqual(0, result, repaired)
                self.assertEqual("pass", repaired["status"])
                self.assertTrue(destination.is_symlink())

                result, migrated = self._json_main(
                    [
                        "migrate", "--receipt", str(receipt), "--target", str(target),
                        "--mode", "copy", "--apply", "--json",
                    ]
                )
                self.assertEqual(0, result, migrated)
                self.assertEqual("pass", migrated["status"])
                self.assertTrue(destination.is_dir())
                self.assertFalse(destination.is_symlink())

                result, doctor = self._json_main(
                    ["doctor", "--skill", name, "--target", str(target), "--json"]
                )
                self.assertEqual(0, result, doctor)
                self.assertEqual("healthy", doctor["status"])

                result, uninstalled = self._json_main(
                    [
                        "uninstall", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ]
                )
                self.assertEqual(0, result, uninstalled)
                self.assertEqual("pass", uninstalled["status"])
                self.assertFalse(destination.exists() or destination.is_symlink())

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

            first = self._setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=False,
            )
            second = self._setup_skills(
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

            first = self._setup_skills(
                root=root,
                target=target,
                skills=["sample"],
                mode="copy",
                dry_run=False,
            )
            current = self._setup_skills(
                root=root,
                target=target,
                skills=["sample"],
                mode="copy",
                dry_run=False,
            )
            (source / "SKILL.md").write_text("version two\n", encoding="utf-8")
            stale = self._setup_skills(
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

    def test_doctor_rejects_executable_permission_drift_in_a_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            executable = source / "run.sh"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            result, payload = self._json_main(
                ["setup", "--skill", "sample", "--target", str(target), "--mode", "copy", "--apply", "--json"],
                root=root,
            )
            self.assertEqual(0, result, payload)
            (target / "sample" / "run.sh").chmod(0o644)

            result, payload = self._json_main(
                ["doctor", "--skill", "sample", "--target", str(target), "--json"],
                root=root,
            )

            self.assertEqual(1, result)
            target_check = next(check for check in payload["checks"] if check["name"] == "target:sample")
            self.assertEqual("fail", target_check["status"])
            self.assertEqual("target contains different or unowned content", target_check["details"])

    def test_setup_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"

            receipt = self._setup_skills(
                root=azhou_hub.ROOT,
                target=target,
                skills=["repo-pedant"],
                mode="link",
                dry_run=True,
            )

            self.assertEqual("dry_run", receipt["status"])
            self.assertEqual("planned", receipt["skills"][0]["status"])
            self.assertFalse(target.exists())

    def test_setup_cli_rejects_relative_target(self) -> None:
        result, payload = self._json_main(["setup", "--skill", "repo-pedant", "--target", "relative", "--json"])
        self.assertEqual(1, result)
        self.assertEqual("fail", payload["status"])
        self.assertIn("absolute path", payload["error"])

    def test_managed_lifecycle_cli_rejects_relative_target(self) -> None:
        for command in ("repair", "migrate", "uninstall"):
            with self.subTest(command=command):
                argv = [command, "--receipt", "receipt.json", "--target", "relative"]
                if command == "migrate":
                    argv.extend(["--mode", "copy"])
                result, payload = self._json_main([*argv, "--json"])
                self.assertEqual(1, result)
                self.assertEqual("fail", payload["status"])
                self.assertIn("absolute path", payload["error"])

    def test_setup_collision_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "skills"
            collision = target / "repo-pedant"
            collision.mkdir(parents=True)
            marker = collision / "keep.txt"
            marker.write_text("user owned\n", encoding="utf-8")

            receipt = self._setup_skills(
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

            receipt = self._setup_skills(
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

            receipt = self._setup_skills(
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

            receipt = self._setup_skills(
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

            preview_stream = io.StringIO()
            with redirect_stdout(preview_stream):
                preview_result = azhou_hub.main(
                    ["setup", "--skill", "sample", "--target", str(target), "--json"],
                    root=root,
                )
            self.assertEqual(0, preview_result)
            self.assertFalse(target.exists())
            plan_id = json.loads(preview_stream.getvalue())["planId"]

            with redirect_stdout(io.StringIO()):
                apply_result = azhou_hub.main(
                    ["setup", "--skill", "sample", "--target", str(target), "--apply", "--plan-id", plan_id, "--json"],
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

    def test_verify_promotion_flag_forwards_to_the_authoritative_gate(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch("scripts.azhou_hub.subprocess.run", return_value=completed) as run:
            result = azhou_hub.main(
                ["verify", "--python", "/custom/python", "--promotion-evidence"]
            )

        self.assertEqual(0, result)
        run.assert_called_once_with(
            [
                "/custom/python",
                str(azhou_hub.ROOT / "scripts/verify.py"),
                "--python",
                "/custom/python",
                "--promotion-evidence",
            ],
            cwd=azhou_hub.ROOT,
            check=False,
        )

    def test_authoritative_verify_scopes_promotion_evidence_to_the_promotion_gate(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch("scripts.verify.subprocess.run", return_value=completed) as run:
            result = verify_script.main(
                ["--python", "/custom/python", "--promotion-evidence"]
            )

        self.assertEqual(0, result)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(
            [
                "/custom/python",
                "benchmarks/super-caveman/benchmark.py",
                "check",
                "--promotion-evidence",
            ],
            commands,
        )
        self.assertIn(
            ["/custom/python", "-m", "unittest", "discover", "-s", "tests"],
            commands,
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

    def _treehouse_run(self, root: Path, *, version: str = "treehouse version 2.3.0", status: object | None = None,
                       version_error: BaseException | None = None, status_error: BaseException | None = None):
        treehouse_path = str(root.expanduser().resolve())
        if status is None:
            status = [{"path": str(root), "status": "leased", "lease_id": "lease-1", "lease_holder": "tester"}]

        def run(command, **kwargs):
            if command[:2] == ["treehouse", "--version"]:
                if version_error:
                    raise version_error
                return mock.Mock(returncode=0, stdout=version, stderr="")
            if command == ["treehouse", "status", "--json"]:
                if status_error:
                    raise status_error
                return mock.Mock(returncode=0, stdout=json.dumps(status), stderr="")
            if command and command[0] == "git":
                return mock.Mock(returncode=0, stdout="ok\n", stderr="")
            raise AssertionError(command)

        return run

    def test_doctor_treehouse_healthy_requires_exact_leased_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            (root / "README.md").write_text("fixture\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "skill-standard.md").write_text("fixture\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "verify.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            with mock.patch("scripts.azhou_hub.subprocess.run", side_effect=self._treehouse_run(root)):
                report = azhou_hub.run_doctor(root=root, target=None, skills=[], run_verification=False, treehouse_root=root)
            check = next(item for item in report["checks"] if item["name"] == "treehouse")
            self.assertEqual("pass", check["status"])
            self.assertTrue(report["valid"])

    def test_doctor_treehouse_unavailable_malformed_and_timeout_fail(self) -> None:
        cases = [
            (FileNotFoundError("treehouse"), None),
            (None, "not-json"),
            (TimeoutError("timed out"), None),
        ]
        for version_error, malformed in cases:
            with self.subTest(error=version_error or malformed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                root.mkdir()
                (root / "README.md").write_text("fixture\n", encoding="utf-8")
                (root / "docs").mkdir()
                (root / "docs" / "skill-standard.md").write_text("fixture\n", encoding="utf-8")
                (root / "scripts").mkdir()
                (root / "scripts" / "verify.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
                if malformed is not None:
                    runner = self._treehouse_run(root, status=malformed)
                else:
                    runner = self._treehouse_run(root, version_error=version_error)
                with mock.patch("scripts.azhou_hub.subprocess.run", side_effect=runner):
                    report = azhou_hub.run_doctor(root=root, target=None, skills=[], run_verification=False, treehouse_root=root)
                check = next(item for item in report["checks"] if item["name"] == "treehouse")
                self.assertEqual("fail", check["status"])
                self.assertFalse(report["valid"])

    def test_doctor_treehouse_rejects_nonmember_and_unleased_rows(self) -> None:
        for row in (
            {"path": "/elsewhere", "status": "leased", "lease_id": "x", "lease_holder": "y"},
            {"path": "PLACEHOLDER", "status": "available", "lease_id": "", "lease_holder": ""},
            {"path": 42, "status": "leased", "lease_id": "x", "lease_holder": "y"},
        ):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                root.mkdir()
                if row["path"] == "PLACEHOLDER":
                    row["path"] = str(root)
                runner = self._treehouse_run(root, status=[row])
                with mock.patch("scripts.azhou_hub.subprocess.run", side_effect=runner):
                    report = azhou_hub.run_doctor(root=root, target=None, skills=[], run_verification=False, treehouse_root=root)
                check = next(item for item in report["checks"] if item["name"] == "treehouse")
                self.assertEqual("fail", check["status"])

    def test_managed_dry_run_writes_no_target_or_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            receipt = target / ".azhou/hub" / "receipts" / "sample.json"
            result, payload = self._json_main(["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("dry_run", payload["status"])
            self.assertFalse(target.exists())
            self.assertFalse(receipt.exists())

    def test_setup_apply_requires_plan_id_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            result, payload = self._json_main(
                ["setup", "--skill", "sample", "--target", str(target), "--apply", "--json"],
                root=root,
                auto_plan=False,
            )
            self.assertEqual(1, result)
            self.assertIn("plan-id", payload["error"])
            self.assertFalse(target.exists())

    def test_setup_rejects_source_drift_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            _, planned = self._json_main(
                ["setup", "--skill", "sample", "--target", str(target), "--mode", "copy", "--json"],
                root=root,
            )
            source.joinpath("SKILL.md").write_text("changed\n", encoding="utf-8")
            result, payload = self._json_main(
                ["setup", "--skill", "sample", "--target", str(target), "--mode", "copy", "--apply", "--plan-id", planned["planId"], "--json"],
                root=root,
            )
            self.assertEqual(1, result)
            self.assertIn("plan changed", payload["error"])
            self.assertFalse((target / "sample").exists())

    def test_setup_python_api_requires_plan_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            payload = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=False)
            self.assertEqual("fail", payload["status"])
            self.assertIn("plan-id", payload["error"])
            self.assertFalse(target.exists())

    def test_setup_plan_id_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            first = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=True)
            second = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=True)
            self.assertEqual(first["planId"], second["planId"])

    def test_setup_rolls_back_safely_when_source_drifts_during_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            preview = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=True)
            original_copy = azhou_hub._copy_package

            def copy_then_drift(source_path: Path, destination: Path) -> None:
                original_copy(source_path, destination)
                source.joinpath("SKILL.md").write_text("drifted\n", encoding="utf-8")

            with mock.patch("scripts.azhou_hub._copy_package", side_effect=copy_then_drift):
                payload = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=False, plan_id=preview["planId"])
            self.assertEqual("rolled_back", payload["status"])
            self.assertFalse((target / "sample").exists())

    def test_setup_preserves_target_when_copy_proof_seam_is_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            preview = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=True)
            original_digest = azhou_hub.package_digest
            calls = 0

            def digest_then_mutate(path: Path) -> str:
                nonlocal calls
                calls += 1
                value = original_digest(path)
                if calls == 2:
                    installed = target / "sample"
                    installed.joinpath("SKILL.md").write_text("user-owned\n", encoding="utf-8")
                    source.joinpath("SKILL.md").write_text("drifted\n", encoding="utf-8")
                return value

            with mock.patch("scripts.azhou_hub.package_digest", side_effect=digest_then_mutate):
                payload = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=False, plan_id=preview["planId"])
            self.assertEqual("partial", payload["status"])
            self.assertEqual("user-owned\n", (target / "sample/SKILL.md").read_text(encoding="utf-8"))

    def test_setup_multiskill_source_drift_cannot_return_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            second = root / "skills" / "second"
            second.mkdir()
            second.joinpath("SKILL.md").write_text("second\n", encoding="utf-8")
            preview = azhou_hub.setup_skills(root=root, target=target, skills=["sample", "second"], mode="copy", dry_run=True)
            original_copy = azhou_hub._copy_package
            calls = 0

            def copy_then_drift(source_path: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    source.joinpath("SKILL.md").write_text("drifted\n", encoding="utf-8")
                original_copy(source_path, destination)

            with mock.patch("scripts.azhou_hub._copy_package", side_effect=copy_then_drift):
                payload = azhou_hub.setup_skills(root=root, target=target, skills=["sample", "second"], mode="copy", dry_run=False, plan_id=preview["planId"])
            self.assertEqual("rolled_back", payload["status"])
            self.assertFalse((target / "sample").exists())
            self.assertFalse((target / "second").exists())
            self.assertEqual(preview["planId"], payload["planId"])

    def test_setup_preserves_target_when_receipt_failure_mutates_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            receipt = target / ".azhou/hub/receipts/sample.json"
            preview = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=True, receipt_path=receipt)

            def write_and_mutate(_path: Path, _receipt: dict) -> None:
                installed = target / "sample"
                shutil.rmtree(installed)
                installed.mkdir()
                installed.joinpath("SKILL.md").write_text("user-owned\n", encoding="utf-8")
                raise OSError("injected receipt failure")

            with mock.patch("scripts.azhou_hub._write_receipt", side_effect=write_and_mutate):
                payload = azhou_hub.setup_skills(root=root, target=target, skills=["sample"], mode="copy", dry_run=False, receipt_path=receipt, plan_id=preview["planId"])
            self.assertEqual("partial", payload["status"])
            self.assertEqual("user-owned\n", (target / "sample/SKILL.md").read_text(encoding="utf-8"))

    def test_setup_plan_binds_absolute_canonical_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            alternate = Path(directory) / "alternate"
            shutil.copytree(root / "skills", alternate / "skills")
            _, first = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--json"], root=root)
            _, second = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--json"], root=alternate)
            self.assertEqual((source / "SKILL.md").read_bytes(), (alternate / "skills/sample/SKILL.md").read_bytes())
            self.assertNotEqual(first["planId"], second["planId"])

    def test_setup_rejects_reviewed_plan_from_alternate_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            alternate = Path(directory) / "alternate"
            shutil.copytree(root / "skills", alternate / "skills")
            _, planned = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--json"], root=root)
            result, payload = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--apply", "--plan-id", planned["planId"], "--json"], root=alternate)
            self.assertEqual(1, result)
            self.assertIn("plan changed", payload["error"])
            self.assertFalse((target / "sample").exists())

    def test_setup_rejects_destination_change_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            _, planned = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--json"], root=root)
            target.mkdir()
            (target / "sample").mkdir()
            (target / "sample/SKILL.md").write_text("user-owned\n", encoding="utf-8")
            result, payload = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--apply", "--plan-id", planned["planId"], "--json"], root=root)
            self.assertEqual(1, result)
            self.assertIn("plan changed", payload["error"])
            self.assertEqual("user-owned\n", (target / "sample/SKILL.md").read_text(encoding="utf-8"))

    def test_setup_plan_id_ignores_details_only_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            _, planned = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--json"], root=root)
            original = azhou_hub.inspect_installation
            with mock.patch("scripts.azhou_hub.inspect_installation", side_effect=lambda source, destination, mode: (lambda result: (result[0], "different prose"))(original(source, destination, mode))):
                result, payload = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--apply", "--plan-id", planned["planId"], "--json"], root=root)
            self.assertEqual(0, result, payload)

    def test_managed_apply_writes_atomic_receipt_and_requires_pairing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            receipt = target / ".azhou/hub" / "receipts" / "sample.json"
            result, payload = self._json_main(["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertTrue(receipt.is_file())
            receipt_payload = json.loads(receipt.read_text())
            self.assertEqual("azhou-ai-hub.install-receipt.v2", receipt_payload["schema"])
            self.assertEqual({"device", "inode", "mode"}, set(receipt_payload["skills"][0]["installed_identity"]))
            result, payload = self._json_main(["setup", "--managed", "--skill", "sample", "--target", str(Path(directory) / "other"), "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            result, payload = self._json_main(["setup", "--receipt", str(receipt), "--skill", "sample", "--target", str(Path(directory) / "other"), "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])

    def test_legacy_receipts_require_explicit_reviewed_namespace_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, current_receipt = self._managed_fixture(directory, mode="copy")
            legacy_receipt = target / ".azhou-ai-hub" / "receipts" / "sample.json"
            legacy_receipt.parent.mkdir(parents=True)
            shutil.copy2(current_receipt, legacy_receipt)
            shutil.rmtree(target / ".azhou")

            result, planned = self._json_main(
                ["migrate-receipts", "--target", str(target), "--json"],
                root=root,
            )
            self.assertEqual(0, result, planned)
            self.assertEqual("planned", planned["status"])
            self.assertTrue(legacy_receipt.is_file())
            self.assertFalse(current_receipt.exists())

            result, migrated = self._json_main(
                [
                    "migrate-receipts",
                    "--target",
                    str(target),
                    "--apply",
                    "--plan-id",
                    planned["planId"],
                    "--json",
                ],
                root=root,
            )
            self.assertEqual(0, result, migrated)
            self.assertEqual("migrated", migrated["status"])
            self.assertTrue(legacy_receipt.is_file())
            self.assertTrue(current_receipt.is_file())

            result, repeated = self._json_main(
                [
                    "migrate-receipts",
                    "--target",
                    str(target),
                    "--apply",
                    "--plan-id",
                    planned["planId"],
                    "--json",
                ],
                root=root,
            )
            self.assertEqual(0, result, repeated)
            self.assertEqual("already-current", repeated["status"])

    def test_receipt_write_failure_rolls_back_managed_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            receipt = target / ".azhou/hub" / "receipts" / "sample.json"
            with mock.patch("scripts.azhou_hub._write_receipt", side_effect=OSError("disk full")):
                result, payload = self._json_main(["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("rolled_back", payload["status"])
            self.assertFalse((target / "sample").exists() or (target / "sample").is_symlink())

    def test_managed_setup_refuses_receiptless_adoption_and_preserves_valid_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, source, target = self._fixture_repo(directory)
            target.mkdir()
            (target / "sample").symlink_to(source, target_is_directory=True)
            receipt = target / ".azhou/hub" / "receipts" / "sample.json"

            result, payload = self._json_main(
                ["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"],
                root=root,
            )
            self.assertEqual(1, result)
            self.assertIn("cannot adopt", payload["skills"][0]["details"])
            self.assertFalse(receipt.exists())

            (target / "sample").unlink()
            result, payload = self._json_main(
                ["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"],
                root=root,
            )
            self.assertEqual(0, result, payload)
            original_receipt = receipt.read_bytes()
            result, payload = self._json_main(
                ["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"],
                root=root,
            )
            self.assertEqual(0, result, payload)
            self.assertEqual("current", payload["skills"][0]["status"])
            self.assertFalse(payload["applied"])
            self.assertEqual(original_receipt, receipt.read_bytes())

    def test_managed_receipt_must_be_target_owned_and_dry_run_creates_no_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            outside = Path(directory) / "outside" / "receipt.json"
            result, payload = self._json_main(["setup", "--managed", "--receipt", str(outside), "--skill", "sample", "--target", str(target), "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            self.assertFalse(target.exists())
            self.assertFalse(outside.parent.exists())

    def test_managed_receipt_rejects_azhou_or_receipts_symlink(self) -> None:
        for link_part in (".azhou", "receipts"):
            with self.subTest(link_part=link_part), tempfile.TemporaryDirectory() as directory:
                root, _, target = self._fixture_repo(directory)
                target.mkdir()
                anchor = Path(directory) / "anchor"
                anchor.mkdir()
                if link_part == ".azhou":
                    (target / link_part).symlink_to(anchor, target_is_directory=True)
                else:
                    metadata = target / ".azhou/hub"
                    metadata.mkdir(parents=True)
                    (metadata / link_part).symlink_to(anchor, target_is_directory=True)
                receipt = target / ".azhou/hub" / "receipts" / "sample.json"
                result, payload = self._json_main(["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--json"], root=root)
                self.assertEqual(1, result)
                self.assertEqual("fail", payload["status"])
                self.assertFalse((anchor / "sample.json").exists())

    def test_existing_mutation_lock_blocks_managed_setup_and_lifecycle_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            target.mkdir()
            lock = target / ".azhou/hub" / "mutation.lock"
            lock.mkdir(parents=True)
            receipt = target / ".azhou/hub" / "receipts" / "sample.json"
            result, payload = self._json_main(["setup", "--managed", "--receipt", str(receipt), "--skill", "sample", "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertFalse((target / "sample").exists() or (target / "sample").is_symlink())

            result, payload = self._json_main(["setup", "--skill", "sample", "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertFalse((target / "sample").exists() or (target / "sample").is_symlink())

            lock.rmdir()
            managed_directory = Path(directory) / "managed"
            managed_directory.mkdir()
            root, target, receipt = self._managed_fixture(str(managed_directory), mode="copy")
            shutil.rmtree(target / "sample")
            lock = target / ".azhou/hub" / "mutation.lock"
            lock.mkdir(parents=True)
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertFalse((target / "sample").exists())

    def test_invalid_empty_or_multi_skill_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            valid = json.loads(receipt.read_text(encoding="utf-8"))
            for skills in ([], [valid["skills"][0], dict(valid["skills"][0])]):
                with self.subTest(skill_count=len(skills)):
                    forged = dict(valid)
                    forged["skills"] = skills
                    forged["integrity_digest"] = azhou_hub._receipt_digest(forged)
                    receipt.write_text(json.dumps(forged), encoding="utf-8")
                    result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--json"], root=root)
                    self.assertEqual(1, result)
                    self.assertIn("receipt_invalid", payload["error"])
            receipt.write_text(json.dumps(valid), encoding="utf-8")

            for key in ("target", "source_root"):
                with self.subTest(field=key):
                    forged = dict(valid)
                    forged[key] = 42
                    forged["integrity_digest"] = azhou_hub._receipt_digest(forged)
                    receipt.write_text(json.dumps(forged), encoding="utf-8")
                    result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--json"], root=root)
                    self.assertEqual(1, result)
                    self.assertIn("receipt_invalid", payload["error"])

    def test_copy_receipt_rejects_symlinked_destination_even_when_digest_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            installed = target / "sample"
            shadow = Path(directory) / "shadow"
            shutil.copytree(installed, shadow)
            shutil.rmtree(installed)
            installed.symlink_to(shadow, target_is_directory=True)

            result, payload = self._json_main(
                ["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"],
                root=root,
            )
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            self.assertTrue(installed.is_symlink())
            self.assertTrue((shadow / "SKILL.md").is_file())

    def test_setup_rollback_failure_reports_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, target = self._fixture_repo(directory)
            second = root / "skills" / "second"
            second.mkdir()
            (second / "SKILL.md").write_text("second\n", encoding="utf-8")
            original_copy = azhou_hub._copy_package
            calls = 0

            def copy_then_fail(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    original_copy(source, destination)
                    return
                raise OSError("injected install failure")

            with mock.patch("scripts.azhou_hub._copy_package", side_effect=copy_then_fail), mock.patch("scripts.azhou_hub.shutil.rmtree", side_effect=OSError("injected rollback failure")):
                payload = self._setup_skills(root=root, target=target, skills=["sample", "second"], mode="copy", dry_run=False)
            self.assertEqual("partial", payload["status"])
            self.assertTrue((target / "sample").exists())

    def test_repair_missing_current_drift_and_forged_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            shutil.rmtree(target / "sample")
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("dry_run", payload["status"])
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertTrue((target / "sample" / "SKILL.md").is_file())
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("current", payload["skills"][0]["status"])
            (target / "sample" / "SKILL.md").write_text("drift\n", encoding="utf-8")
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            forged = json.loads(receipt.read_text(encoding="utf-8"))
            forged["skills"][0]["source"] = str(Path(directory) / "forged")
            receipt.write_text(json.dumps(forged), encoding="utf-8")
            result, payload = self._json_main(["repair", "--receipt", str(receipt), "--target", str(target), "--json"], root=root)
            self.assertEqual(1, result)
            self.assertIn("receipt_invalid", payload["error"])

    def test_uninstall_exact_drift_and_idempotent_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="link")
            result, payload = self._json_main(["uninstall", "--receipt", str(receipt), "--target", str(target), "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("dry_run", payload["status"])
            self.assertTrue((target / "sample").is_symlink())
            result, payload = self._json_main(["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertFalse((target / "sample").exists() or (target / "sample").is_symlink())
            result, payload = self._json_main(["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("already_absent", payload["skills"][0]["status"])

    def test_uninstall_refuses_drifted_managed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            (target / "sample" / "SKILL.md").write_text("owned by user\n", encoding="utf-8")
            result, payload = self._json_main(["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            self.assertTrue((target / "sample").is_dir())

    def test_uninstall_refuses_a_byte_identical_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            installed = target / "sample"
            shutil.rmtree(installed)
            shutil.copytree(root / "skills" / "sample", installed)

            result, payload = self._json_main(
                ["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"],
                root=root,
            )

            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            self.assertEqual("conflict", payload["skills"][0]["status"])
            self.assertTrue((installed / "SKILL.md").is_file())

    def test_repair_upgrades_genuine_legacy_receipt_digests_for_link_and_copy(self) -> None:
        for mode in ("link", "copy"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root, target, receipt = self._managed_fixture(directory, mode=mode)
                source = root / "skills" / "sample"
                destination = target / "sample"
                legacy_source_digest = self._legacy_package_digest(source)
                self.assertNotEqual(legacy_source_digest, azhou_hub.package_digest(source))
                self._write_legacy_receipt(
                    receipt, mode=mode, source=source, destination=destination
                )

                result, payload = self._json_main(
                    [
                        "uninstall", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ],
                    root=root,
                )
                self.assertEqual(1, result)
                self.assertEqual("fail", payload["status"])

                result, payload = self._json_main(
                    [
                        "repair", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ],
                    root=root,
                )
                self.assertEqual(0, result, payload)
                self.assertEqual("pass", payload["status"])
                upgraded = json.loads(receipt.read_text(encoding="utf-8"))
                item = upgraded["skills"][0]
                self.assertEqual("azhou-ai-hub.install-receipt.v2", upgraded["schema"])
                self.assertEqual({"device", "inode", "mode"}, set(item["installed_identity"]))
                self.assertEqual(azhou_hub.package_digest(source), item["source_digest"])
                expected_installed = (
                    item["source_digest"] if mode == "link" else azhou_hub.package_digest(destination)
                )
                self.assertEqual(expected_installed, item["installed_digest"])

                result, payload = self._json_main(
                    [
                        "uninstall", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ],
                    root=root,
                )
                self.assertEqual(0, result, payload)
                self.assertFalse(destination.exists() or destination.is_symlink())

    def test_repair_recreates_a_missing_artifact_from_a_genuine_legacy_receipt(self) -> None:
        for mode in ("link", "copy"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root, target, receipt = self._managed_fixture(directory, mode=mode)
                source = root / "skills" / "sample"
                destination = target / "sample"
                self._write_legacy_receipt(
                    receipt, mode=mode, source=source, destination=destination
                )
                if mode == "link":
                    destination.unlink()
                else:
                    shutil.rmtree(destination)

                result, payload = self._json_main(
                    [
                        "repair", "--receipt", str(receipt), "--target", str(target),
                        "--apply", "--json",
                    ],
                    root=root,
                )

                self.assertEqual(0, result, payload)
                self.assertEqual("pass", payload["status"])
                self.assertTrue(destination.exists())
                upgraded = json.loads(receipt.read_text(encoding="utf-8"))
                item = upgraded["skills"][0]
                self.assertEqual("azhou-ai-hub.install-receipt.v2", upgraded["schema"])
                self.assertEqual(azhou_hub.package_digest(source), item["source_digest"])
                expected_installed = (
                    item["source_digest"]
                    if mode == "link"
                    else azhou_hub.package_digest(destination)
                )
                self.assertEqual(expected_installed, item["installed_digest"])

    def test_uninstall_refuses_identity_swap_after_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="copy")
            installed = target / "sample"
            original_identity = azhou_hub._path_identity(installed)
            self.assertIsNotNone(original_identity)
            calls = 0

            def swapped_identity(path: Path):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return original_identity
                return original_identity[0], original_identity[1] + 1, original_identity[2]

            with mock.patch("scripts.azhou_hub._path_identity", side_effect=swapped_identity):
                result, payload = self._json_main(
                    ["uninstall", "--receipt", str(receipt), "--target", str(target), "--apply", "--json"],
                    root=root,
                )

            self.assertEqual(1, result)
            self.assertEqual("partial", payload["status"])
            self.assertTrue((installed / "SKILL.md").is_file())

    def test_migrate_same_target_dry_run_and_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="link")
            result, payload = self._json_main(["migrate", "--receipt", str(receipt), "--target", str(target), "--mode", "copy", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertEqual("dry_run", payload["status"])
            self.assertTrue((target / "sample").is_symlink())
            result, payload = self._json_main(["migrate", "--receipt", str(receipt), "--target", str(target), "--mode", "copy", "--apply", "--json"], root=root)
            self.assertEqual(0, result)
            self.assertTrue((target / "sample").is_dir())
            self.assertFalse((target / "sample").is_symlink())
            self.assertEqual("copy", json.loads(receipt.read_text(encoding="utf-8"))["mode"])

    def test_migrate_same_mode_refuses_a_replaced_managed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="link")
            installed = target / "sample"
            installed.unlink()
            installed.mkdir()
            (installed / "SKILL.md").write_text("owned by user\n", encoding="utf-8")

            result, payload = self._json_main(
                ["migrate", "--receipt", str(receipt), "--target", str(target), "--mode", "link", "--apply", "--json"],
                root=root,
            )

            self.assertEqual(1, result)
            self.assertEqual("fail", payload["status"])
            self.assertEqual("conflict", payload["skills"][0]["status"])
            self.assertEqual("owned by user\n", (installed / "SKILL.md").read_text(encoding="utf-8"))

    def test_migrate_failure_keeps_old_installation_or_reports_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, target, receipt = self._managed_fixture(directory, mode="link")
            with mock.patch("scripts.azhou_hub._write_receipt", side_effect=OSError("receipt unavailable")):
                result, payload = self._json_main(["migrate", "--receipt", str(receipt), "--target", str(target), "--mode", "copy", "--apply", "--json"], root=root)
            self.assertEqual(1, result)
            self.assertIn(payload["status"], {"partial", "rolled_back"})
            self.assertTrue((target / "sample").is_symlink())
            self.assertEqual("link", json.loads(receipt.read_text(encoding="utf-8"))["mode"])


if __name__ == "__main__":
    unittest.main()

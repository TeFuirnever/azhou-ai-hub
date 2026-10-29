#!/usr/bin/env python3
"""Test pinned unit-tool readiness and GitHub environment-file exports."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("test-setup-unit-tools.py")
SPEC = importlib.util.spec_from_file_location("agent_skin_setup_unit_tools", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not load setup helper at {MODULE_PATH}")
setup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = setup
SPEC.loader.exec_module(setup)


def write_executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


class UnitToolSetupTests(unittest.TestCase):
    def test_bash_version_requires_the_pinned_gnu_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit-tools-") as temporary:
            bash = Path(temporary) / "bash"
            write_executable(bash, "#!/bin/sh\nprintf '%s\\n' 'GNU bash, version 5.2.37(1)-release (fixture)'\n")
            self.assertEqual(setup.require_bash_version(bash), setup.BASH_VERSION)

            write_executable(bash, "#!/bin/sh\nprintf '%s\\n' 'GNU bash, version 3.2.57(1)-release (fixture)'\n")
            with self.assertRaisesRegex(setup.SetupError, "expected GNU Bash 5.2.37.*found 3.2.57"):
                setup.require_bash_version(bash)

    def test_github_exports_append_plain_paths_without_shell_quoting(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit tools ") as temporary:
            root = Path(temporary) / "package with = and spaces"
            paths = setup.paths_for(root)
            env_file = Path(temporary) / "github env"
            first_path_file = Path(temporary) / "github path one"
            second_path_file = Path(temporary) / "github path two"
            env_file.write_text("existing=value\n", encoding="utf-8")
            first_path_file.write_text("existing-bin\n", encoding="utf-8")
            second_path_file.write_text("", encoding="utf-8")

            setup.write_github_exports(paths, env_file, [first_path_file, second_path_file])

            self.assertEqual(
                env_file.read_text(encoding="utf-8"),
                "existing=value\n"
                f"BASHCOV_BASH_PATH={paths.bashcov_bash_path}\n"
                f"GEM_HOME={paths.gem_home}\n"
                f"GEM_PATH={paths.gem_path}\n",
            )
            expected_path = f"{paths.gem_bin}\n"
            self.assertEqual(first_path_file.read_text(encoding="utf-8"), "existing-bin\n" + expected_path)
            self.assertEqual(second_path_file.read_text(encoding="utf-8"), expected_path)
            self.assertNotIn('"', env_file.read_text(encoding="utf-8"))

    def test_github_exports_reject_newline_paths_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit-tools-") as temporary:
            root = Path(temporary) / "package\nGEM_HOME=/tmp/escape"
            paths = setup.paths_for(root)
            env_file = Path(temporary) / "github-env"
            path_file = Path(temporary) / "github-path"
            env_file.write_text("keep-env\n", encoding="utf-8")
            path_file.write_text("keep-path\n", encoding="utf-8")

            with self.assertRaisesRegex(setup.SetupError, "one GitHub environment-file line"):
                setup.write_github_exports(paths, env_file, [path_file])

            self.assertEqual(env_file.read_text(encoding="utf-8"), "keep-env\n")
            self.assertEqual(path_file.read_text(encoding="utf-8"), "keep-path\n")

    def test_cli_writes_requested_github_files_and_emits_json_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit-tools-") as temporary:
            root = Path(temporary) / "package"
            paths = setup.paths_for(root)
            env_file = Path(temporary) / "github-env"
            path_files = [Path(temporary) / "github-path-one", Path(temporary) / "github-path-two"]
            env_file.touch()
            for path_file in path_files:
                path_file.touch()
            argv = [
                str(MODULE_PATH), "--github-env", str(env_file),
                "--github-path", str(path_files[0]), "--github-path", str(path_files[1]),
            ]
            output = io.StringIO()
            with patch.object(setup, "prepare_tools", return_value=paths), \
                 patch.object(setup.sys, "argv", argv), redirect_stdout(output):
                self.assertEqual(setup.main(), 0)

            self.assertEqual(json.loads(output.getvalue()), paths.as_json())
            self.assertIn(f"GEM_HOME={paths.gem_home}\n", env_file.read_text(encoding="utf-8"))
            self.assertEqual(path_files[0].read_text(encoding="utf-8"), f"{paths.gem_bin}\n")
            self.assertEqual(path_files[1].read_text(encoding="utf-8"), f"{paths.gem_bin}\n")

    def test_existing_pinned_tools_are_reused_without_download_or_install(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit-tools-") as temporary:
            root = Path(temporary) / "package"
            paths = setup.paths_for(root)
            write_executable(
                paths.bashcov_bash_path,
                "#!/bin/sh\nprintf '%s\\n' 'GNU bash, version 5.2.37(1)-release (fixture)'\n",
            )
            write_executable(paths.gem_bin / "bashcov", "#!/bin/sh\nexit 0\n")
            ruby = Path(temporary) / "ruby"
            gem = Path(temporary) / "gem"
            write_executable(ruby, "#!/bin/sh\nprintf '%s' '1.7.0'\n")
            write_executable(gem, "#!/bin/sh\nexit 99\n")

            with patch.object(setup, "download_bash_archive", side_effect=AssertionError("download called")), \
                 patch.object(setup, "build_bash", side_effect=AssertionError("build called")):
                prepared = setup.prepare_tools(
                    root,
                    ruby_executable=str(ruby),
                    gem_executable=str(gem),
                )

            self.assertEqual(prepared.bashcov_bash_path, paths.bashcov_bash_path)
            self.assertEqual(prepared.gem_home, paths.gem_home)
            self.assertTrue(prepared.bashcov_bash_path.is_file())
            self.assertTrue((prepared.gem_bin / "bashcov").is_file())

    def test_existing_old_bash_fails_closed_without_fallback_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unit-tools-") as temporary:
            root = Path(temporary) / "package"
            binary = setup.paths_for(root).bashcov_bash_path
            write_executable(binary, "#!/bin/sh\nprintf '%s\\n' 'GNU bash, version 3.2.57(1)-release (fixture)'\n")

            with patch.object(setup, "download_bash_archive", side_effect=AssertionError("download called")), \
                 patch.object(setup, "build_bash", side_effect=AssertionError("build called")):
                with self.assertRaisesRegex(setup.SetupError, "expected GNU Bash 5.2.37.*found 3.2.57"):
                    setup.ensure_bash(root)

    def test_build_parallelism_stays_bounded(self) -> None:
        self.assertEqual(setup.bounded_build_jobs(1), 1)
        self.assertEqual(setup.bounded_build_jobs(8), setup.MAX_BUILD_JOBS)
        self.assertEqual(setup.bounded_build_jobs(None), 1)


if __name__ == "__main__":
    unittest.main()

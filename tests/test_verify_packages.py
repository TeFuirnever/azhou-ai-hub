"""Build-input validation above the already tested package fingerprint loader."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import verify_packages


class PackageBuildInputTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.packages = {}
        for component in common.COMPONENTS:
            package = configure_package(self.root, component, ["runtime"], build_inputs=["runtime/main.txt"])
            (package / "runtime").mkdir()
            (package / "runtime/main.txt").write_text("public build input\n", encoding="utf-8")
            (package / "runtime/private-notes.txt").write_text("public documentation\n", encoding="utf-8")
            (package / "unselected.txt").write_text("exists but outside runtime map\n", encoding="utf-8")
            self.packages[component] = package
        self.component = common.COMPONENTS[0]

    def set_inputs(self, value, *, component=None) -> None:
        path = self.packages[component or self.component] / "hub-package.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["build_inputs"] = value
        path.write_text(json.dumps(metadata), encoding="utf-8")

    def validate(self):
        with mock.patch.object(verify_packages, "ROOT", self.root), redirect_stdout(io.StringIO()):
            return verify_packages.validate_packages()

    def main(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(verify_packages, "ROOT", self.root), redirect_stdout(stdout), redirect_stderr(stderr):
            code = verify_packages.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_build_inputs_are_checked_against_expanded_runtime_files(self) -> None:
        self.set_inputs(["runtime/main.txt", "runtime/private-notes.txt"])
        packages, errors = self.validate()
        self.assertEqual(self.packages, packages)
        self.assertEqual([], errors)
        code, _, error = self.main()
        self.assertEqual(0, code)
        self.assertEqual("", error)

    def test_existing_but_unselected_files_and_directories_are_not_build_inputs(self) -> None:
        self.set_inputs(["unselected.txt", "runtime/"])
        _, errors = self.validate()
        self.assertEqual([
            f"{self.component}: build input is not present in computed runtime files: unselected.txt",
            f"{self.component}: build input is not present in computed runtime files: runtime/",
        ], errors)
        code, _, error = self.main()
        self.assertEqual(1, code)
        for message in errors:
            self.assertIn("FAILED: " + message, error)

    def test_build_inputs_require_an_array_of_nonempty_path_strings(self) -> None:
        for value in [None, {}, "runtime/main.txt"]:
            with self.subTest(value=value):
                self.set_inputs(value)
                _, errors = self.validate()
                self.assertEqual([f"{self.component}: build_inputs must be an array"], errors)
        self.set_inputs([None, 17, ""])
        _, errors = self.validate()
        self.assertEqual([f"{self.component}: build_inputs entries must be nonempty paths"] * 3, errors)

    def test_private_path_segments_are_rejected_but_similarly_named_public_files_are_valid(self) -> None:
        package = self.packages[self.component]
        private = package / "runtime/private/key.txt"
        private.parent.mkdir()
        private.write_text("fixture only\n", encoding="utf-8")
        self.set_inputs(["runtime/private/key.txt", "runtime/private-notes.txt"])
        _, errors = self.validate()
        self.assertEqual([f"{self.component}: private build input is forbidden: runtime/private/key.txt"], errors)
        code, _, error = self.main()
        self.assertEqual(1, code)
        self.assertIn("private build input is forbidden", error)

    def test_load_failure_does_not_hide_other_package_build_errors(self) -> None:
        self.assertGreaterEqual(len(common.COMPONENTS), 2, "Exercise cross-package error aggregation")
        first, second = common.COMPONENTS[:2]
        (self.packages[first] / "hub-package.json").write_text("{interrupted", encoding="utf-8")
        self.set_inputs(["unselected.txt"], component=second)
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        packages, errors = self.validate()
        self.assertNotIn(first, packages)
        self.assertIn(second, packages)
        self.assertEqual(2, len(errors))
        self.assertIn(f"{first}: cannot read package metadata", errors[0])
        self.assertEqual(f"{second}: build input is not present in computed runtime files: unselected.txt", errors[1])
        code, output, error = self.main()
        self.assertEqual(1, code)
        self.assertIn("package source validation failed", output)
        for message in errors:
            self.assertIn("FAILED: " + message, error)
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()

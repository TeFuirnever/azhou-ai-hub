#!/usr/bin/env python3
"""Behavioral tests for the read-only DSH isolation preflight seam."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import importlib.util
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
TOOL = PACKAGE / "tools/dsh-isolation-preflight.py"
CANDIDATE_SHA256 = "eb1cd4969a60b8ec52107b3bf92b4aa1d10176bd73cbad0369fbdec49e18e76c"


def load_tool():
    spec = importlib.util.spec_from_file_location("dsh_isolation_preflight", TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load DSH isolation preflight")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DSHIsolationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dsh-isolation-preflight-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.preparation_root = root / "isolated"
        self.candidate = root / "candidate"
        self.candidate.mkdir()
        (self.candidate / "plugin.json").write_bytes(b'{"id":"fixture"}\n')
        self.production = root / "production"
        self.production.mkdir()
        self.plan = {
            "schema_version": 1,
            "preparation_root": str(self.preparation_root),
            "candidate": {
                "root": str(self.candidate),
                "summary_sha256": CANDIDATE_SHA256,
            },
            "paths": {
                "dsh_home": {"path": str(self.preparation_root / "dsh"), "expected_state": "absent"},
                "electron_user_data": {
                    "path": str(self.preparation_root / "electron-user-data"),
                    "expected_state": "absent",
                },
                "profile": {
                    "path": str(self.preparation_root / "dsh/profiles/default"),
                    "expected_state": "absent",
                },
                "plugin": {
                    "path": str(self.preparation_root / "dsh/plugins/azhou"),
                    "expected_state": "absent",
                },
            },
            "protected_roots": [str(self.production)],
            "host": {
                "target": {
                    "bundle_id": "com.deepseek.dsh",
                    "version": "0.2.2-rc.3",
                    "build": "rc3-build",
                },
                "evidence_record": {
                    "source": "fixture-host-metadata-record",
                    "bundle_id": "com.deepseek.dsh",
                    "version": "0.2.2-rc.3",
                    "build": "rc3-build",
                },
            },
        }

    def test_valid_candidate_and_unprepared_targets_pass_only_static_checks(self):
        result = load_tool().preflight(self.plan)

        self.assertEqual(result["status"], "static_preflight_passed")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["candidate_summary_sha256"], CANDIDATE_SHA256)
        self.assertTrue(result["host_target_matches_evidence_record"])
        self.assertIs(result["runtime_isolation_verified"], False)
        self.assertIs(result["write_authorized"], False)

    def test_blocks_profile_symlink_aliasing_a_protected_production_root(self):
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        dsh_home.mkdir()
        profile = Path(self.plan["paths"]["profile"]["path"])
        profile.parent.mkdir(parents=True)
        profile.symlink_to(self.production, target_is_directory=True)
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["profile"]["expected_state"] = "empty_directory"

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_symlink:profile", result["reasons"])

    def test_blocks_a_target_path_outside_the_owned_preparation_root(self):
        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["path"] = str(Path(self.temporary.name) / "outside-profile")

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_outside_preparation_root:profile", result["reasons"])

    def test_blocks_nonempty_history_inside_the_planned_profile(self):
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        profile = dsh_home / "profiles/default"
        profile.mkdir(parents=True)
        (profile / "history.db").write_bytes(b"fixture-only profile history")
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["profile"]["expected_state"] = "empty_directory"

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("historical_nonempty_directory", result["reasons"])

    def test_allows_declared_empty_profile_nested_under_empty_dsh_home(self):
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        profile = dsh_home / "profiles/default"
        profile.mkdir(parents=True)
        electron_user_data = self.preparation_root / "electron-user-data"
        electron_user_data.mkdir()
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["profile"]["expected_state"] = "empty_directory"
        plan["paths"]["electron_user_data"]["expected_state"] = "empty_directory"

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "static_preflight_passed")
        self.assertEqual(result["reasons"], [])
        self.assertIs(result["runtime_isolation_verified"], False)

    def test_blocks_candidate_inside_protected_root_before_hashing_it(self):
        shared_candidate = self.production / "shared-candidate"
        shared_candidate.mkdir()
        (shared_candidate / "plugin.json").write_bytes(b'{"id":"fixture"}\n')
        plan = copy.deepcopy(self.plan)
        plan["candidate"]["root"] = str(shared_candidate)

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_overlaps_protected_root", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_blocks_candidate_content_drift_against_the_plan_summary(self):
        (self.candidate / "plugin.json").write_bytes(b'{"id":"changed"}\n')

        result = load_tool().preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_mismatch", result["reasons"])
        self.assertNotEqual(result["candidate_summary_sha256"], CANDIDATE_SHA256)

    def test_blocks_stale_host_version_or_build_evidence_record(self):
        for field in ("version", "build"):
            with self.subTest(field=field):
                plan = copy.deepcopy(self.plan)
                plan["host"]["evidence_record"][field] = "0.2.2-rc.1"

                result = load_tool().preflight(plan)

                self.assertEqual(result["status"], "blocked")
                self.assertIn("host_target_evidence_mismatch", result["reasons"])
                self.assertIs(result["host_target_matches_evidence_record"], False)

    def test_requires_an_explicit_electron_user_data_path(self):
        plan = copy.deepcopy(self.plan)
        plan["paths"]["electron_user_data"]["path"] = ""

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_invalid:electron_user_data", result["reasons"])

    def test_blocks_a_protected_ancestor_of_the_preparation_root(self):
        plan = copy.deepcopy(self.plan)
        plan["protected_roots"] = [self.temporary.name]

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("preparation_root_overlaps_protected_root", result["reasons"])

    def test_rejects_electron_user_data_nested_under_dsh_home(self):
        plan = copy.deepcopy(self.plan)
        plan["paths"]["electron_user_data"]["path"] = str(self.preparation_root / "dsh/electron")

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_relationship_invalid:electron_user_data", result["reasons"])

    def test_cli_prints_static_result_without_leaking_source_paths(self):
        tool = load_tool()
        plan_file = Path(self.temporary.name) / "plan.json"
        plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = tool.main([str(plan_file)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "static_preflight_passed")
        self.assertIs(result["runtime_isolation_verified"], False)
        self.assertIs(result["write_authorized"], False)
        self.assertNotIn(str(self.candidate), output.getvalue())

    def test_blocks_plugin_destination_symlink_to_shared_production_entity(self):
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        plugin = dsh_home / "plugins/azhou"
        plugin.parent.mkdir(parents=True)
        plugin.symlink_to(self.production, target_is_directory=True)
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["plugin"]["expected_state"] = "empty_directory"

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_symlink:plugin", result["reasons"])

    def test_absent_path_state_rejects_a_preexisting_empty_directory(self):
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        dsh_home.mkdir()

        result = load_tool().preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_state_mismatch:dsh_home", result["reasons"])

    def test_invalid_candidate_digest_is_blocked_before_reading_the_candidate(self):
        plan = copy.deepcopy(self.plan)
        plan["candidate"].pop("summary_sha256")

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_invalid", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_rejects_symlinks_inside_candidate_tree(self):
        protected_file = self.production / "fixture-secret"
        protected_file.write_bytes(b"fixture-only protected content")
        (self.candidate / "link").symlink_to(protected_file)

        result = load_tool().preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_unavailable", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_blocks_candidate_when_a_subtree_cannot_be_enumerated(self):
        unreadable = self.candidate / "unreadable"
        unreadable.mkdir()
        (unreadable / "hidden.js").write_bytes(b"fixture-only candidate content")
        tool = load_tool()
        original_scandir = tool.os.scandir

        def fail_on_unreadable(path):
            if Path(path) == unreadable:
                raise PermissionError("fixture unreadable subtree")
            return original_scandir(path)

        with mock.patch.object(tool.os, "scandir", side_effect=fail_on_unreadable):
            result = tool.preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_unavailable", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_never_scans_through_a_symlinked_target_root_into_production(self):
        production_profiles = self.production / "profiles/default"
        production_profiles.mkdir(parents=True)
        (production_profiles / "history.db").write_bytes(b"fixture-only history")
        production_plugin = self.production / "plugins/azhou"
        production_plugin.mkdir(parents=True)
        (production_plugin / "secret.js").write_bytes(b"fixture-only production data")
        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        dsh_home.symlink_to(self.production, target_is_directory=True)
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["profile"]["expected_state"] = "empty_directory"
        plan["paths"]["plugin"]["expected_state"] = "empty_directory"

        tool = load_tool()
        original_scandir = tool.os.scandir
        original_lstat = tool.os.lstat
        protected_scandir_calls = []
        protected_lstat_calls = []

        def watch_protected_scandir(path):
            resolved = Path(path).resolve()
            if resolved == self.production or self.production in resolved.parents:
                protected_scandir_calls.append(resolved)
            return original_scandir(path)

        def watch_protected_lstat(path, *args, **kwargs):
            candidate_path = Path(path)
            if candidate_path != self.production and self.production in candidate_path.parents:
                protected_lstat_calls.append(candidate_path)
            return original_lstat(path, *args, **kwargs)

        with (
            mock.patch.object(tool.os, "scandir", side_effect=watch_protected_scandir),
            mock.patch.object(tool.os, "lstat", side_effect=watch_protected_lstat),
        ):
            result = tool.preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(protected_lstat_calls, [])
        self.assertEqual(protected_scandir_calls, [])

    def test_cli_returns_static_block_for_unreadable_plan_json(self):
        tool = load_tool()
        plan_file = Path(self.temporary.name) / "invalid-plan.json"
        plan_file.write_text("{", encoding="utf-8")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = tool.main([str(plan_file)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reasons"], ["plan_unreadable"])
        self.assertIs(result["runtime_isolation_verified"], False)
        self.assertIs(result["write_authorized"], False)

    def test_blocks_missing_empty_file_and_symlink_candidate_roots(self):
        empty = Path(self.temporary.name) / "empty-candidate"
        empty.mkdir()
        not_a_directory = Path(self.temporary.name) / "candidate-file"
        not_a_directory.write_bytes(b"fixture-only")
        symlink = Path(self.temporary.name) / "candidate-link"
        symlink.symlink_to(self.candidate, target_is_directory=True)
        missing = Path(self.temporary.name) / "missing-candidate"

        for label, root in (
            ("missing", missing),
            ("empty", empty),
            ("file", not_a_directory),
            ("symlink", symlink),
        ):
            with self.subTest(label=label):
                plan = copy.deepcopy(self.plan)
                plan["candidate"]["root"] = str(root)

                result = load_tool().preflight(plan)

                self.assertEqual(result["status"], "blocked")
                self.assertIn("candidate_summary_unavailable", result["reasons"])
                self.assertIsNone(result["candidate_summary_sha256"])

    def test_rejects_a_symlinked_candidate_directory_without_following_it(self):
        linked_directory = self.candidate / "linked-directory"
        linked_directory.symlink_to(self.production, target_is_directory=True)

        result = load_tool().preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_unavailable", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_blocks_candidate_if_a_file_changes_after_its_size_is_read(self):
        tool = load_tool()
        candidate_file = self.candidate / "plugin.json"
        original_open = Path.open

        def truncate_candidate(path, mode="r", *args, **kwargs):
            if path == candidate_file and mode == "rb":
                return io.BytesIO(b"")
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", new=truncate_candidate):
            result = tool.preflight(self.plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_summary_unavailable", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_host_record_shape_and_required_fields_fail_closed(self):
        malformed_hosts = (
            None,
            "not-an-object",
            {"target": None, "evidence_record": {}},
            {"target": {}, "evidence_record": None},
            {"target": self.plan["host"]["target"], "evidence_record": {"source": " "}},
        )
        for host in malformed_hosts:
            with self.subTest(host=host):
                plan = copy.deepcopy(self.plan)
                plan["host"] = host

                result = load_tool().preflight(plan)

                self.assertEqual(result["status"], "blocked")
                self.assertIn("host_target_evidence_mismatch", result["reasons"])
                self.assertIs(result["host_target_matches_evidence_record"], False)

        for field_value in ("", 7):
            with self.subTest(bundle_id=field_value):
                plan = copy.deepcopy(self.plan)
                plan["host"]["target"]["bundle_id"] = field_value

                result = load_tool().preflight(plan)

                self.assertEqual(result["status"], "blocked")
                self.assertIn("host_target_evidence_mismatch", result["reasons"])

    def test_invalid_plan_candidate_and_path_schema_are_blocked(self):
        result = load_tool().preflight(None)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("invalid_plan", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["candidate"] = []
        result = load_tool().preflight(plan)
        self.assertIn("candidate_root_invalid", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["candidate"]["root"] = "relative-candidate"
        result = load_tool().preflight(plan)
        self.assertIn("candidate_root_invalid", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

        plan = copy.deepcopy(self.plan)
        plan["preparation_root"] = "relative-preparation-root"
        result = load_tool().preflight(plan)
        self.assertIn("preparation_root_invalid", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["protected_roots"] = []
        result = load_tool().preflight(plan)
        self.assertIn("protected_roots_invalid", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["protected_roots"] = ["relative-protected-root"]
        result = load_tool().preflight(plan)
        self.assertIn("protected_root_invalid", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"] = None
        result = load_tool().preflight(plan)
        self.assertIn("planned_paths_invalid", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"] = None
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_invalid:profile", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["expected_state"] = "nonempty"
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_invalid:profile", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["path"] = "relative-profile"
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_invalid:profile", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["path"] = str(self.preparation_root)
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_outside_preparation_root:profile", result["reasons"])

    def test_canonical_path_failure_and_invalid_raw_paths_fail_closed(self):
        tool = load_tool()
        path_type = type(self.candidate)
        original_resolve = path_type.resolve

        def fail_candidate_resolve(path, *args, **kwargs):
            if path == self.candidate:
                raise RuntimeError("fixture symlink loop")
            return original_resolve(path, *args, **kwargs)

        with mock.patch.object(path_type, "resolve", new=fail_candidate_resolve):
            self.assertIsNone(tool._canonical_plan_path(str(self.candidate)))

        for value in (None, "", "relative", "/tmp/../escape"):
            with self.subTest(path=value):
                self.assertIsNone(tool._raw_plan_path(value))

    def test_missing_empty_directory_target_and_non_directory_target_block(self):
        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["expected_state"] = "empty_directory"
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_state_mismatch:profile", result["reasons"])

        self.preparation_root.mkdir()
        dsh_home = self.preparation_root / "dsh"
        dsh_home.mkdir()
        profiles = dsh_home / "profiles"
        profiles.mkdir()
        (profiles / "default").write_bytes(b"fixture-only not-a-profile-directory")
        plan = copy.deepcopy(self.plan)
        plan["paths"]["dsh_home"]["expected_state"] = "empty_directory"
        plan["paths"]["profile"]["expected_state"] = "empty_directory"

        result = load_tool().preflight(plan)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("planned_path_state_mismatch:profile", result["reasons"])

    def test_lstat_and_scandir_errors_block_planned_target_inspection(self):
        self.preparation_root.mkdir()
        tool = load_tool()
        original_lstat = Path.lstat

        def fail_preparation_lstat(path, *args, **kwargs):
            if path == self.preparation_root:
                raise PermissionError("fixture target metadata unavailable")
            return original_lstat(path, *args, **kwargs)

        with mock.patch.object(Path, "lstat", new=fail_preparation_lstat):
            result = tool.preflight(self.plan)
        self.assertIn("planned_directory_unreadable", result["reasons"])

        original_scandir = tool.os.scandir

        def fail_preparation_scandir(path):
            if Path(path) == self.preparation_root:
                raise PermissionError("fixture target directory unreadable")
            return original_scandir(path)

        with mock.patch.object(tool.os, "scandir", side_effect=fail_preparation_scandir):
            result = tool.preflight(self.plan)
        self.assertIn("planned_directory_unreadable", result["reasons"])

    def test_relationship_overlaps_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["paths"]["profile"]["path"] = str(self.preparation_root / "profile-outside-dsh")
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_relationship_invalid:profile", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["plugin"]["path"] = plan["paths"]["profile"]["path"]
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_relationship_invalid:plugin", result["reasons"])

        plan = copy.deepcopy(self.plan)
        plan["paths"]["electron_user_data"]["path"] = plan["paths"]["profile"]["path"]
        result = load_tool().preflight(plan)
        self.assertIn("planned_path_relationship_invalid:profile", result["reasons"])

    def test_candidate_overlapping_owned_roots_is_blocked_before_hashing(self):
        plan = copy.deepcopy(self.plan)
        plan["candidate"]["root"] = str(self.preparation_root)
        result = load_tool().preflight(plan)
        self.assertIn("candidate_overlaps_preparation_root", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

        dsh_home = self.preparation_root / "dsh"
        dsh_home.mkdir(parents=True)
        (dsh_home / "fixture.txt").write_text("candidate overlaps planned DSH_HOME", encoding="utf-8")
        plan = copy.deepcopy(self.plan)
        plan["candidate"]["root"] = str(dsh_home)
        result = load_tool().preflight(plan)
        self.assertIn("candidate_overlaps_planned_path", result["reasons"])
        self.assertIsNone(result["candidate_summary_sha256"])

    def test_target_scanner_skips_protected_nodes_before_metadata_or_enumeration(self):
        root = self.preparation_root
        root.mkdir()
        protected = root / "dsh/profiles"
        protected.mkdir(parents=True)
        tool = load_tool()
        original_scandir = tool.os.scandir
        original_lstat = Path.lstat
        protected_scandir = []
        protected_lstat = []

        def watch_scandir(path):
            if Path(path) == protected or protected in Path(path).parents:
                protected_scandir.append(Path(path))
            return original_scandir(path)

        def watch_lstat(path, *args, **kwargs):
            if path == protected or protected in path.parents:
                protected_lstat.append(path)
            return original_lstat(path, *args, **kwargs)

        with (
            mock.patch.object(tool.os, "scandir", side_effect=watch_scandir),
            mock.patch.object(Path, "lstat", new=watch_lstat),
        ):
            reasons = tool._target_tree_reasons(
                root,
                {"profile": protected / "default"},
                {"profile": "absent"},
                [protected],
            )

        self.assertEqual(reasons, set())
        self.assertEqual(protected_scandir, [])
        self.assertEqual(protected_lstat, [])

    def test_actual_module_entry_point_handles_missing_plan(self):
        plan_file = Path(self.temporary.name) / "not-created-plan.json"
        output = io.StringIO()
        with mock.patch("sys.argv", [str(TOOL), str(plan_file)]), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as exit_info:
                runpy.run_path(str(TOOL), run_name="__main__")

        result = json.loads(output.getvalue())
        self.assertEqual(exit_info.exception.code, 1)
        self.assertEqual(result["reasons"], ["plan_unreadable"])
        self.assertIs(result["runtime_isolation_verified"], False)
        self.assertIs(result["write_authorized"], False)


if __name__ == "__main__":
    unittest.main()

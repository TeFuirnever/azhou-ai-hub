from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
CURRENT_CASE_SHA256 = "3a01e2ebcace21bcf4dbe609dee7db806bb1c2ac67e85a4b047543e4e9abf6e9"
LEGACY_CASE_SHA256 = "0f4b59246c731e2fb2138ac74a2fc8b9c3bf0c864f2ed3856cb8244fe9ad2598"
LEGACY_RESULT_SHA256 = {
    "revision-a6cfc850-attempt-1-summary.json": "78b67833aef9ad2bf337eb2a851905cd2b7622781fe863d4a82ccd897d3ea9d0",
    "revision-de6b836a-attempt-1-summary.json": "ceeeeda13a7984f5050fb300a8d2f9afb81fc595e4ef6227d08a599b0ddfc9fc",
    "revision-dfe45d69-attempt-1-summary.json": "7fc271a32cb46676dc85ecc2c10c0662b8feabb83886d659cd1d7dd5cf7eac73",
    "revision-e1eef218-attempt-1-summary.json": "97323e91da439bb6e2df90c65b192e52c8a7f1d476e08879523ff69db120db23",
    "revision-f3ab4d37-attempt-1-summary.json": "9e2a6505dbadd0b32d3d8c95cdf0de309b7dbbf8c917581cb5768968fc92dd99",
}
PRIOR_19_CASE_SHA256 = "cfe991555de0f3086ebc4e294266ffe6c8ac84122a748eabdb1d64dece250bb8"
PRIOR_19_RESULT_SHA256 = {
    "revision-daa150ae-attempt-1-summary.json": "88c488455e9ded1a38f786e784d6ea7abde82be8236a8810c5dcae297e193429",
    "revision-8cb8447d-attempt-1-summary.json": "c0ffea2f249c4300f44a6c15aace76fb9cad61c2c9bb950ccfa22b8648096422",
    "revision-e995cac8-attempt-1-summary.json": "f6e160bdb7db057de6e6472a75ee6cf7fe2a1e738f4ac59bca8c05827a9fb0f4",
}
PRIOR_CLOSURE_CASE_SHA256 = "1d75a0a86b3da90c5551e1c6e78c4b09a310ad8a011cc5116fef64ac0d450d19"
PRIOR_CLOSURE_RESULT_SHA256 = {
    "revision-e5f16195-attempt-1-summary.json": "be2d02f6e3d259ee7d41857afe7cd1d32ef949ec099f4e895ce4378746e60715",
}
PRIOR_STATE_CASE_SHA256 = "3136808262609cf5bc9083b379b7f1cf15bb79b788127f012ff294142da09290"
PRIOR_STATE_RESULT_SHA256 = {
    "revision-45121948-attempt-1-summary.json": "cce6d8ef17114efd02dae0a89e7182dcc3ec00c3acf6f2d2a8db809413956058",
    "revision-6210ab51-attempt-1-summary.json": "e3071a4f1da088a45f70bf51d9c54693c9fdcf4088d071a822d3d569e1530f95",
}


def result_summaries() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "benchmarks/super-caveman/results").glob("*-summary.json")
    ]


def current_pass_summaries() -> list[dict]:
    return [
        summary
        for summary in result_summaries()
        if summary.get("cases_sha256") == CURRENT_CASE_SHA256
        and summary.get("status") == "pass"
    ]


class SuperCavemanBenchmarkTest(unittest.TestCase):
    def test_approved_benchmark_requires_raw_approval_environment(self) -> None:
        environment = os.environ.copy()
        environment.pop("SUPER_CAVEMAN_APPROVAL_RECORD", None)
        environment.pop("SUPER_CAVEMAN_REVIEW_RECORD", None)
        result = subprocess.run(
            [sys.executable, "benchmarks/super-caveman/benchmark.py", "check", "--promotion-evidence"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        current_passes = current_pass_summaries()
        if current_passes:
            approval = current_passes[0]["promotion_review"]["exact_diff_human_approval"]
            if approval.get("status") == "approved":
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("lacks valid paired promotion evidence", result.stdout)
            else:
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("lacks valid paired promotion evidence", result.stdout)
        else:
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn(
                "ERROR: exactly one current passing evaluation result is required; found 0",
                result.stdout,
            )

    def test_capability_and_trigger_integrity(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        current_passes = current_pass_summaries()
        if current_passes:
            approval = current_passes[0]["promotion_review"]["exact_diff_human_approval"]
            if approval.get("status") == "approved":
                reviewed = {
                    key: approval[key]
                    for key in ("base_commit", "path_set_sha256", "staged_patch_sha256")
                }
                with mock.patch.dict(benchmark.os.environ, {}, clear=True), mock.patch.object(
                    benchmark, "staged_review_digests", return_value=reviewed
                ):
                    self.assertEqual([], benchmark.check(require_promotion_evidence=False))
            else:
                errors = benchmark.check(require_promotion_evidence=False)
                self.assertTrue(
                    any("lacks valid paired promotion evidence" in error for error in errors),
                    errors,
                )
        else:
            errors = benchmark.check(require_promotion_evidence=False)
            self.assertIn(
                "exactly one current passing evaluation result is required; found 0",
                errors,
            )

    def test_evaluation_contract_is_bounded(self) -> None:
        contract = json.loads(
            (ROOT / "benchmarks/super-caveman/evaluation-contract.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, contract["execution"]["attempt"])
        self.assertEqual(1, contract["execution"]["maximum_attempts"])
        self.assertEqual(120, contract["execution"]["timeout_seconds_per_case"])
        self.assertEqual(2, contract["execution"]["concurrency"])
        self.assertIn("exclude only generated __pycache__, .pyc, and .pyo", contract["runtime"]["skill_tree_digest"])
        self.assertFalse(contract["execution"]["tool_permissions"]["default"]["repository_write"])
        self.assertEqual(
            "disposable fixture only",
            contract["execution"]["tool_permissions"]["case_overrides"]["agent-owned-edit"]["repository_write"],
        )
        self.assertEqual(CURRENT_CASE_SHA256, contract["cases"]["sha256"])
        self.assertEqual(19, contract["cases"]["count"])
        self.assertEqual(19, contract["claim_gate"]["required_passed_cases"])
        self.assertEqual(19, contract["claim_gate"]["required_total_cases"])
        legacy = contract["legacy_case_sets"]
        self.assertEqual(4, len(legacy))
        self.assertEqual(LEGACY_CASE_SHA256, legacy[0]["sha256"])
        self.assertEqual(14, legacy[0]["count"])
        self.assertEqual(LEGACY_RESULT_SHA256, legacy[0]["result_files"])
        self.assertEqual(PRIOR_19_CASE_SHA256, legacy[1]["sha256"])
        self.assertEqual(19, legacy[1]["count"])
        self.assertEqual(PRIOR_19_RESULT_SHA256, legacy[1]["result_files"])
        self.assertEqual(PRIOR_CLOSURE_CASE_SHA256, legacy[2]["sha256"])
        self.assertEqual(19, legacy[2]["count"])
        self.assertEqual(PRIOR_CLOSURE_RESULT_SHA256, legacy[2]["result_files"])
        self.assertEqual(PRIOR_STATE_CASE_SHA256, legacy[3]["sha256"])
        self.assertEqual(19, legacy[3]["count"])
        self.assertEqual(PRIOR_STATE_RESULT_SHA256, legacy[3]["result_files"])
        self.assertEqual(0, contract["claim_gate"]["high_risk_failures_allowed"])
        self.assertIn("Git-external", contract["evidence"]["raw_outputs"])
        self.assertEqual(3, contract["promotion_review"]["independent_paired_judges"])
        self.assertEqual(
            ["candidate-baseline", "baseline-candidate", "candidate-baseline"],
            contract["promotion_review"]["presentation_orders"],
        )
        self.assertEqual(0, contract["promotion_review"]["high_risk_regressions_allowed"])
        approval = contract["promotion_review"]["exact_diff_human_approval"]
        self.assertTrue(approval["required"])
        self.assertEqual("super-caveman-exact-diff-approval.v1", approval["schema"])
        self.assertEqual("Git aggregate receipt; raw approval Git-external", approval["record_storage"])
        self.assertEqual("SUPER_CAVEMAN_APPROVAL_RECORD", approval["raw_record_environment"])
        self.assertEqual("SUPER_CAVEMAN_REVIEW_RECORD", approval["review_record_environment"])
        self.assertIn("every promotion ingest and replay", approval["raw_record_validation"])
        self.assertIn(
            "every replay revalidates both Git-external raw records",
            approval["approved_replay_validation"],
        )
        self.assertIn("current staged or committed exact-diff", approval["approved_replay_validation"])
        self.assertIn("regular file", approval["raw_record_validation"])
        self.assertIn("current staged or committed exact-diff", approval["approved_replay_validation"])
        self.assertIn("byte-identical index and working-tree", approval["approved_replay_validation"])
        self.assertIn("later commits or working-tree changes", approval["approved_replay_validation"])
        self.assertIn("path/blob tuples", approval["digest_algorithm"])
        self.assertIn("sha256", approval["digest_algorithm"])

    def test_behavior_attempt_trail_retains_failures_and_one_pass(self) -> None:
        result_paths = sorted((ROOT / "benchmarks/super-caveman/results").glob("*-summary.json"))
        legacy_paths = [
            path
            for path in result_paths
            if json.loads(path.read_text(encoding="utf-8")).get("cases_sha256")
            == LEGACY_CASE_SHA256
        ]
        legacy_results = [json.loads(path.read_text(encoding="utf-8")) for path in legacy_paths]
        self.assertEqual(set(LEGACY_RESULT_SHA256), {path.name for path in legacy_paths})
        for path in legacy_paths:
            self.assertEqual(LEGACY_RESULT_SHA256[path.name], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(2, sum(result["status"] == "failed" for result in legacy_results))
        self.assertEqual(1, sum(result["status"] == "pass" for result in legacy_results))
        self.assertEqual(2, sum(result["status"] == "superseded" for result in legacy_results))
        self.assertEqual([11, 12, 14, 14, 14], sorted(result["passed"] for result in legacy_results))
        self.assertEqual(3, sum(result["passed"] == 14 for result in legacy_results))

        prior_paths = [
            path
            for path in result_paths
            if json.loads(path.read_text(encoding="utf-8")).get("cases_sha256")
            == PRIOR_19_CASE_SHA256
        ]
        prior_results = [json.loads(path.read_text(encoding="utf-8")) for path in prior_paths]
        self.assertEqual(set(PRIOR_19_RESULT_SHA256), {path.name for path in prior_paths})
        for path in prior_paths:
            self.assertEqual(PRIOR_19_RESULT_SHA256[path.name], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(2, sum(result["status"] == "failed" for result in prior_results))
        self.assertEqual(1, sum(result["status"] == "pass" for result in prior_results))

        closure_paths = [
            path
            for path in result_paths
            if json.loads(path.read_text(encoding="utf-8")).get("cases_sha256")
            == PRIOR_CLOSURE_CASE_SHA256
        ]
        self.assertEqual(set(PRIOR_CLOSURE_RESULT_SHA256), {path.name for path in closure_paths})
        for path in closure_paths:
            self.assertEqual(
                PRIOR_CLOSURE_RESULT_SHA256[path.name],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        self.assertEqual(
            ["failed"],
            [json.loads(path.read_text(encoding="utf-8"))["status"] for path in closure_paths],
        )

        state_paths = [
            path
            for path in result_paths
            if json.loads(path.read_text(encoding="utf-8")).get("cases_sha256")
            == PRIOR_STATE_CASE_SHA256
        ]
        self.assertEqual(set(PRIOR_STATE_RESULT_SHA256), {path.name for path in state_paths})
        for path in state_paths:
            self.assertEqual(
                PRIOR_STATE_RESULT_SHA256[path.name],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        self.assertEqual(
            ["failed", "failed"],
            sorted(json.loads(path.read_text(encoding="utf-8"))["status"] for path in state_paths),
        )

    def test_passing_attempt_is_bound_to_stable_runtime_tree(self) -> None:
        current_passes = current_pass_summaries()
        self.assertLessEqual(len(current_passes), 1)
        if current_passes:
            self.assertEqual(current_passes[0]["skill_tree_sha256"], subprocess.run(
                [sys.executable, "-c", "import sys; sys.path.insert(0, 'benchmarks/super-caveman'); import benchmark; print(benchmark.sha256_skill_tree())"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip())

    def test_legacy_case_results_are_history_not_stale_current_passes(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        errors = benchmark.check()
        self.assertFalse(
            any("evaluation result case digest is stale" in error for error in errors),
            errors,
        )
        current_passes = current_pass_summaries()
        if not current_passes:
            self.assertIn(
                "exactly one current passing evaluation result is required; found 0",
                errors,
            )

    def test_integrity_rejects_empty_reviewer_and_permissions(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        original_loads = benchmark.json.loads

        def malformed_loads(text: str) -> object:
            payload = original_loads(text)
            if isinstance(payload, dict) and payload.get("schema") == "super-caveman-evaluation-result.v1":
                payload["reviewer"] = {"identity": "judge", "review_sha256": {}}
                payload["tool_permissions"] = {
                    "network": {},
                    "repository_write": 1,
                    "shell": False,
                    "external_apps": False,
                }
            return payload

        with mock.patch.object(benchmark.json, "loads", side_effect=malformed_loads):
            errors = benchmark.check()
        self.assertTrue(any("reviewer evidence is invalid" in error for error in errors))
        self.assertTrue(any("tool permissions are incomplete" in error for error in errors))

    def test_integrity_rejects_changed_local_source_hash(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        original_load = benchmark.load

        def malformed_load(name: str) -> object:
            payload = original_load(name)
            if name == "capability-map.json":
                payload["sources"][0]["local_snapshot_sha256"] = "0" * 64
            return payload

        with mock.patch.object(benchmark, "load", side_effect=malformed_load):
            errors = benchmark.check()
        self.assertTrue(any("local source hash differs from trusted snapshot" in error for error in errors))

    def test_exact_diff_approval_requires_bound_record(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            benchmark_root = Path(directory)
            results = benchmark_root / "results"
            results.mkdir()
            result_path = results / "revision-test-summary.json"
            approval = {
                "schema": "super-caveman-exact-diff-approval.v1",
                "status": "approved",
                "review_scope": "all staged task paths except the aggregate result and aggregate approval record",
                "base_commit": "1" * 40,
                "path_set_sha256": "2" * 64,
                "staged_patch_sha256": "3" * 64,
                "approver": "workspace-owner",
                "approved_at": "2026-08-24T12:00:00+08:00",
                "record_path": "results/revision-1234abcd-exact-diff-approval.json",
                "record_sha256": "4" * 64,
                "record_storage": "Git aggregate receipt; raw approval Git-external",
            }
            with mock.patch.object(benchmark, "BENCHMARK", benchmark_root):
                self.assertFalse(benchmark.is_approved_exact_diff("approved", result_path))
                self.assertFalse(benchmark.is_approved_exact_diff({"status": "approved"}, result_path))
                self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                self.assertFalse(
                    benchmark.is_approved_exact_diff(
                        {**approval, "record_path": "results/*.json"}, result_path
                    )
                )

                raw_record = {
                    "schema": "super-caveman-exact-diff-human-record.v1",
                    "decision": "approved",
                    "approver": "workspace-owner",
                    "approved_at": "2026-08-24T12:00:00+08:00",
                    "base_commit": "1" * 40,
                    "review_scope": "all staged task paths except the aggregate result and aggregate approval record",
                    "path_set_sha256": "2" * 64,
                    "staged_patch_sha256": "3" * 64,
                }
                raw_path = benchmark_root / "raw-human-approval.json"
                raw_path.write_text(json.dumps(raw_record, indent=2) + "\n", encoding="utf-8")

                record = {
                    "schema": "super-caveman-exact-diff-approval-record.v1",
                    "decision": "approved",
                    "approver": "workspace-owner",
                    "approved_at": "2026-08-24T12:00:00+08:00",
                    "base_commit": "1" * 40,
                    "review_scope": "all staged task paths except the aggregate result and aggregate approval record",
                    "path_set_sha256": "2" * 64,
                    "staged_patch_sha256": "3" * 64,
                    "raw_approval_record_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                    "raw_approval_storage": "Git-external",
                }
                record_path = results / "revision-1234abcd-exact-diff-approval.json"
                record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                approval["record_sha256"] = hashlib.sha256(record_path.read_bytes()).hexdigest()
                review_record = {
                    "schema": "super-caveman-spec-review.v1",
                    "identity": "/root/reviewer",
                    "candidate_raw_sha256": "7" * 64,
                    "cases_sha256": "8" * 64,
                }
                review_path = benchmark_root / "review.json"
                review_path.write_text(json.dumps(review_record, indent=2) + "\n", encoding="utf-8")
                result_path.write_text(
                    json.dumps(
                        {
                            "reviewer": {
                                "identity": review_record["identity"],
                                "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                            },
                            "promotion_review": {
                                "candidate_raw_sha256": review_record["candidate_raw_sha256"]
                            },
                            "cases_sha256": review_record["cases_sha256"],
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                explicit_env = {
                    benchmark.RAW_APPROVAL_ENV: str(raw_path),
                    benchmark.REVIEW_RECORD_ENV: str(review_path),
                }
                staged = {
                    "base_commit": "1" * 40,
                    "path_set_sha256": "2" * 64,
                    "staged_patch_sha256": "3" * 64,
                }
                with mock.patch.dict(benchmark.os.environ, {}, clear=True), mock.patch.object(
                    benchmark, "staged_review_digests", return_value=staged
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                    self.assertFalse(
                        benchmark.is_approved_exact_diff(
                            {**approval, "status": "pending"}, result_path
                        )
                    )
                with mock.patch.dict(
                    benchmark.os.environ,
                    {benchmark.RAW_APPROVAL_ENV: ""},
                    clear=True,
                ), mock.patch.object(benchmark, "staged_review_digests", return_value=staged):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(
                    benchmark.os.environ,
                    {benchmark.RAW_APPROVAL_ENV: raw_path.name},
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                raw_link = benchmark_root / "raw-human-approval-link.json"
                raw_link.symlink_to(raw_path)
                with mock.patch.dict(
                    benchmark.os.environ,
                    {benchmark.RAW_APPROVAL_ENV: str(raw_link)},
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(
                    benchmark.os.environ,
                    {benchmark.RAW_APPROVAL_ENV: str(results)},
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(
                    benchmark.os.environ,
                    {
                        benchmark.RAW_APPROVAL_ENV: str(
                            ROOT / "benchmarks/super-caveman/evaluation-contract.json"
                        )
                    },
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))

                def bind_raw(payload: dict, raw_digest: str | None = None) -> None:
                    raw_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                    record["raw_approval_record_sha256"] = (
                        raw_digest or hashlib.sha256(raw_path.read_bytes()).hexdigest()
                    )
                    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                    approval["record_sha256"] = hashlib.sha256(record_path.read_bytes()).hexdigest()

                invalid_raw_fields = {
                    "schema": "wrong-schema",
                    "decision": "rejected",
                    "approver": "different-owner",
                    "approved_at": "2026-08-24T13:00:00+08:00",
                    "base_commit": "4" * 40,
                    "review_scope": "different scope",
                    "path_set_sha256": "5" * 64,
                    "staged_patch_sha256": "6" * 64,
                }
                for field, invalid_value in invalid_raw_fields.items():
                    with self.subTest(raw_field=field):
                        bind_raw({**raw_record, field: invalid_value})
                        with mock.patch.dict(
                            benchmark.os.environ,
                            explicit_env,
                        ), mock.patch.object(
                            benchmark, "staged_review_digests", return_value=staged
                        ):
                            self.assertFalse(
                                benchmark.is_approved_exact_diff(approval, result_path)
                            )
                bind_raw({**raw_record, "unexpected": True})
                with mock.patch.dict(
                    benchmark.os.environ,
                    explicit_env,
                ), mock.patch.object(benchmark, "staged_review_digests", return_value=staged):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                bind_raw(raw_record, raw_digest="0" * 64)
                with mock.patch.dict(
                    benchmark.os.environ,
                    explicit_env,
                ), mock.patch.object(benchmark, "staged_review_digests", return_value=staged):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))

                bind_raw(raw_record)
                with mock.patch.dict(
                    benchmark.os.environ,
                    explicit_env,
                ):
                    with mock.patch.object(benchmark, "staged_review_digests", return_value=staged):
                        self.assertTrue(benchmark.is_approved_exact_diff(approval, result_path))
                    with mock.patch.object(
                        benchmark,
                        "staged_review_digests",
                        return_value={**staged, "staged_patch_sha256": "6" * 64},
                    ):
                        self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))

                for field, invalid_value in {
                    "schema": "wrong-schema",
                    "identity": "/root/other-reviewer",
                    "candidate_raw_sha256": "9" * 64,
                    "cases_sha256": "a" * 64,
                }.items():
                    with self.subTest(review_field=field):
                        invalid_review = {**review_record, field: invalid_value}
                        review_path.write_text(
                            json.dumps(invalid_review, indent=2) + "\n", encoding="utf-8"
                        )
                        with mock.patch.dict(
                            benchmark.os.environ,
                            explicit_env,
                        ), mock.patch.object(
                            benchmark, "staged_review_digests", return_value=staged
                        ):
                            self.assertFalse(
                                benchmark.is_approved_exact_diff(approval, result_path)
                            )
                review_path.write_text(
                    json.dumps(review_record, indent=2) + "\n", encoding="utf-8"
                )
                with mock.patch.dict(
                    benchmark.os.environ,
                    {benchmark.RAW_APPROVAL_ENV: str(raw_path)},
                    clear=True,
                ), mock.patch.object(benchmark, "staged_review_digests", return_value=staged):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(benchmark.os.environ, {}, clear=True), mock.patch.object(
                    benchmark,
                    "staged_review_digests",
                    return_value={**staged, "staged_patch_sha256": "6" * 64},
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(benchmark.os.environ, {}, clear=True), mock.patch.object(
                    benchmark, "staged_review_digests", return_value=None
                ), mock.patch.object(benchmark, "committed_review_digests", return_value=None):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(benchmark.os.environ, {}, clear=True), mock.patch.object(
                    benchmark, "staged_review_digests", return_value=None
                ), mock.patch.object(
                    benchmark, "committed_review_digests", return_value=staged
                ):
                    self.assertFalse(benchmark.is_approved_exact_diff(approval, result_path))
                with mock.patch.dict(
                    benchmark.os.environ,
                    explicit_env,
                ), mock.patch.object(
                    benchmark, "staged_review_digests", return_value=None
                ), mock.patch.object(
                    benchmark, "committed_review_digests", return_value=staged
                ):
                    self.assertTrue(benchmark.is_approved_exact_diff(approval, result_path))

    def test_staged_review_digests_normalize_benchmark_relative_exclusions(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        captured: dict[str, list[str]] = {}

        def canonical_tuples(_diff_range: str | None, selectors: list[str]) -> list[bytes]:
            captured["selectors"] = selectors
            return [b"README.md\0" + b"1" * 40 + b"\0" + b"2" * 40 + b"\0"]

        with mock.patch.object(
            benchmark, "_canonical_blob_tuples", side_effect=canonical_tuples
        ), mock.patch.object(
            benchmark, "_staged_aggregates_match", return_value=True
        ), mock.patch.object(
            benchmark.subprocess, "check_output", return_value="1" * 40
        ):
            benchmark.staged_review_digests(
                {
                    "results/revision-test-summary.json",
                    "results/revision-1234abcd-exact-diff-approval.json",
                }
            )
        first_command = captured["selectors"]
        self.assertIn(
            ":(top,literal,exclude)benchmarks/super-caveman/results/revision-test-summary.json",
            first_command,
        )
        self.assertIn(
            ":(top,literal,exclude)benchmarks/super-caveman/results/revision-1234abcd-exact-diff-approval.json",
            first_command,
        )

    def test_staged_review_rejects_aggregate_index_worktree_split(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "super-caveman@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Super Caveman Test"],
                cwd=repository,
                check=True,
            )
            benchmark_root = repository / "benchmarks/super-caveman"
            results = benchmark_root / "results"
            results.mkdir(parents=True)
            subject = repository / "README.md"
            subject.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)

            subject.write_text("approved subject\n", encoding="utf-8")
            result_path = results / "revision-1234abcd-attempt-1-summary.json"
            record_path = results / "revision-1234abcd-exact-diff-approval.json"
            result_path.write_text('{"status":"pass"}\n', encoding="utf-8")
            record_path.write_text('{"decision":"approved"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            exclusions = {
                "results/revision-1234abcd-attempt-1-summary.json",
                "results/revision-1234abcd-exact-diff-approval.json",
            }
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                self.assertIsNotNone(benchmark.staged_review_digests(exclusions))
                result_path.write_text('{"status":"tampered"}\n', encoding="utf-8")
                self.assertIsNone(benchmark.staged_review_digests(exclusions))

    def test_committed_review_uses_approval_anchor_after_later_commit(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "super-caveman@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Super Caveman Test"],
                cwd=repository,
                check=True,
            )
            benchmark_root = repository / "benchmarks/super-caveman"
            results = benchmark_root / "results"
            results.mkdir(parents=True)
            (repository / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()

            (repository / "README.md").write_text("approved subject\n", encoding="utf-8")
            result_path = results / "revision-1234abcd-attempt-1-summary.json"
            record_path = results / "revision-1234abcd-exact-diff-approval.json"
            result_path.write_text('{"status":"pass"}\n', encoding="utf-8")
            record_path.write_text('{"decision":"approved"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "approved subject"], cwd=repository, check=True)

            exclusions = {
                "results/revision-1234abcd-attempt-1-summary.json",
                "results/revision-1234abcd-exact-diff-approval.json",
            }
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                approved = benchmark.committed_review_digests(exclusions, base_commit)

            (repository / "UNRELATED.md").write_text("later work\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "unrelated follow-up"], cwd=repository, check=True)
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                replayed = benchmark.committed_review_digests(exclusions, base_commit)

            self.assertIsNotNone(approved)
            self.assertEqual(approved, replayed)

            result_path.write_text('{"status":"tampered"}\n', encoding="utf-8")
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                self.assertIsNone(benchmark.committed_review_digests(exclusions, base_commit))

    def test_committed_review_rejects_later_commit_to_approved_path(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "super-caveman@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Super Caveman Test"],
                cwd=repository,
                check=True,
            )
            benchmark_root = repository / "benchmarks/super-caveman"
            results = benchmark_root / "results"
            results.mkdir(parents=True)
            readme = repository / "README.md"
            readme.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()

            readme.write_text("approved subject\n", encoding="utf-8")
            result_path = results / "revision-1234abcd-attempt-1-summary.json"
            record_path = results / "revision-1234abcd-exact-diff-approval.json"
            result_path.write_text('{"status":"pass"}\n', encoding="utf-8")
            record_path.write_text('{"decision":"approved"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "approved subject"], cwd=repository, check=True)

            readme.write_text("later drift\n", encoding="utf-8")
            exclusions = {
                "results/revision-1234abcd-attempt-1-summary.json",
                "results/revision-1234abcd-exact-diff-approval.json",
            }
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                working_tree_replay = benchmark.committed_review_digests(exclusions, base_commit)

            subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "change approved path"], cwd=repository, check=True)
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                committed_replay = benchmark.committed_review_digests(exclusions, base_commit)

            self.assertIsNone(working_tree_replay)
            self.assertIsNone(committed_replay)

    def test_committed_review_rejects_aggregate_outside_head_ancestry(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "super-caveman@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Super Caveman Test"],
                cwd=repository,
                check=True,
            )
            (repository / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()
            main_branch = subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=repository, text=True
            ).strip()

            subprocess.run(["git", "switch", "-qc", "approval-side"], cwd=repository, check=True)
            results = repository / "benchmarks/super-caveman/results"
            results.mkdir(parents=True)
            result_bytes = b'{"status":"pass"}\n'
            record_bytes = b'{"decision":"approved"}\n'
            result_path = results / "revision-1234abcd-attempt-1-summary.json"
            record_path = results / "revision-1234abcd-exact-diff-approval.json"
            result_path.write_bytes(result_bytes)
            record_path.write_bytes(record_bytes)
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "side approval"], cwd=repository, check=True)

            subprocess.run(["git", "switch", "-q", main_branch], cwd=repository, check=True)
            results.mkdir(parents=True)
            result_path.write_bytes(result_bytes)
            record_path.write_bytes(record_bytes)
            exclusions = {
                "results/revision-1234abcd-attempt-1-summary.json",
                "results/revision-1234abcd-exact-diff-approval.json",
            }
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", repository / "benchmarks/super-caveman"
            ):
                self.assertIsNone(benchmark.committed_review_digests(exclusions, base_commit))

    def test_review_digests_ignore_repository_diff_configuration(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "super-caveman@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Super Caveman Test"],
                cwd=repository,
                check=True,
            )
            external_diff = repository / "external-diff.sh"
            external_diff.write_text("#!/bin/sh\nprintf 'configured external diff\\n'\n", encoding="utf-8")
            external_diff.chmod(0o755)
            order_file = repository / "diff-order.txt"
            order_file.write_text("NEW.md\nB.md\nA.md\nOLD.md\n", encoding="utf-8")
            first_path = repository / "A.md"
            second_path = repository / "B.md"
            first_path.write_text("base A\n", encoding="utf-8")
            second_path.write_text("base B\n", encoding="utf-8")
            old_path = repository / "OLD.md"
            old_path.write_text("approved subject\n", encoding="utf-8")
            (repository / ".gitattributes").write_text("*.md diff=custom\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)
            base_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()

            benchmark_root = repository / "benchmarks/super-caveman"
            results = benchmark_root / "results"
            results.mkdir(parents=True)
            subprocess.run(["git", "mv", "OLD.md", "NEW.md"], cwd=repository, check=True)
            first_path.write_text("approved A\n", encoding="utf-8")
            second_path.write_text("approved B\n", encoding="utf-8")
            result_path = results / "revision-1234abcd-attempt-1-summary.json"
            record_path = results / "revision-1234abcd-exact-diff-approval.json"
            result_path.write_text('{"status":"pass"}\n', encoding="utf-8")
            record_path.write_text('{"decision":"approved"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            exclusions = {
                "results/revision-1234abcd-attempt-1-summary.json",
                "results/revision-1234abcd-exact-diff-approval.json",
            }
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                expected = benchmark.staged_review_digests(exclusions)

            for key, value in (
                ("diff.noprefix", "true"),
                ("diff.renames", "true"),
                ("diff.algorithm", "patience"),
                ("diff.external", str(external_diff)),
                ("diff.orderFile", str(order_file)),
                ("diff.custom.command", str(external_diff)),
            ):
                subprocess.run(["git", "config", key, value], cwd=repository, check=True)
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                configured = benchmark.staged_review_digests(exclusions)
            self.assertEqual(expected, configured)

            subprocess.run(["git", "commit", "-qm", "approved rename"], cwd=repository, check=True)
            with mock.patch.object(benchmark, "ROOT", repository), mock.patch.object(
                benchmark, "BENCHMARK", benchmark_root
            ):
                committed = benchmark.committed_review_digests(exclusions, base_commit)
            self.assertEqual(
                {key: expected[key] for key in ("base_commit", "path_set_sha256", "staged_patch_sha256")},
                {key: committed[key] for key in ("base_commit", "path_set_sha256", "staged_patch_sha256")},
            )

    def test_integrity_requires_fresh_promotion_after_runtime_change(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        original_sha256_file = benchmark.sha256_file

        def pinned_case_digest(name: str) -> str:
            if name == "response-cases.json":
                return CURRENT_CASE_SHA256
            return original_sha256_file(name)

        with mock.patch.object(
            benchmark, "sha256_skill_tree", return_value="0" * 64
        ), mock.patch.object(benchmark, "sha256_file", side_effect=pinned_case_digest):
            errors = benchmark.check()
        self.assertIn("exactly one current passing evaluation result is required; found 0", errors)

    def test_public_integrity_still_recomputes_the_approved_exact_diff(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)

        with mock.patch.object(
            benchmark, "staged_review_digests", return_value=None
        ), mock.patch.object(
            benchmark, "committed_review_digests", return_value=None
        ):
            errors = benchmark.check(require_promotion_evidence=False)

        self.assertTrue(
            any(
                error.startswith(
                    "passing evaluation result lacks valid paired promotion evidence: "
                )
                for error in errors
            ),
            errors,
        )

    def test_stable_digest_includes_hidden_runtime_files(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            (runtime / "SKILL.md").write_text("visible\n", encoding="utf-8")
            with mock.patch.object(benchmark, "SKILL", runtime):
                before = benchmark.sha256_skill_tree()
                hidden = runtime / ".digest-regression"
                hidden.write_text("must affect digest\n", encoding="utf-8")
                self.assertNotEqual(before, benchmark.sha256_skill_tree())

    def test_stable_digest_excludes_generated_python_cache(self) -> None:
        sys.path.insert(0, str(ROOT / "benchmarks/super-caveman"))
        try:
            import benchmark
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            (runtime / "SKILL.md").write_text("visible\n", encoding="utf-8")
            with mock.patch.object(benchmark, "SKILL", runtime):
                before = benchmark.sha256_skill_tree()
                cache = runtime / "scripts/__pycache__"
                cache.mkdir(parents=True)
                (cache / "runtime.pyc").write_bytes(b"generated")
                self.assertEqual(before, benchmark.sha256_skill_tree())


if __name__ == "__main__":
    unittest.main()

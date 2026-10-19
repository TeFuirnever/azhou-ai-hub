from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "super-repo-pedant" / "scripts" / "manage_evolution.py"
SPEC = importlib.util.spec_from_file_location("manage_evolution", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ManageEvolutionTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_cli_with_umask(self, umask: int, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
            preexec_fn=lambda: os.umask(umask),
        )

    def add_signal_args(
        self,
        project: Path,
        *,
        session: str,
        category: str = "stale_fact",
        severity: str = "medium",
        outcome: str = "failure",
        mechanism: str = "missed-memory",
        observed_at: str = "2026-08-23T00:00:00+00:00",
    ) -> list[str]:
        return [
            "add-signal",
            "--project",
            str(project),
            "--runtime",
            "codex",
            "--mechanism",
            mechanism,
            "--category",
            category,
            "--severity",
            severity,
            "--outcome",
            outcome,
            "--session-id",
            session,
            "--evidence",
            f"receipt-{session}",
            "--source",
            "receipt",
            "--user-feedback",
            "corrected",
            "--observed-at",
            observed_at,
        ]

    def add_signal(
        self,
        project: Path,
        *,
        session: str,
        category: str = "stale_fact",
        severity: str = "medium",
        outcome: str = "failure",
        mechanism: str = "missed-memory",
        observed_at: str = "2026-08-23T00:00:00+00:00",
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            *self.add_signal_args(
                project,
                session=session,
                category=category,
                severity=severity,
                outcome=outcome,
                mechanism=mechanism,
                observed_at=observed_at,
            )
        )

    def propose_args(self, project: Path, *extra: str) -> list[str]:
        return [
            "propose",
            "--project",
            str(project),
            "--mechanism",
            "missed-memory",
            "--change-summary",
            "Require project memory classification",
            "--regression-id",
            "multi-surface-handoff",
            *extra,
        ]

    def propose(self, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_cli(*self.propose_args(project, *extra))

    def test_one_ordinary_failure_cannot_form_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.assertEqual(0, self.add_signal(project, session="one").returncode)
            result = self.propose(project)
            self.assertEqual(2, result.returncode)
            self.assertIn("two independent", result.stderr)

    def test_two_independent_failures_create_isolated_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="one")
            self.add_signal(project, session="two")
            result = self.propose(project)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            candidate = Path(payload["candidate"])
            self.assertTrue(candidate.is_file())
            self.assertIn(".azhou/super-repo-pedant/evolution/candidates", candidate.as_posix())
            self.assertFalse(payload["live_skill_modified"])
            self.assertEqual(2, payload["independent_sessions"])

    def test_one_severe_safety_failure_can_form_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="severe", category="safety", severity="critical")
            result = self.propose(project)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["severe_trigger"])

    def test_failed_processing_retains_batch_and_valid_candidate_can_archive_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="one")
            self.add_signal(project, session="two")
            signals = project / ".azhou" / "super-repo-pedant" / "evolution" / "signals.jsonl"
            before = signals.read_text(encoding="utf-8")
            invalid = project / "invalid.json"
            invalid.write_text("{}", encoding="utf-8")
            failed = self.run_cli("archive", "--project", str(project), "--candidate", str(invalid))
            self.assertEqual(2, failed.returncode)
            self.assertEqual(before, signals.read_text(encoding="utf-8"))

            proposal = json.loads(self.propose(project).stdout)
            archived = self.run_cli("archive", "--project", str(project), "--candidate", proposal["candidate"])
            self.assertEqual(0, archived.returncode, archived.stdout + archived.stderr)
            self.assertEqual("", signals.read_text(encoding="utf-8"))
            self.assertTrue(Path(json.loads(archived.stdout)["archive"]).is_file())
            repeated = self.run_cli("archive", "--project", str(project), "--candidate", proposal["candidate"])
            self.assertEqual(2, repeated.returncode)

    def test_archive_rejects_symlinked_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="one")
            self.add_signal(project, session="two")
            proposal = json.loads(self.propose(project).stdout)
            link = project / ".azhou" / "super-repo-pedant" / "evolution" / "candidates" / "linked.json"
            link.symlink_to(Path(proposal["candidate"]))
            result = self.run_cli("archive", "--project", str(project), "--candidate", str(link))
            self.assertEqual(2, result.returncode)
            self.assertIn("non-symlink", result.stderr)

    def test_add_signal_rejects_symlinked_signals_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            outside = project / "outside-sentinel.txt"
            outside.write_text("SENTINEL\n", encoding="utf-8")
            evolution = project / ".azhou" / "super-repo-pedant" / "evolution"
            evolution.mkdir(parents=True)
            (evolution / "signals.jsonl").symlink_to(outside)
            result = self.add_signal(project, session="one")
            self.assertEqual(2, result.returncode)
            self.assertIn("symlink", result.stderr)
            self.assertEqual("SENTINEL\n", outside.read_text(encoding="utf-8"))

    def test_propose_rejects_symlinked_candidates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="one")
            self.add_signal(project, session="two")
            outside = project / "outside-candidates"
            outside.mkdir()
            candidates = project / ".azhou" / "super-repo-pedant" / "evolution" / "candidates"
            candidates.symlink_to(outside)
            result = self.propose(project)
            self.assertEqual(2, result.returncode)
            self.assertIn("symlink", result.stderr)
            self.assertEqual([], list(outside.iterdir()))

    @unittest.skipIf(os.name == "nt", "0700/0600 mode enforcement is a POSIX contract")
    def test_private_modes_hold_under_umask_022(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for session in ("one", "two"):
                result = self.run_cli_with_umask(0o022, *self.add_signal_args(project, session=session))
                self.assertEqual(0, result.returncode, result.stderr)
            result = self.run_cli_with_umask(0o022, *self.propose_args(project))
            self.assertEqual(0, result.returncode, result.stderr)
            namespace = project / ".azhou"
            for directory_path in (
                namespace,
                namespace / "super-repo-pedant",
                namespace / "super-repo-pedant" / "evolution",
                namespace / "super-repo-pedant" / "evolution" / "candidates",
            ):
                self.assertEqual(0o700, directory_path.stat().st_mode & 0o777, str(directory_path))
            self.assertEqual(0o600, (namespace / "super-repo-pedant" / "evolution" / "signals.jsonl").stat().st_mode & 0o777)
            candidate_file = next((namespace / "super-repo-pedant" / "evolution" / "candidates").glob("*.json"))
            self.assertEqual(0o600, candidate_file.stat().st_mode & 0o777)

    @unittest.skipIf(os.name == "nt", "the transaction lock needs fcntl, absent on Windows")
    def test_append_blocks_while_archive_transaction_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            state_root = MODULE.safe_state_root(project, None)
            with MODULE.transaction_lock(state_root, project):
                racer = subprocess.Popen(
                    [sys.executable, str(SCRIPT), *self.add_signal_args(project, session="racer")],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                time.sleep(0.5)
                self.assertIsNone(
                    racer.poll(),
                    "add-signal must wait for the held transaction lock, not write through it",
                )
            stdout, stderr = racer.communicate(timeout=30)
            self.assertEqual(0, racer.returncode, stderr)
            signal_id = json.loads(stdout)["signal_id"]
            self.assertIn(signal_id, (state_root / "signals.jsonl").read_text(encoding="utf-8"))

    @unittest.skipIf(os.name == "nt", "without fcntl the archive window is not serialized on Windows")
    def test_signal_attempted_during_archive_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="one")
            self.add_signal(project, session="two")
            proposal = json.loads(self.propose(project).stdout)

            original = MODULE.write_private_text
            racer: subprocess.Popen[str] | None = None

            def publish_spawning_racer(path: Path, text: str, *, root: Path) -> None:
                nonlocal racer
                original(path, text, root=root)
                if path.name.startswith("processed-") and racer is None:
                    # The racer attempts its append inside the archive window;
                    # with the transaction lock it commits only after the
                    # archive releases, and must still land in live or archive.
                    racer = subprocess.Popen(
                        [sys.executable, str(SCRIPT), *self.add_signal_args(project, session="racer")],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

            MODULE.write_private_text = publish_spawning_racer
            try:
                args = argparse.Namespace(project=project, state_root=None, candidate=Path(proposal["candidate"]))
                self.assertEqual(0, MODULE.cmd_archive(args))
            finally:
                MODULE.write_private_text = original

            self.assertIsNotNone(racer)
            stdout, stderr = racer.communicate(timeout=30)
            self.assertEqual(0, racer.returncode, stderr)
            signal_id = json.loads(stdout)["signal_id"]
            evolution = project / ".azhou" / "super-repo-pedant" / "evolution"
            live = (evolution / "signals.jsonl").read_text(encoding="utf-8")
            archived = "".join(
                path.read_text(encoding="utf-8") for path in (evolution / "archive").glob("*.jsonl")
            )
            self.assertTrue(
                signal_id in live or signal_id in archived,
                f"confirmed signal lost everywhere: {signal_id}",
            )

    def test_global_candidate_requires_two_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = base / "first"
            second = base / "second"
            first.mkdir()
            second.mkdir()
            self.add_signal(first, session="one", category="safety", severity="critical")
            one_project = self.propose(first, "--scope", "global")
            self.assertEqual(2, one_project.returncode)

            self.add_signal(second, session="two", category="safety", severity="critical")
            second_signals = second / ".azhou" / "super-repo-pedant" / "evolution" / "signals.jsonl"
            two_projects = self.propose(first, "--scope", "global", "--include-signal-file", str(second_signals))
            self.assertEqual(0, two_projects.returncode, two_projects.stdout + two_projects.stderr)
            self.assertEqual(2, json.loads(two_projects.stdout)["projects"])

    def evaluation(self, candidate_id: str, diff_sha: str, approved: bool = True) -> dict:
        return {
            "schema_version": MODULE.EVALUATION_SCHEMA,
            "candidate_id": candidate_id,
            "diff_sha256": diff_sha,
            "deterministic_checks": [
                {"name": name, "status": "passed"} for name in sorted(MODULE.REQUIRED_CHECKS)
            ],
            "paired_votes": [
                {"judge_id": "judge-1", "order": "baseline_first", "preference": "candidate"},
                {"judge_id": "judge-2", "order": "candidate_first", "preference": "candidate"},
                {"judge_id": "judge-3", "order": "baseline_first", "preference": "baseline"},
            ],
            "safety_review": {"status": "passed", "regression_found": False},
            "human_approval": {
                "status": "approved" if approved else "pending",
                "reviewer": "human-maintainer" if approved else "",
                "diff_sha256": diff_sha,
            },
        }

    def test_promotion_requires_exact_human_approval_and_all_gates(self) -> None:
        candidate = {
            "schema_version": MODULE.CANDIDATE_SCHEMA,
            "candidate_id": "a" * 24,
            "created_at": "2026-08-23T00:00:00+00:00",
            "status": "proposed",
            "scope": "project",
            "mechanism": "missed-memory",
            "change_summary": "Require project memory classification",
            "regression_id": "multi-surface-handoff",
            "signal_ids": ["d" * 64],
            "independent_sessions": 2,
            "projects": 1,
            "severe_trigger": False,
            "parse_errors": 0,
            "origin": "learned",
            "live_skill_modified": False,
        }
        diff_sha = "b" * 64
        pending = self.evaluation(candidate["candidate_id"], diff_sha, approved=False)
        self.assertTrue(any("human approval" in error for error in MODULE.validate_promotion(candidate, pending)))
        approved = self.evaluation(candidate["candidate_id"], diff_sha, approved=True)
        self.assertEqual([], MODULE.validate_promotion(candidate, approved))
        approved["human_approval"]["diff_sha256"] = "c" * 64
        self.assertTrue(any("exact diff" in error for error in MODULE.validate_promotion(candidate, approved)))

    def test_legacy_schema_versions_remain_accepted(self) -> None:
        candidate = {
            "schema_version": MODULE.LEGACY_CANDIDATE_SCHEMA,
            "candidate_id": "a" * 24,
            "created_at": "2026-08-23T00:00:00+00:00",
            "status": "proposed",
            "scope": "project",
            "mechanism": "missed-memory",
            "change_summary": "Require project memory classification",
            "regression_id": "multi-surface-handoff",
            "signal_ids": ["d" * 64],
            "independent_sessions": 2,
            "projects": 1,
            "severe_trigger": False,
            "parse_errors": 0,
            "origin": "learned",
            "live_skill_modified": False,
        }
        diff_sha = "b" * 64
        approved = self.evaluation(candidate["candidate_id"], diff_sha, approved=True)
        approved["schema_version"] = MODULE.LEGACY_EVALUATION_SCHEMA
        self.assertEqual([], MODULE.validate_promotion(candidate, approved))

        signal = {
            "schema_version": MODULE.LEGACY_SIGNAL_SCHEMA,
            "signal_id": "a" * 64,
            "observed_at": "2026-08-23T00:00:00+00:00",
            "project_id": "b" * 24,
            "runtime": "codex",
            "session_digest": "c" * 24,
            "source": "hook",
            "provenance": "learned",
            "category": "privacy",
            "mechanism": "raw-capture",
            "severity": "high",
            "outcome": "failure",
            "user_feedback": "none",
            "evidence_digest": "d" * 64,
        }
        self.assertEqual([], MODULE.validate_signal(signal))

    def test_raw_fields_are_rejected(self) -> None:
        signal = {
            "schema_version": MODULE.SIGNAL_SCHEMA,
            "signal_id": "a" * 64,
            "observed_at": "2026-08-23T00:00:00+00:00",
            "project_id": "b" * 24,
            "runtime": "codex",
            "session_digest": "c" * 24,
            "source": "hook",
            "provenance": "learned",
            "category": "privacy",
            "mechanism": "raw-capture",
            "severity": "high",
            "outcome": "failure",
            "user_feedback": "none",
            "evidence_digest": "d" * 64,
            "raw_text": "secret material",
        }
        self.assertIn("forbidden_raw_field", MODULE.validate_signal(signal))

    def test_health_trend_is_investigation_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.add_signal(project, session="recent-fail", outcome="failure", observed_at="2026-08-22T00:00:00+00:00")
            self.add_signal(project, session="old-success", outcome="success", observed_at="2026-08-10T00:00:00+00:00")
            result = self.run_cli("health", "--project", str(project), "--now", "2026-08-23T00:00:00+00:00")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["declining"])
            self.assertEqual("investigate", payload["action"])
            self.assertFalse(payload["promotion_authority"])


if __name__ == "__main__":
    unittest.main()

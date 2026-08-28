from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "repo-pedant" / "scripts" / "manage_evolution.py"
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
        )

    def propose(self, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
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
        )

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
            self.assertIn(".azhou/repo-pedant/evolution/candidates", candidate.as_posix())
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
            signals = project / ".azhou" / "repo-pedant" / "evolution" / "signals.jsonl"
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
            link = project / ".azhou" / "repo-pedant" / "evolution" / "candidates" / "linked.json"
            link.symlink_to(Path(proposal["candidate"]))
            result = self.run_cli("archive", "--project", str(project), "--candidate", str(link))
            self.assertEqual(2, result.returncode)
            self.assertIn("non-symlink", result.stderr)

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
            second_signals = second / ".azhou" / "repo-pedant" / "evolution" / "signals.jsonl"
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

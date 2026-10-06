from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest import mock

from scripts.verify import SUMMARY_SCHEMA, commands, main, summary_payload


FAILURE_PATTERN = re.compile(r"(?i)\bfailed\b|failures?=\d+")
ROOT = Path(__file__).parents[1]
VALIDATOR = ROOT / "skills" / "azhou-verify" / "scripts" / "check-gate-report.py"


class FakeRunner:
    """Return a configured exit code per gate command without launching anything."""

    def __init__(self, codes: dict[str, int] | None = None, raise_on: str | None = None):
        self.codes = codes or {}
        self.raise_on = raise_on
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs):
        self.calls.append(list(command))
        joined = " ".join(command)
        if self.raise_on and self.raise_on in joined:
            raise OSError(f"cannot launch: {joined}")
        code = 0
        for needle, value in self.codes.items():
            if needle in joined:
                code = value
        return subprocess.CompletedProcess(command, code)


def run_main(argv: list[str], runner: FakeRunner) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch("subprocess.run", runner):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def split_summary(out: str) -> tuple[dict, str]:
    """Split a --print-summary capture into (payload, final verdict line)."""
    lines = out.rstrip("\n").splitlines()
    verdict = lines[-1]
    start = lines.index("{")
    return json.loads("\n".join(lines[start:-1])), verdict


class VerifyFinalVerdictTest(unittest.TestCase):
    """Contract tests for the single aggregate final verdict (issue #252, u8).

    Evidence: docs/research/2026-10-06-cross-harness-execution-evidence.md
    section 3.7 - a piped tail masked a real failure (the consumer's exit code
    0 hid the gate's failure) and one captured block held both
    "FAILED (failures=2)" and "verification passed". The gate therefore runs
    every sub-gate to completion and always ends on exactly one aggregate
    verdict line that is the true conjunction of all sub-gate results.
    """

    def test_green_run_ends_with_single_pass_verdict(self) -> None:
        runner = FakeRunner()
        code, out, err = run_main([], runner)
        self.assertEqual(0, code)
        self.assertEqual("", err)
        lines = out.strip().splitlines()
        self.assertEqual("verification passed", lines[-1])
        self.assertEqual(1, sum(1 for line in lines if line == "verification passed"))
        for line in lines:
            self.assertIsNone(FAILURE_PATTERN.search(line), line)
        self.assertEqual(len(commands(sys.executable)), len(runner.calls))

    def test_failed_aggregate_never_prints_pass_verdict(self) -> None:
        runner = FakeRunner(codes={"unittest": 1})
        code, out, err = run_main([], runner)
        self.assertEqual(1, code)
        lines = out.strip().splitlines()
        self.assertEqual(
            "verification FAILED (1 of 8 gates failed: unit tests)", lines[-1]
        )
        self.assertNotIn("verification passed", out)
        self.assertEqual(
            {"FAILED: unit tests (exit 1)"},
            {line for line in err.splitlines() if line.startswith("FAILED:")},
        )
        # Every gate runs to completion; the aggregate reflects all of them.
        self.assertEqual(len(commands(sys.executable)), len(runner.calls))

    def test_multiple_failures_aggregate_into_one_line(self) -> None:
        runner = FakeRunner(codes={"unittest": 2, "super-caveman": 3})
        code, out, err = run_main([], runner)
        self.assertEqual(2, code, "exit code is the first failing gate's code")
        lines = out.strip().splitlines()
        self.assertEqual(
            "verification FAILED (2 of 8 gates failed: unit tests, super-caveman benchmark)",
            lines[-1],
        )
        self.assertEqual(1, sum(1 for line in lines if "verification FAILED" in line))
        self.assertNotIn("verification passed", out)
        self.assertEqual(
            {"FAILED: unit tests (exit 2)", "FAILED: super-caveman benchmark (exit 3)"},
            {line for line in err.splitlines() if line.startswith("FAILED:")},
        )

    def test_launch_failure_counts_as_failed_gate(self) -> None:
        runner = FakeRunner(raise_on="check_repository.py")
        code, out, err = run_main([], runner)
        self.assertEqual(127, code)
        lines = out.strip().splitlines()
        self.assertEqual(
            "verification FAILED (1 of 8 gates failed: repository policy)", lines[-1]
        )
        self.assertNotIn("verification passed", out)
        self.assertIn("FAILED: repository policy (exit 127)", err)

    def test_print_summary_keeps_verdict_as_last_line(self) -> None:
        runner = FakeRunner()
        code, out, _ = run_main(["--print-summary"], runner)
        self.assertEqual(0, code)
        payload, verdict = split_summary(out)
        self.assertEqual("verification passed", verdict)
        self.assertEqual(SUMMARY_SCHEMA, payload["schema"])
        self.assertEqual("passed", payload["verdict"])
        self.assertEqual(0, payload["exit_code"])
        self.assertEqual([], payload["failed_gates"])
        self.assertEqual(len(commands(sys.executable)), len(payload["gates"]))
        for gate in payload["gates"]:
            self.assertEqual("passed", gate["status"])

    def test_print_summary_reports_failed_gates(self) -> None:
        runner = FakeRunner(codes={"super-repo-pedant": 4})
        code, out, err = run_main(["--print-summary"], runner)
        self.assertEqual(4, code)
        payload, verdict = split_summary(out)
        self.assertEqual(
            "verification FAILED (1 of 8 gates failed: super-repo-pedant benchmark)",
            verdict,
        )
        self.assertEqual("failed", payload["verdict"])
        self.assertEqual(4, payload["exit_code"])
        self.assertEqual(["super-repo-pedant benchmark"], payload["failed_gates"])
        failed_entry = next(
            gate for gate in payload["gates"] if gate["label"] == "super-repo-pedant benchmark"
        )
        self.assertEqual(4, failed_entry["exit_code"])
        self.assertEqual("failed", failed_entry["status"])
        passed_entry = next(gate for gate in payload["gates"] if gate["label"] == "unit tests")
        self.assertEqual(0, passed_entry["exit_code"])
        self.assertEqual("passed", passed_entry["status"])
        self.assertIn("FAILED: super-repo-pedant benchmark (exit 4)", err)

    def test_promotion_evidence_flag_reaches_super_caveman_gate(self) -> None:
        runner = FakeRunner()
        code, out, _ = run_main(["--promotion-evidence"], runner)
        self.assertEqual(0, code)
        super_caveman_calls = [call for call in runner.calls if "super-caveman" in " ".join(call)]
        self.assertEqual(1, len(super_caveman_calls))
        self.assertIn("--promotion-evidence", super_caveman_calls[0])

    def test_green_summary_lines_match_no_failure_pattern(self) -> None:
        """A green capture carrying the JSON summary stays validator-clean."""
        results = [
            {"label": label, "command": " ".join(command), "exit_code": 0}
            for label, command in commands(sys.executable)
        ]
        rendered = json.dumps(summary_payload(results), indent=2).splitlines()
        rendered.append("verification passed")
        for line in rendered:
            self.assertIsNone(FAILURE_PATTERN.search(line), line)

    def test_green_capture_satisfies_the_gate_report_validator(self) -> None:
        """The azhou-verify validator must stay green on the new default output."""
        runner = FakeRunner()
        code, out, err = run_main([], runner)
        self.assertEqual(0, code)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--exit-code", str(code)],
            input=out + err,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("verdict: green", result.stdout)

    def test_red_capture_with_child_failure_lines_stays_red(self) -> None:
        """The historically observed contradiction shape (a child unittest
        failure summary next to the gate's verdict) stays red for the
        validator, and the gate's own last line is the aggregate verdict
        instead of a pass claim."""
        runner = FakeRunner(codes={"unittest": 1})
        code, out, err = run_main([], runner)
        self.assertEqual(1, code)
        self.assertNotIn("verification passed", out)
        merged = "OK (476 tests)\nFAILED (failures=1)\n" + out + err
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--exit-code", str(code)],
            input=merged,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("verdict: red", result.stdout)
        self.assertIn("failure verdict line: FAILED (failures=1)", result.stdout)


if __name__ == "__main__":
    unittest.main()

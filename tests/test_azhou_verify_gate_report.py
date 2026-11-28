from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATOR = ROOT / "skills" / "super-azhou-verify" / "scripts" / "check-gate-report.py"


def run_validator(exit_code: int, captured: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--exit-code", str(exit_code)],
        input=captured,
        capture_output=True,
        text=True, encoding="utf-8",
        check=False,
    )
    return result.returncode, result.stdout


class AzhouVerifyGateReportTest(unittest.TestCase):
    """Regression fixtures for the mechanical green/red verdict derivation.

    The contradiction case replays the anonymized shape of a captured block
    observed on 2026-08-31 where a unittest failure summary sat next to the
    gate's passing summary; the verdict rule must make that shape red.
    Since issue #252 u8 the gate itself always ends on one aggregate verdict
    line, so the current red fixture carries that line and the green fixture
    also covers a capture that carries the machine summary JSON.
    """

    def test_green_on_clean_pass(self) -> None:
        code, out = run_validator(0, "==> unit tests\nOK (26 tests)\nverification passed\n")
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)

    def test_red_on_nonzero_exit(self) -> None:
        code, out = run_validator(1, "FAILED (failures=2)\nFAILED: unit tests (exit 1)\n")
        self.assertEqual(1, code)
        self.assertIn("verdict: red", out)

    def test_red_on_current_aggregate_verdict_shape(self) -> None:
        captured = (
            "OK (476 tests)\n"
            "FAILED (failures=2)\n"
            "FAILED: unit tests (exit 1)\n"
            "verification FAILED (1 of 8 gates failed: unit tests)\n"
        )
        code, out = run_validator(1, captured)
        self.assertEqual(1, code)
        self.assertIn("verdict: red", out)
        self.assertIn("failure verdict line: FAILED (failures=2)", out)

    def test_red_on_contradiction_shape(self) -> None:
        code, out = run_validator(0, "FAILED (failures=2)\nverification passed\n")
        self.assertEqual(1, code)
        self.assertIn("verdict: red", out)
        self.assertIn("failure verdict line: FAILED (failures=2)", out)

    def test_argparse_error_with_wrapper_pass_is_red(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "azhou_hub.py"), "verify", "--not-a-real-option"],
            capture_output=True,
            text=True, encoding="utf-8",
            check=False,
        )
        self.assertEqual(2, result.returncode)
        captured = result.stdout + result.stderr + "verification passed\n"
        code, out = run_validator(0, captured)
        self.assertEqual(1, code)
        self.assertIn("argument parser error line:", out)

    def test_expected_error_log_without_argparse_signature_stays_green(self) -> None:
        captured = "negative control expected error: missing fixture\nverification passed\n"
        code, out = run_validator(0, captured)
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)

    def test_expected_argparse_rejection_inside_passing_gate_stays_green(self) -> None:
        captured = (
            "==> unit tests\n"
            "...usage: azhou-ai-hub [-h] {verify} ...\n"
            "azhou-ai-hub: error: unrecognized arguments: --plan-id reviewed\n"
            "Ran 1 test\nOK\n"
            "==> package manifests\n"
            "passed\nverification passed\n"
        )
        code, out = run_validator(0, captured)
        self.assertEqual(0, code, out)
        self.assertIn("verdict: green", out)

    def test_green_capture_with_machine_summary_stays_green(self) -> None:
        captured = (
            "==> repository policy\n"
            '  "schema": "azhou-hub.verify-summary.v1",\n'
            '  "verdict": "passed",\n'
            '  "failed_gates": [],\n'
            "verification passed\n"
        )
        code, out = run_validator(0, captured)
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)

    def test_setup_receipts_with_pass_status_keep_capture_green(self) -> None:
        for status in ("pass", "dry_run"):
            with self.subTest(status=status):
                receipt = json.dumps({
                    "schema_version": "azhou-ai-hub.setup.v1",
                    "status": status,
                    "mode": "copy",
                    "target": "/temporary/skills",
                    "applied": status == "pass",
                    "skills": [],
                }, indent=2)
                code, out = run_validator(0, receipt + "\nverification passed\n")
                self.assertEqual(0, code)
                self.assertIn("verdict: green", out)

    def test_setup_receipt_conflicts_override_outer_success(self) -> None:
        start = '{"schema_version": "azhou-ai-hub.setup.v1", '
        for case, receipt in {
            "truncated": start + '"status": "pass"',
            "invalid JSON": start + '"status": pass}',
            "trailing damage": start + '"status": "pass"}!',
            "duplicate status": start + '"status": "fail", "status": "pass"}',
            "fail": start + '"status": "fail"}',
            "rolled back": start + '"status": "rolled_back"}',
            "partial": start + '"status": "partial"}',
            "dry-run conflict": start + '"status": "dry_run_same_source"}',
        }.items():
            with self.subTest(case=case):
                code, out = run_validator(0, receipt + "\nverification passed\n")
                self.assertEqual(1, code, out)
                self.assertIn("verdict: red", out)
                self.assertIn("setup receipt", out)

    def test_truncated_schema_first_prefixes_are_red(self) -> None:
        for receipt in ('{"schema_version"', '{"schema_', '{"schema'):
            with self.subTest(receipt=receipt):
                code, out = run_validator(0, receipt + "\nverification passed\n")
                self.assertEqual(1, code, out)
                self.assertIn("malformed or truncated Foundation setup receipt", out)

    def test_json_escaped_schema_key_is_recognized(self) -> None:
        receipt = '{"schema\\u005fversion":"azhou-ai-hub.setup.v1","status":'
        code, out = run_validator(0, receipt + "\nverification passed\n")
        self.assertEqual(1, code, out)
        self.assertIn("malformed or truncated Foundation setup receipt", out)

    def test_json_encoded_receipt_inside_capture_is_inspected(self) -> None:
        receipt = json.dumps({"schema_version": "azhou-ai-hub.setup.v1", "status": "fail"})
        captured = json.dumps({"captured_stdout": receipt}) + "\nverification passed\n"
        code, out = run_validator(0, captured)
        self.assertEqual(1, code, out)
        self.assertIn("non-passing Foundation setup receipt status: 'fail'", out)

    def test_skip_lines_are_quoted_not_upgraded(self) -> None:
        code, out = run_validator(0, "skipped: benchmark not run\nverification passed\n")
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)
        self.assertIn("skipped: skipped: benchmark not run", out)


if __name__ == "__main__":
    unittest.main()

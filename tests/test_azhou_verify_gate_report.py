from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATOR = ROOT / "skills" / "azhou-verify" / "scripts" / "check-gate-report.py"


def run_validator(exit_code: int, captured: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--exit-code", str(exit_code)],
        input=captured,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout


class AzhouVerifyGateReportTest(unittest.TestCase):
    """Regression fixtures for the mechanical green/red verdict derivation.

    The contradiction case replays the anonymized shape of a captured block
    observed on 2026-08-31 where a unittest failure summary sat next to the
    gate's passing summary; the verdict rule must make that shape red.
    """

    def test_green_on_clean_pass(self) -> None:
        code, out = run_validator(0, "==> unit tests\nOK (26 tests)\nverification passed\n")
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)

    def test_red_on_nonzero_exit(self) -> None:
        code, out = run_validator(1, "FAILED (failures=2)\nFAILED: unit tests (exit 1)\n")
        self.assertEqual(1, code)
        self.assertIn("verdict: red", out)

    def test_red_on_contradiction_shape(self) -> None:
        code, out = run_validator(0, "FAILED (failures=2)\nverification passed\n")
        self.assertEqual(1, code)
        self.assertIn("verdict: red", out)
        self.assertIn("failure verdict line: FAILED (failures=2)", out)

    def test_skip_lines_are_quoted_not_upgraded(self) -> None:
        code, out = run_validator(0, "skipped: benchmark not run\nverification passed\n")
        self.assertEqual(0, code)
        self.assertIn("verdict: green", out)
        self.assertIn("skipped: skipped: benchmark not run", out)


if __name__ == "__main__":
    unittest.main()

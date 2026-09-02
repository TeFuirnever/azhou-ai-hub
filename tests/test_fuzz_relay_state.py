"""Deterministic smoke test for scripts/fuzz_relay_state.py.

Runs a bounded, seeded slice of the fuzzer on every test run so a parser
crash regression or a broken harness fails loudly before CI fuzzing would.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
HARNESS = ROOT / "scripts" / "fuzz_relay_state.py"


class FuzzHarnessSmokeTest(unittest.TestCase):
    def test_seeded_bounded_run_stays_clean(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "--seconds",
                "2",
                "--max-inputs",
                "300",
                "--seed",
                "20260902",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr[-2000:])
        self.assertIn("crashes=0", result.stdout)


if __name__ == "__main__":
    unittest.main()

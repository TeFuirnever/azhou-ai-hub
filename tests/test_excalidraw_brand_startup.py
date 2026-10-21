from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATOR = ROOT / "skills" / "excalidraw-diagram" / "scripts" / "check-brand-startup.py"

PREFIX = "\U0001f98a \u963f\u821f \u00b7 Excalidraw Diagram \u542f\u52a8\uff08"


def run_validator(line: str, *flags: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), *flags],
        input=line,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.returncode, result.stdout


class ExcalidrawBrandStartupTest(unittest.TestCase):
    """Regression fixtures for the startup-line value discipline.

    Real sessions repeatedly broadcast the contract template verbatim
    (scope=<diagram>) when scope was not yet nameable; the discipline makes
    `unresolved` the only legal pending value and forbids template text.
    """

    def test_concrete_value_ok(self) -> None:
        code, out = run_validator(PREFIX + "mode=create, deliverable=svg, scope=checkout-flow）\n")
        self.assertEqual(0, code)
        self.assertIn("ok:", out)

    def test_template_leak_rejected(self) -> None:
        code, out = run_validator(PREFIX + "mode=create, deliverable=svg, scope=<diagram>）\n")
        self.assertEqual(1, code)
        self.assertIn("invalid:", out)
        self.assertIn("template placeholder in scope", out)

    def test_unresolved_before_lock_ok(self) -> None:
        code, out = run_validator(PREFIX + "mode=create, deliverable=svg, scope=unresolved）\n")
        self.assertEqual(0, code)
        self.assertIn("ok:", out)

    def test_unresolved_after_lock_rejected(self) -> None:
        code, out = run_validator(PREFIX + "mode=create, deliverable=svg, scope=unresolved）\n", "--locked")
        self.assertEqual(1, code)
        self.assertIn("scope=unresolved after requirement lock", out)

    def test_ok_line_prints_utf8_under_cp1252_console(self) -> None:
        # Git Bash piped stdio on windows-latest defaults to the cp1252 ANSI
        # codec (T6 receipt, #236); the validator's own echo must not depend
        # on the console locale. The line travels in via argv, isolating the
        # write side.
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), PREFIX + "mode=create, deliverable=svg, scope=checkout-flow）\n"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.startswith("ok:"), result.stdout[:80])
        self.assertIn("\U0001f98a", result.stdout)


if __name__ == "__main__":
    unittest.main()

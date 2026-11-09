from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "pstack-agent-harness"


@unittest.skipUnless(shutil.which("awk"), "awk is required for the Copilot hook")
class PstackResumeContractTest(unittest.TestCase):
    def test_unshipped_resume_is_not_approved_but_existing_contract_remains(self) -> None:
        contracts = [PACKAGE / "hub-runtime" / "hooks" / "script-contracts.awk"]
        contracts.extend((PACKAGE / "harness" / "pstack" / runtime / "hooks" / "script-contracts.awk")
                         for runtime in ("claude-code", "codex", "skills-root", "zcode"))
        with tempfile.TemporaryDirectory() as temporary:
            driver = Path(temporary) / "driver.awk"
            driver.write_text(
                'function safe_path(p) { return 1 }\n'
                'BEGIN { T[1]="read"; T[2]="--project"; T[3]="fixture"; '
                'print script_contract("skills/poteto-mode/scripts/resume.mjs", "node", T, 1, 3); '
                'T[1]="fixture"; print script_contract("skills/poteto-mode/scripts/check-plan.mjs", "node", T, 1, 1) }\n',
                encoding="utf-8",
            )
            for contract in contracts:
                with self.subTest(contract=contract):
                    result = subprocess.run(["awk", "-f", str(contract), "-f", str(driver)],
                                            capture_output=True, text=True, encoding="utf-8", check=False)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual(["0", "1"], result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()

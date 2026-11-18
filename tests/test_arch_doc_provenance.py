import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path("benchmarks/super-arch-doc/run_case.py")
SKILL = Path("skills/super-arch-doc")


class TemplateProvenanceTests(unittest.TestCase):
    def test_inventory_through_benchmark_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / SKILL, root / SKILL)
            (root / RUNNER.parent).mkdir(parents=True)
            shutil.copyfile(ROOT / RUNNER, root / RUNNER)
            manifest = root / SKILL / "references/templates/PROVENANCE.md"
            original = manifest.read_text(encoding="utf-8")
            missing_prd = "\n".join(line for line in original.splitlines()
                                    if not line.startswith("| [prd.md]"))
            prd_row = next(line for line in original.splitlines() if line.startswith("| [prd.md]"))
            for label, content, expected in (
                ("empty", "", False),
                ("missing prd", missing_prd, False),
                ("duplicate", original.replace(prd_row, prd_row + "\n" + prd_row), False),
                ("bad digest", original.replace(prd_row, re.sub(r"[a-f0-9]{64}", "0" * 64, prd_row)), False),
                ("complete", original, True),
            ):
                with self.subTest(label=label):
                    manifest.write_text(content, encoding="utf-8")
                    run = subprocess.run([sys.executable, str(root / RUNNER)],
                                         capture_output=True, text=True, encoding="utf-8",
                                         env={**os.environ, "PYTHONUTF8": "1"})
                    receipt = json.loads(run.stdout.splitlines()[-1])
                    self.assertEqual(run.returncode, 0 if expected else 1)
                    self.assertEqual(receipt["status"], "passed" if expected else "failed")
                    checks = {c["name"]: c["pass"] for c in receipt["checks"]}
                    self.assertEqual(checks["template hashes match PROVENANCE"], expected)

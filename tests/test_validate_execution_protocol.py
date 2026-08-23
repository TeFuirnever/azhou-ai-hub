from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "repo-pedant" / "scripts" / "validate_execution_protocol.py"
FIXTURES = ROOT / "benchmarks" / "repo-pedant" / "protocol"


class ValidateExecutionProtocolTest(unittest.TestCase):
    def run_validator(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), str(path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_variant(self, value: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "execution.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def valid_fixture(self) -> dict:
        return json.loads((FIXTURES / "valid.execution.json").read_text(encoding="utf-8"))

    def test_valid_protocol_passes(self) -> None:
        result = self.run_validator(FIXTURES / "valid.execution.json")
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_prior_freeform_brand_drift_is_rejected(self) -> None:
        result = self.run_validator(FIXTURES / "prior-drift.execution.json")
        self.assertEqual(1, result.returncode)
        errors = json.loads(result.stdout)["errors"]
        self.assertTrue(any("events[0].message" in error for error in errors))
        self.assertTrue(any("inventory" in error for error in errors))
        self.assertTrue(any("verify_success" in error for error in errors))

    def test_success_requires_every_check_and_must_be_last(self) -> None:
        protocol = self.valid_fixture()
        protocol["events"][-1]["completed_checks"].remove("coverage")
        protocol["events"].append(
            {"stage": "verify_failure", "message": "❌ 验证失败｜check=coverage｜impact=late evidence"}
        )
        result = self.run_validator(self.write_variant(protocol))
        self.assertEqual(1, result.returncode)
        errors = json.loads(result.stdout)["errors"]
        self.assertTrue(any("completed_checks" in error for error in errors))
        self.assertTrue(any("last event" in error for error in errors))

    def test_failed_run_ends_with_exact_failure_anchor(self) -> None:
        protocol = self.valid_fixture()
        protocol["result"] = "failed"
        protocol["checks"][-1]["status"] = "failed"
        protocol["checks"][-1]["evidence"] = "Coverage tool returned an incomplete range."
        protocol["events"][-1] = {
            "stage": "verify_failure",
            "message": "❌ 验证失败｜check=coverage｜impact=one range needs direct read",
        }
        result = self.run_validator(self.write_variant(protocol))
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()

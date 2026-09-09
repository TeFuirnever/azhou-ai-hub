from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "repo-pedant" / "benchmark.py"
FIXTURE = ROOT / "benchmarks" / "repo-pedant" / "fixtures" / "code-spec-conflict"


def load_benchmark_module():
    # Load under a unique name: test_super_caveman_benchmark imports its own
    # module as plain "benchmark", and sys.modules must not collide.
    spec = importlib.util.spec_from_file_location("repo_pedant_benchmark", BENCHMARK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECEIPT = """## 🦊 阿舟 · Repo Pedant receipt

> 🧹 代码是唯一现役答案，其他都要对齐。

- Schema: repo-pedant.receipt.v2
- Status: complete
- Mode: reconcile
- Scope: synthetic fixture

### 🧭 Current truth
- Current truth: src/routes.ts and tests/routes.test.ts

### 🧹 Changed
- Changed: README.md and STATUS.md
- Reminders: POST /v3/export remains an unimplemented target

### ✅ Verification
- Verified: ./verify.sh

### 🔒 Boundaries
- Holds: none

### ➡️ Next action
- Next action: none

### 🧠 Learning
- Learning signal: stale_fact — current docs claimed v3
"""


class RepoPedantBenchmarkTest(unittest.TestCase):
    def run_benchmark(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BENCHMARK), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    @unittest.skipIf(
        os.name == "nt",
        "case verify commands are POSIX shell scripts; the deterministic gate runs on ubuntu",
    )
    def test_check_validates_registered_cases(self) -> None:
        result = self.run_benchmark("check")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(4, json.loads(result.stdout)["cases"])

    def test_run_verify_command_routes_shell_scripts_through_git_bash_on_windows(self) -> None:
        module = load_benchmark_module()
        completed = subprocess.CompletedProcess(["bash", "./verify.sh"], 1)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(module.os, "name", "nt"), mock.patch.object(
                module.shutil,
                "which",
                side_effect=lambda name: r"C:\Git\bin\bash.exe" if name == "bash" else None,
            ), mock.patch.object(module.subprocess, "run", return_value=completed) as run_mock:
                result = module.run_verify_command({"verify_command": ["./verify.sh"]}, Path(directory))
        self.assertIs(completed, result)
        self.assertEqual([r"C:\Git\bin\bash.exe", "./verify.sh"], run_mock.call_args.args[0])

    def test_run_verify_command_leaves_non_shell_commands_untouched_on_windows(self) -> None:
        module = load_benchmark_module()
        completed = subprocess.CompletedProcess(["tool", "--check"], 0)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(module.os, "name", "nt"), mock.patch.object(
                module.subprocess, "run", return_value=completed
            ) as run_mock:
                result = module.run_verify_command({"verify_command": ["tool", "--check"]}, Path(directory))
        self.assertIs(completed, result)
        self.assertEqual(["tool", "--check"], run_mock.call_args.args[0])

    def test_run_verify_command_leaves_shell_scripts_direct_on_posix(self) -> None:
        module = load_benchmark_module()
        completed = subprocess.CompletedProcess(["./verify.sh"], 1)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(module.os, "name", "posix"), mock.patch.object(
                module.subprocess, "run", return_value=completed
            ) as run_mock:
                result = module.run_verify_command({"verify_command": ["./verify.sh"]}, Path(directory))
        self.assertIs(completed, result)
        self.assertEqual(["./verify.sh"], run_mock.call_args.args[0])

    def test_multi_surface_case_requires_project_memory_sync(self) -> None:
        case = json.loads(
            (ROOT / "benchmarks" / "repo-pedant" / "cases" / "multi-surface-handoff.case.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("agent memory", case["prompt"])
        memory = ROOT / "benchmarks" / "repo-pedant" / "fixtures" / "software-handoff" / "agent-memory" / "MEMORY.md"
        self.assertTrue(memory.is_file())
        verifier = memory.parents[1] / "verify.sh"
        self.assertIn("agent-memory/MEMORY.md", verifier.read_text(encoding="utf-8"))

    @unittest.skipIf(
        os.name == "nt",
        "case verify commands are POSIX shell scripts; the deterministic gate runs on ubuntu",
    )
    def test_verify_accepts_usable_first_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            shutil.copytree(FIXTURE, candidate)
            (candidate / "README.md").write_text(
                "# Export API\n\nCurrent endpoint: `POST /v2/export`.\n",
                encoding="utf-8",
            )
            (candidate / "STATUS.md").write_text(
                "# Status\n\n- Active export route: `POST /v2/export`\n- POST /v3/export remains planned.\n",
                encoding="utf-8",
            )
            (candidate / "response.md").write_text(RECEIPT, encoding="utf-8")
            (candidate / "checks.txt").write_text("./verify.sh: pass\n", encoding="utf-8")
            run = root / "run.json"
            run.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "case_id": "code-spec-conflict",
                        "agent": "test-agent",
                        "model": "test-model",
                        "attempt": 1,
                        "human_review": {"status": "passed", "reviewer": "human-test"},
                        "safety_review": {"status": "passed", "reviewer": "safety-test"},
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_benchmark(
                "verify",
                "--case",
                "code-spec-conflict",
                "--candidate",
                str(candidate),
                "--run",
                str(run),
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["first_pass_usable"])

    @unittest.skipIf(
        os.name == "nt",
        "case verify commands are POSIX shell scripts; the deterministic gate runs on ubuntu",
    )
    def test_verify_detects_protected_code_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            shutil.copytree(FIXTURE, candidate)
            (candidate / "src" / "routes.ts").write_text("export const route = 'changed';\n", encoding="utf-8")
            (candidate / "response.md").write_text(RECEIPT, encoding="utf-8")
            (candidate / "checks.txt").write_text("failed\n", encoding="utf-8")
            run = root / "run.json"
            run.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "case_id": "code-spec-conflict",
                        "agent": "test-agent",
                        "model": "test-model",
                        "attempt": 1,
                        "human_review": {"status": "passed", "reviewer": "human-test"},
                        "safety_review": {"status": "passed", "reviewer": "safety-test"},
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_benchmark(
                "verify",
                "--case",
                "code-spec-conflict",
                "--candidate",
                str(candidate),
                "--run",
                str(run),
            )

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertFalse(json.loads(result.stdout)["gates"]["protected_paths"])


if __name__ == "__main__":
    unittest.main()

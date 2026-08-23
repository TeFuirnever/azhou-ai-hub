from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "benchmark.py"


class ExcalidrawBenchmarkTest(unittest.TestCase):
    def test_external_benchmark_wires_to_runtime_skill(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BENCHMARK), "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("5 cases", result.stdout)

    def test_setup_is_harness_neutral_and_preview_first(self) -> None:
        setup = (ROOT / "skills" / "excalidraw-diagram" / "references" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("uv sync --frozen --dry-run", setup)
        self.assertIn("npm ci --dry-run --ignore-scripts", setup)
        self.assertIn("pipx install uv", setup)
        self.assertNotIn("~/.agents", setup)
        self.assertNotIn("~/.claude", setup)


if __name__ == "__main__":
    unittest.main()

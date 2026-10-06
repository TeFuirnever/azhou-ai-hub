"""Sandbox fallback verification and explicit holds for excalidraw-diagram.

Evidence: docs/research/2026-10-06-cross-harness-execution-evidence.md section
3.4 — under a Codex sandbox the render/preview chain failed five ways (patch
rejected, renderer traceback, sips failure, file:// preview blocked, magick
fonts missing) and the session ended with a silent "Visual review: skipped".
u5 requires a GUI-free geometry-plus-hash fallback channel and an explicit
hold instead of a silent skip, aligned with the holds mechanism of the other
benchmark suites (for example session-insights "zcode unsupported").
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "excalidraw-diagram" / "scripts" / "visual-check.py"
BENCHMARK = ROOT / "benchmarks" / "excalidraw-diagram" / "ordinary-model-floor" / "benchmark.py"
SUITE = BENCHMARK.parent
CASE = SUITE / "cases" / "layered-architecture.case.json"
REFERENCE_SCENE = SUITE / "fixtures" / "reference" / "reference.architecture.excalidraw"
REFERENCE_SVG = SUITE / "fixtures" / "reference" / "reference.architecture.svg"
FALLBACK_RECEIPT = SUITE / "fixtures" / "reference" / "reference.architecture.svg.visual-check.json"
SANDBOX_RUN = SUITE / "fixtures" / "reference" / "reference.sandbox-blocked.run.json"

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"fake-pixel-data" * 40

SHIM_IMPORT_ERROR = {
    "playwright/__init__.py": 'raise ImportError("simulated sandbox: playwright denied")\n',
}

SHIM_LAUNCH_DENIED = {
    "playwright/__init__.py": "",
    "playwright/sync_api.py": '''
class _Browser:
    def close(self):
        pass


class _Chromium:
    def launch(self, headless=True):
        raise RuntimeError("simulated sandbox: browser launch denied")


class _Playwright:
    chromium = _Chromium()


class _Manager:
    def __enter__(self):
        return _Playwright()

    def __exit__(self, *exc):
        return False


def sync_playwright():
    return _Manager()
''',
}

SHIM_CAPTURE_OK = {
    "playwright/__init__.py": "",
    "playwright/sync_api.py": '''
FAKE_PNG = %(fake_png)r


class _Element:
    def screenshot(self, path):
        with open(path, "wb") as handle:
            handle.write(FAKE_PNG)


class _Page:
    def goto(self, url):
        pass

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, script, arg):
        pass

    def query_selector(self, selector):
        return _Element()


class _Browser:
    def new_page(self, viewport=None):
        return _Page()

    def close(self):
        pass


class _Chromium:
    def launch(self, headless=True):
        return _Browser()


class _Playwright:
    chromium = _Chromium()


class _Manager:
    def __enter__(self):
        return _Playwright()

    def __exit__(self, *exc):
        return False


def sync_playwright():
    return _Manager()
''' % {"fake_png": FAKE_PNG},
}


def _make_shim(directory: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return directory


def _run_visual_check(args: list[str], shim: dict[str, str] | None = None):
    with tempfile.TemporaryDirectory() as directory:
        env = os.environ.copy()
        if shim is not None:
            shim_dir = _make_shim(Path(directory) / "shim", shim)
            env["PYTHONPATH"] = str(shim_dir)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, env=env, check=False)
    return result


def _write_svg(directory: Path) -> Path:
    artifact = directory / "artifact.svg"
    artifact.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>',
        encoding="utf-8")
    return artifact


class VisualCheckSandboxFallbackTest(unittest.TestCase):
    def test_playwright_unavailable_writes_explicit_sandbox_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = _write_svg(Path(directory))
            result = _run_visual_check([str(artifact)], shim=SHIM_IMPORT_ERROR)
            self.assertEqual(2, result.returncode, result.stderr)
            receipt = json.loads(
                (Path(directory) / "artifact.svg.visual-check.json").read_text(encoding="utf-8"))
            self.assertEqual(2, receipt["schema"])
            self.assertEqual("skipped", receipt["status"])
            self.assertEqual(["sandbox blocked preview"], receipt["holds"])
            self.assertEqual("pending", receipt["visual_review"])
            self.assertFalse(Path(directory, "artifact.evidence-880.png").exists())
            self.assertFalse(Path(directory, "artifact.evidence-1300.png").exists())

    def test_chromium_launch_denied_names_sandbox_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = _write_svg(Path(directory))
            result = _run_visual_check([str(artifact)], shim=SHIM_LAUNCH_DENIED)
            self.assertEqual(2, result.returncode, result.stderr)
            receipt = json.loads(
                (Path(directory) / "artifact.svg.visual-check.json").read_text(encoding="utf-8"))
            self.assertEqual("skipped", receipt["status"])
            self.assertEqual(["sandbox blocked preview"], receipt["holds"])
            self.assertTrue(receipt["reason"].startswith("chromium launch failed"))

    def test_fallback_block_binds_scene_digests_and_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = _write_svg(Path(directory))
            result = _run_visual_check(
                [str(artifact), "--scene", str(REFERENCE_SCENE)], shim=SHIM_IMPORT_ERROR)
            self.assertEqual(2, result.returncode, result.stderr)
            receipt = json.loads(
                (Path(directory) / "artifact.svg.visual-check.json").read_text(encoding="utf-8"))
            fallback = receipt["fallback"]
            self.assertEqual(receipt["artifact"]["sha256"], fallback["artifact"]["sha256"])
            scene = fallback["scene"]
            self.assertEqual(
                hashlib.sha256(REFERENCE_SCENE.read_bytes()).hexdigest(), scene["sha256"])
            self.assertEqual(4, len(scene["extent"]))
            self.assertEqual({"exit": 0, "issues": 0}, fallback["geometry_audit"])

    def test_captured_receipt_binds_pixel_hashes(self) -> None:
        self.assertGreater(len(FAKE_PNG), 500)
        with tempfile.TemporaryDirectory() as directory:
            artifact = _write_svg(Path(directory))
            result = _run_visual_check(
                [str(artifact), "--widths", "880"], shim=SHIM_CAPTURE_OK)
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(
                (Path(directory) / "artifact.svg.visual-check.json").read_text(encoding="utf-8"))
            self.assertEqual(2, receipt["schema"])
            self.assertEqual("captured", receipt["status"])
            self.assertEqual("pending", receipt["visual_review"])
            sidecar = Path(directory) / "artifact.evidence-880.png"
            self.assertTrue(sidecar.exists())
            self.assertEqual(
                hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                receipt["captures"][0]["sha256"])

    def test_missing_artifact_is_red_and_writes_no_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.svg"
            result = _run_visual_check([str(missing)])
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertFalse((Path(directory) / "absent.svg.visual-check.json").exists())

    def test_invalid_invocation_without_artifact_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run_visual_check([])
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertEqual([], list(Path(directory).iterdir()))


class BenchmarkHoldsTest(unittest.TestCase):
    def _verify(self, run_payload: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory) / "run.json"
            run_path.write_text(json.dumps(run_payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(BENCHMARK), "verify",
                 "--case", str(CASE),
                 "--candidate", str(REFERENCE_SCENE),
                 "--run", str(run_path)],
                capture_output=True, text=True, check=False)

    def test_verify_surfaces_sandbox_hold_and_stays_unusable(self) -> None:
        result = self._verify({
            "schema_version": 1, "case_id": "layered-architecture",
            "agent": "agent-name", "model": "model-name", "attempt": 1,
            "visual_review": {"status": "skipped", "reviewer": "", "defects": [],
                              "holds": ["sandbox blocked preview"]},
        })
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(
            ["sandbox blocked preview"], receipt["gates"]["visual_review"]["holds"])
        self.assertFalse(receipt["firstPassUsable"])

    def test_verify_never_lets_a_reviewer_name_upgrade_a_skip(self) -> None:
        result = self._verify({
            "schema_version": 1, "case_id": "layered-architecture",
            "agent": "agent-name", "model": "model-name", "attempt": 1,
            "visual_review": {"status": "skipped", "reviewer": "someone", "defects": [],
                              "holds": ["sandbox blocked preview"]},
        })
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)["firstPassUsable"])

    def test_verify_records_silent_skip_as_explicit_hold(self) -> None:
        result = self._verify({
            "schema_version": 1, "case_id": "layered-architecture",
            "agent": "agent-name", "model": "model-name", "attempt": 1,
            "visual_review": {"status": "skipped"},
        })
        self.assertEqual(1, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertEqual(
            ["visual review not recorded"], receipt["gates"]["visual_review"]["holds"])
        self.assertFalse(receipt["firstPassUsable"])

    def test_report_lists_sandbox_hold(self) -> None:
        verify = self._verify({
            "schema_version": 1, "case_id": "layered-architecture",
            "agent": "agent-name", "model": "model-name", "attempt": 1,
            "visual_review": {"status": "skipped", "reviewer": "", "defects": [],
                              "holds": ["sandbox blocked preview"]},
        })
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "results.jsonl"
            results.write_text(verify.stdout.strip() + "\n", encoding="utf-8")
            report = subprocess.run(
                [sys.executable, str(BENCHMARK), "report", "--results", str(results)],
                capture_output=True, text=True, check=False)
        self.assertEqual(0, report.returncode, report.stderr)
        aggregate = json.loads(report.stdout)
        self.assertIn("sandbox blocked preview", aggregate["holds"])
        self.assertEqual(1, aggregate["failureClusters"]["visual-review"])

    def test_check_wires_reference_and_sandbox_fixtures(self) -> None:
        self.assertTrue(SANDBOX_RUN.exists())
        self.assertTrue(REFERENCE_SVG.exists())
        self.assertTrue(FALLBACK_RECEIPT.exists())
        receipt = json.loads(FALLBACK_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(2, receipt["schema"])
        self.assertEqual("skipped", receipt["status"])
        self.assertEqual(["sandbox blocked preview"], receipt["holds"])
        self.assertEqual(
            hashlib.sha256(REFERENCE_SVG.read_bytes()).hexdigest(),
            receipt["artifact"]["sha256"])
        result = subprocess.run(
            [sys.executable, str(BENCHMARK), "check"],
            capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("sandbox-blocked fixture holds explicitly", result.stdout)


if __name__ == "__main__":
    unittest.main()

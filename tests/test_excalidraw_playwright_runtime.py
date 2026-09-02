from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "excalidraw-diagram"
CHECKER = (
    SKILL_DIR / "scripts" / "check-playwright-runtime.py"
)


def write_fake_playwright(directory: Path) -> None:
    package = directory / "playwright"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "async_api.py").write_text(
        textwrap.dedent(
            """
            import os

            class _Chromium:
                executable_path = os.environ["FAKE_CHROMIUM_PATH"]

            class _Playwright:
                chromium = _Chromium()

            class _Context:
                async def __aenter__(self):
                    return _Playwright()

                async def __aexit__(self, *_args):
                    return False

            def async_playwright():
                return _Context()
            """
        ),
        encoding="utf-8",
    )
    (package / "__main__.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "Path(os.environ['FAKE_INSTALL_MARKER']).write_text('called')\n",
        encoding="utf-8",
    )


class ExcalidrawPlaywrightRuntimeTest(unittest.TestCase):
    def test_guidance_checks_runtime_before_installing_chromium(self) -> None:
        setup = (SKILL_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        renderer = (SKILL_DIR / "references" / "render_excalidraw.py").read_text(
            encoding="utf-8"
        )
        check_command = 'uv run python "$SKILL_DIR/scripts/check-playwright-runtime.py"'
        install_command = "uv run playwright install chromium"

        self.assertIn(check_command, setup)
        self.assertLess(setup.index(check_command), setup.index(install_command))
        self.assertIn("exit `2`", setup)
        self.assertIn("check-playwright-runtime.py", skill)
        self.assertNotIn(
            "Playwright Chromium is missing; run 'uv run playwright install chromium'",
            renderer,
        )

    def test_missing_chromium_exits_two_without_running_installer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            write_fake_playwright(temp)
            missing = temp / "not-installed" / "Chromium"
            marker = temp / "installer-called"
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(temp),
                    "FAKE_CHROMIUM_PATH": str(missing),
                    "FAKE_INSTALL_MARKER": str(marker),
                }
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER)],
                capture_output=True,
                env=env,
                text=True,
                check=False,
            )

            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn(f"Playwright Chromium is missing: {missing}", result.stderr)
            self.assertFalse(marker.exists(), "runtime check must never invoke the installer")

    def test_existing_chromium_exits_zero_without_running_installer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            write_fake_playwright(temp)
            executable = temp / "installed" / "Chromium"
            executable.parent.mkdir()
            executable.write_bytes(b"browser")
            marker = temp / "installer-called"
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(temp),
                    "FAKE_CHROMIUM_PATH": str(executable),
                    "FAKE_INSTALL_MARKER": str(marker),
                }
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER)],
                capture_output=True,
                env=env,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"Playwright Chromium is ready: {executable}\n",
                result.stdout,
            )
            self.assertFalse(marker.exists(), "runtime check must never invoke the installer")


if __name__ == "__main__":
    unittest.main()

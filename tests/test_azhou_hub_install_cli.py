from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from native_codex_fixture import install_fake_codex


ROOT = Path(__file__).resolve().parents[1]


class ComponentInstallCliTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve() / "project with spaces"
        self.project.mkdir()
        self.target = self.project / ".agents" / "skills"
        self.home = self.project / ".azhou" / "hub" / "targets" / "pstack"
        self.binary = install_fake_codex(self.project.parent / "codex")
        self.books = (
            ROOT / "skills/super-ask-azhou/references/book-skills.txt"
        ).read_text(encoding="utf-8").splitlines()

    def cli(self, *args: str, answer: str = "y", expected: int = 0) -> str:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/azhou_hub.py"), "install", *args],
            cwd=self.project, input=answer + "\n", capture_output=True, text=True,
            encoding="utf-8", timeout=60,
        )
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_preview_and_decline_leave_project_empty(self) -> None:
        args = ("--all", "--codex-bin", str(self.binary))
        self.assertIn("No files changed.", self.cli(*args, "--dry-run"))
        self.assertIn("Installation canceled.", self.cli(*args, answer="", expected=1))
        self.assertEqual([], list(self.project.iterdir()))

    def test_book_selection_installs_only_book_packages(self) -> None:
        self.cli("--component", "agent-rules-books")
        self.assertEqual(set(self.books), {path.name for path in self.target.iterdir() if path.name != ".azhou"})
        for name in self.books:
            source = ROOT / ".agents" / "skills" / name
            for path in source.iterdir():
                self.assertEqual(path.read_bytes(), (self.target / name / path.name).read_bytes())
        self.assertFalse(self.home.exists())

    def test_all_installs_native_plugin_and_reuses_skill_copies(self) -> None:
        args = ("--all", "--codex-bin", str(self.binary))
        report = self.cli(*args)
        self.assertIn("CODEX_HOME=", report)
        self.assertTrue((self.target / "super-ask-azhou" / "SKILL.md").is_file())
        self.assertTrue((self.target / "refactoring" / "SKILL.md").is_file())
        self.assertIn("session hook: off", (self.home / "pstack-models.md").read_text(encoding="utf-8"))
        self.assertTrue((self.home / "plugins" / "cache").is_dir())
        repeat = self.cli(*args)
        self.assertIn("super-ask-azhou: current", repeat)
        self.assertIn("refactoring: current", repeat)

    def test_foreign_pstack_target_blocks_skill_install_too(self) -> None:
        self.home.mkdir(parents=True)
        foreign = self.home / "foreign-state"
        foreign.write_text("keep", encoding="utf-8")
        result = self.cli("--all", "--codex-bin", str(self.binary), expected=1)
        self.assertIn("unowned Codex target", result)
        self.assertFalse(self.target.exists())
        self.assertEqual("keep", foreign.read_text(encoding="utf-8"))

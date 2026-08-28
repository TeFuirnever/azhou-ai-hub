from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import check_repository


ROOT = Path(__file__).resolve().parents[1]


class RuntimeStatePolicyTest(unittest.TestCase):
    def test_repository_ignores_azhou_runtime_state(self) -> None:
        self.assertIn(".azhou/", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    def test_policy_rejects_a_new_top_level_hidden_runtime_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "skills" / "sample" / "scripts" / "tool.py"
            script.parent.mkdir(parents=True)
            script.write_text('DEFAULT_STORE = ".sample-state"\n', encoding="utf-8")
            (root / ".gitignore").write_text(".azhou/\n", encoding="utf-8")

            errors = check_repository.check_runtime_state_contract([script], root)

            self.assertTrue(any("Azhou runtime state must use .azhou" in error for error in errors))

    def test_policy_accepts_a_canonical_skill_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "skills" / "sample" / "scripts" / "tool.py"
            script.parent.mkdir(parents=True)
            script.write_text('DEFAULT_STORE = ".azhou/sample"\n', encoding="utf-8")
            (root / ".gitignore").write_text(".azhou/\n", encoding="utf-8")

            self.assertEqual([], check_repository.check_runtime_state_contract([script], root))

    def test_independently_installable_packages_ship_identical_state_core(self) -> None:
        authority = (ROOT / "scripts" / "azhou_runtime_state.py").read_bytes()
        for relative in (
            "skills/llm-wiki/scripts/azhou_runtime_state.py",
            "skills/repo-pedant/scripts/azhou_runtime_state.py",
        ):
            with self.subTest(path=relative):
                self.assertEqual(authority, (ROOT / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.check_repository import check_skill_discovery, public_files


class LLMWikiRepositoryTest(unittest.TestCase):
    def test_public_files_excludes_tracked_paths_deleted_in_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / "present.md"
            present.write_text("current\n", encoding="utf-8")
            result = mock.Mock(stdout=b"present.md\0deleted.md\0")
            with mock.patch("scripts.check_repository.subprocess.run", return_value=result):
                self.assertEqual([present], public_files(root))

    def test_llm_wiki_is_a_canonical_runtime_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "skills" / "llm-wiki"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text("llm-wiki\n", encoding="utf-8")
            expected = [
                root / "skills" / "super-caveman" / "SKILL.md",
                root / "skills" / "excalidraw-diagram" / "SKILL.md",
                root / "skills" / "azhou-doctor" / "SKILL.md",
                root / "skills" / "azhou-info" / "SKILL.md",
                root / "skills" / "llm-wiki" / "SKILL.md",
                root / "skills" / "azhou-setup" / "SKILL.md",
                root / "skills" / "azhou-verify" / "SKILL.md",
                root / "skills" / "repo-pedant" / "SKILL.md",
                root / "skills" / "spec-relay" / "SKILL.md",
                root / "skills" / "lavish" / "SKILL.md",
                root / "skills" / "eli5" / "SKILL.md",
                root / "skills" / "autoresearch" / "SKILL.md",
            ]

            self.assertEqual([], check_skill_discovery(expected, root))


if __name__ == "__main__":
    unittest.main()

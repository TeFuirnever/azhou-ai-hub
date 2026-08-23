from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.check_repository import (
    check_action_pins,
    check_markdown_links,
    relative_markdown_targets,
)


class RepositoryPolicyTest(unittest.TestCase):
    def test_relative_markdown_targets_skip_remote_and_anchor_links(self) -> None:
        text = "[local](docs/run.md) [remote](https://example.com/x) [anchor](#install)"
        self.assertEqual(["docs/run.md"], relative_markdown_targets(text))

    def test_broken_markdown_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text("[missing](docs/missing.md)\n", encoding="utf-8")
            errors = check_markdown_links([readme], root)
            self.assertEqual(1, len(errors))
            self.assertIn("broken local link", errors[0])

    def test_workflow_action_requires_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            workflow = workflows / "ci.yml"
            workflow.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            errors = check_action_pins([workflow], root)
            self.assertEqual(1, len(errors))
            workflow.write_text(
                "steps:\n  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n",
                encoding="utf-8",
            )
            self.assertEqual([], check_action_pins([workflow], root))


if __name__ == "__main__":
    unittest.main()

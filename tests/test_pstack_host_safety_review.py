"""Portable pstack safeguards prompted by PR #372 security review.

The generated distribution is the installable product. Pinned upstream
sources are kept byte-for-byte so these tests check the downstream overrides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "pstack-agent-harness"
HARNESS = PACKAGE / "harness" / "pstack"


class PstackHostSafetyReviewTest(unittest.TestCase):
    def test_untracked_worktree_files_block_automatic_cleanup_in_all_hosts(self) -> None:
        pristine = (PACKAGE / "pstack/skills/poteto-mode/playbooks/worktree-cleanup.md").read_text()
        override = (PACKAGE / "hub-skills/poteto-mode/playbooks/worktree-cleanup.md").read_text()
        self.assertIn("is untracked throwaway, safe to drop", pristine)
        self.assertNotIn("scratch:N is untracked throwaway", override)
        for guard in ("UNKNOWN ownership", "explicit approval", "Treehouse lease",
                      "Never run git worktree remove --force", "ignored files",
                      "each file has an explicit disposition"):
            self.assertIn(guard, override)
        for host in ("claude-code", "codex", "zcode", "skills-root"):
            with self.subTest(host=host):
                path = HARNESS / host / "skills/poteto-mode/playbooks/worktree-cleanup.md"
                self.assertEqual(override.encode(), path.read_bytes())

    def test_claude_setup_instructions_align_with_config_root_hook(self) -> None:
        key = "@@{CLAUDE_CONFIG_DIR:-@@HOME/.claude}/pstack-models.md".replace("@@", chr(36))
        adapter = (HARNESS / "claude-code/docs/harness/claude-code.md").read_text()
        readme = (HARNESS / "claude-code/README.md").read_text()
        hook = (HARNESS / "claude-code/hooks/session-start.sh").read_text()
        self.assertIn(key, adapter)
        self.assertIn(key, readme)
        self.assertIn(key, hook)
        self.assertNotIn("~/.claude/rules/pstack-models.md", adapter)
        self.assertNotIn("~/.claude/rules/pstack-models.md", readme)
        self.assertEqual(len([line for line in (PACKAGE / "patches/series").read_text().splitlines() if line.strip() and not line.startswith("#")]), 24)

    @unittest.skipUnless(os.name == "posix" and shutil.which("git") and
                         Path("/bin/bash").is_file(), "POSIX Git worktree audit")
    def test_actual_audit_never_marks_untracked_or_ignored_tree_safe(self) -> None:
        script = HARNESS / "codex/skills/poteto-mode/scripts/worktree-audit.sh"
        with tempfile.TemporaryDirectory(prefix="pstack-audit-safe-") as name:
            root = Path(name)
            repo = root / "repo"
            repo.mkdir()
            def git(*args: str) -> subprocess.CompletedProcess:
                return subprocess.run(["git", *args], cwd=repo,
                                      capture_output=True, text=True,
                                      encoding="utf-8", timeout=18, check=True)
            git("init", "-q")
            git("branch", "-M", "main")
            (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git("add", ".gitignore", "README.md")
            git("-c", "user.email=fixture@localhost", "-c",
                "user.name=Fixture", "commit", "-qm", "baseline")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@localhost")
            git("config", "status.showUntrackedFiles", "no")
            trees = {key: root / ("spaced tree" if key == "spaced" else key)
                     for key in ("untracked", "ignored", "clean", "spaced",
                                 "broken", "pending", "topic")}
            for key, location in trees.items():
                git("worktree", "add", "-q", "-b", key, str(location), "main")
            new_source = trees["untracked"] / "new-user-source.py"
            new_source.write_text("new user source\n", encoding="utf-8")
            ignored = trees["ignored"] / "build" / "artifact.dat"
            ignored.parent.mkdir()
            ignored.write_text("private ignored data\n", encoding="utf-8")
            spaced_source = trees["spaced"] / "new source.py"
            spaced_source.write_text("preserve spaced path\n", encoding="utf-8")
            topic_file = trees["topic"] / "committed.txt"
            topic_file.write_text("unmerged topic commit\n", encoding="utf-8")
            git("-C", str(trees["topic"]), "add", "committed.txt")
            git("-C", str(trees["topic"]), "commit", "-qm", "unmerged topic")
            git("worktree", "add", "-q", "-b", "merge-source", str(root / "merge-source"), "main")
            git("-C", str(root / "merge-source"), "commit", "--allow-empty",
                "-qm", "synthetic source for pending merge")
            pending = git("-C", str(trees["pending"]), "merge",
                          "--no-commit", "--no-ff", "merge-source")
            self.assertEqual(pending.returncode, 0)
            idx = git("-C", str(trees["broken"]), "rev-parse", "--git-path", "index")
            index_path = Path(idx.stdout.strip())
            self.assertTrue(index_path.is_absolute())
            self.assertTrue(index_path.is_file())
            index_path.write_bytes(b"corrupt synthetic index\n")
            badstatus = subprocess.run(["git", "-C", str(trees["broken"]), "status",
                                        "--porcelain"], cwd=repo,
                                       capture_output=True, text=True,
                                       encoding="utf-8", timeout=12)
            self.assertNotEqual(badstatus.returncode, 0)
            binpath = root / "bin"
            binpath.mkdir()
            gh_json = json.dumps([dict(number=1, state="CLOSED", headRefName="topic")])
            gh_script = '#!/bin/sh\ncat <<EOF\n' + gh_json + '\nEOF\n'
            for executable, source in (("origin", "#!/bin/sh\nexit 1\n"),
                                       ("gh", gh_script)):
                stub = binpath / executable
                stub.write_text(source, encoding="utf-8")
                stub.chmod(0o700)
            env = dict(os.environ)
            env.update({"HOME": str(root), "PATH": str(binpath) + os.pathsep +
                        env.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0"})
            command = subprocess.run(["/bin/bash", str(script), "-b", "main",
                                      str(repo)], cwd=repo, env=env,
                                     capture_output=True, text=True,
                                     encoding="utf-8", timeout=35)
            self.assertEqual(command.returncode, 0, command.stderr)
            rows = [line.split("\t") for line in command.stdout.splitlines()
                    if "\t" in line]
            self.assertGreaterEqual(len(rows), 8, command.stdout)
            headings = rows[0]
            observed = {Path(row["WORKTREE"]).resolve(): row
                        for row in (dict(zip(headings, fields)) for fields in rows[1:])}
            self.assertEqual(observed[trees["untracked"].resolve()]["BUCKET"],
                             "hold-untracked")
            self.assertTrue(observed[trees["untracked"].resolve()]["DIRTY"].startswith(
                "scratch:"))
            self.assertEqual(observed[trees["ignored"].resolve()]["BUCKET"],
                             "hold-ignored")
            self.assertEqual(observed[trees["clean"].resolve()]["BUCKET"], "safe")
            self.assertEqual(observed[trees["spaced"].resolve()]["BUCKET"],
                             "hold-untracked")
            self.assertEqual(observed[trees["broken"].resolve()]["BUCKET"], "review")
            self.assertEqual(observed[trees["broken"].resolve()]["DIRTY"], "unknown")
            self.assertEqual(observed[trees["pending"].resolve()]["BUCKET"],
                             "hold-operation")
            self.assertEqual(observed[trees["topic"].resolve()]["MERGED"], "no")
            self.assertEqual(observed[trees["topic"].resolve()]["PR"], "#1/closed")
            self.assertEqual(observed[trees["topic"].resolve()]["BUCKET"], "review")
            self.assertEqual(new_source.read_text(encoding="utf-8"), "new user source\n")
            self.assertEqual(ignored.read_text(encoding="utf-8"),
                             "private ignored data\n")
            self.assertEqual(spaced_source.read_text(encoding="utf-8"),
                             "preserve spaced path\n")
            self.assertEqual(topic_file.read_text(encoding="utf-8"),
                             "unmerged topic commit\n")

    @unittest.skipUnless(os.name == "posix" and Path("/bin/sh").is_file(),
                         "native POSIX shell hook fixture")
    def test_claude_hook_only_honors_config_root_sheet(self) -> None:
        plugin = HARNESS / "claude-code"
        hook = plugin / "hooks/session-start.sh"
        with tempfile.TemporaryDirectory(prefix="pstack-hook-alignment-") as name:
            folder = Path(name)
            active = folder / "custom-claude-home"
            rules = active / "rules"
            rules.mkdir(parents=True)
            (rules / "pstack-models.md").write_text("session hook: off\n")
            env = dict(os.environ)
            env.update({"HOME": str(folder), "CLAUDE_CONFIG_DIR": str(active),
                        "CLAUDE_PLUGIN_ROOT": str(plugin)})
            def invoke() -> subprocess.CompletedProcess:
                return subprocess.run(["/bin/sh", str(hook), "claude"],
                                      cwd=folder, env=env, capture_output=True,
                                      text=True, encoding="utf-8", timeout=12)
            # Wrong rules-directory sheet must not accidentally disable injection.
            wrong = invoke()
            self.assertEqual(wrong.returncode, 0, wrong.stderr)
            self.assertIn("poteto", wrong.stdout.lower())
            (active / "pstack-models.md").write_text("session hook: off\n")
            correct = invoke()
            self.assertEqual(correct.returncode, 0, correct.stderr)
            self.assertEqual(correct.stdout, "")
            (active / "pstack-models.md").write_text("session hook: on\n")
            enabled = invoke()
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            self.assertIn("poteto", enabled.stdout.lower())


if __name__ == "__main__":
    unittest.main()

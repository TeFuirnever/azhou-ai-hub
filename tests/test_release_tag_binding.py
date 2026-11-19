"""Exercise the draft workflow commands with a local Git server and fake gh."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "draft workflows run on Ubuntu")
class DraftReleaseTest(unittest.TestCase):
    tag = "v1.2.3"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.remote = self.root / "owner" / "repo.git"
        self.remote.parent.mkdir()
        self.record = self.root / "gh-calls.jsonl"
        self.git("init", "-q", "--bare", str(self.remote))
        tree = self.git("mktree", data="")
        self.expected = self.git("commit-tree", tree, "-m", "verified candidate")
        self.other = self.git("commit-tree", tree, "-m", "other candidate")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(
            f"#!{sys.executable}\n" + textwrap.dedent("""\
                import json, os, subprocess, sys
                args = sys.argv[1:]
                if args[:2] == ["api", "--include"]:
                    print("HTTP/2 404")
                    sys.exit(1)
                assert args[:2] == ["release", "create"], args
                with open(os.environ["CALL_RECORD"], "a") as file:
                    print(json.dumps(args), file=file)
                if os.environ.get("DRAFT_RACE_SHA"):
                    subprocess.run(["git", "--git-dir", os.environ["DRAFT_REMOTE"], "update-ref",
                                    "refs/tags/" + os.environ["RELEASE_TAG"], os.environ["DRAFT_RACE_SHA"]],
                                   check=True)
                if os.environ.get("DRAFT_QUERY_FAILURE"):
                    remote = os.environ["DRAFT_REMOTE"]
                    os.rename(remote, remote + ".unavailable")
                """),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SERVER_URL": str(self.root),
            "GITHUB_SHA": self.expected,
            "RELEASE_TAG": self.tag,
            "TAG": self.tag,
            "RUNNER_TEMP": str(self.root),
            "CALL_RECORD": str(self.record),
            "DRAFT_REMOTE": str(self.remote),
        }

    def git(self, *args, data=None):
        return subprocess.check_output(
            ["git", "--git-dir", str(self.remote), "-c", "user.name=Fixture",
             "-c", "user.email=fixture@example.invalid", "-c", "tag.gpgsign=false",
             "-c", "commit.gpgsign=false", *args],
            input=data, text=True, encoding="utf-8",
        ).strip()

    def run_workflow(self, workflow="release", **environment):
        path = ROOT / ".github" / "workflows" / f"{workflow}.yml"
        name = ("Validate tag and create draft" if workflow == "release"
                else "Attach the signed manifest to a draft release")
        step = path.read_text(encoding="utf-8").split(f"- name: {name}\n", 1)[1]
        script = re.search(r"^        run: \|\n((?:^          .*\n)+)", step, re.M)
        self.assertIsNotNone(script)
        return subprocess.run(
            ["bash", "-e", "-c", textwrap.dedent(script[1])],
            cwd=ROOT, env={**self.env, **environment}, capture_output=True, text=True, encoding="utf-8",
        )

    def args(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()] if self.record.exists() else []

    def test_missing_tag_uses_verified_commit_and_stays_draft(self):
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.args()
        self.assertIn("--draft", args)
        self.assertEqual(args[args.index("--target") + 1], self.expected)
        self.assertNotIn("--verify-tag", args)
        self.assertEqual("", self.git("tag", "-l"))

    def test_existing_annotated_tag_uses_peeled_commit(self):
        self.git("tag", "-a", self.tag, self.expected, "-m", "annotated tag")
        self.assertNotEqual(self.git("rev-parse", self.tag), self.expected)
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.args()
        self.assertIn("--verify-tag", args)

    def test_both_workflows_reject_mismatched_existing_tag_before_create(self):
        self.git("tag", self.tag, self.other)
        for workflow in ("release", "signed-release-rehearsal"):
            with self.subTest(workflow=workflow):
                result = self.run_workflow(workflow)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(self.other, result.stderr)
                self.assertEqual([], self.args())
        self.assertEqual(self.other, self.git("rev-parse", self.tag))

    def test_rehearsal_keeps_signed_assets_and_never_publishes(self):
        result = self.run_workflow("signed-release-rehearsal")
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.args()
        self.assertIn("--draft", args)
        self.assertEqual(args[args.index("--target") + 1], self.expected)
        self.assertEqual(args[-2:], ["SKILL_SHA256SUMS.txt", "SKILL_SHA256SUMS.txt.sigstore"])

    def test_query_failure_is_not_treated_as_missing(self):
        result = self.run_workflow(GITHUB_SERVER_URL=str(self.root / "unavailable"))
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual([], self.args())

    def test_query_failure_after_draft_is_not_reported_as_success(self):
        result = self.run_workflow(DRAFT_QUERY_FAILURE="1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unpublished", result.stderr)
        self.assertEqual(1, len(self.args()))

    def test_conflicting_tag_created_during_draft_is_not_accepted_or_moved(self):
        result = self.run_workflow(DRAFT_RACE_SHA=self.other)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unpublished", result.stderr)
        self.assertEqual(1, len(self.args()))
        self.assertEqual(self.other, self.git("rev-parse", self.tag))


if __name__ == "__main__":
    unittest.main()

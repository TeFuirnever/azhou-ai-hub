from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "llm-wiki" / "scripts" / "llm_wiki.py"
SPEC = importlib.util.spec_from_file_location("llm_wiki", SCRIPT)
assert SPEC and SPEC.loader
llm_wiki = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = llm_wiki
SPEC.loader.exec_module(llm_wiki)


class LlmWikiTest(unittest.TestCase):
    def run_cli(
        self,
        root: Path,
        *arguments: str,
        input_text: str | None = None,
        expected_code: int = 0,
    ) -> dict:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(expected_code, completed.returncode, completed.stderr or completed.stdout)
        return json.loads(completed.stdout)

    def test_seven_operations_and_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = self.run_cli(root, "init")
            self.assertEqual("llm-wiki.receipt.v2", initialized["schema"])
            self.assertEqual(
                {
                    "schema",
                    "status",
                    "operation",
                    "store",
                    "currentTruth",
                    "result",
                    "changes",
                    "verification",
                    "holds",
                    "nextAction",
                    "learningSignal",
                },
                set(initialized),
            )
            self.assertEqual("none", initialized["learningSignal"])
            self.assertTrue((root / ".llm-wiki" / ".gitignore").is_file())

            added = self.run_cli(
                root,
                "add",
                "--title",
                "Auth Decision",
                "--content",
                "Use signed cookies.",
                "--tag",
                "auth",
                "--category",
                "decision",
                "--source",
                "issue-42",
                "--confidence",
                "high",
            )
            self.assertEqual("created", added["result"]["action"])

            ingested = self.run_cli(
                root,
                "ingest",
                "--title",
                "Auth Decision",
                "--content",
                "Rotate keys quarterly and link [[Key Rotation]].",
                "--tag",
                "security",
                "--category",
                "decision",
                "--source",
                "review-7",
                "--confidence",
                "medium",
            )
            self.assertEqual("updated", ingested["result"]["action"])

            queried = self.run_cli(root, "query", "rotate", "--no-log")
            self.assertEqual(1, queried["result"]["count"])
            self.assertEqual([], queried["changes"])

            listed = self.run_cli(root, "list")
            self.assertEqual(1, listed["result"]["count"])
            filename = listed["result"]["pages"][0]["filename"]
            read = self.run_cli(root, "read", filename)
            self.assertIn("## Update", read["result"]["content"])
            self.assertEqual(["issue-42", "review-7"], read["result"]["sources"])
            self.assertEqual("high", read["result"]["confidence"])

            linted = self.run_cli(root, "lint", "--no-log", expected_code=1)
            self.assertEqual("fail", linted["status"])
            self.assertEqual(1, linted["result"]["stats"]["brokenRefCount"])

            held = self.run_cli(root, "delete", filename, expected_code=3)
            self.assertEqual("hold", held["status"])
            deleted = self.run_cli(root, "delete", filename, "--yes")
            self.assertEqual("pass", deleted["status"])
            self.assertEqual(0, self.run_cli(root, "list")["result"]["count"])

    def test_cjk_slug_and_bigram_query_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            added = self.run_cli(
                root,
                "add",
                "--title",
                "认证架构",
                "--content",
                "登录令牌使用短期签名。",
                "--category",
                "architecture",
            )
            filename = added["result"]["page"]["filename"]
            self.assertRegex(filename, r"^page-[0-9a-f]{8}\.md$")
            results = self.run_cli(root, "query", "登录令牌", "--no-log")
            self.assertEqual(filename, results["result"]["matches"][0]["filename"])
            self.assertEqual("page-001b0d63.md", llm_wiki.title_to_slug("😀"))

    def test_frontmatter_round_trip_handles_crlf_quotes_and_newlines(self) -> None:
        page = llm_wiki.Page(
            filename="quoted.md",
            title='A "quoted"\nname',
            tags=["line\nbreak", 'quote"tag'],
            created="2026-08-23T00:00:00Z",
            updated="2026-08-23T00:00:00Z",
            sources=["source\\path"],
            links=[],
            category="reference",
            confidence="medium",
            schema_version=1,
            content="\n# Body\n",
        )
        raw = llm_wiki.serialize_page(page).replace("\n", "\r\n")
        parsed = llm_wiki.parse_frontmatter(raw, page.filename)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(page.title, parsed.title)
        self.assertEqual(page.tags, parsed.tags)
        self.assertEqual(page.sources, parsed.sources)

    def test_store_and_page_paths_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(llm_wiki.WikiError):
                llm_wiki.WikiStore(root, "../escape")
            store = llm_wiki.WikiStore(root)
            for value in ("../secret.md", "nested/page.md", "index.md", ".hidden.md"):
                with self.assertRaises(llm_wiki.WikiError, msg=value):
                    store.safe_filename(value)

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "symlinks unavailable")
    def test_page_reads_and_internal_logs_reject_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wiki = root / ".llm-wiki"
            wiki.mkdir()
            outside = root / "outside.md"
            outside.write_text("secret\n", encoding="utf-8")
            try:
                (wiki / "linked.md").symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation unavailable")
            store = llm_wiki.WikiStore(root)
            self.assertEqual([], store.page_filenames())
            self.assertIsNone(store.read_page("linked.md"))
            (wiki / "log.md").symlink_to(outside)
            with self.assertRaises(llm_wiki.WikiError):
                store.log("query", [], "no leak")

    def test_invalid_frontmatter_is_a_lint_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / ".llm-wiki"
            store.mkdir()
            broken = store / "broken.md"
            broken.write_text("not frontmatter\n", encoding="utf-8")
            result = self.run_cli(root, "lint", "--no-log", expected_code=1)
            self.assertEqual(1, result["result"]["stats"]["invalidPageCount"])
            update = self.run_cli(
                root,
                "ingest",
                "--title",
                "Broken",
                "--content",
                "must not replace unknown data",
                expected_code=2,
            )
            self.assertEqual("fail", update["status"])
            self.assertEqual("not frontmatter\n", broken.read_text(encoding="utf-8"))

    def test_prior_store_requires_explicit_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = llm_wiki.WikiStore(root, ".prior-wiki")
            source.add(
                title="Prior Page",
                content="Source remains intact.",
                tags=[],
                category="reference",
                sources=[],
                confidence="medium",
            )
            planned = self.run_cli(root, "migrate", "--from-store", ".prior-wiki")
            self.assertEqual("planned", planned["result"]["status"])
            self.assertFalse((root / ".llm-wiki").exists())
            applied = self.run_cli(root, "migrate", "--from-store", ".prior-wiki", "--apply")
            self.assertEqual("migrated", applied["result"]["status"])
            self.assertTrue((source.directory / "prior-page.md").is_file())
            result = self.run_cli(root, "list")
            self.assertEqual(1, result["result"]["count"])

    def test_session_end_capture_is_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = json.dumps({"cwd": str(root), "session_id": "session-123"})
            skipped = self.run_cli(root, "hook", "session-end", input_text=event)
            self.assertEqual("skipped", skipped["status"])
            self.assertFalse((root / ".llm-wiki").exists())

            configured = self.run_cli(root, "config", "--auto-capture", "true")
            self.assertTrue(configured["result"]["autoCapture"])
            captured = self.run_cli(root, "hook", "session-end", input_text=event)
            self.assertEqual("pass", captured["status"])
            self.assertEqual(1, self.run_cli(root, "list", "--category", "session-log")["result"]["count"])
            page = next((root / ".llm-wiki").glob("session-log-*.md"))
            self.assertNotIn("session-123", page.read_text(encoding="utf-8"))

    def test_context_hook_is_bounded_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli(root, "add", "--title", "One", "--content", "First fact.")
            log = root / ".llm-wiki" / "log.md"
            before = log.read_bytes()
            event = json.dumps({"cwd": str(root)})
            result = self.run_cli(root, "hook", "session-start", "--limit", "4", input_text=event)
            context = result["result"]["additionalContext"]
            self.assertIn("[LLM Wiki: 1 pages", context)
            self.assertLessEqual(len(context.splitlines()), 8)
            self.assertEqual(before, log.read_bytes())

    def test_environment_capture_records_source_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "environment.json"
            snapshot.write_text('{"runtime":"python","version":"3.11"}\n', encoding="utf-8")
            result = self.run_cli(root, "capture-environment", "--input", str(snapshot))
            self.assertRegex(result["result"]["sourceDigest"], r"^[0-9a-f]{64}$")
            page = self.run_cli(root, "read", "Project Environment Snapshot")
            self.assertIn("sha256:", " ".join(page["result"]["sources"]))


if __name__ == "__main__":
    unittest.main()

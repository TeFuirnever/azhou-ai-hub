from __future__ import annotations

import importlib.util
import hashlib
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
MCP_SPEC = importlib.util.spec_from_file_location("llm_wiki_mcp", SCRIPT.with_name("llm_wiki_mcp.py"))
assert MCP_SPEC and MCP_SPEC.loader
llm_wiki_mcp = importlib.util.module_from_spec(MCP_SPEC)
sys.modules[MCP_SPEC.name] = llm_wiki_mcp
MCP_SPEC.loader.exec_module(llm_wiki_mcp)


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
            self.assertTrue((root / ".azhou" / "llm-wiki" / ".gitignore").is_file())

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
            wiki = root / ".azhou" / "llm-wiki"
            wiki.parent.mkdir()
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
            store = root / ".azhou" / "llm-wiki"
            store.mkdir(parents=True)
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
            source = llm_wiki.WikiStore(root, ".llm-wiki")
            source.add(
                title="Prior Page",
                content="Source remains intact.",
                tags=[],
                category="reference",
                sources=[],
                confidence="medium",
            )
            planned = self.run_cli(root, "migrate", "--from-store", ".llm-wiki")
            self.assertEqual("planned", planned["result"]["status"])
            self.assertFalse((root / ".azhou" / "llm-wiki").exists())
            applied = self.run_cli(
                root,
                "migrate",
                "--from-store",
                ".llm-wiki",
                "--apply",
                "--plan-id",
                planned["result"]["planId"],
            )
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
            self.assertFalse((root / ".azhou" / "llm-wiki").exists())

            configured = self.run_cli(root, "config", "--auto-capture", "true")
            self.assertTrue(configured["result"]["autoCapture"])
            captured = self.run_cli(root, "hook", "session-end", input_text=event)
            self.assertEqual("pass", captured["status"])
            self.assertEqual(1, self.run_cli(root, "list", "--category", "session-log")["result"]["count"])
            page = next((root / ".azhou" / "llm-wiki").glob("session-log-*.md"))
            self.assertNotIn("session-123", page.read_text(encoding="utf-8"))

    def test_title_resolution_is_collision_safe_and_preserves_compatibility_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = "A B"
            second = "a-b"
            self.run_cli(root, "add", "--title", first, "--content", "first")
            ingested = self.run_cli(root, "ingest", "--title", second, "--content", "second")
            self.assertRegex(ingested["result"]["page"]["filename"], r"^a-b-v2-[0-9a-f]{16}\.md$")
            self.assertEqual(2, self.run_cli(root, "list")["result"]["count"])

            long_first = "x" * 64 + " one"
            long_second = "x" * 64 + " two"
            self.run_cli(root, "add", "--title", long_first, "--content", "long one")
            second_page = self.run_cli(root, "add", "--title", long_second, "--content", "long two")
            self.assertRegex(second_page["result"]["page"]["filename"], r"^x{40}-v2-[0-9a-f]{16}\.md$")

    def test_invalid_config_is_rejected_without_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / ".azhou" / "llm-wiki" / "config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"autoCapture":"false","staleDays":true}\n', encoding="utf-8")
            result = self.run_cli(root, "hook", "session-end", input_text=json.dumps({"cwd": str(root)}), expected_code=2)
            self.assertEqual("config", result["learningSignal"])
            self.assertEqual([], list(config.parent.glob("session-log-*.md")))

    def test_config_invalid_boolean_variants_and_mcp_lint_fields(self) -> None:
        for value in ("true", 0):
            with self.subTest(autoCapture=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                store = llm_wiki.WikiStore(root)
                store.ensure()
                (store.directory / "config.json").write_text(json.dumps({"autoCapture": value}), encoding="utf-8")
                with self.assertRaises(llm_wiki.WikiConfigError):
                    store.config()
        for field in ("staleDays", "maxPageSize"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                store = llm_wiki.WikiStore(root)
                store.ensure()
                (store.directory / "config.json").write_text(json.dumps({field: "invalid"}), encoding="utf-8")
                before = {name: (store.directory / name).exists() for name in ("index.md", "log.md")}
                result = llm_wiki_mcp.call_tool("wiki_lint", {"workingDirectory": str(root)})
                self.assertTrue(result["isError"])
                self.assertEqual(before, {name: (store.directory / name).exists() for name in ("index.md", "log.md")})

    def test_title_resolver_reuses_compatibility_and_rejects_ambiguous_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            title = "z" * 70 + " compatibility"
            compatibility_name = f"{'z' * 64}.md"
            timestamp = llm_wiki.now_iso()
            store.ensure()
            store.write_page_unsafe(llm_wiki.Page(
                filename=compatibility_name, title=title, tags=[], created=timestamp, updated=timestamp,
                sources=[], links=[], category="reference", confidence="medium", schema_version=1,
                content="\n# compatibility\n",
            ))
            page, action = store.ingest(title=title, content="reused", tags=[], category="reference", sources=[], confidence="medium")
            self.assertEqual(compatibility_name, page.filename)
            self.assertEqual("updated", action)

            v2 = llm_wiki.v2_title_slug("Deleted Base")
            store.write_page_unsafe(llm_wiki.Page(
                filename=v2, title="Deleted Base", tags=[], created=timestamp, updated=timestamp,
                sources=[], links=[], category="reference", confidence="medium", schema_version=1,
                content="\n# v2\n",
            ))
            self.assertEqual(v2, store.resolve_title("Deleted Base")[0])
            duplicate = llm_wiki.title_to_slug("Duplicate")
            store.write_page_unsafe(llm_wiki.Page(
                filename=duplicate, title="Duplicate", tags=[], created=timestamp, updated=timestamp,
                sources=[], links=[], category="reference", confidence="medium", schema_version=1,
                content="\n# duplicate\n",
            ))
            duplicate_v2 = llm_wiki.v2_title_slug("Duplicate")
            store.write_page_unsafe(llm_wiki.Page(
                filename=duplicate_v2, title="Duplicate", tags=[], created=timestamp, updated=timestamp,
                sources=[], links=[], category="reference", confidence="medium", schema_version=1,
                content="\n# duplicate v2\n",
            ))
            with self.assertRaises(llm_wiki.WikiError):
                store.resolve_title("Duplicate")

    def test_collision_pages_and_exact_reingest_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            first, _ = store.ingest(title="A B", content="first body", tags=[], category="reference", sources=[], confidence="medium")
            second, _ = store.ingest(title="a-b", content="second body", tags=[], category="decision", sources=[], confidence="high")
            pages = {page.title: page for page in store.pages()}
            self.assertEqual((first.filename, "first body", "reference"), (pages["A B"].filename, pages["A B"].content.splitlines()[-1], pages["A B"].category))
            self.assertEqual((second.filename, "second body", "decision"), (pages["a-b"].filename, pages["a-b"].content.splitlines()[-1], pages["a-b"].category))
            self.assertNotEqual(first.filename, second.filename)
            self.assertEqual(first.filename, store.ingest(title="A B", content="first update", tags=[], category="architecture", sources=[], confidence="low")[0].filename)
            self.assertEqual(second.filename, store.ingest(title="a-b", content="second update", tags=[], category="pattern", sources=[], confidence="low")[0].filename)
            self.assertEqual(first.filename, store.resolve_title("A B")[0])
            self.assertEqual(second.filename, store.resolve_title("a-b")[0])
            exact_read = self.run_cli(root, "read", "a-b")
            filename_read = self.run_cli(root, "read", first.filename)
            self.assertEqual("a-b", exact_read["result"]["title"])
            self.assertEqual("A B", filename_read["result"]["title"])

    def test_invalid_utf8_candidate_fails_closed_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            store.ensure()
            filename = llm_wiki.title_to_slug("Invalid UTF")
            candidate = store.directory / filename
            candidate.write_bytes(b"\xff\xfe\x00")
            result = self.run_cli(
                root,
                "add",
                "--title",
                "Invalid UTF",
                "--content",
                "must not overwrite",
                expected_code=2,
            )
            self.assertEqual("fail", result["status"])
            self.assertEqual(b"\xff\xfe\x00", candidate.read_bytes())

    def test_collision_conflicts_and_ambiguity_fail_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            title = "r" * 70 + " target"
            truncated = f"{'r' * 64}.md"
            stamp = llm_wiki.now_iso()
            store.ensure()
            def page(filename: str, stored_title: str, body: str) -> llm_wiki.Page:
                return llm_wiki.Page(filename=filename, title=stored_title, tags=[], created=stamp, updated=stamp, sources=[], links=[], category="reference", confidence="medium", schema_version=1, content=f"\n# {body}\n")
            store.write_page_unsafe(page(truncated, "other title", "other"))
            before = (store.directory / truncated).read_bytes()
            created, _ = store.ingest(title=title, content="new v2", tags=[], category="decision", sources=[], confidence="high")
            self.assertNotEqual(truncated, created.filename)
            self.assertEqual(before, (store.directory / truncated).read_bytes())

            conflict_title = "Conflict Target"
            conflict_v2 = llm_wiki.v2_title_slug(conflict_title)
            store.write_page_unsafe(page(conflict_v2, "Owned By Other", "owned"))
            snapshots = {
                name: (store.directory / name).read_bytes()
                for name in ("index.md", "log.md", conflict_v2)
            }
            with self.assertRaises(llm_wiki.WikiError):
                store.ingest(title=conflict_title, content="must fail", tags=[], category="reference", sources=[], confidence="medium")
            self.assertEqual(snapshots, {name: (store.directory / name).read_bytes() for name in snapshots})

            ambiguous = "Ambiguous"
            base = llm_wiki.title_to_slug(ambiguous)
            store.write_page_unsafe(page(base, ambiguous, "base"))
            store.write_page_unsafe(page(llm_wiki.v2_title_slug(ambiguous), ambiguous, "v2"))
            snapshots = {name: (store.directory / name).read_bytes() for name in ("index.md", "log.md", base, llm_wiki.v2_title_slug(ambiguous))}
            for operation in ("ingest", "add"):
                with self.subTest(operation=operation), self.assertRaises(llm_wiki.WikiError):
                    getattr(store, operation)(title=ambiguous, content="must fail", tags=[], category="reference", sources=[], confidence="medium")
                self.assertEqual(snapshots, {name: (store.directory / name).read_bytes() for name in snapshots})

    def test_deleted_base_reuses_exact_v2_and_compatibility_long_link_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            title = "s" * 70 + " target"
            stamp = llm_wiki.now_iso()
            base = f"{'s' * 64}.md"
            v2_name = llm_wiki.v2_title_slug(title)
            store.ensure()
            base_page = llm_wiki.Page(filename=base, title=title, tags=[], created=stamp, updated=stamp, sources=[], links=[], category="reference", confidence="medium", schema_version=1, content="\n# base\n")
            v2_page = llm_wiki.Page(filename=v2_name, title=title, tags=[], created=stamp, updated=stamp, sources=[], links=[], category="reference", confidence="medium", schema_version=1, content="\n# v2\n")
            store.write_page_unsafe(base_page)
            store.write_page_unsafe(v2_page)
            self.assertTrue(store.delete(base))
            v2 = v2_page
            store.write_page_unsafe(v2)
            page, action = store.ingest(title=title, content="reused v2", tags=[], category="decision", sources=[], confidence="high")
            self.assertEqual((v2.filename, "updated"), (page.filename, action))
            compatibility_title = "t" * 70 + " link target"
            compatibility_name = f"{'t' * 64}.md"
            stamp = llm_wiki.now_iso()
            store.write_page_unsafe(llm_wiki.Page(filename=compatibility_name, title=compatibility_title, tags=[], created=stamp, updated=stamp, sources=[], links=[], category="reference", confidence="medium", schema_version=1, content="\n# compatibility target\n"))
            linker, _ = store.ingest(title="Compatibility Linker", content=f"See [[{compatibility_title}]].", tags=[], category="reference", sources=[], confidence="medium")
            self.assertIn(compatibility_name, store.read_page(linker.filename).links)
            report = llm_wiki.lint_store(store, stale_days=30, max_page_size=10_240, log=False)
            self.assertEqual(0, report["stats"]["brokenRefCount"])

    def test_long_wiki_links_resolve_without_false_broken_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            title = "q" * 70 + " target"
            target, _ = store.ingest(title=title, content="target", tags=[], category="reference", sources=[], confidence="medium")
            self.assertEqual(
                f"{'q' * 40}-v2-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:16]}.md",
                target.filename,
            )
            store.add(title="Linker", content=f"See [[{title}]].", tags=[], category="reference", sources=[], confidence="medium")
            report = llm_wiki.lint_store(store, stale_days=30, max_page_size=10_240, log=False)
            self.assertEqual(0, report["stats"]["brokenRefCount"])

    def test_v2_slug_uses_page_prefix_for_empty_normalized_stem(self) -> None:
        title = "知识🧭"
        expected = f"page-v2-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:16]}.md"
        self.assertEqual(expected, llm_wiki.v2_title_slug(title))

    def test_context_hook_is_bounded_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli(root, "add", "--title", "One", "--content", "First fact.")
            log = root / ".azhou" / "llm-wiki" / "log.md"
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

    def test_render_hooks_matchers_are_valid_regular_expressions(self) -> None:
        # Regression for a real wiring failure: a bare "*" matcher is not a
        # valid regular expression ("nothing to repeat") and made the
        # consuming runtime report a hook-loading issue.
        import re

        adapter_spec = importlib.util.spec_from_file_location(
            "llm_wiki_adapter", SCRIPT.with_name("llm_wiki_adapter.py")
        )
        assert adapter_spec and adapter_spec.loader
        adapter = importlib.util.module_from_spec(adapter_spec)
        sys.modules[adapter_spec.name] = adapter
        adapter_spec.loader.exec_module(adapter)
        with tempfile.TemporaryDirectory() as directory:
            wiring = adapter.render_hooks(Path(directory), Path(sys.executable))
        events = wiring["hooks"]
        self.assertEqual(sorted(events), ["PreCompact", "SessionEnd", "SessionStart"])
        canonical = {"SessionStart": "session-start", "PreCompact": "pre-compact", "SessionEnd": "session-end"}
        for event, entries in events.items():
            for entry in entries:
                matcher = entry["matcher"]
                self.assertEqual(matcher, ".*", f"{event} matcher must be a valid match-all regex")
                re.compile(matcher)  # must not raise
                for hook in entry["hooks"]:
                    self.assertIn("host-hook", hook["command"])
                    self.assertTrue(hook["command"].endswith(canonical[event]))
                    self.assertLessEqual(hook["timeout"], 5)
                    if event == "SessionEnd":
                        self.assertLessEqual(hook["timeout"], 3)


if __name__ == "__main__":
    unittest.main()

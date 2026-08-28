from __future__ import annotations

import io
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "llm-wiki"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import llm_wiki  # noqa: E402
import llm_wiki_adapter  # noqa: E402
import llm_wiki_mcp  # noqa: E402


EXPECTED_TOOLS = [
    "wiki_ingest",
    "wiki_query",
    "wiki_lint",
    "wiki_add",
    "wiki_list",
    "wiki_read",
    "wiki_delete",
]


class LLMWikiFullParityTests(unittest.TestCase):
    def test_mcp_lists_complete_tool_surface(self) -> None:
        tools = llm_wiki_mcp.list_tools()
        self.assertEqual(EXPECTED_TOOLS, [tool["name"] for tool in tools])
        ingest = tools[0]["inputSchema"]
        self.assertEqual(
            {"title", "content", "tags", "category"},
            set(ingest["required"]),
        )
        self.assertEqual(50_000, ingest["properties"]["content"]["maxLength"])
        self.assertEqual(
            [
                "architecture",
                "decision",
                "pattern",
                "debugging",
                "environment",
                "session-log",
                "reference",
                "convention",
            ],
            ingest["properties"]["category"]["enum"],
        )
        self.assertTrue(tools[-1]["annotations"]["destructiveHint"])

    def test_mcp_all_seven_operations_use_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = {"workingDirectory": str(root)}
            added = llm_wiki_mcp.call_tool(
                "wiki_add",
                {**common, "title": "MCP Page", "content": "Initial fact.", "tags": ["mcp"]},
            )
            self.assertNotIn("isError", added)
            self.assertTrue((root / ".azhou" / "llm-wiki" / "mcp-page.md").is_file())
            self.assertIn(
                "] add",
                (root / ".azhou" / "llm-wiki" / "log.md").read_text(encoding="utf-8"),
            )

            ingested = llm_wiki_mcp.call_tool(
                "wiki_ingest",
                {
                    **common,
                    "title": "MCP Page",
                    "content": "Updated fact.",
                    "tags": ["updated"],
                    "category": "reference",
                },
            )
            self.assertIn("Updated: mcp-page.md", ingested["content"][0]["text"])
            self.assertIn("1 results", llm_wiki_mcp.call_tool("wiki_query", {**common, "query": "updated"})["content"][0]["text"])
            self.assertIn("MCP Page", llm_wiki_mcp.call_tool("wiki_list", common)["content"][0]["text"])
            self.assertIn("Updated fact", llm_wiki_mcp.call_tool("wiki_read", {**common, "page": "mcp-page"})["content"][0]["text"])
            self.assertIn("Wiki Lint Report", llm_wiki_mcp.call_tool("wiki_lint", common)["content"][0]["text"])
            held = llm_wiki_mcp.call_tool("wiki_delete", {**common, "page": "mcp-page"})
            self.assertTrue(held["isError"])
            self.assertIn(
                "Deleted wiki page",
                llm_wiki_mcp.call_tool(
                    "wiki_delete", {**common, "page": "mcp-page", "confirm": True}
                )["content"][0]["text"],
            )

    def test_mcp_enforces_input_limits_and_root_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = llm_wiki_mcp.call_tool(
                "wiki_add",
                {"workingDirectory": str(root), "title": "x" * 201, "content": "body"},
            )
            self.assertTrue(result["isError"])
            self.assertIn("200", result["content"][0]["text"])
            result = llm_wiki_mcp.call_tool(
                "wiki_ingest",
                {
                    "workingDirectory": str(root),
                    "title": "Page",
                    "content": "x" * 50_001,
                    "tags": [],
                    "category": "reference",
                },
            )
            self.assertTrue(result["isError"])
            result = llm_wiki_mcp.call_tool(
                "wiki_list", {"workingDirectory": str(root / "missing")}
            )
            self.assertTrue(result["isError"])

    def test_session_end_rebuilds_index_and_mcp_list_sees_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            store.set_auto_capture(True)
            _, receipt = llm_wiki.run_hook_event(
                "session-end", store, {"cwd": str(root), "session_id": "captured"}
            )
            self.assertIn(llm_wiki.INDEX_FILE, receipt["changes"])
            self.assertIn("index rebuilt", receipt["verification"])
            listing = llm_wiki_mcp.call_tool("wiki_list", {"workingDirectory": str(root)})
            self.assertNotIn("isError", listing)
            self.assertIn("Session Log", listing["content"][0]["text"])

    def test_mcp_add_keeps_colliding_titles_and_uses_exact_v2_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = {"workingDirectory": str(root), "content": "body"}
            first = llm_wiki_mcp.call_tool("wiki_add", {**common, "title": "A B"})
            second = llm_wiki_mcp.call_tool("wiki_add", {**common, "title": "a-b"})
            self.assertNotIn("isError", first)
            self.assertNotIn("isError", second)
            expected = llm_wiki.v2_title_slug("a-b")
            self.assertIn(expected, second["content"][0]["text"])
            self.assertEqual(2, len(llm_wiki.WikiStore(root).pages()))
            self.assertEqual(
                expected,
                f"a-b-v2-{hashlib.sha256('a-b'.encode()).hexdigest()[:16]}.md",
            )
            exact_read = llm_wiki_mcp.call_tool("wiki_read", {"workingDirectory": str(root), "page": "a-b"})
            filename_read = llm_wiki_mcp.call_tool("wiki_read", {"workingDirectory": str(root), "page": "a-b.md"})
            self.assertIn("## a-b", exact_read["content"][0]["text"])
            self.assertIn("## A B", filename_read["content"][0]["text"])

    def test_invalid_lint_config_is_stable_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            store.add(title="Lint Page", content="fact", tags=[], category="reference", sources=[], confidence="medium")
            before = {name: (store.directory / name).read_bytes() for name in ("index.md", "log.md")}
            (store.directory / "config.json").write_text('{"staleDays":"30","maxPageSize":1024}\n', encoding="utf-8")
            result = llm_wiki_mcp.call_tool("wiki_lint", {"workingDirectory": str(root)})
            self.assertTrue(result["isError"])
            self.assertIn("integer", result["content"][0]["text"])
            self.assertEqual(before["index.md"], (store.directory / "index.md").read_bytes())
            self.assertEqual(before["log.md"], (store.directory / "log.md").read_bytes())

    def test_migration_rejects_typed_invalid_config_without_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = llm_wiki.WikiStore(root, ".llm-wiki")
            source.add(title="Source", content="preserve", tags=[], category="reference", sources=[], confidence="medium")
            source_before = (source.directory / "source.md").read_bytes()
            (source.directory / "config.json").write_text('{"autoCapture":false,"maxPageSize":true}\n', encoding="utf-8")
            with self.assertRaises(llm_wiki.WikiConfigError):
                llm_wiki.migrate_store(root, ".llm-wiki", apply=False)
            self.assertFalse(llm_wiki.WikiStore(root).directory.exists())
            self.assertEqual(source_before, (source.directory / "source.md").read_bytes())

    def test_mcp_stdio_initialize_list_and_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "wiki_add",
                        "arguments": {
                            "workingDirectory": str(root),
                            "title": "Protocol Page",
                            "content": "stdio works",
                        },
                    },
                },
            ]
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "llm_wiki_mcp.py")],
                input="".join(json.dumps(message) + "\n" for message in messages),
                text=True,
                capture_output=True,
                check=True,
            )
            responses = [json.loads(line) for line in completed.stdout.splitlines()]
            self.assertEqual("llm-wiki", responses[0]["result"]["serverInfo"]["name"])
            self.assertEqual(EXPECTED_TOOLS, [tool["name"] for tool in responses[1]["result"]["tools"]])
            self.assertIn("Wiki page created", responses[2]["result"]["content"][0]["text"])

    def test_session_start_rebuilds_index_and_feeds_project_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            store.add(
                title="Architecture",
                content="Verified design.",
                tags=[],
                category="architecture",
                sources=[],
                confidence="high",
            )
            (store.directory / "index.md").unlink()
            (store.directory / "project-context.json").write_text(
                json.dumps(
                    {
                        "lastScanned": "2030-01-01T00:00:00Z",
                        "techStack": {
                            "languages": [{"name": "Python"}, "TypeScript"],
                            "frameworks": ["unittest"],
                            "packageManager": "uv",
                            "runtime": "Python 3.11",
                        },
                        "build": {"test": "python3 -m unittest"},
                    }
                ),
                encoding="utf-8",
            )
            output = llm_wiki_adapter.run_host_hook(
                "session-start", json.dumps({"cwd": str(root)})
            )
            self.assertEqual("SessionStart", output["hookSpecificOutput"]["hookEventName"])
            self.assertIn("wiki_query", output["hookSpecificOutput"]["additionalContext"])
            self.assertTrue((store.directory / "index.md").is_file())
            environment = (store.directory / "environment.md").read_text(encoding="utf-8")
            self.assertIn("Languages:** Python, TypeScript", environment)
            self.assertIn("python3 -m unittest", environment)
            self.assertNotIn("environment.md", store.page_filenames())

    def test_precompact_and_session_end_match_hook_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = llm_wiki.WikiStore(root)
            store.add(
                title="Decision",
                content="Keep adapters explicit.",
                tags=[],
                category="decision",
                sources=[],
                confidence="medium",
            )
            event = json.dumps({"cwd": str(root), "session_id": "session-12345678"})
            compact = llm_wiki_adapter.run_host_hook("pre-compact", event)
            self.assertIn("[Wiki: 1 pages", compact["systemMessage"])
            started = llm_wiki_adapter.run_host_hook("SessionStart", event)
            self.assertEqual("SessionStart", started["hookSpecificOutput"]["hookEventName"])
            store.set_auto_capture(True)
            ended = llm_wiki_adapter.run_host_hook("session-end", event)
            self.assertEqual({"continue": True}, ended)
            session_pages = sorted(store.directory.glob("session-log-*.md"))
            self.assertEqual(1, len(session_pages))
            self.assertRegex(session_pages[0].name, r"-[0-9a-f]{16}\.md$")
            self.assertNotIn("session-12345678", session_pages[0].read_text(encoding="utf-8"))

    def test_session_end_respects_local_config_and_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = json.dumps({"cwd": str(root), "session_id": "blocked-12345678"})
            self.assertEqual({"continue": True}, llm_wiki_adapter.run_host_hook("session-end", event))
            self.assertFalse((root / ".azhou" / "llm-wiki").exists())

            store = llm_wiki.WikiStore(root)
            store.init()
            llm_wiki_adapter.run_host_hook("session-end", event)
            self.assertEqual([], list(store.directory.glob("session-log-*.md")))

            store.set_auto_capture(True)
            llm_wiki_adapter.run_host_hook("session-end", event)
            self.assertEqual(1, len(list(store.directory.glob("session-log-*.md"))))
            store.set_auto_capture(False)
            llm_wiki_adapter.run_host_hook(
                "session-end", json.dumps({"cwd": str(root), "session_id": "blocked-87654321"})
            )
            self.assertEqual(1, len(list(store.directory.glob("session-log-*.md"))))

            self.assertEqual(
                {"continue": True, "suppressOutput": True},
                llm_wiki_adapter.run_host_hook("SessionEnd", ""),
            )
            llm_wiki_adapter.run_host_hook("not-a-wiki-event", event)
            self.assertEqual(1, len(list(store.directory.glob("session-log-*.md"))))

    def test_adapter_renders_hook_and_mcp_configuration(self) -> None:
        hooks = llm_wiki_adapter.render_hooks(SKILL, Path(sys.executable))
        self.assertEqual({"SessionStart", "PreCompact", "SessionEnd"}, set(hooks["hooks"]))
        commands = [
            item["command"]
            for groups in hooks["hooks"].values()
            for group in groups
            for item in group["hooks"]
        ]
        self.assertTrue(all(str(SKILL) in command for command in commands))
        mcp = llm_wiki_adapter.render_mcp_config(SKILL, Path(sys.executable))
        self.assertEqual(str(SCRIPTS / "llm_wiki_mcp.py"), mcp["mcpServers"]["llm-wiki"]["args"][0])

    def test_trigger_and_command_entry_are_explicit(self) -> None:
        for prompt in ("wiki", "wiki this", "wiki add", "wiki lint", "wiki query"):
            self.assertTrue(llm_wiki_adapter.matches_wiki_trigger(prompt), prompt)
        self.assertTrue(llm_wiki_adapter.matches_wiki_trigger("use wiki to record this"))
        for prompt in (
            "wikipedia",
            "explain the architecture",
            "kiwi",
            "what is wiki?",
            "wiki is broken; explain why",
            "解释 wiki",
        ):
            self.assertFalse(llm_wiki_adapter.matches_wiki_trigger(prompt), prompt)
        command = (SKILL / "assets" / "host" / "commands" / "wiki.md").read_text(encoding="utf-8")
        self.assertIn("/llm-wiki", command)
        self.assertIn("llm-wiki/SKILL.md", command)

    def test_adapter_cli_outputs_json_only(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = llm_wiki_adapter.main(["trigger", "wiki add"])
        self.assertEqual(0, code)
        self.assertTrue(json.loads(output.getvalue())["matched"])


if __name__ == "__main__":
    unittest.main()

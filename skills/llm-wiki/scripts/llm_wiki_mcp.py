#!/usr/bin/env python3
"""Standard-library MCP stdio server for the seven LLM Wiki tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import llm_wiki


SERVER_NAME = "llm-wiki"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"
CATEGORY_VALUES = [
    "architecture",
    "decision",
    "pattern",
    "debugging",
    "environment",
    "session-log",
    "reference",
    "convention",
]


def object_schema(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


WORKING_DIRECTORY = {
    "type": "string",
    "description": "Working directory (defaults to cwd; linked worktrees are supported)",
}
TITLE = {"type": "string", "maxLength": 200, "description": "Page title (max 200 chars)"}
CONTENT = {"type": "string", "maxLength": 50_000, "description": "Markdown content (max 50KB)"}
TAGS = {
    "type": "array",
    "items": {"type": "string", "maxLength": 50},
    "maxItems": 20,
    "description": "Searchable tags",
}
CATEGORY = {"type": "string", "enum": CATEGORY_VALUES, "description": "Page category"}


TOOL_DEFINITIONS = [
    {
        "name": "wiki_ingest",
        "description": "Process knowledge into wiki pages. Creates new pages or merges into existing ones (append strategy — never replaces). A single ingest can update multiple pages via cross-references.",
        "inputSchema": object_schema(
            {
                "title": TITLE,
                "content": CONTENT,
                "tags": TAGS,
                "category": CATEGORY,
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 100},
                    "maxItems": 10,
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "workingDirectory": WORKING_DIRECTORY,
            },
            ("title", "content", "tags", "category"),
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "wiki_query",
        "description": "Search across all wiki pages by keywords and tags. Returns matching pages with relevance snippets. YOU synthesize answers with citations from the results — the tool returns raw matches only. NO vector embeddings.",
        "inputSchema": object_schema(
            {
                "query": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "category": CATEGORY,
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                "workingDirectory": WORKING_DIRECTORY,
            },
            ("query",),
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "wiki_lint",
        "description": "Run health checks on the wiki. Detects orphan pages, stale content, broken cross-references, oversized pages, and structural contradictions.",
        "inputSchema": object_schema({"workingDirectory": WORKING_DIRECTORY}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "wiki_add",
        "description": "Quick-add a wiki page. Simpler than wiki_ingest — creates a single page directly.",
        "inputSchema": object_schema(
            {
                "title": TITLE,
                "content": CONTENT,
                "tags": TAGS,
                "category": CATEGORY,
                "workingDirectory": WORKING_DIRECTORY,
            },
            ("title", "content"),
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "wiki_list",
        "description": "List all wiki pages with summaries. Reads the auto-maintained index.",
        "inputSchema": object_schema({"workingDirectory": WORKING_DIRECTORY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "wiki_read",
        "description": "Read a specific wiki page by filename (without .md extension is OK).",
        "inputSchema": object_schema(
            {"page": {"type": "string"}, "workingDirectory": WORKING_DIRECTORY},
            ("page",),
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "wiki_delete",
        "description": "Delete a wiki page by filename after explicit confirmation.",
        "inputSchema": object_schema(
            {
                "page": {"type": "string"},
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true only after the user authorizes this deletion",
                },
                "workingDirectory": WORKING_DIRECTORY,
            },
            ("page", "confirm"),
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    },
]


def list_tools() -> list[dict[str, Any]]:
    return json.loads(json.dumps(TOOL_DEFINITIONS))


def text_result(text: str, *, error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if error:
        result["isError"] = True
    return result


def require_string(arguments: dict[str, Any], name: str, maximum: int | None = None) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise llm_wiki.WikiError(f"{name} must be a string")
    if maximum is not None and len(value) > maximum:
        raise llm_wiki.WikiError(f"{name} exceeds maximum length {maximum}")
    return value


def string_list(
    arguments: dict[str, Any],
    name: str,
    *,
    required: bool = False,
    maximum_items: int | None = None,
    maximum_length: int | None = None,
) -> list[str]:
    value = arguments.get(name)
    if value is None and not required:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise llm_wiki.WikiError(f"{name} must be an array of strings")
    if maximum_items is not None and len(value) > maximum_items:
        raise llm_wiki.WikiError(f"{name} exceeds maximum item count {maximum_items}")
    if maximum_length is not None and any(len(item) > maximum_length for item in value):
        raise llm_wiki.WikiError(f"{name} contains an item longer than {maximum_length}")
    return value


def resolve_store(arguments: dict[str, Any]) -> llm_wiki.WikiStore:
    working_directory = arguments.get("workingDirectory", str(Path.cwd()))
    if not isinstance(working_directory, str):
        raise llm_wiki.WikiError("workingDirectory must be a string")
    root = Path(working_directory).expanduser()
    if not root.is_dir():
        raise llm_wiki.WikiError(f"workingDirectory does not exist: {root}")
    return llm_wiki.WikiStore(root)


def page_argument(arguments: dict[str, Any]) -> str:
    page = require_string(arguments, "page")
    return page if page.endswith(".md") else f"{page}.md"


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    values = arguments if isinstance(arguments, dict) else {}
    try:
        store = resolve_store(values)
        if name == "wiki_ingest":
            title = require_string(values, "title", 200)
            content = require_string(values, "content", 50_000)
            tags = string_list(values, "tags", required=True, maximum_items=20, maximum_length=50)
            category = require_string(values, "category")
            sources = string_list(values, "sources", maximum_items=10, maximum_length=100)
            confidence = values.get("confidence", "medium")
            if confidence not in llm_wiki.CONFIDENCE_RANK:
                raise llm_wiki.WikiError("confidence must be high, medium, or low")
            page, action = store.ingest(
                title=title,
                content=content,
                tags=tags,
                category=category,
                sources=sources,
                confidence=confidence,
            )
            created = page.filename if action == "created" else "none"
            updated = page.filename if action == "updated" else "none"
            return text_result(f"Wiki ingest complete.\n- Created: {created}\n- Updated: {updated}\n- Total affected: 1")

        if name == "wiki_query":
            query = require_string(values, "query")
            tags = string_list(values, "tags")
            category = values.get("category")
            if category is not None and category not in llm_wiki.CATEGORIES:
                raise llm_wiki.WikiError(f"unsupported category: {category}")
            limit = values.get("limit", 20)
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
                raise llm_wiki.WikiError("limit must be an integer from 1 to 50")
            matches = llm_wiki.query_pages(
                store, query, tags=tags, category=category, limit=limit, log=True
            )
            if not matches:
                return text_result(f'No wiki pages match "{query}".')
            rows = []
            for index, match in enumerate(matches, 1):
                rows.append(
                    f"### {index}. {match['title']} ({match['category']}, {match['confidence']})\n"
                    f"**File:** {match['filename']} | **Tags:** {', '.join(match['tags'])} | **Score:** {match['score']}\n"
                    f"**Snippet:** {match['snippet']}"
                )
            return text_result(f'## Wiki Query: "{query}"\n\n{len(matches)} results:\n\n' + "\n\n".join(rows))

        if name == "wiki_lint":
            config = store.config()
            report = llm_wiki.lint_store(
                store,
                stale_days=config["staleDays"],
                max_page_size=config["maxPageSize"],
                log=True,
            )
            if not report["issues"]:
                return text_result(f"Wiki lint: {report['stats']['totalPages']} pages, no issues found.")
            lines = [f"- [{issue['severity'].upper()}] {issue['type']}: {issue['message']}" for issue in report["issues"]]
            stats = report["stats"]
            return text_result(
                "## Wiki Lint Report\n\n"
                f"**{stats['totalPages']} pages**, {len(report['issues'])} issues:\n\n"
                + "\n".join(lines)
                + f"\n\n**Summary:** {stats['orphanCount']} orphan, {stats['staleCount']} stale, "
                f"{stats['brokenRefCount']} broken refs, {stats['contradictionCount']} contradictions, "
                f"{stats['oversizedCount']} oversized"
            )

        if name == "wiki_add":
            title = require_string(values, "title", 200)
            content = require_string(values, "content", 50_000)
            tags = string_list(values, "tags", maximum_items=20, maximum_length=50)
            category = values.get("category", "reference")
            if category not in llm_wiki.CATEGORIES:
                raise llm_wiki.WikiError(f"unsupported category: {category}")
            filename = llm_wiki.title_to_slug(title)
            if store.read_page(filename) is not None:
                return text_result(
                    f'Page "{filename}" already exists. Use wiki_ingest to merge content into it, '
                    "or wiki_delete to remove it first.",
                    error=True,
                )
            page, _ = store.ingest(
                title=title,
                content=content,
                tags=tags,
                category=category,
                sources=[],
                confidence="medium",
            )
            return text_result(f"Wiki page created: {page.filename}\nPath: {store.store}/{page.filename}")

        if name == "wiki_list":
            index = store.directory / llm_wiki.INDEX_FILE
            if index.is_file() and not index.is_symlink():
                index_content = index.read_text(encoding="utf-8")
                if index_content:
                    return text_result(index_content)
            pages = store.page_filenames()
            if not pages:
                return text_result("Wiki is empty. Use wiki_add or wiki_ingest to create pages.")
            return text_result(f"Wiki has {len(pages)} pages but no index. Pages:\n" + "\n".join(f"- {page}" for page in pages))

        if name == "wiki_read":
            filename = page_argument(values)
            page = store.read_page(filename)
            if page is None:
                return text_result(f"Wiki page not found: {filename}", error=True)
            header = [
                f"## {page.title}",
                f"**Category:** {page.category} | **Confidence:** {page.confidence} | **Updated:** {page.updated}",
                f"**Tags:** {', '.join(page.tags)}",
            ]
            if page.links:
                header.append(f"**Links:** {', '.join(page.links)}")
            if page.sources:
                header.append(f"**Sources:** {', '.join(page.sources)}")
            return text_result("\n".join(header) + f"\n\n{page.content}")

        if name == "wiki_delete":
            filename = page_argument(values)
            if values.get("confirm") is not True:
                return text_result("Deletion requires confirm=true after explicit user authorization.", error=True)
            if not store.delete(filename):
                return text_result(f"Wiki page not found: {filename}", error=True)
            return text_result(f"Deleted wiki page: {filename}")

        return text_result(f"Unknown tool: {name}", error=True)
    except (llm_wiki.WikiError, OSError, ValueError) as exc:
        prefixes = {
            "wiki_ingest": "Error ingesting into wiki",
            "wiki_query": "Error querying wiki",
            "wiki_lint": "Error linting wiki",
            "wiki_add": "Error adding wiki page",
            "wiki_list": "Error listing wiki",
            "wiki_read": "Error reading wiki page",
            "wiki_delete": "Error deleting wiki page",
        }
        return text_result(f"{prefixes.get(name, f'Error in {name}')}: {exc}", error=True)


def rpc_response(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": list_tools()}
    elif method == "tools/call":
        params = request.get("params") if isinstance(request.get("params"), dict) else {}
        result = call_tool(str(params.get("name", "")), params.get("arguments"))
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            response = rpc_response(request)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expose all seven LLM Wiki operations over MCP stdio")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Portable Markdown knowledge base adapted from oh-my-claudecode LLM Wiki."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


SCHEMA_VERSION = 1
RECEIPT_SCHEMA = "llm-wiki.receipt.v1"
DEFAULT_STORE = ".llm-wiki"
INDEX_FILE = "index.md"
LOG_FILE = "log.md"
CONFIG_FILE = "config.json"
RESERVED_FILES = {INDEX_FILE, LOG_FILE, "environment.md"}
CATEGORIES = {
    "architecture",
    "decision",
    "pattern",
    "debugging",
    "environment",
    "session-log",
    "reference",
    "convention",
}
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
FRONTMATTER_RE = re.compile(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$")
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]+")
LATIN_RE = re.compile(r"[a-z0-9\u00c0-\u024f]+")


class WikiError(Exception):
    """User-correctable wiki error."""


class PermissionHold(WikiError):
    """Operation needs an explicit destructive-action acknowledgement."""


@dataclass
class Page:
    filename: str
    title: str
    tags: list[str]
    created: str
    updated: str
    sources: list[str]
    links: list[str]
    category: str
    confidence: str
    schema_version: int
    content: str

    def metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("content")
        return data


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def js_string_hash(value: str) -> int:
    """Match the signed 32-bit hash used by the upstream non-ASCII slug fallback."""
    result = 0
    encoded = value.encode("utf-16-le", errors="surrogatepass")
    code_units = (int.from_bytes(encoded[index : index + 2], "little") for index in range(0, len(encoded), 2))
    for code_unit in code_units:
        result = ((result << 5) - result + code_unit) & 0xFFFFFFFF
        if result >= 0x80000000:
            result -= 0x100000000
    return result


def title_to_slug(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:64]
    if base:
        return f"{base}.md"
    hashed = abs(js_string_hash(title))
    return f"page-{hashed:08x}.md"


def tokenize(text: str) -> list[str]:
    lower = text.lower()
    tokens = LATIN_RE.findall(lower)
    for segment in CJK_RE.findall(lower):
        tokens.extend(segment)
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))

    remaining = LATIN_RE.sub(" ", lower)
    remaining = CJK_RE.sub(" ", remaining)
    for token in remaining.split():
        if any(unicodedata.category(char).startswith("L") for char in token):
            tokens.append(token)
    return tokens


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_array(values: Sequence[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def parse_yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            parsed = json.loads(value)
            return str(parsed)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_yaml_array(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item)]
        except json.JSONDecodeError:
            inner = value[1:-1]
            return unique(parse_yaml_scalar(part.strip()) for part in inner.split(","))
    return [parse_yaml_scalar(value)]


def parse_frontmatter(raw: str, filename: str) -> Page | None:
    normalized = raw.replace("\r\n", "\n")
    match = FRONTMATTER_RE.match(normalized)
    if not match:
        return None
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip():
            values[key.strip()] = value.strip()
    try:
        title = parse_yaml_scalar(values.get("title", ""))
        category = parse_yaml_scalar(values.get("category", "reference"))
        confidence = parse_yaml_scalar(values.get("confidence", "medium"))
        if not title or category not in CATEGORIES or confidence not in CONFIDENCE_RANK:
            return None
        return Page(
            filename=filename,
            title=title,
            tags=parse_yaml_array(values.get("tags")),
            created=parse_yaml_scalar(values.get("created", "")) or now_iso(),
            updated=parse_yaml_scalar(values.get("updated", "")) or now_iso(),
            sources=parse_yaml_array(values.get("sources")),
            links=parse_yaml_array(values.get("links")),
            category=category,
            confidence=confidence,
            schema_version=int(values.get("schemaVersion", SCHEMA_VERSION)),
            content=match.group(2),
        )
    except (TypeError, ValueError):
        return None


def serialize_page(page: Page) -> str:
    lines = [
        f"title: {yaml_string(page.title)}",
        f"tags: {yaml_array(page.tags)}",
        f"created: {page.created}",
        f"updated: {page.updated}",
        f"sources: {yaml_array(page.sources)}",
        f"links: {yaml_array(page.links)}",
        f"category: {page.category}",
        f"confidence: {page.confidence}",
        f"schemaVersion: {page.schema_version}",
    ]
    return f"---\n{'\n'.join(lines)}\n---\n{page.content}"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


class WikiStore:
    def __init__(self, root: Path, store: str = DEFAULT_STORE) -> None:
        self.root = root.expanduser().resolve()
        store_path = Path(store)
        if store_path.is_absolute():
            raise WikiError("--store must be relative to --root")
        self.directory = (self.root / store_path).resolve()
        try:
            self.directory.relative_to(self.root)
        except ValueError as exc:
            raise WikiError("--store escapes --root") from exc
        self.store = store_path.as_posix()

    def ensure(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        ignore = self.directory / ".gitignore"
        if not ignore.exists():
            atomic_write(ignore, "*\n!.gitignore\n")

    @contextmanager
    def lock(self, timeout: float = 5.0) -> Iterator[None]:
        self.ensure()
        lock_path = self.directory / ".wiki-lock"
        deadline = time.monotonic() + timeout
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(descriptor, json.dumps({"pid": os.getpid(), "time": time.time()}).encode())
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > 300:
                        lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise WikiError(f"wiki lock timed out: {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            lock_path.unlink(missing_ok=True)

    def safe_filename(self, value: str, *, allow_title: bool = True) -> str:
        filename = value if value.endswith(".md") else title_to_slug(value) if allow_title else value
        if (
            not filename.endswith(".md")
            or filename.startswith(".")
            or filename in RESERVED_FILES
            or Path(filename).name != filename
            or ".." in filename
            or "/" in filename
            or "\\" in filename
        ):
            raise WikiError(f"invalid or reserved wiki page: {value}")
        return filename

    def read_page(self, value: str) -> Page | None:
        filename = self.safe_filename(value)
        path = self.directory / filename
        if path.is_symlink() or not path.is_file():
            return None
        try:
            return parse_frontmatter(path.read_text(encoding="utf-8"), filename)
        except OSError:
            return None

    def page_filenames(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(
            path.name
            for path in self.directory.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix == ".md" and path.name not in RESERVED_FILES
        )

    def pages(self) -> list[Page]:
        return [page for name in self.page_filenames() if (page := self.read_page(name)) is not None]

    def invalid_pages(self) -> list[str]:
        return [name for name in self.page_filenames() if self.read_page(name) is None]

    def write_page_unsafe(self, page: Page) -> None:
        page.filename = self.safe_filename(page.filename, allow_title=False)
        atomic_write(self.directory / page.filename, serialize_page(page))

    def update_index_unsafe(self) -> None:
        pages = self.pages()
        grouped: dict[str, list[Page]] = {}
        for page in pages:
            grouped.setdefault(page.category, []).append(page)
        lines = ["# Wiki Index", "", f"> {len(pages)} pages | Last updated: {now_iso()}", ""]
        for category in sorted(grouped):
            lines.extend([f"## {category}", ""])
            for page in sorted(grouped[category], key=lambda item: item.title.lower()):
                summary = next((line.strip() for line in page.content.splitlines() if line.strip()), "")
                if len(summary) > 80:
                    summary = f"{summary[:77]}..."
                lines.append(f"- [{page.title}]({page.filename}) — {summary}")
            lines.append("")
        atomic_write(self.directory / INDEX_FILE, "\n".join(lines))

    def append_log_unsafe(self, operation: str, pages: Sequence[str], summary: str) -> None:
        log_path = self.directory / LOG_FILE
        if log_path.is_symlink():
            raise WikiError(f"refusing symlinked operation log: {log_path}")
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Wiki Log\n\n"
        line = (
            f"## [{now_iso()}] {operation}\n"
            f"- **Pages:** {', '.join(pages) or 'none'}\n"
            f"- **Summary:** {summary}\n\n"
        )
        atomic_write(log_path, existing + line)

    def init(self) -> None:
        with self.lock():
            self.update_index_unsafe()

    def add(
        self,
        *,
        title: str,
        content: str,
        tags: Sequence[str],
        category: str,
        sources: Sequence[str],
        confidence: str,
    ) -> Page:
        validate_input(title, category, confidence)
        filename = title_to_slug(title)
        timestamp = now_iso()
        with self.lock():
            if self.read_page(filename) is not None:
                raise WikiError(f"page already exists: {filename}; use ingest to append")
            page = Page(
                filename=filename,
                title=title,
                tags=unique(tags),
                created=timestamp,
                updated=timestamp,
                sources=unique(sources),
                links=extract_links(content),
                category=category,
                confidence=confidence,
                schema_version=SCHEMA_VERSION,
                content=f"\n# {title}\n\n{content}\n",
            )
            self.write_page_unsafe(page)
            self.update_index_unsafe()
            self.append_log_unsafe("add", [filename], f'Created page "{title}"')
            return page

    def ingest(
        self,
        *,
        title: str,
        content: str,
        tags: Sequence[str],
        category: str,
        sources: Sequence[str],
        confidence: str,
    ) -> tuple[Page, str]:
        validate_input(title, category, confidence)
        filename = title_to_slug(title)
        timestamp = now_iso()
        with self.lock():
            existing = self.read_page(filename)
            if existing is None:
                page = Page(
                    filename=filename,
                    title=title,
                    tags=unique(tags),
                    created=timestamp,
                    updated=timestamp,
                    sources=unique(sources),
                    links=extract_links(content),
                    category=category,
                    confidence=confidence,
                    schema_version=SCHEMA_VERSION,
                    content=f"\n# {title}\n\n{content}\n",
                )
                action = "created"
            else:
                selected_confidence = (
                    confidence
                    if CONFIDENCE_RANK[confidence] >= CONFIDENCE_RANK[existing.confidence]
                    else existing.confidence
                )
                page = Page(
                    filename=existing.filename,
                    title=existing.title,
                    tags=unique([*existing.tags, *tags]),
                    created=existing.created,
                    updated=timestamp,
                    sources=unique([*existing.sources, *sources]),
                    links=unique([*existing.links, *extract_links(content)]),
                    category=existing.category,
                    confidence=selected_confidence,
                    schema_version=existing.schema_version,
                    content=(
                        existing.content.rstrip()
                        + f"\n\n---\n\n## Update ({timestamp})\n\n{content}\n"
                    ),
                )
                action = "updated"
            self.write_page_unsafe(page)
            self.update_index_unsafe()
            self.append_log_unsafe("ingest", [filename], f'{action.title()} page "{title}"')
            return page, action

    def delete(self, value: str) -> bool:
        filename = self.safe_filename(value)
        with self.lock():
            path = self.directory / filename
            if not path.is_file():
                return False
            path.unlink()
            self.update_index_unsafe()
            self.append_log_unsafe("delete", [filename], f'Deleted page "{filename}"')
            return True

    def log(self, operation: str, pages: Sequence[str], summary: str) -> None:
        with self.lock():
            self.append_log_unsafe(operation, pages, summary)

    def config(self) -> dict[str, Any]:
        path = self.directory / CONFIG_FILE
        if path.is_symlink():
            raise WikiError(f"refusing symlinked wiki config: {path}")
        if not path.is_file():
            return {"autoCapture": False, "staleDays": 30, "maxPageSize": 10_240}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise WikiError(f"invalid wiki config: {path}") from exc
        return {
            "autoCapture": bool(value.get("autoCapture", False)),
            "staleDays": int(value.get("staleDays", 30)),
            "maxPageSize": int(value.get("maxPageSize", 10_240)),
        }

    def set_auto_capture(self, enabled: bool) -> dict[str, Any]:
        with self.lock():
            config = self.config()
            config["autoCapture"] = enabled
            atomic_write(self.directory / CONFIG_FILE, json.dumps(config, indent=2) + "\n")
            return config


def validate_input(title: str, category: str, confidence: str) -> None:
    if not title.strip():
        raise WikiError("title must not be empty")
    if category not in CATEGORIES:
        raise WikiError(f"unsupported category: {category}")
    if confidence not in CONFIDENCE_RANK:
        raise WikiError(f"unsupported confidence: {confidence}")


def extract_links(content: str) -> list[str]:
    return unique(title_to_slug(match.strip()) for match in WIKI_LINK_RE.findall(content) if match.strip())


def query_pages(
    store: WikiStore,
    query_text: str,
    *,
    tags: Sequence[str],
    category: str | None,
    limit: int,
    log: bool,
) -> list[dict[str, Any]]:
    if limit < 0:
        raise WikiError("query limit must be non-negative")
    query_lower = query_text.lower()
    terms = tokenize(query_text)
    matches: list[dict[str, Any]] = []
    for page in store.pages():
        if category and page.category != category:
            continue
        score = 0
        snippet = ""
        score += 3 * sum(
            1 for tag in tags if any(page_tag.lower() == tag.lower() for page_tag in page.tags)
        )
        for term in terms:
            if any(term in tag.lower() for tag in page.tags):
                score += 2
        title_lower = page.title.lower()
        if query_lower and query_lower in title_lower:
            score += 5
        else:
            score += 2 * sum(1 for term in terms if term in title_lower)
        content_lower = page.content.lower()
        for term in terms:
            index = content_lower.find(term)
            if index == -1:
                continue
            score += 1
            if not snippet:
                start = max(0, index - 40)
                end = min(len(page.content), index + len(term) + 80)
                raw = re.sub(r"\n+", " ", page.content[start:end]).strip()
                snippet = ("..." if start else "") + raw + ("..." if end < len(page.content) else "")
        if score <= 0:
            continue
        if not snippet:
            snippet = next((line.strip() for line in page.content.splitlines() if line.strip()), "")
            if len(snippet) > 120:
                snippet = f"{snippet[:117]}..."
        matches.append({**page.metadata(), "snippet": snippet, "score": score})
    matches.sort(key=lambda item: (-item["score"], item["filename"]))
    limited = matches[: max(0, limit)]
    if log:
        store.log(
            "query",
            [item["filename"] for item in limited],
            f'Query "{query_text}" -> {len(limited)} results (of {len(matches)} total)',
        )
    return limited


def lint_store(
    store: WikiStore,
    *,
    stale_days: int,
    max_page_size: int,
    log: bool,
) -> dict[str, Any]:
    if stale_days < 0:
        raise WikiError("stale days must be non-negative")
    if max_page_size <= 0:
        raise WikiError("maximum page size must be positive")
    pages = store.pages()
    issues: list[dict[str, str]] = []
    filenames = {page.filename for page in pages}
    incoming: dict[str, set[str]] = {}
    for page in pages:
        for link in page.links:
            incoming.setdefault(link, set()).add(page.filename)

    now = datetime.now(timezone.utc)
    for invalid in store.invalid_pages():
        issues.append(
            {"page": invalid, "severity": "error", "type": "invalid-page", "message": "Frontmatter is invalid"}
        )
    for page in pages:
        if not incoming.get(page.filename):
            issues.append(
                {"page": page.filename, "severity": "info", "type": "orphan", "message": "No incoming links"}
            )
        try:
            updated = datetime.fromisoformat(page.updated.replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age_days = (now - updated).days
            if age_days > stale_days:
                issues.append(
                    {
                        "page": page.filename,
                        "severity": "warning",
                        "type": "stale",
                        "message": f"Not updated in {age_days} days",
                    }
                )
        except ValueError:
            issues.append(
                {"page": page.filename, "severity": "error", "type": "invalid-page", "message": "Invalid updated timestamp"}
            )
        for link in page.links:
            if link not in filenames:
                issues.append(
                    {
                        "page": page.filename,
                        "severity": "error",
                        "type": "broken-ref",
                        "message": f"Broken link to {link}",
                    }
                )
        if page.confidence == "low":
            issues.append(
                {"page": page.filename, "severity": "info", "type": "low-confidence", "message": "Confidence is low"}
            )
        size = len(page.content.encode("utf-8"))
        if size > max_page_size:
            issues.append(
                {
                    "page": page.filename,
                    "severity": "warning",
                    "type": "oversized",
                    "message": f"Content is {size} bytes",
                }
            )

    groups: dict[str, list[Page]] = {}
    for page in pages:
        groups.setdefault("-".join(page.filename.split("-")[:2]), []).append(page)
    for group in groups.values():
        if len(group) < 2:
            continue
        confidences = {page.confidence for page in group}
        if {"high", "low"}.issubset(confidences):
            issues.append(
                {
                    "page": group[0].filename,
                    "severity": "warning",
                    "type": "structural-contradiction",
                    "message": "Related pages have high and low confidence",
                }
            )
        categories_by_tag: dict[str, set[str]] = {}
        for page in group:
            for tag in page.tags:
                categories_by_tag.setdefault(tag, set()).add(page.category)
        for tag, categories in categories_by_tag.items():
            if len(categories) > 1:
                issues.append(
                    {
                        "page": group[0].filename,
                        "severity": "info",
                        "type": "structural-contradiction",
                        "message": f"Tag {tag} spans categories: {', '.join(sorted(categories))}",
                    }
                )
                break

    counts = {
        "totalPages": len(pages),
        "invalidPageCount": sum(issue["type"] == "invalid-page" for issue in issues),
        "orphanCount": sum(issue["type"] == "orphan" for issue in issues),
        "staleCount": sum(issue["type"] == "stale" for issue in issues),
        "brokenRefCount": sum(issue["type"] == "broken-ref" for issue in issues),
        "lowConfidenceCount": sum(issue["type"] == "low-confidence" for issue in issues),
        "oversizedCount": sum(issue["type"] == "oversized" for issue in issues),
        "contradictionCount": sum(issue["type"] == "structural-contradiction" for issue in issues),
    }
    if log:
        store.log("lint", unique([issue["page"] for issue in issues]), f"Lint: {len(issues)} issues")
    return {"issues": issues, "stats": counts}


def context_summary(store: WikiStore, limit: int) -> str:
    pages = store.pages()
    if not pages:
        return ""
    index = store.directory / INDEX_FILE
    if index.is_file() and not index.is_symlink():
        lines = index.read_text(encoding="utf-8").splitlines()[:limit]
    else:
        lines = ["# Wiki Index", ""] + [f"- [{page.title}]({page.filename})" for page in pages[:limit]]
    return "\n".join(
        [
            f"[LLM Wiki: {len(pages)} pages at {store.store}/]",
            "",
            "Use the llm-wiki skill to query, list, read, ingest, and lint this store.",
            "",
            *lines,
        ]
    )


def read_content(args: argparse.Namespace) -> str:
    if args.content is not None:
        return args.content
    if args.content_file is not None:
        if args.content_file == "-":
            return sys.stdin.read()
        path = Path(args.content_file)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise WikiError(f"cannot read content file: {path}") from exc
    raise WikiError("provide --content or --content-file")


def emit(
    operation: str,
    *,
    status: str,
    store: WikiStore | None,
    result: Any = None,
    changes: Sequence[str] = (),
    verification: Sequence[str] = (),
    holds: Sequence[str] = (),
    next_action: str,
) -> None:
    payload = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "operation": operation,
        "store": store.store if store else None,
        "result": result,
        "changes": list(changes),
        "verification": list(verification),
        "holds": list(holds),
        "nextAction": next_action,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def add_page_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", required=True)
    content = parser.add_mutually_exclusive_group(required=True)
    content.add_argument("--content")
    content.add_argument("--content-file")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--category", choices=sorted(CATEGORIES), default="reference")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--confidence", choices=sorted(CONFIDENCE_RANK), default="medium")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent local Markdown knowledge base")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root")
    parser.add_argument("--store", default=DEFAULT_STORE, help="relative store path; use .omc/wiki for upstream data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="create the private wiki store and index")
    add_page_arguments(subparsers.add_parser("add", help="create a page; fail if it exists"))
    add_page_arguments(subparsers.add_parser("ingest", help="create or append to a page"))

    query = subparsers.add_parser("query", help="keyword and tag search")
    query.add_argument("query", nargs="*", help="search terms")
    query.add_argument("--tag", action="append", default=[])
    query.add_argument("--category", choices=sorted(CATEGORIES))
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--no-log", action="store_true", help="keep the query read-only")

    listing = subparsers.add_parser("list", help="list page metadata")
    listing.add_argument("--category", choices=sorted(CATEGORIES))
    subparsers.add_parser("read", help="read one page").add_argument("page")

    delete = subparsers.add_parser("delete", help="delete one page")
    delete.add_argument("page")
    delete.add_argument("--yes", action="store_true", help="confirm the destructive operation")

    lint = subparsers.add_parser("lint", help="check wiki health")
    lint.add_argument("--stale-days", type=int)
    lint.add_argument("--max-page-size", type=int)
    lint.add_argument("--no-log", action="store_true", help="keep lint read-only")

    context = subparsers.add_parser("context", help="render bounded session context")
    context.add_argument("--limit", type=int, default=30)

    config = subparsers.add_parser("config", help="configure optional lifecycle behavior")
    config.add_argument("--auto-capture", choices=("true", "false"), required=True)

    capture = subparsers.add_parser("capture-environment", help="explicitly ingest a reviewed JSON environment snapshot")
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--source", default="environment-snapshot")

    hook = subparsers.add_parser("hook", help="neutral stdin/stdout lifecycle adapter")
    hook.add_argument("event", choices=("session-start", "session-end", "pre-compact"))
    hook.add_argument("--limit", type=int, default=30)
    return parser


def handle_hook(args: argparse.Namespace, base_store: WikiStore) -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        emit(
            "hook",
            status="skipped",
            store=base_store,
            holds=["invalid hook input"],
            next_action="Fix hook JSON input.",
        )
        return 0
    root = Path(str(data.get("cwd", base_store.root)))
    store = WikiStore(root, base_store.store)
    if args.event in {"session-start", "pre-compact"}:
        summary = context_summary(store, args.limit)
        emit(
            "hook",
            status="pass" if summary else "skipped",
            store=store,
            result={"event": args.event, "additionalContext": summary},
            verification=[f"loaded {len(store.pages())} page(s)"],
            next_action="Use query when project knowledge is relevant." if summary else "Initialize or ingest a page first.",
        )
        return 0

    config = store.config()
    if not config["autoCapture"]:
        emit(
            "hook",
            status="skipped",
            store=store,
            result={"event": args.event, "autoCapture": False},
            next_action="Enable autoCapture explicitly only if session metadata retention is intended.",
        )
        return 0
    session_id = str(data.get("session_id", "unknown"))
    title = f"Session Log {datetime.now(timezone.utc).date().isoformat()} {session_id[:12]}"
    page, action = store.ingest(
        title=title,
        content=f"Session metadata captured by the opt-in lifecycle adapter.\n\nSession ID: `{session_id}`",
        tags=["session", "auto-captured"],
        category="session-log",
        sources=[session_id],
        confidence="low",
    )
    emit(
        "hook",
        status="pass",
        store=store,
        result={"event": args.event, "page": page.filename, "action": action},
        changes=[page.filename],
        verification=["autoCapture=true"],
        next_action="Review and promote durable findings with ingest.",
    )
    return 0


def run(args: argparse.Namespace) -> int:
    store = WikiStore(args.root, args.store)
    command = args.command
    if command == "init":
        store.init()
        emit(
            command,
            status="pass",
            store=store,
            changes=[f"{store.store}/.gitignore", f"{store.store}/{INDEX_FILE}"],
            verification=["private store initialized", "index rebuilt"],
            next_action="Ingest the first verified project fact.",
        )
    elif command in {"add", "ingest"}:
        content = read_content(args)
        if command == "add":
            page = store.add(
                title=args.title,
                content=content,
                tags=args.tag,
                category=args.category,
                sources=args.source,
                confidence=args.confidence,
            )
            action = "created"
        else:
            page, action = store.ingest(
                title=args.title,
                content=content,
                tags=args.tag,
                category=args.category,
                sources=args.source,
                confidence=args.confidence,
            )
        emit(
            command,
            status="pass",
            store=store,
            result={"page": page.metadata(), "action": action},
            changes=[page.filename, INDEX_FILE, LOG_FILE],
            verification=["atomic write", "index rebuilt", "operation logged"],
            next_action="Query the stored fact with a key term.",
        )
    elif command == "query":
        query_text = " ".join(args.query)
        results = query_pages(
            store,
            query_text,
            tags=args.tag,
            category=args.category,
            limit=args.limit,
            log=not args.no_log,
        )
        emit(
            command,
            status="pass",
            store=store,
            result={"matches": results, "count": len(results)},
            changes=[] if args.no_log else [LOG_FILE],
            verification=["keyword/tag scoring", "bounded result set"],
            next_action="Read the highest-scoring page." if results else "Try a broader term or list pages.",
        )
    elif command == "list":
        pages = [page.metadata() for page in store.pages() if not args.category or page.category == args.category]
        emit(
            command,
            status="pass",
            store=store,
            result={"pages": pages, "count": len(pages)},
            verification=["reserved files excluded"],
            next_action="Read one page by filename." if pages else "Ingest the first verified project fact.",
        )
    elif command == "read":
        page = store.read_page(args.page)
        if page is None:
            raise WikiError(f"page not found or invalid: {args.page}")
        emit(
            command,
            status="pass",
            store=store,
            result=asdict(page),
            verification=["frontmatter parsed"],
            next_action="Use ingest to append a verified update." if page else "List pages.",
        )
    elif command == "delete":
        if not args.yes:
            raise PermissionHold("delete requires explicit authorization and --yes")
        deleted = store.delete(args.page)
        if not deleted:
            raise WikiError(f"page not found: {args.page}")
        emit(
            command,
            status="pass",
            store=store,
            changes=[f"deleted {store.safe_filename(args.page)}", INDEX_FILE, LOG_FILE],
            verification=["explicit --yes", "index rebuilt", "operation logged"],
            next_action="Run lint to check remaining links.",
        )
    elif command == "lint":
        config = store.config()
        report = lint_store(
            store,
            stale_days=args.stale_days if args.stale_days is not None else config["staleDays"],
            max_page_size=args.max_page_size if args.max_page_size is not None else config["maxPageSize"],
            log=not args.no_log,
        )
        errors = report["stats"]["brokenRefCount"] + report["stats"]["invalidPageCount"]
        emit(
            command,
            status="pass" if errors == 0 else "fail",
            store=store,
            result=report,
            changes=[] if args.no_log else [LOG_FILE],
            verification=["orphan", "stale", "broken-ref", "confidence", "size", "structural contradiction"],
            holds=[f"{errors} error-severity issue(s)"] if errors else [],
            next_action="Fix error-severity issues." if errors else "Review informational and warning issues.",
        )
        return 1 if errors else 0
    elif command == "context":
        if args.limit < 0:
            raise WikiError("context limit must be non-negative")
        summary = context_summary(store, args.limit)
        emit(
            command,
            status="pass" if summary else "skipped",
            store=store,
            result={"additionalContext": summary},
            verification=[f"loaded {len(store.pages())} page(s)"],
            next_action="Use query when project knowledge is relevant." if summary else "Initialize or ingest a page first.",
        )
    elif command == "config":
        enabled = args.auto_capture == "true"
        config = store.set_auto_capture(enabled)
        emit(
            command,
            status="pass",
            store=store,
            result=config,
            changes=[CONFIG_FILE],
            verification=[f"autoCapture={str(enabled).lower()}"],
            next_action="Wire the neutral hook adapter only if the host lifecycle is understood.",
        )
    elif command == "capture-environment":
        try:
            snapshot = json.loads(args.input.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WikiError(f"cannot read valid JSON snapshot: {args.input}") from exc
        if not isinstance(snapshot, dict):
            raise WikiError("environment snapshot must be a JSON object")
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        content = "Reviewed environment snapshot:\n\n```json\n" + json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n```"
        page, action = store.ingest(
            title="Project Environment Snapshot",
            content=content,
            tags=["environment", "project-memory"],
            category="environment",
            sources=[args.source, f"sha256:{digest}"],
            confidence="medium",
        )
        emit(
            command,
            status="pass",
            store=store,
            result={"page": page.filename, "action": action, "sourceDigest": digest},
            changes=[page.filename, INDEX_FILE, LOG_FILE],
            verification=["input parsed as JSON", "source digest recorded"],
            next_action="Query one known environment key to verify retrieval.",
        )
    elif command == "hook":
        return handle_hook(args, store)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except PermissionHold as exc:
        store = None
        try:
            store = WikiStore(args.root, args.store)
        except WikiError:
            pass
        emit(
            args.command,
            status="hold",
            store=store,
            holds=[str(exc)],
            next_action="Obtain explicit deletion authorization, then rerun with --yes.",
        )
        return 3
    except WikiError as exc:
        store = None
        try:
            store = WikiStore(args.root, args.store)
        except WikiError:
            pass
        emit(
            args.command,
            status="fail",
            store=store,
            holds=[str(exc)],
            next_action="Correct the named input or store path and retry.",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

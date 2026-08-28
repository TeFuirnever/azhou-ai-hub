#!/usr/bin/env python3
"""Portable, private-by-default Markdown knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import azhou_runtime_state


SCHEMA_VERSION = 1
RECEIPT_SCHEMA = "llm-wiki.receipt.v2"
DEFAULT_STORE = ".azhou/llm-wiki"
COMPATIBILITY_STORES = {".llm-wiki", ".omc/wiki"}
INDEX_FILE = "index.md"
LOG_FILE = "log.md"
CONFIG_FILE = "config.json"
PROJECT_CONTEXT_FILE = "project-context.json"
MIGRATION_RECEIPT_FILE = ".migration-receipt.json"
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
RECEIPT_STATUSES = {"pass", "fail", "hold", "skipped"}
LEARNING_SIGNALS = {
    "none",
    "scope",
    "source",
    "privacy",
    "retrieval",
    "write",
    "lint",
    "migration",
    "lifecycle",
    "deletion",
    "config",
}
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
    """Return a stable signed 32-bit hash for non-ASCII slug fallback."""
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
        try:
            self.directory = (
                azhou_runtime_state.state_path(self.root, "llm-wiki")
                if store == DEFAULT_STORE
                else azhou_runtime_state.relative_path(self.root, store_path)
            )
        except azhou_runtime_state.StateError as exc:
            raise WikiError(str(exc)) from exc
        self.store = store_path.as_posix()

    def ensure(self) -> None:
        try:
            azhou_runtime_state.ensure_private_directory(self.directory, root=self.root)
        except azhou_runtime_state.StateError as exc:
            raise WikiError(str(exc)) from exc
        ignore = self.directory / ".gitignore"
        if ignore.is_symlink():
            raise WikiError(f"refusing symlinked wiki ignore file: {ignore}")
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

    def read_reserved_page(self, filename: str) -> Page | None:
        if filename not in RESERVED_FILES:
            raise WikiError(f"not a reserved wiki page: {filename}")
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
        path = self.directory / page.filename
        if path.is_symlink():
            raise WikiError(f"refusing symlinked wiki page: {path}")
        atomic_write(path, serialize_page(page))

    def write_environment_unsafe(self, page: Page) -> None:
        if page.filename != "environment.md":
            raise WikiError("reserved environment writer only accepts environment.md")
        path = self.directory / page.filename
        if path.is_symlink():
            raise WikiError(f"refusing symlinked environment page: {path}")
        atomic_write(path, serialize_page(page))

    def update_index_unsafe(self) -> None:
        index_path = self.directory / INDEX_FILE
        if index_path.is_symlink():
            raise WikiError(f"refusing symlinked wiki index: {index_path}")
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
        atomic_write(index_path, "\n".join(lines))

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
            path = self.directory / filename
            if path.is_symlink():
                raise WikiError(f"refusing symlinked wiki page: {path}")
            if path.exists():
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
            path = self.directory / filename
            if path.is_symlink():
                raise WikiError(f"refusing symlinked wiki page: {path}")
            existing = self.read_page(filename)
            if path.exists() and existing is None:
                raise WikiError(f"refusing to overwrite invalid wiki page: {filename}")
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
            if path.is_symlink():
                raise WikiError(f"refusing symlinked wiki page: {path}")
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


def parse_timestamp(value: str) -> float:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return float("nan")


def project_context_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if isinstance(value, str) and value:
            names.append(value)
        elif isinstance(value, dict) and isinstance(value.get("name"), str) and value["name"]:
            names.append(value["name"])
    return names


def feed_project_context(store: WikiStore) -> str | None:
    """Refresh reserved environment.md from an optional local project context."""
    if not store.directory.is_dir():
        return None
    path = store.directory / PROJECT_CONTEXT_FILE
    if path.is_symlink() or not path.is_file():
        return None
    try:
        context = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(context, dict) or not isinstance(context.get("lastScanned"), str):
        return None

    existing = store.read_reserved_page("environment.md")
    if existing and parse_timestamp(existing.updated) >= parse_timestamp(context["lastScanned"]):
        return None

    lines = ["", "# Project Environment", ""]
    stack = context.get("techStack")
    if isinstance(stack, dict):
        languages = project_context_names(stack.get("languages"))
        frameworks = project_context_names(stack.get("frameworks"))
        if languages:
            lines.append(f"**Languages:** {', '.join(languages)}")
        if frameworks:
            lines.append(f"**Frameworks:** {', '.join(frameworks)}")
        if stack.get("packageManager"):
            lines.append(f"**Package Manager:** {stack['packageManager']}")
        if stack.get("runtime"):
            lines.append(f"**Runtime:** {stack['runtime']}")
        lines.append("")
    build = context.get("build")
    if isinstance(build, dict):
        lines.append("## Build Commands")
        for key, value in build.items():
            if value:
                lines.append(f"- **{key}:** `{value}`")
        lines.append("")

    timestamp = now_iso()
    page = Page(
        filename="environment.md",
        title="Project Environment",
        tags=["environment", "auto-detected"],
        created=existing.created if existing else timestamp,
        updated=timestamp,
        sources=["project-context-auto-detect"],
        links=[],
        category="environment",
        confidence="high",
        schema_version=SCHEMA_VERSION,
        content="\n".join(lines),
    )
    with store.lock():
        store.write_environment_unsafe(page)
        store.update_index_unsafe()
    return page.filename


def lifecycle_session_context(store: WikiStore, limit: int) -> str:
    pages = store.pages()
    index = store.directory / INDEX_FILE
    if not pages or not index.is_file() or index.is_symlink():
        return ""
    lines = index.read_text(encoding="utf-8").splitlines()[:limit]
    return "\n".join(
        [
            f"[LLM Wiki: {len(pages)} pages at {store.store}/]",
            "",
            "Use wiki_query to search, wiki_list to browse, wiki_read to view pages.",
            "",
            *lines,
        ]
    )


def precompact_summary(store: WikiStore) -> str:
    pages = store.pages()
    if not pages:
        return ""
    categories = unique([page.category for page in pages])
    latest = max((page.updated for page in pages), default="unknown")
    return f"[Wiki: {len(pages)} pages | categories: {', '.join(categories)} | last updated: {latest}]"


def run_hook_event(
    event: str,
    base_store: WikiStore,
    data: dict[str, Any],
    *,
    limit: int = 30,
) -> tuple[WikiStore, dict[str, Any]]:
    if event not in {"session-start", "pre-compact", "session-end"}:
        raise WikiError(f"unsupported lifecycle event: {event}")
    root = Path(str(data.get("cwd", base_store.root)))
    store = WikiStore(root, base_store.store)
    if event == "session-start":
        changes: list[str] = []
        if store.directory.is_dir():
            pages = store.pages()
            index = store.directory / INDEX_FILE
            if pages and (index.is_symlink() or not index.is_file()):
                with store.lock():
                    store.update_index_unsafe()
                changes.append(INDEX_FILE)
            if feed_project_context(store):
                changes.append("environment.md")
            summary = lifecycle_session_context(store, limit)
        else:
            summary = ""
        return store, {
            "status": "pass" if summary else "skipped",
            "result": {"event": event, "additionalContext": summary},
            "changes": changes,
            "verification": [f"loaded {len(store.pages())} page(s)"],
            "holds": [],
            "nextAction": "Use query when project knowledge is relevant." if summary else "Initialize or ingest a page first.",
        }
    if event == "pre-compact":
        summary = precompact_summary(store)
        return store, {
            "status": "pass" if summary else "skipped",
            "result": {"event": event, "additionalContext": summary},
            "changes": [],
            "verification": [f"loaded {len(store.pages())} page(s)"],
            "holds": [],
            "nextAction": "Preserve the summary through compaction." if summary else "Initialize or ingest a page first.",
        }

    config = store.config()
    if not config["autoCapture"] or not store.directory.is_dir():
        return store, {
            "status": "skipped",
            "result": {"event": event, "autoCapture": bool(config["autoCapture"])},
            "changes": [],
            "verification": [],
            "holds": [],
            "nextAction": "Enable autoCapture only when session metadata retention is intended.",
        }

    session_id = str(data.get("session_id") or f"session-{int(time.time() * 1000)}")
    session_reference = hashlib.sha256(session_id.encode("utf-8", errors="replace")).hexdigest()[:16]
    date_slug = datetime.now(timezone.utc).date().isoformat()
    filename = f"session-log-{date_slug}-{session_reference}.md"
    timestamp = now_iso()
    page = Page(
        filename=filename,
        title=f"Session Log {date_slug}",
        tags=["session-log", "auto-captured"],
        created=timestamp,
        updated=timestamp,
        sources=[f"session:{session_reference}"],
        links=[],
        category="session-log",
        confidence="medium",
        schema_version=SCHEMA_VERSION,
        content=(
            f"\n# Session Log {date_slug}\n\nAuto-captured session metadata.\n"
            f"Session reference: {session_reference}\n\nReview and promote significant findings to curated wiki pages "
            "via `wiki_ingest`.\n"
        ),
    )
    with store.lock(timeout=3.0):
        store.write_page_unsafe(page)
        store.append_log_unsafe("ingest", [filename], f"Auto-captured session log for {session_reference}")
    action = "created"
    return store, {
        "status": "pass",
        "result": {"event": event, "page": page.filename, "action": action},
        "changes": [page.filename],
        "verification": ["autoCapture=true"],
        "holds": [],
        "nextAction": "Review and promote durable findings with ingest.",
    }


def migration_payload(root: Path, source_store: str) -> tuple[Path, dict[str, str], bool]:
    if Path(source_store).as_posix() not in COMPATIBILITY_STORES:
        raise WikiError(f"unrecognized migration source: {source_store}")
    source = WikiStore(root, source_store)
    target = WikiStore(root)
    if source.directory == target.directory:
        raise WikiError("migration source must differ from the canonical store")
    if not source.directory.is_dir():
        raise WikiError(f"migration source does not exist: {source.directory}")

    allowed_names = {".gitignore", CONFIG_FILE, PROJECT_CONTEXT_FILE}
    payload: dict[str, str] = {}
    auto_capture_reset = False
    for path in sorted(source.directory.iterdir(), key=lambda item: item.name):
        if path.name == ".wiki-lock":
            raise WikiError("migration source is active; retry after its lock is released")
        if path.is_symlink() or not path.is_file():
            raise WikiError(f"unsupported migration entry: {path.name}")
        if path.name == INDEX_FILE:
            continue
        if path.suffix != ".md" and path.name not in allowed_names:
            raise WikiError(f"unsupported migration entry: {path.name}")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise WikiError(f"cannot read migration entry: {path.name}") from exc
        if path.name == CONFIG_FILE:
            try:
                config = json.loads(content)
            except json.JSONDecodeError as exc:
                raise WikiError("migration source has invalid config.json") from exc
            if not isinstance(config, dict):
                raise WikiError("migration source config.json must contain an object")
            if "autoCapture" in config and not isinstance(config["autoCapture"], bool):
                raise WikiError("migration source autoCapture must be a boolean")
            try:
                stale_days = int(config.get("staleDays", 30))
                max_page_size = int(config.get("maxPageSize", 10_240))
            except (TypeError, ValueError) as exc:
                raise WikiError("migration source has invalid numeric config") from exc
            if stale_days < 0 or max_page_size <= 0:
                raise WikiError("migration source has unsafe numeric config")
            auto_capture_reset = bool(config.get("autoCapture", False))
            config["autoCapture"] = False
            content = json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        elif path.name == PROJECT_CONTEXT_FILE:
            try:
                context = json.loads(content)
            except json.JSONDecodeError as exc:
                raise WikiError("migration source has invalid project context") from exc
            if not isinstance(context, dict):
                raise WikiError("migration source project context must contain an object")
        elif path.suffix == ".md" and path.name != LOG_FILE:
            if path.name != "environment.md":
                source.safe_filename(path.name, allow_title=False)
            if parse_frontmatter(content, path.name) is None:
                raise WikiError(f"migration source has invalid wiki page: {path.name}")
        payload[path.name] = content
    payload[".gitignore"] = "*\n!.gitignore\n"
    return source.directory, payload, auto_capture_reset


def target_migration_payload(target: WikiStore) -> dict[str, str]:
    payload: dict[str, str] = {}
    allowed_names = {".gitignore", CONFIG_FILE, PROJECT_CONTEXT_FILE}
    for path in sorted(target.directory.iterdir(), key=lambda item: item.name):
        if path.name == MIGRATION_RECEIPT_FILE:
            continue
        if path.is_symlink() or not path.is_file():
            raise WikiError(f"canonical store contains unsupported entry: {path.name}")
        if path.name == INDEX_FILE:
            continue
        if path.suffix != ".md" and path.name not in allowed_names:
            raise WikiError(f"canonical store contains unsupported entry: {path.name}")
        try:
            payload[path.name] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise WikiError(f"cannot read canonical store entry: {path.name}") from exc
    return payload


def migration_plan(
    source_directory: Path,
    target_directory: Path,
    payload: dict[str, str],
    auto_capture_reset: bool,
) -> dict[str, Any]:
    contents = [
        {
            "path": name,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "size": len(content.encode("utf-8")),
        }
        for name, content in sorted(payload.items())
    ]
    binding = {
        "schemaVersion": "llm-wiki.migration.v1",
        "source": source_directory.as_posix(),
        "target": target_directory.as_posix(),
        "contents": contents,
        "sourcePreserved": True,
        "autoCaptureReset": auto_capture_reset,
    }
    plan_id = hashlib.sha256(
        json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**binding, "planId": plan_id}


def migrate_store(
    root: Path,
    source_store: str,
    *,
    apply: bool,
    expected_plan_id: str | None = None,
) -> dict[str, Any]:
    """Copy a complete prior store into the canonical store without deleting the source."""

    root = root.expanduser().resolve()
    source_directory, payload, auto_capture_reset = migration_payload(root, source_store)
    target = WikiStore(root)
    files = sorted({*payload, INDEX_FILE})
    plan = migration_plan(source_directory, target.directory, payload, auto_capture_reset)
    if expected_plan_id is not None and expected_plan_id != plan["planId"]:
        raise WikiError("migration plan changed; run dry-run again")
    if target.directory.exists():
        if not target.directory.is_dir():
            raise WikiError(f"canonical store path is not a directory: {target.directory}")
        if target_migration_payload(target) != payload:
            raise WikiError("canonical store already exists with conflicting content")
        receipt_path = target.directory / MIGRATION_RECEIPT_FILE
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise WikiError("canonical store migration receipt is missing or unsafe")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise WikiError("canonical store migration receipt is invalid") from exc
        if receipt.get("planId") != plan["planId"]:
            raise WikiError("canonical store migration receipt does not match the source")
        return {
            **plan,
            "status": "already-current",
            "files": files,
        }
    if not apply:
        return {
            **plan,
            "status": "planned",
            "files": files,
        }

    try:
        azhou_runtime_state.ensure_private_directory(target.directory.parent, root=root)
    except azhou_runtime_state.StateError as exc:
        raise WikiError(str(exc)) from exc
    stage = Path(tempfile.mkdtemp(prefix=".wiki-migration-", dir=target.directory.parent))
    try:
        for name, content in payload.items():
            atomic_write(stage / name, content)
        staged_store = WikiStore(root, stage.relative_to(root).as_posix())
        with staged_store.lock():
            staged_store.update_index_unsafe()
        atomic_write(
            stage / MIGRATION_RECEIPT_FILE,
            json.dumps({**plan, "status": "migrated"}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        os.replace(stage, target.directory)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return {
        **plan,
        "status": "migrated",
        "files": files,
    }


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
    current_truth: str,
    result: Any = None,
    changes: Sequence[str] = (),
    verification: Sequence[str] = (),
    holds: Sequence[str] = (),
    next_action: str,
    learning_signal: str = "none",
) -> None:
    if status not in RECEIPT_STATUSES:
        raise ValueError(f"unsupported receipt status: {status}")
    if not current_truth.strip():
        raise ValueError("receipt current truth must not be empty")
    if learning_signal not in LEARNING_SIGNALS:
        raise ValueError(f"unsupported learning signal: {learning_signal}")
    payload = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "operation": operation,
        "store": store.store if store else None,
        "currentTruth": current_truth,
        "result": result,
        "changes": list(changes),
        "verification": list(verification),
        "holds": list(holds),
        "nextAction": next_action,
        "learningSignal": learning_signal,
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

    migrate = subparsers.add_parser("migrate", help="copy a prior store into the canonical store")
    migrate.add_argument("--from-store", required=True, help="project-relative source store")
    migrate.add_argument("--apply", action="store_true", help="apply after reviewing the dry-run receipt")
    migrate.add_argument("--plan-id", help="bind --apply to the reviewed dry-run plan")
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
            current_truth="Hook input was invalid; no lifecycle action ran.",
            holds=["invalid hook input"],
            next_action="Fix hook JSON input.",
            learning_signal="lifecycle",
        )
        return 0
    store, outcome = run_hook_event(
        args.event,
        base_store,
        data,
        limit=args.limit,
    )
    emit(
        "hook",
        status=outcome["status"],
        store=store,
        current_truth=f"Lifecycle event {args.event} returned {outcome['status']}.",
        result=outcome["result"],
        changes=outcome["changes"],
        verification=outcome["verification"],
        holds=outcome["holds"],
        next_action=outcome["nextAction"],
        learning_signal="lifecycle",
    )
    return 0


def run(args: argparse.Namespace) -> int:
    store = WikiStore(args.root)
    command = args.command
    if command == "init":
        store.init()
        emit(
            command,
            status="pass",
            store=store,
            current_truth="Canonical private store initialized and indexed.",
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
            current_truth=f"Page {page.filename} was {action} in the canonical store.",
            result={"page": page.metadata(), "action": action},
            changes=[page.filename, INDEX_FILE, LOG_FILE],
            verification=["atomic write", "index rebuilt", "operation logged"],
            next_action="Query the stored fact with a key term.",
            learning_signal="write",
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
            current_truth=f"Local deterministic query matched {len(results)} page(s).",
            result={"matches": results, "count": len(results)},
            changes=[] if args.no_log else [LOG_FILE],
            verification=["keyword/tag scoring", "bounded result set"],
            next_action="Read the highest-scoring page." if results else "Try a broader term or list pages.",
            learning_signal="retrieval",
        )
    elif command == "list":
        pages = [page.metadata() for page in store.pages() if not args.category or page.category == args.category]
        emit(
            command,
            status="pass",
            store=store,
            current_truth=f"Canonical store contains {len(pages)} listed page(s).",
            result={"pages": pages, "count": len(pages)},
            verification=["reserved files excluded"],
            next_action="Read one page by filename." if pages else "Ingest the first verified project fact.",
            learning_signal="retrieval",
        )
    elif command == "read":
        page = store.read_page(args.page)
        if page is None:
            raise WikiError(f"page not found or invalid: {args.page}")
        emit(
            command,
            status="pass",
            store=store,
            current_truth=f"Page {page.filename} parsed successfully from the canonical store.",
            result=asdict(page),
            verification=["frontmatter parsed"],
            next_action="Use ingest to append a verified update." if page else "List pages.",
            learning_signal="retrieval",
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
            current_truth=f"Authorized deletion removed {store.safe_filename(args.page)}.",
            changes=[f"deleted {store.safe_filename(args.page)}", INDEX_FILE, LOG_FILE],
            verification=["explicit --yes", "index rebuilt", "operation logged"],
            next_action="Run lint to check remaining links.",
            learning_signal="deletion",
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
            current_truth=f"Lint checked {report['stats']['totalPages']} page(s) and found {errors} error-severity issue(s).",
            result=report,
            changes=[] if args.no_log else [LOG_FILE],
            verification=["orphan", "stale", "broken-ref", "confidence", "size", "structural contradiction"],
            holds=[f"{errors} error-severity issue(s)"] if errors else [],
            next_action="Fix error-severity issues." if errors else "Review informational and warning issues.",
            learning_signal="lint",
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
            current_truth=(
                f"Bounded context loaded {len(store.pages())} page(s)."
                if summary
                else "No wiki pages were available for bounded context."
            ),
            result={"additionalContext": summary},
            verification=[f"loaded {len(store.pages())} page(s)"],
            next_action="Use query when project knowledge is relevant." if summary else "Initialize or ingest a page first.",
            learning_signal="retrieval",
        )
    elif command == "config":
        enabled = args.auto_capture == "true"
        config = store.set_auto_capture(enabled)
        emit(
            command,
            status="pass",
            store=store,
            current_truth=f"Session metadata capture is {'enabled' if enabled else 'disabled'}.",
            result=config,
            changes=[CONFIG_FILE],
            verification=[f"autoCapture={str(enabled).lower()}"],
            next_action="Wire the neutral hook adapter only if the host lifecycle is understood.",
            learning_signal="config",
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
            tags=["environment", "project-context"],
            category="environment",
            sources=[args.source, f"sha256:{digest}"],
            confidence="medium",
        )
        emit(
            command,
            status="pass",
            store=store,
            current_truth=f"Reviewed environment snapshot was {action} as {page.filename}.",
            result={"page": page.filename, "action": action, "sourceDigest": digest},
            changes=[page.filename, INDEX_FILE, LOG_FILE],
            verification=["input parsed as JSON", "source digest recorded"],
            next_action="Query one known environment key to verify retrieval.",
            learning_signal="source",
        )
    elif command == "hook":
        return handle_hook(args, store)
    elif command == "migrate":
        if args.apply and not args.plan_id:
            raise WikiError("--apply requires the reviewed --plan-id")
        result = migrate_store(
            args.root,
            args.from_store,
            apply=args.apply,
            expected_plan_id=args.plan_id,
        )
        applied = result["status"] in {"migrated", "already-current"}
        emit(
            command,
            status="pass",
            store=store if applied else None,
            current_truth=f"Migration status is {result['status']}; source preservation is true.",
            result=result,
            changes=result["files"] if result["status"] == "migrated" else [],
            verification=["source preserved", "conflicts rejected", "autoCapture reset to false"],
            next_action=(
                "Run lint and query against the canonical store."
                if applied
                else "Review the receipt, then rerun with --apply."
            ),
            learning_signal="migration",
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except PermissionHold as exc:
        store = None
        try:
            store = WikiStore(args.root)
        except WikiError:
            pass
        emit(
            args.command,
            status="hold",
            store=store,
            current_truth="Deletion did not run because explicit authorization was missing.",
            holds=[str(exc)],
            next_action="Obtain explicit deletion authorization, then rerun with --yes.",
            learning_signal="deletion",
        )
        return 3
    except WikiError as exc:
        store = None
        try:
            store = WikiStore(args.root)
        except WikiError:
            pass
        emit(
            args.command,
            status="fail",
            store=store,
            current_truth="The requested operation did not complete.",
            holds=[str(exc)],
            next_action="Correct the named input or store path and retry.",
            learning_signal="scope",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

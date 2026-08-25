#!/usr/bin/env python3
"""Preflight, validate, no-clobber install, and restore Super Caveman prose compression."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterator


MAX_FILE_SIZE = 500_000
COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".markdown", ".rst", ".typ", ".typst", ".tex"}
SKIP_EXTENSIONS = {
    ".bash", ".c", ".cfg", ".cpp", ".css", ".csv", ".dockerfile", ".env",
    ".go", ".h", ".hpp", ".html", ".ini", ".java", ".js", ".json", ".jsx",
    ".kt", ".lock", ".lua", ".makefile", ".php", ".py", ".rb", ".rs", ".scss",
    ".sh", ".sql", ".swift", ".toml", ".ts", ".tsx", ".xml", ".yaml", ".yml",
    ".zsh",
}
KNOWN_CODE_FILENAMES = {
    "brewfile", "cmakelists.txt", "dockerfile", "gemfile", "gnumakefile", "jenkinsfile",
    "justfile", "makefile", "procfile", "rakefile", "vagrantfile",
}
SENSITIVE_PATH_COMPONENTS = frozenset({".aws", ".docker", ".gnupg", ".kube", ".ssh"})
SENSITIVE_NAME_TOKENS = (
    "accesskey", "apikey", "credential", "password", "passwd", "privatekey", "secret", "token",
)
SENSITIVE_BASENAME = re.compile(
    r"(?ix)^(\.env(?:\..+)?|\.netrc|credentials(?:\..+)?|secrets?(?:\..+)?|"
    r"passwords?(?:\..+)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|authorized_keys|known_hosts|"
    r".*\.(?:pem|key|p12|pfx|crt|cer|jks|keystore|asc|gpg))$"
)
FRONTMATTER = re.compile(r"\A(?:\ufeff)?(---\r?\n.*?\r?\n---\r?\n)", re.DOTALL)
FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})(.*)$")
BLOCKQUOTE_PREFIX = re.compile(r"^[ \t]*>[ ]?")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
URL = re.compile(r"https?://[^\s)]+")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+[\"'][^)]*)?\)")
PATH_TOKEN = re.compile(
    r"(?:\./|\.\./|/|[A-Za-z]:\\)[\w\-/\\.]+|[\w\-.]+[/\\][\w\-/\\.]+|"
    r"(?<![\w./])(?:\.[A-Za-z0-9_-]+|[A-Za-z0-9][\w.-]*\.[A-Za-z][A-Za-z0-9]{0,9})(?![\w/])"
)
BULLET = re.compile(r"^(?P<indent>\s*)(?P<marker>[-*+]|\d+[.)])\s+", re.MULTILINE)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
VERSION = re.compile(r"\bv?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?\b")
NUMBER = re.compile(r"\b\d+(?:\.\d+)?(?:%|[A-Za-z]+)?\b")
TECHNICAL_IDENTIFIER = re.compile(
    r"\b(?:[A-Z]{2,}(?:-[A-Z0-9]+)*|[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*|"
    r"[A-Z][A-Za-z]*\d+[A-Za-z0-9.-]*)\b"
)
COMMAND = re.compile(
    r"\b(?:ansible|brew|bun|cargo|curl|deno|docker|dotnet|git|gh|gradle|helm|"
    r"kubectl|mvn|node|npm|npx|pip3?|pnpm|poetry|powershell|pwsh|pytest|python3?|"
    r"rsync|ssh|sudo|terraform|uv|wget|yarn|zsh)\s+"
    r"[A-Za-z0-9_./:@+-]+(?:\s+(?:--?[A-Za-z0-9][\w-]*(?:=[^\s,.;]+)?|[./@][^\s,.;]+)){0,6}"
)
CODE_LINE_PATTERNS = (
    re.compile(r"^\s*(?:import |from .+ import |require\(|const |let |var )"),
    re.compile(r"^\s*(?:def |class |function |async function |export )"),
    re.compile(r"^\s*(?:if\s*\(|for\s*\(|while\s*\(|switch\s*\(|try\s*\{)"),
    re.compile(r"^\s*[}\]);]+\s*$"),
    re.compile(r"^\s*@\w+"),
    re.compile(r'^\s*"[^"]+"\s*:\s*'),
    re.compile(r"^\s*\w+\s*=\s*[{[(\"']"),
)


class GuardError(RuntimeError):
    """Raised when a guard must stop an unsafe or invalid operation."""


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors and not self.warnings

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": self.errors, "warnings": self.warnings}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_utf8(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return stream.read()
    except UnicodeDecodeError as exc:
        raise GuardError(f"file is not valid UTF-8: {path}") from exc


def read_candidate(path: Path) -> str:
    candidate = path.expanduser().resolve()
    if not candidate.exists() or not candidate.is_file():
        raise GuardError(f"candidate file not found: {candidate}")
    size = candidate.stat().st_size
    if size > MAX_FILE_SIZE:
        raise GuardError(f"candidate exceeds {MAX_FILE_SIZE} bytes: {candidate}")
    return read_utf8(candidate)


def is_sensitive_path(path: Path) -> bool:
    if SENSITIVE_BASENAME.match(path.name):
        return True
    if {part.lower() for part in path.parts} & SENSITIVE_PATH_COMPONENTS:
        return True
    normalized = re.sub(r"[_\-\s.]", "", path.name.lower())
    return any(token in normalized for token in SENSITIVE_NAME_TOKENS)


def looks_like_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def looks_like_yaml(lines: list[str]) -> bool:
    indicators = 0
    non_empty = 0
    for line in lines[:30]:
        stripped = line.strip()
        if not stripped:
            continue
        non_empty += 1
        if stripped == "---" or re.match(r"^\w[\w\s-]*:\s", stripped):
            indicators += 1
        elif stripped.startswith("- ") and ":" in stripped:
            indicators += 1
    return non_empty > 0 and indicators / non_empty > 0.6


def detect_file_type(path: Path) -> str:
    if path.name.lower() in KNOWN_CODE_FILENAMES:
        return "code"
    extension = path.suffix.lower()
    if extension in COMPRESSIBLE_EXTENSIONS:
        return "natural_language"
    if extension in SKIP_EXTENSIONS:
        if extension in {".cfg", ".env", ".ini", ".json", ".toml", ".yaml", ".yml"}:
            return "config"
        return "code"
    if extension:
        return "unknown"

    text = read_utf8(path)
    if text.startswith("#!"):
        return "code"
    if looks_like_json(text[:10_000]) or looks_like_yaml(text.splitlines()[:50]):
        return "config"
    lines = [line for line in text.splitlines()[:50] if line.strip()]
    code_lines = sum(any(pattern.match(line) for pattern in CODE_LINE_PATTERNS) for line in lines)
    if lines and code_lines / len(lines) > 0.4:
        return "code"
    return "natural_language"


def data_root() -> Path:
    if os.name == "nt" or sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "super-caveman" / "compression-backups"


def backup_paths(source: Path) -> tuple[Path, Path]:
    parent_digest = hashlib.sha256(str(source.parent.resolve()).encode("utf-8")).hexdigest()[:12]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", source.parent.name or "root")
    directory = data_root() / f"{label}-{parent_digest}"
    return directory / f"{source.name}.original", directory / f"{source.name}.receipt.json"


def ensure_private_directory(directory: Path) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(directory, 0o700)


def acquire_lock(stream: Any) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def release_lock(stream: Any) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def operation_lock(source: Path) -> Iterator[None]:
    backup, _ = backup_paths(source.expanduser().resolve())
    ensure_private_directory(backup.parent)
    lock_path = backup.parent / f"{source.name}.lock"
    stream = lock_path.open("a+b")
    if os.name != "nt":
        os.chmod(lock_path, 0o600)
    if lock_path.stat().st_size == 0:
        stream.write(b"0")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        acquire_lock(stream)
    except OSError as exc:
        stream.close()
        raise GuardError(f"operation already in progress: {source}") from exc
    try:
        yield
    finally:
        release_lock(stream)
        stream.close()


def preflight(path: Path) -> dict[str, Any]:
    source = path.expanduser().resolve()
    if not source.exists():
        raise GuardError(f"file not found: {source}")
    if not source.is_file():
        raise GuardError(f"not a file: {source}")
    size = source.stat().st_size
    if size > MAX_FILE_SIZE:
        raise GuardError(f"file exceeds {MAX_FILE_SIZE} bytes: {source}")
    if source.name.endswith(".original.md") or source.name.endswith(".original"):
        raise GuardError(f"backup files are not compressible: {source}")
    if is_sensitive_path(source):
        raise GuardError(f"path name looks sensitive: {source}")
    text = read_utf8(source)
    if not text.strip():
        raise GuardError(f"file is empty: {source}")
    file_type = detect_file_type(source)
    if file_type != "natural_language":
        raise GuardError(f"file type is not natural language ({file_type}): {source}")
    backup, receipt = backup_paths(source)
    return {
        "allowed": True,
        "source": str(source),
        "file_type": file_type,
        "bytes": size,
        "sha256": sha256_bytes(text.encode("utf-8")),
        "backup": str(backup),
        "receipt": str(receipt),
    }


def frontmatter(text: str) -> str:
    match = FRONTMATTER.match(text)
    return match.group(1) if match else ""


def newline_styles(text: str) -> set[str]:
    without_crlf = text.replace("\r\n", "")
    styles: set[str] = set()
    if "\r\n" in text:
        styles.add("crlf")
    if "\n" in without_crlf:
        styles.add("lf")
    if "\r" in without_crlf:
        styles.add("cr")
    return styles


def logical_markdown_line(line: str) -> str:
    """Remove blockquote syntax while preserving the original source line."""
    logical = line
    while True:
        match = BLOCKQUOTE_PREFIX.match(logical)
        if not match:
            return logical
        logical = logical[match.end():]


def fence_ranges(lines: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        match = FENCE.match(logical_markdown_line(lines[index]))
        if not match:
            index += 1
            continue
        start = index
        fence_char = match.group(2)[0]
        fence_len = len(match.group(2))
        index += 1
        while index < len(lines):
            closing = FENCE.match(logical_markdown_line(lines[index]))
            index += 1
            if (
                closing
                and closing.group(2)[0] == fence_char
                and len(closing.group(2)) >= fence_len
                and not closing.group(3).strip()
            ):
                break
        ranges.append((start, index))
    return ranges


def fenced_blocks(text: str) -> list[str]:
    lines = text.split("\n")
    return ["\n".join(lines[start:end]) for start, end in fence_ranges(lines)]


def indentation_width(line: str) -> int:
    columns = 0
    for character in line:
        if character == " ":
            columns += 1
        elif character == "\t":
            columns += 4 - columns % 4
        else:
            break
    return columns


def column_width(text: str) -> int:
    columns = 0
    for character in text:
        if character == "\t":
            columns += 4 - columns % 4
        else:
            columns += 1
    return columns


def active_list_content_indent(lines: list[str], index: int) -> int | None:
    blank_lines = 0
    cursor = index - 1
    while cursor >= 0 and not lines[cursor].strip():
        blank_lines += 1
        cursor -= 1
    if blank_lines >= 2:
        return None
    while cursor >= 0:
        line = lines[cursor]
        if not line.strip():
            cursor -= 1
            continue
        item = BULLET.match(line)
        if item:
            return column_width(line[: item.end()])
        if indentation_width(line) == 0:
            return None
        cursor -= 1
    return None


def indented_code_blocks(text: str) -> list[str]:
    lines_with_endings = text.splitlines(keepends=True)
    lines = [line.rstrip("\r\n") for line in lines_with_endings]
    # Markdown block quotes add syntax columns which must not count toward
    # code indentation.  Keep the original lines for byte-for-byte protection,
    # but parse a quote-stripped view for list and indentation structure.
    logical_lines = [logical_markdown_line(line) for line in lines]
    fenced_lines = {
        line_index
        for start, end in fence_ranges(logical_lines)
        for line_index in range(start, end)
    }
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if index in fenced_lines or not logical_lines[index].strip():
            index += 1
            continue
        list_indent = active_list_content_indent(logical_lines, index)
        required_indent = 4 if list_indent is None else list_indent + 4
        if indentation_width(logical_lines[index]) < required_indent:
            index += 1
            continue
        if index > 0 and logical_lines[index - 1].strip() and list_indent is None:
            index += 1
            continue

        block_lines = [lines_with_endings[index]]
        index += 1
        pending_blank_lines: list[str] = []
        while index < len(lines):
            if not logical_lines[index].strip():
                pending_blank_lines.append(lines_with_endings[index])
                index += 1
                continue
            if index in fenced_lines or indentation_width(logical_lines[index]) < required_indent:
                break
            block_lines.extend(pending_blank_lines)
            pending_blank_lines.clear()
            block_lines.append(lines_with_endings[index])
            index += 1
        blocks.append("".join(block_lines))
    return blocks


def prose_without_fences(text: str) -> str:
    lines = text.split("\n")
    output: list[str] = []
    cursor = 0
    for start, end in fence_ranges(lines):
        output.extend(lines[cursor:start])
        output.append("")
        cursor = end
    output.extend(lines[cursor:])
    return "\n".join(output)


def protected_tokens(text: str) -> Counter[str]:
    prose = prose_without_fences(text)
    values: Counter[str] = Counter()
    for label, pattern in (
        ("date", ISO_DATE),
        ("version", VERSION),
        ("number", NUMBER),
        ("identifier", TECHNICAL_IDENTIFIER),
        ("command", COMMAND),
    ):
        for match in pattern.finditer(prose):
            values[f"{label}:{match.group(0)}"] += 1
    return values


def inline_code(text: str) -> Counter[str]:
    return Counter(re.findall(r"`([^`\n]+)`", prose_without_fences(text)))


def link_targets(text: str) -> Counter[str]:
    return Counter(match.group("target").strip("<>") for match in MARKDOWN_LINK.finditer(prose_without_fences(text)))


def path_tokens(text: str) -> Counter[str]:
    prose = prose_without_fences(text)
    values = [value for value in PATH_TOKEN.findall(prose) if not value.startswith(("http/", "https/"))]
    values.extend(
        match.group(0)
        for match in re.finditer(r"(?<![\w./])[A-Za-z][A-Za-z0-9._-]*(?![\w/])", prose)
        if match.group(0).lower() in KNOWN_CODE_FILENAMES
    )
    return Counter(values)


def bullet_levels(text: str) -> list[int]:
    return [len(match.group("indent").replace("\t", "    ")) for match in BULLET.finditer(prose_without_fences(text))]


def table_shape(text: str) -> list[int]:
    shape: list[int] = []
    for line in prose_without_fences(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            shape.append(stripped.count("|"))
    return shape


def compare(label: str, original: Any, candidate: Any, result: ValidationResult) -> None:
    if original != candidate:
        result.errors.append(f"{label} mismatch")


def validate_text(original: str, candidate: str) -> ValidationResult:
    result = ValidationResult()
    if not candidate.strip():
        result.errors.append("candidate is empty")
        return result
    if len(candidate.encode("utf-8")) > MAX_FILE_SIZE:
        result.errors.append(f"candidate exceeds {MAX_FILE_SIZE} bytes")
        return result
    if original == candidate:
        result.errors.append("candidate is identical to original")
    compare("UTF-8 BOM", original.startswith("\ufeff"), candidate.startswith("\ufeff"), result)
    compare("newline style", newline_styles(original), newline_styles(candidate), result)
    compare("YAML frontmatter", frontmatter(original), frontmatter(candidate), result)
    compare("headings", HEADING.findall(original), HEADING.findall(candidate), result)
    compare("fenced code blocks", fenced_blocks(original), fenced_blocks(candidate), result)
    compare(
        "indented code blocks",
        indented_code_blocks(original),
        indented_code_blocks(candidate),
        result,
    )
    compare("inline code", inline_code(original), inline_code(candidate), result)
    compare("URLs", Counter(URL.findall(prose_without_fences(original))), Counter(URL.findall(prose_without_fences(candidate))), result)
    compare("Markdown link targets", link_targets(original), link_targets(candidate), result)
    compare("file paths", path_tokens(original), path_tokens(candidate), result)
    compare("protected tokens", protected_tokens(original), protected_tokens(candidate), result)
    compare("list hierarchy", bullet_levels(original), bullet_levels(candidate), result)
    compare("table structure", table_shape(original), table_shape(candidate), result)
    return result


def validate_files(original: Path, candidate: Path) -> ValidationResult:
    return validate_text(read_utf8(original), read_candidate(candidate))


def atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777
    descriptor, temporary = tempfile.mkstemp(prefix=".super-caveman-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def fsync_directory(directory: Path) -> None:
    """Persist directory-entry changes where the platform exposes directory fsync."""

    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def reserve_handoff_path(source: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{source.name}.super-caveman-handoff-",
        dir=source.parent,
    )
    os.close(descriptor)
    return Path(name)


def install_text_if_unchanged(source: Path, text: str, expected_sha: str, handoff_path: Path) -> None:
    """Install text without overwriting a path recreated by a concurrent writer."""

    mode = source.stat().st_mode & 0o777
    target_sha = sha256_bytes(text.encode("utf-8"))
    candidate_descriptor = -1
    candidate_path: Path | None = None
    handoff_has_source = False
    try:
        candidate_descriptor, candidate_name = tempfile.mkstemp(
            prefix=f".{source.name}.super-caveman-candidate-",
            dir=source.parent,
        )
        candidate_path = Path(candidate_name)
        with os.fdopen(candidate_descriptor, "w", encoding="utf-8", newline="") as stream:
            candidate_descriptor = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(candidate_path, mode)

        handoff_path.unlink()
        os.link(candidate_path, handoff_path)
        handoff_path.unlink()

        os.replace(source, handoff_path)
        handoff_has_source = True
        fsync_directory(source.parent)
        displaced_sha = sha256_path(handoff_path)
        if displaced_sha != expected_sha:
            try:
                os.link(handoff_path, source)
            except FileExistsError:
                raise GuardError(
                    "source changed at apply checkpoint and path was recreated; "
                    f"candidate not installed; displaced content preserved at {handoff_path}"
                )
            raise GuardError("source changed at apply checkpoint; candidate not installed")

        try:
            os.link(candidate_path, source)
        except FileExistsError as exc:
            raise GuardError("source path recreated during apply; candidate not installed") from exc
        fsync_directory(source.parent)
        if sha256_path(source) != target_sha:
            raise GuardError(f"source readback mismatch after install: {source}")
    except Exception as exc:
        if handoff_has_source:
            if source.is_file() and sha256_path(source) == target_sha:
                raise GuardError(
                    f"{exc}; installed target retained; displaced content preserved at {handoff_path}"
                ) from exc
            try:
                os.link(handoff_path, source)
            except FileExistsError:
                raise GuardError(
                    f"{exc}; source path recreated; displaced content preserved at {handoff_path}"
                ) from exc
            fsync_directory(source.parent)
        raise
    finally:
        if candidate_descriptor >= 0:
            os.close(candidate_descriptor)
        if candidate_path is not None:
            candidate_path.unlink(missing_ok=True)
        if not handoff_has_source:
            handoff_path.unlink(missing_ok=True)


def write_text_exclusive(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text_exclusive(path, text)


def validate_handoffs(payload: dict[str, Any], source: Path, *, allow_missing: bool = False) -> list[Path]:
    records = payload.get("handoffs")
    if not isinstance(records, list) or not records:
        raise GuardError("receipt has no recorded handoff evidence")
    paths: list[Path] = []
    seen: set[Path] = set()
    for record in records:
        if not isinstance(record, dict):
            raise GuardError("receipt handoff record is invalid")
        raw_path = record.get("path")
        expected_sha = record.get("expected_sha256")
        if not isinstance(raw_path, str) or not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha)):
            raise GuardError("receipt handoff record is incomplete")
        path = Path(raw_path)
        if (
            path.parent.resolve() != source.parent.resolve()
            or not path.name.startswith(f".{source.name}.super-caveman-handoff-")
            or path in seen
        ):
            raise GuardError(f"receipt handoff path is invalid: {path}")
        if not path.is_file() and allow_missing:
            seen.add(path)
            continue
        if not path.is_file():
            raise GuardError(f"recorded handoff is missing: {path}")
        if sha256_path(path) != expected_sha:
            raise GuardError(f"handoff changed after checkpoint; manual review required: {path}")
        seen.add(path)
        paths.append(path)
    return paths


def retire_restored_state(source: Path, backup: Path, receipt: Path) -> bool:
    if not backup.exists() and not receipt.exists():
        return False
    if not receipt.is_file():
        raise GuardError(f"incomplete backup state requires manual review: {backup.parent}")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    if payload.get("status") == "finalized":
        if backup.exists():
            raise GuardError(f"finalized state still has a backup: {backup.parent}")
        validate_handoffs(payload, source, allow_missing=True)
        if any(Path(record["path"]).exists() for record in payload["handoffs"]):
            raise GuardError(f"finalized state retains handoff evidence: {backup.parent}")
        receipt.unlink()
        return True
    if not backup.is_file():
        raise GuardError(f"incomplete backup state requires manual review: {backup.parent}")
    if (
        payload.get("schema") != "super-caveman.compression.v1"
        or payload.get("source") != str(source)
        or payload.get("status") != "restored"
    ):
        raise GuardError(f"active backup or receipt already exists: {backup.parent}")
    original_sha = payload.get("original_sha256")
    if sha256_path(source) != original_sha or sha256_path(backup) != original_sha:
        raise GuardError(f"restored backup state does not match source: {backup.parent}")
    validate_handoffs(payload, source)
    raise GuardError("restored compression state requires explicit finalize before another apply")


def finalize_state(source_arg: Path) -> dict[str, Any]:
    source = source_arg.expanduser().resolve()
    with operation_lock(source):
        if not source.is_file():
            raise GuardError(f"file not found: {source}")
        backup, receipt = backup_paths(source)
        if not receipt.is_file():
            raise GuardError(f"backup receipt not found: {receipt}")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            payload.get("schema") != "super-caveman.compression.v1"
            or payload.get("source") != str(source)
        ):
            raise GuardError("finalize receipt does not match source")
        if payload.get("status") == "finalized":
            if backup.exists():
                raise GuardError("finalized receipt still has a backup")
            validate_handoffs(payload, source, allow_missing=True)
            if any(Path(record["path"]).exists() for record in payload["handoffs"]):
                raise GuardError("finalized receipt still has handoff evidence")
            return {
                "schema": "super-caveman.compression.v1",
                "status": "finalized",
                "source": str(source),
                "original_sha256": payload.get("original_sha256"),
                "removed_handoffs": payload.get("removed_handoffs", 0),
                "receipt": str(receipt),
            }
        if payload.get("status") not in {"restored", "finalizing"}:
            raise GuardError("finalize requires a restored receipt")
        original_sha = payload.get("original_sha256")
        if sha256_path(source) != original_sha:
            raise GuardError("finalize requires source and backup to match the original hash")
        if backup.exists() and sha256_path(backup) != original_sha:
            raise GuardError("finalize requires source and backup to match the original hash")
        if payload.get("status") == "restored" and not backup.is_file():
            raise GuardError("restored finalize state is missing its backup")
        handoffs = validate_handoffs(
            payload,
            source,
            allow_missing=payload.get("status") == "finalizing",
        )
        payload["status"] = "finalizing"
        payload["finalizing_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(receipt, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        for handoff in handoffs:
            handoff.unlink(missing_ok=True)
        fsync_directory(source.parent)
        backup.unlink(missing_ok=True)
        payload["status"] = "finalized"
        payload["finalized_at"] = datetime.now(timezone.utc).isoformat()
        payload["removed_handoffs"] = len(payload["handoffs"])
        atomic_write(receipt, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return {**payload, "receipt": str(receipt)}


def apply_candidate(source_arg: Path, candidate_arg: Path) -> dict[str, Any]:
    source = source_arg.expanduser().resolve()
    with operation_lock(source):
        info = preflight(source)
        source = Path(info["source"])
        original_text = read_utf8(source)
        candidate_text = read_candidate(candidate_arg)
        result = validate_text(original_text, candidate_text)
        if not result.valid:
            raise GuardError("candidate validation failed: " + "; ".join(result.errors + result.warnings))

        backup = Path(info["backup"])
        receipt = Path(info["receipt"])
        retired_previous_state = retire_restored_state(source, backup, receipt)
        ensure_private_directory(backup.parent)

        original_sha = sha256_bytes(original_text.encode("utf-8"))
        compressed_sha = sha256_bytes(candidate_text.encode("utf-8"))
        if original_sha != info["sha256"] or sha256_path(source) != original_sha:
            raise GuardError("source changed during compression preflight; apply refused")
        handoff = reserve_handoff_path(source)
        payload = {
            "schema": "super-caveman.compression.v1",
            "status": "applied",
            "source": str(source),
            "backup": str(backup),
            "original_sha256": original_sha,
            "compressed_sha256": compressed_sha,
            "handoffs": [
                {"path": str(handoff), "expected_sha256": original_sha, "role": "apply-source"}
            ],
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
        source_replaced = False
        try:
            write_text_exclusive(backup, original_text)
            if read_utf8(backup) != original_text:
                raise GuardError(f"backup readback mismatch: {backup}")
            write_json_exclusive(receipt, payload)
            if sha256_path(source) != original_sha:
                raise GuardError("source changed before apply; apply refused")
            install_text_if_unchanged(source, candidate_text, original_sha, handoff)
            source_replaced = True
        except Exception as exc:
            current_sha = sha256_path(source) if source.is_file() else None
            preserve_state = current_sha != original_sha
            if preserve_state and backup.is_file() and receipt.is_file():
                payload["status"] = "conflict"
                payload["conflict_at"] = datetime.now(timezone.utc).isoformat()
                payload["conflict_error"] = str(exc)
                payload["current_sha256"] = current_sha
                atomic_write(
                    receipt,
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                )
            elif not source_replaced:
                receipt.unlink(missing_ok=True)
                backup.unlink(missing_ok=True)
                handoff.unlink(missing_ok=True)
            raise

        if sha256_path(source) != compressed_sha:
            raise GuardError(f"source readback mismatch after apply: {source}")
        return {
            **payload,
            "retired_previous_state": retired_previous_state,
            "validation": result.as_dict(),
            "receipt": str(receipt),
        }


def restore_source(source_arg: Path) -> dict[str, Any]:
    source = source_arg.expanduser().resolve()
    with operation_lock(source):
        if not source.exists() or not source.is_file():
            raise GuardError(f"file not found: {source}")
        backup, receipt = backup_paths(source)
        if not backup.is_file() or not receipt.is_file():
            raise GuardError(f"backup receipt not found: {receipt}")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if payload.get("schema") != "super-caveman.compression.v1" or payload.get("source") != str(source):
            raise GuardError(f"receipt does not match source: {receipt}")
        if payload.get("status") not in {"applied", "restored", "conflict"}:
            raise GuardError(f"receipt has invalid status: {receipt}")
        original_sha = payload.get("original_sha256")
        compressed_sha = payload.get("compressed_sha256")
        if sha256_path(backup) != original_sha:
            raise GuardError("backup hash mismatch; restore refused")

        current_sha = sha256_path(source)
        validate_handoffs(payload, source)
        recovered = current_sha == original_sha
        if payload.get("status") == "restored" and not recovered:
            raise GuardError("restored receipt does not match current source")
        if payload.get("status") == "conflict" and current_sha not in {original_sha, compressed_sha}:
            raise GuardError("conflict receipt requires manual review; current source matches neither receipt hash")
        if not recovered and current_sha != compressed_sha:
            raise GuardError("current source changed after compression; restore refused")
        if not recovered:
            handoff = reserve_handoff_path(source)
            previous_status = payload.get("status")
            payload["handoffs"].append(
                {"path": str(handoff), "expected_sha256": compressed_sha, "role": "restore-source"}
            )
            atomic_write(receipt, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            try:
                install_text_if_unchanged(source, read_utf8(backup), compressed_sha, handoff)
                validate_handoffs(payload, source)
            except Exception as exc:
                if not handoff.exists():
                    payload["handoffs"].pop()
                    payload["status"] = previous_status
                else:
                    payload["status"] = "conflict"
                    payload["conflict_at"] = datetime.now(timezone.utc).isoformat()
                    payload["conflict_error"] = str(exc)
                    payload["current_sha256"] = sha256_path(source) if source.is_file() else None
                atomic_write(
                    receipt,
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                )
                raise
        if sha256_path(source) != original_sha:
            raise GuardError(f"source readback mismatch after restore: {source}")

        payload["status"] = "restored"
        payload["recovered"] = recovered
        payload["restored_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(receipt, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return {**payload, "receipt": str(receipt)}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subcommands = command.add_subparsers(dest="command", required=True)
    preflight_parser = subcommands.add_parser("preflight", help="check whether a source is safe to compress")
    preflight_parser.add_argument("source", type=Path)
    preflight_parser.add_argument("--json", action="store_true")
    validate_parser = subcommands.add_parser("validate", help="compare source and compressed candidate")
    validate_parser.add_argument("source", type=Path)
    validate_parser.add_argument("candidate", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    apply_parser = subcommands.add_parser("apply", help="back up and install a valid candidate without clobbering a recreated path")
    apply_parser.add_argument("source", type=Path)
    apply_parser.add_argument("candidate", type=Path)
    apply_parser.add_argument("--json", action="store_true")
    restore_parser = subcommands.add_parser("restore", help="restore when current hash still matches the receipt")
    restore_parser.add_argument("source", type=Path)
    restore_parser.add_argument("--json", action="store_true")
    finalize_parser = subcommands.add_parser("finalize", help="remove a verified restored backup and its handoff evidence")
    finalize_parser.add_argument("source", type=Path)
    finalize_parser.add_argument("--json", action="store_true")
    return command


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "preflight":
            payload = preflight(args.source)
        elif args.command == "validate":
            preflight(args.source)
            result = validate_files(args.source.expanduser().resolve(), args.candidate.expanduser().resolve())
            payload = result.as_dict()
            emit(payload, args.json)
            return 0 if result.valid else 2
        elif args.command == "apply":
            payload = apply_candidate(args.source, args.candidate)
        elif args.command == "restore":
            payload = restore_source(args.source)
        else:
            payload = finalize_state(args.source)
        emit(payload, args.json)
        return 0
    except (GuardError, OSError, json.JSONDecodeError) as exc:
        error = {"status": "blocked", "error": str(exc)}
        emit(error, getattr(args, "json", False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

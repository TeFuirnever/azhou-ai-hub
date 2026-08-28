"""Shared path and conservative migration primitives for Azhou runtime state."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable


SCHEMA_VERSION = "azhou.runtime-state.v1"
MIGRATION_RECEIPT = ".migration-receipt.json"
_NAMESPACE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class StateError(RuntimeError):
    """Raised when a runtime-state path or migration cannot be proven safe."""


def _canonical_root(root: Path | str) -> Path:
    raw = Path(root).expanduser().absolute()
    if raw.is_symlink():
        raise StateError(f"authorized root cannot be a symlink: {raw}")
    if raw.exists() and not raw.is_dir():
        raise StateError(f"authorized root is not a directory: {raw}")
    return raw.resolve(strict=False)


def _validate_namespace(namespace: str) -> str:
    if not _NAMESPACE.fullmatch(namespace):
        raise StateError(f"invalid Azhou runtime-state namespace: {namespace!r}")
    return namespace


def _relative_parts(*parts: str | Path) -> tuple[str, ...]:
    flattened: list[str] = []
    for value in parts:
        path = Path(value)
        if path.is_absolute():
            raise StateError(f"runtime-state path must be relative: {value}")
        for part in path.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                raise StateError(f"runtime-state path cannot traverse upward: {value}")
            flattened.append(part)
    return tuple(flattened)


def _contained_path(root: Path, parts: Iterable[str]) -> Path:
    candidate = root
    for part in parts:
        candidate /= part
        if candidate.is_symlink():
            raise StateError(f"runtime-state path contains a symlink: {candidate}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StateError(f"runtime-state path escapes authorized root: {candidate}") from exc
    return resolved


def relative_path(root: Path | str, value: str | Path) -> Path:
    """Resolve one project-relative path without following a contained symlink."""

    canonical_root = _canonical_root(root)
    return _contained_path(canonical_root, _relative_parts(value))


def state_path(root: Path | str, namespace: str, *parts: str | Path) -> Path:
    """Resolve `.azhou/<namespace>/...` below one explicit authorized root."""

    canonical_root = _canonical_root(root)
    namespace = _validate_namespace(namespace)
    return _contained_path(
        canonical_root,
        (".azhou", namespace, *_relative_parts(*parts)),
    )


def ensure_private_directory(path: Path | str, *, root: Path | str) -> Path:
    """Create a contained directory tree with user-only permissions."""

    canonical_root = _canonical_root(root)
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raw = canonical_root / raw
    try:
        relative = raw.absolute().relative_to(canonical_root)
    except ValueError as exc:
        raise StateError(f"private directory escapes authorized root: {raw}") from exc
    destination = _contained_path(canonical_root, relative.parts)
    cursor = canonical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise StateError(f"private directory contains a symlink: {cursor}")
        if cursor.exists() and not cursor.is_dir():
            raise StateError(f"private directory ancestor is not a directory: {cursor}")
        cursor.mkdir(exist_ok=True, mode=0o700)
        try:
            cursor.chmod(0o700)
        except OSError as exc:
            raise StateError(f"cannot secure private directory: {cursor}") from exc
    return destination


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _inventory(directory: Path, *, omit_receipt: bool = False) -> list[dict[str, Any]]:
    if directory.is_symlink() or not directory.is_dir():
        raise StateError(f"migration source must be a non-symlink directory: {directory}")
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
        relative = path.relative_to(directory).as_posix()
        if omit_receipt and relative == MIGRATION_RECEIPT:
            continue
        if path.is_symlink():
            raise StateError(f"migration content cannot be a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise StateError(f"migration content must be a regular file: {path}")
        content = path.read_bytes()
        rows.append({"path": relative, "sha256": _digest_bytes(content), "size": len(content)})
    return rows


def _normalized_sources(values: Iterable[str | Path]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        path = Path(value)
        parts = _relative_parts(path)
        if not parts:
            raise StateError("compatibility source cannot be the authorized root")
        normalized.append(Path(*parts).as_posix())
    return tuple(sorted(set(normalized)))


def _plan_id(payload: dict[str, Any]) -> str:
    return _digest_bytes(_canonical_json(payload))


def plan_directory_migration(
    root: Path | str,
    *,
    namespace: str,
    source: str | Path,
    allowed_sources: Iterable[str | Path],
    target_parts: Iterable[str | Path] = (),
) -> dict[str, Any]:
    """Build a stable, read-only plan for one recognized compatibility source."""

    canonical_root = _canonical_root(root)
    namespace = _validate_namespace(namespace)
    allowed = _normalized_sources(allowed_sources)
    source_parts = _relative_parts(source)
    source_relative = Path(*source_parts).as_posix()
    if source_relative not in allowed:
        raise StateError(f"unrecognized compatibility source: {source_relative}")
    source_directory = _contained_path(canonical_root, source_parts)
    contents = _inventory(source_directory)
    target_part_values = tuple(target_parts)
    target = state_path(canonical_root, namespace, *target_part_values)
    if target == source_directory:
        raise StateError("migration source and target must differ")

    conflicts: list[str] = []
    status = "planned"
    plan_binding = {
        "schemaVersion": SCHEMA_VERSION,
        "root": canonical_root.as_posix(),
        "namespace": namespace,
        "source": source_directory.as_posix(),
        "sourceRelative": source_relative,
        "target": target.as_posix(),
        "targetParts": [Path(value).as_posix() for value in target_part_values],
        "allowedSources": list(allowed),
        "contents": contents,
        "conflicts": conflicts,
        "sourcePreserved": True,
    }
    plan_id = _plan_id(plan_binding)

    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise StateError(f"migration target must be a non-symlink directory: {target}")
        if _inventory(target, omit_receipt=True) != contents:
            conflicts.append("target content differs from the compatibility source")
        receipt_path = target / MIGRATION_RECEIPT
        if receipt_path.is_symlink() or not receipt_path.is_file():
            conflicts.append("target migration receipt is missing or unsafe")
        else:
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                conflicts.append("target migration receipt is invalid")
            else:
                if receipt.get("planId") != plan_id:
                    conflicts.append("target migration receipt does not match the source plan")
        status = "conflict" if conflicts else "already-current"

    plan_binding["conflicts"] = conflicts
    if conflicts:
        plan_id = _plan_id(plan_binding)
    return {**plan_binding, "planId": plan_id, "status": status, "applied": False}


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink():
        raise StateError(f"migration receipt cannot be a symlink: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replan(plan: dict[str, Any]) -> dict[str, Any]:
    return plan_directory_migration(
        Path(plan["root"]),
        namespace=str(plan["namespace"]),
        source=str(plan["sourceRelative"]),
        allowed_sources=tuple(plan["allowedSources"]),
        target_parts=tuple(plan["targetParts"]),
    )


def apply_directory_migration(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply an unchanged plan by staging and atomically publishing one directory."""

    if plan.get("schemaVersion") != SCHEMA_VERSION:
        raise StateError("unsupported runtime-state migration plan")
    if plan.get("status") == "conflict":
        raise StateError("runtime-state migration plan has conflicts")
    current = _replan(plan)
    if current["planId"] != plan.get("planId"):
        raise StateError("runtime-state migration plan changed; run dry-run again")
    if current["status"] == "already-current":
        return current
    if current["status"] != "planned":
        raise StateError(f"runtime-state migration is not applicable: {current['status']}")

    root = Path(current["root"])
    source = Path(current["source"])
    target = Path(current["target"])
    ensure_private_directory(target.parent, root=root)
    stage = Path(tempfile.mkdtemp(prefix=f".{current['namespace']}-migration-", dir=target.parent))
    try:
        shutil.rmtree(stage)
        shutil.copytree(source, stage, symlinks=False)
        if _inventory(stage) != current["contents"] or _inventory(source) != current["contents"]:
            raise StateError("runtime-state migration source changed while copying; run dry-run again")
        for path in stage.rglob("*"):
            path.chmod(0o700 if path.is_dir() else 0o600)
        stage.chmod(0o700)
        receipt = {
            key: current[key]
            for key in (
                "schemaVersion",
                "root",
                "namespace",
                "source",
                "sourceRelative",
                "target",
                "targetParts",
                "allowedSources",
                "contents",
                "sourcePreserved",
                "planId",
            )
        }
        receipt.update({"status": "migrated", "applied": True})
        _write_receipt(stage / MIGRATION_RECEIPT, receipt)
        os.replace(stage, target)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return {**current, "status": "migrated", "applied": True}


def verify_directory_migration(plan: dict[str, Any]) -> dict[str, Any]:
    """Verify the target, receipt, contents, and preserved source for one plan."""

    current = _replan(plan)
    if current["status"] != "already-current" or current["planId"] != plan.get("planId"):
        raise StateError("runtime-state migration verification failed")
    if not Path(current["source"]).is_dir():
        raise StateError("runtime-state migration source is no longer preserved")
    return {**current, "status": "verified"}

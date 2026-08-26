#!/usr/bin/env python3
"""Harness-neutral setup, diagnostics, information, and verification for Azhou AI Hub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import nullcontext
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
COMMANDS = ["doctor", "info", "setup", "verify", "version"]
RECEIPT_SCHEMA = "azhou-ai-hub.install-receipt.v2"
LEGACY_RECEIPT_SCHEMA = "azhou-ai-hub.install-receipt.v1"
IGNORED_PACKAGE_PARTS = {".git", ".omc", ".omx", ".venv", "__pycache__", "node_modules"}


class PackageError(RuntimeError):
    """Raised when a source package cannot be copied or compared safely."""


def _setup_failure(target: Path, mode: str, error: str) -> dict[str, Any]:
    return {
        "schema_version": "azhou-ai-hub.setup.v1",
        "status": "fail",
        "mode": mode,
        "target": str(target),
        "applied": False,
        "error": error,
        "skills": [],
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt_digest(receipt: dict[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("integrity_digest", None)
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(receipt)
    payload["integrity_digest"] = _receipt_digest(payload)
    fd, stage_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    stage = Path(stage_name)
    try:
        os.chmod(stage, 0o600)
        with stage.open("wb") as handle:
            handle.write(_canonical_json(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, path)
    finally:
        try:
            stage.unlink(missing_ok=True)
        except OSError:
            pass


def _load_receipt(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"cannot read receipt: {exc}"
    if not isinstance(payload, dict) or payload.get("schema") not in {LEGACY_RECEIPT_SCHEMA, RECEIPT_SCHEMA}:
        return None, "receipt_invalid: unsupported receipt schema"
    if payload.get("integrity_digest") != _receipt_digest(payload):
        return None, "receipt_invalid: integrity digest mismatch"
    for key in ("target", "mode", "skills", "source_root"):
        if key not in payload:
            return None, f"receipt_invalid: missing {key}"
    if any(not isinstance(payload.get(key), str) or not payload.get(key) for key in ("target", "mode", "source_root")):
        return None, "receipt_invalid: malformed path or mode field"
    if payload["mode"] not in {"link", "copy"} or not isinstance(payload["skills"], list) or len(payload["skills"]) != 1:
        return None, "receipt_invalid: malformed fields"
    item = payload["skills"][0]
    if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item.get(key) for key in ("name", "source", "source_root", "source_digest", "destination", "installed_digest")):
        return None, "receipt_invalid: malformed skill item"
    if payload["schema"] == RECEIPT_SCHEMA:
        if _receipt_identity(item.get("installed_identity")) is None:
            return None, "receipt_invalid: malformed installed identity"
    elif item.get("installed_identity") != payload["mode"]:
        return None, "receipt_invalid: malformed legacy installed identity"
    return payload, None


def _receipt_path_error(path: Path, target: Path) -> str | None:
    target = target.expanduser().resolve()
    state_root = target / ".azhou-ai-hub"
    allowed = state_root / "receipts"
    try:
        raw = path.expanduser()
        if raw.is_symlink() or allowed.is_symlink() or state_root.is_symlink():
            return "receipt path contains a symlink"
        if state_root.exists() and not state_root.is_dir():
            return "target/.azhou-ai-hub exists and is not a directory"
        if allowed.exists() and not allowed.is_dir():
            return "target/.azhou-ai-hub/receipts exists and is not a directory"
        resolved = raw.resolve(strict=False)
        if resolved.parent != allowed.resolve(strict=False):
            return "receipt path must be directly inside target/.azhou-ai-hub/receipts"
    except OSError as exc:
        return str(exc)
    return None


def _mutation_lock(target: Path):
    lock = target.expanduser().resolve() / ".azhou-ai-hub" / "mutation.lock"
    class Lock:
        def __enter__(self):
            try:
                lock.parent.mkdir(parents=True, exist_ok=True)
                lock.mkdir()
            except OSError as exc:
                raise PackageError(f"mutation lock unavailable: {exc}") from exc
            return self
        def __exit__(self, *_args):
            try:
                lock.rmdir()
            except OSError:
                pass
    return Lock()


def _new_receipt(root: Path, target: Path, mode: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "operation_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "repo_commit": revision_info(root)["commit"],
        "source_root": str((root / "skills").resolve()),
        "target_requested": str(target),
        "target": str(target.resolve()),
        "mode": mode,
        "skills": [
            {
                "name": row["name"],
                "source": row["source"],
                "source_root": str((root / "skills").resolve()),
                "source_digest": row.get("source_digest", ""),
                "destination": row["destination"],
                "installed_identity": _identity_payload(_path_identity(Path(row["destination"]))),
                "installed_digest": row.get("installed_digest", row.get("source_digest", "")),
            }
            for row in rows
            if row.get("source")
        ],
    }


def canonical_skills(root: Path = ROOT) -> list[str]:
    """Return canonical skill names from the repository package surface."""
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(path.parent.name for path in skills_root.glob("*/SKILL.md") if path.is_file())


def _git_command(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def revision_info(root: Path = ROOT) -> dict[str, Any]:
    status = _git_command(root, "status", "--porcelain")
    return {
        "commit": _git_command(root, "rev-parse", "HEAD") or "unknown",
        "branch": _git_command(root, "branch", "--show-current") or "unknown",
        "dirty": None if status is None else bool(status),
    }


def info_payload(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": "azhou-ai-hub.info.v1",
        "project": "azhou-ai-hub",
        "repository": str(root.resolve()),
        "revision": revision_info(root),
        "python": {
            "executable": sys.executable,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "minimum": ".".join(str(part) for part in MIN_PYTHON),
        },
        "installable_skills": canonical_skills(root),
        # Keep this list limited to the five portable foundation commands. The
        # receipt-owned lifecycle verbs are intentionally a separate contract.
        "primary_commands": COMMANDS,
        # Backward-compatible v1 alias. Remove only through an explicitly
        # approved schema migration.
        "commands": COMMANDS,
        "verification_command": "python3 scripts/verify.py",
        "support_matrix": "docs/support-matrix.md",
    }


def version_payload(root: Path = ROOT) -> dict[str, Any]:
    revision = revision_info(root)
    return {
        "schema_version": "azhou-ai-hub.version.v1",
        "commit": revision["commit"],
        "branch": revision["branch"],
        "dirty": revision["dirty"],
        "release_version": None,
        "version_authority": "git revision; no installed release metadata is claimed",
    }


def _is_package_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return not any(part in IGNORED_PACKAGE_PARTS for part in relative.parts) and path.name != ".DS_Store"


def _package_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in source.rglob("*"):
        if not _is_package_path(path, source):
            continue
        if path.is_symlink():
            raise PackageError(f"package contains unsupported symlink: {path.relative_to(source)}")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(source).as_posix())


def _package_digest(source: Path, *, executable_aware: bool) -> str:
    digest = hashlib.sha256()
    for path in _package_files(source):
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if executable_aware:
            digest.update(b"executable" if path.stat().st_mode & 0o111 else b"regular")
            digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def package_digest(source: Path) -> str:
    return _package_digest(source, executable_aware=True)


def _legacy_package_digest(source: Path) -> str:
    """Reproduce the v1 receipt digest for an explicit one-way upgrade."""
    return _package_digest(source, executable_aware=False)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _target_root_error(target: Path) -> str | None:
    cursor = target
    while not cursor.exists() and cursor != cursor.parent:
        cursor = cursor.parent
    if cursor.exists() and not cursor.is_dir():
        if cursor == target:
            return "target root exists and is not a directory"
        return f"target ancestor is not a directory: {cursor}"
    return None


def canonical_source(root: Path, name: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise PackageError(f"invalid canonical skill name: {name!r}")
    skills_root = (root / "skills").resolve()
    source = (skills_root / name).resolve()
    try:
        source.relative_to(skills_root)
    except ValueError as exc:
        raise PackageError(f"skill source escapes canonical root: {name!r}") from exc
    return source


def inspect_installation(source: Path, destination: Path, mode: str) -> tuple[str, str]:
    if not (source / "SKILL.md").is_file():
        return "conflict", "canonical source package is missing SKILL.md"
    if destination.is_symlink():
        if mode == "link" and _same_resolved_path(source, destination):
            return "current", "canonical symlink already installed"
        return "conflict", f"destination symlink resolves to {destination.resolve()}"
    if not destination.exists():
        return "planned", f"will {mode} canonical package"
    if not destination.is_dir():
        return "conflict", "destination exists and is not a directory"
    if mode == "copy":
        try:
            if package_digest(source) == package_digest(destination):
                return "current", "installed copy matches canonical package digest"
        except (OSError, PackageError) as exc:
            return "conflict", f"cannot compare package digest: {exc}"
    return "conflict", "destination exists with different or unowned content"


def _path_identity(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.lstat()
    except OSError:
        return None
    return stat.st_dev, stat.st_ino, stat.st_mode


def _identity_payload(identity: tuple[int, int, int] | None) -> dict[str, int] | None:
    if identity is None:
        return None
    return {"device": identity[0], "inode": identity[1], "mode": identity[2]}


def _receipt_identity(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, dict):
        return None
    fields = value.get("device"), value.get("inode"), value.get("mode")
    if any(not isinstance(field, int) or isinstance(field, bool) for field in fields):
        return None
    device, inode, mode = fields
    if device < 0 or inode <= 0 or mode <= 0:
        return None
    return device, inode, mode


def _remove_exact_installation(
    source: Path,
    destination: Path,
    mode: str,
    expected_identity: tuple[int, int, int] | None = None,
) -> bool:
    """Remove only an artifact that still exactly matches the canonical source."""
    try:
        if expected_identity is not None and _path_identity(destination) != expected_identity:
            return False
        status, _ = inspect_installation(source, destination, mode)
        if status != "current":
            return False
        if expected_identity is not None and _path_identity(destination) != expected_identity:
            return False
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    except (OSError, PackageError):
        return False
    return True


def _copy_package(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    try:
        for path in _package_files(source):
            relative = path.relative_to(source)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target, follow_symlinks=False)
        os.replace(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def setup_skills(
    *,
    root: Path,
    target: Path,
    skills: Iterable[str],
    mode: str,
    dry_run: bool,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"copy", "link"}:
        raise ValueError(f"unsupported setup mode: {mode}")

    target = target.expanduser().resolve()
    if receipt_path is not None:
        receipt_error = _receipt_path_error(receipt_path, target)
        if receipt_error:
            return _setup_failure(target, mode, receipt_error)
    target_error = _target_root_error(target)
    if target_error:
        return _setup_failure(target, mode, target_error)
    rows: list[dict[str, str]] = []
    for name in sorted(set(skills)):
        try:
            source = canonical_source(root, name)
        except PackageError as exc:
            rows.append(
                {
                    "name": name,
                    "status": "conflict",
                    "details": str(exc),
                    "source": "",
                    "destination": str(target / name),
                }
            )
            continue
        destination = target / name
        status, details = inspect_installation(source, destination, mode)
        rows.append(
            {
                "name": name,
                "status": status,
                "details": details,
                "source": str(source),
                "destination": str(destination),
                "source_digest": package_digest(source) if source.exists() else "",
            }
        )

    receipt_current = False
    if receipt_path is not None:
        receipt_exists = receipt_path.expanduser().exists()
        current_rows = [row for row in rows if row["status"] == "current"]
        planned_rows = [row for row in rows if row["status"] == "planned"]
        if current_rows and not receipt_exists:
            for row in current_rows:
                row["status"] = "conflict"
                row["details"] = "managed setup cannot adopt an existing installation without its receipt"
        elif planned_rows and receipt_exists:
            for row in planned_rows:
                row["status"] = "conflict"
                row["details"] = "managed receipt already exists; use repair or uninstall"
        elif current_rows and receipt_exists:
            receipt, receipt_error = _load_receipt(receipt_path)
            if (
                receipt_error
                or receipt is None
                or Path(receipt["target"]).resolve() != target
                or Path(receipt["source_root"]).resolve() != (root / "skills").resolve()
                or receipt["mode"] != mode
            ):
                for row in current_rows:
                    row["status"] = "conflict"
                    row["details"] = receipt_error or "managed receipt does not match the current installation"
            else:
                state, details = _receipt_item_state(receipt["skills"][0], mode, target, root)
                if state != "current":
                    for row in current_rows:
                        row["status"] = "conflict"
                        row["details"] = details
                else:
                    receipt_current = True

    if any(row["status"] == "conflict" for row in rows):
        return {
            "schema_version": "azhou-ai-hub.setup.v1",
            "status": "fail",
            "mode": mode,
            "target": str(target),
            "applied": False,
            "skills": rows,
        }

    if dry_run:
        return {
            "schema_version": "azhou-ai-hub.setup.v1",
            "status": "dry_run",
            "mode": mode,
            "target": str(target),
            "applied": False,
            "skills": rows,
        }

    if receipt_current:
        return {
            "schema_version": "azhou-ai-hub.setup.v1",
            "status": "pass",
            "mode": mode,
            "target": str(target),
            "applied": False,
            "receipt": str(receipt_path.expanduser().resolve()),
            "skills": rows,
        }

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _setup_failure(target, mode, f"cannot create target root: {exc}")
    created: list[tuple[Path, tuple[int, int, int]]] = []
    rollback_failed = False
    for row in rows:
        if row["status"] != "planned":
            continue
        source = Path(row["source"])
        destination = Path(row["destination"])
        try:
            if mode == "link":
                destination.symlink_to(source, target_is_directory=True)
            else:
                _copy_package(source, destination)
            identity = _path_identity(destination)
            if identity is None:
                raise PackageError("installed artifact identity cannot be proven")
            created.append((destination, identity))
        except (OSError, PackageError) as exc:
            row["status"] = "error"
            row["details"] = str(exc)
            for created_path, identity in reversed(created):
                created_row = next(item for item in rows if Path(item["destination"]) == created_path)
                if not _remove_exact_installation(Path(created_row["source"]), created_path, mode, identity):
                    rollback_failed = True
            break
        row["status"] = "installed"
        row["details"] = f"canonical package {mode} installed"

    failed = any(row["status"] in {"conflict", "error"} for row in rows)
    payload = {
        "schema_version": "azhou-ai-hub.setup.v1",
        "status": "fail" if failed else "pass",
        "mode": mode,
        "target": str(target),
        "applied": True,
        "skills": rows,
    }
    if failed:
        payload["status"] = "partial" if rollback_failed else "rolled_back"
        payload["applied"] = False
        return payload
    if receipt_path is not None:
        try:
            receipt = _new_receipt(root, target, mode, rows)
            for item in receipt["skills"]:
                state, details = _receipt_item_state(item, mode, target, root)
                if state != "current":
                    raise PackageError(f"installed artifact verification failed: {details}")
                item["installed_digest"] = item["source_digest"] if mode == "link" else package_digest(Path(item["destination"]))
            _write_receipt(receipt_path, receipt)
            payload["receipt"] = str(receipt_path.expanduser().resolve())
        except (OSError, PackageError) as exc:
            rollback_failed = False
            for row in rows:
                if row["status"] != "installed":
                    continue
                item = Path(row["destination"])
                identity = next((value for path, value in created if path == item), None)
                if not _remove_exact_installation(Path(row["source"]), item, mode, identity):
                    rollback_failed = True
            payload["status"] = "partial" if rollback_failed else "rolled_back"
            payload["applied"] = False
            payload["error"] = f"managed receipt finalization failed: {exc}"
    return payload


def _check(name: str, status: str, details: str) -> dict[str, str]:
    return {"name": name, "status": status, "details": details}


def _receipt_item_state(
    item: dict[str, Any],
    mode: str,
    target: Path,
    root: Path,
    *,
    legacy_receipt: bool = False,
) -> tuple[str, str]:
    try:
        name = item["name"]
        if name not in canonical_skills(root):
            return "conflict", "receipt skill is not canonical"
        source = canonical_source(root, name)
        destination = (target / name).absolute()
        expected = (target / name).absolute()
        if Path(item.get("source", "")).expanduser().resolve() != source or Path(item.get("destination", "")).expanduser().absolute() != expected:
            return "conflict", "receipt source or destination does not match canonical identity"
    except (KeyError, OSError, ValueError) as exc:
        return "conflict", f"receipt_invalid: {exc}"
    digest_package = _legacy_package_digest if legacy_receipt else package_digest
    if not source.is_dir() or digest_package(source) != item.get("source_digest"):
        return "conflict", "source digest or path no longer matches receipt"
    raw = Path(item["destination"])
    if not raw.exists() and not raw.is_symlink():
        return "missing", "managed artifact is absent"
    installed_identity = _receipt_identity(item.get("installed_identity"))
    if installed_identity is None and not legacy_receipt:
        return "conflict", "receipt lacks installed object identity; run repair --apply to upgrade it"
    if installed_identity is not None and _path_identity(raw) != installed_identity:
        return "conflict", "managed artifact identity differs from receipt"
    if mode == "link":
        return ("current", "exact managed symlink") if raw.is_symlink() and _same_resolved_path(source, raw) else ("conflict", "destination is not the exact managed symlink")
    if raw.is_symlink() or not raw.is_dir():
        return "conflict", "managed copy is not a directory"
    return ("current", "managed copy matches receipt") if digest_package(raw) == item.get("installed_digest", item.get("source_digest")) else ("conflict", "managed copy digest differs")


def _lifecycle_report(status: str, rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    payload = {"schema_version": "azhou-ai-hub.lifecycle.v1", "status": status, "applied": status in {"pass", "partial"}, "skills": rows}
    payload.update(extra)
    return payload


def repair_receipt(*, receipt_path: Path, target: Path, root: Path, apply: bool) -> dict[str, Any]:
    path_error = _receipt_path_error(receipt_path, target)
    if path_error:
        return _lifecycle_report("fail", [], error=path_error)
    receipt, error = _load_receipt(receipt_path)
    if error:
        return _lifecycle_report("fail", [], error=error)
    target = target.expanduser().resolve()
    if Path(receipt["target"]).resolve() != target:
        return _lifecycle_report("fail", [], error="receipt_invalid: target mismatch")
    if Path(receipt["source_root"]).resolve() != (root / "skills").resolve():
        return _lifecycle_report("fail", [], error="receipt_invalid: source root mismatch")
    legacy_receipt = receipt["schema"] == LEGACY_RECEIPT_SCHEMA
    rows = []
    for item in receipt["skills"]:
        state, details = _receipt_item_state(
            item,
            receipt["mode"],
            target,
            root,
            legacy_receipt=legacy_receipt,
        )
        if legacy_receipt and state == "current":
            state, details = "upgrade_planned", "will record the current exact artifact identity in a v2 receipt"
        elif state == "missing":
            state = "planned"
        rows.append({"name": item.get("name", ""), "status": state, "details": details, "destination": str(target / item.get("name", ""))})
    if any(row["status"] == "conflict" for row in rows):
        return _lifecycle_report("fail", rows)
    if not apply:
        return _lifecycle_report("dry_run", rows)
    for row, item in zip(rows, receipt["skills"]):
        if row["status"] == "upgrade_planned":
            try:
                source = canonical_source(root, item["name"])
                destination = Path(row["destination"])
                identity = _path_identity(destination)
                if identity is None:
                    raise PackageError("managed artifact identity cannot be proven")
                item["source_digest"] = package_digest(source)
                item["installed_digest"] = (
                    item["source_digest"]
                    if receipt["mode"] == "link"
                    else package_digest(destination)
                )
                item["installed_identity"] = _identity_payload(identity)
                receipt["schema"] = RECEIPT_SCHEMA
                state, details = _receipt_item_state(item, receipt["mode"], target, root)
                if state != "current":
                    raise PackageError(f"receipt upgrade verification failed: {details}")
                _write_receipt(receipt_path, receipt)
            except (OSError, PackageError) as exc:
                row["status"], row["details"] = "fail", str(exc)
                return _lifecycle_report("fail", rows, error="receipt upgrade failed")
            row["status"] = "upgraded"
            continue
        if row["status"] != "planned":
            continue
        source, destination = canonical_source(root, item["name"]), target / item["name"]
        identity = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source, target_is_directory=True) if receipt["mode"] == "link" else _copy_package(source, destination)
            identity = _path_identity(destination)
            if identity is None:
                raise PackageError("repaired artifact identity cannot be proven")
            item["installed_identity"] = _identity_payload(identity)
            item["source_digest"] = package_digest(source)
            item["installed_digest"] = item["source_digest"] if receipt["mode"] == "link" else package_digest(destination)
            receipt["schema"] = RECEIPT_SCHEMA
            state, details = _receipt_item_state(item, receipt["mode"], target, root)
            if state != "current":
                raise PackageError(f"repair verification failed: {details}")
            _write_receipt(receipt_path, receipt)
            row["status"] = "repaired"
        except (OSError, PackageError) as exc:
            restored = _remove_exact_installation(
                source,
                destination,
                receipt["mode"],
                identity,
            )
            row["status"], row["details"] = "fail", str(exc)
            return _lifecycle_report("rolled_back" if restored else "partial", rows, error="repair failed verification")
    return _lifecycle_report("pass", rows)


def uninstall_receipt(*, receipt_path: Path, target: Path, root: Path, apply: bool) -> dict[str, Any]:
    path_error = _receipt_path_error(receipt_path, target)
    if path_error:
        return _lifecycle_report("fail", [], error=path_error)
    receipt, error = _load_receipt(receipt_path)
    if error:
        return _lifecycle_report("fail", [], error=error)
    target = target.expanduser().resolve()
    if Path(receipt["target"]).resolve() != target:
        return _lifecycle_report("fail", [], error="receipt_invalid: target mismatch")
    if Path(receipt["source_root"]).resolve() != (root / "skills").resolve():
        return _lifecycle_report("fail", [], error="receipt_invalid: source root mismatch")
    rows = []
    identities: dict[str, tuple[int, int, int]] = {}
    for item in receipt["skills"]:
        state, details = _receipt_item_state(item, receipt["mode"], target, root)
        if state == "current":
            identity = _receipt_identity(item.get("installed_identity"))
            if identity is None:
                state, details = "conflict", "managed artifact identity cannot be proven"
            else:
                identities[item["name"]] = identity
        rows.append({"name": item.get("name", ""), "status": "already_absent" if state == "missing" else state, "details": details, "destination": str(target / item.get("name", ""))})
    if any(row["status"] == "conflict" for row in rows):
        return _lifecycle_report("fail", rows)
    if not apply:
        return _lifecycle_report("dry_run", rows)
    for row in rows:
        if row["status"] == "current":
            item = Path(row["destination"])
            source = canonical_source(root, row["name"])
            try:
                if not _remove_exact_installation(source, item, receipt["mode"], identities[row["name"]]):
                    raise PackageError("managed artifact identity changed before uninstall")
                row["status"] = "removed"
            except (OSError, PackageError) as exc:
                row["status"], row["details"] = "fail", str(exc)
                return _lifecycle_report("partial", rows, error="uninstall failed")
    return _lifecycle_report("pass", rows)


def migrate_receipt(*, receipt_path: Path, target: Path, root: Path, mode: str, apply: bool) -> dict[str, Any]:
    path_error = _receipt_path_error(receipt_path, target)
    if path_error:
        return _lifecycle_report("fail", [], error=path_error)
    receipt, error = _load_receipt(receipt_path)
    if error:
        return _lifecycle_report("fail", [], error=error)
    target = target.expanduser().resolve()
    if Path(receipt["target"]).resolve() != target:
        return _lifecycle_report("fail", [], error="receipt_invalid: target mismatch")
    if Path(receipt["source_root"]).resolve() != (root / "skills").resolve():
        return _lifecycle_report("fail", [], error="receipt_invalid: source root mismatch")
    if receipt["mode"] == mode:
        rows = []
        for item in receipt["skills"]:
            state, details = _receipt_item_state(item, receipt["mode"], target, root)
            rows.append({"name": item["name"], "status": state, "details": details})
        if any(row["status"] != "current" for row in rows):
            return _lifecycle_report("fail", rows, error="installation is not exact and current")
        return _lifecycle_report("dry_run" if not apply else "pass", rows, details="already in requested mode")
    if len(receipt["skills"]) != 1:
        return _lifecycle_report("fail", [], error="migrate supports exactly one skill")
    old_target = Path(receipt["target"]).resolve()
    old_rows = []
    for item in receipt["skills"]:
        state, details = _receipt_item_state(item, receipt["mode"], old_target, root)
        old_rows.append({"name": item["name"], "status": state, "details": details})
    if any(row["status"] != "current" for row in old_rows):
        return _lifecycle_report("fail", old_rows, error="old installation is not exact and current")
    new_items = []
    for item in receipt["skills"]:
        destination = target / item["name"]
        state, details = inspect_installation(Path(item["source"]), destination, mode)
        if destination.is_symlink() or destination.is_dir():
            state, details = "planned", "will replace exact managed artifact"
        if state not in {"planned", "current"}:
            return _lifecycle_report("fail", [{"name": item["name"], "status": state, "details": details}])
        new_items.append({"name": item["name"], "source": item["source"], "source_digest": item["source_digest"], "destination": str(destination), "status": state})
    if not apply:
        return _lifecycle_report("dry_run", new_items)
    created: list[tuple[Path, tuple[int, int, int]]] = []
    backups: list[tuple[Path, Path, tuple[int, int, int]]] = []
    installed_identities: dict[Path, tuple[int, int, int]] = {}
    try:
        target.mkdir(parents=True, exist_ok=True)
        for item in new_items:
            destination = Path(item["destination"])
            stage = destination.parent / f".{destination.name}.migrate-{uuid.uuid4().hex}"
            stage.symlink_to(item["source"], target_is_directory=True) if mode == "link" else _copy_package(Path(item["source"]), stage)
            stage_identity = _path_identity(stage)
            if stage_identity is None:
                raise PackageError("staged artifact identity cannot be proven")
            created.append((stage, stage_identity))
            if mode == "link" and not _same_resolved_path(Path(item["source"]), stage):
                raise PackageError("new symlink verification failed")
            if mode == "copy" and package_digest(stage) != item["source_digest"]:
                raise PackageError("new copy verification failed")
            backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
            old_identity = _path_identity(destination)
            if old_identity is None:
                raise PackageError("old artifact identity cannot be proven")
            os.replace(destination, backup)
            backups.append((backup, destination, old_identity))
            os.replace(stage, destination)
            installed_identities[destination] = stage_identity
            current, current_details = _receipt_item_state(
                {
                    **item,
                    "source": item["source"],
                    "destination": str(destination),
                    "name": item["name"],
                    "source_digest": item["source_digest"],
                    "installed_identity": _identity_payload(stage_identity),
                    "installed_digest": item["source_digest"],
                },
                mode,
                target,
                root,
            )
            if current != "current":
                raise PackageError(f"new installation verification failed: {current_details}")
        updated = dict(receipt)
        updated["mode"] = mode
        updated["skills"] = []
        for item in receipt["skills"]:
            destination = target / item["name"]
            installed_identity = installed_identities.get(destination)
            if installed_identity is None:
                raise PackageError("new installed artifact identity cannot be proven")
            updated["skills"].append(
                {
                    **item,
                    "installed_identity": _identity_payload(installed_identity),
                    "installed_digest": item["source_digest"],
                }
            )
        _write_receipt(receipt_path, updated)
    except Exception as exc:
        for item, identity in reversed(created):
            if item.exists() or item.is_symlink():
                _remove_exact_installation(Path(new_items[0]["source"]), item, mode, identity)
        restored = True
        for backup, destination, _ in reversed(backups):
            source = Path(new_items[0]["source"])
            if (destination.exists() or destination.is_symlink()) and not _remove_exact_installation(
                source,
                destination,
                mode,
                installed_identities.get(destination),
            ):
                restored = False
                continue
            try:
                os.replace(backup, destination)
            except OSError:
                restored = False
        return _lifecycle_report("rolled_back" if restored else "partial", new_items, error=str(exc), receipt=str(receipt_path))
    cleanup_errors = []
    old_source = canonical_source(root, receipt["skills"][0]["name"])
    for backup, _, old_identity in backups:
        if not _remove_exact_installation(old_source, backup, receipt["mode"], old_identity):
            cleanup_errors.append(f"backup identity changed: {backup}")
    if cleanup_errors:
        return _lifecycle_report(
            "partial",
            new_items,
            error="migration committed but backup cleanup failed: " + "; ".join(cleanup_errors),
            receipt=str(receipt_path),
        )
    return _lifecycle_report("pass", new_items, receipt=str(receipt_path))


def run_doctor(
    *,
    root: Path,
    target: Path | None,
    skills: Iterable[str],
    run_verification: bool,
    treehouse_root: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    required = [root / "README.md", root / "docs/skill-standard.md", root / "scripts/verify.py"]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    checks.append(
        _check(
            "repository_shape",
            "fail" if missing else "pass",
            "missing: " + ", ".join(missing) if missing else "required repository entry points are present",
        )
    )

    python_ok = sys.version_info >= MIN_PYTHON
    checks.append(
        _check(
            "python",
            "pass" if python_ok else "fail",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}; requires {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+",
        )
    )
    if not (root / ".git").exists():
        checks.append(_check("git_metadata", "warn", "Git metadata unavailable; revision cannot be proven"))
    else:
        head = _git_command(root, "rev-parse", "HEAD")
        checks.append(
            _check(
                "git_metadata",
                "pass" if head else "fail",
                f"HEAD {head}" if head else "Git metadata exists but HEAD cannot be read",
            )
        )

    selected = sorted(set(skills))
    for name in selected:
        try:
            source = canonical_source(root, name) / "SKILL.md"
        except PackageError as exc:
            checks.append(_check(f"package:{name}", "fail", str(exc)))
            continue
        checks.append(
            _check(
                f"package:{name}",
                "pass" if source.is_file() else "fail",
                "canonical SKILL.md present" if source.is_file() else "canonical SKILL.md missing",
            )
        )

    if target is None:
        checks.append(_check("installation_target", "skip", "no --target supplied"))
    else:
        resolved_target = target.expanduser().resolve()
        target_error = _target_root_error(resolved_target)
        if target_error:
            checks.append(_check("installation_target", "fail", target_error))
        else:
            for name in selected:
                try:
                    source = canonical_source(root, name)
                except PackageError:
                    continue
                destination = resolved_target / name
                if destination.is_symlink():
                    status = "pass" if _same_resolved_path(source, destination) else "fail"
                    details = "canonical symlink" if status == "pass" else f"symlink resolves to {destination.resolve()}"
                elif not destination.exists():
                    status, details = "warn", "not installed at target"
                elif destination.is_dir():
                    try:
                        matches = package_digest(source) == package_digest(destination)
                    except (OSError, PackageError) as exc:
                        status, details = "fail", f"cannot compare package digest: {exc}"
                    else:
                        status = "pass" if matches else "fail"
                        details = (
                            "installed copy matches canonical package digest"
                            if matches
                            else "target contains different or unowned content"
                        )
                else:
                    status, details = "fail", "target contains different or unowned content"
                checks.append(_check(f"target:{name}", status, details))

    if run_verification:
        try:
            result = subprocess.run(
                [sys.executable, "scripts/verify.py"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            output = (result.stderr or result.stdout or "").strip().splitlines()
            suffix = f"; {output[-1]}" if output else ""
            checks.append(
                _check(
                    "repository_verification",
                    "pass" if result.returncode == 0 else "fail",
                    f"exit {result.returncode}{suffix}",
                )
            )
        except OSError as exc:
            checks.append(_check("repository_verification", "fail", str(exc)))
    else:
        checks.append(_check("repository_verification", "skip", "use --verify to run the complete gate"))

    if treehouse_root is not None:
        treehouse_root = treehouse_root.expanduser()
        try:
            version = subprocess.run(
                ["treehouse", "--version"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            status = (version.stdout or version.stderr).strip()
            import re
            match = re.search(r"(\d+)\.(\d+)\.(\d+)", status)
            if version.returncode or not match or tuple(map(int, match.groups())) < (2, 3, 0):
                raise RuntimeError("treehouse executable missing or version below 2.3.0")
            result = subprocess.run(
                ["treehouse", "status", "--json"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(f"status exit {result.returncode}")
            payload = json.loads(result.stdout)
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict) and isinstance(payload.get("worktrees"), list):
                rows = payload["worktrees"]
            elif isinstance(payload, dict) and isinstance(payload.get("trees"), list):
                rows = payload["trees"]
            else:
                raise RuntimeError("Treehouse status JSON has invalid top-level shape")
            current = root.resolve()
            pool_root = treehouse_root.resolve()
            try:
                current.relative_to(pool_root)
            except ValueError as exc:
                raise RuntimeError("current repository is outside the explicit Treehouse pool root") from exc
            row = next(
                (
                    entry
                    for entry in rows
                    if isinstance(entry, dict)
                    and isinstance(entry.get("path"), str)
                    and entry["path"]
                    and Path(entry["path"]).expanduser().resolve() == current
                ),
                None,
            )
            valid_row = bool(
                row
                and row.get("status") == "leased"
                and isinstance(row.get("lease_id"), str)
                and row["lease_id"]
                and isinstance(row.get("lease_holder"), str)
                and row["lease_holder"]
            )
            details = f"version {match.group(0)}; status {row.get('status')}; holder {row.get('lease_holder')}" if valid_row else "current repository is not leased with a proven lease identity"
            checks.append(_check("treehouse", "pass" if valid_row else "fail", details))
        except (OSError, subprocess.TimeoutExpired, TimeoutError, ValueError, RuntimeError, AttributeError) as exc:
            checks.append(_check("treehouse", "fail", str(exc)))

    has_failure = any(check["status"] == "fail" for check in checks)
    has_warning = any(check["status"] == "warn" for check in checks)
    return {
        "schema_version": "azhou-ai-hub.doctor.v1",
        "valid": not has_failure,
        "status": "unhealthy" if has_failure else "degraded" if has_warning else "healthy",
        "checks": checks,
    }


def _print_info(payload: dict[str, Any]) -> None:
    revision = payload["revision"]
    print("Azhou AI Hub")
    print(f"Repository: {payload['repository']}")
    print(f"Revision: {revision['commit']} ({revision['branch']}, dirty={revision['dirty']})")
    print(f"Skills: {', '.join(payload['installable_skills'])}")
    print(f"Verify: {payload['verification_command']}")


def _print_version(payload: dict[str, Any]) -> None:
    print(f"Commit: {payload['commit']}")
    print(f"Branch: {payload['branch']}")
    print(f"Dirty: {payload['dirty']}")
    print("Release version: unavailable (no installed release metadata)")


def _print_doctor(payload: dict[str, Any]) -> None:
    print(f"Azhou AI Hub doctor: {payload['status']}")
    for check in payload["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['details']}")


def _print_setup(payload: dict[str, Any]) -> None:
    print(f"Azhou AI Hub setup: {payload['status']} ({payload['mode']} -> {payload['target']})")
    if payload.get("error"):
        print(f"[FAIL] target: {payload['error']}")
    for row in payload["skills"]:
        print(f"[{row['status'].upper()}] {row['name']}: {row['details']}")
    if payload["status"] == "dry_run":
        print("No files changed. Re-run with --apply to execute this plan.")


def run_verifier(root: Path, python: str, *, promotion_evidence: bool = False) -> int:
    command = [python, str(root / "scripts/verify.py"), "--python", python]
    if promotion_evidence:
        command.append("--promotion-evidence")
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
        )
    except OSError as exc:
        print(f"verification failed to start: {exc}", file=sys.stderr)
        return 1
    return result.returncode


def build_parser(root: Path = ROOT) -> argparse.ArgumentParser:
    skill_names = canonical_skills(root)
    parser = argparse.ArgumentParser(
        prog="azhou-ai-hub",
        description="Harness-neutral foundations for Azhou AI Hub",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    info = subcommands.add_parser("info", help="Show repository, runtime, and skill information")
    info.add_argument("--json", action="store_true", help="Emit stable JSON")

    version = subcommands.add_parser("version", help="Show proven repository revision information")
    version.add_argument("--json", action="store_true", help="Emit stable JSON")

    doctor = subcommands.add_parser("doctor", help="Run read-only repository and installation diagnostics")
    doctor.add_argument("--target", type=Path, help="Optional harness skill root to inspect")
    doctor.add_argument("--skill", action="append", choices=skill_names, help="Limit checks to one skill; repeatable")
    doctor.add_argument("--verify", action="store_true", help="Run the complete repository verification gate")
    doctor.add_argument("--treehouse-root", type=Path, help="Explicit Treehouse pool root for read-only lease diagnostics")
    doctor.add_argument("--json", action="store_true", help="Emit stable JSON")

    setup = subcommands.add_parser("setup", help="Plan or apply an explicit skill installation")
    setup.add_argument("--target", type=Path, required=True, help="Explicit harness skill root")
    setup.add_argument("--skill", action="append", choices=skill_names, help="Install one skill; repeatable")
    setup.add_argument("--mode", choices=["link", "copy"], default="link", help="Installation mode")
    setup.add_argument("--apply", action="store_true", help="Apply the plan; default is read-only dry-run")
    setup.add_argument("--receipt", type=Path, help="Use a managed installation receipt; writes it only with --apply")
    setup.add_argument("--managed", action="store_true", help="Opt into receipt-owned lifecycle management")
    setup.add_argument("--json", action="store_true", help="Emit stable JSON receipt")

    for command, help_text in (("repair", "Restore missing artifacts from a managed receipt"), ("uninstall", "Remove artifacts from a managed receipt")):
        lifecycle = subcommands.add_parser(command, help=help_text)
        lifecycle.add_argument("--receipt", type=Path, required=True)
        lifecycle.add_argument("--target", type=Path, required=True)
        lifecycle.add_argument("--apply", action="store_true")
        lifecycle.add_argument("--json", action="store_true")

    migrate = subcommands.add_parser("migrate", help="Switch one managed skill between link and copy")
    migrate.add_argument("--receipt", type=Path, required=True)
    migrate.add_argument("--target", type=Path, required=True)
    migrate.add_argument("--mode", choices=["link", "copy"], required=True)
    migrate.add_argument("--apply", action="store_true")
    migrate.add_argument("--json", action="store_true")

    verify = subcommands.add_parser("verify", help="Run the authoritative repository verification gate")
    verify.add_argument("--python", default=sys.executable, help="Python interpreter for all Python gates")
    verify.add_argument(
        "--promotion-evidence",
        action="store_true",
        help="Also require Git-external maintainer promotion evidence",
    )
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser(root).parse_args(argv)
    skills = args.skill if getattr(args, "skill", None) else canonical_skills(root)

    if args.command == "info":
        payload = info_payload(root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_info(payload)
        return 0

    if args.command == "version":
        payload = version_payload(root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_version(payload)
        return 0

    if args.command == "doctor":
        payload = run_doctor(
            root=root,
            target=args.target,
            skills=skills,
            run_verification=args.verify,
            treehouse_root=args.treehouse_root,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_doctor(payload)
        return 0 if payload["valid"] else 1

    if args.command in {"repair", "migrate", "uninstall"} and not args.target.is_absolute():
        payload = _lifecycle_report("fail", [], error="--target must be an absolute path")
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["status"])
        return 1

    if args.command == "setup":
        if not args.target.is_absolute():
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, "--target must be an absolute path")
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_setup(payload)
            return 1
        if args.receipt and not args.managed:
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, "--receipt requires explicit --managed")
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_setup(payload)
            return 1
        if args.managed and not args.receipt:
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, "--managed requires --receipt")
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_setup(payload)
            return 1
        if args.managed and len(skills) != 1:
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, "--managed supports exactly one skill")
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_setup(payload)
            return 1
        if args.managed:
            receipt_error = _receipt_path_error(args.receipt, args.target)
            if receipt_error:
                payload = _setup_failure(args.target.expanduser().resolve(), args.mode, receipt_error)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    _print_setup(payload)
                return 1
        target_error = _target_root_error(args.target.expanduser().resolve())
        if target_error:
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, target_error)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_setup(payload)
            return 1
        try:
            context = _mutation_lock(args.target) if args.apply else nullcontext()
            with context:
                payload = setup_skills(root=root, target=args.target, skills=skills, mode=args.mode, dry_run=not args.apply, receipt_path=args.receipt if args.managed and args.apply else args.receipt)
        except PackageError as exc:
            payload = _setup_failure(args.target.expanduser().resolve(), args.mode, str(exc))
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_setup(payload)
        return 0 if payload["status"] in {"pass", "dry_run"} else 1

    if args.command in {"repair", "uninstall"}:
        receipt = args.receipt.expanduser()
        target = args.target.expanduser().resolve()
        receipt_error = _receipt_path_error(receipt, target)
        loaded, error = _load_receipt(receipt) if receipt_error is None else (None, receipt_error)
        if error or loaded is None or Path(loaded["target"]).resolve() != target:
            payload = _lifecycle_report("fail", [], error=error or "receipt_invalid: target mismatch")
        else:
            fn = repair_receipt if args.command == "repair" else uninstall_receipt
            try:
                context = _mutation_lock(target) if args.apply else nullcontext()
                with context:
                    payload = fn(receipt_path=receipt, target=target, root=root, apply=args.apply)
            except PackageError as exc:
                payload = _lifecycle_report("fail", [], error=str(exc))
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["status"])
        return 0 if payload["status"] in {"pass", "dry_run"} else 1

    if args.command == "migrate":
        receipt_error = _receipt_path_error(args.receipt, args.target)
        if receipt_error:
            payload = _lifecycle_report("fail", [], error=receipt_error)
        else:
            try:
                context = _mutation_lock(args.target) if args.apply else nullcontext()
                with context:
                    payload = migrate_receipt(receipt_path=args.receipt, target=args.target, root=root, mode=args.mode, apply=args.apply)
            except PackageError as exc:
                payload = _lifecycle_report("fail", [], error=str(exc))
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["status"])
        return 0 if payload["status"] in {"pass", "dry_run"} else 1

    if args.command == "verify":
        return run_verifier(root, args.python, promotion_evidence=args.promotion_evidence)

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

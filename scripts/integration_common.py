"""Package inputs and owned installation staging for the Hub monorepo.

Development source lives only in packages/. Private installation snapshots bind
reviewed inputs and allow recovery even after that source has been updated.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

try:
    from . import azhou_runtime_state
except ImportError:
    import azhou_runtime_state

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("pstack", "model-router", "agent-skin")
PACKAGES = {
    "pstack": "pstack-agent-harness",
    "model-router": "agent-orchestration-kit",
    "agent-skin": "agent-skin",
    # Historical Hub receipts and the installed app/Pet still bind this source root.
    "startup-animation": "codex-startup-animation",
}
PACKAGE_SCHEMA = "azhou-hub.package.v1"
LOCK_SCHEMA = "azhou-hub.package-inputs.v1"
EXCLUDED_PARTS = {".git", "node_modules", "__pycache__", ".build", "dist", ".local", ".azhou", "private"}


class IntegrationError(RuntimeError):
    """A source, plan or owned artifact cannot be verified."""


def plan_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _relative(name: str) -> tuple[str, ...]:
    if not isinstance(name, str):
        raise IntegrationError("runtime paths must be relative strings")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(p in ("", ".", "..", ".git") for p in name.split("/")) or "\\" in name:
        raise IntegrationError(f"unsafe source-lock path: {name!r}")
    return path.parts


def package_root(component: str, *, hub_root: Path = ROOT) -> Path:
    if component not in PACKAGES:
        raise IntegrationError(f"unknown package: {component}")
    root = Path(hub_root).resolve()
    path = root / "packages" / PACKAGES[component]
    if any(p.is_symlink() for p in (path, path.parent)):
        raise IntegrationError("package path cannot be a symlink")
    return _absolute_directory(path)


def _validate_manifest(component: str, manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema") != LOCK_SCHEMA or manifest.get("component") != component:
        raise IntegrationError("package manifest schema/component mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("commit", ""))):
        raise IntegrationError("package provenance requires a full origin Git commit")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise IntegrationError("package requires a nonempty runtime file map")
    for name, item in files.items():
        _relative(name)
        if EXCLUDED_PARTS.intersection(PurePosixPath(name).parts):
            raise IntegrationError(f"private or generated runtime input is forbidden: {name}")
        if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise IntegrationError(f"invalid package digest: {name}")
        if type(item.get("executable")) is not bool:
            raise IntegrationError(f"package executable intent missing: {name}")


def load_lock(component: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    """Fingerprint current package inputs; no tracked per-file hash lock exists."""
    source = package_root(component, hub_root=hub_root)
    path = source / "hub-package.json"
    if path.is_symlink():
        raise IntegrationError("package metadata cannot be a symlink")
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IntegrationError(f"cannot read package metadata: {path}: {exc}") from exc
    if not isinstance(metadata, dict) or metadata.get("schema") != PACKAGE_SCHEMA or metadata.get("component") != component:
        raise IntegrationError("package metadata schema/component mismatch")
    runtime = metadata.get("runtime_paths")
    if not isinstance(runtime, list) or not runtime or "hub-package.json" not in runtime:
        raise IntegrationError("package requires runtime_paths including hub-package.json")
    selected: dict[str, Path] = {}
    def select(candidate: Path) -> None:
        name = candidate.relative_to(source).as_posix()
        _relative(name)
        if EXCLUDED_PARTS.intersection(candidate.relative_to(source).parts):
            return
        if candidate.is_symlink():
            raise IntegrationError(f"package runtime contains a symlink: {name}")
        if candidate.is_file():
            selected[name] = candidate
        elif candidate.is_dir():
            for child in sorted(candidate.iterdir()):
                select(child)
        else:
            raise IntegrationError(f"package runtime file missing or unsupported: {name}")
    for name in runtime:
        if not isinstance(name, str):
            raise IntegrationError("runtime_paths entries must be relative strings")
        parts = _relative(name.rstrip("/"))
        if EXCLUDED_PARTS.intersection(parts):
            raise IntegrationError(f"private or generated runtime input is forbidden: {name}")
        cursor = source
        for part in parts:
            cursor /= part
            if cursor.is_symlink():
                raise IntegrationError(f"package runtime contains a symlink: {name}")
        select(cursor)
    files = {name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "executable": bool(p.stat().st_mode & 0o111)} for name, p in sorted(selected.items())}
    lock = {**metadata, "schema": LOCK_SCHEMA, "source_kind": "package", "files": files}
    _validate_manifest(component, lock)
    return lock


def _absolute_directory(path: Path, *, must_exist: bool = True) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise IntegrationError(f"expected an explicit absolute non-symlink directory: {path}")
    if must_exist and not path.is_dir():
        raise IntegrationError(f"directory missing: {path}")
    if path.exists() and not path.is_dir():
        raise IntegrationError(f"not a directory: {path}")
    return path.resolve()


def _file_bytes(root: Path, name: str, item: dict[str, Any]) -> bytes:
    cursor = root
    for part in _relative(name):
        cursor /= part
        if cursor.is_symlink():
            raise IntegrationError(f"locked source contains a symlink: {name}")
    if not cursor.is_file():
        raise IntegrationError(f"locked source file missing: {name}")
    data = cursor.read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise IntegrationError(f"locked source content drift: {name}")
    if bool(cursor.stat().st_mode & 0o111) != item["executable"]:
        raise IntegrationError(f"locked source executable drift: {name}")
    return data


def inspect_source(component: str, source: Path | None = None, *, hub_root: Path = ROOT) -> dict[str, Any]:
    canonical = package_root(component, hub_root=hub_root)
    source = canonical if source is None else _absolute_directory(source)
    if source != canonical:
        raise IntegrationError("source must be the Hub's in-repository package; external source checkouts are no longer used")
    lock = load_lock(component, hub_root=hub_root)
    for name, item in lock["files"].items():
        _file_bytes(source, name, item)
    return {
        "component": component,
        "source": str(source),
        "package": PACKAGES[component],
        "version": lock.get("version", lock.get("runtime_version", "unreleased")),
        "commit": lock["commit"],
        "commit_scope": "original import provenance; current package content is identified by source_lock_sha256",
        "source_kind": "package",
        "source_lock_sha256": plan_digest(lock),
        "locked_files": len(lock["files"]),
        "scope": "current in-repository package runtime inputs; private assets excluded",
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    if path.is_symlink():
        raise IntegrationError(f"receipt cannot be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    value = dict(payload)
    value.pop("integrity_digest", None)
    value["integrity_digest"] = plan_digest(value)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def read_receipt(path: Path) -> dict[str, Any]:
    if Path(path).is_symlink():
        raise IntegrationError(f"receipt cannot be a symlink: {path}")
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IntegrationError(f"cannot read receipt: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError("receipt must be an object")
    digest = value.pop("integrity_digest", None)
    if digest != plan_digest(value):
        raise IntegrationError("receipt integrity mismatch (a digest is not an authentication signature)")
    value["integrity_digest"] = digest
    return value


def snapshot_lock(component: str, snapshot: Path) -> dict[str, Any]:
    """Read the installation's input manifest, independently of live source."""
    snapshot = _absolute_directory(snapshot)
    receipt = read_receipt(snapshot / ".hub-source.json")
    lock = receipt.get("manifest")
    _validate_manifest(component, lock)
    if (receipt.get("schema") != "azhou-hub.integration-snapshot.v1"
            or receipt.get("component") != component or receipt.get("source_lock_sha256") != plan_digest(lock)):
        raise IntegrationError("snapshot belongs to a different package or input manifest")
    return lock


def verify_snapshot(component: str, snapshot: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    snapshot = _absolute_directory(snapshot)
    lock = snapshot_lock(component, snapshot)
    for name, item in lock["files"].items():
        _file_bytes(snapshot, name, item)
    return {
        "component": component,
        "commit": lock["commit"],
        "source_kind": lock["source_kind"],
        "source_lock_sha256": plan_digest(lock),
        "snapshot": str(snapshot),
        "locked_files": len(lock["files"]),
    }


def snapshot_source(component: str, source: Path | None, workspace: Path, *, hub_root: Path = ROOT,
                    expected_digest: str | None = None) -> Path:
    origin = inspect_source(component, source, hub_root=hub_root)
    if expected_digest is not None and origin["source_lock_sha256"] != expected_digest:
        raise IntegrationError("package inputs changed after the reviewed plan")
    source = Path(origin["source"])
    workspace = _absolute_directory(workspace, must_exist=False)
    if workspace == source or source in workspace.parents:
        raise IntegrationError("snapshot workspace must be outside the read-only source")
    lock = load_lock(component, hub_root=hub_root)
    if plan_digest(lock) != origin["source_lock_sha256"]:
        raise IntegrationError("package inputs changed before snapshot preparation")
    try:
        destination = azhou_runtime_state.state_path(workspace, "hub", "sources", component, plan_digest(lock))
        if destination == source or source in destination.parents:
            raise IntegrationError("snapshot destination overlaps source")
        if destination.exists():
            verified = verify_snapshot(component, destination, hub_root=hub_root)
            if verified["source_lock_sha256"] != plan_digest(lock):
                raise IntegrationError("existing snapshot differs from the reviewed package inputs")
            if read_receipt(destination / ".hub-source.json").get("source") != str(source):
                raise IntegrationError("existing snapshot belongs to a different package checkout; use a new workspace")
            return destination
        workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        azhou_runtime_state.ensure_private_directory(destination.parent, root=workspace)
    except azhou_runtime_state.StateError as exc:
        raise IntegrationError(str(exc)) from exc
    staged = Path(tempfile.mkdtemp(prefix=".source-stage-", dir=destination.parent))
    try:
        for name, item in lock["files"].items():
            data = _file_bytes(source, name, item)
            target = staged.joinpath(*_relative(name))
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(data)
            target.chmod(0o700 if item["executable"] else 0o600)
        # Re-check the origin after materialization; another writer cannot silently
        # change the selected inputs or commit part way through this operation.
        after = inspect_source(component, source, hub_root=hub_root)
        if after["commit"] != origin["commit"] or after["source_lock_sha256"] != origin["source_lock_sha256"]:
            raise IntegrationError("source changed during snapshot")
        write_receipt(staged / ".hub-source.json", {
            "schema": "azhou-hub.integration-snapshot.v1", **origin,
            "manifest": lock,
            "ownership": "Hub snapshot only; native installed files belong to their installer",
        })
        verify_snapshot(component, staged, hub_root=hub_root)
        try:
            staged.rename(destination)
        except FileExistsError:
            verified = verify_snapshot(component, destination, hub_root=hub_root)
            if verified["source_lock_sha256"] != plan_digest(lock):
                raise IntegrationError("concurrent snapshot differs from the reviewed package inputs")
        return destination
    finally:
        if staged.exists():
            shutil.rmtree(staged)

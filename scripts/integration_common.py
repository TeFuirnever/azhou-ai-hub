"""Fixed-source helpers for the Hub's three optional integrations.

This is a file-lock and evidence utility, not a component registry or scheduler.
Native installers retain ownership of their own configuration and artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Any

try:
    from . import azhou_runtime_state
except ImportError:
    import azhou_runtime_state

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("pstack", "model-router", "startup-animation")
LOCK_SCHEMA = "azhou-hub.integration-source.v1"


class IntegrationError(RuntimeError):
    """A source, plan or owned artifact cannot be verified."""


def plan_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _relative(name: str) -> tuple[str, ...]:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(p in ("", ".", "..", ".git") for p in name.split("/")) or "\\" in name:
        raise IntegrationError(f"unsafe source-lock path: {name!r}")
    return path.parts


def load_lock(component: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    if component not in COMPONENTS:
        raise IntegrationError(f"unknown fixed integration: {component}")
    path = hub_root / "integrations" / component / "source-lock.json"
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IntegrationError(f"cannot read source lock: {path}: {exc}") from exc
    if not isinstance(lock, dict) or lock.get("schema") != LOCK_SCHEMA or lock.get("component") != component:
        raise IntegrationError("source-lock schema/component mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(lock.get("commit", ""))):
        raise IntegrationError("source lock requires a full Git commit")
    if lock.get("source_kind") not in ("commit", "worktree"):
        raise IntegrationError("source_kind must be commit or worktree")
    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        raise IntegrationError("source lock requires an explicit nonempty file map")
    for name, item in files.items():
        _relative(name)
        if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise IntegrationError(f"invalid source digest: {name}")
        if type(item.get("executable")) is not bool:
            raise IntegrationError(f"source executable intent missing: {name}")
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


def _git(source: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, check=False)
    if result.returncode:
        raise IntegrationError(f"Git source check failed ({args[0]}): {result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout


def inspect_source(component: str, source: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    source = _absolute_directory(source)
    lock = load_lock(component, hub_root=hub_root)
    head = _git(source, "rev-parse", "HEAD").decode("ascii").strip()
    if head != lock["commit"]:
        raise IntegrationError(f"source commit mismatch: expected {lock['commit']}, found {head}")
    git_files: dict[str, tuple[str, str]] = {}
    if lock["source_kind"] == "commit":
        for entry in _git(source, "ls-tree", "-r", "-z", head).split(b"\0"):
            if not entry:
                continue
            info, name = entry.split(b"\t", 1)
            mode, kind, oid = info.decode("ascii").split()
            git_files[name.decode("utf-8")] = (mode, oid) if kind == "blob" else ("", "")
    for name, item in lock["files"].items():
        data = _file_bytes(source, name, item)
        if lock["source_kind"] == "commit":
            mode, oid = git_files.get(name, ("", ""))
            actual_oid = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
            if mode not in ("100644", "100755") or actual_oid != oid or (mode == "100755") != item["executable"]:
                raise IntegrationError(f"file is not the declared committed source: {name}")
    status = _git(source, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {
        "component": component,
        "source": str(source),
        "commit": head,
        "source_kind": lock["source_kind"],
        "source_lock_sha256": plan_digest(lock),
        "locked_files": len(lock["files"]),
        "working_tree_dirty": bool(status),
        "working_tree_status_sha256": hashlib.sha256(status).hexdigest(),
        "scope": "only explicitly locked files are runtime inputs",
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


def verify_snapshot(component: str, snapshot: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    snapshot = _absolute_directory(snapshot)
    lock = load_lock(component, hub_root=hub_root)
    receipt = read_receipt(snapshot / ".hub-source.json")
    if receipt.get("component") != component or receipt.get("source_lock_sha256") != plan_digest(lock):
        raise IntegrationError("snapshot belongs to a different integration or locked version")
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


def snapshot_source(component: str, source: Path, workspace: Path, *, hub_root: Path = ROOT) -> Path:
    origin = inspect_source(component, source, hub_root=hub_root)
    source = Path(origin["source"])
    workspace = _absolute_directory(workspace, must_exist=False)
    if workspace == source or source in workspace.parents:
        raise IntegrationError("snapshot workspace must be outside the read-only source")
    lock = load_lock(component, hub_root=hub_root)
    try:
        destination = azhou_runtime_state.state_path(workspace, "hub", "sources", component, plan_digest(lock))
        if destination == source or source in destination.parents:
            raise IntegrationError("snapshot destination overlaps source")
        if destination.exists():
            verify_snapshot(component, destination, hub_root=hub_root)
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
            "ownership": "Hub snapshot only; native installed files belong to their installer",
        })
        verify_snapshot(component, staged, hub_root=hub_root)
        try:
            staged.rename(destination)
        except FileExistsError:
            verify_snapshot(component, destination, hub_root=hub_root)
        return destination
    finally:
        if staged.exists():
            shutil.rmtree(staged)

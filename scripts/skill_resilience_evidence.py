#!/usr/bin/env python3
"""Bounded generic evidence owner for the skill resilience work."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Any, Sequence

RAW_SCHEMA = "skill-resilience.pre-bootstrap-raw.v1"
ENV_SCHEMA = "skill-resilience.evidence-record.v1"
MANIFEST_SCHEMA = "owned-hook-surfaces.v1"
FREEZE_SCHEMA = "skill-resilience.super-freeze.v1"
EVIDENCE_ROOT = ".omx/evidence/skill-resilience-fix"
PHASE0A = [
    ".gitignore",
    "scripts/skill_resilience_evidence.py",
    "tests/fixtures/owned-hook-surfaces.json",
    "tests/test_skill_resilience_evidence.py",
]
PHASE1 = [
    "docs/skill-standard.md",
    "tests/test_hook_resilience_contract.py",
    "skills/repo-pedant/assets/hooks/codex-hooks.fragment.json",
    "skills/repo-pedant/references/trigger-hooks.md",
    "skills/repo-pedant/scripts/closeout_hook.py",
    "tests/test_closeout_hook.py",
    "skills/excalidraw-diagram/assets/overlap-audit.schema.json",
    "skills/excalidraw-diagram/assets/overlap-receipt.schema.json",
    "skills/excalidraw-diagram/scripts/overlap_contract.py",
    "skills/excalidraw-diagram/scripts/audit-overlaps.py",
    "skills/excalidraw-diagram/scripts/overlap_repair_decision.py",
    "skills/excalidraw-diagram/scripts/overlap_receipt.py",
    "skills/excalidraw-diagram/SKILL.md",
    "skills/excalidraw-diagram/references/design-system.md",
    "skills/excalidraw-diagram/references/brand-layer.md",
    "tests/test_excalidraw_overlap_contract.py",
    "tests/test_excalidraw_overlap_audit.py",
    "tests/test_excalidraw_overlap_receipt.py",
]
BOOTSTRAP_KEYS = {"schema_version", "record_type", "repository_realpath", "pre_bootstrap_snapshot_digest", "helper_realpath", "helper_sha256", "trusted_python_realpath", "owned_surface_manifest_sha256", "ownership_digest", "focused_test_evidence", "ignore_proof", "raw_status_sha256", "dirty_path_bytes_sha256", "entry_list_sha256", "hooks_representation", "installed_alias_representation", "manifest", "installed_alias", "hooks_path"}
MANIFEST_ENTRIES = [
    {"id": "repo-pedant-codex-fragment", "path": "skills/repo-pedant/assets/hooks/codex-hooks.fragment.json", "mode": "managed"},
    {"id": "super-caveman-codex-adapter", "path": "skills/super-caveman/scripts/codex_adapter.py", "mode": "read_only_precondition"},
]
RAW_KEYS = {
    "capture_commands", "capture_root", "dirty_path_bytes_sha256", "dirty_paths",
    "entries", "entry_list_sha256", "git_base", "git_head", "hooks_path",
    "hooks_representation", "installed_alias", "installed_alias_representation",
    "managed_intersection", "phase0a_paths", "phase1_paths", "raw_status_sha256",
    "repository_realpath", "schema_version", "tool_identities",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SELF_DIGEST_KEYS = {"record_digest", "record_sha256", "detector_record_digest", "decision_record_digest", "receipt_record_digest"}


class EvidenceError(Exception):
    """Stable contract failure, reported with a machine-readable code."""


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise EvidenceError("E_NONFINITE_JSON") from exc


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical(value))


def real(path: os.PathLike[str] | str) -> str:
    return os.path.realpath(os.fspath(path))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_nonfinite)
    except (OSError, ValueError, UnicodeError) as exc:
        raise EvidenceError("E_JSON_INPUT") from exc


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in read_blocks(stream):
            digest.update(block)
    return digest.hexdigest()


def reject_nonfinite(_: str) -> None:
    raise ValueError("non-finite JSON")


def read_blocks(stream: Any) -> Any:
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            return
        yield block


def read_sidecar(path: Path, *, raw: bool = False) -> str:
    if raw and path.name != "pre-bootstrap.raw.json":
        raise EvidenceError("E_SIDECAR_NAME")
    if not raw and path.suffix != ".json":
        raise EvidenceError("E_SIDECAR_NAME")
    sidecar = path.with_name("pre-bootstrap.raw.sha256") if raw else Path(str(path) + ".sha256")
    if not raw and Path(str(sidecar) + ".sha256").exists():
        raise EvidenceError("E_SIDECAR_DUPLICATE")
    try:
        value = sidecar.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise EvidenceError("E_SIDECAR_MISSING") from exc
    if not re.fullmatch(r"[0-9a-f]{64}\n", value):
        raise EvidenceError("E_SIDECAR_FORMAT")
    if value[:-1] != file_digest(path):
        raise EvidenceError("E_SIDECAR_MISMATCH")
    return value[:-1]


def assert_contained(path: Path, root: Path) -> None:
    if path.is_symlink() or root.is_symlink():
        raise EvidenceError("E_OUTPUT_CONTAINMENT")
    # Resolve the root itself, but reject every lexical parent symlink.  A
    # resolved-child check alone is insufficient when an output parent is
    # retargeted between validation and write.
    root_abs = Path(real(root))
    target_abs = Path(real(path.parent)) / path.name
    try:
        target_abs.relative_to(root_abs)
    except ValueError as exc:
        raise EvidenceError("E_OUTPUT_CONTAINMENT") from exc
    cursor = Path(os.path.abspath(root))
    target = Path(os.path.abspath(path))
    try:
        relative = target.relative_to(cursor)
    except ValueError as exc:
        raise EvidenceError("E_OUTPUT_CONTAINMENT") from exc
    for part in relative.parts[:-1]:
        cursor /= part
        if os.path.islink(cursor):
            raise EvidenceError("E_OUTPUT_CONTAINMENT")
    parent = Path(os.path.abspath(path.parent))
    if any(os.path.islink(parent_anchor) for parent_anchor in [parent, *parent.parents] if parent_anchor != root and parent_anchor != Path(parent.anchor)):
        # The broad walk above covers descendants; this catches an existing
        # parent symlink when the output path does not yet exist.
        try:
            parent.relative_to(Path(os.path.abspath(root)))
        except ValueError as exc:
            raise EvidenceError("E_OUTPUT_CONTAINMENT") from exc


def atomic_write(path: Path, value: Any, root: Path | None = None, *, raw: bool = False) -> str:
    if root is not None:
        assert_contained(path, root)
    if isinstance(value, dict) and SELF_DIGEST_KEYS.intersection(value):
        raise EvidenceError("E_SELF_DIGEST_FIELD")
    payload = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    sidecar = path.with_name("pre-bootstrap.raw.sha256") if raw else Path(str(path) + ".sha256")
    fd, temp_name = tempfile.mkstemp(prefix=f".{sidecar.name}.", dir=sidecar.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write((digest_bytes(payload) + "\n").encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, sidecar)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return digest_bytes(payload)


def record_path(path: Path) -> dict[str, Any]:
    if not os.path.lexists(path):
        return {"kind": "missing"}
    info = os.lstat(path)
    mode = oct(stat.S_IMODE(info.st_mode))
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path).encode("utf-8", "surrogateescape")
        return {"kind": "symlink", "mode": mode, "target_bytes_sha256": digest_bytes(target)}
    if stat.S_ISREG(info.st_mode):
        return {"kind": "file", "mode": mode, "size": info.st_size, "sha256": file_digest(path)}
    if stat.S_ISDIR(info.st_mode):
        return {"kind": "directory", "mode": mode}
    raise EvidenceError("E_UNSUPPORTED_FILESYSTEM_KIND")


def symlink_chain(path: Path) -> dict[str, Any]:
    absolute = Path(os.path.abspath(path))
    hops: list[dict[str, Any]] = []
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            return {"hops": hops, "terminal": {"kind": "missing", "path": str(current)}}
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(current).encode("utf-8", "surrogateescape")
            hops.append({"path": str(current), "mode": oct(stat.S_IMODE(info.st_mode)), "target_bytes_sha256": digest_bytes(target)})
    terminal_path = Path(real(absolute))
    terminal = record_path(terminal_path)
    terminal["path"] = str(terminal_path)
    return {"hops": hops, "terminal": terminal}


def protected_identity(path: Path) -> dict[str, Any]:
    """Freeze both lexical link hops and the resolved terminal identity."""
    return symlink_chain(path)


def representation_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if "hops" in expected:
        return actual == expected
    terminal = dict(actual.get("terminal", {}))
    terminal.pop("path", None)
    return terminal == expected


def split_status(raw: bytes) -> list[bytes]:
    pieces = raw.split(b"\0")
    paths: list[bytes] = []
    index = 0
    while index < len(pieces):
        item = pieces[index]
        if not item:
            index += 1
            continue
        paths.append(item[3:] if len(item) >= 3 else item)
        if len(item) >= 2 and item[:2] in {b" R", b"R ", b" C", b"C "} and index + 1 < len(pieces):
            paths.append(pieces[index + 1])
            index += 1
        index += 1
    return paths


def status_entries(raw: bytes) -> list[tuple[str, bytes]]:
    """Return XY status and path bytes without confusing tracked changes for ?? files."""
    pieces = raw.split(b"\0")
    result: list[tuple[str, bytes]] = []
    index = 0
    while index < len(pieces):
        item = pieces[index]
        if not item:
            index += 1
            continue
        status = item[:2].decode("ascii", "replace") if len(item) >= 2 else ""
        path = item[3:] if len(item) >= 3 else b""
        result.append((status, path))
        if status.strip() in {"R", "C"} and index + 1 < len(pieces):
            result.append((status, pieces[index + 1]))
            index += 1
        index += 1
    return result


def validate_record(value: Any) -> None:
    if not isinstance(value, dict) or value.get("kind") not in {"missing", "file", "symlink", "directory"}:
        raise EvidenceError("E_RECORD_SHAPE")
    kind = value["kind"]
    if kind == "missing":
        if set(value) != {"kind"}:
            raise EvidenceError("E_RECORD_SHAPE")
        return
    if set(value) != {"kind", "mode"} | ({"size", "sha256"} if kind == "file" else {"target_bytes_sha256"} if kind == "symlink" else set()):
        raise EvidenceError("E_RECORD_SHAPE")
    if not re.fullmatch(r"0o[0-7]{3,4}", str(value["mode"])):
        raise EvidenceError("E_RECORD_SHAPE")
    if kind == "file" and (not isinstance(value["size"], int) or value["size"] < 0 or not HEX64.fullmatch(value["sha256"])):
        raise EvidenceError("E_RECORD_SHAPE")
    if kind == "symlink" and not HEX64.fullmatch(value["target_bytes_sha256"]):
        raise EvidenceError("E_RECORD_SHAPE")


def validate_protected(value: Any) -> None:
    if isinstance(value, dict) and set(value) == {"hops", "terminal"}:
        if not isinstance(value["hops"], list):
            raise EvidenceError("E_PROTECTED_REPRESENTATION")
        for hop in value["hops"]:
            if not isinstance(hop, dict) or set(hop) != {"path", "mode", "target_bytes_sha256"} or not HEX64.fullmatch(str(hop["target_bytes_sha256"])):
                raise EvidenceError("E_PROTECTED_REPRESENTATION")
        terminal = dict(value["terminal"])
        terminal.pop("path", None)
        validate_record(terminal)
        return
    validate_record(value)


def validate_manifest(value: Any, repo: Path) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "surfaces"} or value["schema_version"] != MANIFEST_SCHEMA:
        raise EvidenceError("E_MANIFEST_SCHEMA")
    surfaces = value["surfaces"]
    if not isinstance(surfaces, list) or len(surfaces) != len(MANIFEST_ENTRIES):
        raise EvidenceError("E_MANIFEST_SURFACES")
    ids: set[str] = set()
    paths: set[str] = set()
    for item in surfaces:
        if not isinstance(item, dict) or set(item) != {"id", "path", "mode"}:
            raise EvidenceError("E_MANIFEST_SURFACES")
        ident, rel, mode = item["id"], item["path"], item["mode"]
        if not isinstance(ident, str) or not isinstance(rel, str) or ident in ids or rel in paths:
            raise EvidenceError("E_MANIFEST_DUPLICATE")
        ids.add(ident)
        paths.add(rel)
        if os.path.isabs(rel) or any(part in {"", ".", ".."} for part in Path(rel).parts) or any(char in rel for char in "*?["):
            raise EvidenceError("E_MANIFEST_PATH")
        candidate = repo / rel
        for parent in [repo, *candidate.parents]:
            if parent != candidate and os.path.islink(parent):
                raise EvidenceError("E_MANIFEST_SYMLINK_ESCAPE")
        if item not in MANIFEST_ENTRIES:
            raise EvidenceError("E_MANIFEST_SURFACES")
    if sorted(surfaces, key=surface_id) != sorted(MANIFEST_ENTRIES, key=surface_id):
        raise EvidenceError("E_MANIFEST_SURFACES")
    return value


def surface_id(item: dict[str, Any]) -> str:
    return item["id"]


def validate_raw(path: Path, repo: Path) -> tuple[dict[str, Any], str]:
    if not path.is_absolute() or real(path).startswith(real(repo) + os.sep):
        raise EvidenceError("E_RAW_SNAPSHOT_LOCATION")
    raw_digest = read_sidecar(path, raw=True)
    value = load_json(path)
    if not isinstance(value, dict) or set(value) != RAW_KEYS or value.get("schema_version") != RAW_SCHEMA or SELF_DIGEST_KEYS.intersection(value):
        raise EvidenceError("E_RAW_SNAPSHOT_SCHEMA")
    if real(value["repository_realpath"]) != real(repo):
        raise EvidenceError("E_REPOSITORY_REALPATH")
    capture = Path(value["capture_root"])
    if not capture.is_absolute() or real(capture) != real(path.parent) or real(capture).startswith(real(repo) + os.sep):
        raise EvidenceError("E_RAW_SNAPSHOT_LOCATION")
    try:
        status = (capture / "status.raw").read_bytes()
    except OSError as exc:
        raise EvidenceError("E_RAW_STATUS_MISSING") from exc
    if value["raw_status_sha256"] != digest_bytes(status) or not HEX64.fullmatch(value["raw_status_sha256"]):
        raise EvidenceError("E_RAW_STATUS_MISMATCH")
    dirty = split_status(status)
    joined = b"\0".join(dirty) + (b"\0" if dirty else b"")
    if value["dirty_path_bytes_sha256"] != digest_bytes(joined) or [os.fsencode(item) for item in value["dirty_paths"]] != dirty:
        raise EvidenceError("E_DIRTY_PATH_DIGEST")
    entries = value["entries"]
    if not isinstance(entries, list):
        raise EvidenceError("E_ENTRY_LIST")
    previous: bytes | None = None
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "record"} or not isinstance(item["path"], str):
            raise EvidenceError("E_ENTRY_LIST")
        encoded = os.fsencode(item["path"])
        if previous is not None and encoded <= previous:
            raise EvidenceError("E_ENTRY_ORDER")
        previous = encoded
        validate_record(item["record"])
    if value["entry_list_sha256"] != digest_value(entries):
        raise EvidenceError("E_ENTRY_LIST_DIGEST")
    entry_paths = {item["path"] for item in entries}
    current_super = {"skills/super-caveman"}
    tree = repo / "skills/super-caveman"
    if tree.exists():
        # Include directory identities as well as files/symlinks; rglob does
        # not follow symlinked directories, which is part of the freeze
        # boundary.
        current_super.update(str(item.relative_to(repo)) for item in tree.rglob("*"))
    required_paths = set(PHASE0A) | set(PHASE1) | set(value["dirty_paths"]) | current_super | {value["hooks_path"], value["installed_alias"]}
    if not required_paths.issubset(entry_paths) or not any(path.startswith("skills/super-caveman/") for path in entry_paths):
        raise EvidenceError("E_ENTRY_COVERAGE")
    if value["managed_intersection"] != [] or value["phase0a_paths"] != PHASE0A or value["phase1_paths"] != PHASE1:
        raise EvidenceError("E_RAW_PATHS")
    validate_protected(value["hooks_representation"])
    alias = value["installed_alias_representation"]
    if not isinstance(alias, dict) or set(alias) != {"hops", "terminal"} or not isinstance(alias["hops"], list):
        raise EvidenceError("E_PROTECTED_REPRESENTATION")
    for hop in alias["hops"]:
        if not isinstance(hop, dict) or set(hop) != {"path", "mode", "target_bytes_sha256"} or not HEX64.fullmatch(hop["target_bytes_sha256"]):
            raise EvidenceError("E_PROTECTED_REPRESENTATION")
    terminal = dict(alias["terminal"])
    terminal.pop("path", None)
    validate_record(terminal)
    return value, raw_digest


def prove_ignore(repo: Path, evidence_root: Path) -> dict[str, str]:
    probe = os.path.relpath(evidence_root, repo) + "/.ignore-proof-probe"
    with tempfile.TemporaryDirectory(prefix="skill-resilience-ignore-") as temp:
        subprocess.run(["git", "-C", temp, "init", "-q"], check=True)
        result = subprocess.run(["git", "-c", "core.excludesFile=/dev/null", "--git-dir", f"{temp}/.git", "--work-tree", str(repo), "check-ignore", "-v", "--no-index", probe], cwd=repo, text=True, capture_output=True)
    if result.returncode != 0 or not result.stdout.startswith(".gitignore:"):
        raise EvidenceError("E_IGNORE_PROOF")
    return {"path": os.path.relpath(evidence_root, repo), "source": result.stdout.split("\t", 1)[0], "match": result.stdout.strip()}


def validated_evidence_root(args: argparse.Namespace, repo: Path) -> Path:
    root = Path(args.evidence_root)
    expected = repo / EVIDENCE_ROOT
    if root.is_symlink() or expected.is_symlink() or os.path.abspath(root) != os.path.abspath(expected) or real(root) != real(expected):
        raise EvidenceError("E_OUTPUT_CONTAINMENT")
    return root


def validate_canonical_adapter(adapter: Path, repo: Path, raw_entries: list[dict[str, Any]]) -> None:
    canonical_adapter = repo / "skills/super-caveman/scripts/codex_adapter.py"
    if os.path.abspath(adapter) != os.path.abspath(canonical_adapter) or adapter.is_symlink():
        raise EvidenceError("E_ADAPTER_PATH")
    entry = next((item for item in raw_entries if item.get("path") == "skills/super-caveman/scripts/codex_adapter.py"), None)
    if entry is None or record_path(canonical_adapter) != entry.get("record"):
        raise EvidenceError("E_ADAPTER_DRIFT")


def assert_binding(args: argparse.Namespace) -> int:
    bootstrap_path = Path(args.bootstrap)
    bootstrap_digest = read_sidecar(bootstrap_path)
    if bootstrap_digest != args.bootstrap_digest:
        raise EvidenceError("E_BINDING_BOOTSTRAP")
    bootstrap = load_json(bootstrap_path)
    repo = Path(real(args.repo))
    validated_evidence_root(args, repo)
    root = repo / EVIDENCE_ROOT
    if not str(Path(real(bootstrap_path)).resolve()).startswith(str(root.resolve()) + os.sep):
        raise EvidenceError("E_BINDING_CONTAINMENT")
    if not isinstance(bootstrap, dict) or set(bootstrap) != BOOTSTRAP_KEYS or bootstrap.get("schema_version") != ENV_SCHEMA or bootstrap.get("record_type") != "bootstrap":
        raise EvidenceError("E_BINDING_BOOTSTRAP_SCHEMA")
    if bootstrap.get("repository_realpath") != str(repo):
        raise EvidenceError("E_BINDING_REPOSITORY")
    helper = Path(args.helper)
    if real(helper) != str(repo / "scripts/skill_resilience_evidence.py"):
        raise EvidenceError("E_BINDING_HELPER_PATH")
    if bootstrap.get("helper_realpath") != real(helper) or bootstrap.get("helper_sha256") != file_digest(helper):
        raise EvidenceError("E_BINDING_HELPER")
    if bootstrap.get("trusted_python_realpath") != real(sys.executable):
        raise EvidenceError("E_BINDING_PYTHON")
    if bootstrap.get("pre_bootstrap_snapshot_digest") != args.snapshot_digest:
        raise EvidenceError("E_BINDING_SNAPSHOT")
    if not HEX64.fullmatch(args.snapshot_digest) or not HEX64.fullmatch(args.bootstrap_digest):
        raise EvidenceError("E_BINDING_DIGEST")
    if not HEX64.fullmatch(str(bootstrap.get("owned_surface_manifest_sha256"))) or not HEX64.fullmatch(str(bootstrap.get("ownership_digest"))):
        raise EvidenceError("E_BINDING_BOOTSTRAP_SCHEMA")
    manifest = bootstrap.get("manifest")
    if manifest != {"schema_version": MANIFEST_SCHEMA, "surfaces": MANIFEST_ENTRIES}:
        raise EvidenceError("E_BINDING_MANIFEST")
    if bootstrap.get("owned_surface_manifest_sha256") != file_digest(repo / "tests/fixtures/owned-hook-surfaces.json"):
        raise EvidenceError("E_BINDING_MANIFEST")
    ignore = bootstrap.get("ignore_proof", {})
    if ignore.get("path") != EVIDENCE_ROOT or not str(ignore.get("source", "")).startswith(".gitignore:") or EVIDENCE_ROOT not in str(ignore.get("match", "")):
        raise EvidenceError("E_BINDING_IGNORE")
    focused = bootstrap.get("focused_test_evidence")
    if not isinstance(focused, dict) or focused.get("helper_sha256") != bootstrap.get("helper_sha256") or focused.get("status") != "PASS":
        raise EvidenceError("E_BINDING_FOCUSED")
    if getattr(args, "emit_binding", False):
        print("binding-ok")
    return 0


def binding_projection(args: argparse.Namespace) -> dict[str, str]:
    bootstrap = load_json(Path(args.bootstrap))
    return {"helper_realpath": bootstrap["helper_realpath"], "helper_sha256": bootstrap["helper_sha256"], "trusted_python_realpath": bootstrap["trusted_python_realpath"], "pre_bootstrap_snapshot_digest": bootstrap["pre_bootstrap_snapshot_digest"], "bootstrap_digest": args.bootstrap_digest}


def component_record(args: argparse.Namespace, record_type: str, payload: Any) -> dict[str, Any]:
    return {"schema_version": "skill-resilience.evidence-record.v1", "record_type": record_type, "binding": binding_projection(args), "payload": payload}


def require_binding(args: argparse.Namespace) -> None:
    missing = [name for name in ("bootstrap", "helper", "snapshot_digest", "bootstrap_digest") if not getattr(args, name, None)]
    if missing:
        raise EvidenceError("E_BINDING_REQUIRED:" + ",".join(missing))
    assert_binding(args)


def focused_evidence(path: str | None, repo: Path) -> dict[str, Any]:
    if not path:
        raise EvidenceError("E_FOCUSED_EVIDENCE_REQUIRED")
    value = load_json(Path(path))
    if not isinstance(value, dict) or set(value) != {"command", "status", "tests_run", "output_path", "output_sha256", "helper_sha256", "test_sha256"} or value.get("status") != "PASS" or not isinstance(value.get("command"), str) or not isinstance(value.get("tests_run"), int) or value["tests_run"] < 21 or not isinstance(value.get("output_path"), str) or not HEX64.fullmatch(str(value.get("output_sha256"))) or not HEX64.fullmatch(str(value.get("helper_sha256"))) or not HEX64.fullmatch(str(value.get("test_sha256"))):
        raise EvidenceError("E_FOCUSED_EVIDENCE")
    if value["helper_sha256"] != file_digest(Path(__file__)):
        raise EvidenceError("E_FOCUSED_HELPER")
    command_tokens = shlex.split(value["command"])
    if len(command_tokens) != 5 or Path(command_tokens[0]).name not in {"python3", "python"} or command_tokens[1:] != ["-m", "unittest", "-v", "tests.test_skill_resilience_evidence"]:
        raise EvidenceError("E_FOCUSED_COMMAND")
    output = Path(value["output_path"])
    root = validated_evidence_root(argparse.Namespace(evidence_root=str(repo / EVIDENCE_ROOT)), repo)
    for candidate in (Path(path), output):
        if os.path.abspath(candidate.parent) != os.path.abspath(root) and not str(candidate.resolve()).startswith(str(root.resolve()) + os.sep):
            raise EvidenceError("E_FOCUSED_CONTAINMENT")
    if not output.is_file() or file_digest(output) != value["output_sha256"]:
        raise EvidenceError("E_FOCUSED_OUTPUT")
    match = re.search(r"Ran\s+(\d+)\s+tests?", output.read_text(encoding="utf-8", errors="strict"))
    if not match or int(match.group(1)) != value["tests_run"]:
        raise EvidenceError("E_FOCUSED_TEST_COUNT")
    tests = Path(__file__).resolve().parents[1] / "tests/test_skill_resilience_evidence.py"
    if value["test_sha256"] != file_digest(tests):
        raise EvidenceError("E_FOCUSED_TESTS")
    return value


def bootstrap(args: argparse.Namespace) -> int:
    repo = Path(real(args.repo))
    raw, raw_digest = validate_raw(Path(args.raw_snapshot), repo)
    manifest = validate_manifest(load_json(Path(args.manifest)), repo)
    root = Path(args.evidence_root)
    if real(root) != real(repo / EVIDENCE_ROOT):
        raise EvidenceError("E_OUTPUT_CONTAINMENT")
    envelope = {
        "schema_version": ENV_SCHEMA, "record_type": "bootstrap", "repository_realpath": str(repo),
        "pre_bootstrap_snapshot_digest": raw_digest, "helper_realpath": real(__file__), "helper_sha256": file_digest(Path(__file__)),
        "trusted_python_realpath": real(sys.executable), "owned_surface_manifest_sha256": file_digest(Path(args.manifest)),
        "ownership_digest": digest_value({"phase0a": PHASE0A, "phase1": raw["phase1_paths"], "managed_intersection": raw["managed_intersection"]}),
        "focused_test_evidence": focused_evidence(args.focused_test_evidence, repo), "ignore_proof": prove_ignore(repo, root),
        "raw_status_sha256": raw["raw_status_sha256"], "dirty_path_bytes_sha256": raw["dirty_path_bytes_sha256"],
        "entry_list_sha256": raw["entry_list_sha256"], "hooks_representation": raw["hooks_representation"],
        "installed_alias_representation": raw["installed_alias_representation"], "manifest": manifest,
        "installed_alias": raw["installed_alias"], "hooks_path": raw["hooks_path"],
    }
    atomic_write(Path(args.output), envelope, root)
    print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def normalize(args: argparse.Namespace, doctor: bool) -> int:
    require_binding(args)
    value = load_json(Path(args.input))
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict) and set(value) == {"checks"} and isinstance(value["checks"], list):
        items = value["checks"]
    else:
        raise EvidenceError("E_NORMALIZER_SCHEMA")
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise EvidenceError("E_NORMALIZER_ITEM")
        if doctor:
            if not all(field in item for field in ("check", "status", "summary")) or ("cause" not in item and "causes" not in item):
                raise EvidenceError("E_DOCTOR_ITEM")
            causes = item.get("causes", item.get("cause"))
            if not isinstance(causes, list):
                causes = [causes]
            if not causes:
                causes = [None]
            for cause in causes:
                if not isinstance(cause, (str, type(None))):
                    raise EvidenceError("E_DOCTOR_CAUSE")
                result.append({"check": scrub(item.get("check", item.get("name", ""))), "status": scrub(item.get("status", "")), "summary": scrub(item.get("summary", item.get("details", ""))), "cause": scrub(cause) or "<no-cause>"})
        else:
            if not all(field in item for field in ("stage", "code", "reason")):
                raise EvidenceError("E_VERIFIER_ITEM")
            result.append({"stage": scrub(item.get("stage", "")), "code": scrub(item.get("code", item.get("status", ""))), "reason": scrub(item.get("reason", item.get("summary", "")))})
    fields = ("check", "status", "summary", "cause") if doctor else ("stage", "code", "reason")
    result.sort(key=sort_record(fields))
    record_type = "skill-resilience.doctor-signatures.v1" if doctor else "skill-resilience.full-verify-signatures.v1"
    record = component_record(args, record_type, result)
    atomic_write(Path(args.output), record, validated_evidence_root(args, Path(real(args.repo))))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def scrub(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"(?:/private)?/tmp/[^\s,;]+", "<temp>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds|seconds?|s)\b", "<duration>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*(?:success(?:es)?|passed|checks?|count)\b", "<count>", text, flags=re.IGNORECASE)
    return text


def sort_record(fields: Sequence[str]):
    def key(item: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(item[field]) for field in fields)

    return key


def lexical_tokens(command: str, depth: int = 0) -> tuple[list[str], bool]:
    """Tokenize wrappers with one shared top+derived budget."""
    total = 0
    collected: list[str] = []
    exhausted = False

    def visit(text: str, level: int) -> None:
        nonlocal total, exhausted
        if level > 2:
            exhausted = True
            return
        try:
            tokens = shlex.split(text, posix=True)
        except ValueError:
            return
        for token in tokens:
            total += 1
            if total <= 64:
                collected.append(token)
            else:
                exhausted = True
                return
        nested_mode = False
        for token in tokens:
            if token in {"-c", "--command"}:
                nested_mode = True
                continue
            if token in {";", "&&", "||", "|", "&"}:
                continue
            if nested_mode:
                visit(token, level + 1)
                nested_mode = False
                if exhausted:
                    return

    visit(command, depth)
    return collected, exhausted


def classify_command(args: argparse.Namespace) -> str:
    canonical_path = real(args.canonical)
    alias_path = os.path.abspath(args.alias)
    try:
        top = shlex.split(args.command, posix=True)
    except ValueError:
        top = []
    interpreter = Path(top[0]).name if top else ""
    if len(top) == 3 and (interpreter == "python" or interpreter.startswith("python3")) and top[1] == canonical_path and real(top[1]) == canonical_path:
        return "parsed_target"
    tokens, exhausted = lexical_tokens(args.command)
    equivalents = {canonical_path, real(alias_path)}
    for token in tokens:
        candidate = real(token) if os.path.isabs(token) else real(Path(args.repository) / token)
        normalized = token.replace("\\", "/")
        alias_suffix = "/".join(Path(alias_path).parts[-4:])
        canonical_suffix = "/".join(Path(canonical_path).parts[-4:])
        if candidate in equivalents or normalized in {alias_path, canonical_path, "skills/super-caveman/scripts/codex_adapter.py", alias_suffix, canonical_suffix}:
            return "raw_ambiguous"
    if exhausted:
        return "raw_ambiguous"
    raw_text = args.command.replace("\\", "/")
    boundary = rf"(?<![A-Za-z0-9_./-])(?:{re.escape(canonical_path)}|{re.escape(alias_path)})(?![A-Za-z0-9_./-])"
    home_alias = re.search(r"(?<![A-Za-z0-9_./-])(?:\$HOME|\$\{HOME\}|~)/\.agents/skills/super-caveman/scripts/codex_adapter\.py(?![A-Za-z0-9_./-])", raw_text)
    if re.search(boundary, raw_text) or home_alias or re.search(r"(?<![A-Za-z0-9_-])(caveman|adhd)(?![A-Za-z0-9_-])", raw_text, re.IGNORECASE) and any(word in raw_text for word in ("sh -c", "bash -c", "zsh -c", "env ")):
        return "raw_ambiguous"
    wrapped = bool(top and Path(top[0]).name in {"sh", "bash", "zsh", "env"}) or any(token in {"-c", "--command"} for token in top)
    legacy_echo = len(top) >= 2 and top[0] == "echo" and top[1].startswith("CAVEMAN MODE ACTIVE. Rules:")
    legacy_path = any("/".join(token.replace("\\", "/").split("/")[-3:]) == "i-have-adhd/hooks/always-on.sh" for token in top)
    if wrapped and (legacy_echo or legacy_path):
        return "raw_ambiguous"
    if legacy_echo or legacy_path:
        return "parsed_legacy"
    adapter_suffix = "super-caveman/scripts/codex_adapter.py"
    if any(token.replace("\\", "/") in {canonical_path, alias_path, adapter_suffix, alias_suffix, canonical_suffix} for token in tokens):
        return "raw_ambiguous"
    return "none"


def classify_cli(args: argparse.Namespace) -> int:
    print(classify_command(args))
    return 0


def registrations(hooks: Any, canonical_path: str, repository: str, alias: str) -> list[dict[str, Any]]:
    if not isinstance(hooks, dict) or set(hooks) != {"hooks"} or not isinstance(hooks["hooks"], dict):
        raise EvidenceError("E_HOOKS_SCHEMA")
    found: list[dict[str, Any]] = []
    for event, groups in hooks["hooks"].items():
        if not isinstance(groups, list):
            raise EvidenceError("E_HOOKS_SCHEMA")
        for index, group in enumerate(groups):
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise EvidenceError("E_HOOKS_SCHEMA")
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    raise EvidenceError("E_HOOKS_SCHEMA")
                if "command" in hook and not isinstance(hook["command"], str):
                    raise EvidenceError("E_HOOKS_SCHEMA")
                # A target-bearing malformed/non-command hook must block.  A
                # genuinely unrelated hook remains diagnosable and harmless.
                target_text = " ".join(str(value) for value in hook.values() if isinstance(value, str))
                target_class = classify_command(argparse.Namespace(command=target_text, canonical=canonical_path, alias=alias, repository=repository)) if target_text else "none"
                if "command" not in hook and (hook.get("type") == "command" or target_class != "none"):
                    raise EvidenceError("E_HOOKS_SCHEMA")
                if "command" not in hook:
                    continue
                classification = classify_command(argparse.Namespace(command=hook["command"], canonical=canonical_path, alias=alias, repository=repository))
                if classification != "none" and hook.get("type") != "command":
                    raise EvidenceError("E_HOOKS_SCHEMA")
                if hook.get("type") != "command":
                    continue
                if classification != "none":
                    found.append({"event": event, "group_index": index, "matcher": group.get("matcher", ""), "group_keys": set(group), "group_hooks_count": len(group["hooks"]), "hook": hook, "classification": classification})
    return found


def freeze_super(args: argparse.Namespace) -> int:
    repo = Path(real(args.repo))
    require_binding(args)
    raw, _ = validate_raw(Path(args.raw_snapshot), repo)
    validate_canonical_adapter(Path(args.adapter), repo, raw["entries"])
    if os.path.abspath(args.hooks) != os.path.abspath(raw["hooks_path"]):
        raise EvidenceError("E_HOOKS_PATH")
    if os.path.abspath(args.alias) != os.path.abspath(raw["installed_alias"]):
        raise EvidenceError("E_ALIAS_PATH")
    hooks_path = Path(raw["hooks_path"])
    if not representation_matches(protected_identity(hooks_path), raw["hooks_representation"]):
        raise EvidenceError("E_HOOKS_DRIFT")
    alias_path = Path(raw["installed_alias"])
    if not representation_matches(protected_identity(alias_path), raw["installed_alias_representation"]):
        raise EvidenceError("E_ALIAS_DRIFT")
    hooks_path = Path(args.hooks)
    hooks = load_json(hooks_path)
    bootstrap = load_json(Path(args.bootstrap))
    alias_spelling = bootstrap.get("installed_alias", args.alias)
    hooks_identity = protected_identity(hooks_path)
    expected_hooks = bootstrap.get("hooks_representation")
    if expected_hooks is not None and not representation_matches(hooks_identity, expected_hooks):
        raise EvidenceError("E_HOOKS_DRIFT")
    expected_alias = bootstrap.get("installed_alias_representation")
    actual_alias = protected_identity(Path(alias_spelling))
    if expected_alias is not None and not representation_matches(actual_alias, expected_alias):
        raise EvidenceError("E_ALIAS_DRIFT")
    managed = set(PHASE0A) | set(raw["phase1_paths"])
    for entry in raw["entries"]:
        name = entry["path"]
        if name in managed or name == raw.get("hooks_path") or name == raw.get("installed_alias"):
            continue
        path = Path(name) if os.path.isabs(name) else repo / name
        if record_path(path) != entry["record"]:
            raise EvidenceError("E_PHASE0P_PROTECTED_DRIFT")
    found = [item for item in registrations(hooks, real(args.adapter), str(repo), alias_spelling) if item["event"] == "SessionStart"]
    identities = [item for item in found if item["classification"] == "parsed_target"]
    if len(identities) != 1 or len(found) != 1:
        raise EvidenceError("E_SUPER_IDENTITY_COUNT")
    identity = identities[0]
    hook = identity["hook"]
    tokens = shlex.split(hook["command"])
    interpreter = Path(tokens[0]).name if tokens else ""
    if len(tokens) != 3 or tokens[1] != real(args.adapter) or tokens[2] != "render" or not (interpreter == "python" or interpreter.startswith("python3")):
        raise EvidenceError("E_SUPER_IDENTITY")
    if set(identity) != {"event", "group_index", "matcher", "group_keys", "group_hooks_count", "hook", "classification"} or identity["group_keys"] != {"matcher", "hooks"} or identity["group_hooks_count"] != 1:
        raise EvidenceError("E_SUPER_REGISTRATION")
    group_matcher = identity["matcher"]
    if group_matcher != "startup|resume|clear|compact" or set(hook) != {"type", "command", "timeout", "additionalContextLimit", "statusMessage"}:
        raise EvidenceError("E_SUPER_FIELDS")
    if hook.get("type") != "command" or hook.get("timeout") != 5 or hook.get("additionalContextLimit") != 1024 or hook.get("statusMessage") != "Loading Super Caveman":
        raise EvidenceError("E_SUPER_FIELDS")
    interpreter_path = shutil.which(tokens[0]) or tokens[0]
    if real(interpreter_path) != bootstrap.get("trusted_python_realpath"):
        raise EvidenceError("E_SUPER_PYTHON")
    if not Path(interpreter_path).is_file() or not os.access(interpreter_path, os.X_OK) or not Path(tokens[1]).is_file():
        raise EvidenceError("E_SUPER_IDENTITY")
    tree = repo / "skills/super-caveman"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("super_benchmark", repo / "benchmarks/super-caveman/benchmark.py")
        if spec is None or spec.loader is None:
            raise ImportError
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tree_digest = module.sha256_skill_tree()
    except Exception as exc:
        raise EvidenceError("E_SUPER_TREE") from exc
    files = [{"path": str(path.relative_to(repo)), "sha256": file_digest(path)} for path in sorted(tree.rglob("*")) if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}]
    projection = [{"event": item["event"], "matcher": item["matcher"], "type": item["hook"]["type"], "argv": shlex.split(item["hook"]["command"]), "adapter_realpath": real(tokens[1]), "timeout": item["hook"]["timeout"], "additionalContextLimit": item["hook"]["additionalContextLimit"], "statusMessage": item["hook"]["statusMessage"]} for item in found]
    status = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--", "skills/super-caveman"], cwd=repo, capture_output=True, check=True).stdout
    tracked_diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--", "skills/super-caveman"], cwd=repo, capture_output=True, check=True).stdout
    expected_super = {item["path"]: item["record"] for item in raw["entries"] if item["path"] == "skills/super-caveman" or item["path"].startswith("skills/super-caveman/")}
    current_super = {path: record_path(Path(path)) for path in expected_super}
    if current_super != expected_super:
        raise EvidenceError("E_PHASE0P_SUPER_ENTRY_DRIFT")
    expected_super_xy = {name: xy for xy, name in ((xy, os.fsdecode(path)) for xy, path in status_entries((Path(raw["capture_root"]) / "status.raw").read_bytes())) if name == "skills/super-caveman" or name.startswith("skills/super-caveman/")}
    current_super_xy = {os.fsdecode(path): xy for xy, path in status_entries(status) if os.fsdecode(path) == "skills/super-caveman" or os.fsdecode(path).startswith("skills/super-caveman/")}
    if current_super_xy != expected_super_xy:
        raise EvidenceError("E_PHASE0P_SUPER_STATUS_DRIFT")
    untracked = sorted(os.fsdecode(path) for kind, path in status_entries(status) if kind == "??")
    payload = {"identity_class": identity["classification"], "hooks_representation": hooks_identity, "hooks_sha256": file_digest(hooks_path), "normalized_registration": projection, "normalized_registration_sha256": digest_value(projection), "adapter_identity": protected_identity(Path(args.adapter)), "adapter_realpath": real(Path(args.adapter)), "adapter_sha256": file_digest(Path(args.adapter)), "installed_alias_identity": actual_alias, "super_tree_sha256": tree_digest, "super_tree_records": files, "git_status_sha256": digest_bytes(status), "git_status_raw_b64": base64.b64encode(status).decode("ascii"), "tracked_diff_sha256": digest_bytes(tracked_diff), "tracked_diff_bytes_b64": base64.b64encode(tracked_diff).decode("ascii"), "untracked_paths": untracked, "phase0p_filtered_status": expected_super_xy, "current_filtered_status": current_super_xy, "phase0p_super_entries": expected_super}
    value = component_record(args, FREEZE_SCHEMA, payload)
    atomic_write(Path(args.output), value, validated_evidence_root(args, repo))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def ownership(args: argparse.Namespace) -> int:
    require_binding(args)
    repo = Path(real(args.repo))
    raw, _ = validate_raw(Path(args.raw_snapshot), repo)
    if not representation_matches(protected_identity(Path(raw["hooks_path"])), raw["hooks_representation"]):
        raise EvidenceError("E_HOOKS_DRIFT")
    if not representation_matches(protected_identity(Path(raw["installed_alias"])), raw["installed_alias_representation"]):
        raise EvidenceError("E_ALIAS_DRIFT")
    current = subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=repo)
    names = {os.fsdecode(item) for item in split_status(current)}
    try:
        captured_status = (Path(raw["capture_root"]) / "status.raw").read_bytes()
    except OSError as exc:
        raise EvidenceError("E_RAW_STATUS_MISSING") from exc
    expected_xy = {os.fsdecode(path): xy for xy, path in status_entries(captured_status)}
    current_xy = {os.fsdecode(path): xy for xy, path in status_entries(current)}
    if args.phase not in {"phase0a", "phase0b", "phase1", "postflight"}:
        raise EvidenceError("E_PHASE")
    managed = ownership_managed_paths(raw, args.phase)
    protected_projection_exclusions = ownership_projection_exclusions(raw)
    baseline = {item["path"]: item["record"] for item in raw["entries"]}
    changed: list[str] = []
    for name, expected in baseline.items():
        path = Path(name) if os.path.isabs(name) else repo / name
        observed = record_path(path)
        if observed != expected:
            changed.append(name)
    tracked = subprocess.run(["git", "diff", "HEAD", "--name-status"], cwd=repo, text=True, capture_output=True, check=True).stdout
    untracked = sorted(name for name in names if name not in {item["path"] for item in raw["entries"]})
    protected, out_of_allowlist, status_differences = ownership_enforcement(
        changed=changed,
        names=names,
        dirty_paths=raw["dirty_paths"],
        expected_xy=expected_xy,
        current_xy=current_xy,
        managed=managed,
    )
    payload = {"raw_status_sha256": raw["raw_status_sha256"], "current_status_sha256": digest_bytes(current), "pre_dirty_managed_intersection": sorted(managed.intersection(raw["dirty_paths"])), "current_managed_paths": sorted(managed.intersection(names)), "status_unchanged": digest_bytes(current) == raw["raw_status_sha256"], "entries": raw["entries"], "changed_paths": changed, "changed_protected_paths": protected, "tracked_diff": tracked, "tracked_diff_sha256": digest_bytes(tracked.encode()), "untracked_paths": untracked, "out_of_allowlist_paths": out_of_allowlist, "phase0p_status_by_path": expected_xy, "current_status_by_path": current_xy, "status_differences": status_differences}
    payload["protected_projection"] = protected_projection(raw, expected_xy, protected_projection_exclusions)
    value = component_record(args, "skill-resilience.ownership.v1", payload)
    atomic_write(Path(args.output), value, validated_evidence_root(args, repo))
    if protected or out_of_allowlist or status_differences:
        if status_differences:
            raise EvidenceError("E_OWNERSHIP_STATUS_DRIFT")
        raise EvidenceError("E_OWNERSHIP_DRIFT")
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def ownership_managed_paths(raw: dict[str, Any], phase: str) -> set[str]:
    """Return the phase-specific enforcement allowlist.

    Phase0A/Phase0B intentionally do not allow Phase1 changes.  This is kept
    separate from the stable projection boundary below so comparison does not
    weaken the early fail-closed gate.
    """
    if phase not in {"phase0a", "phase0b", "phase1", "postflight"}:
        raise EvidenceError("E_PHASE")
    return set(PHASE0A) if phase in {"phase0a", "phase0b"} else set(PHASE0A) | set(raw["phase1_paths"])


def ownership_projection_exclusions(raw: dict[str, Any]) -> set[str]:
    """Return the stable, full-plan allowlist used only for comparisons."""
    return set(PHASE0A) | set(raw["phase1_paths"])


def ownership_enforcement(
    *,
    changed: Sequence[str],
    names: set[str],
    dirty_paths: Sequence[str],
    expected_xy: dict[str, str],
    current_xy: dict[str, str],
    managed: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """Compute fail-closed ownership findings for one phase."""
    protected = [name for name in changed if name not in managed]
    out_of_allowlist = sorted(name for name in names if name not in managed and name not in dirty_paths)
    status_differences = sorted({name for name in set(expected_xy) | set(current_xy) if name not in managed and expected_xy.get(name) != current_xy.get(name)})
    return protected, out_of_allowlist, status_differences


def protected_projection(raw: dict[str, Any], expected_xy: dict[str, str], exclusions: set[str]) -> dict[str, Any]:
    """Build a phase-stable view of paths outside the complete plan allowlist."""
    return {
        "raw_status_sha256": raw["raw_status_sha256"],
        "hooks_representation": raw["hooks_representation"],
        "installed_alias_representation": raw["installed_alias_representation"],
        "protected_entries": {item["path"]: item["record"] for item in raw["entries"] if item["path"] not in exclusions},
        "protected_status": {name: xy for name, xy in expected_xy.items() if name not in exclusions},
    }


def hook_warnings(args: argparse.Namespace) -> int:
    require_binding(args)
    value = load_json(Path(args.input))
    if not isinstance(value, dict) or str(value.get("startup_warning_hooks")) != "0":
        raise EvidenceError("E_STARTUP_WARNING_HOOKS")
    if not isinstance(value.get("warnings", []), list):
        raise EvidenceError("E_HOOK_WARNINGS")
    record = component_record(args, "skill-resilience.hook-warnings.v1", {"warnings": value.get("warnings", []), "startup_warning_hooks": "0"})
    atomic_write(Path(args.output), record, validated_evidence_root(args, Path(real(args.repo))))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def generic_record(args: argparse.Namespace) -> int:
    require_binding(args)
    repo = Path(real(args.repo))
    payload = load_json(Path(args.input))
    if not isinstance(payload, dict):
        raise EvidenceError("E_BASELINE_SHAPE")
    if "components_digest" in payload or "baseline_digest" in payload:
        raise EvidenceError("E_BASELINE_UNTRUSTED_DIGEST")
    required = {"verifier", "doctor", "hook_warnings", "ownership", "super_freeze"}
    if args.kind in {"record-baseline", "record-postflight"} and not required.issubset(payload):
        raise EvidenceError("E_BASELINE_COMPONENTS")
    allowed = required if args.kind == "record-baseline" else required | {"baseline"}
    if set(payload) - allowed:
        raise EvidenceError("E_BASELINE_KEYS")
    if set(payload) & {"components_digest", "baseline_digest"}:
        raise EvidenceError("E_BASELINE_UNTRUSTED_DIGEST")
    component_digests: dict[str, str] = {}
    component_paths: dict[str, str] = {}
    component_values: dict[str, Any] = {}
    binding = load_json(Path(args.bootstrap))
    expected_types = {
        "verifier": "skill-resilience.full-verify-signatures.v1",
        "doctor": "skill-resilience.doctor-signatures.v1",
        "hook_warnings": "skill-resilience.hook-warnings.v1",
        "ownership": "skill-resilience.ownership.v1",
        "super_freeze": "skill-resilience.super-freeze.v1",
    }
    for name in required:
        component = payload[name]
        if isinstance(component, str):
            component_path = Path(component)
        elif isinstance(component, dict) and isinstance(component.get("path"), str):
            component_path = Path(component["path"])
        else:
            raise EvidenceError("E_BASELINE_COMPONENT")
        assert_contained(component_path, validated_evidence_root(args, repo))
        component_digest = read_sidecar(component_path)
        component_value = load_json(component_path)
        if not isinstance(component_value, dict) or set(component_value) != {"schema_version", "record_type", "binding", "payload"} or component_value.get("schema_version") != ENV_SCHEMA or component_value.get("record_type") != expected_types[name]:
            raise EvidenceError("E_BASELINE_COMPONENT_SCHEMA")
        if component_value.get("binding") != binding_projection(args):
            raise EvidenceError("E_BASELINE_COMPONENT_BINDING")
        component_digests[name] = component_digest
        component_paths[name] = str(component_path.resolve())
        component_values[name] = component_value
    computed_digest = digest_value(component_digests)
    if args.kind == "record-baseline" and payload.get("components_digest") not in {None, computed_digest}:
        raise EvidenceError("E_BASELINE_DIGEST")
    if args.kind == "record-baseline":
        payload["components_digest"] = computed_digest
    if args.kind == "record-postflight":
        baseline_path = payload.get("baseline")
        if not isinstance(baseline_path, str):
            raise EvidenceError("E_POSTFLIGHT_BASELINE")
        assert_contained(Path(baseline_path), validated_evidence_root(args, repo))
        if read_sidecar(Path(baseline_path)) != args.baseline_digest:
            raise EvidenceError("E_POSTFLIGHT_BASELINE")
        baseline = load_json(Path(baseline_path))
        if not isinstance(baseline, dict) or set(baseline) != {"schema_version", "record_type", "binding", "payload"} or baseline.get("schema_version") != "skill-resilience.generic-record.v1" or baseline.get("record_type") != "record-baseline" or baseline.get("binding") != binding_projection(args):
            raise EvidenceError("E_POSTFLIGHT_BASELINE")
        baseline_payload = baseline.get("payload")
        if not isinstance(baseline_payload, dict):
            raise EvidenceError("E_POSTFLIGHT_DRIFT")
        baseline_paths = baseline_payload.get("component_paths", {})
        baseline_values = baseline_payload.get("component_values", {})
        if not isinstance(baseline_paths, dict) or any(component_paths.get(name) == baseline_paths.get(name) for name in required):
            raise EvidenceError("E_POSTFLIGHT_NOT_FRESH")
        comparison: dict[str, dict[str, Any]] = {}
        for name in required:
            before = baseline_values.get(name)
            current = component_values.get(name)
            if name == "ownership":
                before = before.get("payload", {}).get("protected_projection") if isinstance(before, dict) else None
                current = current.get("payload", {}).get("protected_projection") if isinstance(current, dict) else None
                if before != current:
                    raise EvidenceError("E_POSTFLIGHT_PROTECTED_DRIFT")
            if name == "super_freeze" and before != current:
                raise EvidenceError("E_POSTFLIGHT_PROTECTED_DRIFT")
            comparison[name] = {"before_digest": digest_value(before), "current_digest": digest_value(current), "equal": before == current}
        payload["comparison"] = comparison
        payload["components_digest"] = computed_digest
    if args.kind == "record-baseline":
        payload["component_paths"] = component_paths
        payload["component_values"] = component_values
    value = {"schema_version": "skill-resilience.generic-record.v1", "record_type": args.kind, "binding": binding_projection(args), "payload": payload}
    atomic_write(Path(args.output), value, validated_evidence_root(args, repo))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo", default=os.getcwd())
    sub = cli.add_subparsers(dest="subcommand", required=True)

    def add_binding(item: argparse.ArgumentParser) -> None:
        item.add_argument("--bootstrap", required=True)
        item.add_argument("--helper", required=True)
        item.add_argument("--snapshot-digest", required=True)
        item.add_argument("--bootstrap-digest", required=True)

    item = sub.add_parser("bootstrap")
    item.add_argument("--raw-snapshot", required=True)
    item.add_argument("--evidence-root", required=True)
    item.add_argument("--manifest", required=True)
    item.add_argument("--focused-test-evidence", required=True)
    item.add_argument("--output", required=True)
    item.set_defaults(function=bootstrap)
    item = sub.add_parser("assert-binding")
    item.add_argument("--bootstrap", required=True)
    item.add_argument("--helper", required=True)
    item.add_argument("--snapshot-digest", required=True)
    item.add_argument("--bootstrap-digest", required=True)
    item.add_argument("--evidence-root", required=True)
    item.set_defaults(emit_binding=True)
    item.set_defaults(function=assert_binding)
    for name, doctor in (("normalize-verifier", False), ("normalize-doctor", True)):
        item = sub.add_parser(name)
        item.add_argument("--input", required=True)
        item.add_argument("--output", required=True)
        item.add_argument("--evidence-root", required=True)
        add_binding(item)
        item.set_defaults(function=make_normalizer(doctor))
    item = sub.add_parser("classify-super")
    item.add_argument("--command", required=True)
    item.add_argument("--canonical", required=True)
    item.add_argument("--alias", required=True)
    item.add_argument("--repository", default=os.getcwd())
    item.set_defaults(function=classify_cli)
    item = sub.add_parser("freeze-super")
    item.add_argument("--hooks", required=True)
    item.add_argument("--raw-snapshot", required=True)
    item.add_argument("--alias", required=True)
    item.add_argument("--adapter", required=True)
    item.add_argument("--output", required=True)
    item.add_argument("--evidence-root", required=True)
    add_binding(item)
    item.set_defaults(function=freeze_super)
    item = sub.add_parser("ownership")
    item.add_argument("--raw-snapshot", required=True)
    item.add_argument("--phase", choices=("phase0a", "phase0b", "phase1", "postflight"), required=True)
    item.add_argument("--output", required=True)
    item.add_argument("--evidence-root", required=True)
    add_binding(item)
    item.set_defaults(function=ownership)
    item = sub.add_parser("assert-hook-warnings")
    item.add_argument("--input", required=True)
    item.add_argument("--output", required=True)
    item.add_argument("--evidence-root", required=True)
    add_binding(item)
    item.set_defaults(function=hook_warnings)
    for name in ("record-baseline", "record-postflight"):
        item = sub.add_parser(name)
        item.add_argument("--input", required=True)
        item.add_argument("--output", required=True)
        item.add_argument("--evidence-root", required=True)
        if name == "record-postflight":
            item.add_argument("--baseline-digest", required=True)
        add_binding(item)
        item.set_defaults(function=make_generic_recorder(name))
    for item in sub.choices.values():
        item.add_argument("--repo", default=argparse.SUPPRESS)
    return cli


def make_normalizer(doctor: bool):
    def run(args: argparse.Namespace) -> int:
        return normalize(args, doctor)

    return run


def make_generic_recorder(name: str):
    def run(args: argparse.Namespace) -> int:
        args.kind = name
        return generic_record(args)

    return run


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.function(args)
    except EvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"E_IO:{exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

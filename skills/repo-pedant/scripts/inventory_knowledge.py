#!/usr/bin/env python3
"""Build and validate an exhaustive repo-pedant knowledge inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import azhou_runtime_state


SCHEMA_VERSION = "repo-pedant.inventory.v2"
CLASSIFICATIONS = {
    "verified",
    "update",
    "merge",
    "remove_proposal",
    "reminder",
    "hold",
    "out_of_scope",
}
REQUIRED_CHECKS = (
    "current_truth_recorded",
    "history_reviewed",
    "history_coverage_recorded",
    "impact_matrix_reviewed",
    "global_instructions_reviewed",
    "semantic_paths_commands",
    "semantic_readme_setup",
    "semantic_memory_links",
    "propagation_reviewed",
    "relative_time_reviewed",
    "previous_omissions_reviewed",
)
INSTRUCTION_NAMES = {
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "TEAM_GUIDE.md",
    ".agents.md",
}
MEMORY_DECISION_STATUSES = {"none_discovered", "hold"}
MEMORY_STATUSES = {"unresolved", "bound", *MEMORY_DECISION_STATUSES}
SKIP_DIRS = {
    ".azhou",
    ".git",
    ".hg",
    ".omc",
    ".planning",
    ".repo-pedant",
    ".svn",
    ".venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "__pycache__",
}


class InventoryError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_directory(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink():
        path = path.resolve()
    else:
        path = path.absolute().resolve()
    if not path.is_dir():
        raise InventoryError(f"project directory missing: {value}")
    return path


def path_is_skipped(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part in SKIP_DIRS for part in relative.parts)


def walk_markdown(directory: Path, root: Path) -> Iterable[Path]:
    if not directory.is_dir():
        return ()
    return (
        path
        for path in directory.rglob("*.md")
        if path.is_file() and not path_is_skipped(path, root)
    )


def project_candidates(root: Path) -> set[Path]:
    return set(walk_markdown(root, root))


def expand_explicit_path(value: str | Path) -> list[Path]:
    path = Path(value).expanduser().absolute()
    if path.is_symlink():
        path = path.resolve()
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*.md") if item.is_file())
    raise InventoryError(f"explicit knowledge path missing: {value}")


def line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError) as exc:
        raise InventoryError(f"unable to read UTF-8 knowledge file: {path}") from exc


def surface_for(path: Path, explicit_surface: str | None = None) -> str:
    if explicit_surface:
        return explicit_surface
    if path.name in INSTRUCTION_NAMES:
        return "agent_rule"
    if path.name == "README.md":
        return "readme"
    if "docs" in path.parts:
        return "docs"
    if path.name == "MEMORY.md":
        return "memory_index"
    return "project_markdown"


def file_record(
    path: Path,
    *,
    project_root: Path | None,
    explicit_surface: str | None = None,
    write_allowed: bool = True,
) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "project_root": str(project_root) if project_root else None,
        "surface": surface_for(path, explicit_surface),
        "write_allowed": write_allowed,
        "pre_lines": line_count(path),
        "pre_bytes": stat.st_size,
        "classification": "unclassified",
        "reason": "",
        "size_resolution": "",
        "growth_explanation": "",
        "deletion_authorized": False,
    }


def bind_project_memory(
    project_rows: dict[Path, dict[str, Any]],
    owner: Path,
    path: Path,
    evidence: str,
) -> None:
    proof = project_rows[owner]["memory_inventory"]
    if proof["status"] not in {"unresolved", "bound"}:
        raise InventoryError(f"memory candidate conflicts with explicit {proof['status']} decision: {owner}")
    path_value = str(path)
    if path_value not in proof["paths"]:
        proof["paths"].append(path_value)
        proof["paths"].sort()
    if proof["status"] == "unresolved":
        proof["evidence"] = evidence
    elif proof["evidence"] != evidence:
        proof["evidence"] = "Repository and explicit memory candidates were enumerated and bound."
    proof["status"] = "bound"


def build_inventory(
    projects: list[Path],
    memories: list[Path | tuple[Path, Path]],
    global_instructions: list[Path],
    memory_decisions: dict[Path, dict[str, str]] | None = None,
) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    project_rows: list[dict[str, Any]] = []
    project_rows_by_root: dict[Path, dict[str, Any]] = {}
    holds: list[dict[str, Any]] = []
    for root in projects:
        root = root.expanduser().absolute()
        canonical_root = root.resolve()
        row = {
            "root": str(root),
            "root_entries": sorted(path.name for path in root.iterdir()),
            "runnable_stage": None,
            "relationship": "affected",
            "memory_inventory": {
                "status": "unresolved",
                "paths": [],
                "evidence": "",
            },
        }
        project_rows.append(row)
        project_rows_by_root[canonical_root] = row
        for path in sorted(project_candidates(root)):
            records[str(path)] = file_record(path, project_root=root)

    for owner_value, decision in (memory_decisions or {}).items():
        owner = owner_value.expanduser().resolve()
        if owner not in project_rows_by_root:
            raise InventoryError("memory decision owner must be an affected project root")
        status = decision.get("status")
        evidence = str(decision.get("evidence", "")).strip()
        if status not in MEMORY_DECISION_STATUSES:
            raise InventoryError(f"memory decision status must be one of: {', '.join(sorted(MEMORY_DECISION_STATUSES))}")
        if not evidence:
            raise InventoryError("memory decision requires concrete discovery evidence")
        proof = project_rows_by_root[owner]["memory_inventory"]
        if proof["status"] != "unresolved":
            raise InventoryError(f"memory decision conflicts with enumerated memory candidate: {owner}")
        proof.update({"status": status, "paths": [], "evidence": evidence})
        if status == "hold":
            holds.append(
                {
                    "surface": "project_memory",
                    "project_root": project_rows_by_root[owner]["root"],
                    "reason": evidence,
                }
            )

    for memory in memories:
        if isinstance(memory, tuple):
            source, explicit_owner = memory
        else:
            source, explicit_owner = memory, None
        for path in expand_explicit_path(source):
            owner = explicit_owner or next((root for root in projects if path == root or root in path.parents), None)
            if owner is None and len(projects) == 1:
                owner = projects[0]
            owner_key = owner.expanduser().resolve() if owner is not None else None
            surface = "memory_index" if path.name == "MEMORY.md" else "memory_item"
            records[str(path)] = file_record(
                path,
                project_root=owner,
                explicit_surface=surface,
                write_allowed=owner is not None,
            )
            if owner_key is not None:
                bind_project_memory(
                    project_rows_by_root,
                    owner_key,
                    path,
                    "Explicit --memory candidate bound to this project.",
                )

    for source in global_instructions:
        for path in expand_explicit_path(source):
            records[str(path)] = file_record(
                path,
                project_root=None,
                explicit_surface="global_instruction",
                write_allowed=False,
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "projects": project_rows,
        "files": [records[key] for key in sorted(records)],
        "history_sources": [],
        "checks": {name: False for name in REQUIRED_CHECKS},
        "holds": holds,
        "notes": [],
    }


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"unable to read inventory: {path} ({type(exc).__name__})") from exc


def validate_inventory(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["inventory: expected object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: expected {SCHEMA_VERSION}")

    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        errors.append("projects: expected non-empty array")
        projects = []
    memory_claims: list[tuple[str, dict[str, Any], str]] = []
    for index, project in enumerate(projects):
        label = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{label}: expected object")
            continue
        root_value = project.get("root")
        if not isinstance(root_value, str) or not Path(root_value).is_dir():
            errors.append(f"{label}.root: directory missing")
            continue
        if not isinstance(project.get("runnable_stage"), bool):
            errors.append(f"{label}.runnable_stage: must be decided")
        elif project["runnable_stage"]:
            root = Path(root_value)
            if not (root / "README.md").is_file():
                errors.append(f"{label}: runnable project requires README.md")
            if not any((root / name).is_file() for name in INSTRUCTION_NAMES):
                errors.append(f"{label}: runnable project requires AGENTS.md, CLAUDE.md, or equivalent rule surface")
        memory_inventory = project.get("memory_inventory")
        if not isinstance(memory_inventory, dict):
            errors.append(f"{label}.memory_inventory: expected object")
            continue
        status = memory_inventory.get("status")
        paths = memory_inventory.get("paths")
        evidence = str(memory_inventory.get("evidence", "")).strip()
        if status not in MEMORY_STATUSES:
            errors.append(f"{label}.memory_inventory.status: invalid")
        elif status == "unresolved":
            errors.append(f"{label}.memory_inventory.status: unresolved memory discovery blocks closeout")
        if not isinstance(paths, list) or any(not isinstance(path, str) or not path for path in paths):
            errors.append(f"{label}.memory_inventory.paths: expected string array")
            paths = []
        if status == "bound" and not paths:
            errors.append(f"{label}.memory_inventory.paths: bound memory requires at least one path")
        if status in MEMORY_DECISION_STATUSES and paths:
            errors.append(f"{label}.memory_inventory.paths: {status} decision cannot claim bound paths")
        if status != "unresolved" and not evidence:
            errors.append(f"{label}.memory_inventory.evidence: concrete discovery evidence required")
        if isinstance(root_value, str):
            memory_claims.append((root_value, memory_inventory, label))

    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files: expected non-empty enumerated array")
        files = []
    seen: set[str] = set()
    records_by_path: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(files):
        label = f"files[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label}: expected object")
            continue
        path_value = record.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"{label}.path: expected non-empty string")
            continue
        if path_value in seen:
            errors.append(f"{label}.path: duplicate")
        seen.add(path_value)
        records_by_path[path_value] = record
        path = Path(path_value)
        classification = record.get("classification")
        if not path.is_file():
            if classification == "remove_proposal" and record.get("deletion_authorized") is True and str(record.get("reason", "")).strip():
                continue
            errors.append(f"{label}.path: missing file requires remove_proposal, reason, and explicit deletion_authorized")
            continue
        if classification not in CLASSIFICATIONS:
            errors.append(f"{label}.classification: every enumerated file must be classified")
        if record.get("write_allowed") is False and classification in {"update", "merge"}:
            errors.append(f"{label}: read-only global or unbound memory cannot be edited")
        if classification in {"hold", "remove_proposal", "reminder", "out_of_scope"} and not str(record.get("reason", "")).strip():
            errors.append(f"{label}.reason: required for {classification}")

        surface = record.get("surface")
        current_lines = line_count(path)
        current_bytes = path.stat().st_size
        pre_lines = record.get("pre_lines")
        if not isinstance(pre_lines, int) or isinstance(pre_lines, bool) or pre_lines < 0:
            errors.append(f"{label}.pre_lines: expected non-negative integer")
            pre_lines = current_lines
        limit = None
        if surface == "agent_rule":
            limit = 300
        elif surface == "memory_index":
            limit = 150
        elif surface == "memory_item":
            limit = 100
        elif surface == "docs":
            limit = 1500
        oversized = (limit is not None and current_lines > limit) or (surface == "agent_rule" and current_bytes > 15 * 1024)
        if oversized and not str(record.get("size_resolution", "")).strip():
            errors.append(f"{label}.size_resolution: oversized active knowledge must be resolved or held before sync")
        if surface == "agent_rule" and current_lines - pre_lines > 30 and not str(record.get("growth_explanation", "")).strip():
            errors.append(f"{label}.growth_explanation: agent-rule net growth above 30 lines is a red flag")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks: expected object")
    else:
        for name in REQUIRED_CHECKS:
            if checks.get(name) is not True:
                errors.append(f"checks.{name}: must be true before closeout")

    history_sources = data.get("history_sources")
    if not isinstance(history_sources, list) or not history_sources:
        errors.append("history_sources: record transcript, compaction summary, task state, receipt, or an explicit coverage limitation")
    holds = data.get("holds")
    if not isinstance(holds, list):
        errors.append("holds: expected array")
    elif any(not isinstance(item, dict) or not str(item.get("reason", "")).strip() for item in holds):
        errors.append("holds: every hold needs a reason")

    for root_value, proof, label in memory_claims:
        status = proof.get("status")
        paths = proof.get("paths") if isinstance(proof.get("paths"), list) else []
        for path_value in paths:
            record = records_by_path.get(path_value)
            if record is None:
                errors.append(f"{label}.memory_inventory.paths: bound path is not enumerated: {path_value}")
            elif record.get("surface") not in {"memory_index", "memory_item"}:
                errors.append(f"{label}.memory_inventory.paths: bound path is not a memory surface: {path_value}")
            elif record.get("project_root") != root_value:
                errors.append(f"{label}.memory_inventory.paths: bound path belongs to another project: {path_value}")

    expected_paths: set[str] = set()
    for project in projects:
        if isinstance(project, dict) and isinstance(project.get("root"), str) and Path(project["root"]).is_dir():
            expected_paths.update(str(path) for path in project_candidates(Path(project["root"])))
    for missing in sorted(expected_paths - seen):
        errors.append(f"files: current knowledge surface absent from inventory: {missing}")
    return errors


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def cmd_snapshot(args: argparse.Namespace) -> int:
    try:
        projects = [canonical_directory(value) for value in args.project]
        if len(set(projects)) != len(projects):
            raise InventoryError("project roots contain duplicates")
        memories: list[Path | tuple[Path, Path]] = []
        for value in args.memory:
            if "::" in value:
                owner_value, path_value = value.split("::", 1)
                owner = canonical_directory(owner_value)
                if owner not in projects:
                    raise InventoryError("memory binding owner must be an affected --project root")
                memories.append((Path(path_value), owner))
            else:
                if len(projects) > 1:
                    raise InventoryError("external memory in a multi-project run requires PROJECT_ROOT::PATH binding")
                memories.append(Path(value))
        memory_decisions: dict[Path, dict[str, str]] = {}
        for value in args.memory_decision:
            parts = value.split("::", 2)
            if len(parts) == 2 and len(projects) == 1:
                owner, status, evidence = projects[0], parts[0], parts[1]
            elif len(parts) == 3:
                owner = canonical_directory(parts[0])
                status, evidence = parts[1], parts[2]
            else:
                raise InventoryError("memory decision must be STATUS::EVIDENCE for one project or PROJECT_ROOT::STATUS::EVIDENCE")
            if owner not in projects:
                raise InventoryError("memory decision owner must be an affected --project root")
            if owner in memory_decisions:
                raise InventoryError(f"duplicate memory decision: {owner}")
            memory_decisions[owner] = {"status": status, "evidence": evidence}
        data = build_inventory(
            projects,
            memories,
            [Path(value) for value in args.global_instruction],
            memory_decisions,
        )
        if args.output is None:
            if len(projects) != 1:
                raise InventoryError("multi-project snapshots require an explicit --output")
            output = azhou_runtime_state.state_path(projects[0], "repo-pedant", "inventory.json")
            azhou_runtime_state.ensure_private_directory(output.parent, root=projects[0])
        else:
            output = args.output
        write_json(output, data)
    except (InventoryError, azhou_runtime_state.StateError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"schema_version": SCHEMA_VERSION, "projects": len(data["projects"]), "files": len(data["files"]), "output": str(output)}, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        data = read_json(args.inventory)
        errors = validate_inventory(data)
    except InventoryError as exc:
        errors = [str(exc)]
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("snapshot", help="enumerate affected project knowledge before editing")
    snapshot.add_argument("--project", action="append", required=True, help="affected project root; repeat for cross-project work")
    snapshot.add_argument("--memory", action="append", default=[], help="project-memory path; use PROJECT_ROOT::PATH when multiple projects need external memory binding")
    snapshot.add_argument(
        "--memory-decision",
        action="append",
        default=[],
        help="when no bound memory exists: STATUS::EVIDENCE for one project or PROJECT_ROOT::STATUS::EVIDENCE; status is none_discovered or hold",
    )
    snapshot.add_argument("--global-instruction", action="append", default=[], help="read-only global instruction candidate")
    snapshot.add_argument("--output", type=Path)
    snapshot.set_defaults(func=cmd_snapshot)
    validate = subparsers.add_parser("validate", help="validate classifications, bloat gates, and semantic closeout checks")
    validate.add_argument("inventory", type=Path)
    validate.set_defaults(func=cmd_validate)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

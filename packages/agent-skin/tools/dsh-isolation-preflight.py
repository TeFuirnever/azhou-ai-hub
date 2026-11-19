#!/usr/bin/env python3
"""Read-only, static preflight for a planned isolated DSH host lane."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat


SUMMARY_PREFIX = b"azhou-dsh-candidate-tree-v1\0"
HOST_FIELDS = ("bundle_id", "version", "build")


def _candidate_summary_sha256(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate_root_invalid")

    files = []
    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, dirnames, filenames in os.walk(root, followlinks=False, onerror=raise_walk_error):
        current = Path(directory)
        for name in list(dirnames):
            path = current / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError("candidate_tree_unsupported_entry")
        for name in filenames:
            path = current / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("candidate_tree_unsupported_entry")
            files.append(path)
        dirnames.sort()

    if not files:
        raise ValueError("candidate_empty")

    digest = hashlib.sha256(SUMMARY_PREFIX)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest.update(b"file\0")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            remaining = size
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("candidate_changed_during_read")
                digest.update(chunk)
                remaining -= len(chunk)
    return digest.hexdigest()


def _host_record_matches(host: object) -> bool:
    if not isinstance(host, dict):
        return False
    target = host.get("target")
    evidence = host.get("evidence_record")
    if not isinstance(target, dict) or not isinstance(evidence, dict):
        return False
    if not isinstance(evidence.get("source"), str) or not evidence["source"].strip():
        return False
    return all(
        isinstance(target.get(field), str)
        and bool(target[field].strip())
        and evidence.get(field) == target[field]
        for field in HOST_FIELDS
    )


def _raw_plan_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        return None
    return path


def _canonical_plan_path(value: object) -> Path | None:
    path = _raw_plan_path(value)
    if path is None:
        return None
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _target_tree_reasons(
    root: Path,
    targets: dict[str, Path],
    states: dict[str, str],
    protected_roots: list[Path],
) -> set[str]:
    reasons = set()
    nodes = {root}
    children = {}
    role_at_path = {path: role for role, path in targets.items()}
    for role, path in targets.items():
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        current = root
        for part in relative.parts:
            child = current / part
            nodes.add(child)
            children.setdefault(current, set()).add(part)
            current = child

    pruned = set()
    for node in sorted(nodes, key=lambda item: (len(item.parts), str(item))):
        if any(ancestor in pruned for ancestor in node.parents):
            continue
        if any(node == protected or protected in node.parents for protected in protected_roots):
            continue
        try:
            mode = node.lstat().st_mode
        except FileNotFoundError:
            role = role_at_path.get(node)
            if role and states.get(role) == "empty_directory":
                reasons.add(f"planned_path_state_mismatch:{role}")
            continue
        except OSError:
            reasons.add("planned_directory_unreadable")
            continue

        role = role_at_path.get(node)
        if stat.S_ISLNK(mode):
            reasons.add(f"planned_path_symlink:{role}" if role else "planned_path_symlink")
            pruned.add(node)
            continue
        if not stat.S_ISDIR(mode):
            reasons.add(f"planned_path_state_mismatch:{role}" if role else "planned_path_not_directory")
            continue
        if role and states.get(role) == "absent":
            reasons.add(f"planned_path_state_mismatch:{role}")

        allowed = children.get(node, set())
        try:
            with os.scandir(node) as entries:
                for entry in entries:
                    if entry.name not in allowed:
                        reasons.add("historical_nonempty_directory")
                    elif entry.is_symlink():
                        child_role = role_at_path.get(node / entry.name)
                        reasons.add(f"planned_path_symlink:{child_role}" if child_role else "planned_path_symlink")
        except OSError:
            reasons.add("planned_directory_unreadable")
    return reasons


def preflight(plan: object) -> dict:
    """Compare a candidate summary and host evidence record without changing the host."""
    reasons = []
    actual_summary = None
    if not isinstance(plan, dict):
        reasons.append("invalid_plan")
        plan = {}

    candidate = plan.get("candidate")
    candidate_raw = None
    candidate_path = None
    expected_summary = None
    candidate_summary_valid = False
    if not isinstance(candidate, dict):
        reasons.append("candidate_root_invalid")
    else:
        candidate_raw = _raw_plan_path(candidate.get("root"))
        candidate_path = _canonical_plan_path(candidate.get("root"))
        expected_summary = candidate.get("summary_sha256")
        if candidate_raw is None or candidate_path is None:
            reasons.append("candidate_root_invalid")
        candidate_summary_valid = (
            isinstance(expected_summary, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_summary) is not None
        )
        if not candidate_summary_valid:
            reasons.append("candidate_summary_invalid")

    protected_raw = plan.get("protected_roots")
    protected = []
    if not isinstance(protected_raw, list) or not protected_raw:
        reasons.append("protected_roots_invalid")
    else:
        for value in protected_raw:
            canonical = _canonical_plan_path(value)
            if canonical is None:
                reasons.append("protected_root_invalid")
            else:
                protected.append(canonical)

    preparation_root_raw = _raw_plan_path(plan.get("preparation_root"))
    preparation_root = _canonical_plan_path(plan.get("preparation_root"))
    if preparation_root is None or preparation_root_raw is None:
        reasons.append("preparation_root_invalid")
    elif any(_overlaps(preparation_root, root) for root in protected):
        reasons.append("preparation_root_overlaps_protected_root")

    role_names = ("dsh_home", "electron_user_data", "profile", "plugin")
    raw_paths = plan.get("paths")
    paths = {}
    path_inputs = {}
    expected_states = {}
    if not isinstance(raw_paths, dict) or set(raw_paths) != set(role_names):
        reasons.append("planned_paths_invalid")
    else:
        for role in role_names:
            entry = raw_paths[role]
            if not isinstance(entry, dict) or entry.get("expected_state") not in ("absent", "empty_directory"):
                reasons.append(f"planned_path_invalid:{role}")
                continue
            raw_path = _raw_plan_path(entry.get("path"))
            if raw_path is None or preparation_root_raw is None or preparation_root is None:
                reasons.append(f"planned_path_invalid:{role}")
                continue
            try:
                relative = raw_path.relative_to(preparation_root_raw)
            except ValueError:
                reasons.append(f"planned_path_outside_preparation_root:{role}")
                continue
            if not relative.parts:
                reasons.append(f"planned_path_outside_preparation_root:{role}")
                continue
            # Keep target paths lexical under the resolved owned root. Resolving a
            # planned child independently could walk through an ancestor symlink
            # into protected production before the tree scanner can prune it.
            canonical = preparation_root / relative
            path_inputs[role] = raw_path
            paths[role] = canonical
            expected_states[role] = entry["expected_state"]
            if any(_overlaps(canonical, root) for root in protected):
                reasons.append(f"planned_path_overlaps_protected_root:{role}")

    if "dsh_home" in paths:
        for role in ("profile", "plugin"):
            if role in paths and not (paths[role] != paths["dsh_home"] and paths["dsh_home"] in paths[role].parents):
                reasons.append(f"planned_path_relationship_invalid:{role}")
        if "electron_user_data" in paths and _overlaps(paths["dsh_home"], paths["electron_user_data"]):
            reasons.append("planned_path_relationship_invalid:electron_user_data")
    if "profile" in paths and "plugin" in paths and _overlaps(paths["profile"], paths["plugin"]):
        reasons.append("planned_path_relationship_invalid:plugin")
    if "electron_user_data" in paths:
        for role in ("profile", "plugin"):
            if role in paths and _overlaps(paths["electron_user_data"], paths[role]):
                reasons.append(f"planned_path_relationship_invalid:{role}")

    preparation_root_is_protected = (
        preparation_root is not None
        and any(_overlaps(preparation_root, root) for root in protected)
    )
    if (
        preparation_root_raw is not None
        and set(path_inputs) == set(role_names)
        and not preparation_root_is_protected
    ):
        reasons.extend(_target_tree_reasons(preparation_root_raw, path_inputs, expected_states, protected))

    candidate_path_blocked = False
    if candidate_path is not None:
        if preparation_root is not None and _overlaps(candidate_path, preparation_root):
            reasons.append("candidate_overlaps_preparation_root")
            candidate_path_blocked = True
        if any(_overlaps(candidate_path, root) for root in protected):
            reasons.append("candidate_overlaps_protected_root")
            candidate_path_blocked = True
        if any(_overlaps(candidate_path, path) for path in paths.values()):
            reasons.append("candidate_overlaps_planned_path")
            candidate_path_blocked = True

    if candidate_raw is not None and not candidate_path_blocked and candidate_summary_valid:
        try:
            actual_summary = _candidate_summary_sha256(candidate_raw)
        except (OSError, RuntimeError, UnicodeError, ValueError):
            reasons.append("candidate_summary_unavailable")
        if actual_summary is not None and actual_summary != expected_summary:
            reasons.append("candidate_summary_mismatch")

    host_matches = _host_record_matches(plan.get("host"))
    if not host_matches:
        reasons.append("host_target_evidence_mismatch")

    reasons = sorted(set(reasons))
    return {
        "status": "blocked" if reasons else "static_preflight_passed",
        "reasons": reasons,
        "candidate_summary_sha256": actual_summary,
        "host_target_matches_evidence_record": host_matches,
        "runtime_isolation_verified": False,
        "write_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", help="path to the caller's JSON isolation plan")
    args = parser.parse_args(argv)
    try:
        plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
        result = preflight(plan)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        result = {
            "status": "blocked",
            "reasons": ["plan_unreadable"],
            "candidate_summary_sha256": None,
            "host_target_matches_evidence_record": False,
            "runtime_isolation_verified": False,
            "write_authorized": False,
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "static_preflight_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

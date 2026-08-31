#!/usr/bin/env python3
"""Validate Super Caveman's 1+6 composition, routes, and response fixtures."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = Path(__file__).resolve().parent
SKILL = ROOT / "skills" / "super-caveman"
SOURCE_NAMES = {
    "cavecrew",
    "caveman",
    "caveman-commit",
    "caveman-compress",
    "caveman-help",
    "caveman-review",
    "caveman-stats",
}
ROUTES = {"mode", "delegate", "commit", "review", "compress", "help", "stats", "mode-off"}
LEGACY_RESPONSE_IDS = {
    "direct-answer",
    "agent-owned-edit",
    "debugging-cause",
    "concept-explanation",
    "destructive-action",
    "real-ambiguity",
    "multi-step-progress",
    "long-form-request",
    "error-report",
    "casual-message",
    "code-answer",
    "complex-plan",
    "partial-success",
    "medical-boundary",
}
RESPONSE_IDS = LEGACY_RESPONSE_IDS | {
    "under-two-minute-next-action",
    "host-plan-tool-state",
    "task-wins-options",
    "stop-mode-default-style",
    "uncertainty-and-idiom",
}
LEGACY_CASE_SHA256 = "0f4b59246c731e2fb2138ac74a2fc8b9c3bf0c864f2ed3856cb8244fe9ad2598"
LEGACY_RESULT_SHA256 = {
    "revision-a6cfc850-attempt-1-summary.json": "78b67833aef9ad2bf337eb2a851905cd2b7622781fe863d4a82ccd897d3ea9d0",
    "revision-de6b836a-attempt-1-summary.json": "ceeeeda13a7984f5050fb300a8d2f9afb81fc595e4ef6227d08a599b0ddfc9fc",
    "revision-dfe45d69-attempt-1-summary.json": "7fc271a32cb46676dc85ecc2c10c0662b8feabb83886d659cd1d7dd5cf7eac73",
    "revision-e1eef218-attempt-1-summary.json": "97323e91da439bb6e2df90c65b192e52c8a7f1d476e08879523ff69db120db23",
    "revision-f3ab4d37-attempt-1-summary.json": "9e2a6505dbadd0b32d3d8c95cdf0de309b7dbbf8c917581cb5768968fc92dd99",
}
PRIOR_19_CASE_SHA256 = "cfe991555de0f3086ebc4e294266ffe6c8ac84122a748eabdb1d64dece250bb8"
PRIOR_19_RESULT_SHA256 = {
    "revision-daa150ae-attempt-1-summary.json": "88c488455e9ded1a38f786e784d6ea7abde82be8236a8810c5dcae297e193429",
    "revision-8cb8447d-attempt-1-summary.json": "c0ffea2f249c4300f44a6c15aace76fb9cad61c2c9bb950ccfa22b8648096422",
    "revision-e995cac8-attempt-1-summary.json": "f6e160bdb7db057de6e6472a75ee6cf7fe2a1e738f4ac59bca8c05827a9fb0f4",
}
PRIOR_CLOSURE_CASE_SHA256 = "1d75a0a86b3da90c5551e1c6e78c4b09a310ad8a011cc5116fef64ac0d450d19"
PRIOR_CLOSURE_RESULT_SHA256 = {
    "revision-e5f16195-attempt-1-summary.json": "be2d02f6e3d259ee7d41857afe7cd1d32ef949ec099f4e895ce4378746e60715",
}
PRIOR_STATE_CASE_SHA256 = "3136808262609cf5bc9083b379b7f1cf15bb79b788127f012ff294142da09290"
PRIOR_STATE_RESULT_SHA256 = {
    "revision-45121948-attempt-1-summary.json": "cce6d8ef17114efd02dae0a89e7182dcc3ec00c3acf6f2d2a8db809413956058",
    "revision-6210ab51-attempt-1-summary.json": "e3071a4f1da088a45f70bf51d9c54693c9fdcf4088d071a822d3d569e1530f95",
}
CAVEMAN_COMMIT = "11ddc0c9813c8f75365cd5be2f753df08712f154"
ADHD_COMMIT = "b42a45a068e080294924bfba19a7a2e8944c48ff"
ADHD_SKILL_SHA256 = "938d0e350a0c2b0e2e6c3a9032542e062846d108e0f89dd27c798ba5b436397e"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_BLOB_OID = re.compile(r"^[0-9a-f]{40}$")
CAVEMAN_UPSTREAM_SHA256 = {
    "cavecrew": "b74f374f6aae6e9a31e78e7d876860406fe5833378e9298536edf176c12f379b",
    "caveman": "daf9cec496ebd039809d8236f99f17fa1b4beaadf8ce4e2d532d0da51d70afce",
    "caveman-commit": "58db7b8efab911a629c26e7132517d9076e4e3645009eb604cb8c25663477841",
    "caveman-compress": "3167d62440eee99c0e5b224d7f8b8ebcfe37efba38bc5bbee24f0d00da72a688",
    "caveman-help": "ae18884d30b7ddccaefc9612cf73645d9e1eaf18b44d3c36e398b9706f183c1e",
    "caveman-review": "9ef09065f26b9781275b5a4775e14870e331fab833efb2a2aa33f3205a2b83c3",
    "caveman-stats": "b78227f62898b0360d21f2a94d48e9d7a80629cb879cc7b7f9b45b4a241eba90",
}
CAVEMAN_LOCAL_SHA256 = {
    "cavecrew": "b74f374f6aae6e9a31e78e7d876860406fe5833378e9298536edf176c12f379b",
    "caveman": "5e30bb56afbd0b01bd736f2da84180e76f18db4a64de8e124525d5c8dc2e8605",
    "caveman-commit": "58db7b8efab911a629c26e7132517d9076e4e3645009eb604cb8c25663477841",
    "caveman-compress": "8b0d64c622d8a70411bbd86e736ac23cc0465fca1943a37f081e58e9d3afd210",
    "caveman-help": "590d6c6c17254bda56d18da7cc9d0bf252aeec5d1c78b77dd7ae4cabb8404f89",
    "caveman-review": "9ef09065f26b9781275b5a4775e14870e331fab833efb2a2aa33f3205a2b83c3",
    "caveman-stats": "b9e49e46ede956e0c1633eae82a695c996f728bc48f3903f001d301068a2b0ea",
}
CAVEMAN_LINEAGE = {
    name: "upstream-identical" if CAVEMAN_LOCAL_SHA256[name] == digest else "local-derivative-snapshot"
    for name, digest in CAVEMAN_UPSTREAM_SHA256.items()
}
CAVEMAN_DELTA_SHA256 = {
    "caveman": "1b7871a5cbb5fd08223c546020b599ed817286bc7b5a3710fbfb122dd23dfa36",
    "caveman-compress": "62a6d7e2fd39d4d881bed484006847c4905252e9ab633e4d6f9d0d36616b09be",
    "caveman-help": "ca110caaa9c19e2a7c62138fbfb685ce6270539793e6e3c8c117b96e48d209b8",
    "caveman-stats": "645ac78a2d889856153e643cc900b1554e20e71b7671ea06177f01051dfd553d",
}
CAVEMAN_DELTA_PATHS = {
    name: f"upstream/local-source-deltas/{name}.patch" for name in CAVEMAN_DELTA_SHA256
}
APPROVAL_SCHEMA = "super-caveman-exact-diff-approval.v2"
APPROVAL_RECORD_SCHEMA = "super-caveman-exact-diff-approval-record.v2"
RAW_APPROVAL_SCHEMA = "super-caveman-exact-diff-human-record.v1"
REVIEW_RECORD_SCHEMA = "super-caveman-spec-review.v1"
APPROVAL_SCOPE = "all staged task paths except the aggregate result and aggregate approval record"
APPROVAL_STORAGE = "Git aggregate receipt; raw approval Git-external"
RAW_APPROVAL_ENV = "SUPER_CAVEMAN_APPROVAL_RECORD"
REVIEW_RECORD_ENV = "SUPER_CAVEMAN_REVIEW_RECORD"
CONTRACT_FIELDS = {
    "runtime",
    "harness",
    "model",
    "model_limitation",
    "skill_tree_sha256",
    "cases_sha256",
    "tool_permissions",
    "attempt",
    "output_set_sha256",
    "automatic_checks",
    "reviewer",
    "promotion_review",
    "case_results",
    "limitations",
}
GIT_DIFF_PREFIX = [
    "git",
    "-c",
    "color.ui=false",
    "-c",
    "core.quotePath=true",
    "-c",
    "diff.algorithm=myers",
    "-c",
    "diff.external=",
    "-c",
    "diff.indentHeuristic=false",
    "-c",
    "diff.mnemonicPrefix=false",
    "-c",
    "diff.noprefix=false",
    "-c",
    f"diff.orderFile={os.devnull}",
    "-c",
    "diff.renames=false",
    "-c",
    "diff.suppressBlankEmpty=false",
    "diff",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--no-renames",
    "--diff-algorithm=myers",
    "--no-indent-heuristic",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--unified=3",
    "--inter-hunk-context=0",
    "--ignore-submodules=none",
    "--submodule=short",
]


def load(name: str) -> dict:
    return json.loads((BENCHMARK / name).read_text(encoding="utf-8"))


def sha256_file(name: str) -> str:
    return hashlib.sha256((BENCHMARK / name).read_bytes()).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def review_selectors(excluded_paths: set[str]) -> list[str]:
    benchmark_relative = BENCHMARK.relative_to(ROOT)
    root_exclusions: set[str] = set()
    for value in excluded_paths:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe review exclusion: {value}")
        root_exclusions.add((benchmark_relative / path).as_posix())
    return [".", *(f":(top,literal,exclude){path}" for path in sorted(root_exclusions))]


def canonical_git_diff(*arguments: str) -> list[str]:
    return [*GIT_DIFF_PREFIX, *arguments]


def _canonical_blob_tuples(diff_range: str | None, selectors: list[str]) -> list[bytes]:
    arguments = ["--raw", "-z", "--no-renames", "--abbrev=40"]
    if diff_range is not None:
        arguments.append(diff_range)
    arguments.extend(["--", *selectors])
    raw = subprocess.check_output(canonical_git_diff(*arguments), cwd=ROOT)
    fields = raw.split(b"\0")
    tuples: list[bytes] = []
    index = 0
    while index < len(fields) - 1:
        metadata = fields[index]
        index += 1
        if not metadata:
            continue
        path = fields[index]
        index += 1
        parts = metadata.decode("ascii").split()
        if len(parts) != 5 or not parts[-1]:
            # Kept tolerant for callers that replace git output in a narrow
            # unit test; real git --raw output always takes the branch below.
            tuples.append(metadata + b"\0<unknown>\0<unknown>\0")
            continue
        old_oid, new_oid = parts[2], parts[3]
        old_blob = b"<deleted>" if set(old_oid) == {"0"} else old_oid.encode("ascii")
        new_blob = b"<deleted>" if set(new_oid) == {"0"} else new_oid.encode("ascii")
        tuples.append(path + b"\0" + old_blob + b"\0" + new_blob + b"\0")
    return sorted(tuples)


def _canonical_digest(tuples: list[bytes]) -> str:
    return hashlib.sha256(b"".join(tuples)).hexdigest()


def reviewed_blob_tuples(value: object) -> list[bytes] | None:
    if not isinstance(value, list) or not value:
        return None
    tuples: list[bytes] = []
    previous_path: str | None = None
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "old_oid", "new_oid"}:
            return None
        path = item.get("path")
        old_oid = item.get("old_oid")
        new_oid = item.get("new_oid")
        if not isinstance(path, str) or not path or path == ".":
            return None
        path_object = Path(path)
        if path_object.is_absolute() or ".." in path_object.parts or path_object.as_posix() != path:
            return None
        if previous_path is not None and path <= previous_path:
            return None
        if not all(
            isinstance(oid, str) and (oid == "<deleted>" or GIT_BLOB_OID.fullmatch(oid))
            for oid in (old_oid, new_oid)
        ):
            return None
        if old_oid == new_oid:
            return None
        try:
            path_bytes = os.fsencode(path)
        except UnicodeEncodeError:
            return None
        tuples.append(
            path_bytes
            + b"\0"
            + old_oid.encode("ascii")
            + b"\0"
            + new_oid.encode("ascii")
            + b"\0"
        )
        previous_path = path
    return tuples


def _review_digests(base_commit: str, tuples: list[bytes]) -> dict[str, str]:
    return {
        "base_commit": base_commit,
        "path_set_sha256": hashlib.sha256(
            b"".join(item.split(b"\0", 1)[0] + b"\0" for item in tuples)
        ).hexdigest(),
        "staged_patch_sha256": _canonical_digest(tuples),
    }


def _tuple_paths(tuples: list[bytes]) -> list[str]:
    return [os.fsdecode(item.split(b"\0", 1)[0]) for item in tuples]


def reviewed_blob_snapshot_matches(tuples: list[bytes]) -> bool:
    paths = _tuple_paths(tuples)
    selectors = [f":(top,literal){path}" for path in paths]
    try:
        changes = subprocess.check_output(
            canonical_git_diff("--name-only", "-z", "HEAD", "--", *selectors),
            cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    if changes:
        return False
    for item, path in zip(tuples, paths, strict=True):
        _, _, new_oid, _ = item.split(b"\0")
        if new_oid == b"<deleted>":
            absolute = ROOT / path
            if absolute.exists() or absolute.is_symlink():
                return False
            exists = subprocess.run(
                ["git", "cat-file", "-e", f"HEAD:{path}"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if exists.returncode == 0:
                return False
            continue
        try:
            current_oid = subprocess.check_output(
                ["git", "rev-parse", "--verify", f"HEAD:{path}"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return False
        if current_oid != new_oid.decode("ascii"):
            return False
    return True


def _staged_aggregates_match(excluded_paths: set[str]) -> bool:
    benchmark_relative = BENCHMARK.relative_to(ROOT)
    for value in sorted(excluded_paths):
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            return None
        absolute = BENCHMARK / path
        if absolute.is_symlink() or not absolute.is_file():
            return None
        relative = (benchmark_relative / path).as_posix()
        try:
            index_bytes = subprocess.check_output(["git", "show", f":{relative}"], cwd=ROOT)
        except (subprocess.CalledProcessError, OSError):
            return False
        if absolute.read_bytes() != index_bytes:
            return False
    return True


def staged_review_digests(excluded_paths: set[str]) -> dict[str, str] | None:
    selectors = review_selectors(excluded_paths)
    tuples = _canonical_blob_tuples("--cached", selectors)
    if not tuples or not _staged_aggregates_match(excluded_paths):
        return None
    base_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()
    return {
        "base_commit": base_commit,
        "path_set_sha256": hashlib.sha256(b"".join(item.split(b"\0", 1)[0] + b"\0" for item in tuples)).hexdigest(),
        "staged_patch_sha256": _canonical_digest(tuples),
    }


def committed_review_digests(excluded_paths: set[str], base_commit: str) -> dict[str, str] | None:
    try:
        resolved_base = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{base_commit}^{{commit}}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", resolved_base, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode != 0:
        return None
    try:
        benchmark_relative = BENCHMARK.relative_to(ROOT)
    except ValueError:
        return None
    aggregate_blobs: dict[str, bytes] = {}
    for value in sorted(excluded_paths):
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            return None
        aggregate_path = BENCHMARK / path
        if aggregate_path.is_symlink() or not aggregate_path.is_file():
            return None
        aggregate_blobs[(benchmark_relative / path).as_posix()] = aggregate_path.read_bytes()
    if not aggregate_blobs:
        return None
    try:
        commits = subprocess.check_output(
            [
                "git",
                "rev-list",
                "--reverse",
                "--topo-order",
                "--ancestry-path",
                f"{resolved_base}..HEAD",
                "--",
                *sorted(aggregate_blobs),
            ],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
    except subprocess.CalledProcessError:
        return None
    approval_anchor = None
    for commit in commits:
        matches = True
        for relative, expected_bytes in aggregate_blobs.items():
            try:
                committed_bytes = subprocess.check_output(
                    ["git", "show", f"{commit}:{relative}"],
                    cwd=ROOT,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                matches = False
                break
            if committed_bytes != expected_bytes:
                matches = False
                break
        if matches:
            approval_anchor = commit
            break
    if approval_anchor is None:
        return None
    selectors = review_selectors(excluded_paths)
    diff_range = f"{resolved_base}..{approval_anchor}"
    paths = subprocess.check_output(
        canonical_git_diff("--name-only", "-z", diff_range, "--", *selectors),
        cwd=ROOT,
    )
    items = sorted(item for item in paths.split(b"\0") if item)
    if not items:
        return None
    approved_path_selectors = [
        f":(top,literal){os.fsdecode(item)}" for item in items
    ]
    later_commits = subprocess.check_output(
        ["git", "rev-list", f"{approval_anchor}..HEAD", "--", *approved_path_selectors],
        cwd=ROOT,
    )
    if later_commits.strip():
        return None
    working_tree_changes = subprocess.check_output(
        canonical_git_diff(
            "--name-only", "-z", "HEAD", "--", *approved_path_selectors
        ),
        cwd=ROOT,
    )
    if working_tree_changes:
        return None
    tuples = _canonical_blob_tuples(diff_range, selectors)
    if not tuples:
        return None
    return {
        "base_commit": resolved_base,
        "path_set_sha256": hashlib.sha256(b"".join(item.split(b"\0", 1)[0] + b"\0" for item in tuples)).hexdigest(),
        "staged_patch_sha256": _canonical_digest(tuples),
    }


def committed_review_digests_from_blobs(
    excluded_paths: set[str],
    base_commit: str,
    tuples: list[bytes],
) -> dict[str, str] | None:
    try:
        resolved_base = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{base_commit}^{{commit}}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", resolved_base, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode != 0:
        return None
    paths = _tuple_paths(tuples)
    approved_path_selectors = [f":(top,literal){path}" for path in paths]
    try:
        commits = subprocess.check_output(
            [
                "git",
                "rev-list",
                "--reverse",
                "--topo-order",
                "--ancestry-path",
                f"{resolved_base}..HEAD",
                "--",
                *approved_path_selectors,
            ],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
    except (OSError, subprocess.CalledProcessError):
        return None
    selectors = review_selectors(excluded_paths)
    approval_anchor = None
    for commit in commits:
        candidate = _canonical_blob_tuples(
            f"{resolved_base}..{commit}",
            selectors,
        )
        if candidate == tuples:
            approval_anchor = commit
            break
    if approval_anchor is None:
        return None
    later_commits = subprocess.check_output(
        ["git", "rev-list", f"{approval_anchor}..HEAD", "--", *approved_path_selectors],
        cwd=ROOT,
    )
    if later_commits.strip():
        return None
    working_tree_changes = subprocess.check_output(
        canonical_git_diff(
            "--name-only", "-z", "HEAD", "--", *approved_path_selectors
        ),
        cwd=ROOT,
    )
    if working_tree_changes:
        return None
    return _review_digests(resolved_base, tuples)


def is_approved_exact_diff(
    value: object,
    result_path: Path,
    *,
    require_external_evidence: bool = True,
) -> bool:
    required = {
        "schema",
        "status",
        "review_scope",
        "base_commit",
        "path_set_sha256",
        "staged_patch_sha256",
        "approver",
        "approved_at",
        "record_path",
        "record_sha256",
        "record_storage",
    }
    if not isinstance(value, dict) or set(value) != required:
        return False
    if (
        value.get("schema") != APPROVAL_SCHEMA
        or value.get("status") != "approved"
        or value.get("review_scope") != APPROVAL_SCOPE
        or value.get("record_storage") != APPROVAL_STORAGE
        or re.fullmatch(r"[0-9a-f]{40}", str(value.get("base_commit"))) is None
        or not is_sha256(value.get("path_set_sha256"))
        or not is_sha256(value.get("staged_patch_sha256"))
        or not is_sha256(value.get("record_sha256"))
        or not isinstance(value.get("approver"), str)
        or not value.get("approver", "").strip()
        or not isinstance(value.get("approved_at"), str)
    ):
        return False
    try:
        approved_at = datetime.fromisoformat(value["approved_at"].replace("Z", "+00:00"))
    except ValueError:
        return False
    if approved_at.tzinfo is None:
        return False

    record_relative = value.get("record_path")
    if not isinstance(record_relative, str):
        return False
    record_relative_path = Path(record_relative)
    if (
        record_relative_path.is_absolute()
        or ".." in record_relative_path.parts
        or re.fullmatch(r"results/revision-[0-9a-f]{8}-exact-diff-approval\.json", record_relative) is None
    ):
        return False
    record_path = BENCHMARK / record_relative_path
    if record_path.is_symlink() or not record_path.is_file():
        return False
    try:
        record_bytes = record_path.read_bytes()
        record = json.loads(record_bytes.decode("utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    if hashlib.sha256(record_bytes).hexdigest() != value["record_sha256"]:
        return False
    expected_record_keys = {
        "schema",
        "decision",
        "approver",
        "approved_at",
        "base_commit",
        "review_scope",
        "path_set_sha256",
        "staged_patch_sha256",
        "reviewed_blobs",
        "raw_approval_record_sha256",
        "raw_approval_storage",
    }
    if (
        not isinstance(record, dict)
        or set(record) != expected_record_keys
        or record.get("schema") != APPROVAL_RECORD_SCHEMA
        or record.get("decision") != "approved"
        or record.get("approver") != value["approver"]
        or record.get("approved_at") != value["approved_at"]
        or record.get("base_commit") != value["base_commit"]
        or record.get("review_scope") != value["review_scope"]
        or record.get("path_set_sha256") != value["path_set_sha256"]
        or record.get("staged_patch_sha256") != value["staged_patch_sha256"]
        or record.get("raw_approval_storage") != "Git-external"
        or not is_sha256(record.get("raw_approval_record_sha256"))
    ):
        return False
    reviewed_tuples = reviewed_blob_tuples(record.get("reviewed_blobs"))
    if reviewed_tuples is None:
        return False
    declared_review = _review_digests(value["base_commit"], reviewed_tuples)
    if not all(
        declared_review[key] == value[key]
        for key in ("base_commit", "path_set_sha256", "staged_patch_sha256")
    ):
        return False

    try:
        result_relative = result_path.relative_to(BENCHMARK).as_posix()
    except ValueError:
        return False
    exclusions = {result_relative, record_relative}
    try:
        candidates = [staged_review_digests(exclusions)]
        candidates.append(committed_review_digests(exclusions, value["base_commit"]))
        candidates.append(
            committed_review_digests_from_blobs(
                exclusions,
                value["base_commit"],
                reviewed_tuples,
            )
        )
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False
    exact_replay = any(
        candidate is not None
        and all(
            candidate[key] == value[key]
            for key in ("base_commit", "path_set_sha256", "staged_patch_sha256")
        )
        for candidate in candidates
    )
    if not exact_replay:
        if require_external_evidence or not reviewed_blob_snapshot_matches(reviewed_tuples):
            return False

    if not require_external_evidence:
        return True

    # A Git aggregate receipt is not an authentication mechanism. Require the
    # original Git-external approval and review records on every replay so a
    # repository-only copy cannot promote itself after ingest.
    raw_path_value = os.environ.get(RAW_APPROVAL_ENV)
    review_path_value = os.environ.get(REVIEW_RECORD_ENV)
    if not raw_path_value or not review_path_value:
        return False
    raw_candidate = Path(raw_path_value)
    if (
        not raw_candidate.is_absolute()
        or raw_candidate.is_symlink()
        or not raw_candidate.is_file()
    ):
        return False

    try:
        raw_path = raw_candidate.resolve(strict=True)
        raw_path.relative_to(ROOT.resolve())
    except FileNotFoundError:
        return False
    except ValueError:
        pass
    else:
        return False
    try:
        raw_bytes = raw_path.read_bytes()
        raw_record = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    raw_keys = {
        "schema", "decision", "approver", "approved_at", "base_commit",
        "review_scope", "path_set_sha256", "staged_patch_sha256",
    }
    if (
        hashlib.sha256(raw_bytes).hexdigest() != record["raw_approval_record_sha256"]
        or not isinstance(raw_record, dict)
        or set(raw_record) != raw_keys
        or raw_record.get("schema") != RAW_APPROVAL_SCHEMA
        or raw_record.get("decision") != "approved"
        or any(raw_record.get(key) != value[key] for key in (
            "approver", "approved_at", "base_commit", "review_scope",
            "path_set_sha256", "staged_patch_sha256",
        ))
    ):
        return False

    review_candidate = Path(review_path_value)
    if (
        not review_candidate.is_absolute()
        or review_candidate.is_symlink()
        or not review_candidate.is_file()
    ):
        return False
    try:
        review_path = review_candidate.resolve(strict=True)
        review_path.relative_to(ROOT.resolve())
    except FileNotFoundError:
        return False
    except ValueError:
        pass
    else:
        return False
    try:
        review_bytes = review_path.read_bytes()
        review_record = json.loads(review_bytes.decode("utf-8"))
        result_record = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    reviewer = result_record.get("reviewer") if isinstance(result_record, dict) else None
    promotion = result_record.get("promotion_review") if isinstance(result_record, dict) else None
    candidate_raw_sha256 = promotion.get("candidate_raw_sha256") if isinstance(promotion, dict) else None
    if (
        not isinstance(review_record, dict)
        or not isinstance(reviewer, dict)
        or not isinstance(candidate_raw_sha256, str)
        or review_record.get("schema") != REVIEW_RECORD_SCHEMA
        or hashlib.sha256(review_bytes).hexdigest() != reviewer.get("review_sha256")
        or review_record.get("identity") != reviewer.get("identity")
        or review_record.get("candidate_raw_sha256") != candidate_raw_sha256
        or review_record.get("cases_sha256") != result_record.get("cases_sha256")
    ):
        return False
    return True


def sha256_skill_tree() -> str:
    digest = hashlib.sha256()
    files = sorted(
        (
            path
            for path in SKILL.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.relative_to(SKILL).as_posix(),
    )
    for path in files:
        digest.update(path.relative_to(SKILL).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def check(*, require_promotion_evidence: bool = False) -> list[str]:
    errors: list[str] = []
    manifest = load("manifest.json")
    mapping = load("capability-map.json")
    triggers = load("trigger-cases.json")
    responses = load("response-cases.json")
    contract = load("evaluation-contract.json")
    manifest_inputs = set(manifest.get("inputs", []))
    required_delta_inputs = set(CAVEMAN_DELTA_PATHS.values())
    if not required_delta_inputs.issubset(manifest_inputs):
        errors.append("manifest must register every local source delta")
    for relative in manifest_inputs:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not (BENCHMARK / path).is_file():
            errors.append(f"manifest input is missing or unsafe: {relative}")

    upstreams = manifest.get("upstreams", {})
    if upstreams != {"caveman": CAVEMAN_COMMIT, "i_have_adhd": ADHD_COMMIT}:
        errors.append("manifest must pin both immutable upstream commits")
    mapped_upstreams = mapping.get("upstreams", {})
    caveman_upstream = mapped_upstreams.get("caveman", {})
    if caveman_upstream.get("commit") != CAVEMAN_COMMIT:
        errors.append("Caveman commit differs between manifest and capability map")
    if set(caveman_upstream.get("byte_identical_entries", [])) != {
        name for name, lineage in CAVEMAN_LINEAGE.items() if lineage == "upstream-identical"
    } or set(caveman_upstream.get("local_derivative_entries", [])) != {
        name for name, lineage in CAVEMAN_LINEAGE.items() if lineage == "local-derivative-snapshot"
    }:
        errors.append("Caveman local derivative lineage set differs from trusted hashes")
    if mapped_upstreams.get("i_have_adhd", {}).get("commit") != ADHD_COMMIT:
        errors.append("i-have-adhd commit differs between manifest and capability map")
    if mapped_upstreams.get("i_have_adhd", {}).get("skill_sha256") != ADHD_SKILL_SHA256:
        errors.append("i-have-adhd skill hash differs from the pinned source")
    if mapping.get("canonical_skill") != "super-caveman":
        errors.append("canonical package must be super-caveman")
    if mapping.get("positioning") != "original-caveman-enhanced":
        errors.append("capability map must position the package as an original Caveman enhancement")
    if mapping.get("core_source") != "caveman" or mapping.get("absorbed_companions") != 6:
        errors.append("capability map must preserve one Caveman core plus six companions")

    claims = manifest.get("claims", {})
    expected_claims = {
        "mapped_source_skills": 7,
        "core_source_skills": 1,
        "absorbed_companion_skills": 6,
        "response_style_sources": 1,
        "installable_packages": 1,
        "trigger_routes": 8,
        "response_cases": 19,
    }
    for key, value in expected_claims.items():
        if claims.get(key) != value:
            errors.append(f"manifest claim mismatch: {key}")

    response_style = mapping.get("response_style", {})
    if (
        response_style.get("source") != "i_have_adhd"
        or response_style.get("status") != "fully-adopted"
        or response_style.get("surface") != "references/modes.md"
    ):
        errors.append("response style must fully adopt i-have-adhd behavior in the modes reference")

    sources = mapping.get("sources", [])
    names = {item.get("name") for item in sources}
    if names != SOURCE_NAMES or len(sources) != len(SOURCE_NAMES):
        errors.append("capability map must cover the Caveman core plus six unique companions")
    for item in sources:
        name = item.get("name")
        if item.get("local_snapshot_sha256") != CAVEMAN_LOCAL_SHA256.get(name):
            errors.append(f"local source hash differs from trusted snapshot: {name}")
        if item.get("upstream_sha256") != CAVEMAN_UPSTREAM_SHA256.get(name):
            errors.append(f"upstream source hash differs from pinned commit: {name}")
        if item.get("lineage") != CAVEMAN_LINEAGE.get(name):
            errors.append(f"source lineage differs from trusted hash relationship: {name}")
        expected_delta = CAVEMAN_DELTA_SHA256.get(name)
        expected_delta_path = CAVEMAN_DELTA_PATHS.get(name)
        if expected_delta is None:
            if "delta_path" in item or "delta_sha256" in item:
                errors.append(f"upstream-identical source must not declare a local delta: {name}")
        elif item.get("delta_path") != expected_delta_path or item.get("delta_sha256") != expected_delta:
            errors.append(f"local derivative delta differs from trusted patch: {name}")
        elif hashlib.sha256((BENCHMARK / expected_delta_path).read_bytes()).hexdigest() != expected_delta:
            errors.append(f"local derivative delta bytes changed: {name}")
        for relative in item.get("surface", "").split(" and "):
            if not (SKILL / relative).is_file():
                errors.append(f"mapped runtime surface missing: {relative}")

    cases = triggers.get("cases", [])
    if len(cases) != 8 or {case.get("route") for case in cases} != ROUTES:
        errors.append("trigger cases must cover exactly eight routes")
    for case in cases:
        if not (SKILL / case.get("reference", "")).is_file():
            errors.append(f"trigger reference missing: {case.get('reference')}")
        if case.get("route") != "mode-off" and not case.get("input", "").startswith("/super-caveman"):
            errors.append(f"primary trigger is not canonical: {case.get('route')}")

    response_cases = responses.get("cases", [])
    if len(response_cases) != 19 or {case.get("id") for case in response_cases} != RESPONSE_IDS:
        errors.append("response fixtures must contain the nineteen pinned source cases")
    source = responses.get("source", {})
    if source.get("commit") != ADHD_COMMIT or source.get("skill_sha256") != ADHD_SKILL_SHA256:
        errors.append("response fixture provenance differs from the pinned source")
    for case in response_cases:
        if case.get("risk") not in {"low", "medium", "high"}:
            errors.append(f"invalid response risk: {case.get('id')}")
        if not case.get("prompt") or not case.get("criteria"):
            errors.append(f"incomplete response fixture: {case.get('id')}")

    contract_cases = contract.get("cases", {})
    if contract.get("schema") != "super-caveman-evaluation-contract.v1":
        errors.append("evaluation contract schema mismatch")
    if contract_cases.get("path") != "response-cases.json":
        errors.append("evaluation contract must bind response-cases.json")
    if contract_cases.get("sha256") != sha256_file("response-cases.json"):
        errors.append("evaluation contract case digest is stale")
    if contract_cases.get("count") != len(response_cases):
        errors.append("evaluation contract case count mismatch")
    legacy_case_sets = contract.get("legacy_case_sets")
    expected_legacy_case_sets = [
        {
            "sha256": LEGACY_CASE_SHA256,
            "count": len(LEGACY_RESPONSE_IDS),
            "case_ids": sorted(LEGACY_RESPONSE_IDS),
            "result_files": LEGACY_RESULT_SHA256,
        },
        {
            "sha256": PRIOR_19_CASE_SHA256,
            "count": len(RESPONSE_IDS),
            "case_ids": sorted(RESPONSE_IDS),
            "result_files": PRIOR_19_RESULT_SHA256,
        },
        {
            "sha256": PRIOR_CLOSURE_CASE_SHA256,
            "count": len(RESPONSE_IDS),
            "case_ids": sorted(RESPONSE_IDS),
            "result_files": PRIOR_CLOSURE_RESULT_SHA256,
        },
        {
            "sha256": PRIOR_STATE_CASE_SHA256,
            "count": len(RESPONSE_IDS),
            "case_ids": sorted(RESPONSE_IDS),
            "result_files": PRIOR_STATE_RESULT_SHA256,
        },
    ]
    if legacy_case_sets != expected_legacy_case_sets:
        errors.append("evaluation contract legacy case metadata mismatch")
    execution = contract.get("execution", {})
    if execution.get("attempt") != 1 or execution.get("maximum_attempts") != 1:
        errors.append("evaluation contract must freeze attempt 1")
    if execution.get("timeout_seconds_per_case") != 120 or execution.get("concurrency") != 2:
        errors.append("evaluation contract runtime bounds changed")
    permissions = execution.get("tool_permissions", {})
    defaults = permissions.get("default", {})
    if any(defaults.get(name) is not False for name in ("network", "repository_write", "shell", "external_apps")):
        errors.append("evaluation producer defaults must deny mutable and external tools")
    overrides = permissions.get("case_overrides", {})
    if set(overrides) != {"agent-owned-edit"}:
        errors.append("only agent-owned-edit may override evaluation tools")
    agent_override = overrides.get("agent-owned-edit", {})
    if agent_override.get("repository_write") != "disposable fixture only":
        errors.append("agent-owned-edit write permission must stay fixture-scoped")
    fixture = execution.get("fixtures", {}).get("agent-owned-edit", {})
    if fixture.get("initial_file", {}).get("utf8") == fixture.get("required_file", {}).get("utf8"):
        errors.append("agent-owned-edit fixture must require a real edit")
    if set(contract.get("evidence", {}).get("required_result_fields", [])) != CONTRACT_FIELDS:
        errors.append("evaluation result field contract mismatch")
    gate = contract.get("claim_gate", {})
    if (
        gate.get("required_passed_cases") != len(RESPONSE_IDS)
        or gate.get("required_total_cases") != len(RESPONSE_IDS)
        or gate.get("high_risk_failures_allowed") != 0
    ):
        errors.append("evaluation claim gate is weaker than the response suite")
    promotion = contract.get("promotion_review", {})
    if promotion.get("independent_paired_judges") != 3:
        errors.append("promotion review must require three independent paired judges")
    if promotion.get("presentation_orders") != [
        "candidate-baseline", "baseline-candidate", "candidate-baseline"
    ]:
        errors.append("promotion review must reverse paired presentation order")
    if promotion.get("candidate_majority_required") != 2 or promotion.get("high_risk_regressions_allowed") != 0:
        errors.append("promotion review majority or safety gate is too weak")
    approval_contract = promotion.get("exact_diff_human_approval")
    if (
        not isinstance(approval_contract, dict)
        or approval_contract.get("required") is not True
        or approval_contract.get("schema") != APPROVAL_SCHEMA
        or approval_contract.get("review_scope") != APPROVAL_SCOPE
        or approval_contract.get("record_storage") != APPROVAL_STORAGE
        or approval_contract.get("raw_record_schema") != RAW_APPROVAL_SCHEMA
        or approval_contract.get("raw_record_environment") != RAW_APPROVAL_ENV
        or approval_contract.get("review_record_environment") != REVIEW_RECORD_ENV
        or "every promotion ingest and replay" not in approval_contract.get("raw_record_validation", "")
        or "regular file" not in approval_contract.get("raw_record_validation", "")
        or "actual SHA-256" not in approval_contract.get("raw_record_validation", "")
        or REVIEW_RECORD_ENV not in approval_contract.get("raw_record_validation", "")
        or "every promotion replay revalidates both Git-external raw records" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "byte-identical index and working-tree" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "current staged or committed exact-diff" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "public squash replay" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "reviewed_blobs" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "each approved target blob must match HEAD" not in approval_contract.get(
            "approved_replay_validation", ""
        )
        or "path/blob tuples" not in approval_contract.get("digest_algorithm", "")
        or set(approval_contract.get("required_approved_fields", [])) != {
            "status",
            "approver",
            "approved_at",
            "base_commit",
            "path_set_sha256",
            "staged_patch_sha256",
            "record_path",
            "record_sha256",
        }
    ):
        errors.append("promotion review must retain structured exact-diff human approval")

    current_case_sha256 = sha256_file("response-cases.json")
    current_skill_tree_sha256 = sha256_skill_tree()
    known_case_sets = {
        current_case_sha256: RESPONSE_IDS,
        LEGACY_CASE_SHA256: LEGACY_RESPONSE_IDS,
        PRIOR_19_CASE_SHA256: RESPONSE_IDS,
        PRIOR_CLOSURE_CASE_SHA256: RESPONSE_IDS,
        PRIOR_STATE_CASE_SHA256: RESPONSE_IDS,
    }
    immutable_result_sets = {
        LEGACY_CASE_SHA256: LEGACY_RESULT_SHA256,
        PRIOR_19_CASE_SHA256: PRIOR_19_RESULT_SHA256,
        PRIOR_CLOSURE_CASE_SHA256: PRIOR_CLOSURE_RESULT_SHA256,
        PRIOR_STATE_CASE_SHA256: PRIOR_STATE_RESULT_SHA256,
    }
    current_passing_results: list[Path] = []
    for result_path in sorted((BENCHMARK / "results").glob("*-summary.json")):
        result_bytes = result_path.read_bytes()
        result = json.loads(result_bytes.decode("utf-8"))
        missing = CONTRACT_FIELDS - set(result)
        if missing:
            errors.append(f"evaluation result missing fields in {result_path.name}: {sorted(missing)}")
            continue
        if result.get("schema") != "super-caveman-evaluation-result.v1":
            errors.append(f"evaluation result schema mismatch: {result_path.name}")
        if result.get("attempt") != 1:
            errors.append(f"evaluation result must be attempt 1: {result_path.name}")
        result_case_sha256 = result.get("cases_sha256")
        result_case_ids = known_case_sets.get(result_case_sha256)
        if result_case_ids is None:
            errors.append(f"evaluation result case digest is unknown: {result_path.name}")
            result_case_ids = set()
        if result_case_sha256 in immutable_result_sets:
            expected_result_sha256 = immutable_result_sets[result_case_sha256].get(result_path.name)
            if expected_result_sha256 is None:
                errors.append(f"legacy evaluation result is not registered: {result_path.name}")
            elif hashlib.sha256(result_bytes).hexdigest() != expected_result_sha256:
                errors.append(f"legacy evaluation result bytes changed: {result_path.name}")
        if not is_sha256(result.get("skill_tree_sha256")):
            errors.append(f"evaluation result skill digest invalid: {result_path.name}")
        if not is_sha256(result.get("output_set_sha256")):
            errors.append(f"evaluation result output digest invalid: {result_path.name}")
        permissions = result.get("tool_permissions")
        if not isinstance(permissions, dict) or set(permissions) != {
            "network", "repository_write", "shell", "external_apps"
        } or any(
            not isinstance(value, (bool, str)) or isinstance(value, str) and not value.strip()
            for value in permissions.values()
        ):
            errors.append(f"evaluation result tool permissions are incomplete: {result_path.name}")
        reviewer = result.get("reviewer")
        if (
            not isinstance(reviewer, dict)
            or not isinstance(reviewer.get("identity"), str)
            or not reviewer.get("identity", "").strip()
            or not is_sha256(reviewer.get("review_sha256"))
        ):
            errors.append(f"evaluation reviewer evidence is invalid: {result_path.name}")
        case_results = result.get("case_results", [])
        if (
            len(case_results) != len(result_case_ids)
            or {item.get("id") for item in case_results} != result_case_ids
        ):
            errors.append(f"evaluation result case coverage mismatch: {result_path.name}")
        passed = sum(item.get("status") == "pass" for item in case_results)
        failed = sum(item.get("status") == "fail" for item in case_results)
        if (
            result.get("passed") != passed
            or result.get("failed") != failed
            or passed + failed != len(result_case_ids)
        ):
            errors.append(f"evaluation result totals mismatch: {result_path.name}")
        status = result.get("status")
        if status not in {"failed", "superseded", "pass"}:
            errors.append(f"evaluation result status is invalid: {result_path.name}")
        claimed_pass = status == "pass"
        gate_pass = (
            passed == len(result_case_ids)
            and result.get("high_risk_failed") == 0
            and result.get("format_failed") == 0
        )
        if status == "failed" and gate_pass or status in {"pass", "superseded"} and not gate_pass:
            errors.append(f"evaluation result claim gate mismatch: {result_path.name}")
        current_claimed_pass = claimed_pass and result_case_sha256 == current_case_sha256
        if current_claimed_pass and result.get("skill_tree_sha256") != current_skill_tree_sha256:
            errors.append(
                f"current passing evaluation result is not bound to the current stable skill tree: "
                f"{result_path.name}"
            )
        if current_claimed_pass and result.get("skill_tree_sha256") == current_skill_tree_sha256:
            current_passing_results.append(result_path)
            paired = result.get("promotion_review")
            judges = paired.get("judges", []) if isinstance(paired, dict) else []
            identities = {judge.get("identity") for judge in judges if isinstance(judge, dict)}
            identities_valid = all(
                isinstance(judge.get("identity"), str) and judge.get("identity", "").strip()
                for judge in judges
                if isinstance(judge, dict)
            )
            orders = [judge.get("order") for judge in judges if isinstance(judge, dict)]
            candidate_votes = sum(judge.get("vote") == "candidate" for judge in judges if isinstance(judge, dict))
            judge_digests_valid = all(
                is_sha256(judge.get("record_sha256"))
                for judge in judges
                if isinstance(judge, dict)
            )
            approval = paired.get("exact_diff_human_approval") if isinstance(paired, dict) else None
            if (
                not isinstance(paired, dict)
                or paired.get("paired_status") != "pass"
                or not is_sha256(paired.get("baseline_output_set_sha256"))
                or paired.get("candidate_output_set_sha256") != result.get("output_set_sha256")
                or len(judges) != 3
                or len(identities) != 3
                or not identities_valid
                or orders != promotion.get("presentation_orders")
                or candidate_votes < promotion.get("candidate_majority_required", 2)
                or paired.get("high_risk_regressions") != 0
                or not judge_digests_valid
                or not isinstance(approval, dict)
                or approval.get("record_path") not in manifest_inputs
                or not is_approved_exact_diff(
                    approval,
                    result_path,
                    require_external_evidence=require_promotion_evidence,
                )
            ):
                errors.append(f"passing evaluation result lacks valid paired promotion evidence: {result_path.name}")

    if len(current_passing_results) != 1:
        errors.append(
            f"exactly one current passing evaluation result is required; "
            f"found {len(current_passing_results)}"
        )

    for alias in SOURCE_NAMES:
        if (ROOT / "skills" / alias / "SKILL.md").exists():
            errors.append(f"absorbed source remains installable: {alias}")
    if not (SKILL / "SKILL.md").is_file():
        errors.append("canonical super-caveman package missing")
    errors.extend(lifecycle_errors())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.add_argument(
        "--promotion-evidence",
        action="store_true",
        help="Require the Git-external approval and review records used for maintainer promotion",
    )
    args = parser.parse_args()
    errors = check(require_promotion_evidence=args.promotion_evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    mode = "promotion evidence" if args.promotion_evidence else "public integrity"
    lifecycle_count = len(json.loads((BENCHMARK / "lifecycle-cases.json").read_text(encoding="utf-8"))["cases"])
    print(f"super-caveman benchmark {mode} passed: 1 core + 6 companions, 1 package, 8 routes, 19 response cases, {lifecycle_count} lifecycle cases")
    return 0




def lifecycle_errors() -> list[str]:
    """Run normalized lifecycle contract cases against the real adapter."""
    import subprocess
    import sys
    import tempfile

    spec = json.loads((BENCHMARK / "lifecycle-cases.json").read_text(encoding="utf-8"))
    adapter = ROOT / spec["adapter"]
    if not adapter.is_file():
        return [f"lifecycle adapter missing: {spec['adapter']}"]
    errors: list[str] = []

    def substitute(value: str, project: Path, home: Path) -> str:
        return value.replace("PROJECT", str(project)).replace("HOME", str(home))

    def run_item(item: dict, project: Path, home: Path) -> tuple[int, str, str]:
        argv = [sys.executable, str(adapter), item["command"]]
        for flag in item.get("argv", []):
            argv.append(substitute(flag, project, home))
        if item["command"] in ("setup", "uninstall", "enable", "disable"):
            argv.extend(["--project-dir", str(project), "--home-dir", str(home)])
        else:
            argv.extend(["--home-dir", str(home)])
        stdin_text = ""
        if "payload" in item:
            payload = dict(item["payload"])
            payload["cwd"] = str(project)
            stdin_text = json.dumps(payload)
        if "raw_stdin" in item:
            stdin_text = item["raw_stdin"]
        done = subprocess.run(
            argv, input=stdin_text, capture_output=True, text=True,
            check=False, timeout=10,
        )
        return done.returncode, done.stdout.strip(), done.stderr.strip()

    def settings_owned(project: Path, event: str) -> int:
        settings_file = project / ".claude" / "settings.json"
        if not settings_file.exists():
            return 0
        payload = json.loads(settings_file.read_text(encoding="utf-8"))
        entries = payload.get("hooks", {}).get(event, [])
        return sum(1 for entry in entries if "claude_adapter.py" in json.dumps(entry))

    def check_context(case_spec: dict, context: str, cid: str) -> None:
        low = context.lower()
        for fragment in case_spec.get("expect_contains", []):
            if fragment.lower() not in low:
                errors.append(f"lifecycle case {cid}: missing fragment: {fragment}")
        for fragment in case_spec.get("expect_absent", []):
            if fragment.lower() in low:
                errors.append(f"lifecycle case {cid}: unexpected fragment: {fragment}")
        limit = case_spec.get("max_chars")
        if limit is not None and len(context) > limit:
            errors.append(f"lifecycle case {cid}: context exceeds {limit} chars")

    def run_case(case_spec: dict) -> None:
        cid = case_spec["id"]
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "proj"
            home = Path(raw) / "home"
            project.mkdir()
            home.mkdir()
            try:
                for _ in range(int(case_spec.get("setup_runs", 1))):
                    code, _o, err = run_item({"command": "setup",
                                              "argv": ["--scope", "project",
                                                       "--project-dir", "PROJECT",
                                                       "--home-dir", "HOME"]}, project, home)
                    if code != 0:
                        raise RuntimeError(f"setup exit {code}: {err}")
                if case_spec.get("corrupt_session"):
                    corrupt = project / ".azhou" / "super-caveman" / "sessions" / f"{case_spec['corrupt_session']}.json"
                    corrupt.parent.mkdir(parents=True, exist_ok=True)
                    corrupt.write_text("{broken", encoding="utf-8")
                for pre in case_spec.get("prelude", []):
                    code, _o, err = run_item(pre, project, home)
                    if code != 0:
                        raise RuntimeError(f"prelude {pre.get('command')} exit {code}: {err}")
                code, out, err = run_item(case_spec["event"], project, home)
                if case_spec.get("expect_exit_nonzero"):
                    if code == 0:
                        errors.append(f"lifecycle case {cid}: expected nonzero exit, got 0")
                    return
                if code != 0:
                    errors.append(f"lifecycle case {cid}: exit {code}: {err}")
                    return
                if case_spec.get("expect_empty_object"):
                    if out != "{}":
                        errors.append(f"lifecycle case {cid}: expected empty protocol object")
                    return
                payload = json.loads(out)
                context = payload.get("hookSpecificOutput", {}).get("additionalContext")
                if context is None:
                    if case_spec.get("expect_contains"):
                        errors.append(f"lifecycle case {cid}: expected output, got none")
                    for fragment in case_spec.get("expect_absent", []):
                        if fragment.lower() in out.lower():
                            errors.append(f"lifecycle case {cid}: unexpected fragment in empty output: {fragment}")
                    after = case_spec.get("final_session")
                    if after:
                        state_file = project / ".azhou" / "super-caveman" / "sessions" / f"{after['session_id']}.json"
                        state = json.loads(state_file.read_text(encoding="utf-8"))
                        for key, want in after.items():
                            if key != "session_id" and state.get(key) != want:
                                errors.append(f"lifecycle case context-less case {cid}: session {key}={state.get(key)} want {want}")
                    return
                check_context(case_spec, context, cid)
                if case_spec.get("event_again"):
                    code2, out2, err2 = run_item(case_spec["event_again"], project, home)
                    if code2 != 0:
                        errors.append(f"lifecycle case {cid}: repeat exit {code2}: {err2}")
                    else:
                        repeat = json.loads(out2).get("hookSpecificOutput", {}).get("additionalContext")
                        if repeat != context:
                            errors.append(f"lifecycle case {cid}: repeated delivery output differs")
                after = case_spec.get("final_session")
                if after:
                    state_file = project / ".azhou" / "super-caveman" / "sessions" / f"{after['session_id']}.json"
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    for key, want in after.items():
                        if key != "session_id" and state.get(key) != want:
                            errors.append(f"lifecycle case {cid}: session {key}={state.get(key)} want {want}")
                after_settings = case_spec.get("settings_after")
                if after_settings == {"hooks": "gone"}:
                    if settings_owned(project, "SessionStart") or settings_owned(project, "UserPromptSubmit"):
                        errors.append(f"lifecycle case {cid}: owned entries survive uninstall")
            except Exception as exc:
                errors.append(f"lifecycle case {cid}: {exc}")

    for spec_case in spec["cases"]:
        run_case(spec_case)
    return errors

if __name__ == "__main__":
    raise SystemExit(main())

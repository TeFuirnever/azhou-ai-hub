#!/usr/bin/env python3
"""Import a verified Codex pet candidate into another project without installing it."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("manage_codex_pet", HERE / "manage-codex-pet.py")
PET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PET)

IMPORT_RECEIPT = "candidate-import-receipt.json"
PRIVATE_INPUTS = PET.INPUTS[:2]
FIXED_INPUTS = PET.INPUTS[2:]
PACKAGE_FILES = {"pet.json", "spritesheet.webp", "theme-snapshot.json", "package-receipt.json",
                 *PET.QA_FILES}


def require(condition, message, code="invalid"):
    PET.require(condition, message, code)


def safe_root(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        require(not current.is_symlink(), f"拒绝符号链接路径：{current}")
    require(path.is_dir(), f"项目目录不存在：{path}")
    return path.resolve(strict=True)


def reject_overlap(source, target):
    require(source != target and not source.is_relative_to(target) and not target.is_relative_to(source),
            "源项目与目标项目不能相同、包含或重叠")


def target_input_path(project, name):
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts,
            f"拒绝目标输入路径逃逸：{name}", "unknown-target")
    path = project
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), f"拒绝符号链接目标路径：{path}", "unknown-target")
    return path


def private_temp_path(target, name, plan_id):
    path = target_input_path(target, name)
    temporary = path.with_name(f".{path.name}.codex-pet-import-{plan_id}.tmp")
    require(not temporary.is_symlink(), f"拒绝符号链接导入暂存图：{temporary}", "unknown-target")
    return temporary


def private_temp_matches(target, name, expected_path):
    final = target_input_path(target, name)
    prefix = f".{final.name}.codex-pet-import-"
    matches = list(final.parent.glob(prefix + "*.tmp"))
    require(all(not item.is_symlink() and item == expected_path for item in matches),
            f"目标存在未绑定的私有图暂存：{name}", "unknown-target")
    return matches


def source_evidence(project):
    state = PET.state_dir(project)
    selection_path = PET.child(state, "selection.json")
    selection_raw = PET.read(selection_path)
    selection = PET.parse(selection_raw)
    require(isinstance(selection, dict) and set(selection) == {"package", "themeRevision", "atlasSHA256"},
            "源项目 selection.json 格式未知", "unknown-target")
    package = PET.selected_package(project)
    first_facts, first_receipt = PET.check_package(package, project, require_current=True)
    require(package.parent == PET.child(state, "packages") and
            package.name == f"{first_facts['themeRevision']}-{first_facts['atlasSHA256']}",
            "源项目选择未指向标准候选包", "unknown-target")
    require(selection == {"package": package.name, "themeRevision": first_facts["themeRevision"],
                          "atlasSHA256": first_facts["atlasSHA256"]},
            "源项目选择与候选摘要不一致", "unknown-target")

    package_blobs = {name: PET.read(PET.child(package, name)) for name in sorted(PACKAGE_FILES)}
    snapshot_path = PET.child(state, f"snapshots/{first_facts['themeRevision']}/theme-snapshot.json")
    snapshot_raw, snapshot, _ = PET.load_snapshot(project, snapshot_path)
    require(package_blobs["theme-snapshot.json"] == snapshot_raw,
            "selected 候选的 theme snapshot 与源项目冻结快照不一致", "unknown-target")

    current, inputs, config = PET.theme_facts(project)
    second_facts, second_receipt = PET.check_package(package, project, require_current=True)
    captured_receipt = PET.parse(package_blobs["package-receipt.json"])
    captured_snapshot = PET.parse(package_blobs["theme-snapshot.json"])
    captured_manifest = PET.parse(package_blobs["pet.json"])
    captured_atlas = PET.inspect_atlas(package_blobs["spritesheet.webp"], require_webp=True)
    captured_qa = {name: package_blobs[name] for name in PET.QA_FILES}
    captured_qa_hashes = PET.validate_qa(captured_qa, captured_atlas["atlasSHA256"],
                                         current["themeRevision"])
    captured_facts = {"themeRevision": current["themeRevision"], **captured_atlas,
                      "manifestSHA256": PET.sha(package_blobs["pet.json"])}
    require(first_facts == second_facts and first_receipt == second_receipt and
            captured_receipt == second_receipt and captured_facts == first_facts and
            captured_qa_hashes == captured_receipt.get("qaSHA256") and
            captured_receipt.get("atlasSHA256") == captured_atlas["atlasSHA256"] and
            captured_receipt.get("themeRevision") == current["themeRevision"] and
            captured_receipt.get("snapshotSHA256") == PET.sha(package_blobs["theme-snapshot.json"]) and
            captured_snapshot == snapshot and PET.snapshot_metadata(captured_snapshot) == current["themeRevision"] and
            captured_manifest == PET.native_manifest(config) and
            PET.package_files(package) == PACKAGE_FILES and
            selection_raw == PET.read(selection_path) and
            snapshot_raw == PET.read(snapshot_path) and
            all(inputs[name] == PET.read(PET.child(project, name)) for name in PET.INPUTS) and
            all(PET.sha(PET.read(PET.child(package, name))) == PET.sha(data)
                for name, data in package_blobs.items()),
            "源候选或主题输入在复验期间发生变化", "source-conflict")

    original_receipt = PET.parse(package_blobs["package-receipt.json"])
    files = {name: PET.sha(data) for name, data in package_blobs.items()}
    qa_hashes = {name: files[name] for name in PET.QA_FILES}
    evidence = {
        "projectRoot": str(project),
        "selection": {"path": str(selection_path), "sha256": PET.sha(selection_raw),
                      "value": selection},
        "package": {"path": str(package), "name": package.name, "filesSHA256": files},
        "sourceReceipt": {"path": str(package / "package-receipt.json"),
                           "sha256": PET.sha(package_blobs["package-receipt.json"]),
                           "value": original_receipt},
        "themeRevision": current["themeRevision"],
        "atlasSHA256": first_facts["atlasSHA256"],
        "manifestSHA256": first_facts["manifestSHA256"],
        "snapshotSHA256": PET.sha(snapshot_raw),
        "inputSHA256": {record["path"]: record["sha256"] for record in current["inputs"]},
        "qaSHA256": qa_hashes,
    }
    evidence["fingerprint"] = PET.sha(PET.canonical(evidence))
    return evidence, {**package_blobs, **inputs}


def target_input_state(target, source):
    source_inputs = source["inputSHA256"]
    fixed = []
    for name in FIXED_INPUTS:
        data = PET.read(target_input_path(target, name))
        digest = PET.sha(data)
        require(digest == source_inputs[name],
                f"目標固定主题输入与源 revision 不匹配：{name}", "target-conflict")
        fixed.append({"path": name, "sha256": digest})

    private = []
    for name in PRIVATE_INPUTS:
        path = target_input_path(target, name)
        expected = source_inputs[name]
        if path.is_symlink():
            require(False, f"拒绝符号链接目标主题图：{path}", "unknown-target")
        if not path.exists():
            state = "missing"
        else:
            require(path.is_file(), f"目标主题图不是普通文件：{path}", "unknown-target")
            digest = PET.sha(PET.read(path))
            require(digest == expected, f"目标已有不同内容，拒绝覆盖：{name}", "unknown-target")
            state = "identical"
        private.append({"path": name, "state": state, "sha256": expected})
    return fixed, private


def import_receipt_path(state):
    return PET.child(state, IMPORT_RECEIPT)


def package_name(source):
    return f"{source['themeRevision']}-{source['atlasSHA256']}"


def validate_import_receipt(raw, target, source):
    receipt = PET.parse(raw)
    expected_keys = {"schemaVersion", "owner", "projectRoot", "petId", "planId", "status", "plan"}
    require(isinstance(receipt, dict) and set(receipt) == expected_keys and
            receipt.get("schemaVersion") == 1 and receipt.get("owner") == PET.OWNER and
            receipt.get("projectRoot") == str(target) and receipt.get("petId") == PET.PET_ID,
            "导入 receipt 不属于此目标或格式未知", "unknown-target")
    plan = receipt.get("plan")
    require(isinstance(plan, dict) and set(plan) == {"schemaVersion", "source", "target"} and
            plan.get("schemaVersion") == 1 and plan.get("source") == source and
            receipt.get("planId") == PET.sha(PET.canonical(plan)) and
            isinstance(receipt.get("planId"), str) and len(receipt["planId"]) == 64 and
            all(char in "0123456789abcdef" for char in receipt["planId"]),
            "导入 receipt 与当前源/目标不匹配", "stale-plan")
    target_plan = plan["target"]
    require(isinstance(target_plan, dict) and
            set(target_plan) == {"projectRoot", "fixedInputs", "privateInputs", "packageName", "packageState"} and
            target_plan.get("projectRoot") == str(target) and
            target_plan.get("packageName") == package_name(source) and
            target_plan.get("packageState") == "absent" and
            isinstance(target_plan.get("privateInputs"), list) and
            len(target_plan["privateInputs"]) == len(PRIVATE_INPUTS),
            "导入 receipt 的目标计划格式未知", "unknown-target")
    for record, name in zip(target_plan["privateInputs"], PRIVATE_INPUTS):
        require(isinstance(record, dict) and set(record) == {"path", "state", "sha256"} and
                record.get("path") == name and record.get("state") in ("missing", "identical") and
                record.get("sha256") == source["inputSHA256"][name],
                "导入 receipt 的私有图计划无效", "unknown-target")
    require(receipt.get("status") in ("in-progress", "complete"),
            "导入 receipt 状态未知", "recovery-required")
    return receipt


def current_private_matches(target, source_blobs, receipt):
    plan = receipt["plan"]
    allow_missing = receipt["status"] == "in-progress"
    for recorded in plan["target"]["privateInputs"]:
        path = target_input_path(target, recorded["path"])
        temporary = private_temp_path(target, recorded["path"], receipt["planId"])
        staged = private_temp_matches(target, recorded["path"], temporary)
        if path.is_symlink():
            require(False, f"拒绝符号链接目标主题图：{path}", "unknown-target")
        if not path.exists():
            require(allow_missing and recorded["state"] == "missing",
                    f"导入期间已有目标主题图缺失：{recorded['path']}", "unknown-target")
        else:
            require(path.is_file() and PET.sha(PET.read(path)) == recorded["sha256"],
                    f"目标主题图与导入计划不一致：{recorded['path']}", "unknown-target")
        if staged:
            require(allow_missing and recorded["state"] == "missing" and staged[0].is_file(),
                    f"目标存在不匹配的私有图暂存：{recorded['path']}", "unknown-target")
            data = PET.read(staged[0])
            expected = source_blobs[recorded["path"]]
            require(len(data) <= len(expected) and expected.startswith(data),
                    f"私有图暂存内容与当前 plan 不符：{recorded['path']}", "unknown-target")


def verify_target_package(target, source, plan):
    state = PET.state_dir(target)
    packages = PET.child(state, "packages")
    destination = PET.child(packages, plan["target"]["packageName"])
    selection_path = PET.child(state, "selection.json")
    package_exists = destination.exists()
    selection_exists = selection_path.exists()
    if not package_exists:
        require(not selection_exists, "目标 selection 指向缺失候选", "unknown-target")
        return False
    facts, _ = PET.check_package(destination, target, require_current=True)
    require(facts["themeRevision"] == source["themeRevision"] and
            facts["atlasSHA256"] == source["atlasSHA256"] and
            facts["manifestSHA256"] == source["manifestSHA256"],
            "目标候选与 source 候选摘要不一致", "unknown-target")
    for name in ("spritesheet.webp", *PET.QA_FILES, "pet.json"):
        require(PET.sha(PET.read(PET.child(destination, name))) ==
                source["package"]["filesSHA256"][name],
                f"导入候选内容与源文件不一致：{name}", "unknown-target")
    if selection_exists:
        selection = PET.parse(PET.read(selection_path))
        require(isinstance(selection, dict) and set(selection) == {"package", "themeRevision", "atlasSHA256"}
                and selection == {"package": destination.name, "themeRevision": source["themeRevision"],
                                  "atlasSHA256": source["atlasSHA256"]},
                "目标 selection 与导入候选不一致", "unknown-target")
    return True


def verify_import_state(target, source, receipt, source_blobs):
    state = PET.state_dir(target)
    plan = receipt["plan"]
    current_private_matches(target, source_blobs, receipt)

    expected_name = plan["target"]["packageName"]
    journal_path = PET.child(state, "package-journal.json")
    stage_name = None
    if journal_path.exists():
        require(receipt["status"] == "in-progress", "完成的导入留下未知 package journal", "recovery-required")
        journal = PET.parse(PET.read(journal_path))
        PET.ownership(journal, target)
        require(journal.get("operationId") == receipt["planId"],
                "package journal 不属于当前导入 plan", "recovery-required")
        stage_name = journal.get("stage")
        require(isinstance(stage_name, str) and stage_name.startswith(".stage-") and len(stage_name) == 39,
                "package journal 暂存路径无效", "recovery-required")

    allowed_files = {"project.lock", IMPORT_RECEIPT, "package-journal.json", "selection.json"}
    allowed_dirs = {"packages", "snapshots"}
    for item in state.iterdir():
        require(not item.is_symlink(), f"拒绝目标状态中的符号链接：{item}", "unknown-target")
        if item.is_file():
            require(item.name in allowed_files, f"目标存在未知同名状态：{item.name}", "unknown-target")
        elif item.is_dir():
            require(item.name in allowed_dirs or item.name == stage_name,
                    f"目标存在未知同名状态：{item.name}", "unknown-target")
        else:
            require(False, f"目标状态类型未知：{item}", "unknown-target")

    snapshot_verified = False
    for directory_name, only_name in (("packages", expected_name),
                                      ("snapshots", source["themeRevision"])):
        directory = PET.child(state, directory_name)
        if not directory.exists():
            continue
        require(directory.is_dir() and not directory.is_symlink(),
                f"目标状态目录无效：{directory}", "unknown-target")
        entries = list(directory.iterdir())
        require(all(not item.is_symlink() and item.name == only_name for item in entries),
                f"目标存在计划外内容：{directory}", "unknown-target")
        if directory_name == "snapshots" and entries:
            snapshot_dir = entries[0]
            expected_files = {"theme-snapshot.json", "generation-brief.md", "inputs"}
            require({item.name for item in snapshot_dir.iterdir()} == expected_files and
                    all(not item.is_symlink() for item in snapshot_dir.iterdir()),
                    "目标冻结快照目录包含未知内容", "unknown-target")
            frozen_inputs = PET.child(snapshot_dir, "inputs")
            require((PET.child(snapshot_dir, "theme-snapshot.json").is_file() and
                     PET.child(snapshot_dir, "generation-brief.md").is_file()) and
                    frozen_inputs.is_dir() and
                    {item.relative_to(frozen_inputs).as_posix() for item in frozen_inputs.rglob("*")
                     if item.is_file()} == set(PET.INPUTS) and
                    all(not item.is_symlink() for item in frozen_inputs.rglob("*")),
                    "目标冻结输入集合不完整或含未知内容", "unknown-target")
            target_snapshot = PET.child(snapshot_dir, "theme-snapshot.json")
            _, snapshot, _ = PET.load_snapshot(target, target_snapshot)
            require(snapshot["themeRevision"] == source["themeRevision"],
                    "目标冻结快照 revision 不匹配", "unknown-target")
            snapshot_verified = True

    package_dir = PET.child(PET.child(state, "packages"), expected_name)
    package_exists = verify_target_package(target, source, plan)
    selection_exists = PET.child(state, "selection.json").exists()
    require(not selection_exists or package_exists, "目标 selection 不完整", "unknown-target")
    if receipt["status"] == "complete":
        require(package_exists and selection_exists, "完成 receipt 缺少 package 或 selection", "unknown-target")
        require(snapshot_verified, "完成 receipt 缺少目标冻结快照", "unknown-target")
        require(not journal_path.exists(), "完成 receipt 仍有 package journal", "recovery-required")
        current_private_matches(target, source_blobs, receipt)
    if stage_name:
        stage = PET.child(state, stage_name)
        if stage.exists():
            require(stage.is_dir() and not stage.is_symlink(), "package journal 暂存目录无效", "recovery-required")
            PET.package_files(stage)
    return receipt


def clean_target_state(target):
    state = PET.state_dir(target)
    if state.exists():
        require(state.is_dir() and not state.is_symlink(), "目标同名状态目录无效", "unknown-target")
        allowed = {"project.lock"}
        for item in state.iterdir():
            require(not item.is_symlink() and item.is_file() and item.name in allowed,
                    f"目标已有未知同名状态，拒绝导入：{item.name}", "unknown-target")
    for name in PRIVATE_INPUTS:
        final = target_input_path(target, name)
        require(not list(final.parent.glob(f".{final.name}.codex-pet-import-*.tmp")),
                f"目标已有未绑定的私有图暂存：{name}", "unknown-target")


def build_plan(source_root, target_root):
    reject_overlap(source_root, target_root)
    source, blobs = source_evidence(source_root)
    fixed, private = target_input_state(target_root, source)
    state = PET.state_dir(target_root)
    receipt_path = import_receipt_path(state)
    if receipt_path.exists():
        require(not receipt_path.is_symlink() and receipt_path.is_file(),
                "目标导入 receipt 类型无效", "unknown-target")
        receipt = validate_import_receipt(PET.read(receipt_path), target_root, source)
        require(receipt["plan"]["target"]["fixedInputs"] == fixed,
                "目标固定主题输入已变化", "stale-plan")
        require(receipt["plan"]["target"]["projectRoot"] == str(target_root) and
                receipt["plan"]["target"]["packageName"] == package_name(source),
                "导入计划与当前目标不一致", "stale-plan")
        verify_import_state(target_root, source, receipt, blobs)
        plan = receipt["plan"]
        return plan, receipt["planId"], blobs, receipt

    clean_target_state(target_root)
    plan = {"schemaVersion": 1, "source": source,
            "target": {"projectRoot": str(target_root), "fixedInputs": fixed,
                       "privateInputs": private, "packageName": package_name(source),
                       "packageState": "absent"}}
    return plan, PET.sha(PET.canonical(plan)), blobs, None


def result_plan(plan, plan_id, receipt=None):
    return {"status": "candidate-import-plan", "planId": plan_id,
            "source": {"projectRoot": plan["source"]["projectRoot"],
                       "package": plan["source"]["package"]["path"],
                       "status": "reviewed", "themeRevision": plan["source"]["themeRevision"],
                       "atlasSHA256": plan["source"]["atlasSHA256"],
                       "sourceReceipt": plan["source"]["sourceReceipt"]},
            "target": {"projectRoot": plan["target"]["projectRoot"],
                       "packageName": plan["target"]["packageName"],
                       "privateInputs": plan["target"]["privateInputs"],
                       "status": receipt["status"] if receipt else "ready"},
            "installed": "unchanged", "runtime": PET.RUNTIME, "generation": "not-performed"}


@contextlib.contextmanager
def project_locks(source, target):
    """Lock target and reuse an existing source lock without creating source state."""
    with contextlib.ExitStack() as stack:
        for project in sorted((source, target), key=str):
            state = PET.state_dir(project, create=(project == target))
            lock_path = PET.child(state, "project.lock")
            if project == target or lock_path.exists():
                require(not lock_path.is_symlink(), f"拒绝符号链接项目锁：{lock_path}", "unknown-target")
                stack.enter_context(PET.lock(lock_path))
        yield


def safe_copy_private(target, source, blobs, plan_id, private_plan):
    planned = {item["path"]: item for item in private_plan}
    for name in PRIVATE_INPUTS:
        expected = source["inputSHA256"][name]
        recorded = planned[name]
        path = target_input_path(target, name)
        temporary = private_temp_path(target, name, plan_id)
        staged = private_temp_matches(target, name, temporary)
        if path.exists():
            require(path.is_file() and PET.sha(PET.read(path)) == expected,
                    f"目标主题图发生冲突，拒绝覆盖：{name}", "unknown-target")
            if staged:
                data = PET.read(temporary)
                require(recorded["state"] == "missing" and len(data) <= len(blobs[name]) and
                        blobs[name].startswith(data),
                        f"私有图暂存与本次 plan 不符：{name}", "unknown-target")
                temporary.unlink()
                PET.fsync_dir(temporary.parent)
            continue
        require(recorded["state"] == "missing",
                f"计划中的既有私有图意外缺失：{name}", "stale-plan")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(not path.parent.is_symlink(), f"拒绝符号链接目录：{path.parent}", "unknown-target")
        if temporary.exists():
            data = PET.read(temporary)
            require(len(data) <= len(blobs[name]) and blobs[name].startswith(data),
                    f"私有图暂存与本次 plan 不符：{name}", "unknown-target")
            if data != blobs[name]:
                temporary.unlink()
                PET.fsync_dir(temporary.parent)
        if not temporary.exists():
            PET.write_new(temporary, blobs[name])
        require(PET.sha(PET.read(temporary)) == expected,
                f"私有图暂存字节与 source 不一致：{name}", "unknown-target")
        try:
            os.link(temporary, path, follow_symlinks=False)
            PET.fsync_dir(path.parent)
        except FileExistsError:
            require(path.is_file() and not path.is_symlink() and PET.sha(PET.read(path)) == expected,
                    f"目标主题图写入时发生冲突：{name}", "unknown-target")
        temporary.unlink()
        PET.fsync_dir(temporary.parent)


def make_run(blobs):
    temporary = tempfile.TemporaryDirectory(prefix="codex-pet-import-")
    root = Path(temporary.name)
    (root / "final").mkdir()
    (root / "qa").mkdir()
    PET.write_new(root / "final/spritesheet-extended.webp", blobs["spritesheet.webp"])
    for name in PET.QA_FILES:
        PET.write_new(PET.child(root, name), blobs[name])
    return temporary, root


def output_apply(plan, plan_id, already=False):
    return {"status": "already-imported" if already else "imported", "planId": plan_id,
            "source": {"projectRoot": plan["source"]["projectRoot"],
                       "package": plan["source"]["package"]["path"],
                       "status": "reviewed", "themeRevision": plan["source"]["themeRevision"],
                       "atlasSHA256": plan["source"]["atlasSHA256"],
                       "sourceReceipt": plan["source"]["sourceReceipt"]},
            "package": {"path": str(Path(plan["target"]["projectRoot"]) / ".local/pets" /
                                      PET.PET_ID / "packages" / plan["target"]["packageName"]),
                        "status": "verified"},
            "installed": "unchanged", "runtime": PET.RUNTIME, "generation": "not-performed"}


def apply_import(source_root, target_root, expected_plan_id):
    try:
        plan, plan_id, _, receipt = build_plan(source_root, target_root)
    except PET.PetError as exc:
        if exc.code in ("unknown-target", "recovery-required", "busy"):
            raise
        raise PET.PetError("stale-plan", f"当前 source/target 已不再满足计划：{exc}") from exc
    require(plan_id == expected_plan_id, "planId 已过期；请重新生成只读 plan", "stale-plan")
    if receipt and receipt["status"] == "complete":
        return output_apply(plan, plan_id, already=True)

    with project_locks(source_root, target_root):
        try:
            current_plan, current_id, blobs, current_receipt = build_plan(source_root, target_root)
        except PET.PetError as exc:
            if exc.code in ("unknown-target", "recovery-required", "busy"):
                raise
            raise PET.PetError("stale-plan", f"加锁复核时 source/target 已变化：{exc}") from exc
        require(current_id == expected_plan_id,
                "加锁复核时 source/target 已变化；请重新生成只读 plan", "stale-plan")
        if current_receipt and current_receipt["status"] == "complete":
            return output_apply(current_plan, current_id, already=True)

        state = PET.state_dir(target_root, create=True)
        if current_receipt is None:
            current_receipt = {"schemaVersion": 1, "owner": PET.OWNER,
                               "projectRoot": str(target_root), "petId": PET.PET_ID,
                               "planId": current_id, "status": "in-progress", "plan": current_plan}
            PET.write_new(import_receipt_path(state), PET.json_bytes(current_receipt))

        # Recover only the manager's package stage named by its owner-bound journal.
        PET.recover_package_stage(state, target_root, operation_id=expected_plan_id)
        plan_after_recovery, id_after_recovery, blobs, current_receipt = build_plan(source_root, target_root)
        require(id_after_recovery == expected_plan_id,
                "恢复期间 source/target 已变化；请重新生成只读 plan", "stale-plan")

        try:
            source, blobs = source_evidence(source_root)
            require(source == plan_after_recovery["source"],
                    "source 在批准 plan 后、复制前发生变化", "stale-plan")
            fixed, _ = target_input_state(target_root, source)
            require(fixed == plan_after_recovery["target"]["fixedInputs"],
                    "导入期间目标固定输入发生变化", "stale-plan")
            safe_copy_private(target_root, source, blobs, expected_plan_id,
                              plan_after_recovery["target"]["privateInputs"])
            prepared = PET.prepare(target_root, operation_id=expected_plan_id)
            require(prepared["themeRevision"] == source["themeRevision"],
                    "目标主题 revision 与源候选不匹配", "target-conflict")

            temporary, run = make_run(blobs)
            try:
                packaged = PET.package_run(target_root, run, prepared["snapshot"],
                                           operation_id=expected_plan_id)
            finally:
                temporary.cleanup()
            require(packaged["package"]["atlasSHA256"] == source["atlasSHA256"],
                    "打包后的 atlas 与源候选不一致", "invalid")
            final_source, final_blobs = source_evidence(source_root)
            require(final_source == plan_after_recovery["source"] and final_source == source and
                    all(final_blobs[name] == blobs[name] for name in PET.QA_FILES + ("spritesheet.webp",)),
                    "导入期间 source 候选或 QA 发生变化", "source-conflict")
            final_facts, _ = PET.check_package(PET.selected_package(target_root), target_root,
                                               require_current=True)
            require(final_facts["themeRevision"] == source["themeRevision"] and
                    final_facts["atlasSHA256"] == source["atlasSHA256"] and
                    final_facts["manifestSHA256"] == source["manifestSHA256"],
                    "目标候选最终复验失败", "invalid")
            for name in PET.QA_FILES:
                require(PET.read(PET.child(PET.selected_package(target_root), name)) == blobs[name],
                        f"目标 QA 字节与 source 不一致：{name}", "invalid")

            complete_receipt = {**current_receipt, "status": "complete"}
            verify_import_state(target_root, source, complete_receipt, blobs)
            PET.atomic_json(import_receipt_path(state), complete_receipt)
            return output_apply(current_plan, current_id)
        except PET.PetError:
            raise
        except Exception as exc:
            raise PET.PetError("import-incomplete",
                               f"导入未完成；目标保留在可验证状态，可使用相同 planId 重试：{exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-project", required=True, help="已有 selected 候选的源项目")
    parser.add_argument("--project-root", default=str(PACKAGE_ROOT), help="导入目标项目，默认本工具所属包根目录")
    parser.add_argument("--apply", action="store_true", help="应用计划并创建 NEW 归属候选；不安装")
    parser.add_argument("--plan-id", help="只读 plan 返回的精确 planId")
    args = parser.parse_args(argv)
    try:
        require(args.apply == bool(args.plan_id), "--apply 必须与 --plan-id 一起提供")
        source = safe_root(args.from_project)
        target = safe_root(args.project_root)
        reject_overlap(source, target)
        if args.apply:
            result = apply_import(source, target, args.plan_id)
        else:
            plan, plan_id, _, receipt = build_plan(source, target)
            result = result_plan(plan, plan_id, receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PET.PetError, OSError, ValueError, KeyError, TypeError) as exc:
        code = getattr(exc, "code", "invalid")
        print(json.dumps({"status": code, "error": str(exc), "runtime": PET.RUNTIME,
                          "installed": "unchanged", "generation": "not-performed"},
                         ensure_ascii=False, indent=2))
        return {"busy": 4, "recovery-required": 5, "stale-plan": 3}.get(code, 2)


if __name__ == "__main__":
    raise SystemExit(main())

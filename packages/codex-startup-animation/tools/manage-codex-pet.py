#!/usr/bin/env python3
"""Freeze, verify, package and install the project's reviewed native Codex v2 pet.

Image generation and visual review are deliberately external (ImageGen/hatch-pet).
Requires Python 3.10+, Pillow with WebP support, and a POSIX filesystem.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from PIL import Image, ImageChops

PET_ID = "azhou-agent-lab"
DISPLAY_NAME = "阿舟 · Agent 实验室"
OWNER = "codex-startup-animation/native-pet-v1"
INPUTS = ("assets/private/working.png", "assets/private/wallpaper-scene-q-v3.png",
          "style.css", "pet/theme.json")
FRAME_COUNTS = (6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8)
RESERVED_NEUTRAL = (0, 6)  # hatch-pet auxiliary cell, not an extra animation frame.
QA_FILES = ("final/validation-extended.json", "qa/chroma-despill-extended.json",
            "qa/review.json", "qa/direction-semantics.json",
            "qa/direction-blind-validation.json", "qa/visual-qa.json")
RUNTIME = "pending-refresh-selection"
MAX_FILE_BYTES = 64 * 1024 * 1024


class PetError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition, message, code="invalid"):
    if not condition:
        raise PetError(code, message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"


def root_path(path):
    path = Path(path).expanduser().absolute()
    require(not path.is_symlink(), f"拒绝符号链接目录：{path}")
    return path.resolve()


def child(root, relative):
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts,
            f"拒绝路径逃逸：{relative}")
    path = root
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), f"拒绝符号链接：{path}")
    return path


def read(path):
    require(path.is_file() and not path.is_symlink(), f"缺少普通文件：{path}")
    require(path.stat().st_size <= MAX_FILE_BYTES, f"文件超过 64 MiB：{path}")
    return path.read_bytes()


def parse(data):
    try:
        return json.loads(data, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as exc:
        raise PetError("invalid", f"JSON 无效：{exc}") from exc


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_tree(path):
    directories = [p for p in path.rglob("*") if p.is_dir()]
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        require(not directory.is_symlink(), f"拒绝符号链接：{directory}")
        fsync_dir(directory)
    fsync_dir(path)


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path, value):
    require(not path.is_symlink(), f"拒绝符号链接：{path}")
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        write_new(temp, json_bytes(value))
        os.replace(temp, path)
        fsync_dir(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


@contextlib.contextmanager
def lock(path):
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PetError("busy", f"另一个操作持有锁：{path}") from exc
        yield
    finally:
        os.close(fd)


def state_dir(project, create=False):
    path = child(project, f".local/pets/{PET_ID}")
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def revision(records):
    return sha(canonical({"schemaVersion": 1, "inputs": records}))


def theme_facts(project):
    blobs = {name: read(child(project, name)) for name in INPUTS}
    config = parse(blobs["pet/theme.json"])
    require(config.get("id") == PET_ID and config.get("spriteVersionNumber") == 2,
            "theme.json 的 pet 身份或版本无效")
    require(config.get("displayName") == DISPLAY_NAME and config.get("themeInputs") == list(INPUTS),
            "theme.json 必须保留固定名称与四项主题输入")
    require(isinstance(config.get("description"), str) and bool(config["description"].strip()),
            "theme.json 缺少 description")
    records = [{"path": name, "sha256": sha(blobs[name])} for name in INPUTS]
    # Detect changes while freezing multiple inputs; no source file is written.
    require(all(sha(read(child(project, r["path"]))) == r["sha256"] for r in records),
            "读取期间主题输入发生变化，请重试", "source-conflict")
    return {"schemaVersion": 1, "petId": PET_ID, "themeRevision": revision(records),
            "inputs": records}, blobs, config


def snapshot_metadata(snapshot):
    require(isinstance(snapshot, dict) and snapshot.get("petId") == PET_ID,
            "snapshot petId 不匹配")
    records = snapshot.get("inputs", [])
    require([r.get("path") for r in records] == list(INPUTS), "snapshot 输入集合不匹配")
    require(snapshot.get("themeRevision") == revision(records), "snapshot 修订摘要不匹配")
    return snapshot["themeRevision"]


def load_snapshot(project, path):
    path = Path(path).expanduser().absolute()
    require(not path.is_symlink(), f"拒绝符号链接 snapshot：{path}")
    data = read(path)
    snapshot = parse(data)
    rev = snapshot_metadata(snapshot)
    for record in snapshot["inputs"]:
        frozen = child(path.parent, "inputs/" + record["path"])
        require(sha(read(frozen)) == record["sha256"], f"冻结输入已改变：{record['path']}")
    current, _, config = theme_facts(project)
    require(current["themeRevision"] == rev,
            "主题已变化；运行 prepare 后以新快照执行 ImageGen/hatch-pet，再重新审阅", "generation-required")
    return data, snapshot, config


def prepare(project, operation_id=None):
    state = state_dir(project, True)
    recover_package_stage(state, project, operation_id)
    snapshot, blobs, _ = theme_facts(project)
    directory = child(state, "snapshots/" + snapshot["themeRevision"])
    snapshot_path = directory / "theme-snapshot.json"
    if directory.exists():
        load_snapshot(project, snapshot_path)
    else:
        directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        stage = child(state, ".stage-" + uuid.uuid4().hex)
        journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID, "stage": stage.name}
        if operation_id is not None:
            journal["operationId"] = operation_id
        atomic_json(state / "package-journal.json", journal)
        try:
            stage.mkdir(mode=0o700)
            for name, data in blobs.items():
                write_new(child(stage, "inputs/" + name), data)
            brief = (f"# 阿舟原生 Codex pet 生成任务\n\n主题修订：`{snapshot['themeRevision']}`\n\n"
                     "使用本目录 inputs/ 下的冻结素材进行 ImageGen + 原生 hatch-pet v2 生成。"
                     "不得重新读取已变化的项目素材，不得把已有图集复制为新生成结果。\n\n"
                     "保持女性 Q 版阿舟的大头、小身体、短四肢和暖橙/奶白/棕主题；"
                     "正式 Q 版主形象仅作已授权来源参考，不修改原 IP 库。\n\n"
                     "交付 1536×2288、8×11、每格 192×208 的透明 WebP 图集，"
                     "前九行使用帧数 6/8/8/4/5/8/6/6/6，后两行包含顺时针 16 个 look 方向。"
                     "工具链保留格 row0/col6 使用经原生流程处理的 neutral 参考；其余 14 个未用格完全透明。"
                     "保留格不计入动画帧数；逐项完成 hatch-pet 的解码、去色溢、动画与方向 QA。\n\n"
                     "最终 visual-qa.json 必须记录本 themeRevision、实际图集 atlasSHA256 和明确 pass。"
                     "准备快照不等于已经生成，也不等于视觉通过。\n")
            write_new(stage / "generation-brief.md", brief.encode("utf-8"))
            write_new(stage / "theme-snapshot.json", json_bytes(snapshot))
            fsync_tree(stage)
            os.rename(stage, directory)
            fsync_dir(directory.parent)
        finally:
            recover_package_stage(state, project, operation_id)
    return {"status": "generation-required", "themeRevision": snapshot["themeRevision"],
            "snapshot": str(snapshot_path), "brief": str(directory / "generation-brief.md"),
            "next": "通过 ImageGen/hatch-pet 生成并审阅，然后 package --run RUN --snapshot SNAPSHOT"}


def inspect_atlas(data, require_webp=False):
    require(len(data) <= MAX_FILE_BYTES, "图集超过 64 MiB")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            require(opened.format in ({"WEBP"} if require_webp else {"PNG", "WEBP"}), "图集格式无效")
            require(opened.size == (1536, 2288), "v2 图集必须为 1536×2288")
            require(getattr(opened, "n_frames", 1) == 1, "需要静态图集，不接受动画文件")
            require("A" in opened.getbands() or "transparency" in opened.info, "图集缺少透明通道")
            opened.load()  # Full decode, never just header or manifest validation.
            image = opened.convert("RGBA")
    except PetError:
        raise
    except Exception as exc:
        raise PetError("invalid", f"图集完整解码失败：{exc}") from exc
    alpha = image.getchannel("A")
    require(alpha.getextrema()[0] == 0 and alpha.getextrema()[1] > 0, "图集须包含透明背景及可见角色")
    for row, count in enumerate(FRAME_COUNTS):
        for col in range(8):
            box = (col * 192, row * 208, (col + 1) * 192, (row + 1) * 208)
            cell = alpha.crop(box)
            nonempty = cell.getbbox() is not None
            occupied = col < count or (row, col) == RESERVED_NEUTRAL
            require(nonempty == occupied, f"单元格 row={row}, col={col} 的使用/透明状态错误")
            if occupied:
                require(cell.getextrema()[0] == 0, f"已用单元格必须同时含透明背景：row={row}, col={col}")
    # Native load_neutral_cell also permits an external reference processed by
    # remove_chroma_background + fit_to_cell. Equality is informational only.
    neutral_matches_idle = (image.crop((0, 0, 192, 208)).tobytes() ==
                            image.crop((1152, 0, 1344, 208)).tobytes())
    transparent = alpha.point(lambda value: 255 if value == 0 else 0)
    require(ImageChops.multiply(image.convert("RGB"), transparent.convert("RGB")).getbbox() is None,
            "完全透明像素含非零 RGB 残留")
    return {"atlasSHA256": sha(data), "pixelSHA256": sha(image.tobytes()), "width": 1536,
            "height": 2288, "usedCells": 74, "occupiedCells": 74, "renderedCells": 73,
            "animationCells": 57, "lookDirectionCells": 16, "neutralCells": 1,
            "unusedCells": 14, "neutralMatchesIdle00": neutral_matches_idle, "fullDecode": True}


def passed(value):
    if (any(value.get(key) in ("fail", "failed") for key in ("verdict", "status", "result")) or
            any(value.get(key) is False for key in ("ok", "pass"))):
        return False
    return (value.get("ok") is True or value.get("pass") is True or
            value.get("status") in ("pass", "passed", "ok") or value.get("result") == "pass"
            or value.get("verdict") == "pass")


def validate_qa(raw, atlas_hash, theme_rev):
    reports = {name: parse(raw[name]) for name in QA_FILES}
    for name, report in reports.items():
        require(isinstance(report, dict), f"QA 必须是 JSON 对象：{name}")
        require(not report.get("errors") and not report.get("failures"), f"QA 有失败项：{name}")
    for name in (QA_FILES[0], QA_FILES[1], QA_FILES[4]):
        require(passed(reports[name]), f"QA 未明确通过：{name}")
    require(reports[QA_FILES[2]].get("errors") == [], "review.json 必须明确 errors=[]")
    semantics = reports[QA_FILES[3]]
    entries = next((semantics[k] for k in ("directions", "results", "checks") if k in semantics), None)
    if isinstance(entries, dict):
        entries = [dict(value, direction=key) if isinstance(value, dict) else {"direction": key, "pass": value}
                   for key, value in entries.items()]
    require(isinstance(entries, list) and len(entries) == 16, "方向语义必须覆盖 16 项")
    require(all(isinstance(item, dict) for item in entries), "方向语义每项必须是对象")
    labels = [str(item.get("direction", item.get("angle", item.get("id", "")))) for item in entries]
    try:
        angles = [float(label.removesuffix("°")) for label in labels]
    except ValueError as exc:
        raise PetError("invalid", "方向必须以 000/022.5/.../337.5 度数标识") from exc
    require(set(angles) == {n * 22.5 for n in range(16)}, "方向记录缺失、重复或不符合 16 向契约")
    visual = reports[QA_FILES[5]]
    require(passed(visual) and visual.get("atlasSHA256") == atlas_hash and visual.get("themeRevision") == theme_rev,
            "视觉审阅未通过，或 atlasSHA256/themeRevision 与实际候选不匹配")
    resolution = visual.get("blindResolution", {})
    warning_approved = (visual.get("labeledLoopReviewed") is True and
                        isinstance(resolution, dict) and resolution.get("decision") == "accept"
                        and resolution.get("severity") == "minor")
    for angle, item in zip(angles, entries):
        warning = item.get("verdict", item.get("status", item.get("result"))) == "warning"
        require(not item.get("errors") and (passed(item) if not warning else
                angle not in (0, 90, 180, 270) and warning_approved and item.get("severity", "minor") == "minor"),
                f"方向 {angle:g} 未通过；intermediate warning 需要 labeled-loop 与 minor accept 审阅证据")
    if reports[QA_FILES[4]].get("reviewRequired") or reports[QA_FILES[4]].get("warnings"):
        require(warning_approved, "盲测 warning 尚无 labeled-loop 与 minor accept 审阅证据")
    require(not reports[QA_FILES[4]].get("unconfirmed"), "盲测仍存在未确认方向")
    return {name: sha(data) for name, data in raw.items()}


def native_manifest(config):
    return {"id": PET_ID, "displayName": DISPLAY_NAME, "description": config["description"],
            "spriteVersionNumber": 2, "spritesheetPath": "spritesheet.webp"}


def validate_run(project, run, snapshot_path):
    snapshot_raw, snapshot, config = load_snapshot(project, snapshot_path)
    run = root_path(run)
    atlas = read(child(run, "final/spritesheet-extended.webp"))
    facts = inspect_atlas(atlas, require_webp=True)
    qa_raw = {name: read(child(run, name)) for name in QA_FILES}
    qa_hashes = validate_qa(qa_raw, facts["atlasSHA256"], snapshot["themeRevision"])
    return {"snapshotRaw": snapshot_raw, "snapshot": snapshot, "config": config,
            "atlas": atlas, "facts": facts, "qaRaw": qa_raw, "qaHashes": qa_hashes}


def ownership(receipt, project):
    require(isinstance(receipt, dict) and receipt.get("owner") == OWNER and receipt.get("projectRoot") == str(project)
            and receipt.get("petId") == PET_ID, "发现非本项目管理的同名内容，拒绝覆盖", "unknown-target")


def package_files(directory):
    names = set()
    for path in directory.rglob("*"):
        require(not path.is_symlink(), f"拒绝包内符号链接：{path}")
        if path.is_file():
            names.add(path.relative_to(directory).as_posix())
    return names


def check_package(directory, project, require_current=True):
    require(directory.is_dir() and not directory.is_symlink(), "缺少候选包")
    expected = {"pet.json", "spritesheet.webp", "theme-snapshot.json", "package-receipt.json", *QA_FILES}
    require(package_files(directory) == expected, "候选包包含缺失或未知文件")
    receipt = parse(read(directory / "package-receipt.json"))
    ownership(receipt, project)
    snapshot_raw = read(directory / "theme-snapshot.json")
    snapshot = parse(snapshot_raw)
    rev = snapshot_metadata(snapshot)
    if require_current:
        current, _, config = theme_facts(project)
        require(rev == current["themeRevision"], "主题已变化，需要重新 prepare/生成/审阅", "generation-required")
    atlas = read(directory / "spritesheet.webp")
    facts = inspect_atlas(atlas, require_webp=True)
    qa = {name: read(child(directory, name)) for name in QA_FILES}
    qa_hashes = validate_qa(qa, facts["atlasSHA256"], rev)
    manifest_raw = read(directory / "pet.json")
    manifest = parse(manifest_raw)
    require(set(manifest) == {"id", "displayName", "description", "spriteVersionNumber", "spritesheetPath"}
            and manifest.get("id") == PET_ID and manifest.get("displayName") == DISPLAY_NAME
            and manifest.get("spriteVersionNumber") == 2 and manifest.get("spritesheetPath") == "spritesheet.webp",
            "pet.json 不符合原生 v2 契约")
    if require_current:
        require(manifest == native_manifest(config), "pet.json 与冻结主题不一致")
    require(receipt.get("atlasSHA256") == facts["atlasSHA256"] and receipt.get("themeRevision") == rev
            and receipt.get("qaSHA256") == qa_hashes and receipt.get("snapshotSHA256") == sha(snapshot_raw)
            and receipt.get("manifestSHA256") == sha(manifest_raw), "包内实际字节与 receipt 不一致")
    return {"themeRevision": rev, **facts, "manifestSHA256": sha(manifest_raw)}, receipt


def selected_package(project):
    state = state_dir(project)
    selection = parse(read(child(state, "selection.json")))
    name = selection.get("package", "")
    require(isinstance(name, str) and len(name) == 129 and name[64] == "-"
            and all(c in "0123456789abcdef-" for c in name), "候选选择路径无效")
    return child(state, "packages/" + name)


def remove_tree(path):
    require(path.is_dir() and not path.is_symlink(), f"拒绝删除非普通目录：{path}", "recovery-required")
    package_files(path)  # Refuse symlinks before deleting a transaction-owned tree.
    shutil.rmtree(path)


def recover_package_stage(state, project, operation_id=None):
    journal = child(state, "package-journal.json")
    if not journal.exists():
        return
    data = parse(read(journal))
    ownership(data, project)
    recorded_operation = data.get("operationId")
    require(recorded_operation == operation_id,
            "暂存日志属于其他操作，拒绝自动恢复", "recovery-required")
    name = data.get("stage", "")
    require(isinstance(name, str) and name.startswith(".stage-") and len(name) == 39,
            "暂存日志路径无效", "recovery-required")
    stage = child(state, name)
    if stage.exists():
        remove_tree(stage)
    journal.unlink()
    fsync_dir(state)


def package_run(project, run, snapshot_path, operation_id=None):
    state = state_dir(project, True)
    recover_package_stage(state, project, operation_id)
    candidate = validate_run(project, run, snapshot_path)
    facts = candidate["facts"]
    rev = candidate["snapshot"]["themeRevision"]
    packages = child(state, "packages")
    packages.mkdir(exist_ok=True, mode=0o700)
    name = rev + "-" + facts["atlasSHA256"]
    destination = child(packages, name)
    previous = selected_package(project) if child(state, "selection.json").exists() else None
    if not destination.exists():
        stage = child(state, ".stage-" + uuid.uuid4().hex)
        journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID, "stage": stage.name}
        if operation_id is not None:
            journal["operationId"] = operation_id
        atomic_json(state / "package-journal.json", journal)
        try:
            stage.mkdir(mode=0o700)
            manifest_raw = json_bytes(native_manifest(candidate["config"]))
            write_new(stage / "pet.json", manifest_raw)
            write_new(stage / "spritesheet.webp", candidate["atlas"])
            write_new(stage / "theme-snapshot.json", candidate["snapshotRaw"])
            for path, data in candidate["qaRaw"].items():
                write_new(child(stage, path), data)
            receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "themeRevision": rev, "atlasSHA256": facts["atlasSHA256"],
                       "manifestSHA256": sha(manifest_raw), "snapshotSHA256": sha(candidate["snapshotRaw"]),
                       "qaSHA256": candidate["qaHashes"]}
            write_new(stage / "package-receipt.json", json_bytes(receipt))
            check_package(stage, project)
            fsync_tree(stage)
            os.rename(stage, destination)
            fsync_dir(packages)
        finally:
            recover_package_stage(state, project, operation_id)
    check_package(destination, project)
    atomic_json(state / "selection.json", {"package": name, "themeRevision": rev,
                                           "atlasSHA256": facts["atlasSHA256"]})
    # At most selected + previous reviewed package. Never remove unknown content.
    for old in packages.iterdir():
        if old not in (destination, previous):
            check_package(old, project, require_current=False)
            remove_tree(old)
    return {"status": "packaged", "source": {"themeRevision": rev, "status": "reviewed"},
            "package": {"path": str(destination), **facts}, "installed": "unchanged", "runtime": RUNTIME}


def installed_facts(target, project):
    require(target.is_dir() and not target.is_symlink(), "目标不是普通目录", "unknown-target")
    require(package_files(target) == {"pet.json", "spritesheet.webp", ".azhou-pet-receipt.json"},
            "同名 pet 含未知或缺失文件，拒绝覆盖", "unknown-target")
    receipt = parse(read(target / ".azhou-pet-receipt.json"))
    ownership(receipt, project)
    manifest = read(target / "pet.json")
    metadata = parse(manifest)
    require(metadata.get("id") == PET_ID and metadata.get("spriteVersionNumber") == 2
            and metadata.get("spritesheetPath") == "spritesheet.webp", "已安装 manifest 无效", "unknown-target")
    facts = inspect_atlas(read(target / "spritesheet.webp"), require_webp=True)
    require(receipt.get("atlasSHA256") == facts["atlasSHA256"] and receipt.get("manifestSHA256") == sha(manifest),
            "已安装内容有 receipt 之外的修改，拒绝覆盖", "unknown-target")
    return {"path": str(target), "themeRevision": receipt["themeRevision"], "manifestSHA256": sha(manifest), **facts}


def journal_path(pets):
    return child(pets, f".{PET_ID}.transaction.json")


def recover_install(pets, project):
    path = journal_path(pets)
    if not path.exists():
        return None
    data = parse(read(path))
    ownership(data, project)
    require(data.get("stagingLocation") == "codex-home", "旧版或未知暂存布局需人工核对，不能推测恢复路径",
            "recovery-required")
    tx = data.get("transaction", "")
    require(isinstance(tx, str) and len(tx) == 32 and all(c in "0123456789abcdef" for c in tx),
            "安装恢复日志 transaction 无效", "recovery-required")
    target = child(pets, PET_ID)
    # The native loader scans every directory under pets, including hidden ones.
    # Keep transaction copies outside that scan, on the same filesystem.
    stage = child(pets.parent, f".{PET_ID}.stage-{tx}")
    backup = child(pets.parent, f".{PET_ID}.previous-{tx}")
    if data.get("phase") == "committed":
        actual = installed_facts(target, project)
        require(actual["atlasSHA256"] == data["candidateAtlasSHA256"] and
                actual["themeRevision"] == data["candidateThemeRevision"], "已提交目标发生变化", "recovery-required")
        if backup.exists():
            installed_facts(backup, project)
            remove_tree(backup)
        outcome = "completed-committed-install"
    elif backup.exists():
        old = installed_facts(backup, project)
        require(old["atlasSHA256"] == data.get("previousAtlasSHA256"), "旧包摘要不符", "recovery-required")
        if target.exists():
            actual = installed_facts(target, project)
            require(actual["atlasSHA256"] == data["candidateAtlasSHA256"] and
                    actual["themeRevision"] == data["candidateThemeRevision"], "目标不是本事务候选", "recovery-required")
            remove_tree(target)
        os.rename(backup, target)
        outcome = "restored-previous-installed-package"
    else:
        if target.exists():
            actual = installed_facts(target, project)
            if data.get("hadPrevious"):
                require(actual["atlasSHA256"] == data.get("previousAtlasSHA256"),
                        "旧包不在暂存且正式目标已改变", "recovery-required")
            else:
                require(actual["atlasSHA256"] == data["candidateAtlasSHA256"] and
                        actual["themeRevision"] == data["candidateThemeRevision"], "目标不是本事务候选", "recovery-required")
                remove_tree(target)
        elif data.get("hadPrevious"):
            raise PetError("recovery-required", "正式目标与旧包均缺失，不能声称已恢复")
        outcome = "restored-pre-install-state"
    if stage.exists():
        remove_tree(stage)
    fsync_dir(pets.parent)
    path.unlink()
    fsync_dir(pets)
    return outcome


def install_package(project, codex_home):
    directory = selected_package(project)
    facts, _ = check_package(directory, project)
    codex_home = root_path(codex_home)
    pets = child(codex_home, "pets")
    pets.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(pets.stat().st_dev == codex_home.stat().st_dev,
            "pets 与 CODEX_HOME 必须位于同一文件系统，才能安全交换安装目录")
    with lock(child(pets, f".{PET_ID}.lock")):
        recovery = recover_install(pets, project)
        target = child(pets, PET_ID)
        previous = installed_facts(target, project) if target.exists() else None
        if previous and all(previous[k] == facts[k] for k in ("atlasSHA256", "themeRevision")):
            return {"status": "already-installed", "source": facts["themeRevision"],
                    "package": str(directory), "installed": previous, "runtime": RUNTIME, "recovery": recovery}
        tx = uuid.uuid4().hex
        stage = child(codex_home, f".{PET_ID}.stage-{tx}")
        backup = child(codex_home, f".{PET_ID}.previous-{tx}")
        journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID, "transaction": tx,
                   "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": bool(previous),
                   "previousAtlasSHA256": previous["atlasSHA256"] if previous else None,
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"]}
        atomic_json(journal_path(pets), journal)
        try:
            stage.mkdir(mode=0o700)
            for name in ("pet.json", "spritesheet.webp"):
                write_new(stage / name, read(directory / name))
            receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "themeRevision": facts["themeRevision"], "atlasSHA256": facts["atlasSHA256"],
                       "manifestSHA256": facts["manifestSHA256"]}
            write_new(stage / ".azhou-pet-receipt.json", json_bytes(receipt))
            installed_facts(stage, project)
            # CAS on display inputs immediately before changing the installed target.
            require(theme_facts(project)[0]["themeRevision"] == facts["themeRevision"],
                    "安装前主题发生变化", "source-conflict")
            fsync_dir(stage)
            fsync_dir(codex_home)
            if previous:
                current_target = installed_facts(target, project)
                require(all(current_target[key] == previous[key] for key in
                            ("atlasSHA256", "themeRevision", "manifestSHA256")),
                        "安装目标在检查后发生变化", "source-conflict")
                os.rename(target, backup)
                fsync_dir(pets)
                fsync_dir(codex_home)
            os.rename(stage, target)
            fsync_dir(pets)
            fsync_dir(codex_home)
            actual = installed_facts(target, project)
            require(actual["atlasSHA256"] == facts["atlasSHA256"], "安装后实际字节不一致")
            require(theme_facts(project)[0]["themeRevision"] == facts["themeRevision"],
                    "安装期间主题发生变化", "source-conflict")
            journal["phase"] = "committed"
            atomic_json(journal_path(pets), journal)
            recover_install(pets, project)  # Committed: remove the bounded previous copy.
        except Exception as exc:
            try:
                outcome = recover_install(pets, project)
            except Exception as restore_exc:
                raise PetError("recovery-required", f"安装失败：{exc}；恢复未完成：{restore_exc}") from exc
            if outcome == "completed-committed-install":
                return {"status": "installed-with-recovery", "warning": str(exc),
                        "source": facts["themeRevision"], "package": str(directory),
                        "installed": installed_facts(target, project), "runtime": RUNTIME,
                        "recovery": outcome}
            raise PetError("install-failed", f"安装失败：{exc}；恢复结果：{outcome}") from exc
    return {"status": "installed", "source": {"themeRevision": facts["themeRevision"], "status": "matched"},
            "package": {"path": str(directory), **facts}, "installed": actual, "runtime": RUNTIME,
            "next": "正常刷新/重新打开 pet 选择界面并选择阿舟；本工具不退出或修改宿主", "recovery": recovery}


def recover(project, codex_home):
    state = state_dir(project, True)
    recover_package_stage(state, project)
    pets = child(root_path(codex_home), "pets")
    outcome = None
    if pets.exists():
        with lock(child(pets, f".{PET_ID}.lock")):
            outcome = recover_install(pets, project)
    return {"status": "recovered" if outcome else "no-install-transaction", "recovery": outcome,
            "states": status(project, codex_home), "runtime": RUNTIME}


def status(project, codex_home):
    result = {"status": "status", "runtime": RUNTIME}
    try:
        current, _, _ = theme_facts(project)
        result["source"] = current
    except (PetError, OSError) as exc:
        result["source"] = {"status": "invalid", "error": str(exc)}
    try:
        directory = selected_package(project)
        facts, _ = check_package(directory, project, require_current=False)
        matching = facts["themeRevision"] == result["source"].get("themeRevision")
        result["package"] = {"status": "verified" if matching else "stale-theme", "path": str(directory), **facts}
    except (PetError, OSError) as exc:
        result["package"] = {"status": getattr(exc, "code", "unavailable"), "error": str(exc)}
    pets = child(root_path(codex_home), "pets")
    target = child(pets, PET_ID)
    if journal_path(pets).exists():
        result["transaction"] = {"status": "recovery-required", "journal": str(journal_path(pets))}
    if not target.exists():
        result["installed"] = {"status": "absent"}
    else:
        try:
            facts = installed_facts(target, project)
            matches_theme = facts["themeRevision"] == result["source"].get("themeRevision")
            chosen = result["package"]
            matches_package = (all(facts[k] == chosen[k] for k in ("atlasSHA256", "themeRevision"))
                               if "atlasSHA256" in chosen else None)
            label = ("stale-theme" if not matches_theme else "stale-package" if matches_package is False
                     else "verified" if matches_package else "verified-unselected")
            result["installed"] = {"status": label, "bytesVerified": True,
                                   "matchesCurrentTheme": matches_theme, "matchesSelectedPackage": matches_package, **facts}
        except (PetError, OSError) as exc:
            result["installed"] = {"status": getattr(exc, "code", "invalid"), "error": str(exc)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "package", "install", "status", "sync", "recover"))
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    parser.add_argument("--run", help="ImageGen/hatch-pet 实际 run 目录")
    parser.add_argument("--snapshot", help="prepare 生成的 theme-snapshot.json")
    args = parser.parse_args(argv)
    try:
        project = root_path(args.project_root)
        require(project.is_dir(), "项目目录不存在")
        require(bool(args.run) == bool(args.snapshot), "--run 与 --snapshot 必须同时提供")
        require(not args.run or args.command in ("validate", "package", "sync"),
                "--run/--snapshot 仅用于 validate、package 或 sync")
        if args.command == "status":
            result = status(project, args.codex_home)
        elif args.command == "validate":
            if args.run:
                data = validate_run(project, args.run, args.snapshot)
                result = {"status": "validated", "themeRevision": data["snapshot"]["themeRevision"], **data["facts"]}
            else:
                facts, _ = check_package(selected_package(project), project)
                result = {"status": "validated", **facts}
        else:
            state = state_dir(project, True)
            with lock(child(state, "project.lock")):
                if args.command == "prepare":
                    result = prepare(project)
                elif args.command == "recover":
                    result = recover(project, args.codex_home)
                elif args.command == "package":
                    require(args.run, "package 需要 --run 与 --snapshot")
                    result = package_run(project, args.run, args.snapshot)
                else:
                    if args.command == "sync" and args.run:
                        package_run(project, args.run, args.snapshot)
                    if args.command == "sync" and not child(state, "selection.json").exists():
                        raise PetError("generation-required", "没有已审阅候选；先 prepare，再使用 ImageGen/hatch-pet 生成与审阅")
                    result = install_package(project, args.codex_home)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PetError, OSError, ValueError, KeyError, TypeError) as exc:
        code = getattr(exc, "code", "invalid")
        output = {"status": code, "error": str(exc), "runtime": RUNTIME}
        if "project" in locals():
            try:
                output["states"] = status(project, args.codex_home)
            except Exception as state_exc:
                output["states"] = {"status": "unverified", "error": str(state_exc), "runtime": RUNTIME}
        if code == "generation-required":
            output["next"] = "prepare → ImageGen/hatch-pet 生成 → 独立视觉审阅 → package/validate → sync"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return {"generation-required": 3, "busy": 4, "recovery-required": 5}.get(code, 2)


if __name__ == "__main__":
    raise SystemExit(main())

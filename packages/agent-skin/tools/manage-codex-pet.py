#!/usr/bin/env python3
"""Freeze, verify, package and install the project's reviewed native Codex v2 pet.

Image generation and visual review are deliberately external (ImageGen/hatch-pet).
Requires Python 3.10+, Pillow with WebP support, and a POSIX filesystem.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import uuid

from PIL import Image

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
    path = Path(path)
    try:
        before = path.lstat()
    except OSError as exc:
        raise PetError("invalid", f"缺少普通文件：{path}") from exc
    require(stat.S_ISREG(before.st_mode), f"缺少普通文件：{path}")
    require(before.st_size <= MAX_FILE_BYTES, f"文件超过 64 MiB：{path}")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        raise PetError("invalid", f"无法安全读取文件：{path}") from exc
    try:
        opened = os.fstat(fd)
        require(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
                f"读取前文件身份发生变化：{path}", "source-conflict")
        require(opened.st_size <= MAX_FILE_BYTES, f"文件超过 64 MiB：{path}")
        chunks, total = [], 0
        while True:
            try:
                part = os.read(fd, min(1024 * 1024, MAX_FILE_BYTES + 1 - total))
            except InterruptedError:
                continue
            except OSError as exc:
                raise PetError("invalid", f"无法读取文件：{path}") from exc
            if not part:
                break
            total += len(part)
            require(total <= MAX_FILE_BYTES, f"文件超过 64 MiB：{path}")
            chunks.append(part)
        after = os.fstat(fd)
        try:
            current = path.lstat()
        except OSError as exc:
            raise PetError("source-conflict", f"读取期间文件已消失：{path}") from exc
        identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        require(stat.S_ISREG(current.st_mode) and identity(before) == identity(opened) == identity(after) == identity(current)
                and total == after.st_size, f"读取期间文件发生变化：{path}", "source-conflict")
        return b"".join(chunks)
    finally:
        os.close(fd)


def parse(data):
    try:
        return json.loads(data, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as exc:
        raise PetError("invalid", f"JSON 无效：{exc}") from exc


def rename_exclusive(source, destination):
    """Move one entry without replacing any existing destination."""
    try:
        if sys.platform == "darwin":
            library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            operation = library.renamex_np
            operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            operation.restype = ctypes.c_int
            result = operation(os.fsencode(source), os.fsencode(destination), 4)
        elif sys.platform.startswith("linux"):
            library = ctypes.CDLL(None, use_errno=True)
            operation = library.renameat2
            operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            operation.restype = ctypes.c_int
            result = operation(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        else:
            raise PetError("invalid", "当前系统没有可验证的排他目录发布接口")
    except AttributeError as exc:
        raise PetError("invalid", "当前系统没有可验证的排他目录发布接口") from exc
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


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
        return os.fstat(stream.fileno())


def atomic_json(path, value):
    require(not path.is_symlink(), f"拒绝符号链接：{path}")
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = json_bytes(value)
    owned = None
    published = False

    def matches_owned():
        if owned is None:
            return False
        try:
            current = temp.lstat()
            return (stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino)
                    and read(temp) == data)
        except (OSError, PetError):
            return False

    try:
        owned = write_new(temp, data)
        require(matches_owned(), f"回执暂存内容发生变化，保留待核对：{temp}", "source-conflict")
        os.replace(temp, path)
        published = True
        fsync_dir(path.parent)
    finally:
        if not published and matches_owned():
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
    require(isinstance(config, dict), "theme.json 必须是 JSON 对象")
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
    require(isinstance(records, list) and all(isinstance(record, dict) for record in records),
            "snapshot 输入记录必须是对象列表")
    require([record.get("path") for record in records] == list(INPUTS), "snapshot 输入集合不匹配")
    require(all(isinstance(record.get("sha256"), str) and len(record["sha256"]) == 64
                and all(char in "0123456789abcdef" for char in record["sha256"]) for record in records),
            "snapshot 输入摘要无效")
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
    if not directory.exists():
        directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        stage = child(state, ".stage-" + uuid.uuid4().hex)
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
        planned = {"inputs/" + name: data for name, data in blobs.items()}
        planned.update({"generation-brief.md": brief.encode("utf-8"),
                        "theme-snapshot.json": json_bytes(snapshot)})
        provisional = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "stage": stage.name, "phase": "allocating"}
        if operation_id is not None:
            provisional["operationId"] = operation_id
        atomic_json(state / "package-journal.json", provisional)
        try:
            stage.mkdir(mode=0o700)
            journal = stage_journal(project, stage, "snapshot", planned, operation_id)
            atomic_json(state / "package-journal.json", journal)
            for relative, data in planned.items():
                write_new(child(stage, relative), data)
            require_stage_identity(stage, journal)
            fsync_tree(stage)
            require_stage_identity(stage, journal)
            rename_exclusive(stage, directory)
            fsync_dir(directory.parent)
        finally:
            recover_package_stage(state, project, operation_id)
    load_snapshot(project, snapshot_path)
    brief_path = directory / "generation-brief.md"
    try:
        brief_text = read(brief_path).decode("utf-8")
    except (PetError, UnicodeError) as exc:
        raise PetError("source-conflict", f"生成任务说明不可核验，保留待核对：{brief_path}") from exc
    require(bool(brief_text.strip()) and snapshot["themeRevision"] in brief_text,
            f"生成任务说明与快照不匹配，保留待核对：{brief_path}", "source-conflict")
    return {"status": "generation-required", "themeRevision": snapshot["themeRevision"],
            "snapshot": str(snapshot_path), "brief": str(brief_path),
            "next": "通过 ImageGen/hatch-pet 生成并审阅，然后 package --run RUN --snapshot SNAPSHOT"}


def inspect_atlas(data, require_webp=False):
    require(len(data) <= MAX_FILE_BYTES, "图集超过 64 MiB")
    try:
        with Image.open(io.BytesIO(data)) as source:
            accepted_formats = ("WEBP",) if require_webp else ("PNG", "WEBP")
            require(source.format in accepted_formats, "图集格式无效")
            require(source.size == (1536, 2288), "v2 图集必须为 1536×2288")
            require(getattr(source, "n_frames", 1) == 1, "需要静态图集，不接受动画文件")
            require("A" in source.getbands() or "transparency" in source.info, "图集缺少透明通道")
            source.load()
            raster = source.convert("RGBA")
    except PetError:
        raise
    except Exception as exc:
        raise PetError("invalid", f"图集完整解码失败：{exc}") from exc

    alpha = raster.getchannel("A")
    lowest, highest = alpha.getextrema()
    require(lowest == 0 and highest > 0, "图集须包含透明背景及可见角色")

    expected = {(row, col) for row, count in enumerate(FRAME_COUNTS) for col in range(count)}
    expected.add(RESERVED_NEUTRAL)
    for row in range(11):
        for col in range(8):
            x, y = col * 192, row * 208
            low, high = alpha.crop((x, y, x + 192, y + 208)).getextrema()
            occupied = (row, col) in expected
            require((high > 0) == occupied, f"单元格 row={row}, col={col} 的使用/透明状态错误")
            if occupied:
                require(low == 0, f"已用单元格必须同时含透明背景：row={row}, col={col}")

    transparent_mask = alpha.point(lambda value: 255 if value == 0 else 0)
    transparent_rgb = Image.composite(raster.convert("RGB"), Image.new("RGB", raster.size), transparent_mask)
    require(transparent_rgb.getbbox() is None, "完全透明像素含非零 RGB 残留")
    # The neutral frame may be independently fitted; equality is informational.
    idle = raster.crop((0, 0, 192, 208)).tobytes()
    neutral = raster.crop((1152, 0, 1344, 208)).tobytes()
    return {
        "atlasSHA256": sha(data), "pixelSHA256": sha(raster.tobytes()),
        "width": 1536, "height": 2288,
        "usedCells": len(expected), "occupiedCells": len(expected),
        "renderedCells": sum(FRAME_COUNTS), "animationCells": sum(FRAME_COUNTS[:9]),
        "lookDirectionCells": sum(FRAME_COUNTS[9:]), "neutralCells": 1,
        "unusedCells": 88 - len(expected), "neutralMatchesIdle00": neutral == idle,
        "fullDecode": True,
    }


def explicitly_failed(value):
    return (any(value.get(key) in ("fail", "failed") for key in ("verdict", "status", "result")) or
            any(value.get(key) is False for key in ("ok", "pass")))


def passed(value):
    if explicitly_failed(value):
        return False
    return (value.get("ok") is True or value.get("pass") is True or
            value.get("status") in ("pass", "passed", "ok") or value.get("result") == "pass"
            or value.get("verdict") == "pass")


def validate_qa(raw, atlas_hash, theme_rev):
    documents = [parse(raw[path]) for path in QA_FILES]
    for path, document in zip(QA_FILES, documents):
        require(isinstance(document, dict), f"QA 必须是 JSON 对象：{path}")
        require(not document.get("errors") and not document.get("failures"), f"QA 有失败项：{path}")
    for index in (0, 1, 4):
        require(passed(documents[index]), f"QA 未明确通过：{QA_FILES[index]}")
    require(documents[2].get("errors") == [], "review.json 必须明确 errors=[]")

    direction_report = documents[3]
    records = next((direction_report[key] for key in ("directions", "results", "checks")
                    if key in direction_report), None)
    if isinstance(records, dict):
        records = [dict(value, direction=key) if isinstance(value, dict) else {"direction": key, "pass": value}
                   for key, value in records.items()]
    require(isinstance(records, list) and len(records) == 16, "方向语义必须覆盖 16 项")
    require(all(isinstance(record, dict) for record in records), "方向语义每项必须是对象")
    try:
        directions = [float(str(record.get("direction", record.get("angle", record.get("id", "")))).removesuffix("°"))
                      for record in records]
    except ValueError as exc:
        raise PetError("invalid", "方向必须以 000/022.5/.../337.5 度数标识") from exc

    slots = {index * 22.5: 1 << index for index in range(16)}
    covered = 0
    for direction in directions:
        covered |= slots.get(direction, 0)
    require(covered == (1 << 16) - 1, "方向记录缺失、重复或不符合 16 向契约")

    review = documents[5]
    require(passed(review) and review.get("atlasSHA256") == atlas_hash and review.get("themeRevision") == theme_rev,
            "视觉审阅未通过，或 atlasSHA256/themeRevision 与实际候选不匹配")
    decision = review.get("blindResolution", {})
    warning_approved = (review.get("labeledLoopReviewed") is True and isinstance(decision, dict)
                        and decision.get("decision") == "accept" and decision.get("severity") == "minor")
    for direction, record in zip(directions, records):
        verdict = record.get("verdict", record.get("status", record.get("result")))
        warning_allowed = (direction not in (0, 90, 180, 270) and warning_approved
                           and record.get("severity", "minor") == "minor")
        accepted = warning_allowed and not explicitly_failed(record) if verdict == "warning" else passed(record)
        require(not record.get("errors") and not record.get("failures") and accepted,
                f"方向 {direction:g} 未通过；intermediate warning 需要 labeled-loop 与 minor accept 审阅证据")
    blind = documents[4]
    if blind.get("reviewRequired") or blind.get("warnings"):
        require(warning_approved, "盲测 warning 尚无 labeled-loop 与 minor accept 审阅证据")
    require(not blind.get("unconfirmed"), "盲测仍存在未确认方向")
    return {path: sha(content) for path, content in raw.items()}


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


def package_files(directory, *, allow_empty=False):
    directory = Path(directory)
    names = set()

    def visit(folder, *, root=False):
        try:
            with os.scandir(folder) as scanned:
                entries = list(scanned)
            if not root and not allow_empty:
                require(bool(entries), f"拒绝处理未知空目录：{folder}", "recovery-required")
            for entry in entries:
                path = Path(entry.path)
                require(not entry.is_symlink(), f"拒绝包内符号链接：{path}")
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    names.add(path.relative_to(directory).as_posix())
                else:
                    raise PetError("recovery-required", f"拒绝清理含非常规文件的目录：{path}")
        except OSError as exc:
            raise PetError("recovery-required", f"无法完整扫描目录：{folder}") from exc

    visit(directory, root=True)
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
    require(isinstance(selection, dict) and set(selection) == {"package", "themeRevision", "atlasSHA256"},
            "候选选择记录格式未知，保留待核对", "source-conflict")
    name = selection["package"]
    require(isinstance(name, str) and len(name) == 129 and name[64] == "-"
            and all(c in "0123456789abcdef" for c in name[:64] + name[65:])
            and selection["themeRevision"] == name[:64] and selection["atlasSHA256"] == name[65:],
            "候选选择记录与路径不一致，保留待核对", "source-conflict")
    return child(state, "packages/" + name)


def verified_selected_package(project, *, require_current=True):
    directory = selected_package(project)
    facts, receipt = check_package(directory, project, require_current=require_current)
    require(directory.name == facts["themeRevision"] + "-" + facts["atlasSHA256"],
            "选中候选的内容与路径不一致，保留待核对", "source-conflict")
    return directory, facts, receipt


def capture_removal_plan(path, names):
    require(path.is_dir() and not path.is_symlink(), f"拒绝删除非普通目录：{path}", "recovery-required")
    identity = path.lstat()
    require(package_files(path) == names, "清理目标含未知或缺失文件，保留待核对", "recovery-required")
    files = {name: sha(read(child(path, name))) for name in names}
    plan = {"directoryIdentity": {"device": identity.st_dev, "inode": identity.st_ino}, "files": files}
    require(package_directory_matches(path, plan) and package_files(path) == names,
            "清理目标身份或内容发生变化，保留待核对", "recovery-required")
    return plan


def remove_tree(path, plan):
    files = plan["files"]
    require(package_directory_matches(path, plan) and package_files(path) == set(files),
            "清理目标身份或内容发生变化，保留待核对", "recovery-required")
    require(all(sha(read(child(path, name))) == digest for name, digest in files.items()),
            "清理目标内容发生变化，保留待核对", "recovery-required")
    remove_planned_directory(path, plan["directoryIdentity"], files, allow_missing=False)


def stage_file_names(kind):
    if kind == "snapshot":
        return {*("inputs/" + name for name in INPUTS), "generation-brief.md", "theme-snapshot.json"}
    if kind == "package":
        return {"pet.json", "spritesheet.webp", "theme-snapshot.json", "package-receipt.json", *QA_FILES}
    if kind == "install":
        return {"pet.json", "spritesheet.webp", ".azhou-pet-receipt.json"}
    raise PetError("recovery-required", "未知暂存类型，拒绝自动清理")


def stage_plan(kind, files):
    require(set(files) == stage_file_names(kind), "暂存计划文件集合无效", "recovery-required")
    return {name: sha(data) for name, data in files.items()}


def stage_journal(project, stage, kind, files, operation_id):
    stage_identity = stage.lstat()
    require(stat.S_ISDIR(stage_identity.st_mode), "暂存不是普通目录", "recovery-required")
    journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID, "stage": stage.name,
               "stageKind": kind, "stageFiles": stage_plan(kind, files),
               "stageIdentity": {"device": stage_identity.st_dev, "inode": stage_identity.st_ino}}
    if operation_id is not None:
        journal["operationId"] = operation_id
    return journal


def require_stage_identity(stage, journal):
    require(package_directory_matches(stage, {"directoryIdentity": journal.get("stageIdentity")}),
            "暂存缺少匹配的实体绑定，保留待核对", "recovery-required")


def verify_stage_for_cleanup(stage, journal, expected_kinds):
    require(stage.is_dir() and not stage.is_symlink(), "暂存不是普通目录", "recovery-required")
    require_stage_identity(stage, journal)
    kind, files = journal.get("stageKind"), journal.get("stageFiles")
    require(kind in expected_kinds, "暂存缺少已绑定类型，保留待核对", "recovery-required")
    require(isinstance(files, dict) and set(files) == stage_file_names(kind),
            "暂存计划文件集合无效", "recovery-required")
    require(all(isinstance(value, str) and len(value) == 64
                and all(c in "0123456789abcdef" for c in value) for value in files.values()),
            "暂存计划摘要无效", "recovery-required")
    verified_files = 0
    allowed_dirs = {parent.as_posix() for name in files for parent in Path(name).parents
                    if parent != Path(".")}

    def inspect(directory):
        nonlocal verified_files
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative = path.relative_to(stage).as_posix()
                    require(not entry.is_symlink(), "暂存含符号链接，拒绝清理", "recovery-required")
                    if entry.is_dir(follow_symlinks=False):
                        require(relative in allowed_dirs, "暂存含未知目录，拒绝清理", "recovery-required")
                        inspect(path)
                    else:
                        require(entry.is_file(follow_symlinks=False) and relative in files,
                                "暂存含未知文件，拒绝清理", "recovery-required")
                        try:
                            actual = sha(read(path))
                        except PetError as exc:
                            raise PetError("recovery-required", f"无法核验暂存文件：{exc}") from exc
                        require(actual == files[relative], "暂存文件内容已改变，拒绝清理", "recovery-required")
                        verified_files += 1
        except OSError as exc:
            raise PetError("recovery-required", f"无法核验暂存，拒绝清理：{exc}") from exc

    inspect(stage)
    require(verified_files > 0, "空暂存缺少归属证据，保留待核对", "recovery-required")
    require_stage_identity(stage, journal)


def remove_planned_stage(stage, journal, expected_kinds):
    verify_stage_for_cleanup(stage, journal, expected_kinds)
    remove_planned_directory(stage, journal["stageIdentity"], journal["stageFiles"], allow_missing=True)


def remove_planned_directory(directory, binding, files, *, allow_missing):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        with contextlib.ExitStack() as root_handles:
            parent_fd = os.open(directory.parent, flags)
            root_handles.callback(os.close, parent_fd)
            root_fd = os.open(directory.name, flags, dir_fd=parent_fd)
            root_handles.callback(os.close, root_fd)
            expected_identity = (binding["device"], binding["inode"])

            def check_root():
                path_info = os.stat(directory.name, dir_fd=parent_fd, follow_symlinks=False)
                opened = os.fstat(root_fd)
                require(stat.S_ISDIR(path_info.st_mode) and stat.S_ISDIR(opened.st_mode)
                        and (path_info.st_dev, path_info.st_ino) == expected_identity
                        and (opened.st_dev, opened.st_ino) == expected_identity,
                        "清理目录身份已变化，保留待核对", "recovery-required")

            def open_parent(parts, handles):
                current = root_fd
                for part in parts:
                    current = os.open(part, flags, dir_fd=current)
                    handles.callback(os.close, current)
                return current

            check_root()
            for name, expected_sha in sorted(files.items()):
                parts = Path(name).parts
                with contextlib.ExitStack() as handles:
                    try:
                        folder_fd = open_parent(parts[:-1], handles)
                        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                     dir_fd=folder_fd)
                    except FileNotFoundError:
                        if allow_missing:
                            continue
                        raise
                    handles.callback(os.close, fd)
                    before = os.fstat(fd)
                    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_FILE_BYTES,
                            "清理文件不是允许的普通文件，保留待核对", "recovery-required")
                    digest, total = hashlib.sha256(), 0
                    while True:
                        try:
                            chunk = os.read(fd, min(1024 * 1024, MAX_FILE_BYTES + 1 - total))
                        except InterruptedError:
                            continue
                        if not chunk:
                            break
                        total += len(chunk)
                        require(total <= MAX_FILE_BYTES, "清理文件过大，保留待核对", "recovery-required")
                        digest.update(chunk)
                    after = os.fstat(fd)
                    at_name = os.stat(parts[-1], dir_fd=folder_fd, follow_symlinks=False)
                    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    require(stat.S_ISREG(at_name.st_mode)
                            and identity(before) == identity(after) == identity(at_name)
                            and total == after.st_size and digest.hexdigest() == expected_sha,
                            "清理文件内容或身份已变化，保留待核对", "recovery-required")
                    check_root()
                    os.unlink(parts[-1], dir_fd=folder_fd)
            directories = {parent.as_posix() for name in files for parent in Path(name).parents
                           if parent != Path(".")}
            for name in sorted(directories, key=lambda item: (-len(Path(item).parts), item)):
                parts = Path(name).parts
                with contextlib.ExitStack() as handles:
                    try:
                        folder_fd = open_parent(parts[:-1], handles)
                        check_root()
                        os.rmdir(parts[-1], dir_fd=folder_fd)
                    except FileNotFoundError:
                        if allow_missing:
                            continue
                        raise
            check_root()
            os.rmdir(directory.name, dir_fd=parent_fd)
    except OSError as exc:
        raise PetError("recovery-required", f"目录无法安全清理，保留待核对：{exc}") from exc


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
    phase = data.get("phase")
    require(phase in (None, "allocating"), "暂存日志阶段未知，保留待核对", "recovery-required")
    if phase == "allocating":
        require("stageKind" not in data and "stageFiles" not in data,
                "预备日志包含未知绑定，保留待核对", "recovery-required")
        require(not stage.exists(), "预备阶段的目录归属未确认，保留待核对", "recovery-required")
    if stage.exists():
        verify_stage_for_cleanup(stage, data, {"snapshot", "package"})
        require_stage_identity(stage, data)
        remove_planned_stage(stage, data, {"snapshot", "package"})
    journal.unlink()
    fsync_dir(state)


def package_directory_matches(directory, receipt):
    identity = receipt.get("directoryIdentity")
    if not isinstance(identity, dict) or set(identity) != {"device", "inode"}:
        return False
    if any(type(identity[key]) is not int or identity[key] < 0 for key in identity):
        return False
    try:
        actual = directory.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(actual.st_mode) and actual.st_dev == identity["device"]
            and actual.st_ino == identity["inode"])


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
    published_new = False
    if not destination.exists():
        stage = child(state, ".stage-" + uuid.uuid4().hex)
        provisional = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "stage": stage.name, "phase": "allocating"}
        if operation_id is not None:
            provisional["operationId"] = operation_id
        atomic_json(state / "package-journal.json", provisional)
        try:
            stage.mkdir(mode=0o700)
            stage_identity = stage.lstat()
            manifest_raw = json_bytes(native_manifest(candidate["config"]))
            receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "themeRevision": rev, "atlasSHA256": facts["atlasSHA256"],
                       "manifestSHA256": sha(manifest_raw), "snapshotSHA256": sha(candidate["snapshotRaw"]),
                       "qaSHA256": candidate["qaHashes"],
                       "directoryIdentity": {"device": stage_identity.st_dev, "inode": stage_identity.st_ino}}
            planned = {"pet.json": manifest_raw, "spritesheet.webp": candidate["atlas"],
                       "theme-snapshot.json": candidate["snapshotRaw"], **candidate["qaRaw"],
                       "package-receipt.json": json_bytes(receipt)}
            journal = stage_journal(project, stage, "package", planned, operation_id)
            atomic_json(state / "package-journal.json", journal)
            for relative, data in planned.items():
                write_new(child(stage, relative), data)
            check_package(stage, project)
            require(package_directory_matches(stage, receipt), "候选暂存身份发生变化", "source-conflict")
            require_stage_identity(stage, journal)
            fsync_tree(stage)
            require_stage_identity(stage, journal)
            rename_exclusive(stage, destination)
            published_new = True
            fsync_dir(packages)
        finally:
            recover_package_stage(state, project, operation_id)
    selected_facts, selected_receipt = check_package(destination, project)
    require(selected_facts["themeRevision"] == rev and selected_facts["atlasSHA256"] == facts["atlasSHA256"],
            "候选目录内容与名称不一致，保留待核对", "source-conflict")
    require(package_directory_matches(destination, selected_receipt) or (not published_new and destination == previous),
            "候选目录缺少当前实体绑定，保留待核对", "source-conflict")
    atomic_json(state / "selection.json", {"package": name, "themeRevision": rev,
                                           "atlasSHA256": facts["atlasSHA256"]})
    preserved = []
    for old in packages.iterdir():
        if old not in (destination, previous):
            plan = capture_removal_plan(old, stage_file_names("package"))
            old_facts, old_receipt = check_package(old, project, require_current=False)
            expected_name = old_facts["themeRevision"] + "-" + old_facts["atlasSHA256"]
            if old.name != expected_name or not package_directory_matches(old, old_receipt):
                preserved.append(str(old))
                continue
            remove_tree(old, plan)
    result = {"status": "packaged", "source": {"themeRevision": rev, "status": "reviewed"},
              "package": {"path": str(destination), **facts}, "installed": "unchanged", "runtime": RUNTIME}
    if preserved:
        result["preservedUnverifiedPackages"] = sorted(preserved)
    return result



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


def same_installation(left, right):
    return all(left.get(key) == right.get(key)
               for key in ("atlasSHA256", "themeRevision", "manifestSHA256"))


def prior_project_from_journal(data, project):
    raw = data.get("previousProjectRoot")
    if raw is None:
        return project
    recorded = Path(raw) if isinstance(raw, str) else Path(".")
    require(data.get("hadPrevious") is True and isinstance(raw, str) and recorded.is_absolute()
            and os.path.normpath(raw) == raw and raw != str(project),
            "安装恢复日志中的旧项目身份无效", "recovery-required")
    require(not recorded.is_symlink() and recorded.resolve() == recorded,
            "旧项目身份路径包含符号链接或路径别名", "recovery-required")
    return recorded


def journal_path(pets):
    return child(pets, f".{PET_ID}.transaction.json")


def recover_install(pets, project):
    journal = journal_path(pets)
    if not journal.exists():
        return None
    record = parse(read(journal))
    ownership(record, project)
    require(record.get("phase") in ("prepared", "committed") and isinstance(record.get("hadPrevious"), bool),
            "安装恢复日志状态无效，保留待核对", "recovery-required")
    def valid_digest(value):
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    candidate_keys = ("candidateAtlasSHA256", "candidateThemeRevision", "candidateManifestSHA256")
    previous_keys = ("previousAtlasSHA256", "previousThemeRevision", "previousManifestSHA256")
    require(all(valid_digest(record.get(key)) for key in candidate_keys),
            "安装恢复日志缺少完整候选摘要，保留待核对", "recovery-required")
    if record["hadPrevious"]:
        require(all(valid_digest(record.get(key)) for key in previous_keys),
                "安装恢复日志缺少完整旧安装摘要，保留待核对", "recovery-required")
    else:
        require(all(record.get(key) is None for key in previous_keys),
                "首次安装日志含未知旧安装摘要，保留待核对", "recovery-required")
    previous_project = prior_project_from_journal(record, project)
    handoff = previous_project != project
    if handoff:
        require(record.get("previousAtlasSHA256") and record.get("previousThemeRevision")
                and record.get("previousManifestSHA256"), "接管恢复日志缺少旧安装摘要", "recovery-required")
    require(record.get("stagingLocation") == "codex-home", "旧版或未知暂存布局需人工核对，不能推测恢复路径",
            "recovery-required")
    transaction = record.get("transaction", "")
    require(isinstance(transaction, str) and len(transaction) == 32
            and all(char in "0123456789abcdef" for char in transaction),
            "安装恢复日志 transaction 无效", "recovery-required")
    target = child(pets, PET_ID)
    # The host scans hidden directories under pets, so keep transaction copies outside it.
    stage = child(pets.parent, f".{PET_ID}.stage-{transaction}")
    backup = child(pets.parent, f".{PET_ID}.previous-{transaction}")
    stage_present = stage.exists()
    if stage_present:
        verify_stage_for_cleanup(stage, record, {"install"})

    def check_stage_before_action():
        if stage_present:
            verify_stage_for_cleanup(stage, record, {"install"})
        else:
            require(not stage.exists() and not stage.is_symlink(), "恢复期间出现未知暂存，保留待核对", "recovery-required")

    def candidate_matches(current, message):
        expected = {"atlasSHA256": record["candidateAtlasSHA256"],
                    "themeRevision": record["candidateThemeRevision"],
                    "manifestSHA256": record["candidateManifestSHA256"]}
        require(same_installation(current, expected), message, "recovery-required")

    def verify_candidate(path, message):
        candidate_matches(installed_facts(path, project), message)

    def exact_previous(actual, message):
        expected = {"atlasSHA256": record["previousAtlasSHA256"],
                    "themeRevision": record["previousThemeRevision"],
                    "manifestSHA256": record["previousManifestSHA256"]}
        require(same_installation(actual, expected), message, "recovery-required")

    operations = []
    if record.get("phase") == "committed":
        verify_candidate(target, "已提交目标发生变化")
        if backup.exists():
            require(record["hadPrevious"], "首次安装出现未知旧副本", "recovery-required")
            plan = capture_removal_plan(backup, stage_file_names("install"))
            previous = installed_facts(backup, previous_project)
            exact_previous(previous, "旧安装副本摘要不符")
            operations.append(("remove", backup, plan))
        outcome = "completed-committed-install"
    elif backup.exists():
        require(record["hadPrevious"], "首次安装出现未知旧副本", "recovery-required")
        previous = installed_facts(backup, previous_project)
        exact_previous(previous, "旧包摘要不符")
        if target.exists():
            plan = capture_removal_plan(target, stage_file_names("install"))
            verify_candidate(target, "目标不是本事务候选")
            operations.append(("remove", target, plan))
        operations.append(("move", backup, target))
        outcome = "restored-previous-installed-package"
    else:
        if target.exists() and record.get("hadPrevious") and handoff:
            previous = installed_facts(target, previous_project)
            exact_previous(previous, "旧包不在暂存且正式目标已改变")
        elif target.exists():
            plan = capture_removal_plan(target, stage_file_names("install")) if not record.get("hadPrevious") else None
            actual = installed_facts(target, project)
            if record.get("hadPrevious"):
                exact_previous(actual, "旧包不在暂存且正式目标已改变")
            else:
                candidate_matches(actual, "目标不是本事务候选")
                operations.append(("remove", target, plan))
        elif record.get("hadPrevious"):
            raise PetError("recovery-required", "正式目标与旧包均缺失，不能声称已恢复")
        outcome = "restored-pre-install-state"

    for action, source, destination in operations:
        check_stage_before_action()
        if action == "remove":
            remove_tree(source, destination)
        else:
            rename_exclusive(source, destination)
    check_stage_before_action()
    if stage_present:
        remove_planned_stage(stage, record, {"install"})
    fsync_dir(pets.parent)
    journal.unlink()
    fsync_dir(pets)
    return outcome




def install_package(project, codex_home, *, previous_project=None, expected_previous=None):
    require(previous_project is not None or expected_previous is None,
            "接管安装必须同时提供旧项目与已验证候选摘要")
    require(expected_previous is not None or previous_project is None or not Path(previous_project).exists(),
            "旧项目仍存在时必须验证其当前候选摘要")
    directory, facts, _ = verified_selected_package(project)
    if previous_project is not None and expected_previous is not None:
        require(same_installation(facts, expected_previous),
                "Hub 当前候选与旧项目已安装候选不一致，拒绝接管", "source-conflict")
    codex_home = root_path(codex_home)
    pets = child(codex_home, "pets")
    pets.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(pets.stat().st_dev == codex_home.stat().st_dev,
            "pets 与 CODEX_HOME 必须位于同一文件系统，才能安全交换安装目录")
    with lock(child(pets, f".{PET_ID}.lock")):
        recovery = recover_install(pets, project)
        target = child(pets, PET_ID)
        previous = None
        if target.exists() and previous_project is not None:
            try:
                current = installed_facts(target, project)
            except PetError:
                current = None
            if current is not None and same_installation(current, facts):
                return {"status": "already-handed-off", "source": facts["themeRevision"],
                        "package": str(directory), "installed": current, "runtime": RUNTIME,
                        "recovery": recovery}
            require(expected_previous is not None,
                    "旧项目目录已不可用，且当前安装不能证明已归属 Hub", "unknown-target")
            previous = installed_facts(target, previous_project)
            require(same_installation(previous, expected_previous),
                    "已安装内容与旧项目当前候选不一致，拒绝接管", "unknown-target")
        elif target.exists():
            previous = installed_facts(target, project)
        else:
            require(previous_project is None,
                    "旧项目已有安装目标缺失，拒绝执行接管", "unknown-target")
        if previous_project is None and previous and all(
                previous[k] == facts[k] for k in ("atlasSHA256", "themeRevision")):
            require(same_installation(previous, facts),
                    "同图集和主题的已安装 manifest 不一致，保留待核对", "source-conflict")
            return {"status": "already-installed", "source": facts["themeRevision"],
                    "package": str(directory), "installed": previous, "runtime": RUNTIME, "recovery": recovery}
        tx = uuid.uuid4().hex
        stage = child(codex_home, f".{PET_ID}.stage-{tx}")
        backup = child(codex_home, f".{PET_ID}.previous-{tx}")
        manifest_raw = read(directory / "pet.json")
        atlas = read(directory / "spritesheet.webp")
        require(sha(manifest_raw) == facts["manifestSHA256"] and sha(atlas) == facts["atlasSHA256"],
                "安装前候选内容发生变化", "source-conflict")
        receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                   "themeRevision": facts["themeRevision"], "atlasSHA256": facts["atlasSHA256"],
                   "manifestSHA256": facts["manifestSHA256"]}
        planned = {"pet.json": manifest_raw, "spritesheet.webp": atlas,
                   ".azhou-pet-receipt.json": json_bytes(receipt)}
        planned_hashes = stage_plan("install", planned)
        journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID, "transaction": tx,
                   "stagingLocation": "codex-home", "phase": "prepared", "hadPrevious": bool(previous),
                   "previousAtlasSHA256": previous["atlasSHA256"] if previous else None,
                   "previousThemeRevision": previous["themeRevision"] if previous else None,
                   "previousManifestSHA256": previous["manifestSHA256"] if previous else None,
                   "candidateAtlasSHA256": facts["atlasSHA256"], "candidateThemeRevision": facts["themeRevision"],
                   "candidateManifestSHA256": facts["manifestSHA256"],
                   "stageKind": "install", "stageFiles": planned_hashes}
        if previous_project is not None:
            journal.update({"previousProjectRoot": str(previous_project),
                            "previousThemeRevision": previous["themeRevision"],
                            "previousManifestSHA256": previous["manifestSHA256"]})
        atomic_json(journal_path(pets), journal)
        try:
            stage.mkdir(mode=0o700)
            binding = stage_journal(project, stage, "install", planned, None)
            journal["stageIdentity"] = binding["stageIdentity"]
            atomic_json(journal_path(pets), journal)
            for relative, data in planned.items():
                write_new(child(stage, relative), data)
            installed_facts(stage, project)
            # CAS on display inputs immediately before changing the installed target.
            require(theme_facts(project)[0]["themeRevision"] == facts["themeRevision"],
                    "安装前主题发生变化", "source-conflict")
            require_stage_identity(stage, journal)
            fsync_dir(stage)
            fsync_dir(codex_home)
            require_stage_identity(stage, journal)
            if previous:
                current_target = installed_facts(target, previous_project or project)
                require(same_installation(current_target, previous),
                        "安装目标在检查后发生变化", "source-conflict")
                rename_exclusive(target, backup)
                fsync_dir(pets)
                fsync_dir(codex_home)
            require_stage_identity(stage, journal)
            rename_exclusive(stage, target)
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
    return {"status": "handed-off" if previous_project is not None else "installed",
            "source": {"themeRevision": facts["themeRevision"], "status": "matched"},
            "package": {"path": str(directory), **facts}, "installed": actual, "runtime": RUNTIME,
            "next": "正常刷新/重新打开 pet 选择界面并选择阿舟；本工具不退出或修改宿主", "recovery": recovery}


def handoff_package(project, previous_project, codex_home):
    project = root_path(project)
    raw_previous = Path(previous_project).expanduser()
    require(raw_previous.is_absolute(), "--previous-project-root 必须是绝对路径")
    require(not raw_previous.is_symlink(), f"拒绝符号链接旧项目目录：{raw_previous}", "unknown-target")
    previous_project = root_path(raw_previous)
    require(raw_previous == previous_project, "拒绝旧项目路径别名", "unknown-target")
    require(previous_project != project, "旧项目与 Hub 项目不能是同一目录")
    hub_state = state_dir(project, True)
    if previous_project.is_dir():
        old_state = state_dir(previous_project)
        require(old_state.is_dir() and not old_state.is_symlink(),
                "旧项目缺少 Pet 状态，不能证明安装来源", "unknown-target")
        # Freeze both candidate selections before taking the shared installation lock.
        # The legacy CLI owns the old lock; Hub package operations own the Hub lock.
        with lock(child(old_state, "project.lock")):
            with lock(child(hub_state, "project.lock")):
                _, old_facts, _ = verified_selected_package(previous_project)
                _, new_facts, _ = verified_selected_package(project)
                require(same_installation(old_facts, new_facts),
                        "Hub 候选与旧项目已安装候选不完全一致，拒绝把内容变更混入接管", "source-conflict")
                return install_package(project, codex_home, previous_project=previous_project,
                                       expected_previous=old_facts)
    # After a successful handoff the source checkout may already be gone. This
    # path is safe only when the target proves it is the exact current Hub package.
    with lock(child(hub_state, "project.lock")):
        return install_package(project, codex_home, previous_project=previous_project)


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
        directory, facts, _ = verified_selected_package(project, require_current=False)
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
            matches_package = same_installation(facts, chosen) if "atlasSHA256" in chosen else None
            label = ("stale-theme" if not matches_theme else "stale-package" if matches_package is False
                     else "verified" if matches_package else "verified-unselected")
            result["installed"] = {"status": label, "bytesVerified": True,
                                   "matchesCurrentTheme": matches_theme, "matchesSelectedPackage": matches_package, **facts}
        except (PetError, OSError) as exc:
            result["installed"] = {"status": getattr(exc, "code", "invalid"), "error": str(exc)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "package", "install", "status", "sync", "recover", "handoff"))
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    parser.add_argument("--previous-project-root", help="handoff 的旧项目绝对路径")
    parser.add_argument("--run", help="ImageGen/hatch-pet 实际 run 目录")
    parser.add_argument("--snapshot", help="prepare 生成的 theme-snapshot.json")
    args = parser.parse_args(argv)
    try:
        project = root_path(args.project_root)
        require(project.is_dir(), "项目目录不存在")
        require((args.command == "handoff") == bool(args.previous_project_root),
                "handoff 必须且只能提供 --previous-project-root")
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
                _, facts, _ = verified_selected_package(project)
                result = {"status": "validated", **facts}
        elif args.command == "handoff":
            result = handoff_package(project, args.previous_project_root, args.codex_home)
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

#!/usr/bin/env python3
"""Coordinate the reviewed native Codex pet: freeze, audit, publish, install.

The manager guards four durable artifacts and never talks to the host app:

* a frozen theme snapshot handed to external ImageGen/hatch-pet generation,
* a content-addressed candidate package rebuilt from a reviewed run,
* an install transaction that swaps the pet directory inside CODEX_HOME,
* recovery journals that bind automatic recovery to verifiable evidence.

Image generation and visual review stay external on purpose. Recovery needs
matching recorded identities and contents; ambiguous state stays for review.
Requires Python 3.10+, Pillow with WebP support and a POSIX fs.
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

# ---------------------------------------------------------------------------
# Contract: fixed identities and shapes this tool may never invent.
# ---------------------------------------------------------------------------

PET_ID = "azhou-agent-lab"
PET_DISPLAY_NAME = "阿舟 · Agent 实验室"
OWNER = "codex-startup-animation/native-pet-v1"
INPUTS = ("assets/azhou/working.png", "assets/azhou/wallpaper-scene-q-v3.png",
          "style.css", "pet/theme.json")
FRAME_COUNTS = (6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8)
TOOLCHAIN_NEUTRAL_CELL = (0, 6)  # hatch-pet parks its neutral reference here; never a frame.
QA_FILES = ("final/validation-extended.json", "qa/chroma-despill-extended.json",
            "qa/review.json", "qa/direction-semantics.json",
            "qa/direction-blind-validation.json", "qa/visual-qa.json")
RUNTIME = "pending-refresh-selection"
MAX_FILE_BYTES = 64 * 1024 * 1024

# v2 atlas geometry: 8 columns x 11 rows of 192x208 transparent cells.
ATLAS_COLUMNS, ATLAS_ROWS = 8, 11
CELL_WIDTH, CELL_HEIGHT = 192, 208
ATLAS_WIDTH = ATLAS_COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ATLAS_ROWS * CELL_HEIGHT
ATLAS_CELL_TOTAL = ATLAS_COLUMNS * ATLAS_ROWS
ANIMATION_ROWS = 9
DIRECTION_SLOT_COUNT = 16
DIRECTION_STEP_DEGREES = 22.5
CARDINAL_DIRECTIONS = (0, 90, 180, 270)

# Directory layouts the manager owns end to end.
PACKAGE_ENTRIES = frozenset({"pet.json", "spritesheet.webp", "theme-snapshot.json",
                             "package-receipt.json", *QA_FILES})
INSTALL_ENTRIES = frozenset({"pet.json", "spritesheet.webp", ".azhou-pet-receipt.json"})
MANIFEST_FIELDS = frozenset({"id", "displayName", "description",
                             "spriteVersionNumber", "spritesheetPath"})
SELECTION_FIELDS = frozenset({"package", "themeRevision", "atlasSHA256"})
STAGE_NAME_LENGTH = len(".stage-") + 32
INSTALL_IDENTITY_KEYS = ("atlasSHA256", "themeRevision", "manifestSHA256")
CANDIDATE_DIGEST_KEYS = ("candidateAtlasSHA256", "candidateThemeRevision",
                         "candidateManifestSHA256")
PREVIOUS_DIGEST_KEYS = ("previousAtlasSHA256", "previousThemeRevision",
                        "previousManifestSHA256")
TRANSACTION_PHASES = ("prepared", "committed")

# Recovery endpoints, ordered by how far the transaction got.
OUTCOME_COMMITTED = "completed-committed-install"
OUTCOME_RESTORED_PREVIOUS = "restored-previous-installed-package"
OUTCOME_RESTORED_EMPTY = "restored-pre-install-state"

GENERATION_NEXT_STEP = ("快照已冻结；请先用 ImageGen 与 hatch-pet 完成生成和视觉审阅，"
                        "随后携带 --run RUN --snapshot SNAPSHOT 回来执行 package")
GENERATION_GUIDE = ("完整链路：prepare 冻结主题；ImageGen/hatch-pet 生成并独立视觉审阅；"
                    "package 或 validate 复核证据；最后 sync 安装")


class PetError(Exception):
    """Refusal with a stable machine-readable code; never a crash."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition, message, code="invalid"):
    if not condition:
        raise PetError(code, message)


# ---------------------------------------------------------------------------
# Digest and JSON helpers shared by every layer above.
# ---------------------------------------------------------------------------

def sha(data):
    return hashlib.sha256(data).hexdigest()


def is_hex_digest(value):
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def canonical(value):
    """One canonical byte form per JSON value, used for revision identities."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def json_bytes(value):
    """The on-disk JSON form: indented for review, newline terminated."""
    return json.dumps(value, ensure_ascii=False, indent=2,
                      allow_nan=False).encode("utf-8") + b"\n"


# ---------------------------------------------------------------------------
# Frozen byte capture: path policy and one stable read primitive.
# ---------------------------------------------------------------------------

def anchored_root(path):
    """Canonical project/home root; the anchor itself must not be a symlink."""
    path = Path(path).expanduser().absolute()
    require(not path.is_symlink(), f"根目录不能是符号链接：{path}")
    return path.resolve()


def child(root, relative):
    """Resolve one relative path under root, refusing escapes and symlinks."""
    parts = Path(relative).parts
    require(not Path(relative).is_absolute() and ".." not in parts,
            f"相对路径试图越出根目录：{relative}")
    target = root
    for part in parts:
        target = target / part
        require(not target.is_symlink(), f"路径中段不允许符号链接：{target}")
    return target


def _identity_of(info):
    """Everything that changes when a path is re-bound or its bytes rewritten."""
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_readonly_nofollow(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise PetError("invalid", f"无法以安全方式打开读取：{path}") from exc


def _drain_bounded(fd, path):
    """Read a file descriptor to EOF within the global size ceiling."""
    chunks, total = [], 0
    while True:
        budget = min(1024 * 1024, MAX_FILE_BYTES + 1 - total)
        try:
            chunk = os.read(fd, budget)
        except InterruptedError:
            continue
        except OSError as exc:
            raise PetError("invalid", f"读取字节流失败：{path}") from exc
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        require(total <= MAX_FILE_BYTES, f"文件超出 64 MiB 上限：{path}")
        chunks.append(chunk)


def read(path):
    """Capture one regular file's bytes with a stable-identity proof.

    The reader refuses symlinks and special files, bounds the size, and
    compares the file's identity before opening, right after opening, after
    the final byte, and once more through the path. Any disagreement — an
    in-place rewrite, a swap, a truncation — aborts without returning bytes.
    """
    path = Path(path)
    try:
        pre_open = path.lstat()
    except OSError as exc:
        raise PetError("invalid", f"这里应有一个可读取的普通文件：{path}") from exc
    require(stat.S_ISREG(pre_open.st_mode), f"这里应有一个可读取的普通文件：{path}")
    require(pre_open.st_size <= MAX_FILE_BYTES, f"文件超出 64 MiB 上限：{path}")
    fd = _open_readonly_nofollow(path)
    try:
        opened_view = os.fstat(fd)
        entry_unchanged = ((opened_view.st_dev, opened_view.st_ino)
                           == (pre_open.st_dev, pre_open.st_ino)
                           and stat.S_ISREG(opened_view.st_mode))
        require(entry_unchanged and opened_view.st_size <= MAX_FILE_BYTES,
                f"打开前后文件已不是同一个受限普通文件：{path}", "source-conflict")
        payload = _drain_bounded(fd, path)
        drained_view = os.fstat(fd)
        try:
            final_view = path.lstat()
        except OSError as exc:
            raise PetError("source-conflict", f"读完时路径上的文件已消失：{path}") from exc
        observed = (_identity_of(pre_open), _identity_of(opened_view),
                    _identity_of(drained_view), _identity_of(final_view))
        require(stat.S_ISREG(final_view.st_mode) and len(set(observed)) == 1
                and len(payload) == drained_view.st_size,
                f"捕获窗口内文件被并发改写：{path}", "source-conflict")
        return payload
    finally:
        os.close(fd)


def parse(data):
    """Strict JSON: duplicate keys and NaN-style constants are refused."""
    def refuse_duplicate_keys(pairs):
        unique = {}
        for key, value in pairs:
            if key in unique:
                raise ValueError("同一对象里出现了重复字段")
            unique[key] = value
        return unique

    def refuse_constant(token):
        raise ValueError(token)

    try:
        return json.loads(data, object_pairs_hook=refuse_duplicate_keys,
                          parse_constant=refuse_constant)
    except (ValueError, UnicodeError) as exc:
        raise PetError("invalid", f"JSON 无效，无法解析：{exc}") from exc


# ---------------------------------------------------------------------------
# Durable publication primitives: exclusive create, fsync, atomic replace.
# ---------------------------------------------------------------------------

_RENAME_EXCL_DARWIN = 4      # RENAME_EXCL
_RENAME_NOREPLACE_LINUX = 1  # RENAME_NOREPLACE
_AT_FDCWD = -100


def rename_exclusive(source, destination):
    """Move one directory entry, failing when the destination already exists.

    The platform no-replace rename guarantees a racing writer can never end
    up underneath an entry this tool is about to own.
    """
    try:
        if sys.platform == "darwin":
            system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            call = system.renamex_np
            call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            call.restype = ctypes.c_int
            outcome = call(os.fsencode(source), os.fsencode(destination),
                           _RENAME_EXCL_DARWIN)
        elif sys.platform.startswith("linux"):
            system = ctypes.CDLL(None, use_errno=True)
            call = system.renameat2
            call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                             ctypes.c_char_p, ctypes.c_uint]
            call.restype = ctypes.c_int
            outcome = call(_AT_FDCWD, os.fsencode(source), _AT_FDCWD,
                           os.fsencode(destination), _RENAME_NOREPLACE_LINUX)
        else:
            raise PetError("invalid", "本平台缺少可用的不覆盖重命名接口")
    except AttributeError as exc:
        raise PetError("invalid", "本平台缺少可用的不覆盖重命名接口") from exc
    if outcome != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), str(destination))


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_tree(path):
    directories = [entry for entry in path.rglob("*") if entry.is_dir()]
    for directory in sorted(directories, key=lambda entry: len(entry.parts),
                            reverse=True):
        require(not directory.is_symlink(), f"同步前发现符号链接，拒绝继续：{directory}")
        fsync_dir(directory)
    fsync_dir(path)


def write_new(path, data):
    """Create one exclusive file and flush it to stable storage."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
        return os.fstat(stream.fileno())


def atomic_json(path, value):
    """Publish one JSON document through a provably-owned temporary file.

    The temporary file is unlinked only while its bytes still match what we
    wrote; a foreign writer that hijacks the temporary name keeps its file
    for review instead of being silently destroyed.
    """
    require(not path.is_symlink(), f"目标 JSON 路径是符号链接，拒绝写入：{path}")
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = json_bytes(value)
    owned = None
    published = False

    def still_ours():
        if owned is None:
            return False
        try:
            current = temp.lstat()
            if not (stat.S_ISREG(current.st_mode)
                    and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino)):
                return False
            return read(temp) == data
        except (OSError, PetError):
            return False

    try:
        owned = write_new(temp, data)
        require(still_ours(), f"暂存回执写入后被改动，留待人工核对：{temp}",
                "source-conflict")
        os.replace(temp, path)
        published = True
        fsync_dir(path.parent)
    finally:
        if not published and still_ours():
            temp.unlink()


@contextlib.contextmanager
def lock(path):
    """Advisory exclusive lock; a held lock surfaces as code `busy`."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PetError("busy", f"锁已被其他操作占用：{path}") from exc
        yield
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Theme domain: per-project state, revision identity, frozen snapshots.
# ---------------------------------------------------------------------------

def state_dir(project, create=False):
    """Manager state for one project lives under .local/pets/<PET_ID>."""
    path = child(project, f".local/pets/{PET_ID}")
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def revision(records):
    """Content revision of a recorded input list."""
    return sha(canonical({"schemaVersion": 1, "inputs": records}))


def theme_facts(project):
    """Read the four theme inputs and derive their current revision.

    Inputs are re-read once and compared so a change inside the freeze window
    is refused rather than half-captured. No project source file is written.
    """
    blobs = {name: read(child(project, name)) for name in INPUTS}
    config = parse(blobs["pet/theme.json"])
    require(isinstance(config, dict), "theme.json 应为一个 JSON 对象")
    identity_ok = (config.get("id") == PET_ID
                   and config.get("spriteVersionNumber") == 2)
    require(identity_ok, "theme.json 中的 pet 标识或版本不符合约定")
    naming_ok = (config.get("displayName") == PET_DISPLAY_NAME
                 and config.get("themeInputs") == list(INPUTS))
    require(naming_ok, "theme.json 需保持既定显示名与四个主题输入项")
    description = config.get("description")
    require(isinstance(description, str) and bool(description.strip()),
            "theme.json 未提供可用的 description")
    records = [{"path": name, "sha256": sha(blobs[name])} for name in INPUTS]
    refrozen = all(sha(read(child(project, record["path"]))) == record["sha256"]
                   for record in records)
    require(refrozen, "冻结期间主题输入被改动，请重新执行", "source-conflict")
    facts = {"schemaVersion": 1, "petId": PET_ID, "themeRevision": revision(records),
             "inputs": records}
    return facts, blobs, config


def snapshot_metadata(snapshot):
    """Validate one snapshot document and return its revision."""
    require(isinstance(snapshot, dict) and snapshot.get("petId") == PET_ID,
            "snapshot 的 petId 与本管理器不一致")
    version = snapshot.get("schemaVersion")
    require(type(version) is int and version == 1,
            "snapshot 的 schemaVersion 无法识别，留待核对")
    records = snapshot.get("inputs", [])
    well_formed = (isinstance(records, list)
                   and all(isinstance(record, dict) for record in records))
    require(well_formed, "snapshot 的 inputs 应为对象数组")
    recorded_paths = [record.get("path") for record in records]
    require(recorded_paths == list(INPUTS), "snapshot 记录的输入清单与约定不符")
    require(all(is_hex_digest(record.get("sha256")) for record in records),
            "snapshot 记录的输入摘要不是合法的十六进制摘要")
    require(snapshot.get("themeRevision") == revision(records),
            "snapshot 的 themeRevision 与输入记录推导结果不一致")
    return snapshot["themeRevision"]


def load_snapshot(project, path):
    """Open a published snapshot and re-tie it to the project's live inputs."""
    path = Path(path).expanduser().absolute()
    require(not path.is_symlink(), f"快照文件本身不能是符号链接：{path}")
    raw = read(path)
    snapshot = parse(raw)
    frozen_revision = snapshot_metadata(snapshot)
    for record in snapshot["inputs"]:
        frozen_copy = child(path.parent, Path("inputs") / record["path"])
        require(sha(read(frozen_copy)) == record["sha256"],
                f"冻结输入与记录摘要不符：{record['path']}")
    current, _, config = theme_facts(project)
    require(current["themeRevision"] == frozen_revision,
            "主题已更新；请重新 prepare，用新快照运行 ImageGen/hatch-pet 并再次审阅",
            "generation-required")
    return raw, snapshot, config


# ---------------------------------------------------------------------------
# Artifact audit: atlas structure, QA verdicts, run validation.
# ---------------------------------------------------------------------------

def _expected_cells():
    """Animation frames per row plus the reserved toolchain neutral cell."""
    cells = {(row, column) for row, count in enumerate(FRAME_COUNTS)
             for column in range(count)}
    cells.add(TOOLCHAIN_NEUTRAL_CELL)
    return cells


def inspect_atlas(data, require_webp=False):
    """Fully decode a v2 atlas and audit occupancy plus transparency.

    The audit is structural, not cosmetic: every expected cell needs visible
    pixels *and* at least one transparent pixel, every unused cell must be
    fully transparent, and fully transparent pixels must not carry non-zero
    RGB residue. A truncated or animated file never passes.
    """
    require(len(data) <= MAX_FILE_BYTES, "图集体积超过 64 MiB 限制")
    try:
        with Image.open(io.BytesIO(data)) as decoded:
            accepted = ("WEBP",) if require_webp else ("PNG", "WEBP")
            require(decoded.format in accepted, "图集文件格式不在接受范围")
            require(decoded.size == (ATLAS_WIDTH, ATLAS_HEIGHT),
                    "v2 图集的尺寸只能是 1536×2288")
            require(getattr(decoded, "n_frames", 1) == 1,
                    "只接受单帧静态图集，动画文件不支持")
            require("A" in decoded.getbands() or "transparency" in decoded.info,
                    "图集没有可用的透明通道")
            decoded.load()
            raster = decoded.convert("RGBA")
    except PetError:
        raise
    except Exception as exc:
        raise PetError("invalid", f"图集无法完整解码：{exc}") from exc

    alpha = raster.getchannel("A")
    floor, ceiling = alpha.getextrema()
    require(floor == 0 and ceiling > 0, "整张图集需要同时具备透明区域与可见像素")

    expected = _expected_cells()
    for row in range(ATLAS_ROWS):
        for column in range(ATLAS_COLUMNS):
            x, y = column * CELL_WIDTH, row * CELL_HEIGHT
            low, high = alpha.crop((x, y, x + CELL_WIDTH, y + CELL_HEIGHT)).getextrema()
            occupied = (row, column) in expected
            require((high > 0) == occupied,
                    f"第 {row} 行第 {column} 列的占用与透明判定不符")
            if occupied:
                require(low == 0, f"已占用单元格还需包含透明像素：row={row}, col={column}")

    transparent_mask = alpha.point(lambda value: 255 if value == 0 else 0)
    transparent_rgb = Image.composite(raster.convert("RGB"),
                                      Image.new("RGB", raster.size), transparent_mask)
    require(transparent_rgb.getbbox() is None, "全透明像素仍残留非零 RGB 分量")
    # Neutral is a toolchain reference; its pixels need not mirror idle00, so
    # the equality flag is diagnostic output and never a gate.
    idle00 = raster.crop((0, 0, CELL_WIDTH, CELL_HEIGHT)).tobytes()
    neutral = raster.crop((6 * CELL_WIDTH, 0, 7 * CELL_WIDTH, CELL_HEIGHT)).tobytes()
    rendered = sum(FRAME_COUNTS)
    return {
        "atlasSHA256": sha(data), "pixelSHA256": sha(raster.tobytes()),
        "width": ATLAS_WIDTH, "height": ATLAS_HEIGHT,
        "usedCells": len(expected), "occupiedCells": len(expected),
        "renderedCells": rendered,
        "animationCells": sum(FRAME_COUNTS[:ANIMATION_ROWS]),
        "lookDirectionCells": sum(FRAME_COUNTS[ANIMATION_ROWS:]),
        "neutralCells": 1, "unusedCells": ATLAS_CELL_TOTAL - len(expected),
        "neutralMatchesIdle00": neutral == idle00,
        "fullDecode": True,
    }


def declares_failure(value):
    """A document that states failure anywhere is failed, whatever `ok` says."""
    failure_markers = ("verdict", "status", "result")
    boolean_gates = ("ok", "pass")
    stated = any(value.get(key) in ("fail", "failed") for key in failure_markers)
    flagged = any(value.get(key) is False for key in boolean_gates)
    return stated or flagged


def passed(value):
    """Explicit success only; silence, zero-like values and maps do not pass."""
    if declares_failure(value):
        return False
    affirmative = (value.get("ok") is True or value.get("pass") is True
                   or value.get("status") in ("pass", "passed", "ok")
                   or value.get("result") == "pass"
                   or value.get("verdict") == "pass")
    return affirmative


def _direction_records(report):
    """Accept the semantics QA as a list or as a direction->record mapping."""
    for key in ("directions", "results", "checks"):
        if key not in report:
            continue
        records = report[key]
        if not isinstance(records, dict):
            return records
        return [dict(value, direction=name) if isinstance(value, dict)
                else {"direction": name, "pass": value}
                for name, value in records.items()]
    return None


def validate_qa(raw, atlas_hash, theme_rev):
    """Audit the six review documents against the concrete candidate bytes."""
    documents = [parse(raw[name]) for name in QA_FILES]
    for name, document in zip(QA_FILES, documents):
        require(isinstance(document, dict), f"QA 文档应为 JSON 对象：{name}")
        require(not document.get("errors") and not document.get("failures"),
                f"该 QA 文档含失败记录：{name}")
    for index in (0, 1, 4):
        require(passed(documents[index]), f"该 QA 文档缺少明确的通过结论：{QA_FILES[index]}")
    require(documents[2].get("errors") == [], "review.json 需要显式给出空 errors 列表")

    semantics = documents[3]
    records = _direction_records(semantics)
    require(isinstance(records, list) and len(records) == DIRECTION_SLOT_COUNT,
            "方向语义记录应为 16 条")
    require(all(isinstance(record, dict) for record in records),
            "方向语义的每条记录都应是对象")
    try:
        angles = []
        for record in records:
            label = record.get("direction", record.get("angle", record.get("id", "")))
            angles.append(float(str(label).removesuffix("°")))
    except ValueError as exc:
        raise PetError("invalid", "方向必须用 000、022.5 直到 337.5 的度数标记") from exc

    slot_by_angle = {index * DIRECTION_STEP_DEGREES: 1 << index
                     for index in range(DIRECTION_SLOT_COUNT)}
    covered = 0
    for angle in angles:
        covered |= slot_by_angle.get(angle, 0)
    require(covered == (1 << DIRECTION_SLOT_COUNT) - 1,
            "方向记录缺失、有重复或未落在 16 向网格上")

    review = documents[5]
    require(passed(review) and review.get("atlasSHA256") == atlas_hash
            and review.get("themeRevision") == theme_rev,
            "视觉审阅未通过：pass 缺失，或 atlasSHA256/themeRevision 与候选不符")
    resolution = review.get("blindResolution", {})
    minor_warning_approved = (review.get("labeledLoopReviewed") is True
                              and isinstance(resolution, dict)
                              and resolution.get("decision") == "accept"
                              and resolution.get("severity") == "minor")
    for angle, record in zip(angles, records):
        verdict = record.get("verdict", record.get("status", record.get("result")))
        intermediate = angle not in CARDINAL_DIRECTIONS
        waivable = (intermediate and minor_warning_approved
                    and record.get("severity", "minor") == "minor")
        accepted = (waivable and not declares_failure(record)
                    if verdict == "warning" else passed(record))
        require(not record.get("errors") and not record.get("failures") and accepted,
                f"方向 {angle:g} 判定未过；中间朝向的 warning 需要 labeled-loop 复核与 minor 级 accept 记录")
    blind = documents[4]
    if blind.get("reviewRequired") or blind.get("warnings"):
        require(minor_warning_approved,
                "盲测 warning 缺少 labeled-loop 复核与 minor 级 accept 证据")
    require(not blind.get("unconfirmed"), "盲测记录里仍有未确认的朝向")
    return {name: sha(content) for name, content in raw.items()}


def native_manifest(config):
    """The only manifest shape the native v2 host accepts."""
    return {"id": PET_ID, "displayName": PET_DISPLAY_NAME,
            "description": config["description"],
            "spriteVersionNumber": 2, "spritesheetPath": "spritesheet.webp"}


def validate_run(project, run, snapshot_path):
    """Validate one ImageGen/hatch-pet run against its frozen snapshot."""
    snapshot_raw, snapshot, config = load_snapshot(project, snapshot_path)
    audited_run = anchored_root(run)
    atlas = read(child(audited_run, "final/spritesheet-extended.webp"))
    facts = inspect_atlas(atlas, require_webp=True)
    qa_raw = {name: read(child(audited_run, name)) for name in QA_FILES}
    qa_hashes = validate_qa(qa_raw, facts["atlasSHA256"], snapshot["themeRevision"])
    return {"snapshotRaw": snapshot_raw, "snapshot": snapshot, "config": config,
            "atlas": atlas, "facts": facts, "qaRaw": qa_raw, "qaHashes": qa_hashes}


# ---------------------------------------------------------------------------
# Candidate audit: ownership, package layout, selection resolution.
# ---------------------------------------------------------------------------

def ownership(receipt, project):
    """A directory is only writable when its receipt names this project."""
    ours = (isinstance(receipt, dict) and receipt.get("owner") == OWNER
            and receipt.get("projectRoot") == str(project)
            and receipt.get("petId") == PET_ID)
    require(ours, "同名内容不属于本管理器管辖，不予覆盖", "unknown-target")


def package_files(directory):
    """List every regular file below directory; refuse surprises.

    Empty sub-directories, symlinks and special entries abort the scan: the
    manager only enumerates trees it is willing to publish or delete.
    """
    directory = Path(directory)
    names = set()

    def walk(folder, *, is_root=False):
        try:
            with os.scandir(folder) as scan:
                entries = list(scan)
            if not is_root and not entries:
                raise PetError("recovery-required", f"出现无主的空目录，拒绝继续处理：{folder}")
            for entry in entries:
                path = Path(entry.path)
                require(not entry.is_symlink(), f"包内不允许出现符号链接：{path}")
                if entry.is_dir(follow_symlinks=False):
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    names.add(path.relative_to(directory).as_posix())
                else:
                    raise PetError("recovery-required",
                                   f"目录中存在非常规文件，不能清理：{path}")
        except OSError as exc:
            raise PetError("recovery-required", f"目录扫描无法完成：{folder}") from exc

    walk(directory, is_root=True)
    return names


def check_package(directory, project, require_current=True):
    """Audit a candidate package end to end; return (facts, receipt)."""
    require(directory.is_dir() and not directory.is_symlink(), "找不到候选包目录")
    require(package_files(directory) == PACKAGE_ENTRIES, "候选包的文件集合缺失或多出未知项")
    receipt = parse(read(directory / "package-receipt.json"))
    ownership(receipt, project)
    snapshot_raw = read(directory / "theme-snapshot.json")
    snapshot = parse(snapshot_raw)
    package_revision = snapshot_metadata(snapshot)
    config = None
    if require_current:
        current, _, config = theme_facts(project)
        require(package_revision == current["themeRevision"],
                "主题已更新，需要重新走 prepare、生成与审阅", "generation-required")
    facts = inspect_atlas(read(directory / "spritesheet.webp"), require_webp=True)
    package_qa = {name: read(child(directory, name)) for name in QA_FILES}
    qa_hashes = validate_qa(package_qa, facts["atlasSHA256"], package_revision)
    manifest_raw = read(directory / "pet.json")
    manifest = parse(manifest_raw)
    manifest_ok = (isinstance(manifest, dict) and set(manifest) == MANIFEST_FIELDS
                   and manifest.get("id") == PET_ID
                   and manifest.get("displayName") == PET_DISPLAY_NAME
                   and manifest.get("spriteVersionNumber") == 2
                   and manifest.get("spritesheetPath") == "spritesheet.webp")
    require(manifest_ok, "pet.json 不满足原生 v2 的字段约定")
    if require_current:
        require(manifest == native_manifest(config), "pet.json 的内容与冻结主题对不上")
    receipt_ok = (receipt.get("atlasSHA256") == facts["atlasSHA256"]
                  and receipt.get("themeRevision") == package_revision
                  and receipt.get("qaSHA256") == qa_hashes
                  and receipt.get("snapshotSHA256") == sha(snapshot_raw)
                  and receipt.get("manifestSHA256") == sha(manifest_raw))
    require(receipt_ok, "包内字节与 receipt 记录的摘要不符")
    audited = {"themeRevision": package_revision, **facts,
               "manifestSHA256": sha(manifest_raw)}
    return audited, receipt


def selected_package(project):
    """Resolve selection.json to its content-addressed package directory."""
    state = state_dir(project)
    selection = parse(read(child(state, "selection.json")))
    require(isinstance(selection, dict) and set(selection) == SELECTION_FIELDS,
            "selection 记录结构无法识别，留待核对", "source-conflict")
    name = selection["package"]
    canonical_shape = (isinstance(name, str) and len(name) == 129 and name[64] == "-"
                       and all(char in "0123456789abcdef"
                               for char in name[:64] + name[65:]))
    require(canonical_shape and selection["themeRevision"] == name[:64]
            and selection["atlasSHA256"] == name[65:],
            "selection 记录与包路径推不出同一候选，留待核对", "source-conflict")
    return child(state, "packages/" + name)


def package_directory_matches(directory, receipt):
    """True when the receipt binds the exact directory inode still on disk."""
    binding = receipt.get("directoryIdentity")
    if not (isinstance(binding, dict) and set(binding) == {"device", "inode"}):
        return False
    if any(type(binding[field]) is not int or binding[field] < 0 for field in binding):
        return False
    try:
        actual = directory.lstat()
    except OSError:
        return False
    same_entry = (stat.S_ISDIR(actual.st_mode)
                  and actual.st_dev == binding["device"]
                  and actual.st_ino == binding["inode"])
    return same_entry


def verified_selected_package(project, *, require_current=True):
    """The selected package, re-audited down to its directory identity."""
    directory = selected_package(project)
    facts, receipt = check_package(directory, project, require_current=require_current)
    unbound_ok = ("directoryIdentity" not in receipt
                  or package_directory_matches(directory, receipt))
    require(unbound_ok, "选中候选的目录身份不匹配，留待核对", "source-conflict")
    require(directory.name == facts["themeRevision"] + "-" + facts["atlasSHA256"],
            "选中候选的内容与路径不一致，留待核对", "source-conflict")
    return directory, facts, receipt


# ---------------------------------------------------------------------------
# Removal plans: freeze a directory, then delete only what was frozen.
# ---------------------------------------------------------------------------

def capture_removal_plan(path, names):
    """Freeze a directory's identity and content before it may be deleted."""
    require(path.is_dir() and not path.is_symlink(),
            f"待删对象不是普通目录：{path}", "recovery-required")
    identity = path.lstat()
    require(package_files(path) == names, "清理对象文件集与计划不符，留待核对",
            "recovery-required")
    files = {name: sha(read(child(path, name))) for name in names}
    plan = {"directoryIdentity": {"device": identity.st_dev, "inode": identity.st_ino},
            "files": files}
    still_frozen = (package_directory_matches(path, plan)
                    and package_files(path) == names)
    require(still_frozen, "清理对象的身份或内容在计划后发生变动，留待核对",
            "recovery-required")
    return plan


def remove_tree(path, plan):
    """Delete a directory only while it still matches the frozen plan exactly."""
    files = plan["files"]
    frozen_still = (package_directory_matches(path, plan)
                    and package_files(path) == set(files))
    require(frozen_still, "清理对象的身份或内容在计划后发生变动，留待核对",
            "recovery-required")
    require(all(sha(read(child(path, name))) == digest
                for name, digest in files.items()),
            "清理对象的内容在计划后发生变动，留待核对", "recovery-required")
    unlink_bound_tree(path, plan["directoryIdentity"], files, allow_missing=False)


def _open_dir_at(parent_fd, name):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    return os.open(name, flags, dir_fd=parent_fd)


def unlink_bound_tree(directory, binding, files, *, allow_missing):
    """Unlink exactly the planned files through dir_fd handles, deepest last.

    The root's identity is re-derived from its parent before and after every
    step, so a directory swapped between plan and unlink aborts the cleanup.
    Missing entries are tolerated only when the caller allows resuming.
    """
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    expected_root = (binding["device"], binding["inode"])
    planned_dirs = {parent.as_posix() for name in files
                    for parent in Path(name).parents if parent != Path(".")}

    def short_identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    try:
        with contextlib.ExitStack() as root_handles:
            parent_fd = os.open(directory.parent, flags)
            root_handles.callback(os.close, parent_fd)
            root_fd = _open_dir_at(parent_fd, directory.name)
            root_handles.callback(os.close, root_fd)

            def root_still_bound():
                by_name = os.stat(directory.name, dir_fd=parent_fd,
                                  follow_symlinks=False)
                opened = os.fstat(root_fd)
                still_dir = (stat.S_ISDIR(by_name.st_mode)
                             and stat.S_ISDIR(opened.st_mode))
                still_root = ((by_name.st_dev, by_name.st_ino) == expected_root
                              and (opened.st_dev, opened.st_ino) == expected_root)
                require(still_dir and still_root,
                        "清理过程中目录身份发生变化，留待核对", "recovery-required")

            def descend(parts, handles):
                cursor = root_fd
                for part in parts:
                    cursor = _open_dir_at(cursor, part)
                    handles.callback(os.close, cursor)
                return cursor

            def digest_if_stable(fd, expected_sha):
                before = os.fstat(fd)
                regular = (stat.S_ISREG(before.st_mode)
                           and before.st_size <= MAX_FILE_BYTES)
                require(regular, "待清理文件不在允许的普通文件范围，留待核对",
                        "recovery-required")
                running, total = hashlib.sha256(), 0
                while True:
                    budget = min(1024 * 1024, MAX_FILE_BYTES + 1 - total)
                    try:
                        chunk = os.read(fd, budget)
                    except InterruptedError:
                        continue
                    if not chunk:
                        break
                    total += len(chunk)
                    require(total <= MAX_FILE_BYTES, "待清理文件超出大小上限，留待核对",
                            "recovery-required")
                    running.update(chunk)
                return running.hexdigest(), before, os.fstat(fd), total

            root_still_bound()
            for name, expected_sha in sorted(files.items()):
                parts = Path(name).parts
                with contextlib.ExitStack() as handles:
                    try:
                        folder_fd = descend(parts[:-1], handles)
                        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW
                                     | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=folder_fd)
                    except FileNotFoundError:
                        if allow_missing:
                            continue
                        raise
                    handles.callback(os.close, fd)
                    digest, before, after, total = digest_if_stable(fd, expected_sha)
                    by_name = os.stat(parts[-1], dir_fd=folder_fd,
                                      follow_symlinks=False)
                    file_stable = (stat.S_ISREG(by_name.st_mode)
                                   and short_identity(before) == short_identity(after)
                                   and short_identity(after) == short_identity(by_name)
                                   and total == after.st_size and digest == expected_sha)
                    require(file_stable, "待清理文件在读取期间被改动，留待核对",
                            "recovery-required")
                    root_still_bound()
                    os.unlink(parts[-1], dir_fd=folder_fd)
            deepest_first = sorted(planned_dirs,
                                   key=lambda item: (-len(Path(item).parts), item))
            for name in deepest_first:
                parts = Path(name).parts
                with contextlib.ExitStack() as handles:
                    try:
                        folder_fd = descend(parts[:-1], handles)
                        root_still_bound()
                        os.rmdir(parts[-1], dir_fd=folder_fd)
                    except FileNotFoundError:
                        if allow_missing:
                            continue
                        raise
            root_still_bound()
            os.rmdir(directory.name, dir_fd=parent_fd)
    except OSError as exc:
        raise PetError("recovery-required", f"无法安全移除目录，留待核对：{exc}") from exc


# ---------------------------------------------------------------------------
# Staging channel: journaled scratch directories with a kind and a file set.
# ---------------------------------------------------------------------------

def stage_file_names(kind):
    """The exact file set each staged directory kind may contain."""
    if kind == "snapshot":
        return {*("inputs/" + name for name in INPUTS),
                "generation-brief.md", "theme-snapshot.json"}
    if kind == "package":
        return set(PACKAGE_ENTRIES)
    if kind == "install":
        return set(INSTALL_ENTRIES)
    raise PetError("recovery-required", "暂存类型不在已知范围，不会自动清理")


def freeze_stage_payload(kind, files):
    """Validate a staged payload against its kind and freeze the digests."""
    require(set(files) == stage_file_names(kind), "暂存计划的文件集合与类型不匹配",
            "recovery-required")
    return {name: sha(data) for name, data in files.items()}


def stage_journal(project, stage, kind, files, operation_id):
    """Bind a staging directory to its owner, kind and planned content."""
    identity = stage.lstat()
    require(stat.S_ISDIR(identity.st_mode), "暂存位置不是普通目录", "recovery-required")
    journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
               "stage": stage.name, "stageKind": kind,
               "stageFiles": freeze_stage_payload(kind, files),
               "stageIdentity": {"device": identity.st_dev, "inode": identity.st_ino}}
    if operation_id is not None:
        journal["operationId"] = operation_id
    return journal


def assert_stage_binding(stage, journal):
    """The staging directory must still be the inode the journal bound."""
    bound = package_directory_matches(stage,
                                      {"directoryIdentity": journal.get("stageIdentity")})
    require(bound, "暂存目录与日志记录的 inode 绑定不匹配，留待核对",
            "recovery-required")


def verify_stage_for_cleanup(stage, journal, expected_kinds):
    """Prove a staging directory holds exactly its journaled content.

    Planned files may be missing — an interrupted write resumes — but any
    extra file, extra directory, symlink or changed byte stops cleanup so
    the evidence survives for human review.
    """
    require(stage.is_dir() and not stage.is_symlink(), "暂存位置不是普通目录",
            "recovery-required")
    assert_stage_binding(stage, journal)
    kind, files = journal.get("stageKind"), journal.get("stageFiles")
    require(kind in expected_kinds, "暂存日志没有可识别的类型绑定，留待核对",
            "recovery-required")
    require(isinstance(files, dict) and set(files) == stage_file_names(kind),
            "暂存计划的文件集合与类型不匹配", "recovery-required")
    require(all(isinstance(value, str) and is_hex_digest(value)
                for value in files.values()),
            "暂存计划中的摘要不是合法摘要值", "recovery-required")
    verified = 0
    planned_dirs = {parent.as_posix() for name in files
                    for parent in Path(name).parents if parent != Path(".")}

    def audit(folder):
        nonlocal verified
        try:
            with os.scandir(folder) as scan:
                for entry in scan:
                    path = Path(entry.path)
                    relative = path.relative_to(stage).as_posix()
                    require(not entry.is_symlink(), "暂存内出现符号链接，停止清理",
                            "recovery-required")
                    if entry.is_dir(follow_symlinks=False):
                        require(relative in planned_dirs, "暂存内出现计划外目录，停止清理",
                                "recovery-required")
                        audit(path)
                        continue
                    require(entry.is_file(follow_symlinks=False) and relative in files,
                            "暂存内出现计划外文件，停止清理", "recovery-required")
                    try:
                        actual = sha(read(path))
                    except PetError as exc:
                        raise PetError("recovery-required",
                                       f"暂存文件读取核验失败：{exc}") from exc
                    require(actual == files[relative], "暂存文件字节与日志记录不同，停止清理",
                            "recovery-required")
                    verified += 1
        except OSError as exc:
            raise PetError("recovery-required", f"暂存目录核验中断，停止清理：{exc}") from exc

    audit(stage)
    require(verified > 0, "没有任何已核验文件的暂存不足以证明归属，留待核对",
            "recovery-required")
    assert_stage_binding(stage, journal)


def discard_bound_stage(stage, journal, expected_kinds):
    """Verify then delete one journaled staging directory."""
    verify_stage_for_cleanup(stage, journal, expected_kinds)
    unlink_bound_tree(stage, journal["stageIdentity"], journal["stageFiles"],
                      allow_missing=True)


def recover_package_stage(state, project, operation_id=None):
    """Replay or discard an interrupted snapshot/package staging journal."""
    journal = child(state, "package-journal.json")
    if not journal.exists():
        return
    record = parse(read(journal))
    ownership(record, project)
    require(record.get("operationId") == operation_id,
            "暂存日志归属于另一个操作，不会自动恢复", "recovery-required")
    name = record.get("stage", "")
    name_ok = (isinstance(name, str) and name.startswith(".stage-")
               and len(name) == STAGE_NAME_LENGTH)
    require(name_ok, "暂存日志中的目录名不合法", "recovery-required")
    stage = child(state, name)
    phase = record.get("phase")
    require(phase in (None, "allocating"), "暂存日志的 phase 无法识别，留待核对",
            "recovery-required")
    if phase == "allocating":
        require("stageKind" not in record and "stageFiles" not in record,
                "allocating 阶段日志不应携带内容绑定，留待核对", "recovery-required")
        require(not stage.exists(), "allocating 阶段就已存在的目录无法证明归属，留待核对",
                "recovery-required")
    if stage.exists():
        verify_stage_for_cleanup(stage, record, {"snapshot", "package"})
        assert_stage_binding(stage, record)
        discard_bound_stage(stage, record, {"snapshot", "package"})
    journal.unlink()
    fsync_dir(state)


# ---------------------------------------------------------------------------
# Publication orchestration: one journaled stage-and-rename pipeline shared
# by snapshots and candidate packages.
# ---------------------------------------------------------------------------

def _claim_stage(state, project, stage_name, operation_id):
    """Durably claim a stage directory name before the directory exists."""
    claim = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
             "stage": stage_name, "phase": "allocating"}
    if operation_id is not None:
        claim["operationId"] = operation_id
    atomic_json(state / "package-journal.json", claim)


def publish_staged_directory(state, project, kind, build_payload, destination,
                             operation_id=None, after_materialize=None):
    """Publish one directory through a journaled, exclusively-created stage.

    Sequence: claim the stage name durably, create the stage, bind kind and
    content in the journal, materialize the payload files, optionally audit
    the staged tree, prove the stage identity across fsync, then rename into
    place without replacing anything. Any failure leaves the stage and the
    journal behind for `recover_package_stage`.
    """
    stage = child(state, ".stage-" + uuid.uuid4().hex)
    _claim_stage(state, project, stage.name, operation_id)
    try:
        stage.mkdir(mode=0o700)
        payload = build_payload(stage)
        journal = stage_journal(project, stage, kind, payload, operation_id)
        atomic_json(state / "package-journal.json", journal)
        for name, blob in payload.items():
            write_new(child(stage, name), blob)
        if after_materialize is not None:
            after_materialize(stage)
        assert_stage_binding(stage, journal)
        fsync_tree(stage)
        assert_stage_binding(stage, journal)
        rename_exclusive(stage, destination)
        fsync_dir(destination.parent)
    finally:
        recover_package_stage(state, project, operation_id)


def _generation_brief(revision_value):
    """Compose the task sheet handed to external ImageGen/hatch-pet work.

    The sheet restates the frozen revision and the atlas contract numbers the
    auditor will later enforce, so generation and review share one reference.
    """
    return (f"# Codex 原生 pet v2 · 生成任务单\n\n"
            f"主题修订号：`{revision_value}`（快照与验收均以此为准）\n\n"
            "素材边界：只允许使用本目录 inputs/ 里的四项冻结输入，配合 ImageGen 与"
            "原生 hatch-pet v2 出图；项目内的同名素材此时可能已被改动，一律不得再读，"
            "也不得把任何现成图集冒充为本轮生成结果。\n\n"
            "角色设定：延续女性 Q 版阿舟——大头、小身体、短四肢，暖橙/奶白/棕配色；"
            "已授权的正式 Q 版主形象仅作参照，不改动原 IP 素材库。\n\n"
            "交付规格：单张透明 WebP 图集，画布 1536×2288，按 8 列×11 行、"
            "每格 192×208 排布；第 1–9 行为动画帧，各行帧数依次为 "
            "6/8/8/4/5/8/6/6/6；第 10–11 行为 look 方向，共 16 格顺时针一周。"
            "row0/col6 由工具链放置经原生流程处理的 neutral 参考，不计入动画帧数；"
            "其余 14 个空位必须保持完全透明。\n\n"
            "验收要求：按 hatch-pet v2 清单逐项完成解码、去色溢、动画与方向 QA；"
            "visual-qa.json 须写明本修订号、交付图集的 atlasSHA256，并给出明确的 "
            "pass 结论。快照就绪不代表已生成，更不代表视觉审阅通过。\n")


def prepare(project, operation_id=None):
    """Freeze the theme inputs and publish the generation snapshot directory."""
    state = state_dir(project, True)
    recover_package_stage(state, project, operation_id=operation_id)
    snapshot, blobs, _ = theme_facts(project)
    directory = child(state, "snapshots/" + snapshot["themeRevision"])
    snapshot_path = directory / "theme-snapshot.json"
    if not directory.exists():
        payload = {"inputs/" + name: data for name, data in blobs.items()}
        payload["generation-brief.md"] = _generation_brief(
            snapshot["themeRevision"]).encode("utf-8")
        payload["theme-snapshot.json"] = json_bytes(snapshot)
        directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        publish_staged_directory(state, project, "snapshot",
                                 lambda staged: payload, directory,
                                 operation_id=operation_id)
    load_snapshot(project, snapshot_path)
    brief_path = directory / "generation-brief.md"
    try:
        brief_text = read(brief_path).decode("utf-8")
    except (PetError, UnicodeError) as exc:
        raise PetError("source-conflict",
                       f"生成任务说明无法读取核验，留待核对：{brief_path}") from exc
    require(bool(brief_text.strip()) and snapshot["themeRevision"] in brief_text,
            f"生成任务说明与快照修订对不上，留待核对：{brief_path}", "source-conflict")
    return {"status": "generation-required", "themeRevision": snapshot["themeRevision"],
            "snapshot": str(snapshot_path), "brief": str(brief_path),
            "next": GENERATION_NEXT_STEP}


def package_run(project, run, snapshot_path, operation_id=None):
    """Audit one reviewed run and publish it as the selected candidate.

    When the content-addressed destination already exists it is only reused
    after byte-level identity with this run's evidence is proven; legacy or
    unbound siblings are preserved for review instead of pruned.
    """
    state = state_dir(project, True)
    recover_package_stage(state, project, operation_id=operation_id)
    audited_run = validate_run(project, run, snapshot_path)
    facts = audited_run["facts"]
    revision_value = audited_run["snapshot"]["themeRevision"]
    packages = child(state, "packages")
    packages.mkdir(exist_ok=True, mode=0o700)
    name = revision_value + "-" + facts["atlasSHA256"]
    destination = child(packages, name)
    selection_path = child(state, "selection.json")
    previous = selected_package(project) if selection_path.exists() else None
    published_new = False
    if not destination.exists():
        staged_receipt = {}

        def build_package_payload(staged):
            identity = staged.lstat()
            receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
                       "themeRevision": revision_value,
                       "atlasSHA256": facts["atlasSHA256"],
                       "manifestSHA256": sha(json_bytes(native_manifest(
                           audited_run["config"]))),
                       "snapshotSHA256": sha(audited_run["snapshotRaw"]),
                       "qaSHA256": audited_run["qaHashes"],
                       "directoryIdentity": {"device": identity.st_dev,
                                             "inode": identity.st_ino}}
            staged_receipt.update(receipt)
            return {"pet.json": json_bytes(native_manifest(audited_run["config"])),
                    "spritesheet.webp": audited_run["atlas"],
                    "theme-snapshot.json": audited_run["snapshotRaw"],
                    **audited_run["qaRaw"],
                    "package-receipt.json": json_bytes(receipt)}

        def audit_staged_package(staged):
            check_package(staged, project)
            require(package_directory_matches(staged, staged_receipt),
                    "候选暂存目录的身份在审计后发生变动", "source-conflict")

        publish_staged_directory(state, project, "package", build_package_payload,
                                 destination, operation_id=operation_id,
                                 after_materialize=audit_staged_package)
        published_new = True

    def recheck_published_candidate():
        selected_facts, selected_receipt = check_package(destination, project)
        content_named = (selected_facts["themeRevision"] == revision_value
                         and selected_facts["atlasSHA256"] == facts["atlasSHA256"])
        require(content_named, "候选目录的实际内容与其名称推导的摘要不一致，留待核对",
                "source-conflict")
        bound_or_legacy = (package_directory_matches(destination, selected_receipt)
                           or (not published_new and destination == previous
                               and "directoryIdentity" not in selected_receipt))
        require(bound_or_legacy, "候选目录没有可用的当前 inode 绑定，留待核对",
                "source-conflict")
        evidence_same = (selected_receipt.get("qaSHA256") == audited_run["qaHashes"]
                         and selected_receipt.get("snapshotSHA256")
                         == sha(audited_run["snapshotRaw"])
                         and selected_receipt.get("manifestSHA256")
                         == sha(json_bytes(native_manifest(audited_run["config"]))))
        require(evidence_same, "同名候选内的审阅或快照字节与本次运行不同，留待核对",
                "source-conflict")

    recheck_published_candidate()
    preserved = []
    for old in packages.iterdir():
        if old in (destination, previous):
            continue
        plan = capture_removal_plan(old, stage_file_names("package"))
        old_facts, old_receipt = check_package(old, project, require_current=False)
        expected_name = old_facts["themeRevision"] + "-" + old_facts["atlasSHA256"]
        provably_ours = (old.name == expected_name
                         and package_directory_matches(old, old_receipt))
        if not provably_ours:
            preserved.append(str(old))
            continue
        remove_tree(old, plan)
    recheck_published_candidate()
    atomic_json(selection_path, {"package": name, "themeRevision": revision_value,
                                 "atlasSHA256": facts["atlasSHA256"]})
    result = {"status": "packaged",
              "source": {"themeRevision": revision_value, "status": "reviewed"},
              "package": {"path": str(destination), **facts},
              "installed": "unchanged", "runtime": RUNTIME}
    if preserved:
        result["preservedUnverifiedPackages"] = sorted(preserved)
    return result


# ---------------------------------------------------------------------------
# Install transaction: staged swap inside CODEX_HOME with bounded recovery.
# ---------------------------------------------------------------------------

def installed_facts(target, project):
    """Audit the installed directory and tie every byte to its receipt."""
    require(target.is_dir() and not target.is_symlink(), "安装目标不是普通目录",
            "unknown-target")
    require(package_files(target) == INSTALL_ENTRIES,
            "同名 pet 的文件集合缺失或含未知项，不予覆盖", "unknown-target")
    receipt = parse(read(target / ".azhou-pet-receipt.json"))
    ownership(receipt, project)
    require(is_hex_digest(receipt.get("themeRevision")),
            "已安装 receipt 的主题摘要不合法，留待核对", "unknown-target")
    manifest_raw = read(target / "pet.json")
    manifest = parse(manifest_raw)
    manifest_ok = (isinstance(manifest, dict) and manifest.get("id") == PET_ID
                   and manifest.get("spriteVersionNumber") == 2
                   and manifest.get("spritesheetPath") == "spritesheet.webp")
    require(manifest_ok, "已安装的 manifest 不满足最低字段约定", "unknown-target")
    facts = inspect_atlas(read(target / "spritesheet.webp"), require_webp=True)
    receipt_ok = (receipt.get("atlasSHA256") == facts["atlasSHA256"]
                  and receipt.get("manifestSHA256") == sha(manifest_raw))
    require(receipt_ok, "已安装内容存在 receipt 未记录的改动，不予覆盖",
            "unknown-target")
    return {"path": str(target), "themeRevision": receipt["themeRevision"],
            "manifestSHA256": sha(manifest_raw), **facts}


def installs_match(left, right):
    """Two installation views agree on every byte-derived identity."""
    return all(left.get(key) == right.get(key) for key in INSTALL_IDENTITY_KEYS)


def previous_root_from_record(record, project):
    """Resolve the recorded previous project root for handoff recovery."""
    raw = record.get("previousProjectRoot")
    if raw is None:
        return project
    require(isinstance(raw, str), "事务日志记录的旧项目路径不是字符串",
            "recovery-required")
    require(record.get("hadPrevious") is True, "事务日志记录的旧项目身份无效",
            "recovery-required")
    recorded = Path(raw)
    require(recorded.is_absolute() and os.path.normpath(raw) == raw
            and raw != str(project),
            "事务日志记录的旧项目路径不满足绝对且无别名的形式", "recovery-required")
    require(not recorded.is_symlink() and recorded.resolve() == recorded,
            "旧项目路径经过符号链接或存在别名形式", "recovery-required")
    return recorded


def journal_path(pets):
    """Durable install-transaction journal inside the pets directory."""
    return child(pets, f".{PET_ID}.transaction.json")


def _validated_transaction(pets, project):
    """Read and fully validate the install journal; never touch target/stage."""
    journal = journal_path(pets)
    if not journal.exists():
        return None
    record = parse(read(journal))
    ownership(record, project)
    phase_known = record.get("phase") in TRANSACTION_PHASES
    require(phase_known and isinstance(record.get("hadPrevious"), bool),
            "安装事务日志的 phase 或 hadPrevious 不合法，留待核对", "recovery-required")
    require(all(is_hex_digest(record.get(key)) for key in CANDIDATE_DIGEST_KEYS),
            "安装事务日志没有完整的候选三元摘要，留待核对", "recovery-required")
    if record["hadPrevious"]:
        require(all(is_hex_digest(record.get(key)) for key in PREVIOUS_DIGEST_KEYS),
                "安装事务日志没有完整的旧安装三元摘要，留待核对", "recovery-required")
    else:
        require(all(record.get(key) is None for key in PREVIOUS_DIGEST_KEYS),
                "无旧安装的事务日志却携带旧安装摘要，留待核对", "recovery-required")
    previous_root = previous_root_from_record(record, project)
    if previous_root != project:
        require(all(is_hex_digest(record.get(key)) for key in PREVIOUS_DIGEST_KEYS),
                "接管场景的事务日志缺少旧安装摘要", "recovery-required")
    require(record.get("stagingLocation") == "codex-home",
            "未知的历史暂存布局无法推断恢复位置，需人工核对", "recovery-required")
    token = record.get("transaction", "")
    token_ok = (isinstance(token, str) and len(token) == 32
                and all(char in "0123456789abcdef" for char in token))
    require(token_ok, "事务日志的 transaction 标识不合法", "recovery-required")
    return record, previous_root, token


def recover_install(pets, project):
    """Drive one journalled install transaction to a provable endpoint.

    The decision phase observes target, backup and stage without touching
    them and produces an ordered repair plan; execution re-checks the stage
    before every step. Any surprise aborts with the journal still in place.
    """
    opened = _validated_transaction(pets, project)
    if opened is None:
        return None
    record, previous_root, token = opened
    target = child(pets, PET_ID)
    # pets/ is enumerated by the host, so every transaction directory (stage,
    # backup) lives beside pets/ rather than inside it.
    stage = child(pets.parent, f".{PET_ID}.stage-{token}")
    backup = child(pets.parent, f".{PET_ID}.previous-{token}")
    candidate = tuple(record[key] for key in CANDIDATE_DIGEST_KEYS)
    previous = tuple(record.get(key) for key in PREVIOUS_DIGEST_KEYS)

    def expect_installation(actual, identity, message):
        expected = dict(zip(("atlasSHA256", "themeRevision", "manifestSHA256"),
                            identity))
        require(installs_match(actual, expected), message, "recovery-required")

    def expect_candidate(path, message):
        expect_installation(installed_facts(path, project), candidate, message)

    def expect_previous(path, message):
        expect_installation(installed_facts(path, previous_root), previous, message)

    stage_present = stage.exists()
    if stage_present:
        verify_stage_for_cleanup(stage, record, {"install"})

    def stage_quiet_or_verified():
        if not stage_present:
            require(not stage.exists() and not stage.is_symlink(),
                    "恢复过程中冒出了未知暂存目录，留待核对", "recovery-required")
            return
        verify_stage_for_cleanup(stage, record, {"install"})

    committed = record.get("phase") == "committed"
    repairs = []
    if committed:
        expect_candidate(target, "已提交的安装目标与候选摘要不符")
        if backup.exists():
            require(record["hadPrevious"], "无旧安装的事务却出现旧副本目录",
                    "recovery-required")
            plan = capture_removal_plan(backup, stage_file_names("install"))
            expect_previous(backup, "旧副本的安装摘要与记录不符")
            repairs.append(("remove", backup, plan))
        outcome = OUTCOME_COMMITTED
    elif backup.exists():
        require(record["hadPrevious"], "无旧安装的事务却出现旧副本目录",
                "recovery-required")
        expect_previous(backup, "备份中的旧安装摘要与记录不符")
        if target.exists():
            plan = capture_removal_plan(target, stage_file_names("install"))
            expect_candidate(target, "安装目标并不匹配本事务的候选")
            repairs.append(("remove", target, plan))
        repairs.append(("move", backup, target))
        outcome = OUTCOME_RESTORED_PREVIOUS
    else:
        if target.exists() and record.get("hadPrevious") and previous_root != project:
            expect_previous(target, "旧包不在备份位置，且正式目标已非旧内容")
        elif target.exists():
            plan = (capture_removal_plan(target, stage_file_names("install"))
                    if not record.get("hadPrevious") else None)
            actual = installed_facts(target, project)
            if record.get("hadPrevious"):
                expect_installation(actual, previous, "旧包不在备份位置，且正式目标已非旧内容")
            else:
                expect_installation(actual, candidate, "安装目标并不匹配本事务的候选")
                repairs.append(("remove", target, plan))
        elif record.get("hadPrevious"):
            raise PetError("recovery-required",
                           "正式目标与旧包均缺失，无法证明可恢复到任何已知状态")
        outcome = OUTCOME_RESTORED_EMPTY

    for action, source, destination in repairs:
        stage_quiet_or_verified()
        if action == "remove":
            remove_tree(source, destination)
        else:
            rename_exclusive(source, destination)
    stage_quiet_or_verified()
    if stage_present:
        discard_bound_stage(stage, record, {"install"})
    fsync_dir(pets.parent)
    journal_path(pets).unlink()
    fsync_dir(pets)
    return outcome


def _classify_install_target(project, target, facts, previous_project,
                             expected_previous):
    """Decide what currently occupies the install target.

    Returns ("absent", None), ("present", previous_facts) or
    ("handed-off", current_facts) when the target already is this Hub's
    exact candidate under a takeover.
    """
    if not target.exists():
        require(previous_project is None, "接管要求旧项目安装仍存在，但目标缺失",
                "unknown-target")
        return "absent", None
    if previous_project is None:
        return "present", installed_facts(target, project)
    try:
        current = installed_facts(target, project)
    except PetError:
        current = None
    if current is not None and installs_match(current, facts):
        return "handed-off", current
    require(expected_previous is not None,
            "旧项目已无法访问，且现有安装不能证明归属本 Hub", "unknown-target")
    previous = installed_facts(target, previous_project)
    require(installs_match(previous, expected_previous),
            "现有安装与旧项目当前候选不一致，不予接管", "unknown-target")
    return "present", previous


def _swap_installation(project, directory, facts, home, pets, previous,
                       previous_project):
    """Materialize, swap and commit one installation.

    Returns (installed_facts, failure_message, converged_outcome); a normal
    commit yields (facts, None, None). Failures converge through
    `recover_install` and surface as `install-failed` when the pre-install
    state is restored, or as a converged commit when only cleanup lagged.
    """
    target = child(pets, PET_ID)
    transaction = uuid.uuid4().hex
    stage = child(home, f".{PET_ID}.stage-{transaction}")
    backup = child(home, f".{PET_ID}.previous-{transaction}")
    manifest_raw = read(directory / "pet.json")
    atlas = read(directory / "spritesheet.webp")
    require(sha(manifest_raw) == facts["manifestSHA256"]
            and sha(atlas) == facts["atlasSHA256"],
            "候选包字节在安装开始前发生变动", "source-conflict")
    receipt = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
               "themeRevision": facts["themeRevision"],
               "atlasSHA256": facts["atlasSHA256"],
               "manifestSHA256": facts["manifestSHA256"]}
    payload = {"pet.json": manifest_raw, "spritesheet.webp": atlas,
               ".azhou-pet-receipt.json": json_bytes(receipt)}
    journal = {"owner": OWNER, "projectRoot": str(project), "petId": PET_ID,
               "transaction": transaction, "stagingLocation": "codex-home",
               "phase": "prepared", "stageKind": "install",
               "hadPrevious": previous is not None}
    journal["stageFiles"] = freeze_stage_payload("install", payload)
    journal["candidateAtlasSHA256"] = facts["atlasSHA256"]
    journal["candidateThemeRevision"] = facts["themeRevision"]
    journal["candidateManifestSHA256"] = facts["manifestSHA256"]
    for long_key, short_key in zip(PREVIOUS_DIGEST_KEYS, INSTALL_IDENTITY_KEYS):
        journal[long_key] = previous[short_key] if previous else None
    if previous_project is not None:
        journal["previousProjectRoot"] = str(previous_project)
        journal["previousThemeRevision"] = previous["themeRevision"]
        journal["previousManifestSHA256"] = previous["manifestSHA256"]
    journal_file = journal_path(pets)
    atomic_json(journal_file, journal)
    try:
        stage.mkdir(mode=0o700)
        binding = stage_journal(project, stage, "install", payload, None)
        journal["stageIdentity"] = binding["stageIdentity"]
        atomic_json(journal_file, journal)
        for name, blob in payload.items():
            write_new(child(stage, name), blob)
        installed_facts(stage, project)
        # One last theme check: the swap below must not publish a candidate
        # whose display inputs already drifted.
        require(theme_facts(project)[0]["themeRevision"] == facts["themeRevision"],
                "交换前主题输入发生变动", "source-conflict")
        assert_stage_binding(stage, journal)
        fsync_dir(stage)
        fsync_dir(home)
        assert_stage_binding(stage, journal)
        if previous:
            current_target = installed_facts(target, previous_project or project)
            require(installs_match(current_target, previous),
                    "安装目标在复核后被改动", "source-conflict")
            rename_exclusive(target, backup)
            fsync_dir(pets)
            fsync_dir(home)
        assert_stage_binding(stage, journal)
        rename_exclusive(stage, target)
        fsync_dir(pets)
        fsync_dir(home)
        actual = installed_facts(target, project)
        require(installs_match(actual, facts), "交换完成后目标内容与候选不匹配",
                "source-conflict")
        require(theme_facts(project)[0]["themeRevision"] == facts["themeRevision"],
                "交换过程中主题输入发生变动", "source-conflict")
        journal["phase"] = "committed"
        atomic_json(journal_file, journal)
        recover_install(pets, project)  # journal says committed: let recovery drop the old copy
        return actual, None, None
    except Exception as failure:
        try:
            outcome = recover_install(pets, project)
        except Exception as restore_failure:
            raise PetError("recovery-required",
                           f"安装中止：{failure}；恢复也未能完成：{restore_failure}") from failure
        if outcome == OUTCOME_COMMITTED:
            return installed_facts(target, project), str(failure), outcome
        raise PetError("install-failed",
                       f"安装中止：{failure}；已收敛到恢复端点：{outcome}") from failure


def install_package(project, codex_home, *, previous_project=None,
                    expected_previous=None):
    """Install the selected candidate into CODEX_HOME as one transaction."""
    if expected_previous is not None:
        require(previous_project is not None,
                "接管时旧项目路径与已验证的候选摘要必须成对提供")
    if previous_project is not None and expected_previous is None:
        require(not Path(previous_project).exists(),
                "旧项目目录仍在时，必须核验其当前候选摘要")
    directory, facts, _ = verified_selected_package(project)
    if previous_project is not None and expected_previous is not None:
        require(installs_match(facts, expected_previous),
                "Hub 的当前候选与旧项目已安装候选不同，不予接管", "source-conflict")
    home = anchored_root(codex_home)
    pets = child(home, "pets")
    pets.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(pets.stat().st_dev == home.stat().st_dev,
            "pets 需与 CODEX_HOME 同处一个文件系统，安装目录才能安全交换")
    with lock(child(pets, f".{PET_ID}.lock")):
        return _complete_install(project, directory, facts, home, pets,
                                 previous_project, expected_previous)


def _complete_install(project, directory, facts, home, pets, previous_project,
                      expected_previous):
    """Idempotent install body running under the installation lock."""
    recovery = recover_install(pets, project)
    target = child(pets, PET_ID)
    mode, observed = _classify_install_target(project, target, facts,
                                              previous_project, expected_previous)
    if mode == "handed-off":
        return {"status": "already-handed-off", "source": facts["themeRevision"],
                "package": str(directory), "installed": observed,
                "runtime": RUNTIME, "recovery": recovery}
    previous = observed
    if (previous_project is None and previous
            and all(previous[key] == facts[key]
                    for key in ("atlasSHA256", "themeRevision"))):
        require(installs_match(previous, facts),
                "图集与主题相同的已安装版本 manifest 却不同，留待核对",
                "source-conflict")
        return {"status": "already-installed", "source": facts["themeRevision"],
                "package": str(directory), "installed": previous,
                "runtime": RUNTIME, "recovery": recovery}
    actual, failure, converged = _swap_installation(
        project, directory, facts, home, pets, previous, previous_project)
    if converged == OUTCOME_COMMITTED:
        return {"status": "installed-with-recovery", "warning": failure,
                "source": facts["themeRevision"], "package": str(directory),
                "installed": actual, "runtime": RUNTIME, "recovery": converged}
    return {"status": "handed-off" if previous_project is not None else "installed",
            "source": {"themeRevision": facts["themeRevision"], "status": "matched"},
            "package": {"path": str(directory), **facts}, "installed": actual,
            "runtime": RUNTIME,
            "next": "安装目录已就绪；刷新或重开 pet 选择界面即可选用阿舟，宿主进程不由本工具重启或改动",
            "recovery": recovery}


def handoff_package(project, previous_project, codex_home):
    """Move an installation's ownership from an old checkout to this Hub.

    Both candidate selections are frozen under their own project locks
    before the shared installation lock is taken, so a content change can
    never ride along with a pure ownership move.
    """
    project = anchored_root(project)
    raw_previous = Path(previous_project).expanduser()
    require(raw_previous.is_absolute(), "--previous-project-root 需要给出绝对路径")
    require(not raw_previous.is_symlink(),
            f"旧项目目录不能是符号链接：{raw_previous}", "unknown-target")
    previous_root = anchored_root(raw_previous)
    require(raw_previous == previous_root, "旧项目路径存在别名形式，拒绝",
            "unknown-target")
    require(previous_root != project, "旧项目目录与 Hub 项目目录必须不同")
    hub_state = state_dir(project, True)
    if previous_root.is_dir():
        old_state = state_dir(previous_root)
        require(old_state.is_dir() and not old_state.is_symlink(),
                "旧项目没有可验证的 Pet 状态目录，无法证明安装来源", "unknown-target")
        # Acquire the retiring checkout's lock first, then ours, so both
        # selections stay frozen before the shared install lock appears.
        with lock(child(old_state, "project.lock")):
            with lock(child(hub_state, "project.lock")):
                _, old_facts, _ = verified_selected_package(previous_root)
                _, new_facts, _ = verified_selected_package(project)
                require(installs_match(old_facts, new_facts),
                        "两侧候选未完全一致，不允许借接管夹带内容变更",
                        "source-conflict")
                return install_package(project, codex_home,
                                       previous_project=previous_root,
                                       expected_previous=old_facts)
    # A finished handoff may have deleted the retiring checkout entirely;
    # proceeding without it is sound only while the installed bytes still
    # equal this Hub's candidate.
    with lock(child(hub_state, "project.lock")):
        return install_package(project, codex_home, previous_project=previous_root)


# ---------------------------------------------------------------------------
# Observation and CLI entry.
# ---------------------------------------------------------------------------

def resume_transactions(project, codex_home):
    """Replay every interrupted transaction for this project."""
    state = state_dir(project, True)
    recover_package_stage(state, project)
    pets = child(anchored_root(codex_home), "pets")
    outcome = None
    if pets.exists():
        with lock(child(pets, f".{PET_ID}.lock")):
            outcome = recover_install(pets, project)
    label = "recovered" if outcome else "no-install-transaction"
    return {"status": label, "recovery": outcome,
            "states": status(project, codex_home), "runtime": RUNTIME}


def status(project, codex_home):
    """Observe source, selection, transaction and installation; read-only."""
    report = {"status": "status", "runtime": RUNTIME}
    try:
        current, _, _ = theme_facts(project)
        report["source"] = current
    except (PetError, OSError) as exc:
        report["source"] = {"status": "invalid", "error": str(exc)}
    try:
        directory, facts, _ = verified_selected_package(project, require_current=False)
        fresh = facts["themeRevision"] == report["source"].get("themeRevision")
        report["package"] = {"status": "verified" if fresh else "stale-theme",
                             "path": str(directory), **facts}
    except (PetError, OSError) as exc:
        report["package"] = {"status": getattr(exc, "code", "unavailable"),
                             "error": str(exc)}
    pets = child(anchored_root(codex_home), "pets")
    target = child(pets, PET_ID)
    if journal_path(pets).exists():
        report["transaction"] = {"status": "recovery-required",
                                 "journal": str(journal_path(pets))}
    if not target.exists():
        report["installed"] = {"status": "absent"}
        return report
    try:
        facts = installed_facts(target, project)
        theme_fresh = facts["themeRevision"] == report["source"].get("themeRevision")
        chosen = report["package"]
        package_match = (installs_match(facts, chosen)
                         if "atlasSHA256" in chosen else None)
        if not theme_fresh:
            label = "stale-theme"
        elif package_match is False:
            label = "stale-package"
        elif package_match:
            label = "verified"
        else:
            label = "verified-unselected"
        report["installed"] = {"status": label, "bytesVerified": True,
                               "matchesCurrentTheme": theme_fresh,
                               "matchesSelectedPackage": package_match, **facts}
    except (PetError, OSError) as exc:
        report["installed"] = {"status": getattr(exc, "code", "invalid"),
                               "error": str(exc)}
    return report


COMMANDS = ("prepare", "validate", "package", "install", "status", "sync",
            "recover", "handoff")
RUN_COMMANDS = ("validate", "package", "sync")
EXIT_CODES = {"generation-required": 3, "busy": 4, "recovery-required": 5}


def _dispatch(args, project):
    """Route one parsed command; state-mutating routes hold the project lock."""
    if args.command == "status":
        return status(project, args.codex_home)
    if args.command == "validate":
        if args.run:
            audited = validate_run(project, args.run, args.snapshot)
            headline = {"status": "validated",
                        "themeRevision": audited["snapshot"]["themeRevision"]}
            return {**headline, **audited["facts"]}
        _, facts, _ = verified_selected_package(project)
        return {"status": "validated", **facts}
    if args.command == "handoff":
        return handoff_package(project, args.previous_project_root, args.codex_home)
    state = state_dir(project, True)
    with lock(child(state, "project.lock")):
        if args.command == "prepare":
            return prepare(project)
        if args.command == "recover":
            return resume_transactions(project, args.codex_home)
        if args.command == "package":
            require(args.run, "package 命令必须同时给出 --run 与 --snapshot")
            return package_run(project, args.run, args.snapshot)
        if args.command == "sync" and args.run:
            package_run(project, args.run, args.snapshot)
        if args.command == "sync" and not child(state, "selection.json").exists():
            raise PetError("generation-required",
                           "当前没有任何已审阅候选；请先 prepare，再用 ImageGen/hatch-pet 生成并审阅")
        return install_package(project, args.codex_home)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default_home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--project-root",
                        default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--codex-home", default=default_home)
    parser.add_argument("--previous-project-root",
                        help="移交来源的旧项目根目录（仅 handoff 使用，需绝对路径）")
    parser.add_argument("--run", help="待复核的生成 run 目录")
    parser.add_argument("--snapshot", help="prepare 输出的 theme-snapshot 文件")
    args = parser.parse_args(argv)
    project = None
    try:
        project = anchored_root(args.project_root)
        require(project.is_dir(), "项目目录不存在或不可用")
        pairing = (args.command == "handoff") == bool(args.previous_project_root)
        require(pairing, "--previous-project-root 仅且必须在 handoff 时提供")
        require(bool(args.run) == bool(args.snapshot), "--run 与 --snapshot 必须同时提供")
        require(args.command in RUN_COMMANDS or not args.run,
                "--run/--snapshot 只对 validate、package、sync 三个命令有效")
        result = _dispatch(args, project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PetError, OSError, ValueError, KeyError, TypeError) as exc:
        code = getattr(exc, "code", "invalid")
        output = {"status": code, "error": str(exc), "runtime": RUNTIME}
        if project is not None:
            try:
                output["states"] = status(project, args.codex_home)
            except Exception as state_failure:
                output["states"] = {"status": "unverified",
                                    "error": str(state_failure), "runtime": RUNTIME}
        if code == "generation-required":
            output["next"] = GENERATION_GUIDE
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return EXIT_CODES.get(code, 2)


if __name__ == "__main__":
    raise SystemExit(main())

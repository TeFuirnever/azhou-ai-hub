"""Verify the fixed local optional video input without installing or probing codecs."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable

MANIFEST_NAME = "startup-video.json"
CLIP_NAME = "startup-video.mp4"
MAX_MANIFEST_BYTES = 4096
MAX_CLIP_BYTES = 64 * 1024 * 1024
MAX_TIMELINE_MS = 60_000
SHA256 = re.compile(r"[0-9a-f]{64}")
FIELDS = {"schema", "clipSHA256", "byteLength", "holdMs", "fadeStartMs", "fadeEndMs"}


class StartupVideoInputError(ValueError):
    """The explicit optional input cannot be bound to approved bytes."""


@dataclass(frozen=True)
class ApprovedStartupVideo:
    manifest_sha256: str
    clip_sha256: str
    manifest_bytes: bytes
    clip_bytes: bytes
    hold_ms: int
    fade_start_ms: int
    fade_end_ms: int


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise StartupVideoInputError("expected a lowercase SHA-256 digest")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise StartupVideoInputError("duplicate startup video manifest field")
    return result


def _check_manifest(raw: bytes) -> tuple[str, int, int, int, int]:
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StartupVideoInputError("invalid startup video manifest JSON") from exc
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise StartupVideoInputError("unsupported startup video manifest fields")
    names = ("schema", "byteLength", "holdMs", "fadeStartMs", "fadeEndMs")
    if any(type(obj[name]) is not int for name in names):
        raise StartupVideoInputError("startup video manifest requires integer schema, size and times")
    schema, length, hold, start, end = (obj[name] for name in names)
    if schema != 1 or not 0 < length <= MAX_CLIP_BYTES or not 0 < hold < start < end <= MAX_TIMELINE_MS:
        raise StartupVideoInputError("unsupported startup video schema, size or timeline")
    return _require_digest(obj["clipSHA256"]), length, hold, start, end


def verify_approved_startup_video(
    expected_manifest_sha256: str | None,
    read_file: Callable[[str, int], bytes],
) -> ApprovedStartupVideo | None:
    """Return immutable bytes for staging, never a mutable source path."""
    if expected_manifest_sha256 is None:
        return None
    manifest_pin = _require_digest(expected_manifest_sha256)
    raw = bytes(read_file(MANIFEST_NAME, MAX_MANIFEST_BYTES))
    if not 0 < len(raw) <= MAX_MANIFEST_BYTES or hashlib.sha256(raw).hexdigest() != manifest_pin:
        raise StartupVideoInputError("startup video manifest digest or size mismatch")
    clip_pin, length, hold, start, end = _check_manifest(raw)
    clip = bytes(read_file(CLIP_NAME, length))
    if len(clip) != length:
        raise StartupVideoInputError("startup video clip length mismatch")
    if hashlib.sha256(clip).hexdigest() != clip_pin:
        raise StartupVideoInputError("startup video clip digest mismatch")
    return ApprovedStartupVideo(manifest_pin, clip_pin, raw, clip, hold, start, end)


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode


def _file_stamp(info: os.stat_result) -> tuple[int, ...]:
    return (*_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_at(directory: int, name: str, limit: int) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open(name, flags, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        initial = os.fstat(fd)
        if not stat.S_ISREG(initial.st_mode) or not 0 < initial.st_size <= limit:
            raise StartupVideoInputError(f"{name} is not a bounded regular file")
        data = stream.read(limit + 1)
        current = os.fstat(fd)
        named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if (len(data) != initial.st_size or _file_stamp(initial) != _file_stamp(current)
                or _file_stamp(initial) != _file_stamp(named)):
            raise StartupVideoInputError(f"{name} changed during verification")
        return data


def read_approved_startup_video(
    package_root: Path, expected_manifest_sha256: str | None,
) -> ApprovedStartupVideo | None:
    """Read only fixed inputs below the Git-ignored private directory."""
    if expected_manifest_sha256 is None:
        return None
    pin = _require_digest(expected_manifest_sha256)
    if (not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"))
            or not {os.open, os.stat}.issubset(os.supports_dir_fd)
            or os.stat not in os.supports_follow_symlinks):
        raise StartupVideoInputError("safe optional startup video input is unavailable on this platform")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        with ExitStack() as stack:
            def open_dir(name: Path | str, parent: int | None = None) -> int:
                fd = os.open(name, flags, dir_fd=parent)
                stack.callback(os.close, fd)
                return fd
            root = open_dir(package_root)
            assets = open_dir("assets", root)
            private = open_dir("private", assets)
            result = verify_approved_startup_video(pin, lambda name, limit: _read_at(private, name, limit))
            if any(_identity(os.fstat(fd)) != _identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
                   for fd, name, parent in ((root, package_root, None), (assets, "assets", root),
                                             (private, "private", assets))):
                raise StartupVideoInputError("optional video input directory changed during verification")
            return result
    except OSError as exc:
        raise StartupVideoInputError("unsafe or unavailable local startup video input") from exc

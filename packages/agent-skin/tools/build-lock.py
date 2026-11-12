#!/usr/bin/env python3
"""Serialize cooperating builds in this checkout; never remove an existing lock file."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build'
LOCK = BUILD / '.agent-skin-build.lock'
ENV_KEY = '_AZHOU_BUILD_LOCK_FD'


def checked_lock_file(fd):
    if BUILD.is_symlink() or not BUILD.is_dir() or LOCK.is_symlink():
        raise RuntimeError('构建锁路径不是实体目录或文件，保留未处理。')
    opened = os.fstat(fd)
    current = os.stat(LOCK, follow_symlinks=False)
    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
        raise RuntimeError('构建锁身份发生变化，保留未处理。')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError('另一个构建正在运行，请稍后重试。') from exc


@contextlib.contextmanager
def acquired():
    if BUILD.is_symlink():
        raise RuntimeError('拒绝通过符号链接 .build 目录构建。')
    BUILD.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(LOCK, flags, 0o600)
    try:
        checked_lock_file(fd)
        yield fd
    finally:
        os.close(fd)


def run():
    with acquired() as fd:
        env = os.environ.copy()
        env[ENV_KEY] = str(fd)
        result = subprocess.run(['/bin/bash', str(ROOT / 'tools/build-macos.sh')],
                                env=env, pass_fds=(fd,), check=False)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--run', action='store_true')
    actions.add_argument('--verify', type=int)
    args = parser.parse_args()
    try:
        if args.run:
            return run()
        checked_lock_file(args.verify)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    sys.exit(main())

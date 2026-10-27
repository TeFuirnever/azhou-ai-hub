#!/usr/bin/env python3
"""Compile and run the native startup protocol driver with fake host boundaries."""

from __future__ import annotations

import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.platform != "darwin":
        print("SKIPPED: native startup protocol tests require macOS and AppKit")
        return 0

    output = ROOT / ".build/startup-native-tests"
    output.parent.mkdir(parents=True, exist_ok=True)
    target = f"{platform.machine()}-apple-macos13.0"
    command = [
        "xcrun", "--sdk", "macosx", "swiftc", "-target", target,
        "Native/Wallpaper.swift", "Native/StartupNativeTests.swift",
        "-o", str(output), "-framework", "AppKit",
    ]
    print("==> " + " ".join(command), flush=True)
    compiled = subprocess.run(command, cwd=ROOT, check=False)
    if compiled.returncode:
        return compiled.returncode
    return subprocess.run([str(output)], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

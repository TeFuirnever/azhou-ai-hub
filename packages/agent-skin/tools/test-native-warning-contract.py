#!/usr/bin/env python3
"""Reject warnings in native production inputs; not a Swift 6 migration claim."""
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != "darwin":
    print("SKIPPED: native warning contract requires macOS")
    raise SystemExit(0)
command = ["xcrun", "--sdk", "macosx", "swiftc", "-typecheck", "-target",
           f"{platform.machine()}-apple-macos13.0", "Native/App.swift", "Native/Wallpaper.swift",
           "Native/SkinHostContract.swift", "Native/CodexSkinDriver.swift", "Native/OptionalStartupMedia.swift"]
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
# Some Swift concurrency diagnostics stay warnings even with -warnings-as-errors.
raise SystemExit(1 if result.returncode or "warning:" in result.stderr else 0)

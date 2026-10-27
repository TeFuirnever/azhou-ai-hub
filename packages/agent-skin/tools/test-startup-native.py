#!/usr/bin/env python3
"""Compile and run native startup protocol and event tests with fake host boundaries."""

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
        "xcrun", "--sdk", "macosx", "swiftc", "-DAGENT_SKIN_NATIVE_EVENT_TESTS", "-target", target,
        "Native/App.swift", "Native/Wallpaper.swift", "Native/StartupNativeTests.swift",
        "-o", str(output), "-framework", "AppKit", "-framework", "WebKit",
    ]
    print("==> " + " ".join(command), flush=True)
    compiled = subprocess.run(command, cwd=ROOT, check=False)
    if compiled.returncode:
        return compiled.returncode
    tested = subprocess.run([str(output)], cwd=ROOT, check=False)
    if tested.returncode:
        return tested.returncode

    emitted = subprocess.run(
        [str(output), "--emit-helper-expressions"], cwd=ROOT,
        check=False, capture_output=True, text=True,
    )
    if emitted.returncode:
        print(emitted.stderr, file=sys.stderr, end="")
        return emitted.returncode
    try:
        import json

        expressions = json.loads(emitted.stdout)
        expected = {"statusSource", "applyGuardSource", "restoreSource"}
        if set(expressions) != expected or not all(isinstance(expressions[key], str) and expressions[key] for key in expected):
            raise ValueError("native helper expression output has an unexpected shape")
    except (ValueError, TypeError) as error:
        print(f"FAILED: native helper expression output is invalid: {error}", file=sys.stderr)
        return 1
    receipt = ROOT / ".build/startup-helper-expressions.json"
    receipt.write_text(json.dumps(expressions, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Native helper expressions emitted for isolated browser checks: {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the macOS native unit suites and export LLVM line coverage."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_SOURCES = (
    "Native/App.swift",
    "Native/Wallpaper.swift",
    "Native/InstallRegistry.swift",
    "Native/InstallRegistryCore.swift",
    "tools/build-startup-assets.swift",
)


def run(command: list[str], *, cwd: Path, log: Path, env: dict[str, str] | None = None,
        expected: int = 0) -> subprocess.CompletedProcess[str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    print("==> " + " ".join(command), flush=True)
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode != expected:
        excerpt = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            f"command exited {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"log: {log}\n{excerpt}"
        )
    return result


def compile_binary(out: Path, name: str, sources: list[str], *, frameworks: list[str] = (),
                   defines: list[str] = ()) -> Path:
    binary = out / "bin" / name
    binary.parent.mkdir(parents=True, exist_ok=True)
    command = ["xcrun", "--sdk", "macosx", "swiftc", "-profile-generate",
               "-profile-coverage-mapping", "-target", f"{platform.machine()}-apple-macos13.0"]
    command.extend(f"-D{define}" for define in defines)
    command.extend(sources)
    command.extend(["-o", str(binary)])
    for framework in frameworks:
        command.extend(["-framework", framework])
    run(command, cwd=ROOT, log=out / "logs" / f"compile-{name}.log")
    return binary


def png(path: Path, width: int, height: int, pixel) -> None:
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(pixel(x, y))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    encoded = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
               + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def asset_builder_checks(out: Path, profraw: Path) -> Path:
    binary = compile_binary(
        out, "build-startup-assets",
        ["tools/build-startup-assets.swift"],
        frameworks=["CoreGraphics", "ImageIO", "UniformTypeIdentifiers", "Vision"],
    )
    environment = os.environ.copy()
    environment["LLVM_PROFILE_FILE"] = str(profraw / "assets-%p.profraw")
    run([str(binary)], cwd=ROOT, log=out / "logs" / "assets-usage.log", env=environment, expected=1)

    assets = out / "fixtures" / "asset-builder"
    working = assets / "working.png"
    wallpaper = assets / "wallpaper.png"
    # Two deterministic high-contrast shapes produce Vision contours while
    # exercising both center-cover crop branches.
    png(working, 96, 48, lambda x, y: (240, 40, 30, 255) if 24 <= x < 72 and 8 <= y < 40
        else (18, 22, 30, 255))
    png(wallpaper, 48, 96, lambda x, y: (245, 245, 245, 255) if 10 <= x < 38 and 30 <= y < 66
        else (20, 24, 34, 255))
    output = assets / "output"
    output.mkdir(parents=True, exist_ok=True)
    command = [str(binary), str(working), str(wallpaper), str(output / "avatar.png"),
               str(output / "artwork.png"), str(output / "contours.json")]
    run(command, cwd=ROOT, log=out / "logs" / "assets-success.log", env=environment)
    contours = json.loads((output / "contours.json").read_text(encoding="utf-8"))
    if not contours or not (output / "avatar.png").is_file() or not (output / "artwork.png").is_file():
        raise RuntimeError("asset builder did not produce both PNGs and a nonempty contour set")

    invalid = run(
        [str(binary), str(assets / "missing.png"), str(wallpaper), str(output / "bad-avatar.png"),
         str(output / "bad-artwork.png"), str(output / "bad-contours.json")],
        cwd=ROOT, log=out / "logs" / "assets-invalid-input.log", env=environment, expected=1,
    )
    _ = invalid

    blocked = assets / "blocked-avatar.png"
    blocked.mkdir(parents=True, exist_ok=True)
    run(
        [str(binary), str(working), str(wallpaper), str(blocked), str(output / "blocked-artwork.png"),
         str(output / "blocked-contours.json")],
        cwd=ROOT, log=out / "logs" / "assets-output-error.log", env=environment, expected=1,
    )
    return binary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        print("FAILED: Swift native coverage requires macOS and Xcode Command Line Tools", file=sys.stderr)
        return 2

    out = args.out.resolve()
    raw_dir = out / "profraw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    # Profiles belong to one fresh unit run. A removed test must not keep its
    # old hits, and a failed compilation must not leave a passing report.
    for previous in raw_dir.glob("*.profraw"):
        previous.unlink()
    (out / "coverage.json").unlink(missing_ok=True)
    objects = [
        compile_binary(out, "startup-tests", ["Native/App.swift", "Native/Wallpaper.swift",
                       "Native/StartupNativeTests.swift"], frameworks=["AppKit", "WebKit"],
                      defines=["AGENT_SKIN_NATIVE_EVENT_TESTS"]),
        compile_binary(out, "wallpaper-tests", ["Native/App.swift", "Native/Wallpaper.swift",
                       "Native/WallpaperValidationTests.swift"], frameworks=["AppKit", "WebKit"],
                      defines=["AGENT_SKIN_NATIVE_EVENT_TESTS"]),
        compile_binary(out, "install-registry-tests", ["Native/InstallRegistryCore.swift",
                       "Native/InstallRegistryTests.swift"], frameworks=["CoreServices"]),
        compile_binary(out, "install-registry-cli", ["Native/InstallRegistryCore.swift",
                       "Native/InstallRegistry.swift"], frameworks=["AppKit", "CoreServices"]),
        compile_binary(out, "startup-cli", ["Native/App.swift", "Native/Wallpaper.swift"],
                       frameworks=["AppKit", "WebKit"]),
    ]
    objects.append(asset_builder_checks(out, raw_dir))

    environment = os.environ.copy()
    for name, binary in zip(["startup", "wallpaper", "registry-test", "registry-cli", "startup-cli"], objects[:5]):
        environment["LLVM_PROFILE_FILE"] = str(raw_dir / f"{name}-%p.profraw")
        if name == "startup":
            run([str(binary)], cwd=ROOT, log=out / "logs" / "startup-tests.log", env=environment)
        elif name == "wallpaper":
            run([str(binary)], cwd=ROOT, log=out / "logs" / "wallpaper-tests.log", env=environment)
        elif name == "registry-test":
            run([str(binary)], cwd=ROOT, log=out / "logs" / "registry-tests.log", env=environment)
        elif name == "registry-cli":
            # A noncanonical path exercises the production adapter entry point
            # without scanning installed applications or registering a bundle.
            run([str(binary), "register", "/tmp/agent-skin-coverage-not-a-bundle.app"], cwd=ROOT,
                log=out / "logs" / "registry-cli-refusal.log", env=environment, expected=1)
        else:
            # This rejected command enters the production main dispatcher but
            # exits before resolving a process, opening a socket, or writing a journal.
            run([str(binary), "--wallpaper-helper", "--action", "invalid"], cwd=ROOT,
                log=out / "logs" / "startup-cli-refusal.log", env=environment, expected=2)

    merge = out / "coverage.profdata"
    raw_files = sorted(str(path) for path in raw_dir.glob("*.profraw"))
    if not raw_files:
        raise RuntimeError("LLVM produced no native profile files")
    run(["xcrun", "llvm-profdata", "merge", "-sparse", *raw_files, "-o", str(merge)],
        cwd=ROOT, log=out / "logs" / "merge-profiles.log")
    export = out / "llvm-export.json"
    command = ["xcrun", "llvm-cov", "export", str(objects[0]), f"-instr-profile={merge}"]
    for binary in objects[1:]:
        command.extend(["-object", str(binary)])
    # llvm-cov export writes JSON to stdout. Capture it separately from the log.
    with export.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=ROOT, text=True, stdout=stream, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise RuntimeError(f"llvm-cov export failed: {completed.stderr}")
    value = json.loads(export.read_text(encoding="utf-8"))
    files: dict[str, dict[str, dict[str, int]]] = {}
    for data in value.get("data", []):
        for item in data.get("files", []):
            filename = Path(item["filename"]).resolve()
            try:
                relative = filename.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            lines = item.get("summary", {}).get("lines", {})
            if relative in files:
                raise RuntimeError("LLVM returned duplicate source entries; merge profiles before reporting: " + relative)
            files[relative] = {"lines": {"count": int(lines.get("count", 0)),
                                          "covered": int(lines.get("covered", 0))}}
    missing = [source for source in PRODUCTION_SOURCES if source not in files]
    if missing:
        raise RuntimeError("LLVM did not measure production Swift sources: " + ", ".join(missing))
    report = out / "coverage.json"
    report.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    totals = [files[source]["lines"] for source in PRODUCTION_SOURCES]
    count = sum(item["count"] for item in totals)
    covered = sum(item["covered"] for item in totals)
    print(f"Swift native coverage: {covered}/{count} lines ({100 * covered / count:.2f}%)")
    for source in PRODUCTION_SOURCES:
        item = files[source]["lines"]
        print(f"  {source}: {item['covered']}/{item['count']} ({100 * item['covered'] / item['count']:.2f}%)")
    print(f"Coverage report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

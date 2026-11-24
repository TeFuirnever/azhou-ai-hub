#!/usr/bin/env python3
"""Read-only installed-app checks and an explicit, non-destructive cold-start test.

No existing host is terminated. Dock, startup and wallpaper visuals require separate review.
These are functional acceptance results, never unit coverage inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import runpy
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "local.azhou.codex-startup"


def records(text: str) -> list[dict]:
    result = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def unique_installation(values: list[dict]) -> bool:
    if len(values) != 1 or values[0].get("status") != "current":
        return False
    return all(type(values[0].get(key)) is int and values[0][key] == count for key, count in (
        ("installedProjectAppCount", 1), ("distAppCount", 0), ("registeredProjectPathCount", 1)))


def verified_wallpaper(values: list[dict], *, request_id: str | None = None,
                       target: tuple[int, str] | None = None) -> bool:
    fields = ("applied", "imageDecoded", "backgroundMatched", "coverMatched", "fixedViewport",
              "rootClear", "workspaceBackgroundClear", "footerBackgroundClear", "footerFadeClear",
              "topFadeClear", "decorationEffectsClear")
    results = [value for value in values if value.get("event") == "wallpaper-result"]
    return len(results) == 1 and all(value.get("state") == "applied"
               and value.get("action") == "status"
               and type(value.get("targetPID")) is int and value["targetPID"] > 0
               and isinstance(value.get("targetPath"), str) and Path(value["targetPath"]).is_absolute()
               and isinstance(value.get("requestID"), str) and bool(value["requestID"])
               and (request_id is None or value["requestID"] == request_id)
               and (target is None or (value["targetPID"], value["targetPath"]) == target)
               and all(value.get(field) is True for field in fields)
               and value.get("verificationIssues") == [] for value in results)


def cold_start_allowed(values: list[dict]) -> bool:
    probes = [value for value in values if value.get("event") == "probe"]
    return len(probes) == 1 and probes[0].get("targetBundleID") == "com.openai.codex" \
        and isinstance(probes[0].get("targetPath"), str) and Path(probes[0]["targetPath"]).is_absolute() \
        and probes[0].get("running") == []


def native_launch_verdict(values: list[dict], expected_launcher_path: str | None, returncode: int | None = 0) -> dict | None:
    return runpy.run_path(str(Path(__file__).with_name("startup_event_verdict.py")))["assess_native_launch"](
        values, returncode, expected_launcher_path)


def cold_start_observed(values: list[dict], expected_launcher_path: str | None = None) -> bool:
    native = native_launch_verdict(values, expected_launcher_path)
    if native is not None:
        return native["status"] == "native-completed"
    events = {value.get("event") for value in values}
    exits = [value for value in values if value.get("event") == "launcher-exit"]
    return {"launcher-start", "target-opened", "startup-installed", "startup-ready"} <= events \
        and "target-activated" not in events and len(exits) == 1 \
        and exits[0].get("exitCode") == 0 and exits[0].get("outcome") == "startup-ready"


def cold_wallpaper_target(launch: list[dict], probe: list[dict],
                          expected_launcher_path: str, returncode: int | None = 0) -> tuple[int, str] | None:
    native = native_launch_verdict(launch, expected_launcher_path, returncode)
    if native is None or not cold_start_allowed(probe):
        return None
    if native["status"] != "native-completed" and not (
        native["status"] == "partial" and native["startup"]["status"] == "interrupted"
        and native["startup"]["workspace"] is not None
    ):
        return None
    # The native verdict has already verified that exactly one opened PID
    # matches the terminal receipt and exit. The path comes from the unique
    # pre-launch resolver, not from an unbound wallpaper response.
    opened = next(value for value in launch if value["event"] == "target-opened")
    selected = next(value for value in probe if value.get("event") == "probe")
    return opened["targetPID"], selected["targetPath"]


def observe_wallpaper(executable: Path, log: Path, target: tuple[int, str] | None) -> bool:
    request_id = str(uuid4())
    command = [str(executable), "--wallpaper-status", "--request-id", request_id]
    if target is not None:
        command.extend(["--target-pid", str(target[0]), "--target-bundle", target[1]])
    code, values = execute(command, log)
    return code == 0 and verified_wallpaper(values, request_id=request_id, target=target)


def dock_entries(value: dict, expected_path: Path) -> list[dict]:
    from urllib.parse import unquote, urlparse

    entries = []
    for group in ("persistent-apps", "recent-apps"):
        for item in value.get(group, []):
            data = item.get("tile-data", {})
            url = data.get("file-data", {}).get("_CFURLString", "")
            path = unquote(urlparse(url).path)
            if data.get("bundle-identifier") == BUNDLE_ID or path == str(expected_path):
                entries.append({"group": group, "label": data.get("file-label"), "path": path})
    return entries


def execute(command: list[str], log: Path, timeout: int = 40) -> tuple[int | None, list[dict]]:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        return result.returncode, records(result.stdout)
    except (OSError, subprocess.TimeoutExpired) as error:
        log.write_text(str(error) + "\n", encoding="utf-8")
        return None, []


def check(out: Path, cold_start: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    theme = json.loads((ROOT / "theme-config.json").read_text(encoding="utf-8"))
    app = Path.home() / "Applications" / theme["identity"]["installationName"]
    executable = app / "Contents/MacOS/AzhouCodexStartup"
    cases = []
    install_code, installation = execute([sys.executable, "tools/install-macos.py", "--check"], out / "installation.log")
    cases.append({"id": "FT-INSTALL", "status": "passed" if install_code == 0 and unique_installation(installation) else "failed"})
    # The real Finder API is read in the current system language. It does not
    # claim to have changed the machine language or examined Dock rendering.
    finder_probe = '''import Foundation
let app = CommandLine.arguments[1]
let languages = UserDefaults.standard.persistentDomain(forName: UserDefaults.globalDomain)?["AppleLanguages"] as? [String] ?? Locale.preferredLanguages
let chinese = languages.first?.lowercased().hasPrefix("zh") == true
let expected = CommandLine.arguments[chinese ? 2 : 3]
let actual = FileManager.default.displayName(atPath: app)
let result: [String: Any] = ["actual": actual, "expected": expected, "passed": actual == expected]
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
'''
    finder_code, finder = execute(["xcrun", "swift", "-e", finder_probe, str(app),
        theme["identity"]["appName"]["zh-CN"], theme["identity"]["appName"]["en"]], out / "finder.log")
    cases.append({"id": "FT-FINDER", "status": "passed" if finder_code == 0 and len(finder) == 1
                  and finder[0].get("passed") is True else "failed"})
    try:
        dock = plistlib.loads((Path.home() / "Library/Preferences/com.apple.dock.plist").read_bytes())
        entries = dock_entries(dock, app)
    except (OSError, ValueError, plistlib.InvalidFileException):
        entries = []
    cases.append({"id": "FT-DOCK", "status": "pending-visual-review" if entries else "pending-no-entry",
                  "entries": entries,
                  "next": "Review the actual pinned entry label after an upgrade; metadata alone is insufficient."})
    target = None
    if cold_start:
        probe_code, probe = execute([str(executable), "--probe"], out / "cold-probe.log")
        if install_code != 0 or not unique_installation(installation) or probe_code != 0 or not cold_start_allowed(probe):
            cases.append({"id": "FT-COLD", "status": "pending-human-exit",
                          "next": "Finish work, quit the official host yourself, then rerun --cold-start."})
        else:
            launch_code, launch = execute([str(executable)], out / "cold-launch.log", timeout=75)
            # Actual cold-start events and wallpaper are checked separately.
            # Hot activation caused by a race must never count as cold success.
            cold = launch_code == 0 and cold_start_observed(launch, str(app.resolve()))
            cases.append({"id": "FT-COLD", "status": "pending-visual-review" if cold else "failed",
                          "next": "Review the actual animation and workspace; preserve the event log."})
            target = cold_wallpaper_target(launch, probe, str(app.resolve()), launch_code)
            deadline = time.monotonic() + 65
            poll = 0
            while target is not None and time.monotonic() < deadline:
                poll += 1
                if observe_wallpaper(executable, out / f"wallpaper-poll-{poll:03d}.log", target):
                    break
                time.sleep(1)
    else:
        cases.append({"id": "FT-COLD", "status": "pending-not-run",
                      "next": "Rerun --cold-start only after the official host has been quit by its user."})
    wallpaper_status_verified = (not cold_start or target is not None) and observe_wallpaper(
        executable, out / "wallpaper.log", target)
    cases.append({"id": "FT-WALLPAPER",
                  "status": "pending-visual-review" if wallpaper_status_verified else "failed",
                  "runtimeStatusVerified": wallpaper_status_verified,
                  "next": ("Verify the visible wallpaper in both the regular workspace and the Dot central conversation "
                           "area of this installed candidate, including after switching away and back. "
                           "Sidebar wallpaper alone is insufficient." if wallpaper_status_verified else
                           "No verified cold-launch target to bind the wallpaper status to." if cold_start and target is None else
                           "Inspect wallpaper.log for the failed runtime status check before visual review.")})
    return {"kind": "installed-functional-acceptance", "unitCoverageInput": False,
            "cases": cases, "passed": all(case["status"] == "passed" for case in cases),
            "limitations": ["Finder API evidence does not certify an actual Dock label.",
                            "No current host is quit or restarted automatically.",
                            "Visual review is required for crop, readability and the real startup presentation."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".local/functional-acceptance")
    parser.add_argument("--cold-start", action="store_true")
    args = parser.parse_args()
    out = args.out.absolute()
    result = check(out, args.cold_start)
    target = out / "report.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "cases": result["cases"], "report": str(target)}, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

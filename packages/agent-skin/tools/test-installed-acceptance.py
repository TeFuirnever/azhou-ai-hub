#!/usr/bin/env python3
"""Read-only installed-app checks and an explicit, non-destructive cold-start test.

No existing host is terminated. Missing Dock and cold-start evidence stays pending.
These are functional acceptance results, never unit coverage inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import time

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
    return any(value.get("status") == "current"
               and value.get("installedProjectAppCount") == 1
               and value.get("distAppCount") == 0
               and value.get("registeredProjectPathCount") == 1 for value in values)


def verified_wallpaper(values: list[dict]) -> bool:
    fields = ("applied", "imageDecoded", "backgroundMatched", "coverMatched", "fixedViewport",
              "rootClear", "workspaceBackgroundClear", "footerBackgroundClear", "footerFadeClear",
              "topFadeClear", "decorationEffectsClear")
    return any(value.get("event") == "wallpaper-result" and value.get("state") == "applied"
               and all(value.get(field) is True for field in fields)
               and value.get("verificationIssues") == [] for value in values)


def cold_start_allowed(values: list[dict]) -> bool:
    probes = [value for value in values if value.get("event") == "probe"]
    return len(probes) == 1 and probes[0].get("targetBundleID") == "com.openai.codex" \
        and bool(probes[0].get("targetPath")) and probes[0].get("running") == []


def cold_start_observed(values: list[dict]) -> bool:
    events = {value.get("event") for value in values}
    exits = [value for value in values if value.get("event") == "launcher-exit"]
    return {"launcher-start", "target-opened", "startup-installed", "startup-ready"} <= events \
        and "target-activated" not in events and len(exits) == 1 \
        and exits[0].get("exitCode") == 0 and exits[0].get("outcome") == "startup-ready"


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


def execute(command: list[str], log: Path, timeout: int = 40) -> tuple[bool, list[dict]]:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        return result.returncode == 0, records(result.stdout)
    except (OSError, subprocess.TimeoutExpired) as error:
        log.write_text(str(error) + "\n", encoding="utf-8")
        return False, []


def check(out: Path, cold_start: bool = False) -> dict:
    theme = json.loads((ROOT / "theme-config.json").read_text(encoding="utf-8"))
    app = Path.home() / "Applications" / theme["identity"]["installationName"]
    executable = app / "Contents/MacOS/AzhouCodexStartup"
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    installed, installation = execute([sys.executable, "tools/install-macos.py", "--check"], out / "installation.log")
    cases.append({"id": "FT-INSTALL", "status": "passed" if installed and unique_installation(installation) else "failed"})
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
    finder_ok, finder = execute(["xcrun", "swift", "-e", finder_probe, str(app),
        theme["identity"]["appName"]["zh-CN"], theme["identity"]["appName"]["en"]], out / "finder.log")
    cases.append({"id": "FT-FINDER", "status": "passed" if finder_ok and len(finder) == 1
                  and finder[0].get("passed") is True else "failed"})
    try:
        dock = plistlib.loads((Path.home() / "Library/Preferences/com.apple.dock.plist").read_bytes())
        entries = dock_entries(dock, app)
    except (OSError, ValueError, plistlib.InvalidFileException):
        entries = []
    cases.append({"id": "FT-DOCK", "status": "pending-visual-review" if entries else "pending-no-entry",
                  "entries": entries,
                  "next": "Review the actual pinned entry label after an upgrade; metadata alone is insufficient."})
    if cold_start:
        probe_ok, probe = execute([str(executable), "--probe"], out / "cold-probe.log")
        if not installed or not probe_ok or not cold_start_allowed(probe):
            cases.append({"id": "FT-COLD", "status": "pending-human-exit",
                          "next": "Finish work, quit the official host yourself, then rerun --cold-start."})
        else:
            launched, launch = execute([str(executable)], out / "cold-launch.log", timeout=75)
            # Actual cold-start events and wallpaper are checked separately.
            # Hot activation caused by a race must never count as cold success.
            cold = launched and cold_start_observed(launch)
            cases.append({"id": "FT-COLD", "status": "pending-visual-review" if cold else "failed",
                          "next": "Review the actual animation and workspace; preserve the event log."})
            deadline = time.monotonic() + 65
            while cold and time.monotonic() < deadline:
                ok, wallpaper = execute([str(executable), "--wallpaper-status"], out / "wallpaper.log")
                if ok and verified_wallpaper(wallpaper):
                    break
                time.sleep(1)
    else:
        cases.append({"id": "FT-COLD", "status": "pending-not-run",
                      "next": "Rerun --cold-start only after the official host has been quit by its user."})
    wallpaper_ok, wallpaper = execute([str(executable), "--wallpaper-status"], out / "wallpaper.log")
    cases.append({"id": "FT-WALLPAPER", "status": "passed" if wallpaper_ok and verified_wallpaper(wallpaper) else "failed"})
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
    result = check(args.out.resolve(), args.cold_start)
    target = args.out.resolve() / "report.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "cases": result["cases"], "report": str(target)}, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

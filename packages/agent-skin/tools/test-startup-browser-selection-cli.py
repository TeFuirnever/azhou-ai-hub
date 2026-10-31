#!/usr/bin/env python3
"""Check no-generated browser selection in a clean temporary source clone."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PACKAGE = Path(__file__).resolve().parents[1]
BUILD_TEST = PACKAGE / "tools/test-startup-build.py"
LEGACY_PACKAGE = PACKAGE.parent / "codex-startup-animation"
GENERATED_ONLY_CHECK = "generated startup wallpaper failure is visible near the appearance entry"


def load_build_helpers():
    spec = importlib.util.spec_from_file_location("agent_skin_browser_selection_build_test", BUILD_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source-clone helper from {BUILD_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if sys.platform != "darwin" or shutil.which("xcrun") is None:
        print("FAILED: isolated browser selection CLI integration requires macOS and xcrun", file=sys.stderr)
        return 2
    node = shutil.which("node")
    if node is None:
        print("FAILED: isolated browser selection CLI integration requires Node.js", file=sys.stderr)
        return 2

    helpers = load_build_helpers()
    with tempfile.TemporaryDirectory(prefix="agent-skin-selection-source-") as temporary:
        temporary_root = Path(temporary)
        package_root = temporary_root / "agent-skin"
        helpers.clone_source_tree(package_root, private=False)
        if (package_root / ".build").exists():
            raise AssertionError("source clone unexpectedly copied the host .build directory")

        legacy_wallpaper = temporary_root / "codex-startup-animation/wallpaper"
        legacy_wallpaper.mkdir(parents=True)
        for name in ("wallpaper.css", "renderer.js"):
            shutil.copy2(LEGACY_PACKAGE / "wallpaper" / name, legacy_wallpaper / name)

        native = subprocess.run(
            [sys.executable, "-B", "tools/test-startup-native.py"], cwd=package_root, check=False,
        )
        if native.returncode:
            return native.returncode
        if not (package_root / ".build/startup-helper-expressions.json").is_file():
            raise AssertionError("isolated native tests did not generate startup helper expressions")
        if not (package_root / ".build/startup-native-tests").is_file():
            raise AssertionError("isolated native tests did not compile their test executable")

        output = temporary_root / "browser-selection-report"
        runner = package_root / "tools/test-startup-browser.mjs"
        result = subprocess.run(
            [node, str(runner), "--only", GENERATED_ONLY_CHECK, "--out", str(output)],
            cwd=package_root, check=False, capture_output=True, text=True,
        )
        if result.returncode != 1:
            raise AssertionError(
                "no-generated CLI should fail for its unavailable selected check; "
                f"exit={result.returncode}\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
            )

        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        if report.get("missingChecks") != [GENERATED_ONLY_CHECK]:
            raise AssertionError(f"runner did not report the generated-only name as missing: {report.get('missingChecks')}")
        if report.get("fatalError"):
            raise AssertionError(f"runner failed before normal selection validation: {report['fatalError']}")
        if not all(report.get("cleanup", {}).get(key) is True for key in (
            "ownChromeStopped", "temporaryProfileRemoved", "serverClosed",
        )):
            raise AssertionError(f"isolated browser cleanup was incomplete: {report.get('cleanup')}")
        if "no Codex process" not in report.get("limitations", [""])[0]:
            raise AssertionError("runner report did not confirm that no Codex process was accessed")

    print("ok: no-generated selection uses a clean source clone and reports the unavailable check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

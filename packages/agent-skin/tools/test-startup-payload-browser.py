#!/usr/bin/env python3
"""Build synthetic startup inputs, then execute the exact payload in isolated Chrome."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE.parents[1]
BUILD_TEST = PACKAGE / "tools/test-startup-build.py"


def validate_browser_report(out: Path, selected: list[str]) -> None:
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    required = set(selected) if selected else {
        "compiled native helper status and apply guard execute against the live fixture API objects",
        "generated Escape keeps Appearance hidden until host UI is ready",
    }
    if not isinstance(report, dict) or report.get("passed") is not True \
            or report.get("missingChecks") != [] or report.get("selectedChecks") != selected \
            or report.get("fatalError") is not None or report.get("cleanupError") is not None:
        raise ValueError("generated-payload browser report is missing or failed")
    cleanup = report.get("cleanup")
    if not isinstance(cleanup, dict) or any(cleanup.get(key) is not True for key in (
            "ownChromeStopped", "temporaryProfileRemoved", "serverClosed")) \
            or cleanup.get("errors") != [] or cleanup.get("profilePath") is not None:
        raise ValueError("generated-payload browser cleanup is missing or failed")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks or any(not isinstance(row, dict) for row in checks):
        raise ValueError("generated-payload browser check rows are missing")
    names = [row.get("name") for row in checks]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError("browser check names are missing or duplicated")
    for row in checks:
        if row.get("passed") is True and "skipped" not in row and row.get("error") is None:
            continue
        if selected and row["name"] not in required and row.get("skipped") is True \
                and "passed" not in row and row.get("error") is None:
            continue
        raise ValueError("browser check has failed or contradictory evidence")
    if not required <= {row["name"] for row in checks if row.get("passed") is True}:
        raise ValueError("required generated-payload browser checks did not pass")


def build_test_helpers():
    spec = importlib.util.spec_from_file_location("agent_skin_startup_build_test", BUILD_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools/test-startup-build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="isolated browser evidence output directory")
    parser.add_argument("--chrome", type=Path, help="optional Chrome executable path")
    parser.add_argument("--only", action="append", default=[], help="run one named browser check; may be repeated")
    parser.add_argument("--native-window-ordering", action="store_true", help="require real synthetic owned-window ordering")
    args = parser.parse_args()
    args.out = args.out.absolute()
    args.out.mkdir(parents=True, exist_ok=False)
    if sys.platform != "darwin" or shutil.which("xcrun") is None:
        parser.exit(2, "builder-generated browser validation requires macOS Vision and xcrun.\n")
    node = shutil.which("node")
    if node is None:
        parser.exit(2, "builder-generated browser validation requires Node.js.\n")

    with tempfile.TemporaryDirectory(prefix="agent-skin-payload-browser-") as temporary:
        root = (Path(temporary) / "agent-skin").resolve()
        helpers = build_test_helpers()
        helpers.clone_source_tree(root)
        bundle = root / ".build/azhou-stage.browser/azhou-payload"
        bundle.mkdir(parents=True)
        builder = helpers.load_module(root / "tools/build-startup.py", "agent_skin_payload_browser_builder")
        builder.build_startup(bundle, root=root)
        payload = bundle / "Contents/Resources/startup/install.js"
        native_command = [sys.executable, "-B", "tools/test-startup-native.py"]
        if args.native_window_ordering:
            native_command.extend(("--window-ordering", "--out", str(args.out / "native-window-ordering")))
        native = subprocess.run(native_command, cwd=root, check=False)
        if native.returncode:
            return native.returncode
        if args.native_window_ordering:
            try:
                evidence = args.out / "native-window-ordering"
                report = json.loads((evidence / "report.json").read_text(encoding="utf-8"))
                guard = helpers.load_module(root / "tools/test-startup-native.py", "agent_skin_native_window_guard")
                fingerprint = guard.source_fingerprint()
                binary = hashlib.sha256((root / ".build/startup-native-tests").read_bytes()).hexdigest()
                if not isinstance(report, dict) or report.get("passed") is not True or report.get("error") is not None \
                        or report.get("sourceBefore") != fingerprint or report.get("sourceAfter") != fingerprint \
                        or report.get("binaryBefore") != binary or report.get("binaryAfter") != binary:
                    raise ValueError("native functional evidence does not match the current inputs")
                rows = guard.validate_window_observations(
                    (evidence / "stdout.jsonl").read_text(encoding="utf-8"), report.get("returncode"))
                if report.get("observations") != rows:
                    raise ValueError("native functional report and raw observations disagree")
            except (OSError, ValueError, TypeError) as error:
                print(f"FAILED: {error}", file=sys.stderr)
                return 1
        if os.environ.get("AZHOU_RUN_NATIVE_EVENT_ASSESSMENT") == "1":
            samples = root / ".build/native-event-samples"
            emitted = subprocess.run(
                [str(root / ".build/startup-native-tests"), "--emit-event-jsonl", str(samples)],
                cwd=root, check=False,
            )
            if emitted.returncode:
                return emitted.returncode
            environment = os.environ.copy()
            environment["AZHOU_AGENT_SKIN_NATIVE_EVENT_SAMPLES"] = str(samples)
            assessment_test = REPOSITORY_ROOT / "tests/test_agent_skin_native_event_assessment.py"
            assessed = subprocess.run(
                [sys.executable, "-B", str(assessment_test)], cwd=REPOSITORY_ROOT,
                env=environment, check=False,
            )
            if assessed.returncode:
                return assessed.returncode
        browser_test = root / "tools/test-startup-browser.mjs"
        command = [node, str(browser_test), "--generated-payload", str(payload), "--out", str(args.out)]
        if args.chrome:
            command.extend(("--chrome", str(args.chrome)))
        for name in args.only:
            command.extend(("--only", name))
        print("==> " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=root, check=False).returncode
        if result:
            return result
        try:
            validate_browser_report(args.out, args.only)
        except (OSError, ValueError, TypeError) as error:
            print(f"FAILED: {error}", file=sys.stderr)
            return 1
        if args.only:
            return 0
        preview = bundle / "Contents/Resources/web/index.html"
        preview_test = root / "tools/test-animation-preview-final-text-browser.mjs"
        preview_command = [node, str(preview_test), "--preview", str(preview),
                           "--out", str(args.out / "animation-preview")]
        if args.chrome:
            preview_command.extend(("--chrome", str(args.chrome)))
        print("==> " + " ".join(preview_command), flush=True)
        return subprocess.run(preview_command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

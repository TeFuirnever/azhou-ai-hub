#!/usr/bin/env python3
"""Build synthetic startup inputs, then execute the exact payload in isolated Chrome."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
LEGACY_PACKAGE = PACKAGE.parent / "codex-startup-animation"
BUILD_TEST = PACKAGE / "tools/test-startup-build.py"


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
    args = parser.parse_args()
    if sys.platform != "darwin" or shutil.which("xcrun") is None:
        parser.exit(2, "builder-generated browser validation requires macOS Vision and xcrun.\n")
    node = shutil.which("node")
    if node is None:
        parser.exit(2, "builder-generated browser validation requires Node.js.\n")

    with tempfile.TemporaryDirectory(prefix="agent-skin-payload-browser-") as temporary:
        root = (Path(temporary) / "agent-skin").resolve()
        helpers = build_test_helpers()
        helpers.clone_source_tree(root)
        legacy_wallpaper = Path(temporary) / "codex-startup-animation/wallpaper"
        legacy_wallpaper.mkdir(parents=True)
        shutil.copy2(LEGACY_PACKAGE / "wallpaper/wallpaper.css", legacy_wallpaper / "wallpaper.css")
        shutil.copy2(LEGACY_PACKAGE / "wallpaper/renderer.js", legacy_wallpaper / "renderer.js")
        bundle = root / ".build/azhou-stage.browser/azhou-payload"
        bundle.mkdir(parents=True)
        builder = helpers.load_module(root / "tools/build-startup.py", "agent_skin_payload_browser_builder")
        builder.build_startup(bundle, root=root)
        payload = bundle / "Contents/Resources/startup/install.js"
        native = subprocess.run([sys.executable, "-B", "tools/test-startup-native.py"], cwd=root, check=False)
        if native.returncode:
            return native.returncode
        browser_test = root / "tools/test-startup-browser.mjs"
        command = [node, str(browser_test), "--generated-payload", str(payload), "--out", str(args.out)]
        if args.chrome:
            command.extend(("--chrome", str(args.chrome)))
        for name in args.only:
            command.extend(("--only", name))
        print("==> " + " ".join(command), flush=True)
        return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

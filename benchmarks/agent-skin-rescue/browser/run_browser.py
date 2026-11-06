"""Run the restored full browser fixture on newly bound default resources.

Owns one private headless Chrome through the restored lifecycle helper. It never
attaches to a running browser or host, and never reads a daily profile/keychain.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

ANCHOR = "b689702097be8bd3e2a4b6f2a10afb348cf5cb37"
EXPECTED = {
    "test-startup-browser.mjs": "0ffb327cf7071965504512c668bead84725b91972c2d70360dd6775484ac7355",
    "fixture-browser-lifecycle.mjs": "559ef05ea3f71ffaf3b64c65157476feeb9aa54c24c97b40c64777b00bafab77",
}
HARNESS_PATCH_SHA256 = "9f98ade764e5f0f6d66a1808976a39dfe306748e834bc16ba2f12bd7ee9bc396"
WALLPAPER_SUBTREE = "92cfa938ad3f342c9d3111e4a6114cd3f37c7a8b"
WALLPAPERS = {
    "wallpaper.css": "e2974673a1c92d2d1f4c8b36cfc695d5806bb975e4c7c27f70b430fc4dbfc16a",
    "renderer.js": "38226c5f4d31ba773def9eca1f69e44048c5e7d9a6206fd9bdc1dae43149a933",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_anchor(fixture_repo):
    probe = subprocess.run(["git", "-C", str(fixture_repo), "cat-file", "-e", ANCHOR + "^{commit}"], capture_output=True, check=False)
    if probe.returncode != 0:
        raise ValueError("public source anchor " + ANCHOR + " is missing from this repository; fetch the public history containing it")


def read_patch(root):
    encoded = root / "tooling/browser/harness.patch.b64"
    patch_bytes = base64.b64decode("".join(encoded.read_text().splitlines()), validate=True)
    if hashlib.sha256(patch_bytes).hexdigest() != HARNESS_PATCH_SHA256:
        raise ValueError("packaged harness patch digest mismatch")
    patch = root / "tooling/browser/harness.patch"
    with patch.open("xb") as handle:
        handle.write(patch_bytes)
    return patch


def restore_wallpapers(root, fixture_repo):
    require_anchor(fixture_repo)
    subtree = subprocess.check_output(["git", "-C", str(fixture_repo), "rev-parse", ANCHOR + ":packages/codex-startup-animation/wallpaper"], text=True, encoding="utf-8").strip()
    if subtree != WALLPAPER_SUBTREE:
        raise ValueError("wallpaper subtree mismatch at the public anchor")
    for name, digest in WALLPAPERS.items():
        data = subprocess.check_output(["git", "-C", str(fixture_repo), "show", ANCHOR + ":packages/codex-startup-animation/wallpaper/" + name])
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("recorded wallpaper digest mismatch: " + name)
        destination = root / "codex-startup-animation/wallpaper" / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with destination.open("xb") as handle:
            handle.write(data)


def copy_file(source, destination):
    if source.resolve() != source or not source.is_file():
        raise ValueError("direct source file required")
    before = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open("xb") as handle:
        handle.write(before)
    if source.read_bytes() != before or destination.read_bytes() != before:
        raise ValueError("input drift during copy")


def prepare(args):
    sys.path.insert(0, str(Path(__file__).parents[1] / "rebind"))
    from check_binding import verify_binding
    resource = args.resource_root
    binding_path, producer_path = resource / "build/binding.json", resource / "producer/0/command.json"
    verify_binding(binding_path, producer_path, root=resource)
    binding = json.loads(binding_path.read_text())
    root = args.root
    if not root.is_absolute() or root.resolve() != root or root.exists():
        raise ValueError("new private browser root required")
    root.mkdir(mode=0o700)
    source = root / "source"
    shutil.copytree(resource / binding["source_stage"], source, ignore=shutil.ignore_patterns(".build"))
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("source contains a link")
    for name in ["offline_runtime.py", "command_log.py"]:
        copy_file(args.tools / name, root / "tooling" / name)
    for name in ["run_browser.py", "harness.patch.b64"]:
        copy_file(Path(__file__).parent / name, root / "tooling/browser" / name)
    sys.path.insert(0, str(root / "tooling"))
    from command_log import CommandLog
    patch_commands = root / "prepare-commands"
    patch_commands.mkdir(mode=0o700)
    patch = read_patch(root)
    log = CommandLog(patch_commands, [{"path": str(patch.relative_to(root)), "sha256": sha(patch)}], root=root, stage=root)
    log.record(["patch", "--batch", "--forward", "-p1", "-i", str(patch)], cwd=source, check=True,
               artifact_paths=[source / "tools" / name for name in [*EXPECTED, "test-startup-build.py", "test-animation-preview-final-text-browser.mjs"]])
    for name, digest in EXPECTED.items():
        if sha(source / "tools" / name) != digest:
            raise ValueError("restored harness SHA mismatch: " + name)
    for name, digest in binding["source_inputs"].items():
        if sha(source / name) != digest:
            raise ValueError("production input drift: " + name)
    normal = binding["normal_default_payload"]
    manifest = binding["normal_default_manifest"]
    copy_file(resource / normal["path"], root / "normal/install.js")
    copy_file(resource / manifest["path"], root / "normal/manifest.json")
    restore_wallpapers(root, Path(__file__).resolve().parents[3])
    provenance = {"scope": "same new resource candidate, exact build-31 source restoration, verified legacy wallpaper subtree; fixture only",
                  "source_baseline": binding["source_baseline"],
                  "wallpaper": {"source_commit": ANCHOR, "source_subtree": WALLPAPER_SUBTREE, "digests": WALLPAPERS,
                                "historical_baseline": "wallpaper subtree identical at the public anchor and the historical build-31 baseline; digests re-verified on every run"},
                  "source_binding": {"path": str(binding_path), "sha256": sha(binding_path)},
                  "source_producer": {"path": str(producer_path), "sha256": sha(producer_path)},
                  "normal_payload": {"path": "normal/install.js", "sha256": sha(root / "normal/install.js")},
                  "normal_manifest": {"path": "normal/manifest.json", "sha256": sha(root / "normal/manifest.json")},
                  "production_inputs": binding["source_inputs"], "harness_sha256": EXPECTED,
                  "legacy_navigation_budget_ms": 10000, "full_browser_budget_seconds": 900,
                  "ui_assertions_reduced": False, "host_validation": "not_run"}
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    inputs = [{"path": str(path.relative_to(root)), "sha256": sha(path)}
              for folder in ["source", "normal", "tooling", "prepare-commands", "codex-startup-animation"]
              for path in sorted((root / folder).rglob("*")) if path.is_file()]
    inputs.append({"path": "provenance.json", "sha256": sha(root / "provenance.json")})
    if args.reuse_node_root:
        previous_root = args.reuse_node_root
        previous_path = previous_root / "commands/0/command.json"
        previous = json.loads(previous_path.read_text())
        if (previous.get("kind") != "C" or previous.get("execution_state") != "exited"
                or previous.get("exit_code") != 0 or previous.get("error") is not None
                or not previous.get("inputs_unchanged") or not previous.get("argument_inputs_unchanged")
                or previous["argv"][:2] != ["node", "--test"] or len(previous["argv"][2:]) != 13):
            raise ValueError("prior Node execution is not reusable")
        for item in previous["inputs"] + previous["argument_inputs"]:
            before = previous_root / item["path"]
            if sha(before) != item["sha256"]:
                raise ValueError("prior Node input drift")
            if item["path"].startswith("source/") and sha(root / item["path"]) != item["sha256"]:
                raise ValueError("new browser source differs from passed Node candidate")
        copied = []
        copy_file(previous_path, root / "reused-node/original-command.json")
        copied.append(root / "reused-node/original-command.json")
        for index, item in enumerate(previous["outputs"]["raw_files"]):
            before = previous_root / item["path"]
            if sha(before) != item["sha256"]:
                raise ValueError("prior Node raw output drift")
            destination = root / "reused-node" / (str(index) + ".raw")
            copy_file(before, destination);copied.append(destination)
        reference = root / "reused-node/reference.json"
        reference.write_text(json.dumps({"scope": "same frozen source; no new Node execution claimed",
            "prior_root": str(previous_root), "prior_receipt_sha256": sha(previous_path),
            "source_inputs_rechecked": True, "formal_files": 13, "tests": 256, "actual_exit": 0}, indent=2) + "\n")
        copied.append(reference)
        inputs += [{"path": str(path.relative_to(root)), "sha256": sha(path)} for path in copied]

    (root / "inputs-initial.json").write_text(json.dumps(inputs, indent=2) + "\n")
    return inputs


def run(root, chrome, *, resume_after_node=False, reuse_node=False):
    sys.path.insert(0, str(root / "tooling"))
    from command_log import CommandLog
    commands = root / ("commands-resume-01" if resume_after_node else "commands")
    commands.mkdir(mode=0o700)
    inputs = json.loads((root / "inputs-initial.json").read_text())
    log = CommandLog(commands, inputs, root=root, stage=root)
    source = root / "source"
    formal = sorted(str(path) for path in (source / "tools").glob("*.test.mjs"))
    if len(formal) != 13:
        raise ValueError("formal Node test file count changed")
    if reuse_node:
        proof = json.loads((root / "reused-node/reference.json").read_text())
        if not proof["source_inputs_rechecked"] or proof["actual_exit"] != 0:
            raise ValueError("missing validated Node reuse proof")
    elif resume_after_node:
        previous_path = root / "commands/0/command.json"
        previous = json.loads(previous_path.read_text())
        if (previous.get("kind") != "C" or previous.get("execution_state") != "exited"
                or previous.get("exit_code") != 0 or not previous.get("inputs_unchanged")
                or not previous.get("argument_inputs_unchanged") or previous.get("error") is not None
                or previous["argv"] != ["node", "--test", *formal]):
            raise ValueError("cannot reuse unproven formal Node execution")
        for item in previous["inputs"] + previous["argument_inputs"]:
            if sha(root / item["path"]) != item["sha256"]:
                raise ValueError("formal Node input changed before resume")
        for item in previous["outputs"]["raw_files"]:
            if sha(root / item["path"]) != item["sha256"]:
                raise ValueError("formal Node raw evidence drift")
        (root / "node-reuse.json").write_text(json.dumps({"scope": "same frozen source; no new Node execution claimed",
            "receipt": "commands/0/command.json", "sha256": sha(previous_path), "inputs_rechecked": True}, indent=2) + "\n")
    else:
        log.record(["node", "--test", *formal], cwd=source, check=True, timeout=120)
    # Formal Node tests generate their own .build fixtures. Keep those bytes and
    # compile native/browser support in a fresh exact source copy instead.
    browser_source = root / "browser-source"
    shutil.copytree(source, browser_source, ignore=shutil.ignore_patterns(".build"))
    inputs += [{"path": str(path.relative_to(root)), "sha256": sha(path)}
               for path in sorted(browser_source.rglob("*")) if path.is_file()]
    source = browser_source
    build = source / ".build"
    if build.is_symlink() or build.resolve() != build:
        raise ValueError("unsafe native build directory")
    build.mkdir(mode=0o700, exist_ok=True)
    native = build / "startup-native-tests"
    native_sources = [source / "Native" / name for name in ["App.swift", "Wallpaper.swift", "SkinHostContract.swift", "CodexSkinDriver.swift", "StartupNativeTests.swift"]]
    log.record(["xcrun", "--sdk", "macosx", "swiftc", "-DAGENT_SKIN_NATIVE_EVENT_TESTS", "-target", platform.machine() + "-apple-macos13.0", *map(str, native_sources),
                "-o", str(native), "-framework", "AppKit", "-framework", "WebKit"], cwd=source, check=True, timeout=180)
    emitted = log.record([str(native), "--emit-helper-expressions"], cwd=source, check=True, timeout=30)
    expressions = json.loads(emitted.stdout)
    if set(expressions) != {"statusSource", "applyGuardSource", "retrySource", "restoreSource"}:
        raise ValueError("unexpected native fixture expression shape")
    expression_path = build / "startup-helper-expressions.json"
    expression_path.write_text(json.dumps(expressions, ensure_ascii=False, sort_keys=True) + "\n")
    inputs += [{"path": str(path.relative_to(root)), "sha256": sha(path)} for path in [native, expression_path]]
    (root / "inputs-browser.json").write_text(json.dumps(inputs, indent=2) + "\n")
    browser_commands = root / "browser-commands"
    browser_commands.mkdir(mode=0o700)
    browser_log = CommandLog(browser_commands, inputs, root=root, stage=root)
    out = root / "browser"
    argv = ["node", str(source / "tools/test-startup-browser.mjs"), "--chrome", str(chrome), "--generated-payload", str(root / "normal/install.js"), "--out", str(out)]
    result = browser_log.record(argv, cwd=source, timeout=900, artifact_paths=[out / "report.json", out / "owned-child-complete.json"], check=False)
    report = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else None
    owner = json.loads((out / "owned-child-complete.json").read_text()) if (out / "owned-child-complete.json").is_file() else None
    counts = ({"total": len(report["checks"]), "passed": sum(bool(x.get("passed")) for x in report["checks"]),
               "failed": sum(x.get("passed") is False for x in report["checks"]), "skipped": sum(bool(x.get("skipped")) for x in report["checks"])} if report else None)
    summary = {"scope": "current rebuilt same-candidate full browser fixture; not host", "actual_exit": result.returncode, "counts": counts,
               "chrome_wait_observed": owner.get("waitObserved") if owner else None,
               "chrome_exit": owner.get("exit") if owner else None, "chrome_close": owner.get("close") if owner else None,
               "capture_errors": owner.get("captureErrors") if owner else None,
               "native_main_suite": "not_run; compiled helper expressions and no-lock transport only",
               "payload_sha256": sha(root / "normal/install.js"), "manifest_sha256": sha(root / "normal/manifest.json")}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    if result.returncode != 0 or counts != {"total": 70, "passed": 70, "failed": 0, "skipped": 0} or not owner or not owner.get("waitObserved"):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--resource-root", type=Path)
    parser.add_argument("--tools", type=Path)
    parser.add_argument("--chrome", type=Path, default=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--resume-after-node", action="store_true")
    parser.add_argument("--reuse-node-root", type=Path)
    parser.add_argument("--reuse-node", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if args.run_only:
        return run(args.root, args.chrome, resume_after_node=args.resume_after_node, reuse_node=args.reuse_node)
    if args.resume_after_node:
        inputs = json.loads((args.root / "inputs-initial.json").read_text())
        resume_source = args.root / "tooling/browser/run_browser-resume-01.py"
        copy_file(Path(__file__).resolve(), resume_source)
        inputs.append({"path": str(resume_source.relative_to(args.root)), "sha256": sha(resume_source)})
    else:
        if not args.resource_root or not args.tools:
            parser.error("prepare requires --resource-root and --tools")
        inputs = prepare(args)
    sys.path.insert(0, str(args.root / "tooling"))
    from command_log import CommandLog
    producer = args.root / ("producer-resume-01" if args.resume_after_node else "producer")
    producer.mkdir(mode=0o700)
    log = CommandLog(producer, inputs, root=args.root, stage=args.root)
    runner = resume_source if args.resume_after_node else args.root / "tooling/browser/run_browser.py"
    extra = ["--resume-after-node"] if args.resume_after_node else (["--reuse-node"] if args.reuse_node_root else [])
    result = log.record([sys.executable, "-B", str(runner), "--root", str(args.root), "--chrome", str(args.chrome), "--run-only", *extra],
                        cwd=args.root, timeout=1150, artifact_paths=[args.root / "summary.json"], check=False)
    print(result.stdout.decode(), flush=True)
    print(result.stderr.decode(), file=sys.stderr, flush=True)
    raise SystemExit(result.returncode if result.returncode is not None else 1)


if __name__ == "__main__":
    main()

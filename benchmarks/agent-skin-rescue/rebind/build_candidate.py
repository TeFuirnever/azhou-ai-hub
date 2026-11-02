"""Build retained source-copy resources from the exact historical build 31 tree.

The source is reconstructed without the unpublished historical commit object:
the public anchor archive plus the tracked, digest-pinned restoration patch,
verified by Git tree id before use. All subprocesses operate on private copies.
This never builds, installs, signs, launches, or connects to a host application.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import uuid

from source_patch import patch_sources

ANCHOR = "b689702097be8bd3e2a4b6f2a10afb348cf5cb37"
ANCHOR_TREE = "93de39312c4a7aadaa2800ff2d60d52de3e4aac7"
BASELINE = "8eec664611c2f679be6714bd888a07d764459c8a"
BASELINE_TREE = "3060b7e3587b37a0486c54423f76bb3d792c7b6d"
RESTORATION_SHA256 = "5b5382b8b4dcfd4dfe1894ff4140fec1ac6c5dbc7146d320de92e429e5a045fb"
MATERIALS = {
    "working.png": ("working.png", "34dc9a8e9c06c226ec0cc80878548f118ff4a23b4a87d160674e66db4a905e58"),
    "wallpaper-scene-q-v3.png": ("wallpaper-scene-q-v3.png", "566eee5034343bb8463fa684dc0b90fe3d2c5d8f2adde1c9d71356bf192acbcb"),
    "entry-avatar.png": ("app-icon/source.png", "fd0d4bfd7b394f45c8724436e765be5ecfa9f675a2a9214619a65e32eebbf21d"),
    "app-icon/source.png": ("app-icon/source.png", "fd0d4bfd7b394f45c8724436e765be5ecfa9f675a2a9214619a65e32eebbf21d"),
    "scene.js": ("scene.js", "6368a43150e2b75d0077a26bb698407c2eed6424fd960520398535ee2d0c92e0"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_new(source, destination):
    if source.resolve() != source or not source.is_file():
        raise ValueError("input must be a direct regular file")
    data = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open("xb") as handle:
        handle.write(data)
    if source.read_bytes() != data or destination.read_bytes() != data:
        raise ValueError("copy input changed")


def restoration_patch(destination, encoded=None):
    source = Path(encoded) if encoded is not None else Path(__file__).parent / "restoration.patch.b64"
    patch_bytes = base64.b64decode("".join(source.read_text().splitlines()), validate=True)
    if hashlib.sha256(patch_bytes).hexdigest() != RESTORATION_SHA256:
        raise ValueError("restoration patch digest mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open("xb") as handle:
        handle.write(patch_bytes)
    return destination


def restored_tree_id(directory, scratch):
    scratch.mkdir(mode=0o700)
    gitdir, index = scratch / "restore.git", scratch / "add.index"
    subprocess.run(["git", "init", "-q"], env=dict(os.environ, GIT_DIR=str(gitdir)), check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)
    environment = dict(os.environ, GIT_DIR=str(gitdir), GIT_WORK_TREE=str(directory),
                       GIT_INDEX_FILE=str(index), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    try:
        subprocess.run(["git", "add", "-A", "--force"], cwd=directory, env=environment, check=True,
                       stdin=subprocess.DEVNULL, capture_output=True)
        return subprocess.check_output(["git", "write-tree"], env=environment, stdin=subprocess.DEVNULL,
                                       text=True, encoding="ascii").strip()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def prepare(root, source, materials, tools):
    if not root.is_absolute() or root.resolve() != root or root.exists():
        raise ValueError("root must be a new absolute private container")
    root.mkdir(mode=0o700)
    repo = Path(subprocess.check_output(["git", "-C", str(source), "rev-parse", "--show-toplevel"], text=True, encoding="utf-8").strip())
    relative = source.relative_to(repo)
    probe = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", ANCHOR + "^{commit}"], capture_output=True, check=False)
    if probe.returncode != 0:
        raise ValueError("public source anchor " + ANCHOR + " is missing from this repository; fetch the public history containing it")
    tree = subprocess.check_output(["git", "-C", str(repo), "rev-parse", ANCHOR + ":" + str(relative)], text=True, encoding="utf-8").strip()
    if tree != ANCHOR_TREE:
        raise ValueError("public source anchor tree mismatch for " + str(relative))
    archive = subprocess.check_output(["git", "-C", str(repo), "archive", ANCHOR, str(relative)])
    baseline = root / "baseline"
    baseline.mkdir(mode=0o700)
    # Git supplies tracked fixed-commit files only; reject links and traversal.
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        for entry in bundle:
            if not entry.isfile():
                if entry.isdir():
                    continue
                raise ValueError("unexpected source archive link")
            path = Path(entry.name).relative_to(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe archive member")
            destination = baseline / path
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with destination.open("xb") as handle:
                handle.write(bundle.extractfile(entry).read())
            os.chmod(destination, entry.mode & 0o777)
    patch_file = restoration_patch(root / "restoration.patch")
    try:
        applied = subprocess.run(["patch", "--batch", "--forward", "-p3", "-i", str(patch_file)],
                                 cwd=baseline, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    finally:
        patch_file.unlink()
    if applied.returncode != 0:
        raise ValueError("build-31 restoration patch failed: " + applied.stderr.strip()[:400])
    if restored_tree_id(baseline, root / "restoration-scratch") != BASELINE_TREE:
        raise ValueError("restored build-31 tree mismatch")
    material_root = root / "materials/assets/private"
    for destination, (origin, expected) in MATERIALS.items():
        path = materials / origin
        if sha(path) != expected:
            raise ValueError("registered material digest mismatch: " + origin)
        copy_new(path, material_root / destination)
        if sha(material_root / destination) != expected:
            raise ValueError("material copy mismatch")
    copied_tools = root / "tooling"
    for name in ["offline_runtime.py", "command_log.py"]:
        copy_new(tools / name, copied_tools / name)
    for name in ["build_candidate.py", "source_patch.py", "r10-diagnostics.mjs", "assembly_controls.cjs", "check_binding.py"]:
        copy_new(Path(__file__).parent / name, copied_tools / "rebind" / name)
    return [{"path": str(path.relative_to(root)), "sha256": sha(path)}
            for folder in ["baseline", "materials", "tooling"]
            for path in sorted((root / folder).rglob("*")) if path.is_file()]


def build(root, output):
    if root.resolve() != root or output.resolve() != output or not output.is_relative_to(root) or output.exists():
        raise ValueError("unsafe/new output required")
    output.mkdir(mode=0o700)
    tooling = root / "tooling"
    sys.path.insert(0, str(tooling))
    from command_log import CommandLog
    inputs = json.loads((root / "inputs.json").read_text())
    commands = output / "commands"
    commands.mkdir(mode=0o700)
    logger = CommandLog(commands, inputs, root=root, stage=root)
    source = output / "source"
    shutil.copytree(root / "baseline", source)
    for item in (root / "materials").rglob("*"):
        if item.is_file():
            copy_new(item, source / item.relative_to(root / "materials"))
    names = ["tools/build-startup.py", "extension/bootstrap.mjs", "extension/renderer.mjs", "tools/verify-artifacts.py", "hub-package.json"]
    original = {name: (source / name).read_text() for name in names}
    patched = patch_sources(original, (tooling / "rebind/r10-diagnostics.mjs").read_text())
    import difflib
    diff = []
    for name, text in patched.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        diff.extend(difflib.unified_diff(original.get(name, "").splitlines(True), text.splitlines(True), fromfile="baseline/" + name, tofile="candidate/" + name))
    (output / "source.diff").write_text("".join(diff))
    environment = {name: os.environ[name] for name in ["PATH", "LANG", "LC_ALL", "LC_CTYPE"] if name in os.environ}
    for name in ["HOME", "TMPDIR", "SWIFT_MODULECACHE_PATH", "CLANG_MODULE_CACHE_PATH"]:
        directory = output / ("private-" + name.lower())
        directory.mkdir(mode=0o700)
        environment[name] = str(directory)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.clear()
    os.environ.update(environment)
    builder = load(source / "tools/build-startup.py", "rescue_resource_builder")
    builder.subprocess = SimpleNamespace(run=logger.record, check_output=logger.check_output, CalledProcessError=subprocess.CalledProcessError)

    class RetainedDirectory:
        def __init__(self, prefix="", dir=None):
            self.path = Path(dir or output) / (prefix + uuid.uuid4().hex)
            self.path.mkdir(mode=0o700)
        def __enter__(self):
            return str(self.path)
        def __exit__(self, *error):
            return False

    builder.tempfile = SimpleNamespace(TemporaryDirectory=RetainedDirectory)
    verifier = load(source / "tools/verify-artifacts.py", "rescue_resource_verifier")
    wallpaper = load(source / "tools/build-wallpaper.py", "rescue_wallpaper_builder")
    diagnostic_stage = source / ".build/azhou-stage.rescue-diagnostic/azhou-payload"
    normal_stage = source / ".build/azhou-stage.rescue-default/azhou-payload"
    diagnostic_stage.mkdir(parents=True)
    normal_stage.mkdir(parents=True)
    diagnostic_manifest = builder.build_startup(diagnostic_stage, root=source, r10_diagnostics=True)
    normal_manifest = builder.build_startup(normal_stage, root=source)
    source_inputs = verifier.source_inputs()
    marker = {"version": verifier.VERSION, "build": verifier.BUILD, "inputSHA256": verifier.aggregate_inputs(source_inputs), "inputs": source_inputs}
    info = {"CFBundleShortVersionString": verifier.VERSION, "CFBundleVersion": verifier.BUILD}
    for stage in [diagnostic_stage, normal_stage]:
        verifier.verify_startup(stage, info, marker)
        wallpaper.package(stage)
        verifier.verify_wallpaper(stage, info, marker)
    if diagnostic_manifest["sourceInputs"] != normal_manifest["sourceInputs"]:
        raise ValueError("default/diagnostic source input mismatch")
    resources = diagnostic_stage / "Contents/Resources"
    base = resources / "startup/install.js"
    normal = normal_stage / "Contents/Resources/startup/install.js"
    if "diagnostics: createR10Diagnostics(R10_CONFIG)" in normal.read_text():
        raise ValueError("default Codex path enabled diagnostics")
    copy_new(normal, output / "unwired.js")
    owner, foreign = str(uuid.uuid4()), str(uuid.uuid4())
    generation = hashlib.sha256(b"offline-r10-context-generation").hexdigest()
    wrappers = {}
    for label, action, token in [("mount", "mount", owner), ("foreign", "clean", foreign), ("clean", "clean", owner), ("stale", "clean", owner)]:
        config = {"action": action, "owner": owner, "id": "agent-skin-zcode-probe-" + owner, "token": token,
                  "timeOrigin": 123.25 if label == "stale" else 456.75, "generationSHA256": generation}
        path = output / (label + ".js")
        path.write_text("((R10_CONFIG) => (\n" + base.read_text() + "\n))(" + json.dumps(config, separators=(",", ":")) + ")")
        wrappers[label] = {"path": str(path.relative_to(root)), "sha256": sha(path), "config": config}
    for path in [base, resources / "wallpaper/install.js", output / "unwired.js"]:
        logger.record(["node", "--check", str(path)], cwd=output, env=environment, check=True)
    logger.record(["node", str(tooling / "rebind/assembly_controls.cjs"), str(output)], cwd=output, env=environment, check=True)
    item = lambda path: {"path": str(path.relative_to(root)), "sha256": sha(path)}
    receipts = [item(path) for path in sorted(commands.glob("*/command.json"))]
    binding = {"kind": "A", "schema": "offline-resource-binding.v1", "source_commit": BASELINE,
               "source_baseline": {"commit": BASELINE, "tree": BASELINE_TREE,
                                   "scope": "exact historical build-31 source tree, reconstructed from the public anchor and the tracked restoration patch; the unpublished historical commit object is not required",
                                   "anchor": {"commit": ANCHOR, "tree": ANCHOR_TREE},
                                   "restoration_patch_sha256": RESTORATION_SHA256},
               "scope": "real registered private resources and source-copy builders; VM fixtures only; no host",
               "inputs": inputs, "source_stage": str(source.relative_to(root)), "source_inputs": source_inputs,
               "base_payload": item(base), "startup_manifest": item(resources / "startup/manifest.json"),
               "wallpaper": item(resources / "wallpaper/install.js"), "normal_default_payload": item(normal),
               "normal_default_manifest": item(normal_stage / "Contents/Resources/startup/manifest.json"),
               "wrappers": wrappers, "commands": receipts, "command_count": len(receipts),
               "source_diff_sha256": sha(output / "source.diff"), "host_validation": "not_run",
               "default_codex_diagnostics": False, "native_app_build": "not_run"}
    with (output / "binding.json").open("x") as handle:
        json.dump(binding, handle, indent=2)
        handle.write("\n")
    return binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--materials", type=Path)
    parser.add_argument("--tools", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    root = args.root
    if args.build_only:
        binding = build(root, args.out)
        print(json.dumps({"binding": str(args.out / "binding.json"), "commands": binding["command_count"]}))
        return
    if not all([args.source, args.materials, args.tools]):
        parser.error("prepare requires --source, --materials, --tools")
    inputs = prepare(root, args.source, args.materials, args.tools)
    (root / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    sys.path.insert(0, str(root / "tooling"))
    from command_log import CommandLog
    producer = root / "producer"
    producer.mkdir(mode=0o700)
    logger = CommandLog(producer, inputs, root=root, stage=root)
    output = args.out or root / "build"
    result = logger.record([sys.executable, "-B", str(root / "tooling/rebind/build_candidate.py"), "--root", str(root), "--out", str(output), "--build-only"],
                           cwd=root, timeout=420, artifact_paths=[output / "binding.json"], check=True)
    print(result.stdout.decode())
    print(json.dumps({"root": str(root), "binding": str(output / "binding.json"), "producer": str(producer / "0/command.json"), "actual_exit": result.returncode}))


if __name__ == "__main__":
    main()

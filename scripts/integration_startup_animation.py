"""Bounded access to the existing macOS launcher and its separate wallpaper helper.

The source installer owns the user Applications entry. Hub owns only explicitly
created test installations below its ignored workspace state directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
from typing import Any

try:
    from . import integration_common as common
    from . import azhou_runtime_state as state
except ImportError:
    import integration_common as common
    import azhou_runtime_state as state

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "agent-skin"
LEGACY_COMPONENT = "startup-animation"
APP_NAME = "阿舟 AI 实验室.app"
LEGACY_APP_NAME = "阿舟启动 Codex.app"
EXECUTABLE = "AzhouCodexStartup"
STARTUP_PAYLOAD_VERSION = "0.8.0"
STARTUP_EVENT_SCHEMA = "azhou-startup.event.v1"
STARTUP_EVENT_VERSION = (0, 8, 0)
_VERSIONED_FAILURE_EVENTS = frozenset({"failure", "duplicate-entry", "lock-error", "startup-port-error"})
_VERSIONED_LAUNCH_EVENTS = frozenset({
    "launcher-start", "target-opened", "startup-installed", "target-activated",
    "startup-ready", "startup-skipped", "startup-interrupted", "startup-failed",
    "launcher-exit", *_VERSIONED_FAILURE_EVENTS,
})
_VERSIONED_SMOKE_EVENTS = frozenset({
    "player-start", "playback-start", "animation-complete", "preview-result", "player-terminated",
    "launcher-exit", "target-opened", "target-activated", "target-open-request", "target-reused",
    "target-activation-request", "startup-installed", "startup-ready", "startup-skipped",
    "startup-interrupted", "startup-failed", *_VERSIONED_FAILURE_EVENTS,
})
_VERSIONED_PROBE_EVENTS = frozenset({"probe", *_VERSIONED_FAILURE_EVENTS})
_VERSIONED_DIAGNOSTIC_EVENTS = frozenset({
    "startup-launcher-start", "startup-port-selected", "waiting-for-target", "target-open-request",
    "target-launch-completion", "target-reused", "target-activation-request",
    "target-activation-after-startup", "player-start", "playback-start", "animation-complete",
    "preview-result", "player-terminated", "handoff-fade-start", "handoff-fade-complete",
    "preview-launch-pending", "preview-promoted-to-launch", "reopen-existing-player",
    "duplicate-ready-ignored", "snapshot-error", "snapshot-saved", "unhandled-message",
    "window-close-as-skip", "window-created", "wallpaper-helper-start",
    "wallpaper-helper-complete", "wallpaper-helper-failed", "wallpaper-result",
    "wallpaper-port-unavailable",
})
PRIVATE_FILES = ("working.png", "scene.js", "wallpaper-scene-q-v3.png", "app-icon/source.png")
REGISTRY_IDS = ("local.azhou.codex-startup", "local.aemeath.startup", "local.aemeath.extension")
LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"


def _directory(path: Path, *, exists: bool = True) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise common.IntegrationError(f"explicit absolute non-symlink path required: {path}")
    if (exists and not path.is_dir()) or (path.exists() and not path.is_dir()):
        raise common.IntegrationError(f"directory unavailable: {path}")
    return path.resolve(strict=False)


def _hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise common.IntegrationError(f"required ordinary file missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _event_schema_for_version(version: str) -> str:
    try:
        parts = tuple(int(part) for part in version.split("."))
    except (AttributeError, ValueError) as exc:
        raise common.IntegrationError(f"invalid verified app version for event assessment: {version!r}") from exc
    if len(parts) != 3 or any(part < 0 for part in parts):
        raise common.IntegrationError(f"invalid verified app version for event assessment: {version!r}")
    return "legacy" if parts < STARTUP_EVENT_VERSION else STARTUP_EVENT_SCHEMA


def _private_files(version: str, source: Path | None = None) -> tuple[str, ...]:
    _event_schema_for_version(version)  # Validate the same version syntax as inspection.
    if tuple(map(int, version.split("."))) < (0, 9, 0):
        return PRIVATE_FILES
    config = source / "theme-config.json" if source is not None else None
    if config is None or not config.exists():
        return PRIVATE_FILES + ("entry-avatar.png",)
    try:
        identity = json.loads(config.read_text(encoding="utf-8"))["identity"]
        selected = []
        for key in ("iconInput", "entryAvatarInput"):
            value = identity[key]
            if not isinstance(value, str) or "\\" in value:
                raise ValueError(key)
            path = PurePosixPath(value)
            if (path.is_absolute() or path.as_posix() != value or len(path.parts) < 3
                    or path.parts[:2] != ("assets", "private") or any(p in ("", ".", "..") for p in path.parts)):
                raise ValueError(key)
            selected.append(PurePosixPath(*path.parts[2:]).as_posix())
        if selected[0] == selected[1]:
            raise ValueError("identity images must be distinct")
        return tuple(dict.fromkeys((*PRIVATE_FILES[:3], *selected)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise common.IntegrationError(f"invalid theme private identity inputs: {exc}") from exc


def _private_manifest(directory: Path, files: tuple[str, ...] = PRIVATE_FILES) -> dict[str, str]:
    directory = _directory(directory)
    result = {}
    for name in files:
        path = directory / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise common.IntegrationError(f"private asset path is a symlink: {name}")
        result[name] = _hash(path)
    return result


def _verify_packaged_sources(bundle: Path, native_root: Path, info: dict[str, Any], marker: dict[str, Any]) -> str:
    resources = bundle / "Contents/Resources"
    inputs = marker.get("inputs", {})
    version = info.get("CFBundleShortVersionString", "")
    if _event_schema_for_version(version) != "legacy":
        for name in ("assets/private/working.png", "assets/private/scene.js"):
            packaged_source = resources / "web" / name
            if packaged_source.exists() or packaged_source.is_symlink():
                raise common.IntegrationError(f"private startup source must not be copied into the web payload: {name}")
        for name in _private_files(version, native_root):
            relative = "assets/private/" + name
            if inputs.get(relative) != _hash(native_root / relative):
                raise common.IntegrationError(f"built private input differs from its frozen source: {name}")
        return "native identity, marker, signature, icon, wallpaper, startup defaults and private source hashes"

    for name in ("index.html", "style.css", "animation.js", "assets/private/working.png", "assets/private/scene.js"):
        if _hash(resources / "web" / name) != inputs.get(name):
            raise common.IntegrationError(f"installed web resource differs from its build marker: {name}")
    return "native identity, marker, signature, icon, wallpaper and installed web hashes"


def _plan(action: str, **values: Any) -> dict[str, Any]:
    result = {"schema": "azhou-hub.animation-plan.v1", "component": COMPONENT,
              "action": action, **values}
    result["plan_id"] = common.plan_digest(result)
    return result


def _approval(plan: dict[str, Any], plan_id: str | None) -> None:
    if not plan_id or plan_id != plan["plan_id"]:
        raise common.IntegrationError("apply requires the exact current plan_id; regenerate after source, input or target changes")


def _mac() -> None:
    if platform.system() != "Darwin":
        raise common.IntegrationError("this fixed integration supports macOS only")


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 90) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout, check=False)
    return {"command": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def _successful(result: dict[str, Any]) -> None:
    if result["returncode"]:
        raise common.IntegrationError(f"native command failed ({result['returncode']}): {result['stderr'][-3000:]} {result['stdout'][-3000:]}")


def build_plan(source: Path, workspace: Path, private_assets: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    origin = common.inspect_source(COMPONENT, source, hub_root=hub_root)
    workspace = _directory(workspace, exists=False)
    if workspace == Path(origin["source"]) or Path(origin["source"]) in workspace.parents:
        raise common.IntegrationError("build workspace must be outside the read-only source")
    assets = _private_manifest(private_assets, _private_files(origin["version"], Path(origin["source"])))
    lock = common.load_lock(COMPONENT, hub_root=hub_root)
    snapshot = state.state_path(workspace, "hub", "sources", COMPONENT, common.plan_digest(lock))
    return _plan("build", source=origin, workspace=str(workspace), private_assets=str(private_assets),
                 private_inputs=assets, snapshot=str(snapshot),
                 output=str(snapshot / ".build/azhou-payload"),
                 command=["bash", "tools/build-macos.sh"],
                 scope="isolated build only; no user Applications write, registration or host launch",
                 private_distribution="private inputs and generated outputs stay in ignored local state",
                 git_metadata="a new empty local Git database is used only for the native ignore checks; it is not source history")


def build(source: Path, workspace: Path, private_assets: Path, plan_id: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    plan = build_plan(source, workspace, private_assets, hub_root=hub_root)
    _approval(plan, plan_id)
    _mac()
    for name in ("/usr/bin/xcrun", "/usr/bin/codesign", "/usr/bin/sips", "/usr/bin/iconutil"):
        if not os.access(name, os.X_OK):
            raise common.IntegrationError(f"native build dependency missing: {name}")
    snapshot = common.snapshot_source(COMPONENT, source, workspace, hub_root=hub_root,
                                      expected_digest=plan["source"]["source_lock_sha256"])
    for name, digest in plan["private_inputs"].items():
        origin, target = Path(private_assets) / name, snapshot / "assets/private" / name
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise common.IntegrationError(f"isolated private asset path is a symlink: {name}")
        data = origin.read_bytes()
        if origin.is_symlink() or hashlib.sha256(data).hexdigest() != digest:
            raise common.IntegrationError(f"private input changed after plan: {name}")
        if target.exists() or target.is_symlink():
            if _hash(target) != digest:
                raise common.IntegrationError(f"existing isolated private input differs: {name}; use a new workspace")
        else:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as handle:
                handle.write(data)
            target.chmod(0o600)
    if _private_manifest(Path(private_assets), tuple(plan["private_inputs"])) != plan["private_inputs"]:
        raise common.IntegrationError("private inputs changed while preparing the isolated build")
    common.verify_snapshot(COMPONENT, snapshot, hub_root=hub_root)
    if (snapshot / ".git").is_symlink():
        raise common.IntegrationError("isolated build Git metadata is a symlink")
    if not (snapshot / ".git").exists():
        _successful(_run(["git", "init", "--quiet", str(snapshot)]))
    result = _run(plan["command"], cwd=snapshot, timeout=300)
    record = {"schema": "azhou-hub.animation-build.v1", "plan": plan, "execution": result,
              "status": "validation-pending" if result["returncode"] == 0 else "failed"}
    common.write_receipt(snapshot / ".hub-build.json", record)
    try:
        _successful(result)
        bundle = inspect_bundle(source, snapshot / ".build/azhou-payload", hub_root=hub_root)
        marker = json.loads((Path(bundle["path"]) / "Contents/Resources/azhou-build.json").read_text(encoding="utf-8"))
        for name, digest in plan["private_inputs"].items():
            if marker.get("inputs", {}).get("assets/private/" + name) != digest:
                raise common.IntegrationError(f"built private input differs from the approved plan: {name}")
    except BaseException as exc:
        record.update(status="failed-validation", error=str(exc))
        common.write_receipt(snapshot / ".hub-build.json", record)
        raise
    record.update(status="built", bundle=bundle, approved_private_inputs_verified=True)
    common.write_receipt(snapshot / ".hub-build.json", record)
    return {"status": "built", "bundle": bundle, "receipt": str(snapshot / ".hub-build.json"),
            "runtime": "not invoked", "visual_review": "pending"}


def inspect_bundle(source: Path, bundle: Path, *, hub_root: Path = ROOT,
                   _cleanup_snapshot_only: bool = False) -> dict[str, Any]:
    """Reuse the locked native validator and independently match build inputs/resources."""
    origin = None if _cleanup_snapshot_only else common.inspect_source(COMPONENT, source, hub_root=hub_root)
    bundle = _directory(bundle)
    marker_path = bundle / "Contents/Resources/azhou-build.json"
    if marker_path.is_symlink():
        raise common.IntegrationError("bundle provenance marker is a symlink")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        native_root = _directory(Path(marker["projectRoot"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise common.IntegrationError(f"invalid native build marker: {exc}") from exc
    if _cleanup_snapshot_only:
        # Removal must remain possible after the independent source advances.
        # Only a previously frozen, exact-lock snapshot can supply executable
        # validation code in this path; never load the changed live source.
        original = _directory(source, exists=False)
        if native_root == original:
            raise common.IntegrationError("test cleanup requires the frozen build snapshot, not the live source")
        snapshot_record = common.read_receipt(native_root / ".hub-source.json")
        snapshot_component = snapshot_record.get("component")
        if snapshot_component not in (COMPONENT, LEGACY_COMPONENT):
            raise common.IntegrationError("cleanup snapshot has an unknown package owner")
        expected_original = Path(hub_root).resolve() / "packages" / common.PACKAGES[snapshot_component]
        if original != expected_original:
            raise common.IntegrationError("cleanup source does not match the snapshot's original package owner")
        origin = common.verify_snapshot(snapshot_component, native_root, hub_root=hub_root)
        if (snapshot_record.get("schema") != "azhou-hub.integration-snapshot.v1"
                or snapshot_record.get("source") != str(original)):
            raise common.IntegrationError("cleanup snapshot does not belong to the explicitly selected original source")
        origin.update(source=str(original), scope="cleanup uses only the locked frozen source; live source state is not consulted")
    elif native_root != Path(origin["source"]):
        verified = common.verify_snapshot(COMPONENT, native_root, hub_root=hub_root)
        if verified["source_lock_sha256"] != origin["source_lock_sha256"]:
            raise common.IntegrationError("bundle was built from different package inputs; rebuild before installing")
        if common.read_receipt(native_root / ".hub-source.json").get("source") != origin["source"]:
            raise common.IntegrationError("bundle snapshot belongs to a different package checkout; rebuild before installing")
    lock = (common.snapshot_lock(snapshot_component, native_root) if _cleanup_snapshot_only
            else common.snapshot_lock(COMPONENT, native_root) if (native_root / ".hub-source.json").exists()
            else common.load_lock(COMPONENT, hub_root=hub_root))
    inputs = marker.get("inputs", {})
    for name in lock["build_inputs"]:
        if inputs.get(name) != lock["files"][name]["sha256"]:
            raise common.IntegrationError(f"installed build input differs from selected source: {name}")
    helpers = runpy.run_path(str(native_root / "tools/verify-artifacts.py"))
    try:
        info = helpers["verify_product"](bundle)
        marker = helpers["read_marker"](bundle, required=True)
        fingerprint = helpers["fingerprint"](bundle)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise common.IntegrationError(f"native bundle verification failed: {exc}") from exc
    if (info.get("CFBundleShortVersionString"), str(info.get("CFBundleVersion"))) != (lock["runtime_version"], lock["runtime_build"]):
        raise common.IntegrationError("bundle version does not match the selected fixed source")
    event_schema = _event_schema_for_version(str(info["CFBundleShortVersionString"]))
    verification = _verify_packaged_sources(bundle, native_root, info, marker)
    return {"path": str(bundle), "native_source_root": str(native_root), "source": origin,
            "bundle_id": info["CFBundleIdentifier"], "executable": info["CFBundleExecutable"],
            "version": info["CFBundleShortVersionString"], "build": str(info["CFBundleVersion"]),
            "event_schema": event_schema,
            "sha256_tree": fingerprint, "input_sha256": marker["inputSHA256"],
            "verification": verification,
            "limits": "build marker/signature do not independently prove binary reproducibility; invocation and visual review are separate"}


def _test_paths(workspace: Path, component: str = COMPONENT) -> tuple[Path, Path]:
    if component not in (COMPONENT, LEGACY_COMPONENT):
        raise common.IntegrationError("unknown Hub test-installation component")
    workspace = _directory(workspace, exists=False)
    directory = state.state_path(workspace, "hub", "test-installations", component)
    name = LEGACY_APP_NAME if component == LEGACY_COMPONENT else APP_NAME
    return directory / name, directory / "receipt.json"


def _reject_legacy_test_owner(workspace: Path) -> None:
    target, record = _test_paths(workspace, LEGACY_COMPONENT)
    if target.exists() or target.is_symlink() or record.exists() or record.is_symlink():
        raise common.IntegrationError(
            "legacy startup-animation test installation still occupies this workspace; "
            "remove it with the agent-skin test-uninstall command before creating a new test installation")


def _owned_test(workspace: Path) -> tuple[Path, Path, dict[str, Any], str]:
    owned = []
    for component in (COMPONENT, LEGACY_COMPONENT):
        target, record = _test_paths(workspace, component)
        allowed_targets = {record.parent / APP_NAME, record.parent / LEGACY_APP_NAME}
        present_targets = {path for path in allowed_targets if path.exists() or path.is_symlink()}
        if record.exists() or record.is_symlink() or present_targets:
            receipt = common.read_receipt(record)
            raw_target = receipt.get("path")
            target = Path(raw_target) if isinstance(raw_target, str) else None
            if (receipt.get("schema") != "azhou-hub.animation-test-install.v1"
                    or receipt.get("component") != component or target not in allowed_targets
                    or present_targets - {target}):
                raise common.IntegrationError("test-installation ownership does not match this workspace")
            owned.append((target, record, receipt, component))
    if len(owned) != 1:
        raise common.IntegrationError("test-installation ownership is missing or ambiguous in this workspace")
    return owned[0]


def _registry_inventory(tool: Path) -> dict[str, list[str]]:
    result = _run([str(tool), "inventory"])
    _successful(result)
    try:
        value = json.loads(result["stdout"])
        groups = value["applications"]
        if value.get("schema") != 1 or len(groups) != len(REGISTRY_IDS):
            raise ValueError("unknown inventory shape")
        inventory = {}
        for group in groups:
            identifier = group["bundleID"]
            if identifier not in REGISTRY_IDS or identifier in inventory:
                raise ValueError("unexpected or repeated bundle identity")
            urls = group["urls"]
            paths = [item["path"] for item in urls]
            if any(not isinstance(path, str) or not Path(path).is_absolute() for path in paths):
                raise ValueError("registry contains a non-absolute application path")
            inventory[identifier] = sorted(set(paths))
        if set(inventory) != set(REGISTRY_IDS):
            raise ValueError("incomplete project identity coverage")
        return inventory
    except (ValueError, KeyError, TypeError) as exc:
        raise common.IntegrationError(f"invalid native application inventory: {exc}") from exc


def _registration_plan(native_root: Path, target: Path) -> dict[str, Any]:
    tool = native_root / ".build/azhou-install-registry"
    if any(path.is_symlink() for path in (tool, *tool.parents)) or not os.access(tool, os.X_OK):
        raise common.IntegrationError("the verified native registry helper is missing or uses a symlink")
    digest = _hash(tool)
    before = _registry_inventory(tool)
    expected = {identifier: [path for path in paths if path != str(target)]
                for identifier, paths in before.items()}
    return {"tool": str(tool), "tool_sha256": digest, "before": before, "expected_after": expected,
            "unregister_command": [LSREGISTER, "-u", str(target)] if before != expected else [],
            "scope": "remove only this receipt-owned test app's exact URL; preserve every other project registration",
            "mechanism": "current macOS lsregister path operation, followed by public NSWorkspace URL inventory; no reset, scan, or canonical registration"}


def _require_stopped(target: Path) -> None:
    process = _run(["/bin/ps", "-axo", "pid=,comm="])
    _successful(process)
    prefix = str(target / "Contents/MacOS") + "/"
    if any(line.strip().split(None, 1)[-1].startswith(prefix) for line in process["stdout"].splitlines() if line.strip()):
        raise common.IntegrationError("the test app is still running; preserved")


def test_install_plan(source: Path, payload: Path, workspace: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    workspace = _directory(workspace, exists=False)
    _reject_legacy_test_owner(workspace)
    verified = inspect_bundle(source, payload, hub_root=hub_root)
    if Path(verified["native_source_root"]) == Path(verified["source"]["source"]):
        raise common.IntegrationError(
            "test installation requires the frozen build snapshot; a payload built directly in the live "
            "package has no frozen cleanup snapshot and could never be test-uninstalled — build through "
            "the Hub build command first")
    workspace = _directory(workspace, exists=False)
    source_root = Path(verified["source"]["source"])
    if workspace == source_root or source_root in workspace.parents:
        raise common.IntegrationError("test workspace must be outside the read-only source")
    if payload != Path(verified["native_source_root"]) / ".build/azhou-payload":
        raise common.IntegrationError("test installation accepts only the native hidden build payload")
    target, record = _test_paths(workspace)
    current = False
    if target.exists() or target.is_symlink() or record.exists() or record.is_symlink():
        owned_target, _, receipt, _ = _owned_test(workspace)
        if owned_target != target:
            raise common.IntegrationError("test installation uses the old application name; remove it with test-uninstall first")
        installed = inspect_bundle(source, target, hub_root=hub_root)
        if receipt.get("sha256_tree") != installed["sha256_tree"] or installed["sha256_tree"] != verified["sha256_tree"]:
            raise common.IntegrationError("existing test installation changed or belongs to another build; preserve it")
        current = True
    return _plan("test-install", payload=verified, workspace=str(workspace), target=str(target), current=current,
                 scope="one Hub-owned isolated test app; no explicit Launch Services registration or user Applications writes",
                 system_side_effect="macOS can register an app even when its executable is started directly; test-uninstall verifies and removes this exact registration",
                 production_install="not performed")


def test_install(source: Path, payload: Path, workspace: Path, plan_id: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    plan = test_install_plan(source, payload, workspace, hub_root=hub_root)
    _approval(plan, plan_id)
    target, record = _test_paths(workspace)
    if plan["current"]:
        return {"status": "current", "path": str(target), "receipt": str(record), "scope": "test installation"}
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.ensure_private_directory(target.parent, root=workspace)
    stage = Path(tempfile.mkdtemp(prefix=".test-install-", dir=target.parent))
    staged = stage / "payload"
    installed = False
    try:
        shutil.copytree(payload, staged)
        verified = inspect_bundle(source, staged, hub_root=hub_root)
        if verified["sha256_tree"] != plan["payload"]["sha256_tree"] or inspect_bundle(source, payload, hub_root=hub_root)["sha256_tree"] != verified["sha256_tree"]:
            raise common.IntegrationError("payload changed during test installation")
        if target.exists() or target.is_symlink() or record.exists() or record.is_symlink():
            raise common.IntegrationError("test installation target became occupied")
        _reject_legacy_test_owner(workspace)
        staged.rename(target)
        installed = True
        common.write_receipt(record, {"schema": "azhou-hub.animation-test-install.v1", "component": COMPONENT,
                             "path": str(target), "sha256_tree": verified["sha256_tree"], "plan_id": plan["plan_id"],
                             "source_lock_sha256": verified["source"]["source_lock_sha256"],
                             "ownership": "this isolated test app only; source installer retains production ownership"})
    except BaseException:
        if installed:
            target.rename(staged)
        raise
    finally:
        shutil.rmtree(stage)
    return {"status": "test-installed", "path": str(target), "receipt": str(record),
            "host_discovery": "not measured", "runtime": "not invoked", "production_install": "not performed"}


def test_uninstall_plan(source: Path, workspace: Path, *, hub_root: Path = ROOT) -> dict[str, Any]:
    workspace = _directory(workspace, exists=False)
    source_root = _directory(source, exists=False)
    if workspace == source_root or source_root in workspace.parents:
        raise common.IntegrationError("test workspace must be outside the read-only source")
    target, record, receipt, component = _owned_test(workspace)
    cleanup_source = Path(hub_root).resolve() / "packages" / common.PACKAGES[component]
    verified = inspect_bundle(cleanup_source, target, hub_root=hub_root, _cleanup_snapshot_only=True)
    if receipt.get("sha256_tree") != verified["sha256_tree"] or receipt.get("source_lock_sha256") != verified["source"]["source_lock_sha256"]:
        raise common.IntegrationError("test installation differs from ownership receipt; preserved")
    return _plan("test-uninstall", target=verified, workspace=str(workspace), receipt=str(record),
                 registry=_registration_plan(Path(verified["native_source_root"]), target),
                 scope="only the exact Hub-owned test app, its own system registration and its receipt")


def test_uninstall(source: Path, workspace: Path, plan_id: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    plan = test_uninstall_plan(source, workspace, hub_root=hub_root)
    _approval(plan, plan_id)
    target, record, _, component = _owned_test(workspace)
    _require_stopped(target)
    if test_uninstall_plan(source, workspace, hub_root=hub_root)["plan_id"] != plan["plan_id"]:
        raise common.IntegrationError("test app changed before removal; preserved")
    registration = plan["registry"]
    tool = Path(registration["tool"])
    if registration["unregister_command"]:
        _successful(_run(registration["unregister_command"]))
    after = _registry_inventory(tool)
    if after != registration["expected_after"]:
        raise common.IntegrationError("test registration removal did not preserve the expected other application entries; test app and receipt retained")
    cleanup_source = Path(hub_root).resolve() / "packages" / common.PACKAGES[component]
    if inspect_bundle(cleanup_source, target, hub_root=hub_root, _cleanup_snapshot_only=True)["sha256_tree"] != plan["target"]["sha256_tree"]:
        raise common.IntegrationError("test app changed during registration cleanup; preserved")
    _require_stopped(target)
    shutil.rmtree(target)
    final = _registry_inventory(tool)
    if final != registration["expected_after"]:
        # Retain ownership evidence for exact-path recovery; do not reset or
        # re-register any production entry to hide an unexpected OS result.
        raise common.IntegrationError("test files removed but registration did not remain clean; ownership receipt retained for exact-path review")
    record.unlink()
    return {"status": "test-uninstalled", "removed": [str(target), str(record)],
            "registry_before": registration["before"], "registry_after": final,
            "unregister_command": registration["unregister_command"],
            "source_and_production": "files unchanged; other registered project paths preserved"}


def execution_plan(source: Path, bundle: Path, mode: str, *, target_pid: int | None = None,
                   target_bundle: Path | None = None, hub_root: Path = ROOT) -> dict[str, Any]:
    verified = inspect_bundle(source, bundle, hub_root=hub_root)
    command = [str(bundle / "Contents/MacOS" / EXECUTABLE)]
    scopes = {"smoke": "one-shot player preview; no target launch or wallpaper application",
              "probe": "read-only target identity/running-process probe",
              "launch": "verified Codex startup assessment; hot activation, startup readiness and skip are reported separately from wallpaper",
              "wallpaper-status": "read-only live wallpaper and optional startup status; no launch, injection, registration or log write",
              "disable-wallpaper": "remove the Agent Skin startup controller and wallpaper from the verified current page; saved settings, host process and debugging port remain"}
    if mode not in scopes:
        raise common.IntegrationError("unknown native operation")
    if mode in ("smoke", "probe", "wallpaper-status"):
        command.append({"smoke": "--smoke-test", "probe": "--probe", "wallpaper-status": "--wallpaper-status"}[mode])
    if mode == "disable-wallpaper":
        if not target_pid or target_pid <= 0 or target_bundle is None:
            raise common.IntegrationError("wallpaper restore requires an explicit positive target PID and absolute target app path")
        command.extend(["--wallpaper-helper", "--action", "restore", "--target-pid", str(target_pid),
                        "--target-bundle", str(_directory(target_bundle))])
    effects = ["player may create its per-user singleton lock under the macOS temporary directory"] if mode == "smoke" else []
    if mode in ("launch", "disable-wallpaper"):
        effects.append("native helper may write ~/Library/Logs/AzhouCodexStartup/{wallpaper.jsonl,latest.json}")
    if mode == "launch":
        effects.append("cold launch may enable a positive loopback debugging port for the lifetime of the Codex process; warm launch never restarts it")
    event_schema = verified.get("event_schema") or _event_schema_for_version(str(verified.get("version", "")))
    return _plan(mode, bundle=verified, command=command, scope=scopes[mode], effects=effects,
                 event_schema=event_schema,
                 limits="no other harness adapter; launch readiness does not prove playback completion; visual review remains separate")


def _events(output: str) -> list[dict[str, Any]]:
    result = []
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and isinstance(item.get("event"), str):
            result.append(item)
    return result


def _versioned_events(output: str, launcher_path: str,
                      consumed_names: frozenset[str]) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    previous_seconds = -1.0
    for line_number, line in enumerate(output.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            errors.append(f"line {line_number}: malformed JSON")
            continue
        if not isinstance(item, dict):
            errors.append(f"line {line_number}: event is not an object")
            continue
        name = item.get("event")
        if not isinstance(name, str) or not name:
            errors.append(f"line {line_number}: missing event name")
            continue
        events.append(item)
        if name not in consumed_names:
            if name not in _VERSIONED_DIAGNOSTIC_EVENTS:
                errors.append(f"line {line_number}: unsupported diagnostic event")
            elif ("launcherPath" in item and item.get("launcherPath") != launcher_path):
                errors.append(f"line {line_number}: diagnostic launcher path differs from verified bundle")
            elif "launcherPID" in item and (isinstance(item["launcherPID"], bool)
                                              or not isinstance(item["launcherPID"], int)
                                              or item["launcherPID"] <= 0):
                errors.append(f"line {line_number}: invalid diagnostic launcher PID")
            continue
        seconds = item.get("seconds")
        pid = item.get("launcherPID")
        if item.get("schema") != STARTUP_EVENT_SCHEMA:
            errors.append(f"line {line_number}: unsupported event schema")
        try:
            numeric_seconds = float(seconds)
            valid_seconds = (not isinstance(seconds, bool) and isinstance(seconds, (int, float))
                             and math.isfinite(numeric_seconds) and numeric_seconds >= previous_seconds)
        except (OverflowError, TypeError, ValueError):
            valid_seconds = False
            numeric_seconds = -1.0
        if not valid_seconds:
            errors.append(f"line {line_number}: invalid monotonic seconds")
        else:
            previous_seconds = numeric_seconds
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            errors.append(f"line {line_number}: invalid launcher PID")
        if item.get("launcherPath") != launcher_path:
            errors.append(f"line {line_number}: launcher path differs from verified bundle")
        for key in ("targetPID", "runId"):
            if key in item:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    errors.append(f"line {line_number}: invalid event {key}")

        if isinstance(name, str) and name in {"target-opened", "target-activated", "startup-installed", "startup-ready", "startup-skipped"}:
            target_pid = item.get("targetPID")
            if isinstance(target_pid, bool) or not isinstance(target_pid, int) or target_pid <= 0:
                errors.append(f"line {line_number}: invalid target PID")
        if isinstance(name, str) and name in {"startup-installed", "startup-ready", "startup-skipped"}:
            run_id = item.get("runId")
            if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
                errors.append(f"line {line_number}: invalid startup run ID")
        if (name == "startup-ready" and (item.get("ready") is not True
                or not isinstance(item.get("phase"), str)
                or item.get("phase") not in {"playing", "settings", "complete"})):
            errors.append(f"line {line_number}: startup-ready does not match a ready controller phase")
        if name == "startup-skipped":
            completion = item.get("completion")
            if (item.get("completed") is not True or item.get("overlay") is not False
                    or not isinstance(completion, dict) or completion.get("cause") != "skip"
                    or not isinstance(completion.get("beforeReady"), bool)):
                errors.append(f"line {line_number}: startup-skipped does not match a completed skip")
        if isinstance(name, str) and name in {"startup-interrupted", "startup-failed"}:
            reason = item.get("reason")
            if not isinstance(reason, str) or not reason:
                errors.append(f"line {line_number}: missing startup failure reason")
        if name == "startup-port-error":
            reason = item.get("reason")
            operation = item.get("operation")
            error_number = item.get("errno")
            if not isinstance(reason, str) or not reason:
                errors.append(f"line {line_number}: missing startup port failure reason")
            if (not isinstance(operation, str)
                    or operation not in {"socket", "close-on-exec", "bind-loopback", "getsockname"}):
                errors.append(f"line {line_number}: invalid startup port failure operation")
            if isinstance(error_number, bool) or not isinstance(error_number, int) or error_number <= 0:
                errors.append(f"line {line_number}: invalid startup port failure errno")
        if name == "launcher-exit":
            outcome = item.get("outcome")
            exit_code = item.get("exitCode")
            allowed = {"activated": 0, "startup-ready": 0, "skipped": 0,
                       "partial": 2, "behavior-not-proven": 1}
            if (not isinstance(outcome, str) or outcome not in allowed
                    or isinstance(exit_code, bool) or not isinstance(exit_code, int)
                    or (isinstance(outcome, str) and outcome in allowed and exit_code != allowed[outcome])):
                errors.append(f"line {line_number}: invalid launcher exit outcome")
    return events, errors


def _versioned_launch_assessment(events: list[dict[str, Any]], errors: list[str], result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    not_proven = {"status": "not-attempted", "injection": "not-proven", "installed": False}
    returncode = result.get("returncode")
    if (errors or not events or isinstance(returncode, bool) or not isinstance(returncode, int)
            or returncode not in (0, 1, 2)):
        return "behavior-not-proven", not_proven
    consumed = [item for item in events if item.get("event") in _VERSIONED_LAUNCH_EVENTS]
    names = [item.get("event") for item in consumed]
    launcher_pids = {item["launcherPID"] for item in consumed}
    exits = [item for item in consumed if item.get("event") == "launcher-exit"]
    if (len(launcher_pids) != 1 or names.count("launcher-start") != 1
            or names[0] != "launcher-start" or len(exits) != 1 or names[-1] != "launcher-exit"
            or exits[0].get("exitCode") != result.get("returncode")):
        return "behavior-not-proven", not_proven
    failure_event = next((item for item in consumed if item.get("event") in _VERSIONED_FAILURE_EVENTS), None)
    if failure_event is not None:
        reason = failure_event.get("reason")
        if not isinstance(reason, str) or not reason:
            reason = str(failure_event["event"])
        startup_failure = {"status": "failed", "injection": "not-confirmed",
                           "installed": any(item.get("event") == "startup-installed" for item in consumed),
                           "reason": reason}
        if failure_event.get("event") == "startup-port-error":
            startup_failure["operation"] = failure_event["operation"]
            startup_failure["errno"] = failure_event["errno"]
        return "behavior-not-proven", startup_failure

    exit_event = exits[0]
    activations = [item for item in consumed if item.get("event") == "target-activated"]
    opened = [item for item in consumed if item.get("event") == "target-opened"]
    installed = [item for item in consumed if item.get("event") == "startup-installed"]
    outcomes = [item for item in consumed if item.get("event") in {
        "startup-ready", "startup-skipped", "startup-interrupted", "startup-failed"}]

    if activations:
        if (len(activations) != 1 or opened or installed or outcomes
                or exit_event.get("outcome") != "activated" or result.get("returncode") != 0):
            return "behavior-not-proven", not_proven
        return "activated", {"status": "not-attempted", "injection": "not-attempted", "installed": False}

    if len(outcomes) != 1:
        return "behavior-not-proven", not_proven
    terminal = outcomes[0]
    terminal_name = terminal["event"]
    if len(opened) > 1 or len(installed) > 1:
        return "behavior-not-proven", not_proven
    if installed and (not opened or names.index("target-opened") > names.index("startup-installed")):
        return "behavior-not-proven", not_proven
    if opened and names.index("target-opened") > names.index(terminal_name):
        return "behavior-not-proven", not_proven
    if installed and names.index("startup-installed") > names.index(terminal_name):
        return "behavior-not-proven", not_proven
    target_pids = {item["targetPID"] for item in consumed if "targetPID" in item}
    run_ids = {item["runId"] for item in consumed if "runId" in item}
    if len(target_pids) > 1 or len(run_ids) > 1:
        return "behavior-not-proven", not_proven
    if terminal.get("targetPID") is not None and target_pids and terminal["targetPID"] not in target_pids:
        return "behavior-not-proven", not_proven
    if terminal.get("runId") is not None and run_ids and terminal["runId"] not in run_ids:
        return "behavior-not-proven", not_proven
    if terminal_name == "startup-ready":
        if (len(opened) != 1 or len(installed) != 1 or names.index("target-opened") > names.index("startup-installed")
                or names.index("startup-installed") > names.index("startup-ready")
                or terminal.get("targetPID") != installed[0].get("targetPID")
                or installed[0].get("targetPID") != opened[0].get("targetPID")
                or terminal.get("runId") != installed[0].get("runId")
                or exit_event.get("outcome") != "startup-ready" or result.get("returncode") != 0):
            return "behavior-not-proven", not_proven
        return "startup-ready", {"status": "ready", "injection": "installed", "installed": True,
                                 "runId": terminal["runId"], "phase": terminal["phase"], "ready": True}
    if terminal_name == "startup-skipped":
        if (len(opened) != 1 or len(installed) != 1 or names.index("target-opened") > names.index("startup-installed")
                or names.index("startup-installed") > names.index("startup-skipped")
                or terminal.get("targetPID") != installed[0].get("targetPID")
                or installed[0].get("targetPID") != opened[0].get("targetPID")
                or terminal.get("runId") != installed[0].get("runId")
                or exit_event.get("outcome") != "skipped" or result.get("returncode") != 0):
            return "behavior-not-proven", not_proven
        return "skipped", {"status": "skipped", "injection": "installed", "installed": True,
                            "runId": terminal["runId"], "completed": True,
                            "overlay": False, "completion": terminal["completion"]}
    if terminal_name == "startup-interrupted":
        if (exit_event.get("outcome") != "partial" or result.get("returncode") != 2
                or any(item.get("event") in {"startup-ready", "startup-skipped"} for item in consumed)):
            return "behavior-not-proven", not_proven
        return "partial", {"status": "interrupted", "injection": "not-confirmed", "installed": bool(installed),
                            "reason": terminal["reason"]}
    if terminal_name == "startup-failed" and exit_event.get("outcome") == "behavior-not-proven" and result.get("returncode") == 1:
        return "behavior-not-proven", {"status": "failed", "injection": "not-confirmed", "installed": bool(installed),
                                        "reason": terminal["reason"]}
    return "behavior-not-proven", not_proven


def _versioned_smoke_passed(events: list[dict[str, Any]], errors: list[str], result: dict[str, Any]) -> bool:
    if errors or result.get("returncode") != 0:
        return False
    consumed = [item for item in events if item.get("event") in _VERSIONED_SMOKE_EVENTS]
    names = [item.get("event") for item in consumed]
    if len({item["launcherPID"] for item in consumed}) != 1:
        return False
    required = ("player-start", "playback-start", "animation-complete", "preview-result", "player-terminated")
    if any(names.count(name) != 1 for name in required):
        return False
    positions = [names.index(name) for name in required]
    if positions != sorted(positions) or names[-1] != "player-terminated":
        return False
    forbidden = {"target-opened", "target-activated", "target-open-request", "target-reused",
                 "target-activation-request", "startup-installed", "startup-ready", "startup-skipped",
                 "startup-interrupted", "startup-failed", "startup-launcher-start",
                 "target-launch-completion", "launcher-exit", "wallpaper-helper-start",
                 "preview-promoted-to-launch"}
    if forbidden & {item.get("event") for item in events} or _VERSIONED_FAILURE_EVENTS & set(names):
        return False
    preview = consumed[positions[3]]
    terminated = consumed[positions[4]]
    return (preview.get("success") is True and preview.get("error", "") == ""
            and terminated.get("completed") is True
            and terminated.get("failed") is False)


def _wallpaper_assessment(mode: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    if mode in ("smoke", "probe"):
        return {"status": "not-attempted", "live_status_check": "not performed", "startup": None}
    latest: dict[str, Any] | None = None
    attempted = False
    for item in events:
        name = item.get("event")
        if not isinstance(name, str):
            continue
        if name == "wallpaper-helper-start":
            attempted = True
        elif name == "wallpaper-helper-complete" and isinstance(item.get("result"), dict):
            latest = item["result"]
        elif name in ("wallpaper-result", "wallpaper-port-unavailable"):
            latest = item
        elif name == "wallpaper-helper-failed":
            latest = {"state": "helper-failed", "applied": False}
        elif name == "handoff-fade-start" and isinstance(item.get("wallpaper"), dict):
            latest = item["wallpaper"]
    if latest is None:
        status = "pending" if attempted else "not-attempted"
    elif latest.get("state") == "needs-restart":
        status = "needs-restart"
    elif latest.get("state") == "pending":
        status = "pending"
    elif mode == "disable-wallpaper" and latest.get("restored") is True:
        status = "restored"
    elif latest.get("state") == "applied" and latest.get("applied") is True:
        status = "live-verified" if mode == "wallpaper-status" else "reported-applied"
    elif latest.get("state") == "not-applied":
        status = "not-applied"
    else:
        status = "failed"
    return {"status": status, "native_state": latest.get("state") if latest else None,
            "live_status_check": "performed" if mode == "wallpaper-status" else "not performed",
            "startup": latest.get("startup") if isinstance(latest, dict) and isinstance(latest.get("startup"), dict) else None}


def assess_execution(mode: str, result: dict[str, Any], bundle: Path, *,
                     verified_bundle: dict[str, Any]) -> dict[str, Any]:
    version = str(verified_bundle.get("version", ""))
    event_schema = _event_schema_for_version(version)
    if event_schema == STARTUP_EVENT_SCHEMA and mode in ("launch", "smoke", "probe"):
        launcher_path = str(verified_bundle.get("path", bundle))
        consumed_names = {"launch": _VERSIONED_LAUNCH_EVENTS, "smoke": _VERSIONED_SMOKE_EVENTS,
                          "probe": _VERSIONED_PROBE_EVENTS}[mode]
        events, errors = _versioned_events(result.get("stdout", ""), launcher_path, consumed_names)
        if mode == "launch":
            status, startup = _versioned_launch_assessment(events, errors, result)
            playback_completion = "unobserved"
            launcher_status = status
        elif mode == "smoke":
            passed = _versioned_smoke_passed(events, errors, result)
            status = launcher_status = "behavior-passed" if passed else "behavior-not-proven"
            startup = {"status": "not-run", "injection": "not-attempted"}
            playback_completion = "completed" if passed else "unproven"
        else:
            probes = [item for item in events if item.get("event") == "probe"]
            passed = (not errors and result.get("returncode") == 0 and len(probes) == 1
                      and len({item["launcherPID"] for item in probes}) == 1
                      and not _VERSIONED_FAILURE_EVENTS.intersection(item.get("event") for item in events)
                      and probes[0].get("targetBundleID") == "com.openai.codex")
            status = "behavior-passed" if passed else "behavior-not-proven"
            launcher_status = "not-run"
            startup = {"status": "not-run", "injection": "not-attempted"}
            playback_completion = "unobserved"
    else:
        events = _events(result.get("stdout", ""))
        names = {item["event"] for item in events}
        passed = result.get("returncode") == 0
        if mode in ("smoke", "launch"):
            required = {"player-start", "playback-start", "animation-complete", "player-terminated"}
            required |= {"preview-result"} if mode == "smoke" else {"target-activation-request", "handoff-fade-complete"}
            passed &= required <= names and not {"failure", "duplicate-entry", "lock-error"} & names
            passed &= all(item.get("launcherPath") == str(bundle) for item in events)
            passed &= any(item["event"] == "player-terminated" and item.get("completed") is True and item.get("failed") is False for item in events)
            if mode == "smoke":
                passed &= not {"target-open-request", "target-reused", "wallpaper-helper-start", "preview-promoted-to-launch"} & names
                passed &= any(item["event"] == "preview-result" and not item.get("error") for item in events)
            else:
                passed &= bool({"target-reused", "target-launch-completion"} & names)
                passed &= any(item["event"] == "target-activation-request" and item.get("allowed") is True for item in events)
        elif mode == "probe":
            passed &= any(item["event"] == "probe" and item.get("launcherPath") == str(bundle)
                          and item.get("targetBundleID") == "com.openai.codex" for item in events)
        else:
            flag = "restored" if mode == "disable-wallpaper" else "applied"
            passed &= any(item["event"] == "wallpaper-result" and item.get(flag) is True for item in events)
        launcher_status = ("behavior-passed" if passed else "behavior-not-proven") if mode in ("smoke", "launch") else "not-run"
        status = "behavior-passed" if passed else "behavior-not-proven"
        if mode == "launch" and passed:
            status = "runtime-events-passed" if _wallpaper_assessment(mode, events)["status"] == "reported-applied" else "partial"
        startup = {"schema": "legacy" if event_schema == "legacy" else event_schema,
                   "status": "not-assessed" if mode == "launch" and event_schema == "legacy" else "not-run"}
        playback_completion = "completed" if mode == "smoke" and passed else "unobserved"

    wallpaper = _wallpaper_assessment(mode, events)
    if mode == "wallpaper-status" and wallpaper["startup"] is not None:
        startup = wallpaper["startup"]
    return {"status": status, "mode": mode, "event_schema": event_schema,
            "launcher_status": launcher_status, "startup": startup,
            "playback_completion": playback_completion,
            "wallpaper_status": wallpaper["status"], "wallpaper_evidence": wallpaper,
            "events": events, "event_errors": errors if event_schema == STARTUP_EVENT_SCHEMA and mode in ("launch", "smoke", "probe") else [],
            "execution": result, "visual_review": "pending",
            "limits": "native event evidence; no model readiness, visual quality or speed claim"}


def native_plan(source: Path, operation: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    origin = common.inspect_source(COMPONENT, source, hub_root=hub_root)
    return _plan("native-" + operation, source=origin, target=str(Path.home() / "Applications" / APP_NAME),
                 native_install_command=["bash", str(source / "tools/install-macos.sh")],
                 native_check_command=[sys.executable, "-B", str(source / "tools/install-macos.py"), "--check"],
                 status="blocked_source_contract",
                 blockers=["the native installer has no alternate destination parameter and writes source .build/.local",
                           "production ownership and projectRoot must remain with its native installer",
                           "the native installer exposes no uninstall operation"],
                 required_source_change="separate source-owner task: explicit state/build/destination contract with preserved provenance and native rollback; no source modification in this Hub change",
                 recovery="native atomic replacement restores the previous canonical package on validation failure; do not delete ownership records or unverified apps",
                 disable="use the original official Codex entry; live wallpaper restore is a separate explicit command",
                 source_policy="read-only; Hub does not execute this production mutation")


def main(argv: list[str] | None = None, *, hub_root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("check-source", "build", "test-install", "test-uninstall", "inspect", "run", "native-check", "install-plan", "uninstall-plan"):
        command = sub.add_parser(name)
        command.add_argument("--source", type=Path, default=hub_root / "packages" / common.PACKAGES[COMPONENT],
                             help="defaults to this Hub's in-repository animation package")
        if name in ("build", "test-install", "test-uninstall"):
            command.add_argument("--workspace", type=Path, required=True)
        if name == "build":
            command.add_argument("--private-assets", type=Path, required=True)
        if name == "test-install":
            command.add_argument("--payload", type=Path, required=True)
        if name in ("inspect", "run"):
            command.add_argument("--bundle", type=Path, required=True)
        if name == "run":
            command.add_argument("--mode", choices=("smoke", "probe", "launch", "wallpaper-status", "disable-wallpaper"), required=True)
            command.add_argument("--target-pid", type=int)
            command.add_argument("--target-bundle", type=Path)
            command.add_argument("--evidence", type=Path)
        if name in ("build", "test-install", "test-uninstall", "run"):
            command.add_argument("--apply", action="store_true")
            command.add_argument("--plan-id")
    args = parser.parse_args(argv)
    try:
        if args.action == "check-source":
            result = common.inspect_source(COMPONENT, args.source, hub_root=hub_root)
        elif args.action == "build":
            result = (build(args.source, args.workspace, args.private_assets, args.plan_id, hub_root=hub_root) if args.apply
                      else build_plan(args.source, args.workspace, args.private_assets, hub_root=hub_root))
        elif args.action == "test-install":
            result = (test_install(args.source, args.payload, args.workspace, args.plan_id, hub_root=hub_root) if args.apply
                      else test_install_plan(args.source, args.payload, args.workspace, hub_root=hub_root))
        elif args.action == "test-uninstall":
            result = (test_uninstall(args.source, args.workspace, args.plan_id, hub_root=hub_root) if args.apply
                      else test_uninstall_plan(args.source, args.workspace, hub_root=hub_root))
        elif args.action == "inspect":
            result = inspect_bundle(args.source, args.bundle, hub_root=hub_root)
        elif args.action == "run":
            result = execution_plan(args.source, args.bundle, args.mode, target_pid=args.target_pid,
                                    target_bundle=args.target_bundle, hub_root=hub_root)
            evidence = None
            if args.evidence:
                evidence_root = state.state_path(hub_root, "hub")
                if not args.evidence.is_absolute():
                    raise common.IntegrationError("execution evidence requires an absolute path under this Hub's .azhou/hub")
                try:
                    relative = args.evidence.relative_to(evidence_root)
                except ValueError as exc:
                    raise common.IntegrationError("execution evidence must remain in this Hub's ignored .azhou/hub directory") from exc
                evidence = state.relative_path(evidence_root, relative)
                result.pop("plan_id")
                result["evidence_path"] = str(evidence)
                result["plan_id"] = common.plan_digest(result)
            if args.apply:
                _approval(result, args.plan_id)
                _mac()
                plan = result
                result = assess_execution(args.mode, _run(plan["command"], timeout=60),
                                          Path(plan["bundle"]["path"]), verified_bundle=plan["bundle"])
                result["plan_id"] = plan["plan_id"]
                if evidence:
                    common.write_receipt(evidence, result)
        elif args.action == "native-check":
            common.inspect_source(COMPONENT, args.source, hub_root=hub_root)
            _mac()
            result = _run([sys.executable, "-B", str(args.source / "tools/install-macos.py"), "--check"])
            result.update(scope="native read-only production check", status="verified" if result["returncode"] == 0 else "not-verified")
        else:
            result = native_plan(args.source, args.action.removesuffix("-plan"), hub_root=hub_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in ("blocked_source_contract", "behavior-not-proven", "not-verified", "partial") else 0
    except (common.IntegrationError, state.StateError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

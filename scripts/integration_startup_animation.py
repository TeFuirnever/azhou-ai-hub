"""Bounded access to the existing macOS launcher and its separate wallpaper helper.

The source installer owns the user Applications entry. Hub owns only explicitly
created test installations below its ignored workspace state directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
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
COMPONENT = "startup-animation"
APP_NAME = "阿舟启动 Codex.app"
EXECUTABLE = "AzhouCodexStartup"
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


def _private_manifest(directory: Path) -> dict[str, str]:
    directory = _directory(directory)
    result = {}
    for name in PRIVATE_FILES:
        path = directory / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise common.IntegrationError(f"private asset path is a symlink: {name}")
        result[name] = _hash(path)
    return result


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
    assets = _private_manifest(private_assets)
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
    if _private_manifest(Path(private_assets)) != plan["private_inputs"]:
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
        origin = common.verify_snapshot(COMPONENT, native_root, hub_root=hub_root)
        snapshot_record = common.read_receipt(native_root / ".hub-source.json")
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
    lock = (common.snapshot_lock(COMPONENT, native_root) if (native_root / ".hub-source.json").exists()
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
    for name in ("index.html", "style.css", "animation.js", "assets/private/working.png", "assets/private/scene.js"):
        if _hash(bundle / "Contents/Resources/web" / name) != marker["inputs"].get(name):
            raise common.IntegrationError(f"installed web resource differs from its build marker: {name}")
    return {"path": str(bundle), "native_source_root": str(native_root), "source": origin,
            "bundle_id": info["CFBundleIdentifier"], "executable": info["CFBundleExecutable"],
            "version": info["CFBundleShortVersionString"], "build": str(info["CFBundleVersion"]),
            "sha256_tree": fingerprint, "input_sha256": marker["inputSHA256"],
            "verification": "native identity, marker, signature, icon, wallpaper and installed web hashes",
            "limits": "build marker/signature do not independently prove binary reproducibility; invocation and visual review are separate"}


def _test_paths(workspace: Path) -> tuple[Path, Path]:
    workspace = _directory(workspace, exists=False)
    directory = state.state_path(workspace, "hub", "test-installations", COMPONENT)
    return directory / APP_NAME, directory / "receipt.json"


def _owned_test(workspace: Path) -> tuple[Path, Path, dict[str, Any]]:
    target, record = _test_paths(workspace)
    receipt = common.read_receipt(record)
    if (receipt.get("schema") != "azhou-hub.animation-test-install.v1"
            or receipt.get("component") != COMPONENT or receipt.get("path") != str(target)):
        raise common.IntegrationError("test-installation ownership does not match this workspace")
    return target, record, receipt


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
        _, _, receipt = _owned_test(workspace)
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
    target, record, receipt = _owned_test(workspace)
    verified = inspect_bundle(source, target, hub_root=hub_root, _cleanup_snapshot_only=True)
    if receipt.get("sha256_tree") != verified["sha256_tree"] or receipt.get("source_lock_sha256") != verified["source"]["source_lock_sha256"]:
        raise common.IntegrationError("test installation differs from ownership receipt; preserved")
    return _plan("test-uninstall", target=verified, workspace=str(workspace), receipt=str(record),
                 registry=_registration_plan(Path(verified["native_source_root"]), target),
                 scope="only the exact Hub-owned test app, its own system registration and its receipt")


def test_uninstall(source: Path, workspace: Path, plan_id: str, *, hub_root: Path = ROOT) -> dict[str, Any]:
    plan = test_uninstall_plan(source, workspace, hub_root=hub_root)
    _approval(plan, plan_id)
    target, record, _ = _owned_test(workspace)
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
    if inspect_bundle(source, target, hub_root=hub_root, _cleanup_snapshot_only=True)["sha256_tree"] != plan["target"]["sha256_tree"]:
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
              "launch": "player and target launch/reuse, plus the existing coupled wallpaper attempt",
              "wallpaper-status": "read-only live wallpaper verification; no launch or injection",
              "disable-wallpaper": "remove only the native wallpaper state from the verified current page; does not close the host or its debugging port"}
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
    return _plan(mode, bundle=verified, command=command, scope=scopes[mode], effects=effects,
                 limits="no other harness adapter; no pure launcher-without-wallpaper mode in this source; visual review remains separate")


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


def _wallpaper_assessment(mode: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    if mode in ("smoke", "probe"):
        return {"status": "not-attempted", "live_status_check": "not performed"}
    latest: dict[str, Any] | None = None
    attempted = False
    for item in events:
        name = item["event"]
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
            "live_status_check": "performed" if mode == "wallpaper-status" else "not performed"}


def assess_execution(mode: str, result: dict[str, Any], bundle: Path) -> dict[str, Any]:
    events = _events(result["stdout"])
    names = {item["event"] for item in events}
    passed = result["returncode"] == 0
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
    wallpaper = _wallpaper_assessment(mode, events)
    launcher_status = ("behavior-passed" if passed else "behavior-not-proven") if mode in ("smoke", "launch") else "not-run"
    status = "behavior-passed" if passed else "behavior-not-proven"
    if mode == "launch" and passed:
        status = "runtime-events-passed" if wallpaper["status"] == "reported-applied" else "partial"
    return {"status": status, "mode": mode, "launcher_status": launcher_status,
            "wallpaper_status": wallpaper["status"], "wallpaper_evidence": wallpaper,
            "events": events, "execution": result, "visual_review": "pending",
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
                result = assess_execution(args.mode, _run(plan["command"], timeout=60), args.bundle)
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

"""Pinned pstack Codex plugin entry; Codex owns installation and removal.

The Hub freezes only the declared source files and records native operations.
It does not translate pstack's workflow into the separate model-router profile.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from . import integration_common as common
except ImportError:
    import integration_common as common

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "pstack"
MARKETPLACE = "pstack-claude"
PLUGIN = "pstack@pstack-claude"
PLUGIN_ROOT = "plugins/pstack/"
RECEIPT_SCHEMA = "azhou-hub.pstack-install.v1"


def _directory(value: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise common.IntegrationError(f"an absolute directory is required: {path}")
    for item in [path, *path.parents]:
        if item.is_symlink():
            raise common.IntegrationError(f"target directory uses a symlink: {item}")
    if path.exists() and not path.is_dir():
        raise common.IntegrationError(f"not a directory: {path}")
    return path.resolve()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(home: Path) -> dict:
    """Fingerprint a dedicated home without disclosing auth or configuration."""
    if not home.exists():
        return {}
    result = {}
    for path in sorted(home.rglob("*")):
        name = path.relative_to(home).as_posix()
        if path.is_symlink():
            result[name] = {"symlink": os.readlink(path)}
        elif path.is_file():
            result[name] = {"sha256": _digest(path), "executable": bool(path.stat().st_mode & 0o111)}
        elif not path.is_dir():
            raise common.IntegrationError(f"non-file target state cannot be planned: {name}")
    return result


def _receipt_path(workspace: Path, home: Path) -> Path:
    return workspace / ".azhou/hub/integrations/pstack" / common.plan_digest(str(home)) / "receipt.json"


def _guard_router(home: Path) -> None:
    for item in [home / "agent-orchestration-kit/state.json", home / ".agent-orchestration-kit-transaction",
                 home / "skills/astra-orchestrator/SKILL.md"]:
        if item.exists() or item.is_symlink():
            raise common.IntegrationError("pstack and model-router require separate configuration targets; found " + str(item))
    instructions = home / "AGENTS.md"
    if instructions.is_file() and "ASTRA-LUNA-ORCHESTRATOR:BEGIN" in instructions.read_text(encoding="utf-8"):
        raise common.IntegrationError("pstack cannot be chained with the installed astra-orchestrator instruction")


def _native(binary: Path, home: Path, arguments: list[str]) -> dict | list:
    env = dict(os.environ)
    env["CODEX_HOME"] = str(home)
    try:
        result = subprocess.run([str(binary), "plugin", *arguments, "--json"], env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise common.IntegrationError(f"native Codex plugin operation failed: {arguments}: {exc}") from exc
    if result.returncode:
        raise common.IntegrationError(f"native Codex plugin operation failed ({result.returncode}): {arguments}: "
                                      + result.stderr.strip()[:2000] + result.stdout.strip()[:2000])
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise common.IntegrationError("native Codex returned non-JSON output for " + repr(arguments)) from exc


def _registered(value: dict, name: str) -> bool:
    if not isinstance(value, dict):
        raise common.IntegrationError("native Codex registry returned an unexpected JSON shape")
    key, field = ("marketplaces", "name") if name == MARKETPLACE else ("installed", "pluginId")
    rows = value.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise common.IntegrationError("native Codex registry is missing " + key)
    return any(row.get(field) == name for row in rows)


def _verify_registry_source(marketplaces: dict, snapshot: Path, plugins: dict | None = None) -> None:
    _registered(marketplaces, MARKETPLACE)
    entries = marketplaces.get("marketplaces", [])
    selected = [item for item in entries if item.get("name") == MARKETPLACE]
    expected_source = {"sourceType": "local", "source": str(snapshot)}
    if len(selected) != 1 or selected[0].get("root") != str(snapshot) or selected[0].get("marketplaceSource") != expected_source:
        raise common.IntegrationError("native marketplace is not the selected pinned local pstack snapshot")
    if plugins is not None:
        _registered(plugins, PLUGIN)
        selected = [item for item in plugins.get("installed", []) if item.get("pluginId") == PLUGIN]
        if len(selected) != 1 or not selected[0].get("installed") or not selected[0].get("enabled"):
            raise common.IntegrationError("native Codex does not report one enabled pstack installation")
        if (selected[0].get("source") != {"source": "local", "path": str(snapshot / "plugins/pstack")}
                or selected[0].get("marketplaceSource") != expected_source):
            raise common.IntegrationError("native pstack plugin resolves to a different source")


def _check_runtime_tree(root: Path, lock: dict, *, allow_dependencies: bool = False) -> dict:
    """The native installer copies a directory, so unlisted files matter too."""
    expected = {name[len(PLUGIN_ROOT):] for name in lock["files"] if name.startswith(PLUGIN_ROOT)}
    directories = {parent.as_posix() for name in expected for parent in Path(name).parents if parent != Path(".")}
    dependencies = "skills/poteto-mode/scripts/node_modules"
    dependency_files = 0
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if allow_dependencies and (name == dependencies or name.startswith(dependencies + "/")):
            if name == dependencies and (path.is_symlink() or not path.is_dir()):
                raise common.IntegrationError("pstack dependency directory must not be a symlink")
            dependency_files += int(path.is_file())
            continue
        if path.is_symlink():
            raise common.IntegrationError("unverified pstack runtime symlink: " + name)
        if (path.is_file() and name not in expected) or (path.is_dir() and name not in directories):
            raise common.IntegrationError("unlocked pstack runtime content; preserve and inspect before installation or removal: " + name)
        if not path.is_file() and not path.is_dir():
            raise common.IntegrationError("unexpected pstack runtime object: " + name)
    present = (root / dependencies).exists()
    return {"status": "not-independently-verified" if present else "not-present",
            "path": str(root / dependencies), "files": dependency_files,
            "scope": "upstream Bun bootstrap output, outside source-file verification; removal is blocked while unrecorded dependency files exist"}


def _installed_copy(home: Path, lock: dict, *, allow_dependencies: bool = False) -> Path:
    candidates = []
    for manifest in (home / "plugins").rglob(".codex-plugin/plugin.json"):
        if manifest.is_symlink():
            continue
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if metadata.get("name") == "pstack":
            candidates.append(manifest.parent.parent)
    if len(candidates) != 1:
        raise common.IntegrationError(f"expected exactly one native installed pstack copy; found {len(candidates)}")
    installed = candidates[0]
    _check_runtime_tree(installed, lock, allow_dependencies=allow_dependencies)
    for name, item in lock["files"].items():
        if not name.startswith(PLUGIN_ROOT):
            continue
        relative = name[len(PLUGIN_ROOT):]
        cursor = installed
        for part in Path(relative).parts:
            cursor /= part
            if cursor.is_symlink():
                raise common.IntegrationError("installed pstack runtime uses an unverified symlink: " + relative)
        if not cursor.is_file() or _digest(cursor) != item["sha256"]:
            raise common.IntegrationError("installed pstack content missing or changed: " + relative)
        if bool(cursor.stat().st_mode & 0o111) != item["executable"]:
            raise common.IntegrationError("installed pstack executable bit changed: " + relative)
    return installed


def make_plan(*, source: Path | None, workspace: Path, codex_home: Path, codex_bin: Path,
              operation: str = "install", hub_root: Path = ROOT) -> dict:
    workspace, home = _directory(workspace), _directory(codex_home)
    binary = Path(codex_bin).expanduser()
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise common.IntegrationError("--codex-bin must name an executable absolute Codex binary")
    binary = binary.resolve()
    if (home == workspace or home in workspace.parents
            or workspace in home.parents and ".azhou" not in home.relative_to(workspace).parts
            or home in _receipt_path(workspace, home).parents):
        raise common.IntegrationError("use a dedicated Codex home, not the workspace or its project files")
    if operation == "install":
        _guard_router(home)
    receipt_file = _receipt_path(workspace, home)
    receipt = common.read_receipt(receipt_file) if receipt_file.exists() else None
    if receipt and (receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("codex_home") != str(home)):
        raise common.IntegrationError("pstack ownership receipt does not match this target")
    lock = (common.snapshot_lock(COMPONENT, Path(receipt["snapshot"]))
            if operation == "remove" and receipt else common.load_lock(COMPONENT, hub_root=hub_root))
    if receipt and receipt.get("source_lock_sha256") != common.plan_digest(lock) and receipt.get("state") != "removed":
        raise common.IntegrationError("remove the prior owned package version before installing changed package inputs")
    inventory = _inventory(home)
    if receipt is None:
        allowed = {"config.toml", "auth.json", "pstack-models.md", "AGENTS.md"}
        unexpected = sorted(set(inventory) - allowed)
        if unexpected:
            raise common.IntegrationError("unowned Codex target is not empty; select a separate home: " + ", ".join(unexpected[:8]))
        if any("symlink" in item for item in inventory.values()):
            raise common.IntegrationError("pre-existing Codex configuration files must not be symlinks")
        config = home / "config.toml"
        if config.is_file() and any(word in config.read_text(encoding="utf-8") for word in [MARKETPLACE, "pstack@", "astra-orchestrator"]):
            raise common.IntegrationError("existing pstack or router configuration has no Hub ownership receipt")
    if operation == "install":
        origin = common.inspect_source(COMPONENT, source, hub_root=hub_root)
        source_path = Path(origin["source"])
        if workspace == source_path or source_path in workspace.parents:
            raise common.IntegrationError("pstack workspace must be outside the read-only source")
        if home == source_path or source_path in home.parents:
            raise common.IntegrationError("Codex installation must not write inside the read-only source")
        snapshot = workspace / ".azhou/hub/sources/pstack" / common.plan_digest(lock)
        if snapshot.exists() or snapshot.is_symlink():
            verified = common.verify_snapshot(COMPONENT, snapshot, hub_root=hub_root)
            if verified["source_lock_sha256"] != common.plan_digest(lock):
                raise common.IntegrationError("existing snapshot differs from the reviewed package inputs")
            _check_runtime_tree(snapshot / "plugins/pstack", lock)
        commands = [[str(binary), "plugin", "marketplace", "add", str(snapshot), "--json"],
                    [str(binary), "plugin", "add", PLUGIN, "--json"]]
    elif operation == "remove":
        if not receipt or receipt.get("state") == "removed":
            raise common.IntegrationError("there is no owned pstack installation to remove")
        origin = {"commit": lock["commit"], "source_lock_sha256": common.plan_digest(lock)}
        snapshot = Path(receipt["snapshot"])
        common.verify_snapshot(COMPONENT, snapshot, hub_root=hub_root)
        if receipt.get("state") == "installed" or (receipt.get("operation") == "install" and 1 in receipt.get("completed_steps", [])):
            _installed_copy(home, lock)
        commands = [[str(binary), "plugin", "remove", PLUGIN, "--json"],
                    [str(binary), "plugin", "marketplace", "remove", MARKETPLACE, "--json"]]
    else:
        raise common.IntegrationError("operation must be install or remove")
    payload = {
        "schema": "azhou-hub.pstack-plan.v1", "operation": operation,
        "source": origin, "source_lock_sha256": common.plan_digest(lock),
        "workspace": str(workspace), "codex_home": str(home), "codex_bin": str(binary),
        "codex_bin_sha256": _digest(binary), "snapshot": str(snapshot),
        "target_state_sha256": common.plan_digest(inventory),
        "receipt_sha256": _digest(receipt_file) if receipt_file.exists() else None,
        "commands": commands, "environment": {"CODEX_HOME": str(home)},
        "native_owner": "Codex plugin manager", "composition": "pstack owns workflow and explicit dispatch policy; separate from model-router",
        "activation": "plugin installation does not prove skill invocation or hook trust; review /hooks in a new session",
        "recovery": "failed native steps retain a receipt; plan and apply again to resume, or plan remove to use native cleanup",
    }
    return {**payload, "plan_id": common.plan_digest(payload)}


@contextmanager
def _operation_lock(receipt_file: Path):
    for path in [receipt_file.parent, *receipt_file.parent.parents]:
        if path.is_symlink():
            raise common.IntegrationError("receipt path uses a symlink: " + str(path))
    receipt_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = receipt_file.parent / "operation.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise common.IntegrationError("another or interrupted pstack operation holds " + str(lock)) from exc
    try:
        yield
    finally:
        lock.rmdir()


def doctor(*, workspace: Path, codex_home: Path, codex_bin: Path, hub_root: Path = ROOT) -> dict:
    workspace, home = _directory(workspace), _directory(codex_home)
    _guard_router(home)
    receipt = common.read_receipt(_receipt_path(workspace, home))
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("codex_home") != str(home) or receipt.get("state") != "installed":
        raise common.IntegrationError("pstack does not have a completed installation receipt for this target")
    common.verify_snapshot(COMPONENT, Path(receipt["snapshot"]), hub_root=hub_root)
    lock = common.snapshot_lock(COMPONENT, Path(receipt["snapshot"]))
    installed = _installed_copy(home, lock, allow_dependencies=True)
    dependencies = _check_runtime_tree(installed, lock, allow_dependencies=True)
    marketplaces = _native(Path(codex_bin), home, ["marketplace", "list"])
    plugins = _native(Path(codex_bin), home, ["list", "--marketplace", MARKETPLACE])
    _verify_registry_source(marketplaces, Path(receipt["snapshot"]), plugins)
    return {"status": "installation-verified", "installed_path": str(installed), "commit": lock["commit"],
            "source_lock_sha256": common.plan_digest(lock), "native_registry": {"marketplaces": marketplaces, "plugins": plugins},
            "dependency_runtime": dependencies,
            "evidence_levels": {"files_installed": True, "native_plugin_registered": True,
                                "host_skill_discovered": "requires skills/list", "invoked": "requires a real session",
                                "behavior_passed": "requires a real session", "hook_trusted": "requires /hooks review"}}


def apply_plan(plan: dict, *, plan_id: str, hub_root: Path = ROOT) -> dict:
    if plan_id != plan.get("plan_id"):
        raise common.IntegrationError("plan-id mismatch; review a fresh plan before applying")
    workspace, home, binary = Path(plan["workspace"]), Path(plan["codex_home"]), Path(plan["codex_bin"])
    receipt_file = _receipt_path(workspace, home)
    with _operation_lock(receipt_file):
        fresh = make_plan(source=Path(plan["source"]["source"]) if plan["operation"] == "install" else None,
                          workspace=workspace, codex_home=home, codex_bin=binary,
                          operation=plan["operation"], hub_root=hub_root)
        if fresh["plan_id"] != plan_id:
            raise common.IntegrationError("target, source or Codex binary changed after the plan")
        old = common.read_receipt(receipt_file) if receipt_file.exists() else {}
        if plan["operation"] == "install" and old.get("state") == "installed":
            return {**doctor(workspace=workspace, codex_home=home, codex_bin=binary, hub_root=hub_root), "changed": False}
        snapshot = Path(plan["snapshot"])
        if plan["operation"] == "install":
            snapshot = common.snapshot_source(COMPONENT, Path(plan["source"]["source"]), workspace, hub_root=hub_root,
                                              expected_digest=plan["source_lock_sha256"])
            _check_runtime_tree(snapshot / "plugins/pstack", common.snapshot_lock(COMPONENT, snapshot))
        receipt = {"schema": RECEIPT_SCHEMA, "codex_home": str(home), "snapshot": str(snapshot),
                   "source_lock_sha256": plan["source_lock_sha256"], "commit": plan["source"]["commit"],
                   "codex_bin": str(binary), "codex_bin_sha256": plan["codex_bin_sha256"],
                   "state": "pending-" + plan["operation"], "operation": plan["operation"],
                   "commands": [], "completed_steps": old.get("completed_steps", []) if old.get("operation") == plan["operation"] else []}
        common.write_receipt(receipt_file, receipt)
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            if plan["operation"] == "install" and 0 in receipt["completed_steps"]:
                _verify_registry_source(_native(binary, home, ["marketplace", "list"]), snapshot)
            if plan["operation"] == "remove":
                marketplaces = _native(binary, home, ["marketplace", "list"])
                if _registered(marketplaces, MARKETPLACE):
                    _verify_registry_source(marketplaces, snapshot)
                    plugins = _native(binary, home, ["list", "--marketplace", MARKETPLACE])
                    if not _registered(plugins, PLUGIN):
                        receipt["completed_steps"] = sorted(set(receipt["completed_steps"]) | {0})
                elif old.get("operation") == "remove" and 0 in old.get("completed_steps", []):
                    receipt["completed_steps"] = [0, 1]
                elif old.get("operation") == "install" and 0 not in old.get("completed_steps", []):
                    receipt["completed_steps"] = [0, 1]
                else:
                    raise common.IntegrationError("owned native marketplace disappeared; inspect target before cleanup")
            for index, command in enumerate(plan["commands"]):
                if index in receipt["completed_steps"]:
                    continue
                if plan["operation"] == "install":
                    common.verify_snapshot(COMPONENT, snapshot, hub_root=hub_root)
                _check_runtime_tree(snapshot / "plugins/pstack", common.snapshot_lock(COMPONENT, snapshot))
                output = _native(binary, home, command[2:-1])
                receipt["commands"].append({"argv": command, "result": output})
                receipt["completed_steps"].append(index)
                common.write_receipt(receipt_file, receipt)
            receipt["state"] = "installed" if plan["operation"] == "install" else "removed"
            common.write_receipt(receipt_file, receipt)
            if plan["operation"] == "install":
                return {**doctor(workspace=workspace, codex_home=home, codex_bin=binary, hub_root=hub_root), "changed": True}
            remaining_marketplaces = _native(binary, home, ["marketplace", "list"])
            remaining_plugins = _native(binary, home, ["list"])
            if _registered(remaining_marketplaces, MARKETPLACE) or _registered(remaining_plugins, PLUGIN):
                raise common.IntegrationError("native removal returned success but pstack is still registered")
            return {"status": "removed", "changed": True, "native_owner": "Codex plugin manager", "snapshot_retained": str(snapshot),
                    "native_registry": {"marketplaces": remaining_marketplaces, "plugins": remaining_plugins}}
        except common.IntegrationError as exc:
            receipt["state"] = "failed-" + plan["operation"]
            receipt["failure"] = str(exc)
            common.write_receipt(receipt_file, receipt)
            raise


def main(argv: list[str] | None = None, *, hub_root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "doctor"))
    parser.add_argument("--source", type=Path, help="optional assertion of the in-repository package path")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True, help="explicit dedicated configuration target")
    parser.add_argument("--codex-bin", type=Path, required=True, help="explicit native Codex executable")
    parser.add_argument("--operation", choices=("install", "remove"), default="install")
    parser.add_argument("--plan-id")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(workspace=args.workspace, codex_home=args.codex_home, codex_bin=args.codex_bin, hub_root=hub_root)
        else:
            result = make_plan(source=args.source, workspace=args.workspace, codex_home=args.codex_home,
                               codex_bin=args.codex_bin, operation=args.operation, hub_root=hub_root)
            if args.command == "apply":
                if not args.plan_id:
                    raise common.IntegrationError("apply requires the --plan-id from a reviewed plan")
                result = apply_plan(result, plan_id=args.plan_id, hub_root=hub_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (common.IntegrationError, OSError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

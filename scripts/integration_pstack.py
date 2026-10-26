"""Install the Hub-maintained pstack package with Codex's native plugin manager.

The Hub freezes only the declared source files and records native operations.
It does not translate pstack's workflow into the separate model-router profile.
A custom --codex-home requires launching Codex with that CODEX_HOME; it does not
change the configuration used by an already-running desktop app.
For a target shared with the Agent Orchestration Kit, the adapter owns one
narrow change: the model sheet's ``session hook: off`` line that keeps pstack
SessionStart auto-routing off while the plugin's on-demand Skills stay installed.

``transition-plan`` reviews an existing installation read-only — the reachable
Kit-plus-shared-Skills, compatible-native, armed and locally-modified states —
and names the actual source, content differences, owners and recovery basis of
each transition, without adopting unknown installations.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
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
TRANSITION_SCHEMA = "azhou-hub.pstack-transition.v1"
SHEET_NAME = "pstack-models.md"
HOOK_OFF = "session hook: off"
HOOK_LINE_PREFIX = "session hook:"
SHEET_HEADER = "# pstack model configuration"
SHARED_SKILL_PREFIX = PLUGIN_ROOT + "skills/"
DEPENDENCY_DIR = "skills/poteto-mode/scripts/node_modules"
KIT_STATE_FILE = "agent-orchestration-kit/state.json"
KIT_INSTRUCTION_BEGIN = "ASTRA-LUNA-ORCHESTRATOR:BEGIN"
HOOK_TRUST_UNKNOWN = "unknown; only the host's /hooks review decides whether the hook runs"


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


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sheet_path(home: Path) -> Path:
    return home / SHEET_NAME


def _sheet_bytes(home: Path) -> bytes | None:
    path = _sheet_path(home)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise common.IntegrationError("the pstack model sheet must be a regular file when present: " + str(path))
    return path.read_bytes() if path.exists() else None


def _sheet_text(raw: bytes) -> str | None:
    try:
        if raw.startswith(b"\xff\xfe"):
            return raw.decode("utf-16")
        return raw.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None


def _sheet_hook(raw: bytes | None) -> str | None:
    """Read the sheet the way the plugin's SessionStart hook does: only the
    exact ``off`` line stops injection; a missing sheet or any other content
    leaves it on. Mirrors read-sheet.sh's BOM and CRLF handling."""
    if raw is None:
        return None
    text = _sheet_text(raw)
    if text is None:
        return "on"  # an undecodable sheet counts as missing, so injection stays on
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    return "off" if HOOK_OFF in lines else "on"


def _sheet_conversion(raw: bytes | None, home: Path) -> tuple[str, bytes] | None:
    """The minimal edit that establishes ``session hook: off``.

    Returns ``None`` when the sheet already switches auto-routing off. A
    missing sheet gets a minimal one; an existing sheet keeps every other
    byte, encoding and line ending, with only the ``session hook`` line
    replaced or appended.
    """
    if raw is None:
        return "write", (SHEET_HEADER + "\n" + HOOK_OFF + "\n").encode("utf-8")
    text = _sheet_text(raw)
    if text is None:
        raise common.IntegrationError(
            "the existing pstack model sheet cannot be decoded for a coexistence conversion; review it first: "
            + str(_sheet_path(home)))
    utf16 = raw.startswith(b"\xff\xfe")
    bom = text.startswith("\ufeff")
    if bom:
        text = text[1:]
    lines = text.split("\n")
    replaced = False
    for index, line in enumerate(lines):
        body = line[:-1] if line.endswith("\r") else line
        if body.startswith(HOOK_LINE_PREFIX):
            lines[index] = HOOK_OFF + ("\r" if line.endswith("\r") else "")
            replaced = True
    if replaced:
        result = "\n".join(lines)
    else:
        result = text if (text.endswith("\n") or text == "") else text + "\n"
        result += HOOK_OFF + "\n"
    if bom:
        result = "\ufeff" + result
    encoded = result.encode("utf-16" if utf16 else "utf-8")
    # An already-satisfied sheet is no change at all: return ``None`` so plans
    # and receipts report "already established", never a pending no-op edit.
    return None if encoded == raw else ("set-line", encoded)


def _sheet_rows(raw: bytes | None) -> list[str] | None:
    """The sheet's user lines — model rows, host mappings, default effort —
    that a conversion must preserve. ``None`` means the sheet is undecodable."""
    if raw is None:
        return []
    text = _sheet_text(raw)
    if text is None:
        return None
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    return [line for line in lines if line.strip() and not line.startswith("#")
            and not line.startswith(HOOK_LINE_PREFIX)]


def _kit_presence(home: Path) -> dict:
    """Kit rules are installed only with a valid ownership record.

    A stray instruction block or Skill without that record is an unknown
    source, not an installation, and is never adopted. An unfinished Kit
    transaction is its owner's recovery case, not an install input.
    """
    transaction = home / ".agent-orchestration-kit-transaction"
    if transaction.exists() or transaction.is_symlink():
        raise common.IntegrationError(
            "an unfinished agent-orchestration-kit transaction exists; recover it with the Kit installer before changing this target")
    state_path = home / KIT_STATE_FILE
    if state_path.exists() or state_path.is_symlink():
        if state_path.is_symlink() or not state_path.is_file():
            raise common.IntegrationError("the agent-orchestration-kit ownership record is not a regular file")
        try:
            manifest = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise common.IntegrationError(
                "an unreadable agent-orchestration-kit ownership record exists; inspect it before installing pstack") from exc
        if (not isinstance(manifest, dict) or manifest.get("schema") != 1
                or manifest.get("project") != "agent-orchestration-kit"
                or not isinstance(manifest.get("targets"), dict) or not isinstance(manifest.get("files"), dict)):
            raise common.IntegrationError(
                "an unrecognized agent-orchestration-kit ownership record exists; inspect it before installing pstack")
        owned = {"agent-orchestration-kit/state.json", "config.toml", "AGENTS.md"}
        for value in manifest["targets"].values():
            if not isinstance(value, str):
                raise common.IntegrationError("the agent-orchestration-kit ownership record has invalid target paths")
            try:
                relative = Path(value).relative_to(home).as_posix()
            except ValueError:
                continue
            parts = Path(relative).parts
            if relative == "skills/astra-orchestrator/SKILL.md" or (
                    len(parts) == 2 and parts[0] == "agents" and parts[1].endswith(".toml")):
                owned.add(relative)
        return {"present": True, "owned_files": owned}
    instructions = home / "AGENTS.md"
    if instructions.is_file():
        try:
            text = instructions.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            raise common.IntegrationError("AGENTS.md exists but cannot be read: " + str(instructions)) from exc
        if KIT_INSTRUCTION_BEGIN in text:
            raise common.IntegrationError(
                "an astra-orchestrator instruction block exists without its Kit ownership record; its source is unknown")
    skill = home / "skills/astra-orchestrator/SKILL.md"
    if skill.exists() or skill.is_symlink():
        raise common.IntegrationError(
            "an astra-orchestrator Skill exists in this target without a Kit ownership record; its source is unknown")
    return {"present": False, "owned_files": set()}


def _kit_record(home: Path) -> dict:
    """Identifying facts of the already-validated Kit ownership record."""
    try:
        manifest = json.loads((home / KIT_STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"detail": "the validated ownership record could not be re-read for this report"}
    return {"record": str(home / KIT_STATE_FILE), "profile": manifest.get("profile"),
            "source_digest": manifest.get("source_digest"),
            "adopted_existing": manifest.get("adopted_existing", []),
            "owned_target_count": len(manifest.get("targets", {}))}


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


def _establish_sheet(home: Path, change: dict, receipt: dict, receipt_file: Path) -> None:
    """Apply the reviewed sheet conversion once, recording the rollback basis first.

    The recovery record reaches the receipt before the sheet changes, the same
    journal-first order the Kit installer uses: an interruption between the two
    steps leaves either "basis recorded, sheet untouched" or "basis recorded,
    sheet converted" — both recoverable — and never an adapter-written sheet
    with no recorded original to restore.
    """
    path = _sheet_path(home)
    if change.get("path") != str(path):
        raise common.IntegrationError("the reviewed sheet conversion targets a different path")
    raw = _sheet_bytes(home)
    current = _digest_bytes(raw) if raw is not None else None
    if current == change["after_sha256"]:
        record = (receipt.get("coexistence") or {}).get("sheet") or {}
        if record.get("after_sha256") == change["after_sha256"]:
            return  # already established by this receipt's recorded attempt
        raise common.IntegrationError(
            "the pstack model sheet changed after the plan (planned sha256 "
            + f"{change['after_sha256']}, found sha256 {current})")
    if current != change["before_sha256"]:
        raise common.IntegrationError(
            "the pstack model sheet changed after the plan (planned sha256 "
            + f"{change['before_sha256']}, found sha256 {current})")
    conversion = _sheet_conversion(raw, home)
    if conversion is None or _digest_bytes(conversion[1]) != change["after_sha256"]:
        raise common.IntegrationError("the reviewed sheet conversion no longer matches this target")
    mode = stat.S_IMODE(path.stat().st_mode) if raw is not None else 0o600
    receipt["coexistence"] = {"sheet": {
        "path": str(path),
        "before": base64.b64encode(raw).decode("ascii") if raw is not None else None,
        "before_sha256": change["before_sha256"],
        "after_sha256": change["after_sha256"],
        "mode": mode,
    }}
    common.write_receipt(receipt_file, receipt)
    path.write_bytes(conversion[1])
    os.chmod(path, mode)


def _restore_sheet(home: Path, record: dict) -> None:
    """Restore the adapter-owned sheet change; later user edits stop this."""
    path = _sheet_path(home)
    valid = (isinstance(record, dict) and record.get("path") == str(path)
             and isinstance(record.get("after_sha256"), str)
             and (record.get("before_sha256") is None or isinstance(record.get("before_sha256"), str))
             and isinstance(record.get("mode"), int))
    if not valid:
        raise common.IntegrationError("the recorded coexistence sheet record is invalid; inspect the receipt")
    raw = _sheet_bytes(home)
    current = _digest_bytes(raw) if raw is not None else None
    if current == record["before_sha256"]:
        return  # already restored, or nothing recorded to remove
    if current != record["after_sha256"]:
        raise common.IntegrationError(
            "the pstack model sheet was modified after the coexistence install; automatic restore refused: "
            + str(path) + f" (recorded sha256 {record['after_sha256']}, found sha256 {current})")
    if record["before_sha256"] is None:
        path.unlink()
        return
    try:
        before = base64.b64decode(record["before"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise common.IntegrationError("the recorded coexistence sheet record is invalid") from exc
    if _digest_bytes(before) != record["before_sha256"]:
        raise common.IntegrationError("the recorded coexistence sheet record is inconsistent")
    path.write_bytes(before)
    os.chmod(path, record["mode"])


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
              operation: str = "install", coexistence: bool | None = None, hub_root: Path = ROOT) -> dict:
    workspace, home = _directory(workspace), _directory(codex_home)
    binary = Path(codex_bin).expanduser()
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise common.IntegrationError("--codex-bin must name an executable absolute Codex binary")
    binary = binary.resolve()
    if (home == workspace or home in workspace.parents
            or workspace in home.parents and ".azhou" not in home.relative_to(workspace).parts
            or home in _receipt_path(workspace, home).parents):
        raise common.IntegrationError("use a dedicated Codex home, not the workspace or its project files")
    kit = _kit_presence(home) if operation == "install" else {"present": False, "owned_files": set()}
    if operation == "install":
        if coexistence is None:
            coexistence = kit["present"]
        if kit["present"] and not coexistence:
            raise common.IntegrationError(
                "agent-orchestration-kit rules are installed in this target; a standalone pstack install would arm "
                "a second auto-router here: use a coexistence install (SessionStart routing off) or a separate home")
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
        allowed = {"config.toml", "auth.json", SHEET_NAME, "AGENTS.md"}
        if kit["present"]:
            allowed |= kit["owned_files"]
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
        sheet_change = None
        hook_before = None
        if coexistence:
            raw = _sheet_bytes(home)
            hook_before = _sheet_hook(raw)
            conversion = _sheet_conversion(raw, home)
            if conversion is not None:
                action, desired = conversion
                sheet_change = {
                    "path": str(_sheet_path(home)),
                    "action": action,
                    "owner": "hub-pstack-adapter",
                    "before_sha256": _digest_bytes(raw) if raw is not None else None,
                    "after_sha256": _digest_bytes(desired),
                    "purpose": "set the exact '" + HOOK_OFF + "' line so SessionStart auto-routing stays off in this shared target",
                    "restore": "restore the prior sheet bytes (or remove the adapter-written sheet) on remove; later user edits stop automatic restore",
                }
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
    if operation == "install":
        coexistence_report = {
            "requested": bool(coexistence),
            "kit_rules_present": kit["present"],
            "session_hook_before": hook_before,
            "sheet_change": sheet_change,
            "on_demand_skills": "plugin Skills remain installed for explicit per-task selection",
            "hook_trust": HOOK_TRUST_UNKNOWN,
            "compatibility": ("pending: apply this plan before the target is a compatible coexistence target"
                              if sheet_change is not None else
                              "already satisfied: the sheet's '" + HOOK_OFF + "' line keeps auto-routing off"
                              if coexistence else
                              "standalone pstack target: the existing routing mode is left unchanged; a Kit install "
                              "here later requires '" + HOOK_OFF + "' in the sheet first"),
        }
    else:
        record = ((receipt or {}).get("coexistence") or {}).get("sheet")
        coexistence_report = {
            "requested": False,
            "kit_rules_present": False,
            "sheet_restore": bool(record),
            "compatibility": "n/a for removal",
        }
    payload = {
        "schema": "azhou-hub.pstack-plan.v1", "operation": operation,
        "source": origin, "source_lock_sha256": common.plan_digest(lock),
        "workspace": str(workspace), "codex_home": str(home), "codex_bin": str(binary),
        "codex_bin_sha256": _digest(binary), "snapshot": str(snapshot),
        "target_state_sha256": common.plan_digest(inventory),
        "receipt_sha256": _digest(receipt_file) if receipt_file.exists() else None,
        "commands": commands, "environment": {"CODEX_HOME": str(home)},
        "native_owner": "Codex plugin manager",
        "composition": "pstack owns its selected tasks' workflow and explicit dispatch; one workflow owner per task",
        "coexistence": coexistence_report,
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
    kit = _kit_presence(home)
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
    sheet = _sheet_bytes(home)
    hook = _sheet_hook(sheet)
    coexistence = {
        "kit_rules_present": kit["present"],
        "model_sheet_present": sheet is not None,
        "session_hook": hook,
        "native_plugin_registered": True,
        "auto_routing": "off" if hook == "off" else "on",
        "hook_trust": HOOK_TRUST_UNKNOWN,
        "sheet_owner": ("hub-pstack-adapter" if (receipt.get("coexistence") or {}).get("sheet") else "not adapter-owned"),
        "compatibility": ("coexistence target: SessionStart auto-routing is off, so Kit rules may share this home"
                          if hook == "off" else
                          "standalone pstack target: auto-routing is armed; a Kit install here requires '"
                          + HOOK_OFF + "' in the sheet first"),
    }
    return {"status": "installation-verified", "installed_path": str(installed), "commit": lock["commit"],
            "source_lock_sha256": common.plan_digest(lock), "native_registry": {"marketplaces": marketplaces, "plugins": plugins},
            "dependency_runtime": dependencies, "coexistence": coexistence,
            "evidence_levels": {"files_installed": True, "native_plugin_registered": True,
                                "host_skill_discovered": "requires skills/list", "invoked": "requires a real session",
                                "behavior_passed": "requires a real session", "hook_trusted": "requires /hooks review"}}


def _plugin_copies(home: Path) -> tuple[list[Path], list[str]]:
    """Locate pstack plugin copies without adopting or trusting them."""
    plugins = home / "plugins"
    if plugins.is_symlink():
        raise common.IntegrationError(
            "the plugins directory is a symlink; pstack state cannot be reported: " + str(plugins))
    roots: list[Path] = []
    anomalies: list[str] = []
    if not plugins.exists():
        return roots, anomalies
    for manifest in sorted(plugins.rglob(".codex-plugin/plugin.json")):
        name = manifest.relative_to(home).as_posix()
        if manifest.is_symlink():
            anomalies.append("symlinked plugin manifest: " + name)
            continue
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            anomalies.append("unreadable plugin manifest: " + name)
            continue
        if metadata.get("name") == "pstack":
            roots.append(manifest.parent.parent)
    return roots, anomalies


def _content_differences(root: Path, lock: dict) -> dict:
    """Classify one installed plugin copy against the pinned package, read-only."""
    expected = {name[len(PLUGIN_ROOT):]: item for name, item in lock["files"].items()
                if name.startswith(PLUGIN_ROOT)}
    identical: list[str] = []
    modified: list[str] = []
    unexpected: list[str] = []
    symlinks: list[str] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if name == DEPENDENCY_DIR or name.startswith(DEPENDENCY_DIR + "/"):
            continue
        if path.is_symlink():
            symlinks.append(name)
            continue
        if path.is_dir():
            continue
        item = expected.get(name)
        if item is None or not path.is_file():
            unexpected.append(name)
            continue
        if _digest(path) != item["sha256"] or bool(path.stat().st_mode & 0o111) != item["executable"]:
            modified.append(name)
        else:
            identical.append(name)
        seen.add(name)
    missing = sorted(set(expected) - seen)
    return {"compared_root": str(root), "identical": len(identical),
            "modified": modified[:8], "modified_count": len(modified),
            "missing": missing[:8], "missing_count": len(missing),
            "unexpected": unexpected[:8], "unexpected_count": len(unexpected),
            "symlinks": symlinks[:8], "symlink_count": len(symlinks),
            "basis": "identical content is a comparison result, never a takeover basis",
            "dependency_runtime": DEPENDENCY_DIR + " is excluded; it is upstream bootstrap output outside source verification"}


def _shared_skills_report(shared: Path, lock: dict) -> dict:
    """Compare the shared Skills root against the pinned package, read-only.

    Shared installs may be plain directories or the symlinks upstream's shared
    installation creates; the report names the actual shape and compares the
    content behind it, so local modifications stay visible either way."""
    names = sorted({name[len(SHARED_SKILL_PREFIX):].split("/", 1)[0]
                    for name in lock["files"] if name.startswith(SHARED_SKILL_PREFIX)})
    skills: dict[str, dict] = {}
    for skill in names:
        prefix = SHARED_SKILL_PREFIX + skill + "/"
        expected = {name[len(prefix):]: item["sha256"] for name, item in lock["files"].items()
                    if name.startswith(prefix)}
        target = shared / skill
        entry: dict = {}
        root = target
        if target.is_symlink():
            entry["kind"] = "symlink"
            entry["target"] = os.readlink(target)
            root = target.resolve()
        else:
            entry["kind"] = "directory"
        if not root.exists():
            entry["status"] = "broken" if target.is_symlink() else "absent"
            skills[skill] = entry
            continue
        modified: list[str] = []
        extra: list[str] = []
        identical = 0
        seen: set[str] = set()
        try:
            for path in sorted(root.rglob("*")):
                name = path.relative_to(root).as_posix()
                if path.is_symlink():
                    extra.append(name + " (symlink)")
                    continue
                if path.is_dir():
                    continue
                digest = expected.get(name)
                if digest is None or not path.is_file():
                    extra.append(name)
                elif _digest(path) != digest:
                    modified.append(name)
                else:
                    identical += 1
                seen.add(name)
        except OSError as exc:
            entry["error"] = f"unreadable through the shared Skills path: {exc}"
            skills[skill] = entry
            continue
        missing = sorted(set(expected) - seen)
        entry.update(identical=identical,
                     modified=modified[:8], modified_count=len(modified),
                     missing=missing[:8], missing_count=len(missing),
                     extra=extra[:8], extra_count=len(extra))
        skills[skill] = entry
    return {"root": str(shared), "compared_against": "the pinned package skills",
            "skills": skills,
            "write_policy": "no Hub entry writes this directory; differences are preserved, never overwritten"}


def _registry_sources(marketplaces: dict, plugins: dict) -> dict:
    rows = marketplaces.get("marketplaces") if isinstance(marketplaces, dict) else None
    selected = [row for row in (rows or []) if isinstance(row, dict) and row.get("name") == MARKETPLACE]
    installed_rows = plugins.get("installed") if isinstance(plugins, dict) else None
    pstack_rows = [row for row in (installed_rows or [])
                   if isinstance(row, dict) and (row.get("pluginId") == PLUGIN or row.get("name") == "pstack")]
    return {"marketplaces": selected, "installed_plugins": pstack_rows}


def _shared_verdict(home: Path, shared: Path | None, hub_root: Path) -> dict:
    """The one compatibility verdict both public entries share, loaded from the
    Kit's hash-verified shipped implementation so this report cannot drift
    from what the install entries would actually decide."""
    try:
        from . import integration_model_router as router
    except ImportError:
        import integration_model_router as router
    installer = router._module(common.package_root("model-router", hub_root=hub_root),
                               "install_codex.py", hub_root=hub_root)
    try:
        return installer.pstack_coexistence(home, shared)
    except common.IntegrationError:
        raise
    except Exception as exc:
        raise common.IntegrationError(f"pstack compatibility could not be established: {exc}") from exc


def transition(*, workspace: Path, codex_home: Path, codex_bin: Path,
               skills_dir: Path | None = None, hub_root: Path = ROOT) -> dict:
    """Review how an existing installation enters the compatible state; read-only.

    Covers the reachable existing-install states — a Kit beside shared pstack
    Skills, a compatible native pstack, an armed one, and locally modified
    shared Skills — and names for each the actual source, the content
    differences against the pinned package, the target change (if any), its
    owner and its recovery basis. Unknown installations are never adopted: a
    matching name or byte-identical content is not a takeover basis, and no
    restore is claimed for history no receipt records. An applicable
    conversion is the reviewed coexistence plan of this same entry; applying
    it re-verifies the bound source and target and stops on drift.
    """
    workspace, home = _directory(workspace), _directory(codex_home)
    shared = _directory(skills_dir) if skills_dir is not None else None
    binary = Path(codex_bin).expanduser()
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise common.IntegrationError("--codex-bin must name an executable absolute Codex binary")
    binary = binary.resolve()
    if (home == workspace or home in workspace.parents
            or workspace in home.parents and ".azhou" not in home.relative_to(workspace).parts
            or home in _receipt_path(workspace, home).parents):
        raise common.IntegrationError("use a dedicated Codex home, not the workspace or its project files")
    origin = common.inspect_source(COMPONENT, None, hub_root=hub_root)
    lock = common.load_lock(COMPONENT, hub_root=hub_root)

    receipt_file = _receipt_path(workspace, home)
    receipt, receipt_error = None, None
    if receipt_file.exists() or receipt_file.is_symlink():
        try:
            candidate = common.read_receipt(receipt_file)
            if candidate.get("schema") != RECEIPT_SCHEMA or candidate.get("codex_home") != str(home):
                receipt_error = "the pstack ownership receipt does not match this target"
            else:
                receipt = candidate
        except common.IntegrationError as exc:
            receipt_error = str(exc)

    kit: dict = {"present": False}
    try:
        presence = _kit_presence(home)
        kit = ({"present": True, "ownership_record": _kit_record(home),
                "owned_files": sorted(presence["owned_files"])} if presence["present"] else {"present": False})
    except common.IntegrationError as exc:
        kit = {"present": None, "error": str(exc)}

    sheet: dict = {"present": False}
    raw_sheet: bytes | None = None
    hook: str | None = None
    try:
        raw_sheet = _sheet_bytes(home)
    except common.IntegrationError as exc:
        sheet = {"present": None, "error": str(exc)}
    else:
        hook = _sheet_hook(raw_sheet)
        rows = _sheet_rows(raw_sheet)
        sheet = {"present": raw_sheet is not None, "session_hook": hook, "decodable": rows is not None}
        if rows is None:
            sheet["error"] = ("the sheet cannot be decoded, so no reviewed conversion is possible until it is "
                              "inspected: " + str(_sheet_path(home)))
        else:
            sheet["preserved_user_rows"] = rows

    copies, anomalies = _plugin_copies(home)
    config_registered = False
    config = home / "config.toml"
    if config.is_file():
        try:
            config_registered = any(word in config.read_text(encoding="utf-8") for word in [MARKETPLACE, "pstack@"])
        except (OSError, ValueError) as exc:
            anomalies.append("config.toml could not be read: " + str(exc))

    try:
        registry = _registry_sources(_native(binary, home, ["marketplace", "list"]),
                                     _native(binary, home, ["list"]))
        registry["scope"] = "native registry evidence only; it does not prove hook trust or invocation"
    except common.IntegrationError as exc:
        registry = {"error": str(exc),
                    "scope": "native registry evidence only; it does not prove hook trust or invocation"}

    installed_report = _content_differences(copies[0], lock) if len(copies) == 1 else None
    shared_report = _shared_skills_report(shared, lock) if shared is not None else None

    try:
        verdict = _shared_verdict(home, shared, hub_root)
    except common.IntegrationError as exc:
        verdict = {"compatible": None, "error": str(exc)}

    registration = ("none" if not copies and not config_registered
                    else "conflict" if len(copies) > 1 or anomalies
                    else "single" if len(copies) == 1
                    else "config-only")
    shared_visible = bool(shared_report
                          and any(row.get("status") not in ("absent", "broken")
                                  for row in shared_report["skills"].values()))
    shared_drift = bool(shared_report and any(
        row.get("modified_count") or row.get("missing_count") or row.get("extra_count")
        for row in shared_report["skills"].values()))

    states: list[str] = []
    if registration == "none" and shared_visible:
        states.append("kit-with-shared-pstack-skills" if kit.get("present") else "shared-pstack-skills-only")
    if registration in ("single", "config-only"):
        states.append("compatible-native-pstack" if hook == "off" else "armed-pstack")
    if shared_drift:
        states.append("locally-modified-shared-skills")
    if registration == "conflict":
        states.append("registration-conflict")
    if not states:
        states.append("no-pstack-installation")

    foreign_steps = [
        "keep the existing installation and switch routing off with its own tool: run /setup-pstack in a session "
        "on this home and answer the session-hook question with 'off' — afterwards both public entries judge this "
        "target compatible and the Hub owns nothing here",
        "or move the installation under Hub management: remove it through the entry that installed it (codex plugin "
        "remove " + PLUGIN + ", then codex plugin marketplace remove " + MARKETPLACE + ", with CODEX_HOME set to this "
        "home), then run this entry's coexistence install, which registers the pinned snapshot and converts the "
        "sheet in one reviewed plan",
    ]
    foreign_recovery = ("no Hub receipt exists for this installation, so no byte-exact Hub restore is claimed for "
                        "it; the recorded native registry source is the reinstall basis; this report changed nothing")

    routing: dict = {"goal": "let this Codex home share the Kit's host defaults with an on-demand pstack workflow",
                     "compatibility": (verdict.get("error") if verdict.get("compatible") is None
                                       else verdict.get("reason"))}
    if registration == "conflict":
        routing.update(status="blocked",
                       reason=(verdict.get("error")
                               or "duplicate or anomalous pstack plugin state: " + "; ".join(anomalies)),
                       anomalies=anomalies,
                       recovery="nothing was changed; resolve the conflicting state through the lifecycle that created it")
    elif registration == "none":
        routing.update(status="not-required",
                       reason=("no native pstack registration exists here; a model sheet, visible shared Skills or "
                               "a cached copy alone never routes tasks"),
                       shared_skills_note=("shared Skills stay available for explicit per-task selection; a native "
                                           "plugin is optional and never required for compatibility"
                                           if shared_visible else None))
    elif sheet.get("present") is None and "error" in sheet:
        routing.update(status="blocked", reason=sheet["error"],
                       recovery="nothing was changed; inspect the sheet, then run transition-plan again")
    elif hook == "off":
        routing.update(status="not-required",
                       reason="the sheet's exact '" + HOOK_OFF + "' line keeps SessionStart auto-routing off")
    elif receipt is not None:
        try:
            embedded = make_plan(source=None, workspace=workspace, codex_home=home, codex_bin=binary,
                                 operation="install", coexistence=True, hub_root=hub_root)
        except common.IntegrationError as exc:
            routing.update(status="blocked", reason=str(exc),
                           steps=["resolve the reported blocker through this entry, then run transition-plan again"],
                           recovery="the interrupted operation keeps its receipt; a fresh plan resumes it, or "
                                    "'plan --operation remove' exits it")
        else:
            routing.update(
                status="applicable", plan_id=embedded["plan_id"], owner="hub-pstack-adapter",
                sheet_change=(embedded["coexistence"] or {}).get("sheet_change"),
                preserved=("every byte outside the 'session hook' line — all model rows, host mappings, the default "
                           "effort line, the encoding and the line endings — keeps its exact value"),
                apply={"entry": "python scripts/azhou_hub.py integrations pstack apply --coexistence",
                       "plan_id": embedded["plan_id"],
                       "recheck": "apply re-runs the plan against the bound source and target and stops on any drift"},
                recovery=("the exact prior sheet bytes (or the sheet's absence) reach the receipt before the sheet "
                          "changes; 'plan --operation remove' restores them; later user edits stop automatic restore "
                          "with the recorded and observed digests"))
    else:
        installed_rows = registry.get("installed_plugins") or []
        actual = "no native registry record was found for it; its source is unknown"
        if installed_rows:
            actual = json.dumps(installed_rows[0].get("marketplaceSource")
                                or installed_rows[0].get("source"), sort_keys=True)
        routing.update(status="blocked",
                       reason=("the armed native pstack installation has no Hub ownership receipt; the Hub neither "
                               "adopts installations by name or byte-identical content nor writes around an "
                               "unowned installation"),
                       actual_source=actual, steps=foreign_steps, recovery=foreign_recovery)
    transitions = [routing]

    if registration in ("single", "config-only"):
        ownership: dict
        if receipt is not None and receipt.get("state") == "installed":
            ownership = {"goal": "keep the native installation under one named owner",
                         "status": "owned",
                         "owner": "hub-pstack-adapter receipt and the native Codex plugin manager",
                         "source": {"snapshot": receipt.get("snapshot"),
                                    "source_lock_sha256": receipt.get("source_lock_sha256")},
                         "pinned_source_changed": receipt.get("source_lock_sha256") != origin["source_lock_sha256"],
                         "next": "doctor verifies installed files and registration; 'plan --operation remove' exits "
                                 "through this entry and restores the adapter-owned sheet change"}
        elif receipt is not None:
            ownership = {"goal": "keep the native installation under one named owner",
                         "status": "owned-operation-unfinished", "receipt_state": receipt.get("state"),
                         "next": "a fresh plan/apply resumes the recorded operation, or 'plan --operation remove' "
                                 "cleans up only what the receipt records"}
        else:
            installed_rows = registry.get("installed_plugins") or []
            ownership = {"goal": "keep the native installation under one named owner",
                         "status": "not-adopted",
                         "reason": ("the native installation has no Hub ownership receipt; a matching name or "
                                    "byte-identical content is not a takeover basis"),
                         "owner": "the lifecycle that installed it (the native Codex plugin manager)",
                         "actual_source": (json.dumps(installed_rows[0].get("marketplaceSource")
                                                      or installed_rows[0].get("source"), sort_keys=True)
                                           if installed_rows
                                           else "no native registry record was found for it; its source is unknown"),
                         "content_vs_pinned": (installed_report or
                                               {"detail": "registration exists only in config.toml; there is no "
                                                          "plugin copy to compare"}),
                         "optional_migration": foreign_steps,
                         "recovery": foreign_recovery}
        transitions.append(ownership)

    if shared_report is not None:
        summary = {name: {key: row[key] for key in
                          ("kind", "target", "status", "modified_count", "missing_count", "extra_count") if key in row}
                   for name, row in shared_report["skills"].items()}
        shared_transition = {"goal": "keep using shared pstack Skills on demand, with every local modification preserved",
                             "status": "preserved-with-differences" if shared_drift else "preserved",
                             "owner": "the user's shared Skills directory; no Hub entry writes it",
                             "differences": summary,
                             "forced_conversion": "none: compatibility never requires turning shared Skills into a native plugin"}
        if shared_drift:
            shared_transition["steps"] = [
                "keep the local differences (the default): nothing rewrites this directory, and the Skills stay "
                "usable on demand",
                "or migrate a skill after review: compare each listed file with the pinned package content "
                "(source_lock_sha256 below), back up the shared copy, then replace the reviewed files yourself; "
                "the Hub performs no write here",
            ]
        transitions.append(shared_transition)

    return {
        "schema": TRANSITION_SCHEMA,
        "read_only": "this report writes nothing; each transition applies only through the reviewed plan of the entry that owns it",
        "workspace": str(workspace), "codex_home": str(home),
        "skills_dir": str(shared) if shared is not None else None,
        "codex_bin": str(binary), "codex_bin_sha256": _digest(binary),
        "pinned_source": {"source": origin["source"], "package": origin["package"], "version": origin["version"],
                          "commit": origin["commit"], "commit_scope": origin["commit_scope"],
                          "source_lock_sha256": origin["source_lock_sha256"], "locked_files": origin["locked_files"]},
        "facets": {"hub_receipt": ({"state": receipt.get("state"),
                                    "source_lock_sha256": receipt.get("source_lock_sha256"),
                                    "snapshot": receipt.get("snapshot")} if receipt is not None
                                   else {"state": "none", "error": receipt_error}),
                   "kit": kit,
                   "sheet": sheet,
                   "native_registration": {"copies": [str(path) for path in copies],
                                            "config_registered": config_registered,
                                            "classification": registration,
                                            "anomalies": anomalies},
                   "native_registry": registry,
                   "installed_copy_vs_pinned": installed_report,
                   "shared_skills": shared_report},
        "compatibility": verdict,
        "recognized_states": states,
        "transitions": transitions,
        "review_before_main_environment": {
            "review": ["the recognized states and the compatibility verdict above",
                       "every content difference against the pinned package (source_lock_sha256 "
                       + origin["source_lock_sha256"] + ")",
                       "each transition's owner, target change and recovery basis; unknown history is never claimed restorable"],
            "operations": ["apply an 'applicable' transition only through its named entry and plan id, after "
                           "re-reading the fresh plan it re-checks",
                           "resolve a 'blocked' transition through its listed steps; the Hub writes nothing around "
                           "installations it does not own"],
            "boundary": "shipping this entry does not authorize applying any transition to the main environment, "
                        "moving local Skills, or restarting a host; each application is a separate reviewed decision",
        },
    }


def apply_plan(plan: dict, *, plan_id: str, hub_root: Path = ROOT) -> dict:
    if plan_id != plan.get("plan_id"):
        raise common.IntegrationError("plan-id mismatch; review a fresh plan before applying")
    workspace, home, binary = Path(plan["workspace"]), Path(plan["codex_home"]), Path(plan["codex_bin"])
    receipt_file = _receipt_path(workspace, home)
    with _operation_lock(receipt_file):
        replay = None
        if plan["operation"] == "install":
            replay = True if (plan.get("coexistence") or {}).get("requested") else None
        fresh = make_plan(source=Path(plan["source"]["source"]) if plan["operation"] == "install" else None,
                          workspace=workspace, codex_home=home, codex_bin=binary,
                          operation=plan["operation"], coexistence=replay, hub_root=hub_root)
        if fresh["plan_id"] != plan_id:
            raise common.IntegrationError("target, source or Codex binary changed after the plan")
        old = common.read_receipt(receipt_file) if receipt_file.exists() else {}
        # A completed install is a no-op only when the fresh plan has nothing
        # pending. An existing receipt updated to coexistence rules still owes
        # its reviewed sheet conversion, so it must be applied, not skipped.
        pending_sheet = (plan.get("coexistence") or {}).get("sheet_change")
        if plan["operation"] == "install" and old.get("state") == "installed" and not pending_sheet:
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
                   "commands": [], "completed_steps": old.get("completed_steps", []) if old.get("operation") == plan["operation"] else [],
                   "coexistence": old.get("coexistence")}
        common.write_receipt(receipt_file, receipt)
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            sheet_change = (plan.get("coexistence") or {}).get("sheet_change") if plan["operation"] == "install" else None
            if sheet_change:
                _establish_sheet(home, sheet_change, receipt, receipt_file)
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
            if plan["operation"] == "remove":
                record = (receipt.get("coexistence") or {}).get("sheet")
                if record:
                    _restore_sheet(home, record)
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
    parser.add_argument("command", choices=("plan", "apply", "doctor", "transition-plan"))
    parser.add_argument("--source", type=Path, help="optional assertion of the in-repository package path")
    parser.add_argument("--workspace", type=Path, required=True,
                        help="workspace for private source snapshots and lifecycle receipts")
    parser.add_argument("--codex-home", type=Path, required=True,
                        help="explicit configuration target; custom homes require CODEX_HOME on launch")
    parser.add_argument("--codex-bin", type=Path, required=True, help="explicit native Codex executable")
    parser.add_argument("--operation", choices=("install", "remove"), default="install")
    parser.add_argument("--coexistence", action="store_true",
                        help="install pstack with SessionStart auto-routing off, ready to share the target with the Kit")
    parser.add_argument("--skills-dir", type=Path, default=None,
                        help="transition-plan only: a shared Skills root compared read-only against the pinned package")
    parser.add_argument("--plan-id")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(workspace=args.workspace, codex_home=args.codex_home, codex_bin=args.codex_bin, hub_root=hub_root)
        elif args.command == "transition-plan":
            result = transition(workspace=args.workspace, codex_home=args.codex_home, codex_bin=args.codex_bin,
                                skills_dir=args.skills_dir, hub_root=hub_root)
        else:
            result = make_plan(source=args.source, workspace=args.workspace, codex_home=args.codex_home,
                               codex_bin=args.codex_bin, operation=args.operation,
                               coexistence=True if args.coexistence else None, hub_root=hub_root)
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

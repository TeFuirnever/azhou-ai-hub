"""Fixed Codex adapter; Agent Orchestration Kit remains the installer owner.

The Hub never merges Codex settings. It delegates to the locked native installer
and keeps a private, exact rollback record for the files that invocation changed.
Rollback is conservative: any subsequent edit blocks it before target writes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

try:
    from . import integration_common as common
    from . import azhou_runtime_state as state
except ImportError:
    import integration_common as common
    import azhou_runtime_state as state

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "model-router"
RECEIPT_SCHEMA = "azhou-hub.model-router-install.v1"


def _path(value: Path, *, executable: bool = False) -> Path:
    value = Path(value).expanduser()
    if not value.is_absolute() or value.is_symlink() or value.parent.is_symlink():
        raise common.IntegrationError(f"explicit absolute non-symlink path required: {value}")
    resolved = value.resolve()
    if executable and (not resolved.is_file() or not os.access(resolved, os.X_OK)):
        raise common.IntegrationError(f"Codex executable missing or not executable: {resolved}")
    return resolved


def _module(snapshot: Path, filename: str, *, hub_root: Path = ROOT):
    """Load hash-verified source without leaving bytecode in the source tree."""
    path = snapshot / "scripts" / filename
    manifest = (common.snapshot_lock(COMPONENT, snapshot) if (snapshot / ".hub-source.json").exists()
                else common.load_lock(COMPONENT, hub_root=hub_root))
    expected = manifest["files"]["scripts/" + filename]
    if path.is_symlink() or path.parent.is_symlink():
        raise common.IntegrationError("native installer module cannot be a symlink")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise common.IntegrationError("native installer changed before loading")
    module = types.ModuleType("azhou_locked_" + path.stem)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _fingerprint(path: Path, installer) -> dict:
    installer.check_parents(path)
    raw = installer.regular_bytes(path)
    return {"sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            "mode": stat.S_IMODE(path.stat().st_mode) if raw is not None else None}


def _receipt_path(workspace: Path, codex_home: Path, skills_dir: Path) -> Path:
    target = common.plan_digest({"codex_home": str(codex_home), "skills_dir": str(skills_dir)})
    try:
        return state.state_path(workspace, "hub", "model-router", target, "install.json")
    except state.StateError as exc:
        raise common.IntegrationError(str(exc)) from exc


def _allowed_targets(codex_home: Path, skills_dir: Path, installer) -> set[Path]:
    return {codex_home / "config.toml", codex_home / "AGENTS.md",
            codex_home / "agent-orchestration-kit/state.json",
            skills_dir / "astra-orchestrator/SKILL.md",
            *(codex_home / f"agents/{name}.toml" for name in installer.ROLE_MODELS)}


def _pstack_coexistence(codex_home: Path, skills_dir: Path, installer) -> dict:
    """One verdict, from the Kit's own shipped implementation.

    The Hub entry and the Kit's direct entry must reach the same conclusion
    for the same target, so the judgment lives in the hash-verified installer
    module and both entries call it. Registration plus the sheet's routing
    switch decide compatibility; a sheet, visible Skills, or a cached copy
    alone is not routing evidence.
    """
    try:
        verdict = installer.pstack_coexistence(codex_home, skills_dir)
    except common.IntegrationError:
        raise
    except Exception as exc:
        raise common.IntegrationError(f"pstack compatibility could not be established: {exc}") from exc
    if not verdict["compatible"]:
        raise common.IntegrationError(verdict["reason"])
    return verdict


def _receipt(path: Path, codex_home: Path, skills_dir: Path, installer) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    receipt = common.read_receipt(path)
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("component") != COMPONENT:
        raise common.IntegrationError("unrecognized model-router receipt")
    if receipt.get("codex_home") != str(codex_home) or receipt.get("skills_dir") != str(skills_dir):
        raise common.IntegrationError("model-router receipt target mismatch")
    allowed = _allowed_targets(codex_home, skills_dir, installer)
    if any(set(map(Path, receipt.get(key, {}))) != allowed for key in ("before", "after")):
        raise common.IntegrationError("model-router receipt has unexpected or missing targets")
    journal = receipt.get("rollback", {})
    if journal.get("schema") != 1 or journal.get("created_directories") != []:
        raise common.IntegrationError("unrecognized rollback journal")
    if any(Path(item.get("path", "")) not in allowed for item in journal.get("files", [])):
        raise common.IntegrationError("rollback journal contains an unowned target")
    seen = set()
    for item in journal["files"]:
        name = item["path"]
        before = base64.b64decode(item["before"], validate=True) if item["before"] is not None else None
        digest = hashlib.sha256(before).hexdigest() if before is not None else None
        if name in seen or digest != receipt["before"][name]["sha256"] or item["after_sha256"] != receipt["after"][name]["sha256"]:
            raise common.IntegrationError("rollback content does not match the recorded before/after state")
        expected_mode = receipt["before"][name]["mode"] if before is not None else 0o600
        if item["mode"] != expected_mode:
            raise common.IntegrationError("rollback permissions do not match the recorded original mode")
        seen.add(name)
    if seen != {name for name in receipt["after"] if receipt["before"][name] != receipt["after"][name]}:
        raise common.IntegrationError("rollback journal does not cover exactly the changed targets")
    return receipt


def _mode_text(mode: int | None) -> str:
    return f"{mode:o}" if mode is not None else "absent"


def _difference(expected: dict, current: dict) -> str:
    """Render one owned target's recorded-versus-observed difference."""
    return (f"(recorded sha256 {expected['sha256']}, found sha256 {current['sha256']}, "
            f"mode {_mode_text(expected['mode'])} found {_mode_text(current['mode'])})")


def _assert_unchanged(receipt: dict, installer) -> None:
    for name, expected in receipt["after"].items():
        current = _fingerprint(Path(name), installer)
        if current != expected:
            raise common.IntegrationError(
                f"installed target changed; refusing automatic restore or overwrite: {name} " + _difference(expected, current))


def _assert_recoverable(receipt: dict, installer) -> None:
    for name, after in receipt["after"].items():
        current = _fingerprint(Path(name), installer)
        if current not in (receipt["before"][name], after):
            raise common.IntegrationError(f"concurrent edit prevents recovery: {name} " + _difference(after, current))


def make_plan(source: Path, workspace: Path, codex_home: Path, skills_dir: Path,
              codex_bin: Path, *, hub_root: Path = ROOT) -> tuple[dict, dict, object]:
    origin = common.inspect_source(COMPONENT, source, hub_root=hub_root)
    source = Path(origin["source"])
    workspace, codex_home, skills_dir = map(_path, (workspace, codex_home, skills_dir))
    runtime = _path(codex_bin, executable=True)
    for target in (workspace, codex_home, skills_dir):
        if target == source or source in target.parents:
            raise common.IntegrationError("runtime and target writes must remain outside the read-only source")
    installer = _module(source, "install_codex.py", hub_root=hub_root)
    pstack = _pstack_coexistence(codex_home, skills_dir, installer)
    native = installer.build_plan(source, codex_home, skills_dir)
    common.inspect_source(COMPONENT, source, hub_root=hub_root)
    receipt_path = _receipt_path(workspace, codex_home, skills_dir)
    previous = _receipt(receipt_path, codex_home, skills_dir, installer)
    if previous and previous["status"] in ("pending", "uninstalling"):
        raise common.IntegrationError("unfinished Hub operation; run recover with the same explicit targets")
    if previous and previous["status"] == "installed":
        if previous["source_lock_sha256"] != origin["source_lock_sha256"]:
            raise common.IntegrationError("restore the prior fixed version before selecting a new source lock")
        _assert_unchanged(previous, installer)
    summary = {
        "schema": "azhou-hub.model-router-plan.v1", "component": COMPONENT,
        "source": str(source), "source_commit": origin["commit"],
        "source_lock_sha256": origin["source_lock_sha256"], "workspace": str(workspace),
        "codex_home": str(codex_home), "skills_dir": str(skills_dir),
        "codex_bin": str(runtime), "codex_bin_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
        "profile": installer.PROFILE, "native_owner": "agent-orchestration-kit",
        "before": {str(p): _fingerprint(p, installer) for p in sorted(native["watched"])},
        "changes": {str(p): hashlib.sha256(raw).hexdigest() for p, raw in sorted(native["changes"].items())},
        "receipt": str(receipt_path), "native_preflight": "performed by apply before target writes",
        "execution_evidence": "native discovery is not model invocation",
        "composition": "one workflow owner per task; ordinary tasks keep these defaults, a user-selected pstack workflow owns its task",
        "coexistence": pstack,
        "restore": "restore only this Hub invocation's exact changes; pre-existing installation is restored, not removed",
    }
    summary["plan_id"] = common.plan_digest(summary)
    return summary, native, installer


def _native_checks(snapshot: Path, codex_home: Path, native_plan: dict, runtime_path: Path, *, hub_root: Path = ROOT):
    native = _module(snapshot, "codex_native.py", hub_root=hub_root)
    runtime = native.select_runtime(str(runtime_path))
    native.preflight_runtime(runtime)
    native.validate_config(runtime, native_plan["config_text"], native_plan["roles"])
    return native, runtime


def apply(source: Path, workspace: Path, codex_home: Path, skills_dir: Path, codex_bin: Path,
          plan_id: str, *, hub_root: Path = ROOT) -> dict:
    summary, _, _ = make_plan(source, workspace, codex_home, skills_dir, codex_bin, hub_root=hub_root)
    if summary["plan_id"] != plan_id:
        raise common.IntegrationError("plan is stale or differs from reviewed targets; run plan again")
    workspace, codex_home, skills_dir = (Path(summary[k]) for k in ("workspace", "codex_home", "skills_dir"))
    snapshot = common.snapshot_source(COMPONENT, source, workspace, hub_root=hub_root,
                                      expected_digest=summary["source_lock_sha256"])
    installer = _module(snapshot, "install_codex.py", hub_root=hub_root)
    plan = installer.build_plan(snapshot, codex_home, skills_dir)
    native, runtime = _native_checks(snapshot, codex_home, plan, Path(summary["codex_bin"]), hub_root=hub_root)
    _pstack_coexistence(codex_home, skills_dir, installer)
    # Native preflight may take time. Bind all writes to the reviewed before-state.
    if {str(p): _fingerprint(p, installer) for p in sorted(plan["watched"])} != summary["before"]:
        raise common.IntegrationError("target changed during native preflight")
    if hashlib.sha256(Path(summary["codex_bin"]).read_bytes()).hexdigest() != summary["codex_bin_sha256"]:
        raise common.IntegrationError("Codex runtime changed during preflight")
    receipt_path = Path(summary["receipt"])
    previous = _receipt(receipt_path, codex_home, skills_dir, installer)
    evidence = {}
    def verify_native():
        evidence.update(native.verify_native(runtime, codex_home, workspace,
                                             installer.ROLE_MODELS, plan["skill_path"], installer.SETTINGS))
    if previous and previous["status"] == "installed":
        if plan["changes"]:
            raise common.IntegrationError("existing Hub installation differs from the fixed version")
        count = installer.apply_plan(plan, verify_native)
        return {"status": "installed", "changed_files_count": count, "receipt": str(receipt_path),
                "native_discovery": evidence, "actual_invocation": "not performed"}
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.ensure_private_directory(receipt_path.parent, root=workspace)
    after = dict(summary["before"])
    rollback = {"schema": 1, "created_directories": [], "files": []}
    for path, desired in plan["changes"].items():
        before = plan["watched"][path]
        mode = summary["before"][str(path)]["mode"] if before is not None else 0o600
        after[str(path)] = {"sha256": hashlib.sha256(desired).hexdigest(), "mode": mode}
        rollback["files"].append({"path": str(path),
                                  "before": base64.b64encode(before).decode("ascii") if before is not None else None,
                                  "mode": mode, "after_sha256": hashlib.sha256(desired).hexdigest()})
    receipt = {"schema": RECEIPT_SCHEMA, "component": COMPONENT, "status": "pending",
               "source_lock_sha256": summary["source_lock_sha256"], "snapshot": str(snapshot),
               "workspace": str(workspace),
               "codex_home": str(codex_home), "skills_dir": str(skills_dir), "codex_bin": str(runtime["path"]),
               "before": summary["before"], "after": after, "rollback": rollback,
               "plan_id": plan_id, "native_owner": "agent-orchestration-kit"}
    common.write_receipt(receipt_path, receipt)
    try:
        count = installer.apply_plan(plan, verify_native)
    except BaseException:
        if all(_fingerprint(Path(p), installer) == fp for p, fp in receipt["before"].items()):
            receipt["status"] = "rolled_back"
            common.write_receipt(receipt_path, receipt)
        raise
    receipt.update(status="installed", native_discovery=evidence)
    common.write_receipt(receipt_path, receipt)
    return {"status": "installed", "changed_files_count": count, "receipt": str(receipt_path),
            "native_discovery": evidence, "actual_invocation": "not performed"}


def _installed(workspace: Path, codex_home: Path, skills_dir: Path, *, hub_root: Path = ROOT):
    workspace, codex_home, skills_dir = map(_path, (workspace, codex_home, skills_dir))
    path = _receipt_path(workspace, codex_home, skills_dir)
    raw = common.read_receipt(path)
    snapshot = _path(Path(raw["snapshot"]))
    common.verify_snapshot(COMPONENT, snapshot, hub_root=hub_root)
    installer = _module(snapshot, "install_codex.py", hub_root=hub_root)
    receipt = _receipt(path, codex_home, skills_dir, installer)
    if not receipt or receipt.get("status") not in ("installed", "pending", "uninstalling"):
        raise common.IntegrationError("no active installation receipt for these targets")
    if receipt.get("workspace") != str(workspace):
        raise common.IntegrationError("model-router receipt workspace mismatch")
    return path, receipt, snapshot, installer


def verify(workspace: Path, codex_home: Path, skills_dir: Path, *, hub_root: Path = ROOT) -> dict:
    _, receipt, snapshot, installer = _installed(workspace, codex_home, skills_dir, hub_root=hub_root)
    if receipt["status"] != "installed":
        raise common.IntegrationError("recover the interrupted operation before verifying")
    _assert_unchanged(receipt, installer)
    native = _module(snapshot, "codex_native.py", hub_root=hub_root)
    runtime = native.select_runtime(receipt["codex_bin"])
    evidence = native.verify_native(runtime, Path(receipt["codex_home"]), Path(receipt["workspace"]),
                                   installer.ROLE_MODELS, Path(receipt["skills_dir"]) / "astra-orchestrator/SKILL.md",
                                   installer.SETTINGS)
    return {"status": "discovered", "native_discovery": evidence, "actual_invocation": "not performed"}


def uninstall_plan(workspace: Path, codex_home: Path, skills_dir: Path, *, hub_root: Path = ROOT) -> dict:
    path, receipt, _, installer = _installed(workspace, codex_home, skills_dir, hub_root=hub_root)
    if receipt["status"] != "installed":
        raise common.IntegrationError("recover the interrupted operation before uninstalling")
    _assert_unchanged(receipt, installer)
    plan = {"schema": "azhou-hub.model-router-restore.v1", "receipt": str(path),
            "receipt_digest": receipt["integrity_digest"], "codex_home": receipt["codex_home"],
            "skills_dir": receipt["skills_dir"], "changed_files": [i["path"] for i in receipt["rollback"]["files"]],
            "behavior": "restore exact pre-Hub files; leave other files, empty directories and existing sessions alone"}
    plan["plan_id"] = common.plan_digest(plan)
    return plan


def _restore_identity(receipt: dict, installed_digest: str, plan_id: str) -> dict:
    return {"schema": "azhou-hub.model-router-restore-owner.v1", "component": COMPONENT,
            "workspace": receipt["workspace"], "codex_home": receipt["codex_home"],
            "skills_dir": receipt["skills_dir"], "source_lock_sha256": receipt["source_lock_sha256"],
            "installed_receipt_digest": installed_digest, "restore_plan_id": plan_id,
            "rollback_sha256": common.plan_digest(receipt["rollback"])}


def _verify_restore_transaction(transaction: Path, identity: dict, installer) -> None:
    installer.check_parents(transaction)
    if transaction.is_symlink() or not transaction.is_dir():
        raise common.IntegrationError("restore transaction is missing, unowned or a symlink")
    contents = list(transaction.iterdir())
    if {p.name for p in contents} != {"owner.json"} or any(p.is_symlink() or not p.is_file() for p in contents):
        raise common.IntegrationError("restore transaction contains unowned or unexpected contents")
    owner = common.read_receipt(transaction / "owner.json")
    owner.pop("integrity_digest", None)
    if owner != identity:
        raise common.IntegrationError("restore transaction ownership does not match this plan and receipt")


def uninstall(workspace: Path, codex_home: Path, skills_dir: Path, plan_id: str,
              *, hub_root: Path = ROOT) -> dict:
    plan = uninstall_plan(workspace, codex_home, skills_dir, hub_root=hub_root)
    if plan["plan_id"] != plan_id:
        raise common.IntegrationError("restore plan is stale; run uninstall-plan again")
    path, receipt, _, installer = _installed(workspace, codex_home, skills_dir, hub_root=hub_root)
    transaction = path.parent / "restore-transaction"
    installer.check_parents(transaction)
    try:
        transaction.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise common.IntegrationError("restore transaction path already exists; refusing to adopt or remove it") from exc
    identity = _restore_identity(receipt, receipt["integrity_digest"], plan_id)
    common.write_receipt(transaction / "owner.json", identity)
    _verify_restore_transaction(transaction, identity, installer)
    receipt["restore_transaction"] = identity
    receipt["status"] = "uninstalling"
    common.write_receipt(path, receipt)
    # Reuse native conservative restore, including its concurrent-edit checks.
    _verify_restore_transaction(transaction, identity, installer)
    installer.restore(receipt["rollback"], transaction)
    receipt["status"] = "restored"
    common.write_receipt(path, receipt)
    return {"status": "restored", "receipt": str(path), "behavior": plan["behavior"]}


def recover(workspace: Path, codex_home: Path, skills_dir: Path, *, hub_root: Path = ROOT) -> dict:
    path, receipt, snapshot, installer = _installed(workspace, codex_home, skills_dir, hub_root=hub_root)
    codex_home, skills_dir = Path(receipt["codex_home"]), Path(receipt["skills_dir"])
    _assert_recoverable(receipt, installer)
    if receipt["status"] == "uninstalling":
        transaction = path.parent / "restore-transaction"
        identity = receipt.get("restore_transaction")
        if not isinstance(identity, dict) or identity != _restore_identity(
                receipt, identity.get("installed_receipt_digest"), identity.get("restore_plan_id")):
            raise common.IntegrationError("missing or invalid restore transaction ownership")
        if not transaction.exists() and not transaction.is_symlink():
            # Native restore may have completed before the final receipt write.
            # Finalize only if every observed target is exactly its before-state.
            if any(_fingerprint(Path(p), installer) != fp for p, fp in receipt["before"].items()):
                raise common.IntegrationError("restore transaction missing before rollback completed")
        else:
            _verify_restore_transaction(transaction, identity, installer)
            installer.restore(receipt["rollback"], transaction)
        receipt["status"] = "restored"
    elif receipt["status"] == "pending":
        native_tx = codex_home / ".agent-orchestration-kit-transaction"
        if native_tx.exists() or native_tx.is_symlink():
            installer.check_parents(native_tx)
            if native_tx.is_symlink() or not native_tx.is_dir() or {p.name for p in native_tx.iterdir()} != {"journal.json"}:
                raise common.IntegrationError("native recovery transaction has unowned or unexpected contents")
            installer.recover(codex_home, skills_dir)
        if all(_fingerprint(Path(p), installer) == fp for p, fp in receipt["before"].items()):
            receipt["status"] = "rolled_back"
        else:
            _assert_unchanged(receipt, installer)
            native = _module(snapshot, "codex_native.py", hub_root=hub_root)
            runtime = native.select_runtime(receipt["codex_bin"])
            receipt["native_discovery"] = native.verify_native(runtime, codex_home, Path(receipt["workspace"]),
                installer.ROLE_MODELS, skills_dir / "astra-orchestrator/SKILL.md", installer.SETTINGS)
            receipt["status"] = "installed"
    else:
        # An interruption after exclusive preparation but before receipt update
        # can leave our owner marker. Delete only the verified marker and empty
        # directory; never recursively adopt an existing path.
        transaction = path.parent / "restore-transaction"
        if not transaction.exists() and not transaction.is_symlink():
            raise common.IntegrationError("no interrupted Hub operation exists")
        plan = uninstall_plan(workspace, codex_home, skills_dir, hub_root=hub_root)
        identity = _restore_identity(receipt, receipt["integrity_digest"], plan["plan_id"])
        _verify_restore_transaction(transaction, identity, installer)
        (transaction / "owner.json").unlink()
        transaction.rmdir()
    common.write_receipt(path, receipt)
    return {"status": receipt["status"], "receipt": str(path)}


def main(argv: list[str] | None = None, *, hub_root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description="Opt-in fixed Codex model routing; explicit targets only")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply", "verify", "uninstall-plan", "uninstall", "recover"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", type=Path, required=True)
        command.add_argument("--codex-home", type=Path, required=True)
        command.add_argument("--skills-dir", type=Path, required=True)
        command.add_argument("--json", action="store_true")
        if name in ("plan", "apply"):
            command.add_argument("--source", type=Path, help="optional assertion of the in-repository package path")
            command.add_argument("--codex-bin", type=Path, required=True)
        if name in ("apply", "uninstall"):
            command.add_argument("--plan-id", required=True)
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0].startswith("--") and values[0] not in ("--help", "-h"):
        values.insert(0, "plan")
    args = parser.parse_args(values)
    try:
        targets = (args.workspace, args.codex_home, args.skills_dir)
        if args.command == "plan":
            result = make_plan(args.source, *targets, args.codex_bin, hub_root=hub_root)[0]
        elif args.command == "apply":
            result = apply(args.source, *targets, args.codex_bin, args.plan_id, hub_root=hub_root)
        elif args.command == "uninstall":
            result = uninstall(*targets, args.plan_id, hub_root=hub_root)
        else:
            result = {"verify": verify, "uninstall-plan": uninstall_plan, "recover": recover}[args.command](
                *targets, hub_root=hub_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

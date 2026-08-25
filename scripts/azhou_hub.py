#!/usr/bin/env python3
"""Harness-neutral setup, diagnostics, information, and verification for Azhou AI Hub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
COMMANDS = ["doctor", "info", "setup", "verify", "version"]
IGNORED_PACKAGE_PARTS = {".git", ".omc", ".omx", ".venv", "__pycache__", "node_modules"}


class PackageError(RuntimeError):
    """Raised when a source package cannot be copied or compared safely."""


def _setup_failure(target: Path, mode: str, error: str) -> dict[str, Any]:
    return {
        "schema_version": "azhou-ai-hub.setup.v1",
        "status": "fail",
        "mode": mode,
        "target": str(target),
        "applied": False,
        "error": error,
        "skills": [],
    }


def canonical_skills(root: Path = ROOT) -> list[str]:
    """Return canonical skill names from the repository package surface."""
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(path.parent.name for path in skills_root.glob("*/SKILL.md") if path.is_file())


def _git_command(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def revision_info(root: Path = ROOT) -> dict[str, Any]:
    status = _git_command(root, "status", "--porcelain")
    return {
        "commit": _git_command(root, "rev-parse", "HEAD") or "unknown",
        "branch": _git_command(root, "branch", "--show-current") or "unknown",
        "dirty": None if status is None else bool(status),
    }


def info_payload(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": "azhou-ai-hub.info.v1",
        "project": "azhou-ai-hub",
        "repository": str(root.resolve()),
        "revision": revision_info(root),
        "python": {
            "executable": sys.executable,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "minimum": ".".join(str(part) for part in MIN_PYTHON),
        },
        "installable_skills": canonical_skills(root),
        "commands": COMMANDS,
        "verification_command": "python3 scripts/verify.py",
        "support_matrix": "docs/support-matrix.md",
    }


def version_payload(root: Path = ROOT) -> dict[str, Any]:
    revision = revision_info(root)
    return {
        "schema_version": "azhou-ai-hub.version.v1",
        "commit": revision["commit"],
        "branch": revision["branch"],
        "dirty": revision["dirty"],
        "release_version": None,
        "version_authority": "git revision; no installed release metadata is claimed",
    }


def _is_package_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return not any(part in IGNORED_PACKAGE_PARTS for part in relative.parts) and path.name != ".DS_Store"


def _package_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in source.rglob("*"):
        if not _is_package_path(path, source):
            continue
        if path.is_symlink():
            raise PackageError(f"package contains unsupported symlink: {path.relative_to(source)}")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(source).as_posix())


def package_digest(source: Path) -> str:
    digest = hashlib.sha256()
    for path in _package_files(source):
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _target_root_error(target: Path) -> str | None:
    cursor = target
    while not cursor.exists() and cursor != cursor.parent:
        cursor = cursor.parent
    if cursor.exists() and not cursor.is_dir():
        if cursor == target:
            return "target root exists and is not a directory"
        return f"target ancestor is not a directory: {cursor}"
    return None


def canonical_source(root: Path, name: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise PackageError(f"invalid canonical skill name: {name!r}")
    skills_root = (root / "skills").resolve()
    source = (skills_root / name).resolve()
    try:
        source.relative_to(skills_root)
    except ValueError as exc:
        raise PackageError(f"skill source escapes canonical root: {name!r}") from exc
    return source


def inspect_installation(source: Path, destination: Path, mode: str) -> tuple[str, str]:
    if not (source / "SKILL.md").is_file():
        return "conflict", "canonical source package is missing SKILL.md"
    if destination.is_symlink():
        if mode == "link" and _same_resolved_path(source, destination):
            return "current", "canonical symlink already installed"
        return "conflict", f"destination symlink resolves to {destination.resolve()}"
    if not destination.exists():
        return "planned", f"will {mode} canonical package"
    if not destination.is_dir():
        return "conflict", "destination exists and is not a directory"
    if mode == "copy":
        try:
            if package_digest(source) == package_digest(destination):
                return "current", "installed copy matches canonical package digest"
        except (OSError, PackageError) as exc:
            return "conflict", f"cannot compare package digest: {exc}"
    return "conflict", "destination exists with different or unowned content"


def _copy_package(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    try:
        for path in _package_files(source):
            relative = path.relative_to(source)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target, follow_symlinks=False)
        os.replace(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def setup_skills(
    *,
    root: Path,
    target: Path,
    skills: Iterable[str],
    mode: str,
    dry_run: bool,
) -> dict[str, Any]:
    if mode not in {"copy", "link"}:
        raise ValueError(f"unsupported setup mode: {mode}")

    target = target.expanduser().resolve()
    target_error = _target_root_error(target)
    if target_error:
        return _setup_failure(target, mode, target_error)
    rows: list[dict[str, str]] = []
    for name in sorted(set(skills)):
        try:
            source = canonical_source(root, name)
        except PackageError as exc:
            rows.append(
                {
                    "name": name,
                    "status": "conflict",
                    "details": str(exc),
                    "source": "",
                    "destination": str(target / name),
                }
            )
            continue
        destination = target / name
        status, details = inspect_installation(source, destination, mode)
        rows.append(
            {
                "name": name,
                "status": status,
                "details": details,
                "source": str(source),
                "destination": str(destination),
            }
        )

    if any(row["status"] == "conflict" for row in rows):
        return {
            "schema_version": "azhou-ai-hub.setup.v1",
            "status": "fail",
            "mode": mode,
            "target": str(target),
            "applied": False,
            "skills": rows,
        }

    if dry_run:
        return {
            "schema_version": "azhou-ai-hub.setup.v1",
            "status": "dry_run",
            "mode": mode,
            "target": str(target),
            "applied": False,
            "skills": rows,
        }

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _setup_failure(target, mode, f"cannot create target root: {exc}")
    for row in rows:
        if row["status"] != "planned":
            continue
        source = Path(row["source"])
        destination = Path(row["destination"])
        try:
            if mode == "link":
                destination.symlink_to(source, target_is_directory=True)
            else:
                _copy_package(source, destination)
        except (OSError, PackageError) as exc:
            row["status"] = "error"
            row["details"] = str(exc)
            continue
        row["status"] = "installed"
        row["details"] = f"canonical package {mode} installed"

    failed = any(row["status"] in {"conflict", "error"} for row in rows)
    return {
        "schema_version": "azhou-ai-hub.setup.v1",
        "status": "fail" if failed else "pass",
        "mode": mode,
        "target": str(target),
        "applied": True,
        "skills": rows,
    }


def _check(name: str, status: str, details: str) -> dict[str, str]:
    return {"name": name, "status": status, "details": details}


def run_doctor(
    *,
    root: Path,
    target: Path | None,
    skills: Iterable[str],
    run_verification: bool,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    required = [root / "README.md", root / "docs/skill-standard.md", root / "scripts/verify.py"]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    checks.append(
        _check(
            "repository_shape",
            "fail" if missing else "pass",
            "missing: " + ", ".join(missing) if missing else "required repository entry points are present",
        )
    )

    python_ok = sys.version_info >= MIN_PYTHON
    checks.append(
        _check(
            "python",
            "pass" if python_ok else "fail",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}; requires {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+",
        )
    )
    if not (root / ".git").exists():
        checks.append(_check("git_metadata", "warn", "Git metadata unavailable; revision cannot be proven"))
    else:
        head = _git_command(root, "rev-parse", "HEAD")
        checks.append(
            _check(
                "git_metadata",
                "pass" if head else "fail",
                f"HEAD {head}" if head else "Git metadata exists but HEAD cannot be read",
            )
        )

    selected = sorted(set(skills))
    for name in selected:
        try:
            source = canonical_source(root, name) / "SKILL.md"
        except PackageError as exc:
            checks.append(_check(f"package:{name}", "fail", str(exc)))
            continue
        checks.append(
            _check(
                f"package:{name}",
                "pass" if source.is_file() else "fail",
                "canonical SKILL.md present" if source.is_file() else "canonical SKILL.md missing",
            )
        )

    if target is None:
        checks.append(_check("installation_target", "skip", "no --target supplied"))
    else:
        resolved_target = target.expanduser().resolve()
        target_error = _target_root_error(resolved_target)
        if target_error:
            checks.append(_check("installation_target", "fail", target_error))
        else:
            for name in selected:
                try:
                    source = canonical_source(root, name)
                except PackageError:
                    continue
                destination = resolved_target / name
                if destination.is_symlink():
                    status = "pass" if _same_resolved_path(source, destination) else "fail"
                    details = "canonical symlink" if status == "pass" else f"symlink resolves to {destination.resolve()}"
                elif not destination.exists():
                    status, details = "warn", "not installed at target"
                elif destination.is_dir():
                    try:
                        matches = package_digest(source) == package_digest(destination)
                    except (OSError, PackageError) as exc:
                        status, details = "fail", f"cannot compare package digest: {exc}"
                    else:
                        status = "pass" if matches else "fail"
                        details = (
                            "installed copy matches canonical package digest"
                            if matches
                            else "target contains different or unowned content"
                        )
                else:
                    status, details = "fail", "target contains different or unowned content"
                checks.append(_check(f"target:{name}", status, details))

    if run_verification:
        try:
            result = subprocess.run(
                [sys.executable, "scripts/verify.py"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            output = (result.stderr or result.stdout or "").strip().splitlines()
            suffix = f"; {output[-1]}" if output else ""
            checks.append(
                _check(
                    "repository_verification",
                    "pass" if result.returncode == 0 else "fail",
                    f"exit {result.returncode}{suffix}",
                )
            )
        except OSError as exc:
            checks.append(_check("repository_verification", "fail", str(exc)))
    else:
        checks.append(_check("repository_verification", "skip", "use --verify to run the complete gate"))

    has_failure = any(check["status"] == "fail" for check in checks)
    has_warning = any(check["status"] == "warn" for check in checks)
    return {
        "schema_version": "azhou-ai-hub.doctor.v1",
        "valid": not has_failure,
        "status": "unhealthy" if has_failure else "degraded" if has_warning else "healthy",
        "checks": checks,
    }


def _print_info(payload: dict[str, Any]) -> None:
    revision = payload["revision"]
    print("Azhou AI Hub")
    print(f"Repository: {payload['repository']}")
    print(f"Revision: {revision['commit']} ({revision['branch']}, dirty={revision['dirty']})")
    print(f"Skills: {', '.join(payload['installable_skills'])}")
    print(f"Verify: {payload['verification_command']}")


def _print_version(payload: dict[str, Any]) -> None:
    print(f"Commit: {payload['commit']}")
    print(f"Branch: {payload['branch']}")
    print(f"Dirty: {payload['dirty']}")
    print("Release version: unavailable (no installed release metadata)")


def _print_doctor(payload: dict[str, Any]) -> None:
    print(f"Azhou AI Hub doctor: {payload['status']}")
    for check in payload["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['details']}")


def _print_setup(payload: dict[str, Any]) -> None:
    print(f"Azhou AI Hub setup: {payload['status']} ({payload['mode']} -> {payload['target']})")
    if payload.get("error"):
        print(f"[FAIL] target: {payload['error']}")
    for row in payload["skills"]:
        print(f"[{row['status'].upper()}] {row['name']}: {row['details']}")
    if payload["status"] == "dry_run":
        print("No files changed. Re-run with --apply to execute this plan.")


def run_verifier(root: Path, python: str) -> int:
    try:
        result = subprocess.run(
            [python, str(root / "scripts/verify.py"), "--python", python],
            cwd=root,
            check=False,
        )
    except OSError as exc:
        print(f"verification failed to start: {exc}", file=sys.stderr)
        return 1
    return result.returncode


def build_parser(root: Path = ROOT) -> argparse.ArgumentParser:
    skill_names = canonical_skills(root)
    parser = argparse.ArgumentParser(
        prog="azhou-ai-hub",
        description="Harness-neutral foundations for Azhou AI Hub",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    info = subcommands.add_parser("info", help="Show repository, runtime, and skill information")
    info.add_argument("--json", action="store_true", help="Emit stable JSON")

    version = subcommands.add_parser("version", help="Show proven repository revision information")
    version.add_argument("--json", action="store_true", help="Emit stable JSON")

    doctor = subcommands.add_parser("doctor", help="Run read-only repository and installation diagnostics")
    doctor.add_argument("--target", type=Path, help="Optional harness skill root to inspect")
    doctor.add_argument("--skill", action="append", choices=skill_names, help="Limit checks to one skill; repeatable")
    doctor.add_argument("--verify", action="store_true", help="Run the complete repository verification gate")
    doctor.add_argument("--json", action="store_true", help="Emit stable JSON")

    setup = subcommands.add_parser("setup", help="Plan or apply an explicit skill installation")
    setup.add_argument("--target", type=Path, required=True, help="Explicit harness skill root")
    setup.add_argument("--skill", action="append", choices=skill_names, help="Install one skill; repeatable")
    setup.add_argument("--mode", choices=["link", "copy"], default="link", help="Installation mode")
    setup.add_argument("--apply", action="store_true", help="Apply the plan; default is read-only dry-run")
    setup.add_argument("--json", action="store_true", help="Emit stable JSON receipt")

    verify = subcommands.add_parser("verify", help="Run the authoritative repository verification gate")
    verify.add_argument("--python", default=sys.executable, help="Python interpreter for all Python gates")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser(root).parse_args(argv)
    skills = args.skill if getattr(args, "skill", None) else canonical_skills(root)

    if args.command == "info":
        payload = info_payload(root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_info(payload)
        return 0

    if args.command == "version":
        payload = version_payload(root)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_version(payload)
        return 0

    if args.command == "doctor":
        payload = run_doctor(
            root=root,
            target=args.target,
            skills=skills,
            run_verification=args.verify,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_doctor(payload)
        return 0 if payload["valid"] else 1

    if args.command == "setup":
        payload = setup_skills(
            root=root,
            target=args.target,
            skills=skills,
            mode=args.mode,
            dry_run=not args.apply,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_setup(payload)
        return 0 if payload["status"] in {"pass", "dry_run"} else 1

    if args.command == "verify":
        return run_verifier(root, args.python)

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

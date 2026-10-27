#!/usr/bin/env python3
"""Validate in-repository package inputs and safe POSIX lifecycle suites."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

try:
    from . import integration_common as common
except ImportError:
    import integration_common as common


ROOT = Path(__file__).resolve().parents[1]


def _has_private_part(name: str) -> bool:
    return bool(common.EXCLUDED_PARTS.intersection(PurePosixPath(name.rstrip("/")).parts))


def validate_packages() -> tuple[dict[str, Path], list[str]]:
    """Load all package metadata and verify build inputs are in each runtime map."""
    packages: dict[str, Path] = {}
    errors: list[str] = []
    for component in common.COMPONENTS:
        try:
            package = common.package_root(component, hub_root=ROOT)
            manifest = common.load_lock(component, hub_root=ROOT)
        except (common.IntegrationError, OSError, ValueError) as exc:
            errors.append(f"{component}: {exc}")
            continue

        packages[component] = package
        runtime_paths = manifest.get("runtime_paths", [])
        for name in runtime_paths:
            if isinstance(name, str) and _has_private_part(name):
                errors.append(f"{component}: private runtime path is forbidden: {name}")

        files = manifest.get("files", {})
        for name in files:
            if _has_private_part(name):
                errors.append(f"{component}: private runtime file is forbidden: {name}")

        build_inputs = manifest.get("build_inputs", [])
        if not isinstance(build_inputs, list):
            errors.append(f"{component}: build_inputs must be an array")
            continue
        for name in build_inputs:
            if not isinstance(name, str) or not name:
                errors.append(f"{component}: build_inputs entries must be nonempty paths")
            elif _has_private_part(name):
                errors.append(f"{component}: private build input is forbidden: {name}")
            elif name not in files:
                errors.append(f"{component}: build input is not present in computed runtime files: {name}")

        print(
            f"ok: {component} package manifest ({len(files)} runtime files; "
            f"{len(build_inputs)} build inputs)",
            flush=True,
        )
    return packages, errors


def run_suite(label: str, package: Path, arguments: list[str]) -> int:
    command = [sys.executable, *arguments]
    print(f"==> {label}: {' '.join(arguments)}", flush=True)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(command, cwd=package, env=environment, check=False)
        code = result.returncode
    except OSError as exc:
        print(f"FAILED: {label} could not launch: {exc}", file=sys.stderr, flush=True)
        return 127
    if code:
        print(f"FAILED: {label} (exit {code})", file=sys.stderr, flush=True)
    return code


def main() -> int:
    packages, errors = validate_packages()
    if errors:
        for error in errors:
            print(f"FAILED: {error}", file=sys.stderr, flush=True)
        print("package source validation failed", flush=True)
        return 1

    if os.name != "posix":
        if sys.platform == "win32":
            print(
                "SKIPPED: native package lifecycle suites are unvalidated on Windows; "
                "package manifests were checked",
                flush=True,
            )
        else:
            print(
                f"SKIPPED: native package lifecycle suites are unvalidated on {sys.platform}; "
                "package manifests were checked",
                flush=True,
            )
        return 0

    results = [
        run_suite(
            "model-router package tests",
            packages["model-router"],
            ["-m", "unittest", "discover", "-s", "tests"],
        ),
        run_suite(
            "startup-animation installer lifecycle tests",
            packages["startup-animation"],
            ["tools/test-install-macos.py"],
        ),
    ]
    return next((code for code in results if code), 0)


if __name__ == "__main__":
    raise SystemExit(main())

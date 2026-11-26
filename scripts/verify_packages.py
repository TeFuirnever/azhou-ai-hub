#!/usr/bin/env python3
"""Validate in-repository package inputs."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
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


def main() -> int:
    _, errors = validate_packages()
    if errors:
        for error in errors:
            print(f"FAILED: {error}", file=sys.stderr, flush=True)
        print("package source validation failed", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

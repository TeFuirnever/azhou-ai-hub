"""Small isolated Hub package fixtures for integration boundary tests."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import integration_common as common


def package_root(hub_root: Path, component: str) -> Path:
    return Path(hub_root) / "packages" / common.PACKAGES[component]


def configure_package(hub_root: Path, component: str, runtime_paths: list[str], **metadata) -> Path:
    root = package_root(hub_root, component)
    root.mkdir(parents=True, exist_ok=True)
    selected = list(runtime_paths)
    if "hub-package.json" not in selected:
        selected.insert(0, "hub-package.json")
    manifest = {
        "schema": common.PACKAGE_SCHEMA,
        "component": component,
        "commit": "a" * 40,
        "runtime_paths": selected,
        **metadata,
    }
    (root / "hub-package.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return root

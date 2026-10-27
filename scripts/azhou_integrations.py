"""Discover and dispatch exactly three optional, independently selected integrations."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

try:
    from . import integration_common as common
except ImportError:
    import integration_common as common

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {
    "pstack": "integration_pstack",
    "model-router": "integration_model_router",
    "startup-animation": "integration_startup_animation",
}


def catalog(*, hub_root: Path = ROOT) -> dict:
    integrations = []
    for component in common.COMPONENTS:
        lock = common.load_lock(component, hub_root=hub_root)
        integrations.append({
            "id": component,
            "name": lock.get("display_name", component),
            "commit": lock["commit"],
            "commit_scope": "original import provenance",
            "package": common.PACKAGES[component],
            "path": str(common.package_root(component, hub_root=hub_root)),
            "version": lock.get("version", lock.get("runtime_version", "unreleased")),
            "source_kind": lock["source_kind"],
            "source_lock_sha256": common.plan_digest(lock),
            "license": lock.get("license", lock.get("license_status", "see source provenance")),
            "entry": f"python scripts/azhou_hub.py integrations {component} --help",
            "enabled_by_default": False,
        })
    return {
        "schema": "azhou-hub.integrations.v1",
        "integrations": integrations,
        "contract": "docs/integrations.md",
        "activation": "installation, host discovery, invocation and behavior require separate evidence",
    }


def main(argv: list[str] | None = None, *, hub_root: Path = ROOT) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ADAPTERS:
        prefix = (__package__ + ".") if __package__ else ""
        adapter = importlib.import_module(prefix + ADAPTERS[args[0]])
        try:
            return adapter.main(args[1:], hub_root=hub_root)
        except common.IntegrationError as exc:
            print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
            return 1
    parser = argparse.ArgumentParser(
        prog="azhou-ai-hub integrations",
        description="Three in-repository packages with optional installation; installing Skills never enables them.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List in-repository packages and separate operational entries")
    listing.add_argument("--json", action="store_true")
    for component in ADAPTERS:
        sub.add_parser(component, help=f"Use the {component} adapter", add_help=False)
    parsed = parser.parse_args(args)
    try:
        payload = catalog(hub_root=hub_root)
    except common.IntegrationError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    if parsed.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in payload["integrations"]:
            print(f"{item['id']}: {item['name']} {item['version']} ({item['package']})")
            print(f"  original import: {item['commit']}")
            print(f"  {item['entry']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

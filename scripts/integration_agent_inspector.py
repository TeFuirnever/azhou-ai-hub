"""Describe the native installation inputs for the session monitor."""
import argparse
import json

try:
    from . import integration_common as common
except ImportError:
    import integration_common as common


def main(argv=None, *, hub_root=common.ROOT):
    parser = argparse.ArgumentParser(prog="azhou-ai-hub integrations azhou-agent-inspector")
    parser.add_argument("command", choices=["plan"])
    parser.add_argument("--harness", required=True, choices=["codex", "zcode"])
    args = parser.parse_args(argv)
    component = "azhou-agent-inspector"
    source = common.package_root(component, hub_root=hub_root)
    lock = common.load_lock(component, hub_root=hub_root)
    print(json.dumps({"harness": args.harness, "marketplace_root": str(source),
                      "plugin": component + "@azhou-agent-tools",
                      "source_lock_sha256": common.plan_digest(lock),
                      "instructions": str(source / "README.md")}, indent=2))
    return 0

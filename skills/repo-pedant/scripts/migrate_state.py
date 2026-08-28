#!/usr/bin/env python3
"""Migrate the prior Repo Pedant state directory into its Azhou namespace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import azhou_runtime_state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        plan = azhou_runtime_state.plan_directory_migration(
            args.project,
            namespace="repo-pedant",
            source=".repo-pedant",
            allowed_sources=(".repo-pedant",),
        )
        if args.apply:
            if not args.plan_id:
                raise azhou_runtime_state.StateError("--apply requires the reviewed --plan-id")
            if args.plan_id != plan["planId"]:
                raise azhou_runtime_state.StateError("migration plan changed; run dry-run again")
            result = azhou_runtime_state.apply_directory_migration(plan)
            azhou_runtime_state.verify_directory_migration(result)
        else:
            result = plan
    except (OSError, ValueError, azhou_runtime_state.StateError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

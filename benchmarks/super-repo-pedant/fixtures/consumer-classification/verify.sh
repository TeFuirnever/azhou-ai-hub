#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import pathlib
import sys

inventory_path = pathlib.Path("analysis/inventory.json")
try:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    print(f"FAIL: analysis/inventory.json unreadable: {exc}", file=sys.stderr)
    sys.exit(1)

entries = inventory.get("candidates")
if not isinstance(entries, list) or not entries:
    print("FAIL: inventory.candidates must be a non-empty array", file=sys.stderr)
    sys.exit(1)

allowed = {"production", "non_production", "ambiguous", "not_applicable"}
by_surface = {}
for entry in entries:
    if not isinstance(entry, dict) or not entry.get("surface"):
        print("FAIL: every candidate needs a surface", file=sys.stderr)
        sys.exit(1)
    if entry.get("consumer_class") not in allowed:
        print(f"FAIL: {entry['surface']}: consumer_class outside enum", file=sys.stderr)
        sys.exit(1)
    by_surface[entry["surface"]] = entry

expected = {
    "src/format.py::format_money": "production",
    "src/legacy.py::legacy_slugify": "non_production",
    "src/migrate.py::migrate_config": "ambiguous",
    "src/retry.py::retry_until_quiet": "production",
}
missing = sorted(set(expected) - set(by_surface))
if missing:
    print(f"FAIL: unclassified candidates: {missing}", file=sys.stderr)
    sys.exit(1)
wrong = {
    surface: by_surface[surface]["consumer_class"]
    for surface, want in expected.items()
    if by_surface[surface]["consumer_class"] != want
}
if wrong:
    print(f"FAIL: wrong consumer_class: {wrong}", file=sys.stderr)
    sys.exit(1)

gap = by_surface["src/migrate.py::migrate_config"].get("evidence_gap")
if not isinstance(gap, str) or not gap.strip():
    print("FAIL: ambiguous candidate must record its evidence gap", file=sys.stderr)
    sys.exit(1)

removal = by_surface["src/legacy.py::legacy_slugify"].get("removal")
if removal != "pending_authorization":
    print("FAIL: non_production removal must stay pending_authorization", file=sys.stderr)
    sys.exit(1)
PY

test -f src/legacy.py
test -f src/migrate.py
grep -q "def retry_until_quiet" src/retry.py
grep -Eq "TODO" src/retry.py
grep -q "retry_until_quiet" src/server.py
grep -q "format_money" src/server.py

#!/usr/bin/env python3
"""Benchmark integrity check for the prose-standard recall batteries.

Fixtures prove probe wiring only: every leakage fixture must hit at least one
probe, and the keep corpus may hit only the documented false-positive families.
They are never evidence about model behavior.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "prose-standard" / "scripts" / "recall_batteries.py"
MANIFEST = Path(__file__).resolve().parent / "manifest.json"
DOCUMENTED_FALSE_POSITIVES = {
    ("external-standard.md", "stamp"),
    ("external-standard.md", "draft-section"),
    ("runtime-lifecycle.md", "narration"),
}


def run_check() -> int:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        errors.append("manifest: schema_version must be 1")
    corpus = manifest.get("corpus", {})
    for group in ("leakage", "keep"):
        names = corpus.get(group, [])
        if not names:
            errors.append(f"manifest.corpus.{group}: expected fixture names")
            continue
        for name in names:
            if not (ROOT / "tests" / "fixtures" / "prose-standard" / group / name).is_file():
                errors.append(f"manifest.corpus.{group}: missing fixture {name}")

    def probe(group: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(ROOT / "tests" / "fixtures" / "prose-standard" / group)],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            return json.loads(completed.stdout)
        except ValueError:
            return {"status": "probe-error", "findings": [], "stderr": completed.stderr}

    if not errors:
        leak = probe("leakage")
        hit_files = {Path(f["path"]).name for f in leak["findings"]}
        for name in corpus["leakage"]:
            if name not in hit_files:
                errors.append(f"leakage fixture produced no probe hit: {name}")
        keep = probe("keep")
        observed = {(Path(f["path"]).name, f["probe"]) for f in keep["findings"]}
        if observed != DOCUMENTED_FALSE_POSITIVES:
            errors.append(
                "keep corpus findings drifted from the documented false-positive families: "
                + json.dumps(sorted(observed), ensure_ascii=False)
            )

    verdict = {"valid": not errors, "errors": errors}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(run_check())

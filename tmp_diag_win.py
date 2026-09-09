"""Temporary Windows diagnostic: dump every promotion-evidence candidate."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "benchmarks/super-caveman")
import benchmark

BASE = "ce242fad50f9852c50c967dd54a36238d03600ff"
EXCLUSIONS = {
    "results/revision-8f493670-attempt-1-summary.json",
    "results/revision-8f493670-exact-diff-approval.json",
}

staged = benchmark.staged_review_digests(EXCLUSIONS)
committed = benchmark.committed_review_digests(EXCLUSIONS, BASE)
summary = json.loads(
    (benchmark.BENCHMARK / "results/revision-8f493670-attempt-1-summary.json").read_text(encoding="utf-8")
)
value = summary["promotion_review"]["exact_diff_human_approval"]
record = json.loads(
    (benchmark.BENCHMARK / "results/revision-8f493670-exact-diff-approval.json").read_text(encoding="utf-8")
)
tuples = benchmark.reviewed_blob_tuples(record["reviewed_blobs"])
from_blobs = (
    benchmark.committed_review_digests_from_blobs(EXCLUSIONS, BASE, tuples)
    if tuples else None
)

keys = ("base_commit", "path_set_sha256", "staged_patch_sha256")
print("VALUE      :", {k: value[k][:20] for k in keys})
print("staged     :", staged)
print("committed  :", {k: committed[k][:20] for k in keys} if committed else None)
print("from_blobs :", {k: from_blobs[k][:20] for k in keys} if from_blobs else None)
print("tuples     :", len(tuples) if tuples is not None else None)
if tuples:
    print("paths      :", benchmark._tuple_paths(tuples))
readme = subprocess.check_output(
    benchmark.canonical_git_diff("--name-only", "-z", "HEAD", "--", ":(top,literal)README.md"),
    cwd=benchmark.ROOT,
)
print("wt README  :", readme)
print("git version:", subprocess.check_output(["git", "--version"], cwd=benchmark.ROOT, text=True).strip())

import hashlib
commits = subprocess.check_output(
    ["git", "rev-list", "--reverse", "--topo-order", "--ancestry-path", f"{BASE}..HEAD", "--",
     *sorted(f"benchmarks/super-caveman/{p}" for p in EXCLUSIONS)],
    cwd=benchmark.ROOT, text=True,
).splitlines()
print("rev-list commits:", commits)
for commit in commits:
    for p in sorted(EXCLUSIONS):
        rel = f"benchmarks/super-caveman/{p}"
        shown = subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=benchmark.ROOT)
        wt = (benchmark.BENCHMARK / p).read_bytes()
        print(
            f"{commit[:10]} {p}: show={len(shown)}B sha={hashlib.sha256(shown).hexdigest()[:12]} "
            f"wt={len(wt)}B sha={hashlib.sha256(wt).hexdigest()[:12]} "
            f"norm_eq={benchmark._normalized_newlines(shown) == benchmark._normalized_newlines(wt)}"
        )

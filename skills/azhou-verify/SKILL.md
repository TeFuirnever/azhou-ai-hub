---
name: azhou-verify
description: Run and report the authoritative Azhou AI Hub repository verification gate. Use before completion, handoff, commit, pull request, release, or when full-codebase evidence is requested.
---

# Azhou Verify

Use the repository Foundation CLI as the only full-gate entry. Do not replace it with selected tests or infer success from prior output.

## Workflow

1. Emit `🦊 阿舟 · Azhou Verify 启动` with `mode=verify` and the checkout scope.
2. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
3. Run `python3 scripts/azhou_hub.py verify` from that checkout. This is the public, reproducible integrity gate and still recomputes the approved Super Caveman exact diff against the current staged or committed tree. Use `--python <interpreter>` only when the user or environment requires an explicit interpreter.
4. Add `--promotion-evidence` only for an explicitly requested maintainer/release replay after both required Git-external Super Caveman records are available. This mode authenticates those raw records against the same exact diff. Never describe the default public gate as authenticated human-promotion evidence.
5. Preserve the underlying exit code. Report the repository-policy, unit-test, benchmark-integrity, whitespace, and optional promotion-evidence gates actually observed; do not convert skipped or unavailable checks into pass.
6. A failed gate blocks a completion claim but does not authorize fixes outside the user's task.
7. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. `changes` is always empty.

For requirements and the exact full-gate boundary, read [setup and compatibility](references/setup.md).

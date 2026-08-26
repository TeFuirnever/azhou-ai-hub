---
name: azhou-verify
description: Run and report the authoritative Azhou AI Hub repository verification gate. Use before completion, handoff, commit, pull request, release, or when full-codebase evidence is requested.
---

# Azhou Verify

Use the repository Foundation CLI as the only full-gate entry. Do not replace it with selected tests or infer success from prior output.

## Workflow

1. Emit `🦊 阿舟 · Azhou Verify 启动` with `mode=verify` and the checkout scope.
2. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
3. Run `python3 scripts/azhou_hub.py verify` from that checkout. Use `--python <interpreter>` only when the user or environment requires an explicit interpreter.
4. Preserve the underlying exit code. Report the repository-policy, unit-test, benchmark-integrity, and whitespace gates actually observed; do not convert skipped or unavailable checks into pass.
5. A failed gate blocks a completion claim but does not authorize fixes outside the user's task.
6. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. `changes` is always empty.

For requirements and the exact full-gate boundary, read [setup and compatibility](references/setup.md).

---
name: foundation-doctor
description: Diagnose Azhou AI Hub checkout, package, explicit install-target, or Treehouse lease health without mutation. Use for health checks, broken installs, environment diagnostics, or support verification.
---

# Foundation Doctor

Run the repository Foundation CLI and keep diagnosis read-only. Never turn a doctor request into setup, repair, cleanup, cache removal, or configuration edits.

## Workflow

1. Emit `🦊 阿舟 · Foundation Doctor 启动` with `mode=doctor` and the checkout scope.
2. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
3. Build `python3 scripts/azhou_hub.py doctor --json` and add only explicitly grounded options:
   - `--target <skill-root>` for an exact install root.
   - `--skill <canonical-name>` for each requested package.
   - `--treehouse-root <pool-root>` for the explicit Treehouse boundary.
   - `--verify` only when the user requests the complete repository gate or the claim requires it.
4. Preserve the CLI distinction between `healthy`, `degraded`, and failed diagnostics. A warning is not a deterministic failure.
5. Report findings and recommended next actions without applying them. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. `changes` is always empty.

If no valid checkout is available, stop with `status=hold` and request one explicit checkout path. For requirements and supported checks, read [setup and compatibility](references/setup.md).

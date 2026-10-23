# Azhou Doctor setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py` and `docs/skill-standard.md`.
- Python 3.11 or newer.
- Git for revision/worktree diagnostics.
- Treehouse 2.3.0 or newer only when `--treehouse-root` is requested.

This Skill is harness-neutral and does not bundle or install the repository-level Foundation CLI. Install the same Skill directory into any Agent Skills-compatible root, then invoke it while working in the checkout or provide the checkout path explicitly. It does not infer Codex, Claude Code, zcode, or another harness root.

## Smoke check

~~~bash
python scripts/azhou_hub.py doctor --json
~~~

The optional `--host-root <host-root>` probe extends the doctor with a read-only migration scan for residual installs and stale hook paths that still use a renamed-away skill name. It scans the explicit host root's skills directory and its depth-1 `*.json`/`*.toml` config files against the canonical list, reports findings, and never mutates the host; the operator applies the migration steps in [host install migration](host-migration.md).

The doctor is read-only. It never calls Treehouse `get`, `return`, `prune`, or `destroy`, and it never repairs package or harness state.

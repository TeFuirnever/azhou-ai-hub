# Foundation Doctor setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py` and `docs/skill-standard.md`.
- Python 3.11 or newer.
- Git for revision/worktree diagnostics.
- Treehouse 2.3.0 or newer only when `--treehouse-root` is requested.

This Skill is harness-neutral and does not bundle or install the repository-level Foundation CLI. Install the same Skill directory into any Agent Skills-compatible root, then invoke it while working in the checkout or provide the checkout path explicitly. It does not infer Codex, Claude Code, zcode, or another harness root.

## Smoke check

~~~bash
python3 scripts/azhou_hub.py doctor --json
~~~

The doctor is read-only. It never calls Treehouse `get`, `return`, `prune`, or `destroy`, and it never repairs package or harness state.

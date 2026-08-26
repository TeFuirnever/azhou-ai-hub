# Foundation Setup setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py`, `docs/skill-standard.md`, and the source skill packages.
- Python 3.11 or newer.
- An explicit writable Agent Skills root supplied by the user or calling environment.

This Skill is harness-neutral and does not bundle the repository-level Foundation CLI or infer host installation paths. The same package can guide Codex, Claude Code, zcode, or another compatible harness; only the explicit target root changes.

## Dry-run and apply

~~~bash
python3 scripts/azhou_hub.py setup --skill <name> --target <absolute-root> --mode link --json
python3 scripts/azhou_hub.py setup --skill <name> --target <absolute-root> --mode link --apply --json
~~~

Managed operations use a receipt directly below `<target>/.azhou-ai-hub/receipts/`. Run every `repair`, `migrate`, or `uninstall` command once without `--apply`, review the exact plan, then apply only with authorization.

Package-manager installations stay owned by their package manager. This Skill cannot adopt or remove them.

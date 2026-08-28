# Azhou Setup setup and compatibility

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

Managed operations use a receipt directly below `<target>/.azhou/hub/receipts/`. Run every `repair`, `migrate`, or `uninstall` command once without `--apply`, review the exact plan, then apply only with authorization.

Receipts under the prior metadata root are not read as a fallback. Use `migrate-receipts --target <absolute-root> --json`, review the emitted `planId`, then rerun with `--apply --plan-id <reviewed-planId>`. The source remains intact.

Current managed installs write `azhou-ai-hub.install-receipt.v2`, including the installed object's filesystem identity and executable-aware package digest. Legacy v1 receipts cannot authorize migration or deletion; an explicit `repair --apply` validates their original byte digests, records the current object identity, and recomputes source and installed v2 digests. Byte drift remains blocked.

Package-manager installations stay owned by their package manager. This Skill cannot adopt or remove them.

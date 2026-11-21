# Azhou Setup setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py`, `docs/skill-standard.md`, and the source skill packages.
- Python 3.11 or newer.
- An explicit writable Agent Skills root supplied by the user or calling environment.

This Skill is harness-neutral and does not bundle the repository-level Foundation CLI or infer host installation paths. The same package can guide Codex, Claude Code, zcode, or another compatible harness; only the explicit target root changes.

## Dry-run and apply

~~~bash
python scripts/azhou_hub.py setup --skill <name> --target <absolute-root> --mode link --json
python scripts/azhou_hub.py setup --skill <name> --target <absolute-root> --mode link --apply --plan-id <reviewed-planId> --json
~~~

Managed operations use a receipt directly below `<target>/.azhou/hub/receipts/`. Run every `repair`, `migrate`, or `uninstall` command once without `--apply`, review the exact plan, then apply only with authorization.

Setup distinguishes two destination conflicts. A `conflict` row is foreign content: an unowned directory, a file, or a symlink resolving to different package content; it fails with exit code `1`. A `conflict-same-source` row means the destination symlink already resolves to canonical package content identical to this checkout, typically a link owned by another checkout of the same repository. A dry-run blocked only by `conflict-same-source` reports `dry_run_same_source` and exits `3` while still emitting the `planId`; `--apply` keeps refusing until the duplicate checkout is resolved or a different target is chosen.

Receipts under the prior metadata root are not read as a fallback. Use `migrate-receipts --target <absolute-root> --json`, review the emitted `planId`, then rerun with `--apply --plan-id <reviewed-planId>`. The source remains intact.

Current managed installs write `azhou-ai-hub.install-receipt.v2`, including the installed object's filesystem identity and executable-aware package digest. Legacy v1 receipts cannot authorize migration or deletion; an explicit `repair --apply` validates their original byte digests, records the current object identity, and recomputes source and installed v2 digests. Byte drift remains blocked.

Package-manager installations stay owned by their package manager. This Skill cannot adopt or remove them.

## Skills CLI installation

Use the project directory as the working directory for a project-scoped install. Add `--global` when the user chooses user scope. Confirm the chosen scope and the Skill name before an operation.

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou --agent codex
npx skills list --agent codex
npx skills check --project super-ask-azhou
npx skills update --project super-ask-azhou
npx skills remove super-ask-azhou
~~~

For a user-wide installation, add `--global` to `list` and `remove`, and replace `--project` with `--global` in `check` and `update`. The shared project Skill directory can be used by multiple agents. Name-based removal affects that shared copy. Check the remaining list and the destination after removal. The documented check syntax was verified with Skills CLI 1.9.0.

## Managed update

The receipt records the source path and digest as well as the installed artifact identity. A changed source is a conflict for repair and uninstall. Before changing the source checkout, use the existing source to inspect the receipt and preview `uninstall`. After an explicitly authorized uninstall succeeds, move the old receipt out of the active receipt directory. Preserve the original source revision and archived receipt. Update the source checkout, run managed `setup` against the same target with a fresh plan, and verify the new bytes with `doctor`. Restore the old revision through the same receipt-owned sequence if rollback is needed. An absent old source or changed installed artifact requires recovery of the exact source or user-owned changes before proceeding.

If uninstall reports `partial`, stop concurrent changes and show any `recovery` fields. The observed path and identities may have changed again. Inspect the receipt and record manually without following links; do not automatically delete the record or repeat the uninstall.

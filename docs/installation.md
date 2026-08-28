# Installation

## Package-manager install

Install only the skill you need:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-info
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-doctor
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-setup
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-verify
npx skills add TeFuirnever/azhou-ai-hub --skill super-caveman
npx skills add TeFuirnever/azhou-ai-hub --skill llm-wiki
~~~

Run one command per desired skill. The package manager chooses the harness destination. This path has no repository-owned receipt; verify discovery and invocation in the target harness.

The four Foundation Skills are portable UX wrappers around a local checkout. They do not bundle the repository CLI or infer a harness home. Invoke them while working in an Azhou AI Hub checkout or provide that checkout path explicitly; the Skill then runs the checkout's `scripts/azhou_hub.py`.

## Checkout-assisted setup

For a local checkout, the foundation CLI can plan and reconcile a manual copy or contributor symlink. It requires the exact harness skill root and defaults to a read-only dry-run:

~~~bash
SKILLS_HOME=/absolute/path/to/harness/skills

python3 scripts/azhou_hub.py setup --skill repo-pedant --target "$SKILLS_HOME" --mode link --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target "$SKILLS_HOME" --mode link --apply --json
python3 scripts/azhou_hub.py doctor --skill repo-pedant --target "$SKILLS_HOME" --json
~~~

Use `--mode copy` for a standalone snapshot. Setup is idempotent and fails closed on different or unowned destination content. It never replaces a package-manager installation or rewrites harness configuration.

To let this checkout later repair, switch or remove exactly what it installed, opt into a single-skill managed receipt:

~~~bash
RECEIPT="$SKILLS_HOME/.azhou/hub/receipts/repo-pedant.json"

python3 scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill repo-pedant --target "$SKILLS_HOME" --mode link --json

python3 scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill repo-pedant --target "$SKILLS_HOME" --mode link --apply --json
~~~

The first command is still read-only. Keep the receipt: `repair`, same-target `migrate` between `link` and `copy`, and `uninstall` require it plus the same explicit `--target`. They fail closed if the source, target or installed content has drifted. The receipt integrity digest detects accidental corruption, not malicious rewriting. See the [foundation CLI contract](foundations.md).

Existing checkout-managed receipts under the prior metadata root are migration sources only. Diagnose and copy them without deleting the source:

~~~bash
python3 scripts/azhou_hub.py migrate-receipts --target "$SKILLS_HOME" --json
python3 scripts/azhou_hub.py migrate-receipts \
  --target "$SKILLS_HOME" --apply --plan-id '<reviewed-planId>' --json
~~~

The apply step revalidates each receipt's target, canonical source, digest and installed object identity before publishing `.azhou/hub/receipts/` atomically.

## Manual copy

Copy the complete runtime directory into a skill root supported by the active harness:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

cp -R "$REPO_ROOT/skills/repo-pedant" "$SKILLS_HOME/repo-pedant"
cp -R "$REPO_ROOT/skills/super-caveman" "$SKILLS_HOME/super-caveman"
cp -R "$REPO_ROOT/skills/llm-wiki" "$SKILLS_HOME/llm-wiki"
~~~

Keep every runtime subdirectory: <code>references/</code>, <code>scripts/</code>, <code>assets/</code>, <code>templates/</code> and vendored runtime data. Do not copy repository-level <code>benchmarks/</code>.

## Development symlink

A symlink makes edits visible immediately:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

ln -s "$REPO_ROOT/skills/repo-pedant" "$SKILLS_HOME/repo-pedant"
ln -s "$REPO_ROOT/skills/excalidraw-diagram" "$SKILLS_HOME/excalidraw-diagram"
ln -s "$REPO_ROOT/skills/super-caveman" "$SKILLS_HOME/super-caveman"
ln -s "$REPO_ROOT/skills/llm-wiki" "$SKILLS_HOME/llm-wiki"
~~~

If a harness cached its skill catalog before the symlink existed, reload the harness or start a new task. Do not create duplicate copies to force refresh.

## One-path rule

For one canonical name, choose exactly one ownership mode and target root. Do not mix modes in one target root:

1. package-manager install;
2. checkout-managed install (the Foundation CLI and optional receipt);
3. manual copy;
4. development symlink.

Multiple copies cause stale selection, ambiguous provenance and updates landing in the wrong package.

## Skill-specific dependencies

- Repo Pedant uses Python standard library for its deterministic scripts. See [repo-pedant setup](../skills/repo-pedant/references/setup.md).
- Excalidraw Diagram needs Python 3.11, uv, Node.js 20+, Playwright Chromium and npm packages for full render/export paths. Inspect dry-runs before installing: [excalidraw setup](../skills/excalidraw-diagram/references/setup.md).
- Azhou Info, Doctor, Setup and Verify require Python 3.11+ plus an explicit Azhou AI Hub checkout. Their package-local setup references state the narrower Git, Treehouse and write-access requirements.
- Super Caveman uses Python 3.10+ standard library only for guarded file compression. Install only the canonical `super-caveman` package, not the seven upstream source packages; hooks, global response configuration and private-log discovery are never automatic: [Super Caveman setup](../skills/super-caveman/references/setup.md).
- LLM Wiki uses Python 3.11+ standard library only. CLI, seven-tool stdio MCP, lifecycle adapter and migration ship together. MCP and hook configuration remain explicit; `.azhou/llm-wiki/` stays private by default: [LLM Wiki setup](../skills/llm-wiki/references/setup.md).

No package requires <code>agents/openai.yaml</code> or a model-specific runtime copy.

## Upgrade or uninstall

Package-manager installations follow the package manager's update/remove commands. For unmanaged manual copies, replace the whole skill directory only after reviewing local changes. For unmanaged symlinks, pull the repository and rerun verification.

For a checkout-managed artifact, inspect before applying:

~~~bash
python3 scripts/azhou_hub.py repair --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
python3 scripts/azhou_hub.py migrate --receipt "$RECEIPT" --target "$SKILLS_HOME" --mode copy --json
python3 scripts/azhou_hub.py uninstall --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
~~~

Add `--apply` only after reviewing the JSON plan. There is no force overwrite, cross-root migration, hook cleanup or receipt-less adoption.

Remove the legacy <code>neat-freak</code> name only after confirming <code>repo-pedant</code> resolves and passes its smoke checks. Do not keep a hidden alias unless a user explicitly needs a transition period.

LLM Wiki normal operations use only <code>.azhou/llm-wiki/</code>. Import a recognized prior store through the dry-run-first <code>migrate --from-store</code> command, then bind apply to the emitted <code>planId</code>. Migration never deletes the source; contraction remains separately authorized.

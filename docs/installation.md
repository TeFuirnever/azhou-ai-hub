# Installation

## Recommended: managed install

Install only the skill you need:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
~~~

Run one command per desired skill. The package manager chooses the harness destination.

## Checkout-assisted setup

For a local checkout, the foundation CLI can plan and reconcile a manual copy or contributor symlink. It requires the exact harness skill root and defaults to a read-only dry-run:

~~~bash
SKILLS_HOME=/absolute/path/to/harness/skills

python3 scripts/azhou_hub.py setup --skill repo-pedant --target "$SKILLS_HOME" --mode link --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target "$SKILLS_HOME" --mode link --apply --json
python3 scripts/azhou_hub.py doctor --skill repo-pedant --target "$SKILLS_HOME" --json
~~~

Use `--mode copy` for a standalone snapshot. Setup is idempotent and fails closed on different or unowned destination content. It never replaces a managed installer and never updates, removes, or rewrites harness configuration. See the [foundation CLI contract](foundations.md).

## Manual install

Copy the complete runtime directory into a skill root supported by the active harness:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

cp -R "$REPO_ROOT/skills/repo-pedant" "$SKILLS_HOME/repo-pedant"
~~~

Keep every runtime subdirectory: <code>references/</code>, <code>scripts/</code>, <code>assets/</code>, <code>templates/</code> and vendored runtime data. Do not copy repository-level <code>benchmarks/</code>.

## Contributor install

A symlink makes edits visible immediately:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

ln -s "$REPO_ROOT/skills/repo-pedant" "$SKILLS_HOME/repo-pedant"
ln -s "$REPO_ROOT/skills/excalidraw-diagram" "$SKILLS_HOME/excalidraw-diagram"
~~~

If a harness cached its skill catalog before the symlink existed, reload the harness or start a new task. Do not create duplicate copies to force refresh.

## One-path rule

For one canonical name, choose exactly one of:

1. managed install;
2. manual copy;
3. development symlink.

Multiple copies cause stale selection, ambiguous provenance and updates landing in the wrong package.

## Skill-specific dependencies

- Repo Pedant uses Python standard library for its deterministic scripts. See [repo-pedant setup](../skills/repo-pedant/references/setup.md).
- Excalidraw Diagram needs Python 3.11, uv, Node.js 20+, Playwright Chromium and npm packages for full render/export paths. Inspect dry-runs before installing: [excalidraw setup](../skills/excalidraw-diagram/references/setup.md).

Neither package requires <code>agents/openai.yaml</code> or a model-specific runtime copy.

## Upgrade or uninstall

Managed installations follow the package manager's update/remove commands. For manual copies, replace the whole skill directory only after reviewing local changes. For symlinks, pull the repository and rerun verification.

Remove the legacy <code>neat-freak</code> name only after confirming <code>repo-pedant</code> resolves and passes its smoke checks. Do not keep a hidden alias unless a user explicitly needs a transition period.

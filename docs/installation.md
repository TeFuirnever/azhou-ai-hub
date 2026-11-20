# Installation

## Optional external integrations

The existing Skill installation paths below remain independent. For the two optional pstack and Agent Skin integrations, start with `python scripts/azhou_hub.py integrations list --json` and follow the [integration runbook](integrations.md). These operations have distinct native ownership and source locks; the Skill package manager and Foundation Skill installer must not manage their targets.

## Install or update when a task needs it

If a book skill is missing from the Azhou AI Hub checkout, check the current branch and the files under `.agents/skills/`. Update the checkout or restore the tracked files from the intended revision. These book skills ship with the project. Installing Ask Azhou by itself adds the router. To use a specific book in a different project, install it there from [agent-rules-books](https://github.com/ciembor/agent-rules-books).

If you need Ask Azhou in a project where it is unavailable, use the single-skill install below. A recommendation can point to the missing skill and its installation route when it helps complete the task. Offer an update when you can verify that the active skill is older and the newer revision fixes a relevant problem, adds a capability the user needs, or addresses a security or compatibility issue. Check the installed skill and its source before making that suggestion. A newer Hub release by itself is insufficient because releases can change other packages. Use the installation method that owns the active copy.

## Package-manager install

Install only the skill you need:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill super-excalidraw-diagram
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-info
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-doctor
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-setup
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-verify
npx skills add TeFuirnever/azhou-ai-hub --skill super-eli5
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou
npx skills add TeFuirnever/azhou-ai-hub --skill super-arch-doc
npx skills add TeFuirnever/azhou-ai-hub --skill super-session-insights
npx skills add TeFuirnever/azhou-ai-hub --skill super-asd-ste100
npx skills add TeFuirnever/azhou-ai-hub --skill super-archify
npx skills add TeFuirnever/azhou-ai-hub --skill super-lavish
npx skills add TeFuirnever/azhou-ai-hub --skill super-imagegen
npx skills add TeFuirnever/azhou-ai-hub --skill super-i-have-adhd
npx skills add TeFuirnever/azhou-ai-hub --skill super-gh-axi
~~~

Select the skill and harness in one command. For example, run this from the project where you want to use Ask Azhou in Codex.

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou --agent codex
~~~

For a user-wide install, add `--global`. Keep the scope for later updates and removal. This installation has no repository-owned receipt. Verify discovery and invocation in the target harness.

## Verify what you installed

Package-manager installs resolve the mutable default branch and carry no repository receipt, so verify the installed content instead of trusting the install step.

**Tag-snapshot comparison (works on every host).** Compare the installed skill directory against the version you intended, at a published tag:

~~~bash
git clone --depth 1 --branch v2.0.1 https://github.com/TeFuirnever/azhou-ai-hub /tmp/azhou-tag
diff -r /tmp/azhou-tag/skills/<skill-name> <installed-skills-root>/<skill-name> && echo identical
~~~

`<installed-skills-root>` is wherever your harness placed the skill (the package manager prints the destination). Any drift — including extra files — prints as a diff. Release notes list which skills a release touches; per-skill content digests are not published yet, so the tag snapshot is the reference.

**Receipt-backed verification (checkout-assisted path only).** The checkout-assisted `setup --apply` writes a managed receipt whose digests `doctor` re-checks on demand:

~~~bash
python scripts/azhou_hub.py doctor --skill <skill-name> --target "$SKILLS_HOME" --json
~~~

`doctor` fails closed when the source, target or installed content has drifted from the receipt. The receipt integrity digest detects accidental corruption, not malicious rewriting.

The four Foundation Skills are portable UX wrappers around a local checkout. They do not bundle the repository CLI or infer a harness home. Invoke them while working in an Azhou AI Hub checkout or provide that checkout path explicitly; the Skill then runs the checkout's `scripts/azhou_hub.py`.

## Checkout-assisted setup

Examples invoke the unversioned `python` interpreter (Python ≥3.11 required). If your system only installs a versioned name — common on macOS — substitute it in the examples, or add the unversioned name via `brew install python`.

For a local checkout, the foundation CLI can plan and reconcile a manual copy or contributor symlink. It requires the exact harness skill root and defaults to a read-only dry-run:

~~~bash
SKILLS_HOME=/absolute/path/to/harness/skills

python scripts/azhou_hub.py setup --skill super-repo-pedant --target "$SKILLS_HOME" --mode link --json
python scripts/azhou_hub.py setup --skill super-repo-pedant --target "$SKILLS_HOME" --mode link --apply --plan-id '<reviewed-planId>' --json
python scripts/azhou_hub.py doctor --skill super-repo-pedant --target "$SKILLS_HOME" --json
~~~

Use `--mode copy` for a standalone snapshot. Setup is idempotent and fails closed on different or unowned destination content. It never replaces a package-manager installation or rewrites harness configuration.

To let this checkout later repair, switch or remove exactly what it installed, opt into a single-skill managed receipt:

~~~bash
RECEIPT="$SKILLS_HOME/.azhou/hub/receipts/super-repo-pedant.json"

python scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill super-repo-pedant --target "$SKILLS_HOME" --mode link --json

python scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill super-repo-pedant --target "$SKILLS_HOME" --mode link --apply --plan-id '<reviewed-planId>' --json
~~~

The first command is still read-only. Keep the receipt: `repair`, same-target `migrate` between `link` and `copy`, and `uninstall` require it plus the same explicit `--target`. They fail closed if the source, target or installed content has drifted. The receipt integrity digest detects accidental corruption, not malicious rewriting. See the [foundation CLI contract](foundations.md).

Existing checkout-managed receipts under the prior metadata root are migration sources only. Diagnose and copy them without deleting the source:

~~~bash
python scripts/azhou_hub.py migrate-receipts --target "$SKILLS_HOME" --json
python scripts/azhou_hub.py migrate-receipts \
  --target "$SKILLS_HOME" --apply --plan-id '<reviewed-planId>' --json
~~~

The apply step revalidates each receipt's target, canonical source, digest and installed object identity before publishing `.azhou/hub/receipts/` atomically.

## Manual copy

Copy the complete runtime directory into a skill root supported by the active harness:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

cp -R "$REPO_ROOT/skills/super-repo-pedant" "$SKILLS_HOME/super-repo-pedant"
~~~

Keep every runtime subdirectory: <code>references/</code>, <code>scripts/</code>, <code>assets/</code>, <code>templates/</code> and vendored runtime data. Do not copy repository-level <code>benchmarks/</code>.

## Development symlink

A symlink makes edits visible immediately:

~~~bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills

ln -s "$REPO_ROOT/skills/super-repo-pedant" "$SKILLS_HOME/super-repo-pedant"
ln -s "$REPO_ROOT/skills/super-excalidraw-diagram" "$SKILLS_HOME/super-excalidraw-diagram"
~~~

If a harness cached its skill catalog before the symlink existed, reload the harness or start a new task. Do not create duplicate copies to force refresh.

## Windows notes

All shell examples in this document are POSIX (`bash`/`zsh`) syntax. On Windows, run them in Git Bash (recommended; install Git for Windows) or translate:

| POSIX example | PowerShell equivalent |
|---|---|
| `SKILLS_HOME=/absolute/path` | `$env:SKILLS_HOME = "C:\absolute\path"` |
| `"$SKILLS_HOME"` | `$env:SKILLS_HOME` |
| `cp -R src dst` | `Copy-Item -Recurse src dst` |

- Checkout-assisted `setup` defaults to `--mode link`, which creates a symlink. Windows requires Developer Mode or an elevated prompt for symlink creation; without it, use `--mode copy`, which needs no special privilege and produces a standalone snapshot.
- Development symlinks follow the same privilege premise as `--mode link`; without Developer Mode prefer `--mode copy`.
- A linked install follows the checkout: when a canonical skill is retired upstream, remove the link and any registered lifecycle-adapter hooks before pulling the retirement commit — `python scripts/azhou_hub.py doctor --host-root <root>` reports stale hook paths. `--mode copy` and package-manager installs are frozen snapshots and keep working after a retirement.
- Some skill scripts print brand emoji to the console. On Chinese Windows the legacy code page (cp936) cannot encode them; if you see `UnicodeEncodeError`, prefix commands with `PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8 = "1"`).
- Hook commands rendered by super-repo-pedant are POSIX shell syntax executed by the host shell: on Windows they require Git Bash; a PowerShell fallback is outside the supported claim.

Checked-in Windows full-flow receipts exist: the managed flow (info → setup → doctor) and the repository gate pass fully green on a real Windows runner with the default Git Bash console encoding ([evidence/windows-full-flow-receipt-2026-10-17.md](../evidence/windows-full-flow-receipt-2026-10-17.md), after the #236 UTF-8 console fix); the 2026-09-13 receipt ([evidence/windows-full-flow-receipt-2026-09-13.md](../evidence/windows-full-flow-receipt-2026-09-13.md)) records the pre-fix cp1252 divergence for history.

## One-path rule

For one canonical name, choose exactly one ownership mode and target root. Do not mix modes in one target root:

1. package-manager install;
2. checkout-managed install (the Foundation CLI and optional receipt);
3. manual copy;
4. development symlink.

Multiple copies cause stale selection, ambiguous provenance and updates landing in the wrong package.

## Skill-specific dependencies

- Repo Pedant uses Python standard library for its deterministic scripts. See [super-repo-pedant setup](../skills/super-repo-pedant/references/setup.md).
- Excalidraw Diagram needs Python 3.11, uv, Node.js 22.22.2+, Playwright Chromium and npm packages for full render/export paths. Run its read-only browser preflight first and install Chromium only when the checker exits `2`: [excalidraw setup](../skills/super-excalidraw-diagram/references/setup.md).
- Azhou Info, Doctor, Setup and Verify require Python 3.11+ plus an explicit Azhou AI Hub checkout. Their package-local setup references state the narrower Git, Treehouse and write-access requirements.
- Arch Doc uses the Python 3 standard library for its `new_doc.py` scaffold and `verify_doc.py` closing gates. An optional local PlantUML CLI enables the per-diagram render gate and is skipped honestly when absent: [Arch Doc setup](../skills/super-arch-doc/references/setup.md).
- Archify runs a self-contained Node.js CLI and needs Node.js 18+ (`package.json` `engines.node`); do not run `npm install`. A local Chrome or Chromium is required for the native-diagram `finalize` browser gate and explicit explainer browser checks: [Archify setup](../skills/super-archify/references/setup.md).

No package requires <code>agents/openai.yaml</code> or a model-specific runtime copy.

## Offline recovery

Dependency installation is the only network-dependent step for the Excalidraw Diagram toolchain; rendering is offline afterwards. When the network is unavailable or a cache is incomplete — the recorded failure is a missing Playwright arm64 wheel during `uv sync --frozen` — recover from local caches instead of switching to an unlocked install.

### Warm the caches once on a matching host

Package caches are platform-specific. Fill them on an online host with the same OS and architecture as the offline target, using the same locked commands as a normal install:

~~~bash
uv cache dir
# default: ~/.cache/uv

npm config get cache
# default: ~/.npm

cd /absolute/path/to/super-excalidraw-diagram/references
uv sync --frozen

cd /absolute/path/to/super-excalidraw-diagram/scripts
npm ci --ignore-scripts
~~~

Copy both cache directories to the same locations on the offline host.

### Recover offline

~~~bash
cd /absolute/path/to/super-excalidraw-diagram/references
uv sync --frozen --offline
uv run python /absolute/path/to/super-excalidraw-diagram/scripts/check-playwright-runtime.py

cd /absolute/path/to/super-excalidraw-diagram/scripts
npm ci --offline --ignore-scripts
~~~

`uv sync --frozen --offline` installs exactly the locked versions from the local uv cache and fails instead of resolving anything new. `npm ci --offline --ignore-scripts` installs from `package-lock.json` out of the local npm cache with lifecycle scripts disabled — the same posture as the online install.

If the runtime check exits `2`, the Chromium build for the locked Playwright version is absent. A browser cannot come from the package caches alone: on the online host, print the exact artifact and install location, install once, and copy the browser cache directory over.

~~~bash
cd /absolute/path/to/super-excalidraw-diagram/references
uv run playwright install --dry-run chromium
# prints the install location, e.g. ~/Library/Caches/ms-playwright/chromium-1234 on macOS arm64

uv run playwright install chromium
~~~

Copy that directory to the same path on the offline host — or set `PLAYWRIGHT_BROWSERS_PATH` to the copied location on both hosts — and repeat the runtime check offline. Exit `0` means the browser is ready; exit `1` or `3` is a Playwright runtime or Python-package problem, not a missing browser, so fix that problem instead of copying browsers.

### Hard-won rules

- Copy, never move, a leased locked environment. A `uv sync --frozen` environment records absolute paths, and a treehouse worktree's path is recorded in its lease metadata. Moving either invalidates the recorded path; copy to the new location and keep the original until the copy verifies.
- Warm the caches with the same lockfile the offline host uses (`--frozen`, `npm ci`). A cache warmed from a looser resolve misses the exact versions the offline install needs.
- Stay on the declared seam: `uv sync --frozen`, `npm ci --ignore-scripts`, `uv run playwright install chromium`. Do not force an offline success with unlocked installs (`uv sync` without `--frozen`, `npm install`); that hides the drift the locks exist to prevent.
- Verify a recovered environment with the same checks as a fresh install — the runtime checker and the skill's own verify steps — before trusting anything it renders.

## Upgrade or uninstall

For Skills CLI installations, use the owning scope and name the skill. Run project commands from the project where you installed it.

~~~bash
npx skills list --agent codex
npx skills update --project super-ask-azhou
npx skills remove super-ask-azhou
~~~

For a user-wide install, add `--global` to `list` and `remove`, and replace `--project` with `--global` in `update`. See the [Skills CLI command reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md). For a Skill shared through `.agents/skills/`, removing it by name from its installation scope also affects other agents that use that copy. Run `list` again after removal. Verify the resulting skill in the harness after updating.

For a manual copy, review local changes before replacing the whole skill directory with the intended snapshot. For an unmanaged symlink, update its source checkout and rerun verification.

For a checkout-managed artifact, inspect before applying:

~~~bash
python scripts/azhou_hub.py repair --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
python scripts/azhou_hub.py migrate --receipt "$RECEIPT" --target "$SKILLS_HOME" --mode copy --json
python scripts/azhou_hub.py uninstall --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
~~~

Add `--apply` only after reviewing the JSON plan. There is no force overwrite, cross-root migration, hook cleanup or receipt-less adoption.

To move a managed installation to changed package bytes, use the checkout that still matches the old receipt to dry-run and apply `uninstall`. After confirming removal, archive that receipt outside the active receipts directory. Update the source checkout, run managed `setup` for the new revision, and verify the new install with `doctor`. For rollback, keep the old revision and use the same sequence in reverse with a fresh receipt. If the old source already drifted, inspect with `doctor` and recover the receipt's exact source at its recorded path before using this sequence.

Remove the legacy <code>neat-freak</code> name only after confirming <code>super-repo-pedant</code> resolves and passes its smoke checks. Do not keep a hidden alias unless a user explicitly needs a transition period.

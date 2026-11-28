# Installation

Use the [Ask Azhou install prompt](../README.md#let-your-agent-install) to let your agent install and check the skill in the project you have open.

- [Install manually](#choose-your-agent-host).
- [Find a skill your agent cannot see](#check-that-your-host-finds-the-skill).
- [Update or uninstall a skill](#upgrade-or-uninstall).

## Choose your agent host

These routes install individual Hub Skills. Claude Code, ZCode, and MiMo Code use a local clone of Azhou AI Hub for the routes shown here. Use the skill directory your agent host scans and check discovery after installation.

| Host | Where to start |
|---|---|
| Codex | Follow [the first-install walkthrough](#first-install-in-codex). |
| Claude Code | Use [checkout-assisted setup](#checkout-assisted-setup) with the project's `.claude/skills/` root. |
| ZCode | Use [checkout-assisted setup](#checkout-assisted-setup) with the project's `.agents/skills/` root. See the [ZCode discovery and load receipt](../evidence/canonical-skill-load-zcode-2026-09-02.md) for the tested version and packages. |
| MiMo Code | Use [checkout-assisted setup](#checkout-assisted-setup) with the project's `.mimocode/skills/` root. The [MiMo discovery receipt](../evidence/mimocode-skill-discovery-2026-10-26.md) covers Ask Azhou discovery. |
| DeepSeek Harness | Check the [support matrix](support-matrix.md) for shared user-root evidence. Confirm the host's project installation path before using a project-only install. |

See the [support matrix](support-matrix.md) for the evidence and limits of each route. The [unified component installer](#install-hub-components-in-codex) targets Codex projects.

## Install with an agent

Use this procedure to install one named Hub Skill in the project the user has open.

1. Identify the active agent host and project directory. If either is unclear, ask before changing files. If you cannot inspect or write to the project, give the user the relevant steps from the host guide.
2. Check whether the host already discovers the requested Skill. If it does, report the installation scope and path when available. Reuse that copy and leave it intact.
3. If the Skill is missing, use the matching [host route](#choose-your-agent-host). Install only the requested Skill from [Azhou AI Hub](https://github.com/TeFuirnever/azhou-ai-hub) in this project. Keep existing installations, plugins, and host settings intact. For a Foundation Skill (`super-azhou-*`), locate a local Hub checkout before installing. Report the checkout path so the user can provide it when running the skill in their current project. If you cannot locate a checkout, ask for its path. For `super-imagegen`, verify the private `azhou-imagegen` prerequisite before installing. If the host has no confirmed project route, explain the limitation and ask before changing scope.
4. Verify that the host discovers the installed Skill. Report the destination and verification result. If discovery needs a fresh session or cannot be checked, say so and give the next step.

## First install in Codex

[Already installed Ask Azhou from the GitHub repository? Switch to the website download.](#switch-ask-azhou-to-the-website-download)

Use Ask Azhou to choose a Hub Skill for a task. Before starting, sign in to Codex and open a terminal in the folder you normally open as a Codex project. You need internet access for installation and Node.js with `npx`. Skills CLI 1.9.1, used to verify this walkthrough, requires Node.js 22.20 or later.

1. **Install in this project.** Run the following in the terminal and confirm the installation. The installer shows where it put Ask Azhou.

   ~~~bash
   npx skills add https://tefuirnever.github.io/azhou-ai-hub/downloads/super-ask-azhou.tgz --agent codex
   ~~~

   This command downloads the Ask Azhou package from the Hub website and installs it in the current project. Add `--global` on the first install if you want a user-wide copy instead. For later updates and removal, use the scope you installed into.

2. **Try Ask Azhou.** Open a new Codex chat in the same project. Type `$super-ask-azhou` and check that Codex offers the skill, then enter the following question.

   > `$super-ask-azhou` I have a Mermaid diagram and want to turn it into an interactive architecture diagram. Which Hub Skill should I use?

   The expected recommendation is `super-archify` for an interactive HTML diagram. Install the recommended Skill separately when you want to run it.

## Check that your host finds the skill

Open a new agent session in the same project and use the host's skill list or picker. Look for the requested skill by its package name. Check the reported path and scope before calling it. A copied file is only installation evidence until the host discovers it.

If you cannot find the skill, [check the host's configured project root](#choose-your-agent-host). For Codex, use the check below. For other hosts, check that the installed skill directory contains `SKILL.md` under the [root your host uses](#choose-your-agent-host). Then look for it in a fresh session using the host’s discovery tools.

### If Codex cannot find Ask Azhou

Run this from the same project.

~~~bash
npx skills list --agent codex
~~~

Add `--global` for a user-wide install. If `super-ask-azhou` is absent, check the terminal folder and the installation output. If it is listed, compare the displayed scope and path with the project open in Codex, then try the question in a fresh chat.

## Install Hub components in Codex

Keep a checkout of Azhou AI Hub as the installation source. Use Python 3.11 or later and, when selecting pstack, a Codex CLI that supports native plugin management. Run the command in the project where you want to use the components. Replace the script path with the path in your Hub checkout.

~~~bash
python /path/to/azhou-ai-hub/scripts/azhou_hub.py install --all
~~~

Use `--component hub-skills agent-rules-books` in place of `--all` to select those two components. The available choices are `hub-skills`, `pstack` and `agent-rules-books`. Use `--workspace /path/to/project` to select another existing project directory. When prompted, review the paths and plan, then enter `y` to install. If you selected only skills and all copies already match, the command reports that no files changed and exits. Add `--dry-run` to exit after the preview.

The installer copies Hub Skills and Agent Rules Books into the project's `.agents/skills/` directory. pstack uses the native Codex plugin manager and a dedicated home at `.azhou/hub/targets/pstack` in that project. Use the printed command to start a terminal Codex session with that home. pstack is available on demand in that session, with SessionStart auto-routing off. The ChatGPT desktop app selects its own Codex home when the app process starts. Use `--codex-bin` or `--codex-home` to select a different executable or dedicated target explicitly.

If either component plan is blocked, resolve the reported conflict before retrying. If pstack fails after the skill copies have completed, the copies remain available. Resolve the pstack error and repeat the same selection. Matching skill copies are reused. For other pstack hosts and ongoing plugin management, see the [native integration guide](integrations.md#pstack-local-source-to-native-plugin).

## Optional external integrations

The existing Skill installation paths below remain independent. For the optional pstack integration, start with `python scripts/azhou_hub.py integrations list --json` and follow the [integration runbook](integrations.md). These operations have distinct native ownership and source locks; the Skill package manager and Foundation Skill installer must not manage their targets.

## Install or update when a task needs it

If Ask Azhou is missing from a project, [choose the installation route for your agent host](#choose-your-agent-host). A recommendation can point to the missing skill and its installation route when it helps complete the task. Offer an update when you can verify that the active skill is older and the newer revision fixes a relevant problem, adds a capability the user needs, or addresses a security or compatibility issue. Check the installed skill and its source before making that suggestion. A newer Hub release by itself is insufficient because releases can change other packages. Use the installation method that owns the active copy.

## Install Agent Rules Books

Hub contributors use the book skills tracked under `.agents/skills/` in their checkout. If a book skill is missing, check the current branch and restore the tracked files from the intended revision.

In another project, choose a name from the [Agent Rules Books catalog](agent-rules-books.md). Run the command in that project's directory, using Node.js and npm.

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

Open a new Codex session in the same project and look for `$refactoring`. Use `npx skills list --agent codex` to confirm the installed name and scope if the skill is missing. For a specific Hub revision, write `TeFuirnever/azhou-ai-hub@<commit>` as the source. For an existing Skills CLI install, use its [current scope when you update or remove it](#upgrade-or-uninstall).

## Package-manager install

Find the package name in the [skill catalog](https://tefuirnever.github.io/azhou-ai-hub/skills/). The four `super-azhou-*` skills require a local Hub checkout to run. `super-imagegen` requires the private `azhou-imagegen` skill. In a terminal opened in your agent's project folder, run this example with the chosen package name.

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-archify --agent codex
~~~

This example installs Super Archify for Codex in the current project. For another host, follow its [installation route](#choose-your-agent-host). Use the original scope when updating. Skills CLI resolves the default branch. Check the installed files if you need to verify a revision.

## Alternate installer

If you cannot download the Ask Azhou archive from the Hub website, use Codex's bundled skill installer to install Ask Azhou from GitHub. Run this from your Codex project directory with your system's Python command.

~~~bash
python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" --repo TeFuirnever/azhou-ai-hub --path skills/super-ask-azhou --method git --dest "$PWD/.agents/skills"
~~~

Open a new chat in the project and [try Ask Azhou](#first-install-in-codex). The installer stops if the destination already exists. To install a different skill, find its package name in the [skill catalog](https://tefuirnever.github.io/azhou-ai-hub/skills/) and replace `skills/super-ask-azhou` with `skills/<package-name>`.

## Verify what you installed

Package-manager installs resolve the mutable default branch and carry no repository receipt, so verify the installed content instead of trusting the install step.

**Tag-snapshot comparison (works on every host).** Set `TAG` to the published version you installed. Run the comparison in a POSIX shell, such as Git Bash on Windows.

~~~bash
TAG=v2.0.1
SKILL=super-ask-azhou
SKILLS_HOME=/absolute/path/to/installed/skills
SNAPSHOT=$(mktemp -d)
git clone --depth 1 --branch "$TAG" https://github.com/TeFuirnever/azhou-ai-hub "$SNAPSHOT" &&
  diff -r "$SNAPSHOT/skills/$SKILL" "$SKILLS_HOME/$SKILL" && echo identical
~~~

Set `SKILLS_HOME` to the parent directory of the installed skill. Use the destination shown by the package manager. The comparison reports changed and extra files. Release notes list the affected skills, and the tag snapshot supplies the reference files.

**Receipt-backed verification (checkout-assisted path only).** The checkout-assisted `setup --apply` writes a managed receipt whose digests `doctor` re-checks on demand:

~~~bash
python scripts/azhou_hub.py doctor --skill <skill-name> --target "$SKILLS_HOME" --json
~~~

`doctor` fails closed when the source, target or installed content has drifted from the receipt. The receipt integrity digest detects accidental corruption, not malicious rewriting.

The four Foundation Skills are portable UX wrappers around a local checkout. They do not bundle the repository CLI or infer a harness home. Invoke them while working in an Azhou AI Hub checkout or provide that checkout path explicitly; the Skill then runs the checkout's `scripts/azhou_hub.py`.

## Check Codex discovery

If an installed Skill is missing in Codex, open a terminal with the same Codex configuration as the project you use. From an Azhou AI Hub checkout, pass the absolute path of that project:

~~~bash
python scripts/azhou_hub.py doctor --codex-project /absolute/path/to/project --skill super-ask-azhou
~~~

The check reports whether the installed Codex CLI finds the Skill in that project and whether each listed copy is enabled. It shows the entry path and scope. For a missing Skill, check the project folder and installation scope. For a disabled Skill, enable the intended copy in Codex. If an enabled copy is found, try `$super-ask-azhou` in a new chat in that project to confirm invocation. Add `--target /absolute/path/to/project/.agents/skills` to also check the installed bytes against the checkout.

## Checkout-assisted setup

Examples invoke the unversioned `python` interpreter (Python ≥3.11 required). If your system only installs a versioned name — common on macOS — substitute it in the examples, or add the unversioned name via `brew install python`.

Run these commands from your local Hub checkout. Set `SKILL` to the package name on your skill card or the name Ask Azhou recommended. Set `SKILLS_HOME` to [the directory your agent host scans](#choose-your-agent-host). Preview the install first.

~~~bash
SKILL=super-repo-pedant
SKILLS_HOME=/absolute/path/to/harness/skills

python scripts/azhou_hub.py setup --skill "$SKILL" --target "$SKILLS_HOME" --mode link --json
~~~

Check the preview for the skill name and destination. Replace `<reviewed-planId>` with the preview's `planId`, then apply the install and run Doctor.

~~~bash
python scripts/azhou_hub.py setup --skill "$SKILL" --target "$SKILLS_HOME" --mode link --apply --plan-id '<reviewed-planId>' --json
python scripts/azhou_hub.py doctor --skill "$SKILL" --target "$SKILLS_HOME" --json
~~~

Use `--mode copy` for a standalone snapshot. Setup is idempotent and fails closed on different or unowned destination content. It never replaces a package-manager installation or rewrites harness configuration.

To let this checkout later repair, switch or remove exactly what it installed, opt into a single-skill managed receipt:

~~~bash
RECEIPT="$SKILLS_HOME/.azhou/hub/receipts/$SKILL.json"

python scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill "$SKILL" --target "$SKILLS_HOME" --mode link --json

python scripts/azhou_hub.py setup \
  --managed --receipt "$RECEIPT" \
  --skill "$SKILL" --target "$SKILLS_HOME" --mode link --apply --plan-id '<reviewed-planId>' --json
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

Use the method and scope that own the installed copy. From the same project, first confirm the skill's name, scope, and path. Check for local changes before updating or removing anything.

### Switch Ask Azhou to the website download

If you installed Ask Azhou in this Codex project with the older Skills CLI command that used `TeFuirnever/azhou-ai-hub`, run the [current install command](#first-install-in-codex) from the same project with Ask Azhou still installed. Skills CLI reuses `.agents/skills/super-ask-azhou/` and switches the source in `skills-lock.json` to the website archive. Later project checks and updates use that archive.

### Check a Skills CLI install

~~~bash
npx skills list --agent codex
npx skills check --project super-ask-azhou
~~~

The list example targets Codex. Run the check for your chosen skill. For a user-wide install, use `--global` for both commands.

### Update or remove a Skills CLI install

If the check shows changes you want to keep, save a copy before updating. Run the update only for the intended scope.

~~~bash
npx skills update --project super-ask-azhou
~~~

Before removing, list the skills across all hosts in this scope from a terminal. Confirm the skill name and path. If you may need the same revision again, record the source revision or save the installed files.

~~~bash
npx skills list
~~~

The list may group copies that share a name. Check the host's actual skill directory before removing a separate copy. For example, use this only if you intend to remove the Ask Azhou copy under `.claude/skills/`.

~~~bash
npx skills remove super-ask-azhou --agent claude-code
~~~

A copy under `.agents/skills/` can be shared by multiple hosts. Skills CLI 1.9.0 can report success for `--agent codex` while leaving that shared copy in place. Keep it if any host still needs it. Only use the command below after confirming that every host in this scope can lose its copy of the named skill. Without an agent filter, this can remove separate host copies of that skill too.

~~~bash
npx skills remove super-ask-azhou
~~~

An agent session can run removal without an interactive confirmation. For a user-wide install, add `--global` to list and remove, and use it in place of `--project` for update. Run the list again and check the path as well as the command's output. See the [Skills CLI command reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md#skills-remove).

For a manual copy, review local changes before replacing the whole skill directory with the intended snapshot. For an unmanaged symlink, update its source checkout and rerun verification.

For a checkout-managed artifact, inspect before applying:

~~~bash
python scripts/azhou_hub.py repair --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
python scripts/azhou_hub.py migrate --receipt "$RECEIPT" --target "$SKILLS_HOME" --mode copy --json
python scripts/azhou_hub.py uninstall --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
~~~

A successful managed uninstall keeps its receipt unchanged and records the removal using a hard link under `.azhou/hub/uninstalled/`. Doctor verifies the record and that the target remains absent. The target filesystem must support hard links. A missing Skill can still appear as a warning when specifically selected for installation checks. If uninstall returns `partial`, stop concurrent changes and inspect the receipt and any reported record manually; do not automatically delete or retry. See the [recovery details](foundations.md#managed-checkout-lifecycle-explicit-opt-in).

Add `--apply` only after reviewing the JSON plan. There is no force overwrite, cross-root migration, hook cleanup or receipt-less adoption.

To move a managed installation to changed package bytes, use the checkout that still matches the old receipt to dry-run and apply `uninstall`. After confirming removal, archive that receipt outside the active receipts directory. Update the source checkout, run managed `setup` for the new revision, and verify the new install with `doctor`. For rollback, keep the old revision and use the same sequence in reverse with a fresh receipt. If the old source already drifted, inspect with `doctor` and recover the receipt's exact source at its recorded path before using this sequence.

Remove the legacy <code>neat-freak</code> name only after confirming <code>super-repo-pedant</code> resolves and passes its smoke checks. Do not keep a hidden alias unless a user explicitly needs a transition period.

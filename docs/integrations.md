# Optional integrations / 可选能力接入

The 21 canonical Skills under `skills/` keep their existing independent install, discovery and invocation contracts. Optional entries are complete projects under `packages/`, not new Skills or a general package manager. `setup` does not enable them. The `integrations` command remains their stable operational entry.

The current package is [pstack-agent-harness](../packages/pstack-agent-harness/README.md). Each keeps its own native layout and toolchain. `hub-package.json` declares the runtime paths; every plan computes a fingerprint from those current files and their executable modes. No tracked external source lock pins a checkout. The `commit` metadata records original import provenance, not the current Hub revision or package contents.


```sh
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
```

Use Python 3.11+ and a verified Codex executable for operations that need the native runtime. Commands default to the canonical package under `packages/`; optional `--source` accepts only that exact absolute package path as an assertion and cannot select an external checkout. The native acceptance evidence is dated and applies only to the recorded macOS Codex runtime in the [historical report](../evidence/optional-integrations-2026-10-25.md); other operating systems and arbitrary Codex versions are not covered. Resolve and inspect the executable, not only the command found first on `PATH`.

## Delivery and ownership

| Entry | Package runtime and adapter scope | Native owner and boundary |
|---|---|---|
| `pstack` | `packages/pstack-agent-harness/`; current `runtime_paths` fingerprint, private snapshot, native install/doctor/remove adapter and read-only transition review | Codex plugin manager owns registration and cache; the Hub adapter owns only the coexistence model-sheet line it writes. Bun/Node support bundled scripts; forge workflows may need their declared tools. |

Adapters copy only manifest-selected runtime inputs below `<workspace>/.azhou/hub/sources/` and record a per-plan digest in an ignored private receipt. Receipts can contain local paths, frozen source bytes and exact rollback bytes; do not publish them. They keep recovery and owned cleanup tied to the reviewed package snapshot even after package files change. Build outputs and explicitly supplied private inputs have separate checks. A digest detects input changes; it is not a signature or an upstream license grant.

The adapters do not modify package source files. Any runtime input change changes the next plan fingerprint; review the plan before applying it. An existing installation may require recovery or removal using its recorded snapshot before a changed package can be installed. See [package provenance and updates](integration-provenance.md).

## pstack: local source to native plugin

Use the maintained Hub package as the source for new pstack installations. Upstream repositories remain provenance and update inputs. The [package install guide](../packages/pstack-agent-harness/README.md#install) covers the maintained installation targets. Only the Codex adapter below has a Hub-managed lifecycle; the other targets use native registration or an explicit Skills root. Imported formats for other harnesses remain source history, outside current support. Existing external installations require their native owner's removal or an explicitly reviewed source transition; copying the package into this repository does not adopt them.

Set task-specific paths. `PSTACK_HOME` must be a dedicated target below the workspace's `.azhou/hub/` or an explicitly selected separate home; do not point it at the project itself. The package source defaults to `packages/pstack-agent-harness`; `--source` is optional and only asserts that canonical path. For the installed runtime, `CODEX_HOME` below is set only for that one process.

Codex normally uses `~/.codex` when `CODEX_HOME` is unset. Its local plugin cache is below that home's `plugins/cache/`; bundled or remote catalog plugins may have other managed source locations. A sibling such as `~/.codex-pstack` is a separate configuration, even though it is outside a project. It is available only to Codex processes launched with that home; an already-running desktop app does not switch homes when a terminal command sets the variable. The adapter accepts a fresh or previously owned target and rejects unknown non-empty targets, plus `config.toml` content that mentions a pstack registration or the retired router without a Hub ownership receipt.

```sh
PSTACK_WORKSPACE=/absolute/test-project
PSTACK_HOME="$PSTACK_WORKSPACE/.azhou/hub/targets/pstack"
CODEX_BIN=/absolute/path/to/verified/codex

python scripts/azhou_hub.py integrations pstack plan \
  --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations pstack apply \
  --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
python scripts/azhou_hub.py integrations pstack doctor \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
env CODEX_HOME="$PSTACK_HOME" "$CODEX_BIN" -C "$PSTACK_WORKSPACE"
```

Replace `PLAN_ID` with the current plan output. The adapter calls native `plugin marketplace add` with its private **in-repository snapshot**, then `plugin add pstack-azhouzhou@azhou-hub`. The marketplace was renamed from the fork-era `pstack-claude` to `azhou-hub` on 2026-11-12; installs registered under the old name keep their recorded identity and are removed or verified through it, while the reviewed local source path always determines the installed bytes. The adapter verifies the native marketplace root, marketplace source, plugin source path, installed version, current snapshot files and the complete plugin file set. Existing foreign installations are not adopted.

After opening the dedicated session, inspect native Skills and invoke `pstack-azhouzhou:how` or another selected workflow. `doctor` proves installed files and registration; it does not prove invocation. `/setup-pstack` owns model-sheet setup. On Codex the native sheet is `<codex-home>/pstack-models.md` (the active `${CODEX_HOME:-$HOME/.codex}/pstack-models.md`); the upstream Cursor `.mdc` instructions do not apply, and model rows must not be copied to `AGENTS.md`. Review the rows and actual host-supported model aliases before dispatch; only a sheet-declared, host-supported fallback is permitted. The Hub does not invent a universal model table.

The `SessionStart` hook requires native `/hooks` trust review. Setting `session hook: off` in that target's model sheet stops automatic injection, while explicit Skill invocation remains available. No adapter bypasses hook trust.

### Coexistence installs: the model sheet's `session hook` line

A coexistence install registers the plugin with SessionStart auto-routing off, for a home where routing must stay off while the plugin's on-demand Skills stay available:

```sh
python scripts/azhou_hub.py integrations pstack plan --coexistence \
  --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$SHARED_HOME" --codex-bin "$CODEX_BIN"
```

Besides native registration, a coexistence plan owns exactly one narrow change: the model sheet's `session hook` line switched to `off`, with every other byte, encoding and line ending preserved — or a minimal sheet written when none exists. The plan lists that change with its owner (`hub-pstack-adapter`), purpose and restore behavior, and reports the target as compatible only after the reviewed plan is applied; planning alone modifies nothing. A target whose routing is already armed is converted by that same reviewed plan, and an undecodable sheet blocks instead of being rewritten. The change's recovery record reaches the receipt before the sheet is written, so an interrupted conversion always leaves either an untouched sheet with a recorded basis or a converted sheet whose exact original is recorded — never an orphaned adapter write. An existing standalone installation is recognized when it is later updated to coexistence rules: its receipt stays valid, the plan reports the pending sheet change, and applying it converts the target in place, after which replans report the sheet as already satisfied. `remove` restores the exact prior sheet bytes or deletes the adapter-written sheet, and refuses automatic restore after later user edits, printing the recorded and observed digests of the refusal. A standalone pstack install keeps its existing routing mode untouched.

A dedicated target also carries byproducts the native runtime itself writes the moment it is opened; a native validation pass leaves exactly these behind. The pstack plan accepts precisely that observed byproduct set, discloses the accepted entries in the plan (`host_runtime_state_accepted`) with the statement that the adapter neither reads nor writes them, and still refuses unknown names, user-placed Skills under the home's `skills/`, and symlinks — an unknown or foreign target fails closed for review, and a new client build writing new names does too.

`doctor` reports the states separately: the model sheet and its `session hook` value, native plugin registration, the resulting `auto_routing` judgment, and hook trust as unknown, because only the host's `/hooks` review decides whether the hook runs.

### Reviewing an existing installation before any transition

A target that already holds a pstack native plugin or shared pstack Skills is reviewed before anything changes: `transition-plan` is read-only and returns a differentiated plan or block reason for each reachable state, so an existing installation enters the compatible state through the reviewed plan of the entry that owns the change.

```sh
python scripts/azhou_hub.py integrations pstack transition-plan \
  --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$SHARED_HOME" --codex-bin "$CODEX_BIN" \
  --skills-dir "$SHARED_SKILLS"
```

`--skills-dir` names the shared Skills root (for Codex shared installs, typically `~/.agents/skills`); it is compared read-only against the pinned package and never written. The report names the actual source of everything it finds — the Hub receipt and snapshot, the native registry's marketplace source, or the clone a symlinked shared Skill points at — the per-file content differences against the pinned `source_lock_sha256`, the target change (if any), its owner, and its recovery basis. Shared Skills alone never route tasks: they are never forced into a native plugin, and locally modified or locally added files are listed and preserved with the choice to keep them or migrate them after review. A compatible or armed native installation without a Hub receipt is reported, never adopted — a matching name or byte-identical content is not a takeover basis — and the plan lists the reviewed steps instead: switch routing off with `/setup-pstack` in that home, or remove the installation through its own lifecycle and install through the Hub entry. The Hub claims no byte-exact restore for installs it did not write; the recorded native registry source is the reinstall basis, and the report says so.

An armed installation the Hub does own gets the applicable conversion: the same reviewed coexistence plan as above, embedded with its plan id, owner `hub-pstack-adapter`, the exact before/after sheet digests, and the statement that every byte outside the `session hook` line — all model rows and host mappings — keeps its exact value. Ownership is not inferred from the receipt alone: the native registry must resolve the registered installation back to the receipt's snapshot first, so a completed removal followed by a user's own install, a swapped marketplace source, or an unreadable registry all stay blocked with the actual recorded source named — and the install entry refuses a stale completed-removal receipt over a reappeared registration instead of installing over it. Apply an applicable conversion through `apply --coexistence --plan-id PLAN_ID`: apply re-checks the bound source and target and stops on drift, the recovery basis reaches the receipt before the sheet changes, an interruption resumes through a fresh plan, and the update and exit paths above keep working afterwards. Duplicate plugin copies, symlinked plugin state and undecodable sheets are block reasons, not conversions. Completing this review does not authorize applying any transition to the main environment, moving local Skills, or restarting a host; each application is a separate reviewed decision.

```sh
python scripts/azhou_hub.py integrations pstack plan --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations pstack apply --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
```

Removal calls native plugin removal followed by marketplace removal, then checks both lists. Keep the target `CODEX_HOME` free of concurrent native plugin or marketplace changes for the entire removal: the Hub's lock scoped to the workspace and `CODEX_HOME` cannot coordinate other workspaces or the native manager, and the marketplace check and removal are separate operations. The plan states this requirement but does not verify it. If concurrent changes may have occurred, the empty lists alone do not establish complete cleanup; review the native installation and registration before proceeding. It restores the adapter-owned coexistence sheet change when the receipt records one, as described above. It retains the frozen source and Hub receipt. A partial install records completed native steps; a new plan/apply resumes, or the remove operation cleans only that recorded native installation. Unrecognized cache additions block removal. The upstream Bun bootstrap may create `skills/poteto-mode/scripts/node_modules`; `doctor` reports it as outside source-file verification, and automatic removal refuses unrecorded dependency files instead of deleting them by assumption.

### Retiring an upstream installation

Inspect the native registration's source and scope before removal. Preserve model sheets and local source changes, then use the native manager to uninstall the exact pstack plugin. Keep a marketplace that still supplies other plugins, and let the native manager retire caches that are in use. For a shared Skills installation, remove only links whose targets were verified to belong to the retired source; other entries remain user-owned. Back up any pstack-specific standing instruction before removing its bounded block or exact pointer. Source clones can be retired after their local changes are preserved and no installed references or processes depend on them.

Model sheets in automatically loaded rule locations still inject instructions after a plugin is removed. Preserve their contents outside those locations when retiring the installation: [Claude user rules](https://code.claude.com/docs/en/memory#user-level-rules) apply across projects, and [Cursor rules](https://cursor.com/docs/rules) with `alwaysApply: true` are always included. A saved sheet with no include, rule registration or standing pointer can remain as dormant user preferences for a later Hub-sourced installation.

`~/.agents/skills` is a shared Skills discovery directory, including for Codex processes with an isolated home. A skills-only pstack installation there has no native routing hook. Its presence alone does not establish automatic routing or require a native-plugin conversion; choose one workflow owner per task. A later shared installation must link to this Hub's maintained package, and its removal affects every runtime that reads the shared directory. This manual source-retirement procedure does not adopt unknown installations or replace the planned controlled-conversion lifecycle.

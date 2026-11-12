# Optional integrations / 可选能力接入

The twelve canonical Skills under `skills/` keep their existing independent install, discovery and invocation contracts. The two optional entries are complete projects under `packages/`, not new Skills or a general package manager. `setup` does not enable them. The `integrations` command remains their stable operational entry.

The in-repository packages are [pstack-agent-harness](../packages/pstack-agent-harness/README.md) and [Agent Skin](../packages/agent-skin/README.md). Each keeps its own native layout and toolchain. `hub-package.json` declares the runtime paths; every plan computes a fingerprint from those current files and their executable modes. No tracked external source lock pins a checkout. The `commit` metadata records original import provenance, not the current Hub revision or package contents.

The 2026-10-26 local App and Pet handoff receipts bound `packages/codex-startup-animation/`; the Agent Skin rename did not itself transfer either installation. That required handoff was completed on 2026-11-12 by a byte-faithful isolated rehearsal, its persistent-root replay instructions and maintainer approval ([receipt](../packages/agent-skin/evidence/codex-pet-legacy-root-handoff-2026-11-11.md)): the tool's designed rejection was accepted as final, the installed Pet receipt remains an orphan pointing at the deleted root while the Pet itself stays self-contained and usable, and the legacy root was then deleted. Installation ownership is still checked against the current App and Pet receipts separately.

```sh
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
python scripts/azhou_hub.py integrations agent-skin --help
```

Use Python 3.11+ and a verified Codex executable for operations that need the native runtime. Commands default to the canonical package under `packages/`; optional `--source` accepts only that exact absolute package path as an assertion and cannot select an external checkout. The native acceptance evidence is dated and applies only to the recorded macOS Codex runtime in the [historical report](../evidence/optional-integrations-2026-10-25.md); other operating systems and arbitrary Codex versions are not covered. Resolve and inspect the executable, not only the command found first on `PATH`.

## Delivery and ownership

| Entry | Package runtime and adapter scope | Native owner and boundary |
|---|---|---|
| `pstack` | `packages/pstack-agent-harness/`; current `runtime_paths` fingerprint, private snapshot, native install/doctor/remove adapter and read-only transition review | Codex plugin manager owns registration and cache; the Hub adapter owns only the coexistence model-sheet line it writes. Bun/Node support bundled scripts; forge workflows may need their declared tools. |
| `agent-skin` | `packages/agent-skin/`; current runtime and build inputs, isolated build/test install/run/inspect; production lifecycle plans remain blocked | Azhou AI Lab, a Codex adapter with the native player and wallpaper helper, plus the assembled `azhou-agent-skin` DeepSeek Harness plugin package (`tools/build-dsh-plugin.py`, local assembly only). Owned UI supports Chinese/English and follows official host language/theme without separate preferences. The bot entry portrait is a separate private input; startup artwork and Pet remain independent. Version-aware events, independent playback smoke, read-only status and scoped restore retain their existing boundaries. Local tests do not establish official-host acceptance or installation handoff. No program redistribution grant is recorded. |

Adapters copy only manifest-selected runtime inputs below `<workspace>/.azhou/hub/sources/` and record a per-plan digest in an ignored private receipt. Receipts can contain local paths, frozen source bytes and exact rollback bytes; do not publish them. They keep recovery and owned cleanup tied to the reviewed package snapshot even after package files change. Build outputs and explicitly supplied private inputs have separate checks. A digest detects input changes; it is not a signature or an upstream license grant.

The adapters do not modify package source files. Any runtime input change changes the next plan fingerprint; review the plan before applying it. An existing installation may require recovery or removal using its recorded snapshot before a changed package can be installed. See [package provenance and updates](integration-provenance.md).

## pstack: local source to native plugin

Use the maintained Hub package as the source for new pstack installations. Upstream repositories remain provenance and update inputs. The [package install guide](../packages/pstack-agent-harness/README.md#install) covers the maintained targets: native Codex and Claude Code formats, and skills-only zcode, MiMo Code and DeepSeek Harness. Only the Codex adapter below has a Hub-managed lifecycle; the other targets use native registration or an explicit Skills root. Imported formats for other harnesses remain source history, outside current support. Existing external installations require their native owner's removal or an explicitly reviewed source transition; copying the package into this repository does not adopt them.

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

Replace `PLAN_ID` with the current plan output. The adapter calls native `plugin marketplace add` with its private **in-repository snapshot**, then `plugin add pstack-azhouzhou@pstack-claude`. The marketplace name `pstack-claude` is retained for compatibility; the reviewed local source path determines the installed bytes. The adapter verifies the native marketplace root, marketplace source, plugin source path, installed version, current snapshot files and the complete plugin file set. Existing foreign installations are not adopted.

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

## Agent Skin: build, test entry and production boundary

For updates to existing daily installations, follow the [local install SOP](../packages/agent-skin/docs/local-install-sop.md). The test-entry adapter below keeps its existing ownership boundary.

The ZCode host layer is retired from this package: its last supported version was `0.9.0/build 41`, installed ZCode skins are frozen installs, the [README exit statement](../README.md#retired-surfaces) carries the uninstall guidance, and the persisted/protocol identifiers that installed-state migrations depend on keep their historical names ([decision record](decisions/hub-retirement-physical-deletion.md)).

The canonical package is `packages/agent-skin/`. The CLI uses it by default; optional `--source` only asserts that canonical path. Its code has no recorded open-source license grant, so the Hub root license does not apply and source/binary publication remains on hold pending maintainer authorization. Personal artwork is never included in the package.

```sh
ANIMATION_WORKSPACE=/absolute/animation-test-project
PRIVATE_INPUTS=/absolute/explicit-private-inputs
python scripts/azhou_hub.py integrations agent-skin check-source
python scripts/azhou_hub.py integrations agent-skin build \
  --workspace "$ANIMATION_WORKSPACE" --private-assets "$PRIVATE_INPUTS"
```

The last command is a plan. Repeat it with `--apply --plan-id PLAN_ID` after reviewing the targets and private-input hashes. Supply `working.png`, `scene.js`, `wallpaper-scene-q-v3.png` and `app-icon/source.png`; 0.9.0 and later also require the separate bot portrait `entry-avatar.png`. Missing inputs fail. The adapter copies them only into ignored local state, runs the fixed native build and compares the final marker against **all** approved private inputs. The temporary empty Git database in that snapshot serves only the native ignore checks, not source-history attribution.

The same package assembles the DeepSeek Harness plugin without a plan, because the plugin never installs anything: `python tools/build-dsh-plugin.py` (from `packages/agent-skin/`) emits `.build/azhou-dsh-plugin/azhou-agent-skin/` and `python tools/verify-artifacts.py --verify-dsh-plugin <package>` checks it. The plugin's source inputs joined `hub-package.json` `build_inputs` and `runtime_paths`, so the next native plan fingerprint changes; review it before applying. Installing the package into a DSH profile is a separate manual step, not performed by this repository's adapters. The official throwaway-profile installation loop was verified in the [2026-11-05 live install receipt](../evidence/live-dsh-plugin-install-2026-11-05.md). See the [plugin contract](../packages/agent-skin/docs/dsh-plugin.md) and the [assembly receipt](../evidence/dsh-agent-skin-assembly-2026-11-05.md).

Use the returned `.build/azhou-payload` path as `PAYLOAD`. Test installation accepts only that frozen-snapshot payload: a bundle built directly in the live package directory is rejected at planning, because test-uninstall restores from the frozen snapshot. Test installation likewise requires its own current plan:

```sh
python scripts/azhou_hub.py integrations agent-skin test-install \
  --workspace "$ANIMATION_WORKSPACE" --payload "$PAYLOAD"
# Repeat with --apply --plan-id PLAN_ID; set TEST_APP to the returned path.
python scripts/azhou_hub.py integrations agent-skin inspect --bundle "$TEST_APP"
python scripts/azhou_hub.py integrations agent-skin run --bundle "$TEST_APP" --mode smoke
python scripts/azhou_hub.py integrations agent-skin run --bundle "$TEST_APP" --mode probe
```

`run` is a plan until repeated with `--apply --plan-id PLAN_ID`. `smoke` runs a one-shot player without launching or enhancing Codex. `probe` resolves the actual `com.openai.codex` target without launching it. The returned log must name the installed application; a source preview or successful exit alone is insufficient. The optional `--evidence` path must be inside this Hub checkout's `.azhou/hub/` and is bound into the plan.

The Hub assesses output according to the inspected bundle version: verified 0.7.1 payloads retain legacy event rules; 0.8.0 and later payloads use `azhou-startup.event.v1` for consumed events. Known diagnostics may omit the schema and are not counted as startup evidence. For the current contract, `launch` reports hot activation, startup readiness, skip, interruption and unproven behavior separately from wallpaper status; it does not require playback or wallpaper completion to report startup readiness. `smoke` is a one-shot player check that requires its own playback-completion evidence and never launches or enhances Codex. `probe` only resolves the actual `com.openai.codex` target. These event assessments are validated with synthetic fixtures; no live producer or official host run is claimed.

Plans disclose temporary locks, helper logs and the possible lifetime of a cold-start loopback debugging port. `wallpaper-status` is a separate read-only check that can report an optional startup state without launching, injecting, registering or writing logs. `disable-wallpaper` requires a specific target PID and bundle; its restore scope removes the Agent Skin controller and wallpaper while preserving saved settings, the host process and its debugging port. Playback completion, launcher result, wallpaper report, live page state and visual review remain separate evidence. Never restart an active host merely to make an acceptance test pass.

For the test entry, use `test-uninstall --workspace ...`, then repeat with `--apply --plan-id PLAN_ID`. macOS may automatically register even a directly executed test `.app`; cleanup is limited to this receipt-owned exact path and must preserve other registrations. Cleanup uses the verified private package snapshot and receipt, so later package changes do not remove the recovery source. New build, install, run and inspect plans fingerprint the current in-repository inputs. This is separate from the native production entry. Apple describes `lsregister` as a [debugging tool, not a stable API](https://developer.apple.com/forums/thread/725805); the tested exact-path operation and NSWorkspace before/after check do not establish support for every macOS release.

`install-plan` and `uninstall-plan` describe the production target and return `blocked_source_contract`. The Hub package's native installer has a narrow one-time `--migrate-from OLD_ROOT` operation for an existing launcher at the fixed user Applications entry. Run it only from the final Hub package path after building its own payload. It requires matching old schema-2 installation receipt, old build payload and installed app fingerprints, the old build marker, unique registration, a user-entry lock and both project install locks. It replaces the exact verified entry, writes a Hub-owned receipt with `sourceHandoff`, and leaves the old checkout intact for separate archival or removal. A normal install still rejects another `projectRoot`. This native handoff does not implement the Hub adapter's general production install/uninstall plans; explicit build/state/destination and native uninstall contracts remain needed there. `native-check` remains read-only. The original official Codex entry remains available.

### Pet maintenance after the import

The Pet toolchain — `tools/manage-codex-pet.py`, `tools/import-codex-pet.py`, their runbook and isolated tests — is maintained only in [Agent Skin](../packages/agent-skin/README.md); its current contracts live in the [Agent Skin Pet runbook](../packages/agent-skin/docs/codex-pet.md). The package tool owns Pet preparation, validation, packaging, installation, synchronization and recovery; the Hub integration CLI has no Pet subcommand.

The legacy `packages/codex-startup-animation/` root was deleted on 2026-11-12. Its installed-receipt ownership handoff was completed by a byte-faithful isolated rehearsal, its persistent-root replay instructions and maintainer approval on 2026-11-12 ([handoff receipt](../packages/agent-skin/evidence/codex-pet-legacy-root-handoff-2026-11-11.md)); the tool's designed rejection was accepted as final, so the installed Pet receipt remains an orphan pointing at the deleted root while the installed Pet stays self-contained and usable. A future Pet installation from Agent Skin follows the runbook's native prepare/generate/review chain; remove the old install the native way first, because ordinary `install` refuses a receipt owned by another `projectRoot`. Historical legacy-source maintenance followed the legacy runbook that Git history now carries.

From the Hub root, these commands inspect state or run the isolated tests at the maintained home:

```sh
cd packages/agent-skin
python -B tools/manage-codex-pet.py status
```

```sh
python -B packages/agent-skin/tools/test-codex-pet.py
python -B packages/agent-skin/tools/test-import-codex-pet.py
```

A source-only checkout lacks private theme inputs, frozen snapshots and reviewed candidates. `status` is an inspection result, not a readiness or host-activation verdict; invalid source/candidate state or `unknown-target` for a receipt bound to another `projectRoot` does not establish that an installation is damaged. Private inputs, candidates and installation receipts remain local. The Pillow-dependent Pet and importer suites above run in the macOS CI leg and should both run for Pet runtime changes.

## Why these checks are necessary

The initial read-only review answered the four implementation questions with concrete consequences:

| Question | Implementation consequence |
|---|---|
| Necessary work beyond copying capabilities? | Keep two native projects as independent packages, select only declared runtime inputs, bind current bytes to each plan, preserve recovery after source edits, and separate private artwork, playback, host launch and appearance evidence. |
| Which primary materials prove what? | Package manifests and runtime source show current intended inputs; package licenses define stated grants; host protocol/config and task metadata prove native discovery/dispatch. README and dated receipts locate evidence but do not prove current behavior. |
| How is the path traced? | `hub-package.json` runtime paths → per-plan digest → private package snapshot → native plan/installer → receipt → native list/config/schema → task or installed-player events. Dated acceptance records remain tied to their original inputs. |
| What can disprove correctness? | Changed package bytes, native configuration/Skill validation, independent review, altered target/dependency/material/transaction negative controls, installed resource hashes and actual run metadata. Formal visual approval, redistribution permission and unexecuted host behavior remain explicit holds. |

Run the repository gate with `python scripts/verify.py`; it includes each package's targeted native tests. The [2026-10-25 acceptance report](../evidence/optional-integrations-2026-10-25.md) and [support matrix](support-matrix.md#optional-integrations) are historical evidence, not fresh acceptance of the monorepo package contents. No quality, latency, price or cross-harness equivalence claim follows from these integrations.

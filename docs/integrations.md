# Optional integrations / 可选能力接入

The fourteen canonical Skills under `skills/` keep their existing independent install, discovery and invocation contracts. The three optional entries are complete projects under `packages/`, not new Skills or a general package manager. `setup` does not enable them. The `integrations` command remains their stable operational entry.

The in-repository packages are [pstack-agent-harness](../packages/pstack-agent-harness/README.md), [Agent Orchestration Kit](../packages/agent-orchestration-kit/README.md), and [codex-startup-animation](../packages/codex-startup-animation/README.md). Each keeps its own native layout and toolchain. `hub-package.json` declares the runtime paths; every plan computes a fingerprint from those current files and their executable modes. No tracked external source lock pins a checkout. The `commit` metadata records original import provenance, not the current Hub revision or package contents.

```sh
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
python scripts/azhou_hub.py integrations model-router --help
python scripts/azhou_hub.py integrations startup-animation --help
```

Use Python 3.11+ and a verified Codex executable for operations that need the native runtime. Commands default to the canonical package under `packages/`; optional `--source` accepts only that exact absolute package path as an assertion and cannot select an external checkout. The native acceptance evidence is dated and applies only to the recorded macOS Codex runtime in the [historical report](../evidence/optional-integrations-2026-10-25.md); other operating systems and arbitrary Codex versions are not covered. Resolve and inspect the executable, not only the command found first on `PATH`.

## Delivery and ownership

| Entry | Package runtime and adapter scope | Native owner and boundary |
|---|---|---|
| `pstack` | `packages/pstack-agent-harness/`; current `runtime_paths` fingerprint, private snapshot and native install/doctor/remove adapter | Codex plugin manager owns registration and cache; the Hub adapter owns only the coexistence model-sheet line it writes. Bun/Node support bundled scripts; forge workflows may need their declared tools. |
| `model-router` | `packages/agent-orchestration-kit/`; current `runtime_paths` fingerprint, private snapshot and native install/verify/recovery adapter | Agent Orchestration Kit's installer owns its Codex settings, six roles, instructions and Skill. Codex owns actual dispatch. |
| `startup-animation` | `packages/codex-startup-animation/`; current runtime and build inputs, isolated build/test install/run/inspect; production lifecycle plans remain blocked | Native macOS Swift/AppKit/WKWebView player and Codex wallpaper helper. Four private assets are supplied separately. No program redistribution grant is recorded. |

Adapters copy only manifest-selected runtime inputs below `<workspace>/.azhou/hub/sources/` and record a per-plan digest in an ignored private receipt. Receipts can contain local paths, frozen source bytes and exact rollback bytes; do not publish them. They keep recovery and owned cleanup tied to the reviewed package snapshot even after package files change. Build outputs and explicitly supplied private inputs have separate checks. A digest detects input changes; it is not a signature or an upstream license grant.

The adapters do not modify package source files. Any runtime input change changes the next plan fingerprint; review the plan before applying it. An existing installation may require recovery or removal using its recorded snapshot before a changed package can be installed. See [package provenance and updates](integration-provenance.md).

## pstack: local source to native plugin

Use the maintained Hub package as the source for new pstack installations. Upstream repositories remain provenance and update inputs. The [package install guide](../packages/pstack-agent-harness/README.md#install) covers the maintained targets: native Codex and Claude Code formats, and skills-only zcode and MiMo Code. Only the Codex adapter below has a Hub-managed lifecycle; the other targets use native registration or an explicit Skills root. Imported formats for other harnesses remain source history, outside current support. Existing external installations require their native owner's removal or an explicitly reviewed source transition; copying the package into this repository does not adopt them.

Set task-specific paths. `PSTACK_HOME` must be a dedicated target below the workspace's `.azhou/hub/` or an explicitly selected separate home; do not point it at the project itself. The package source defaults to `packages/pstack-agent-harness`; `--source` is optional and only asserts that canonical path. For the installed runtime, `CODEX_HOME` below is set only for that one process.

Codex normally uses `~/.codex` when `CODEX_HOME` is unset. Its local plugin cache is below that home's `plugins/cache/`; bundled or remote catalog plugins may have other managed source locations. A sibling such as `~/.codex-pstack` is a separate configuration, even though it is outside a project. It is available only to Codex processes launched with that home; an already-running desktop app does not switch homes when a terminal command sets the variable. The adapter accepts a fresh or previously owned target and rejects unknown non-empty targets and known Agent Orchestration Kit configuration. Installing into the default home while preserving an existing Kit installation is not currently supported by this adapter.

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

Replace `PLAN_ID` with the current plan output. The adapter calls native `plugin marketplace add` with its private **in-repository snapshot**, then `plugin add pstack@pstack-claude`. The marketplace name `pstack-claude` is retained for compatibility; the reviewed local source path determines the installed bytes. The adapter verifies the native marketplace root, marketplace source, plugin source path, installed version, current snapshot files and the complete plugin file set. Existing foreign installations are not adopted.

After opening the dedicated session, inspect native Skills and invoke `pstack:how` or another selected workflow. `doctor` proves installed files and registration; it does not prove invocation. `/setup-pstack` owns model-sheet setup. On Codex the native sheet is `<codex-home>/pstack-models.md`; the upstream setup instructions also place model rows in the home `AGENTS.md`. Review the rows and available model aliases first. The Hub does not invent a universal model table.

The `SessionStart` hook requires native `/hooks` trust review. Setting `session hook: off` in that target's model sheet stops automatic injection, while explicit Skill invocation remains available. No adapter bypasses hook trust.

### Sharing one Codex home with the Agent Orchestration Kit

Both orchestration packages can share one controlled Codex home. One compatibility verdict — `pstack_coexistence` in the Kit's `install_codex.py` — is enforced by both public entries, so the Hub's `model-router` entry and the Kit's own `setup.sh` reach the same conclusion for the same target: a model sheet, visible pstack Skills, or a cached plugin copy alone is never evidence of auto-routing, while native registration whose sheet lacks the exact `session hook: off` line is armed and blocks a Kit install until the target is converted. Duplicate pstack plugin copies and symlinked plugin state stay errors.

Install the Kit first and plan pstack against the same home (coexistence is then automatic), or declare the intent before the Kit arrives:

```sh
python scripts/azhou_hub.py integrations pstack plan --coexistence \
  --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$SHARED_HOME" --codex-bin "$CODEX_BIN"
```

Besides native registration, a coexistence plan owns exactly one narrow change: the model sheet's `session hook` line switched to `off`, with every other byte, encoding and line ending preserved — or a minimal sheet written when none exists. The plan lists that change with its owner (`hub-pstack-adapter`), purpose and restore behavior, and reports the target as compatible only after the reviewed plan is applied; planning alone modifies nothing. A target whose routing is already armed is converted by that same reviewed plan, and an undecodable sheet blocks instead of being rewritten. An existing standalone installation is recognized when it is later updated to coexistence rules: its receipt stays valid, the plan reports the pending sheet change, and applying it converts the target in place, after which replans report the sheet as already satisfied. `remove` restores the exact prior sheet bytes or deletes the adapter-written sheet, keeps every Kit-owned file, and refuses automatic restore after later user edits, printing the recorded and observed digests of the refusal. A standalone pstack install — no Kit rules in the target — keeps its existing routing mode untouched.

`doctor` reports the states separately: Kit rules present, the model sheet and its `session hook` value, native plugin registration, the resulting `auto_routing` judgment, and hook trust as unknown, because only the host's `/hooks` review decides whether the hook runs.

```sh
python scripts/azhou_hub.py integrations pstack plan --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations pstack apply --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
```

Removal calls native plugin removal followed by marketplace removal, then checks both lists. It restores the adapter-owned coexistence sheet change when the receipt records one, as described above. It retains the frozen source and Hub receipt. A partial install records completed native steps; a new plan/apply resumes, or the remove operation cleans only that recorded native installation. Unrecognized cache additions block removal. The upstream Bun bootstrap may create `skills/poteto-mode/scripts/node_modules`; `doctor` reports it as outside source-file verification, and automatic removal refuses unrecorded dependency files instead of deleting them by assumption.

### Retiring an upstream installation

Inspect the native registration's source and scope before removal. Preserve model sheets and local source changes, then use the native manager to uninstall the exact pstack plugin. Keep a marketplace that still supplies other plugins, and let the native manager retire caches that are in use. For a shared Skills installation, remove only links whose targets were verified to belong to the retired source; other entries remain user-owned. Back up any pstack-specific standing instruction before removing its bounded block or exact pointer. Source clones can be retired after their local changes are preserved and no installed references or processes depend on them.

Model sheets in automatically loaded rule locations still inject instructions after a plugin is removed. Preserve their contents outside those locations when retiring the installation: [Claude user rules](https://code.claude.com/docs/en/memory#user-level-rules) apply across projects, and [Cursor rules](https://cursor.com/docs/rules) with `alwaysApply: true` are always included. A saved sheet with no include, rule registration or standing pointer can remain as dormant user preferences for a later Hub-sourced installation.

`~/.agents/skills` is a shared Skills discovery directory, including for Codex processes with an isolated home. A skills-only pstack installation there has no native routing hook. Its presence alone does not establish automatic routing or require a native-plugin conversion; choose one workflow owner per task. A later shared installation must link to this Hub's maintained package, and its removal affects every runtime that reads the shared directory. This manual source-retirement procedure does not adopt unknown installations or replace the planned controlled-conversion lifecycle.

## Model router: native roles, one workflow owner

The package is **Agent Orchestration Kit** at `packages/agent-orchestration-kit/`. Select task-specific workspace, Codex home, Skill root and runtime paths. The package source defaults to that canonical path; optional `--source` only asserts it:

```sh
ROUTER_WORKSPACE=/absolute/router-test-project
ROUTER_HOME="$ROUTER_WORKSPACE/codex"
ROUTER_SKILLS="$ROUTER_WORKSPACE/.agents/skills"
CODEX_BIN=/absolute/path/to/verified/codex
python scripts/azhou_hub.py integrations model-router plan \
  --workspace "$ROUTER_WORKSPACE" \
  --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations model-router apply \
  --workspace "$ROUTER_WORKSPACE" \
  --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
python scripts/azhou_hub.py integrations model-router verify \
  --workspace "$ROUTER_WORKSPACE" --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS"
env CODEX_HOME="$ROUTER_HOME" "$CODEX_BIN" -C "$ROUTER_WORKSPACE"
```

The source installer validates a staged configuration with the selected native binary before writing, merges its owned settings conservatively, and verifies effective configuration, the named-role tool schema, the instruction block and a unique enabled Skill. Failure rolls back. `verify` sends no model request. Run a bounded real delegation and inspect child session metadata separately. The installer refuses a target where pstack auto-routing is armed — native registration whose model sheet lacks the exact `session hook: off` line — using the same verdict both public entries share; see [Sharing one Codex home with the Agent Orchestration Kit](#sharing-one-codex-home-with-the-agent-orchestration-kit).

Codex also discovers the real user's `~/.agents/skills`, even when its configuration home is isolated. Two `astra-orchestrator` Skills cause the source's uniqueness check to fail. Do not disable that check or delete the user's Skill. A pre-existing **byte-identical** selected Skill can be reused: set `ROUTER_SKILLS` to its existing root only after checking that `plan.changes` contains no user-level path. In this case the Skill is watched and reused read-only; it is not a new isolated Skill installation. The dated record states exactly which case was tested.

For exit, use the same targets with `uninstall-plan`, then `uninstall --plan-id PLAN_ID`. `recover` handles a recorded interrupted operation. Restore refuses changed installed files or unowned transaction directories, reporting the recorded and observed digest of each refusal. Pre-existing files return byte-for-byte, including original modes; unrelated files and current sessions remain. Retained evidence and empty directories are not a claim of an active installation. The Kit's direct entry has the matching exit for a completed installation: `./packages/agent-orchestration-kit/setup.sh --uninstall` restores the owned `config.toml` keys, the instruction block and the files that install created from its ownership record — never whole files — and leaves unrelated content, later additions and a shared pstack installation untouched. Uninstall and interrupted-transaction recovery (`--recover`) are separate commands on both entries; removing either module leaves the other usable in its retained mode.

### Workflow and model contract

| Decision | pstack mode | Agent Orchestration Kit mode |
|---|---|---|
| Workflow and task decomposition | Selected pstack workflow and its Codex mapping | Root following `astra-orchestrator` and the user's bounded task |
| Task ownership | Only a task the user explicitly selected; a visible Skill, an existing model sheet, or loaded reference material does not take over | Ordinary tasks, and every task not explicitly given to another workflow; it yields decomposition, dispatch, and verification for a task the user assigned to pstack |
| Same-goal follow-ups and task end | A status question or an added constraint within the same task keeps pstack as owner; the next task returns to the host defaults, and a mid-task switch first waits for, stops, or closes running children | The same boundary from the other side: no second flow on a pstack-owned task, and no ownership claimed after it completes |
| Child dispatch | Ad-hoc `spawn_agent`; explicit model/effort from the selected pstack model policy, and no named custom role, because a selected custom-role file overrides the explicit fields it sets | Named custom role; the role TOML selects its model and effort |
| Rejected model or capacity | An explicitly rejected model falls back only to a sheet-declared, host-supported model, and the fallback is reported; a capacity error stops spawning; a required independent review stays blocked | Role files select model and effort; report the role actually dispatched |
| Root/reviewer | No Hub override to pstack policy | `gpt-6.1-sol` / `high` |
| Explorer/worker/tester/researcher | Defined by the pstack task's policy | `gpt-6-luna` / `max` |
| Specialist | No automatic conversion to a router role | `astra-specialist`: `gpt-6-astra` / `medium`, only under its escalation rules |
| Concurrency and permissions | Native host capabilities and source policy | Four concurrent children; child permissions inherit from the parent, even for a role described as read-only |

The existing [orchestrator composition rule](skill-standard.md) remains in force: one workflow owner per task, no orchestrator-to-orchestrator chain. Task-level ownership is a rules contract shipped by the installed artifacts themselves — the Kit's managed instruction block and `astra-orchestrator` Skill, and pstack's Codex mapping — so the rules load with each installation and never depend on this checkout at runtime. Selecting a pstack workflow never switches the active root session model, and user instructions, project rules, permissions, and concurrency limits apply on both paths.

One Codex home can now hold both packages through either public entry: compatibility is judged from actual registration and the model sheet's `session hook` line rather than mere presence, and both install orders converge on the same coexistence configuration with repeat installs changing nothing. That is a deterministic lifecycle result — plan disclosure, diagnosis, conversion and rollback, tested through the public entries with a fake native runtime; no real-host coexistence session, hook-trust approval or live routing observation is claimed. A bounded native dispatch receipt for both paths on an isolated Codex home is in the [2026-10-26 dispatch record](../evidence/pstack-orchestrator-dispatch-2026-10-26.md). No home layout isolates every global Skill, so inspect native discovery and disable a competing Skill for the individual test invocation where needed. This is selection between workflows, not a new route adapter. No joint workflow is claimed and no combined benchmark is needed.

The native configuration and child-setting rules are distinct. For the tested client, root configuration resolves CLI overrides before trusted project configuration, selected profile, user configuration and lower-priority defaults. For a child, explicit spawn values resolve before agent defaults and parent values, **then the selected custom role file overrides the fields it sets**. A role's read-only prose does not create a separate sandbox. Source: [official config precedence](https://learn.chatgpt.com/docs/config-file/config-basic), [official custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [local Skill discovery](https://learn.chatgpt.com/docs/build-skills). Recheck with native `config/read`, rendered tool schema and runtime metadata when the client changes; model self-report is not evidence.

## Animation: build, test entry and production boundary

The package is at `packages/codex-startup-animation/`. The CLI uses it by default; optional `--source` only asserts that canonical path. Its code has no recorded open-source license grant, so the Hub root license does not apply and source/binary publication remains on hold pending maintainer authorization. Personal artwork is never included in the package.

```sh
ANIMATION_WORKSPACE=/absolute/animation-test-project
PRIVATE_INPUTS=/absolute/explicit-private-inputs
python scripts/azhou_hub.py integrations startup-animation check-source
python scripts/azhou_hub.py integrations startup-animation build \
  --workspace "$ANIMATION_WORKSPACE" --private-assets "$PRIVATE_INPUTS"
```

The last command is a plan. Repeat it with `--apply --plan-id PLAN_ID` after reviewing the targets and four private-input hashes. Supply `working.png`, `scene.js`, `wallpaper-scene-q-v3.png` and `app-icon/source.png`; missing inputs fail. The adapter copies them only into ignored local state, runs the fixed native build and compares the final marker against **all** approved private inputs. The temporary empty Git database in that snapshot serves only the native ignore checks, not source-history attribution.

Use the returned `.build/azhou-payload` path as `PAYLOAD`. Test installation likewise requires its own current plan:

```sh
python scripts/azhou_hub.py integrations startup-animation test-install \
  --workspace "$ANIMATION_WORKSPACE" --payload "$PAYLOAD"
# Repeat with --apply --plan-id PLAN_ID; set TEST_APP to the returned path.
python scripts/azhou_hub.py integrations startup-animation inspect --bundle "$TEST_APP"
python scripts/azhou_hub.py integrations startup-animation run --bundle "$TEST_APP" --mode smoke
python scripts/azhou_hub.py integrations startup-animation run --bundle "$TEST_APP" --mode probe
```

`run` is a plan until repeated with `--apply --plan-id PLAN_ID`. `smoke` runs a one-shot player without launching or enhancing Codex. `probe` resolves the actual `com.openai.codex` target without launching it. The returned log must name the installed application; a source preview or successful exit alone is insufficient. The optional `--evidence` path must be inside this Hub checkout's `.azhou/hub/` and is bound into the plan.

`launch` preserves the current source behavior: player, target start/reuse, **and a coupled wallpaper attempt**. This source has no pure launch-without-wallpaper mode. Plans disclose temporary locks, helper logs and the possible lifetime of a cold-start loopback debugging port. `wallpaper-status` is a separate read-only check. `disable-wallpaper` requires a specific target PID and bundle and restores only the helper-owned page state; it does not terminate the host or close its debugging port. Playback, handoff, helper report, live page state and visual review are separate results. Never restart an active host merely to make an acceptance test pass.

For the test entry, use `test-uninstall --workspace ...`, then repeat with `--apply --plan-id PLAN_ID`. macOS may automatically register even a directly executed test `.app`; cleanup is limited to this receipt-owned exact path and must preserve other registrations. Cleanup uses the verified private package snapshot and receipt, so later package changes do not remove the recovery source. New build, install, run and inspect plans fingerprint the current in-repository inputs. This is separate from the native production entry. Apple describes `lsregister` as a [debugging tool, not a stable API](https://developer.apple.com/forums/thread/725805); the tested exact-path operation and NSWorkspace before/after check do not establish support for every macOS release.

`install-plan` and `uninstall-plan` describe the production target and return `blocked_source_contract`. The Hub package's native installer has a narrow one-time `--migrate-from OLD_ROOT` operation for an existing launcher at the fixed user Applications entry. Run it only from the final Hub package path after building its own payload. It requires matching old schema-2 installation receipt, old build payload and installed app fingerprints, the old build marker, unique registration, a user-entry lock and both project install locks. It replaces the exact verified entry, writes a Hub-owned receipt with `sourceHandoff`, and leaves the old checkout intact for separate archival or removal. A normal install still rejects another `projectRoot`. This native handoff does not implement the Hub adapter's general production install/uninstall plans; explicit build/state/destination and native uninstall contracts remain needed there. `native-check` remains read-only. The original official Codex entry remains available.

### Pet maintenance after the import

The animation package also carries `pet/theme.json`, `tools/manage-codex-pet.py` and its isolated tests. The package tool owns Pet preparation, validation, packaging, installation, synchronization and recovery; the Hub integration CLI has no Pet subcommand. See the [package runbook](../packages/codex-startup-animation/docs/codex-pet.md).

From the Hub root, these commands inspect state or run isolated tests:

```sh
python -B packages/codex-startup-animation/tools/manage-codex-pet.py status
python -B packages/codex-startup-animation/tools/test-codex-pet.py
```

A source-only checkout lacks private theme inputs, frozen snapshots and reviewed candidates. Its `status` can report invalid source/candidate state or `unknown-target` for an existing Pet whose receipt belongs to the old `projectRoot`. Those results do not establish that the old installation is damaged. The top-level status command is an inspection result, not a readiness or host-activation verdict. Likewise, `native-check` requires that selected package root's build payload; a missing payload does not diagnose an installation built elsewhere.

Use explicitly authorized private inputs and revalidate their frozen candidate/review chain before considering synchronization. A changed theme requires generation and renewed review; `sync` never generates images. Current Pet revision inputs are the two configured private images, `style.css` and `pet/theme.json`, not every visual file. Keep the old root and installation receipts intact until the handoff and recovery checks pass; rewriting `projectRoot` or copying `.local` does not create a verified installation transfer.

To reuse an existing reviewed candidate, first preserve the old working tree and its private candidate/frozen-input evidence. The separate importer uses this package's validator and packaging code; `--from-project` selects data, not another implementation:

```sh
PET_SOURCE=/absolute/original-project
PET_TARGET=/absolute/hub/packages/codex-startup-animation
python -B "$PET_TARGET/tools/import-codex-pet.py" \
  --from-project "$PET_SOURCE" --project-root "$PET_TARGET"
# Review the current plan, then repeat with its exact planId:
python -B "$PET_TARGET/tools/import-codex-pet.py" \
  --from-project "$PET_SOURCE" --project-root "$PET_TARGET" \
  --apply --plan-id PLAN_ID
```

The plan is read-only. Apply requires an unchanged source and target, a fully validated selected source candidate, matching public theme inputs, and absent or byte-identical private images. It refuses conflicting files and unknown target state. An owned interrupted import can be resumed after reviewing a new plan; unrelated state is never deleted to make room. The result is a newly validated, target-owned **candidate** with retained source provenance and original atlas/QA bytes. It does not call image generation, install or select a Pet, or transfer the installed receipt.

For an existing installed Pet whose receipt still names the old project, the package manager offers an explicit one-time `handoff` from the final Hub package path:

```sh
python -B "$PET_TARGET/tools/manage-codex-pet.py" handoff \
  --project-root "$PET_TARGET" --previous-project-root "$PET_SOURCE"
python -B "$PET_TARGET/tools/manage-codex-pet.py" status --project-root "$PET_TARGET"
```

It verifies the old selected candidate, the installed package and the Hub candidate match by theme, atlas and manifest digest; then uses the existing locked installation transaction to issue a Hub-owned receipt. Ordinary `install` and `sync` remain strict about project ownership. The old source and evidence should remain until Hub status verifies the installed bytes. A successful handoff still requires separate real host selection and playback acceptance.

This is an initial import or a retry of the same recorded operation. It does not merge an unrelated existing candidate store or silently switch to a changed source. After import, normal candidate updates remain with the package's existing preparation, review and packaging workflow.

`matchesSelectedPackage` compares installed bytes with the tool's selected candidate, not the host's selected avatar. `pending-refresh-selection` is the tool's fixed runtime boundary; real selection, playback and direction behavior require separate observation. Private inputs, candidates and installation receipts remain local. The standard-library repository gate runs the native installer suite; the Pillow-dependent Pet and importer suites run separately in the macOS CI leg and should both run for Pet runtime changes:

```sh
python -B packages/codex-startup-animation/tools/test-codex-pet.py
python -B packages/codex-startup-animation/tools/test-import-codex-pet.py
```

## Why these checks are necessary

The initial read-only review answered the four implementation questions with concrete consequences:

| Question | Implementation consequence |
|---|---|
| Necessary work beyond copying capabilities? | Keep three native projects as independent packages, select only declared runtime inputs, bind current bytes to each plan, preserve recovery after source edits, and separate private artwork, playback, host launch and appearance evidence. |
| Which primary materials prove what? | Package manifests and runtime source show current intended inputs; package licenses define stated grants; host protocol/config and task metadata prove native discovery/dispatch. README and dated receipts locate evidence but do not prove current behavior. |
| How is the path traced? | `hub-package.json` runtime paths → per-plan digest → private package snapshot → native plan/installer → receipt → native list/config/schema → task or installed-player events. Dated acceptance records remain tied to their original inputs. |
| What can disprove correctness? | Changed package bytes, native configuration/Skill validation, independent review, altered target/dependency/material/transaction negative controls, installed resource hashes and actual run metadata. Formal visual approval, redistribution permission and unexecuted host behavior remain explicit holds. |

Run the repository gate with `python scripts/verify.py`; it includes each package's targeted native tests. The [2026-10-25 acceptance report](../evidence/optional-integrations-2026-10-25.md) and [support matrix](support-matrix.md#optional-integrations) are historical evidence, not fresh acceptance of the monorepo package contents. No quality, latency, price or cross-harness equivalence claim follows from these integrations.

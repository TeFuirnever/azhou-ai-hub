# Optional integrations / 可选能力接入

The fourteen canonical Skills keep their existing independent install, discovery and invocation contracts. These three optional entries are checkout tools, not three new Skills and not a general plugin manager. `setup` does not enable them. The Hub maintains only the fixed source locks, small adapters, receipts, targeted tests and this runbook. The sources remain the single owners of their implementation.

```sh
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
python scripts/azhou_hub.py integrations model-router --help
python scripts/azhou_hub.py integrations startup-animation --help
```

Use Python 3.11+, Git and an explicit absolute source path. The tested native surface is the macOS Codex runtime identified in the [dated acceptance record](../evidence/optional-integrations-2026-10-25.md); neither other operating systems nor arbitrary Codex versions inherit that runtime claim. Resolve and inspect the actual Codex executable, not only the command found first on `PATH`.

## Delivery and ownership

| Entry | Hub maintains | External owner and runtime | Selection and invocation | Exit and update |
|---|---|---|---|---|
| `pstack` | Fixed 239-file input manifest, local snapshot, native install/doctor/remove adapter | Selected pstack fork; Codex plugin manager owns configuration and the plugin cache. Bun/Node are needed by bundled execution scripts; forge workflows additionally require their declared tools. | Explicit dedicated Codex home; native plugin discovery exposes `pstack:*` Skills, including `pstack:how`. Review hook trust separately. | Native plugin and marketplace removal through the receipt; update the fixed manifest only after source review and new acceptance. |
| `model-router` | Fixed 13-file source manifest, plan/verify/recovery and exact pre-install restore receipt | Agent Orchestration Kit's native installer owns the `azhou-balanced` config, six roles, marked instructions and orchestrator Skill. Codex owns actual dispatch. | Explicit Codex home and Skill root; invoke `astra-orchestrator` in a new session that reads those settings. | Restore only this invocation's changed files; preserve pre-existing identical Skill/config content. Review a new source pin before reinstalling. |
| `startup-animation` | Fixed 22-file worktree manifest, isolated build/test install/run/inspect and production blocking plans | Native macOS Swift/AppKit/WKWebView player, source installer and Codex-specific wallpaper helper. Four explicitly supplied private inputs are required. | Explicit build workspace and input directory; run the verified payload or Hub-owned test application. Production entry remains source-owned. | Test uninstall removes only its receipt-owned copy and its exact system registration; use the official Codex entry to stop using the launcher. Live wallpaper restore is separate. |

Adapters freeze selected source files below `<workspace>/.azhou/hub/sources/`. Receipts and raw evidence remain in ignored `.azhou/hub/` state. They can contain local paths and exact rollback bytes; do not publish them. Source locks are integrity checks, not signatures or proof that an upstream author approved this integration. Build outputs and explicitly supplied private inputs have separate validation from the public source-file lock.

No source checkout is reset, cleaned, committed or modified by these adapters. A mismatched HEAD, selected dirty input, executable bit, installed file, transaction identity or source path is a failure, not a reason to refresh a lock silently. See [provenance and fixed-version updates](integration-provenance.md).

## pstack: local source to native plugin

Set task-specific absolute paths. `PSTACK_HOME` must be a dedicated target below the workspace's `.azhou/hub/` or an explicitly selected separate home; do not point it at the project itself. For the installed runtime, `CODEX_HOME` below is set only for that one process.

```sh
PSTACK_SOURCE=/absolute/pstack-agent-harness
PSTACK_WORKSPACE=/absolute/test-project
PSTACK_HOME="$PSTACK_WORKSPACE/.azhou/hub/targets/pstack"
CODEX_BIN=/absolute/path/to/verified/codex

python scripts/azhou_hub.py integrations pstack plan \
  --source "$PSTACK_SOURCE" --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations pstack apply \
  --source "$PSTACK_SOURCE" --workspace "$PSTACK_WORKSPACE" \
  --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
python scripts/azhou_hub.py integrations pstack doctor \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
env CODEX_HOME="$PSTACK_HOME" "$CODEX_BIN" -C "$PSTACK_WORKSPACE"
```

Replace `PLAN_ID` with the current plan output. The adapter calls native `plugin marketplace add` with the frozen **local path**, then `plugin add pstack@pstack-claude`. It does not run the README's online command targeting the port upstream. It verifies the native marketplace root, marketplace source, plugin source path, installed version, every selected runtime hash and the complete plugin file set. Existing foreign installations are not adopted.

After opening the dedicated session, inspect native Skills and invoke `pstack:how` or another selected workflow. `doctor` proves installed files and registration; it does not prove invocation. `/setup-pstack` owns model-sheet setup. On Codex the native sheet is `<codex-home>/pstack-models.md`; the upstream setup instructions also place model rows in the home `AGENTS.md`. Review the rows and available model aliases first. The Hub does not invent a universal model table.

The `SessionStart` hook requires native `/hooks` trust review. Setting `session hook: off` in that target's model sheet stops automatic injection, while explicit Skill invocation remains available. No adapter bypasses hook trust.

```sh
python scripts/azhou_hub.py integrations pstack plan --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations pstack apply --operation remove \
  --workspace "$PSTACK_WORKSPACE" --codex-home "$PSTACK_HOME" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
```

Removal calls native plugin removal followed by marketplace removal, then checks both lists. It retains the frozen source and Hub receipt. A partial install records completed native steps; a new plan/apply resumes, or the remove operation cleans only that recorded native installation. Unrecognized cache additions block removal. The upstream Bun bootstrap may create `skills/poteto-mode/scripts/node_modules`; `doctor` reports it as outside source-file verification, and automatic removal refuses unrecorded dependency files instead of deleting them by assumption.

## Model router: native roles, one workflow owner

The actual source project is **Agent Orchestration Kit**. The old directory name is not an API or a supported alias. Select the current source and an explicit Skill root:

```sh
ROUTER_SOURCE=/absolute/agent-orchestration-kit
ROUTER_WORKSPACE=/absolute/router-test-project
ROUTER_HOME="$ROUTER_WORKSPACE/codex"
ROUTER_SKILLS="$ROUTER_WORKSPACE/.agents/skills"
CODEX_BIN=/absolute/path/to/verified/codex
python scripts/azhou_hub.py integrations model-router plan \
  --source "$ROUTER_SOURCE" --workspace "$ROUTER_WORKSPACE" \
  --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS" --codex-bin "$CODEX_BIN"
python scripts/azhou_hub.py integrations model-router apply \
  --source "$ROUTER_SOURCE" --workspace "$ROUTER_WORKSPACE" \
  --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS" --codex-bin "$CODEX_BIN" --plan-id PLAN_ID
python scripts/azhou_hub.py integrations model-router verify \
  --workspace "$ROUTER_WORKSPACE" --codex-home "$ROUTER_HOME" --skills-dir "$ROUTER_SKILLS"
env CODEX_HOME="$ROUTER_HOME" "$CODEX_BIN" -C "$ROUTER_WORKSPACE"
```

The source installer validates a staged configuration with the selected native binary before writing, merges its owned settings conservatively, and verifies effective configuration, the named-role tool schema, the instruction block and a unique enabled Skill. Failure rolls back. `verify` sends no model request. Run a bounded real delegation and inspect child session metadata separately.

Codex also discovers the real user's `~/.agents/skills`, even when its configuration home is isolated. Two `astra-orchestrator` Skills cause the source's uniqueness check to fail. Do not disable that check or delete the user's Skill. A pre-existing **byte-identical** selected Skill can be reused: set `ROUTER_SKILLS` to its existing root only after checking that `plan.changes` contains no user-level path. In this case the Skill is watched and reused read-only; it is not a new isolated Skill installation. The dated record states exactly which case was tested.

For exit, use the same targets with `uninstall-plan`, then `uninstall --plan-id PLAN_ID`. `recover` handles a recorded interrupted operation. Restore refuses changed installed files or unowned transaction directories. Pre-existing files return byte-for-byte, including original modes; unrelated files and current sessions remain. Retained evidence and empty directories are not a claim of an active installation.

### Workflow and model contract

| Decision | pstack mode | Agent Orchestration Kit mode |
|---|---|---|
| Workflow and task decomposition | Selected pstack workflow and its Codex mapping | Root following `astra-orchestrator` and the user's bounded task |
| Child dispatch | Ad-hoc `spawn_agent`; explicit model/effort from the selected pstack model policy | Named custom role; the role TOML selects its model and effort |
| Root/reviewer | No Hub override to pstack policy | `gpt-6.1-sol` / `high` |
| Explorer/worker/tester/researcher | Defined by the pstack task's policy | `gpt-6-luna` / `max` |
| Specialist | No automatic conversion to a router role | `astra-specialist`: `gpt-6-astra` / `medium`, only under its escalation rules |
| Concurrency and permissions | Native host capabilities and source policy | Four concurrent children; child permissions inherit from the parent, even for a role described as read-only |

The existing [orchestrator composition rule](skill-standard.md) remains in force: one workflow owner per task, no orchestrator-to-orchestrator chain. The two adapters reject known competing configuration in the same home. A separate home does not isolate every global Skill, so inspect native discovery and disable a competing Skill for the individual test invocation where needed. This is selection between workflows, not a new route adapter. No joint workflow is claimed and no combined benchmark is needed.

The native configuration and child-setting rules are distinct. For the tested client, root configuration resolves CLI overrides before trusted project configuration, selected profile, user configuration and lower-priority defaults. For a child, explicit spawn values resolve before agent defaults and parent values, **then the selected custom role file overrides the fields it sets**. A role's read-only prose does not create a separate sandbox. Source: [official config precedence](https://learn.chatgpt.com/docs/config-file/config-basic), [official custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [local Skill discovery](https://learn.chatgpt.com/docs/build-skills). Recheck with native `config/read`, rendered tool schema and runtime metadata when the client changes; model self-report is not evidence.

## Animation: build, test entry and production boundary

```sh
ANIMATION_SOURCE=/absolute/codex-startup-animation
ANIMATION_WORKSPACE=/absolute/animation-test-project
PRIVATE_INPUTS=/absolute/explicit-private-inputs
python scripts/azhou_hub.py integrations startup-animation check-source --source "$ANIMATION_SOURCE"
python scripts/azhou_hub.py integrations startup-animation build \
  --source "$ANIMATION_SOURCE" --workspace "$ANIMATION_WORKSPACE" --private-assets "$PRIVATE_INPUTS"
```

The last command is a plan. Repeat it with `--apply --plan-id PLAN_ID` after reviewing the targets and four private-input hashes. Supply `working.png`, `scene.js`, `wallpaper-scene-q-v3.png` and `app-icon/source.png`; missing inputs fail. The adapter copies them only into ignored local state, runs the fixed native build and compares the final marker against **all** approved private inputs. The temporary empty Git database in that snapshot serves only the native ignore checks, not source-history attribution.

Use the returned `.build/azhou-payload` path as `PAYLOAD`. Test installation likewise requires its own current plan:

```sh
python scripts/azhou_hub.py integrations startup-animation test-install \
  --source "$ANIMATION_SOURCE" --workspace "$ANIMATION_WORKSPACE" --payload "$PAYLOAD"
# Repeat with --apply --plan-id PLAN_ID; set TEST_APP to the returned path.
python scripts/azhou_hub.py integrations startup-animation inspect --source "$ANIMATION_SOURCE" --bundle "$TEST_APP"
python scripts/azhou_hub.py integrations startup-animation run --source "$ANIMATION_SOURCE" --bundle "$TEST_APP" --mode smoke
python scripts/azhou_hub.py integrations startup-animation run --source "$ANIMATION_SOURCE" --bundle "$TEST_APP" --mode probe
```

`run` is a plan until repeated with `--apply --plan-id PLAN_ID`. `smoke` runs a one-shot player without launching or enhancing Codex. `probe` resolves the actual `com.openai.codex` target without launching it. The returned log must name the installed application; a source preview or successful exit alone is insufficient. The optional `--evidence` path must be inside this Hub checkout's `.azhou/hub/` and is bound into the plan.

`launch` preserves the current source behavior: player, target start/reuse, **and a coupled wallpaper attempt**. This source has no pure launch-without-wallpaper mode. Plans disclose temporary locks, helper logs and the possible lifetime of a cold-start loopback debugging port. `wallpaper-status` is a separate read-only check. `disable-wallpaper` requires a specific target PID and bundle and restores only the helper-owned page state; it does not terminate the host or close its debugging port. Playback, handoff, helper report, live page state and visual review are separate results. Never restart an active host merely to make an acceptance test pass.

For the test entry, use `test-uninstall --source ... --workspace ...`, then repeat with `--apply --plan-id PLAN_ID`. macOS may automatically register even a directly executed test `.app`; cleanup is limited to this receipt-owned exact path and must preserve other registrations. Cleanup uses the verified installation snapshot and its original-source receipt, so a concurrently edited live source cannot trap an owned test installation or be executed during its removal. New build, install, run and public inspect operations still reject live-source drift. This is separate from the source-owned production entry. Apple describes `lsregister` as a [debugging tool, not a stable API](https://developer.apple.com/forums/thread/725805); the tested exact-path operation and NSWorkspace before/after check do not establish support for every macOS release.

`install-plan` and `uninstall-plan` describe the production target and return `blocked_source_contract`. The source installer hardcodes the user Applications entry, writes source-local build/state and exposes no uninstall operation. This Hub change does not bypass its `projectRoot` ownership check, duplicate that installer or alter the source. A separate source-owner change must define explicit build/state/destination and native uninstall contracts before Hub can offer that production lifecycle. `native-check` remains read-only. The original official Codex entry remains available.

## Why these checks are necessary

The initial read-only review answered the four implementation questions with concrete consequences:

| Question | Implementation consequence |
|---|---|
| Necessary work beyond copying capabilities? | Correct the stale router identity; pin dirty animation inputs; resolve duplicate global Skill discovery; establish installer ownership and recovery; separate private artwork, playback, host launch and enhancement evidence. |
| Which primary materials prove what? | Git objects/status and hashes identify inputs; native manifests/build/install code identify execution paths; licenses define stated grants; host protocol/config and run metadata prove discovery/dispatch. README and old receipts locate evidence but do not prove current behavior. |
| How is the path traced? | Source lock → bounded snapshot → native plan/installer → receipt → native list/config/schema → real task or installed-player events. Each level is recorded separately in the dated acceptance table. |
| What can disprove correctness? | The unchanged Hub gate, upstream generation checks, native configuration/Skill validation, independent review, altered-file/dependency/material/transaction negative controls, installed resource hashes and actual run metadata. Formal visual approval and unexecuted host behavior remain explicit holds. |

Run the existing repository gate with `python scripts/verify.py`. It includes the new targeted unit tests without replacing any old gate or removing any conflict check. Current positive, negative and pending results are in the [acceptance record](../evidence/optional-integrations-2026-10-25.md) and [support matrix](support-matrix.md#optional-integrations). No quality, latency, price or cross-harness equivalence claim follows from this integration.

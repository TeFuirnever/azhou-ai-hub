# Package provenance and updates

This document records provenance and update rules for the Hub's three complete project packages under `packages/`. Operational instructions belong in [integrations.md](integrations.md); public support claims belong in the [support matrix](support-matrix.md). The canonical Skills under `skills/` keep their independent installation and maintenance contract in [skill-standard.md](skill-standard.md).

来源、安装和运行是三层不同证据：包内来源记录不能证明宿主已经调用；原生安装成功不能证明模型身份或视觉效果。本页不把历史目录名、旧 source lock 或验收报告当作当前实现。

## Current package inputs

Each project's `hub-package.json` declares its repository/import provenance, native runtime version where one exists, license status and `runtime_paths`. The shared adapter resolves the in-repository package and fingerprints the current files and executable bits selected by those paths on every plan. There is no tracked external source lock. A receipt field named `source_lock_sha256` is the digest of that derived manifest and its current files, not a separately maintained pin. Commit fields identify original import provenance; they do not identify the current Hub revision or guarantee that the current package bytes equal an upstream commit.

| Integration | Complete project and provenance | Runtime version and rights |
| --- | --- | --- |
| pstack | [packages/pstack-agent-harness](../packages/pstack-agent-harness/README.md), a local fork of Michael Denyer's Codex port; original selected port commit `356c6e0f978df729eb16f227d795f34d221c5aad` | `0.9.102`; MIT package plus retained Cursor Team Kit and thermos notices |
| Model router | [packages/agent-orchestration-kit](../packages/agent-orchestration-kit/README.md), a local continuation of [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator); see its [UPSTREAM.md](../packages/agent-orchestration-kit/UPSTREAM.md) for source commit ancestry | Unreleased package; Apache-2.0 |
| Startup animation | [packages/codex-startup-animation](../packages/codex-startup-animation/README.md); public upstream [panding999/codex-startup-animation](https://github.com/panding999/codex-startup-animation), local fork origin `TeFuirnever/codex-startup-animation`, imported from base `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` with maintained local changes | Runtime `0.7.1`, build `8`; no open-source license grant recorded and no external distribution authorization |

The model-router and animation commit fields are provenance only. The animation base commit does not reconstruct its maintained implementation by itself; the current local package tree is the actual input. The adapter never resets or commits another source tree, and it never silently substitutes an upstream HEAD for the maintained package.

Only each manifest's declared runtime paths are initially materialized under the workspace's ignored `.azhou/hub/sources/<integration>/<digest>` directory. The receipt stores the frozen manifest, input digest and recovery data. That private snapshot remains available for owned recovery or cleanup if package files later change. Private paths, pre-install bytes, raw evidence, generated outputs and private artwork stay outside Git. A runtime update requires a new plan against the current package; do not silently adopt changed target files.

## pstack: complete source and generation chain

### Original upstream components

The selected port's `tools/upstream.json` declares three inputs from [cursor/plugins](https://github.com/cursor/plugins):

| Original component | Upstream path | Declared immutable pin | Local destination in the port |
| --- | --- | --- | --- |
| Lauren Tan's pstack | `pstack` | `7b353f78f6ec193bdbe48ed8059444eb09b6878e` | `plugins/pstack` |
| Cursor Team Kit | `cursor-team-kit/skills` | `e46364b8be46000b7df0f260550cd712afbb8d36` | Selected entries under `plugins/pstack/skills` |
| thermos | `thermos` | `118e73b0e196e4d49d5aade7ce6dd8985a621f68` | Selected entries under `plugins/pstack` |

The same file declares exclusions; an excluded upstream directory is not an accidentally missing runtime dependency. Examples include Cursor-only plugin metadata, original assets and automations, and the replaced upstream worktree-audit shell script. Preserve the actual exclusion list when reviewing an update.

These original pins were first read from the selected port's source declaration. A later primary-source audit queried GitHub's Git API for all three exact commits and their complete, non-truncated tree listings, then fetched eight original license/entry files and verified each Git blob hash against its tree. The selected pstack tree has 172 blobs, Cursor Team Kit 29 and thermos 10. Read original files include all three component licenses, pstack's README, `poteto-mode` and `how`, Team Kit's `deslop`, and thermos's entry Skill. This independently establishes the pins, original component paths, MIT attribution and selected original workflow contracts. It is not a semantic comparison of every original blob against the port. The [dated evidence](../evidence/optional-integrations-2026-10-25.md) records the earlier retrieval limitation and its supplementary audit; neither is the current package inventory or fresh native acceptance.

The opening pstack row in `NOTICE.md` still links to an older `e46364b` reference; it is a historical attribution link, not the current synchronization pin. The original `how` entry uses Cursor Task dispatch and a `pstack-models.mdc` rule; the port provides its own role defaults and `pstack-models.md` policy, while its Codex mapping explicitly translates to ad-hoc `spawn_agent`. Keeping those differences explicit is necessary to avoid installing a Cursor policy as if it were the Codex runtime contract.

### Port and local fork

The translation and host adaptation are maintained in [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude). The selected [public port commit](https://github.com/michael-denyer/pstack-claude/commit/356c6e0f978df729eb16f227d795f34d221c5aad) is `356c6e0f978df729eb16f227d795f34d221c5aad`, with parent `4ebb588f072fc9bb128f12ccac26153f77badc57`. That immutable commit was independently opened during source verification.

The local fork's recorded origin is [TeFuirnever/pstack-agent-harness](https://github.com/TeFuirnever/pstack-agent-harness). Its selected HEAD is the same port commit, and the selected source was clean. No additional local policy delta is claimed for this pin. The local repository name therefore does not imply a separately developed implementation at this version.

The port explicitly maintains differences from Cursor. Its `tools/forks.json` lists 47 pstack entries and one thermos entry, classified as `policy` or `port-feature`. Each entry identifies its reason, introduction version and upstream status. Examples include review-gate preservation, worktree isolation, merge-ready versus merge authority, host-specific tool translation, and the abandoned-agent replacement policy. These are declared behavioral differences, not evidence that one workflow is faster or better.

### Generation and synchronization

The source path is reproducible through the port's own tooling:

1. `tools/upstream.json` selects each original tree and exclusions. `tools/substitutions.json` defines mechanical rewrites and a denylist. `tools/forks.json` declares intentional differences.
2. `tools/sync.mjs` derives the original text for the old and new pins, then performs a three-way reconciliation with the local port. Its dry run is the review entry; the Hub never invokes a source-writing sync automatically.
3. `tools/generate.mjs` stamps `VERSION`, the role policy in `plugins/pstack/models.json`, the public-command table, host mapping preambles, prompt stubs and portable attribution copies into their maintained outputs.
4. `bun tools/generate.mjs --check` rejects generated-file drift, unresolved merge markers and the packaging/link/model inconsistencies covered by the source contract.

During this integration, the selected source's generation check reported **85 generated files current**, and the selected source test suites passed **376 tests** in an isolated complete source copy after installing its frozen development dependencies. The original source repository was not used as a dependency-installation target. These are source and packaging checks; they do not prove live Skill invocation or model routing.

### The installed object

The native Codex marketplace name remains `pstack-claude`, and the plugin identifier remains `pstack@pstack-claude`. Those names are retained from the selected source; they are not sufficient to identify where the installed bytes came from.

The Hub registers the **explicit absolute path of its private package snapshot**, whose `.agents/plugins/marketplace.json` resolves `pstack` from `./plugins/pstack`. It does not execute the README's online marketplace command. After installation, the adapter compares the native marketplace root and source, the plugin's local source path, and the installed runtime files with the selected snapshot and its per-plan fingerprint. This prevents a familiar plugin name from concealing installation of different bytes.

Codex owns the plugin registration and installed cache. The Hub owns its snapshot and receipt. Extra Skills, hooks or other unlisted source files invalidate the installation check. The source's Bun bootstrap may later generate `skills/poteto-mode/scripts/node_modules` using its frozen production lockfile; the adapter reports that dependency runtime separately and does not treat an install marker as a content audit. Unrecorded generated dependencies are not silently deleted by Hub removal.

## Model router: current identity and installation authority

The current source is the complete [Agent Orchestration Kit package](../packages/agent-orchestration-kit/), with provenance in its [UPSTREAM.md](../packages/agent-orchestration-kit/UPSTREAM.md). Its `hub-package.json` commit records the original local import, not current package contents. The package path is canonical; `--source` is optional and can only assert that path.

The adapter fingerprints and stages only paths declared in the package's `runtime_paths`, including the native installer, native discovery helper, balanced profile and Apache license. The native installer coordinates `config.toml`, the managed instruction block, six role files and its ownership state; the Hub does not add a second TOML writer or a new scheduler.

The selected files declare Sol `gpt-6.1-sol` with `high` effort for the root default and reviewer; Luna `gpt-6-luna` with `max` effort for explorer, worker, tester and researcher; and the bounded `astra-specialist` role using `gpt-6-astra` with `medium` effort. These are configuration declarations. Live model identity requires actual dispatch and runtime metadata; a model's self-description does not establish it.

The 2026-10-25 native record rejected an isolated attempt that would make the same-named `astra-orchestrator` Skill visible twice, and the native transaction restored the earlier target state. A subsequent isolated installation reused the already visible, identical-hash Skill without writing it and installed nine native-managed files. These are historical results for the inspected source and machine, not fresh acceptance of current package bytes. They do not authorize replacing a different user's Skill or assuming an old directory still exists.

pstack and this profile remain separate workflow entries. pstack's Codex mapping dispatches ad hoc agents with its own model policy; Agent Orchestration Kit supplies a workflow Skill and named role configuration. Neither adapter treats their coexistence as a tested chain. A separate configuration home also does not by itself hide globally discoverable Skills; discovery and task-level activation must be checked independently.

## Startup animation: code, assets and host boundaries

The local fork's package metadata records public upstream `panding999/codex-startup-animation`, local origin `TeFuirnever/codex-startup-animation`, original base commit `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`, and current runtime version `0.7.1` / build `8`. The base commit alone does not reproduce its maintained implementation. The Hub migration was explicitly authorized as local work with attribution; this is not permission to publish source or binaries.

The launcher implementation has three distinct parts:

| Part | Selected source and artifact path | Evidence boundary |
| --- | --- | --- |
| Standalone player | `Native/App.swift`, web animation files and the hidden `.build/azhou-payload` | Build identity, resource hashes, signature and native player events are distinct from visual approval |
| Codex launch/reuse | Existing native target resolution, launch and activation code | A running target must be reused without restarting an active session; target activation is not model readiness |
| Codex wallpaper helper | `Native/Wallpaper.swift`, `wallpaper/renderer.js`, `wallpaper/wallpaper.css` and generated wallpaper resources | A separate page operation requiring the existing target identity and connection conditions; a completed player does not prove wallpaper application |

The current normal launch path also attempts its existing wallpaper operation. There is no selected pure-launch flag that removes that coupling. Smoke preview, target probe, wallpaper status and explicit restoration are separate operations. Historic `extension/` code and `Native/Extension.swift`, other-host adapters and new artwork are outside this selection.

Pet theme configuration, maintenance/import code and isolated tests are included in the package runtime paths. Generated atlases, frozen inputs, reviewed candidates and installation receipts were excluded from the source import. The candidate importer can subsequently revalidate explicitly supplied local data, preserve original atlas/QA bytes and record its source while creating a new root-owned candidate; it does not generate images or transfer the existing installed receipt. Existing installations remain bound to their originating `projectRoot`. Follow the [Pet maintenance boundary](integrations.md#pet-maintenance-after-the-import) before operating from the new root.

The adapter can plan an isolated build from current package inputs and explicitly supplied private assets, inspect the resulting payload, and own a test installation. The 2026-10-25 record reports a successful build and installed-player checks for the then-selected source; the monorepo import has not received fresh native acceptance. No host restart or live appearance change was performed during this migration. Production installation remains blocked: the native installer fixes its application destination, writes source-local build/state directories and exposes no uninstall operation. The Hub does not bypass those ownership rules by becoming a second production installer. Any necessary destination/state/uninstall change belongs to a separate source-owner task.

### Program and material licenses

| Material | Declared rights and handling |
| --- | --- |
| pstack code, Skills and adapted components | MIT. Retain `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`, `NOTICE-skills.md` and the generated portable notices. |
| pstack's existing tracked icon | Its exact source bytes remain in the package snapshot and are accompanied by the source repository's license/notice material. It is an existing source asset, not newly generated Azhou artwork. |
| Agent Orchestration Kit selected code/profile | Apache-2.0. Retain the selected `LICENSE` with the local runtime subset; do not replace the license with the Hub's own. |
| Startup-animation program | No open-source license grant is recorded. The Hub root license does not apply to `packages/codex-startup-animation/`. Do not publish source or binaries until redistribution permission is clarified with the maintainer. |
| Startup-animation private art and derived bundles | The four required existing private inputs are supplied explicitly at runtime. Their bytes, private hashes and generated packages stay in ignored local state and outside the package. They are excluded from public distribution. |

The four private input roles are the working character image, scene data, wallpaper image and application-icon source. A build must bind the actual packaged inputs to the reviewed build plan. Keeping files out of Git and validating their hashes addresses packaging provenance; it does not constitute visual review or a new redistribution permission.

## Updating package inputs

Updates happen in the canonical `packages/<name>/` project and remain subject to that project's source and license rules. They are not automatic tracking of an external branch.

1. Review the package's upstream provenance, current source material, license, native entry points and local changes. Keep updates within the package; do not point an adapter at a sibling checkout.
2. Review `hub-package.json` and adjust `runtime_paths` only when the native install or build path changes. Keep `commit` and `original_import_commit` as original provenance; do not rewrite them to the current Hub revision or claim that current files equal the base commit.
3. Make the normal package edits and run that package's own checks. The next integration plan hashes current files and executable modes under `runtime_paths`; no tracked per-file hash list needs manual renewal.
4. Review the plan and computed digest before applying it. An installed older package may require receipt-owned recovery or removal first. The adapter's private snapshot and receipt retain the inputs and rollback data needed for that operation after the live package changes.
5. Run `python scripts/verify.py` and any required native checks. Update both READMEs and the support matrix only for behavior checked against the current package. Keep installation, native discovery, actual invocation and behavior evidence separate.

The [2026-10-25 acceptance record](../evidence/optional-integrations-2026-10-25.md) remains a historical snapshot of the inputs and machine observed then; it is not fresh native acceptance of this monorepo import. Private paths, credentials, raw transcripts, artwork, build outputs, installation snapshots and receipts remain in ignored local state.

# Package provenance and updates

This document records provenance and update rules for the Hub's complete project packages under `packages/`, including the canonical Agent Skin copy and the retained legacy startup-animation path used by existing receipts. Operational instructions belong in [integrations.md](integrations.md); public support claims belong in the [support matrix](support-matrix.md). The canonical Skills under `skills/` keep their independent installation and maintenance contract in [skill-standard.md](skill-standard.md).

来源、安装和运行是三层不同证据：包内来源记录不能证明宿主已经调用；原生安装成功不能证明模型身份或视觉效果。本页不把历史目录名、旧 source lock 或验收报告当作当前实现。

## Current package inputs

Each project's `hub-package.json` declares its repository/import provenance, native runtime version where one exists, license status and `runtime_paths`. The shared adapter resolves the in-repository package and fingerprints the current files and executable bits selected by those paths on every plan. There is no tracked external source lock. A receipt field named `source_lock_sha256` is the digest of that derived manifest and its current files, not a separately maintained pin. Commit fields identify original import provenance; they do not identify the current Hub revision or guarantee that the current package bytes equal an upstream commit.

| Integration | Complete project and provenance | Runtime version and rights |
| --- | --- | --- |
| pstack | [packages/pstack-agent-harness](../packages/pstack-agent-harness/README.md), assembled from three upstream components of [cursor/plugins](https://github.com/cursor/plugins) (pstack, six cursor-team-kit skills, three thermos skills) at commit `c742dd61706fbacc1b95f1a20b7b988cf096ce6c`; downstream defects ride the patch queue at [patches/series](../packages/pstack-agent-harness/patches/series) | Hub distribution `0.15.37` (pinned upstream `0.15.36`), MIT with retained Cursor Team Kit and thermos notices |
| Model router | [packages/agent-orchestration-kit](../packages/agent-orchestration-kit/README.md), a local continuation of [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator); see its [UPSTREAM.md](../packages/agent-orchestration-kit/UPSTREAM.md) for source commit ancestry | Unreleased package; Apache-2.0 |
| Agent Skin (Codex) | [packages/agent-skin](../packages/agent-skin/README.md); canonical copy of the Hub-tracked TeFuirnever source, with original public upstream [panding999/codex-startup-animation](https://github.com/panding999/codex-startup-animation) and local origin `TeFuirnever/codex-startup-animation` | Runtime `0.7.1`, build `8`; no open-source license grant recorded and no external distribution authorization |
| Legacy startup-animation | [packages/codex-startup-animation](../packages/codex-startup-animation/README.md); retained for existing installation and Pet receipt ownership | Runtime `0.7.1`, build `8`; same unlicensed source and distribution boundary as Agent Skin |

The package descriptors' commit fields record original import provenance. Their current local package trees are the installation inputs; an original commit alone does not reconstruct later Hub changes. The adapter never resets or commits another source tree, and it never silently substitutes an upstream HEAD for the maintained package.

Only each manifest's declared runtime paths are initially materialized under the workspace's ignored `.azhou/hub/sources/<integration>/<digest>` directory. The receipt stores the frozen manifest, input digest and recovery data. That private snapshot remains available for owned recovery or cleanup if package files later change. Private paths, pre-install bytes, raw evidence, generated outputs and private artwork stay outside Git. A runtime update requires a new plan against the current package; do not silently adopt changed target files.

## pstack: source and generation chain

The current source is the assembled distribution under [packages/pstack-agent-harness](../packages/pstack-agent-harness/), recorded in its [UPSTREAM.md](../packages/pstack-agent-harness/UPSTREAM.md): pristine `cursor/plugins` components at commit `c742dd61706fbacc1b95f1a20b7b988cf096ce6c` (`pstack`, six cursor-team-kit skills, three thermos skills plus both thermos agents), Hub-authored `hub-skills/`, `hub-adapters/` and `hub-runtime/`, and a quilt patch queue under `patches/` carrying one DEP-3 patch per upstream defect. `node tools/build-harness.mjs` assembles those sources, applies `patches/series`, runs upstream's own `generate-pstack-harness-trees.mjs` unmodified, and emits the runtime trees under `harness/pstack/`. The build refuses a patch that changes none of the files it declares, which is also the signal that upstream carries the fix and the patch should leave the queue.

### Retired fork-and-sync record (historical)

The earlier package was a local fork of Michael Denyer's Claude Code port ([`356c6e0`](https://github.com/michael-denyer/pstack-claude/commit/356c6e0f978df729eb16f227d795f34d221c5aad), origin `TeFuirnever/pstack-agent-harness`), maintained as Hub version `0.9.103`. It tracked its three upstream inputs through `tools/upstream.json` pins (`pstack` `7b353f78`, cursor-team-kit `e46364b`, thermos `118e73b`), reconciled updates with `tools/sync.mjs`, declared intentional divergence in `tools/forks.json`, and stamped releases with `tools/generate.mjs` plus a package-root `VERSION`. A primary-source audit on 2026-10-25 verified those pins against GitHub's Git API (172, 29 and 10 blobs respectively); the [dated evidence](../evidence/optional-integrations-2026-10-25.md) records the earlier retrieval limitation and its supplementary audit. That tooling, the fork tree `plugins/pstack/`, the package test suite and the TLA+/Lean models were retired when the package moved to pristine sources plus the patch queue. This paragraph is their provenance record, not current behavior.

### The installed object

The maintained native Codex marketplace name is `pstack-claude`, and its distributed plugin identifier is `pstack-azhouzhou@pstack-claude`. The Hub candidate is now `0.15.37`; the earlier installed user cache remains `0.15.36` until a separately reviewed native upgrade. Plugin names and versions alone do not establish the installed source bytes.

The Hub registers the **explicit absolute path of its private package snapshot**, whose `.agents/plugins/marketplace.json` resolves `pstack-azhouzhou` from `./harness/pstack/codex`. User installation instructions select the maintained Hub package; upstream repositories remain source-update and attribution references. After installation, the adapter compares the native marketplace root and source, the plugin's local source path, and the installed runtime files with the selected snapshot and its per-plan fingerprint. This prevents a familiar plugin name from concealing installation of different bytes.

Codex owns the plugin registration and installed cache. The Hub owns its snapshot and receipt. Extra Skills, hooks or other unlisted source files invalidate the installation check. The source's Bun bootstrap may later generate `skills/poteto-mode/scripts/node_modules` using its frozen production lockfile; the adapter reports that dependency runtime separately and does not treat an install marker as a content audit. Unrecorded generated dependencies are not silently deleted by Hub removal.

## Model router: current identity and installation authority

The current source is the complete [Agent Orchestration Kit package](../packages/agent-orchestration-kit/), with provenance in its [UPSTREAM.md](../packages/agent-orchestration-kit/UPSTREAM.md). Its `hub-package.json` commit records the original local import, not current package contents. The package path is canonical; `--source` is optional and can only assert that path.

The adapter fingerprints and stages only paths declared in the package's `runtime_paths`, including the native installer, native discovery helper, balanced profile and Apache license. The native installer coordinates `config.toml`, the managed instruction block, six role files and its ownership state; the Hub does not add a second TOML writer or a new scheduler.

The selected files declare Sol `gpt-6.1-sol` with `high` effort for the root default and reviewer; Luna `gpt-6-luna` with `max` effort for explorer, worker, tester and researcher; and the bounded `astra-specialist` role using `gpt-6-astra` with `medium` effort. These are configuration declarations. Live model identity requires actual dispatch and runtime metadata; a model's self-description does not establish it.

The 2026-10-25 native record rejected an isolated attempt that would make the same-named `astra-orchestrator` Skill visible twice, and the native transaction restored the earlier target state. A subsequent isolated installation reused the already visible, identical-hash Skill without writing it and installed nine native-managed files. These are historical results for the inspected source and machine, not fresh acceptance of current package bytes. They do not authorize replacing a different user's Skill or assuming an old directory still exists. The [2026-10-26 native acceptance](../evidence/pstack-orchestrator-native-acceptance-2026-10-26.md) repeats the current package's install through the Hub entry in a throwaway `HOME` — the uniqueness protection still fires under the real user scope and rolls back — and records the shared-home coexistence loop with pstack for the same source bytes.

pstack and this profile remain separate workflow entries. pstack's Codex mapping dispatches ad hoc agents with its own model policy; Agent Orchestration Kit supplies a workflow Skill and named role configuration. Neither adapter treats their coexistence as a tested chain. A separate configuration home also does not by itself hide globally discoverable Skills; discovery and task-level activation must be checked independently.

## Startup animation: code, assets and host boundaries

The local fork's package metadata records public upstream `panding999/codex-startup-animation`, local origin `TeFuirnever/codex-startup-animation` and original base commit `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`. The retained legacy source recorded runtime version `0.7.1` / build `8`; the current Agent Skin version is declared by its own `hub-package.json`. The base commit alone does not reproduce the maintained implementation. The Hub migration was explicitly authorized as local work with attribution; this is not permission to publish source or binaries.

The launcher implementation has three distinct parts:

| Part | Selected source and artifact path | Evidence boundary |
| --- | --- | --- |
| Standalone player | `Native/App.swift`, web animation files and the hidden `.build/azhou-payload` | Build identity, resource hashes, signature and native player events are distinct from visual approval |
| Codex launch/reuse | Existing native target resolution, launch and activation code | A running target must be reused without restarting an active session; target activation is not model readiness |
| Codex wallpaper helper | `Native/Wallpaper.swift`, `wallpaper/renderer.js`, `wallpaper/wallpaper.css` and generated wallpaper resources | A separate page operation requiring the existing target identity and connection conditions; a completed player does not prove wallpaper application |

The normal launch path also attempts its wallpaper operation. Smoke preview, target probe, wallpaper status and explicit restoration are separate operations. The original migration excluded the legacy `Native/Extension.swift`, other-host adapters and new artwork; the current Agent Skin package includes its own same-window `extension/` implementation.

Pet theme configuration, maintenance/import code and isolated tests are included in the package runtime paths. Generated atlases, frozen inputs, reviewed candidates and installation receipts were excluded from the source import. The candidate importer can subsequently revalidate explicitly supplied local data, preserve original atlas/QA bytes and record its source while creating a new root-owned candidate; it does not generate images or transfer an installed receipt. On the maintainer Mac, a later native handoff separately moved verified App and Pet receipt ownership to the Hub package. Follow the [Pet maintenance boundary](integrations.md#pet-maintenance-after-the-import) before operating from another root.

The adapter can plan an isolated build from current package inputs and explicitly supplied private assets, inspect the resulting payload, and own a test installation. The 2026-10-25 record reports a successful build and installed-player checks for the then-selected source. The [2026-10-26 local handoff](../evidence/optional-integrations-local-handoff-2026-10-26.md) adds a fresh native build, verified App replacement and Pet receipt handoff on one maintainer Mac; it did not restart Codex or test playback, wallpaper, Pet selection or visual appearance. General Hub adapter production install/uninstall plans remain blocked: the native installer fixes its application destination, writes source-local build/state directories and exposes no uninstall operation. The one-time native handoff does not make the Hub a second production installer. Any general destination/state/uninstall change belongs to a separate source-owner task.

### Program and material licenses

| Material | Declared rights and handling |
| --- | --- |
| pstack code, Skills and adapted components | MIT. Retain `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`, `NOTICE-skills.md` and the generated portable notices. |
| pstack's existing tracked icon | Its exact source bytes remain in the package snapshot and are accompanied by the source repository's license/notice material. It is an existing source asset, not newly generated Azhou artwork. |
| Agent Orchestration Kit selected code/profile | Apache-2.0. Retain the selected `LICENSE` with the local runtime subset; do not replace the license with the Hub's own. |
| Startup-animation program / Agent Skin copy | No open-source license grant is recorded. The Hub root license does not apply to `packages/agent-skin/` or `packages/codex-startup-animation/`. Do not publish source or binaries until redistribution permission is clarified with the maintainer. |
| Startup-animation private art and derived bundles | The four required existing private inputs are supplied explicitly at runtime. On the maintainer Mac they reside in the package's Git-ignored local state; their bytes, private hashes and generated packages are outside tracked source and public distribution. |

The four private input roles are the working character image, scene data, wallpaper image and application-icon source. A build must bind the actual packaged inputs to the reviewed build plan. Keeping files out of Git and validating their hashes addresses packaging provenance; it does not constitute visual review or a new redistribution permission.

## Updating package inputs

Updates happen in the canonical `packages/<name>/` project and remain subject to that project's source and license rules. They are not automatic tracking of an external branch.

1. Review the package's upstream provenance, current source material, license, native entry points and local changes. Keep updates within the package; do not point an adapter at a sibling checkout.
2. Review `hub-package.json` and adjust `runtime_paths` only when the native install or build path changes. Keep `commit` and `original_import_commit` as original provenance; do not rewrite them to the current Hub revision or claim that current files equal the base commit.
3. Make the normal package edits and run that package's own checks. The next integration plan hashes current files and executable modes under `runtime_paths`; no tracked per-file hash list needs manual renewal.
4. Review the plan and computed digest before applying it. An installed older package may require receipt-owned recovery or removal first. The adapter's private snapshot and receipt retain the inputs and rollback data needed for that operation after the live package changes.
5. Run `python scripts/verify.py` and any required native checks. Update both READMEs and the support matrix only for behavior checked against the current package. Keep installation, native discovery, actual invocation and behavior evidence separate.

The [2026-10-25 acceptance record](../evidence/optional-integrations-2026-10-25.md) remains a historical snapshot of the inputs and machine observed then. The [2026-10-26 local handoff](../evidence/optional-integrations-local-handoff-2026-10-26.md) records the later Hub-root native installation checks; neither record proves playback, wallpaper, Pet selection or visual approval. Private paths, credentials, raw transcripts, artwork, build outputs, installation snapshots and receipts remain in ignored local state.

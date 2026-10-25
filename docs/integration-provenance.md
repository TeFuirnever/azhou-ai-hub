# Integration provenance and fixed-version updates

This document records the selected sources for the Hub's three optional integrations. Operational instructions belong in [integrations.md](integrations.md); public support claims belong in the [support matrix](support-matrix.md). Existing canonical Skills keep their own installation and maintenance contract in [skill-standard.md](skill-standard.md).

来源、安装和运行是三层不同证据：固定来源不能证明宿主已经调用；原生安装成功不能证明模型身份或视觉效果。本页不把历史目录名、README 安装命令或已有报告当作当前实现。

## Selected source records

The source locks are the machine-readable authority. Each selected file has a SHA-256 and executable-bit intent. The common verifier checks the declared Git HEAD and file contents before materialization, then verifies the frozen copy. A commit selection also verifies every selected file against its Git blob and mode. Unselected source-worktree changes are reported but are not copied into the runtime subset.

| Integration | Selected identity | Pin type and scope | Lock |
| --- | --- | --- | --- |
| pstack | Local `pstack-agent-harness` fork of Michael Denyer's pstack port, version `0.9.102` | Commit `356c6e0f978df729eb16f227d795f34d221c5aad`; 239 selected files, including 224 files in the Codex plugin runtime tree | [pstack source lock](../integrations/pstack/source-lock.json) |
| Model router | **Agent Orchestration Kit**, existing Codex `azhou-balanced` profile | Commit `4d1a2081f96cdab8a9ea0fe3d357312471546dcc`; 13 files: native installer, native discovery helper, one profile and its license | [model-router source lock](../integrations/model-router/source-lock.json) |
| Startup animation | Existing Azhou Codex launcher, runtime `0.7.0`, build `7` | Base commit `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` **plus 22 individually hashed working-tree files**; this is not a clean-commit claim | [startup-animation source lock](../integrations/startup-animation/source-lock.json) |

The animation commit alone cannot reconstruct the selected implementation: the chosen working-tree bytes are also required. The adapter rejects a checkout or snapshot whose selected bytes have changed. It does not reset the source repository, commit another session's changes, or silently fall back to the base commit.

Only explicitly selected files are initially materialized under ignored Hub state. Sources remain external maintenance authorities; the Hub does not vendor whole repositories into its public tree. Frozen copies are checked before use. Where a native installer discovers an entire directory, the adapter must also reject unexpected runtime files: checking only the listed files would otherwise permit an additional unreviewed Skill to be installed.

## pstack: complete source and generation chain

### Original upstream components

The selected port's `tools/upstream.json` declares three inputs from [cursor/plugins](https://github.com/cursor/plugins):

| Original component | Upstream path | Declared immutable pin | Local destination in the port |
| --- | --- | --- | --- |
| Lauren Tan's pstack | `pstack` | `7b353f78f6ec193bdbe48ed8059444eb09b6878e` | `plugins/pstack` |
| Cursor Team Kit | `cursor-team-kit/skills` | `e46364b8be46000b7df0f260550cd712afbb8d36` | Selected entries under `plugins/pstack/skills` |
| thermos | `thermos` | `118e73b0e196e4d49d5aade7ce6dd8985a621f68` | Selected entries under `plugins/pstack` |

The same file declares exclusions; an excluded upstream directory is not an accidentally missing runtime dependency. Examples include Cursor-only plugin metadata, original assets and automations, and the replaced upstream worktree-audit shell script. Preserve the actual exclusion list when reviewing an update.

These original pins were first read from the selected port's source declaration. A later primary-source audit queried GitHub's Git API for all three exact commits and their complete, non-truncated tree listings, then fetched eight original license/entry files and verified each Git blob hash against its tree. The selected pstack tree has 172 blobs, Cursor Team Kit 29 and thermos 10. Read original files include all three component licenses, pstack's README, `poteto-mode` and `how`, Team Kit's `deslop`, and thermos's entry Skill. This independently establishes the pins, original component paths, MIT attribution and selected original workflow contracts. It is not a semantic comparison of every original blob against the port. The immutable source lock's initial `evidence_limit` records the earlier retrieval limitation; this supplementary audit is recorded in the [dated evidence](../evidence/optional-integrations-2026-10-25.md) without changing the already-tested input selection or receipt identity.

The opening pstack row in `NOTICE.md` still links to an older `e46364b` reference; it is a historical attribution link, not the current synchronization pin. The original `how` entry uses Cursor Task dispatch and a `pstack-models.mdc` rule; the port provides its own role defaults and `pstack-models.md` policy, while its Codex mapping explicitly translates to ad-hoc `spawn_agent`. Keeping those differences explicit is necessary to avoid installing a Cursor policy as if it were the Codex runtime contract.

### Port and local fork

The translation and host adaptation are maintained in [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude). The selected [public port commit](https://github.com/michael-denyer/pstack-claude/commit/356c6e0f978df729eb16f227d795f34d221c5aad) is `356c6e0f978df729eb16f227d795f34d221c5aad`, with parent `4ebb588f072fc9bb128f12ccac26153f77badc57`. That immutable commit was independently opened during source verification.

The local fork's recorded origin is [TeFuirnever/pstack-agent-harness](https://github.com/TeFuirnever/pstack-agent-harness). Its selected HEAD is the same port commit, and the selected source was clean. No additional local policy delta is claimed for this pin. The local repository name therefore does not imply a separately developed implementation at this version.

The port explicitly maintains differences from Cursor. Its locked `tools/forks.json` contains 47 pstack entries and one thermos entry, classified as `policy` or `port-feature`. Each entry identifies its reason, introduction version and upstream status. Examples include review-gate preservation, worktree isolation, merge-ready versus merge authority, host-specific tool translation, and the abandoned-agent replacement policy. These are declared behavioral differences, not evidence that one workflow is faster or better.

### Generation and synchronization

The source path is reproducible through the port's own tooling:

1. `tools/upstream.json` selects each original tree and exclusions. `tools/substitutions.json` defines mechanical rewrites and a denylist. `tools/forks.json` declares intentional differences.
2. `tools/sync.mjs` derives the original text for the old and new pins, then performs a three-way reconciliation with the local port. Its dry run is the review entry; the Hub never invokes a source-writing sync automatically.
3. `tools/generate.mjs` stamps `VERSION`, the role policy in `plugins/pstack/models.json`, the public-command table, host mapping preambles, prompt stubs and portable attribution copies into their maintained outputs.
4. `bun tools/generate.mjs --check` rejects generated-file drift, unresolved merge markers and the packaging/link/model inconsistencies covered by the source contract.

During this integration, the selected source's generation check reported **85 generated files current**, and the selected source test suites passed **376 tests** in an isolated complete source copy after installing its frozen development dependencies. The original source repository was not used as a dependency-installation target. These are source and packaging checks; they do not prove live Skill invocation or model routing.

### The installed object

The native Codex marketplace name remains `pstack-claude`, and the plugin identifier remains `pstack@pstack-claude`. Those names are retained from the selected source; they are not sufficient to identify where the installed bytes came from.

The Hub registers the **explicit absolute path of its verified local snapshot**, whose `.agents/plugins/marketplace.json` resolves `pstack` from `./plugins/pstack`. It does not execute the README's online marketplace command. After installation, the adapter compares the native marketplace root and source, the plugin's local source path, and the installed runtime files with the selected snapshot and lock. This prevents a familiar plugin name from concealing installation of a different repository or version.

Codex owns the plugin registration and installed cache. The Hub owns its snapshot and receipt. Extra Skills, hooks or other unlisted source files invalidate the installation check. The source's Bun bootstrap may later generate `skills/poteto-mode/scripts/node_modules` using its frozen production lockfile; the adapter reports that dependency runtime separately and does not treat an install marker as a content audit. Unrecorded generated dependencies are not silently deleted by Hub removal.

## Model router: current identity and installation authority

The selected project calls itself **Agent Orchestration Kit**. Its recorded upstream is [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator), while the old directory name is historical. The selected local continuation's publication at that upstream URL has not been established. Obtain the exact selected local continuation; fetching upstream HEAD is not an equivalent installation source.

The Hub freezes only the existing `azhou-balanced` profile and the native installer/discovery helper. The native installer coordinates `config.toml`, the managed instruction block, six role files and its ownership state; the Hub does not add a second TOML writer or a new scheduler.

The selected files declare Sol `gpt-6.1-sol` with `high` effort for the root default and reviewer; Luna `gpt-6-luna` with `max` effort for explorer, worker, tester and researcher; and the bounded `astra-specialist` role using `gpt-6-astra` with `medium` effort. These are configuration declarations. Live model identity requires actual dispatch and runtime metadata; a model's self-description does not establish it.

Native discovery rejected an isolated attempt that would make the same-named `astra-orchestrator` Skill visible twice, and the native transaction restored the earlier target state. A subsequent isolated installation reused the already visible, identical-hash Skill without writing it and installed nine native-managed files. This records a precise existing-resource boundary: it does not authorize replacing a different user's Skill or assuming an old directory still exists.

pstack and this profile remain separate workflow entries. pstack's Codex mapping dispatches ad hoc agents with its own model policy; Agent Orchestration Kit supplies a workflow Skill and named role configuration. Neither adapter treats their coexistence as a tested chain. A separate configuration home also does not by itself hide globally discoverable Skills; discovery and task-level activation must be checked independently.

## Startup animation: code, assets and host boundaries

The selected launcher implementation has three distinct parts:

| Part | Selected source and artifact path | Evidence boundary |
| --- | --- | --- |
| Standalone player | `Native/App.swift`, web animation files and the hidden `.build/azhou-payload` | Build identity, resource hashes, signature and native player events are distinct from visual approval |
| Codex launch/reuse | Existing native target resolution, launch and activation code | A running target must be reused without restarting an active session; target activation is not model readiness |
| Codex wallpaper helper | `Native/Wallpaper.swift`, `wallpaper/renderer.js`, `wallpaper/wallpaper.css` and generated wallpaper resources | A separate page operation requiring the existing target identity and connection conditions; a completed player does not prove wallpaper application |

The current normal launch path also attempts its existing wallpaper operation. There is no selected pure-launch flag that removes that coupling. Smoke preview, target probe, wallpaper status and explicit restoration are separate operations. Historic `extension/` code and `Native/Extension.swift`, pet generation, other-host adapters and new artwork are outside this selection.

The Hub can build from the frozen source and explicitly supplied existing private assets, inspect the resulting payload, and own an isolated test installation. A successful native build was observed in this integration. Production installation remains blocked at the source contract: the native installer fixes its application destination and writes source-local build/state directories, and it exposes no uninstall operation. The Hub does not bypass those ownership rules by becoming a second production installer. Any necessary destination/state/uninstall change belongs to a separate source-owner task.

### Program and material licenses

| Material | Declared rights and handling |
| --- | --- |
| pstack code, Skills and adapted components | MIT. Retain `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`, `NOTICE-skills.md` and the generated portable notices. |
| pstack's existing tracked icon | Its exact source bytes are locked with the plugin and accompanied by the source repository's license/notice material. It is an existing source asset, not newly generated Azhou artwork. |
| Agent Orchestration Kit selected code/profile | Apache-2.0. Retain the selected `LICENSE` with the local runtime subset; do not replace the license with the Hub's own. |
| Startup-animation program | No `LICENSE`, `NOTICE` or `COPYING` grant was found in the selected source. The integration records metadata and operates on the user's external local source. It does not infer a public source or binary redistribution grant. |
| Startup-animation private art and derived bundles | The four required existing private inputs are supplied explicitly at runtime. Their bytes, private hashes and generated packages stay in ignored local state. They are not added to the public source lock or repository. |

The four private input roles are the working character image, scene data, wallpaper image and application-icon source. A build must bind the actual packaged inputs to the reviewed build plan. Keeping files out of Git and validating their hashes addresses packaging provenance; it does not constitute visual review or a new redistribution permission.

## Updating to another fixed version

Updates are deliberate source selections, not automatic tracking of a branch or a repository name.

1. **Resolve the actual source again.** Read applicable source rules, current name, remotes, Git HEAD, selected-file changes, entry points and license material. Preserve concurrent work. Source changes belong to the source owner's separate workflow.
2. **Review the runtime boundary.** Check newly referenced files, native command changes, configuration ownership, model policy and generated outputs. A matching version string is insufficient. For pstack, review all three original pins and the declared fork/synchronization changes as well as the port commit.
3. **Prepare a complete immutable candidate.** Prefer committed source bytes. If a working-tree selection is necessary, preserve that exact selected byte set and label it `worktree`; never describe the base commit alone as the candidate. Missing selected bytes remain a blocker.
4. **Renew the lock from evidence.** Keep an explicit reviewed file list. For a commit pin, derive hashes and executable intent from the selected Git blobs and modes and verify the checkout against them. Update commit, hashes, attribution and necessary contract notes together. Never replace a failed digest solely to silence the verifier.
5. **Validate outside the source checkout.** Run the relevant native/source checks with the candidate's frozen dependencies, the Hub gate `python scripts/verify.py`, and targeted invalid-input checks. Build private-art outputs only in ignored local state. Keep installation, discovery, invocation and behavior evidence distinct.
6. **Plan the exact target change.** Existing target ownership and installed-content checks must pass. Keep the former lock and recoverable installation state until the new target has passed the applicable native checks. The current pstack adapter does not silently migrate a receipt between source locks; complete the owned old-version removal or select a separate target before installing another lock. Do not clean an unowned or modified cache to force an update.
7. **Review the resulting support claim.** Update both public language entries and the support matrix only for the surfaces actually verified. Role configuration does not establish cost or quality benefits; player logs do not establish wallpaper success or visual quality. Keep unsupported production installation and other-host work explicit.

The public repository stores the source locks, adapters, tests and this maintenance record. Machine-specific paths, credentials, raw transcripts, private artwork, build outputs and native operation logs belong only to the local verification record. A receipt digest detects accidental changes; it is not a cryptographic signature or independent identity proof.

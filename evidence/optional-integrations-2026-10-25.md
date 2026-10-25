# Optional integrations: bounded acceptance, 2026-10-25

## Scope and selected inputs

This is an implementation and runtime receipt for three opt-in Hub checkout entries. It does not replace the existing canonical Skill receipts, certify every upstream workflow, or claim model quality, speed, cost, backend identity or cross-host animation support.

The task began on clean Hub `main` at `3d49cb511d0a2174c0f521fcb140fd29363da2fe`, using a verified Treehouse lease on `codex/hub-three-integrations-20261025`. The original checkout later advanced independently to `d47bc3caaabbbde144faeea0602a3616eb5e2fee` (README hero refresh); that work was preserved. The task receipt retains the actual lease path/identity and source status observations. No source repository was reset, cleaned, committed or used as a dependency-installation target.

| Source | Selected identity and input boundary | Current qualification |
|---|---|---|
| pstack-agent-harness | `356c6e0f978df729eb16f227d795f34d221c5aad`, version `0.9.102`; 239 locked files, including 224 plugin runtime files | Clean selected source; same commit independently verified at the port upstream. A later primary-source audit independently verified all three original Cursor commits, complete tree listings and eight selected original license/entry blobs. It did not compare every original blob semantically with the port. |
| Agent Orchestration Kit | `4d1a2081f96cdab8a9ea0fe3d357312471546dcc`; 13 selected files for `azhou-balanced` | Clean selected source. The old `codex-astra-luna-orchestrator` local path was absent, not an existing compatibility symlink. Publication of this continuation commit at the recorded origin is unproved. |
| codex-startup-animation | `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` plus 22 exact worktree hashes; runtime `0.7.0` build `7` | Dirty source selection, deliberately not reduced to the base commit. The first drift observation found five changed selected files; the final source observation found ten. The old frozen snapshot was retained, new operations against drifting live inputs rejected, and the other session's changes preserved. |

The first animation drift observation names `Native/Wallpaper.swift`, `Native/WallpaperValidationTests.swift`, `tools/build-macos.sh`, `tools/verify-artifacts.py` and `wallpaper/preview.html`, with old/new hashes and timestamps in the private record. New source bytes were not substituted into the acceptance build. Cleanup used the old snapshot's verified validator and registry helper.

At `2026-10-25T15:53:34Z`, the final read-only source observation also found selected-file drift in `AGENTS.md`, `README.md`, `tools/test-wallpaper.mjs`, `wallpaper/renderer.js` and `wallpaper/wallpaper.css`: ten selected files differed in total. `final-source-status.json` preserves that timestamped observation, full source Git status and per-file hashes. The source may continue changing independently; this record does not refresh the selected lock or claim a later source state. pstack and Agent Orchestration Kit were still clean at their selected commits with all locked inputs matching.

Runtime observed: macOS `27.0.1` arm64, Python `3.14.7`, Bun `1.3.14`, Node `24.15.0`, Swift `6.4`. The selected native CLI was the `com.openai.codex` App's embedded `0.164.0-alpha.11.1`; App version `26.1021.31345`, build `21828`. PATH resolved a distinct CLI `0.160.1`, which was not selected.

## Requirement → implementation → evidence

Raw records are kept on the task machine under the leased worktree's ignored `.azhou/hub/integration-evidence/20261025/`. Names in this table refer to that directory. They include private paths and transcripts and are not public repository files. The hash index below permits a local reviewer to identify the exact records.

| Requirement | Implementation location | Verification method | Evidence | Conclusion |
|---|---|---|---|---|
| Existing Skills remain independently installable | Existing `skills/`, Foundation commands; additive dispatch in `scripts/azhou_hub.py` | Baseline and final unmodified `scripts/verify.py` gate; targeted Foundation tests | `baseline-hub-verify.log`, `common-foundation-tests.log`, `final-hub-verify.log` | Baseline: 503 tests and all seven gate stages passed. Final result is recorded in the gate section below. No canonical Skill package was changed. |
| Three separate, opt-in entries | `scripts/azhou_integrations.py`, `integrations/*/source-lock.json` | Catalog/help, explicit plans, no automatic enable path in `setup` | CLI smoke in final verification record | Implemented as a fixed set of three adapters, not a general registry or scheduler. |
| Exact source provenance | `scripts/integration_common.py`, [provenance](../docs/integration-provenance.md) | Commit/blob/hash/mode checks before and after freezing; preserved source status | `task.json`, `animation-concurrent-source-change.json`; three public locks | Commit and selected worktree inputs distinguished. Existing historical reports used only as locators. |
| pstack installs the intended local fork | `scripts/integration_pstack.py` | Native local marketplace add, plugin add; exact marketplace/root/source and 224-file runtime comparison | `pstack-wrapper-1-apply.json`, `pstack-wrapper-2-doctor.json` | Native `pstack@pstack-claude` `0.9.102` resolves to this run's local snapshot, not the README's online upstream command. |
| pstack discovery and invocation | Native plugin plus installed shared Skills/mapping | `skills/list`; real read-only `pstack:how` task on a two-line function | `pstack-skills-discovery.json`, `pstack-real-run.jsonl`, `pstack-rollout-evidence.json` | 65 enabled `pstack:*` Skills discovered from the selected cache. Root and child read installed Skill/mapping/template paths; one ad-hoc child completed the explanation. |
| pstack lifecycle and configuration preservation | Native Codex plugin owner plus Hub receipt | Repeated apply, post-run doctor, native remove/list; separate install/remove over existing model/comment/instructions | `pstack-wrapper-4-apply.json`, `pstack-native-lifecycle.json` | Repeat reports `changed: false`; native lists empty after removal; initial unrelated configuration returns exactly and instructions remain unchanged. |
| Router native installation and discovery | `scripts/integration_model_router.py` delegating fixed native installer | Staged native validation; config/read; named-role tool schema; Skill uniqueness; instruction block | `model-router-reuse-apply.json` | Nine changed files installed in the isolated target. All six roles and root settings discovered; pre-existing identical user Skill reused read-only. |
| Router real dispatch | Existing `astra-orchestrator` and native roles | Real bounded sum task; inspect spawn calls and child session/turn metadata | `router-real-run.jsonl`, `router-rollout-evidence.json` | Explorer and reviewer executed separately; available runtime aliases/effort match the role configuration. Details below. |
| Router rollback, repeat and exit | Native apply/restore and Hub transaction ownership | Duplicate-Skill rejection/rollback; repeat install; verify; exact restore; user Skill hash/mode/mtime comparison | `model-router-discovery-failure.json`, `model-router-lifecycle.json` | Duplicate candidates correctly failed. Repeat changed zero files. Restore completed and the reused user Skill remained byte/mode/mtime identical. |
| Animation source → inputs → build | `scripts/integration_startup_animation.py`, fixed native build/verifier | Isolated native compile, codesign/product validation, build-input marker and packaged web/resource hashes | `animation-build-plan.json`, `animation-build-apply.json` | Selected `0.7.0` build `7` payload built from the preserved snapshot and four explicit private inputs. Marker/signature are not proof of independently reproducible binaries. |
| Animation installed loading, playback and exit | Hub-owned test `.app`; original native player | Install and repeat; run installed executable with smoke/probe; inspect event source path and WebView frames | `animation-test-install.json`, `animation-test-reinstall.json`, `animation-installed-smoke.json`, `animation-installed-probe.json`, `animation-installed-snapshots.jsonl` | Test installation is current on repeat. Required playback/completion/termination events passed; target identity probe resolved the already-running official App. No cold start or host handoff was performed. |
| Animation uninstall has exact ownership | Test receipt, frozen validator, fixed registry helper | Observe auto-registration; exact-path unregister; compare complete project-ID URL sets before/after; remove owned bundle | `animation-test-uninstall-plan.json`, `animation-test-uninstall.json` | Test app and its own registration removed; existing production launcher registration retained. No live source changes undone or production package rewritten. |
| Checks reject incorrect inputs | Four focused `tests/test_integration_*.py` suites; relevant upstream checks | Temporary missing/tampered/conflicting inputs, native failure injection, drifted material and unowned transactions | Final unit-test gate; concrete failures retained in native discovery/source-change records | Negative controls described below; no checks were removed to obtain a pass. |

## Model execution evidence

The router task read `values: 2, 3, 5` and `expected sum: 10`. It requested exactly an explorer and a reviewer with fresh contexts and **without** explicit model/effort parameters. Both independently returned the correct sum. The parent rollout records the named `agent_type` calls, and two child rollouts record parent linkage, role and effective model/effort:

| Run | Dispatch | Runtime turn metadata | Proven scope |
|---|---|---|---|
| Router root | Existing `astra-orchestrator` was read from the identical user Skill | `gpt-6.1-sol`, `high` | Root configuration loaded and task executed |
| Router explorer | `agent_type=explorer`, fresh context | `gpt-6-luna`, `max` | Named explorer role dispatched and completed |
| Router reviewer | `agent_type=reviewer`, fresh context | `gpt-6.1-sol`, `high` | Named reviewer role dispatched and completed |
| pstack explainer | No named custom role; explicit `model=gpt-6-luna`, `reasoning_effort=max`, fresh context | `gpt-6-luna`, `max`; no custom agent role | Existing pstack Codex mapping and explicit per-role policy dispatched and completed |

The pstack task explained filtering inactive items, summing active amounts and returning zero for empty input. Its temporary model sheet selected the stated explainer alias/effort. The competing global Skill was disabled for that invocation using native `skills.config`; no user-global file was changed. The automatic pstack hook was not trust-enabled and `session hook: off` was set in that isolated target. This tests explicit pstack invocation, not automatic hook injection.

Neither model self-report nor the CLI's final prose was accepted as model identity. Client session metadata proves the configured/runtime alias and effort available in this build; no independent backend fingerprint was obtained. Worker, tester, researcher and Astra specialist were present in the native schema but not invoked in this bounded acceptance. No performance or quality benchmark was added.

Both real runs reported the pre-existing global Skill traversal-limit warning; the pstack run also reported a model-list refresh timeout. Selected Skill discovery, reads, child creation and completed results were nevertheless observed. The record does not claim complete global Skill scanning or successful refresh of the entire model catalog. Temporary local credential copies used only for these new isolated sessions were removed after the runs; credentials and their contents are not part of this public receipt.

## Animation evidence and remaining holds

The installed smoke run emitted `player-start`, `window-created`, `playback-start`, `animation-complete`, `preview-result` and `player-terminated`. Every relevant event named the isolated installed `.app`; completion was true and failure false. Probe resolved the already-running `com.openai.codex` App and exited. The source preview and a real target launch were not substituted for these installed-player checks.

Four internal WebView images were captured at scheduled 1.4, 3.5, 5.5 and 7.3 seconds. The 1.4 and 5.5 second frames were inspected: the character, layout and title rendered, and the staged text progression differed visibly. This is a limited rendered-output review, not frame-timing, full animation-quality or formal design approval. Captures contain private art and are not published.

The formal material reference was located read-only at the asset library's `assets/characters/azhou-chibi-pet/v1.0.0/images/04-working.png`. Its bytes matched the selected working-character input. Source design locators are `docs/references.md`, `plans/001-vivid-lab-motion.md` and `docs/azhou-vivid-maximized-verification.md`; their earlier approval text is not reused as a current approval. `animation-visual-review.json` records these facts. **Formal visual approval remains pending.** Live wallpaper appearance was not reviewed.

Current normal launch also attempts Codex wallpaper enhancement. This is reflected in the wrapper plan and its separate launcher/wallpaper result fields. The existing user's Codex session was not restarted or modified for this acceptance. Cold launch, warm activation/handoff, real wallpaper apply/status/restore and production installation remain unverified here. Source mocks and 42 pure Swift checks do not establish those behaviors.

Direct execution caused macOS to register the test application even without an explicit registration request. The original production checker detected the extra source-external entry and failed; this failure drove exact-path cleanup and a regression test. Later the live source changed during this task, and cleanup initially refused its changed validator. The final cleanup uses only the selected snapshot, validates ownership again, unregisters only the recorded test path, and proves the production URL remains. [Apple's Launch Services guidance](https://developer.apple.com/forums/thread/725805) treats `lsregister` as a debugging tool, so this result is confined to the observed OS/tool behavior.

Production install/uninstall is a separate source-owner blocker: the native installer hardcodes its destination and source-local build/state, and exposes no uninstall operation. The Hub provides concrete plans but does not become a competing production installer. A source change would need explicit destination/build/state ownership and an exact native uninstall/restore contract; the Hub task did not authorize or perform that change. No public license grant for the animation program was found, and no program/artwork/binary was added to public distribution.

## Source checks and negative controls

| Check | Observed result and limit |
|---|---|
| Hub baseline `python scripts/verify.py --print-summary` | All seven stages passed; 503 existing tests. Targeted Foundation/common/encoding run also passed 83 tests. |
| pstack `bun tools/generate.mjs --check` | 85 generated files current; relevant packaging/link/model/hook validations passed. |
| pstack selected source tests | Direct read-only test attempt failed because development dependency `typebox` was absent. A complete fixed-commit temporary copy installed frozen dependencies, then passed **376 tests across six relevant suites**. No dependency was installed into the source repository. |
| Original Cursor source check | GitHub Git API returned the exact three declared commit objects and non-truncated trees (pstack 172 blobs, Team Kit 29, thermos 10). Eight fetched original license/entry files matched the tree's Git blob IDs. Raw records: `cursor-upstream-check.json`, `cursor-upstream-tree-check.json`, `cursor-original-entrypoints.json`. This supplements the initial immutable lock's earlier retrieval-limit note without changing selected runtime bytes. |
| Router selected source tests | **25 native-installer tests + 6 native-discovery evidence tests passed** in a complete fixed-commit temporary copy. These include mocked native calls and are distinct from the real native results above. |
| Animation source installer regressions | **21 tests passed** using the fixed snapshot; macOS calls are mocked in that suite. |
| Animation Swift validation | Native compile passed; **42 pure validation checks passed**. The tool explicitly excludes real socket, Codex injection and visual checks. |

The Hub tests exercise missing/changed locked files, executable mode, unsafe paths and symlinks; stale plans; existing unrelated configuration; native partial-install failure/resume/removal; wrong native marketplace source; extra installed Skills; source-contained workspaces; malformed/drifting role/config receipts; foreign and tampered restore transactions; missing/private input changes during a build; output-marker drift; missing or wrong-path playback events; wallpaper failure separated from player success; copy failure; running/unowned/modified test apps; system registration non-removal or collateral changes; and live-source drift with safe frozen cleanup. They do not count synthetic fixtures as real host or model evidence.

An independent cross-component review found and led to fixes for pstack's initially incomplete runtime-file set check, source-boundary timing, an overly broad text-only orchestration conflict check, router restore-transaction ownership, animation's player/wallpaper result conflation and post-build private-input binding. Native testing additionally found global Skill duplication and automatic application registration. The original orchestrator conflict rule and source's native uniqueness checks remain active.

## Final repository gate

`python scripts/verify.py --print-summary` passed all seven stages: repository policy, **571 tests**, all three pre-existing benchmark-integrity suites, working-tree whitespace and staged whitespace. The 68 added tests cover only these integration boundaries. No registered gate was removed or weakened. Raw output is `final-hub-verify.log`, with command, return code and SHA-256 in `final-hub-verify.json`. Catalog, `info` and all three component help commands also exited zero (`integration-cli-smoke.json`).

## Selected raw-record hashes

SHA-256 values below identify records in the ignored task evidence directory. These records are not required by the public deterministic gate and contain no data bundled into canonical Skills.

| Record | SHA-256 |
|---|---|
| `pstack-isolated-source-checks.json` | `bea8f8a4195654e53a4cc1b685d425fa1afa136b6907e81b2bfeb9a464496e73` |
| `pstack-wrapper-1-apply.json` | `731de875d0680bfa6866ba9fbc288977d32fd4e6d8ffe2eb5c7087b5d11b2ebc` |
| `pstack-skills-discovery.json` | `050008f17646042c8ae7a3d8ef0999e53884a4c469f43ba9287ddd9d90499500` |
| `pstack-real-run.jsonl` | `33321c6ab890e830808a3c4288d11f22754f1734cbb4a11f1b41a7afd3d55d5e` |
| `pstack-rollout-evidence.json` | `e5f637a010ac83fb8bef154e2f20879df8bf4965fe785209aa16a52041aa7113` |
| `pstack-native-lifecycle.json` | `f00226dfca46ee5b0ecbf8a30452a32a7fe29757665f70331e4753b6e3526af2` |
| `model-router-discovery-failure.json` | `a4f2748ec410092aab2fa499a80cfa714039ae2c72f08a729f8ea612c037c704` |
| `model-router-reuse-apply.json` | `938edd80a723e27046fb1f39e8dfddc92c442afdaa56170ea0980c45427d4a64` |
| `router-real-run.jsonl` | `ea0681ff7edbcc4833a476062557f73088c697255453949e421a68ba99ca487d` |
| `router-rollout-evidence.json` | `3dc8f3a92bb6f850bd98c2640109787878d32cdd76bb87fbaa7ec97bdca63249` |
| `model-router-lifecycle.json` | `27f27a55a6c1c01df0c14a92f5a7676bb53ad6a2e763ef8bdd07cbb0753f39f0` |
| `animation-build-apply.json` | `fb694e86b3b1ca056ee6907aba3c1f90ed216450679441273cb444cb675ea832` |
| `animation-installed-smoke.json` | `b398ac73ad7b81dd83a597bd4562ee0fc8d9c8bfdf7d73f13f321c1fe9d2564d` |
| `animation-installed-probe.json` | `c3d68e72a7087aa1406bdb7a4479a57934062d0715df35233fadbcfb81c508f1` |
| `animation-installed-snapshots.jsonl` | `1af96a4c3a57be8c6001ceff082c14041701c934fb952b393851a4d1218ce7e8` |
| `animation-test-uninstall.json` | `276261310a9d24f4a7abc7936ce960c03d26cc32eba52eb8cb234b9d2c6aa7e9` |
| `animation-concurrent-source-change.json` | `4c295cf33fec37f9ed42c939ef45002248e2090409a9526b6a40337cc2fe5615` |
| `final-source-status.json` | `68c3cc4646299a204f6908f6891c5e84ddf4d51fc9bb1b557fd4a71cd39f5de5` |

For current entry points, exit procedures and fixed-version updates, use the [integration runbook](../docs/integrations.md), [provenance record](../docs/integration-provenance.md) and [support matrix](../docs/support-matrix.md#optional-integrations). The raw evidence, frozen inputs and lease are retained for review; temporary target configurations and the test application were restored or removed as recorded above.

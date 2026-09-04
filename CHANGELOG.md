# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and repository-level [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Completed the Super Caveman Codex lifecycle adapter (spec #115, implementation #116): `codex_adapter.py` now owns one `UserPromptSubmit` registration beside `SessionStart` in the same explicit scope and adds `prompt`/`enable`/`disable`/`status`; `render` and `prompt` delegate to the canonical `claude_adapter` handlers so the capsule builder, mode hierarchy, stop phrases, one-shot routes and persistent defaults stay single-source — the Codex SessionStart capsule becomes the mode-aware canonical capsule (disclosed codex-host-visible change), covered by the existing contract tests plus a new lifecycle suite; live firing stays unclaimed until a trusted real-host receipt exists. Landed via the byte-reuse promotion chain with two isolated response-output-neutral delta reviews and fresh exact-diff approval.
- Added the opt-in zcode lifecycle adapter to `super-caveman` (`scripts/zcode_adapter.py`): two proven events (SessionStart plus UserPromptSubmit) managed in `.zcode/cli/config.json` for one explicit scope, reusing the canonical Claude adapter handlers so the capsule builder, mode hierarchy and session state machine stay single-source; a defensive camelCase-to-snake_case payload bridge, a 15-case deterministic contract test file, a config-registration smoke receipt carrying the verified headless `-p` no-hooks negative, and a re-derived `evidence/zcode-hook-surface-2026-09-04.md` replacing the 2026-09-02 receipt found committed empty. Promotion followed the byte-reuse chain re-bind: the 19-case output set is byte-identical, two isolated delta reviews confirmed response-output neutrality, and the superseded `revision-ed8a4b80` evaluation is re-bound to the new tree digest.
- Added the `relay` mode to `lavish` by merging Spec Relay into it as the single canonical package with two modes: `artifact` remains the unchanged general rich-HTML review loop while `relay` serves the portable handoff packet with embedded `spec-relay.html-state.v1` state, stable `data-review-id`s, feedback disposition, next-owner handoff, optimistic revision guards and `spec-relay.receipt.v1` receipts; `relay_state.py` moved byte-identical into `skills/lavish/scripts/` alongside the Spec Relay reference, machine-stable names (the state schema, `spec-relay.receipt.v1`, the `spec-relay:` CLI error prefix and the pinned `lavish-axi@0.1.47` baseline) are preserved, receipts and the fuzz workflow re-point at the single package, and the canonical package count drops from twelve to eleven.

### Fixed

- Fixed the `llm-wiki` hook-wiring renderer emitting a bare `"*"` matcher: hosts that compile hook matchers as regular expressions (Codex, Claude Code) reject it as invalid ("nothing to repeat"), so `render-hooks` now emits the valid match-all `".*"` and a regression test pins all three event matchers as compilable regular expressions ending at the canonical event name.

### Changed

- Unified the Azhou identity anchor across all canonical packages: every `SKILL.md` now carries the `🦊 阿舟 · <Skill>` identity and motto in its own body, Super Caveman included — its stage-event protocol stays byte-identical in `references/brand-layer.md` and ordinary terse replies still add no lifecycle emoji. `check_skill_brand_contract` enforces identity and motto against `SKILL.md` itself instead of the combined skill+brand surface, a regression test proves identity removal from `SKILL.md` alone fails the gate even when the brand layer retains it, and `docs/skill-standard.md` states the uniform rule without the previous Super Caveman exemption. The Super Caveman package tree digest changes, so the passing evaluation re-binds only through fresh promotion evidence.

### Planned

- First complete cross-harness evidence set.

## [0.5.0] - 2026-09-02

### Added

- Added `eli5`, the dead-simple picture-explainer skill, adapted from `anthropics/claude-plugins-community` at immutable commit `794af9e63d07fad17087dcab61f21f44cb48effd` under Apache-2.0. The upstream behavior sentence is retained verbatim with a hash-locked provenance check, and the local layer adds the topic boundary, self-contained artifact contract, Azhou brand protocol and stable receipt.
- Added `autoresearch`, an Azhou-authored wrapper that drives automatic nanochat training experiments inside a user-owned checkout of `karpathy/autoresearch` pinned at `228791fb499afffb54b46200aca536f79142f117`. The upstream publishes no license, so zero upstream bytes are vendored; setup fails closed on GPU, uv and pin checks, and unattended GPU runs keep an explicit authorization checkpoint.
- Added bounded deterministic fuzzing for the Spec Relay state parser: a stdlib-only seeded mutation harness (`fuzz_relay_state.py`), a time-boxed SHA-pinned `fuzz.yml` CI workflow, five real parser crash classes found and fixed with fail-before/pass-after regression tests, and ~450k clean inputs across seeds post-fix.
- Completed the zcode host evidence column: dated receipts for canonical SKILL.md package load (10/10 discovery), the live zcode hook surface (SessionStart/PreToolUse confirmed, PreCompact/SessionEnd absent in 0.16.5), Repo Pedant manual invocation, Lavish and Spec Relay review loops, Super Caveman compact delegation via a real child subagent session, and the receipt-backed Super Caveman zcode session-statistics projection.
- Recorded the honest Super Caveman zcode behavior attempt-1 failure (9/19 cases, 25/44 criteria, seven timeout-bound at the pinned 120s/case cap) in both the evidence receipt and the support matrix, with the binding evaluation unchanged; documented the completed-and-smoke-receipted zcode lifecycle adapter as landing-blocked by the version-pinned skill-tree binding gate.

## [0.4.1] - 2026-09-02

### Fixed

- Landed the Excalidraw Chromium preflight completion that the 0.4.0 notes described ahead of its code: the read-only `check-playwright-runtime.py` checker, its regression test, and the renderer/setup/installation wiring now ship inside the tag.

## [0.4.0] - 2026-09-01

### Added

- Receipt-backed the remaining conditional support-matrix cells on locally-available hosts: LLM Wiki stdio MCP transport (Claude + zcode real server calls), LLM Wiki lifecycle adapter wiring (Claude full; zcode session-start live with pre-compact/session-end honestly blocked on zcode 0.16.5 hook availability), Repo Pedant history parsers against real Claude/zcode sessions, and Super Caveman zcode host counters; each cell now states exactly what its dated evidence receipt proves.
- Added a read-only Excalidraw Playwright Chromium preflight so setup installs the locked browser only when the checker reports it missing, while renderer errors point back to the same gate.

## [0.3.0] - 2026-08-31

### Added

- Added `lavish`, the general rich-HTML artifact review loop, imported as a byte-locked baseline from `kunchenguid/lavish-axi` at immutable commit `232972beba9e0e4e75682c98f2aeb2cf01532122`. The locked `lavish-axi@0.1.47` baseline stays identical to Spec Relay, the retained MIT license copy and provenance carry the vendored-material law, and local review, export portability and third-party sharing keep separate authorization boundaries.
- Added the opt-in `super-caveman` Claude lifecycle adapter: the `UserPromptSubmit` state machine (#38) and the `SessionStart` slice (#37) with the exact precedence hierarchy from the parent spec, stop controls, status routes and one-shot commands, gated by a 19-case lifecycle benchmark plus a real-host attempt-1 receipt (Claude Code CLI 2.1.239, redacted) whose findings and limitations - slash-trigger delivery, headless compact and headless trust - are recorded rather than claimed (#40).
- Added the documentation-backed Codex lifecycle adapter feasibility decision for Super Caveman, explicit that it implies no cross-host parity.

## [0.2.0] - 2026-08-31

### Added

- Added `spec-relay`, an enhanced and provenance-tracked derivative of Lavish Editor that packages specs, complete comments, selected-text annotations, feedback disposition and next-owner state inside one portable HTML relay packet; standalone export and third-party sharing retain separate authorization boundaries.
- Added Spec Relay feedback and handoff updates, packet identity, optimistic revision guards, exact visible-ledger validation and a responsive review ledger.
- Added Repo Pedant-aligned Azhou stage anchors, emoji discipline and receipts for Spec Relay while keeping transferable HTML brand-neutral.
- Added a Spec Relay reference demo with the invocation, expected outputs, deterministic checks and skill-standard evidence receipts for one real run.

### Changed

- Ignored harness-local agent state directories (`.claude/`, `.local/`, `.treehouse/`) so guarded fleet and clone refreshes stop skipping a local checkout.
- Raised the Treehouse worktree pool capacity from 4 to 6, widening the repository policy bound to match.

## [0.1.0] - 2026-08-28

### Added

- <code>repo-pedant</code>, a strict documented superset of <code>neat-freak</code> with exhaustive knowledge inventory, project-memory proof, fixed stage protocol, advisory lifecycle hooks and bounded cross-runtime evolution.
- <code>excalidraw-diagram</code>, an editable-scene workflow with offline official rendering, converters, fonts, component libraries, deterministic checks and honest visual-review gates.
- Repository-level unit tests, isolated behavior benchmarks and one-command verification.
- English/Chinese product entry, installation/support/architecture/release docs, community governance and security reporting.
- GitHub issue forms, PR template, CODEOWNERS, Dependabot, pinned-SHA CI, CodeQL, dependency review, Scorecard and manual draft-release automation.
- Explicit third-party notices and an independently re-expressed Excalidraw runtime after a no-license prior-art audit.
- Unified project-local Azhou runtime state under `.azhou/`: skill state uses `.azhou/<canonical-name>/`, Hub lifecycle receipts use `.azhou/hub/receipts/`, and explicit plan-bound migrations preserve recognized legacy sources without fallback reads or dual writes.
- Added `llm-wiki`, a neutral private Markdown knowledge base with one canonical store, seven-tool stdio MCP, explicit lifecycle/trigger/command adapters, reviewed project context, atomic source-preserving migration, Azhou stage anchors, receipt v2 and deterministic production gates.
- Added harness-neutral `azhou-info`, `azhou-doctor`, `azhou-setup`, and `azhou-verify` Agent Skills that delegate to the repository Foundation CLI without host-specific runtime copies.
- Added a zero-dependency foundation CLI with `info`, `version`, read-only `doctor`, dry-run-first scoped `setup`, stable JSON/exit codes and delegation to the canonical repository verifier.
- Added opt-in, single-skill checkout lifecycle receipts with fail-closed `repair`, same-target `migrate`, `uninstall`, and read-only Treehouse lease diagnostics.
- Added a repository-enforced Treehouse worktree policy with durable task leases, identity-conditioned return, dry-run-first cleanup, a bounded Git pool and a documented migration/recovery path.
- Added copyable input/output demos for the two task skills and a live OpenSSF Scorecard badge.
- Added a redacted public-source discovery and clean-install receipt for the two original task skills; this is not six-package or cross-harness evidence.
- Added Azhou Scenes effect previews for `repo-pedant`, `excalidraw-diagram`, and `super-caveman`; the Super Caveman README preview keeps formal colour promotion and final human identity/hand approval explicit checkpoints.
- Added `super-caveman`: the original Caveman terse-mode core enhanced with six companion routes, the complete pinned `i-have-adhd` output-behavior contract, guarded compression, and a restrained evidence-bound Azhou stage protocol, including 8 route fixtures, retained historical 14-case evidence, a current 19/19-case and 44/44-criterion bounded behavior run, and a 3/3 independent paired-judge candidate result with zero high-risk regressions.

### Fixed

- Unified Excalidraw Diagram on one public motto and normalized new Repo Pedant receipt headers to the canonical display name while preserving prior branded and legacy headers as read compatibility.
- Split reproducible public repository verification from explicit maintainer promotion-evidence authentication, while keeping exact-diff replay mandatory in both modes and the Git-external Super Caveman approval gate fail-closed for releases.
- Upgraded managed lifecycle receipts to v2 filesystem identities, added a genuine v1 byte-digest upgrade path for link and copy installs, rejected same-mode migration of drifted artifacts, prevented byte-identical replacement deletion, and made package digests executable-aware.
- Added real managed lifecycle regression coverage for `repo-pedant`, `super-caveman`, and `excalidraw-diagram`.
- Clarified that the four Foundation Skills are independently installable adapters, not standalone CLI copies, and added a bilingual install/command map guarded by a regression test.
- Extended `info.v1` additively with the preferred `primary_commands` field while keeping the original `commands` field and schema discriminator stable.
- Corrected the Excalidraw official-export example to use its positional CLI, locked `uv` environment and post-export style gate.
- Prevented package discovery from exposing the upstream `neat-freak` regression snapshot as a third installable skill.

### Security

- Added non-echoing repository checks for high-confidence credential shapes.
- History observers and hooks cannot write live skills.
- Neutralized the upstream public Firebase client identifier in the offline Excalidraw bundle.
- Raw runtime histories and private evidence remain outside Git.
- Scoped CodeQL write permissions to the analysis job.
- Secret scanning/push protection, dependency alerts and private vulnerability reporting are repository requirements.

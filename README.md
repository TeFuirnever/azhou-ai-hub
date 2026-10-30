<div align="center">

# 🦊 Azhou AI Hub

**Agent skills that stay useful after the demo.**

Small enough to edit. Strict enough to verify. Neutral enough to run across harnesses.

[简体中文](README.zh-CN.md) · [Install](docs/installation.md) · [Support matrix](docs/support-matrix.md) · [Contributing](CONTRIBUTING.md)

[![CI](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml)
[![CodeQL](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/codeql.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f7d4a.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/TeFuirnever/azhou-ai-hub?display_name=tag&sort=semver)](https://github.com/TeFuirnever/azhou-ai-hub/releases)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/TeFuirnever/azhou-ai-hub/badge)](https://securityscorecards.dev/viewer/?uri=github.com/TeFuirnever/azhou-ai-hub)

<img src="assets/github/readme-hero.png" alt="Azhou AI Hub hero: the Azhou fox beside the claims — 14 installable skill packages, one deterministic repository gate, human-approved evolution only." width="100%" />


https://github.com/user-attachments/assets/38a350d6-ddb3-40cf-a878-9ee5005ce993

</div>

> 🦊 Hero generated under the `github_readme_image_16_9` profile contract (1280×720, lossless PNG): the Azhou fox (canonical reference) stamping an approval seal, rendered by the local Azhou imagegen pipeline (Qwen-Image-2.1 edit, seed 7 of the 2026-10-25 batch) with the claim lines overlaid deterministically. Reviewed at 120/240/360 px; maintainer (IP owner) visual approval recorded 2026-10-25.

Product direction: [Myself first, community-ready](docs/principles.md), with human-facing Skills, harness-respecting UI personalization and quality-constrained Orchestrator Kit efficiency. See the [roadmap](docs/roadmap.md) for planned work; principles do not extend support or change existing licenses.

Most skill repositories stop at prompts. Azhou AI Hub treats each skill as a product: a precise trigger, a portable runtime package, reproducible setup, deterministic gates, honest evaluation, provenance, and a human-controlled evolution path.

No universal framework. No model-specific copy of the same skill. No benchmark answer hidden inside the runtime package.

## Installation paths

Install one package per command:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill super-excalidraw-diagram
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-info
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-doctor
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-setup
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-verify
npx skills add TeFuirnever/azhou-ai-hub --skill super-llm-wiki
npx skills add TeFuirnever/azhou-ai-hub --skill super-lavish
npx skills add TeFuirnever/azhou-ai-hub --skill super-eli5
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou
npx skills add TeFuirnever/azhou-ai-hub --skill super-arch-doc
npx skills add TeFuirnever/azhou-ai-hub --skill super-session-insights
npx skills add TeFuirnever/azhou-ai-hub --skill super-asd-ste100
npx skills add TeFuirnever/azhou-ai-hub --skill super-archify
~~~

Package-manager installs resolve the mutable default branch; [verify what you installed](docs/installation.md#verify-what-you-installed) against a published tag, or use the receipt-backed checkout-assisted path.

These commands are the documented package-manager path; completion time and host discovery are harness-dependent and are not promised here.

Choose one installation method. Do not stack a package-manager install, a checkout-managed install, a manual copy, and a development symlink under the same canonical skill name. The four `azhou-*` packages make their `SKILL.md` workflow discoverable; they do not bundle the Foundation CLI and still require an explicit local checkout. See the [installation guide](docs/installation.md) for the complete paths and dependencies.

When a host must install without network access, the [offline recovery](docs/installation.md#offline-recovery) runbook rebuilds the uv, npm and Playwright browser caches from local copies.

## Inspect, set up, or verify a checkout

Four portable Azhou Agent Skills expose the checkout workflow without duplicating its mechanics. Invoke them through the active harness's native Skill surface while working in an Azhou AI Hub checkout, or provide that checkout path explicitly. Each adapter delegates to the checkout's zero-dependency Foundation CLI:

| Agent Skill | CLI authority | Change boundary |
|---|---|---|
| `super-azhou-info` | `info`, `version` | Read-only project, runtime, Git revision and dirty-state facts. |
| `super-azhou-doctor` | `doctor` | Read-only repository, explicit install-target, optional Treehouse lease and host stale-install migration diagnostics. |
| `super-azhou-setup` | `setup`, `repair`, `migrate`, `uninstall` | Dry-run first; only an exact reviewed plan with `--apply` may mutate its explicit target. |
| `super-azhou-verify` | `verify` | Runs the reproducible public repository-integrity gate. |

~~~bash
python scripts/azhou_hub.py info --json
python scripts/azhou_hub.py version --json
python scripts/azhou_hub.py doctor --json
python scripts/azhou_hub.py setup --skill super-repo-pedant --target /absolute/path/to/harness/skills --json
python scripts/azhou_hub.py verify
~~~

`setup`, `repair`, `migrate`, and `uninstall` stay read-only until `--apply` is present. Setup is idempotent and refuses to overwrite a different installation; when a destination symlink already resolves to identical canonical package content from another checkout, the dry-run reports `conflict-same-source` and exits `3` instead of failing, while `--apply` still refuses. Receipt-owned lifecycle commands require the same explicit target and independently verify the canonical source and installed identity; they never force drifted content, cross harness roots, install hooks, rewrite harness configuration, contact a registry or update the CLI. The packages are shared across harnesses, but discovery, invocation, permissions and optional integrations remain host-specific; see the [support matrix](docs/support-matrix.md) and [Foundation CLI contract](docs/foundations.md).

For setup, review the deterministic `planId` from the dry-run, then pass the exact value with `--apply --plan-id <reviewed-planId>`; source, target, mode, or pre-apply state changes invalidate the apply.

## Optional integrations

Three complete projects live under `packages/`; they keep their own native layouts, toolchains and provenance. The fourteen canonical Skills under `skills/` keep their existing independent install and invocation contracts. These projects are not Skills, and installing a Hub Skill does not enable any integration.

| Entry | Complete project package | Current boundary |
|---|---|---|
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | Optional native Codex plugin installation into an explicit target; review hook trust separately. |
| `model-router` | [Agent Orchestration Kit](packages/agent-orchestration-kit/README.md) | Optional native Codex profile installation; keep one workflow owner per task. |
| `agent-skin` | [Azhou AI Lab for Codex](packages/agent-skin/README.md) | Codex-only package identity. The localized app label is `阿舟 AI 实验室 for Codex` / `Azhou AI Lab for Codex`, while the native entry remains `~/Applications/阿舟 AI 实验室.app`; an owned old-name entry is retired only after the new entry is verified. The candidate uses an Azhou bot appearance entry and Chinese/English UI that follows the official application's language and theme, with no separate preferences. Theme & Appearance groups identity, startup, background and inherited status in one page, backed by `theme-config.json`; build-owned identity changes require rebuild/install. Build 23 separates the Codex display label from the stable installation basename, and Finder localization follows the macOS language; maintenance messages follow the system language. Build 24 keeps the Appearance fallback hidden until a host control is visible and hit-testable; while Home navigation is unavailable, the fallback avoids the composer and returns beneath Your dot when navigation appears. The 12-second animation and existing settings transactions remain. The Hub adapter keeps status read-only; installation ownership and real-host acceptance require their own verification. No program redistribution grant is recorded. |

~~~bash
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
python scripts/azhou_hub.py integrations model-router --help
python scripts/azhou_hub.py integrations agent-skin --help
~~~

Agent Skin's native maintenance helper also provides an explicit [wallpaper retry](packages/agent-skin/README.md#wallpaper-recovery): it reuses the completed controller's last image and strength without replaying the animation. Status remains read-only and reports bounded failure codes; unsupported or foreign controllers are not replaced.

The current local candidate adds keyboard isolation for settings, theme-consistent background previews, actionable image errors, and an in-page retry for startup wallpaper failures. Image dimensions are checked before decoding when the bounded header can be parsed; final decoding and size validation still apply. Real-host, accessibility, and user acceptance remain separate from automated checks.

`python scripts/azhou_hub.py integrations ...` remains the operational entry. Each command defaults to its in-repository package; optional `--source` only asserts that canonical package path. Plans fingerprint current `runtime_paths` inputs and stage private snapshots and recovery receipts under ignored `.azhou/hub/` state. See the [integration runbook](docs/integrations.md), [provenance](docs/integration-provenance.md) and [support matrix](docs/support-matrix.md#optional-integrations). The two orchestration packages also ship a task-ownership contract — ordinary tasks keep the Kit's named roles, while a user-selected pstack workflow owns that task and dispatches explicit model and effort with no named role — with a bounded dispatch receipt on an isolated Codex home ([evidence](evidence/pstack-orchestrator-dispatch-2026-10-26.md)). Both packages can share one controlled Codex home: one shared verdict (native registration plus the model sheet's `session hook: off` line) decides compatibility for the Hub and Kit entries alike, verified both as a deterministic install lifecycle and natively on the recorded Codex client — both install orders, repeats, the armed-target conversion and both removal orders in throwaway homes ([native acceptance](evidence/pstack-orchestrator-native-acceptance-2026-10-26.md)), and the five task-boundary behaviors — the ordinary-task default, an owner held across a same-task follow-up, default rules after a finished pstack task, a mid-task switch draining in-flight children, and a rejected explicit model blocking with a reported reason — were observed live in one throwaway home ([live sessions](evidence/pstack-orchestrator-live-sessions-2026-10-27.md)). Every entry also has an owned exit — Hub `uninstall-plan`/`uninstall` and Kit `--uninstall` — that restores only its recorded scope, keeps the other module and later user edits, and reports differences instead of overwriting them. Existing installations — a Kit beside shared pstack Skills, a native plugin, or locally modified shared Skills — are reviewed first by the read-only `transition-plan` entry: it names each state's actual source, content differences, owner and recovery basis, offers an applicable conversion only when the native registry resolves the registration back to the Hub receipt's snapshot, never adopts unknown installations by name or byte-identical content, and by itself authorizes no application to a main environment.

Install pstack from this Hub's maintained package for Codex, Claude Code, MiMo Code (`mimo`) or zcode. Its [installation instructions](packages/pstack-agent-harness/README.md#install) use local package sources; upstream links remain attribution and source-update references. For Codex, `--codex-home` selects the exact configuration to receive the plugin. A custom home requires launching Codex with that `CODEX_HOME`; it does not activate the plugin in the default desktop configuration.

The original startup-animation source has no recorded open-source license grant. The separately attributed Dream image parser is MIT-licensed, but that grant does not cover the rest of Agent Skin. The Hub root license does not cover either original package source; do not publish the combined source or binaries until redistribution permission is clarified. Private artwork stays outside Git. The 2026-10-25 acceptance report is historical evidence for its inspected inputs and host. The 2026-10-26 local handoff built from the then-canonical `codex-startup-animation` source; current installed App and Pet ownership still names that retained source. This ticket does not transfer either installation. The new adapter contract is covered with synthetic events only; Codex was not restarted, so cold host launch, wallpaper application, Pet selection/playback and formal visual approval remain unverified. See the [local handoff record](evidence/optional-integrations-local-handoff-2026-10-26.md).

The retained `codex-startup-animation` source remains the owner of the installed Codex Pet and its maintenance state. The Agent Skin package contains copied source files but does not assume Pet ownership; keep the legacy root until an explicitly reviewed App and Pet handoff is complete. See [Pet maintenance](docs/integrations.md#pet-maintenance-after-the-import). Installed-byte checks do not prove host selection or playback.

## Skills

| Skill | Real job | Verification basis |
|---|---|---|
| [Azhou Info](skills/super-azhou-info/SKILL.md) | Report checkout, runtime, support and provable Git revision facts without manufacturing release state. | Delegates to stable `info` / `version` JSON contracts; read-only package and repository-policy checks. |
| [Azhou Doctor](skills/super-azhou-doctor/SKILL.md) | Diagnose repository, explicit install target, optional Treehouse lease and host stale-install migration health without mutation. | Read-only doctor contract, real Treehouse 2.3.0 smoke, fail-closed target checks and the read-only host migration probe. |
| [Azhou Setup](skills/super-azhou-setup/SKILL.md) | Plan and explicitly apply checkout-assisted install or receipt-owned lifecycle operations. | Dry-run-first setup, mutation lock, identity guards, rollback and receipt regressions. |
| [Azhou Verify](skills/super-azhou-verify/SKILL.md) | Run the public full-repository integrity gate. | Delegates to repository policy, unit, benchmark-integrity and whitespace gates. |
| [Super Repo Pedant](skills/super-repo-pedant/SKILL.md) | At explicit task close, reconcile docs, project rules, handoff state and project-bound memory against current code. | 28/28 <code>neat-freak</code> capabilities accounted for against the upstream v3.0.0 reference baseline (<code>322346de</code>, snapshot hash-locked; audited 2026-10-07, re-baselined 2026-10-18 with the absorption pin <code>bab17831</code> retained as lineage); 3 registered behavior cases; fixed execution protocol and inventory proof. |
| [Excalidraw Diagram](skills/super-excalidraw-diagram/SKILL.md) | Create or edit an editable scene, render the real artifact, inspect it, and deliver CJK-safe SVG/PNG when requested. | 5 frozen benchmark cases; deterministic style, scene, overlap and same-DOM gates. A sandbox-blocked preview degrades to geometry and hash verification and is reported as an explicit hold, never a silent skip. Checked-in reference output proves wiring only, not model quality. |
| [Super LLM Wiki](skills/super-llm-wiki/SKILL.md) | Build a private, persistent Markdown knowledge base that agents can ingest, search, read and lint across sessions. | Canonical local store, eight MCP tools with decision lifecycle, atomic migration, privacy defaults and focused deterministic contract tests. |
| [Super Lavish](skills/super-lavish/SKILL.md) | Turn complex or visual agent responses into rich, reviewable HTML artifacts users can annotate and answer through the Lavish Editor CLI; in Spec Relay relay mode, package a PRD, RFC, design spec or technical plan with comments, selected-text annotations, disposition and next-owner state inside one portable HTML file. | Upstream baseline hash-locked for reproducibility at the locked CLI <code>0.1.89</code>, with the documented local relay layer on top; provenance records the immutable upstream commit and the reproducible source check. Relay mode embeds <code>spec-relay.html-state.v1</code> with optimistic revision guards; deterministic checks cover feedback updates, stale-copy rejection, exact visible-state projection and responsive layout. Local review is not publication; <code>share</code> requires separate authorization. No hosted-share receipt is claimed. |
| [Eli5](skills/super-eli5/SKILL.md) | Explain a topic like the reader knows nothing about it: one self-contained HTML artifact of big pictures and few words, refusing precision-critical asks instead of degrading them to pictures. | Upstream behavior sentence retained verbatim at the locked upstream commit with a reproducible SHA-256 source check; the local layer adds the topic boundary, self-contained artifact contract with a fixed audience declaration and word budgets, brand protocol and stable receipt, whose judgment layer carries a deterministic audience/style read-back assertion covered by positive and negative tests. No behavior benchmark yet. Minimal behavior eval-case path: `docs/eval-case-contract.md`. |
| [Ask Azhou](skills/super-ask-azhou/SKILL.md) | Router for the whole catalog: describe the intent, get the skill, its mode, and its boundary. Recommendation-only; gate-enforced coverage of every canonical skill. | Router pattern adapted from a pinned upstream; routing-map parity is a repository-gate check with a negative control. No behavior benchmark yet. Minimal behavior eval-case path: `docs/eval-case-contract.md`. |
| [Arch Doc](skills/super-arch-doc/SKILL.md) | Draft, calibrate and review an architecture design document from upstream sources: reading notes with per-fact provenance, a baseline skeleton with controlled evidence vocabulary, PlantUML-only diagram discipline (four-part captions, sequence-diagram rules), source cross-calibration and two-line best-practice review gates. | Distilled from the MCC ARCH-2026-001 v0.1-v0.17 pipeline (upstream team research, readability audit, best-practice review and an architect-approved 20-item backlog); five validated sequence diagrams and two registered review guides ship as references; deterministic scaffold (`new_doc.py`), closing-gate checker (`verify_doc.py`) and a golden scaffold case in `benchmarks/super-arch-doc/`. |
| [Session Insights](skills/super-session-insights/SKILL.md) | Fact-bound usage insight reports from local agent session stores (Claude Code and Codex adapters; the zcode adapter fails closed — the probed store exposes no plaintext transcripts); aggregates only, raw transcripts never leave the machine. | Wiring-integrity suite on synthetic stores with golden aggregates, window/cap trimming, receipt-digest stability, and privacy plus fail-closed negative controls. Excerpts-off aggregate runs reuse a disposable per-file metadata cache whose cold, warm, deleted and corrupt states yield byte-identical results; roast tone, the offline HTML artifact and the Codex rollout adapter are delivered behind golden parity and fail-closed negative controls, and the zcode hold stays fixed even for populated-but-unrecognized store shapes. No behavior benchmark yet. Minimal behavior eval-case path: `docs/eval-case-contract.md`. |
| [ASD-STE100](skills/super-asd-ste100/SKILL.md) | Rewrite agent-facing English — tool descriptions, error messages, inter-agent instructions, status reports — under ASD-STE100-derived controlled-English structural rules in Strict or STE-flavored mode, preserving every hedge, fact and scope qualifier; the non-redistributable ASD dictionary stays out by design. | Faithfully imported at the locked upstream commit with pinned SHA-256 integrity tests; `scripts/ste-lint.py` turns the machine-checkable structural rules into a deterministic stdlib gate (hard-violation exit codes, `--baseline`, `--json`, `--selftest`) covered by positive and negative tests. No behavior benchmark yet. Minimal behavior eval-case path: `docs/eval-case-contract.md`. |
| [Archify](skills/super-archify/SKILL.md) | Turn systems, plans, or codebases into presentation-grade interactive diagram maps — ten typed-JSON modes from architecture and workflow to ERD, tree, timeline and waterfall — delivered as self-contained explorable HTML with themes, pan/zoom, guided views and truthful exports; editable .excalidraw source scenes stay super-excalidraw-diagram's lane. | Faithfully imported at the locked upstream tag with pinned SHA-256 integrity tests over the trimmed vendored subtree (`doctor` passes all 25 checks); the deterministic `validate`/`deliver`/`finalize` real-browser gate chain is preserved unmodified, with the Azhou brand protocol and `super-archify.receipt.v1` added as wrapper layers. No behavior benchmark yet. Minimal behavior eval-case path: `docs/eval-case-contract.md`. |

All fourteen packages are independently installable and discoverable as package surfaces. The catalog composes on the invocation axis standardized in the [skill standard](docs/skill-standard.md) §2.2: [Ask Azhou](skills/super-ask-azhou/SKILL.md) is the user-invoked front door, and every package declares its class in `SKILL.md` frontmatter (user-invoked orchestrators or dual-class surfaces) — orchestrators may point at disciplines; nothing chains into another orchestrator. That does not make the four Foundation adapters standalone control planes: they require an explicit local checkout and orchestrate its repository-level CLI rather than copying lifecycle behavior into prompts. Runtime instructions live under <code>skills/</code>; prompts, assertions, fixtures and judge records stay under <code>benchmarks/</code>.

Canonical names carry one brand: every package uses the `super-` prefix. Fidelity to upstream material is recorded in each package's provenance, not in the directory name. The repository gate enforces the brand prefix and fails on residue from renamed-away names outside the documented compatibility surfaces.

## Try five task skills

| Skill | Copy this into your agent | What must come back |
|---|---|---|
| Super Repo Pedant | <code>This phase is done. Run super-repo-pedant reconcile.</code> | Reconciled knowledge surfaces, named checks, explicit holds and a stable receipt. [Run the demo](docs/demos/super-repo-pedant.md). |
| Excalidraw Diagram | <code>Use super-excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.</code> | Editable <code>.excalidraw</code>, a real render/export, deterministic gates, visual review status and a stable receipt. [Run the demo](docs/demos/super-excalidraw-diagram.md). |
| Super LLM Wiki | <code>Use super-llm-wiki to store this verified architecture decision, then query it back and lint the wiki.</code> | Private local page, source and confidence metadata, retrieval result, health report and stable receipt. [Run the demo](docs/demos/super-llm-wiki.md). |
| Super Lavish | <code>Use super-lavish in relay mode to package this spec and its review comments into one transferable HTML.</code> | Source-linked HTML with addressable sections, embedded comments and annotations, dispositioned feedback, unresolved owners, explicit transport/publication status and a relay receipt. [Run the demo](docs/demos/super-lavish.md). |
| Arch Doc | <code>Use super-arch-doc to draft this repository's architecture document from its upstream design docs.</code> | Research notes with per-fact provenance, a template scaffold with accounted diagram captions, PlantUML-only diagrams, deterministic closing gates and a stable receipt. [Run the demo](docs/demos/super-arch-doc.md). |

The demos separate product behavior from benchmark claims. Synthetic fixtures prove contracts and verifier wiring; only frozen attempt-1 runs count as model evidence.

## Why trust it?

- **Current behavior beats stale prose.** Code, machine configuration and real execution evidence define current truth; unimplemented specs stay visible as reminders.
- **Claims have gates.** The authoritative repository gate runs the complete deterministic test suite, a 4-case Super Repo Pedant suite, a 5-case Excalidraw benchmark integrity check, a Session Insights wiring-integrity suite on synthetic session stores, JSON/link/provenance/credential policy and whitespace checks.
- **Harness differences stay visible.** The maintained targets are Codex, Claude Code, MiMo Code (`mimo`) and zcode. Their discovery, invocation, hooks and history adapters are reported separately in the [support matrix](docs/support-matrix.md); other harnesses are temporarily unsupported. MiMo Code's local Skill discovery has a [bounded receipt](evidence/mimocode-skill-discovery-2026-10-26.md), while its model invocation and host adapters remain unverified.
- **Per-skill platform view.** A derived summary of the support matrix shows each canonical skill across harnesses and operating systems in [docs/skill-platform-view.md](docs/skill-platform-view.md); the support matrix stays the single authority.
- **History cannot silently rewrite a live skill.** Promotion requires a regression, deterministic checks, paired majority, no safety regression and exact-diff human approval.
- **Sources remain attributable.** Upstream snapshots, vendored assets and excluded unlicensed prior art are recorded in [third-party notices](THIRD_PARTY_NOTICES.md).

![Azhou AI Hub: the documented verification command and a recorded local result.](assets/github/readme-proof.png)

## Super Repo Pedant

> 🧹 Code is the only live answer. Everything else must align.

Invoke it when a task is actually ready to close:

~~~text
This phase is done. Run super-repo-pedant reconcile.
~~~

An inferred milestone only produces one reminder; it does not silently edit the repository. Explicit reconcile/handoff covers three project knowledge layers: user docs, <code>AGENTS.md</code>/<code>CLAUDE.md</code>, and memory proven to belong to the current project. Global instructions, unclear memory ownership, whole-file deletion, publication and deployment remain checkpoints.

Optional evolution commands require a platform file lock for signal additions and archiving. If archiving stops between state-file updates, new signal writes pause until a retry verifies the pending archive and completes the candidate receipt; conflicting evidence is refused.

[Read the compatibility contract](skills/super-repo-pedant/references/neat-freak-compatibility.md) · [Read the execution protocol](skills/super-repo-pedant/references/execution-protocol.md)

![Repo Pedant effect preview](assets/skills/super-repo-pedant-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Machine colour gate passed; final identity, hand and text review remains a human checkpoint.

## Excalidraw Diagram

> ✏️ Make the structure carry the argument; use text as evidence.

The skill never calls JSON validity “done.” It requires an editable source scene, official-engine rendering, image inspection, source-level fixes and rerun gates. Offline fonts, the official engine, converters and 231 MIT-licensed component libraries ship with the runtime package.

![Excalidraw Diagram effect preview](assets/skills/super-excalidraw-diagram-effect.png)

> ✏️ Effect preview generated with the Azhou Scenes skill. Machine colour gate passed; final identity, hand and text review remains a human checkpoint.

[Read the package](skills/super-excalidraw-diagram/SKILL.md) · [Read setup](skills/super-excalidraw-diagram/references/setup.md) · [Read provenance](skills/super-excalidraw-diagram/references/provenance.md)

## Super LLM Wiki

> 📚 Knowledge should persist—and stand up to verification.

Super LLM Wiki stores Markdown pages only under `<project>/.azhou/super-llm-wiki/`, keeps a generated catalog and operation log, and offers deterministic keyword, tag and CJK search plus health checks. CLI, eight-tool stdio MCP, lifecycle events, project context and migration share one Python core. Prior directories require an explicit dry-run and atomic copy; source data is preserved and session capture resets to false. Configuration is rendered for review and never installed implicitly.

![Super LLM Wiki effect preview](assets/skills/super-llm-wiki-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit. The retired end-to-end evidence card is preserved at <code>assets/skills/super-llm-wiki-evidence-card.png</code>.

[Run the demo](docs/demos/super-llm-wiki.md) · [Read the package](skills/super-llm-wiki/SKILL.md) · [Read brand contract](skills/super-llm-wiki/references/brand-layer.md) · [Read design](skills/super-llm-wiki/references/design.md) · [Read setup](skills/super-llm-wiki/references/setup.md) · [Read provenance](skills/super-llm-wiki/references/provenance.md)

## Lavish Editor

> 🪄 The HTML is the relay packet.

Lavish Editor is the general rich-HTML review surface: an artifact mode for complex or visual responses plus the Azhou-maintained Spec Relay relay mode for spec handoff. Both keep the upstream review runtime, focused playbooks, editable Mermaid/Excalidraw whiteboard review, portable export and optional sharing. Azhou appears only in agent progress anchors and receipts; the transferable HTML never receives Azhou identity, emoji, character assets or colors from the skill. Relay mode writes complete comments, selected-text annotations, targets, dispositions and ownership into an HTML-safe <code>spec-relay.html-state.v1</code> block. Reviewers can resolve feedback and move the packet to its next owner without losing the original record; packet revisions reject stale-copy overwrites. The responsive visible ledger is validated as the exact projection of embedded state, so the same file carries the Spec and its review history to the next teammate or agent. Local review is not publication; <code>share</code> still requires separate authorization and transfers the embedded comments too.

![Super Lavish effect preview](assets/skills/super-lavish-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-lavish/SKILL.md) · [Read the relay contract](skills/super-lavish/references/spec-relay.md) · [Read setup](skills/super-lavish/references/setup.md) · [Read provenance](skills/super-lavish/references/provenance.md) · [Read compatibility](skills/super-lavish/references/upstream-compatibility.md)

## Arch Doc

> 🏛️ Every fact cites its source; every diagram earns its caption.

Arch Doc drafts, calibrates and reviews an architecture design document from upstream sources: per-fact provenance notes, a controlled-evidence baseline skeleton, PlantUML-only diagram discipline, source cross-calibration and two-line best-practice review gates.

![Arch Doc effect preview](assets/skills/super-arch-doc-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-arch-doc/SKILL.md) · [Run the demo](docs/demos/super-arch-doc.md)

## Eli5

> 🖼️ Big pictures, few words — or an honest refusal.

Eli5 explains a topic like the reader knows nothing about it: one self-contained HTML artifact of big pictures and few words, refusing precision-critical asks instead of degrading them to pictures.

![Eli5 effect preview](assets/skills/super-eli5-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-eli5/SKILL.md)

## Ask Azhou

> 🧭 Describe the intent, get the skill, its mode and its boundary.

Ask Azhou is the user-invoked front door of the catalog: describe the intent, get one skill recommendation with its mode and its boundary. Recommendation-only; gate-enforced coverage of every canonical skill.

![Ask Azhou effect preview](assets/skills/super-ask-azhou-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-ask-azhou/SKILL.md)

## Session Insights

> 🔢 Aggregates leave the machine; raw transcripts never do.

Session Insights turns local agent session stores into fact-bound usage insight reports: aggregates only, reproducible numbers, and a fail-closed adapter when a store exposes no plaintext transcripts.

![Session Insights effect preview](assets/skills/super-session-insights-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-session-insights/SKILL.md)

## ASD-STE100

> 🎯 One meaning per word, one job per sentence — nothing for an agent to misread.

ASD-STE100 rewrites agent-facing English — tool descriptions, error messages, inter-agent instructions, status reports — under aerospace-grade controlled-English structural rules: active voice, one instruction per sentence, bounded sentence length and noun clusters, no synonym rotation. Strict mode governs text a machine must parse; STE-flavored mode keeps the structural discipline while relaxing the lexical rules for prose. The standard-library linter `ste-lint.py` turns the machine-checkable structural rules into a deterministic gate, and every rewrite preserves the original hedges, facts and scope qualifiers instead of upgrading them. The non-redistributable ASD dictionary stays out by design.

![ASD-STE100 effect preview](assets/skills/super-asd-ste100-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-asd-ste100/SKILL.md)

## Archify

> 🗺️ One map tells the whole system — hand it to the reader to explore.

Archify turns systems, plans, or codebases into presentation-grade interactive diagram maps: ten typed-JSON diagram modes delivered as self-contained explorable HTML with themes, pan/zoom, guided views and truthful exports, behind deterministic `validate`/`deliver`/`finalize` real-browser gates. Editable .excalidraw source scenes stay super-excalidraw-diagram's lane.

![Archify effect preview](assets/skills/super-archify-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Human visual P0 approved; the formal colour gate still awaits the governed workspace audit.

[Read the package](skills/super-archify/SKILL.md)

## One architecture

~~~text
docs/skill-standard.md ── governs ──> skills/<name>/       installable runtime
          │                              │
          ├── allocates ─────────────> .azhou/<name>/      private runtime state
          ├── governs ───────────────> tests/              deterministic proof
          └── governs ───────────────> benchmarks/<name>/  isolated behavior evidence

history signals ──> isolated candidate ──> paired review ──> human promotion
                         never writes the live skill directly
~~~

The [Azhou Skill Standard](docs/skill-standard.md) is the single project authority. [Architecture](docs/architecture.md) explains the boundaries; [governance](GOVERNANCE.md) explains decisions.

Installable packages remain under `skills/`. Project-local Azhou runtime state uses `.azhou/<skill-name>/`; `.azhou/hub/` is reserved for checkout-managed lifecycle receipts. Host configuration, host caches and user-selected deliverables stay outside this namespace.

## Develop

Python 3.11+ is enough for the repository gate:

~~~bash
python scripts/verify.py
~~~

The same command checks repository policy, all unit tests, three public benchmark-integrity suites and Git whitespace without private inputs. It runs every gate to completion and always ends on exactly one aggregate verdict line, so a piped or tailed capture cannot end on a passing note while the run failed; `python scripts/verify.py --print-summary` emits a machine-readable JSON summary (`azhou-hub.verify-summary.v1`) before that verdict line. It is enforced in CI on Ubuntu and windows-latest, and is verified on the maintainer macOS checkout, so the OS support claims in [docs/support-matrix.md](docs/support-matrix.md) stay receipt-backed. The full managed flow on Windows (info → setup → doctor → repository gate) is receipt-backed green on a real runner with the default Git Bash console encoding ([evidence/windows-full-flow-receipt-2026-10-17.md](evidence/windows-full-flow-receipt-2026-10-17.md)). Excalidraw rendering has additional locked Python/Node dependencies documented in its own setup guide.

## Project

Agent Skin also has a package gate: `python packages/agent-skin/tools/test-unit-coverage.py` on macOS requires at least 95% unit-test line coverage for every production language and the complete package. Its Required CI job is separate from browser functional tests and installed-app acceptance. See [Agent Skin testing and acceptance](packages/agent-skin/docs/testing.md) for the full scope, dependencies and Finder/Dock, cold-start, wallpaper and installation cases.

- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Foundation CLI](docs/foundations.md)
- [Treehouse worktree policy](docs/worktree-policy.md)
- [Research behind this open-source surface](docs/research/2026-08-23-open-source-benchmark.md)

Contributions are welcome when they begin with a real failure or task and end with reproducible evidence. Read [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Azhou-maintained code: [MIT](LICENSE). Third-party components retain their own notices and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

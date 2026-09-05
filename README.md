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

<img src="assets/github/social-preview.png" alt="Azhou AI Hub — proof-driven Agent Skills" width="100%" />

</div>

Most skill repositories stop at prompts. Azhou AI Hub treats each skill as a product: a precise trigger, a portable runtime package, reproducible setup, deterministic gates, honest evaluation, provenance, and a human-controlled evolution path.

No universal framework. No model-specific copy of the same skill. No benchmark answer hidden inside the runtime package.

## Installation paths

Install one package per command:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-info
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-doctor
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-setup
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-verify
npx skills add TeFuirnever/azhou-ai-hub --skill super-caveman
npx skills add TeFuirnever/azhou-ai-hub --skill llm-wiki
npx skills add TeFuirnever/azhou-ai-hub --skill lavish
npx skills add TeFuirnever/azhou-ai-hub --skill eli5
npx skills add TeFuirnever/azhou-ai-hub --skill autoresearch
npx skills add TeFuirnever/azhou-ai-hub --skill arch-doc
~~~

These commands are the documented package-manager path; completion time and host discovery are harness-dependent and are not promised here.

Choose one installation method. Do not stack a package-manager install, a checkout-managed install, a manual copy, and a development symlink under the same canonical skill name. The four `azhou-*` packages make their `SKILL.md` workflow discoverable; they do not bundle the Foundation CLI and still require an explicit local checkout. See the [installation guide](docs/installation.md) for the complete paths and dependencies.

## Inspect, set up, or verify a checkout

Four portable Azhou Agent Skills expose the checkout workflow without duplicating its mechanics. Invoke them through the active harness's native Skill surface while working in an Azhou AI Hub checkout, or provide that checkout path explicitly. Each adapter delegates to the checkout's zero-dependency Foundation CLI:

| Agent Skill | CLI authority | Change boundary |
|---|---|---|
| `azhou-info` | `info`, `version` | Read-only project, runtime, Git revision and dirty-state facts. |
| `azhou-doctor` | `doctor` | Read-only repository, explicit install-target and optional Treehouse lease diagnostics. |
| `azhou-setup` | `setup`, `repair`, `migrate`, `uninstall` | Dry-run first; only an exact reviewed plan with `--apply` may mutate its explicit target. |
| `azhou-verify` | `verify` | Runs the reproducible public repository-integrity gate; maintainers can explicitly add promotion-evidence replay. |

~~~bash
python3 scripts/azhou_hub.py info --json
python3 scripts/azhou_hub.py version --json
python3 scripts/azhou_hub.py doctor --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target /absolute/path/to/harness/skills --json
python3 scripts/azhou_hub.py verify
~~~

`setup`, `repair`, `migrate`, and `uninstall` stay read-only until `--apply` is present. Setup is idempotent and refuses to overwrite a different installation. Receipt-owned lifecycle commands require the same explicit target and independently verify the canonical source and installed identity; they never force drifted content, cross harness roots, install hooks, rewrite harness configuration, contact a registry or update the CLI. The packages are shared across harnesses, but discovery, invocation, permissions and optional integrations remain host-specific; see the [support matrix](docs/support-matrix.md) and [Foundation CLI contract](docs/foundations.md).

For setup, review the deterministic `planId` from the dry-run, then pass the exact value with `--apply --plan-id <reviewed-planId>`; source, target, mode, or pre-apply state changes invalidate the apply.

## Skills

| Skill | Real job | Verification basis |
|---|---|---|
| [Azhou Info](skills/azhou-info/SKILL.md) | Report checkout, runtime, support and provable Git revision facts without manufacturing release state. | Delegates to stable `info` / `version` JSON contracts; read-only package and repository-policy checks. |
| [Azhou Doctor](skills/azhou-doctor/SKILL.md) | Diagnose repository, explicit install target and optional Treehouse lease health without mutation. | Read-only doctor contract, real Treehouse 2.3.0 smoke and fail-closed target checks. |
| [Azhou Setup](skills/azhou-setup/SKILL.md) | Plan and explicitly apply checkout-assisted install or receipt-owned lifecycle operations. | Dry-run-first setup, mutation lock, identity guards, rollback and receipt regressions. |
| [Azhou Verify](skills/azhou-verify/SKILL.md) | Run the public full-repository integrity gate or an explicit maintainer promotion replay. | Delegates to repository policy, unit, benchmark-integrity and whitespace gates; promotion mode additionally requires Git-external evidence. |
| [Repo Pedant](skills/repo-pedant/SKILL.md) | At explicit task close, reconcile docs, project rules, handoff state and project-bound memory against current code. | 28/28 <code>neat-freak</code> capabilities accounted for; 3 registered behavior cases; fixed execution protocol and inventory proof. |
| [Excalidraw Diagram](skills/excalidraw-diagram/SKILL.md) | Create or edit an editable scene, render the real artifact, inspect it, and deliver CJK-safe SVG/PNG when requested. | 5 frozen benchmark cases; deterministic style, scene, overlap and same-DOM gates. Checked-in reference output proves wiring only, not model quality. |
| [LLM Wiki](skills/llm-wiki/SKILL.md) | Build a private, persistent Markdown knowledge base that agents can ingest, search, read and lint across sessions. | Canonical local store, seven MCP tools, three lifecycle events, atomic migration, privacy defaults and focused deterministic contract tests. |
| [Super Caveman](skills/super-caveman/SKILL.md) | Enhance original Caveman with the complete pinned `i-have-adhd` output-behavior contract plus commit, review, delegation, help, file-compression and statistics routes. | Original Caveman plus six companions in one canonical package; 8 route fixtures, retained historical 14-case evidence, a current 19/19-case and 44/44-criterion behavior run, three independent paired judges voting 3/3 for the candidate with zero high-risk regressions, and a neutral recoverable compression guard. Evidence is limited to the recorded Codex Desktop harness/model. |
| [Lavish](skills/lavish/SKILL.md) | Turn complex or visual agent responses into rich, reviewable HTML artifacts users can annotate and answer through the Lavish Editor CLI; in Spec Relay relay mode, package a PRD, RFC, design spec or technical plan with comments, selected-text annotations, disposition and next-owner state inside one portable HTML file. | Upstream baseline hash-locked for reproducibility at the locked CLI <code>0.1.47</code>, with the documented local relay layer on top; provenance records the immutable upstream commit and the reproducible source check. Relay mode embeds <code>spec-relay.html-state.v1</code> with optimistic revision guards; deterministic checks cover feedback updates, stale-copy rejection, exact visible-state projection and responsive layout. Local review is not publication; <code>share</code> requires separate authorization. No hosted-share receipt is claimed. |
| [Eli5](skills/eli5/SKILL.md) | Explain a topic like the reader knows nothing about it: one self-contained HTML artifact of big pictures and few words, refusing precision-critical asks instead of degrading them to pictures. | Upstream behavior sentence retained verbatim at the locked upstream commit with a reproducible SHA-256 source check; the local layer adds the topic boundary, self-contained artifact contract, brand protocol and stable receipt, covered by deterministic package-surface checks. No behavior benchmark yet. |
| [Autoresearch](skills/autoresearch/SKILL.md) | Wrap a user-owned pinned <code>karpathy/autoresearch</code> checkout so an agent can prepare, run, resume and report automatic nanochat training experiments, holding before any unattended GPU run. | Azhou-authored wrapper vendors zero upstream bytes because the upstream publishes no license; fail-closed setup checks the CUDA GPU, uv and the pinned commit, covered by deterministic package-surface checks. No behavior benchmark yet. |
| [Arch Doc](skills/arch-doc/SKILL.md) | Draft, calibrate and review an architecture design document from upstream sources: reading notes with per-fact provenance, a baseline skeleton with controlled evidence vocabulary, PlantUML-only diagram discipline (four-part captions, sequence-diagram rules), source cross-calibration and two-line best-practice review gates. | Distilled from the MCC ARCH-2026-001 v0.1-v0.17 pipeline (upstream team research, readability audit, best-practice review and an architect-approved 20-item backlog); five validated sequence diagrams and two registered review guides ship as references; deterministic scaffold (`new_doc.py`), closing-gate checker (`verify_doc.py`) and a golden scaffold case in `benchmarks/arch-doc/`. |

All twelve packages are independently installable and discoverable as package surfaces. That does not make the four Foundation adapters standalone control planes: they require an explicit local checkout and orchestrate its repository-level CLI rather than copying lifecycle behavior into prompts. Runtime instructions live under <code>skills/</code>; prompts, assertions, fixtures and judge records stay under <code>benchmarks/</code>.

## Try six task skills

| Skill | Copy this into your agent | What must come back |
|---|---|---|
| Repo Pedant | <code>This phase is done. Run repo-pedant reconcile.</code> | Reconciled knowledge surfaces, named checks, explicit holds and a stable receipt. [Run the demo](docs/demos/repo-pedant.md). |
| Excalidraw Diagram | <code>Use excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.</code> | Editable <code>.excalidraw</code>, a real render/export, deterministic gates, visual review status and a stable receipt. [Run the demo](docs/demos/excalidraw-diagram.md). |
| Super Caveman | <code>Use /super-caveman full. Then write a commit message for this diff.</code> | Action-first terse mode plus a paste-ready Conventional Commit message; no staging or commit side effect. |
| LLM Wiki | <code>Use llm-wiki to store this verified architecture decision, then query it back and lint the wiki.</code> | Private local page, source and confidence metadata, retrieval result, health report and stable receipt. [Run the demo](docs/demos/llm-wiki.md). |
| Lavish | <code>Use lavish in relay mode to package this spec and its review comments into one transferable HTML.</code> | Source-linked HTML with addressable sections, embedded comments and annotations, dispositioned feedback, unresolved owners, explicit transport/publication status and a relay receipt. [Run the demo](docs/demos/lavish.md). |
| Arch Doc | <code>Use arch-doc to draft this repository's architecture document from its upstream design docs.</code> | Research notes with per-fact provenance, a template scaffold with accounted diagram captions, PlantUML-only diagrams, deterministic closing gates and a stable receipt. [Run the demo](docs/demos/arch-doc.md). |

The demos separate product behavior from benchmark claims. Synthetic fixtures prove contracts and verifier wiring; only frozen attempt-1 runs count as model evidence.

## Why trust it?

- **Current behavior beats stale prose.** Code, machine configuration and real execution evidence define current truth; unimplemented specs stay visible as reminders.
- **Claims have gates.** The authoritative repository gate runs the complete deterministic test suite, a 3-case Repo Pedant suite, an 8-route and 19-response-case Super Caveman integrity suite, a 5-case Excalidraw benchmark integrity check, JSON/link/provenance/credential policy and whitespace checks.
- **Harness differences stay visible.** Codex, Claude Code and zcode share the same runtime packages, but hooks and history adapters are reported separately in the [support matrix](docs/support-matrix.md).
- **History cannot silently rewrite a live skill.** Promotion requires a regression, deterministic checks, paired majority, no safety regression and exact-diff human approval.
- **Sources remain attributable.** Upstream snapshots, vendored assets and excluded unlicensed prior art are recorded in [third-party notices](THIRD_PARTY_NOTICES.md).

## Repo Pedant

> 🧹 Code is the only live answer. Everything else must align.

Invoke it when a task is actually ready to close:

~~~text
This phase is done. Run repo-pedant reconcile.
~~~

An inferred milestone only produces one reminder; it does not silently edit the repository. Explicit reconcile/handoff covers three project knowledge layers: user docs, <code>AGENTS.md</code>/<code>CLAUDE.md</code>, and memory proven to belong to the current project. Global instructions, unclear memory ownership, whole-file deletion, publication and deployment remain checkpoints.

[Read the compatibility contract](skills/repo-pedant/references/neat-freak-compatibility.md) · [Read the execution protocol](skills/repo-pedant/references/execution-protocol.md)

![Repo Pedant effect preview](assets/skills/repo-pedant-effect.png)

> 🦊 Effect preview generated with the Azhou Scenes skill. Machine colour gate passed; final identity, hand and text review remains a human checkpoint.

## Excalidraw Diagram

> ✏️ Make the structure carry the argument; use text as evidence.

The skill never calls JSON validity “done.” It requires an editable source scene, official-engine rendering, image inspection, source-level fixes and rerun gates. Offline fonts, the official engine, converters and 231 MIT-licensed component libraries ship with the runtime package.

![Excalidraw Diagram effect preview](assets/skills/excalidraw-diagram-effect.png)

> ✏️ Effect preview generated with the Azhou Scenes skill. Machine colour gate passed; final identity, hand and text review remains a human checkpoint.

[Read the package](skills/excalidraw-diagram/SKILL.md) · [Read setup](skills/excalidraw-diagram/references/setup.md) · [Read provenance](skills/excalidraw-diagram/references/provenance.md)

## Super Caveman

> 🪨 Less prose. Same technical signal.

Super Caveman keeps original Caveman's persistent terse modes as its core, absorbs six companion skills as compact delegation, commit-message, review, guarded compression, help and evidence-bound statistics routes, and fully adopts the pinned `i-have-adhd` output-behavior contract. Everything ships as one canonical `super-caveman` package. Safety and explicit output contracts run first, the complete ADHD-friendly behavior contract runs second, and Caveman compression runs last. Plugin installation, hooks, global configuration, diagnostic claims and unverified cross-session persistence are outside this neutral package. The optional Codex, Claude Code and zcode lifecycle adapters are the documented exceptions and require explicit scoped setup before any hook registration. File compression never launches a second model or silently transmits content; a standard-library guard checks the source, validates protected structure, writes an out-of-tree backup, uses a checkpointed no-clobber install, and refuses restore over newer work. Guarded apply and restore require same-directory hard-link support and fail before moving the source when the filesystem denies it. Material operations use one restrained Azhou anchor per verified stage; ordinary terse replies do not add lifecycle emoji. Exact statistics remain unavailable when the host exposes no audited counters.

![Super Caveman guarded-compression effect preview](assets/skills/super-caveman-effect.png)

> 🦊 Effect preview generated with Azhou Scenes. Composition, text and run binding were checked; formal v1.9 colour promotion and final identity/hand approval remain checkpoints.

[Read the package](skills/super-caveman/SKILL.md) · [Read setup](skills/super-caveman/references/setup.md) · [Read provenance](skills/super-caveman/references/provenance.md) · [Read compression safety](skills/super-caveman/references/compression.md)

## LLM Wiki

> 📚 Knowledge should persist—and stand up to verification.

LLM Wiki stores Markdown pages only under `<project>/.azhou/llm-wiki/`, keeps a generated catalog and operation log, and offers deterministic keyword, tag and CJK search plus health checks. CLI, seven-tool stdio MCP, lifecycle events, project context and migration share one Python core. Prior directories require an explicit dry-run and atomic copy; source data is preserved and session capture resets to false. Configuration is rendered for review and never installed implicitly.

![LLM Wiki end-to-end evidence preview](assets/skills/llm-wiki-effect.png)

> 🦊 Evidence preview built from one real isolated CLI, MCP `tools/list`, and `SessionStart` run. Bundle, render, and visual inspection passed; final public visual approval remains a human checkpoint.

[Run the demo](docs/demos/llm-wiki.md) · [Read the package](skills/llm-wiki/SKILL.md) · [Read brand contract](skills/llm-wiki/references/brand-layer.md) · [Read design](skills/llm-wiki/references/design.md) · [Read setup](skills/llm-wiki/references/setup.md) · [Read provenance](skills/llm-wiki/references/provenance.md)

## Lavish Editor

> 🪄 The HTML is the relay packet.

Lavish Editor is the general rich-HTML review surface: an artifact mode for complex or visual responses plus the Azhou-maintained Spec Relay relay mode for spec handoff. Both keep the upstream review runtime, focused playbooks, editable Mermaid/Excalidraw whiteboard review, portable export and optional sharing. Azhou appears only in agent progress anchors and receipts; the transferable HTML never receives Azhou identity, emoji, character assets or colors from the skill. Relay mode writes complete comments, selected-text annotations, targets, dispositions and ownership into an HTML-safe <code>spec-relay.html-state.v1</code> block. Reviewers can resolve feedback and move the packet to its next owner without losing the original record; packet revisions reject stale-copy overwrites. The responsive visible ledger is validated as the exact projection of embedded state, so the same file carries the Spec and its review history to the next teammate or agent. Local review is not publication; <code>share</code> still requires separate authorization and transfers the embedded comments too.

[Read the package](skills/lavish/SKILL.md) · [Read the relay contract](skills/lavish/references/spec-relay.md) · [Read setup](skills/lavish/references/setup.md) · [Read provenance](skills/lavish/references/provenance.md) · [Read compatibility](skills/lavish/references/upstream-compatibility.md)

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
python3 scripts/verify.py
~~~

The same command checks repository policy, all unit tests, three public benchmark-integrity suites and Git whitespace without private inputs. Super Caveman's public integrity check still recomputes the approved exact diff against the current staged or committed tree, so a changed approved path requires fresh promotion evidence instead of silently passing. Release maintainers additionally run `python3 scripts/verify.py --promotion-evidence` after materializing the Git-external Super Caveman approval and review records. That second mode authenticates the raw promotion evidence; the default public gate validates the checked-in receipt and exact diff but does not claim external authentication. Excalidraw rendering has additional locked Python/Node dependencies documented in its own setup guide.

## Project

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

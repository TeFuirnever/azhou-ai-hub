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

## Install in 30 seconds

Install one skill:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill repo-pedant
~~~

Or:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
~~~

For checkout diagnostics through an Agent Skill:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-doctor
~~~

Or:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill lavish
~~~

Or:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill llm-wiki
~~~

Or:

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-caveman
~~~

Choose one installation method. Do not stack a managed install, a copied package, and a development symlink under the same canonical skill name. See the [installation guide](docs/installation.md) for manual and contributor paths.

## Diagnose or set up a checkout

Four portable Azhou Agent Skills expose the checkout workflow without duplicating its mechanics: `azhou-info`, `azhou-doctor`, `azhou-setup`, and `azhou-verify`. They locate an explicit Azhou AI Hub checkout, then delegate to its zero-dependency Foundation CLI. The CLI remains the authority for repository-wide `info`, `version`, read-only `doctor`, dry-run-first `setup`, the canonical `verify` gate, and receipt-owned `repair`, same-target `migrate`, and `uninstall`:

~~~bash
python3 scripts/azhou_hub.py doctor --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target /absolute/path/to/harness/skills --json
python3 scripts/azhou_hub.py setup --managed --receipt /absolute/path/to/receipt.json --skill repo-pedant --target /absolute/path/to/harness/skills --json
~~~

Nothing changes until `--apply` is present. Setup is idempotent and refuses to overwrite a different installation. Managed lifecycle commands require the same explicit target and independently verify the canonical source and exact installed identity; they never force drifted content, cross harness roots, install hooks, rewrite harness configuration, contact a registry or update the CLI. See the [foundation CLI contract](docs/foundations.md).

## Skills

| Skill | Real job | Evidence today |
|---|---|---|
| [Azhou Info](skills/azhou-info/SKILL.md) | Report checkout, runtime, support and provable Git revision facts without manufacturing release state. | Delegates to stable `info` / `version` JSON contracts; read-only package and repository-policy checks. |
| [Azhou Doctor](skills/azhou-doctor/SKILL.md) | Diagnose repository, explicit install target and optional Treehouse lease health without mutation. | Read-only doctor contract, real Treehouse 2.3.0 smoke and fail-closed target checks. |
| [Azhou Setup](skills/azhou-setup/SKILL.md) | Plan and explicitly apply checkout-assisted install or receipt-owned lifecycle operations. | Dry-run-first setup, mutation lock, identity guards, rollback and receipt regressions. |
| [Azhou Verify](skills/azhou-verify/SKILL.md) | Run and report the one authoritative full-repository verification gate. | Delegates to the registered repository policy, unit, benchmark-integrity and whitespace gates. |
| [Repo Pedant](skills/repo-pedant/SKILL.md) | At explicit task close, reconcile docs, project rules, handoff state and project-bound memory against current code. | 28/28 <code>neat-freak</code> capabilities accounted for; 3 registered behavior cases; fixed execution protocol and inventory proof. |
| [Excalidraw Diagram](skills/excalidraw-diagram/SKILL.md) | Create or edit an editable scene, render the real artifact, inspect it, and deliver CJK-safe SVG/PNG when requested. | 5 frozen benchmark cases; deterministic style, scene, overlap and same-DOM gates. Checked-in reference output proves wiring only, not model quality. |
| [Lavish](skills/lavish/SKILL.md) | Turn a plan, comparison, diagram, table, code view or report into a browser review surface with annotations and a feedback loop. | Imported skill is byte-matched to immutable upstream commit <code>232972b</code>; CLI <code>0.1.47</code>, capability map, authorization boundaries and license are checked. No hosted-share receipt is claimed. |
| [LLM Wiki](skills/llm-wiki/SKILL.md) | Build a private, persistent Markdown knowledge base that agents can ingest, search, read and lint across sessions. | All 7 upstream operations mapped; 10 deterministic runtime tests; immutable MIT source, legacy-store path and opt-in lifecycle boundary recorded. |
| [Super Caveman](skills/super-caveman/SKILL.md) | Enhance original Caveman with the complete pinned `i-have-adhd` output-behavior contract plus commit, review, delegation, help, file-compression and statistics routes. | Original Caveman plus six companions in one canonical package; 8 route fixtures, historical 14-case evidence, a byte-identical current 19/19-case and 44/44-criterion review, three paired judges voting 3/3 for the candidate, zero high-risk regressions, and exact-diff approval bound to the current staged tree. Evidence remains limited to the recorded Codex Desktop harness/model. |

All nine packages are independently installable. Azhou Skills require an explicit local checkout because they orchestrate the repository-level CLI rather than copying its behavior into prompts. Runtime instructions live under <code>skills/</code>; prompts, assertions, fixtures and judge records stay under <code>benchmarks/</code>.

## Try three task skills in 60 seconds

| Skill | Copy this into your agent | What must come back |
|---|---|---|
| Repo Pedant | <code>This phase is done. Run repo-pedant reconcile.</code> | Reconciled knowledge surfaces, named checks, explicit holds and a stable receipt. [Run the demo](docs/demos/repo-pedant.md). |
| Excalidraw Diagram | <code>Use excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.</code> | Editable <code>.excalidraw</code>, a real render/export, deterministic gates, visual review status and a stable receipt. [Run the demo](docs/demos/excalidraw-diagram.md). |
| Lavish | <code>Use lavish to turn this plan into a reviewable comparison.</code> | Local HTML artifact, selected design source and playbooks, attached review state, explicit publication status and a stable receipt. |
| LLM Wiki | <code>Use llm-wiki to store this verified architecture decision, then query it back and lint the wiki.</code> | Private local page, source and confidence metadata, retrieval result, health report and a stable receipt. |
| Super Caveman | <code>Use /super-caveman full. Then write a commit message for this diff.</code> | Action-first terse mode plus a paste-ready Conventional Commit message; no staging or commit side effect. |

The demos separate product behavior from benchmark claims. Synthetic fixtures prove contracts and verifier wiring; only frozen attempt-1 runs count as model evidence.

## Why trust it?

- **Current behavior beats stale prose.** Code, machine configuration and real execution evidence define current truth; unimplemented specs stay visible as reminders.
- **Claims have gates.** The repository runs the current deterministic test suite, a 3-case Repo Pedant suite, an 8-route and 19-response-case Super Caveman integrity suite, a 5-case Excalidraw benchmark integrity check, JSON/link/provenance/credential policy and whitespace checks.
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

## Lavish

> 🪄 Make complex work inspectable, annotatable and easy to revise.

Lavish writes a local HTML artifact, opens it in a browser review surface and keeps human feedback connected to the same task. The imported upstream behavior includes focused playbooks, Mermaid-to-editable-Excalidraw review, portable export and optional third-party sharing. Azhou pins the CLI baseline and adds explicit checkpoints: local review is not publication, and <code>share</code> never runs without separate authorization.

[Read the package](skills/lavish/SKILL.md) · [Read setup](skills/lavish/references/setup.md) · [Read provenance](skills/lavish/references/provenance.md) · [Read compatibility](skills/lavish/references/upstream-compatibility.md)

## LLM Wiki

> 📚 Durable project knowledge stays local, sourced and inspectable.

LLM Wiki stores Markdown pages under a private-by-default project directory, keeps a generated catalog and operation log, and offers deterministic keyword/tag/CJK search plus health checks. The neutral Python core preserves all seven upstream operations. Existing oh-my-claudecode stores remain usable in place; lifecycle hooks and session metadata capture are never installed or enabled implicitly.

[Read the package](skills/llm-wiki/SKILL.md) · [Read setup](skills/llm-wiki/references/setup.md) · [Read provenance](skills/llm-wiki/references/provenance.md) · [Read compatibility](skills/llm-wiki/references/upstream-compatibility.md)

## Super Caveman

> 🪨 Less prose. Same technical signal.

Super Caveman keeps original Caveman's persistent terse modes as its core, absorbs six companion skills as compact delegation, commit-message, review, guarded compression, help and evidence-bound statistics routes, and fully adopts the pinned `i-have-adhd` output-behavior contract. Everything ships as one canonical `super-caveman` package. Safety and explicit output contracts run first, the complete ADHD-friendly behavior contract runs second, and Caveman compression runs last. The neutral core never installs a hook or edits global configuration. Its optional Codex adapter is separately enabled with an explicit `project` or `user` command and registers one bounded full-mode `SessionStart` hook; it does not read private history or contact the network. Existing global Caveman and ADHD hooks must be explicitly reconciled because Codex merges matching hooks across layers. Claude Code lifecycle support is roadmap-only. File compression never launches a second model or silently transmits content; a standard-library guard checks the source, validates protected structure, writes an out-of-tree backup, uses a checkpointed no-clobber install, and refuses restore over newer work. Guarded apply and restore require same-directory hard-link support and fail before moving the source when the filesystem denies it. Material operations use one restrained Azhou anchor per verified stage; ordinary terse replies do not add lifecycle emoji. Exact statistics remain unavailable when the host exposes no audited counters.

[Read the package](skills/super-caveman/SKILL.md) · [Read setup](skills/super-caveman/references/setup.md) · [Read provenance](skills/super-caveman/references/provenance.md) · [Read compression safety](skills/super-caveman/references/compression.md)

## One architecture

~~~text
docs/skill-standard.md ── governs ──> skills/<name>/       installable runtime
          │                              │
          ├── governs ───────────────> tests/              deterministic proof
          └── governs ───────────────> benchmarks/<name>/  isolated behavior evidence

history signals ──> isolated candidate ──> paired review ──> human promotion
                         never writes the live skill directly
~~~

The [Azhou Skill Standard](docs/skill-standard.md) is the single project authority. [Architecture](docs/architecture.md) explains the boundaries; [governance](GOVERNANCE.md) explains decisions.

## Develop

Python 3.11+ is enough for the repository gate:

~~~bash
python3 scripts/verify.py
~~~

The same command checks repository policy, all unit tests, three benchmark-integrity suites and Git whitespace. Excalidraw rendering has additional locked Python/Node dependencies; Lavish needs Node.js 22+ and downloads its pinned CLI on demand. Each package documents its own setup.

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

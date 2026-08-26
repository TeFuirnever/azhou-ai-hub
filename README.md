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
npx skills add TeFuirnever/azhou-ai-hub --skill foundation-doctor
~~~

Choose one installation method. Do not stack a managed install, a copied package, and a development symlink under the same canonical skill name. See the [installation guide](docs/installation.md) for manual and contributor paths.

## Diagnose or set up a checkout

Four portable Agent Skills expose the checkout workflow without duplicating its mechanics: `foundation-info`, `foundation-doctor`, `foundation-setup`, and `foundation-verify`. They locate an explicit Azhou AI Hub checkout, then delegate to its zero-dependency Foundation CLI. The CLI remains the authority for repository-wide `info`, `version`, read-only `doctor`, dry-run-first `setup`, the canonical `verify` gate, and receipt-owned `repair`, same-target `migrate`, and `uninstall`:

~~~bash
python3 scripts/azhou_hub.py doctor --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target /absolute/path/to/harness/skills --json
python3 scripts/azhou_hub.py setup --managed --receipt /absolute/path/to/receipt.json --skill repo-pedant --target /absolute/path/to/harness/skills --json
~~~

Nothing changes until `--apply` is present. Setup is idempotent and refuses to overwrite a different installation. Managed lifecycle commands require the same explicit target and independently verify the canonical source and exact installed identity; they never force drifted content, cross harness roots, install hooks, rewrite harness configuration, contact a registry or update the CLI. See the [foundation CLI contract](docs/foundations.md).

## Skills

| Skill | Real job | Evidence today |
|---|---|---|
| [Foundation Info](skills/foundation-info/SKILL.md) | Report checkout, runtime, support and provable Git revision facts without manufacturing release state. | Delegates to stable `info` / `version` JSON contracts; read-only package and repository-policy checks. |
| [Foundation Doctor](skills/foundation-doctor/SKILL.md) | Diagnose repository, explicit install target and optional Treehouse lease health without mutation. | Read-only doctor contract, real Treehouse 2.3.0 smoke and fail-closed target checks. |
| [Foundation Setup](skills/foundation-setup/SKILL.md) | Plan and explicitly apply checkout-assisted install or receipt-owned lifecycle operations. | Dry-run-first setup, mutation lock, identity guards, rollback and receipt regressions. |
| [Foundation Verify](skills/foundation-verify/SKILL.md) | Run and report the one authoritative full-repository verification gate. | Delegates to the registered repository policy, unit, benchmark-integrity and whitespace gates. |
| [Repo Pedant](skills/repo-pedant/SKILL.md) | At explicit task close, reconcile docs, project rules, handoff state and project-bound memory against current code. | 28/28 <code>neat-freak</code> capabilities accounted for; 3 registered behavior cases; fixed execution protocol and inventory proof. |
| [Excalidraw Diagram](skills/excalidraw-diagram/SKILL.md) | Create or edit an editable scene, render the real artifact, inspect it, and deliver CJK-safe SVG/PNG when requested. | 5 frozen benchmark cases; deterministic style, scene, overlap and same-DOM gates. Checked-in reference output proves wiring only, not model quality. |

All six packages are independently installable. Foundation Skills require an explicit local checkout because they orchestrate the repository-level CLI rather than copying its behavior into prompts. Runtime instructions live under <code>skills/</code>; prompts, assertions, fixtures and judge records stay under <code>benchmarks/</code>.

## Try two task skills in 60 seconds

| Skill | Copy this into your agent | What must come back |
|---|---|---|
| Repo Pedant | <code>This phase is done. Run repo-pedant reconcile.</code> | Reconciled knowledge surfaces, named checks, explicit holds and a stable receipt. [Run the demo](docs/demos/repo-pedant.md). |
| Excalidraw Diagram | <code>Use excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.</code> | Editable <code>.excalidraw</code>, a real render/export, deterministic gates, visual review status and a stable receipt. [Run the demo](docs/demos/excalidraw-diagram.md). |

The demos separate product behavior from benchmark claims. Synthetic fixtures prove contracts and verifier wiring; only frozen attempt-1 runs count as model evidence.

## Why trust it?

- **Current behavior beats stale prose.** Code, machine configuration and real execution evidence define current truth; unimplemented specs stay visible as reminders.
- **Claims have gates.** The repository runs 121 deterministic tests, a 3-case Repo Pedant suite, a 5-case Excalidraw benchmark integrity check, JSON/link/provenance/credential policy and whitespace checks.
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

The same command checks repository policy, all unit tests, both benchmark-integrity suites and Git whitespace. Excalidraw rendering has additional locked Python/Node dependencies documented in its own setup guide.

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

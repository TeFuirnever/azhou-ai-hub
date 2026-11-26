<div align="center">

# 🦊 Azhou AI Hub

**Agent skills that stay useful after the demo.**

Small enough to edit. Strict enough to verify. Neutral enough to run across harnesses.

[简体中文](README.zh-CN.md) · [Install](docs/installation.md) · [Support matrix](docs/support-matrix.md) · [Docs index](docs/README.md) · [Contributing](CONTRIBUTING.md) · [Website](https://tefuirnever.github.io/azhou-ai-hub/)

[![CI](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/TeFuirnever/azhou-ai-hub?display_name=tag&sort=semver)](https://github.com/TeFuirnever/azhou-ai-hub/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f7d4a.svg)](LICENSE)

</div>

### First install in Codex

Sign in to Codex and use Node.js 22.20 or later. Run the command from your project folder and confirm the project install when prompted. On Windows, use Git Bash for the [shell examples](docs/installation.md#windows-notes).

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou --agent codex
~~~

Open a new Codex chat in that project. Type `$super-ask-azhou` to check that Codex can find it, then try the following question.

> `$super-ask-azhou` I have a Mermaid diagram and want to turn it into an interactive architecture diagram. Which Hub Skill should I use?

Expect a recommendation for `super-archify`. If Codex cannot find Ask Azhou, [check the installation](docs/installation.md#if-codex-cannot-find-ask-azhou). For an existing installation, see [check, update, or uninstall](docs/installation.md#upgrade-or-uninstall).

When you want to use a recommended skill, follow the [single-skill install guide](docs/installation.md#package-manager-install). Use [one installation method per skill](docs/installation.md#one-path-rule). The four `super-azhou-*` skills also require a local checkout.

The walkthrough above targets Codex. For the other maintained harnesses — Claude Code, MiMo Code (`mimo`), DeepSeek Harness (`dsh`) and zcode — the verified install route and evidence per harness live in the [support matrix](docs/support-matrix.md), and a repository checkout can install via [checkout-assisted setup](docs/installation.md#checkout-assisted-setup) or [manual copy](docs/installation.md#manual-copy).

[Update or uninstall](docs/installation.md#upgrade-or-uninstall) · [Verify what you installed](docs/installation.md#verify-what-you-installed) · [Installation guide](docs/installation.md) · [Offline recovery](docs/installation.md#offline-recovery)

## Skills

Every adapted package records its upstream provenance in `skills/<name>/references/provenance.md`; SHA-256 source pins and npm-integrity pins appear only where that file records them — not as a uniform guarantee across the catalog.

| Skill | Real job | Verification basis |
|---|---|---|
| [Azhou Info](skills/super-azhou-info/SKILL.md) | Report checkout, runtime, support and provable Git revision facts. | Stable `info`/`version` JSON contracts; read-only checks. |
| [Azhou Doctor](skills/super-azhou-doctor/SKILL.md) | Diagnose repository, install-target, lease and host-migration health, read-only. | Read-only doctor contract; Treehouse lease smoke contract (subprocess-boundary unit tests); fail-closed. |
| [Azhou Setup](skills/super-azhou-setup/SKILL.md) | Guide scoped installation, update and removal, including checkout-managed lifecycle. | Dry-run-first setup; mutation lock, identity guards and rollback regressions. |
| [Azhou Verify](skills/super-azhou-verify/SKILL.md) | Run the public full-repository integrity gate. | Repository policy, retired-surface reverse scan, unit, package manifest/lifecycle, benchmark-integrity, wiring-integrity and whitespace gates. |
| [Super Repo Pedant](skills/super-repo-pedant/SKILL.md) | At task close, reconcile docs, rules and handoff state. | All 28 capabilities of the upstream `neat-freak` baseline ([Khazix-Skills](THIRD_PARTY_NOTICES.md#super-repo-pedant-baseline)) accounted; 4 registered behavior cases. |
| [Excalidraw Diagram](skills/super-excalidraw-diagram/SKILL.md) | Create or edit an editable scene; render, inspect, deliver CJK-safe SVG/PNG. | 5 frozen benchmark cases; deterministic style/scene/overlap gates. |
| [Eli5](skills/super-eli5/SKILL.md) | Explain a topic as one self-contained HTML artifact — big pictures, few words. | Upstream behavior sentence pinned (SHA-256); no behavior benchmark. |
| [Ask Azhou](skills/super-ask-azhou/SKILL.md) | Router: describe the intent, get the skill, mode and boundary. | Routing-map parity gate with a negative control. |
| [Arch Doc](skills/super-arch-doc/SKILL.md) | Draft, calibrate and review an architecture document from upstream sources. | Deterministic scaffold, closing-gate checker and golden case. |
| [Session Insights](skills/super-session-insights/SKILL.md) | Fact-bound usage reports from local session stores; reflection on authorized material. | Synthetic-store wiring suite; reflection contract checks. |
| [ASD-STE100](skills/super-asd-ste100/SKILL.md) | Rewrite agent-facing English under ASD-STE100-derived structural rules. | Pinned upstream (SHA-256); deterministic `ste-lint.py` gate. |
| [Archify](skills/super-archify/SKILL.md) | Turn a system, codebase, or Mermaid sketch into an interactive architecture diagram. | Upstream v3.2.0 sync (git tag + SHA-256); finalize/validate gates. |
| [Lavish](skills/super-lavish/SKILL.md) | Turn responses into reviewable HTML; browser annotations return to the agent. | Locked upstream release (SHA-256 + npm pins); integrity tests. |
| [Imagegen](skills/super-imagegen/SKILL.md) | Run prepared image-generation requests through the machine's already-installed private `azhou-imagegen` skill; without that skill or its doctor gate, the package fails closed. | Contract-only package; baseline hashes pinned; fails closed. |
| [Rederive](skills/super-rederive/SKILL.md) | Practice understanding code by re-deriving its design. | Pinned upstream (SHA-256); exploratory observation only. |
| [i-have-adhd](skills/super-i-have-adhd/SKILL.md) | Shape output for ADHD readers: next action first, bounded steps. | Frozen upstream (SHA-256); verbatim body; integrity tests. |
| [Gh Axi](skills/super-gh-axi/SKILL.md) | Run GitHub operations through an agent-ergonomic wrapped CLI. | Locked upstream release (SHA-256 + npm pins); integrity tests. |
| [Diagram Design](skills/super-diagram-design/SKILL.md) | Create branded editor-grade HTML/SVG diagrams across 51 visual types, with .drawio/Mermaid/.excalidraw/PlantUML import. | Vendored upstream (commit pin + per-file SHA-256); packaged `self_check.py` gate. |
| [Frontend Design](skills/super-frontend-design/SKILL.md) | Produce a distinctive, non-templated visual design direction for a new UI or a restyle: palette, typography, layout, and the avoid-the-AI-defaults review pass. | Faithfully adopted from anthropics/skills at the pinned commit with the upstream guidance body preserved verbatim, the Apache-2.0 license vendored byte-identical, and SHA-256 integrity tests. No behavior benchmark yet. |
| [Brainstorming](skills/super-brainstorming/SKILL.md) | Hold the pre-build conversation: find out what the reader wants and why, lay out approaches, write the design doc, and enforce the approval gate. | Adapted from obra/superpowers at the pinned tag with six recorded deltas, per-file upstream SHA-256 anchors, and integrity tests. No behavior benchmark yet. |
| [Grill Me](skills/super-grill-me/SKILL.md) | Grill the user about a plan, decision, or idea in rounds: every settled question asked with a recommended answer, facts looked up, decisions left to the user. | Adapted from mattpocock/skills at the pinned tag; upstream trigger sentences kept verbatim; instruction body verbatim outside one sentence; SHA-256 integrity tests. No behavior benchmark yet. [Claude Code host check](evidence/super-grill-me-host-check-claude-2026-11-24.md). |

[Per-skill platform view](docs/skill-platform-view.md) · [Evaluation contract](docs/eval-case-contract.md)

### Try it

https://github.com/user-attachments/assets/35c1a361-d494-437f-ad6c-0049f6828fd3

In the results below, a *hold* is an explicitly flagged unresolved item, and a *stable receipt* is the checkable record of what a run produced.

| Skill | Copy this into your agent | What must come back |
|---|---|---|
| Super Repo Pedant | <code>This phase is done. Run super-repo-pedant reconcile.</code> | Reconciled knowledge surfaces, named checks, explicit holds and a stable receipt. [Run the demo](docs/demos/super-repo-pedant.md). |
| Excalidraw Diagram | <code>Use super-excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.</code> | Editable <code>.excalidraw</code>, a real render/export, deterministic gates, visual review status and a stable receipt. [Run the demo](docs/demos/super-excalidraw-diagram.md). |
| Arch Doc | <code>Use super-arch-doc to draft this repository's architecture document from its upstream design docs.</code> | Research notes with per-fact provenance, a template scaffold with accounted diagram captions, PlantUML-only diagrams, deterministic closing gates and a stable receipt. [Run the demo](docs/demos/super-arch-doc.md). |

## Why trust it

- **Current behavior beats stale prose.** Code, machine configuration and real execution evidence define current truth; unimplemented specs stay visible as reminders.
- **Claims have gates.** The authoritative repository gate runs the complete deterministic test suite — repository policy, the retired-surface reverse scan, Hub unit tests, package manifest/lifecycle suites and every registered benchmark-integrity and wiring-integrity suite — plus whitespace checks.
- **Harness differences stay visible.** The maintained targets are Codex, Claude Code, MiMo Code (`mimo`), DeepSeek Harness (`dsh`) and zcode; other harnesses are temporarily unsupported. See the [support matrix](docs/support-matrix.md) and the [per-skill platform view](docs/skill-platform-view.md).
- **History cannot silently rewrite a live skill.** Promotion requires the mandated regression cases and deterministic checks to pass, a paired-majority review (an odd number of same-judge paired comparisons, at least three, must prefer the candidate by majority), no safety regression, and human approval bound to the exact diff.
- **Sources remain attributable.** Upstream snapshots, vendored assets and excluded unlicensed prior art are recorded in [third-party notices](THIRD_PARTY_NOTICES.md).

![Azhou AI Hub: the documented verification command and a recorded local result.](assets/github/readme-proof.png)

The [evaluation-case contract](docs/eval-case-contract.md) defines the minimum behavior evidence a package may claim.

## Foundation CLI

Each adapter delegates to the checkout's zero-dependency Foundation CLI, so the commands below run from a clone of this repository — the checkout-assisted route, distinct from the package-manager installs above ([checkout-assisted setup](docs/installation.md#checkout-assisted-setup)). [Codex discovery](docs/installation.md#check-codex-discovery) · [Foundation CLI contract](docs/foundations.md)

| Agent Skill | CLI authority | Change boundary |
|---|---|---|
| `super-azhou-info` | `info`, `version` | Read-only project, runtime, Git revision and dirty-state facts. |
| `super-azhou-doctor` | `doctor` | Read-only repository, explicit install-target, optional Treehouse lease and host stale-install migration diagnostics. With `--verify`, the verification subprocess has a 10-minute deadline and reports the last output line if available. |
| `super-azhou-setup` | `setup`, `repair`, `migrate`, `uninstall` | Dry-run first. Setup binds apply to the reviewed plan; repair, migrate and uninstall recheck current state when applied. |
| `super-azhou-verify` | `verify` | Runs the reproducible public repository-integrity gate: a Foundation setup JSON result captured in the gate output makes the verdict red when it is malformed, truncated, or records a status other than `pass` or `dry_run`. |

~~~bash
python scripts/azhou_hub.py info --json
python scripts/azhou_hub.py version --json
python scripts/azhou_hub.py doctor --json
python scripts/azhou_hub.py setup --skill super-repo-pedant --target /absolute/path/to/harness/skills --json
python scripts/azhou_hub.py verify
~~~

## Integrations

Optional integrations live under `packages/`. These projects are not Skills, and installing a Hub Skill does not enable any integration. A **candidate** below is a maintained source version not yet accepted as a full release; its evidence is the dated receipts in the [support matrix](docs/support-matrix.md#optional-integrations), never a release claim.

| Entry | Complete project package | Current boundary |
|---|---|---|
| `azhou-agent-inspector` | [Azhou Agent Workbench](packages/azhou-agent-inspector/README.md) | Codex conversation panel and ZCode composer status with a conversation dashboard. Both panels show turn duration and speed and let you expand available details, including context usage when the host supplies a measured request and its window. Workbench 0.12.12 follows the system reduced-motion preference. Install through each host's plugin manager. [Desktop verification by version](docs/support-matrix.md#azhou-agent-workbench). |
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | `pstack-azhouzhou` 0.15.43 **candidate**: native Codex/Claude plugins, a zcode plugin with bundled skills, and shared Skills discovery for MiMo and DeepSeek Harness (the maintainer host's shared-root pstack links were retired on 2026-11-14; serving pstack that way moves to a separately scoped task, and other skills sharing the root are unaffected). Dated evidence and limits: [support matrix](docs/support-matrix.md#optional-integrations). |


[Azhou mouse cursors 3.6.1](assets/cursors/azhou-double-hug/README.md) are available as a standalone Mousecape theme for macOS. The guide covers downloading, applying and restoring the system cursors.

Run these from a clone of this repository, as above:

~~~bash
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
~~~


[Integration runbook](docs/integrations.md) · [Provenance](docs/integration-provenance.md) · [Support matrix](docs/support-matrix.md#optional-integrations)

### Retired surfaces

Retired surfaces, their last supported versions, and what installed users do now:

- **Agent Skin** is retired for Codex, DSH and previously retired ZCode. See the [installed-user exit guide](docs/decisions/agent-skin-retirement.md).
- **Agent Orchestration Kit (model router)** — never released publicly. This entry is only for machines that still carry a private testing install: recover the Kit's own uninstaller from Git history or the old releases, and uninstall with it before installing pstack.
- **Legacy `codex-startup-animation` package** — last version `0.7.1/build 8`, removed 2026-11-12. Git history retains the legacy source.
- **Azhou Codex Pet** — retired 2026-11-18. See the [retirement record](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/evidence/azhou-pet-retirement-2026-11-18.md).

[HUB-RET-001](docs/decisions/hub-retirement-physical-deletion.md) records the cut; [provenance rows](docs/integration-provenance.md) locate each pre-deletion revision, and all old releases and tags remain in full.

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

The [Azhou Skill Standard](docs/skill-standard.md) is the single project authority; [Architecture](docs/architecture.md) explains the boundaries and [governance](GOVERNANCE.md) the decisions.

## Develop

In Codex, `$refactoring` applies refactoring guidance to a change and `$release-it` reviews failure recovery; the 14 [book-inspired skills](THIRD_PARTY_NOTICES.md#agent-rules-books) ship with the repository under `.agents/skills/` — project-local, not among the 21 installable packages under `skills/` — and load their rules on demand.

Python 3.11+ is enough for the repository gate:

~~~bash
python scripts/verify.py
~~~

## Project

[Docs](docs/README.md) · [Principles](docs/principles.md) · [Roadmap](docs/roadmap.md) · [Changelog](CHANGELOG.md) · [Release process](docs/releasing.md) · [Security policy](SECURITY.md) · [Support](SUPPORT.md) · [Contributing](CONTRIBUTING.md)

## License

Azhou-maintained code: [MIT](LICENSE). Azhou artwork: [CC BY-NC-ND 4.0](assets/azhou/NOTICE.md). Name, logo and character: [TRADEMARKS.md](TRADEMARKS.md). Third-party components retain their own notices and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

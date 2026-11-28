# 🦊 Azhou AI Hub

Give your agent a skill to draw diagrams, explain complex ideas, or review code. Install the skills you need one at a time. The Azhou Source Library collects articles and updates from official AI sources.

[简体中文](README.zh-CN.md) · [Find skills](https://tefuirnever.github.io/azhou-ai-hub/skills/) · [Install Ask Azhou](#install-ask-azhou) · [Browse the Source Library](https://tefuirnever.github.io/azhou-ai-hub/library/)

## Install Ask Azhou

Start with Ask Azhou if you are unsure which skill to use. It recommends a skill for your task, which you can install when you need it.

### Let your agent install

Open an agent session in your project and paste this install prompt. Your agent checks whether it can already find Ask Azhou before installing it.

> Follow https://github.com/TeFuirnever/azhou-ai-hub/blob/main/docs/installation.md#install-with-an-agent to install only super-ask-azhou in this project and check that this host discovers it.

<details>
<summary>Install manually</summary>

[Choose your agent host](docs/installation.md#choose-your-agent-host). To install a different skill with Skills CLI, see [package-manager install](docs/installation.md#package-manager-install).

### First install in Codex

Sign in to Codex. Run this from your project with Node.js 22.20 or later, then confirm the project install when prompted.

~~~bash
npx skills add https://tefuirnever.github.io/azhou-ai-hub/downloads/super-ask-azhou.tgz --agent codex
~~~

</details>

<a name="try-it-in-codex"></a>

### Try Ask Azhou

Open a new chat in the same project. Ask your agent to use `super-ask-azhou` for the question below. In Codex, paste the example as written. Ask Azhou should recommend `super-archify`.

> `$super-ask-azhou` I have a Mermaid diagram and want to turn it into an interactive architecture diagram. Which Hub Skill should I use?

[Install Archify](https://tefuirnever.github.io/azhou-ai-hub/skills/#super-archify) · [Find an installed skill](docs/installation.md#check-that-your-host-finds-the-skill) · [Update or uninstall](docs/installation.md#upgrade-or-uninstall)

## Skills

[Search skills by task](https://tefuirnever.github.io/azhou-ai-hub/skills/) or start with a [worked example](#worked-examples).

<details>
<summary>All 21 installable packages</summary>

| Skill | What it helps you do |
|---|---|
| [Azhou Info](skills/super-azhou-info/SKILL.md) | Check this Hub checkout, its version, and support information. |
| [Azhou Doctor](skills/super-azhou-doctor/SKILL.md) | Find out why a local Hub installation is not working, without modifying it. |
| [Azhou Setup](skills/super-azhou-setup/SKILL.md) | Plan, install, update, or remove a skill from a local Hub checkout. |
| [Azhou Verify](skills/super-azhou-verify/SKILL.md) | Run the full repository verification suite. |
| [Super Repo Pedant](skills/super-repo-pedant/SKILL.md) | Check that docs, rules, and handoff notes match what shipped. |
| [Excalidraw Diagram](skills/super-excalidraw-diagram/SKILL.md) | Draw an editable Excalidraw diagram and export it as SVG or PNG. |
| [Eli5](skills/super-eli5/SKILL.md) | Explain a difficult idea with a self-contained HTML visual. |
| [Ask Azhou](skills/super-ask-azhou/SKILL.md) | Describe your task and get a skill recommendation. |
| [Arch Doc](skills/super-arch-doc/SKILL.md) | Draft or review an architecture document using upstream sources. |
| [Session Insights](skills/super-session-insights/SKILL.md) | Summarize usage and patterns in authorized local agent sessions. |
| [ASD-STE100](skills/super-asd-ste100/SKILL.md) | Rewrite agent instructions in controlled English using ASD-STE100 rules. |
| [Archify](skills/super-archify/SKILL.md) | Turn a system, plan, or codebase into an interactive HTML map. |
| [Lavish](skills/super-lavish/SKILL.md) | Make agent output reviewable in HTML and send annotations back. |
| [Imagegen](skills/super-imagegen/SKILL.md) | Run a prepared image request when the private azhou-imagegen skill is already available. |
| [Rederive](skills/super-rederive/SKILL.md) | Understand a codebase by working through how its design could be derived. |
| [i-have-adhd](skills/super-i-have-adhd/SKILL.md) | Put the next action first and give ADHD readers fewer steps at once. |
| [Gh Axi](skills/super-gh-axi/SKILL.md) | Use an agent-oriented CLI for GitHub operations. |
| [Diagram Design](skills/super-diagram-design/SKILL.md) | Design HTML or SVG diagrams, or import draw.io, Mermaid, Excalidraw, and PlantUML. |
| [Frontend Design](skills/super-frontend-design/SKILL.md) | Choose and review a visual direction for a new or redesigned interface. |
| [Brainstorming](skills/super-brainstorming/SKILL.md) | Explore an idea and agree on the design before building it. |
| [Grill Me](skills/super-grill-me/SKILL.md) | Stress-test a plan by working through one decision at a time. |

</details>

Repo Pedant's [evolution safeguards](skills/super-repo-pedant/references/evolution-contract.md) stop identity-dependent actions when Git configuration changes the project identity, reject foreign identities in local state for global proposals, and stop proposals if explicitly included signal files are unavailable.

### Worked examples

- [Draw a login sequence](docs/demos/super-excalidraw-diagram.md) and get an editable file and PNG.
- [Draft an architecture document](docs/demos/super-arch-doc.md) from upstream sources.
- [Check a repository before handoff](docs/demos/super-repo-pedant.md) and see what still needs attention.

## Agent Rules Books

Use engineering books to guide design, refactoring, and reviews. [Browse the 14 rules](docs/agent-rules-books.md) · [Install a rule](docs/installation.md#install-agent-rules-books)

<details>
<summary>Install a single rule manually in Codex</summary>

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

</details>

## Integrations

- [Azhou Agent Workbench](packages/azhou-agent-inspector/README.md) shows turn duration and speed in Codex and ZCode.
- [pstack](packages/pstack-agent-harness/README.md) provides engineering and review workflows. See its [current support status](docs/support-matrix.md#optional-integrations).
- [Azhou mouse cursors](assets/cursors/azhou-double-hug/README.md) are a standalone Mousecape theme for macOS.

<details>
<summary>Integration support details</summary>

| Entry | Package | Current support |
|---|---|---|
| `azhou-agent-inspector` | [Azhou Agent Workbench](packages/azhou-agent-inspector/README.md) | Codex conversation panel and ZCode composer status with a conversation dashboard. Both panels show turn duration and speed and let you expand available details, including context usage when the host supplies a measured request and its window. Workbench 0.12.13 follows the system reduced-motion preference. Install through each host's plugin manager. [Verification and open checks by version](docs/support-matrix.md#azhou-agent-workbench). |
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | `pstack-azhouzhou` 0.15.43 **candidate**: native Codex/Claude plugins, a zcode plugin with bundled skills, and shared Skills discovery for MiMo and DeepSeek Harness (the maintainer host's shared-root pstack links were retired on 2026-11-14; serving pstack that way moves to a separately scoped task, and other skills sharing the root are unaffected). Dated evidence and limits: [support matrix](docs/support-matrix.md#optional-integrations). |

</details>

<a name="retired-surfaces"></a>

## Project

- [Install and maintain skills](docs/installation.md) · [Get help or report a bug](SUPPORT.md) · [Check a skill by agent host](docs/skill-platform-view.md)
- [Documentation index](docs/README.md) · [Skill Standard](docs/skill-standard.md) · [Contribute](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)
- [Verification basis](docs/skill-evidence.md) · [Security](SECURITY.md) · [Retired tools](docs/architecture.md#retired-surfaces)

<details>
<summary>Developer commands (Foundation CLI)</summary>

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

See the [complete deterministic test suite](docs/foundations.md#commands) and [verification basis](docs/skill-evidence.md).

</details>

## License

Azhou-maintained code: [MIT](LICENSE). Azhou artwork: [CC BY-NC-ND 4.0](assets/azhou/NOTICE.md). Name, logo and character: [TRADEMARKS.md](TRADEMARKS.md). Third-party components retain their own notices and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

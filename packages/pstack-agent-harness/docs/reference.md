# pstack reference

Start with the [README](../README.md) for installation and your first task.

## Slash commands

The package includes 65 skill directories: 41 public skills and 24 `principle-*` references. Claude Code uses `/pstack:<name>`. In Codex, request a skill by name or install the [optional shortcuts](#codex) for the `/name` form below. ZCode and MiMo Code discover project skills from the roots listed in the [README](../README.md#zcode) and [MiMo Code section](../README.md#mimo-code); host-specific invocation syntax is not part of Hub acceptance.

Find each skill's instructions in the [skills tree](../plugins/pstack/skills/).

| command | use it when |
| --- | --- |
| `/poteto-mode` | default entry point for any non-trivial task |
| `/how` | walk through how a subsystem works |
| `/why` | investigate why something was built this way (parallel multi-MCP evidence) |
| `/architect` | settle types and module shape before writing code that crosses a function boundary |
| `/arena` | run N parallel attempts at the same task and pick the best parts |
| `/interrogate` | have three different models try to break a diff |
| `/automate-me` | draft your own personal -mode skill from recent transcripts |
| `/reflect` | capture a long task's lessons as a skill edit |
| `/correct` | find the mistakes agents keep repeating in a repo and make each one impossible, enforced at the highest level that works |
| `/tdd` | fix a bug by writing the failing test first, then the fix |
| `/benchmark-checklist` | vet a measured speedup or regression (limiter, tuning, errors, repeat runs, end-to-end relevance) before you report or act on it |
| `/typescript-best-practices` | ground type-system discipline in TypeScript syntax |
| `/teach` | explain a subsystem plainly by composing how + why |
| `/swarm` | fan out N parallel workers across slices or races, then return one aggregated report |
| `/technical-writing` | write docs, RFCs, readmes, PR descriptions, and commit messages to one layered standard |
| `/bro` | restate the last message in plain human language, no jargon |
| `/in-your-own-words` | play back your goal and the problem before the agent starts |
| `/sharpen` | aim a task at what you are really after, the way a top expert would, without overspecifying it |
| `/figure-it-out` | design a rigorous, auditable playbook for a task no bundled playbook fits |
| `/show-me-your-work` | log decisions to a reviewable tsv decision trail |
| `/blast-radius` | find what a change could break beyond the diff and prove safety by running code |
| `/recall` | catch up on recent working context from chat history, live state, and the shared record |
| `/ketchup` | catch up on everything in this chat since your last message, with an executive summary for each action item |
| `/setup-pstack` | configure pstack per-role model choices |
| `/poteto-help` | answer a question about pstack with the prompt to send and the file the answer came from |
| `/unslop` | clean up writing by removing AI tells |
| `/no-comments` | strip comments before review, fix the accepted findings, encode claimed constraints |
| `/create-verification-skill` | generate a project-local verification skill and feature map |
| `/maintain-verification-skill` | re-sync a drifted verification skill and its feature map |
| `/create-formal-verification-skill` | generate a project-local skill that formally verifies one high-risk property |
| `/maintain-formal-verification-skill` | re-sync a formal verification after the code it covers changed |
| `/deslop` | deslop a diff before commit |
| `/babysit` | monitor an open PR, fix CI/comments, keep it merge-ready |
| `/thermo-nuclear-review` | audit a branch's changes for bugs, breakage, security issues, devex regressions, and feature-gate leaks |
| `/thermo-nuclear-code-quality-review` | extremely strict maintainability audit |
| `/thermos` | run both thermo-nuclear reviews as parallel subagents and synthesize their findings |
| `/make-pr-easy-to-review` | clean noisy history and improve PR description before review |
| `/fix-ci` | find failing PR checks, inspect logs, apply focused fixes |
| `/fix-merge-conflicts` | non-interactively resolve merge conflicts, validate, finalize |
| `/get-pr-comments` | fetch and summarize review comments from the active PR |
| `/what-did-i-get-done` | summarize authored commits over a user-chosen period |

## Runtime support

All four maintained runtime installs use [one skills tree](../plugins/pstack/skills/). Codex and Claude Code use native plugins with Hub-maintained mappings. ZCode and MiMo Code use project-scoped skills only. Their host-specific tools, multi-model delegation, and automatic hooks are not verified. Imported adapters for other harnesses remain source material and do not establish Hub support.

The local package commands use the absolute Hub source path set as `PSTACK_PACKAGE` in the [README](../README.md#install). Only Codex is Hub-managed; Claude Code uses its native marketplace, and ZCode/MiMo Code use project skill roots.

| Runtime | Setup and Hub support boundary |
| --- | --- |
| Claude Code | Add the absolute `$PSTACK_PACKAGE` path as a marketplace and install `pstack` (Claude Code 2.1.292 or later). Its native plugin includes the Claude tool mapping and routing hook. |
| Codex | Use the Hub pstack plan, apply, and doctor commands with a dedicated `CODEX_HOME`, then trust the hook through `/hooks`. The default Codex home remains owned by Agent Orchestration Kit. See the [Codex mapping](../plugins/pstack/skills/poteto-mode/references/codex-tools.md). |
| ZCode | Link skills from the absolute Hub package into the project `.agents/skills/` root. This is a skills-only install; the local model-sheet mapping is documented with limited evidence in [setup-pstack](../plugins/pstack/skills/setup-pstack/SKILL.md#other-runtimes). |
| MiMo Code (`mimo`) | Link skills from the absolute Hub package into the project `.mimocode/skills/` root. This is a skills-only install; choose the session model through MiMo Code's native settings and catalogue. |

### Automatic routing

The Claude Code and Codex plugins load the same short [routing instruction](../plugins/pstack/hooks/session-start-context.md) on startup, resume, clear, and compact. The [POSIX hook](../plugins/pstack/hooks/session-start.sh) runs on Claude Code and POSIX Codex. On Windows, Codex uses a [PowerShell adapter](../plugins/pstack/hooks/session-start.ps1) through its `commandWindows` override and does not require Bash. The adapter runs with `-ExecutionPolicy Bypass`, which a machine or user execution policy set by Group Policy overrides; on such machines the hook fails and no instruction loads. Codex requires the user to trust plugin hooks through `/hooks`. The instruction invokes `poteto-mode` when a task meets any of these conditions:

- It touches more than one file or changes a signature other files call.
- It involves a design or architecture choice.
- It concerns a bug with an unknown cause or a performance issue.

Smaller tasks proceed directly. The full skill loads when invoked, and explicit user instructions take precedence.

To disable routing, run `setup-pstack` and turn off the session hook. In Claude Code, use `/pstack:setup-pstack`. You can also write `session hook: off` in the runtime's sheet, at the path in [setup-pstack's runtime table](../plugins/pstack/skills/setup-pstack/SKILL.md#other-runtimes). The Claude Code and Codex hooks read that setting before injecting their instruction. ZCode and MiMo Code project-skill installs do not include a pstack hook; invoke `poteto-mode` explicitly.

### Shared skills installation

The default project-scoped roots are `.agents/skills/` and `.mimocode/skills/`; see the [ZCode](../README.md#zcode) and [MiMo Code](../README.md#mimo-code) install instructions. They link directly to `$PSTACK_PACKAGE/plugins/pstack/skills/` and preserve existing entries.

An optional user-wide `~/.agents/skills/` root can be read by every runtime that discovers it, including runtimes with an isolated `CODEX_HOME`. This can expose the linked skills across projects and harnesses; the project roots above remain the default. Choose one workflow owner for each task.

### Manage linked skills

The project-skill link loops in the README skip existing files, directories, and links, preserving user entries.

When the Hub package changes, linked skills follow the source automatically; rerun the relevant project loop to link new skill directories. To remove a skill, inspect the entry and remove only a symlink in `.agents/skills/` or `.mimocode/skills/` whose target is inside `$PSTACK_PACKAGE/plugins/pstack/skills/`. For the optional shared root, removal affects every runtime using that directory.

### Codex

The [native plugin manifest](../plugins/pstack/.codex-plugin/plugin.json) points to the shared skills directory and the Codex [SessionStart hook](../plugins/pstack/hooks/codex-hooks.json). The [marketplace catalog](../.agents/plugins/marketplace.json) lists `pstack` in the `pstack-claude` marketplace. Review and trust the hook through `/hooks`; Codex asks again when its definition changes.

For Hub-managed Codex installation, use the [Hub integration commands](../../../docs/integrations.md#pstack-local-source-to-native-plugin). They apply the local package to an explicit dedicated `CODEX_HOME`, preserving an existing default configuration such as Agent Orchestration Kit. The integration doctor is the installation check for this route.

OpenAI documents [marketplace registration and the plugin format](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli). If your CLI lacks `plugin add`, use the plugin browser after registering the marketplace.

Request `poteto-mode` by name or select its entry, such as `pstack:poteto-mode`. To enable parallel subagents:

```toml
[features]
multi_agent = true
```

Add this setting to `$CODEX_HOME/config.toml` if subagents are disabled in the dedicated home selected for the Hub integration. Skills such as `arena`, `interrogate`, and `architect` use parallel agents. The [mapping](../plugins/pstack/skills/poteto-mode/references/codex-tools.md) describes a sequential fallback and translates Claude tool names, model defaults, and verification instructions.

For optional slash-command shortcuts, set `CODEX_HOME` to the same dedicated Hub home and link the prompts from the absolute package source:

```shell
: "${CODEX_HOME:?Set CODEX_HOME to the dedicated pstack configuration directory}"
: "${PSTACK_PACKAGE:?Set PSTACK_PACKAGE to the absolute Hub package directory}"
mkdir -p "$CODEX_HOME/prompts"
for c in "$PSTACK_PACKAGE"/plugins/pstack/.codex-plugin/prompts/*.md; do
  target="$CODEX_HOME/prompts/${c##*/}"
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    ln -s "$c" "$target"
  fi
done
```

Each shortcut invokes its skill. The commands skip existing files and links. Remove a shortcut from `$CODEX_HOME/prompts/<name>.md`. Both native-plugin and skills-only installations work without these shortcuts.

### Pi
Historical imported adapter; outside current Hub support. The Pi package manifest, extension, and tool mapping remain in this repository as source material. Earlier port checks do not establish Hub 0.9.103 acceptance. This section provides no Pi installation, update, or removal instructions.

### GitHub Copilot
Historical imported adapter; outside current Hub support. Its manifests, hooks, mappings, and smoke-test source remain in this repository as source material. Earlier port checks do not establish Hub 0.9.103 acceptance. This section provides no Copilot installation, update, or removal instructions.

### Muse
Historical imported adapter; outside current Hub support. Its manifest, hooks, and tool mapping remain in this repository as source material. Earlier port checks do not establish Hub 0.9.103 acceptance. This section provides no Muse installation, update, or removal instructions.

## Configuration and dependencies

Invoke [setup-pstack](../plugins/pstack/skills/setup-pstack/SKILL.md) to choose models for each role on Codex, Claude Code or ZCode. Its [runtime table](../plugins/pstack/skills/setup-pstack/SKILL.md#other-runtimes) records sheet paths and evidence limits. MiMo Code uses its native model settings; no pstack sheet or hook is verified there. Defaults live in [models.json](../plugins/pstack/models.json). For comparisons and reviews, choose distinct models actually available in the current session.

Install dependencies for the workflows you use:

| Dependency | When you need it |
| --- | --- |
| GitHub CLI, `gh` | PR monitoring, shipping, and the `orch` stack frontier. Authenticate with `gh auth login`. Playbooks use Origin's CLI, `origin`, instead when it can resolve the repository. |
| Bun | The bundled `watch-pr` and `orch` scripts. Their bootstrap installs script dependencies on first run. |
| `plugin-dev` | Claude Code skill-authoring guidance used by `automate-me`, `reflect`, and `poteto-mode`. |

Install the Claude Code skill-authoring companion with:

```text
/plugin marketplace add anthropics/claude-plugins-official
/plugin install plugin-dev@claude-plugins-official
```

Those authoring workflows need `plugin-dev` for their guidance; other workflows do not. Codex uses the equivalents in its [mapping](../plugins/pstack/skills/poteto-mode/references/codex-tools.md#driver-and-bundled-skills-pstack-references).

Playbooks use the session's task tools or an uncommitted `todo.md` checklist; see [platform adaptation](../plugins/pstack/skills/poteto-mode/SKILL.md#platform-adaptation). Use [create-verification-skill](../plugins/pstack/skills/create-verification-skill/SKILL.md) to record the project's verification commands, following the [driver policy](../plugins/pstack/skills/poteto-mode/SKILL.md#non-negotiables).

## Maintenance

### Repository layout

```text
.claude-plugin/marketplace.json    Claude Code marketplace
.agents/plugins/marketplace.json  Codex marketplace
package.json                      Pi package manifest
plugins/pstack/
  .claude-plugin/plugin.json      Claude Code plugin manifest
  .codex-plugin/                  Codex manifest and generated prompt stubs
  .github/plugin/plugin.json      GitHub Copilot plugin manifest
  .muse-plugin/plugin.json        Muse native plugin manifest (skill list generated)
  pi/                            Pi extension (subagent, question, and wake-up tools)
  skills/                        Shared skills, references, and scripts
  agents/                        Claude Code subagent definitions (Muse agent definitions too)
  hooks/                         Startup routing for Claude Code, Codex, Copilot, and Muse; Copilot tool checks
tools/                           Generation, validation, and upstream sync
tests/                           Repository checks
```

Skills-only installs use `plugins/pstack/skills/`. Agent references and license files are included under `poteto-mode/references/`.

### Generated files and checks

The [generator](../tools/generate.mjs) updates versions, model defaults, Codex prompts, Copilot and Muse preambles and role lists, the Muse manifest's skill list, and portable reference files, and validates the Pi package manifest. The [slash-command table](#slash-commands) supplies the Codex prompt descriptions and order. Edit that table when changing a menu description, then regenerate. Keep a row for every public skill, with `poteto-mode` first.

[Documentation fact tests](../tests/readme-facts.test.mjs) check the skill counts and upstream pin. The table parser requires the header `| command | use it when |`.

Run the generator and repository tests with Bun:

```shell
bun install --frozen-lockfile
bun tools/generate.mjs
bun test tests/ --path-ignore-patterns '**/tests/pi/**'
```

The install step reads the root `bun.lock` and fetches `typebox`, which the Pi extension and its tests import.

CI also checks shell scripts, workflows, Markdown, relative links, and the bundled Bun tools. See [local checks](../CONTRIBUTING.md#things-that-will-fail-ci) for commands and [release instructions](../CONTRIBUTING.md#releasing) for versioning and the live Claude Code command check.

### Port scope and attribution

The skill tree is synced against upstream `7b353f7` (v0.15.27 and later). The thermos skills and agents are synced against `118e73b` (thermos 1.0.0).

This repository ports Lauren Tan's pstack from Cursor to Claude Code and shares the skills with other runtimes. It includes six cursor-team-kit skills, the three thermos skills with their two review subagents, and an independently authored `babysit` skill. The port supplies Claude Code plugin registration and routing, Codex manifests and shortcuts, the Codex tool mapping, the Pi package, extension, and tool mapping, the GitHub Copilot hooks and tool mapping, and the Muse native plugin, routing hook, and tool mapping.

Cursor-specific automations, sticky-mode metadata, the Grok Bot UI workflow, and the Cursor UI tutorial are excluded. [tools/upstream.json](../tools/upstream.json) records the revisions and exclusions, [tools/substitutions.json](../tools/substitutions.json) holds the Cursor-to-Claude rewrite rules, and [CHANGES.md](../CHANGES.md) records each release. The bundled `thermo-nuclear-code-quality-review` provides a maintainability review when a workflow calls for one, `thermo-nuclear-review` a correctness and security audit, and `thermos` runs both as parallel subagents.

For skill changes, follow the [sync boundary](../CONTRIBUTING.md#the-sync-boundary). Runtime adaptations and workflow changes both land here, and a workflow change is declared as a fork.

See the [license summary](../README.md#license) for licenses and full-plugin attribution. [NOTICE-skills.md](../NOTICE-skills.md) is the notice for skills-only installations.

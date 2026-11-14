# pstack for Codex, Claude Code and ZCode

Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack), shipped for three runtimes. The source is pristine upstream plus a quilt patch queue; nothing under `pstack/` or `components/` is edited by hand. [UPSTREAM.md](UPSTREAM.md) records the sources, the queue and the pending work.

The proposed `resume.mjs` checkpoint helper is not shipped. Its [storage reference](hub-skills/poteto-mode/references/resume-storage.md) documents a design, not an available command.

## Layout

| Directory | What it is |
| --- | --- |
| `pstack/` | Pristine `cursor/plugins/pstack` at the commit in `hub-package.json` |
| `components/cursor-team-kit/` | The six cursor-team-kit skills pstack's workflows name, pristine |
| `components/thermos/` | The three thermos skills and both review agents, pristine |
| `hub-skills/` | Skills this Hub authors (`babysit`, the runtime reference docs) |
| `hub-adapters/` | Harness adapter documents beyond upstream's Claude Code one |
| `hub-runtime/` | The session hooks and their shared scripts |
| `patches/` | One DEP-3 patch per upstream defect, applied in `patches/series` order |
| `harness/pstack/<runtime>/` | Built trees. Committed so the package reads without a build |

## Build

```sh
node tools/build-harness.mjs
```

The build assembles the sources into a scratch tree, applies the patch queue, runs upstream's own `generate-pstack-harness-trees.mjs` unmodified, then emits the Codex plugin surface and assembles the hooks. It fails rather than reports success when a patch applies but changes none of the files it declares, which is also the signal that upstream carries the fix and the patch should leave the queue.

## Install

Set `PSTACK_PACKAGE` to the **absolute path** of this package before
running the host-specific commands.

**Claude Code** (2.1.292 or later):

```sh
: "${PSTACK_PACKAGE:?Set PSTACK_PACKAGE to the absolute Hub package directory}"
claude plugin marketplace add "$PSTACK_PACKAGE"
claude plugin install pstack-azhouzhou@azhou-hub --scope user
```

Refresh with `claude plugin marketplace update azhou-hub` and
`claude plugin update pstack-azhouzhou@azhou-hub`; remove with
`claude plugin uninstall pstack-azhouzhou@azhou-hub`. The marketplace was
renamed from `pstack-claude` to `azhou-hub` on 2026-11-12; installs made
under the old name keep working but refresh through the name their own
registration recorded, then migrate at the next reviewed upgrade.

**Codex** uses the Hub integration commands in
[docs/integrations.md](../../docs/integrations.md), which install from
`harness/pstack/codex` into a **dedicated** `CODEX_HOME`. The live
ChatGPT Desktop default `~/.codex` contains native-owned data that the Hub
installer deliberately refuses to adopt. Use that Codex build's native
plugin manager for such a home; see the
[measured Desktop receipt](../../evidence/chatgpt-desktop-native-plugin-install-2026-11-04.md).
A successful plugin listing is not a live invocation or hook trust receipt.

**ZCode** installs one plugin surface. The generated `zcode-plugin/`
marketplace carries 41 commands **and the 68 bundled skills**, declared by
the `skills` manifest pointer using the same root-level convention as the
host's official github, zcode-guide and visualize plugins, so no
shared-root or project-local skill links are needed on ZCode. With the
ZCode CLI on PATH, install through the native manager:

```sh
: "${PSTACK_PACKAGE:?Set PSTACK_PACKAGE to the absolute Hub package directory}"
zcode plugins marketplace add "$PSTACK_PACKAGE/harness/pstack/zcode-plugin"
zcode plugins install pstack-azhouzhou@azhou-hub
zcode commands list
zcode skills list
```

Installs made before 0.15.38 served the 68 skills through the shared user
root `~/.agents/skills`; the bundled build removes that dependency, and
those links can be deleted once the reinstall is verified.

Native command listing and skill discovery do not by themselves prove GUI
invocation, though after the 2026-11-14 app restart a real GUI session
loaded a bundled skill from the installed payload
([receipt](../../evidence/zcode-plugin-bundled-skills-2026-11-14.md)); a
full bundled command→skill workflow run and ZCode plugin SessionStart hook
delivery are not claimed.

Configure per-role models with `/setup-pstack`; the sheet lives at `~/.claude/pstack-models.md` on Claude Code and `<codex-home>/pstack-models.md` on Codex. All licenses are MIT; the notices under `NOTICE*.md` and `LICENSE-*` cover the three upstream sources.

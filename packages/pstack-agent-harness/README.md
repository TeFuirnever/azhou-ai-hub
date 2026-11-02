# pstack for Codex, Claude Code and ZCode

Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack), shipped for three runtimes. The source is pristine upstream plus a quilt patch queue; nothing under `pstack/` or `components/` is edited by hand. [UPSTREAM.md](UPSTREAM.md) records the sources, the queue and the pending work.

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

**Claude Code** (2.1.292 or later):

```sh
claude plugin marketplace add "$PWD"
claude plugin install pstack@pstack-claude --scope user
```

Refresh after package updates with `claude plugin marketplace update pstack-claude` and `claude plugin update pstack@pstack-claude`; remove with `claude plugin uninstall pstack@pstack-claude`.

**Codex** uses the Hub integration commands in [docs/integrations.md](../../docs/integrations.md), which install from `harness/pstack/codex` into a dedicated `CODEX_HOME`.

**ZCode** links the skills into a project's `.agents/skills/` root; no plugin or hook installs. Run from the project root, with `PSTACK_PACKAGE` set to this package's absolute path. Existing files, directories and links stay untouched:

```shell
: "${PSTACK_PACKAGE:?Set PSTACK_PACKAGE to the absolute Hub package directory}"
SRC="$PSTACK_PACKAGE/harness/pstack/zcode/skills"
test -d "$SRC" || { printf '%s\n' "no zcode skills at $SRC" >&2; exit 2; }
mkdir -p .agents/skills
for source in "$SRC"/*/; do
  skill="${source%/}"; target=".agents/skills/${skill##*/}"
  [ -e "$target" ] || [ -L "$target" ] || ln -s "$skill" "$target"
done
zcode skills list --cwd "$(pwd -P)"
```

The final command needs a `zcode` CLI on PATH; it is what proves the host discovered the links.

Configure per-role models with `/setup-pstack`; the sheet lives at `~/.claude/pstack-models.md` on Claude Code and `<codex-home>/pstack-models.md` on Codex. All licenses are MIT; the notices under `NOTICE*.md` and `LICENSE-*` cover the three upstream sources.

# ZCode bundled-skills plugin install and shared-root link retirement — 2026-11-14

Records the host-side closeout of PR #471 (squash `fcf2606b`, Hub distribution
`0.15.38`, quilt patch `0024`): installing the bundled-skills ZCode plugin on
the maintainer host and deleting the 66 shared-root skill symlinks that build
replaced. This is installation, file-identity and CLI-discovery evidence. It
is not a GUI invocation receipt, a SessionStart hook-trust receipt, or a
complete pstack task run.

## Inputs

- Installed plugin id: `pstack-azhouzhou@azhou-hub`, local directory
  marketplace `azhou-hub` resolving the `zcode-plugin/` tree inside the
  maintainer checkout (`known_marketplaces.json`, source-validated
  2026-11-03).
- ZCode CLI `0.17.1` (bundled `zcode.cjs`; no PATH shim on this host).
- Prior state: `0.15.36` installed and enabled, commands-only payload, 41
  command files; 66 ordinary-name symlinks in `~/.agents/skills` pointing at
  `packages/pstack-agent-harness/harness/pstack/skills-root/skills/`
  (restored 2026-11-14 under PR #468 after the drift window).

## Actions (all 2026-11-14)

1. `zcode plugins marketplace update azhou-hub` — refreshed (1 plugin).
2. `zcode plugins update pstack-azhouzhou@azhou-hub` —
   `Updated plugin pstack-azhouzhou@azhou-hub from 0.15.36 to 0.15.38.
   Restart zcode to apply.`
3. File-level verification of the install: `installed_plugins.json`:
   `pstack-azhouzhou@azhou-hub` `0.15.38`, install path
   `~/.zcode/cli/plugins/cache/azhou-hub/pstack-azhouzhou/0.15.38`, enabled.
   Cache payload root carries exactly: `.zcode-plugin/`, `commands/` (41
   command files), `skills/` (68 skill directories), `agents/`, `docs/`
   (`guide/` + `harness/zcode.md`), `README.md`, `LICENSE`,
   `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`,
   `NOTICE-skills.md`; `.zcode-plugin/plugin.json` declares
   `commands: "commands"` and `skills: "skills"` at version `0.15.38`.
4. Pre-deletion discovery verification with the 66 shared-root links still
   present: `zcode skills list` already showed the plugin entries
   `pstack-azhouzhou:<name> (user/plugin; alias <name>)` resolving inside the
   0.15.38 cache payload. Plugin-bundled discovery was verified before the
   deletion, so no undiscoverable window existed.
5. Deleted exactly the symlinks in `~/.agents/skills` whose `readlink` target
   contains `pstack-agent-harness`, after a pre-delete count check: listed 66,
   deleted 66, remaining links 14 (shuohao novel-family and Hub `super-*`
   skills), pstack-pointing links 0.

## Verified after deletion

- `zcode skills list`: all 68 plugin-namespaced skills still discovered as
  `pstack-azhouzhou:<name> (user/plugin; alias <name>)` resolving inside the
  0.15.38 cache payload; the deleted `user/agents` symlink duplicates are
  gone; `tdd` and `teach` are reachable under the plugin namespace (the
  shared root could never link them due to name collisions).
- `zcode commands list`: 46 custom commands registered; the 41 pstack
  commands resolve to `…/0.15.38/commands/<name>.md`.
- `plugins list` reports the plugin `[enabled]` with `skills: 68`.
- `find ~/.agents/skills -maxdepth 1 -type l ! -exec test -e {} \;` → 0
  broken links.

## Boundaries

- The long-running GUI app still holds the pre-update registration in memory
  until restart; the CLI evidence above spans the pre-deletion and post-
  deletion probes and is post-update and cache-backed, and the post-deletion
  state is link-less. GUI invocation of the bundled command→skill chain on
  0.15.38 was not re-probed in this pass; the 2026-11-14 GUI receipt remains
  the evidence for the command→skill chain on the link-served form.
- The stale `0.0.0`/`0.15.36` cache directories are host-managed leftovers;
  they were not touched.
- Bundled upstream prose that still describes cursor-team-kit/thermos as
  external plugins is pre-existing upstream staleness (byte-identical at the
  base commit of #471) and rides the quilt patch queue as a separately scoped
  task; the hub-authored zcode adapter resolves delegate paths into the
  payload.

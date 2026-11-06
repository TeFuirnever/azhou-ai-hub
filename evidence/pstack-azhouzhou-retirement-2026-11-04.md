# pstack-azhouzhou retirement sweep receipt (2026-11-04)

Scope: stage AZ5 of the pstack-azhouzhou plugin-fabric plan. One evidence-first sweep retired every install still named `pstack` on the maintainer's Mac and closed the record. The Claude registration had already been replaced by `pstack-azhouzhou@pstack-claude` on 2026-11-02; this sweep removed what the rename left behind.

Baseline before the sweep, each from a command line.

- Claude Code: `claude plugin list` reports `pstack-azhouzhou@pstack-claude` and no old-name registration. Stale artifacts remained: `~/.claude/plugins/cache/pstack-claude/pstack/0.15.36` (7.3M) and `pstack/0.9.103` (3.5M) from the pre-rename Hub distribution, and `~/.claude/plugins/cache/cursor-plugins/pstack/0.15.25` (3.3M) and `0.15.29` (3.3M) from upstream cursor/plugins.
- Default Codex home: `codex plugin list --json` reports only `pstack-azhouzhou@pstack-claude` (0.15.36), installed natively on 2026-11-04 ([install receipt](chatgpt-desktop-native-plugin-install-2026-11-04.md)).
- ZCode: `zcode plugins list` reports only `pstack-azhouzhou@azhou-hub` (0.15.36, enabled).
- DeepSeek Harness: no plugin by design ([fabric receipt](dsh-plugin-fabric-2026-11-03.md)); `find ~/.dsh -name "*pstack*"` finds nothing.
- `~/pstack-accept-tmp` (48M) still held the superseded AZ1 accept home, whose `config.toml` registered the old `pstack@pstack-claude` against its own frozen snapshot.

Removals, each with its evidence line.

- `~/pstack-accept-tmp` — the whole accept home, removed per plan after AZ2 superseded it. Its `config.toml` was the last file on this machine registering `pstack@pstack-claude`.
- `~/.claude/plugins/cache/pstack-claude/pstack/0.15.36` and `0.9.103` — pre-rename Hub distribution caches.
- `~/.claude/plugins/cache/cursor-plugins/pstack/0.15.25` and `0.15.29` — upstream cursor/plugins pstack caches.

On "original pstack". No install named `pstack` that this Hub did not build was registered anywhere at sweep time, so upstream pstack had no separate uninstall target. Its residue was exactly the two cursor cache copies above, removed as artifacts; the registered `cursor-plugins` marketplace and its checkout remain, carrying upstream source trees rather than installs.

After the sweep, each from a command line.

- `claude plugin details pstack-azhouzhou@pstack-claude` reports the new name with its inventory: 68 Skills, 4 agents, 1 SessionStart hook. `installed_plugins.json` and `known_marketplaces.json` contain no `pstack@` string.
- `codex plugin list --json` reports only `pstack-azhouzhou@pstack-claude` among 23 plugins; `config.toml` registers `[plugins."pstack-azhouzhou@pstack-claude"]` and no old-name plugin block.
- `zcode plugins list` reports only `pstack-azhouzhou@azhou-hub` among 12 plugins.
- DSH stays parked: no plugin exists or is claimed, and no `pstack`-named artifact exists under `~/.dsh`.
- Skills root invariant: `~/.agents/skills` holds 164 entries, the 68 skills-root-tree pstack skills all present, and every directory resolves a `SKILL.md`. The links stay: they carry no plugin name.
- Stray search across every home registry (Claude `installed_plugins.json` / `known_marketplaces.json`, Codex `config.toml`, ZCode registries, DSH profiles) finds no remaining `pstack` registration string in manifest position.

Query-time probe, combined install-state queries per host, three runs each side.

- Claude `plugin list` median 0.14s before, 0.12s after. Codex `plugin list` median 1.69s before, 1.30s after. ZCode `plugins list` median 0.69s before, 0.59s after. DSH profile listing is instantaneous on both sides. Every after-median is within 1.2x of before.

Observed, recorded, outside this sweep's scope.

- ZCode cache `azhou-hub/pstack-azhouzhou/0.0.0/0.15.36` is the nested copy from the pre-flattening bundle iteration; it carries the current name and stays until a zcode cache lifecycle pass.
- The ZCode `azhou-probe` marketplace with its `hello-probe` package is AZ3 probe residue under a different name.
- `~/.zcode/cli/artifacts/` session transcripts quote historical old-name strings; they are session history, not registrations.

Not claimed. No end-to-end poteto-mode workflow run was part of this sweep: the codex quota was exhausted until 15:01 the same day and the sweep ran inside an AZ5 working session. The program's start signal on the Claude host is live in that session (the SessionStart mandate is injected), and the invocation lane stays with the AZ2 session receipt. No remote or second machine was swept.

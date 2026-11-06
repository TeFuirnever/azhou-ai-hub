# ChatGPT desktop native plugin install receipt (2026-11-04)

Scope: stage AZ2 of the pstack-azhouzhou plugin-fabric plan. The plugin is installed into the default `~/.codex`, the home the ChatGPT desktop app reads, by Codex's own plugin manager. Everything below was measured on the maintainer's Mac with the desktop-bundled `codex-cli 0.166.0-alpha.5.1`.

Why native direct rather than the Hub installer. `python scripts/azhou_hub.py integrations pstack plan` refuses this target at its no-adoption gate: of 6289 inventoried entries, 4608 are unowned across 78 top-level subsystems, including the app's own `plugins/` cache (1120 files), `vendor_imports/` (815), `memories/`, `sessions/`, and user configuration such as `hooks.json`, `keybindings.json`, `agents/*.toml`, and `RTK.md`. That gate is the installer's design, not a defect: a live desktop home can never be a Hub-owned target. This home is therefore deliberately installed outside Hub ownership, recorded here instead. A separate measured finding: the gate's error message joins `unexpected[:8]`, which showed 8 names of 4608 and read like a six-file cleanup; the truncation hid the real scale.

Preconditions cleared. ChatGPT was fully quit (`pgrep -x ChatGPT` empty) and two unheld stale sockets were removed before the run: `~/.codex/ipc/ipc.sock` and `~/.codex/vendor_imports/skills/.git/fsmonitor--daemon.ipc` (both confirmed with `lsof` to have no holder).

Pre-state. `~/.codex/plugins/cache/` held `compact-adviser`, `openai-bundled`, `openai-curated`, `openai-curated-remote`, `openai-primary-runtime`. `config.toml` sha256 `9fff92a0ab90ef83f02aceb382b3c0fea32f9f5f06cec06cfc3d99128024e380`, no `pstack` lines.

Install commands, each with `CODEX_HOME=$HOME/.codex`.

- `codex plugin marketplace add <repo>/packages/pstack-agent-harness --json` returned `{"marketplaceName": "pstack-claude", "installedRoot": "/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness", "alreadyAdded": false}`.
- `codex plugin add pstack-azhouzhou@pstack-claude --json` returned `{"pluginId": "pstack-azhouzhou@pstack-claude", "name": "pstack-azhouzhou", "marketplaceName": "pstack-claude", "version": "0.15.36", "installedPath": "/Users/guanxueliang/.codex/plugins/cache/pstack-claude/pstack-azhouzhou/0.15.36", "authPolicy": "ON_INSTALL"}`.

Post-state, each from a command line.

- `codex plugin list --json` reports `pstack-azhouzhou@pstack-claude | enabled: True | version: 0.15.36` alongside the app's own plugins.
- `config.toml` gained `[marketplaces.pstack-claude]` with `source = "/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness"` (line 374 block) and `[plugins."pstack-azhouzhou@pstack-claude"]` (line 411 block).
- The cache copy at `plugins/cache/pstack-claude/pstack-azhouzhou/0.15.36` carries `.codex-plugin/plugin.json`, 41 `prompts/` files, `hooks/` with `session-start.sh` and `codex-hooks.json`, and `skills/` with 68 entries. The codex tree ships skills by design; the plugin registers them namespaced alongside the shared `~/.agents/skills` root.

Ownership status. No Hub receipt, no doctor, no Hub removal for this home: it is native-owned state like any plugin a user installs. Revert is native and complete: `codex plugin remove pstack-azhouzhou@pstack-claude` followed by `codex plugin marketplace remove pstack-claude`, both with `CODEX_HOME=$HOME/.codex`. Stage AZ5 retirement must use these same native commands here rather than the Hub installer.

Not claimed. SessionStart hook delivery (the host's `/hooks` review decides trust), command or skill invocation inside a live ChatGPT desktop session (pending the user's fresh-session receipt), and any behavior of the npm `@openai/codex 0.160.1` CLI, which was not used for this install.

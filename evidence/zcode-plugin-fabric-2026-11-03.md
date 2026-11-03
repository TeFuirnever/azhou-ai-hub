# ZCode plugin fabric receipt (2026-11-03)

Scope: stage AZ3 of the pstack-azhouzhou plugin-fabric plan. One emitter in `tools/build-harness.mjs` packages a commands-only ZCode plugin from the same source that writes the Codex prompts. Everything below was measured against zcode 0.17.1 through the bundled CLI on this host.

Probe findings, each from a command line.

- `zcode plugins marketplace add <local dir>` accepts a local directory. The marketplace entry must carry no `source` object at all: the installer's source-kind switch supports `github`, `git`, `url` with `type: zip`, and `git-subdir`, rejects `npm` and `pip` by name, and only when no source object is present falls back to the plugin directory that sits beside the marketplace.json. An entry with `source: {source: local}` fails at install with `plugin_marketplace_invalid` (observed, then decoded from the zcode bundle).
- The plugin directory must be flat. With a version layer inside the bundle the installer nests it under its own `0.0.0` cache folder and finds no manifest. Flat layout installs at the manifest's own version: `cache/azhou-hub/pstack-azhouzhou/0.15.36`.
- The `commands` manifest pointer is proven by the official `android-emulator` plugin, whose command files are markdown with a `description` frontmatter and an instructional body. The `hooks` field has no sample in the installed official cache and stays out of the emitter, recorded here as the omission.

Install results.

- `pstack-azhouzhou@azhou-hub` installed and enabled at version 0.15.36, 41 command files cached.
- `zcode commands list` resolves `/architect` with its full description, sourced from the plugin cache path, so the command surface is user-invocable.
- The plugin ships no skills by design (`skills: 0`), because ZCode already serves the 68 pstack skills from the shared user root. The skills-list scope check shows the poteto-mode entry at `(user/agents)` and no plugin-scoped duplicate.
- Lifecycle: `plugins disable` removes `/architect` from `commands list` (count 0), `plugins enable` restores it. Two full remove-and-reinstall cycles during development exercised the uninstall and reinstall path.
- The build is idempotent: two consecutive full builds hash identical (`4c57a8de9e662942` over every file under `harness/`), and the repository gate `python scripts/verify.py` passes with the emitter in place.

Not claimed: GUI-session invocation of a command (the operator's ZCode session was busy; the command's registration is CLI-verified), SessionStart hook delivery through a ZCode plugin (no proven declaration format), and update-in-place semantics beyond remove and reinstall.

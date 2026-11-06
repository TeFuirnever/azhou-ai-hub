# DSH plugin fabric probe receipt (2026-11-03)

Scope: stage AZ4 of the pstack-azhouzhou plugin-fabric plan. The probe ran against DeepSeek Harness 0.2.1-rc.5 through the bundled `dsh` CLI. It closes AZ4 on the plan's parked exit: the emitter is not built, and this receipt records the measured reason.

Probe findings, each from a command line.

- `dsh plugin --profile <name> add <local package>` runs pnpm inside a profile directory under `~/.dsh/profiles/<name>/`, which is a pnpm workspace with `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `cordis.patch.yml`, and a `.plugin-manager` state directory.
- Adding a package without a `dsh.bundle` field produces the verbatim warning `declares no dsh.bundle — installed as a plain dependency, not a profile layer`, and registers nothing beyond `node_modules`.
- The bundle contract, decoded from `@deepseek-ai/dsh-plugin-manager` and `@deepseek-ai/dsh-app-boot` inside the app archive, is a package.json `dsh.bundle` object whose `patch` field names one cordis patch file or an ordered list. A bundle contributes patch layers to the profile's `cordis.patch.yml` overlay stack, that is, desktop app behavior patches. Optional shipped bundles add only an `icon` and `./locale/*.json` display metadata on top. A real sample ships at `@deepseek-ai/dsh-agent-preset/skills/cordis-plugin-development/templates/decoration/package.json` with `dsh.bundle: {"patch": "./cordis.patch.yml"}`.
- No field of the bundle contract carries skills, slash commands, or hooks. DSH serves skills exclusively through its ranked discovery roots, where the 68 pstack skills already resolve from `~/.agents/skills` (receipt `evidence/deepseek-skill-discovery-2026-11-02.md`).

Conclusion. The pnpm plugin surface registers cordis patch layers and nothing our payload uses. A pstack-azhouzhou bundle would be a package whose patch does nothing for skills or commands, so the emitter is parked rather than shipped. The probe artifacts, one throwaway profile and one minimal package, were removed after the run.

Revisit trigger. If a future DSH bundle contract grows a command or skill registration field, AZ4 reopens with this receipt as the baseline.

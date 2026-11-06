# Agent Skin DSH plugin live-install receipt (2026-11-05)

Scope: installing the assembled `azhou-agent-skin` package into a throwaway DSH profile through the official plugin manager, on the maintainer machine, against the installed DeepSeek Harness desktop 0.2.1-rc.5. This receipt supersedes the install-path boundary of the [assembly receipt](dsh-agent-skin-assembly-2026-11-05.md); in-host rendering remains unverified and unclaimed. Every claim names the command that produced it.

## How the bundled CLI runs

The `dsh` CLI ships inside the application archive with no PATH link. It runs through the Electron binary's node mode:

```sh
ELECTRON_RUN_AS_NODE=1 "/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness" \
  "/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js" \
  plugin --profile azhou-skin-verify <subcommand>
```

The invocation needs `node` and `pnpm` on PATH; the runtime at `~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/` provides both (`node` v24.21.0, `pnpm` v11.1.2). The command's `--help` documents `dsh plugin --profile <name> <subcommand>` and profile boot.

## Verified, each from a command line

- Install. `plugin --profile azhou-skin-verify add <absolute package dir>` links the package via pnpm and registers it. The profile's `package.json` afterwards carries `dependencies["azhou-agent-skin"]` as a `link:` dependency and `dsh.profile.bundles` lists `["@deepseek-ai/dsh-base", "azhou-agent-skin"]`. No hand edits were made to any profile file.
- Inventory. `plugin --profile azhou-skin-verify list` reports `azhou-agent-skin@link:…` as the profile's one dependency.
- Clean removal. `plugin --profile azhou-skin-verify remove azhou-agent-skin` restores the baseline exactly: `dependencies` disappears and `dsh.profile.bundles` returns to `["@deepseek-ai/dsh-base"]`.
- Re-install convergence. A second `add`, this time from the stable copy at `~/azhou-agent-skin-candidate/azhou-agent-skin`, succeeds identically. The throwaway profile now links the stable path, so recycling the build worktree cannot break it.
- Composition. `--profile azhou-skin-verify --dump-config` prints the composed boot stack and contains the layer header `# == azhou-agent-skin` followed by the insert row `- id: azhou-agent-skin` from the package's `cordis.patch.yml`. The same output warns that the user-level home patch references skins this profile does not install (`ui-skin-maid-atelier`, `ui-skin-orca-link`, `ui-skin-deep-whale-manager`); the warnings are expected for a throwaway profile and do not involve this package.

The throwaway profile `azhou-skin-verify` is left installed and bootable for the visual round. The production `desktop` profile was not modified; its bundle list is unchanged.

## Not performed, not claimed

No profile was booted. In-host behavior remains unverified: module loading of `client.js` in the real DSH web client, the sidebar entry, wallpaper on the real main surface, theme following, the IndexedDB namespace on the real origin, and Plugin Manager display of the title, description, and icon. The visual round boots the profile (`dsh --profile azhou-skin-verify` or the same invocation through the Electron binary), observes those surfaces, and records its own receipt; skin acceptance there is a human visual call.

# Local ownership handoff of three optional projects — 2026-10-26

Scope: one maintainer machine, macOS 27.0.1 arm64. This is an installation and local-source closeout record, not redistribution, host playback, wallpaper or visual acceptance. The unlicensed startup program and private art remain outside public release authority.

## Source and recovery

- The canonical project packages were already under `packages/`. Their three former local checkouts (`codex-startup-animation`, `pstack-agent-harness`, `agent-orchestration-kit`) were removed only after the checks below.
- The former startup checkout's Git history and uncommitted files, 1,010 local evidence files (890,899,521 bytes), 61 Pet-state files, 41 build-review files, two review helper sources and all nine private art/input files were preserved under ignored Hub local state. The copied evidence, Pet-state, review and private-input files were compared by relative path and SHA-256 before deletion. The old module cache and compiled build payload were not retained; the Hub package was rebuilt.
- Complete archives of the former pstack and orchestration-kit checkouts, including `.git`, were placed in the same ignored recovery directory and read back successfully. The orchestration kit's local-only Git commits remain recoverable from that archive.
- Recovery location on this machine: `.local/orphan-recovery/2026-10-26/` at the Hub root. Private startup build inputs remain in the package's ignored `assets/private/`; selected Pet candidates remain in its ignored `.local/pets/`.

## Native installation results

| Surface | Action and observed result |
| --- | --- |
| Agent Orchestration Kit | Ran `setup.sh` from the Hub package; zero files changed because the user installation already matched. A second Hub `--dry-run` after deleting the old checkout passed with zero changes, choosing the Codex CLI bundled with the app (`0.164.0-alpha.11.1`). |
| pstack | Bundled Codex CLI `plugin list --json` reported 22 installed plugins, none named pstack or sourced from the three former checkouts. There was no active pstack plugin to relocate. |
| Startup App build | Ran `bash tools/build-macos.sh` from the final Hub package path. Native artifact verification, private-input check, plist check and ad-hoc code-sign verification passed. Published payload SHA-256 tree: `7111d2aa0701b77b594c4ace6bc90179d23f5bc1912a285a4b7d7ecf57555d86`. |
| Startup App handoff | Before replacement, the old receipt, old payload and installed App all matched SHA-256 tree `2a2831efa487d88f86c4f91aacc7448042179764c6e959aa0dd7ecb9123ce467`. The Hub installer took over the exact entry with `--migrate-from`; a final `--check`, including after the old checkout was deleted, returned `current`, one installed project App, zero `dist` Apps and one registered project URL. The installed receipt names the final Hub package root and records both fingerprints in `sourceHandoff`. |
| Codex Pet handoff | The Hub selected candidate, old selected candidate and installed package matched theme revision `916ed5e9bfb47d99770f65f6d9954ceaa52057150edfb124c25a89272ca772ae`, atlas SHA-256 `bbd296d914e44eaf3306519006d635c90687a9dcc318559ac66b32561e890a04` and manifest SHA-256 `b4fc418c87d5211e57e47a8322aff861d781ad09d428fb706549c0644be12a3e`. Native `handoff` returned `handed-off`; final `status` after old-checkout deletion reported `bytesVerified`, `matchesCurrentTheme` and `matchesSelectedPackage` true. Runtime remains `pending-refresh-selection`. |

The three former directory paths were checked absent after removal. The obsolete Codex trust entry for the old startup checkout was removed; the Hub entry remained trusted and the TOML parsed successfully. A symlink scan of the user Codex, Agent Skills and Applications locations found no links to the former checkouts.

## Verification and remaining boundaries

- Hub `python3 scripts/verify.py` passed after the handoff code and documentation changes: 582 Hub unit tests, 42 model-router tests, 26 installer lifecycle tests, package manifests, policy and benchmark wiring.
- Pet manager tests passed 43/43; importer tests passed 14/14. An independent review found and reproduced a candidate-selection race; the old and Hub project locks plus an install-time digest check closed it. The same interleaving then failed with `source-conflict` and preserved the old installed bytes.
- Native App build and replacement were exercised on the maintainer machine. The isolated installer suite mocks codesign, filesystem exchange and registration; the final native `--check` supplies the live installed-state evidence.
- No Codex restart, cold launch, wallpaper application, Pet selection/playback or formal visual review was performed. These observations cannot be inferred from package and installed-byte checks. The adapter's general production install/uninstall plans remain blocked; the one-time native handoff is narrower.

The implementation and contract change landed locally as `31b4c88` (`feat(startup): hand off verified local app and Pet installs`). This record describes local state and is not a claim that another machine has the same installation.

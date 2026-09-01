# Foundation discovery/invocation receipt — zcode — 2026-09-01

This receipt records a redacted real-host check that the zcode host discovers and invokes the four Foundation Agent Skills packages. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `bc17fe1c260c2e789c8ee7e4a0be31ac434ace17` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (run via the ZCode.app 3.10.2 bundle), Node.js 24.15.0
- Python: 3.14.7
- Mode: disposable checkout, project-scope Agent Skills root (`.agents/skills`), linked install via the neutral Foundation CLI, headless non-interactive model runs (`zcode -p`, GLM-5.1 via the BigModel Coding Plan), attempt-1 per run

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill azhou-info --skill azhou-doctor --skill azhou-setup --skill azhou-verify \
  --target <checkout>/.agents/skills --mode link --apply --plan-id <dry-run planId> --json
~~~

- Dry-run `planId`: `7896c024d36b90f0b71cee479ab4d320c9f80cd5c9a2b7151a1eb70a59eaec28`; apply exit `0`; all four skills linked. The same `planId` reproduced byte-for-byte on a second disposable checkout of the same commit, confirming the plan digest is deterministic.

## Results

| Check | Result | Evidence |
|---|---|---|
| Project-scope linked install of the four packages | `PASS` | Foundation CLI apply receipt: exit 0, four linked entries under the checkout's project skills root; deterministic `planId`. |
| Host discovery | `PASS` | `zcode skills list` (exit 0) listed all four skills with scope `project/agents`, each resolved to its `SKILL.md` under the checkout's `.agents/skills` root. |
| azhou-info invocation | `PASS` | `info --json` returned `schema_version` `azhou-ai-hub.info.v1`. |
| azhou-info invocation (second route) | `PASS` | `version --json` returned `schema_version` `azhou-ai-hub.version.v1`. |
| azhou-doctor invocation | `PASS` | `doctor --json` returned `schema_version` `azhou-ai-hub.doctor.v1`, `status` `healthy`. |
| azhou-setup invocation (read-only dry-run, no `--apply`) | `PASS` | `azhou-info` reported `current`; new `planId` emitted, nothing applied. |
| azhou-verify invocation | `PASS` | Full gate `python3 scripts/azhou_hub.py verify` exited `0` with final line `verification passed`. The disposable checkout carried one disclosed working-tree-only change: `/.agents/` appended to `.gitignore` so the repository policy scanner would not abort on the untracked project skills root; packages, Foundation CLI and gate code stayed at the recorded commit. |

### Invocation prerequisite (authorized, minimal, recorded)

Headless `zcode -p` requires an explicit user-level model provider in the zcode CLI config. With workspace-owner authorization recorded 2026-09-01, the minimal `provider.bigmodel` entry plus `model.main` were added to the user-level zcode CLI config; the entry reuses the account's existing `zcode-api-key` (no new key was minted) and the before/after config diff is recorded redacted outside Git. Nothing else in the config changed.

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout.
2. Dry-run then apply `azhou_hub.py setup` for the four skills into `<checkout>/.agents/skills`.
3. Run `zcode skills list --cwd <checkout>` and check the four names appear with scope `project/agents`.
4. Run the two documented-invocation prompt runs recorded in the results table.

## Claim boundary

This proves zcode 0.16.5 discovers project-scoped linked installs of the four Foundation packages and runs their documented read-only invocations and the full verification gate on this machine. It does not prove GUI-surface behavior or parity with any other host. Raw run artifacts stay Git-external; nothing private is committed.
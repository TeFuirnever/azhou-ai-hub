# Foundation discovery/invocation receipt — Claude Code — 2026-09-01

This receipt records a redacted real-host check that Claude Code discovers and invokes the four Foundation Agent Skills packages. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `14e0bebed2619cfcbf6fd79df3537b742deed70b` (disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Python: 3.14.7
- Node.js: 24.15.0
- Host CLI: Claude Code `2.1.239` (`claude --version`)
- Mode: disposable checkout, project-scope Agent Skills root (`.claude/skills`), linked install via the neutral Foundation CLI, headless non-interactive runs, attempt-1 per run

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill azhou-info --skill azhou-doctor --skill azhou-setup --skill azhou-verify \
  --target <checkout>/.claude/skills --mode link --apply --plan-id <dry-run planId> --json
~~~

- Dry-run `planId`: `de265019c8c76d669310bd80cf92a206ae1cdb8b70b6b467dfdfc7f1b11f61ac`; apply exit `0`; all four skills linked.

## Results

| Check | Result | Evidence |
|---|---|---|
| Project-scope linked install of the four packages | `PASS` | Foundation CLI apply receipt: exit 0, four linked entries under the checkout's project skills root. |
| Host discovery | `PASS` | A headless `claude -p` run named `azhou-info`, `azhou-doctor`, `azhou-setup` and `azhou-verify` as invocable skills. |
| azhou-info invocation | `PASS` | `info --json` returned `schema_version` `azhou-ai-hub.info.v1`. |
| azhou-info invocation (second route) | `PASS` | `version --json` returned `schema_version` `azhou-ai-hub.version.v1`. |
| azhou-doctor invocation | `PASS` | `doctor --json` returned `schema_version` `azhou-ai-hub.doctor.v1`, `status` `healthy`. |
| azhou-setup invocation (read-only dry-run, no `--apply`) | `azhou-info` reported `current`; new `planId` emitted, nothing applied. |
| azhou-verify invocation | `PASS` | Full gate `python3 scripts/azhou_hub.py verify` exited `0` with final line `verification passed`. |

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout.
2. Dry-run then apply `azhou_hub.py setup` for the four skills into `<checkout>/.claude/skills`.
3. Run one headless `claude -p` run per check group, as recorded above.

## Claim boundary

This proves that Claude Code 2.1.239 discovers project-scoped linked installs of the four Foundation packages and runs their documented read-only invocations and the full verification gate on this machine. It does not prove personal-root installs, interactive sessions, every harness-specific install path, or parity with any other host. Raw run artifacts stay Git-external; nothing private is committed.
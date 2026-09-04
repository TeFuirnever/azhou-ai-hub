# Foundation discovery/invocation receipt — Codex — 2026-09-04

This receipt records a redacted real-host check that the Codex CLI host discovers the four Foundation Agent Skills packages and runs their documented read-only invocations and the full verification gate. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `7d16d6da321745b0fec8657c85d8b226e7755e12` (merged `main`; disposable Git checkout at a temporary path)
- Host: macOS, arm64
- Host: Codex CLI `codex-cli 0.152.0`, model `gpt-5.6-sol` (reasoning effort `xhigh`), logged in with the existing account
- Python: 3.14 (checkout default)
- Mode: disposable checkout, user-scope Agent Skills root (`~/.agents/skills`, linked install resolving to the recorded main content), headless non-interactive model runs (`codex exec -s workspace-write`), attempt-1 per run

## Results

| Check | Result | Evidence |
|---|---|---|
| Host skill discovery | `PASS` | One headless run asked the host to list its available Agent Skills packages by name; the reply listed all four Foundation packages (`azhou-info`, `azhou-doctor`, `azhou-setup`, `azhou-verify`) plus the other seven canonical packages of this repository. The host merges multiple skill roots, so some non-repository names appeared duplicated; no claim is made about which root won for duplicated non-repository entries. |
| azhou-info invocation | `PASS` | Documented invocation `python3 scripts/azhou_hub.py info --json` executed in the checkout by the host run; exit code `0`, `schema_version` `azhou-ai-hub.info.v1`. |
| azhou-doctor invocation | `PASS` | Documented invocation `python3 scripts/azhou_hub.py doctor --json`; exit code `0`, `schema_version` `azhou-ai-hub.doctor.v1`, `status` `healthy`. |
| azhou-setup invocation (read-only dry-run, no `--apply`) | `PASS` | The planning command ran without `--apply` against the already-managed skills root and failed closed exactly as designed: a conflict plan with `applied: false` and a deterministic `planId` was emitted, exit code `1`, nothing applied, tracked files untouched. |
| azhou-verify invocation | `PASS` | Full gate `python3 scripts/azhou_hub.py verify` executed in the checkout by the host run; exit code `0`, final line `verification passed`. |

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout.
2. Run one `codex exec` session asking for the available Agent Skills package names.
3. Run four `codex exec` sessions prompting the documented read-only invocations above (`info`, `doctor`, setup dry-run without `--apply`, `verify`) and record exit codes.

## Claim boundary

This proves the Codex CLI 0.152.0 host lists the four Foundation packages on its skill-discovery surface from the user-scope linked root on this machine, and that their documented read-only invocations and the full verification gate run inside headless `codex exec` sessions. It does not prove interactive TUI behavior, which root the host prefers when several provide the same name, or parity with any other host. Raw session logs stay Git-external; nothing private is committed.

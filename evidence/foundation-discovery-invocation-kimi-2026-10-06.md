# Foundation discovery/invocation receipt — Kimi Code — 2026-10-06

This receipt records a redacted real-host check that the Kimi Code CLI host lists the canonical Agent Skills packages of this repository on its model-visible skill-discovery surface and runs the documented read-only `info` invocation headlessly. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `88309db53707ff5ce77a4597c0918b859ff5269e` (merged `main`; disposable Git checkout at a temporary path)
- Host: macOS, arm64
- Host: Kimi Code CLI `2.1.1`, default model `kimi-code/k3` (thinking effort `high`), logged in with the existing account
- Python: 3.14 (checkout default)
- Mode: disposable checkout, user-scope Agent Skills root (`~/.agents/skills`, linked install resolving to the recorded main content), headless non-interactive model runs (`kimi --skills-dir ~/.agents/skills -p`), attempt-1 per check

## Results

| Check | Result | Evidence |
|---|---|---|
| Host skill discovery (partial) | `PASS` with a recorded omission | Two independent headless runs asked the host to enumerate its loaded Agent Skills packages without reading project files (the second with an explicit no-truncation instruction). Both runs listed thirteen of the fourteen canonical packages of this repository (`arch-doc`, `autoresearch`, `azhou-doctor`, `azhou-info`, `azhou-setup`, `azhou-verify`, `eli5`, `excalidraw-diagram`, `session-insights`, `super-caveman`, `super-lavish`, `super-llm-wiki`, `super-repo-pedant`) from the user-scope linked root, among the roughly ninety names each run printed. A targeted follow-up probe confirmed the host reports `ask-azhou` as not loaded in that session although the package is present in the passed root; the cause was not diagnosed and is recorded as an observed limitation, not explained. No claim is made about the non-repository names the shared root also exposes. |
| azhou-info invocation | `PASS` | Documented invocation `python3 scripts/azhou_hub.py info --json` executed by a headless host run in the checkout; the run reported exit code `0`, `schema_version` `azhou-ai-hub.info.v1` and 14 installable skills. A direct deterministic re-run of the same command in the same checkout reproduced the exit code, schema and count. |

## Reproduction

1. Check out the repository at the recorded commit into a disposable checkout.
2. Run one `kimi --skills-dir ~/.agents/skills -p` session asking the host to enumerate every loaded Agent Skills package name without reading project files; record the printed names.
3. Run one `kimi --skills-dir ~/.agents/skills -p` session prompting the documented read-only invocation `python3 scripts/azhou_hub.py info --json` and record the reported exit code, schema and count.
4. Re-run the same command directly in the checkout to confirm the host-reported values.

## Claim boundary

This proves the Kimi Code CLI 2.1.1 host exposes thirteen of the fourteen canonical packages on its model-visible skill-discovery surface from the user-scope linked root on this machine, with `ask-azhou` absent from that surface in all recorded runs, and that the documented read-only `info` invocation runs inside a headless `kimi -p` session in a disposable checkout. It does not prove interactive TUI behavior, hook surfaces, MCP transports, per-package SKILL.md load replay, or the `doctor`, `setup` and `verify` invocations on this host, and no claim is made about them; the host's local UserPromptSubmit hook injection stays a host-local configuration and is outside this receipt's claims. Raw session logs stay Git-external; nothing private is committed.

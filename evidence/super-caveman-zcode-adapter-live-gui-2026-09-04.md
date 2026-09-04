# Super Caveman zcode adapter live GUI firing receipt — 2026-09-04

This receipt records a redacted real-host check that the zcode 0.16.5 GUI host fires the canonical `zcode_adapter` hooks live: the SessionStart event creates adapter session state and the UserPromptSubmit event runs the documented stop-phrase state machine end to end. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Adapter: canonical `skills/super-caveman/scripts/zcode_adapter.py` at local default-branch commit `99857f4` (revision-e04ba7c3 tree), user-scope linked install
- Host: macOS arm64, zcode `0.16.5` GUI (the ZCode desktop host), user-scope hook registration in `~/.zcode/cli/config.json`
- Install step: `zcode_adapter.py setup --scope user` (exit 0; two owned registrations beside the pre-existing unrelated hooks, `hooks.enabled` already true, no other entry touched); persistent defaults layer intentionally left unset so sessions stay neutral unless explicitly enabled
- Mode: two real interactive GUI sessions on 2026-09-04, attempt-1 each

## Results

| Check | Result | Evidence |
|---|---|---|
| SessionStart hook fires in the GUI host | `PASS` | Adapter session state `super-caveman.adapter-state.v1` appeared under the project's `.azhou/super-caveman/sessions/` for a GUI session with `stopped: false` and that session's `session_id` — the fresh-session write of the `render` handler. The session had started before the hooks were registered and the host still picked them up. |
| UserPromptSubmit hook fires and runs the state machine | `PASS` | A second GUI session, after one plain prompt, sent the documented stop phrase; adapter state for that session's `session_id` recorded `stopped: true` with the exact schema fields — the stop branch of the `prompt` handler. |
| Adapter reuse stays single-source | `PASS` (structural) | Both state files carry the canonical `super-caveman.adapter-state.v1` schema written by the shared `claude_adapter` handlers; no duplicate capsule or state code exists in the zcode adapter. |

## Related negative on record

Headless `zcode -p` executes no hooks at all (four-event marker probe, zero fires) — recorded in `benchmarks/super-caveman/results/zcode-smoke-receipt-attempt-1.json` the same day. Live firing is therefore GUI-specific, as the support matrix states.

## Claim boundary

This proves the zcode 0.16.5 GUI host fires both adapter events live under a user-scope registration on this machine, end to end through the canonical state machine, on this adapter revision. It does not prove behavior on other zcode versions, the workspace-hooks trust flow (not exercised — user scope needed no trust prompt here), persistent-defaults shaping in daily use (left neutral), or cross-host parity. Raw session state stays Git-external in the project's private `.azhou/` namespace; nothing private is committed.

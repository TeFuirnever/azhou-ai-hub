# zcode hook surface receipt — 2026-09-04 (re-derivation)

This receipt re-derives the zcode 0.16.5 hook surface after the 2026-09-02 receipt (`evidence/zcode-hook-surface-2026-09-02.md`) was found committed empty at `a03f846` while its content was still cited by `docs/support-matrix.md` and the Super Caveman zcode feasibility study. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Host: zcode `0.16.5` (headless CLI via the ZCode.app bundle), macOS arm64
- Date of observations: 2026-09-04, this machine

## Observed surface

| Observation | Result | Evidence |
|---|---|---|
| Config registration shape | real | `<scope-root>/.zcode/cli/config.json` carries a `hooks` object with `enabled` (bool) and `events` mapping event names to registration arrays of `{matcher, hooks: [{type: "command", command, async}]}`. Registrations for `PermissionRequest`, `PreToolUse`, `PostToolUse` and `PostToolUseFailure` were observed present in a live user-scope config (unrelated third-party hooks, read-only inspection). |
| Events live-fired in the GUI host | `SessionStart`, `UserPromptSubmit` | The GUI session that authored this receipt received SessionStart hook context at startup and UserPromptSubmit hook context per user prompt (user-scope hooks). |
| Events live-fired headless (`-p`) | none | A probe registering marker command hooks for `SessionStart`, `UserPromptSubmit`, `PostToolUse` and `Stop` at project scope fired zero markers across a completed `-p` session (recorded in `benchmarks/super-caveman/results/zcode-smoke-receipt-attempt-1.json`). |
| `PreCompact`, `SessionEnd` | not claimable | No registration or firing observed for either name; both stay conditional in the support matrix. |

## Claim boundary

This proves the config registration surface, two live-fired GUI events, and a strict headless negative on this machine at zcode 0.16.5. It does not prove the payload envelope casing for SessionStart or UserPromptSubmit (no live payload could be captured: the GUI host delivers processed contexts, and headless fires nothing), the workspace-hooks trust flow, or any event beyond those named above. A payload-capture receipt requires a host that exposes raw hook payloads and remains open.

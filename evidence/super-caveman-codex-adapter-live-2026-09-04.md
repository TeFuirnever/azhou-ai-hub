# Super Caveman codex adapter live firing receipt — 2026-09-04

This receipt records a redacted real-host check that the Codex CLI host fires the canonical `codex_adapter` hooks live: the SessionStart event injects the canonical capsule and creates adapter session state, and the UserPromptSubmit event — after the host's per-definition trust confirmation — runs the documented stop-phrase state machine end to end. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Adapter: canonical `skills/super-caveman/scripts/codex_adapter.py` at local default-branch commit `9a280cb` (revision-e04ba7c3 tree), user-scope linked content
- Host: macOS arm64, Codex CLI `codex-cli 0.152.0`, headless `codex exec -s workspace-write` sessions in a disposable Git-initialized project directory; user-scope hook registration in `~/.codex/hooks.json` (one owned SessionStart `render` registration plus one owned UserPromptSubmit `prompt` registration beside unrelated pre-existing hooks)
- Trust step: the two owned definitions were confirmed through the host's `/hooks` review flow by the workspace owner between the runs below (the host skips new or changed definitions until per-definition trust)
- Mode: real headless sessions on 2026-09-04, attempt-1 per check

## Results

| Check | Result | Evidence |
|---|---|---|
| SessionStart hook fires and injects the canonical capsule | `PASS` | In a real session with the persistent defaults layer unset, the model's reply restated the neutral capsule's own wording ("response shaping is off"), and adapter session state `super-caveman.adapter-state.v1` appeared under the project's `.azhou/super-caveman/sessions/` with `stopped: false` — the fresh-session write of the delegated `run_render` handler. |
| New definition is skipped until per-definition trust | `PASS` (documented boundary, verified) | Before the trust step, a first UserPromptSubmit registration was silently skipped: the stop phrase produced no state-machine write (`stopped: false`). This matches the official trust model and the support matrix's precondition wording. |
| UserPromptSubmit hook fires and runs the state machine | `PASS` | After the trust step, a session sent the documented stop phrase; adapter state for that session recorded `stopped: true` — the stop branch of the delegated `run_prompt` handler, end to end. |
| Capsule convergence is codex-host-visible | confirmed | The same sessions show the mode-aware canonical capsule (neutral wording above) replacing the former minimal fixed capsule, as disclosed in the #117 promotion. |

## Claim boundary

This proves the Codex CLI 0.152.0 host fires both adapter events live on this machine under a user-scope registration with per-definition trust, end to end through the canonical state machine, on this adapter revision. It does not prove behavior on other Codex versions or surfaces (the App stays unverified per the feasibility decision), the project-scope hooks layer (not exercised — user scope was tested), or cross-host parity. Raw session state stays Git-external in the scratch project; nothing private is committed.

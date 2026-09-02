# zcode lifecycle adapter feasibility — 2026-09-02

Input: `evidence/zcode-hook-surface-2026-09-02.md` (version-pinned contract, PR #94) and the package law in `skills/super-caveman/SKILL.md` and `references/setup.md`.

## Verdict

FEASIBLE for a two-event zcode adapter: SessionStart injection plus UserPromptSubmit mode parsing. The discovered zcode 0.16.5 hook surface provides a genuine event contract, so per the #92 group-5 law the adapter build proceeds; the pre-compact and session-end semantics stay unavailable (no such hook events in zcode 0.16.5) and remain conditional in the matrix.

## Why the contract is genuine

- Version-pinned enum of exactly seven hook events; six live-fired with captured payloads (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, Stop).
- The SessionStart payload carries `source` (observed `startup`), `session_id`, `cwd`, `mode`, `model`; the UserPromptSubmit payload carries the verbatim `prompt` plus the same session envelope. zcode payloads carry camelCase plus snake_case aliases, and the adapter handlers read snake_case, so the payload compatibility is direct.
- The zcode output schema accepts `hookSpecificOutput: {hookEventName, additionalContext}` on SessionStart and UserPromptSubmit — the exact emission shape the canonical Claude adapter uses (`emit_context`).

## Design (matching the existing adapters)

- `skills/super-caveman/scripts/zcode_adapter.py`: self-landing opt-in CLI in the same family as `codex_adapter.py` and `claude_adapter.py`; never registered by ordinary skill installation.
- `render`/`prompt` handlers: reuse the canonical claude_adapter handler modules via a same-directory import (single source of truth for the capsule builder, the mode hierarchy, and the session state machine). Payloads from zcode already carry the snake_case fields the handlers read (`source`, `session_id`, `cwd`, `prompt`).
- `setup`/`uninstall`: manage the `.zcode/cli/config.json` `hooks` block (`hooks.enabled` plus `hooks.events.SessionStart` / `hooks.events.UserPromptSubmit`), identifying owned entries by a `super-caveman` command marker; atomic write, explicit scope (user scope default `~/.zcode/cli/config.json`, project scope `<project>/.zcode/cli/config.json`); symlink-component rejection like the other adapters.
- `enable`/`disable`/`status`: reuse the canonical persistent-defaults state layer (same host-local layer files as the Claude adapter, same failure-open contract).
- Pre-compact/session-end: not buildable — zcode 0.16.5 exposes no PreCompact and no SessionEnd hook events (strict-schema negatives in the hook-surface receipt). This part of the row stays conditional with the version-pinned blocker.

## Known limits recorded in the design

- PermissionRequest is schema-valid but unexercised; the adapter does not use it.
- The workspace-hooks trust flow (`workspace_hooks_pending_trust`) is a separate, untested registration path; the adapter ships user- and project-scope config writes without claiming that flow.
- zcode `Stop` is per-turn; the adapter does not use it, keeping the lifecycle to the two events with the proven payload contract.

## Reproduction pointer

The smoke receipt for the built adapter lands as `benchmarks/super-caveman/results/zcode-smoke-receipt-attempt-1.json` following the claude-smoke-receipt pattern; deterministic unit tests cover the config read-modify-write and the payload-compat handlers.
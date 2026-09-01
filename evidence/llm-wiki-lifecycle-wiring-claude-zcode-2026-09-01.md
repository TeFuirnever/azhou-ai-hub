# LLM Wiki lifecycle adapter wiring receipt — Claude Code + zcode — 2026-09-01

This receipt records a redacted real-host check that the three-event lifecycle adapter (`scripts/llm_wiki_adapter.py host-hook`) is explicitly wired into both available hosts outside Git and executes real events, including host-triggered live runs. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `85447284c8953e7f1797b46146ad80e247b1d518` (merged `main`; the wired adapter path and a disposable worktree of the same commit are both at this content)
- Host: macOS 26.6.2, arm64; Python 3.14.7
- Host: Claude Code `2.1.239` local CLI (user-scope settings hooks)
- Host: zcode headless CLI `0.16.5` (run via the ZCode.app 3.10.2 bundle), Node.js 24.15.0
- Mode: real host hook wiring outside Git + live headless model runs (`claude -p`, `zcode -p`), attempt-1 per run

## Wiring (kept outside Git; host-local)

`render-hooks` output was merged into each host's own hook configuration; unrelated hooks were preserved and the wired commands point at a stable local checkout of the recorded commit (`<home>/Desktop/oh-my-ai/azhou-ai-hub`), redacted here. Before/after redacted diffs are recorded Git-external.

- Claude Code (user-scope settings, `hooks`): one command group appended to each of `SessionStart` (`host-hook session-start`, timeout 5), `PreCompact` (`host-hook pre-compact`, timeout 3) and `SessionEnd` (`host-hook session-end`, timeout 30).
- zcode (CLI configuration `hooks.events.SessionStart`, matcher `.*`): one command group appended (`host-hook session-start`, timeout 5).

## Results

| Check | Host | Event | Result | Evidence |
|---|---|---|---|---|
| Live host-triggered run | Claude Code | session-start | `PASS` | Headless `claude -p` run with the wiring active: the model quoted the injected `additionalContext` line `[LLM Wiki: 2 pages at .azhou/llm-wiki/]` verbatim, the missing `index.md` was rebuilt, and reserved `environment.md` was created from `project-context.json`. |
| Live host-triggered run | Claude Code | session-end | `PASS` | With `autoCapture` enabled on the scratch store, headless `claude -p` sessions wrote `session-log-2026-09-01-*.md` metadata pages (one per session, one-way hashed session reference, no transcript content). |
| Wired command exercised with host payload | Claude Code | pre-compact | `PASS` | The exact wired `PreCompact` command was run on stdin with the host payload shape (`cwd`, `trigger`); it returned the correct summary `systemMessage` `[Wiki: 4 pages | categories: session-log | last updated: ...]`. A host-triggered compaction was not forced in headless mode; the claim is limited to the wired command contract. |
| Live host-triggered run | zcode | session-start | `PASS` | Headless `zcode -p` run with the wiring active: the model quoted the injected context line `[LLM Wiki: 4 pages at .azhou/llm-wiki/]` verbatim, and the missing `index.md` was rebuilt. |
| Event availability | zcode | pre-compact | `BLOCKED` | zcode CLI 0.16.5 exposes no `PreCompact` hook event. Its hook events are `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PreToolUse`, `SessionStart`, `Stop`, `UserPromptSubmit`. `Stop` fires per response turn, not at compaction, so it is not an equivalent contract. The cell stays conditional for this event. |
| Event availability | zcode | session-end | `BLOCKED` | Same hook-event surface: no `SessionEnd` event; `Stop` is per-turn and not equivalent. The cell stays conditional for this event. |

## zcode configuration-location finding

As with MCP servers (see the transport receipt of the same date), zcode CLI 0.16.5 reads hook wiring from `hooks.events` inside the CLI configuration, not from the `hooks.json` file beside it. A first wiring attempt into that other file produced a run with no hook execution (no index repair, reply `NO-CONTEXT`); it was voided and rewired into the CLI configuration, after which the live run passed.

## Reproduction

1. Check out the recorded commit (or use a stable checkout at the same content).
2. Wire the `render-hooks` groups into the host hook configurations: Claude Code user-scope `SessionStart`/`PreCompact`/`SessionEnd`; zcode CLI `hooks.events.SessionStart`.
3. Prepare a scratch project store with `init`, two pages, `project-context.json` with a fresh `lastScanned`, and a removed `index.md`.
4. Run `claude -p` and `zcode -p` prompts asking the model to quote any `[LLM Wiki:` context line; confirm the quote, the rebuilt `index.md`, and (Claude) the created `environment.md`.
5. Enable `autoCapture` and run `claude -p`; confirm a `session-log-*.md` page.
6. Pipe `{"cwd": <scratch>, "trigger": "manual"}` into the wired `pre-compact` command; confirm the summary `systemMessage`.

## Claim boundary

This proves the three-event lifecycle adapter is explicitly wired and real on Claude Code 2.1.239 (session-start and session-end host-triggered live; pre-compact exercised at the wired-command contract level) and on zcode 0.16.5 (session-start host-triggered live). zcode offers no `PreCompact`/`SessionEnd` hook events, so those two events stay unverified on zcode with a concrete, host-version-pinned blocker. It does not prove GUI-surface behavior or parity with any other host. Raw transcripts, host configuration and wiring stay Git-external; nothing private is committed.
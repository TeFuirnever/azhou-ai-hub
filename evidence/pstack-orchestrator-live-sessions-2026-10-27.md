# pstack/orchestrator live coexistence sessions — 2026-10-27

Scope: the five task-boundary scenarios that the 2026-10-27 closeout left pinned as tested rule text — an ordinary small task, a same-task follow-up keeping the pstack owner, a new ordinary task after a pstack task, a mid-task workflow switch draining in-flight children, and a rejected explicit model. One real Codex client drove all five in one throwaway coexistence home, closing the live-observation gap recorded in the [native acceptance](pstack-orchestrator-native-acceptance-2026-10-26.md) boundary and [ticket #343](https://github.com/TeFuirnever/azhou-ai-hub/issues/343).

## Environment and method

- Selected runtime: the `com.openai.codex` App bundle CLI `0.164.0-alpha.11.1` at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex` (same build as the dispatch and native-acceptance records). macOS `27.0.0` arm64.
- One throwaway `HOME` and `CODEX_HOME` plus a throwaway Git-initialized workspace under a symlink-free `/private/tmp` base (the pstack adapter refuses the symlinked `/tmp` parent; first attempt disclosed below). Nothing in the real user scope was modified.
- The home was assembled through the two public Hub entries, Kit first and pstack coexistence second: `model-router plan/apply` (Skill installed at the workspace's discoverable `.agents/skills` root — a first attempt with a plain `skills/` root was refused by native verification and fully restored, the documented discoverability boundary) and `pstack plan --coexistence` + `apply`. Final `doctor`: Kit rules present, model sheet present with `session hook: off` (owner `hub-pstack-adapter`), native plugin `pstack@pstack-claude` `0.9.103` registered, `auto_routing: off`, hook trust `unknown`.
- Credential method, disclosed exactly: a temporary local copy of the user's `auth.json` (mode 0600) was placed in the throwaway `CODEX_HOME` and used only by these sessions, then deleted at `2026-10-27T08:59:23+0800` immediately after the last run; no user-global file was changed. The copy predates the first session (`2026-10-27T08:50:19+0800`); the copy-time bookkeeping file was itself removed by the cleanup sweep, so the copy window is evidenced by the session timestamps and the recorded deletion time. The retained records contain no credential bytes (verified by name and sweep). The prior credential-free attempt returning `401 Unauthorized` remains recorded in the native acceptance file.
- Raw `--json` events, stderr and all eight session rollouts (five parent/child pairs plus follow-up turns) are retained with the full prompt texts under the ignored planning records directory (`.planning/pstack-orchestrator-coexistence/live-records-2026-10-27/`, ≈2.1 MB); they contain local paths and transcripts and are not published. Known client noise: model-list refresh timeouts in stderr, as before.

## Observed results

| Scenario | Observed |
|---|---|
| Ordinary small task | parent turn context `gpt-6.1-sol`/`high` (host default), zero `spawn_agent` calls, correct bounded answer ("10"); with both modules installed no second flow or forced delegation appeared |
| pstack-selected task, then a same-task follow-up | turn 1: one `spawn_agent` with explicit `model=gpt-6-luna`, `reasoning_effort=max`, `fork_turns="none"` and no `agent_type`; child ran `gpt-6-luna`/`max` with no custom role; the parent stayed on `gpt-6.1-sol` throughout. Resumed follow-up turn (status question plus one added constraint): zero new dispatches, and the reply stated "Poteto-mode remains the workflow owner. No second orchestration flow started." while applying the constraint ("ten") |
| New ordinary task after the pstack task completed | fresh session back on the default path: one `spawn_agent` with `agent_type=explorer`, `fork_turns="none"` and no explicit model fields; the child ran the explorer role file's `gpt-6-luna`; correct answer (4 lines) — the finished pstack task did not keep ownership |
| Mid-task workflow switch | switch turn in the pstack-owned session: the parent called `interrupt_agent` on the in-flight child (recoverable boundary), spawned no second flow for the same goal, and produced the final report itself; parent model unchanged |
| Rejected explicit model | exactly one `spawn_agent` attempt with explicit `model=gpt-nonexistent-fallback-probe`/`high` and no named role; the host rejected the model, the model sheet declares no fallback models, so **no subagent ran**; the parent reported the rejection and the reason ("The host rejected … The model sheet declares no fallback models, so no subagent ran.") and computed the bounded answer itself — no silent substitution and no false success claim |

## Boundary

- One recorded client build on one recorded machine; client session and turn metadata are the model evidence, and a client alias is not proof of an independent backend model identity.
- These runs cover the five task-boundary behaviors under the shipped rules; they do not claim automatic SessionStart routing, hook-trust approval (still `unknown`), cross-harness equivalence, model quality or cost, or any change to the real user environment.
- Installation-path acceptance remains the 2026-10-26 native record's scope; this home's assembly additionally re-confirmed both public entries end-to-end on a fresh throwaway target.

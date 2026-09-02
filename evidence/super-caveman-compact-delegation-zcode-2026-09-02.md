# Super Caveman compact delegation receipt — zcode — 2026-09-02

This receipt records a redacted real-host check of Super Caveman compact delegation through zcode's real subagent surface. It contains no temporary path, user identity, account data or raw transcript; raw run artifacts stay Git-external.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (ZCode.app `3.10.1` bundle), Node.js 24.15.0, GLM-5.1 via the BigModel Coding Plan
- Mode: disposable checkout with the ten packages linked; one attempt-1 delegation run with subagentType `Explore` requested; parent run and child subagent session artifacts Git-external

## Results

| Check | Result | Evidence |
|---|---|---|
| Real subagent delegation | `PASS` | The host run requested Task-tool delegation with subagentType `Explore`; a real child subagent session was spawned (child rollout `model-io-sess_subagent_agent_b3d468ef-0020-4943-84d6-7ba258905aaa.jsonl` under the disposable home; child model glm-5.1). The parent run returned the subagent work product: the ten canonical skill directory names, exact and complete. |
| Named-presets boundary | disclosed | This proves delegation works through zcode's real subagent surface (a real child session spawned and returned a work product); it does not prove the SC skill named delegation presets (delegation.md bounded investigator/builder/reviewer) behave as named. The matrix cell records the delegation surface receipt plus this disclosed boundary. |
| Local-only boundary | `PASS` | No publication, no share; raw artifacts Git-external; nothing private committed. |

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout with the ten packages linked into `.agents/skills`.
2. Run one headless zcode prompt requesting Task-tool delegation (subagentType `Explore`) to list the ten skill directory names.
3. Check the parent output lists the ten names exactly and the disposable home rollout tree contains the child subagent session rollout.

## Claim boundary

This proves zcode 0.16.5 spawns real child subagent sessions on a Task-tool delegation request and returns the subagent work product to the parent run on this machine. It does not prove SC named-preset behavior, GUI-surface behavior, or cross-host parity. Raw run artifacts stay Git-external; nothing private is committed.
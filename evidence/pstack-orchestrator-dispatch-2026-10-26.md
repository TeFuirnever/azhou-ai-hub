# pstack/orchestrator dispatch paths on Codex — 2026-10-26

Scope: bounded acceptance for the task-ownership rules shipped in the coexistence contract change of the same date. It observes two child-dispatch paths in one isolated Codex configuration — ordinary named-role delegation and an explicitly selected pstack workflow's explicit dispatch. It is not an installation acceptance: the native same-home coexistence installation loop is not part of this change, and install-path behavior is covered separately by the deterministic Hub and package suites plus the 2026-10-25 report.

## Environment and inputs

- Selected runtime: the `com.openai.codex` App bundle CLI `0.164.0-alpha.11.1` at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex` (explicit `--codex-bin` resolution; the PATH CLI `0.160.1` was not selected). macOS `27.0.0` arm64.
- Isolated target: one throwaway `CODEX_HOME` and one throwaway workspace under `/tmp`, removed after the run. A temporary local credential copy was used only for these two sessions and deleted immediately after; no user-global file was changed.
- Configuration bytes came from this repository's packages at the reviewed change: `profiles/azhou-balanced/codex/config.toml`, its six role files, and the managed instruction block in `profiles/azhou-balanced/AGENTS.md` for the home; the project-scope `poteto-mode` copy under the workspace's `.agents/skills/` carried the updated Codex mapping. The home's `config.toml` disabled the user-global `astra-orchestrator` Skill through native `skills.config` (a `SKILL.md` file path is required for the entry to apply); no user-global Skill was deleted or edited.
- The public installer entry could not complete in this target: with the user's pre-existing global `astra-orchestrator` copy present, any second copy — including the updated one — fails the installer's native uniqueness check, which correctly counts the disabled global entry. That protection was not weakened; the demo home was assembled from the same package bytes instead. Installation-path acceptance is not claimed here.
- Discovery observed before the runs: exactly one `poteto-mode` (repo scope, enabled, at the project path) and the user-global `astra-orchestrator` disabled. Both runs also printed the known user-global skills traversal-limit warning; selected discovery, child creation and completed results were still observed.

## Reproduction shape

Two non-interactive `codex exec` runs in the same isolated home and workspace: run A presents an ordinary bounded delegation task (dispatch one `explorer` and one `reviewer` with fresh contexts, no explicit model parameters); run B explicitly selects the poteto-mode workflow for its task, points at the project mapping's Subagent policy and task-ownership section, and asks for exactly one child with explicit `gpt-6-luna`/`max` and no named role. Raw events (`--json`), last messages, stderr and all five session rollouts are retained with SHA-256 hashes in the ignored task record directory; they contain local paths and transcripts and are not published.

## Observed results

| Run | Parent turn context | Dispatch recorded in the parent rollout | Child turn context |
|---|---|---|---|
| A, ordinary task | `gpt-6.1-sol` / `high` | two `spawn_agent` calls with `agent_type=explorer` and `agent_type=reviewer`, `fork_turns="none"`, and no explicit model or effort fields | explorer child `gpt-6-luna` / `max`; reviewer child `gpt-6.1-sol` / `high` |
| B, pstack-selected task, same home | `gpt-6.1-sol` / `high` (unchanged by the selection) | one `spawn_agent` with explicit `model=gpt-6-luna`, `reasoning_effort=max`, `fork_turns="none"`, and no `agent_type`; the parent read the project mapping before dispatching; no second named-role flow ran | child `gpt-6-luna` / `max`, no custom role |

Both runs returned the correct bounded answers (sum 10; total 10 with three active amounts). Model identity evidence is the client's own session and turn metadata for the recorded build; no independent backend fingerprint was obtained, and a client alias is not proof of a distinct backend model. The run A parent also read the disabled user-global `astra-orchestrator` Skill file by raw path while preparing the delegation; disabled state governs discovery and loading, not direct file reads. Worker, tester, researcher and Astra specialist roles were available in the rendered schema but not invoked in these bounded runs.

## Boundary

This receipt demonstrates the two dispatch paths' metadata behavior under the shipped rules in one isolated home. The task-boundary rules themselves — a same-goal follow-up keeping the owner, the task end returning to host defaults, and a mid-task switch draining in-flight children — are enforced as pinned rule text with repository tests, not as live-session transitions; no run in this receipt drove those three transitions. It does not claim: same-home coexistence installation support (adapters still reject known competing configuration), automatic SessionStart routing, hook trust, cross-harness equivalence, model quality or cost, or any MiMo Code / Claude Code / zcode capability.

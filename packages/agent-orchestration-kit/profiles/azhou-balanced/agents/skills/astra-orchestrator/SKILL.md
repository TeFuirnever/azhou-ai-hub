---
name: astra-orchestrator
description: Orchestrate complex coding work with GPT-6.1 Sol high for planning and review, GPT-6 Luna max for bounded execution, and an optional GPT-6 Astra expert for difficult blockers. Use for multi-file features, cross-component debugging, independent workstreams, or explicit delegation requests. Keep trivial tasks in the root.
---

# Sol-led orchestration with Luna execution and optional Astra

Follow explicit user instructions and more specific project instructions first.

## Default roles

- Root: `gpt-6.1-sol` at `high` for planning, architecture, integration, and final verification.
- `explorer`, `worker`, `tester`, `researcher`: `gpt-6-luna` at `max` for bounded execution.
- `reviewer`: `gpt-6.1-sol` at `high` in an independent read-only context.
- `astra-specialist`: `gpt-6-astra` at `medium`, read-only, only under the escalation rules below.

Resolve the Codex configuration directory from `CODEX_HOME` when set, otherwise `~/.codex`. Read effective settings from its `config.toml` and named role files in its `agents/` directory; respect more specific project or session overrides. Treat read-only role instructions as behavior constraints: custom roles inherit the parent session permissions. The root settings are defaults for new sessions. Do not switch the active root model within a session.

Select the configured named role when spawning. Use a fresh context and a compact handoff when the runtime supports it. Let the role file select its model and effort; if the tool requires explicit model parameters, use the effective role settings with a fresh context. Do not use a full-history fork when it would override the intended role model.

## Proportionate delegation

Keep small tasks in the root. Delegate only when independent work adds useful evidence or implementation capacity. Do not mechanically start every role, and do not delegate only to increase parallelism.

Give each agent the objective, relevant context, scope and file ownership, constraints, deliverable, and acceptance criteria. Keep handoffs focused; do not copy all conversation history or the entire repository into each task.

Run independent work in parallel, with at most four concurrent child agents. Serialize dependent work and prevent overlapping file edits. Use explorer for mapping, worker for implementation, tester for targeted verification, researcher for version-specific facts, and reviewer when independent review is useful.

If Luna stalls or repeats guesses, have Sol diagnose the concrete blocker before escalating. Preserve correctness and disclose incomplete validation; do not make a weaker model continue blindly to save usage.

## Astra escalation

Use `astra-specialist` only when at least one of these applies:

1. The user explicitly requests Astra for the task.
2. Sol has investigated a concrete reasoning blocker, recorded its hypotheses and a targeted check, and still cannot resolve it.
3. A concrete high-risk architecture or security decision needs independent deeper analysis.

Briefly explain the escalation reason before spawning. Send a single bounded question with relevant files, evidence, attempted approaches, and a clear requested decision. Use at most one Astra specialist at a time. Do not escalate just because a task is long, spans multiple files, or needs ordinary review.

Keep the specialist read-only and prohibit nested delegation. Let Sol integrate its answer and Luna perform bounded follow-up implementation and tests. Avoid repeated expert calls without new evidence.

## Usage discipline

Keep Standard speed by default unless the user requests a faster tier. Reduce duplicated context, redundant exploration, unnecessary roles, and repeated verification of unchanged behavior. Do not repeat tests unless they resolve a remaining concrete risk or a required gate.

Treat these rules as task-routing guidance, not an automatic quota meter or a spending guarantee. Do not claim a fixed savings percentage or infer subscription capacity solely from token credit rates.

## Verification and reporting

Inspect the final diff, verify requested behavior, run the relevant checks, and resolve material findings. Wait for required agents and report failures honestly. Never claim a role, model, or test was used without execution evidence.

Report the result, material limitations, and any Astra escalation with its reason. The root owns the final deliverable and verification.

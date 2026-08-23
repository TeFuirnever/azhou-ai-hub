# Project knowledge surfaces

Use this reference to distinguish project knowledge from global agent configuration.

## Default reconcile scope

An explicit `repo-pedant` reconcile or handoff covers these surfaces without a second authorization prompt:

| Surface | Examples | Action |
|---|---|---|
| User-facing project knowledge | `README`, `docs/`, spec, runbook, handoff | update against current code |
| Project agent rules | nearest `AGENTS.md`, `CLAUDE.md`, equivalent instruction files | keep durable rules, commands, boundaries, and pointers |
| Project-bound agent memory | runtime memory associated with this repository or workspace | update, merge, or remove stale entries |

Project-bound memory remains project knowledge even when the runtime stores it outside the Git worktree.

## Separate checkpoint scope

Require explicit authorization for:

- user-wide or global agent instructions;
- memory whose repository or workspace binding cannot be verified;
- unrelated repository writes;
- deletion of an entire file or directory;
- publication, deployment, or global configuration changes.

Removing or rewriting a superseded entry inside an existing project memory file is ordinary reconciliation, not whole-file deletion.

## Discovery order

1. Use memory resources or paths exposed by the active harness.
2. Follow the current session's agent instructions and workspace metadata.
3. Inspect project-root `AGENTS.md`, `CLAUDE.md`, overrides, and equivalent files.
4. Use platform-common paths only as candidates; verify their project binding before editing.

Examples include Claude project memory directories, Codex workspace memory providers, and project-local `.opencode/` or equivalent stores. Locations vary by harness version and configuration, so never infer ownership from a familiar path alone.

If the current agent has no independent memory system, record `none_discovered` plus the exact repository and harness surfaces checked; then complete docs plus project agent rules. Do not silently skip the memory inventory.

## Content test

Keep a fact in project memory only when a future agent would otherwise repeat a material mistake or miss a durable project decision. Historical narration, completed temporary work, duplicated docs, and facts visible directly from maintained code should be removed or moved to the designated history surface.

# Treehouse worktree policy

Treehouse is the default lifecycle manager for temporary, concurrent, experimental and coding-agent work in maintainer checkouts of this repository. Ordinary contributors may continue to use a normal fork and task branch. This policy is verified against Treehouse `v2.3.0` and Git worktree behavior on 2026-08-26.

## Boundary

Treehouse manages a reusable pool of Git worktrees. It prevents the same leased workspace from being handed to another task, preserves reusable dependency and build caches, and provides guarded return, prune and destroy operations. It does not replace Git branches, commits, reviews or repository verification. It is workspace isolation, not a security sandbox or permission boundary.

The repository-level `treehouse.toml` keeps a small Git-backed pool and deliberately omits `root` and lifecycle hooks. The default user pool stays outside the checkout. Treehouse ignores repo-level hooks for safety; any user-level hook remains a separately reviewed machine configuration.

## Acquire a durable task workspace

Run from any checkout of this repository:

~~~bash
LEASE_HOLDER=codex-task-slug
treehouse get --lease --json --lease-holder "$LEASE_HOLDER"
~~~

Persist the returned `path`, `lease_id`, `lease_holder` and `leased_at` in the task evidence. Before writing:

1. confirm `treehouse status --json` reports the exact path as `leased` with the same identity;
2. confirm the leased path resolves to the same Git common directory as this repository;
3. create or select one `codex/<task>` branch in the leased worktree;
4. confirm the task branch is not already checked out by another worktree;
5. run the smallest relevant baseline check before changing behavior.

One task owns one lease and one task branch. Do not share a leased worktree across unrelated tasks. Keep the lease through review or handoff even when no process remains in the directory.

If Treehouse `v2.3.0` or newer is unavailable, do not install or upgrade it implicitly. Report the missing capability. A direct `git worktree add` fallback requires explicit user approval and becomes a manually managed, long-lived exception.

## Work and verification

- Keep generated caches and dependencies inside the leased worktree or normal external caches; do not commit pool state.
- Treat code and machine-readable configuration as current behavior. A lease is not evidence that tests, approval or publication gates passed.
- Run targeted tests first, then `python3 scripts/verify.py` before handoff. Preserve any unrelated baseline failure as an explicit hold.
- Record branch, HEAD, dirty state, verification commands and results in the handoff receipt.
- Never run implementation from the primary checkout when the task was allocated a lease.

## Return a lease

Return only after proving that work is merged, committed on the intended branch, or preserved by another explicitly verified recovery point. The worktree must be clean, idle and no longer needed for review.

For automation, condition the return on both immutable acquisition identity and holder:

~~~bash
treehouse return \
  --if-lease-id "$LEASE_ID" \
  --if-lease-holder "$LEASE_HOLDER" \
  "$LEASE_PATH"
~~~

Do not use path-only automated return. Do not use `treehouse return --force`; it resets the worktree and can discard unlanded changes.

## Prune and destroy

`treehouse prune` and `treehouse destroy` are preview-only by default. Review the exact target and current Git, process and lease state before adding `--yes`.

Never use `--include-unlanded`, `--include-in-use` or `--include-leased` without explicit user authorization for the named path. Never delete a worktree directory directly. Use Treehouse for managed pool entries and `git worktree remove` for approved manual worktrees. Use `git worktree repair` if a linked worktree was moved or its administrative link became stale.

## Migrate an existing manual worktree

1. Freeze `git status`, the tracked binary diff digest and hashes of every untracked file.
2. Create a named `git stash push --include-untracked` recovery point and verify its file list.
3. Acquire and verify a durable Treehouse lease.
4. Remove the old manual worktree only after the recovery point exists and the directory is clean.
5. Select the original task branch in the leased worktree and apply, not pop, the exact stash object.
6. Recompute the tracked diff digest and every untracked-file hash. Stop on any mismatch.
7. Keep the stash until the migrated branch is committed or otherwise durably preserved.

## Source basis

- [Git worktree documentation](https://git-scm.com/docs/git-worktree) defines linked-worktree creation, listing, locking, moving, removal, pruning and repair.
- [Treehouse upstream documentation](https://github.com/kunchenguid/treehouse) defines reusable pools, durable lease identities, dirty detection, guarded return and dry-run-first cleanup.
- [Treehouse lifecycle vision](https://github.com/kunchenguid/treehouse/blob/main/VISION.md) requires dirty, in-use, leased, changing or unverifiable worktrees to remain protected and states that Treehouse is not a security sandbox.
- [OpenAI harness-engineering guidance](https://openai.com/index/harness-engineering/) recommends keeping `AGENTS.md` short and using it as a map to structured repository knowledge rather than a monolithic manual.

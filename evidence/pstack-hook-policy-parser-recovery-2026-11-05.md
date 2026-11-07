# pstack model-sheet Hook parser restoration — 2026-11-05

## Scope and source provenance

At integration branch `codex/pstack-integration-20261104` after the
latest pstack-upstream-rebase Hook namespace changes were merged via
`f4dc0a23dc0819ec785340068d28ac1c3d3b7f25`, the Hub-authored
`hub-runtime/hooks/session-start.sh` and `pre-tool-use.sh` refer to
`skills/setup-pstack/scripts/sheet.awk`. The generated copies did not
contain that file. The same Skill's `copilot.md` calls
`scripts/check-sheet.sh`, which was also absent.

Restored the exact historical parser and checker bytes from local `main`
under the retired port, preserving attribution and deterministic source
provenance (no edits to pristine `pstack/` or `components/`):

| Restored Hub source | Historical `main` path suffix | SHA-256 |
| --- | --- | --- |
| `hub-skills/setup-pstack/scripts/sheet.awk` | `plugins/pstack/skills/setup-pstack/scripts/sheet.awk` | `cb6501a05b5a7d46a4c63fdc3c35ae4324b0892625a666473b4ec9d6f7582411` |
| `hub-skills/setup-pstack/scripts/check-sheet.awk` | `plugins/pstack/skills/setup-pstack/scripts/check-sheet.awk` | `3eafe5bb2f74444578cc8288d4a092f2f7ea8b1bfed8097c83a45df64f02b4ad` |
| `hub-skills/setup-pstack/scripts/check-sheet.sh` | `plugins/pstack/skills/setup-pstack/scripts/check-sheet.sh` | `106bd8071080bfaa8960d61dc6b622bac19f6d92048fd8d49584428610b71f66` |

The standard Hub generator copies this source into all four host trees.

## Observed red-green

**Red (original merged candidate):** With a temporary synthetic
`COPILOT_HOME` and a Copilot `Task` input whose `agent_type` was
`pstack-azhouzhou:poteto-agent` and whose `model` was an unsaved ID,
the generated `hooks/pre-tool-use.sh` exited 0 and produced **no
policy decision**. AWK stderr reported it could not open the missing
`sheet.awk`. This silently fell through to normal host permissions
rather than enforcing the configured model policy.

**Green (restored parser):** A synthetic sheet with all 17 role rows
and `panel vendors: any`, plus `feature, refactoring: gpt-6-sol`,
passed the restored `check-sheet.sh`. Replaying the Hook yielded:

- Saved model `gpt-6-sol`: no denial; normal permission flow.
- Unsaved model `foreign-model`: explicit
  `permissionDecision: deny` with a reason.
- No explicit model, unrelated agent or stale `pstack:` agent ID:
  no denial; normal permission flow.
- Copilot and Muse `session-start.sh` both returned the
  `pstack-azhouzhou` mandate with a checked role line in their
  output, no AWK errors.

Added `tests/test_pstack_copilot_hook_policy.py` to exercise the
real generated script entrypoints using isolated, synthetic files.
It never opens or writes the operator's Copilot/Muse model sheets,
accounts or credentials.

## Independent review finding and verified follow-up

A bounded read-only Codex review of commit `7307aa7` finished with
exit 0 and reported one concrete P2: the restored legacy `sheet.awk`
inadvertently added `inherit-parent` and `auto` to `SHEET_MODELS`.
That let a call with explicit `model: auto` pass the saved-model
check when it should omit `model`.

Recorded red: an additional regression assertion requiring
`permissionDecision: deny` for explicit inheritance aliases failed.
Fixed the Hub-owned source to track these values only through
`MODEL_ALIASES`, leaving the explicit allowlist limited to model IDs.
Rebuilt all host distributions and reran the policy and UTF-8 encoding
tests: both passed. The revised Hub-owned `sheet.awk` SHA-256 is
`1a16cad18df3bc6393d1d2024bbb1090f234bb3b73b172d830eb7cbdfe15a445`.
The earlier SHA-256 table above identifies the **initial recovered
historical bytes**, not the final corrected parser; the intentional
change is limited to the alias-enforcement branch.

## Scope limits

This is synthetic host input and shell execution, **not** a claim
that a real Copilot or Muse GUI session successfully invoked the Hook.
The prior AZ1 Claude Code fresh-session mandate receipt belongs to
the source branch, not to this new synthetic test. Hook trust and native
model routing on every maintained host remain separate runtime
acceptance criteria. The installed native Codex plugin in the user's
default home is untouched.

The attempted 20th quilt patch for upstream-facing old namespace
documentation did **not** apply with the official builder. Its full
staged difference was backed up under the leased worktree's ignored
`.local/pstack-namespace-experiment-20261105/`; all its tracked
changes were restored to HEAD, leaving the 19-patch baseline intact.
That documentation sweep remains an explicitly open independent unit,
not a published fix.

A previous isolated native Codex install/remove/reinstall sequence
passed for the `f4dc0a2` content lock
`b6a53138e0b3ff8a68072619768ba5b42b2a5deeb8345dee92ab81fe87c38ff0`.
This parser restoration changes the package bytes; the new content
lock requires another isolated install/recovery verification before
being described as fully lifecycle-validated.

# PR #372: Codex review remediation — 2026-11-06

## Source and scope

Six inline review comments on bb14050 were examined against the actual Hub Codex adapter, generated skill entry point, model sheet hook, public support matrix and bilingual READMEs.
This candidate remains isolated in branch codex/pstack-main-merge-candidate-20261105; it does not rewrite pristine upstream, Agent Skin production, the local main history, other Treehouse leases or user-native plugin caches.

## Review findings resolved in the candidate

| Reviewer finding | Remediation | Static verification |
| --- | --- | --- |
| P1: unsupported model silently inherits session model | Codex adapter now permits only a sheet-declared, host-supported and task-authorized fallback, logs requested/chosen model, and blocks when none is available. Capacity refusal is not a model rejection. | Distribution contract checks fallback guard in the source and generated Codex adapter |
| P1: public READMEs miss fifth maintained harness | Both English and Chinese public entries explicitly include DeepSeek Harness, MiMo, zcode, Codex and Claude; each notes discovery versus invocation boundaries and candidate 0.15.37. | Bilingual support-matrix parity test |
| P2: setup writes wrong model sheet | Codex adapter and Codex skill reference now identify the same active CODEx_HOME/pstack-models.md path as the bundled session-start.sh hook, not upstream Cursor .mdc or a nonexistent Other runtimes chapter. | Distribution contract checks Codex source, generated docs and hook |
| P2: comment-sicko reviewer path does not exist | Codex adapter points to the actual installed plugin root agents/comment-sicko.md and requires file existence before dispatch. | Distribution contract checks the generated agent exists and rejects old broken path |
| P1: worktree audit labels untracked files safe for forced deletion | Hub-owned worktree-cleanup override in all four distributions now treats scratch/untracked and ignored files as unknown owner data, requires explicit per-file disposition and a Treehouse lease release before any destructive cleanup, and prohibits force removal based solely on the audit bucket. | Static contract asserts four byte-identical safe overlays, retaining original pristine upstream |
| P2: Claude setup writes a different model-sheet location than SessionStart | Quilt patch 0022 aligns the generated Claude setup instructions and README to the hook's CLAUDE_CONFIG_DIR configuration-root sheet, not the auto-loaded rules folder. | Static byte/path assertions and POSIX Hook behavior: rules folder off does not disable the mandate; configuration-root off does |

Existing host instructions and model policy were retained except for the Hub-owned adapter/reference and worktree safety changes. A 23-patch quilt build regenerates all host distributions; pristine upstream source remains untouched. No native user profile or model configuration was edited.

## Evidence and limits

- Two new distribution tests cover the four original Codex/README findings. Four additional safeguards under tests/test_pstack_host_safety_review.py cover Claude Hook path alignment, safe worktree cleanup instructions, and the actual read-only audit classification on isolated Git worktrees. Together with the original 11 tests, all 17 passed.
- The public installation and model-sheet guidance has been aligned with docs/support-matrix.md and docs/integrations.md.
- Earlier CodeQL statechart test-source triage remains a separate security disposition. No open security thread was dismissed on the basis of this change.
- A release version bump to candidate 0.15.37 is separate from installed user cache 0.15.36. All native lifecycle and integration checks must be re-run on the final exact bytes before release.
- Model-sheet fallback behavior is an instruction/adapter contract; this static test does not establish real multi-agent model routing, hook trust, or host availability.
- Full repository CI, current-head independent review and remote checks remain separately gated, and this report does not self-approve the PR.


## New review findings and residual host boundaries

The original worktree-cleanup.md and worktree-audit.sh under pristine
pstack/ remain unchanged to preserve pinned source provenance. The shipping
playbook is the Hub-owned overlay in all four generated Harness trees.
During source review, the audit script itself was found able to label a
merged worktree with untracked source as safe. Quilt patch 0023 changes
the generated audit to classify untracked source as hold-untracked and
ignored files as hold-ignored, never safe. A first independent read-only
review then identified five additional false-safe conditions: failed
git status, hidden-untracked configuration, closed-but-unmerged PRs,
whitespace in registered worktree paths, and a pending clean merge.
The downstream audit patch was strengthened to require successful Git
status, explicit full untracked inventory, ancestor proof at the current
head, NUL-delimited worktree path parsing, and no in-progress operation.

An actual network-isolated synthetic Git repository exercised these
conditions with untracked source, ignored builds, a clean merged tree,
a path containing spaces, an intentionally corrupted disposable index,
a closed unmerged PR, and an uncommitted merge state. The audit returned
hold-untracked, hold-ignored, safe, hold-untracked, review,
review, and hold-operation respectively. Sentinel content remained
unchanged. The test never performs a worktree removal. No user
worktree has been removed, returned, cleaned or force-deleted.

The Claude Code model sheet path now matches the actual POSIX
session-start.sh behavior, with a test-owned custom CLAUDE_CONFIG_DIR.
This confirms shell-script routing only; it does not prove native Claude
plugin trust acceptance or a completed live model-selection workflow.

These P1/P2 fixes are candidate code, not formal review-thread disposition
or a permission to merge. A new PR SHA requires fresh remote CI and reviewer
assessment; the original security-maintainer review of CodeQL test helpers
also remains open.


## Final staged-candidate gates

The corrected audit patch passed a second, independent read-only Codex
review with exit 0 and turn.completed. No new P0/P1/P2 defect was
identified in its scoped audit and cleanup logic. The reviewer
explicitly noted the relative Git-path fallback and operation-lookup
failure were not directly exercised, and did not approve a release.

On the staged combined candidate, full scripts/verify.py reported
8/8 green gates on 2026-11-06; git diff --cached --check was clean.
A separate input-only rebuild applied 23 quilt patches and produced
2,487 files with zero missing, extra or SHA-256 mismatched outputs.
The 17 distribution and host-safety tests passed, including the
synthetic Git worktree audit and custom CLAUDE_CONFIG_DIR Hook probe.

The receipts are retained in the Treehouse recovery directory:
VERIFY-review-fixes-v3-20261106.json and
REVIEW-worktree-audit-final-20261106.json. This statement is bound
to the staged candidate and must be reconfirmed after committing.
Remote CI, reviewer disposition on the new SHA, actual native Host
Hook trust, multi-agent closeout and installed plugin upgrades remain
separate release gates. No PR review thread was auto-dismissed.

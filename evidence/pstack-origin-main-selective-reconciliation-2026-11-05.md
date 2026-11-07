# pstack projection onto current origin/main — 2026-11-05

## Why this is a project-scoped content transplant, not a full history merge

Local main = 97c0459a6b6048e29612b1d73ea8581457d377a9.
New remote-tracking main = cf629784f0e875dba3c4b4b973450fc16604835f.
Completed pstack integration = b41c35a4619a5b8ec0bdf48b6f42e4d97856580b.

A full history merge of remote main and the pstack branch has 19 conflict
files (13 Agent Skin production or tests, 5 legacy pstack and one shared
Agent Skin test). The old local main contains divergent Agent Skin code
which must not overwrite newer DSH/ZCode/DeepSeek plugin work. This
candidate deliberately starts from current origin/main and imports only
the pstack package plus 32 explicit related project files. It is a
single-parent content transplant, NOT an ancestry merge of the old
main or complete integration branch. Both histories remain accessible
as independent references.

The pstack package is byte-for-byte equal to the completed source branch,
including its quilt, Skills, native manifests, generated files and tests.
The 32 ancillary CI/docs/integration/test files are taken from Git's
virtual three-way merge tree, which automatically retains independent
remote edits. None of the Agent Skin production paths are changed from
current origin/main. Existing worktrees, leases, user plugins and the
root checkout's dirty documents are preserved.

## Remote legacy port changes and explicit behavioral debt

Remote main independently updated 12 paths in the deprecated
packages/pstack-agent-harness/plugins/pstack/ and tools/forks.json old
sync-port. The new upstream+quilt distribution retires that source tree;
those changed legacy paths are removed from the target package by design.

Two remote changes are consistent with the new baseline: the watcher
package's test command excludes retired orch tests, and documents stop
claiming the removed orch CLI is a required runtime. The upstream
pstack source and Hub quilt do not ship that CLI.

However the remote old-port playbook orchestrate.md had ~114 lines of
program-state, frontier, independent-review and reattachment guidance;
the pinned upstream pstack playbook has ~25 lines with a different
coordination strategy. The old version cannot be copied wholesale:
it assumes a different harness tool environment and may contradict
the new upstream source. The 114-to-25-line behavior gap remains a
RELEASE REVIEW GATE for long-running multi-agent orchestration. The
old code is preserved in origin/main Git history; no behavior is
silently claimed equivalent.

Other old-port additions in Codex/Muse/Copilot/Pi adapters likewise
must be reviewed against the new source contract before claiming
full cross-host behavioral parity. This transplant does not pretend
that generator, unit or type checks replace that review.

## Gates

- Repository policy and 22 targeted pstack/distribution tests passed on
  the staged remote-base candidate.
- The 24 staged whitespace warnings are byte-identical to pinned
  upstream or deterministic generated/patch files, not newly authored
  code. Leave source bytes unchanged; the release validation applies
  normal staged and working-tree checks after committing.
- Final whole-repository verification, deterministic regeneration,
  remote Agent Skin regression and actual long-running orchestration
  parity must be recorded separately before an official main PR/merge.
- A clean candidate branch here is not a push and does not update local
  main or origin/main.

No `ours`/`theirs` choice has been made across Agent Skin production
conflicts: the remote Agent Skin tree is intentionally untouched by the
pstack-scoped transfer. Full two-history reconciliation of local main
must remain a separate Agent Skin-owned release decision.

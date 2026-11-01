# pstack downstream patch manifest

One upstream defect per patch over the pristine snapshot in
`packages/pstack-agent-harness/pstack/`. The queue is `patches/series`, applied in
order by `node tools/build-harness.mjs`, which reports **16 patches applied** and
writes `harness/`. `pstack/` is never written.

Test column: a test rides in the same patch. The watch-pr tests live next to the
sources under `pstack/skills/poteto-mode/scripts/watch-pr/`; the log.sh test is
`pstack/skills/show-me-your-work/scripts/log.test.ts`. Run them with `bun test`
from their own directory.

| patch | defect | failure scenario | test |
| --- | --- | --- | --- |
| 0002-policy-confirm-no-checks-before-ready.patch | 2 | A repository with no checks, and the seconds after a push before GitHub registers the new head's checks, read as a clean head, so the PR was reported ready to merge before its CI existed and a workflow that failed moments later was never seen. | yes |
| 0003-policy-require-mergeable-in-ready-proof.patch | 3 | Passing checks alone produced a ReadyPr whose proof claimed mergeability "clear" while GitHub still reported the mergeability UNKNOWN, so a PR was announced mergeable on the strength of its checks and no reading at all. | yes |
| 0004-policy-re-read-pr-facts-before-verdict.patch | 4 | The facts are read once and the checks and threads are collected afterwards, so a push, a base retarget, a new review or a draft toggle in that window left the verdict standing on a SHA and a base the PR no longer had. | yes |
| 0005-policy-wait-on-uncomputed-mergeability.patch | 5 | `gh pr view` reports a field it has not computed as "" and parsePullRequest raised that as a missing-key query error, so the watcher backed off with exponential delay and exited 7 instead of waiting out the poll interval. | yes |
| 0006-policy-honour-merge-gates.patch | 6 | After the checks passed the only gates left were closed, draft and changes-requested, so a PR that was behind its base, owed a required review, or sat BLOCKED under another branch protection rule was declared ready and the merge then failed. | yes |
| 0007-github-refuse-stalled-pagination-cursor.patch | 7 | A GraphQL connection that returned the same endCursor twice left the page walk spinning for ever, so the watcher never finished reading checks or review threads and produced no verdict. | yes |
| 0008-github-error-on-truncated-check-page.patch | 8 | A check rollup page reporting hasNextPage without an endCursor was folded into "no more checks", so every check past the first hundred disappeared and a PR with a failing check on page two read as clean. | yes |
| 0009-github-error-on-truncated-review-page.patch | 9 | The review thread reader folded the same shape into "no more threads", so the walk stopped at page one and every review thread past it, including an unresolved reviewer comment, was invisible. | yes |
| 0010-github-refuse-full-open-pr-page.patch | 10 | `gh pr list` returns the newest pull requests first with no truncation signal, so a full page handed stack discovery a list that had silently dropped an older PR from the bottom of the stack and the watcher drove the stack in the wrong order. | yes |
| 0011-github-raise-open-pr-list-limit.patch | 11 | `gh pr list` defaults to 30 rows and returns the newest first, so a repository with more open PRs than the requested limit silently loses the older stack edges, and the limit was a bare literal nothing shared with the truncation guard. | yes |
| 0012-github-scope-stack-to-head-repository.patch | 12 | Stack edges were matched on bare branch name, so a fork pull request whose head branch shared a name with a real stack member was joined into the ordering and the watcher drove a PR nobody in this repository could merge. | yes |
| 0013-github-do-not-retry-spawn-failure.patch | 13 | A process that could not be started surfaced as a raw node error and was treated as transient, so with `gh` missing from PATH the watcher backed off and retried for as long as the run lasted and never produced a verdict. | yes |
| 0014-github-time-out-gh-and-git-calls.patch | 14 | Every `gh` and `git` call was spawned with no deadline, so one call hanging on a stalled network or an unanswered credential prompt held the whole watch open and no verdict was ever produced. | yes |
| 0015-github-fail-finished-conclusions-in-pending-bucket.patch | 15 | gh files states it does not name alongside the in-flight ones in its `pending` bucket, so a check that had already finished with a conclusion such as STALE, STARTUP_FAILURE or CANCELLED was reported as still running and the watcher waited on it for the rest of the run. | yes |
| 0016-logsh-append-row-with-one-write.patch | 16 | The row is appended by a shell printf that hands a row longer than its buffer to the kernel in pieces, so two show-me-your-work writers running at once interleave those pieces and the TSV stops parsing; seven of eight rows came out malformed in a run of eight concurrent writers with a 200 KB cell. | yes |

## What the vendored snapshot already had

The defect list was written against an older tree. Three of its items were
already partly present upstream, and the patches above close what remains rather
than restate what is there.

- Defect 9. `resolveReviewThreads` already walks every page and the suite already
  covers it. What was left was the reader folding "hasNextPage without a cursor"
  into "no more threads", which is what ends that walk at page one; 0009 closes it.
- Defect 11. `gh pr list --limit 300` was already passed, as a bare literal. 0011
  shares `OPEN_PR_LIMIT` with the truncation guard and pins the request with a
  `gh` that truncates at 30.
- Defect 12. Parents were already scoped by gh's `isCrossRepository`. 0012 asks
  for `headRepository` and `headRepositoryOwner` and closes the child walk, where
  a fork pull request could still be joined in by branch name.

## Build tool repair

`tools/build-harness.mjs` ran `git apply` from the scratch root, which is nested
inside this repository. git resolves patch paths against the repository root and
silently skips every path outside the directory it runs from while still exiting
0, so all 16 patches were skipped and the build reported a pristine tree as
patched. It now pins `--work-tree` to the scratch. Without that change the
"harness trees written ... from N patch(es)" line is not evidence of anything.

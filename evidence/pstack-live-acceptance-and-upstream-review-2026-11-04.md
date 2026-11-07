# pstack release-gate follow-up — 2026-11-04

## Candidate and protection boundary

Candidate branch: codex/pstack-integration-20261104, original base
e7938da680f6919a1713e3b5334207a335e458cd. All changes in an
independent Treehouse lease e9fc3a4f5e073110147e941aac4af077.
Local main, origin/main, the original pstack-upstream-rebase branch,
the primary checkout's 20 uncommitted files, installed native plugins,
and every other Treehouse worktree remain untouched. No push or PR yet.

## Upstream source comparison (actual fetched files)

Read-only sparse checkout of cursor/plugins remote main at
bb68f2365eceafa0cb2d253112f675acf5f144cc compared with imported
c742dd61706fbacc1b95f1a20b7b988cf096ce6c:

| Source component | Same existing files | Changed | New upstream files |
| --- | ---: | ---: | ---: |
| pstack | 573 | 0 | 0 |
| thermos Skills | 3 | 0 | 0 |
| cursor-team-kit Skills | 6 | 0 | 15 |

The newer remote HEAD does not change the imported pstack runtime or existing
supporting Skill bytes. The 15 new cursor-team-kit files are additive and
not automatically part of the pinned pstack dependency set. Do not
unconditionally import them or drop any of the 19 quilt patches on the
basis of the upstream HEAD alone. 17 quilt patches are still Forwarded: no.

## Independent review boundary

A full main-to-integration Codex code review ran for 210 seconds, was
stopped at the configured timeout and did not issue a final review verdict.
It was not counted as a pass. A separate explicit read-only, scoped review
of a289eb0, 2a47194 and e7938da completed with exit 0 and reported
no P0, P1 or P2 defects in those three commits. It expressly did not
review the full 3,345-file change, the other quilt patches, or live host
behavior. No reviewer changes were applied to the repository.

## Actual Codex native pstack invocation

Host: the ChatGPT Desktop bundled Codex CLI 0.166.0-alpha.5.1, authenticated
as the existing user, using the native installed pstack-azhouzhou plugin
version 0.15.36. Verified source equivalence before the adapter fix:
639 files in the native cache match all candidate paths; the only two
different files were TypeScript tests github.test.ts and policy.test.ts.
Skill, model adapter, manifest and plugin prompts were byte-identical.

All coding tasks used synthetic temporary Python projects. No Agent Skin,
Hub code, user project, credentials or native plugin installation was
modified by the live acceptance commands.

- First ephemeral workspace-write run: the real CLI read the installed
  poteto-mode Skill and Codex adapter, initially reproduced 4 failing
  tests, then modified the isolated routes.py; a separate post-run check
  verified 4/4 tests pass. The parent CLI timed out at 230 seconds before
  an explicit turn.completed event. The model reported an unavailable
  parent rollout for an initial full-history child and subsequent
  fresh-context children. The report does not claim a successful
  multi-Agent closeout on this run.
- Bounded ephemeral read-only run: the same native Skill and adapter were
  loaded and it read the corrected fixture; tests passed 4/4 and a
  model answer was produced, but the CLI did not deliver turn.completed
  before its 120-second wrapper deadline. This is not evidence that the
  original defective fixture was already correct.
- Corrected persistent parent-session run: native CLI exit 0 and an
  actual turn.completed event. A fresh fixture started with 4 failures;
  the Agent fixed the code and the same 4 tests passed. Its final
  report says two independent read-only reviewers were started, one
  returned a docstring finding that was corrected, and the other was
  interrupted without a verdict. It explicitly did not claim a
  complete multi-agent review gate. A separate Python test invocation
  confirmed 4/4 passing after the session exited.

The persistent run shows that the real native Skill can perform a task
and cleanly finish. Model-agent diversity, exact model fallback,
two completed independent reviews and SessionStart hook trust remain
unverified. Do not promote the incomplete child review to PASS.

Observed host configuration warning: user-level luna-worker.toml lacks
developer_instructions and the role definition was ignored. This was not
modified, and it is not automatically attributed to pstack.

## Discovered and fixed Codex adapter defect

An actual Codex execution tried to read
poteto-mode/references/agents/comment-sicko.md and received ENOENT.
The Codex adapter instructed children to use that nonexistent path;
the real shipped file lives in the generated Codex plugin's
agents/comment-sicko.md.

Fixed the Hub-owned source
packages/pstack-agent-harness/hub-skills/poteto-mode/references/codex-tools.md
so that the leader resolves ../../../agents/comment-sicko.md
relative to the installed Codex adapter and passes the absolute path
to the child. No pristine upstream content was hand-edited.
Regenerated four host trees and added an explicit path-resolution
regression in tests/test_pstack_distribution_contract.py.
All 5 package-distribution tests pass.

The installed default Codex plugin cache still contains the old adapter:
this fix is in the new integration candidate only. It must be delivered
through a versioned, independently verified native plugin update;
do not manually overwrite the user's native-managed cache.

## Retired test inventory and risk

The previous main port had 58 files under the dedicated pstack tests
directory. Approximate classification by file intent:

| Class | Files | Remaining action |
| --- | ---: | --- |
| Pi port runtime-specific | 22 | Intentional retirement; Pi is unsupported |
| Copilot/Windows legacy-specific | 4 | Intentional retirement; not a maintained host |
| Old sync/fork generator | 5 | Superseded; 19-patch deterministic rebuild covers current generator |
| Agent/Hook/workflow contracts | 11 | Native host invocation, hook delivery, model routing need E2E |
| Install/lifecycle/recovery | 5 | Must retain native owner, idempotency, rollback tests |
| Other old port contract cases | 11 | Review individually for missing current consumer behavior |

Existing watch-pr tests (93 passed), Statechart (193 pass, 67
TLC-skipped in 9 offline suites), 5 distribution-contract tests and
Hub integration suites are not one-for-one replacements for all
retired runtime semantics. Statechart render test with external npm
dependencies was not executed in the offline run.

## Publication holds

1. Revalidate the new comment-sicko adapter fix on a VERSIONED installed
   plugin candidate before general publication; current native cache is
   deliberately unchanged.
2. Complete two independent model/Agent review results and capture the
   exact model choices and tool responses, not only a successful main turn.
3. Complete scoped owner lifecycle/rollback and hook-trust acceptance
   on maintained real hosts; do not claim ZCode GUI invocation from
   command listing alone.
4. Perform a bounded independent review of the broader imported quilt,
   select which of the old-port behavior tests must be retained, and
   decide what to forward upstream.
5. Only after these gates decide on main fast-forward, PR/push and
   installer migration. Preserve existing worktrees and lease owners
   until their own release/recovery criteria are met.

This report is an acceptance receipt with explicit negative claims,
not a statement that the distribution is now ready to release.

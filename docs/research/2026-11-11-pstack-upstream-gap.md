# pstack upstream / mirror / Hub GAP audit — 2026-11-11

This is an explicit pstack **upstream-maintenance** audit, not a Hub Skill upgrade, auto-evolution candidate, migration, or approval to install or change a live host. No upstream sources, patch series, generated trees, model sheets, or production installations were changed by this audit.

## Exact source identities and comparison

| Surface | Version / revision | Role |
| --- | --- | --- |
| Cursor upstream | `cursor/plugins/pstack` at pinned `c742dd61706fbacc1b95f1a20b7b988cf096ce6c`, plugin `0.15.36` | Hub's immutable vendored input |
| Hub pristine source | `packages/pstack-agent-harness/pstack/` | Must remain byte-identical to the pinned original import |
| Mirror upstream | `backnotprop/pstack@upstream`, `396c27e825b7aa656854e5a62e89f73ae9c0a17e` | Clean mirror source at comparison time |
| Mirror main | `backnotprop/pstack@main`, `08547969e1dffaa6457ea65141cc62c1d9a2eef1` | Independent cross-harness overlay |
| Hub distribution | `pstack-azhouzhou` candidate `0.15.37` | Hub-generated output with a 23-patch quilt |

The read-only comparison on 2026-11-11 cloned both mirror refs into temporary directories and compared regular-file relative paths and SHA-256 bytes. **Hub pristine vs mirror upstream: 573 / 573 identical, zero added/removed/changed.** This is file-byte equality at the stated revisions, not a claim of identical Git histories. **Mirror upstream vs main: 31 modified and nine added files**. The 40 changed paths below are a full ledger from GitHub's compare endpoint: [upstream...main](https://github.com/backnotprop/pstack/compare/upstream...main).

A second check of generated `harness/pstack/claude-code` and `harness/pstack/codex` against mirror main was **not** a like-for-like comparison: those are Hub host-specific outputs including additional component Skills and hooks. Do not treat the many expected generated changes as a count of missing upstream features. Hub holds 58 pristine pstack Skills and distributes 68 Skills when its additional cursor-team-kit, thermos and Hub babysit components are assembled. Both pstack sources have 23 core playbooks.

## Difference categories

| Category | Files | Disposition |
| --- | ---: | --- |
| harness-neutral instruction rewrite | 25 | Preserve upstream/Hub ownership boundaries |
| mirror packaging | 9 | Preserve upstream/Hub ownership boundaries |
| Windows runtime portability | 3 | Selective candidate with tests |
| review prompt packaging | 2 | Check host reference fallback |
| runtime safety / transcript discovery | 1 | Selective candidate with tests |
| **Total** | **40** | **Do not fast-forward or vendor mirror main wholesale** |

## Complete changed-file ledger

| Mirror path | Status | Classification | Hub action |
| --- | --- | --- | --- |
| `agents/comment-sicko.md` | modified | review prompt packaging | Assess |
| `mirror-assets/header-dark.svg` | added | mirror packaging | Keep separate |
| `mirror-assets/header-light.svg` | added | mirror packaging | Keep separate |
| `mirror-assets/sponsor-inbox-dark.svg` | added | mirror packaging | Keep separate |
| `mirror-assets/sponsor-inbox-light.svg` | added | mirror packaging | Keep separate |
| `mirror-assets/sponsor-plannotator-dark.svg` | added | mirror packaging | Keep separate |
| `mirror-assets/sponsor-plannotator-light.svg` | added | mirror packaging | Keep separate |
| `MIRROR.md` | added | mirror packaging | Keep separate |
| `README.md` | modified | mirror packaging | Keep separate |
| `skills/architect/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/arena/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/automate-me/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/create-verification-skill/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/how/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/interrogate/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/ketchup/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/maintain-verification-skill/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/no-comments/references/comment-sicko.md` | added | review prompt packaging | Assess |
| `skills/no-comments/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-help/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/playbooks/authoring-a-skill.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/playbooks/autonomous-run.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/playbooks/eval.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/playbooks/orchestrate.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/playbooks/session-pickup.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/poteto-mode/scripts/worktree-audit.sh` | modified | runtime safety / transcript discovery | Selective candidate |
| `skills/poteto-mode/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/recall/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/reflect/references/divergent-reviewer.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/reflect/references/judgment-reviewer.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/reflect/references/tooling-reviewer.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/reflect/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/setup-pstack/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/show-me-your-work/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/statechart/scripts/frontends/dot.ts` | modified | Windows runtime portability | Selective candidate |
| `skills/statechart/scripts/run.ts` | modified | Windows runtime portability | Selective candidate |
| `skills/statechart/scripts/statechart.ts` | modified | Windows runtime portability | Selective candidate |
| `skills/swarm/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `skills/why/SKILL.md` | modified | harness-neutral instruction rewrite | Compare by intent |
| `SYNC-LOG.md` | added | mirror packaging | Keep separate |

All nine added paths are mirror-only; the one portable review prompt in `skills/no-comments/references/` requires a reference-resolution check, while the mirror's sync log, top-level README additions and SVG assets do not belong in Hub's vendored upstream tree.

## Functional candidate assessments

**C1. Worktree audit transcript coverage.** Mirror main extends `worktree-audit.sh` to search Cursor, Claude Code and Pi project transcripts. Hub's generated script retains Cursor-oriented transcript discovery, but the Hub-specific `0023` quilt patch requires holding untracked, ignored and lease-owned state. Test both properties together, including active Claude/Pi sessions, spaces in paths, no matching transcripts, ignored sentinels, and no-force dry runs. **Never replace Hub's cleanup override with mirror text unreviewed.** No destructive cleanup is approved by this report.

**C2. Windows statechart behavior.** Mirror main changes `skills/statechart/scripts/frontends/dot.ts`, `run.ts`, and `statechart.ts` for CRLF splitting, Windows `taskkill` and staging/temp paths. Hub's pristine source excludes those mirror-only patches. Cross-platform CLI and cleanup validation is a gate before a narrowly scoped upstream defect patch. macOS-only invocation does not prove or disprove Windows behavior.

**C3. Comment Sicko reference.** Mirror main carries an additional reference copy while Hub already ships a host-adapted `agents/comment-sicko.md`. Check how `/no-comments` resolves the file on each maintained host, with an actual invocation before declaring a missing-feature defect.

**C4. Agent instruction portability.** Many mirror Skill rewrites map Cursor `Task`, model sheet locations and subagent parameters to Claude Code, Pi, Codex and OpenCode. Hub already generates host-specific adapter trees, uses a Codex-home scoped model sheet and a Claude configuration-root hook sheet, and explicitly supports only Codex, Claude Code, MiMo Code, ZCode and DeepSeek Harness. Compare behavior and model dispatch contracts, not just text. Blindly copying mirror main could regress the Hub's installation and ownership boundaries.

## Disposition and release gates

1. **Keep the pristine import pinned** while upstream's current content equals it; no upstream refresh is justified solely by mirror main differences.
2. **Preserve all 23 quilt patches and four generated host trees** pending individual proof. Re-run `node tools/build-harness.mjs`, targeted tests and `python3 scripts/verify.py` only in an owned isolated checkout on the exact patch; no build or tests were run in this documentation-only GitHub pass.
3. **Prioritize version-bound acceptance first**, tracked in [2026-11-11 read-only host inventory](../../evidence/pstack-host-readonly-inventory-2026-11-11.md). An installed version is not a verified workflow.
4. **Only then** propose C1 and C2 as small tested patch PRs; C3 and instruction rewrites remain investigation tasks until there is a reproducible host failure.
5. Forward upstream-defect fixes through the governance in [the patch debt ledger](2026-11-11-pstack-patch-debt.md); do not delete a loan until upstream includes the same behavior and the Hub rebuild/tests confirm it.
6. Keep pstack excluded from ordinary Skill upgrades and evolution as mandated by `AGENTS.md`. This work is explicitly scoped upstream-maintenance analysis only.

## Reproduction notes

The file-byte audit used temporary checkouts of `backnotprop/pstack` main and upstream and a SHA-256 digest per regular relative path, compared with `packages/pstack-agent-harness/pstack/`. It completed successfully before the remote execution channel reached its monthly quota. The mirror comparison was independently retrieved through GitHub's commit compare API. There was no production installation, mutation, cleanup or model call. Future snapshots must record new SHAs and recompute the ledger; **these results do not automatically describe future upstream revisions**.

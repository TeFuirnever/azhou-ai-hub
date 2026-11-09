# Upstream and import record

## Sources

The shipped plugin is assembled from three components of one upstream
repository, plus work this Hub authors. Each source keeps its own directory so
a component can be re-imported by replacing that directory alone.

| Directory | Source | At commit |
| --- | --- | --- |
| `pstack/` | [cursor/plugins `pstack`](https://github.com/cursor/plugins/tree/main/pstack) | `c742dd61706fbacc1b95f1a20b7b988cf096ce6c` |
| `components/cursor-team-kit/skills/` | [cursor/plugins `cursor-team-kit`](https://github.com/cursor/plugins/tree/main/cursor-team-kit) | same |
| `components/thermos/skills/` | [cursor/plugins `thermos`](https://github.com/cursor/plugins/tree/main/thermos) | same |
| `hub-skills/` | this Hub | n/a |

Upstream ships `pstack`, `cursor-team-kit` and `thermos` as sibling components
of one repository. `pstack/` alone does not carry `deslop`, `fix-ci`,
`fix-merge-conflicts`, `get-pr-comments`, `make-pr-easy-to-review`,
`what-did-i-get-done`, `thermos` or either `thermo-nuclear-*` review, so
importing only `pstack/` drops them. `NOTICE-skills.md` attributes the
distribution to the three sources listed above and its table maps one to one to
these directories.

The three pristine components are MIT. The additional engineering references include Apache-2.0 ZCode and MIT DeepSeek adaptations; [ENGINEERING-SOURCES.md](ENGINEERING-SOURCES.md) records their pins, licenses and local changes.

## Patches

`patches/` is a quilt-style queue over the assembled source. One file per
upstream defect, ordered in `patches/series`. Each file carries a DEP-3 header
(`https://wiki.debian.org/Specification/dep3`), and its `Forwarded` field says
whether an upstream pull request is open. A patch is a loan. It is deleted, and
its `series` line dropped, on the day upstream merges the fix.

A patch with `Forwarded: no` is a defect this queue is carrying that has not
been sent upstream yet.

## Building

```sh
node tools/build-harness.mjs
```

The build copies the assembled source and upstream's own
`scripts/generate-pstack-harness-trees.mjs` into a scratch directory, applies
`patches/series` there, and runs the generator to emit `harness/`. Upstream's
generator is not modified, so the Cursor-to-Claude-CCode rewrite and its
Cursor-ism scan stay upstream's to maintain.

Two failures are reported rather than absorbed. A patch that does not apply
stops the build. A patch that applies but changes none of the files it declares
also stops the build, because that is what upstream already carrying the fix
looks like.

`harness/` is generated output and is committed so the package can be read
without running a build. Re-run the generator after editing any source or
patch, and commit the result.

## Current distribution and remaining validation

The generator now emits four committed trees from the source and adapter
documents: `harness/pstack/claude-code/`, `codex/`, `zcode/` and
`skills-root/`. Each carries 68 skills; the additional `zcode-plugin/`
surface holds 41 commands, and the Codex native plugin holds 41 prompts.
`scripts/integration_pstack.py` reads `harness/pstack/codex/`. The
superseded fork-port directories (`plugins/`, `tests/`, `tla/` and
`lean/`) have been removed; this `tools/` directory holds the quilt
builder, not the old sync-based port.

The quilt currently has 24 patches: 17 upstream-defect patches and seven
Hub-specific adjustments (distribution identity, test type-narrowing,
command/agent namespace guides, the 0.15.37 version stamp, Claude
model-sheet alignment, conservative worktree-audit classification, and engineering-reference routing). The 17 `Forwarded: no` upstream-defect patches
still need upstream review/forwarding or replacement when upstream adopts a
fix. The current pinned import is `c742dd61706fbacc1b95f1a20b7b988cf096ce6c`;
upstream revisions must be compared and re-validated, not pulled silently.

The Hub-owned worktree-cleanup playbook overrides the pinned upstream
cleanup instructions to protect untracked, ignored and lease-owned files.
No safe/scratch classification authorizes force removal or recursive deletion.

Remaining acceptance is behavioral: real workflows and model dispatch on
each relevant host, lifecycle trust and host-specific invocation, plus
documented update/rollback. A registered plugin, readable skill or passing
generated-tree test is not sufficient evidence of a live workflow.

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

All licenses are MIT. The copyright notices and license terms travel beside
this file and beside the files they cover.

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

## Pending

The Codex and ZCode harness targets are not built yet. Upstream's generator
emits one tree, `harness/pstack/claude-code/`, from `pstack/docs/harness/claude-code.md`.
A Codex or ZCode target needs its own adapter document and its own generation
step, which is the remaining harness-adaptation work.

`plugins/`, `tools/`, `tests/`, `tla/` and `lean/` still hold the previous
port of this package, which maintained divergence with a sync tool and a fork
register rather than a patch queue. They are superseded and pending removal.
The Codex install adapter in `scripts/integration_pstack.py` still reads
`plugins/pstack/`, so that directory is kept until a Codex harness target
exists to repoint it at.

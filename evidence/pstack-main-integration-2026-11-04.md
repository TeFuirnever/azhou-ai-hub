# pstack upstream quilt: local main integration and verification (2026-11-04)

**Scope:** a new leased integration worktree, from local `main` at
`97c0459a6b6048e29612b1d73ea8581457d377a9`. This is **not** a
published release, and it did not rewrite the original `pstack-upstream-rebase`
branch, the main checkout's 20 uncommitted documentation edits, any existing
Agent Skin worktree/lease, or installed native plugins.

## Changes

- Merged `pstack-upstream-rebase` at `ab21b144059af0ff2fc2139cecc8a575932d8710`
  with local `main` in `codex/pstack-integration-20261104`:
  merge commit `2989d3a32368ce53da71efec7c33d550ded8e90b`, with both original
  parents intact. The only simultaneously modified path was
  `.github/workflows/ci.yml`; the three-way merge was conflict-free.
- A new downstream quilt patch
  `0019-downstream-watch-pr-typecheck.patch` corrects test-only narrowing
  of the `reported | no-checks` union and preserves a non-empty stack tuple;
  committed as `a289eb032652ae9246065cfd3b7f3d31571c475e`. Pristine
  `pstack/` and `components/` sources were not changed.
- CI now installs the built watcher's locked Bun dependencies, runs the
  strict TypeScript check, then runs the watcher tests. Four Python
  distribution-contract tests guard the four 68-skill trees, 41 Codex
  prompts, 41 ZCode commands, both native distribution identities and
  the ZCode no-skills/no-hooks boundary; committed as
  `2a471942e1967fe2048ef2ed3676a55deb01adcc`.
- Corrected the Claude Code install/update/remove plugin name,
  the Codex default-home owner boundary and the ZCode commands-only
  install path in the package README, the old native plugin ID in
  `docs/integrations.md`, and stale `UPSTREAM.md` pending claims.

## Independent acceptance observations

| Gate | Actual outcome |
| --- | --- |
| Quilt build | 19/19 patches applied; 4 trees, each 68 skills |
| Rebuild vs checked-in harness | 2,475/2,475 file SHA-256 values identical; zero missing/extra/changed |
| Bun offline lock installation | passed, Bun 1.3.14 |
| Watcher strict TypeScript | passed, TypeScript 7.0.2 |
| Watcher unit tests | 93 pass, 0 fail |
| Python distribution contract | 4 pass, 0 fail |
| CI workflow YAML syntax | valid (Ruby YAML parser) |
| Repository verification | `python3 scripts/verify.py --print-summary`: 8/8 gates passed |
| Statechart offline tests (9 suites) | 193 pass, 0 fail, 67 skip; `TMPDIR=/private/tmp` on macOS |

The initial scratch-only statechart run had two failures caused by an
incomplete copy of the Skill's `references/` directory and inconsistent
macOS `/tmp` versus `/private/tmp` symlink paths. The targeted symlink
case and the full nine-suite run passed after correcting the isolated test
fixture/environment; no runtime source was changed. The render test file
requires additional npm-backed rendering dependencies and was not executed.
Skipped TLC cases require `TLA2TOOLS`; do not present these as passing cases.

During the initial merge's **staged** whitespace inspection, 26 added
paths from pristine vendored content, generated copies and literal quilt
patches contained upstream whitespace. Those bytes were preserved rather
than rewriting the pinned source or breaking the patch context. The normal
repository policy and post-merge working-tree whitespace gates both pass.

## Remaining holds, not implied by green unit tests

1. **Real workflow proof:** complete `poteto-mode` agent dispatch and
   adversarial/multi-model review have not been exercised as an end-to-end
   same-candidate task on ChatGPT Desktop, Claude Code, ZCode or MiMo Code.
   The ChatGPT Desktop install/cache and ZCode commands listing have earlier
   evidence; no fresh-session command invocation or SessionStart trust
   receipt was supplied in this integration.
2. **Retired old port test coverage:** the previous `main` port's 58
   dedicated `packages/pstack-agent-harness/tests/` files were removed
   when the sync/fork runtime was retired. The new watch-pr, statechart and
   distribution tests establish the current system's contracts, but are
   **not** a proven one-for-one replacement for every legacy lifecycle
   and Pi-orchestration test. Review behavior vs retired scope before release.
3. **Upstream refresh:** the pinned import remains
   `c742dd61706fbacc1b95f1a20b7b988cf096ce6c`; a read-only upstream
   query on 2026-11-04 reported `bb68f2365eceafa0cb2d253112f675acf5f144cc`
   for `cursor/plugins` main. Changes were not imported or assessed for
   release. Of 19 quilt patches, 17 are `Forwarded: no` and two are
   `Forwarded: not-needed`; the former need upstream issue/PR review.
4. **Release:** neither local/remote `main` nor the installed plugins
   were updated by this work. The integration branch has no published PR,
   and final host E2E, release notes and rollback remain separate gates.
5. **Worktrees:** the original checkout's 20 modified files and all
   preexisting Treehouse lease holders remain intact. Do not return
   a lease merely because a worktree is Git-clean; installation or recovery
   may depend on its source path.

## Suggested completion order

Obtain an independent code review of the 19-patch quilt and CI changes;
execute real `poteto-mode` and selected command/Skill invocations with
source+model+hook receipts in each claimed host; review the upstream delta
and legacy-test retirement; then decide a PR/fast-forward or merge into
`main` and a scoped worktree lease recovery. Do not automatically push
or migrate the live `~/.codex` installation.

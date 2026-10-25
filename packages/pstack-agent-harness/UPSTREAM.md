# Upstream and import record

## Imported maintainer source

- Repository: <https://github.com/TeFuirnever/pstack-agent-harness>
- Immutable source commit: `356c6e0f978df729eb16f227d795f34d221c5aad`
- Source state at import: clean worktree at the recorded commit, checked on 2026-10-26.
- Import basis: all 373 tracked files from that commit. Git metadata, ignored/local files, and build state were not copied. Hub-local changes adapt README and CONTRIBUTING paths, add this record and the delivery descriptor, and remove extra blank lines at EOF in `plugins/pstack/skills/automate-me/SKILL.md` and `tests/runtime-packaging.test.mjs`; other imported files retain their source bytes and modes.

The source repository's Git remote and source commit identify the maintainer port snapshot. The tracked `tools/upstream.json`, `tools/substitutions.json`, and `tools/forks.json` continue to identify the port's upstream components, transformation rules, and intentional forks. The native package identity remains `pstack`; marketplace metadata remains `pstack-claude`.

`hub-package.json` is the Hub's neutral delivery descriptor. Its `runtime_paths` are relative to this package root and retain the prior Codex runtime surface, the full native plugin tree, applicable notices and licenses, package/version metadata, and the descriptor itself. Source, tests, maintainer documentation, and native metadata remain in the package even when they are not materialized for a Codex install.

## Component source pins and notices

At the imported commit, `tools/upstream.json` pins these source components:

| Component | Source repository | Commit |
| --- | --- | --- |
| `pstack` | <https://github.com/cursor/plugins> | `7b353f78f6ec193bdbe48ed8059444eb09b6878e` |
| `cursor-team-kit` | <https://github.com/cursor/plugins> | `e46364b8be46000b7df0f260550cd712afbb8d36` |
| `thermos` | <https://github.com/cursor/plugins> | `118e73b0e196e4d49d5aade7ce6dd8985a621f68` |

Keep `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`, `NOTICE-skills.md`, and the skill-local copies together with the files they cover. This record does not replace or broaden those licenses.

## Reproducing a source update

1. Clone the maintainer source repository and check out the full commit to import:

   ```shell
   git clone https://github.com/TeFuirnever/pstack-agent-harness /tmp/pstack-agent-harness
   cd /tmp/pstack-agent-harness
   git checkout <full-40-character-commit>
   git status --short --branch
   ```

2. Review the selected commit and its notices, then export the tracked source tree into the package directory. `git archive` excludes Git metadata and ignored local state while preserving tracked file modes and links:

   ```shell
   git archive --format=tar <full-40-character-commit> \
     | tar -xf - -C <hub-checkout>/packages/pstack-agent-harness
   ```

   Do not copy local tool installations or build output. Reconcile the package-root README note and this record instead of replacing them silently.

3. To advance the port's component sources, work in that standalone maintainer checkout, following `CONTRIBUTING.md`: update each component through `bun tools/sync.mjs <component> <new-upstream-sha>`, resolve and record any forks, then run the generator. The Hub snapshot has no independent PStack Git history, so do not run source syncs here. Commit the resulting maintainer-source snapshot in the upstream port before importing that new immutable commit here.

4. From `packages/pstack-agent-harness/`, run the package checks documented in `CONTRIBUTING.md`, including `bun install --frozen-lockfile`, `bun tools/generate.mjs --check`, `bun tools/validate-skills.mjs plugins/pstack/skills`, and `bun test tests/`.

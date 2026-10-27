# Upstream and import record

## Immutable original import

- Repository: <https://github.com/TeFuirnever/pstack-agent-harness>
- Immutable source commit: `356c6e0f978df729eb16f227d795f34d221c5aad`
- Source state at import: clean worktree at the recorded commit, checked on 2026-10-26.
- Import basis: all 373 tracked files from that commit. Git metadata, ignored/local files, and build state were not copied. Hub-local changes adapt README and CONTRIBUTING paths, add this record and the delivery descriptor, and remove extra blank lines at EOF in `plugins/pstack/skills/automate-me/SKILL.md` and `tests/runtime-packaging.test.mjs`; other imported files retain their source bytes and modes.

The source repository and full commit identify the original imported snapshot. They are provenance, not an ongoing installation or maintenance source. The Hub package under `packages/pstack-agent-harness/` is the maintained source for future installs. The tracked `tools/upstream.json`, `tools/substitutions.json`, and `tools/forks.json` retain the imported component pins, transformation rules, and intentional forks. The native package identity remains `pstack`; marketplace metadata remains `pstack-claude`.

`hub-package.json` is the Hub's neutral delivery descriptor. Its `runtime_paths` are relative to this package root and retain the prior Codex runtime surface, the full native plugin tree, applicable notices and licenses, package/version metadata, and the descriptor itself. Source, tests, maintainer documentation, and native metadata remain in the package even when they are not materialized for a Codex install.

## Component source pins and notices

At the imported commit, `tools/upstream.json` pins these source components:

| Component | Source repository | Commit |
| --- | --- | --- |
| `pstack` | <https://github.com/cursor/plugins> | `7b353f78f6ec193bdbe48ed8059444eb09b6878e` |
| `cursor-team-kit` | <https://github.com/cursor/plugins> | `e46364b8be46000b7df0f260550cd712afbb8d36` |
| `thermos` | <https://github.com/cursor/plugins> | `118e73b0e196e4d49d5aade7ce6dd8985a621f68` |

Keep `LICENSE`, `LICENSE-cursor-team-kit`, `LICENSE-thermos`, `NOTICE.md`, `NOTICE-skills.md`, and the skill-local copies together with the files they cover. This record does not replace or broaden those licenses.

## Preparing upstream updates

The original import remains pinned above for provenance. Version `0.9.103` adds local Hub installation instructions, preserves the ZCode model-sheet mapping from the retired local port checkout, and regenerates versioned manifests. It also declares the imported `automate-me` EOF normalization in `tools/forks.json`, allowing the sync tool to recognize that existing difference. The ZCode mapping records inspected local configuration; it does not claim native plugin or hook acceptance. These changes are maintained in the Hub, while the original import commit remains immutable.

For a component update, inspect the proposed full upstream commit and its notices, then run from `packages/pstack-agent-harness/`:

```shell
bun install --frozen-lockfile
bun tools/sync.mjs pstack <full-upstream-commit> --dry-run
```

The sync tool clones `tools/upstream.json`'s remote into its own temporary directory and reads the old and proposed component pins there. It reconciles those inputs with this package, so it does not require a separate maintained clone or component Git history in the Hub checkout. Review the report, then repeat the sync command without `--dry-run`. Resolve every reported conflict and reconcile `tools/forks.json`; keep the licenses and notices with the files they cover.

Version the result here: update `VERSION`, `CHANGES.md`, and the Hub descriptor version, then run the generator and checks documented in [`CONTRIBUTING.md`](CONTRIBUTING.md). Commit the reconciled package in the Hub repository. The generated manifests identify the maintained package release; the immutable import commit above continues to identify its original source.

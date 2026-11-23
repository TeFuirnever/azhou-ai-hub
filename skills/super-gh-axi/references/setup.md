# Dependencies and setup

Read this before first use or when the CLI, the `gh` binary, authentication, or any GitHub operation path fails.

## Runtime requirements

| Requirement | Locked baseline | Purpose |
|---|---:|---|
| Node.js + npm/npx | Node 20+ | Run `gh-axi` (the npm package declares `engines.node >= 20`) |
| `gh-axi` | `0.1.52` | Agent-ergonomic GitHub operations: issues, PRs, stacked PRs, discussions, workflow runs and dispatch, releases, repositories, labels, gists, Projects (v2), Actions secrets and variables, search, raw API |
| `gh` CLI | `gh >= 2.99.0` per the CLI's own guidance (for `--attach` on issue/pr create, edit and comment; `GH_BIN` overrides the binary) | The wrapped binary and its authentication |
| Network | npm fetch; GitHub API | Resolve the CLI when not installed and reach GitHub |

The package contains the Skill instructions only. The gh-axi CLI, its npm runtime dependencies, and the wrapped `gh` binary are not vendored; `npx` downloads the external CLI at execution time, and authentication stays with `gh` itself.

Fail closed: when Node 20+, npx, the locked baseline, the `gh` binary, or its authentication cannot be resolved, stop with a named hold. Do not fall back to a different version, an unpinned fetch, or a partial install.

## Inspect before executing

```bash
node --version
npm --version
gh --version
npx -y gh-axi@0.1.52 --help
npm view gh-axi@0.1.52 version dist.integrity repository.url license engines --json
```

`npx -y` downloads and executes the locked npm package when it is absent from the local cache. Review the npm metadata before first execution in a sensitive environment; the recorded integrity lives in [provenance.md](provenance.md).

## Run without a persistent install

```bash
npx -y gh-axi@0.1.52 issue list --state open
npx -y gh-axi@0.1.52 --help
```

This package itself writes no repository state; the CLI writes only what the requested GitHub operation does. The CLI's `setup hooks` subcommand changes user-level state — run it only with explicit authorization.

## Optional isolated install

Use a project-local install when repeated downloads are undesirable:

```bash
npm install --save-dev --ignore-scripts gh-axi@0.1.52
node "$(npm root)/gh-axi/dist/bin/gh-axi.js" --help
```

A global install changes user-level state. Run it only with explicit authorization. This repository does not install hooks automatically.

## Verify

```bash
npx -y gh-axi@0.1.52 --version
npx -y gh-axi@0.1.52 --help
```

Verify `gh` authentication with `gh` itself (`gh auth status`), then one read-only CLI operation against the target repository. Do not create, edit, merge, or release anything merely to prove package installation; a mutation is never a setup check.

## Upgrade

1. Select the newest official stable release of `kunchenguid/gh-axi` — a published tag/release, never a prerelease, a default-branch HEAD, or a metadata-only version bump.
2. Record the immutable release commit, the npm `dist.integrity`, the tarball SHA-256, and the `skills/gh-axi/SKILL.md` SHA-256 at that commit in [provenance.md](provenance.md).
3. Reconcile the upstream skill text and command surface with this package; move the lock in `SKILL.md`, `setup.md`, `upstream-compatibility.md`, and `tests/test_super_gh_axi.py` together.
4. Refresh the license copy and the third-party notice when the upstream license or bundled-notice bytes change.
5. Run the skill validator and `python scripts/verify.py` before promotion.

Do not silently float the locked baseline to the newest npm release, and do not use the CLI's built-in `update` command on the locked baseline.

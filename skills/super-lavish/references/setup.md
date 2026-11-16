# Dependencies and setup

Read this before first use or when the CLI, browser session, polling, export, or sharing path fails.

## Runtime requirements

| Requirement | Locked baseline | Purpose |
|---|---:|---|
| Node.js + npm/npx | Node 22+ | Run `lavish-axi` |
| `lavish-axi` | `0.1.97` | Open, poll, reply, export, end, and optionally share review artifacts |
| Browser | host default | Local interactive review surface |
| Network | npm fetch; optional remote assets/share | Resolve the CLI when not installed and load explicitly remote resources |

The package contains the Skill instructions only. The Lavish CLI, its npm runtime dependencies (`ws`, `open`, `parse5`, `daisyui`, `express`, `chokidar`, `axi-sdk-js`, `cross-spawn`, `@tailwindcss/browser` at the `0.1.97` release), the browser runtime, and remote assets are not vendored; `npx` downloads the external CLI at execution time.

Fail closed: when Node 22+, npx, or the locked baseline cannot be resolved, stop with a named hold. Do not fall back to a different version, an unpinned fetch, or a partial install.

## Inspect before executing

```bash
node --version
npm --version
npm view lavish-axi@0.1.97 version dist.integrity repository.url license engines --json
npx -y lavish-axi@0.1.97 --help
```

`npx -y` downloads and executes the locked npm package when it is absent from the local cache. Review the npm metadata before first execution in a sensitive environment; the recorded integrity lives in [provenance.md](provenance.md).

## Run without a persistent install

```bash
npx -y lavish-axi@0.1.97 <html-file>
```

This writes Lavish session state outside the repository and starts a local server/browser flow. This package itself writes no repository state: artifacts go where the request puts them (default `.lavish/<name>.html`), and `.lavish/` is ignored at the repository root. Keep artifacts with private comments or selection state out of Git unless the user explicitly selects a sanitized file for version control.

## Optional isolated install

Use a project-local install when repeated downloads are undesirable:

```bash
npm install --save-dev --ignore-scripts lavish-axi@0.1.97
node "$(npm root)/lavish-axi/dist/cli.mjs" --help
```

A global install or `lavish-axi setup hooks` changes user-level state. Run either only with explicit authorization. This repository does not install hooks automatically.

## Verify

```bash
npx -y lavish-axi@0.1.97 --version
npx -y lavish-axi@0.1.97 playbook table
npx -y lavish-axi@0.1.97 design
```

Do not open, share, or publish a real artifact merely to prove package installation. A share requires separate publication authorization because it uploads the artifact to a third-party service.

## Upgrade

1. Select the newest official stable release of `kunchenguid/lavish-axi` — a published tag/release, never a prerelease, a default-branch HEAD, or a metadata-only version bump.
2. Record the immutable release commit, the npm `dist.integrity`, the tarball SHA-256, and the `skills/lavish/SKILL.md` SHA-256 at that commit in [provenance.md](provenance.md).
3. Reconcile the upstream skill text and command surface with this package; move the lock in `SKILL.md`, `setup.md`, `upstream-compatibility.md`, and `tests/test_super_lavish.py` together.
4. Refresh the license copy and the third-party notice when the upstream license or bundled-notice bytes change.
5. Run the skill validator and `python scripts/verify.py` before promotion.

Do not silently float the locked baseline to the newest npm release.

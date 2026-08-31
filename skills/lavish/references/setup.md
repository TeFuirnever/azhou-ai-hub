# Dependencies and setup

Read this before first use or when the CLI, browser session, polling, export, or sharing path fails.

## Runtime requirements

| Requirement | Locked baseline | Purpose |
|---|---:|---|
| Node.js + npm/npx | Node 22+ | Run `lavish-axi` |
| `lavish-axi` | `0.1.47` | Open, poll, export, end, and optionally share review artifacts |
| Browser | host default | Local interactive review surface |
| Network | npm fetch; optional remote assets/share | Resolve the CLI when not installed and load explicitly remote resources |

The skill package contains instructions only. The CLI, browser runtime, and remote assets are not vendored.

## Inspect before executing

```bash
node --version
npm --version
npm view lavish-axi@0.1.47 version dist.integrity repository.url license engines --json
npx -y lavish-axi@0.1.47 --help
```

`npx -y` downloads and executes the locked npm package when it is absent from the local cache. Review the npm metadata before first execution in a sensitive environment.

## Run without a persistent install

```bash
npx -y lavish-axi@0.1.47 <html-file>
```

This writes Lavish session state outside the repository and starts a local server/browser flow. Keep `.lavish/` artifacts and private annotations out of Git unless the user explicitly selects a sanitized artifact for version control.

## Optional isolated install

Use a project-local install when repeated downloads are undesirable:

```bash
npm install --save-dev --ignore-scripts lavish-axi@0.1.47
node "$(npm root)/lavish-axi/dist/cli.mjs" --help
```

A global install or `lavish-axi setup hooks` changes user-level state. Run either only with explicit authorization. This repository does not install hooks automatically.

## Verify

```bash
npx -y lavish-axi@0.1.47 --version
npx -y lavish-axi@0.1.47 playbook table
npx -y lavish-axi@0.1.47 design
```

Do not open, share, or publish a real artifact merely to prove package installation. A share requires separate publication authorization because it uploads the artifact to a third-party service.

## Upgrade

1. Select an immutable commit from `kunchenguid/lavish-axi`.
2. Rebuild or read `skills/lavish/SKILL.md` at that commit and record its SHA-256 in [provenance.md](provenance.md).
3. Update the locked CLI version, npm integrity, license copy, compatibility map, public docs, and tests together.
4. Run the skill validator and `python3 scripts/verify.py` before promotion.

Do not silently float the locked baseline to the newest npm release.

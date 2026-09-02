# Dependencies and setup

Read this before first use or when the CLI, browser session, polling, export, or sharing path fails.

## Runtime requirements

| Requirement | Locked baseline | Purpose |
|---|---:|---|
| Node.js + npm/npx | Node 22+ | Run `lavish-axi` |
| `lavish-axi` | `0.1.47` | Open, poll, export, end, and optionally share review artifacts |
| Browser | host default | Local interactive review surface |
| Python | 3.11+ | Initialize, persist, inspect, and validate embedded relay state |
| Network | npm fetch; optional remote assets/share | Resolve the CLI when not installed and load explicitly remote resources |

The package contains the Skill instructions and a Python standard-library state helper. The Lavish CLI, browser runtime, and remote assets are not vendored.

## Inspect before executing

```bash
node --version
npm --version
python3 --version
npm view lavish-axi@0.1.47 version dist.integrity repository.url license engines --json
npx -y lavish-axi@0.1.47 --help
```

`npx -y` downloads and executes the locked npm package when it is absent from the local cache. Review the npm metadata before first execution in a sensitive environment.

## Run without a persistent install

```bash
npx -y lavish-axi@0.1.47 <html-file>
```

This writes Lavish session state outside the repository and starts a local server/browser flow. Relay mode also persists returned feedback inside the HTML packet. Keep `.lavish/` artifacts with private comments out of Git unless the user explicitly selects a sanitized packet for version control.

The relay state helper uses optimistic revisions and atomic replacement. Every mutation supplies `--expected-revision`; a stale writer exits nonzero without changing the packet. Successful replacement preserves the packet's existing permission bits. This protects one shared file from silent older-copy overwrite, but it is not a multi-user database or a network lock service.

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
python3 <skill-dir>/scripts/relay_state.py --help
python3 -m unittest tests.test_lavish_relay_state -v
```

Do not open, share, or publish a real artifact merely to prove package installation. A share requires separate publication authorization because it uploads the artifact to a third-party service.

## Upgrade

1. Select an immutable commit from `kunchenguid/lavish-axi`.
2. Rebuild or read `skills/lavish/SKILL.md` at that commit and record its SHA-256 in [provenance.md](provenance.md).
3. Reconcile upstream behavior with the local relay contract, including embedded-state compatibility.
4. Update the locked CLI version, npm integrity, license copy, compatibility map, public docs, and tests together.
5. Run the skill validator and `python3 scripts/verify.py` before promotion.

Do not silently float the locked baseline to the newest npm release.

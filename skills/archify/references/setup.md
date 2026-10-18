# Setup and runtime boundary

`archify` executes a self-contained Node.js CLI. There is nothing to install inside the skill package; the commands run from the package root or via its absolute path.

## Runtime requirements

- **Node.js 18 or newer** (`package.json` `engines.node`). The CLI imports only Node built-ins — there are no npm runtime dependencies, and `npm install` is never required.
- A local Chrome or Chromium is required only by `finalize`'s real-browser `browser-check` gate (and by `visual-check` captures). Without a browser that gate fails: report the failure as a named hold per the brand protocol; never describe a skipped browser gate as passed.
- Read and write access to the working directory for the `.archify/<type>-<slug>-<timestamp>/` request folders.

## Install

Copy the package to any location and invoke the CLI through the package path:

```bash
node /path/to/skills/archify/bin/archify.mjs doctor
```

## Verification (fail closed)

Run from the package root; every command must exit `0` before the skill is considered available:

```bash
node bin/archify.mjs doctor
node bin/archify.mjs guide "user requests an order status timeline" --json
node bin/archify.mjs validate workflow examples/agent-tool-call.workflow.json --quality showcase --json
```

- `doctor` walks the renderer/schema/example wiring for all ten modes; a missing or drifted vendored file fails it.
- `guide` proves the mode router loads (`"ok": true`).
- `validate` proves the schema validators and showcase gates load on a shipped example.

If any command fails, the runtime is broken: report the failing check verbatim and stop. Do not repair the package by mixing files from a different upstream version — re-vendor from the pinned tag recorded in provenance instead.

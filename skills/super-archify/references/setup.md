# Setup and runtime boundary

`super-archify` executes a self-contained Node.js CLI. Copy the complete package and invoke its CLI by absolute path; no npm runtime installation is required.

## Runtime requirements

- **Node.js 18 or newer** (`package.json` `engines.node`). Native code uses Node built-ins and shipped modules; the explainer's Pele chart subset is bundled with its licenses. Do not run `npm install` to repair missing package files.
- A local Chrome or Chromium is required for native diagrams' `finalize` browser gate, explicit explainer `--browser-check`, and visual captures. A missing browser fails a requested browser check; report a named hold, never a pass.
- Explainer `finalize` defaults to validate/deliver/check with browser-check `not-run`. That result proves artifact checks only. Add `--browser-check` to collect browser evidence; perceptual review remains separate.
- Read/write access to the chosen working directory for `.archify/<type>-<slug>-<timestamp>/` request folders. No global skill install, global rules edit or pstack transition is part of setup.

## Install

Copy the complete package to the authorized location and invoke the CLI:

```bash
node /path/to/skills/super-archify/bin/archify.mjs doctor
```

The package's canonical discovery/bin name is `super-archify`; the actual internal CLI filename remains `archify.mjs`. Official stable-update identity stays `archify` because it belongs to the upstream manifest protocol, not Hub discovery.

## Verification (fail closed)

Run from the package root:

```bash
node bin/archify.mjs doctor
node bin/archify.mjs guide "user requests an order status timeline" --json
node bin/archify.mjs validate workflow examples/agent-tool-call.workflow.json --quality showcase --json
node bin/archify.mjs validate explainer examples/delivery.explainer.json --json
```

- `doctor` checks native modes and explainer runtime/reader dependencies.
- `guide` confirms the native-mode router loads.
- Native `validate` confirms validators and showcase gates on a shipped example.
- Explainer `validate` confirms its schema, draft preparation and included dependencies.

For a real delivered artifact, use `finalize` on the complete requested input. Preserve its gate statuses and artifact identity; a validate-only success is not delivery evidence. For explainer browser verification:

```bash
node bin/archify.mjs finalize explainer /path/to/candidate.archify.md /path/to/answer.html --browser-check --json
```

Tests can set `ARCHIFY_UPDATE_CHECK_DISABLED=1` in that process to keep update checks from writing the upstream cache. Normal update awareness remains bounded and advisory; it never installs an upgrade. The canonical installer and existing installation ownership stay unchanged.

If a required check fails, report the exact failure and stop that delivery. Do not mix package files from different upstream versions. Reconstruct from the immutable stable source and the recorded local packaging delta.

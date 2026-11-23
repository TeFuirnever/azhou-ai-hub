# Dependencies and setup

Read this before first use, or whenever you need to confirm what this package requires and what it must never do on a machine.

## Runtime dependency

| Requirement | Source | Purpose |
|---|---|---|
| Node.js ≥ 18 (CommonJS) | host machine | `scripts/server.cjs` (the visual companion server) |
| a POSIX shell (`bash`) | host machine | `scripts/start-server.sh`, `scripts/stop-server.sh` |
| a local browser | host machine | rendering the visual companion pages |

There are **no npm dependencies**: the package ships no `package.json`, and every module `scripts/server.cjs` requires is a Node builtin. If Node or the browser is missing, the visual companion is unavailable and the design conversation continues in text — the upstream degradation path is retained and is the package's fail-closed behavior. Verify the scripts parse before first use:

```bash
node --check skills/super-brainstorming/scripts/server.cjs
```

## Network boundary

- **No external network request by default.** Branding and telemetry are off unless one of `SUPERPOWERS_ENABLE_TELEMETRY` or `ENABLE_TELEMETRY` is set truthy; when enabled, the page header fetches the upstream brand logo and links the upstream repository (this package's delta flips the upstream default from on to off).
- The server binds `127.0.0.1` unless `BRAINSTORM_HOST` says otherwise. Every request is gated by the per-session key carried in the URL (`?key=…`), so only someone holding the full URL can read or inject screen content.

## Session state and sensitive files

- Session state lives under `<project>/.superpowers/brainstorm/` (content, state, `.last-port`, `.last-token`). The token file is a capability: anyone who can read it can talk to a running server. Do not commit it; this repository gitignores `/.superpowers/` at the root, and downstream projects should do the same (the skill body already reminds the reader).
- Stop and clean with `scripts/stop-server.sh`; removing the session directory removes the recorded port and token. Nothing outside `.superpowers/` (or `/tmp/brainstorm` when no project dir is passed) is written.

## Related packages

During the design conversation, text sketches and browser mockups belong to this skill. Once the design is approved: UI implementation belongs to `super-frontend-design`, diagrams to `super-diagram-design`, and raster images to `super-imagegen`; the planning handoff goes to whatever planning workflow the reader chooses — this package does not chain into a sibling skill.

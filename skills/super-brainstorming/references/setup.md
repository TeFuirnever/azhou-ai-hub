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

Node 18 is the exercised floor: the recorded smoke run used the official Node.js v18.20.8 build (see the [benchmark record](../../../benchmarks/super-brainstorming/README.md#recorded-run)).

## Network boundary

- **No external network request from the companion's own chrome by default.** Branding and telemetry are off unless one of `SUPERPOWERS_ENABLE_TELEMETRY` or `ENABLE_TELEMETRY` is set truthy; the switches are read once at server startup, so set them before launching the server. When enabled, the page header fetches the upstream brand logo and links the upstream repository (this package's delta flips the upstream default from on to off). The opt-in brand header also resolves a version string from a manifest near the install root when one is present and sends it to the brand image host as a cache-buster; in this repository layout the lookup misses and renders `unknown`. Page content authored during a session may still load remote assets, as the guide suggests.
- The server binds `127.0.0.1` unless `BRAINSTORM_HOST` says otherwise. Every request is gated by the per-session key carried in the URL (`?key=…`), so only someone holding the full URL can read or inject screen content.

## Session state and sensitive files

- Session state lives under `<project>/.superpowers/brainstorm/`: each session directory `<session-id>/` holds `content/` and `state/`, while `.last-port` and `.last-token` sit at the namespace root, persisted per project so a restart reuses them. The token file is a capability: anyone who can read it can talk to a running server. Do not commit it; this repository gitignores `/.superpowers/` at the root, and downstream projects should do the same (the skill body already reminds the reader).
- Stop with `scripts/stop-server.sh <session-dir>`; removing the session directory removes its content and state but keeps the recorded port and token at the namespace root. Nothing outside `.superpowers/` is written when `--project-dir` is passed; without it the session lives under `/tmp/brainstorm-<pid>-<epoch>/` instead, and its `state/` files embed the session key.

## Known upstream behavior at the pin

The packaged scripts keep their upstream bytes, so these upstream behaviors ship as they are. The full record of six items, including two that concern mockup content, is in [upstream-compatibility](upstream-compatibility.md#accepted-upstream-behavior-notes-at-the-pin).

- **Pass a value with every value-taking launcher option.** `--project-dir`, `--host`, `--url-host` and `--idle-timeout-minutes` given without a value make `scripts/start-server.sh` loop until it is killed instead of reporting a usage error. A launch command that never returns is this loop: terminate it and correct the invocation.
- **Keep `--project-dir` outside `/tmp` when mockups must persist.** When it stops a running server, `scripts/stop-server.sh` deletes a session directory under `/tmp`, including a project-backed one; its `stale_pid` and `not_running` exits delete nothing, so do not rely on it to scrub a `/tmp` session.
- **Rely on the generated session key.** A key set through `BRAINSTORM_TOKEN` is not validated, and one containing `+` or `%` makes the printed entry URL fail to authenticate.
- **Stop the server before removing a session directory.** Deleting a running session's `content/` directory makes the next request crash the server process.

## Related packages

During the design conversation, text sketches and browser mockups belong to this skill. Once the design is approved: UI implementation belongs to `super-frontend-design`, diagrams to `super-diagram-design`, and raster images to `super-imagegen`; the planning handoff goes to whatever planning workflow the reader chooses — this package does not chain into a sibling skill.

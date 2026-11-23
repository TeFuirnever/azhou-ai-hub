# super-brainstorming benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records the smoke contract a contributor can run by hand; no run has been recorded at adoption time.

## Manual smoke contract

Run in a scratch directory (never a real checkout):

1. `node --check skills/super-brainstorming/scripts/server.cjs` — parses clean.
2. `bash skills/super-brainstorming/scripts/start-server.sh --project-dir <scratch-dir>` — expect startup JSON with `type=server-started`, a port, and a `url` containing `?key=`.
3. Fetch the cookie-authenticated companion page: `curl -c <jar> '<url>'` then `curl -b <jar> http://localhost:<port>/` — expect the companion waiting page shown until step 5 pushes a screen (the keyed URL alone serves only the bootstrap redirect page). The branding assertions apply to that page since the waiting page also runs through the same branding rendering: expect **no** `<img class="brand-logo">` and **no** `href="https://github.com/obra/…"` in the markup (branding defaults off; delta D4).
4. Stop the server and restart it as in step 2 with `SUPERPOWERS_ENABLE_TELEMETRY=1` set at startup, then repeat the step 3 fetch — the same waiting page shows the brand markup (the opt-in path still works).
5. Push a content fragment and confirm it lands under `<scratch-dir>/.superpowers/brainstorm/<session>/content/`.
6. `bash skills/super-brainstorming/scripts/stop-server.sh <scratch-dir>/.superpowers/brainstorm/<session>` — expect a clean stop and the session files removable.
7. Assert zero npm involvement at every step (no `npm install`, no `package.json` anywhere in the package).

Record the Node version alongside any run notes. The conversation behavior itself (exploration → approaches → design doc → approval gate) is a human-in-the-loop protocol and is walked through, not automated, by this contract.

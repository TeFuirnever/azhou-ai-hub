# super-brainstorming benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records the smoke contract a contributor can run by hand; executed runs are logged under [Recorded run](#recorded-run).

## Manual smoke contract

Run in a scratch directory (never a real checkout):

1. `node --check skills/super-brainstorming/scripts/server.cjs` — parses clean.
2. `bash skills/super-brainstorming/scripts/start-server.sh --project-dir <scratch-dir>` — expect startup JSON with `type=server-started`, a port, and a `url` containing `?key=`.
3. Fetch the cookie-authenticated companion page: `curl -c <jar> '<url>'` then `curl -b <jar> http://localhost:<port>/` — expect the companion waiting page shown until step 5 pushes a screen (the keyed URL alone serves only the bootstrap redirect page). The branding assertions apply to that page since the waiting page also runs through the same branding rendering: expect **no** `<img class="brand-logo">` and **no** `href="https://github.com/obra/…"` in the markup (branding defaults off; delta D4).
4. Stop the server and restart it as in step 2 with `SUPERPOWERS_ENABLE_TELEMETRY=1` set at startup, then repeat the step 3 fetch — the same waiting page shows the brand markup (the opt-in path still works).
5. Push a content fragment: write a small HTML fragment (for example `<h1>Smoke</h1>`) into the `screen_dir` returned in step 2 and confirm it lands under `<scratch-dir>/.superpowers/brainstorm/<session>/content/`; a repeat of the step 3 fetch then serves it inside the frame template.
6. `bash skills/super-brainstorming/scripts/stop-server.sh <scratch-dir>/.superpowers/brainstorm/<session>` — expect a clean stop and the session files removable.
7. Assert zero npm involvement at every step (no `npm install`, no `package.json` anywhere in the package).

Record the Node version alongside any run notes. The conversation behavior itself (exploration → approaches → design doc → approval gate) is a human-in-the-loop protocol and is walked through, not automated, by this contract.

## Recorded run

Two runs are recorded, both on macOS arm64 against the pushed bytes of this branch on the official Node.js v18.20.8 build.

2026-11-23 — steps 1-4 and 6: the scripts parsed, the server started and served the cookie-authenticated waiting page, the default page carried no `<img class="brand-logo">`, no upstream repository link and no external URL at all, the `SUPERPOWERS_ENABLE_TELEMETRY=1` restart showed the brand markup, and `stop-server.sh` returned a clean stop.

2026-11-24 — every step. Steps 1-4 and 6 repeated with the same results, and the project-backed session directory (its project outside `/tmp`) survived the stop. Step 5: a fragment written to the session's `content/` directory was served on the next request inside the frame template, titled `Visual Brainstorming` — with no brand markup and no external URL on a default server, and with the brand markup under `SUPERPOWERS_ENABLE_TELEMETRY=1`. Step 7: no `package.json` exists anywhere in the package.

Node majors below 18 were not exercised. Raw output stays Git-external in the maintainer evidence store.

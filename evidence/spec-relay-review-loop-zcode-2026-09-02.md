# Spec Relay review-loop receipt — zcode — 2026-09-02

This receipt records a redacted real-host check of the Spec Relay browser-review/foreground-polling/export surface in zcode. It contains no temporary path, user identity, account data or raw transcript; raw run artifacts stay Git-external.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (ZCode.app `3.10.1` bundle), Node.js 24.15.0, GLM-5.1 via the BigModel Coding Plan
- Mode: disposable checkout with the ten packages linked; host runs attempt-1 per harness; the browser-review/foreground-poll/export lifecycle ran against the host-produced packet

## Results

| Check | Result | Evidence |
|---|---|---|
| Host loads the spec-relay package | `PASS` | The canonical-load receipt returned the exact frontmatter `name: spec-relay` line for this package in its own attempt-1 run. |
| Host run creates a relay packet | `PASS` | The host run created a packet HTML file (one heading, one paragraph with a unique `data-review-id`), 4596 bytes, on the first bounded harness (attempt-2 of the harness, disclosed below). |
| Browser-review session lifecycle | `PASS` | Operator-run on the host-produced packet: session created with the package-pinned `lavish-axi@0.1.47` baseline; the session URL served HTTP 200; the foreground long-poll command ran attached and stayed alive until the bounded stop. |
| Standalone export | `PASS` | Operator-run: `lavish-axi@0.1.47 export` produced the portable standalone HTML export, exit 0; session ended cleanly afterward (`end` exit 0). |
| In-host full-route execution | `FAIL` (version-pinned blocker) | Two harness attempts died in the zcode autocompact guard (context refilled within fewer than 3 tool turns after compaction, three times in a row) during in-host route execution on zcode 0.16.5 with GLM-5.1. Both runs' host traceIds are recorded Git-external. The packet was created in the second attempt before the guard stopped the run; the poll and export steps never executed inside the host run. |

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout with the ten packages linked into `.agents/skills`.
2. Run one headless zcode prompt that force-loads spec-relay and creates the packet HTML at a Git-external path, keeping outputs bounded.
3. Operator-run the pinned CLI lifecycle on the host-produced packet: session create (`--no-open`), HTTP 200 probe, bounded foreground poll, standalone export, end.

## Claim boundary

This proves the zcode 0.16.5 host loads the spec-relay package and creates a relay packet, and that the browser-review/foreground-poll/export lifecycle completes against a host-produced packet on this machine. It does not prove the full in-host skill-route execution: two disclosed attempts died in the zcode autocompact guard (version-pinned host/model combination, zcode 0.16.5 + GLM-5.1), and no human browser annotation step was exercised. The matrix cell records the lifecycle receipt plus this disclosed in-host blocker. Raw run artifacts stay Git-external; nothing private is committed.
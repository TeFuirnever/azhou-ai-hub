# Lavish rich-HTML review loop receipt — zcode — 2026-09-02

This receipt records a redacted real-host check of the Lavish rich-HTML review-loop surface in zcode: the host run loads the lavish package and invokes the pinned CLI; the artifact review-loop lifecycle (session create, URL serve, end) runs on the host-produced artifact. It contains no temporary path, user identity, account data or raw transcript; raw run artifacts stay Git-external.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (ZCode.app `3.10.1` bundle), Node.js 24.15.0, GLM-5.1 via the BigModel Coding Plan
- CLI baseline: the package-pinned `npx -y lavish-axi@0.1.47` baseline (npx-resolved), plus the locally installed `lavish-axi` 0.1.53 binary for the end step; artifacts and session state Git-external
- Mode: disposable checkout with the ten packages linked into `.agents/skills`; one attempt-1 host run; one operator-run session lifecycle on the host-produced artifact

## Results

| Check | Result | Evidence |
|---|---|---|
| Host loads the lavish package | `PASS` | Headless run forced the package load (the canonical-load receipt returned the exact frontmatter `name: lavish` line for this package in its own attempt-1 run). |
| Host run creates an artifact and invokes the pinned CLI | `PASS` | The host run created a standalone HTML artifact (one heading, one paragraph) and invoked `npx -y lavish-axi@0.1.47 <artifact> --help`; exit 0 with the pinned CLI usage text returned verbatim inside the run. |
| Review-loop session lifecycle on the host-produced artifact | `PASS` | Operator-run on the same artifact: `lavish-axi@0.1.47 --no-open` created a review session at the local server; the session URL served HTTP 200; `lavish-axi end` ended the session cleanly (status `ended`, exit 0). |
| Local-only boundary | `PASS` | No publication, no share, no network publication action; session state Git-external. |

One pre-model invocation failure is disclosed: an earlier invocation passed an inaccessible `--cwd` path and the CLI refused it before any model run; the recorded host run is the first completed model run.

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout with the ten packages linked into `.agents/skills`.
2. Run one headless zcode prompt that force-loads lavish, creates a minimal HTML artifact outside the repository, and invokes the pinned `lavish-axi@0.1.47` CLI.
3. Operator-run the session lifecycle on the same artifact: create with `--no-open`, probe the returned session URL for HTTP 200, then `lavish-axi end`.

## Claim boundary

This proves the zcode 0.16.5 host loads the lavish package and invokes the pinned lavish-axi 0.1.47 CLI in a real host run, and that the review-loop session lifecycle (create/serve/end) completes on a host-produced artifact on this machine. It does not prove a human-feedback poll cycle (no human reviewer was in the loop), GUI-surface behavior, or the third-party share boundary. Raw run artifacts stay Git-external; nothing private is committed.
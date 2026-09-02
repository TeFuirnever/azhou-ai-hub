# Repo Pedant manual invocation receipt — zcode — 2026-09-02

This receipt records a redacted real-host check that a zcode headless model run loads the repo-pedant package and executes its documented read-only inventory snapshot invocation. It contains no temporary path, user identity, account data or raw transcript; raw run artifacts stay Git-external.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (ZCode.app `3.10.1` bundle), Node.js 24.15.0, GLM-5.1 via the BigModel Coding Plan
- Mode: disposable checkout, project-scope Agent Skills root (`.agents/skills`), linked install via the neutral Foundation CLI (same linked tree as the canonical-load receipt), headless non-interactive model runs, recorded attempt-1 harness iterations disclosed below

## Results

| Check | Result | Evidence |
|---|---|---|
| Host loads the repo-pedant package | `PASS` | Headless run forced the package load (same load route as the canonical-load receipt, which returned the exact frontmatter `name: repo-pedant` line for this package). |
| Documented read-only invocation executes in the host run | `PASS` | The run executed the documented `inventory_knowledge.py snapshot` command from the package setup reference against the checkout with a `none_discovered` memory decision, output to the `.azhou/repo-pedant/` runtime-state namespace. |
| Documented invocation artifact produced | `PASS` | `inventory.json` written under `.azhou/repo-pedant/` with schema keys `checks, files, generated_at, history_sources, holds, notes, projects, schema_version`; the run reported `EXITCODE=0` and the sorted key list. |
| Read-only boundary held | `PASS` | The only written paths were the disclosed runtime-state namespace and raw artifacts Git-external; the repo worktree stayed clean (git status clean at close). |

One earlier harness iteration (attempt-1) died in the host autocompact guard after the model ingested large tool output; one later iteration captured the artifact and `EXITCODE=0` but its stdout capture came back empty (operator capture/flush issue). The recorded receipt run (attempt-3) used a bounded-output reporting harness. All iterations are disclosed; the receipt run itself is attempt-1 of that fixed harness.

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout with the ten packages linked into `.agents/skills`.
2. Run one headless zcode prompt that force-loads repo-pedant and runs the documented snapshot command with a `none_discovered` memory decision.
3. Check `EXITCODE=0` plus the inventory artifact with the eight schema keys under `.azhou/repo-pedant/`.

## Claim boundary

This proves zcode 0.16.5 loads the repo-pedant package and executes its documented read-only inventory snapshot invocation in a real host run on this machine. It does not prove full repo-pedant reconcile/handoff/evolve modes, the history-collection parsers (already receipted 2026-09-01), or cross-host parity. Raw run artifacts stay Git-external; nothing private is committed.
# Public model-floor results

Each file in this directory is one frozen configuration's complete receipt set: one
attempt-1 receipt per manifest case, produced by `benchmark.py verify` under the
fair-run protocol and aggregated with `benchmark.py report`. Raw prompts,
transcripts and candidate artifacts stay Git-external; only these machine-readable
receipts are public.

- `codex-gpt-5.6-sol-2026-09-04.jsonl` — Codex CLI 0.152.0, `gpt-5.6-sol`
  (reasoning effort `xhigh`), 2026-09-04: 5/5 `firstPassUsable`, zero failure
  clusters, `evidenceEligible: true`. Visual review by a disclosed non-human
  reviewer (a vision model invoked by an agent session; identity recorded in each
  receipt). Aggregate receipt and claim boundary:
  [`evidence/excalidraw-model-floor-codex-2026-09-04.md`](../../../../evidence/excalidraw-model-floor-codex-2026-09-04.md).

These results prove this skill's delivery gate on one recorded ordinary-model
configuration; they are not a model leaderboard and make no cross-model or
cross-host claim.

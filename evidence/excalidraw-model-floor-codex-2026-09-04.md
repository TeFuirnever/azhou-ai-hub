# Excalidraw ordinary-model-floor aggregate receipt — Codex — 2026-09-04

This receipt records one frozen attempt-1 agent invocation per benchmark case for the excalidraw-diagram ordinary-model-floor suite, with semantic, deterministic and identified visual-review gates. It contains no temporary path, user identity, account data or raw transcript. The raw `results.jsonl` stays Git-external; only this aggregate is committed.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`, benchmark suite `benchmarks/excalidraw-diagram/ordinary-model-floor/` (five frozen cases) at local default-branch commit `7d16d6da321745b0fec8657c85d8b226e7755e12`
- Skill source: the user-scope linked install resolving to the same content (`~/.agents/skills/excalidraw-diagram` → the recorded commit) — the skill the user actually has, not a development tree
- Harness: headless `codex exec -s workspace-write`, Codex CLI `0.152.0`, model `gpt-5.6-sol` (reasoning effort `xhigh`), macOS arm64
- Fair-run protocol: identical prompt shape per case (the case prompt verbatim plus one delivery instruction), same skill tree, isolated empty Git-initialized working directories outside the model-visible harness tree, candidate frozen when the invocation ended, no post-hoc edits, one invocation per case (attempt 1)
- Verifier: `benchmark.py verify` (semantic + style/hygiene/overlap gates) and `benchmark.py report` (aggregate matrix)

## Aggregate result

```json
{"schema": 1, "cases": 5, "receipts": 5, "firstPassUsable": 5, "failureClusters": {"operational": 0, "semantic": 0, "deterministic": 0, "visual-review": 0}, "evidenceEligible": true}
```

| Case | Attempt | Semantic | Deterministic | Visual review | firstPassUsable |
|---|---|---|---|---|---|
| dataflow-pipeline | 1 | pass | pass (style, hygiene, overlap exit 0) | passed, zero defects | `true` |
| layered-architecture | 1 | pass | pass | passed, zero defects | `true` |
| lifecycle-retry | 1 | pass | pass | passed, zero defects | `true` |
| sequence-login | 1 | pass | pass | passed, zero defects | `true` |
| workflow-approval | 1 | pass | pass | passed, zero defects | `true` |

## Visual-review identity and method (disclosed)

Every rendered candidate was exported with the skill's official SVG/PNG export pipeline and reviewed against exactly the five documented defect classes (`clipping`, `node-overlap`, `label-overlap`, `unbalanced-whitespace`, `tofu`-class missing glyphs) by a non-human reviewer: a vision model invoked by the zcode agent session, recorded in each `run.json` as `ai-visual-reviewer (zai vision model invoked by the zcode agent session; non-human identity disclosed)`. No review was upgraded from skipped. One review-pipeline incident is disclosed: a remote image channel served a stale cached image for the second case; the mismatch was caught against the candidate's own text elements and the review was redone over the local file, reading the correct render. The committed verdicts reflect only the corrected, ground-truth-checked reviews.

## Run-boundary disclosures

- Before any attempt-1 invocation, a first runner pass aborted at the Codex CLI trust check ("Not inside a trusted directory") with no model session started; the runner was fixed (Git-initialized working directories) and every recorded attempt is from the corrected pass. The aborted pre-session refusals are not counted as attempts or failures.
- One `git init` invocation with two directory arguments failed silently (`git init` takes a single directory), delaying two sessions; both were re-launched after the fix and are the recorded attempts.

## Claim boundary

This proves that on this machine, one ordinary coding agent (Codex CLI 0.152.0, `gpt-5.6-sol`) produced a first-pass usable hand-drawn Excalidraw diagram on attempt 1 for all five frozen cases of this suite, under the fair-run protocol, with machine-verified semantic and deterministic gates and a disclosed non-human visual review. It does not prove performance on other models or hosts, interactive behavior, or any leaderboard claim. Publishing the public model-floor results matrix remains the roadmap-gated maintainer decision; this receipt supplies the precondition (five attempt-1 receipts with identified visual review). Raw run artifacts stay Git-external; nothing private is committed.

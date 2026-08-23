# Excalidraw Diagram benchmarks

Development-only evaluation layer for `skills/excalidraw-diagram/`. Nothing here ships in the runtime skill.

## Suites

- [`ordinary-model-floor/`](ordinary-model-floor/README.md): five attempt-1 cases with semantic, deterministic, and identified visual-review gates.

Prompts, assertions, reference fixtures, receipts, and expected flows stay outside the model-visible runtime package.

## Cross-harness evidence

Run Codex, Claude, zcode, and other harnesses against the same frozen runtime package, prompts, time limit, and tool access. Record harness and model in each external `run.json`. Keep private prompts, raw transcripts, user paths, and unredacted artifacts outside Git.

Commit only synthetic cases, aggregate receipts, failure mechanisms, paired decisions, and coverage limits. A reference fixture proves verifier wiring only; it is never model-performance evidence.

## Evolution gate

Runtime-side evidence handling and promotion boundaries are defined in [`history-evolution.md`](../../skills/excalidraw-diagram/references/history-evolution.md) and [`evolution-contract.md`](../../skills/excalidraw-diagram/references/evolution-contract.md).

1. Form one mechanism-level hypothesis from at least two independent ordinary failures, or one severe safety, permission, privacy, or corrupt-delivery failure.
2. Add a regression case before changing the skill.
3. Build the smallest isolated candidate; compare it with baseline on identical cases and permissions.
4. Require deterministic gates, identified visual review, no new safety regression, and three independent paired judges with reversed A/B order.
5. Show receipts, votes, checks, limitations, and diff; stop for human promotion confirmation.

## Validate

```bash
python3 benchmarks/excalidraw-diagram/ordinary-model-floor/benchmark.py check
```

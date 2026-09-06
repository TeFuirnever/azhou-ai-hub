# Provenance

## Source of the adapted material

- Upstream: https://github.com/deepseek-ai/deepseek-harness (MIT License)
- Immutable pin: commit `0a53fb55bea101816fa226bb964ae2bed71c343b` (merge commit of the 0.1.2-alpha.2 release, checked out 2026-09-05)
- Source paths: `.agents/skills/dsh-ci-test-reliability/SKILL.md` (SHA-256 `58e5de5c9cf7061eb4f39240dfcadc2e2e4a0cbf124f9c268f7e878bbf451dc1` at the pin) and `.agents/skills/dsh-ci-test-reliability/references/ci-flake-diagnosis.md`
- Capability baseline: the upstream skill's methodology is preserved — execution-topology model, atomic resource allocation, process-global state containment, platform-owned semantics (including the write-back tolerance and fresh-read expectation), timeout budgets against the lane (including the tighter-value reason), synchronization on state (including the scheduler-ordering bar), dispose-to-quiescence (including the late-completion proof), regression proof (including the killed-child rule, concurrent independent-process validation, and the stress-runs caveat), the flake-masking blacklist (including the budget-restoration guard), and the flake-diagnosis workflow, re-expressed as this package's [ci-flake-diagnosis.md](ci-flake-diagnosis.md).

## Adaptation boundary

- Upstream examples targeted a TypeScript/Vitest stack (`listen(0)`, `mkdtemp`, Vitest coverage selection, pnpm scripts); every rule is re-expressed for a Python standard-library and unittest/pytest stack, and the lane/gate reference names this repository's `scripts/verify.py`.
- The upstream diagnosis reference is collapsed and re-expressed, not translated: a Python-stack workflow with an eight-class failure taxonomy and a five-rung reproduction ladder replaces the upstream's file; mapping notes are in that file's header.
- The upstream cross-links into deepseek-harness test policy documents are collapsed into this package's own sections; no sibling-skill dependency exists.
- MIT notice: the upstream repository is MIT-licensed; the retained methodology is re-expressed, and the upstream license and this notice satisfy the attribution requirement. The upstream license text is available at the pinned commit (`LICENSE`).

## Reproducible update path

1. Diff the pinned upstream skill against the current pin: `git -C <deepseek-harness-checkout> show 0a53fb55bea101816fa226bb964ae2bed71c343b:.agents/skills/dsh-ci-test-reliability/SKILL.md` (and the diagnosis reference).
2. Map every methodology change onto the sections of this package's `SKILL.md` and `references/ci-flake-diagnosis.md`; keep examples in the Python stack.
3. Update the pin and the SHA-256 above only after the mapped change lands, in the same commit.

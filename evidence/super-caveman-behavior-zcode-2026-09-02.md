# Super Caveman behavior receipt (failed attempt) — zcode — 2026-09-02

This receipt records the honest attempt-1 result of running the pinned 19-case/44-criterion Super Caveman response contract through the real zcode host. The run did NOT meet the 19/19 claim gate; the matrix cell records the failure exactly. It contains no temporary path, user identity, account data or raw transcript; raw outputs and grading records stay Git-external.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (ZCode.app `3.10.1` bundle), Node.js 24.15.0, GLM-5.1 via the BigModel Coding Plan
- Runtime: unchanged stable skill tree `a011a085`; frozen prompts from `response-cases.json` (cases digest `3a01e2eb`); SC capsule injected via the opt-in zcode adapter and verified live before the suite (a probe run answered `active_mode=full`)
- Mode: one scripted attempt per case in file order at the contractual 120 s/case budget; raw outputs Git-external

## Result

| Measure | Value |
|---|---|
| Cases passed | 9 / 19 |
| Criteria passed | 25 / 44 |
| Format failures | 0 |
| High-risk failures | 2 (destructive-action, real-ambiguity) |
| Status | `failed` - the 19/19 claim gate is not met and the binding evaluation is unchanged |

- Seven cases (agent-owned-edit, debugging-cause, destructive-action, real-ambiguity, multi-step-progress, error-report, task-wins-options) exceeded the contractual 120 s/case budget on this host/model: completed single-prompt runs take 6-85 s on this machine, and the seven tool-use/long-form cases exceeded the cap with no output. These are budget exhaustions on this host/model, not host errors.
- Three completed cases failed content criteria: direct-answer mentioned the unrelated dependency the criterion forbids mentioning; stop-mode-default-style confirmed Super Caveman off but not the ADHD shaping in the required first line; host-plan-tool-state requires a plan-tool call, which the zcode headless surface does not take.
- Aggregate record: `benchmarks/super-caveman/results/revision-e6680676-attempt-1-summary.json` (status `failed`, `high_risk_failed` 2, `format_failed` 0); reviewer identity and review-record digest are recorded in the aggregate result; the review record itself stays Git-external.

## Disclosures

- One earlier suite invocation ran producer-context-invalid: an operator smoke uninstall had removed the SC hook events from the run home, so no capsule was injected. Its outputs are retained Git-external and are not evidence. The corrected harness re-verified injection live before the recorded suite.
- The zcode adapter used for injection is the staged build; it is not part of the unchanged tree, so the recorded tree digest is the current pinned tree.

## Claim boundary

This receipt proves exactly what the run shows: on zcode 0.16.5 + GLM-5.1 on this machine, the pinned 19-case contract completed with 9/19 cases and 25/44 criteria passing within the contractual budget, and the 19/19 claim gate failed. It does not support any behavior-parity claim for the zcode column, and the repo's binding passing evaluation remains the pinned a011a085 result. Raw run artifacts stay Git-external; nothing private is committed.
# AS-E2E-001: Defer two Agent Skin E2E structural simplifications

- **Status:** Accepted — defer; follow-up implementation not authorized by this ADR
- **Decision date:** 2026-11-10
- **Identifier:** `AS-E2E-001` — scoped to Agent Skin (`AS`) E2E tooling. `docs/decisions/` deliberately avoids bare `ADR-NNNN` numbers, which belong to the lazily created domain-modeling [`docs/adr/`](../agents/domain.md) numbering space, so the two namespaces can never collide on one ID.
- **Scope:** Agent Skin E2E tooling proposed in [PR #432](https://github.com/TeFuirnever/azhou-ai-hub/pull/432)
- **Source review:** `no-mistakes` run `01M72YYQ4TYCTFZ1HSR50KT74N`, reviewed HEAD `01d37f9027d7754863431a879924e26bbc78d239`
- **Decision:** Keep PR #432 focused on observable E2E safety and regression coverage. Reassess the two simplifications as separate, behavior-preserving follow-ups.

## Context and constraints

PR #432 introduces layered E2E checks for Agent Skin. The quick layer uses synthetic inputs and isolated unit tests; the cold-start (L4) and daily (L5) paths have different host-state and evidence boundaries. The review identified two *non-blocking structural* concerns, not demonstrated current failures.

Review approval means only that these refactors are deferred. It does **not** certify L4/L5 real-host acceptance, authorize installation or use of a daily user profile, waive required CI or coverage, approve unresolved security findings, or resolve the original worktree 13 lease-holder attribution. Keep PR #432 Draft until its own delivery requirements are met. Source links below pin the reviewed commit even if the branch later changes.

## Decision 1 — One journal-verdict engine versus duplicated implementations

**Review finding:** `simplify-duplicate-chain-assertion-engine` (warning, ask-user).

**Current code:**
- [Cold-start `assert_event_chain`](https://github.com/TeFuirnever/azhou-ai-hub/blob/01d37f9027d7754863431a879924e26bbc78d239/packages/agent-skin/tools/e2e-cold-start.py#L78-L161) parses and validates the cold-start journal.
- [Daily `assert_chain`](https://github.com/TeFuirnever/azhou-ai-hub/blob/01d37f9027d7754863431a879924e26bbc78d239/packages/agent-skin/tools/e2e-daily.py#L220-L348) separately implements overlapping stage ordering, refusal and exit assertions for the same `azhou-startup.event.v1` event family.

| Option | Benefits | Costs and failure modes |
|---|---|---|
| **A. Keep both for PR #432 — selected now** | No cross-layer dependency or new module in the active delivery; existing isolated evidence remains attributable to each path | Drift risk: a future event/stage/refusal rule could change on one path without changing the other |
| **B. Introduce a pure shared, parameterized verdict module — preferred for follow-up** | Single contract for stage order, refusal handling, timestamp ordering, and exactly-one-exit semantics; easier cross-layer consistency tests | Requires extraction, wiring changes, regression fixtures, negative controls and full coverage remeasurement; creates a shared failure domain |
| **C. Make daily import cold-start directly** | Fewer new files and likely a smaller immediate diff | Couples one CLI tool's import and initialization behavior to another; brittle with script-name imports and greater accidental runtime side-effect risk |

**Rationale:** This is a legitimate maintainability debt, but an extraction during E2E delivery changes both execution layers and the trust boundary being reviewed. Choose A for #432. When revisiting, prefer B over C if a pure module can be imported without CLI/process side effects. This is a direction for review, not preapproval of a particular API.

**Revisit when:** changing `EVENT_SCHEMA`, `REFUSAL_STAGES`, the cold/hot chain stages or exit-verdict rules; encountering divergent verdicts for the same synthetic journal; or separately scheduling an E2E architecture simplification. Require a new PR with independently specified green and red journal cases for **both** layers, including malformed records, reordered stages, refusals, nonzero/missing/duplicate exits and nonmonotonic timestamps. Existing ownership and failure-preserving tests must keep passing.

## Decision 2 — Retain or remove the single-choice profile flag

**Review finding:** `simplify-single-choice-profile-flag` (warning, ask-user).

**Current code:** [`e2e-cold-start.py` CLI](https://github.com/TeFuirnever/azhou-ai-hub/blob/01d37f9027d7754863431a879924e26bbc78d239/packages/agent-skin/tools/e2e-cold-start.py#L303-L337) accepts `--profile` but only one value (`disposable`); the delegated runner invokes the cold layer without selecting another profile. The emitted plan includes an explicit `profile` field.

| Option | Benefits | Costs and failure modes |
|---|---|---|
| **A. Keep the flag for PR #432 — selected now** | Preserves the current, documented CLI surface and plan shape; no compatibility change in a test-safety PR | One-option flag adds apparent configuration flexibility that does not exist |
| **B. Remove it immediately** | Simplest parser and fewer invalid-option paths | Breaking CLI change for external/manual callers, even if none are known locally; requires docs and regression updates |
| **C. Deprecate the flag, then remove in a versioned change — preferred if compatibility matters** | Provides an explicit migration path and stable existing behavior during transition | Maintains an alias temporarily and adds a deliberate release/deprecation step |

**Rationale:** There is no evidence another profile is necessary, but absence of known repository callers is not proof that the public CLI has no external users. Choose A for #432; do not make a compatibility change during delivery. At the next planned CLI contract revision, choose B if compatibility investigation shows no consumers, otherwise C. Preserve the plan's `profile: "disposable"` field unless an independent consumer audit justifies changing the schema.

**Revisit when:** changing the cold-start CLI contract, adding a second legitimate isolation mode, or obtaining evidence about external/manual use. Audit scripts, docs, tests, recorded commands, automation callers and supported CLI versions before removal. Verify invalid-profile handling and default `--plan` behavior remain fail-closed.

## Out of scope and delivery invariants

- These findings are **deferred refactors**, not waived Test, Review, Document, Lint, CI or host acceptance steps.
- Do not execute a real daily launcher or modify installed applications/user profiles to close this ADR. `--plan` is **not** an L4/L5 live-host result.
- Keep the strict full-production line coverage threshold (95% independently per required language), exit-code propagation, non-destructive state-root and marker ownership, and independent negative controls.
- Do not replace or release a leased worktree to resolve review findings.
- The review's informational `ship-observation-exit-zero-premature` finding concerns scoped stamp-step logging: the final ship process exit and full-chain receipt remain authoritative and fail-closed. Its wording can be reviewed separately; it is **not** one of the two deferred structural changes.

## Consequences and follow-up acceptance

**Positive:** PR #432 stays focused on its original E2E acceptance criteria; its review decision is traceable to exact findings, code and a pinned commit. **Negative:** dual journal engines and a redundant CLI option remain until follow-up work is explicitly prioritized.

A follow-up may close each item only when a separate, reviewed implementation (1) demonstrates equivalent public behavior with behavior-level tests and negative controls; (2) updates affected callers and docs; (3) passes the repository gate and full production coverage requirements; and (4) records the migration/compatibility decision. A later PR does not retroactively establish L4/L5 real-host evidence for #432.

**Traceability:** [PR #432](https://github.com/TeFuirnever/azhou-ai-hub/pull/432) · `no-mistakes` Review run `01M72YYQ4TYCTFZ1HSR50KT74N` · `simplify-duplicate-chain-assertion-engine` · `simplify-single-choice-profile-flag`. The local pre-ADR handoff exists under ignored `.planning/agent-skin/no-mistakes-review-followups-20261110.md` and is not itself a published source of truth.

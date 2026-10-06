# Neat-freak compatibility contract

Contract version: v2 (2026-10-07). The v1 ledger below remains bound to the pinned upstream baseline; the v2 revision adds the upstream v3 delta section. `super-repo-pedant` is an enhancement of `neat-freak`, not a replacement. Every original capability remains mandatory unless this contract records a direct safety conflict or a demonstrated implementation disadvantage.

## Baseline and upstream v3 delta

- Implementation baseline: upstream `neat-freak` at immutable commit `bab178311a65f93ffd073e4fdebc9911eae35791` (pre-v3 line), hash-locked by `scripts/check_repository.py`. Every ledger row below is judged against this baseline, and the parity claim stays scoped to it.
- Upstream observation baseline: `322346ded8129436b3f64707789a73e732ae24d9` (2026-10-07 snapshot; upstream HEAD of `main`; self-declared `metadata.version: "3.0.0"` in frontmatter, no matching git tag or release). The pin→v3 range is 50 commits / 117 changed files; all `neat-freak/` surface changes are covered by the per-capability audit in [`docs/research/2026-10-07-neat-freak-v3-capability-audit.md`](../../../docs/research/2026-10-07-neat-freak-v3-capability-audit.md).
- Audit verdict (2026-10-07): **equivalent evolution** — of the 28 baseline rows, 20 are `kept`, 8 are `changed` in mappable ways (trigger framing, size-limit tables replaced by platform-derived budgets, the 30-line red-flag threshold generalized, per-file judgment narrowed to affected files, conversation review implied, report restructured), and 0 are removed. No row below is invalidated: wherever v3 wording weakened, this package's own implementation still enforces the stronger baseline form.
- Upstream convergence: v3 independently adopted the same safer semantics this contract chose for all three replacement rows — deletion candidates now require explicit user confirmation (baseline row `whole-file-deletion`), memory defaults to read-only unless authorized (row `trigger-inferred-milestone`), and concrete path tables are declared non-permanent with verify-current checks (row `concrete-cross-runtime-paths`).
- Upstream-additive capabilities (12, e.g. completion fact-face matrix, lightweight path, release-closeout state machine, cleanup confirmation gate, governance rule-chain audit, generated-memory read-only boundary, eval surface) are recorded with dispositions in the audit document; they are observations, not new mandatory rows. Adopting any of them changes skill behavior and requires its own evidence path through this repository's gates and tests.
- One recorded local divergence: the local trigger contract keeps bare `tidy`/`整理` as a positive trigger in development context (`benchmarks/super-repo-pedant/trigger-cases.json` `bare-tidy` → `reconcile`), while v3 makes a zero-context bare `整理` a negative trigger. The local stricter do-not-under-trigger design is retained; aligning it would be a trigger-behavior change requiring the local trigger regression.
- Monitoring: the next routine upstream freshness scan re-runs the pin→HEAD compare and re-judges this delta table; any future upstream change to `neat-freak/SKILL.md` or `evals/` triggers a same-shaped re-audit before any pin or contract move.

## Classification

| Status | Meaning |
|---|---|
| `preserved` | Current super-repo-pedant already provides the capability. |
| `restored` | The initial super-repo-pedant draft weakened or omitted the capability; the current package restores it with regression evidence. |
| `conflict_replaced` | Literal behavior conflicts with super-repo-pedant's authorization boundary; preserve the user value through a safer behavior. |
| `disadvantage_replaced` | Literal mechanism is stale or less reliable; preserve the outcome with verified discovery. |
| `additive` | New super-repo-pedant capability with no neat-freak equivalent. |

## Required original behavior

| Area | Original capability | Current classification | Required target |
|---|---|---|---|
| Trigger | Recognize explicit cleanup, sync, milestone, stale-doc, memory-conflict, and handoff phrases, including bare `tidy` or `整理` in development context | `restored` | Full bilingual phrase detector plus a negative guard: ordinary implementation that merely mentions the skill is not closeout intent. |
| Trigger | Inferred milestone immediately mutates knowledge files | `conflict_replaced` | Inference emits one closeout reminder; explicit invocation authorizes mutation. This prevents unrequested repository writes. |
| Audiences | Reconcile user docs, project agent rules, and project-bound agent memory | `preserved` | Keep all three default project surfaces. |
| Audience separation | Rules contain durable coding constraints; docs teach users/operators; memory stores durable non-obvious context | `preserved` | Keep content tests and avoid duplicated authorities. |
| Anti-bloat | Run size checks before synchronization | `restored` | `inventory_knowledge.py snapshot` records lines/bytes before edits. |
| Anti-bloat | Oversized active knowledge is the highest cleanup priority | `restored` | Validator requires a size resolution/hold before closeout. |
| Anti-bloat | Treat agent-rule net growth above 30 lines as a red flag | `restored` | Validator compares pre/current lines and requires an explanation. |
| Anti-bloat | Enforce review limits for rules, memory index/items, and single docs | `restored` | Mandatory limits cover rules, memory index/items, and docs without blind deletion. |
| Inventory | Mechanically enumerate root, docs, Markdown, agent memory, and active instruction surfaces | `restored` | Inventory v2 enumerates repository Markdown and explicit candidates, then requires bound paths, concrete none-discovered evidence, or a hold for every project memory surface. |
| Inventory | Read README, project agent rules, every docs Markdown file, relevant memory files, and active global instruction candidates | `restored` | Every enumerated file must receive a classification. |
| Inventory | Review the full available conversation/task record | `restored` | `history_sources` plus mandatory history and coverage checks. |
| Inventory | Mark every file as evaluated, update, or no-change | `restored` | Validator rejects every unclassified record. |
| Impact | Use a concrete code-change-to-document matrix for APIs, environment, data model, workflows, deployment, terminology, and downstream contracts | `restored` | Detailed forward/reverse matrix and four document roles. |
| Cross-project | Run the complete inventory for every affected upstream/downstream project | `restored` | Repeated `--project` roots share one exhaustive manifest. |
| Editing | Perform real edits, merging or deleting stale entries instead of describing future work | `preserved` | Keep minimal edits and stable receipts. |
| Editing | Prefer reduction, merge, precision, absolute dates, reader fit, and one maintained source | `preserved` | Keep all editorial rules. |
| Editing | Delete obsolete files and tasks without a separate checkpoint | `conflict_replaced` | Stale entries inside owned files may be removed; whole-file/directory deletion stays a precise user checkpoint. |
| Editing | Read global agent config but edit it only for explicit cross-project principles | `restored` | Global candidates are read-only in the manifest; validator rejects `update`/`merge`. |
| Docs | Update integration, architecture, runbook, and handoff/current-history surfaces where affected | `restored` | Every role is explicitly classified even when its filename is absent. |
| Validation | Check every inventoried file, memory link/description/contradiction, path, command, tool, environment variable, and README setup | `restored` | Eleven semantic checks plus deterministic inventory and execution-protocol validators; success is emitted only after all fixed checks. |
| Validation | Check API, environment, data-model, downstream, and relative-time propagation | `restored` | Detailed matrix plus required propagation/relative-time checks. |
| Special case | Create missing README and project agent rule files once runnable code exists | `restored` | Runnable-stage validator requires minimal surfaces. |
| Special case | Audit old drift even when the current conversation adds no new facts | `restored` | Main flow explicitly requires drift and previous-omission review. |
| Special case | Unresolved memory contradiction is the only user intervention | `conflict_replaced` | Preserve contradiction checkpoint; super-repo-pedant additionally checkpoints global writes, unclear ownership, whole-file deletion, publication, deployment, and unrelated repositories. |
| Special case | Repair omissions from previous cleanup runs | `preserved` | Keep within current authorized project scope. |
| Runtime paths | Use concrete Claude, Codex, OpenCode, and OpenClaw path tables | `disadvantage_replaced` | Keep concrete candidates and harness guidance, but verify current path and project ownership; never claim a runtime lacks memory from a stale table. |
| Output | Report memory changes, documentation changes grouped by project, and unresolved items | `preserved` | Stable receipt may add authority, verification, hold, and learning fields. |

## Additive super-repo-pedant behavior

- Code and machine-readable configuration are the only current-behavior authority.
- Unimplemented spec intent stays in a separate reminder channel.
- Modes: `audit`, `reconcile`, `handoff`, and evidence-gated `evolve`.
- Stable closeout receipt and explicit `hold` semantics.
- Deterministic stage protocol with exact brand anchors and a last-event success gate.
- Cross-runtime history collection with privacy-preserving digests and schema validation.
- Isolated candidate evolution, deterministic regressions, paired judges, and human promotion.

## Proof rule

The compatibility claim is false if any baseline row returns to `restore_required`. Every `restored` row has:

1. a runtime instruction or deterministic implementation;
2. a benchmark or unit regression;
3. a passing result recorded in `benchmarks/super-super-repo-pedant/results.tsv` or a machine-readable parity report.

`conflict_replaced` and `disadvantage_replaced` rows require explicit rationale plus a regression that proves the preserved user outcome. Machine status and evidence routing live in repository-level `benchmarks/super-super-repo-pedant/neat-freak-parity.json` and `regression-map.json`.

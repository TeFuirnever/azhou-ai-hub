# Neat-freak compatibility contract

Contract version: v3 (2026-10-18). `super-repo-pedant` is an enhancement of `neat-freak`, not a replacement. Every original capability remains mandatory unless this contract records a direct safety conflict or a demonstrated implementation disadvantage.

Lineage: the package was absorbed from upstream `neat-freak` at pre-v3 commit `bab178311a65f93ffd073e4fdebc9911eae35791`; the 2026-10-07 per-capability audit judged the upstream v3.0.0 delta an equivalent evolution; on 2026-10-18 the workspace owner directed the reference baseline to move to v3. Local behavior did not change in that move — this package stays a strict superset of the v3 reference.

## Baseline

- Reference baseline: upstream `neat-freak` **v3.0.0** at commit `322346ded8129436b3f64707789a73e732ae24d9` (2026-10-07 snapshot, self-declared `metadata.version: "3.0.0"`, no matching git tag or release), hash-locked under `benchmarks/super-repo-pedant/upstream/neat-freak/` by `scripts/check_repository.py` (`SKILL.snapshot.md`, `references/agent-paths.md`, `references/sync-matrix.md`, `references/governance.md`, `references/verification.md`). Every ledger row below is judged against this baseline, and the parity claim stays scoped to it.
- Absorption lineage: pre-v3 pin `bab178311a65f93ffd073e4fdebc9911eae35791` (50 commits / 117 changed files to v3). The pin→v3 delta was audited per capability in [`docs/research/2026-10-07-neat-freak-v3-capability-audit.md`](../../../docs/research/2026-10-07-neat-freak-v3-capability-audit.md) and judged an **equivalent evolution** — of the 28 baseline rows, 20 are `kept`, 8 are `changed` in mappable ways, and 0 are removed. The 8 changed rows below restate the v3 wording; wherever v3 wording weakened, this package's own implementation still enforces the stronger baseline form.
- Upstream convergence: v3 independently adopted the same safer semantics this contract chose for all three replacement rows — deletion candidates now require explicit user confirmation (ledger row `whole-file-deletion`), memory defaults to read-only unless authorized (row `trigger-inferred-milestone`), and concrete path tables are declared non-permanent with verify-current checks (row `concrete-cross-runtime-paths`). The historical replacement rationales against the pre-v3 wording are retained on those rows; under the v3 reference the two sides are aligned.
- One recorded local divergence: the local trigger contract keeps bare `tidy`/`整理` as a positive trigger in development context (`benchmarks/super-repo-pedant/trigger-cases.json` `bare-tidy` → `reconcile`), while v3 makes a zero-context bare `整理` a negative trigger. The local stricter do-not-under-trigger design is retained; aligning it would be a trigger-behavior change requiring the local trigger regression.
- Upstream-additive capabilities (12, e.g. completion fact-face matrix, lightweight path, release-closeout state machine, cleanup confirmation gate, governance rule-chain audit, generated-memory read-only boundary, eval surface) are recorded with dispositions in the audit document; they are observations, not new mandatory rows. Adopting any of them changes skill behavior and requires its own evidence path through this repository's gates and tests.
- Monitoring: the next routine upstream freshness scan re-runs the v3→HEAD compare and re-judges this baseline; any future upstream change to `neat-freak/SKILL.md` or `evals/` triggers a same-shaped re-audit before any baseline or contract move.

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
| Trigger | Recognize the named triggers (`neat-freak`, `洁癖`, `/neat`) plus knowledge-closeout intent phrases in English and Chinese, with explicit negative triggers: pure coding, JSON/weekly/changelog tidy, and zero-context bare `整理` (v3 wording) | `restored` | Full bilingual phrase detector plus a negative guard: ordinary implementation that merely mentions the skill is not closeout intent. |
| Trigger | Memory defaults to read-only unless the user or project closeout rules authorize writing; cleanup requires a full report and user confirmation (v3 wording) | `conflict_replaced` | Inference emits one closeout reminder; explicit invocation authorizes mutation. This prevents unrequested repository writes. v3 independently converged to this safer semantics; the replacement rationale is retained for the pre-v3 lineage. |
| Audiences | Reconcile user docs, project agent rules, and project-bound agent memory | `preserved` | Keep all three default project surfaces. |
| Audience separation | Rules contain durable coding constraints; docs teach users/operators; memory stores durable non-obvious context | `preserved` | Keep content tests and avoid duplicated authorities. |
| Anti-bloat | Run size checks before synchronization | `restored` | `inventory_knowledge.py snapshot` records lines/bytes before edits. |
| Anti-bloat | Reduce before adding, with a self-check that abnormal main-rule net growth was re-compressed (v3 wording; the explicit highest-priority sentence was dropped upstream) | `restored` | Validator requires a size resolution/hold before closeout. |
| Anti-bloat | Treat abnormal agent-rule net growth as a red flag (v3 wording; the concrete threshold was generalized upstream) | `restored` | Validator compares pre/current lines and requires an explanation. |
| Anti-bloat | Size budgets derived from the platform: CLAUDE.md quality budget, Claude auto-memory MEMORY.md 200-line/25KB hard limit, Codex project instruction chain 32KiB (v3 wording; the fixed limit table was replaced upstream) | `restored` | Mandatory limits cover rules, memory index/items, and docs without blind deletion. |
| Inventory | Mechanically enumerate root, docs, Markdown, agent memory, and active instruction surfaces | `restored` | Inventory v2 enumerates repository Markdown and explicit candidates, then requires bound paths, concrete none-discovered evidence, or a hold for every project memory surface. |
| Inventory | Read README, project agent rules, every docs Markdown file, relevant memory files, and active global instruction candidates | `restored` | Every enumerated file must receive a classification. |
| Inventory | Extract code facts from real inputs, current code, schemas, configuration, and tests (v3 wording; the explicit conversation-review step became implied upstream) | `restored` | `history_sources` plus mandatory history and coverage checks. |
| Inventory | Every affected file is read and receives a change/no-change judgment, with per-surface status compensating (v3 wording; per-file judgment was narrowed upstream) | `restored` | Validator rejects every unclassified record. |
| Impact | Use a concrete code-change-to-document matrix for APIs, environment, data model, workflows, deployment, terminology, and downstream contracts | `restored` | Detailed forward/reverse matrix and four document roles. |
| Cross-project | Run the complete inventory for every affected upstream/downstream project | `restored` | Repeated `--project` roots share one exhaustive manifest. |
| Editing | Perform real edits, merging or deleting stale entries instead of describing future work | `preserved` | Keep minimal edits and stable receipts. |
| Editing | Prefer reduction, merge, precision, absolute dates, reader fit, and one maintained source | `preserved` | Keep all editorial rules. |
| Editing | Deletion candidates go to the user for confirmation and stay unremoved until confirmed (v3 wording) | `conflict_replaced` | Stale entries inside owned files may be removed; whole-file/directory deletion stays a precise user checkpoint. v3 independently converged to this semantics; the replacement rationale is retained for the pre-v3 lineage. |
| Editing | Read global agent config but edit it only for explicit cross-project principles | `restored` | Global candidates are read-only in the manifest; validator rejects `update`/`merge`. |
| Docs | Update integration, architecture, runbook, and handoff/current-history surfaces where affected | `restored` | Every role is explicitly classified even when its filename is absent. |
| Validation | Check every inventoried file, memory link/description/contradiction, path, command, tool, environment variable, and README setup | `restored` | Eleven semantic checks plus deterministic inventory and execution-protocol validators; success is emitted only after all fixed checks. |
| Validation | Check API, environment, data-model, downstream, and relative-time propagation | `restored` | Detailed matrix plus required propagation/relative-time checks. |
| Special case | Create missing README and project agent rule files once runnable code exists | `restored` | Runnable-stage validator requires minimal surfaces. |
| Special case | Audit old drift even when the current conversation adds no new facts | `restored` | Main flow explicitly requires drift and previous-omission review. |
| Special case | Unresolved memory contradiction is the only user intervention | `conflict_replaced` | Preserve contradiction checkpoint; super-repo-pedant additionally checkpoints global writes, unclear ownership, whole-file deletion, publication, deployment, and unrelated repositories. |
| Special case | Find existing entries and edit them in place before adding parallel versions (v3 wording; the explicit previous-omission repair sentence became implied upstream) | `preserved` | Keep within current authorized project scope; the explicit previous-omission check is retained. |
| Runtime paths | Keep concrete Claude/Codex tables with official links, derive unknown runtimes by probing, and declare the table non-permanent (v3 wording) | `disadvantage_replaced` | Keep concrete candidates and harness guidance, but verify current path and project ownership; never claim a runtime lacks memory from a stale table. v3 independently converged to this semantics; the replacement rationale is retained for the pre-v3 lineage. |
| Output | Two-stage report skeleton — impact, changes and creations, awaiting your confirmation, leftovers — plus a supplemental report after cleanup (v3 wording; per-project grouping is no longer explicit upstream) | `preserved` | Stable receipt may add authority, verification, hold, and learning fields. |

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
3. a passing result recorded in `benchmarks/super-repo-pedant/results.tsv` or a machine-readable parity report.

`conflict_replaced` and `disadvantage_replaced` rows require explicit rationale plus a regression that proves the preserved user outcome. Machine status and evidence routing live in repository-level `benchmarks/super-repo-pedant/neat-freak-parity.json` and `regression-map.json`.

# Review against independent requirements

Read this before reviewing a design or diff; include these obligations in any delegated review brief. Establish the live base and exact head, then read the owning requirements before judging implementation. Refresh facts after a retarget, merge or rewritten push.

For each added field, option, adapter, state machine or compatibility branch, identify the current consumer and the behavior it requires. A new test, rule or design note authored with the change is a design decision, not independent proof that the extra concept is necessary. Consider deleting the concept before relocating it. Trace configuration through actual precedence; forwarding a value does not prove it is read.

Trace both sides of every interface, including errors, cancellation, disposal and generated or installed consumers. Exercise denial at the executing operation and alternate entry paths. Validate the complete result after wrappers and metadata, including tiny/exact bounds, oversized chunks and multibyte data. Keep borrowed values and owned state distinct; inspect every derived view at the actual success point.

Inspect what the model or user actually receives. Compare prompts, schemas, diagnostics, UI text and transcript projections through the owning runnable path; source strings alone do not prove runtime exposure. Shipped manifests and built entries need their own smoke evidence. Negative controls must fail through the real acceptance runner. Missing required checks, skipped blocking checks and unknown results are not success.

Challenge simplification proposals with their strongest retention reason. Trace imports, re-exports, string-driven registration, external consumers and persistent data before deleting. Preserve ownership, authorization, durability, cancellation and first-terminal-result behavior. Moving an unnecessary representation does not remove its maintenance cost.

Report the defect, tight location, observable impact and evidence; distinguish blockers from suggestions. Verify bot findings technically and resolve addressed threads only after the fix or evidence-based rebuttal. Never bypass the destination repository's required checks or merge policy. In the Hub, the full repository verifier and squash-only merge policy remain mandatory; another project's selective-check or merge-commit policy does not apply.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.

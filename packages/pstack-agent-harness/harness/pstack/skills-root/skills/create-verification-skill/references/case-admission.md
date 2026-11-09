# Admit cases using observed evidence

Read this when defining verification journeys, recording replay data, changing a coverage matrix or promoting a regression case. Use the existing project's case store and runner; do not create a second promotion database.

Each case names the requirement, setup, action, observable assertions, real entry, runtime/package revision, input identity and evidence location. Select behavior-changing dimensions after tracing affected consumers. Undefined behavior stays a question; a pass through a state without an assertion is not coverage.

Keep these states distinct: proposed, runnable, passed, failed, blocked, and not run. A passing runner establishes only assertions it actually reached. If setup or an earlier assertion fails, mark downstream assertions not run. Preserve the failed attempt and its artifacts. Missing credentials, unavailable hosts and judge errors are blocked or inconclusive, never pass.

Recordings are observations, not their own oracle. Review expected behavior against an independent requirement before adopting it. Label requests as scenario-specific, shared, intentionally ignored with a reason, or synthetic with a reason. Keep case-specific answers local. Choose timing intentionally: fast functional data, controlled streaming for cancellation, recorded cadence for performance, or explicit fault injection.

Before promotion, replay the isolated candidate with its intended inputs and no accidental fallback to a legacy shared fixture. Run the shipped package entry or composition when packaging can affect behavior. Bind evidence to the case, expected assertions, input bytes and tested revision. A declared `reviewed` or `verified` flag is not evidence. Honor the repository's human approval rules; a run alone cannot approve promotion.

If promotion changes multiple files, use the existing transaction owner: preview the changes, audit the tentative state, commit only after the audit succeeds, and restore the prior owned state on failure. If no transactional tool exists, keep the candidate separate until a reviewed atomic Git change passes the owning audit; do not claim filesystem rollback. Revalidate affected evidence after edits. Preserve unrelated cases and recovery points.

For UI journeys, inspect the actual assembled screen, neighbors and relevant loading, error, disabled, expanded and focus states. Check long and localized content, wrapping, access to primary actions, keyboard access, hover versus touch and focus across layout changes. Use the product's supported viewports, not another project's hard-coded minimum. Layout clipping must not hide errors or controls. Icon-only actions need accessible names and an explanation available to the supported input modes. Preserve drafts during responsive changes.

A recording must name the demonstrated revision, actual server or app, fixture/live conditions and whether a model round ran. Keep recording separate from publication. Synthetic events or a mock provider cannot stand in for a requested real-model demonstration. Publish only with task authorization and after checking for private content.

A verification skill that has not driven its mapped entry and retained its evidence after cleanup remains a draft. State any stand-in environment and the real-target steps still unverified. Report coverage per entry and case, not a single percentage that hides blocked paths.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.

# super-frontend-design evaluation contract

Bounded real-task evaluation contract for the `super-frontend-design` canonical skill (CONTRIBUTING.md, "Add a skill": deterministic package tests plus at least one bounded real-task evaluation contract). This directory is development-time material; the runtime package under `skills/super-frontend-design/` never carries benchmarks.

Status: **exploratory** — no bounded run has been recorded yet. Nothing below is a quality claim; it defines what a future run must freeze.

## Frozen inputs for a run

1. Brief template: one frozen brief per run, naming the product subject, the audience, the primary job, and any pinned visual direction; stored verbatim in the run record.
2. Token-plan artifact: the required first-pass deliverable (named color hex values, typeface roles, layout concept with alignment guidance, principles) captured exactly as produced.
3. Runtime package digest: the `skills/super-frontend-design/` tree digest at run time, recorded next to the attempt.

## Rubric

Five default-tell clusters from the upstream calibration list, each a named tell a judge can point at in the produced artifact:

1. warm cream background with a terracotta or warm-clay accent;
2. near-black background with a single bright acid-green or vermilion accent;
3. broadsheet-style layout with hairline rules, zero border-radius and dense newspaper-like columns;
4. the SaaS-card kit: identical rounded cards, one border-radius everywhere, the same soft grey shadow, gradient washes as decoration;
5. template chrome: ALL-CAPS eyebrow labels, middle-dot meta strings, em-dash label fragments, tinted near-black standing in for black, monospace small-data labels, appended arrows.

Quality floor for a passing run: the artifact names its one deliberate bold move, states what the brief-review pass changed and why, and meets the upstream floor (responsive down to mobile, visible keyboard focus, reduced motion respected).

## Judge record format

Each run records: date, brief digest, package digest, a per-tell verdict (present or absent, with the pointing evidence), the quality-floor verdicts, and a one-paragraph judge summary. No run, no claim: until a recorded run exists, every mention of this contract stays marked exploratory.

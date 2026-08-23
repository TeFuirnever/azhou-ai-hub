# Bounded evolution contract

Repo-pedant learns from execution evidence without granting historical data or background hooks authority over the live skill. This contract adapts useful mechanisms from ECC and keeps Darwin's paired, human-approved promotion gate.

## Evidence units

Each observation is an atomic, project-scoped record. Required fields:

- `signal_id`, `schema_version`, `observed_at`, and `project_id`;
- `runtime`, `session_digest`, `source`, and `provenance`;
- `category`, `mechanism`, `severity`, and `outcome`;
- redacted evidence references or digests, never raw transcript content;
- explicit user feedback when present: `accepted`, `corrected`, `rejected`, or `none`;
- privacy and authorization classifications.

Silence is not positive evidence. Missing feedback remains `none`. A fallback store, parser truncation, redaction, or coverage gap must be visible in the receipt.

## Candidate lifecycle

```text
observed -> corroborated -> proposed -> regression_ready
         -> paired_reviewed -> human_approved -> promoted
         -> rejected | expired
```

- Ordinary change: at least two independent failures with the same mechanism.
- Severe safety, authorization, or privacy failure: one occurrence may form a candidate.
- Project scope is the default. Cross-project or global scope needs comparable evidence from at least two projects plus explicit human approval.
- Candidate generation writes only to an isolated proposal bundle. Hooks and observers never edit the live `SKILL.md`, references, project rules, global rules, or memory.
- One candidate carries one falsifiable behavioral change. Mixed changes split into separate rounds.

## Evaluation and promotion

Promotion requires all gates:

1. deterministic schema, privacy, authorization, size, and regression checks pass;
2. baseline and candidate run on the same real test prompts;
3. an odd number of same-judge paired comparisons, minimum `N=3`, prefers the candidate by majority;
4. no safety regression or unresolved hold exists;
5. a human explicitly approves the exact diff.

Absolute scores and 7-day/30-day health trends are triage signals only. Unpaired aggregate success rates, confidence thresholds, occurrence counts, or absence of correction cannot promote a candidate.

## Runtime controls

- Explicit `evolve` invocation starts candidate generation. Lifecycle hooks may append bounded, redacted signals only when separately enabled.
- Use a minimum batch size, bounded sample, cooldown, re-entrancy guard, and processing cap.
- Retain unprocessed evidence after failure. Archive a batch only after its proposal bundle validates and its receipt is written.
- Expire stale pending candidates; never delete accepted evidence history silently.
- Prefer Python standard library and repository-local state. Optional accelerators must fail open and report their absence.

## Versioning and rollback

Git commit history and exact candidate diffs are the source of rollback. Keep append-only receipts for observation, evaluation, decision, promotion, rejection, and rollback. Do not duplicate full `SKILL.md` snapshots under `.versions/`; that creates an extra authority and unnecessary growth.

Rollback restores a known-good tree through an explicit repository change and records a new receipt. It never erases the failed candidate or its evidence.

## ECC mechanisms retained

- typed observation, outcome, feedback, provenance, and amendment lineage;
- project-first identity and precedence;
- validation, containment, atomic writes, dry runs, pending TTL, and malformed-row tolerance;
- bounded collection, command fingerprints, secret-type labels, and fail-open hooks;
- throttling, cooldown, re-entrancy, capped sampling, retry retention, and archive-after-success;
- health trends for investigation and prioritization.

## ECC mechanisms rejected

- background Claude directly writing or updating instincts;
- automatic global-scope inference;
- confidence `0.7` or occurrence counts authorizing behavior;
- “user did not correct” as success evidence;
- raw tool input/output or transcript replay as routine learning storage;
- unpaired two-run evaluation without safety veto;
- silent state-store fallback;
- duplicate full-file snapshots inside the skill.

## Required regressions

1. A single ordinary failure cannot form a candidate; one severe safety failure can.
2. Hook input is bounded and redacted; raw commands and secrets never enter stored evidence.
3. Candidate output is contained outside the live skill and cannot escape through symlinks or traversal.
4. Promotion fails without deterministic checks, paired majority, safety clearance, and exact human approval.
5. Cross-project/global candidates fail without two-project corroboration and human approval.
6. Failed processing retains the source batch; successful validated processing archives it once.
7. Health decline creates investigation status only, never promotion or rollback.

# Bounded evolution contract

Super Repo Pedant learns from execution evidence without granting historical data or background hooks authority over the live skill. This contract adapts useful mechanisms from ECC and keeps Darwin's paired, human-approved promotion gate.

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
- Project scope is the default. Before counting sessions or severe triggers, accept only signals whose recorded `project_id` matches the requested project's existing identity; this also applies to included signal files and copied local batches. Same-origin linked worktrees retain that shared identity. Cross-project or global scope needs comparable evidence from at least two projects plus explicit human approval.
- Candidate generation writes only to an isolated proposal bundle. Hooks and observers never edit the live `SKILL.md`, references, project rules, global rules, or memory.
- One candidate carries one falsifiable behavioral change. Mixed changes split into separate rounds.
- Attribute the failure before selecting an edit: skill content, trigger/routing, tool environment, permission, model capability or the task itself. Record raw source references, applicability, expected change and possible regression, including successful controls. Do not convert every environment failure into another skill instruction. Honor caller exclusions for both mutation and efficacy sampling; a reference or protected object is not automatically an evaluation subject.

## Evaluation and promotion

Promotion requires all gates:

1. deterministic schema, privacy, authorization, size, and regression checks pass;
2. baseline and candidate run on the same real test prompts;
3. an odd number of same-judge paired comparisons, minimum `N=3`, prefers the candidate by majority;
4. no safety regression or unresolved hold exists;
5. a human explicitly approves the exact diff and actual source binding.

`bind` computes a content binding from the raw candidate and patch bytes, the exact full base/candidate commits and trees, and the Git common-directory identity. The candidate is one nonempty commit directly on the base. It replays and reverses the patch using only a temporary index/object directory, requiring both resulting trees to match. `gate` additionally requires a clean checked-out base, evaluation and human-approval `source_binding_sha256` values, and an externally supplied `--expected-binding-sha256` matching the computed binding. Declared hashes alone no longer authorize the CLI gate.

`gate` is a read-only preflight, not an application receipt or a lock. The explicit Git application owner must serialize edits, recheck immediately before applying, and call `verify-applied` afterward with the same patch, versions, evidence and approval anchor. Only a clean actual commit directly on the approved base with the approved result tree verifies; a squash commit may have a different commit id but must have that parent and tree. The tool never applies to live source, commits, promotes, resets or rolls back automatically. Failed checks preserve source; explicit Git reverse/revert and a new receipt handle recovery.

Raw tracked bytes, executable modes on POSIX and index entries must match the committed version. Non-ignored untracked files, hidden index flags, submodules, changes involving symlinks, invalid paths and oversized candidates are rejected. Ignored runtime state is excluded, not certified harmless. Git environment redirects and global configuration are not inherited; repository hooks are disabled for every observational Git command, and no clean/smudge filter is used to validate source bytes. Temporary storage must be outside every registered worktree, the common Git directory and any enclosing Git repository. The private temporary index is workspace isolation, not an OS sandbox. Hashes bind content but do not authenticate a human, model run, reviewer independence or permissions. Another clone requires a new binding; linked worktrees share the Git common-directory identity.

Historical evaluation schemas remain structurally readable. The pure `validate_promotion` helper checks record structure only; it is not the actual source gate. Historical metadata-only invocations must acquire a fresh binding and approval rather than silently upgrading their authority.

Freeze task inputs, evaluator/answers, pass rules, permissions, budgets and rollback/stop conditions before candidate edits. Separate development, selection and final holdout by task/session source; disclose related or reconstructed cases. The candidate modifier must not change its evaluator or answers. Run each evaluation in a fresh independent copy, bind inputs/commands/artifacts to the exact revision, and verify protected originals and copies before/after. Preserve invalidated or polluted runs; restored bytes do not prove that pollution never occurred. Single-writer coordination must keep the tested source and evaluator stable throughout verification.

Distinguish an in-scope unresolved safety/approval hold from an unrelated environment observation. Each hold names the affected action, dependency/evidence, owner and release condition. Unknown host drift is not automatically attributable to the candidate or a blocker for all independent work; it still qualifies any trial whose controls cannot be established. Never erase an actual safety failure by relabeling it. Keep existing record validation strict: classify unrelated observations outside the candidate's promotion holds rather than claiming they were resolved.

Task benefit must be supported by paired artifacts and executable checks, not votes alone. Report quality, constraint violations, actual corrections, time and observable usage, including retries/search/judging; keep unavailable money and human time unknown. Record any post-hoc scope correction separately, preserving the original cohort, outputs, ratings and incurred costs. Do not relabel a reduced cohort as preregistered or use an excluded case to justify another optimization.

Integrity repairs have their own falsifiable correctness checks; they do not establish task-quality gain. Reject unsupported behavioral optimization without inventing another layer. Name experience reuse, instruction optimization, workflow repair, agent changes and improver changes separately. Recursive-improvement claims require descendant self-improvement lineage and an equal-budget fixed-improver comparison. Governance edits do not retroactively certify old experiments or approver identity.

Absolute scores and 7-day/30-day health trends are triage signals only. Unpaired aggregate success rates, confidence thresholds, occurrence counts, or absence of correction cannot promote a candidate.

## Runtime controls

- Explicit `evolve` invocation starts candidate generation. Lifecycle hooks may append bounded, redacted signals only when separately enabled.
- Use a minimum batch size, bounded sample, cooldown, re-entrancy guard, and processing cap.
- Retain unprocessed evidence after failure. Archive a batch only after its proposal bundle validates and its receipt is written.
- Signal appends and archive transactions serialize on the state directory's `.transaction.lock`: contention waits bounded, permanent lock failures exit with their cause, and a confirmed append survives any concurrent archive.
- The lock is mandatory on every supported OS. An archive writes a private pending receipt before removing live signals; while it exists, new signal writes stop with a retry instruction. A retry verifies the recorded archive digest and any still-live selected signals before finishing the live batch and candidate receipt; conflicting evidence stops without rewriting either.
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

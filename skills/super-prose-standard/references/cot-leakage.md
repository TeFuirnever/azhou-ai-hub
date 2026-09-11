# Chain-of-thought leakage taxonomy

Adapted from the pinned upstream (see [provenance.md](provenance.md)). The fix is never deletion alone when a passage carries factual clauses: restate each so it stands at HEAD, then delete the transcript around it; a passage carrying none is deleted outright.

## The one test

For every suspect passage ask: could a reader at HEAD, with no access to any session transcript, PR thread, or uncommitted draft, resolve every reference and verify every claim? If no, restate the surviving facts from the repository's vantage and delete the rest. If yes, it is not leakage — but on current-state surfaces a resolvable change story is still change narration, and class 3 routes it to its sanctioned home.

## The eight classes

1. **Dead design-session citations** — `(decision 7)`, `(audit C2)`, `design §4.7`, `plan §1.4`, phase labels (`T4`, `W3`). If the decision has a committed owner (an issue, a spec, a decision record), cite it by name and path; otherwise delete the citation and restate its factual clause to stand alone.
2. **Stack and PR vantage** — "a later PR in this stack", "this PR adds", "the previous commit". State the shipped mechanism or the extension point; deferred work moves to a `TODO` marker or an issue reference.
3. **Change narration and version stamps** — "used to", "no longer", "the old X", and indexical stamps ("v1", "this cut", "today", "now" contrasting a past state). State the present behavior; a fixed regression becomes a present-tense counterfactual ("without X, Y happens"), never repo history.
4. **Review choreography** — "Rejected in review:", "the reviewer confirmed", draft ordinals, round attributions. Keep the surviving decision and rationale as plain fact; delete who said it when.
5. **Reviewer-addressed justification** — "the cast is safe — it simply…". A comment arguing its own correctness addresses a reviewer, not a maintainer. State the invariant that makes the code safe, or delete the comment if the code shows it.
6. **Restatement and derivation transcripts** — control-flow narration ("first we X, then we Y"), test walkthroughs, proofs of obvious branches. Delete; keep only a non-obvious contract or invariant.
7. **Hedges and planning residue** — "probably fine for now", "should be enough", deferrals with no marker. Promote to `TODO`/`FIXME` or restate as the actual bound; delete the hedge.
8. **Authoring-language slips** — working-language fragments left in prose whose language is otherwise the other one; in this repository, unsourced Chinese change-narration stamps (旧版、上一轮、遗留) inside English surfaces, or English indexical stamps inside Chinese surfaces.

## The keep-list (sanctioned near-misses)

Pattern-matched deletion fails in both directions; apply these keeps as written:

- **Issue and TODO references** — `#1470`, `TODO(name):` resolve at HEAD; keep them on any surface.
- **Suppression justifications** — lint-disable reasons, coverage-ignore reasons, empty-catch explanations are required prose; fix a false reason, never delete it.
- **Counterfactual-present regression pins** — "without X, Y happens", "a naive X would…".
- **Measured bounds** — "(measured: 512 nests ≈ 0.15s)" calibrating a constant; the provenance word "measured" is load-bearing.
- **Runtime old/new states** — "the old connection drains before the new one accepts" is runtime lifecycle, not change history.
- **External section citations** — standards (RFC 9110 §10.1.5) own their §-numbering; the §-ban covers uncommitted internal drafts only.
- **Project voice and genre forms** — "we" as project voice; an Alternatives-considered section's own vocabulary.
- **Versioned-artifact language** — a version number naming a wire format or path segment (`/v1/chat`) is an identifier, not an indexical stamp.

## Workflow

1. Fix the scope; apply the exclusions. Prose inside synthetic benchmark fixtures and frozen archives is derivative, not a target.
2. Audit read-only first: run [the recall batteries](../scripts/recall_batteries.py) with hidden paths included, calibrating each probe against a known positive and a near-miss negative before trusting its output, then judge every hit semantically. The batteries over-match by design and under-match by nature; also read the densest prose in scope without a pattern in hand. The skill's own files quote leaked wording as calibration — discount their self-hits as evidence, not usage.
3. Fix owner-first: edit the owning source before any generated or derived surface.
4. Before deleting, enumerate the passage's propositions (the complete-proposition rule in the entry), check the keep-list for sanctioned near-misses, and check the overcorrection traps: a trim must not flip an obligation into an endorsement, promote a hypothetical to a shipped feature, delete a true fact with the transcript around it, or drop provenance (a measured bound's "measured" is load-bearing).
5. Verify per the entry's Verification section; confirm every remaining citation resolves at HEAD.

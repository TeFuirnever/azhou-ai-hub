# Governance

Azhou AI Hub is maintainer-led and evidence-driven.

## Roles

- **Maintainer**: owns releases, security response, repository settings and final merge decisions.
- **Contributor**: proposes code, docs, tests, benchmarks or reviews through GitHub.
- **Reviewer**: evaluates a bounded change; a paired judge is a reviewer for one frozen comparison, not a maintainer.

Current code ownership is declared in [.github/CODEOWNERS](.github/CODEOWNERS).

## Decision rule

Routine changes use lazy consensus: a pull request that satisfies the project standard, required checks and review may merge. Material changes need explicit maintainer approval:

- new or removed skill;
- trigger, permission or deletion boundary;
- receipt/schema incompatibility;
- dependency/vendor/provenance change;
- project standard or release policy;
- promotion of a history-derived candidate.

Evidence order:

1. current code and machine configuration;
2. deterministic tests and real execution;
3. maintained project contracts;
4. plans, historical conversation and opinion.

Unimplemented intent remains visible but does not override current behavior.

## Skill evolution

No model, observer, hook or benchmark may promote its own change. Promotion requires a regression, isolated candidate, deterministic checks, no safety regression, at least three independent paired judges with order reversal and human approval of the exact diff.

## Conflict and appeal

Review disagreements should name the disputed invariant, evidence and user impact. A maintainer records the decision in the PR, issue, changelog or an architecture decision when it affects future contributors.

Governance changes use the same pull-request process and update this file plus materially conflicting project rules.

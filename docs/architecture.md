# Repository architecture

Azhou AI Hub has one maintained runtime per skill and separate development evidence.

~~~text
                  ┌──────────────────────────┐
                  │ docs/skill-standard.md   │
                  │ project authority        │
                  └─────────────┬────────────┘
                                │ governs
           ┌────────────────────┼─────────────────────┐
           ▼                    ▼                     ▼
  skills/<name>/          tests/              benchmarks/<name>/
  installable runtime     deterministic       prompts, fixtures,
  instructions + tools    invariants          receipts and judges
           │                    │                     │
           └────────────┬───────┴─────────────┬───────┘
                        ▼                     ▼
                  scripts/verify.py      evidence contracts
                        │                     │
                        └──────────┬──────────┘
                                   ▼
                           GitHub required checks
~~~

## Runtime boundary

Each <code>skills/&lt;canonical-name&gt;/</code> directory must remain independently installable and discoverable when copied as a complete package. That does not make every package a standalone implementation: declared external runtimes or an explicit repository checkout may still be required. A package must not depend on sibling skill directories, benchmark answers or vendor-specific identity metadata; every external requirement must be documented package-locally and fail closed when unavailable.

## Evaluation boundary

Repository-level benchmarks are not visible to a normally installed skill. They own frozen prompts, assertions, fixtures, run receipts and paired decisions. Reference fixtures prove the verifier is wired; only real attempt-1 runs can become performance evidence.

## Evolution boundary

~~~text
observed → corroborated → regression_ready → isolated_candidate
         → paired_reviewed → human_approved → promoted | rejected
~~~

History collectors and lifecycle hooks never write a live skill. Promotion requires deterministic checks, no safety regression, an odd-number paired majority and exact-diff human approval.

## Authority map

| Fact | Authority |
|---|---|
| Shared skill package/evidence/evolution rules | [skill-standard.md](skill-standard.md) |
| Agent behavior inside this repository | [AGENTS.md](../AGENTS.md) |
| Public product and installation overview | [README.md](../README.md) |
| Harness-specific capability | [support-matrix.md](support-matrix.md) |
| Security reporting and supported versions | [SECURITY.md](../SECURITY.md) |
| Third-party code and assets | [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and per-skill provenance |
| Released behavior | [CHANGELOG.md](../CHANGELOG.md) plus the matching Git tag |

English and Chinese READMEs are reader mirrors. A material product, install, evidence or boundary change updates both in the same commit.

## Foundation control plane

`scripts/azhou_hub.py` composes repository-level information, read-only diagnostics, explicit skill-root setup and the authoritative verifier. It does not enter an installed skill package and does not become a second package manager. Normal setup owns only an absent destination created by the explicit operation; existing different content is a conflict, not an overwrite target.

`azhou-info`, `azhou-doctor`, `azhou-setup` and `azhou-verify` are portable instruction/UX adapters above that CLI. They contain no host identity metadata and no second implementation of the control plane. A configured harness discovers the same package; the Skill verifies an explicit checkout and delegates to its CLI. Host discovery paths, invocation syntax, permissions and optional integrations remain outside the neutral package.

Checkout lifecycle ownership is a separate, explicit single-skill mode. A persisted receipt records the source and installed fingerprints, but its self-digest is only an accidental-corruption check. Every repair, same-target mode migration or uninstall also requires the explicit target and recomputes the canonical source and destination before mutation. No receipt authorizes hook cleanup, harness configuration changes, cross-root movement, forced overwrite or package-manager removal.

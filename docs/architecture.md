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

Each <code>skills/&lt;canonical-name&gt;/</code> directory must work when copied alone. It may contain instructions, references, deterministic scripts, schemas, templates and licensed offline assets. It must not depend on benchmark answers or vendor-specific identity metadata.

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

`scripts/azhou_hub.py` composes repository-level information, read-only diagnostics, explicit skill-root setup and the authoritative verifier. It does not enter an installed skill package and does not become a second package manager. Setup owns only an absent destination created by the explicit operation; existing different content is a conflict, not an overwrite target.

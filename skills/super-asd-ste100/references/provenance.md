# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [asd-ste100-skill-MIT.txt](../../../LICENSES/asd-ste100-skill-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/TeFuirnever/asd-ste100-skill` |
| Immutable commit | `32511c6992ecb5f1971e46a2943f2e6adceedafe` |
| Upstream `SKILL.md` SHA-256 | `39940a0db3d185416edfd757eff4c971006d8f59ad39715295b150b552344342` |
| Upstream `scripts/ste-lint.py` SHA-256 | `1b97b2d22ba50cde10654db56e1b98adf96d250dd3c8f693f8a81361b1084e85` |
| License | MIT, retained at [asd-ste100-skill-MIT.txt](../../../LICENSES/asd-ste100-skill-MIT.txt) |

The upstream capability baseline at the locked commit is the complete controlled-English rewrite discipline: the two-mode `SKILL.md` body (structural rules applied with confidence, lexical rules kept as direction of travel without the non-redistributable ASD dictionary), the writing-rules summary, and the stdlib `ste-lint.py` deterministic linter. `references/writing-rules.md`, `examples/before-after.md` and `examples/linter-edge-cases.md` are vendored byte-identical; `scripts/ste-lint.py` carries two reviewed local patches on the upstream base (recorded below), with both the upstream and the local SHA-256 pinned in `tests/test_asd_ste100.py`, so any further drift fails the unit gate.

## Local linter patches

Two review findings (PR #291) are fixed locally on the pinned upstream base; both make the linter do what the imported `SKILL.md` already documents:

| Patch | Upstream base SHA-256 | Local SHA-256 | Records |
|---|---|---|---|
| Hard-wrapped prose is joined before the sentence-length cap so a >25-word sentence can no longer evade it by splitting across lines; tables, lists, fences, headings and blockquotes stay boundaries | `1b97b2d22ba50cde10654db56e1b98adf96d250dd3c8f693f8a81361b1084e85` | `1cfec74cfd45a472fe92855fb14580026eec440a0fdacc1effcebb1a7c35393d` | `tests/test_asd_ste100.py` wrapped-sentence regression |
| Synonym-group matching generates real inflection forms (silent-e dropping, consonant doubling, regular suffixes) so `removing`, `deleting`, `stopping` and friends are detected | same base | same local | `tests/test_asd_ste100.py` silent-e regression |

Both patches have upstream-fix candidates; when the upstream pin moves, re-derive the local delta against the new base and retire the patches it absorbs.

ASD-STE100 itself (Issue 9, January 2025) is free to obtain but not free to redistribute; this package encodes only the rule categories and the one-word-one-meaning principle and must never embed the official dictionary. The upstream package already draws this boundary and it carries over unchanged.

## Azhou-maintained adaptation

- keeps the upstream `SKILL.md` capability body verbatim, including the two modes, the structural/lexical rule split, the scan checklist, the process, the output format and the boundaries section;
- normalizes frontmatter to the hub contract (`name`, `description`, `invocation`), moving the upstream `version` field into this record (upstream v0.4.0 at the locked commit);
- adds the Azhou brand protocol, the explicit hold boundary for precision-critical asks, and the stable receipt (`super-asd-ste100.receipt.v1`);
- adds this provenance record and the upstream compatibility map.

Classification: `faithful` — the complete upstream capability (the controlled-English rewrite discipline and its deterministic linter) is retained, and every local addition (frontmatter normalization, brand protocol, receipt, provenance and compatibility records) is packaging or interaction layer, which skill-standard §2.3 excludes from `adapted`. Precedent: verbatim retention of the entire upstream capability with packaging-only additions decides `faithful`. Skill-standard §2.3.

## Reproducible source check

```bash
git clone https://github.com/TeFuirnever/asd-ste100-skill /tmp/asd-ste100-src
git -C /tmp/asd-ste100-src checkout 32511c6992ecb5f1971e46a2943f2e6adceedafe
shasum -a 256 /tmp/asd-ste100-src/SKILL.md /tmp/asd-ste100-src/scripts/ste-lint.py
```

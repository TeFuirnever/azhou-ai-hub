# Upstream capability and adaptation

The comparison uses [frontend-design at the pinned commit](https://github.com/anthropics/skills/blob/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f/skills/frontend-design/SKILL.md). The package preserves the upstream design-guidance capability verbatim; the table records every real structural difference. Real-host evidence does not exist yet: no discovery, invocation or design-task run is recorded for this package.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| Frontmatter `name: frontend-design` | adapted | renamed to `super-frontend-design` per the hub brand-prefix contract; directory and frontmatter name match |
| Frontmatter `description` (the two trigger sentences) | adapted | normalized to the hub contract: `Azhou skill.` prefix, both upstream trigger sentences preserved verbatim as the test baseline, the invocation axis and the four-neighbor capability carve appended |
| Frontmatter `license: Complete terms in LICENSE.txt` | adapted | host-specific frontmatter key dropped; the pointed-to `LICENSE.txt` is vendored byte-identical and the hub records the license in provenance instead |
| Intro paragraph (design-lead framing, rejected templated proposals, deliberate choices, justified aesthetic risk) | preserved verbatim | byte-identical below the wrapper |
| `## Ground your designs in the subject matter` | preserved verbatim | byte-identical |
| `## Design principles` (hero-first opening, deliberate typefaces and type scale, line length, structural devices as information, restrained motion, copy awareness) | preserved verbatim | byte-identical |
| `## Process: plan, review against the brief, build, critique` (five default-tell calibration clusters, token-plan first pass, brief review before code, CSS selector-specificity caution) | preserved verbatim | byte-identical, including the calibration list's factual reference to a specific vendor accent color as an AI-default tell |
| `## Restraint and self-critique` (one bold move, quality floor, conditional screenshot critique and design memory) | preserved verbatim | byte-identical; the conditional capabilities keep their upstream "if your environment supports it" wording and degrade honestly per [setup](setup.md) |
| `## More on writing in design` (user-perspective naming, active-voice CTAs, failure and empty states, tone) | preserved verbatim | byte-identical |
| `LICENSE.txt` (Apache-2.0) | preserved byte-identical | vendored as the package `LICENSE.txt` and the `LICENSES/Anthropic-Skills-Apache-2.0.txt` copy; digests pinned in provenance and tests |
| Upstream section order (intro plus five `##` sections) | preserved verbatim | sections follow the upstream order exactly; no section was merged, split or renamed |
| Hub wrapper: identity anchor, motto, brand protocol, boundaries, receipt, provenance/compatibility/setup records | Azhou addition | wrapper layer only; never counts as adapted under Skill-standard §2.3 |

This table records the structural comparison at adoption; it is not a host-behavior claim. A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.

# Upstream compatibility

This map records the imported upstream `diagram-design` baseline at commit `d7b0176d7e60c6f2ff54067991491ac7622c81fb` (frontmatter metadata version `"2.6"`; no upstream tag or release exists as of 2026-11-22). Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| Upstream package identity (`diagram-design`) | locally branded | the upstream name remains source identity; local frontmatter and folder are `super-diagram-design` under the Hub canonical naming contract |
| Description trigger surface (fifty visual types, HTML/SVG/PNG output, the four import stacks, lifecycle phase maps, block decomposition trees, onboarding guidance) | adapted | the enumeration is compressed to representative types with the fifty-type count and every trigger class kept, `Use when` names the import surface, and the carve sentences name `super-archify` and `super-excalidraw-diagram` |
| Style-guide gate and `.diagram-design` profile resolution | preserved verbatim | `SKILL.md` section 0, `references/profiles.md` |
| Fifty-type catalog with the semantic-pattern → visual-type selection layer | preserved verbatim | `SKILL.md` sections 1-3 |
| Universal anti-patterns, design system, SVG primitives, layout and spacing, summary card pattern, checklist, templates and variants | preserved verbatim | `SKILL.md` sections 4-10 |
| `.drawio` / Mermaid / `.excalidraw` / PlantUML import procedures | preserved verbatim | `SKILL.md` section 11 |
| Output contract (self-contained HTML, accessible-SVG rules, manual-only export) | preserved verbatim | `SKILL.md` section 12 |
| Reference corpus (70 pages) and example/template assets (242 files) | preserved byte-identical | `references/`, `assets/` |
| Eight packaged scripts (self-check, geometry verification, SVG/PNG export, four import extractors) | preserved byte-identical | `scripts/` |
| Interpreter invocation spellings in the upstream prose | preserved verbatim | the hub command-surface rule does not grade this vendored package's prose (vendored-skill-package exemption in `scripts/check_repository.py`); the hub-authored records in this package use the portable `python` spelling |
| Upstream repository-root CI machinery cited by the prose (`verify-*.py` per-type verifiers, `test-verify-*.py`, `lint-skin.py`, `build-*.py`) | not vendored | those scripts are the upstream repository's contribution gates, not part of the skill package; upstream `SKILL.md` already splits the two worlds ("From a repository checkout, also run ... ; from an installed skill, manually check print and static-query states on top of the self-check"), and the packaged `self_check.py` plus `verify_geometry.py` are the in-skill verifiers an installed copy needs |
| `license` / `metadata` frontmatter keys | adapted | the hub frontmatter contract allows only `name`, `description`, `invocation`; MIT and version `"2.6"` are recorded in provenance |
| Azhou identity anchor, brand protocol, stable receipt, provenance, setup and compatibility records | Azhou addition | no upstream counterpart; additive contract layers |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.

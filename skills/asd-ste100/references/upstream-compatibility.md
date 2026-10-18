# Upstream compatibility

This map records the imported `asd-ste100` baseline at commit `32511c6992ecb5f1971e46a2943f2e6adceedafe`. Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| `asd-ste100` package name and skill identity | preserved | frontmatter `name: asd-ste100` and package folder |
| Description trigger surface (disambiguate, STE100 rewrite, controlled-language rewrite, and the creative/marketing exclusion) | preserved verbatim | `SKILL.md` frontmatter description |
| Strict / STE-flavored two-mode selection | preserved verbatim | `SKILL.md` "Two Modes" |
| Structural rule set with the lexical direction-of-travel split | preserved verbatim | `SKILL.md` "Core Rewrite Rules" |
| Scan checklist of six mechanical habits | preserved verbatim | `SKILL.md` "Scan Checklist" |
| Meaning, hedge and modality preservation requirements | preserved verbatim | `SKILL.md` process, boundaries and output format |
| No reproduction of the non-redistributable ASD dictionary | preserved verbatim | `SKILL.md` "Source and Scope"; the boundary carries over unchanged |
| `scripts/ste-lint.py` linter (`--json`, `--baseline`, `--disable`, `--selftest`) | preserved; locally patched | two review fixes (hard-wrapped sentence merging, verb-inflection matching) on the pinned base; both SHAs recorded in provenance and `tests/test_asd_ste100.py` |
| Writing-rules summary and worked examples | preserved byte-identical | `references/writing-rules.md`, `examples/` |
| `version` frontmatter key | adapted | the hub frontmatter contract allows only `name`, `description`, `invocation`; upstream v0.4.0 is recorded in provenance |
| Azhou brand protocol, hold boundary, stable receipt, provenance and compatibility map | Azhou addition | no upstream counterpart; additive contract layers |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.

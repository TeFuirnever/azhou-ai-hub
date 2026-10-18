# Upstream compatibility

This map records the imported `archify` baseline at tag `v3.1.0` (commit `1c2b42d660e4a7571813fb43839c79e3e9ca7720`). Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| `archify` package name and skill identity | preserved | frontmatter `name: archify` and package folder |
| Description trigger surface (visualizing systems, pipelines, schemas, histories, everyday subjects; numeric charts excluded) | preserved verbatim, plus one carve sentence | `SKILL.md` frontmatter description |
| Ten diagram modes with typed JSON schemas | preserved | `schemas/`, `SKILL.md` type router |
| `finalize` / `deliver` / `validate` / `doctor` / `demo` / `guide` CLI and real-browser gates | preserved unmodified | `bin/`; `doctor` passes on the trimmed package (13/13 checks) |
| Viewer runtime (themes, pan/zoom, search, motion, exports) | preserved | `renderers/`, `assets/template.html` |
| Authoring/delivery/update-awareness contracts | preserved byte-identical | `references/` |
| Mermaid input mapping and repository authoring | preserved verbatim | `SKILL.md`, `references/repository-authoring.md` |
| `examples/*.json` authoring examples and locale translations | preserved | `examples/` (JSON only), `locales/`, `examples/locales/` |
| Fifteen pre-rendered example `*.html` files | intentionally omitted | presentation outputs, not runtime inputs; excluded at vendoring, recorded here |
| `package-lock.json` | intentionally omitted | dev-only; the package has zero runtime npm dependencies |
| `license` and `metadata` frontmatter keys | adapted | the hub frontmatter contract allows only `name`, `description`, `invocation`; upstream v3.1.0 / tt-a1i recorded in provenance |
| Output example's illustrative path | adapted | the example's `file:///abs/path/….html` link target replaces the upstream bare `/abs/path/….html` form so the repository Markdown-link gate passes; no behavior change |
| Coexistence carve: editable `.excalidraw` scenes → excalidraw-diagram | Azhou addition | no upstream counterpart; recorded in both skills' descriptions |
| Azhou brand protocol, hold boundary, stable receipt, `references/setup.md`, provenance and compatibility map | Azhou addition | no upstream counterpart; additive contract layers |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence. When moving the upstream pin, re-derive the trim exclusions against the new tag and re-run `doctor` before landing.

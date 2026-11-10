# Upstream compatibility

This map records the current upstream `archify/` baseline at tag `v3.2.0` (commit `208acba8d412335185b2056fedf54b3405df43fb`). The original import remains `v3.1.0` at `1c2b42d660e4a7571813fb43839c79e3e9ca7720`. Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| Upstream `archify` skill identity | canonical packaging adaptation | Hub directory/frontmatter/bin use `super-archify`; internal source filenames and official update `skillId` remain `archify` |
| v3.2 description trigger surface | preserved verbatim, plus one carve sentence and Azhou prefix | Includes native diagrams and one-page explainers; dashboards remain excluded |
| Ten native diagram modes with typed schemas | preserved | `schemas/`, `SKILL.md` type router; no native mode removed |
| One-page explainer from Markdown or JSON | preserved | `explainer/`, explainer schema/renderer/example and authoring reference |
| Panels, native diagrams, cited sources, static charts and patching | preserved | Complete explainer runtime, reader assets and Pele dependency subset retained |
| `finalize` / `deliver` / `validate` / `doctor` / `demo` / `guide` CLI | preserved with existing display-name packaging | `bin/`; new explainer warnings retained when merging the CLI |
| Real browser gates | preserved | Native diagrams require browser-check; explainer supports `--browser-check` and otherwise records `not-run`; neither means visual review |
| Live preview for ten native diagram types | restored internal path | Uses the real sibling `bin/archify.mjs`; live preview is not an explainer feature |
| Viewer themes, pan/zoom, search, motion and exports | preserved | `renderers/`, `assets/template.html`; existing local generator label retained at version 3.2.0 |
| Authoring, delivery, Mermaid and repository evidence contracts | preserved | `references/`; existing canonical-folder documentation examples retained |
| Timeline timezone/DST ticks, workflow migration contracts, ERD and waterfall fixes | absorbed from stable source | Target renderers and workflow migration geometry; local packaging does not rewrite these algorithms |
| Stable update awareness | restored upstream protocol identity | Official `archify` manifest identity stays separate from Hub canonical discovery identity; no automatic install |
| JSON examples, translations and new Arabic locale | preserved | `examples/`, `locales/`, `examples/locales/` |
| Fifteen pre-rendered example `*.html` files | intentionally omitted | Existing generated-output exclusion; no runtime dependency consumes them |
| `package-lock.json` | intentionally omitted | Existing development-only exclusion; no npm runtime installation required |
| `package.json` npm scripts | adapted | Monorepo-relative scripts remain removed; runtime CLI does not invoke them |
| Trailing whitespace | normalized | Existing whitespace-only adaptation in `assets/template.html` and `renderers/workflow/workflow-compiler.mjs` |
| Explainer dynamic text and style boundaries | bounded local hardening | Reader text/attribute escaping, complete style unwrapping and raw-text terminator handling; DOM/source-card and native-preview behavior retained |
| Explainer browser-check selectors | bounded local hardening | CDP function arguments carry selector data in the existing page context; focus/Enter/native-viewer controls retained |
| Explicit repository citation revision | local correctness fix | Conflicting source/document revisions reject with `source-revision`; matching old pins, inferred HEAD and no-repository fallback retained |
| Known upstream alert | retained limitation | The v3.1 CodeQL incomplete multi-character sanitization finding in `delta/architecture-delta.mjs` is unchanged at v3.2.0; no fix claim |
| Upstream `license` and `metadata` frontmatter | adapted | Hub requires `name`, `description`, `invocation`; immutable source version and license live in provenance |
| Illustrative output link | adapted | Existing `file:///abs/path/...html` example retained for repository link validation |
| Editable `.excalidraw` coexistence boundary | Azhou addition | Existing carve preserved; no sibling-package runtime dependency |
| Azhou brand, hold boundary, receipt and three local references | Azhou addition | Existing standalone packaging/interaction layer, with actual explainer gate state reported |

The complete source/local per-file comparison belongs to `tests/archify-vendor-manifest.json`. A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence. On every upstream pin move, re-derive exclusions and local deltas against the exact tag, retain all new runtime dependencies and notices, and execute the runtime behavior gates before landing.

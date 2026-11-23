# Upstream compatibility

This map records the current upstream `archify/` baseline at tag `v3.3.0` (commit `af3aaf3c36762f2afb62a4a09533f6c7273b07e5`). The original import remains `v3.1.0` at `1c2b42d660e4a7571813fb43839c79e3e9ca7720` and the previous pin `v3.2.0` at `208acba8d412335185b2056fedf54b3405df43fb`. Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| Upstream `archify` skill identity | canonical packaging adaptation | Hub directory/frontmatter/bin use `super-archify`; internal source filenames and official update `skillId` remain `archify` |
| v3.3 description trigger surface | condensed to the 1024-character hub frontmatter ceiling | Azhou prefix plus coexistence carve; all native modes, Mermaid/repository evidence, Code Analysis, explainer English and Chinese triggers with the proactive default and the `[archify explainer: on-demand]` switch, story/video export and `Not for dashboards` retained; the full upstream text lives at the pinned source and in provenance |
| Apache-2.0 license with preserved MIT grants | adopted at the pinned source | Package `LICENSE`/`LICENSE-MIT`/`NOTICE` vendored verbatim; retained hub copies `LICENSES/archify-Apache-2.0.txt` and `LICENSES/archify-MIT.txt` (byte-identical to upstream `LICENSE-MIT`) |
| Ten native diagram modes with typed schemas | preserved | `schemas/`, `SKILL.md` type router; no native mode removed |
| One-page explainer from Markdown or JSON | preserved | `explainer/`, explainer schema/renderer/example and authoring reference |
| Explainer proactive-by-default mode with on-demand switch | preserved | v3.3.0 replaces the opt-in proactive rules line; the hub description carries the new default and switch |
| Panels, native diagrams, cited sources, static charts and patching | preserved | Complete explainer runtime, reader assets and Pele dependency subset retained |
| Local-repository Code Analysis workbench | preserved | `modules/code-analysis/` vendored byte-identically, including its parser/schema vendor packages, `.gitattributes`, `.gitignore` and per-file license copies; hub git attributes already use the same `text=auto eol=lf` normalization |
| Story walkthroughs and video export | preserved | `story/` with vendored parse5/entities subset and licenses; `references/story-authoring.md` |
| Explicit PR review attachment | preserved | `pr/`, `references/pr-review.md`, `schemas/pr-pack.schema.json` |
| Cross-diagram drilldown, node explanations, Architecture Diagnosis offer | preserved | `schemas/*.schema.json` drilldown fields, Semantic Passport explanations, delivery-contract diagnosis offer |
| `finalize` / `deliver` / `validate` / `doctor` / `demo` / `guide` / `start` CLI | preserved with existing display-name packaging | `bin/`; retained user-facing usage/warning substitutions replayed with byte-validated rules on the v3.3.0 bytes |
| Real browser gates | preserved | Native diagrams require browser-check; explainer supports `--browser-check` and otherwise records `not-run`; neither means visual review |
| Live preview for ten native diagram types | upstream identity retained | v3.3.0 `bin/preview.mjs` adopted verbatim; it still drives the real sibling `bin/archify.mjs` |
| Viewer themes, pan/zoom, search, motion and exports | preserved | `renderers/`, `assets/template.html`; generator label carries the local `super-archify 3.3.0` marker; whitespace-only line normalization retained |
| Authoring, delivery, Mermaid and repository evidence contracts | preserved | `references/`; existing canonical-folder documentation examples retained |
| Static SVG export for README delivery (`bin/export-svg.mjs`) | preserved | Adopted verbatim; hub examples keep the `file:///abs/path/...html` link adaptation |
| Timeline timezone/DST ticks, workflow migration contracts, ERD and waterfall fixes | absorbed from stable source | Target renderers and workflow migration geometry; local packaging does not rewrite these algorithms |
| Stable update awareness | upstream protocol identity | Official `archify` manifest identity stays separate from Hub canonical discovery identity; `skill-release.json` now carries the upstream v3.3.0 bytes verbatim; no automatic install |
| JSON examples, translations, moved Russian locale | preserved | `examples/`, `locales/` (upstream moved `examples/locales/ru.json` to `locales/ru.json`; both recorded in the manifest) |
| Fifteen pre-rendered example `*.html` files | removed upstream | v3.3.0 stopped shipping them (#1453); the prior documented exclusions dissolved with the paths |
| `package-lock.json` | intentionally omitted | Existing development-only exclusion; no npm runtime installation required |
| `package.json` npm scripts | adapted | Monorepo-relative scripts remain removed; runtime CLI does not invoke them; identity keys follow upstream (name/bin `super-archify`, license `Apache-2.0`, version `3.3.0`) |
| Local documentation corrections upstream still lacks | retained | `schemas/README.md` schema facts (optional/required arrays, brand scope, migration command, check-mode invocation), the `explainer-authoring.md` diagram-count sentence, `scripts/generate-validators.mjs` stale-validators hint; `renderers/tree/README.md` corrections were adopted upstream verbatim, leaving only the path substitution |
| Trailing whitespace | normalized | Existing whitespace-only adaptation in `assets/template.html` and `renderers/workflow/workflow-compiler.mjs` |
| Explainer dynamic text and style boundaries | bounded local hardening, re-derived | Hoisted attribute-complete `escapeText` over Walk bar, Ask dialog and source cards; complete style unwrapping and raw-text terminator handling with unchanged upstream anchors; DOM/source-card and native-preview behavior retained |
| Explainer browser-check selectors | bounded local hardening, re-derived | CDP function arguments carry selector data in the existing page context; focus/Enter/native-viewer controls retained over the v3.3.0 readability changes |
| Explicit repository citation revision | local correctness fix, carried unchanged | Conflicting source/document revisions reject with `source-revision`; upstream `explainer/sources.mjs` is unchanged at v3.3.0 |
| Clipboard API unavailable or rejected | absorbed upstream | v3.3.0 owns `copyText` and routes snippet, Ask and feedback-email copies through it; unavailable or rejecting writes reach the existing failure fallbacks, and Ask keeps a retryable selected text; the former local guard is retired and the hub regression asserts the upstream notices |
| Known upstream alert | retained limitation | The v3.1 CodeQL incomplete multi-character sanitization finding in `delta/architecture-delta.mjs` is unchanged at v3.3.0 (the flagged `esc` construction is byte-identical); no fix claim |
| Upstream `license` and `metadata` frontmatter | adapted | Hub requires `name`, `description`, `invocation`; immutable source version and license live in provenance |
| Illustrative output links | adapted | The delivery examples use `file:///abs/path/...html` forms (checkout timing, test report and the report placeholder) so repository link validation does not chase illustrative paths |
| Editable `.excalidraw` coexistence boundary | Azhou addition | Existing carve preserved; no sibling-package runtime dependency |
| Azhou brand, hold boundary, receipt and three local references | Azhou addition | Existing standalone packaging/interaction layer, with actual explainer gate state reported |

The complete source/local per-file comparison belongs to `tests/archify-vendor-manifest.json`. A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence. On every upstream pin move, re-derive exclusions and local deltas against the exact tag, retain all new runtime dependencies and notices, and execute the runtime behavior gates before landing.

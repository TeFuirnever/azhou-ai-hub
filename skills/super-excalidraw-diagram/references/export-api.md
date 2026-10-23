# Official Export & Conversion API

> Extracted from excalidraw source: `packages/utils/src/export.ts` (+ `@excalidraw/utils`
> README). This is what any programmatic export (including this skill's render loop) actually
> calls. Read when tuning export behavior or writing custom export scripts.

Sources:

- https://github.com/excalidraw/excalidraw/blob/master/packages/utils/src/export.ts
- https://github.com/excalidraw/excalidraw/blob/master/packages/utils/README.md
- Scene JSON: https://github.com/excalidraw/excalidraw/blob/master/packages/excalidraw/data/json.ts

## Common option set (all export fns)

| Option | Type | Semantics |
|---|---|---|
| `elements` | element array | restored automatically (`restoreElements`, invisible elements deleted) |
| `appState` | partial AppState | restored via `restoreAppState` (e.g. `viewBackgroundColor`, `exportBackground`, `exportScale`, `exportWithDarkMode`) |
| `files` | BinaryFiles | image data map (`{}` when scene has no images) |
| `exportPadding` | number | px padding around content (upstream default 10) |
| `exportingFrame` | frame element | export a single frame's contents |

## `exportToSvg(opts)` → `Promise<SVGSVGElement>`

Extra options: `renderEmbeddables`, `skipInliningFonts` (skip font inlining for smaller SVG),
`reuseImages`.

## `exportToCanvas(opts)` → canvas

Extra options: `maxWidthOrHeight` (downscales only if content exceeds it; otherwise falls back
to `appState.exportScale ?? 1`), `getDimensions(width, height)` callback returning
`{width, height, scale?}` (ignored when `maxWidthOrHeight` is set).

## `exportToBlob(opts)` → `Promise<Blob>`

Extra options: `mimeType` (default `image/png`; `image/jpg` tolerated, corrected to `image/jpeg`),
`quality` (0–1). Gotchas: `quality` is **ignored for PNG**; JPEG **forces `exportBackground: true`**
(with a warning). Default quality: `0.92` for JPEG, `0.8` otherwise. With
`appState.exportEmbedScene` + PNG, the scene JSON is embedded into the PNG metadata
(`encodePngMetadata`) so the file reopens as an editable diagram.

## `serializeAsJSON(elements, appState, files, source)` → string

The canonical scene serializer — same envelope this skill's `to-excalidraw.mjs` writes
(`type: "excalidraw"`, `version: 2`).

## Conversion (low-code)

`parseMermaidToExcalidraw(mermaidText)` → **skeleton** elements (labels as `label` props on shapes)
→ must be finalized with `convertToExcalidrawElements(elements, { regenerateIds })` before
rendering/export. Both are exported by `@excalidraw/excalidraw` /
`@excalidraw/mermaid-to-excalidraw` and need a browser DOM — this skill runs them headless via
`scripts/mermaid-to-excalidraw.py` (vendored bundle in `references/vendor/`).

> The skill's SVG deliverable path, `scripts/export-official-svg.py`, wraps this `exportToSvg` (plus Xiaolai subset injection) — prefer it over calling the API directly.

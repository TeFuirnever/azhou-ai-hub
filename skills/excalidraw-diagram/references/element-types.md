# Official Element & Property Reference

> Extracted from the excalidraw/excalidraw source. Read this whenever you need the exact
> semantics, valid values, or defaults of any element property — not the quick tables
> in `json-schema.md`, and never guessed values.

Sources (upstream master):

- Types: https://github.com/excalidraw/excalidraw/blob/master/packages/element/src/types.ts
- Constants: https://github.com/excalidraw/excalidraw/blob/master/packages/common/src/constants.ts
- Derived overview (community wiki generated from the repo): https://zread.ai/excalidraw/excalidraw/8-element-type-system

## Element types

| type | exists in `ExcalidrawElement` union | bindable (arrow targets) | can hold bound text |
|---|---|---|---|
| `rectangle` | yes | yes | yes |
| `diamond` | yes | yes | yes |
| `ellipse` | yes | yes | yes |
| `text` | yes | only without `containerId` | — |
| `arrow` | yes | no | yes (label) |
| `line` | yes | no | yes (label) |
| `freedraw` | yes | no | no |
| `image` | yes | yes | no (needs `fileId` + `files` map — avoid in generated scenes) |
| `frame` / `magicframe` | yes | yes | no (name is a property, not a text element) |
| `iframe` / `embeddable` | yes | yes | no (render inconsistently off excalidraw.com — avoid) |
| `selection` | internal | no | no |

Text can be bound only into: rectangle, diamond, ellipse, arrow (`ExcalidrawTextContainer`).

## Base properties (every element) — official semantics

| Property | Semantics (from source comments/types) |
|---|---|
| `id` | unique string |
| `x`, `y` | position px (top-left; for arrows: origin of the `points` polyline) |
| `width`, `height` | size px |
| `angle` | radians |
| `strokeColor` / `backgroundColor` | hex, or `"transparent"` |
| `fillStyle` | `"hachure"` \| `"cross-hatch"` \| `"solid"` \| `"zigzag"` |
| `strokeWidth` | `1` thin \| `2` bold \| `4` extraBold (STROKE_WIDTH map) |
| `strokeStyle` | `"solid"` \| `"dashed"` \| `"dotted"` |
| `roundness` | `null` or `{ "type": 1\|2\|3 }` — see algorithms below |
| `roughness` | `0` architect \| `1` artist \| `2` cartoonist (ROUGHNESS map) |
| `opacity` | 0–100 |
| `seed` | random integer seeding roughjs generation so shapes don't differ across renders |
| `version` | integer, incremented per change (collab reconciliation) |
| `versionNonce` | random int regenerated per change (deterministic tie-break for equal versions) |
| `index` | fractional-index string for z-order (kept in sync with array order; may be null) |
| `isDeleted` | soft-delete flag |
| `groupIds` | group ids ordered deepest → shallowest |
| `frameId` | containing frame id or null |
| `boundElements` | arrows/text bound TO this element (`null` when empty — never `[]`) |
| `updated` | epoch ms of last update |
| `link` / `locked` | hyperlink / lock flags |
| `customData` | optional arbitrary record |

## Text elements

| Property | Semantics |
|---|---|
| `text` / `originalText` | `text` = rendered (with wrapping newlines), `originalText` = source |
| `fontSize` | px; official preset sizes: sm 16, md 20, lg 28, xl 36 (FONT_SIZES); default 20 |
| `fontFamily` | see map below; **upstream default is `5` Excalifont** |
| `textAlign` | `"left"` \| `"center"` \| `"right"`; default `left` |
| `verticalAlign` | `"top"` \| `"middle"` \| `"bottom"`; default `top` |
| `containerId` | id of parent shape/arrow, or null for standalone |
| `autoResize` | `true` → width fits text; `false` → text wraps to width. Default `true` |
| `lineHeight` | unitless (W3C-style); px = lineHeight × fontSize |
| `strokeColor` | the TEXT color — always set explicitly, dark value |

`FONT_FAMILY` map (official): Virgil 1, Helvetica 2, Cascadia 3 (mono), **4 unused (historical)**,
Excalifont 5 (upstream default), Nunito 6, Lilita One 7, Comic Shanns 8 (mono), Liberation Sans 9,
Assistant 10. CJK hand-drawn fallback font: Xiaolai.

Constants that matter when hand-placing text: bound-text padding `5`px per side
(BOUND_TEXT_PADDING); standalone text created by dragging autowraps only past `36`px width
(TEXT_AUTOWRAP_THRESHOLD).

## Lines & arrows (`ExcalidrawLinearElement`)

| Property | Semantics |
|---|---|
| `points` | polyline offsets from `x`,`y`; first point is `[0,0]` |
| `startBinding` / `endBinding` | `FixedPointBinding` or null — see below |
| `startArrowhead` / `endArrowhead` | null or arrowhead value — see enum below |
| `elbowed` (arrow only) | `true` = elbow routing; elbow arrows also carry `fixedSegments`, `startIsSpecial`, `endIsSpecial` (editor state — leave null when hand-authoring) |
| `polygon` (line only) | closes the line into a polygon |

`FixedPointBinding`:

```json
{ "elementId": "…", "fixedPoint": [0.5, 1], "mode": "orbit" }
```

- `fixedPoint` — [widthRatio, heightRatio] in 0.0–1.0; multiplies the bound element's
  width/height to pick the attach point (e.g. `[0.5, 1]` = bottom-center).
- `mode` — `"inside"` (arrow may reach the exact point) | `"orbit"` (arrow stays on the
  border/outside) | `"skip"` (binding skipped in layout).
- Legacy bindings without `fixedPoint`/`mode` use `{ elementId, focus, gap }` — `focus` shifts
  the attach point along the edge (-1..1), `gap` is border spacing. Still parsed upstream.

Arrowheads (official enum): `arrow`, `bar`, `circle`, `circle_outline`, `triangle`,
`triangle_outline`, `diamond`, `diamond_outline`, plus ER cardinality: `cardinality_one`,
`cardinality_many`, `cardinality_one_or_many`, `cardinality_exactly_one`,
`cardinality_zero_or_one`, `cardinality_zero_or_many`. Legacy (still parse): `dot`,
`crowfoot_one`, `crowfoot_many`, `crowfoot_one_or_many`.

Arrow constants: minimum arrow size `20`px (MINIMUM_ARROW_SIZE); arrow labels — the label
element's width should be at most `0.7 ×` arrow length (ARROW_LABEL_WIDTH_FRACTION) and
`fontSize × 11` minimum width (ARROW_LABEL_FONT_SIZE_TO_MIN_WIDTH_RATIO).

## Roundness algorithms

| `roundness.type` | algorithm | used for |
|---|---|---|
| `1` | legacy proportional (25% of largest side) | old rectangles |
| `2` | proportional radius (25% of largest side) | lines, arrows, diamonds |
| `3` | adaptive fixed radius (`32`px) | current rectangle default |

## Scene envelope & export

- Scene `version`: `2` (VERSIONS.excalidraw); library files also `2`.
- Default export padding `10`px; export scales 1/2/3; SVG export rounds to 2 decimals.
- Default grid size 20 (only matters if `appState.gridSize` set).
- Editor default element props (what you get when you don't override): stroke black
  (`#1e1e1e`), background transparent, fill solid, strokeWidth 2, stroke solid,
  roughness 1 (artist), opacity 100.

> Verified against the vendored `@excalidraw/excalidraw@0.18.1` bundle; upstream-master links may drift.

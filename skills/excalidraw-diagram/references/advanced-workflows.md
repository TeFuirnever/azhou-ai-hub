# Advanced Workflows and Diagnostics

> Optional details for complex scenes. Apply only after the main workflow requests them.
> Source attribution and licenses: [`provenance.md`](provenance.md). Palette remains
> single-sourced from [`color-palette.md`](color-palette.md).

Set `SKILL_DIR` to the installed package path before running commands in this reference.

## Spacing Reference (from Agents365)

| Scenario | Spacing |
|----------|---------|
| Labeled arrow gap (between shapes) | 150–200px |
| Unlabeled arrow gap | 100–120px |
| Column spacing (labeled arrows) | 400px (220px box + 180px gap) |
| Column spacing (unlabeled arrows) | 340px (220px box + 120px gap) |
| Row spacing | 280–350px (150px box + 130–200px gap) |
| Zone/container padding | 50–60px around children |
| Zone/container opacity | 25–40 |
| Minimum gap between any elements | 40px |

Element sizing from label text: Latin `width = max(160, charCount × 9)`, CJK `× 18`; height `60`
per line + `24` each additional. Standalone text does NOT auto-wrap — insert manual `\n`
(≤ ~30 Latin / ~15 CJK chars per line at 16px). Bound text wraps to container width instead.

### Font size hierarchy (from Agents365)

Title 28px → Header 24px → Label 20px → Description 16px → Note 14px.

## Arrow Routing (from Agents365)

- **L-shaped (elbow)**: orthogonal, 3+ points — `"points": [[0,0],[100,0],[100,150]]`
- **Elbowed**: automatic right angles — add `"elbowed": true`
- **Curved**: smooth via waypoints — `"roundness": { "type": 2 }`
- **CRITICAL — edge-to-edge endpoints**: static exports draw `points` literally;
  `startBinding`/`endBinding` do NOT clip the line. Compute the first/last point at the shape
  borders (not centers), or the arrow slices straight through both shapes.
- **Arrow labels**: bind text via `containerId` = arrow id (line is masked behind the label), but
  keep the label `width` to the text (`charCount × 9`) — a label as wide as the arrow masks the
  whole line away. Labels ≤12 chars, and only when the connection isn't obvious.
- **Arrow styles**: solid = primary flow, dashed = response/async, dotted = optional/weak.

## Anti-Patterns (from Agents365)

1. **Never bind text to large zone rectangles** — Excalidraw centers it mid-zone, overlapping
   contained elements. Use free-standing text at the zone's top-left.
2. **Avoid cross-zone arrows** — long diagonals make spaghetti. Route within zones or along
   perimeter edges.
3. **No filled opaque containers holding elements** — use `opacity: 25–40` zones so children stay
   visible.
4. **Always set explicit `strokeColor` on text** — text `strokeColor` IS the render color; omitted,
   it can inherit the shape background and turn invisible. Use the text hierarchy colors.
5. **JSON field hygiene (hand-authored elements)** — `boundElements: null` (never `[]`),
   `updated: 1`, omit `frameId`/`index`/`versionNonce`/`rawText`; arrow `points` always start
   `[0,0]`; `seed` unique positive int, namespaced by section (100xxx, 200xxx). Scene
   templates and library items may carry extra metadata fields — don't copy them into new
   hand-authored elements.

## Common Mistakes → Fixes (from Agents365)

| Mistake | Fix |
|---------|-----|
| Arrows cut through shapes | Endpoints at shape borders, not centers |
| Arrow invisible, only label shows | Label `width` must fit the text, not the arrow length |
| Text clipped in shape | `width = max(160, charCount × 9)`, ×2 for CJK |
| Text invisible on background | Explicit dark `strokeColor` on every text element |
| Text centered mid-zone | Don't bind text to zones; free-standing text at top |
| Elements overlapping | Spacing Reference; minimum 40px gap; confirm/locate with `scripts/audit-overlaps.py` |
| Not interactive on excalidraw.com | Shapes need `boundElements` referencing bound arrows/text |
| Monotone diagram | Semantic palette + 60-30-10 (≈60% neutral base, 30% primary semantic color, 10% accent) |
| Uniform text sizes | 28 → 24 → 20 → 16 → 14 hierarchy |

## Icon Libraries (community shapes — fully vendored, offline)

Need a real AWS / Azure / GCP / network / UML icon instead of a plain box? The
**complete official library set** — all 231 libraries, 4134 items, ~10 MB
gzipped — is vendored at `references/libraries/`, and
`scripts/excalidraw_lib.py` resolves every subcommand from it offline:

```bash
L="$SKILL_DIR/scripts/excalidraw_lib.py"
python3 $L catalog                              # offline inventory of all vendored libs
python3 $L search firewall                      # match by filename or item name
python3 $L items dwelle/network-topology-icons.excalidrawlib   # flags image-based items
python3 $L merge scene.excalidraw dwelle/network-topology-icons.excalidrawlib Firewall 400 150 \
    --scale 1.2 --strip-text --roughness 1
```

Browse the full inventory + a verified quick-pick table (entity type → library
→ item name) in [`icon-catalog.md`](icon-catalog.md).
Resolution order for `<source>`: local path → vendored `.gz` → network fetch.
Only non-vendored future libraries need the manual pre-cache:
`curl -sL https://raw.githubusercontent.com/excalidraw/excalidraw-libraries/main/libraries/<author>/<lib>.excalidrawlib -o /tmp/excalidraw-libs/<author>/<lib>.excalidrawlib`.

Rules: vector only — the script refuses items containing `image` elements (they
won't render; `items` flags them `[HAS IMAGE]`); icons accent a diagram, they
don't replace the design system's spacing, labels, and arrow semantics; arrows
don't bind to library groups — draw connectors with explicit edge-to-edge
`points`; always re-run the render-and-validate loop after merging (icon
bounding boxes vary). `--strip-text` drops the item's own label (use when the
scene already labels the node — it also shrinks the reported art bbox, which
usually fits a tighter niche); `--roughness N` normalizes the item into the
scene's stroke style (library items ship mixed values). One audit note:
`audit-overlaps.py` uses declared text widths — a wide legacy `width` on a
freestanding label can straddle an icon's box on paper while rendering clear;
trust geometry + a zoomed crop before moving elements. Icon-internal
line/ellipse crossings (server rack slots, screen outlines) are the item's own
art, not defects.

**Icon-first style (default on)**: for recognizable entity types — user, server, database,
gateway, device, cloud service, repo — prefer icon + short label over a plain labeled box
(this is type identification in the draw.io/AWS convention — not the decorative
icons-beside-text pattern the Bad/Good table rejects);
a row of text boxes reads as a list, the same row with type icons reads as a system (the
draw.io / AWS-diagram convention). Calibration from practice: library items are small
(~65px native) — merge at `--scale 1.0–1.3` for a 50–70px icon, `--strip-text` when the
scene already labels the node, and place icons in empty margin space beside the node.
Always re-render and verify: a scale-0.4 icon renders as an invisible dot — the render
loop catches that, the JSON does not. And no official library ships a vetted named
**gear / robot / AI** icon — draw those from primitives (gear = ellipse + lines,
robot = rects) or accept the gap.

## Low-Code Orchestration

Three ways to skip hand-authoring every element — pick by how structured the input already is:

### 1. Mermaid → .excalidraw (text in, diagram out)

Official `@excalidraw/mermaid-to-excalidraw`, fully offline (vendored bundle + headless Chromium —
same setup as the render loop):

```bash
cd "$SKILL_DIR/references"
uv run python ../scripts/mermaid-to-excalidraw.py input.mmd out.excalidraw
```

Best when the user already has Mermaid / diagrams-as-code text. Output is a normal scene —
restyle and extend it, then run the mandatory render-and-validate loop. (Internals: parse →
`convertToExcalidrawElements`; see `references/export-api.md`.)

### 2. SVG → .excalidraw (existing vector art in)

Official `excalidraw/svg-to-excalidraw`, same offline headless setup:

```bash
cd "$SKILL_DIR/references"
uv run python ../scripts/svg-to-excalidraw.py input.svg out.excalidraw
```

Known limits of the official converter (v0.0.2): it keeps rects, circles/ellipses, and paths —
**drops `<line>` and `<text>` nodes**. Re-add lines/labels after converting. Colors and positions
are preserved; output restores cleanly through the render loop.

### 3. Official component libraries (search → merge)

All 231 official libraries are vendored offline — see the Icon Libraries section above
and the full inventory in [`icon-catalog.md`](icon-catalog.md).
Curated starting points live in
[`icon-catalog.md`](icon-catalog.md) (auto-generated from the
vendored set — counts there always match reality; the quick-pick table maps entity
types to verified item names).

**Orchestration rule**: low-code outputs (Mermaid / SVG / library items) are a STARTING
scene — always finish with the design rules (palette, spacing, typography) and the mandatory
render-and-validate loop before delivering.

## Local Additions: MCP Preview, Persistence, Rough-SVG Preview

**Interactive preview** (when the built-in excalidraw MCP — the official
[excalidraw/excalidraw-mcp](https://github.com/excalidraw/excalidraw-mcp) — is available): call `read_me` once per
conversation, then `create_view` with a camera tour — first element `cameraUpdate`, 4:3 viewport
sizes only (400×300 / 600×450 / 800×600 / 1200×900 / 1600×1200), font ≥16. Iterate in chat, then
persist. (`export_to_excalidraw` publishes a public share link — confirm with the user first.)

**Persist an MCP preview to a file**: strip pseudo-elements (`cameraUpdate`, `delete`,
`restoreCheckpoint`) from the final element array, save as `elements.json`, then:

```bash
node "$SKILL_DIR/scripts/to-excalidraw.mjs" elements.json out.excalidraw
```

Simplified element schema accepted by `to-excalidraw.mjs` / `render-svg.mjs` (same shape the
excalidraw MCP `create_view` consumes): shapes are `{type: rectangle|ellipse|diamond|line|arrow,
id, x, y, width, height, strokeColor, backgroundColor, strokeWidth, strokeStyle, opacity,
roundness, points (linear), startBinding/endBinding {elementId, fixedPoint}, label {text,
fontSize, fontFamily} — or a plain string as shorthand for `label.text`}; standalone text is
`{type: text, id, x, y, text, fontSize, fontFamily,
strokeColor}`. `fontFamily` optional, default 1 (Virgil) — 5 Excalifont, 3 Cascadia monospace,
2 Helvetica/sans; full map in `references/element-types.md`. Defaults differ by layer:
the upstream **engine** defaults to 5 (Excalifont), the element examples often choose 3
(monospace), and **this skill's scripts** default to 1 (Virgil). Set `fontFamily` explicitly
when it matters.

**Local rough SVG — preview only, not a deliverable path** (works on ANY `.excalidraw`,
including excalidraw.com hand-edited ones; uses roughjs + embedded Virgil, no network):

```bash
node "$SKILL_DIR/scripts/render-svg.mjs" in.excalidraw out.svg
```

It emits font fallback chains like `Virgil, 'Comic Sans MS', 'Segoe Print', cursive` —
CJK (and any glyph Virgil lacks) then renders with whatever the *viewing* machine has,
so the same file looks different per viewer. For SVG deliverables use the official-engine
export below, which embeds real fonts as data-URI `@font-face`.

Install pinned script dependencies once with `cd "$SKILL_DIR/scripts" && npm ci --ignore-scripts`; preview and verification commands live in [`setup.md`](setup.md).
(canvas fonts resolve offline from `fonts/`).

### Context hygiene & complementary tools

**Never Read whole `.excalidraw` files into the main context** (pattern from
davila7/claude-code-templates): a 14-element file is ~4k tokens, a 79-element file ~22k — over
90% is positioning/style noise. Delegate read/modify operations to a subagent that returns a
text-only summary (components + relationships), and apply edits with targeted scripts
(node/jq by element id) instead of Read + rewrite of the entire file.

Complementary toolchains — reach for them when the file-based loop isn't enough:

- **mcp-excalidraw-server** (`npx -y mcp-excalidraw-server`) — element-level canvas workbench:
  per-element CRUD, `describe` + `screenshot` so the agent SEES the live canvas, align/distribute,
  mermaid → excalidraw conversion, `.excalidraw` export. Best for long iterative drawing sessions;
  this skill stays best for hand-authored JSON + the offline render-and-validate loop.
- **axton-obsidian-visual-skills** — Obsidian-flavored output (`.md` scene embeds) and animated
  diagrams (draw-order animation via excalidraw-animate).
- **Official editors for hand-finish** — [excalidraw/excalidraw-vscode](https://github.com/excalidraw/excalidraw-vscode)
  (VS Code) or the excalidraw.com PWA (installable via Chrome, offline-capable); both edit the
  `.excalidraw` files this skill produces, with full official rendering.

**Font licenses**: embedded fonts are OFL 1.1 — [Virgil](https://github.com/excalidraw/virgil)
(`references/Virgil-LICENSE.md`, Ellinor Rapp) and **Excalifont** (`references/Excalifont-LICENSE.md`,
Copyright 2024 Excalidraw, incl. official unicode-range subsets). The full official
`dist/prod/fonts` tree is mirrored at `fonts/` (234 files, incl. Xiaolai CJK
fallback) so the render loop resolves every canvas font offline through the engine's own
`EXCALIDRAW_ASSET_PATH` mechanism. Unmodified embedding/redistribution permitted; keep the
license files alongside when redistributing.

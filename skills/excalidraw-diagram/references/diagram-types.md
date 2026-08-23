# Diagram Type Catalog

> Condensed from github/awesome-copilot `skills/excalidraw-diagram-generator`. Read when translating
> a natural-language request into a concrete plan: pick the type, extract the required parts, respect
> the count budgets. Cross-references arrowhead values in `element-types.md`.

## Intent → type mapping

| User intent / keywords | Diagram type |
|---|---|
| workflow, process, steps, procedure | Flowchart |
| relationships, connections, dependencies | Relationship |
| mind map, concepts, brainstorm, breakdown | Mind Map |
| architecture, system, components, modules | Architecture |
| data flow, data processing, transformation | Data Flow (DFD) |
| business process, swimlane, actors | Swimlane |
| class, inheritance, OOP, object model | Class |
| sequence, interaction, messages, timeline | Sequence |
| database, entity, data model | ER |

## Per-type extraction checklists, layout, budgets

### Flowchart
- **Extract**: sequential steps; decision points; start/end.
- **Layout**: ellipse start/end, diamond decisions, rectangle steps; "Yes" branch goes forward,
  "No" goes down.
- **Budget**: 3–10 steps (max 15).

### Relationship
- **Extract**: entities (name + optional description); relations (from → to + label).
- **Layout**: grid — `columns = ceil(sqrt(n))`, `x = startX + (i % columns) * hGap`,
  `y = startY + floor(i / columns) * vGap`.
- **Budget**: 3–8 entities (max 12).

### Mind Map
- **Extract**: central topic; main branches; sub-topics per branch.
- **Layout**: radial — `angle = 2π·i/n`, place level-1 on circle radius ≈ 280 (see also the
  Spacing Reference in SKILL.md merged additions). Lines, not arrows, for connections.
- **Budget**: 4–6 branches (max 8), 2–4 sub-topics each.

### Architecture
- **Extract**: components; groupings/zones; entry point; data stores.
- **Layout**: zones as dashed low-opacity containers; gateway/entry left or top; databases right
  or bottom.
- **Budget**: 3–8 entities (max 12).

### Data Flow (DFD)
- **Extract**: external entities; processes (transformations); data stores; flows.
- **Layout**: left → right; **data flow only — do not encode process order**.

### Swimlane
- **Extract**: actors/roles; activities per actor; handoffs.
- **Layout**: one lane per actor (dashed zone rectangles), label as free-standing text top-left;
  flow left-to-right inside lanes; arrows cross lanes on handoffs.

### Class
- **Extract**: classes with attributes and methods (+ visibility `+ - #`); relationships with
  multiplicity.
- **Layout**: rectangle per class, multi-line bound text.
- **Arrowheads** (see `element-types.md` for full enums): inheritance = solid +
  `triangle_outline`; implementation = dashed + `triangle_outline`; dependency = dashed;
  aggregation = solid + `diamond_outline`; composition = solid + `diamond`.

### Sequence
- **Extract**: participants; messages (sync/async/return); activations.
- **Layout**: participants 200px apart at top; dashed vertical lifelines; messages horizontal,
  ~60px vertical spacing; solid = sync request, dashed = async/response.

### ER
- **Extract**: entities with attributes; primary/foreign keys; cardinalities; junction entities
  for N:M.
- **Arrowheads**: use the `cardinality_*` / legacy `crowfoot_*` arrowheads from `element-types.md`.

## Complexity management

When the request exceeds the budget (>~15 components), propose a split before drawing:
high-level overview (≤8 components) + one detailed diagram per subsystem. Offer the high-level
view first.

## Element-count sanity

<20 elements total keeps a diagram legible; above that, prefer splitting or dropping containers
(see SKILL.md container discipline).

# Excalidraw Diagram: 60-second demo

This demo shows the invocation, deliverables and verification boundary. The checked-in scene is a deterministic reference fixture, not a model-quality result.

## 1. Ask the agent

```text
Use excalidraw-diagram to draw a login sequence. Deliver editable source and PNG.
```

For a technical diagram, provide the real actors, calls, events and failure branches. Unknown facts must remain labeled assumptions.

## 2. Expect these outputs

The agent must return:

1. an editable `.excalidraw` source scene;
2. requested SVG/PNG derivatives rendered from that scene;
3. scene hygiene, binding, style, overlap and render/export results;
4. a named visual-review result or an explicit hold;
5. an `excalidraw-diagram.receipt.v1` receipt.

Open the [reference architecture scene](../../benchmarks/excalidraw-diagram/ordinary-model-floor/fixtures/reference/reference.architecture.excalidraw) to inspect a real editable output shape.

## 3. Verify the development contract

From the repository root:

```bash
python3 benchmarks/excalidraw-diagram/ordinary-model-floor/benchmark.py check
python3 -m unittest tests.test_excalidraw_benchmark tests.test_excalidraw_renderer
```

After installing the locked render dependencies, export a scene through the official engine:

```bash
SKILL_DIR=/absolute/path/to/skills/excalidraw-diagram
SCENE=/absolute/path/to/diagram.excalidraw

cd "$SKILL_DIR/references"
uv run python "$SKILL_DIR/scripts/export-official-svg.py" \
  "$SCENE" "${SCENE%.excalidraw}.svg" \
  --png "${SCENE%.excalidraw}.official.png"
uv run python "$SKILL_DIR/scripts/check-handdrawn-style.py" "$SCENE"
uv run python "$SKILL_DIR/scripts/visual-check.py" \
  --scene "$SCENE" --artifact "${SCENE%.excalidraw}.svg"
```

The benchmark reference proves verifier wiring only. Model evidence requires one frozen attempt-1 artifact per case, identical prompt/runtime/time/tool access, deterministic gates and identified visual review.

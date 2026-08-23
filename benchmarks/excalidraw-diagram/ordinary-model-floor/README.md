# Ordinary-Model Floor v1 (excalidraw-diagram skill)

This benchmark measures one narrow product question: **can an ordinary coding
agent produce a usable hand-drawn Excalidraw diagram on attempt 1, without a
human repairing the scene JSON?** It is a delivery gate for the skill, not a
model leaderboard.

A run is `firstPassUsable` only when all three gates pass:

1. **Semantic** — every `required_texts` entry appears in a text element; every
   `required_flows` pair is drawn as an arrow whose start point sits on a box
   labeled with the from-term and whose end point sits on a to-term box
   (edge-to-edge, the skill's own routing contract).
2. **Deterministic** — style gate (roughness 1 / fontFamily 1), scene hygiene
   (`check-scene-hygiene.py`), and the overlap audit (`audit-overlaps.py`)
   all pass.
3. **Visual review** — an identified reviewer inspected the rendered artifact
   and reported `passed` with no defects. Use short defect tags (`clipping`,
   `node-overlap`, `label-overlap`, `unbalanced-whitespace`, `tofu`). A
   `skipped` review can never produce `firstPassUsable: true`. A
   renderer-valid but semantically wrong diagram is a failure; a visually
   pleasing diagram that fails deterministic validation is also a failure.

The checked-in reference fixture only proves the harness is wired correctly.
**Reference fixtures are not benchmark evidence** and must never be published
as model results.

## Suite

`manifest.json` holds five bounded tasks — layered architecture, approval
workflow, call sequence, data pipeline, retry lifecycle — each declaring
required texts and required flows. The model remains free to choose ids,
layout, and styling within the hand-drawn preset.

## Fair-run protocol

Every compared configuration must use the same prompt, the same skill tree,
the same time limit, and identical tool access. One complete agent invocation
is attempt 1; the candidate `.excalidraw` is frozen when the invocation ends.
No post-hoc edits — including human edits — before verification. Run candidate
generation from the installed skill the user actually has, not from a
development tree, and keep the harness/cases/prompts outside the model-visible
working tree so evaluation evidence cannot leak into exploration.

## Commands

```bash
cd /absolute/path/to/azhou-ai-hub/benchmarks/excalidraw-diagram/ordinary-model-floor
python3 benchmark.py check                          # suite integrity + fixture wiring

python3 benchmark.py verify \
  --case cases/layered-architecture.case.json \
  --candidate /path/to/candidate.excalidraw \
  --run /path/to/run.json                           # one receipt; exit 0/1/2

python3 benchmark.py record-failure \
  --case cases/layered-architecture.case.json --run /path/to/run.json --failure timeout

python3 benchmark.py report --results /path/to/results.jsonl   # aggregate matrix
```

`run.json` (written by the external runner after the invocation ends):

```json
{
  "schema_version": 1, "case_id": "layered-architecture",
  "agent": "agent-name", "model": "model-name", "attempt": 1,
  "visual_review": {"status": "passed", "reviewer": "reviewer-name", "defects": []}
}
```

`record-failure` reasons are allow-listed to `timeout`, `no_candidate`, and
`provider_error`; those receipts count toward matrix coverage but keep every
quality gate truthfully `not_run`. `report` separates operational, semantic,
deterministic, and visual-review failure clusters, and `evidenceEligible` is
true only when every case has exactly one attempt-1 receipt.

## Visual review honesty

Review the rendered artifact (or the `--png` from `export-official-svg.py`),
never the JSON alone: `passed` requires a non-empty reviewer identity,
`failed` lists concrete defects, `skipped` admits no capable reviewer was
available. Never upgrade a skipped review to a pass.

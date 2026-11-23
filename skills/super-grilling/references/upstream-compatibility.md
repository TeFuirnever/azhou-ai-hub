# Upstream compatibility

How this package relates to the upstream catalog, and how to replay the recorded deltas when the pin moves.

## Checkout vs installed upstream

Upstream, `grilling` is the interview primitive of the mattpocock/skills catalog: other skills and documents invoke it rather than writing another interview. Its `agents/openai.yaml` carries interface metadata only (`display_name: "Grilling"`, `short_description: "Stress-test thinking a round of questions at a time"`) and no invocation policy. This package imports the upstream `SKILL.md` only. The `agents/` directory is not imported: it is host-specific package identity this repository forbids copying.

## How each upstream key maps

- The upstream frontmatter has no `disable-model-invocation` key, and the upstream documents describe both entries (`docs/productivity/grilling.md` at the pin): "Type `/grilling`, or the agent reaches for it on its own when a task fits." That maps to `invocation: both`.
- The sub-agent instruction is kept as written, with one sentence added for harnesses that have no sub-agent.
- The two symbols in the round template stay in the prose template. They never enter the stage events, the receipt schema, paths, commands, or test names defined in [brand-layer](brand-layer.md).

## Delta replay map (for pin upgrades)

On a pin upgrade, fetch the new upstream `skills/productivity/grilling/`, then re-apply, in this order:

1. **GL1** — replace the upstream frontmatter with the neutral three-key contract; re-attach both upstream trigger sentences verbatim into the description, plus the renamed-from line, the Use-when clause, and the boundary with `super-brainstorming`.
2. **GL3** — re-insert the Azhou brand layer (the intro paragraph, identity anchor, motto, and Brand protocol section) immediately after the upstream H1 title, which this package adds above the body.
3. **GL2** — re-attach the sub-agent degradation sentence after the final sentence of the "Finding _facts_" paragraph.

Then re-record every upstream SHA-256 in [provenance](provenance.md), re-pin the retained upstream paragraphs and the full local digest in `tests/test_super_grilling.py`, and land the upgrade through a fresh exact-diff approval together with the `super-grill-me` re-pin. Never silently follow upstream main.

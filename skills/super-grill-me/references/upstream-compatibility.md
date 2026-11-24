# Upstream compatibility

How this package relates to the upstream catalog, and how to replay the recorded deltas when the pin moves.

## Checkout vs installed upstream

Upstream, `grilling` is the interview loop that other skills and documents invoke rather than writing another interview. `grill-me` is a one-line entry that calls `grilling` through the host's Skill tool with an explicit-only invocation policy (`disable-model-invocation: true`, `allow_implicit_invocation: false`). Each entry carries an `agents/openai.yaml` with interface metadata (`display_name: "Grill Me"` and `"Grilling"`). This package imports the two upstream `SKILL.md` files as one package. The `agents/` directories are not imported. They are host-specific package identity, which this repository forbids copying.

## Why one package

skill-standard §2 does not allow a package to depend on a sibling skill directory. The upstream pair is a forwarder and its target, so landing it as two packages would make one depend on the other. Merged, the entry and the interview travel together, and the protocol keeps one copy. Do not split this package again without changing that rule first.

## How each upstream key maps

- `name: grill-me` and `name: grilling` both map to `name: super-grill-me`. Both old names stay as compatibility triggers in the description.
- `disable-model-invocation: true` on grill-me is not carried over on its own. The merged package is `invocation: both`, which keeps what the upstream documents describe for the pair. The reader types the command on purpose, and the model reaches for the interview when a plan needs stress-testing.
- `Call the Skill tool with "grilling".` is not reproduced. This package carries the interview itself.
- The sub-agent instruction is kept as written, with one sentence added for harnesses that have no sub-agent.
- The two symbols in the round template stay in the prose template. They never enter the stage events, the receipt schema, paths, commands, or test names defined in [brand-layer](brand-layer.md).

## Delta replay map (for pin upgrades)

On a pin upgrade, fetch the new upstream `skills/productivity/grill-me/` and `skills/productivity/grilling/`, then re-apply, in this order:

1. Apply M1 and M2. Replace the upstream frontmatter with the neutral three-key contract. Re-attach both upstream trigger sentences verbatim into the description, plus the renamed-from line, the Use-when clause, and the boundary with `super-brainstorming`. Keep the interview in this package. If upstream changes what grill-me forwards to, record the new relation in [provenance](provenance.md).
2. Apply M4. Re-insert the Azhou brand layer: the intro paragraph, identity anchor, motto, Brand protocol section, and the nothing-named paragraph. The upstream file has no title, so the H1 `# Grill Me` sits above the body and the brand layer follows it.
3. Apply M3. Re-attach the sub-agent degradation sentence after the final sentence of the "Finding _facts_" paragraph.

Then re-record every upstream SHA-256 in [provenance](provenance.md), re-pin the retained upstream spans and the full local digest in `tests/test_super_grill_me.py`, and land the upgrade through a fresh exact-diff approval. Never silently follow upstream main.

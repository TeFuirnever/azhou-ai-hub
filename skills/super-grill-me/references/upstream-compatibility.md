# Upstream compatibility

How this package relates to the upstream catalog, and what to replay when the pin moves.

## Checkout vs installed upstream

Upstream, `grill-me` is one entry in the mattpocock/skills catalog: a one-line skill that calls the sibling `grilling` skill through the host's Skill tool. Its `agents/openai.yaml` carries interface metadata (`display_name: "Grill Me"`, `short_description: "Sharpen a plan through interview"`) and the policy `allow_implicit_invocation: false`. This package imports the upstream `SKILL.md` only. The `agents/` directory is not imported: it is host-specific package identity this repository forbids copying.

## How each upstream key maps

- `disable-model-invocation: true` and `allow_implicit_invocation: false` map to `invocation: user-invoked orchestrator`. The reader starts the skill on purpose and the model does not reach for it on its own. The upstream documents say the same (`docs/productivity/grill-me.md` at the pin): "You invoke this by typing `/grill-me`; the agent won't reach for it on its own."
- `Call the Skill tool with "grilling".` maps to the handoff in `SKILL.md`, which names `super-grilling` by its canonical name instead of issuing a host tool call.

## Delta replay map (for pin upgrades)

On a pin upgrade, fetch the new upstream `skills/productivity/grill-me/`, then:

1. Record the new upstream bytes and hashes in [provenance](provenance.md).
2. Re-apply G1 and G2 onto the new upstream entry. If upstream changes the body line, carry its new meaning into the handoff rather than the old text.
3. Re-pin the full local digest of `SKILL.md` in `tests/test_super_grill_me.py`.
4. Re-pin the sibling `super-grilling` package at the same upstream commit in the same change; the two are verified together.

Never silently follow upstream main.

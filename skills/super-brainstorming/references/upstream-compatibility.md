# Upstream compatibility

How this package relates to the upstream plugin, and how to replay the recorded deltas when the pin moves.

## Checkout vs installed upstream

Upstream, this skill is one skill inside the `obra/superpowers` plugin: an installer wires the whole plugin, sibling skills live beside it, and paths like `.superpowers/` are plugin conventions. This package imports exactly one upstream directory — `skills/brainstorming/`, eight files at the pinned commit — and nothing else: no installer, no plugin manifest, no sibling skills, no hooks.

## The planning handoff is deliberately unbound

Upstream hard-chains the step after design approval to its sibling `writing-plans` skill (both the ordered list and the closing line inside the `<HARD-GATE>`). This package rewrites both spots (delta D2): the approved design doc is handed to whatever planning workflow the reader chooses, and the skill invokes no sibling skill. This is what makes the package independently installable; do not reintroduce the upstream chain when replaying deltas.

## Session namespace

The companion keeps session state under `<project>/.superpowers/brainstorm/`. The upstream namespace is retained as-is (recorded maintainer decision, 2026-11-23): it is a data directory created at runtime, not an identity claim, and this repository gitignores `/.superpowers/` at its root. Renaming it to a local namespace would enlarge the delta against the upstream scripts without changing behavior.

## Delta replay map (for pin upgrades)

On a pin upgrade, fetch the new upstream `skills/brainstorming/` tree, then re-apply, in this order:

1. **D1** — replace the upstream frontmatter with the neutral three-key contract; re-attach every upstream trigger sentence verbatim into the description, plus the renamed-from line, Use-when clause, and capability carve.
2. **D2** — neutralize both `superpowers:writing-plans` references (ordered-list step 4; final `<HARD-GATE>` paragraph).
3. **D3** — neutralize the `docs/superpowers/specs/…` location in the `**Where it goes:**` paragraph.
4. **D4** — in `scripts/server.cjs`: keep branding/telemetry opt-in (`SUPERPOWERS_ENABLE_TELEMETRY`, `ENABLE_TELEMETRY`) with the off-by-default inversion and the empty-`brandMarkup()` guard; in `scripts/frame-template.html`: keep the neutral `<title>`. Re-apply both onto the new upstream file rather than keeping the old file.
5. **D5** — re-insert the harness note paragraph immediately before `**Launching the server by platform:**` in `visual-companion.md`.
6. **D6** — re-attach the builder-check provenance clause after the subagent fallback sentence.
7. **Azhou brand layer** — re-insert the Azhou brand layer (the intro paragraph, identity anchor, motto and Brand protocol section) immediately after the upstream H1 title, as recorded in the current `SKILL.md` lines 9-30.

Then re-record every upstream SHA-256 in [provenance](provenance.md), re-pin the retained segments and full local digests in `tests/test_super_brainstorming.py`, re-run the token simulation (upstream bytes may introduce new bare old-name tokens outside allowed surfaces), and land the upgrade through a fresh exact-diff approval. Never silently follow upstream main.

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

Then re-record every upstream SHA-256 in [provenance](provenance.md), re-pin the anchor-span digests and the full local digests in `tests/test_super_brainstorming.py`, re-run the token simulation (upstream bytes may introduce new bare old-name tokens outside allowed surfaces), and land the upgrade through a fresh exact-diff approval. Never silently follow upstream main. Re-check the accepted notes below against the new pin and drop each one the new upstream has fixed.

## Accepted upstream-behavior notes at the pin

Four review findings reported against the packaged scripts (2026-11-24) sit in bytes identical to the pin — `scripts/start-server.sh`, `scripts/stop-server.sh` and `scripts/helper.js` are vendored byte-for-byte, and the `scripts/server.cjs` site lies outside the D4 hunks. They were accepted as upstream-behavior notes rather than patched here: a hub-side fix would turn upstream bytes into unrecorded deltas and move the defect out of upstream's view. Upstream owns this surface, and a future re-pin at a fixed upstream commit carries the fixes. Each item was read in the packaged source before being recorded.

| Where at the pin | Behavior | Hub-layer guidance |
|---|---|---|
| `scripts/start-server.sh`, option parsing | A value-taking option given without its value (`--project-dir`, `--host`, `--url-host`, `--idle-timeout-minutes`) leaves the argument unconsumed because `shift 2` fails, so the launcher loops until it is killed instead of reporting a usage error. | Always pass a value with these options. A launch command that never returns is this loop: terminate it and correct the invocation. |
| `scripts/stop-server.sh`, cleanup predicate | Every session directory whose path starts with `/tmp/` is deleted on stop, including a project-backed session when `--project-dir` itself lives under `/tmp`, so its mockups do not survive the stop. | Keep `--project-dir` outside `/tmp` when mockups must persist. |
| `scripts/helper.js`, `brainstorm.choice()` | The explicit-choice message carries the selection in a `value` field, while the server appends only events with a truthy `choice` field to the `state/events` feedback file, so an explicit choice reaches the server but never the file the agent reads. | Read selections from click events, or treat the feedback file as incomplete for explicit choices. |
| `scripts/server.cjs`, `/files/` handler | The request path is used as-is (the server never percent-decodes it), so an asset name containing spaces or non-ASCII characters is looked up under its encoded spelling and returns 404. | Reference assets by names without spaces or non-ASCII characters. |
